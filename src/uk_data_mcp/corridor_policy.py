"""Reviewed read-only corridor products. Do not accept URLs supplied by an MCP caller."""
from urllib.parse import urlsplit

EA = ('https://environment.data.gov.uk/geoservices/datasets/8e5be50f-d465-11e4-ba9a-f0def148f590/'
      'ogc/features/v1/collections/Spatial_Flood_Defences_Including_Standardised_Attributes/items')
BGS = 'https://ogcapi.bgs.ac.uk/collections/onshoreboreholeindex/items'
CRT = ('https://services.arcgis.com/DknzyjEEie5tEW0u/arcgis/rest/services/'
       'Canal_And_River_Trust_Bridges_View/FeatureServer/0/query')
DFT = ('https://services5.arcgis.com/qUwnXV5uf1zyW6Y2/ArcGIS/rest/services/'
       'RoadCasualtyStatsCollision_GB_DfT_Point_2025/FeatureServer/0/query')
ONS = ('https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/'
       'Wards_December_2024_Boundaries_UK_BGC/FeatureServer/0/query')
# Country validation uses one additional reviewed route, never an arbitrary host.
COUNTRIES = ('https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/'
             'Countries_December_2024_Boundaries_UK_BGC/FeatureServer/0/query')

EXACT = frozenset((urlsplit(url).hostname, urlsplit(url).path)
                  for url in (EA, CRT, DFT, ONS, COUNTRIES))

PRODUCTS = {
    'boreholes': (BGS, 'BGS Single Onshore Borehole Index', 'Great Britain',
        'https://www.bgs.ac.uk/datasets/boreholes-index/',
        'Contains British Geological Survey materials © UKRI. OGL v3. Includes OS data. Index position, not interpreted strata.'),
    'bridges': (CRT, 'Canal & River Trust bridge inventory', 'Waterways on the Trust network, England and Wales',
        'https://www.data.gov.uk/dataset/3bad9280-3167-4a8f-ad12-4fa93297bf51/bridges',
        '© Canal & River Trust; see catalogue OGL and publisher terms. Bridge reference points only, not all road or rail bridges, spans, capacity or condition.'),
    'flood_defences': (EA, 'Environment Agency AIMS Spatial Flood Defences', 'England',
        'https://www.data.gov.uk/dataset/cc76738e-fc17-49f9-a216-977c61858dda/aims-spatial-flood-defences-inc-standardised-attributes',
        '© Environment Agency copyright and/or database right 2020. OGL. EA owned, managed or inspected defences, not all defences or a risk assessment.'),
    'collisions': (DFT, 'DfT STATS19 mapped personal-injury collisions, 2025', 'Great Britain',
        'https://www.gov.uk/government/statistical-data-sets/road-safety-open-data',
        'Contains DfT public sector information under OGL v3. Mapped events only; excludes missing locations, unreported and damage-only incidents. Proximity does not attribute an event to a road.'),
    'communities': (ONS, 'ONS electoral wards, December 2024 (20 m generalised)', 'GB routes only in this gateway',
        'https://www.data.gov.uk/dataset/e8493e3d-619e-4362-aa3a-0a3538177da8/wards-december-2024-boundaries-uk-bgc',
        'Source: ONS Geography; contains OS data © Crown copyright and database right. See ONS geography licences. Intersections indicate proximity, not service catchments or beneficiary counts.'),
}
