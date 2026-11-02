"""Include operating spatial connectors alongside the wider civil product directory."""
from ._civil_routes import civil_coverage as _base
from ._civil_routes import route
from .corridor_policy import PRODUCTS


def civil_coverage(query=''):
    result = _base(query)
    words = query.casefold().replace('_',' ').split()
    for key, (_, title, area, url, terms) in PRODUCTS.items():
        domain = 'corridor '+key
        if all(w in f'{domain} {title} {area}'.replace('_',' ').casefold() for w in words):
            result['data'].append(route(domain, title, 'query', area, url, terms, 'corridor_screen',
                alignment={'type':'LineString','coordinates':[[-1.888,52.4728],[-1.8856,52.47515]]},
                nation='England',radius_m=250,layers=[key]))
    result['count'] = len(result['data'])
    result['status'] = 'ok' if result['count'] else 'empty'
    return result
