"""Read-only review harness. Emits observations (including failures); a green job is not site approval."""
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from mcp import Client, StdioServerParameters

from uk_data_mcp import civil_tables as ct
from uk_data_mcp.civil_server import invoke
from uk_data_mcp.corridor_schedule import write_schedule
from uk_data_mcp.transport import HttpClient

TARGET = 'c7debb9cb833f9b8fa81ef25f16f84ad1be8599f'
RECEIPT = json.loads(Path('examples/digbeth-corridor-validation-2026-11-02.json').read_text())
DIG = json.loads(Path('examples/corridor_birmingham.json').read_text())
OUT = {}


def record(k, v):
    OUT[k] = v
    Path('benchmark.json').write_text(json.dumps(OUT, indent=2, allow_nan=False), encoding='utf-8')
    print('METRIC '+k+' '+json.dumps(v, separators=(',',':')), flush=True)


def metrics(arr):
    return {'n':len(arr), 'median_ms':round(statistics.median(arr),3), 'p95_nearest_rank_ms':round(sorted(arr)[math.ceil(.95*len(arr))-1],3), 'min_ms':round(min(arr),3), 'max_ms':round(max(arr),3)}


def elapsed(t):
    return (time.perf_counter()-t)*1000


def dist(p, a, b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    u=max(0,min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dy)


def reference(raw, rep):
    coords,rad=rep['metric']['route_bng_m'],rep['request']['radius_m']
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    # Independently test the national CSV, not the server's ArcGIS candidate rectangle.
    selected={}
    invalid=0
    for row in rows:
        try:
            x,y=float(row['location_easting_osgr']),float(row['location_northing_osgr'])
            if not (0<x<=700000 and 0<y<=1300000):
                raise ValueError()
        except (ValueError, TypeError):
            invalid+=1
            continue
        d=min(dist((x,y),a,b) for a,b in zip(coords,coords[1:]))
        if d<=rad:
            selected[row['collision_index']]=d
    g=rep['results']['collisions']
    returned={str(a['attributes']['collision_index']):a['offset_m'] for a in g['data']}
    common=returned.keys() & selected.keys()
    return {'csv_rows':len(rows),'invalid_grid_rows':invalid,'complete_server_scan':g.get('candidate_scan_complete'),'server_display_capped':g.get('more_matches_than_shown'), 'reference_positive':len(selected),'server_positive':len(returned),'tp':len(common),'fp':len(returned)-len(common),'fn':len(selected)-len(common),'max_offset_delta_m':round(max((abs(returned[k]-selected[k]) for k in common),default=0),3) if common else None}


async def stdio():
    starts=[]
    warm=[]
    routes={'gas main':'utilities','electricity cable':'utilities','underground utilities':'utilities','buried pipelines':'utilities', 'grid capacity':'energy','electricity grid':'energy','energy':'energy','sewer capacity':'water','water':'water','boreholes':'corridor boreholes','house prices':'housing_society','planning':'planning'}
    async def call(c,tool,args):
        r=await c.call_tool(tool,args)
        return r.structured_content or {'status':'error','message':r.content[0].text[:250]}
    with tempfile.TemporaryDirectory() as temp:
        for i in range(3):
            params=StdioServerParameters(command=sys.executable,args=['-m','uk_data_mcp.civil_server','serve'],env={'UK_CIVIL_CACHE':temp})
            t=time.perf_counter()
            async with Client(params, read_timeout_seconds=120) as c:
                tools=(await c.list_tools()).tools
                starts.append(elapsed(t))
                if i<2:
                    continue
                record('handshake',{'cold_to_list_ms':[round(n,2) for n in starts],'tools':len(tools),'read_only':sum(bool(q.annotations and q.annotations.read_only_hint) for q in tools)})
                await call(c,'civil_coverage',{'query':'water'})
                for _ in range(30):
                    t=time.perf_counter()
                    await call(c,'civil_coverage',{'query':'water'})
                    warm.append(elapsed(t))
                record('stdio_warm_water_lookup',metrics(warm))
                hits={}
                for q,domain in routes.items():
                    d=await call(c,'civil_coverage',{'query':q})
                    hits[q]=[r['domain'] for r in d.get('data',[])]
                record('keyword_targets',{'hits':hits, 'correct_routing':sum(dom in hits[q] for q,dom in routes.items()),'tested':len(routes),'target':routes})
                for label,tool,args in [('unprepared','area_census',{'gss_code':'E08000025'}),('unsupported_ni','road_collisions',{'gss_code':'N09000003'}),('unavailable_gas_layer','corridor_screen',{**DIG,'layers':['gas_mains']}),('parcel','corridor_screen',{**DIG,'alignment':{'type':'Polygon','coordinates':[[[-1.9,52.4],[-1.89,52.4],[-1.9,52.41],[-1.9,52.4]]]}})]:
                    out=await call(c,tool,args)
                    record(label,{'status':out.get('status'),'error':out.get('error'),'action':out.get('operator_action')})
                for label,tool,args in [('leakage','company_leakage',{'company':'Severn Trent Water'}),('housing','house_prices',{'region':'birmingham','month':'2024-01'}),('planning','planning_entities',{'dataset':'local-planning-authority','latitude':52.475,'longitude':-1.885,'limit':3})]:
                    t=time.perf_counter()
                    out=await call(c,tool,args)
                    record(label,{'ms':round(elapsed(t),2),'status':out.get('status'),'rows':len(out.get('data',[])), 'sample':str(out.get('data',[])[:1])[:1200], 'error':out.get('error')})
                raw=await ct.download('stats19-2025')
                record('oracle_source',{'url':ct.address('stats19-2025'),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
                for name,args in [('digbeth',DIG),('leeds',{**DIG,'alignment':{'type':'LineString','coordinates':[[-1.551,53.794],[-1.545,53.797],[-1.539,53.798]]},'layers':['collisions']})]:
                    t=time.perf_counter()
                    wire=await c.call_tool('corridor_screen',args)
                    ms=elapsed(t)
                    out=wire.structured_content
                    if not out or 'results' not in out:
                        record(name,{'status':'error','ms':round(ms,2)})
                        continue
                    summary={k:[v['status'],v.get('features_examined'),v.get('matched_examined'),v.get('returned')] for k,v in out['results'].items()}
                    def size(x):
                        return len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode())
                    facts={'ms':round(ms,2),'status':out['status'],'layers':summary, 'structured_bytes':size(out),'result_json_bytes':len(wire.model_dump_json(by_alias=True,exclude_none=True).encode()), 'requests':sum(len(v['requests']) for v in out['results'].values()),'csv_vs_mcp':reference(raw,out)}
                    if name=='digbeth':
                        facts['borehole_precision_fields']=sum('precision' in a['attributes'] for a in out['results']['boreholes']['data'])
                        facts['wards']=[(a['attributes'].get('wd24nm'),a['centreline_contacts']['relation']) for a in out['results']['communities']['data']]
                        facts['defence_contacts']=[e['start_m'] for a in out['results']['flood_defences']['data'] for e in a['centreline_contacts']['events']]
                    record(name,facts)


async def mocked():
    base={'alignment':{'type':'LineString','coordinates':[[400000,280000],[401000,280000]]},'input_crs':'EPSG:27700','nation':'England','layers':['boreholes'],'radius_m':250,'limit':5,'candidate_budget':1000}
    def feature(i):
        return {'type':'Feature','id':i,'geometry':None,'properties':{'bgs_id':i,'easting':400000+(i%1000),'northing':280100,'reference':'test','precision':'10 m'}}
    async def run(handler,opts):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
            return await invoke(HttpClient(client=raw,public_data=True,rate_interval=0,max_retries=0),'corridor_screen',opts)
    for n in (10,100,1000):
        def handler(req):
            off=int(req.url.params.get('offset',0))
            lim=int(req.url.params.get('limit',100))
            return httpx.Response(200,json={'type':'FeatureCollection','numberMatched':n,'features':[feature(i) for i in range(off,min(off+lim,n))]})
        times=[]
        for _ in range(7):
            t=time.perf_counter()
            d=await run(handler,base)
            times.append(elapsed(t))
        r=d['results']['boreholes']
        record('fixture_'+str(n),{'timings':metrics(times),'matched':r['matched_examined'],'shown':r['returned'],'complete':r['candidate_scan_complete'],'requests':len(r['requests'])})
    for label,doc in [('ambiguous_pagination',{'type':'FeatureCollection','numberMatched':0,'features':[feature(1)]}),('conflicting_crs',{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'FAKE:143260'}},'numberMatched':1,'features':[feature(1)]}) ,('nonfinite_live_response',None),('duplicate',{'type':'FeatureCollection','numberMatched':2,'features':[feature(1),feature(1)]})]:
        def handler(_):
            return httpx.Response(200,json=doc) if doc is not None else httpx.Response(200,content=b'{"value":1e400}',headers={'content-type':'application/json'})
        r=(await run(handler,base))['results']['boreholes']
        record(label,{k:r.get(k) for k in ('status','bbox_candidate_count','matched_examined','candidate_scan_complete','issues')})
    opts={**base,'alignment':{'type':'LineString','coordinates':[[-3.20,55.95],[-3.197,55.953]]},'input_crs':'OGC:CRS84','layers':['flood_defences']}
    def empty(_):
        return httpx.Response(200,json={'type':'FeatureCollection','numberMatched':0,'features':[]})
    r=(await run(empty,opts))['results']['flood_defences']
    record('edinburgh_declared_england',{k:r.get(k) for k in ('status','coverage','candidate_scan_complete','matched_examined')})
    fake={'kind':'civil_corridor_screen','results':{'defences':{'status':'ok','source_page':'https://example.invalid','candidate_scan_complete':True,'matched_examined':1,'data':[{'source_feature_id':'1','offset_m':123,'centreline_contacts':{'relation':'nearby_only','count':0,'truncated':False,'events':[{'kind':'point_contact','start_m':-5,'end_m':-5}]}}]}}}
    try:
        f=io.StringIO(); write_schedule(fake,f)
        record('invalid_export',{'accepted':True,'last_row':f.getvalue().splitlines()[-1]})
    except ValueError:
        record('invalid_export',{'accepted':False})
    with tempfile.TemporaryDirectory() as td:
        key='stats19-2025'
        doc=ct.from_bytes(key,b'collision_index,collision_year,local_authority_ons_district,collision_severity\nfixture,2025,E08000025,2\n')
        ct.store(doc,Path(td)); original=doc['source_sha256']
        doc['areas']['E08000025']['reported_injury_collisions']=-7
        ct.store(doc,Path(td)); out=ct.area_record(key,'E08000025',Path(td))
        record('edited_local_cache',{'status':out['status'],'value':out['data'][0]['reported_injury_collisions'],'raw_source_hash_unchanged':out['source']['source_sha256']==original})


async def main():
    record('environment',{'application_sha':TARGET,'src_tree':subprocess.check_output(['git','rev-parse','HEAD:src'],text=True).strip(),'python':sys.version,'platform':platform.platform(),'cpus':os.cpu_count(),'github_run_id':os.environ.get('GITHUB_RUN_ID')})
    await mocked()
    await stdio()


if __name__=='__main__':
    asyncio.run(main())
