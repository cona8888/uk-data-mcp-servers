"""Read-only guidance to the evidence holder, never a utility-location or capacity answer."""

import re

NATIONS = ('England', 'Wales', 'Scotland', 'Northern Ireland')
ENA = 'https://www.energynetworks.org/customers/find-my-network-operator'
OFWAT = 'https://www.ofwat.gov.uk/households/your-water-company/contact-companies/'
NUAR = 'https://www.nuar.uk/faqs'
VAULT = ('https://roadworks.scot/legislation-guidance/commissioner-guidance/'
         'community-apparatus-data-vault-frequently-asked')
HSE = 'https://www.hse.gov.uk/pubns/books/hsg47.htm'
# These are operator-supplied selections, not inferred service areas.
OPERATORS = {
    'severn trent water': ('water', ('England', 'Wales'),
        'https://www.stwater.co.uk/building-and-developing/request-a-water-sewer-map/'),
    'national grid electricity distribution': ('electricity', ('England', 'Wales'),
        'https://www.nationalgrid.co.uk/network-opportunity-map'),
}


def tokens(query):
    return set(re.findall(r'[a-z0-9]+', query.casefold()))


def intent_domains(query):
    """Reviewed task vocabulary; does not infer an asset or claim exact semantic understanding."""
    w = tokens(query)
    domains = set()
    if w & {'gas', 'pipeline', 'pipelines', 'cable', 'cables', 'underground', 'buried', 'utilities'}:
        domains.add('utilities')
    if w & {'grid', 'dno', 'headroom', 'substation', 'feeder', 'energy'}:
        domains.add('energy')
    if 'electricity' in w and w & {'connection', 'capacity', 'supply', 'network'}:
        domains.add('energy')
    if w & {'sewer', 'sewers', 'wastewater', 'drainage', 'water', 'watermain'}:
        domains.add('water')
    if w & {'borehole', 'boreholes', 'geotechnical', 'strata', 'ags'}:
        domains.add('ground')
    if w & {'parcel', 'permission', 'planning', 'consent'}:
        domains.add('planning')
    return domains


def utility_handoff(sector='utilities', nation=None, purpose='asset_records', operator=None):
    if sector not in ('gas', 'electricity', 'water', 'utilities'):
        raise ValueError('Use gas, electricity, water or utilities.')
    if nation is not None and nation not in NATIONS:
        raise ValueError('Use a UK nation or leave it unspecified; a nation does not identify an operator.')
    if purpose not in ('asset_records', 'capacity', 'connection', 'diversion'):
        raise ValueError('Use asset_records, capacity, connection or diversion.')
    if operator is not None and (not isinstance(operator, str) or not operator.strip()
                                or len(operator) > 120 or any(ord(c) < 32 for c in operator)):
        raise ValueError('operator must be a short plain-text name, not credentials or a URL.')
    links = [{'title': 'Official safe-work guidance, not clearance', 'url': HSE}]
    if nation == 'Scotland':
        links.append({'title': 'Scottish Road Works Register / Vault eligibility', 'url': VAULT})
        links.append({'title': 'Scottish plant-information request service',
                      'url': 'https://roadworks.scot/dial-before-you-dig'})
    elif nation in ('England', 'Wales', 'Northern Ireland'):
        links.append({'title': 'NUAR access, permitted uses and expansion status', 'url': NUAR})
    else:
        links += [{'title': 'England, Wales and Northern Ireland: NUAR', 'url': NUAR},
                  {'title': 'Scotland: Vault', 'url': VAULT}]
    if sector == 'water':
        finder = ('https://www.scottishwater.co.uk/' if nation == 'Scotland' else
                  'https://www.niwater.com/' if nation == 'Northern Ireland' else OFWAT)
        links.append({'title': 'Identify water and sewerage infrastructure operator separately', 'url': finder})
        needed = ['Site boundary and intended use', 'Water demand and/or foul and surface-water flows',
                  'Operator asset plans, levels and relevant network assessment']
        next_step = ('Request asset records and a developer-services capacity or diversion assessment '
                     'from the relevant infrastructure operator. Company leakage is not local spare capacity.')
    else:
        links.append({'title': 'Identify the network owner; not the retail supplier', 'url': ENA})
        if nation == 'Northern Ireland':
            links.append({'title': 'Northern Ireland electricity network enquiries',
                          'url': 'https://www.nienetworks.co.uk/'})
        needed = ['Site boundary and proposed works', 'Relevant operator asset-protection records',
                  'For a connection: demand/generation, import/export, timing and voltage or pressure requirements']
        next_step = ('Identify the actual asset/network owner and request its records or formal connection '
                     'assessment. Indicative headroom is not an offer; no pipe or cable absence is established.')
    selection = 'not_supplied'
    if operator:
        selected = OPERATORS.get(operator.strip().casefold())
        selection = 'unverified_name'
        if selected and selected[0] == sector and (nation is None or nation in selected[1]):
            selection = 'user_selected_not_location_verified'
            links.append({'title': 'User-selected operator service; site coverage not checked', 'url': selected[2]})
        elif selected:
            selection = 'sector_or_nation_mismatch'
    return {'status': 'ok', 'kind': 'operator_handoff', 'sector': sector, 'nation': nation,
            'purpose': purpose, 'operator_supplied': operator, 'operator_resolution': selection,
            'guidance_reviewed_on': '2026-11-11', 'evidence_status': 'not_retrieved',
            'asset_locations': None, 'network_capacity': None, 'connection_offer': None,
            'excavation_clearance': None, 'next_step': next_step, 'required_information': needed,
            'official_routes': links,
            'limitations': ['No restricted data were queried, downloaded or granted access.',
                            'Access eligibility and permitted purposes must be checked with each service.',
                            'Operator name or nation alone does not establish site coverage.',
                            'For an emergency use the responsible emergency service, not this research tool.']}
