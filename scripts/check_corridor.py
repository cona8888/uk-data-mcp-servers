"""Reproduce a hypothetical Birmingham alignment and retain a bounded, dated evidence pack."""
import asyncio
import csv
import json
import os
from pathlib import Path

from uk_data_mcp.civil_server import invoke
from uk_data_mcp.transport import HttpClient


async def main():
    args=json.loads(Path('examples/corridor_birmingham.json').read_text())
    async with HttpClient(public_data=True) as client:
        report=await invoke(client,'corridor_screen',args)
    dest=Path('corridor-evidence')
    dest.mkdir(exist_ok=True)
    report['example']='Hypothetical Birmingham alignment, not an adopted road or rail scheme.'
    report['implementation_commit']=os.getenv('GITHUB_SHA')
    (dest/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print('Metric:',report.get('metric'),flush=True)
    out = report.get('results',{})
    labels=[]
    features=[{'type':'Feature','geometry':args['alignment'],'properties':{'role':'hypothetical alignment'}}]
    with (dest/'features.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['layer','source_feature_id','offset_m','chainage_m','intersection','nearest_lon','nearest_lat'])
        for key,r in out.items():
            print(key, {k:r.get(k) for k in ('status','bbox_candidate_count','features_examined','outside_corridor','matched_examined','returned','issues','error')},flush=True)
            labels.append(f"{key}:{r.get('matched_examined')}({r['status']})")
            for item in r['data']:
                assert 0<=item['offset_m']<=args['radius_m'] and 0<=item['chainage_m']<=report['metric']['length_m']+.001
                props={'layer':key,'source_feature_id':item['source_feature_id'],'offset_m':item['offset_m'],'chainage_m':item['chainage_m'],'role':'nearest point on source feature; not an asset footprint'}
                point=item['nearest_feature_lonlat']
                features.append({'type':'Feature','geometry':{'type':'Point','coordinates':point},'properties':props})
                w.writerow([key,item['source_feature_id'],item['offset_m'],item['chainage_m'],item['centreline_intersects'],*point])
    (dest/'locators.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
    line = ' | '.join(labels)[:240]
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
            print('summary='+line,file=f)
    assert set(out)=={'boreholes','bridges','collisions','flood_defences','communities'},report.get('error')
    assert all(r['status'] in ('ok','empty') and r['candidate_scan_complete'] and r['requests'] for r in out.values()),line
    assert out['communities']['matched_examined'] and out['boreholes']['matched_examined'],line


if __name__=='__main__':
    asyncio.run(main())
