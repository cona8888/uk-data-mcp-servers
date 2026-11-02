"""Unified local UK civil engineering MCP server. No special credentials required."""

import argparse
import asyncio
import csv
import json
import re
import sys
import zipfile
from typing import Literal

import httpx

from . import civil_housing as housing
from . import civil_tables as tables
from . import public_server
from .civil_coverage import civil_coverage
from .service import TOOLS, DataService
from .transport import DataAccessError, HttpClient

GROUND = ('list_sources', 'source_details', *TOOLS, 'site_context', 'desk_study')
CIVIL = ('civil_coverage', 'area_census', 'road_collisions', 'civil_area_context')
NAMES = (*GROUND, *public_server.TOOL_NAMES, *CIVIL)
HPI_AREAS = {'E08000025': 'birmingham', 'E08000035': 'leeds', 'W06000015': 'cardiff'}


def census(gss_code, table='ts001'):
    if table not in tables.CENSUS:
        raise ValueError('Use a supported Census 2021 table: ' + ', '.join(tables.CENSUS))
    return tables.area_record(table, gss_code)


def collisions(gss_code, year=2025):
    if type(year) is not int or year not in tables.YEARS:
        raise ValueError('Supported final STATS19 editions are 2024 and 2025.')
    return tables.area_record(f'stats19-{year}', gss_code)


async def context(http, gss_code, collision_year=2025, housing_month=None, housing_edition='live'):
    if housing_month is not None and (not isinstance(housing_month, str) or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])', housing_month)):
        raise ValueError('Use an explicit YYYY-MM for the optional housing period.')
    if housing_edition not in ('live',housing.EDITION):
        raise ValueError('housing_edition must be live or ' + housing.EDITION)
    result = {'population': await asyncio.to_thread(census, gss_code),
              'road_safety': await asyncio.to_thread(collisions, gss_code, collision_year)}
    if housing_month is not None:
        slug = HPI_AREAS.get(gss_code)
        if housing_edition == housing.EDITION:
            result['housing'] = await asyncio.to_thread(housing.record, gss_code, housing_month)
        elif slug:
            result['housing'] = await public_server.invoke(http, 'house_prices', {'region': slug, 'month': housing_month})
            result['housing']['area_mapping'] = {'code': gss_code, 'hpi_slug': slug,
                'authority_reference': f'https://www.ons.gov.uk/explore-local-statistics/areas/{gss_code}-{slug}'}
            if result['housing']['status'] == 'error' and housing_month <= housing.EDITION:
                result['housing']['alternative'] = {'prepare':'uk-civil-data prepare '+housing.KEY,
                    'housing_edition':housing.EDITION,'note':'Re-run with this explicit historical publication; live result was not replaced.'}
        else:
            result['housing'] = {'status':'error', 'error':{'code':'no_reviewed_area_mapping'}, 'data':[]}
    statuses = [r['status'] for r in result.values()]
    return {'status': 'ok' if all(x == 'ok' for x in statuses) else 'error' if all(x == 'error' for x in statuses) else 'partial',
            'gss_code': gss_code, 'results': result,
            'warning': 'Same area code does not prove identical boundaries or dates. Census, collision year and HPI month remain separate. No causal inference, collision rate or site-level exposure is calculated.'}


async def invoke(http, name, args):
    if name not in NAMES or not isinstance(args, dict):
        raise ValueError('Unknown tool or invalid argument object.')
    try:
        if name in public_server.TOOL_NAMES:
            return await public_server.invoke(http, name, args)
        if name in GROUND:
            return await DataService(http).call(name, args)
        if name == 'civil_area_context':
            return await context(http, **args)
        fn = {'civil_coverage': civil_coverage, 'area_census': census, 'road_collisions': collisions}[name]
        return await asyncio.to_thread(fn, **args)
    except (ValueError, TypeError, DataAccessError, OSError, RecursionError) as e:
        return {'status': 'error', 'tool': name, 'error': {'code': getattr(e, 'code', 'invalid_request_or_cache'), 'message': str(e)}, 'data': []}


def create_server(http=None):
    from .server import READ_ONLY, _result
    from .server import create_server as ground_server

    client = http if http is not None else HttpClient(public_data=True)
    server = ground_server(client)
    public_server.register_tools(server, lambda: client)

    @server.tool(name='civil_coverage', annotations=READ_ONLY)
    def coverage(query: str = ''):
        """Find a civil domain and its next tool. Distinguish direct queries, prepared official data, metadata, manual discovery and restricted records."""
        return _result(civil_coverage(query))

    @server.tool(annotations=READ_ONLY)
    async def area_census(gss_code: str, table: Literal['ts001','ts041','ts045','ts061','ts066'] = 'ts001'):
        """Read one 2021 England/Wales LTLA by GSS code: residents, households, cars, commuting or economic activity. Requires the prepared Nomis edition; not a current estimate."""
        return _result(await invoke(client, 'area_census', {'gss_code': gss_code, 'table': table}))

    @server.tool(annotations=READ_ONLY)
    async def road_collisions(gss_code: str, year: int = 2025):
        """Count GB STATS19 police-reported injury collisions by district and raw severity, 2024 or 2025. Not casualties, live incidents or traffic risk. Requires a prepared edition."""
        return _result(await invoke(client, 'road_collisions', {'gss_code': gss_code, 'year': year}))

    @server.tool(annotations=READ_ONLY)
    async def civil_area_context(gss_code: str, collision_year: int = 2025, housing_month: str | None = None,
                                housing_edition: Literal['live','2025-01'] = 'live'):
        """Compare census and road safety using a GSS area code; optional HPI: live (3 reviewed areas) or a prepared January 2025 release matched by code. No silent vintage substitution or risk rate."""
        return _result(await invoke(client, 'civil_area_context', dict(gss_code=gss_code, collision_year=collision_year, housing_month=housing_month, housing_edition=housing_edition)))

    return server


def main():
    p = argparse.ArgumentParser(description='UK civil engineering data: one MCP connection')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('serve', help='Start one read-only stdio gateway')
    sub.add_parser('tools', help='List registered tools')
    prep = sub.add_parser('prepare', help='Download a specified public edition to a local aggregate index')
    prep.add_argument('editions', nargs='+', choices=(*tables.DATASETS,housing.KEY))
    call = sub.add_parser('call')
    call.add_argument('tool', choices=NAMES)
    call.add_argument('--json', default='{}')
    args = p.parse_args()
    if args.cmd == 'serve':
        create_server().run(transport='stdio')
        return
    if args.cmd == 'tools':
        print(json.dumps(NAMES, indent=2))
        return

    async def run():
        if args.cmd == 'prepare':
            return [await housing.prepare() if key == housing.KEY else await tables.prepare(key) for key in dict.fromkeys(args.editions)]
        params = json.loads(args.json)
        async with HttpClient(public_data=True) as http:
            return await invoke(http, args.tool, params)

    try:
        result = asyncio.run(run())
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
        if isinstance(result, dict) and result.get('status') == 'error':
            raise SystemExit(1)
    except (ValueError, csv.Error, zipfile.BadZipFile, httpx.HTTPError, OSError) as exc:
        print(f'Civil data error: {exc}', file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == '__main__':
    main()
