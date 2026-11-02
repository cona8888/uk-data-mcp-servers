"""Verify official files and an explicit vintage join. Separately report live HPI availability."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

from uk_data_mcp import civil_housing as h
from uk_data_mcp import civil_tables as t
from uk_data_mcp.civil_server import context
from uk_data_mcp.transport import HttpClient


async def main():
    with tempfile.TemporaryDirectory() as temp:
        os.environ['UK_CIVIL_CACHE'] = temp
        manifest = []
        for key in t.DATASETS:
            result = await t.prepare(key)
            print(key, result['area_count'], result['source_sha256'], flush=True)
            assert result['area_count'] > 200, (key, result['area_count'])
            for code in ('E08000025', 'W06000015'):
                row = t.area_record(key, code)
                assert row['status'] == 'ok', (key, code, row['status'])
                if key in t.CENSUS:
                    assert any(v['value'] is not None for v in row['data'][0]['observations'].values())
            manifest.append(result)
        code = 'E08000025'
        cells = t.area_record('ts001',code)['data'][0]['observations']
        totals = [cell['value'] for label,cell in cells.items() if 'total' in label.lower()]
        assert len(totals) == 1 and 1_140_000 < totals[0] < 1_150_000, cells
        crashes = t.area_record('stats19-2025',code)['data'][0]['reported_injury_collisions']
        print('Birmingham TS001 and STATS19:', totals[0], crashes, flush=True)
        assert crashes > 0
        price_source = await h.prepare()
        manifest.append(price_source)
        async with HttpClient(public_data=True) as client:
            bham = await context(client, code, 2025, '2024-01', h.EDITION)
            live = await context(client, code, 2025, '2024-01', 'live')
        assert bham['status'] == 'ok', {k:v.get('status') for k,v in bham['results'].items()}
        assert bham['results']['housing']['source']['edition'] == '2025-01'
        price = bham['results']['housing']['data'][0]['averagePrice']
        assert 100000 < price < 500000
        print('Optional HPI linked-data endpoint (not the release file):', live['results']['housing'].get('status'), live['results']['housing'].get('error'), flush=True)
        # The profile-specific smoke suite tests the live HPI service separately. Here the
        # assertion is the explicitly selected dated three-way join, never a silent fallback.
        line = f'Birmingham: {totals[0]:,} Census 2021 residents; {crashes:,} reported injury collisions in 2025; GBP {price:,.0f} Jan 2024 HPI (Jan 2025 vintage); linked API {live["results"]["housing"]["status"]}'
        print(line, flush=True)
        Path('civil-validation.json').write_text(json.dumps({'commit':os.environ.get('GITHUB_SHA'), 'sources':manifest,
            'Birmingham':bham,'live_hpi_diagnostic':live['results']['housing']}, indent=2), encoding='utf-8')
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                print('summary='+line, file=stream)


if __name__ == '__main__':
    asyncio.run(main())
