"""Optional reproducible HPI alternative to the live linked-data service.

Operator-only preparation. Never silently choose an older vintage for a failed live request.
"""

import asyncio
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone

import httpx

from . import civil_tables as t

EDITION = '2025-01'
KEY = 'hpi-' + EDITION
LANDING = 'https://www.gov.uk/government/statistical-data-sets/uk-house-price-index-data-downloads-january-2025'
URL = 'https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/Average-prices-2025-01.csv'
MAX = 20_000_000


def index_file(raw):
    if not 0 < len(raw) <= MAX:
        raise ValueError('Unexpected HPI file size.')
    import csv

    rows = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    fields = rows.fieldnames or []
    cols = {re.sub(r'[^a-z0-9]', '', field.casefold()):field for field in fields}
    if len(cols) != len(fields) or not {'areacode','date','averageprice','regionname'} <= cols.keys():
        raise ValueError('Unrecognised HPI average-price table: ' + str(fields[:8]))
    areas = {}
    for row in rows:
        code = row[cols['areacode']]
        if None in row or None in row.values():
            raise ValueError('Malformed HPI row.')
        if not re.fullmatch(r'(?:E0[6789]|W06|S12|N09)\d{6}', code):
            continue  # The release also has different geography levels, never join by name.
        date = row[cols['date']].strip()
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', date):
            month = datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m')
        elif re.fullmatch(r'\d{4}-\d{2}(-\d{2})?', date):
            month = datetime.strptime(date[:7], '%Y-%m').strftime('%Y-%m')
        else:
            raise ValueError('Unexpected HPI date: ' + date[:20])
        if month > EDITION:
            raise ValueError('Price month newer than the selected publication.')
        price = row[cols['averageprice']].strip()
        if price and not re.fullmatch(r'\d+(?:\.\d+)?', price):
            raise ValueError('Unexpected HPI price in the source file.')
        area = areas.setdefault(code, {'name':row[cols['regionname']], 'months':{}})
        if month in area['months']:
            raise ValueError('Duplicate area/month in the HPI file.')
        area['months'][month] = price or None
    if not areas:
        raise ValueError('Empty HPI district table.')
    return {'schema':1, 'edition':EDITION, 'url':URL, 'landing_page':LANDING,
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_sha256':hashlib.sha256(raw).hexdigest(), 'areas':areas,
            'licence':t.OGL, 'attribution':'Contains HM Land Registry data © Crown copyright and database right 2025. Open Government Licence v3.0.'}


async def prepare(directory=None):
    async with asyncio.timeout(120), httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        async with client.stream('GET', URL) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes(65536):
                if len(chunk) + len(raw) > MAX:
                    raise ValueError('HPI release exceeds the byte cap.')
                raw.extend(chunk)
    index = index_file(raw)
    directory = directory or t.root()
    directory.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index, ensure_ascii=False, separators=(',', ':')).encode()
    if len(payload) > MAX:
        raise ValueError('Oversized HPI index.')
    f = tempfile.NamedTemporaryFile(dir=directory, delete=False)
    try:
        with f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(f.name, directory / (KEY+'.json'))
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)
    return {k:v for k,v in index.items() if k != 'areas'} | {'area_count':len(index['areas'])}


def record(code, month, directory=None):
    if not re.fullmatch(r'[A-Z]\d{8}',code) or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',month):
        raise ValueError('Expected an area code and YYYY-MM.')
    if month > EDITION:
        return {'status':'error','data':[], 'error':{'code':'outside_edition'}, 'edition':EDITION}
    try:
        with ((directory or t.root()) / (KEY+'.json')).open('rb') as f:
            raw = f.read(MAX+1)
    except FileNotFoundError:
        return {'status':'error','data':[], 'error':{'code':'not_prepared'}, 'operator_action':'uk-civil-data prepare '+KEY}
    if len(raw)>MAX:
        raise ValueError('Invalid HPI cache size.')
    index = json.loads(raw)
    if (not isinstance(index,dict) or index.get('schema') != 1 or index.get('edition') != EDITION
            or index.get('url') != URL or not isinstance(index.get('areas'), dict)
            or not re.fullmatch(r'[a-f0-9]{64}', str(index.get('source_sha256')))):
        raise ValueError('Invalid HPI cache. Prepare the named edition again.')
    source = {k:v for k,v in index.items() if k != 'areas'}
    area = index['areas'].get(code)
    price = area['months'].get(month) if area else None
    if price is None:
        return {'status':'empty', 'data':[], 'source':source,'area_code':code,'month':month, 'note':'No published price for this code/month; not zero.'}
    return {'status':'ok', 'source':source, 'data':[{'gss_code':code,'area_name':area['name'],'period':month,
            'averagePrice':float(price),'as_published':price,'unit':'GBP'}],
            'warning':'Fixed January 2025 publication, not a current vintage or a transaction. Do not silently compare editions.'}
