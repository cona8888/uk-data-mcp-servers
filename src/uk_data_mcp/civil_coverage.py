"""Civil-engineering evidence routes, indexed by practical use, not provider count."""

from copy import deepcopy


def route(domain, product, mode, area, url, limitation, tool=None, **args):
    return {'domain': domain, 'product': product, 'access': mode, 'geography': area,
            'publisher_url': url, 'limitation': limitation,
            'next_call': {'tool': tool, 'arguments': args} if tool else None}


R = route
D = 'dataset_record'
F = 'find_public_data'
GS = 'https://www.gov.uk/'
ND = 'https://www.data.gov.uk/dataset/'
ROUTES = (
    R('ground', 'Geology, boreholes, AGS and landslide indexes', 'query', 'GB or UK by collection', 'https://ogcapi.bgs.ac.uk/collections', 'Index is not a log; 625K geology is regional, not a design parameter.', 'bgs_collections'),
    R('survey', 'Topographic survey, LiDAR and terrain: EA 1 m DTM', 'metadata', 'England', ND+'01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m', 'Raster elevation sampling is not implemented. Survey age and vertical datum matter.', D, dataset_id='01b3ee39-da3f-47b6-83da-dc98e73a461f'),
    R('structures', 'Bridges, tunnels, culverts, retaining walls and asset inventories', 'discovery', 'England: National Highways network; local roads have other owners', 'https://opendata.nationalhighways.co.uk/', 'Inventory is not inspection evidence, load rating or a structural model.', F, query='highway structures bridges'),
    R('buildings', 'Building stock and energy performance certificates', 'discovery', 'England and Wales for this release', GS+'government/statistical-data-sets/live-tables-on-energy-performance-of-buildings-certificates', 'Energy certificates do not establish building structural condition or cover every building.', F, query='energy performance of buildings'),
    R('roads', 'Road traffic volume and count points', 'query', 'Great Britain', 'https://roadtraffic.dft.gov.uk/api-documentation', 'Annual estimates, not traffic incidents or a live congestion feed.', 'dft_traffic', year=2024, road_name='A38', limit=3),
    R('roads', 'Pavement surface condition and maintenance', 'discovery', 'England', GS+'government/collections/road-network-size-and-condition', 'Route-level surveys and authority-level summaries are not interchangeable.', F, query='road condition statistics'),
    R('road_safety', 'Reported personal-injury collisions, raw severity counts', 'prepared', 'Great Britain', GS+'government/statistical-data-sets/road-safety-open-data', '2024 or 2025; one collision is not one casualty. No exposure denominator.', 'road_collisions', gss_code='E08000025', year=2025),
    R('road_safety', 'PSNI Northern Ireland injury collisions', 'metadata', 'Northern Ireland', ND+'e5ad2f7f-091b-4a9f-b563-e2291cadd464/police-recorded-injury-road-traffic-collision-statistics-northern-ireland-2025', 'Separate publication; NI counts have not been merged into GB.', D, dataset_id='e5ad2f7f-091b-4a9f-b563-e2291cadd464'),
    R('rail', 'Rail services, station use, safety and asset condition', 'discovery', 'ORR: varies by series, frequently Great Britain', 'https://dataportal.orr.gov.uk/', 'Statistical publications are not real-time trains or engineering inspection files.', F, query='rail station usage'),
    R('public_transport', 'Bus, active travel and commuting: Census 2021 travel to work', 'prepared', 'England and Wales', 'https://www.nomisweb.co.uk/datasets/c2021ts061', 'Census-day commuting during the pandemic, not all trips, live timetables or traffic flows.', 'area_census', gss_code='E08000025', table='ts061'),
    R('water', 'Water supply, company leakage, metering and wastewater', 'query', 'England for the numerical leakage table', 'https://www.ofwat.gov.uk/regulated-companies/open-data-in-the-water-industry/', '2024/25 company leakage as % distribution input; not sewer capacity or site leaks.', 'company_leakage', company='Severn Trent Water'),
    R('flood', 'Rivers, groundwater, flood alerts and hydrology', 'query', 'England for the EA adapters', 'https://environment.data.gov.uk/hydrology/doc/reference', 'An observation is not a design water level. Keep timestamp, quality and datum.', 'hydrology_stations', latitude=52.45, longitude=-1.93, radius_km=5),
    R('flood', 'Flood and coastal defence assets; dams, channels and defences', 'metadata', 'England, EA inventory', ND+'a3861a23-78a1-438d-8c36-1f9f1133c572/aims-asset-bundle', 'Catalogue and resource links; not every asset or an independent condition assessment.', D, dataset_id='a3861a23-78a1-438d-8c36-1f9f1133c572'),
    R('coasts_ports', 'Coastal engineering, marine bathymetry and ports', 'discovery', 'UK waters; specific survey footprints', GS+'guidance/inspire-portal-and-medin-bathymetry-data-archive-centre', 'Chart datum and land survey datum are not necessarily the same.', F, query='UKHO bathymetry'),
    R('aviation', 'Airport and aviation traffic statistics', 'discovery', 'Reporting UK airports', 'https://www.caa.co.uk/data-and-analysis/uk-aviation-market/airports/uk-airport-data/', 'Passenger movements do not measure runway condition or capacity.', F, query='airport passenger statistics'),
    R('energy', 'Energy networks, demand and carbon intensity', 'discovery', 'Great Britain for NESO', 'https://www.neso.energy/data-portal', 'Network and settlement boundaries are not local-authority boundaries; licences vary.', F, query='electricity carbon intensity'),
    R('utilities', 'Buried pipelines, cables and utility records', 'restricted', 'England, Wales and Northern Ireland for NUAR', 'https://www.nuar.uk/', 'Eligible authorised users only; Scotland has separate arrangements. No clearance or public asset lookup.'),
    R('digital', 'Telecommunications and broadband coverage', 'metadata', 'UK, geography varies by Ofcom product', ND+'e218662f-2bdb-4e16-b4a8-8c16fdfd52bd/infrastructure-report', 'Service coverage does not establish buried fibre routing.', D, dataset_id='e218662f-2bdb-4e16-b4a8-8c16fdfd52bd'),
    R('environment', 'Pollution, contamination and environmental permits', 'discovery', 'England for EA registers', 'https://environment.data.gov.uk/public-register/view/index', 'A permit is not a sample or proof of contamination; check devolved registers.', F, query='environmental permits discharges'),
    R('waste', 'Waste, circular economy, construction and demolition arisings', 'discovery', 'UK; definitions differ by nation', GS+'government/statistics/uk-waste-data/uk-statistics-on-waste', 'Aggregate estimates do not establish site waste composition or reuse suitability.', F, query='construction demolition excavation waste'),
    R('climate', 'Climate resilience, weather scenarios and hazards', 'discovery', 'UK; the model grid and domain vary', 'https://www.metoffice.gov.uk/research/approach/collaboration/ukcp', 'Projection ensembles are not observations or site-specific design storms.', F, query='UK climate projections'),
    R('planning', 'Land use, planning authority and constraints', 'query', 'England for Planning Data', 'https://www.planning.data.gov.uk/docs', 'Point intersection, not a complete parcel or planning-permission check.', 'planning_entities', dataset='local-planning-authority', latitude=52.45, longitude=-1.93),
    R('heritage', 'Listed structures, archaeology and heritage at risk', 'metadata', 'England for Historic England', ND+'0d6243d5-d841-4448-83f6-d51d655bfdc5/historic-england-heritage-at-risk', 'Inventory entries are indicative and have an edition; devolved registers differ.', D, dataset_id='0d6243d5-d841-4448-83f6-d51d655bfdc5'),
    R('housing_society', 'House prices, regional housing market', 'query', 'UK HPI; resolution varies', 'https://landregistry.data.gov.uk/data/ukhpi', 'Mix-adjusted area estimate, not a property sale or valuation. Match the geography, month and vintage.', 'house_prices', region='birmingham', month='2024-01'),
    R('housing_society', 'Population, households, vehicle availability and labour market baseline', 'prepared', 'England and Wales, 2021 census LTLA', 'https://www.nomisweb.co.uk/census/2021/bulk', 'Counts at a fixed date and geography, not a current estimate; Scotland and NI have separate census releases.', 'area_census', gss_code='E08000025', table='ts001'),
    R('materials', 'Construction materials, aggregate supply and prices', 'metadata', 'Geography varies by material and table', ND+'75ee36ed-21f7-4d7b-9e7c-f5bf4546145d/building-materials-and-components-statistics', 'Published price indices are not tender quotations or laboratory material properties.', D, dataset_id='75ee36ed-21f7-4d7b-9e7c-f5bf4546145d'),
    R('delivery', 'Major schemes, budgets and infrastructure pipeline publications', 'query', 'NISTA publications; scheme coverage varies', GS+'government/organisations/national-infrastructure-and-service-transformation-authority', 'Pipeline announcements are not delivery commitments or as-built records.', 'nista_publications', query='pipeline'),
    R('delivery', 'Tenders, awards, contracts and procurement evidence', 'discovery', 'UK; portal and procurement regime vary', GS+'government/publications/open-contracting', 'No OCDS award-value adapter. Do not sum notices across revisions.', F, query='public procurement contracts'),
    R('construction_safety', 'Construction health and safety statistics', 'discovery', 'Great Britain for HSE', 'https://www.hse.gov.uk/statistics/industry/', 'Industry statistics do not establish a safe method of work on a site.', F, query='construction workplace injury'),
    R('devolved', 'Scottish spatial data, terrain and statistical catalogues', 'discovery', 'Scotland', 'https://www.gov.scot/policies/digital/data/', 'Use Scottish coverage and boundaries; consult SEPA and Scotland\'s Census for their products.'),
    R('devolved', 'DataMapWales, Welsh spatial data and public infrastructure', 'discovery', 'Wales', 'https://datamap.gov.wales/', 'Use NRW or Welsh authority products, not an English API as a substitute.'),
    R('devolved', 'OpenDataNI, NI statistics and local geography', 'discovery', 'Northern Ireland', 'https://www.opendatani.gov.uk/', 'Use NISRA census, DfI, PSNI and GSNI as applicable; do not substitute GB records.'),
)


def civil_coverage(query=''):
    if not isinstance(query, str) or len(query) > 120:
        raise ValueError('Use a short subject or domain.')
    words = query.casefold().replace('_', ' ').split()
    rows = [deepcopy(row) for row in ROUTES if all(
        w in ' '.join(str(row[k]) for k in ('domain', 'product', 'geography')).replace('_', ' ').casefold()
        for w in words)]
    return {'status': 'ok' if rows else 'empty', 'count': len(rows), 'data': rows,
            'access_key': {'query': 'Specific live API or publication operation', 'prepared': 'Numerical query from locally prepared official files',
                           'metadata': 'Direct national catalogue record and resource links, not file contents',
                           'discovery': 'Provider portal or catalogue search, not a dedicated record connector',
                           'restricted': 'Access-controlled; no connector enabled'},
            'note': 'Non-exhaustive. Source-specific terms apply. Examples illustrate inputs, not a current engineering assessment.'}
