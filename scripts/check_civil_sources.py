"""Explicit live integration check; persist aggregate evidence only, never raw records."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

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
        async with HttpClient(public_data=True) as client:
            bham = await context(client, 'E08000025', 2025, '2024-01')
        assert bham['status'] == 'ok', {k: v.get('status') for k, v in bham['results'].items()}
        cells = bham['results']['population']['data'][0]['observations']
        totals = [cell['value'] for label,cell in cells.items() if 'total' in label.lower()]
        assert len(totals) == 1 and 1_140_000 < totals[0] < 1_150_000, cells
        crashes = bham['results']['road_safety']['data'][0]['reported_injury_collisions']
        assert crashes > 0
        file = Path('civil-validation.json')
        file.write_text(json.dumps({'commit':os.environ.get('GITHUB_SHA'), 'sources':manifest, 'Birmingham':bham}, indent=2), encoding='utf-8')
        line = f'Birmingham: {totals[0]:,} 2021 residents; {crashes:,} reported injury collisions in 2025'
        print(line)
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                print('summary='+line, file=stream)


if __name__ == '__main__':
    asyncio.run(main())
