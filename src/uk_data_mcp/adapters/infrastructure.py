"""No-key OS OpenData discovery and DfT road traffic estimates.

Primary specifications:
https://docs.os.uk/os-apis/accessing-os-apis/os-downloads-api/technical-specification
https://roadtraffic.dft.gov.uk/api-documentation
"""

import re
from datetime import datetime, timezone

from ..geo import validate_limit
from ..results import envelope
from ..transport import DataAccessError, HttpClient

OS_BASE = "https://api.os.uk/downloads/v1/products"
DFT_BASE = "https://roadtraffic.dft.gov.uk/api/average-annual-daily-flow"


async def os_products(
    client: HttpClient, query: str = "", limit: int = 20, offset: int = 0
) -> dict:
    validate_limit(limit)
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError("query must be at most 200 characters.")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000.")
    fetched = await client.get_json(OS_BASE, {"expanded": "true"})
    if not isinstance(fetched.data, list) or any(not isinstance(x, dict) for x in fetched.data):
        raise DataAccessError("OS returned an unexpected product catalogue.")
    matches = [
        p
        for p in fetched.data
        if query.lower()
        in " ".join(str(p.get(k, "")) for k in ("id", "name", "description", "category")).lower()
    ]
    projected = []
    for p in matches[offset : offset + limit]:
        record = {
            k: p[k]
            for k in (
                "id",
                "name",
                "description",
                "version",
                "documentationUrl",
                "url",
                "downloadsUrl",
                "dataStructures",
                "formats",
                "areas",
                "category",
            )
            if k in p
        }
        third_party = p.get("thirdPartyInfo") or {}
        if not isinstance(third_party, dict):
            raise DataAccessError("OS returned invalid third-party provider metadata.")
        provider = third_party.get("dataProvider") or {}
        if not isinstance(provider, dict):
            raise DataAccessError("OS returned invalid data-provider metadata.")
        record["data_provider"] = {
            k: provider[k] for k in ("name", "homepage") if k in provider
        } or {"name": "Ordnance Survey"}
        projected.append(record)
    more = offset + len(projected) < len(matches)
    return envelope(
        "os_open_downloads",
        projected,
        requests=[fetched],
        query={"query": query, "limit": limit, "offset": offset},
        total=len(matches),
        truncated=more or offset > 0,
        next_page={"query": query, "limit": limit, "offset": offset + limit} if more else None,
        metadata={"operation": "product_metadata_only", "downloaded_dataset_files": False},
        warnings=[
            "Product metadata and download links are returned; no road geometry or bulk datasets have been downloaded.",
            "Third-party products retain their own provider licences; check documentationUrl.",
        ],
    )


async def os_downloads(
    client: HttpClient, product_id: str, limit: int = 20, offset: int = 0
) -> dict:
    validate_limit(limit)
    if not isinstance(product_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", product_id):
        raise ValueError(
            "product_id must be an ID from os_products, using letters, numbers, underscores or hyphens."
        )
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000.")
    fetched = await client.get_json(f"{OS_BASE}/{product_id}/downloads")
    if not isinstance(fetched.data, list) or any(not isinstance(x, dict) for x in fetched.data):
        raise DataAccessError("OS returned an unexpected download catalogue.")
    records = [
        {
            k: item[k]
            for k in ("url", "fileName", "size", "format", "subformat", "area", "md5")
            if k in item
        }
        for item in fetched.data[offset : offset + limit]
    ]
    more = offset + len(records) < len(fetched.data)
    return envelope(
        "os_open_downloads",
        records,
        requests=[fetched],
        query={"product_id": product_id, "limit": limit, "offset": offset},
        total=len(fetched.data),
        truncated=more or offset > 0,
        next_page={"product_id": product_id, "limit": limit, "offset": offset + limit}
        if more
        else None,
        metadata={
            "size_unit": "bytes",
            "downloaded_dataset_files": False,
            "product_metadata_followup": {
                "tool": "os_products",
                "arguments": {"query": product_id},
            },
            "licence_status": "check_product_documentation_before_reuse",
        },
        warnings=[
            "Links can point to very large files. The server only lists them; it does not fetch them.",
            "The MD5 field is provider metadata, not a security guarantee.",
            "Call os_products with this product ID to get its data provider and documentationUrl before reuse; third-party terms can differ.",
        ],
    )


async def dft_traffic(
    client: HttpClient,
    year: int,
    road_name: str | None = None,
    count_point_id: int | None = None,
    limit: int = 20,
    page: int = 1,
) -> dict:
    validate_limit(limit)
    if (
        isinstance(year, bool)
        or not isinstance(year, int)
        or not 2000 <= year <= datetime.now(timezone.utc).year
    ):
        raise ValueError(
            "year must be an integer from 2000 to the current year; recent years may not yet be published."
        )
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
        raise ValueError("page must be an integer from 1 to 10000.")
    if road_name is not None and (
        not isinstance(road_name, str) or not re.fullmatch(r"[A-Za-z0-9 ()-]{1,40}", road_name)
    ):
        raise ValueError("road_name must be a road designation such as A38 or M6.")
    if count_point_id is not None and (
        isinstance(count_point_id, bool)
        or not isinstance(count_point_id, int)
        or not 1 <= count_point_id <= 10**9
    ):
        raise ValueError("count_point_id must be a positive integer.")
    params = {
        "filter[year]": year,
        "page[size]": limit,
        "page[number]": page,
        "sort": "count_point_id",
    }
    if road_name is not None:
        params["filter[road_name]"] = road_name
    if count_point_id is not None:
        params["filter[count_point_id]"] = count_point_id
    fetched = await client.get_json(DFT_BASE, params)
    body = fetched.data
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise DataAccessError("DfT returned an unexpected traffic response.")
    records = body["data"]
    if any(not isinstance(x, dict) for x in records):
        raise DataAccessError("DfT returned invalid traffic records.")
    # Check key filters so a changed API cannot silently return another year or count point.
    if any(str(x.get("year")) != str(year) for x in records):
        raise DataAccessError("DfT response did not respect the requested year; results withheld.")
    if count_point_id is not None and any(
        str(x.get("count_point_id")) != str(count_point_id) for x in records
    ):
        raise DataAccessError(
            "DfT response did not respect the requested count point; results withheld."
        )
    if road_name is not None and any(
        str(x.get("road_name", "")).strip().casefold() != road_name.strip().casefold()
        for x in records
    ):
        raise DataAccessError(
            "DfT response did not respect the requested road name; results withheld."
        )
    records = records[:limit]
    total = body.get("total") if isinstance(body.get("total"), int) else None
    more = bool(body.get("next_page_url")) or len(body["data"]) > limit
    query = {
        "year": year,
        "road_name": road_name,
        "count_point_id": count_point_id,
        "limit": limit,
        "page": page,
    }
    return envelope(
        "dft_traffic",
        records,
        requests=[fetched],
        query=query,
        total=total,
        truncated=more or page > 1,
        next_page={**query, "page": page + 1} if more else None,
        metadata={
            "units": {
                "all_motor_vehicles": "vehicles/day (annual average)",
                "pedal_cycles": "cycles/day (annual average)",
                "link_length_km": "km",
            },
            "coordinate_note": "latitude/longitude are WGS84 decimal degrees; easting/northing are provider British National Grid metres.",
        },
        warnings=[
            "Annual average daily flows are estimates, not live traffic or pavement load spectra.",
            "Keep estimation_method and estimation_method_detailed when comparing counts.",
            "Road-name filters can cover many locations; this is not a site-radius query.",
        ],
    )
