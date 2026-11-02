"""Synthetic integration and error contracts. No customer data or upstream requests."""

import csv
import io

import httpx
import pytest
from mcp import Client

from uk_data_mcp.meter_summary import summarize
from uk_data_mcp.public_catalogue import METER, TELEMETRY, public_sources
from uk_data_mcp.public_queries import (
    METER_PUBLISHER_ID,
    company_leakage,
    dataset_record,
    house_prices,
    ons_series,
)
from uk_data_mcp.public_server import TOOL_NAMES, create_server, invoke
from uk_data_mcp.transport import (
    LEAKAGE_PATH,
    DataAccessError,
    FetchResult,
    HttpClient,
    checked_url,
)

URI = '/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms'
OBS = 'http://landregistry.data.gov.uk/data/ukhpi/region/birmingham/month/2024-01'


class Stub:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def get_json(self, url, params=None):
        self.calls.append((url, params))
        return FetchResult(self.value, url, '2026-11-02T00:00:00Z', 'a'*64)


def test_routes_distinguish_manual_from_api_and_do_not_store_challenge_urls():
    routes = public_sources()['data']
    ids = {r['id']:r for r in routes}
    assert ids['waterwise']['capability'] == 'manual_reference'
    assert ids['waterwise']['url'] == 'https://database.waterwise.org.uk/'
    assert ids['ea_telemetry']['catalogue_id'] == TELEMETRY
    assert 'sgcaptcha' not in str(routes)
    assert 'waterwise' in {r['id'] for r in public_sources('waterwise')['data']}


@pytest.mark.parametrize('url', ['https://www.gov.uk/api/search.json', 'https://api.beta.ons.gov.uk/v1/data', 'https://landregistry.data.gov.uk/data/ukhpi.json'])
def test_routes_are_profile_scoped(url):
    assert checked_url(url, public_data=True) == url
    with pytest.raises(DataAccessError):
        checked_url(url)


@pytest.mark.parametrize('url', ['https://www.gov.uk/api/search.json/other', 'https://example.org/v1/data', 'https://database.waterwise.org.uk/', 'http://www.gov.uk/api/search.json'])
def test_no_generic_url_access(url):
    with pytest.raises(DataAccessError):
        checked_url(url, public_data=True)


@pytest.mark.asyncio
async def test_hpi_amount_period_geo_and_provenance():
    client = Stub({'result':{'items':[{'_about':OBS,'averagePrice':123456,'housePriceIndex':99}]}})
    r = await house_prices(client, 'birmingham', '2024-01')
    assert r['data'][0]['averagePrice'] == 123456 and r['metadata']['units']['averagePrice'] == 'GBP'
    assert r['provenance'][0]['response_sha256'] == 'a'*64
    assert client.calls[0][1]['refPeriodStart'] == '2024-01-01'
    assert 'unknown' not in r['metadata']['attribution'].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [OBS.replace('birmingham','leeds'), OBS.replace('2024-01','2023-01')])
async def test_wrong_hpi_identity_rejected(bad):
    with pytest.raises(DataAccessError):
        await house_prices(Stub({'result':{'items':[{'_about':bad, 'averagePrice':0}]}}),'birmingham','2024-01')


@pytest.mark.asyncio
async def test_no_hpi_results_not_zero():
    data = await house_prices(Stub({'result':{'items':[]}}),'birmingham','2024-01')
    assert data['status'] == 'empty' and data['data'] == []


@pytest.mark.asyncio
async def test_series_keeps_period_unit_flags_including_missing():
    client = Stub({'uri':URI,'description':{'cdid':'MGSX','unit':'%'},'years':[{'year':'2024','date':'2024','value':'..','quality':'suppressed'},{'date':'2023','value':'2.0'}]})
    r = await ons_series(client, URI, 2024, 'years')
    assert len(r['data']) == 1 and r['data'][0]['value'] == '..' and r['metadata']['series']['unit'] == '%'
    assert r['data'][0]['quality'] == 'suppressed'
    with pytest.raises(DataAccessError):
        await ons_series(Stub({'description':{'cdid':'OTHER'}, 'years':[]}), URI, 2024, 'years')


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args', [('house_prices',{'region':'../../x','month':'2024-01'}),('house_prices',{'region':'birmingham','month':'2024-13'}),('dataset_record',{'dataset_id':'http://evil.test'}),('ons_series',{'uri':'//evil.test/file','year':2024}),('find_public_data',{'query':'housing','limit':100}),('nista_publications',{'limit':0})])
async def test_reject_before_network(tool,args):
    stub = Stub(None)
    assert (await invoke(stub,tool,args))['status'] == 'error'
    assert not stub.calls


@pytest.mark.asyncio
async def test_alias_only_reads_catalogue_and_retains_resource_terms():
    client = Stub({'success':True,'result':{'id':METER,'name':'customer-meter-data','license_title':'OGL','resources':[{'url':'http://other.test/a.csv','format':'CSV','name':'2014-15'},{'name':'guidance'}]}})
    r = await dataset_record(client,'meter_yorkshire',limit=1)
    assert len(client.calls) == 1 and client.calls[0][1] == {'id':METER}
    assert r['metadata']['record']['license_title'] == 'OGL'
    assert r['pagination']['next_offset'] == 1 and r['metadata']['resource_bytes_fetched'] is False
    assert r['data'][0]['format'] == 'CSV' and r['status'] == 'partial'
    with pytest.raises(DataAccessError):
        await dataset_record(client,'ea_telemetry')


@pytest.mark.asyncio
async def test_meter_cross_listing_preserves_provenance_without_downloading():
    calls = []

    def handler(req):
        key = req.url.params['id']
        calls.append(key)
        assert req.url.host == 'ckan.publishing.service.gov.uk'
        rows = [{'name':'2010-11','url':'https://publisher.test/file.csv','format':'CSV'}] if key == METER_PUBLISHER_ID else []
        return httpx.Response(200,json={'success':True, 'result':{'id':key,'title':'Customer meter data','resources':rows}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        result = await dataset_record(HttpClient(client=raw,public_data=True,rate_interval=0),'meter_yorkshire')
    assert calls == [METER, METER_PUBLISHER_ID]
    assert len(result['provenance']) == 2 and result['metadata']['primary_resource_count'] == 0
    assert result['metadata']['record']['id'] == METER and result['metadata']['resource_listing_record']['id'] == METER_PUBLISHER_ID
    assert result['data'][0]['format'] == 'CSV' and result['metadata']['resource_bytes_fetched'] is False


@pytest.mark.asyncio
async def test_federated_search_preserves_partial_failure_and_real_empty():
    def handler(request):
        if request.url.host == 'api.beta.ons.gov.uk':
            return httpx.Response(200, json={'count':0,'items':[]})
        return httpx.Response(503)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = HttpClient(client=raw, public_data=True, rate_interval=0, max_retries=0)
        data = await invoke(client,'find_public_data',{'query':'water leakage'})
        assert data['status'] == 'partial'
        assert data['results']['ons']['status'] == 'empty' and data['results']['national_directory']['status'] == 'error'


@pytest.mark.asyncio
async def test_nista_filter_not_plain_text_search():
    c = Stub({'total':10,'results':[{'link':'/government/example','title':'Example'}]})
    r = await invoke(c,'nista_publications',{'limit':1})
    assert 'filter_organisations' in c.calls[0][1] and r['pagination']['next_offset'] == 1
    assert r['data'][0]['publication_url'].startswith('https://www.gov.uk/')


@pytest.mark.asyncio
async def test_leakage_rejects_wrong_table_and_retains_zero():
    other = '<table><tr><th>Company</th><th>Consumption</th></tr><tr><td>A</td><td>10%</td></tr></table>'
    good = '<table><thead><tr><th></th><th>Leakage as % of <abbr>DI</abbr></th></tr></thead><tbody><tr><td>Synthetic</td><td>0%</td></tr></tbody></table>'
    def page(html):
        return Stub({'base_path':LEAKAGE_PATH, 'details':{'body':html}})
    r = await company_leakage(page(other+good),'Synthetic')
    assert r['data'][0]['value'] == 0 and r['data'][0]['period'] == '2024/25'
    assert (await company_leakage(page(good),'Missing'))['status'] == 'empty'
    for invalid in (other,good+good,good.replace('0%','120%')):
        with pytest.raises(DataAccessError):
            await company_leakage(page(invalid))


@pytest.mark.parametrize('header', ['GROSS_CONSUMPTION','GROSS_COMSUMPTION'])
def test_meter_ratio_of_sums_suppression_missing_and_privacy(header):
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(['POSTAL_TOWN','READING_SOURCE','METER_KEY',header,'READING_START_DATE','READING_END_DATE'])
    for i in range(10):
        w.writerow(['A','Actual',f'private-key-{i}',1 if i else 10,'01/01/2015','11/01/2015' if i else '21/01/2015'])
    w.writerow(['A','Estimated','private-key-a',999,'01/01/2015','11/01/2015'])
    w.writerow(['A','Actual','private-key-z',-1,'01/01/2015','11/01/2015'])
    s.seek(0)
    r = summarize(s)
    assert len(r['groups']) == 1 and r['excluded_invalid_intervals'] == 1
    assert r['groups'][0]['litres_per_recorded_meter_day'] == round(19000/110,3)
    assert 'private-key' not in str(r)


@pytest.mark.asyncio
async def test_mcp_profile_lists_and_executes_without_network():
    async with Client(create_server()) as c:
        tools = await c.list_tools()
        tools = getattr(tools, 'tools', tools)
        assert {t.name for t in tools} == set(TOOL_NAMES)
        result = await c.call_tool('public_sources',{'query':'waterwise'})
        assert result.structured_content['data'][0]['id'] == 'waterwise'
