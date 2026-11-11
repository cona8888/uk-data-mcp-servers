"""Dated live acceptance and benchmark: uncertainty remains visible, never a false zero."""

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
import time
from pathlib import Path

from mcp import Client, StdioServerParameters

from uk_data_mcp import civil_tables
from uk_data_mcp.corridor_contract import validate_corridor_report
from uk_data_mcp.corridor_schedule import write_schedule

DEST = Path('integrity-evidence')
TARGETS = {'gas main':'utilities', 'electricity cable':'utilities', 'underground utilities':'utilities',
           'buried pipelines':'utilities', 'grid capacity':'energy', 'electricity grid':'energy',
           'energy':'energy', 'sewer capacity':'water', 'water':'water', 'boreholes':'corridor boreholes',
           'house prices':'housing_society', 'planning':'planning'}


def distance(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    u = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-u*dx, p[1]-a[1]-u*dy)


def reference(raw, report):
    xy=report['metric']['route_bng_m']
    radius=report['request']['radius_m']
    expected={}
    invalid=total=0
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        total+=1
        try:
            x,y=float(row['location_easting_osgr']),float(row['location_northing_osgr'])
            if not (0<x<=700000 and 0<y<=1300000):
                raise ValueError('Unlocated')
        except (ValueError,TypeError):
            invalid+=1
            continue
        d=min(distance((x,y),a,b) for a,b in zip(xy,xy[1:]))
        if d<=radius:
            expected[row['collision_index']]=d
    group=report['results']['collisions']
    actual={str(f['attributes']['collision_index']):f for f in group['data']}
    near={str(f['attributes']['collision_index']):f for f in group.get('boundary_candidates',[])}
    missing=expected.keys()-actual.keys()
    extra=actual.keys()-expected.keys()
    return {'reference_rows':total, 'unlocated':invalid, 'strict_reference_positive':len(expected),
            'strict_server_positive':len(actual), 'common':len(actual.keys() & expected.keys()),
            'reference_only':len(missing), 'server_only':len(extra),
            'reference_only_in_review_band':len(missing & near.keys()),
            'unflagged_disagreements':len(missing-near.keys())+
                sum(not actual[k]['threshold_sensitive'] for k in extra),
            'reference_only_distances':[{'csv_offset_m':round(expected[k],3),
                'map_offset_m':near[k]['offset_m']} for k in sorted(missing) if k in near],
            'interpretation':'Separate published coordinate representations, not surveyed ground truth.'}


async def main():
    DEST.mkdir(exist_ok=True)
    outcome={'commit':os.getenv('GITHUB_SHA'), 'python':sys.version, 'platform':platform.platform(),
             'cpu_count':os.cpu_count(), 'checks':{}, 'source_validation':'not_started'}

    def save():
        (DEST/'results.json').write_text(json.dumps(outcome,indent=2,allow_nan=False),encoding='utf-8')

    parameters=StdioServerParameters(command=sys.executable,
                                     args=['-m','uk_data_mcp.civil_server','serve'])
    try:
        cold=[]
        for _ in range(3):
            start=time.perf_counter()
            async with Client(parameters, read_timeout_seconds=120) as client:
                tools=await client.list_tools()
                tools=getattr(tools,'tools',tools)
                cold.append((time.perf_counter()-start)*1000)
                assert len(tools)==29 and all(t.annotations.read_only_hint for t in tools)
        outcome['cold_start_ms']=cold
        async with Client(parameters, read_timeout_seconds=120) as client:
            async def call(tool,args):
                start=time.perf_counter()
                reply=await client.call_tool(tool,args)
                return reply.structured_content, (time.perf_counter()-start)*1000
            routing={}
            for phrase,domain in TARGETS.items():
                r,_=await call('civil_coverage',{'query':phrase})
                routing[phrase]=any(row['domain']==domain for row in r['data'])
            outcome['routing']=routing
            assert all(routing.values())
            warm=[]
            for _ in range(30):
                _,elapsed=await call('civil_coverage',{'query':'water'})
                warm.append(elapsed)
            outcome['warm_lookup']={'n':len(warm),'median_ms':statistics.median(warm),
                                    'p95_nearest_rank_ms':sorted(warm)[28]}
            for nation in ('England','Wales','Scotland','Northern Ireland'):
                for sector in ('gas','electricity','water'):
                    r,_=await call('utility_handoff',{'sector':sector,'nation':nation,'purpose':'capacity'})
                    assert r['network_capacity'] is None and r['excavation_clearance'] is None
            outcome['checks']['handoffs']=12
            # Wrong label must stop before any asset query, against live ONS polygons.
            args={'alignment':{'type':'LineString','coordinates':[[-3.2,55.95],[-3.19,55.95]]},
                  'nation':'England','layers':['flood_defences']}
            blocked,_=await call('corridor_screen',args)
            outcome['nation_mismatch']=blocked
            assert blocked['status']=='error' and blocked['error']['code']=='nation_mismatch'
            assert blocked['results']=={}
            # A coast / cross-border search must never be labelled an in-coverage zero.
            border={'alignment':{'type':'LineString','coordinates':[[-2.7,51.615],[-2.62,51.615]]},
                    'nation':'England','layers':['flood_defences']}
            r,_=await call('corridor_screen',border)
            outcome['coast_or_border']=r
            assert r['status']=='error' and r['results']=={}
            raw=await civil_tables.download('stats19-2025')
            outcome['reference_source']={'url':civil_tables.address('stats19-2025'),
                                         'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
            dig=json.loads(Path('examples/corridor_birmingham.json').read_text())
            leeds={**dig,'alignment':{'type':'LineString','coordinates':
                   [[-1.551,53.794],[-1.545,53.797],[-1.539,53.798]]},'layers':['collisions']}
            for name,args in (('digbeth',dig),('leeds',leeds)):
                r,elapsed=await call('corridor_screen',args)
                (DEST/(name+'.json')).write_text(json.dumps(r,indent=2,allow_nan=False),encoding='utf-8')
                validate_corridor_report(r)
                assert r['status']=='ok', r.get('error')
                assert r['jurisdiction']['status']=='verified'
                summary={k:{f:g.get(f) for f in ('status','matched_examined','returned',
                          'boundary_candidates_count','threshold_sensitive_matched','candidate_scan_complete')}
                         for k,g in r['results'].items()}
                comparison=reference(raw,r)
                outcome[name]={'duration_ms':elapsed,'layers':summary,'reference':comparison,
                               'structured_bytes':len(json.dumps(r).encode())}
                with (DEST/(name+'-chainages.csv')).open('w',newline='',encoding='utf-8') as out:
                    write_schedule(r,out)
                assert comparison['unflagged_disagreements']==0, comparison
                assert all(g['candidate_scan_complete'] and not g['more_matches_than_shown']
                           for g in r['results'].values())
                save()
            outcome['source_validation']='passed'
    except BaseException as exc:
        outcome['failure']={'type':type(exc).__name__,'message':str(exc)}
        outcome['source_validation']='failed'
        raise
    finally:
        save()
        print(json.dumps(outcome,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':
    asyncio.run(main())
