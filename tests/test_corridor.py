"""Synthetic distance and provider contracts. No live records required by ordinary CI."""
import math

import httpx
import pytest
from mcp import Client
from shapely.geometry import LineString, Point, Polygon

from uk_data_mcp.civil_server import create_server
from uk_data_mcp.corridor import corridor_query
from uk_data_mcp.corridor_geo import Corridor
from uk_data_mcp.corridor_policy import BGS, COUNTRIES, CRT, DFT, EA, ONS
from uk_data_mcp.transport import DataAccessError, HttpClient, checked_url

XY = [[400000,280000],[401000,280000],[401000,281000]]
LINE = {'type':'LineString','coordinates':XY}


def args(**extra):
    return {'alignment':LINE,'input_crs':'EPSG:27700','radius_m':250,'nation':'England',**extra}


def test_metric_boundary_caps_bends_and_bbox_false_positive():
    r = Corridor.make(LINE,250,'EPSG:27700')
    assert r.measure(Point(400500,280250))['offset_m']==250
    assert r.measure(Point(400500,280250.001)) is None
    assert r.measure(Point(399750,280000))['chainage_m']==0
    assert r.measure(Point(399750,279750)) is None
    assert r.measure(Point(400100,280900)) is None
    assert r.measure(Point(401050,280500))['chainage_m']==1500
    assert r.measure(LineString([(400500,279000),(400500,281000)]))['offset_m']==0
    assert r.measure(Polygon([(400200,279990),(400700,279990),(400700,280010),(400200,280010)]))['centreline_length_in_area_m']==500
    assert r.measure(Polygon([(400100,280050),(400300,280050),(400300,280100),(400100,280100)]))['centreline_length_in_area_m']==0


def test_cartesian_independent_reference_and_direction():
    import random
    rng = random.Random(927)
    r = Corridor.make(LINE,250,'EPSG:27700')
    reverse = Corridor.make({'type':'LineString','coordinates':XY[::-1]},250,'EPSG:27700')
    for _ in range(100):
        x,y = rng.uniform(399700,401300),rng.uniform(279700,281300)
        # Independent closest-point calculation on two axis-aligned segments.
        dx = max(400000-x,0,x-401000)
        dy = max(280000-y,0,y-281000)
        expected = min(math.hypot(dx,y-280000), math.hypot(x-401000,dy))
        hit = r.measure(Point(x,y))
        assert (hit is not None) == (expected<=250)
        if hit:
            assert abs(hit['offset_m']-expected)<0.00051
            assert hit['chainage_m']+reverse.measure(Point(x,y))['chainage_m']==pytest.approx(2000,abs=.002)


@pytest.mark.parametrize('bad', [dict(nation='Northern Ireland'),dict(radius_m=0),dict(radius_m=True),dict(candidate_budget=1001),dict(layers=['other']),dict(input_crs='unknown'),dict(alignment={'type':'LineString','coordinates':[[0,0],[1,1]]},input_crs='OGC:CRS84'),dict(alignment={'type':'LineString','coordinates':[XY[0],XY[0]]})])
async def test_invalid_before_network(bad):
    with pytest.raises(ValueError):
        await corridor_query(None,**args(**bad))


@pytest.mark.parametrize('url',[CRT,DFT,EA,ONS])
def test_only_reviewed_spatial_paths(url):
    assert checked_url(url, public_data=True)==url
    with pytest.raises(DataAccessError):
        checked_url(url)
    with pytest.raises(DataAccessError):
        checked_url(url+'/unreviewed',public_data=True)


def feat(i,x,y):
    return {'type':'Feature','id':i,'geometry':None,'properties':{'bgs_id':i,'name':'synthetic','easting':x,'northing':y}}


async def exercise(handler, **kw):
    def routed(req):
        if str(req.url).startswith(COUNTRIES):
            nation = kw.get('nation', 'England')
            code = 'S92000003' if nation == 'Scotland' else 'E92000001'
            return httpx.Response(200, json={'features':[{'attributes':{'CTRY24CD':code,'CTRY24NM':nation}}]})
        return handler(req)
    async with httpx.AsyncClient(transport=httpx.MockTransport(routed)) as raw:
        client = HttpClient(client=raw,public_data=True,rate_interval=0,max_retries=0)
        return await corridor_query(client,**args(**kw))


async def test_unknown_rows_and_failed_provider_do_not_become_zero():
    rows = [feat(1,400500,280010),feat(2,400150,280850),feat(3,None,None)]
    def handler(req):
        if str(req.url).startswith(BGS):
            return httpx.Response(200,json={'type':'FeatureCollection','features':rows,'numberMatched':3})
        return httpx.Response(503)
    out=await exercise(handler,layers=['boreholes','bridges'])
    b=out['results']['boreholes']
    assert out['status']==b['status']=='partial'
    assert b['matched_examined']==b['outside_corridor']==b['unlocatable_or_invalid']==1
    assert b['data'][0]['offset_m']==10 and len(b['requests'][0]['response_sha256'])==64
    assert out['results']['bridges']['matched_examined'] is None


async def test_bounded_scan_separate_from_bounded_display():
    rows = [feat(1,400040,280240),feat(2,400050,280001)]
    def handler(req):
        return httpx.Response(200,json={'type':'FeatureCollection','features':rows,'numberMatched':3})
    out=await exercise(handler,layers=['boreholes'],candidate_budget=2,limit=1)
    b=out['results']['boreholes']
    assert b['status']=='partial' and b['matched_examined']==2 and b['returned']==1
    assert b['data'][0]['source_feature_id']=='2' and b['more_matches_than_shown']


async def test_empty_vs_outside_national_scope_and_bad_arcgis():
    def handler(req):
        if str(req.url).startswith(ONS):
            return httpx.Response(200,json={'error':{'message':'service unavailable'}})
        return httpx.Response(200,json={'objectIds':[]})
    out=await exercise(handler,nation='Scotland',layers=['bridges','flood_defences','communities','collisions'])
    assert [out['results'][k]['status'] for k in ('bridges','flood_defences','communities','collisions')]==['not_applicable','not_applicable','error','empty']


async def test_handshake_calls_corridor_through_mcp():
    def routed(req):
        if str(req.url).startswith(COUNTRIES):
            return httpx.Response(200, json={'features':[{'attributes':{'CTRY24CD':'E92000001','CTRY24NM':'England'}}]})
        return httpx.Response(200,json={'objectIds':[]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(routed)) as raw:
        http=HttpClient(client=raw,public_data=True,rate_interval=0,max_retries=0)
        async with Client(create_server(http)) as mcp:
            tool=await mcp.call_tool('corridor_screen',args(layers=['bridges']))
            assert tool.structured_content['status']=='empty'
