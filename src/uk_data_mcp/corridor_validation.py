"""Strict source contracts. A completed request is not a complete inventory."""

from .transport import DataAccessError

# RFC 7946 GeoJSON is longitude/latitude when no legacy CRS member is present.
# Explicit legacy declarations are accepted only by exact reviewed identifier.
CRS84_NAMES = frozenset({
    'OGC:CRS84', 'CRS84', 'urn:ogc:def:crs:OGC:1.3:CRS84',
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'https://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'EPSG:4326', 'urn:ogc:def:crs:EPSG::4326',
    'urn:ogc:def:crs:EPSG:6.6:4326',
    'http://www.opengis.net/def/crs/EPSG/0/4326',
    'https://www.opengis.net/def/crs/EPSG/0/4326',
})


def invalid(message):
    raise DataAccessError(message, code='invalid_response')


def geojson_features(payload):
    if (not isinstance(payload, dict) or payload.get('type') != 'FeatureCollection'
            or not isinstance(payload.get('features'), list)):
        invalid('Provider did not return a GeoJSON FeatureCollection.')
    crs = payload.get('crs')
    if crs is not None:
        if (not isinstance(crs, dict) or set(crs) != {'type', 'properties'}
                or crs['type'] != 'name' or not isinstance(crs['properties'], dict)
                or set(crs['properties']) != {'name'}
                or not isinstance(crs['properties']['name'], str)
                or crs['properties']['name'] not in CRS84_NAMES):
            invalid('Unsupported or ambiguous GeoJSON coordinate reference system.')
    rows = payload['features']
    if 'numberReturned' in payload:
        n = payload['numberReturned']
        if type(n) is not int or n != len(rows):
            invalid('numberReturned contradicts the feature list.')
    if 'exceededTransferLimit' in payload and type(payload['exceededTransferLimit']) is not bool:
        invalid('Invalid transfer-limit flag.')
    return rows


def page_contract(doc, start, returned, previous_total):
    """Validate OGC totals and next links before consuming or declaring a page complete."""
    total = doc.get('numberMatched')
    if total not in (None, 'unknown') and (type(total) is not int or total < 0):
        invalid('Invalid numberMatched; expected a non-negative integer or unknown.')
    total = total if type(total) is int else None
    if previous_total is not None and total is not None and total != previous_total:
        invalid('Upstream candidate count changed between pages; repeat the search.')
    effective = total if total is not None else previous_total
    if effective is not None and start + returned > effective:
        invalid('numberMatched is smaller than the number of features returned.')
    links = doc.get('links', [])
    if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
        invalid('Invalid pagination links.')
    next_links = [link for link in links if link.get('rel') == 'next']
    if len(next_links) > 1 or any(not isinstance(link.get('href'), str) or not link['href']
                                 for link in next_links):
        invalid('Ambiguous or invalid next-page link.')
    more = bool(next_links) or doc.get('exceededTransferLimit', False)
    if more and effective is not None and start + returned >= effective:
        invalid('Next-page indicator contradicts numberMatched.')
    if not returned and (more or (effective is not None and start < effective)):
        invalid('Pagination did not advance although more candidates were indicated.')
    return effective, more
