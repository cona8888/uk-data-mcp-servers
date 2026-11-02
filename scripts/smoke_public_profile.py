"""One-off low-volume contract checks. Record counts, statuses and digests, never customer rows."""

import asyncio
import json
from pathlib import Path

from uk_data_mcp.public_server import invoke
from uk_data_mcp.transport import HttpClient, utc_now


async def run():
    calls = [
        ('national_search','find_public_data',{'query':'housing','catalogue':'national_directory','limit':1}),
        ('ons_search','find_public_data',{'query':'employment','catalogue':'ons','limit':1}),
        ('hpi','house_prices',{'region':'birmingham','month':'2024-01'}),
        ('social','ons_series',{'uri':'/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms','year':2024,'frequency':'years'}),
        ('leakage','company_leakage',{'company':'Severn Trent Water'}),
        ('meter_record','dataset_record',{'dataset_id':'meter_yorkshire'}),
        ('quality_record','dataset_record',{'dataset_id':'ea_telemetry'}),
        ('nista','nista_publications',{'limit':1}),
    ]
    report = []
    async with HttpClient(public_data=True,max_retries=0) as http:
        for label, tool, args in calls:
            try:
                value = await invoke(http,tool,args)
                result = value.get('results',{}).get(args.get('catalogue'),value)
                rows = result.get('data',[])
                passed = result.get('status') in ('ok','partial') and isinstance(rows,list) and bool(rows)
                report.append({'check':label,'passed':passed,'status':result.get('status'),'count':len(rows),'query':args,
                               'error':result.get('error'),'provenance':result.get('provenance',[]),
                               'sample':rows[:1] if label in ('hpi','social','leakage') else None})
            except Exception as exc:
                report.append({'check':label,'passed':False,'error':str(exc)})
    out = {'checked_at_utc':utc_now(),'checks':report}
    Path('public-smoke.json').write_text(json.dumps(out,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    for r in report:
        print(r['check'], 'PASS' if r['passed'] else 'FAIL', r.get('error') or '', r.get('sample') or '')
    return all(r['passed'] for r in report)


if __name__ == '__main__':
    raise SystemExit(0 if asyncio.run(run()) else 1)
