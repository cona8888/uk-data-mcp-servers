"""One semantic contract for saved corridor evidence and every export.

This checks internal consistency, not the truth of editable records. Historical
1.0 reports retain an explicit unverified-jurisdiction label; they gain no new
coverage assurance by being exported with a newer program.
"""

import math

from .corridor_chainage import EVENT_LIMIT
from .json_safety import validate_json_tree

TOL = 0.002  # Output rounding only; not an engineering positional tolerance.
KINDS = {'point_contact', 'line_overlap', 'area_interior', 'area_boundary'}
RELATIONS = {'nearby_only', 'point_contact', 'linear_overlap', 'interior_traversed',
             'boundary_followed', 'boundary_touch'}
STATES = {'ok', 'empty', 'partial', 'error', 'not_applicable'}


def require(condition, message):
    if not condition:
        raise ValueError('Invalid corridor report: ' + message)


def number(value, low, high, name):
    require(type(value) in (int, float) and math.isfinite(value)
            and low <= value <= high, name + ' is outside its finite bounds')
    return value


def count(value, name):
    require(type(value) is int and 0 <= value <= 1_000_000, name + ' is not a non-negative integer')
    return value


def validate_contacts(feature, length, radius):
    chainage = number(feature.get('chainage_m'), 0, length + TOL, 'nearest chainage')
    offset = number(feature.get('offset_m'), 0, radius + TOL, 'offset')
    c = feature.get('centreline_contacts')
    require(isinstance(c, dict), 'report predates the contact schedule; rerun corridor_screen')
    require(c.get('relation') in RELATIONS, 'unrecognised contact relation')
    n = count(c.get('count'), 'contact count')
    events = c.get('events')
    require(isinstance(events, list) and len(events) <= EVENT_LIMIT, 'invalid event list')
    require(type(c.get('truncated')) is bool, 'truncation flag missing')
    require((n == len(events) and not c['truncated']) or
            (n > len(events) == EVENT_LIMIT and c['truncated']), 'count and truncation disagree')
    require((n == 0) == (c['relation'] == 'nearby_only'), 'nearby-only relation contradicts contacts')
    if n:
        require(offset == 0, 'a centreline contact has a non-zero offset')
    if 'centreline_intersects' in feature:
        require(type(feature['centreline_intersects']) is bool
                and feature['centreline_intersects'] == bool(n), 'intersection flag contradicts contacts')
    previous = None
    spans = {}
    points = set()
    for e in events:
        require(isinstance(e, dict) and e.get('kind') in KINDS, 'invalid event kind')
        a = number(e.get('start_m'), 0, length + TOL, 'event start')
        b = number(e.get('end_m'), a, length + TOL, 'event end')
        require((a == b) if e['kind'] == 'point_contact' else (a < b), 'invalid event interval')
        order = (a, b, e['kind'])
        require(previous is None or order > previous, 'events duplicated or not in route order')
        previous = order
        if e['kind'] == 'point_contact':
            require(a not in points, 'duplicate point contact')
            points.add(a)
        else:
            last = spans.get(e['kind'])
            require(last is None or a > last, 'unmerged or overlapping same-kind intervals')
            spans[e['kind']] = b
    area = feature.get('geometry_type') in ('Polygon', 'MultiPolygon')
    has_area_fields = any(k in c for k in ('interior_length_m', 'boundary_length_m', 'covered_length_m'))
    area = area or has_area_fields
    if area:
        require(all(e['kind'] != 'line_overlap' for e in events), 'polygon reported as a line overlap')
        interior = number(c.get('interior_length_m'), 0, length + TOL, 'interior length')
        edge = number(c.get('boundary_length_m'), 0, length + TOL, 'boundary length')
        covered = number(c.get('covered_length_m'), 0, length + TOL, 'covered length')
        require(abs(interior + edge - covered) <= TOL, 'polygon lengths do not reconcile')
        sums = {kind: sum(e['end_m'] - e['start_m'] for e in events if e['kind'] == kind)
                for kind in ('area_interior', 'area_boundary')}
        for value, kind in ((interior, 'area_interior'), (edge, 'area_boundary')):
            require(sums[kind] <= value + TOL, 'shown interval lengths exceed total')
            if not c['truncated']:
                require(abs(value - sums[kind]) <= TOL, 'event lengths contradict polygon total')
        # The relation uses unrounded measures. Submillimetre positive spans may
        # legitimately have a displayed length of zero.
        inside = interior > 0 or any(e['kind'] == 'area_interior' for e in events)
        boundary = edge > 0 or any(e['kind'] == 'area_boundary' for e in events)
        if not c['truncated']:
            expected = ('nearby_only' if n == 0 else 'interior_traversed' if inside
                        else 'boundary_followed' if boundary else 'boundary_touch')
            require(c['relation'] == expected, 'polygon relation contradicts events')
        if 'centreline_length_in_area_m' in feature:
            require(feature['centreline_length_in_area_m'] == covered, 'traversal length disagrees')
    else:
        require(all(e['kind'] not in ('area_interior', 'area_boundary') for e in events),
                'non-polygon has area events')
        require(c['relation'] in ('nearby_only', 'point_contact', 'linear_overlap'), 'non-polygon relation')
        if not c['truncated']:
            expected = ('nearby_only' if n == 0 else 'linear_overlap'
                        if any(e['kind'] == 'line_overlap' for e in events) else 'point_contact')
            require(c['relation'] == expected, 'linear relation contradicts events')
    return chainage


def validate_corridor_report(report):
    validate_json_tree(report)
    require(isinstance(report, dict) and report.get('kind') == 'civil_corridor_screen', 'wrong kind')
    require(report.get('schema_version') in ('1.0', '1.1'), 'unsupported schema version')
    require(report.get('inventory_complete', False) is False, 'inventory completeness is not established')
    groups = report.get('results')
    require(isinstance(groups, dict), 'results must be an object')
    jurisdiction = report.get('jurisdiction', {})
    require(isinstance(jurisdiction, dict), 'invalid jurisdiction block')
    if not groups:
        require(report.get('status') == 'error' and isinstance(report.get('error'), dict),
                'missing results must be an explicit failure')
        return report
    if report['schema_version'] == '1.1':
        require(jurisdiction.get('status') == 'verified', 'coverage was not verified')
        require(jurisdiction.get('requests') and isinstance(jurisdiction['requests'], list),
                'jurisdiction has no request evidence')
    m, request = report.get('metric'), report.get('request')
    require(isinstance(m, dict) and m.get('crs') == 'EPSG:27700', 'metric CRS is missing')
    require(isinstance(request, dict), 'request missing')
    length = number(m.get('length_m'), 1, 20000, 'route length')
    radius = number(request.get('radius_m'), 1, 2000, 'radius')
    vertices = m.get('route_bng_m')
    require(isinstance(vertices, list) and 2 <= len(vertices) <= 256, 'route vertices missing')
    for p in vertices:
        require(isinstance(p, list) and len(p) == 2, 'invalid route vertex')
        number(p[0], 0, 700000, 'easting')
        number(p[1], 0, 1300000, 'northing')
    measured = sum(math.dist(a, b) for a, b in zip(vertices, vertices[1:]))
    require(abs(measured - length) <= TOL, 'route length contradicts saved vertices')
    if 'layers' in request:
        require(isinstance(request['layers'], list) and set(request['layers']) == set(groups)
                and len(request['layers']) == len(groups), 'requested layers differ from results')
    for group in groups.values():
        require(isinstance(group, dict) and group.get('status') in STATES, 'unknown layer status')
        require(group.get('inventory_complete', False) is False, 'unsupported complete inventory claim')
        require(isinstance(group.get('source_page'), str) and group['source_page'].startswith('https://'),
                'source page missing')
        rows = group.get('data')
        require(isinstance(rows, list) and len(rows) <= 100, 'invalid returned features')
        complete = group.get('candidate_scan_complete', False)
        require(type(complete) is bool, 'invalid scan completeness flag')
        require(not complete or group['status'] in ('ok', 'empty'), 'failed/partial scan marked complete')
        require(not complete or not group.get('issues'), 'scan with issues marked complete')
        require(not complete or 'error' not in group, 'scan with an error marked complete')
        require(type(group.get('more_matches_than_shown', False)) is bool, 'invalid display truncation flag')
        require(type(group.get('boundary_candidates_truncated', False)) is bool, 'invalid boundary truncation flag')
        matched = group.get('matched_examined')
        if matched is not None:
            count(matched, 'matched count')
            require(matched >= len(rows), 'displayed count exceeds matches')
            require(group.get('more_matches_than_shown', False) == (matched > len(rows)),
                    'display truncation contradicts matches')
        require(not rows or matched is not None, 'features returned without a match count')
        if 'returned' in group:
            require(type(group['returned']) is int and group['returned'] == len(rows),
                    'returned count contradicts rows')
        if group['status'] == 'empty':
            require(complete and matched == 0 and not rows, 'empty must be a completed, consistent scan')
        if group['status'] == 'ok':
            require(complete and matched and rows, 'ok requires completed scan with matches')
        if group['status'] in ('error', 'not_applicable'):
            require(not rows and matched is None and not complete, 'unavailable layer has known matches')
        if all(k in group for k in ('features_examined', 'outside_corridor', 'unlocatable_or_invalid', 'duplicate_candidates')):
            values = [count(group[k], k) for k in ('features_examined', 'outside_corridor',
                      'unlocatable_or_invalid', 'duplicate_candidates')]
            if matched is not None:
                require(values[0] == sum(values[1:]) + matched, 'candidate counts do not reconcile')
            n = group.get('bbox_candidate_count')
            if n is not None:
                count(n, 'candidate total')
                require(not complete or n == values[0], 'complete scan contradicts candidate total')
        seen = set()
        for feature in rows:
            require(isinstance(feature, dict), 'feature is not an object')
            ident = feature.get('source_feature_id')
            require(isinstance(ident, str) and 0 < len(ident) <= 200 and ident not in seen,
                    'missing or duplicate feature identity')
            seen.add(ident)
            require(isinstance(feature.get('attributes', {}), dict), 'invalid feature attributes')
            validate_contacts(feature, measured, radius)
            require(feature.get('within_corridor', True) is True, 'outside feature presented as a match')
        near = group.get('boundary_candidates', [])
        require(isinstance(near, list) and len(near) <= 100, 'invalid boundary review list')
        near_count = count(group.get('boundary_candidates_count', 0), 'boundary candidate count')
        require(near_count >= len(near) and group.get('boundary_candidates_truncated', False)
                == (near_count > len(near)), 'boundary candidate truncation disagrees')
        for feature in near:
            require(isinstance(feature, dict) and feature.get('within_corridor') is False,
                    'boundary review record must be outside the strict corridor')
            ident = feature.get('source_feature_id')
            require(isinstance(ident, str) and 0 < len(ident) <= 200 and ident not in seen,
                    'invalid or duplicate boundary candidate identity')
            seen.add(ident)
            require(feature.get('offset_m', 0) >= radius - TOL, 'boundary review candidate is a strict match')
            validate_contacts(feature, measured, radius + 25)

    states = [g['status'] for g in groups.values()]
    expected = ('error' if all(s == 'error' for s in states) else 'partial'
                if any(s in ('error', 'partial', 'not_applicable') for s in states)
                else 'empty' if all(s == 'empty' for s in states) else 'ok')
    require(report.get('status') == expected, 'report status contradicts its layers')
    return report
