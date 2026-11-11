"""Explicit bulk preparation for official, aggregate local-authority tables.

Only a local CLI operator can fetch the allowlisted editions. MCP accepts neither
paths nor URLs, performs no bulk requests and cannot modify a prepared snapshot.
"""

import asyncio
import csv
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .cache_integrity import cache_error, seal, validate_table
from .json_safety import loads_json

CENSUS = {'ts001': ('Usual residents by residence type', 'people'),
          'ts041': ('Households', 'households'),
          'ts045': ('Car or van availability', 'households'),
          'ts061': ('Method of travel to work', 'people in employment aged 16 and over'),
          'ts066': ('Economic activity status', 'usual residents aged 16 and over')}
YEARS = (2024, 2025)
DATASETS = (*CENSUS, *(f'stats19-{year}' for year in YEARS))
NOMIS = 'https://www.nomisweb.co.uk/output/census/2021/'
DFT = 'https://data.dft.gov.uk/road-accidents-safety-data/'
CENSUS_GUIDE = 'https://www.nomisweb.co.uk/census/2021/bulk'
DFT_GUIDE = 'https://www.gov.uk/government/statistical-data-sets/road-safety-open-data'
OGL = 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'
EW = re.compile(r'(?:E0[6789]|W06)\d{6}\Z')
GB = re.compile(r'(?:E0[6789]|W06|S12)\d{6}\Z')
CAP = 45_000_000  # Largest supported annual CSV is ~20 MB; refuse a historical bulk dump.
INDEX_CAP = 8_000_000


def root():
    return Path(os.environ.get('UK_CIVIL_CACHE') or (Path.home() / '.cache' / 'uk-civil-data'))


def address(key):
    if key not in DATASETS:
        raise ValueError('Choose a named edition: ' + ', '.join(DATASETS))
    if key in CENSUS:
        return NOMIS + f'census2021-{key}.zip'
    return DFT + f'dft-road-casualty-statistics-collision-{key[-4:]}.csv'


def dicts(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Missing or duplicate CSV headers.')
    return reader


def census_rows(key, raw):
    """Read just the LTLA member, never extract the archive to disk."""
    suffix = f'census2021-{key}-ltla.csv'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = [m for m in z.infolist() if m.filename.rsplit('/', 1)[-1].lower() == suffix]
        if len(members) != 1 or not 0 < members[0].file_size <= 2_000_000:
            raise ValueError('Expected one bounded lower-tier local-authority table: ' + suffix)
        with z.open(members[0]) as member:
            payload = member.read(2_000_001)
        if len(payload) != members[0].file_size or len(payload) > 2_000_000:
            raise ValueError('Unexpected census member length.')
    reader = dicts(payload)
    headers = {h.strip().casefold(): h for h in reader.fieldnames}
    wanted = {'date', 'geography', 'geography code'}
    if not wanted <= headers.keys():
        raise ValueError('Unknown Nomis LTLA schema: ' + str(reader.fieldnames[:5]))
    columns = [h for h in reader.fieldnames if h.strip().casefold() not in wanted]
    if not columns or len(columns) > 100:
        raise ValueError('Unexpected number of census indicators.')
    areas = {}
    for row in reader:
        area = row[headers['geography code']]
        if (None in row or None in row.values() or not EW.fullmatch(area) or area in areas
                or row[headers['date']].strip() != '2021' or not row[headers['geography']].strip()):
            raise ValueError('Invalid, duplicate or wrong-period census geography.')
        cells = {}
        for column in columns:
            original = row[column].strip()
            cells[column] = {'value': int(original) if re.fullmatch(r'\d{1,12}', original) else None,
                             'as_published': original}
        areas[area] = {'area_name': row[headers['geography']], 'observations': cells}
    metadata = {'provider': 'Office for National Statistics via Nomis', 'guide': CENSUS_GUIDE,
                'table': key.upper(), 'subject': CENSUS[key][0], 'unit': CENSUS[key][1],
                'reference_period': '2021-03-21', 'geography': 'England and Wales, LTLA as published',
                'member': members[0].filename, 'member_sha256': hashlib.sha256(payload).hexdigest(),
                'warnings': ['Census-day snapshot, not current demand; statistical disclosure control applies.',
                             'The published total overlaps its components. Never sum the total with its breakdown.',
                             'Keep the original census geography; do not silently transfer boundary changes.']}
    if key == 'ts061':
        metadata['warnings'].append('Travel to work at the pandemic-era census is not current travel demand.')
    return areas, metadata


def collision_rows(key, raw):
    reader = dicts(raw)
    needed = {'collision_index', 'collision_year', 'local_authority_ons_district', 'collision_severity'}
    if not needed <= set(reader.fieldnames):
        raise ValueError('Expected the DfT collision table, not a casualty or vehicle table.')
    year = key[-4:]
    seen, groups = set(), {}
    unassigned = 0
    labels = {'1': 'fatal', '2': 'serious', '3': 'slight'}
    for row in reader:
        ident = row['collision_index']
        if (None in row or None in row.values() or not ident or ident in seen
                or row['collision_year'] != year):
            raise ValueError('Duplicate/missing collision ID, malformed row or wrong year.')
        seen.add(ident)
        area = row['local_authority_ons_district'].strip()
        if not GB.fullmatch(area):
            unassigned += 1
            continue
        count = groups.setdefault(area, Counter())
        count[labels.get(row['collision_severity'], 'unknown')] += 1
    areas = {code: {'reported_injury_collisions': sum(n.values()),
                    'by_reported_collision_severity': {label: n[label] for label in (*labels.values(), 'unknown')}}
             for code, n in groups.items()}
    return areas, {'provider': 'Department for Transport', 'guide': DFT_GUIDE, 'table': 'STATS19 collisions',
                   'reference_period': year, 'unit': 'collisions', 'geography': 'Great Britain; ONS district in source',
                   'source_records': len(seen), 'records_without_usable_district': unassigned,
                   'warnings': ['Police-reported personal-injury collisions on public roads only. Not all crashes or all live incidents.',
                                'Counts are of events, not casualties, vehicles, risk rates or severity-adjusted estimates.',
                                'No exposure denominator is supplied. Northern Ireland uses separate PSNI data.']}


def from_bytes(key, raw):
    url = address(key)
    if not 0 < len(raw) <= CAP:
        raise ValueError('Source outside the allowed byte budget.')
    areas, metadata = census_rows(key, raw) if key in CENSUS else collision_rows(key, raw)
    if not areas:
        raise ValueError('No valid local-authority records; previous cache was not replaced.')
    index = {'schema': 2, 'dataset': key, 'url': url, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'licence': OGL,
            'attribution': metadata['provider'] + '; contains public sector information licensed under the Open Government Licence v3.0.',
            'area_count': len(areas), **metadata, 'areas': areas}
    seal(index)
    validate_table(index, key, url, key in CENSUS, EW if key in CENSUS else GB)
    return index


async def download(key):
    """Fixed HTTPS URLs, no redirects or auth; bound decoded bytes and wall time."""
    url = address(key)
    async with asyncio.timeout(120), httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        async with client.stream('GET', url) as r:
            r.raise_for_status()
            expected = r.headers.get('content-length', '')
            if expected.isdigit() and int(expected) > CAP:
                raise ValueError('Published file exceeds supported size.')
            out = bytearray()
            async for chunk in r.aiter_bytes(65536):
                if len(out) + len(chunk) > CAP:
                    raise ValueError('Download exceeds supported size.')
                out.extend(chunk)
            return bytes(out)


def store(index, directory):
    key = index['dataset']
    validate_table(index, key, address(key), key in CENSUS, EW if key in CENSUS else GB)
    content = json.dumps(index, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if len(content) > INDEX_CAP:
        raise ValueError('Index exceeds size budget.')
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, directory / (key + '.json'))
    finally:
        temp.unlink(missing_ok=True)


async def prepare(key, directory=None):
    index = from_bytes(key, await download(key))
    store(index, directory or root())
    return {k: v for k, v in index.items() if k != 'areas'}


def area_record(key, code, directory=None):
    url = address(key)
    if not isinstance(code, str) or not re.fullmatch(r'[A-Z]\d{8}', code):
        raise ValueError('Use a nine-character GSS code, e.g. E08000025; not a postcode or place name.')
    if not (EW if key in CENSUS else GB).fullmatch(code):
        return {'status': 'error', 'error': {'code': 'unsupported_geography'}, 'dataset': key,
                'area_code': code, 'source_url': url, 'data': [], 'note': 'Not covered by this table; do not report zero.'}
    p = (directory or root()) / (key + '.json')
    try:
        with p.open('rb') as f:
            content = f.read(INDEX_CAP + 1)
    except FileNotFoundError:
        return {'status': 'error', 'error': {'code': 'not_prepared'}, 'dataset': key, 'data': [],
                'source_url': url, 'operator_action': f'uk-civil-data prepare {key}'}
    try:
        if len(content) > INDEX_CAP:
            raise ValueError('Invalid cache size.')
        obj = loads_json(content, max_nodes=2_000_000)
        validate_table(obj, key, url, key in CENSUS, EW if key in CENSUS else GB)
    except (ValueError, TypeError, KeyError) as exc:
        return cache_error(key, str(exc))
    areas = obj.pop('areas')
    if code not in areas:
        return {'status': 'empty', 'area_code': code, 'data': [], 'source': obj,
                'note': 'No row for this code in this edition. Missing does not mean zero.'}
    return {'status': 'ok', 'area_code': code, 'source': obj, 'data': [areas[code]]}
