"""Measure this version; a green harness run means observations were recorded, not site approval."""
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx
from mcp import Client, StdioServerParameters

from uk_data_mcp import civil_tables as ct
from uk_data_mcp.civil_server import invoke
from uk_data_mcp.corridor import pages
from uk_data_mcp.corridor_geo import Corridor
from uk_data_mcp.corridor_schedule import write_schedule
from uk_data_mcp.transport import HttpClient

DIG = json.loads(Path('examples/corridor_birmingham.json').read_text())
LEEDS = {**DIG, 'alignment': {'type':'LineString', 'coordinates':[[-1.551,53.794],[-1.545,53.797],[-1.539,53.798]]}, 'layers':['collisions']}
TARGETS = {'gas main':'utilities', 'electricity cable':'utilities', 'underground utilities':'utilities', 'buried pipelines':'utilities', 'grid capacity':'energy', 'electricity grid':'energy', 'energy':'energy', 'sewer capacity':'water', 'water':'water', 'boreholes':'corridor boreholes', 'house prices':'housing_society', 'planning':'planning'}
OUT = {}


def record(key, value):
    OUT[key] = value
    Path('benchmark.json').write_text(json.dumps(OUT, indent=2, allow_nan=False), encoding='utf8')
    print('METRIC', key, json.dumps(value, separators=(',',':')), flush=True)


def ms(start):
    return (time.perf_counter()-start)*1000


def stats(samples):
    return {'n':len(samples), 'median_ms':round(statistics.median(samples),3), 'p95_nearest_rank_ms':round(sorted(samples)[math.ceil(.95*len(samples))-1],3), 'min_ms':round(min(samples),3), 'max_ms':round(max(samples),3)}


def distance(p, a, b):
    dx,dy = b[0]-a[0], b[1]-a[1]
    u = min(1,max(0,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dy)


async def source_check(raw, report, args):
    xy = report['metric']['route_bng_m']
    segments = list(zip(xy,xy[1:]))
    radius = args['radius_m']
    selected = {}
    rows = invalid = 0
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        rows += 1
        try:
            x,y = float(row['location_easting_osgr']),float(row['location_northing_osgr'])
            if not (0<x<=700000 and 0<y<=1300000):
                raise ValueError('invalid grid position')
        except (ValueError, TypeError):
            invalid += 1
            continue
        d = min(distance((x,y),a,b) for a,b in segments)
        if d<=radius:
            selected[row['collision_index']] = d
    group=report['results']['collisions']
    returned={str(f['attributes']['collision_index']):f['offset_m'] for f in group['data']}
    both=returned.keys() & selected.keys()
    disagreements = {k:{'csv_bng_m':round(selected[k],3)} for k in selected.keys()-returned.keys()}
    if disagreements:
        # Diagnose a missing ID using raw map features BEFORE exact distance filtering.
        # Only the public stationing and digest of the ID are retained; no incident details.
        route = Corridor.make(args['alignment'],radius,args['input_crs'])
        audit={'requests':[], 'issues':[], 'bbox_candidate_count':None}
        async with HttpClient(public_data=True) as h:
            async for fs in pages(h,'collisions',route,1000,audit):
                for f in fs:
                    k = str(f['properties'].get('collision_index'))
                    if k in disagreements:
                        ll = f['geometry']['coordinates'][:2]
                        pos = route.forward.transform(*ll)
                        disagreements[k]['arcgis_bng_m']=round(min(distance(pos,a,b) for a,b in segments),3)
        for v in disagreements.values():
            v['followup_candidate_issues']=audit['issues']
    return {'csv_rows':rows, 'invalid_grid_rows':invalid, 'reference_positive':len(selected),'server_positive':len(returned),'tp':len(both),'fp':len(returned)-len(both),'fn':len(selected)-len(both),'max_offset_delta_m':round(max(abs(returned[k]-selected[k]) for k in both),3) if both else None,'differences':{hashlib.sha256(k.encode()).hexdigest()[:12]:v for k,v in disagreements.items()},'scan_complete':group['candidate_scan_complete'],'display_capped':group['more_matches_than_shown']}


async def live(c):
    async def call(tool,args):
        reply=await c.call_tool(tool,args)
        return reply.structured_content or {'status':'error','message':reply.content[0].text[:250]}
    await call('civil_coverage',{'query':'water'})
    warm=[]
    for _ in range(30):
        start=time.perf_counter()
        await call('civil_coverage',{'query':'water'})
        warm.append(ms(start))
    record('warm_directory',stats(warm))
    hits={}
    for q in TARGETS:
        out=await call('civil_coverage',{'query':q})
        hits[q]=[r['domain'] for r in out['data']]
    record('routing',{'targets':TARGETS,'hits':hits,'correct':sum(k in hits[q] for q,k in TARGETS.items())})
    for tag,tool,args in [('unprepared','area_census',{'gss_code':'E08000025'}),('unsupported_ni','road_collisions',{'gss_code':'N09000003'}),('gas_layer','corridor_screen',{**DIG,'layers':['gas_mains']}),('parcel','corridor_screen',{**DIG,'alignment':{'type':'Polygon','coordinates':[]}}),('leakage','company_leakage',{'company':'Severn Trent Water'}),('housing','house_prices',{'region':'birmingham','month':'2024-01'}),('planning','planning_entities',{'dataset':'local-planning-authority','latitude':52.475,'longitude':-1.885,'limit':3})]:
        start=time.perf_counter()
        d=await call(tool,args)
        record(tag,{'ms':round(ms(start),2),'status':d['status'],'error':d.get('error'),'action':d.get('operator_action'),'sample':str(d.get('data',[])[:1])[:1200]})
    raw=await ct.download('stats19-2025')
    record('reference_file',{'url':ct.address('stats19-2025'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    for label,args in [('digbeth',DIG),('leeds',LEEDS)]:
        start=time.perf_counter()
        wire=await c.call_tool('corridor_screen',args)
        wall=ms(start)
        r=wire.structured_content or {}
        if 'results' not in r:
            record(label,{'status':'failed','ms':round(wall,2),'error':r.get('error')})
            continue
        outputs=r['results']
        facts={'ms':round(wall,2),'status':r['status'],'layers':{k:[v['status'],v.get('features_examined'),v.get('matched_examined'),v.get('returned')] for k,v in outputs.items()},'requests':sum(len(v['requests']) for v in outputs.values()),'structured_bytes':len(json.dumps(r,separators=(',',':'),ensure_ascii=False).encode()),'result_json_bytes':len(wire.model_dump_json(by_alias=True,exclude_none=True).encode()),'csv_vs_mcp':await source_check(raw,r,args)}
        if label=='digbeth':
            facts['borehole_precision_fields']=sum('precision' in x['attributes'] for x in outputs['boreholes']['data'])
            facts['wards']=[(x['attributes'].get('wd24nm'),x['centreline_contacts']['relation']) for x in outputs['communities']['data']]
            facts['defence_contact_m']=[e['start_m'] for x in outputs['flood_defences']['data'] for e in x['centreline_contacts']['events']]
        record(label,facts)


async def mocks():
    base={'alignment':{'type':'LineString','coordinates':[[400000,280000],[401000,280000]]},'input_crs':'EPSG:27700','nation':'England','layers':['boreholes'],'radius_m':250,'limit':5,'candidate_budget':1000}
    def feature(i):
        return {'type':'Feature','id':i,'geometry':None,'properties':{'bgs_id':i,'easting':400000+i%1000,'northing':280100,'reference':'test','precision':'10 m'}}
    async def run(handler,opts):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
            result=await invoke(HttpClient(client=raw,public_data=True,rate_interval=0,max_retries=0),'corridor_screen',opts)
            return result['results'][opts['layers'][0]]
    for n in (10,100,1000):
        def handler(req):
            p=req.url.params
            lo=int(p.get('offset',0))
            return httpx.Response(200,json={'type':'FeatureCollection','numberMatched':n,'features':[feature(i) for i in range(lo,min(lo+int(p.get('limit',100)),n))]})
        samples=[]
        for _ in range(7):
            start=time.perf_counter()
            r=await run(handler,base)
            samples.append(ms(start))
        record('fixture_'+str(n),{'timings':stats(samples),'matched':r['matched_examined'],'shown':r['returned'],'complete':r['candidate_scan_complete'],'requests':len(r['requests'])})
    for label,doc in [('contradictory_total',{'numberMatched':0,'features':[feature(1)]}),('ambiguous_crs',{'crs':{'type':'name','properties':{'name':'FAKE:143260'}},'numberMatched':1,'features':[feature(1)]}),('nonfinite',None),('duplicate',{'numberMatched':2,'features':[feature(1),feature(1)]})]:
        def handler(_):
            if doc is None:
                return httpx.Response(200,content=b'{"value":1e400}',headers={'Content-Type':'application/json'})
            return httpx.Response(200,json={'type':'FeatureCollection',**doc})
        r=await run(handler,base)
        record(label,{k:r.get(k) for k in ('status','bbox_candidate_count','matched_examined','candidate_scan_complete','issues')})
    ed={**base,'alignment':{'type':'LineString','coordinates':[[-3.20,55.95],[-3.197,55.953]]},'input_crs':'OGC:CRS84','layers':['flood_defences']}
    r=await run(lambda _:httpx.Response(200,json={'type':'FeatureCollection','numberMatched':0,'features':[]}),ed)
    record('edinburgh_as_england',{k:r.get(k) for k in ('status','coverage','candidate_scan_complete','matched_examined')})
    fake={'kind':'civil_corridor_screen','results':{'defences':{'status':'ok','source_page':'https://example.invalid','candidate_scan_complete':True,'matched_examined':1,'data':[{'source_feature_id':'1','offset_m':123,'centreline_contacts':{'relation':'nearby_only','count':0,'truncated':False,'events':[{'kind':'point_contact','start_m':-5,'end_m':-5}]}}]}}}
    out=io.StringIO()
    try:
        write_schedule(fake,out)
        record('export',{'accepted':True,'row':out.getvalue().splitlines()[-1]})
    except ValueError:
        record('export',{'accepted':False})
    with tempfile.TemporaryDirectory() as d:
        doc=ct.from_bytes('stats19-2025',b'collision_index,collision_year,local_authority_ons_district,collision_severity\nfixture,2025,E08000025,2\n')
        ct.store(doc,Path(d))
        original=doc['source_sha256']
        doc['areas']['E08000025']['reported_injury_collisions']=-7
        ct.store(doc,Path(d))
        got=ct.area_record('stats19-2025','E08000025',Path(d))
        record('changed_cache',{'status':got['status'],'value':got['data'][0]['reported_injury_collisions'],'source_hash_unchanged':got['source']['source_sha256']==original})


async def main():
    record('environment',{'target':'c7debb9cb833f9b8fa81ef25f16f84ad1be8599f','python':sys.version,'platform':platform.platform(),'cpus':os.cpu_count(),'run':os.getenv('GITHUB_RUN_ID')})
    await mocks()
    with tempfile.TemporaryDirectory() as tmp:
        starts=[]
        for i in range(3):
            params=StdioServerParameters(command=sys.executable,args=['-m','uk_data_mcp.civil_server','serve'],env={'UK_CIVIL_CACHE':tmp})
            start=time.perf_counter()
            async with Client(params,read_timeout_seconds=120) as c:
                tools=(await c.list_tools()).tools
                starts.append(round(ms(start),2))
                if i==2:
                    record('handshake',{'cold_to_list_ms':starts,'tools':len(tools),'read_only':sum(bool(t.annotations and t.annotations.read_only_hint) for t in tools)})
                    await live(c)


if __name__=='__main__':
    asyncio.run(main())
