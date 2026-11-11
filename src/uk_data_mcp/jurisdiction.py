"""Fail-closed nation check against a fixed, versioned ONS country polygon service.

Only the padded search envelope is sent. The complete envelope must be within
one country: this deliberately rejects some valid near-border/coastal routes.
It never substitutes a centroid, a place name, or the caller's nation assertion.
"""

from .corridor_policy import COUNTRIES
from .transport import DataAccessError

SOURCE = ('https://www.data.gov.uk/dataset/c0ebe11c-0c81-4eed-81b3-a0394d4116a9/'
          'countries-december-2024-boundaries-uk-bgc1')
CODES = {'E92000001': 'England', 'W92000004': 'Wales',
         'S92000003': 'Scotland', 'N92000002': 'Northern Ireland'}


def country_records(doc):
    if (not isinstance(doc, dict) or 'error' in doc
            or not isinstance(doc.get('features'), list)
            or doc.get('exceededTransferLimit', False) is not False
            or len(doc['features']) > 4):
        raise DataAccessError('Invalid or incomplete country-boundary response.',
                              code='coverage_unverified', url=COUNTRIES)
    countries = {}
    for feature in doc['features']:
        attrs = feature.get('attributes') if isinstance(feature, dict) else None
        if not isinstance(attrs, dict):
            raise DataAccessError('Country attributes missing.', code='coverage_unverified')
        code, name = attrs.get('CTRY24CD'), attrs.get('CTRY24NM')
        if not isinstance(code, str) or code not in CODES or CODES[code] != name or code in countries:
            raise DataAccessError('Country identity is unknown, contradictory or duplicate.',
                                  code='coverage_unverified')
        countries[code] = name
    return countries


async def verify_jurisdiction(http, route, nation):
    """ArcGIS Within means the query envelope is within a target country polygon."""
    params = {'f': 'json', 'where': '1=1',
              'geometry': ','.join(f'{x:.3f}' for x in route.gb_box),
              'geometryType': 'esriGeometryEnvelope', 'inSR': 27700,
              'spatialRel': 'esriSpatialRelWithin', 'outFields': 'CTRY24CD,CTRY24NM',
              'returnGeometry': 'false', 'resultRecordCount': 5}
    audit = {'status': 'unverified', 'declared_nation': nation,
             'source_page': SOURCE, 'boundary_edition': '2024-12',
             'method': 'Entire padded search envelope within one ONS country polygon',
             'bbox_bng_m': route.gb_box, 'requests': [],
             'attribution': 'ONS Geography; contains OS data © Crown copyright and database right.',
             'limitations': ['20 m generalised, mean-high-water-clipped boundaries; not a legal or survey boundary.',
                            'The envelope includes the corridor radius and 25 m screening margin.',
                            'Border/coastal envelopes may be rejected conservatively; narrow or split the route.']}
    try:
        reply = await http.get_json(COUNTRIES, params=params)
        audit['requests'].append(reply.provenance())
        within = country_records(reply.data)
        audit['containing_countries'] = list(within.values())
        if len(within) == 1 and list(within.values()) == [nation]:
            audit['status'] = 'verified'
            return audit
        if len(within) == 1:
            audit.update(status='mismatch', error={'code': 'nation_mismatch',
                         'message': 'Declared nation differs from the polygon containing the search envelope.'})
            return audit
        if len(within) > 1:
            raise DataAccessError('Overlapping country coverage; cannot certify one jurisdiction.',
                                  code='coverage_unverified')
        reply = await http.get_json(COUNTRIES, params={**params, 'spatialRel': 'esriSpatialRelIntersects'})
        audit['requests'].append(reply.provenance())
        intersecting = country_records(reply.data)
        audit['intersecting_countries'] = list(intersecting.values())
        audit.update(status='unverified', error={'code': 'border_or_coast_unverified',
                     'message': 'The whole search envelope is not within one country. Split or narrow the query; no asset search was performed.'})
    except DataAccessError as exc:
        audit['error'] = {'code': 'coverage_unverified', 'cause': exc.code, 'message': str(exc),
                          'url': exc.url}
    return audit
