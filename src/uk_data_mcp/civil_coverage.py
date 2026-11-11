"""Reviewed source directory with practical vocabulary and explicit evidence handoffs."""

from ._civil_routes import civil_coverage as _base
from ._civil_routes import route
from .corridor_policy import PRODUCTS
from .utility_handoff import NATIONS, intent_domains, tokens


def civil_coverage(query='', nation=None):
    result = _base(query)  # also validates query type/length
    if nation is not None and nation not in NATIONS:
        raise ValueError('Use a UK nation or leave nation unspecified.')
    words = query.casefold().replace('_', ' ').split()
    selected = intent_domains(query) if query else set()
    existing = {(r['domain'], r['product']) for r in result['data']}
    for row in _base()['data']:
        if row['domain'] in selected and (row['domain'], row['product']) not in existing:
            row['match_basis'] = 'reviewed_task_vocabulary'
            result['data'].append(row)
    for key, (_, title, area, url, terms) in PRODUCTS.items():
        domain = 'corridor ' + key
        if all(w in f'{domain} {title} {area}'.replace('_', ' ').casefold() for w in words):
            result['data'].append(route(domain, title, 'query', area, url, terms, 'corridor_screen',
                alignment={'type': 'LineString', 'coordinates': [[-1.888, 52.4728], [-1.8856, 52.47515]]},
                nation='England', radius_m=250, layers=[key]))
    w = tokens(query)
    for row in result['data']:
        domain = row['domain']
        if domain not in ('utilities', 'energy', 'water'):
            continue
        sector = ('gas' if domain == 'utilities' and 'gas' in w else 'electricity'
                  if domain == 'energy' or w & {'electricity', 'electric', 'cable', 'cables'}
                  else 'water' if domain == 'water' else 'utilities')
        purpose = ('diversion' if w & {'divert', 'diversion'} else 'connection'
                   if w & {'connection', 'connect'} else 'capacity'
                   if w & {'capacity', 'headroom'} else 'asset_records')
        row['handoff'] = {'tool': 'utility_handoff',
                          'arguments': {'sector': sector, 'nation': nation, 'purpose': purpose}}
        # Do not route a sewer-capacity request to a company-level leakage number.
        if domain == 'utilities' or purpose != 'asset_records':
            row['next_call'] = row['handoff']
        row['scope_note'] = 'A directory match or handoff is not retrieved utility evidence.'
    result['count'] = len(result['data'])
    result['status'] = 'ok' if result['count'] else 'empty'
    result['nation_filter'] = nation
    result['nation_filter_note'] = 'Nation selects handoff guidance, not a claim that every listed product covers it.'
    if not result['data']:
        result['next_action'] = {'tool': 'find_public_data', 'arguments': {'query': query}}
        result['note'] += ' No reviewed match does not mean no assets or no data exist.'
    return result
