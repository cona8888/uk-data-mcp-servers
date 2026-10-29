"""Regression requirements identified in the review of commit 62fd3e6.

All records are synthetic. These tests fail on the reviewed baseline and must
pass with the integrity, measurement-selection and JSON-safety fixes.
"""
import copy
import sys

import httpx
import pytest

from uk_data_mcp.deskstudy import _measures
from uk_data_mcp.reporting import validate_report
from uk_data_mcp.transport import DataAccessError, HttpClient

DESIGN_KEYS = (
    'effective_stress_friction_angle_deg', 'undrained_shear_strength_kPa',
    'soil_stiffness_MPa', 'permeability_m_per_s', 'design_groundwater_level_mAOD',
    'allowable_bearing_pressure_kPa', 'buried_utility_clearance_m',
)

def report_fixture():
    return {
        'kind': 'geotechnical_desk_study', 'schema_version': '1.0',
        'status': 'ok', 'generated_at_utc': '2026-10-29T00:00:00Z',
        'project': {'project_name': 'Synthetic review fixture', 'development_type': 'general', 'works_description': ''},
        'site': {'latitude': 52.45, 'longitude': -1.93, 'nation': 'England', 'radius_km': 1},
        'summary': {'investigation_count': 0, 'query_count': 1, 'failed_query_count': 0, 'incomplete_query_count': 0, 'open_gap_count': 0},
        'evidence': [{'id':'query-001', 'topic':'regional_geology', 'tool':'bgs_features', 'status':'empty', 'arguments':{},
                      'result': {'status':'empty', 'data':[], 'pagination':{'returned':0}, 'warnings':[], 'provenance':[]}}],
        'investigations': [], 'groundwater': [], 'gaps': [],
        'warnings': ['Synthetic fixture, not an engineering report'], 'omitted_queries': [],
        'design_parameters': {k: {'value':None, 'reason':'Not established'} for k in DESIGN_KEYS}
    }

@pytest.mark.asyncio
async def test_overflowed_json_number_is_provider_error():
    raw = b'{"value":1e400}'
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200,content=raw,headers={'content-type':'application/json'}))) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json('https://ogcapi.bgs.ac.uk/collections')
    assert error.value.code == 'invalid_response'

@pytest.mark.asyncio
async def test_deep_json_is_normalized_provider_error():
    n = max(20_000, sys.getrecursionlimit() + 200)
    raw = b'[' * n + b'0' + b']' * n
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200,content=raw,headers={'content-type':'application/json'}))) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json('https://ogcapi.bgs.ac.uk/collections')
    assert error.value.code == 'invalid_response'

@pytest.mark.parametrize('reference_kind', ['investigation','gap','groundwater'])
def test_dangling_evidence_reference_rejected(reference_kind):
    r=report_fixture()
    if reference_kind=='investigation':
        r['investigations']=[{'id':'inv-1','links':[], 'evidence_ids':['query-does-not-exist'],
                               'review':{'status':'unreviewed','notes':''}}]
    elif reference_kind=='gap':
        r['gaps']=[{'id':'gap-1','title':'Check source','reason':'Synthetic','status':'open','notes':'',
                     'actions':[], 'evidence_ids':['query-does-not-exist']}]
    else:
        r['groundwater']=[{'evidence_id':'query-does-not-exist', 'measure':{},'readings':[],'warnings':[]}]
    with pytest.raises(ValueError):
        validate_report(r)

def test_error_result_cannot_have_successful_envelope():
    r=report_fixture()
    r['evidence'][0]['status']='ok'
    r['evidence'][0]['result']['status']='error'
    r['evidence'][0]['result']['error']={'message':'Synthetic upstream failure'}
    with pytest.raises(ValueError):
        validate_report(r)

def test_invalid_site_rejected_by_backend_like_frontend():
    r=report_fixture()
    r['site']['latitude']=999
    with pytest.raises(ValueError):
        validate_report(r)

def test_groundwater_selection_excludes_known_rainfall_series():
    # The station passes the station-level groundwater filter because it has
    # a groundwater series. A different series must not consume that budget.
    stations=[{'label':'Synthetic mixed station', 'measures':[
        {'notation':'rainfall-series', 'observedProperty':'rainfall','parameterName':'Rainfall'},
        {'notation':'groundwater-series', 'observedProperty':'groundwaterLevel','parameterName':'GroundwaterLevel'},
    ]}]
    selected=[identifier for identifier,_ in _measures(stations)][:1]
    assert selected==['groundwater-series']

# Positive controls establish that this is not a blanket validation failure.
def test_valid_fixture_accepted():
    r=report_fixture()
    assert validate_report(r) is r

def test_non_null_design_value_rejected():
    r=report_fixture()
    r['design_parameters']['undrained_shear_strength_kPa']['value']=45
    with pytest.raises(ValueError):
        validate_report(r)

def test_duplicate_evidence_rejected():
    r=report_fixture()
    r['evidence'].append(copy.deepcopy(r['evidence'][0]))
    with pytest.raises(ValueError):
        validate_report(r)
