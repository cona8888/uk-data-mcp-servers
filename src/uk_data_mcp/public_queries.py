"""Public tool implementations and explicit catalogue crosswalks."""

from . import _public_endpoints as api
from .public_catalogue import METER
from .transport import DataAccessError

company_leakage = api.company_leakage
find_public_data = api.find_public_data
house_prices = api.house_prices
nista_publications = api.nista_publications
ons_search = api.ons_search
ons_series = api.ons_series

# Distinct national catalogue entries describing the same historical Yorkshire series.
# Never replace the identity, publisher or licence of one with those of the other.
METER_PUBLISHER_ID = '8e6a9811-59ea-46de-a941-4207a3641292'
PUBLISHER_PAGE = 'https://datamillnorth.org/dataset/customer-meter-data-2jqzm'


async def dataset_record(client, dataset_id, limit=20, offset=0):
    result = await api.dataset_record(client, dataset_id, limit, offset)
    metadata = result['metadata']
    if metadata['record'].get('id') != METER or metadata['resource_count']:
        return result
    # Some API harvests preserve the Calderdale description but not the file links.
    # Query an explicitly reviewed second record, not an unconstrained search or arbitrary URL.
    metadata['publisher_landing_page'] = PUBLISHER_PAGE
    try:
        alternate = await api.dataset_record(client, METER_PUBLISHER_ID, limit, offset)
    except DataAccessError as exc:
        result['status'] = 'partial'
        result['warnings'].append('The primary record has no resource links in CKAN. See the publisher landing page.')
        metadata['resource_lookup_error'] = {'code':exc.code, 'message':str(exc), 'url':exc.url}
        return result
    alt = alternate['metadata']['record']
    result['provenance'] += alternate['provenance']
    if alt.get('id') != METER_PUBLISHER_ID or str(alt.get('title','')).strip().casefold() != 'customer meter data':
        raise DataAccessError('Cross-listed meter record did not match the reviewed identity.', code='invalid_response')
    metadata['primary_resource_count'] = 0
    metadata['resource_listing_record'] = alt
    metadata['resource_count'] = alternate['metadata']['resource_count']
    metadata['resource_listing_terms'] = 'The original catalogue records OGL. The Yorkshire Water / Data Mill North publisher page specifies Creative Commons Attribution. Check the terms for the particular file before reuse.'
    result['data'] = alternate['data']
    result['pagination'] = alternate['pagination']
    result['status'] = alternate['status'] if metadata['resource_count'] else 'partial'
    result['warnings'].append('File links are from the separately identified Data Mill North catalogue record, not from the primary CKAN resource list. No files downloaded.')
    return result
