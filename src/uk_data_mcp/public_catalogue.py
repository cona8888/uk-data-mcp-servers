"""Public-profile source cards. A directory entry is never a live connector by itself."""

import re

from .transport import LEAKAGE_PATH

METER = '6900f4b9-5fa9-4938-bd6b-977920d2d7f3'
TELEMETRY = 'dccd6c78-5a29-48d7-8d91-bd6a152742a5'
ANNUAL_REVIEW = '87b59684-3da3-45cf-8881-e4727cfd1415'
HPI = '3bff64e9-0691-4569-bf12-323d4e60220e'
NISTA = 'national-infrastructure-and-service-transformation-authority'
ONS = 'https://www.ons.gov.uk'
OGL = 'Open Government Licence v3.0 except where stated; retain attribution.'
SPECIFIC = 'Resource-specific terms; catalogue visibility is not a licence to redistribute.'


def card(provider, title, coverage, url, capability, tools, note, terms=SPECIFIC):
    return dict(provider=provider, title=title, coverage=coverage, url=url, capability=capability,
                tools=tools.split() if tools else [], limitation=note, terms=terms)


SOURCES = {
    'national_directory': card('Government Digital Service', 'National Data Library: cross-sector public dataset directory', 'UK; incomplete and publisher-dependent', 'https://www.data.gov.uk/', 'catalogue_api', 'find_public_data dataset_record', 'Directory records across all subjects, not all underlying data. Curated collections are not all available in the CKAN API.'),
    'ons': card('Office for National Statistics', 'Social and economic statistics: population, migration, health, employment, earnings, households, rents, education and prices', 'Dataset-specific: UK, GB, individual nations or local areas', ONS + '/search?q=water+leakage', 'search_and_observations', 'find_public_data ons_series', 'Search returns publications; ons_series accepts a published time-series URI, not every census table. Never assume all observations cover all four nations.', OGL),
    'uk_hpi': card('HM Land Registry and UK HPI partners', 'UK House Price Index: regional index and average residential price', 'UK; named geography, series and publication frequency vary', 'https://landregistry.data.gov.uk/app/ukhpi/', 'observations', 'house_prices dataset_record', 'Mix-adjusted estimate, not an individual sale or property valuation. Values may be revised; NI source statistics are quarterly.', OGL),
    'price_paid': card('HM Land Registry', 'Price Paid Data: registered residential transactions', 'England and Wales', 'https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads', 'publisher_download', '', 'Individual transaction prices are separate from HPI. Check address reuse conditions, excluded transfers and registration lag.'),
    'ofwat': card('Ofwat', 'Open data in the water industry: sector hub', 'England and Wales water industry', 'https://www.ofwat.gov.uk/regulated-companies/open-data-in-the-water-industry/#sector', 'publisher_directory', '', 'Sector gateway to Stream and water companies, not an observation endpoint.'),
    'stream': card('Stream water-sector partners', 'Water industry open and shared datasets', 'Provider and company service areas', 'https://www.streamwaterdata.co.uk/', 'publisher_directory', '', 'Industry-led rather than a government registry; check terms and access for each item.'),
    'ofwat_leakage': card('Ofwat', 'Company leakage performance and historical dataset', 'England and Wales; company supply areas', 'https://www.ofwat.gov.uk/households/supply-and-standards/leakage/', 'publisher_download', '', 'Use the reporting definition for the year. Not household metering or a map of leak locations.'),
    'ea_leakage': card('Environment Agency', 'Annual water resource performance: company leakage as a share of distribution input, Figure 8', 'England reporting scope; company service areas, not local authorities', 'https://www.gov.uk' + LEAKAGE_PATH, 'observations', 'company_leakage', 'This connector reads the 2024/25 edition only, not a live leak feed. The national average is a separately reported statistic, not an unweighted company mean.', OGL),
    'ea_annual_returns': card('Environment Agency', 'Water resource management plan annual review data', 'Coverage and company boundaries per release', 'https://www.data.gov.uk/dataset/' + ANNUAL_REVIEW + '/water-resource-management-plan-annual-review-data', 'metadata_api', 'dataset_record', 'Distinguish observed outturn, dry-year-adjusted values and forecasts.'),
    'ea_telemetry': card('Environment Agency / Defra DSP', 'National Real Time Water Quality Data: monitoring sites, pH, temperature, dissolved oxygen', 'EA monitoring network, England; not UK-wide', 'https://environment.data.gov.uk/dataset/365df16f-1b80-4e0e-9ed9-1450e0238aef', 'metadata_api_and_viewer', 'dataset_record', 'DSP identifier 365df16f-1b80-4e0e-9ed9-1450e0238aef maps to a different national catalogue UUID. The linked site is a telemetry viewer; the catalogue period ends in 2022 despite continual-update wording. No sensor readings asserted.', 'OGL per DSP; © Environment Agency copyright and/or database right 2015.'),
    'ea_samples': card('Environment Agency', 'Water Quality Explorer: sampled and laboratory water-quality observations', 'England', 'https://environment.data.gov.uk/water-quality/api-docs', 'external_api_documentation', '', 'Separate from the National Real Time Water Quality telemetry viewer. Native observation tool not included in this profile.'),
    'meter_yorkshire': card('Calderdale Metropolitan Borough Council / Yorkshire Water', 'Historical domestic customer meter readings and consumption', 'Yorkshire Water operational area; 2010/11 to 2014/15', 'https://www.data.gov.uk/dataset/' + METER + '/customer-meter-data', 'metadata_api_and_local_aggregate', 'dataset_record', 'Actual and estimated records. Gross consumption in m³, not leakage. Local aggregation only; no meter identifiers or household joins in output.', 'Open Government Licence per catalogue; retain publisher attribution.'),
    'waterwise': card('Waterwise', 'Water efficiency research, evidence, literature and policy', 'UK and other study areas, publication-specific', 'https://database.waterwise.org.uk/', 'manual_reference', '', 'Independent evidence library, not government monitoring data. Use its canonical public page; no CAPTCHA automation, challenge tokens or automatic document downloads.'),
    'nista': card('National Infrastructure and Service Transformation Authority', 'Major infrastructure projects, programmes, pipeline and publications', 'UK government portfolio; project-specific', 'https://www.gov.uk/government/organisations/' + NISTA, 'publication_search', 'nista_publications', 'Searches GOV.UK publications attributed to NISTA. Not an asset register or a row-level pipeline feed.', OGL),
    'nomis': card('ONS / Nomis', 'Census, labour market, employment and local population tables', 'Survey, census and geography-specific', 'https://www.nomisweb.co.uk/api/v01/help', 'external_api_documentation', '', 'Different denominators and geographies; do not sum overlapping populations.'),
    'local_ons': card('ONS', 'Explore local statistics: housing, rents, population and social conditions', 'Indicator-specific', ONS + '/explore-local-statistics/', 'publisher_directory', '', 'Match geography code and vintage rather than place name alone.'),
    'scotland': card('Scottish Government', 'Scottish official statistics: population, housing, health, society', 'Scotland', 'https://statistics.gov.scot/', 'publisher_directory', '', 'Check Scottish geography definitions and statistical release dates.'),
    'wales': card('Welsh Government', 'StatsWales: Welsh social and economic statistics', 'Wales', 'https://stats.gov.wales/', 'publisher_directory', '', 'Check series definition and geography for each release.'),
    'ni': card('Northern Ireland Statistics and Research Agency', 'NISRA data: households, housing, health and education', 'Northern Ireland', 'https://explore.nisra.gov.uk/', 'publisher_directory', '', 'Do not substitute England and Wales census definitions or reference dates.'),
    'education': card('Department for Education', 'Explore Education Statistics: schools, attainment and further education', 'Primarily England; release-specific', 'https://explore-education-statistics.service.gov.uk/', 'publisher_directory', '', 'Use published aggregate tables; avoid identifying pupils or small cells.'),
    'benefits': card('Department for Work and Pensions', 'Stat-Xplore: benefits, welfare and household statistics', 'Benefit and dataset-specific', 'https://stat-xplore.dwp.gov.uk/', 'publisher_directory', '', 'Statistical disclosure control and access rules vary by table.'),
    'health': card('NHS Business Services Authority', 'NHSBSA Open Data Portal: health service activity and prescribing', 'Dataset-specific', 'https://opendata.nhsbsa.net/', 'publisher_directory', '', 'Public statistical data only, not patient records.'),
    'roads': card('Department for Transport', 'Road traffic volumes, count points and vehicle flows', 'Great Britain', 'https://roadtraffic.dft.gov.uk/', 'existing_groundwork_profile', 'dft_traffic', 'Annual average traffic is not a live incident feed.'),
    'collisions': card('Department for Transport', 'STATS19 road safety: police-reported personal-injury collisions, vehicles and casualties', 'Great Britain; PSNI publishes Northern Ireland separately', 'https://www.gov.uk/government/statistical-data-sets/road-safety-open-data', 'publisher_download', '', 'Not all crashes. No collision-row ingestion in this profile.'),
    'rail': card('Office of Rail and Road', 'Passenger rail use, station usage, reliability and safety statistics', 'Principally Great Britain; table-specific', 'https://dataportal.orr.gov.uk/', 'publisher_directory', '', 'Published statistics, not live train departures.'),
}

ALIASES = {'meter_yorkshire': METER, 'ea_telemetry': TELEMETRY, 'ea_annual_returns': ANNUAL_REVIEW, 'uk_hpi': HPI}


def public_sources(query: str = '') -> dict:
    """Search the curated routing table offline, including manual-only sources."""
    if not isinstance(query, str) or len(query) > 180:
        raise ValueError('query must be at most 180 characters')
    words = re.findall(r'[\w]+', query.casefold())
    rows = [dict(id=k, **v, catalogue_id=ALIASES.get(k)) for k, v in SOURCES.items()
            if all(w in (k + ' ' + str(v)).casefold() for w in words)]
    return {'status': 'ok' if rows else 'empty', 'kind': 'reviewed_routes', 'data': rows,
            'count': len(rows), 'reviewed_on': '2026-11-02', 'complete_national_inventory': False}
