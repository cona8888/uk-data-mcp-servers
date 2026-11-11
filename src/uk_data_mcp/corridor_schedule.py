"""Offline CSV companion for a corridor evidence report; never fetch or infer missing data."""
import argparse
import csv
import os
import tempfile
from pathlib import Path

from .corridor_contract import validate_corridor_report
from .json_safety import loads_json

COLUMNS = ('row_type', 'layer', 'feature_id', 'label', 'relation', 'event', 'start_m', 'end_m',
           'nearest_offset_m', 'layer_status', 'scan_complete', 'matched_examined',
           'more_matches_than_shown', 'contact_count', 'contacts_truncated', 'source_page',
           'jurisdiction_status', 'inventory_complete')


def safe(value):
    if isinstance(value, str) and (value.startswith(('\t', '\n', '\r')) or
                                   value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def write_schedule(report, stream):
    validate_corridor_report(report)
    jurisdiction = report.get('jurisdiction', {}).get('status', 'unverified_legacy')
    status_rows, event_rows = [], []
    for layer, group in report['results'].items():
        common = dict(jurisdiction_status=jurisdiction, inventory_complete=False, layer=layer, layer_status=group['status'], source_page=group['source_page'],
                      scan_complete=group.get('candidate_scan_complete'),
                      matched_examined=group.get('matched_examined'),
                      more_matches_than_shown=group.get('more_matches_than_shown'))
        status_rows.append(dict(row_type='layer_summary', **common))
        for feature in group['data']:
            contacts = feature.get('centreline_contacts')
            if not isinstance(contacts, dict):
                raise ValueError('This report predates the contact schedule. Re-run corridor_screen.')
            attrs = feature.get('attributes', {})
            label = next((attrs[k] for k in ('wd24nm', 'reference', 'name', 'asset_name',
                          'assetname', 'common_name', 'collision_index') if attrs.get(k)), '')
            base = dict(**common, feature_id=feature['source_feature_id'], label=label,
                        relation=contacts['relation'], nearest_offset_m=feature['offset_m'],
                        contact_count=contacts['count'], contacts_truncated=contacts['truncated'])
            if contacts['events']:
                for event in contacts['events']:
                    event_rows.append(dict(**base, row_type='contact', event=event['kind'],
                                           start_m=event['start_m'], end_m=event['end_m']))
            elif contacts['relation'] == 'nearby_only' and contacts['count'] == 0:
                event_rows.append(dict(**base, row_type='nearest_only', event='nearest_locator',
                                       start_m=feature['chainage_m'], end_m=None))
            else:
                raise ValueError('Inconsistent contact schedule in report.')
        for feature in group.get('boundary_candidates', []):
            event_rows.append(dict(**common, row_type='boundary_review_only',
                feature_id=feature['source_feature_id'], label='Outside strict radius; review source position',
                relation='nearby_only', event='threshold_review_not_a_match',
                start_m=feature['chainage_m'], nearest_offset_m=feature['offset_m'],
                contact_count=0, contacts_truncated=False))
    event_rows.sort(key=lambda r: (r['start_m'], r['layer'], r['feature_id']))
    if not report['results']:
        status_rows.append(dict(row_type='report_summary', layer_status='error',
                                jurisdiction_status=jurisdiction, inventory_complete=False,
                                scan_complete=False, label=report['error'].get('message', 'Search not run')))
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    for row in [*status_rows, *event_rows]:
        writer.writerow({k: safe(v) for k, v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.report.resolve() == args.output.resolve():
        parser.error('Input and output must differ.')
    # Do not truncate a previous export on invalid input.
    import io

    buf = io.StringIO(newline='')
    try:
        with args.report.open('rb') as f:
            raw = f.read(16_000_001)
        if len(raw) > 16_000_000:
            raise ValueError('Report exceeds 16 MB.')
        report = loads_json(raw)
        write_schedule(report, buf)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                    dir=args.output.parent, delete=False) as f:
                name = f.name
                f.write(buf.getvalue())
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, args.output)
        finally:
            if name is not None and os.path.exists(name):
                os.unlink(name)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(2, f'Cannot export corridor schedule: {exc}\n')


if __name__ == '__main__':
    main()
