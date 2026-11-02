"""Check the fresh demo report and export its contact schedule. No additional provider calls."""
import json
from pathlib import Path

from uk_data_mcp.corridor_schedule import write_schedule


def check(directory):
    report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    length = report['metric']['length_m']
    summary = {'implementation_commit': report['implementation_commit'],
               'retrieved_at_utc': report['retrieved_at_utc'], 'length_m': length,
               'radius_m': report['request']['radius_m'], 'layers': {}}
    for layer, group in report['results'].items():
        summary['layers'][layer] = {
            'matched_examined': group['matched_examined'], 'shown': len(group['data']),
            'candidate_scan_complete': group['candidate_scan_complete'],
            'source_page': group['source_page'], 'status': group['status'], 'contacts_among_shown': 0}
        for item in group['data']:
            contacts = item['centreline_contacts']
            assert bool(contacts['count']) == item['centreline_intersects']
            assert contacts['truncated'] == (contacts['count'] > len(contacts['events']))
            assert all(0 <= e['start_m'] <= e['end_m'] <= length + .001 for e in contacts['events'])
            if item['geometry_type'] in ('Polygon', 'MultiPolygon'):
                assert 0 <= contacts['covered_length_m'] <= length + .001
                assert abs(contacts['interior_length_m'] + contacts['boundary_length_m'] -
                           contacts['covered_length_m']) <= .00101
            summary['layers'][layer]['contacts_among_shown'] += contacts['count']
            if layer == 'communities':
                label = item['attributes'].get('wd24nm', item['source_feature_id'])
                print('WARD', label, contacts, flush=True)
            elif layer == 'flood_defences' and contacts['count']:
                print('DEFENCE', item['source_feature_id'], contacts, flush=True)
    with (directory / 'chainages.csv').open('w', newline='', encoding='utf-8') as out:
        write_schedule(report, out)
    (directory / 'chainage-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


if __name__ == '__main__':
    check(Path('corridor-evidence'))
