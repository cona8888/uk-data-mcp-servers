"""Bounded cross-sector queries. The caller cannot select a network host or raw query language."""

import asyncio
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .adapters.discovery import data_gov_search
from .public_catalogue import ALIASES, NISTA, ONS, SOURCES, public_sources
from .transport import LEAKAGE_PATH, DataAccessError


def _word(q, maximum=180):
    if not isinstance(q, str) or not q.strip() or len(q) > maximum or any(ord(c) < 32 for c in q):
        raise ValueError('Supply a non-empty bounded search term without control characters.')
    return q.strip()


def _page(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 25 or type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError('limit must be 1..25 and offset 0..10000')


def _obj(value, res):
    if not isinstance(value, dict):
        raise DataAccessError('Expected a provider object.', code='invalid_response', url=res.url)
    return value


def _rows(value, res):
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise DataAccessError('Expected a provider array of records.', code='invalid_response', url=res.url)
    return value


def _pick(item, fields):
    return {k: item[k] for k in fields.split() if k in item}


def _result(source, res, rows, kind, query, *, more=False, offset=0, **meta):
    return dict(schema_version='1.0', source_id=source, source=SOURCES[source], kind=kind,
                status='partial' if more or offset else 'ok' if rows else 'empty', query=query,
                data=rows, provenance=[res.provenance()], retrieved_at_utc=res.retrieved_at,
                pagination={'returned': len(rows), 'next_offset': offset + len(rows) if more and rows else None},
                metadata=meta, warnings=[SOURCES[source]['limitation']])


def _provider_page(source, res, rows, total, query, limit, offset, **meta):
    if type(total) is not int or total < 0 or len(rows) > limit:
        raise DataAccessError('Unrecognised provider pagination.', code='invalid_response', url=res.url)
    return _result(source, res, rows, 'publication_metadata', query, more=offset+len(rows)<total,
                   offset=offset, provider_total=total, **meta)


async def ons_search(client, query, limit=5, offset=0):
    _page(limit, offset)
    q = _word(query)
    res = await client.get_json('https://api.beta.ons.gov.uk/v1/search', {'q': q, 'limit': limit, 'offset': offset, 'highlight': 'false'})
    doc = _obj(res.data, res)
    rows = []
    for item in _rows(doc.get('items'), res):
        row = _pick(item, 'title uri type dataset_id release_date cdid summary')
        uri = row.get('uri')
        if isinstance(uri, str) and re.fullmatch(r'/[A-Za-z0-9/_%.\-]+', uri) and not uri.startswith('//'):
            row['publication_url'] = ONS + uri
        rows.append(row)
    return _provider_page('ons', res, rows, doc.get('count'), {'query': q, 'limit': limit, 'offset': offset}, limit, offset)


async def find_public_data(client, query, limit=5, offset=0, catalogue='both'):
    """Search both national indexes without silently treating a failed source as empty."""
    q = _word(query)
    _page(limit, offset)
    if catalogue not in ('both', 'ons', 'national_directory'):
        raise ValueError('catalogue must be both, ons or national_directory')

    async def run(key, fn):
        try:
            return key, await fn(client, q, limit=limit, offset=offset)
        except DataAccessError as exc:
            return key, {'status': 'error', 'source': SOURCES[key], 'data': [], 'error': {'code': exc.code, 'url': exc.url, 'message': str(exc)}}

    calls = [(key, fn) for key, fn in [('national_directory', data_gov_search), ('ons', ons_search)] if catalogue in ('both', key)]
    results = dict(await asyncio.gather(*(run(k, fn) for k, fn in calls)))
    statuses = [d['status'] for d in results.values()]
    status = ('error' if all(v == 'error' for v in statuses) else 'partial' if any(v in ('error','partial') for v in statuses)
              else 'empty' if all(v == 'empty' for v in statuses) else 'ok')
    return {'status': status, 'kind': 'catalogue_search', 'query': q, 'limit_per_catalogue': limit,
            'offset_per_catalogue': offset, 'results': results, 'curated_routes': public_sources(q)['data'],
            'note': 'Catalogues can overlap. Do not sum hits or treat metadata as measured values. No resources were downloaded.'}


async def dataset_record(client, dataset_id, limit=20, offset=0):
    _page(limit, offset)
    value = ALIASES.get(dataset_id, dataset_id) if isinstance(dataset_id, str) else None
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', value):
        raise ValueError('Expected a national catalogue UUID, slug or documented alias.')
    res = await client.get_json('https://ckan.publishing.service.gov.uk/api/3/action/package_show', {'id': value})
    doc = _obj(res.data, res)
    record = _obj(doc.get('result'), res)
    if doc.get('success') is not True or value not in (record.get('id'), record.get('name')) or record.get('private') is True:
        raise DataAccessError('No matching public dataset record.', code='invalid_response', url=res.url)
    resources = _rows(record.get('resources'), res)
    rows = [_pick(r, 'id name format url last_modified created license license_id') for r in resources[offset:offset+limit]]
    info = _pick(record, 'id name title notes license_id license_title license_url isopen metadata_created metadata_modified')
    # CKAN notes and links are untrusted metadata. Never return maintained contact lists or fetch resource URLs.
    info['publisher'] = (record.get('organization') or {}).get('title') if isinstance(record.get('organization'), dict) else None
    key = next((k for k, v in ALIASES.items() if record.get('id') == v), 'national_directory')
    result = _result(key, res, rows, 'dataset_metadata_and_resource_links', {'dataset_id': dataset_id, 'limit': limit, 'offset': offset}, more=offset+limit<len(resources), offset=offset, record=info, resource_count=len(resources), resource_bytes_fetched=False)
    if not resources:
        result['status'] = 'ok'  # A real catalogue record, even when it supplies no downloadable resources.
    return result


async def house_prices(client, region, month):
    if not isinstance(region, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', region) or len(region)>100:
        raise ValueError('Expected a Land Registry region slug, e.g. birmingham or united-kingdom.')
    if not isinstance(month, str) or not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', month):
        raise ValueError('Expected YYYY-MM.')
    date.fromisoformat(month + '-01')
    params = {'refRegion': 'http://landregistry.data.gov.uk/id/region/'+region, 'refPeriodStart': month+'-01', '_pageSize': 2,
              '_properties': 'refMonth,refRegion,refPeriodStart,averagePrice,housePriceIndex,percentageAnnualChange,percentageChange,salesVolume'}
    res = await client.get_json('https://landregistry.data.gov.uk/data/ukhpi.json', params)
    doc = _obj(_obj(res.data, res).get('result'), res)
    items = _rows(doc.get('items'), res)
    expected = '/data/ukhpi/region/'+region+'/month/'+month
    if len(items)>1 or any(i.get('_about') not in ('http://landregistry.data.gov.uk'+expected, 'https://landregistry.data.gov.uk'+expected) for i in items):
        raise DataAccessError('HPI geography or period does not match the request.', code='invalid_response', url=res.url)
    if items and not any(items[0].get(k) is not None for k in ('averagePrice','housePriceIndex')):
        raise DataAccessError('HPI record has no price or index field.', code='invalid_response', url=res.url)
    rows = [dict(region=region, period=month, **_pick(i, '_about refMonth refRegion averagePrice housePriceIndex percentageAnnualChange percentageChange salesVolume')) for i in items]
    return _result('uk_hpi', res, rows, 'observations', {'region': region, 'month': month}, units={'averagePrice':'GBP','housePriceIndex':'index points','percentageAnnualChange':'%','percentageChange':'%','salesVolume':'transactions'}, attribution=f'Contains HM Land Registry data © Crown copyright and database right {res.retrieved_at[:4]}. This data is licensed under the Open Government Licence v3.0.')


async def ons_series(client, uri, year, frequency='months'):
    if not isinstance(uri, str) or len(uri)>240 or not re.fullmatch(r'/(?:[a-z0-9-]+/){1,8}timeseries/[a-z0-9]+/[a-z0-9-]+', uri):
        raise ValueError('Supply the ONS relative time-series URI returned by search, not a URL.')
    if type(year) is not int or not 1800 <= year <= 2100 or frequency not in ('months','quarters','years'):
        raise ValueError('Supply a four-digit year and months, quarters or years.')
    res = await client.get_json('https://api.beta.ons.gov.uk/v1/data', {'uri': uri})
    doc = _obj(res.data, res)
    desc = _obj(doc.get('description'), res)
    if str(desc.get('cdid','')).casefold() != uri.split('/')[-2] or (doc.get('uri') and doc['uri'].casefold() != uri):
        raise DataAccessError('Returned ONS series identity differs from request.', code='invalid_response', url=res.url)
    if not any(isinstance(doc.get(k), list) for k in ('months','quarters','years')):
        raise DataAccessError('Not an ONS time-series response.', code='invalid_response', url=res.url)
    rows = [r for r in _rows(doc.get(frequency, []), res) if str(r.get('year') or str(r.get('date',''))[:4]) == str(year)]
    if len(rows) > {'months':12, 'quarters':4, 'years':1}[frequency]:
        raise DataAccessError('Ambiguous repeated periods; do not aggregate.', code='invalid_response', url=res.url)
    return _result('ons', res, rows, 'observations', {'uri':uri, 'year':year, 'frequency':frequency},
                   series=_pick(desc,'title cdid datasetId unit preUnit releaseDate nextRelease edition source notes nationalStatistic'),
                   publication_url=ONS+uri, interpretation='Observation values and flags kept as supplied. Missing or suppressed does not mean zero; check the series definition, denominator and geographic scope.')


async def nista_publications(client, query='', limit=5, offset=0):
    _page(limit, offset)
    params = {'filter_organisations': NISTA, 'count': limit, 'start': offset, 'fields':'title,link,description,public_timestamp,format,organisations'}
    if query:
        params['q'] = _word(query)
    res = await client.get_json('https://www.gov.uk/api/search.json', params)
    doc = _obj(res.data, res)
    rows = []
    for item in _rows(doc.get('results'), res):
        row = _pick(item, 'title link description public_timestamp format organisations')
        link = row.get('link')
        if isinstance(link, str) and link.startswith('/') and not link.startswith('//') and not urlsplit(link).netloc:
            row['publication_url'] = 'https://www.gov.uk'+link
        rows.append(row)
    return _provider_page('nista', res, rows, doc.get('total'), {'query':query,'limit':limit,'offset':offset}, limit, offset)


class _Tables(HTMLParser):
    """Extract table cells only; no scripts, links or embedded resources are executed."""
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = []
        elif self.table is not None and tag == 'tr':
            self.row = []
        elif self.row is not None and tag in ('td','th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('th','td') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


async def company_leakage(client, company=''):
    """Fetch Figure 8 in a specific EA annual release. Never substitute consumption or a forecast."""
    if company:
        company = _word(company, 100)
    res = await client.get_json('https://www.gov.uk/api/content'+LEAKAGE_PATH)
    doc = _obj(res.data, res)
    body = _obj(doc.get('details'), res).get('body')
    if doc.get('base_path') != LEAKAGE_PATH or not isinstance(body, str):
        raise DataAccessError('Expected the reviewed 2024/25 EA publication.', code='invalid_response', url=res.url)
    parser = _Tables()
    parser.feed(body)
    parser.close()
    tables = [t for t in parser.tables if t and len(t[0]) == 2 and 'leakage' in t[0][1].lower() and '%' in t[0][1] and re.search(r'\bdi\b|distribution input',t[0][1],re.I)]
    if len(tables) != 1 or len(tables[0]) < 2:
        raise DataAccessError('Leakage indicator table missing or ambiguous.', code='invalid_response', url=res.url)
    rows = []
    seen = set()
    for cells in tables[0][1:]:
        if len(cells)!=2 or not cells[0] or cells[0] in seen or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?\s*%', cells[1]):
            raise DataAccessError('Unexpected leakage table row; consult the release.', code='invalid_response', url=res.url)
        seen.add(cells[0])
        value = float(cells[1].replace('%',''))
        if not 0 <= value <= 100:
            raise DataAccessError('Invalid percentage.', code='invalid_response', url=res.url)
        if not company or company.casefold() == cells[0].casefold():
            rows.append({'area_as_published': cells[0], 'period':'2024/25', 'value':value, 'unit':'% of distribution input', 'reported_as':cells[1]})
    return _result('ea_leakage', res, rows, 'observations', {'company':company}, release='2024/25', table='Figure 8', publication_updated=doc.get('public_updated_at'))
