"""Reproduce the stakeholder review counterexamples, with positive controls."""

import copy
import csv
import io
import json
import subprocess
import sys

import httpx
import pytest
from shapely.geometry import Point, box

from uk_data_mcp import civil_housing as housing
from uk_data_mcp import civil_tables as tables
from uk_data_mcp.cache_integrity import seal, verify
from uk_data_mcp.civil_coverage import civil_coverage
from uk_data_mcp.corridor import corridor_query, features
from uk_data_mcp.corridor_contract import validate_corridor_report
from uk_data_mcp.corridor_geo import Corridor
from uk_data_mcp.corridor_policy import COUNTRIES
from uk_data_mcp.corridor_schedule import write_schedule
from uk_data_mcp.corridor_validation import CRS84_NAMES, page_contract
from uk_data_mcp.json_safety import loads_json
from uk_data_mcp.transport import DataAccessError, HttpClient
from uk_data_mcp.utility_handoff import utility_handoff

LINE = {'type': 'LineString', 'coordinates': [[400000, 280000], [401000, 280000]]}
ARGS = {'alignment': LINE, 'input_crs': 'EPSG:27700', 'nation': 'England',
        'radius_m': 250, 'layers': ['boreholes']}
HEADER = 'collision_index,collision_year,local_authority_ons_district,collision_severity\n'


def country(name='England'):
    codes = {'England':'E92000001', 'Scotland':'S92000003', 'Wales':'W92000004'}
    return {'features':[{'attributes': {'CTRY24CD': codes[name], 'CTRY24NM': name}}]}


def feature(ident, offset=10):
    return {'type':'Feature', 'id':ident, 'geometry':None,
            'properties':{'easting':400500, 'northing':280000 + offset}}


async def query(handler, **args):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = HttpClient(client=raw, public_data=True, rate_interval=0, max_retries=0)
        return await corridor_query(client, **(ARGS | args))


def routed(payload):
    def handler(req):
        return httpx.Response(200, json=country() if str(req.url).startswith(COUNTRIES) else payload)
    return handler


@pytest.mark.parametrize('name', ['FAKE:143260','EPSG:43260','EPSG:27700','not4326','urn:evil:4326'])
def test_fake_crs_labels_rejected(name):
    with pytest.raises(DataAccessError):
        features({'type':'FeatureCollection','features':[],
                  'crs':{'type':'name','properties':{'name':name}}})


@pytest.mark.parametrize('name', sorted(CRS84_NAMES))
def test_exact_reviewed_geojson_crs_allowed(name):
    assert features({'type':'FeatureCollection','features':[],
                     'crs':{'type':'name','properties':{'name':name}}}) == []


@pytest.mark.parametrize('declaration', [False, '', [], 4326, {'type':'link'}, {'properties':{'name':'EPSG:4326'}}])
def test_malformed_crs_rejected(declaration):
    with pytest.raises(DataAccessError):
        features({'type':'FeatureCollection','features':[], 'crs':declaration})


async def test_numbermatched_zero_with_feature_is_not_complete():
    r = await query(routed({'type':'FeatureCollection','features':[feature('1')],'numberMatched':0}))
    layer = r['results']['boreholes']
    assert layer['status'] == 'error' and not layer['candidate_scan_complete']
    assert layer['matched_examined'] is None


@pytest.mark.parametrize('doc,start,n,total', [
    ({'numberMatched':0},0,1,None), ({'numberMatched':1},1,1,1),
    ({'numberMatched':False},0,0,None), ({'numberMatched':-1},0,0,None),
    ({'numberMatched':3},1,1,2), ({'numberMatched':3,'links':[]},1,0,3),
    ({'numberMatched':1,'links':[{'rel':'next','href':'https://example.org'}]},0,1,None),
    ({'links':{}},0,0,None), ({'links':[{'rel':'next'}]},0,0,None),
])
def test_inconsistent_pages_rejected(doc,start,n,total):
    with pytest.raises(DataAccessError):
        page_contract(doc,start,n,total)


async def test_declared_england_for_scottish_polygon_blocks_asset_search():
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        assert str(req.url).startswith(COUNTRIES)
        assert req.url.params['spatialRel'] == 'esriSpatialRelWithin'
        return httpx.Response(200, json=country('Scotland'))
    r = await query(handler)
    assert r['status'] == 'error' and r['error']['code'] == 'nation_mismatch'
    assert r['results'] == {} and len(calls) == 1
    out=io.StringIO();write_schedule(r,out)
    assert 'report_summary' in out.getvalue() and 'mismatch' in out.getvalue()


@pytest.mark.parametrize('boundary_response', [{'features':[]}, {'error':{'message':'unavailable'}},
    {'features':[],'exceededTransferLimit':True}, {'features':[{'attributes':{'CTRY24CD':'XX','CTRY24NM':'England'}}]}])
async def test_border_unknown_and_failed_coverage_are_not_empty_assets(boundary_response):
    def handler(req):
        assert str(req.url).startswith(COUNTRIES)
        return httpx.Response(200,json=boundary_response)
    r=await query(handler)
    assert r['status']=='error' and r['results']=={}
    assert r['jurisdiction']['status']!='verified'


async def test_valid_empty_still_empty_after_country_verification():
    r=await query(routed({'type':'FeatureCollection','features':[],'numberMatched':0}))
    assert r['status']=='empty' and r['jurisdiction']['status']=='verified'
    layer=r['results']['boreholes']
    assert layer['candidate_scan_complete'] and layer['matched_examined']==0
    assert not layer['inventory_complete']
    validate_corridor_report(r)


async def test_boundary_band_preserves_strict_membership_and_near_miss():
    payload={'type':'FeatureCollection','numberMatched':4,
             'features':[feature('inside',249.701), feature('outside',250.735),
                         feature('well_inside',10), feature('far',300)]}
    r=await query(routed(payload));layer=r['results']['boreholes']
    assert layer['matched_examined']==2 and layer['outside_corridor']==2
    assert layer['boundary_candidates_count']==1
    assert layer['boundary_candidates'][0]['source_feature_id']=='outside'
    assert layer['threshold_sensitive_matched']==1
    assert layer['membership_stability']=='review_required'
    assert layer['boundary_candidates'][0]['source_position']['crs']=='EPSG:27700'
    validate_corridor_report(r)
    out=io.StringIO();write_schedule(r,out)
    assert 'boundary_review_only' in out.getvalue()


def valid_report():
    route=Corridor.make(LINE,250,'EPSG:27700')
    hit=route.measure(Point(400050,280000))
    hit.update(source_feature_id='1',attributes={})
    group={'source_page':'https://example.org/', 'status':'ok', 'candidate_scan_complete':True,
           'matched_examined':1,'more_matches_than_shown':False,'data':[hit]}
    return {'kind':'civil_corridor_screen','schema_version':'1.0','status':'ok',
            'metric':{'crs':'EPSG:27700','length_m':1000,'route_bng_m':LINE['coordinates']},
            'request':{'radius_m':250},'results':{'boreholes':group}}


@pytest.mark.parametrize('mutation', ['negative_chainage','over_length','nearby_contact','wrong_count',
    'nonzero_offset','bad_relation','bad_truncation','bad_length','bad_status','duplicate','nan','empty_incomplete',
    'error_marked_complete','numeric_flag','invalid_attributes'])
def test_exports_reject_inconsistent_saved_report(mutation):
    r=valid_report();g=r['results']['boreholes'];f=g['data'][0];c=f['centreline_contacts'];e=c['events'][0]
    if mutation=='negative_chainage': e['start_m']=e['end_m']=-5
    elif mutation=='over_length': e['start_m']=e['end_m']=1001
    elif mutation=='nearby_contact': c['relation']='nearby_only'
    elif mutation=='wrong_count': c['count']=0
    elif mutation=='nonzero_offset': f['offset_m']=123
    elif mutation=='bad_relation': c['relation']='interior_traversed'
    elif mutation=='bad_truncation': c['truncated']=True
    elif mutation=='bad_length': r['metric']['length_m']=900
    elif mutation=='bad_status': g['status']='partial'
    elif mutation=='duplicate': g['data'].append(copy.deepcopy(f));g['matched_examined']=2
    elif mutation=='nan': f['offset_m']=float('nan')
    elif mutation=='empty_incomplete': g.update(status='empty',candidate_scan_complete=False,data=[],matched_examined=0)
    elif mutation=='error_marked_complete': g['error']={'code':'upstream_error'}
    elif mutation=='numeric_flag': g['more_matches_than_shown']=0
    elif mutation=='invalid_attributes': f['attributes']=[]
    out=io.StringIO('unchanged');out.seek(0,2)
    with pytest.raises(ValueError): write_schedule(r,out)
    assert out.getvalue()=='unchanged'


def test_valid_legacy_export_marks_jurisdiction_unverified():
    out=io.StringIO();write_schedule(valid_report(),out)
    rows=list(csv.DictReader(io.StringIO(out.getvalue())))
    assert all(x['jurisdiction_status']=='unverified_legacy' and x['inventory_complete']=='False' for x in rows)


def test_invalid_file_does_not_replace_previous_export(tmp_path):
    src=tmp_path/'report.json';dst=tmp_path/'schedule.csv'
    r=valid_report();r['results']['boreholes']['data'][0]['offset_m']=123
    src.write_text(json.dumps(r));dst.write_text('keep me')
    p=subprocess.run([sys.executable,'-m','uk_data_mcp.corridor_schedule',str(src),str(dst)],
                     capture_output=True,text=True)
    assert p.returncode==2 and dst.read_text()=='keep me'


def test_polygon_totals_checked():
    r=valid_report();route=Corridor.make(LINE,250,'EPSG:27700')
    hit=route.measure(box(400100,279990,400200,280010));hit.update(source_feature_id='1',attributes={})
    r['results']['boreholes']['data']=[hit]
    validate_corridor_report(r)
    hit['centreline_contacts']['covered_length_m']=99
    with pytest.raises(ValueError): validate_corridor_report(r)


def collision_cache(tmp_path):
    index=tables.from_bytes('stats19-2025',(HEADER+'a,2025,E08000025,3\n').encode())
    tables.store(index,tmp_path)
    return index,tmp_path/'stats19-2025.json'


@pytest.mark.parametrize('mutation', ['negative','bool','severity_sum','positive_edit','source_count','old_schema','nonfinite'])
def test_corrupt_cache_never_returns_known_count(tmp_path,mutation):
    index,path=collision_cache(tmp_path);row=index['areas']['E08000025']
    if mutation=='negative': row['reported_injury_collisions']=-7;seal(index)
    elif mutation=='bool': row['reported_injury_collisions']=True;seal(index)
    elif mutation=='severity_sum': row['by_reported_collision_severity']['slight']=2;seal(index)
    elif mutation=='positive_edit': row['reported_injury_collisions']=7
    elif mutation=='source_count': index['source_records']=8;seal(index)
    elif mutation=='old_schema': index['schema']=1;index.pop('derived_sha256')
    elif mutation=='nonfinite': row['reported_injury_collisions']=float('nan')
    path.write_text(json.dumps(index))
    r=tables.area_record('stats19-2025','E08000025',tmp_path)
    assert r['status']=='error' and r['error']['code']=='invalid_cache' and r['data']==[]
    assert r['operator_action']=='uk-civil-data prepare stats19-2025'


def test_digest_is_not_claimed_authentication_and_external_reference_can_detect_reseal(tmp_path):
    index,_=collision_cache(tmp_path);trusted=index['derived_sha256']
    index['areas']['E08000025']['reported_injury_collisions']=2
    index['areas']['E08000025']['by_reported_collision_severity']['slight']=2
    index['source_records']=2;seal(index)
    with pytest.raises(ValueError,match='trusted'):verify(index,trusted)


def test_hpi_derived_values_verified(tmp_path):
    index=housing.index_file(b'Date,Region_Name,Area_Code,Average_Price\n01/01/2024,Test,E08000025,10\n')
    index['areas']['E08000025']['months']['2024-01']='-7';seal(index)
    (tmp_path/(housing.KEY+'.json')).write_text(json.dumps(index))
    assert housing.record('E08000025','2024-01',tmp_path)['error']['code']=='invalid_cache'


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError,match='Duplicate'):loads_json('{"a":1,"a":2}')


@pytest.mark.parametrize('query,domain', [
    ('gas main','utilities'),('electricity cable','utilities'),('underground utilities','utilities'),
    ('buried pipelines','utilities'),('grid capacity','energy'),('electricity grid','energy'),
    ('energy','energy'),('sewer capacity','water'),('water','water'),
    ('boreholes','corridor boreholes'),('house prices','housing_society'),('planning','planning'),
    ('HV cable protection','utilities'),('DNO connection headroom','energy'),
    ('pre-development sewer enquiry','water'),('gas distribution diversion','utilities'),
])
def test_professional_vocabulary(query,domain):
    assert any(row['domain']==domain for row in civil_coverage(query)['data'])


def test_capacity_is_not_routed_to_leakage():
    row=next(r for r in civil_coverage('sewer capacity',nation='Scotland')['data'] if r['domain']=='water')
    assert row['next_call']['tool']=='utility_handoff'
    r=utility_handoff(**row['next_call']['arguments'])
    assert r['network_capacity'] is None and r['excavation_clearance'] is None
    assert any('roadworks.scot' in x['url'] for x in r['official_routes'])
    assert not any(x['url'].startswith('https://www.ofwat.gov.uk') for x in r['official_routes'])


def test_operator_selection_is_not_geographic_inference():
    r=utility_handoff('electricity','England','connection','National Grid Electricity Distribution')
    assert r['operator_resolution']=='user_selected_not_location_verified'
    assert r['connection_offer'] is None
    r=utility_handoff('water','Scotland',operator='Severn Trent Water')
    assert r['operator_resolution']=='sector_or_nation_mismatch'
    r=utility_handoff('gas',None,operator='Unverified example')
    assert r['operator_resolution']=='unverified_name'
