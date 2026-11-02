"""Local, aggregate-only reader for the historic Yorkshire Water meter CSVs."""

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .public_catalogue import SOURCES

FIELDS = {'POSTAL_TOWN', 'READING_SOURCE', 'METER_KEY', 'GROSS_CONSUMPTION', 'READING_START_DATE', 'READING_END_DATE'}
MIN_METERS = 10


def day(raw):
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S'):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError('unrecognised date')


def summarize(stream):
    reader = csv.DictReader(stream)
    names = [v.strip().lstrip('\ufeff').upper() for v in (reader.fieldnames or [])]
    # The published data dictionary uses GROSS_COMSUMPTION in some editions.
    names = ['GROSS_CONSUMPTION' if v == 'GROSS_COMSUMPTION' else v for v in names]
    if not FIELDS.issubset(names) or len(set(names)) != len(names):
        raise ValueError('Unrecognised or ambiguous meter CSV headers; check the publisher guidance.')
    reader.fieldnames = names
    groups = {}
    invalid = 0
    for row in reader:
        try:
            if None in row or any(not (row.get(k) or '').strip() for k in FIELDS):
                raise ValueError('missing field')
            town, source, key = [row[k].strip() for k in ('POSTAL_TOWN','READING_SOURCE','METER_KEY')]
            if any(len(x)>120 for x in (town, source, key)):
                raise ValueError('oversized label')
            start, end = day(row['READING_START_DATE']), day(row['READING_END_DATE'])
            days = (end-start).days
            volume = Decimal(row['GROSS_CONSUMPTION'].strip())
            if days <= 0 or not volume.is_finite() or volume < 0 or volume > Decimal('1e9') or (volume and volume.adjusted() < -12):
                raise ValueError('invalid interval or volume')
        except (ValueError, InvalidOperation):
            invalid += 1
            continue
        group = (town.upper(), source, end.year)
        if group not in groups:
            if len(groups) >= 20000:
                raise ValueError('Too many groups: inspect the file schema.')
            groups[group] = [Decimal(0), 0, 0, set()]
        bucket = groups[group]
        bucket[0] += volume
        bucket[1] += days
        bucket[2] += 1
        if len(bucket[3]) < MIN_METERS:
            bucket[3].add(key)
    output = []
    for (town, source, year), (volume, days, n, keys) in sorted(groups.items()):
        if len(keys) >= MIN_METERS:
            output.append({'town':town, 'reading_source_as_published':source, 'interval_end_year':year,
                           'interval_count':n, 'recorded_meter_days':days, 'gross_m3':str(volume),
                           'litres_per_recorded_meter_day':round(float(1000*volume/days), 3)})
    return {'kind':'local_aggregate', 'source':SOURCES['meter_yorkshire'], 'groups':output,
            'excluded_invalid_intervals':invalid, 'minimum_distinct_meters_per_output_group':MIN_METERS,
            'attribution':'Contains derived Yorkshire Water customer meter data. Check the file-specific licence: the original Calderdale catalogue states OGL; the Data Mill North publisher page links to Creative Commons Attribution.',
            'method':'Group complete input intervals by end year, postal town and reading source. Ratio of summed volumes to summed interval-days, not an arithmetic mean of daily rates. Not population-weighted or leakage. Identifiers never exported. Completeness, overlap and duplicate intervals are not audited; use one original file per run. Small groups are not returned.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path, help='A single locally downloaded publisher CSV (not a URL).')
    parser.add_argument('--encoding', default='utf-8-sig', choices=['utf-8-sig','cp1252'])
    args = parser.parse_args()
    try:
        with args.csv_file.open('rb') as raw:
            digest = hashlib.file_digest(raw, 'sha256').hexdigest()
            raw.seek(0)
            with io.TextIOWrapper(raw, encoding=args.encoding, newline='') as text:
                result = summarize(text)
        result['input_sha256'] = digest
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
