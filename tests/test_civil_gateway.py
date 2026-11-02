"""Civil gateway contracts; all small source files in this module are synthetic."""

import asyncio
import io
import json
import zipfile

import pytest
from mcp import Client

from uk_data_mcp import civil_tables as t
from uk_data_mcp.civil_coverage import civil_coverage
from uk_data_mcp.civil_server import NAMES, context, create_server, invoke

CODE = 'E08000025'
HEADER = 'collision_index,collision_year,local_authority_ons_district,collision_severity\n'


def zipped(data, member='census2021-ts001-ltla.csv'):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr(member, data)
        z.writestr('census2021-ts001-oa.csv', 'DO NOT EXTRACT')
    return out.getvalue()


def test_snapshot_and_roundtrip(tmp_path):
    index = t.from_bytes('ts001', zipped('date,geography,geography code,total,one,other\n2021,Test,E08000025,100,0,..\n'))
    t.store(index, tmp_path)
    obs = t.area_record('ts001', CODE, tmp_path)
    assert obs['status'] == 'ok'
    assert obs['source']['table'] == 'TS001' and 'areas' not in obs['source']
    assert len(obs['source']['member_sha256']) == len(obs['source']['source_sha256']) == 64
    values = obs['data'][0]['observations']
    assert values['total']['value'] == 100 and values['one']['value'] == 0
    assert values['other'] == {'as_published':'..','value':None}
    assert t.area_record('ts001', 'W06000015', tmp_path)['status'] == 'empty'
    assert t.area_record('ts001', 'S12000049', tmp_path)['error']['code'] == 'unsupported_geography'


@pytest.mark.parametrize('raw', [zipped('bad\n123'), zipped('x', 'not-ltla.csv'),
    zipped('date,geography,geography code,v\n2020,Test,E08000025,1'),
    zipped('date,geography,geography code,v\n2021,Test,E08000025,1\n2021,Test,E08000025,2')])
def test_reject_changed_or_ambiguous_census(raw):
    with pytest.raises(ValueError):
        t.from_bytes('ts001', raw)


def test_counts_are_events_not_people(tmp_path):
    raw = (HEADER+'id-a,2025,E08000025,1\nid-b,2025,E08000025,3\nid-c,2025,E08000025,-1\nid-d,2025,-1,2\n').encode()
    snap = t.from_bytes('stats19-2025', raw)
    t.store(snap, tmp_path)
    res = t.area_record('stats19-2025', CODE, tmp_path)
    assert res['source']['source_records'] == 4 and res['source']['records_without_usable_district'] == 1
    assert res['data'] == [{'reported_injury_collisions':3,'by_reported_collision_severity':{'fatal':1,'serious':0,'slight':1,'unknown':1}}]
    assert 'id-a' not in json.dumps(res) and 'id-d' not in json.dumps(snap)
    assert t.area_record('stats19-2025','N09000003',tmp_path)['error']['code'] == 'unsupported_geography'


@pytest.mark.parametrize('rows', ['a,2025,E08000025,1\na,2025,E08000025,2', 'a,2024,E08000025,1', '', 'a,2025,-1,1'])
def test_bad_collisions(rows):
    with pytest.raises(ValueError):
        t.from_bytes('stats19-2025', (HEADER+rows).encode())


def test_missing_snapshot_not_missing_events(tmp_path):
    res = t.area_record('stats19-2025', CODE, tmp_path)
    assert res['error']['code'] == 'not_prepared'
    assert res['operator_action'] == 'uk-civil-data prepare stats19-2025'
    with pytest.raises(ValueError):
        t.area_record('../etc/passwd', CODE, tmp_path)
    with pytest.raises(ValueError):
        t.area_record('ts001','birmingham',tmp_path)


def test_cross_sector_routes_have_actionable_limits():
    data = civil_coverage()['data']
    assert len({r['domain'] for r in data}) >= 20
    assert all(r['publisher_url'].startswith('https://') and r['limitation'] for r in data)
    assert all(r['next_call'] is None or r['next_call']['tool'] in NAMES for r in data)
    assert civil_coverage('bridges')['data'][0]['access'] == 'discovery'
    assert civil_coverage('buried')['data'][0]['access'] == 'restricted'
    assert civil_coverage('doesnotexist')['status'] == 'empty'


def test_partial_preserves_independent_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv('UK_CIVIL_CACHE', str(tmp_path))
    t.store(t.from_bytes('stats19-2025', (HEADER+'a,2025,E08000025,2\n').encode()), tmp_path)
    r = asyncio.run(context(None, CODE))
    assert r['status'] == 'partial' and r['results']['road_safety']['status'] == 'ok'
    assert r['results']['population']['error']['code'] == 'not_prepared'
    r = asyncio.run(context(None, 'E06000001', housing_month='2024-01'))
    assert r['results']['housing']['error']['code'] == 'no_reviewed_area_mapping'
    assert asyncio.run(invoke(None, 'civil_area_context', {'gss_code':CODE,'housing_month':'2020-13'}))['status'] == 'error'


@pytest.mark.asyncio
async def test_same_handshake_exposes_ground_public_and_civil(tmp_path, monkeypatch):
    monkeypatch.setenv('UK_CIVIL_CACHE', str(tmp_path))
    async with Client(create_server()) as client:
        tools = await client.list_tools()
        actual = {t.name for t in getattr(tools, 'tools', tools)}
        assert actual == set(NAMES)
        for name, args in [('list_sources',{}), ('public_sources',{}), ('civil_coverage',{'query':'rail'})]:
            result = await client.call_tool(name, args)
            assert not result.is_error and result.structured_content
        result = await client.call_tool('area_census', {'gss_code':CODE})
        assert result.is_error and result.structured_content['error']['code'] == 'not_prepared'
