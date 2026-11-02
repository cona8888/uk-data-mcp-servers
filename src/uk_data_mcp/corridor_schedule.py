"""Offline CSV companion for a corridor evidence report; never fetch or infer missing data."""
import argparse
import csv
import json
from pathlib import Path

COLUMNS = ('row_type', 'layer', 'feature_id', 'label', 'relation', 'event', 'start_m', 'end_m',
           'nearest_offset_m', 'layer_status', 'scan_complete', 'matched_examined',
           'more_matches_than_shown', 'contact_count', 'contacts_truncated', 'source_page')


def safe(value):
    if isinstance(value, str) and (value.startswith(('\t', '\n', '\r')) or
                                   value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def write_schedule(report, stream):
    if report.get('kind') != 'civil_corridor_screen' or not isinstance(report.get('results'), dict):
        raise ValueError('Expected a civil_corridor_screen report.')
    status_rows, event_rows = [], []
    for layer, group in report['results'].items():
        common = dict(layer=layer, layer_status=group['status'], source_page=group['source_page'],
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
    event_rows.sort(key=lambda r: (r['start_m'], r['layer'], r['feature_id']))
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
        report = json.loads(args.report.read_text(encoding='utf-8'))
        write_schedule(report, buf)
        args.output.write_text(buf.getvalue(), encoding='utf-8', newline='')
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(2, f'Cannot export corridor schedule: {exc}\n')


if __name__ == '__main__':
    main()
