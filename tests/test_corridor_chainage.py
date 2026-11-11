"""Analytical tests in grid metres; not surveyed asset positions."""
import csv
import io
import random

import pytest
from shapely.geometry import LineString, MultiLineString, MultiPoint, Point, Polygon, box

from uk_data_mcp.corridor_chainage import EVENT_LIMIT, RouteAxis
from uk_data_mcp.corridor_geo import Corridor
from uk_data_mcp.corridor_schedule import write_schedule


def axis(*vertices):
    return RouteAxis(LineString(vertices))


def events(result):
    return [(e['kind'], e['start_m'], e['end_m']) for e in result['events']]


def test_retraced_ward_counts_travel_not_unique_footprint():
    route = Corridor.make({'type': 'LineString', 'coordinates': [[400000, 280000],
                          [400100, 280000], [400000, 280000]]}, 250, 'EPSG:27700')
    ward = box(400020, 279990, 400080, 280010)
    assert route.line.intersection(ward).length == 60
    hit = route.measure(ward)
    assert hit['centreline_length_in_area_m'] == 120
    assert events(hit['centreline_contacts']) == [('area_interior', 20, 80),
                                                  ('area_interior', 120, 180)]
    assert route.axis is route.axis
    assert route.measure(Point(400050, 280250))['centreline_contacts']['relation'] == 'nearby_only'
    assert route.measure(Point(400050, 280250.0001)) is None


def test_repeated_contacts_shared_vertex_and_direction():
    original = [(0, 0), (100, 0), (0, 0), (0, 25)]
    geom = MultiLineString([[(10, -5), (10, 5)], [(100, -5), (100, 5)]])
    a = axis(*original).contacts(geom)
    b = axis(*reversed(original)).contacts(geom)
    assert events(a) == [('point_contact', s, s) for s in (10, 100, 190)]
    assert events(b) == [('point_contact', s, s) for s in (35, 125, 215)]


def test_mixed_overlap_and_touch():
    g = MultiLineString([[(10, 0), (20, 0)], [(30, -2), (30, 2)]])
    r = axis((0, 0), (15, 0), (35, 0)).contacts(g)
    assert events(r) == [('line_overlap', 10, 20), ('point_contact', 30, 30)]


def test_hole_and_submillimetre_gap_are_not_bridged():
    g = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)],
                [[(5, 1), (5.0002, 1), (5.0002, 9), (5, 9)]])
    r = axis((-1, 4), (11, 4)).contacts(g)
    assert events(r) == [('area_interior', 1, 6), ('area_interior', 6.0002, 11)]


def test_boundary_run_inside_and_corner_are_distinct():
    g = box(0, 0, 100, 100)
    r = axis((-10, 0), (50, 0), (50, 50)).contacts(g)
    assert events(r) == [('area_boundary', 10, 60), ('area_interior', 60, 110)]
    assert r['interior_length_m'] == r['boundary_length_m'] == 50
    assert r['covered_length_m'] == 100
    r = axis((-1, 1), (1, -1)).contacts(g)
    assert r['relation'] == 'boundary_touch' and r['covered_length_m'] == 0
    assert axis((-1, 0), (105, 0)).contacts(g)['relation'] == 'boundary_followed'
    assert axis((-1, -1), (105, -1)).contacts(g)['relation'] == 'nearby_only'


def test_truncation_not_silent():
    r = axis((0, 0), (100, 0)).contacts(MultiPoint([(i, 0) for i in range(50)]))
    assert r['count'] == 50 and len(r['events']) == EVENT_LIMIT and r['truncated']


def test_random_axis_against_analytic_rectangles():
    rng = random.Random(702)
    for _ in range(80):
        x = [rng.randint(-25, 125)]
        for __ in range(8):
            x.append(rng.choice([p for p in range(-25, 126) if p != x[-1]]))
        lo, hi = sorted(rng.sample(range(101), 2))
        expected = sum(max(0, min(max(a, b), hi) - max(min(a, b), lo)) for a, b in zip(x, x[1:]))
        a = axis(*[(v, 4) for v in x]).contacts(box(lo, 0, hi, 10))
        assert a['interior_length_m'] == expected
        assert a['boundary_length_m'] == 0


def test_csv_distinguishes_nearby_omission_and_crossing():
    route = axis((0, 0), (100, 0))
    items = [{'source_feature_id': str(i), 'attributes': {'name': '=unsafe'},
              'chainage_m': x, 'offset_m': y, 'centreline_contacts': route.contacts(Point(x, y))}
             for i, (x, y) in enumerate([(20, 0), (10, 100)])]
    group = {'source_page': 'https://example.org/', 'status': 'ok', 'candidate_scan_complete': True,
             'matched_examined': 2, 'more_matches_than_shown': False, 'data': items}
    report = {'kind': 'civil_corridor_screen', 'schema_version':'1.0', 'status':'partial',
              'metric':{'crs':'EPSG:27700','length_m':100,'route_bng_m':[[0,0],[100,0]]},
              'request':{'radius_m':250}, 'results': {'assets': group, 'other':
              {'status': 'error', 'source_page': 'https://example.org/', 'data': []}}}
    out = io.StringIO(newline='')
    write_schedule(report, out)
    rows = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert [r['row_type'] for r in rows] == ['layer_summary', 'layer_summary', 'nearest_only', 'contact']
    assert rows[1]['layer_status'] == 'error' and rows[1]['matched_examined'] == ''
    assert rows[2]['label'] == "'=unsafe" and rows[2]['end_m'] == ''
    assert rows[3]['start_m'] == rows[3]['end_m']
    del items[0]['centreline_contacts']
    with pytest.raises(ValueError, match='predates'):
        write_schedule(report, out)
