"""Build an offline station-observation map from retained MCP data and sourced vectors.

Input files are archived under examples/maps/. No network requests or inferred
groundwater surface are used. Optional PNG rendering can use any SVG renderer.
"""

from __future__ import annotations

import gzip
import json
import math
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples" / "maps"
DOCS = ROOT / "docs" / "maps"
OUT = ROOT / "output" / "html"
WIDTH, HEIGHT = 960, 820
BBOX = (-2.114331, 52.349836, -1.666469, 52.622564)


def mercator(lon, lat):
    return math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


west, south = mercator(BBOX[0], BBOX[1])
east, north = mercator(BBOX[2], BBOX[3])
scale = min((WIDTH - 70) / (east - west), (HEIGHT - 70) / (north - south))
cx, cy = (west + east) / 2, (south + north) / 2


def xy(point):
    x, y = mercator(*point)
    return (WIDTH / 2 + (x - cx) * scale, HEIGHT / 2 - (y - cy) * scale)


def path(points, close=False):
    if not points:
        return ""
    pairs = [xy(p) for p in points]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pairs) + ("Z" if close else "")


def colour(value, minimum, maximum):
    t = (value - minimum) / (maximum - minimum or 1)
    a, b = (28, 83, 136), (38, 155, 139)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def text(x, y, value, size=15, fill="#243f46", weight=400, **attrs):
    extra = " ".join(
        f'{k.replace("_", "-")}="{escape(str(v), quote=True)}"' for k, v in attrs.items()
    )
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{weight}" {extra}>{escape(str(value))}</text>'


def map_svg(data, context, boundary):
    features = data["features"]
    values = [f["properties"]["value_mAOD"] for f in features]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="map-title map-desc">',
        '<title id="map-title">Birmingham-area groundwater observations</title>',
        '<desc id="map-desc">Twelve independent monitoring-point readings, with dates from January 2020 to July 2026, on sourced main-road and waterway context. Colours show elevation above Ordnance Datum, not depth below ground.</desc>',
        f'<defs><clipPath id="map-clip"><rect x="18" y="18" width="{WIDTH - 36}" height="{HEIGHT - 36}" rx="12"/></clipPath></defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f5f7f4"/>',
        '<g clip-path="url(#map-clip)">',
    ]
    for feature in boundary["features"]:
        polygons = (
            [feature["geometry"]["coordinates"]]
            if feature["geometry"]["type"] == "Polygon"
            else feature["geometry"]["coordinates"]
        )
        for polygon in polygons:
            d = "".join(path(ring, True) for ring in polygon)
            parts.append(
                f'<path d="{d}" fill="#e5eee7" stroke="#8ba699" stroke-width="1.2" fill-rule="evenodd"/>'
            )
    # All source geometries remain real published coordinates. SVG clipping bounds
    # complete ways; no invented roads or interpolation is added.
    groups = {"primary": [], "trunk": [], "motorway": [], "river": [], "canal": []}
    for feature in context["features"]:
        props = feature["properties"]
        kind = props.get("waterway") or props.get("highway")
        if kind not in groups:
            continue
        points = feature["geometry"]["coordinates"]
        if not any(BBOX[0] <= p[0] <= BBOX[2] and BBOX[1] <= p[1] <= BBOX[3] for p in points):
            continue
        # Preserve covered/tunnelled context as dashed, not a surface-flow claim.
        dashed = props.get("tunnel") not in (None, "no") or props.get("covered") not in (None, "no")
        groups[kind].append((path(points), dashed))
    for kind, stroke, width in [
        ("primary", "#c7cbbd", 0.7),
        ("trunk", "#b9bfae", 1),
        ("motorway", "#a9b29e", 1.6),
        ("river", "#7eafbc", 1.1),
        ("canal", "#8bb8c2", 0.8),
    ]:
        for d, dashed in groups[kind]:
            dash = ' stroke-dasharray="3 3"' if dashed else ""
            parts.append(
                f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash}/>'
            )
    circle = []
    lat0, lon0 = map(math.radians, [52.4862, -1.8904])
    angle = 15 / 6371.0088
    for bearing in range(361):
        b = math.radians(bearing)
        lat = math.asin(
            math.sin(lat0) * math.cos(angle) + math.cos(lat0) * math.sin(angle) * math.cos(b)
        )
        lon = lon0 + math.atan2(
            math.sin(b) * math.sin(angle) * math.cos(lat0),
            math.cos(angle) - math.sin(lat0) * math.sin(lat),
        )
        circle.append([math.degrees(lon), math.degrees(lat)])
    parts.append(
        f'<path d="{path(circle, True)}" fill="none" stroke="#657c87" stroke-width="1" stroke-dasharray="5 5"/>'
    )
    x, y = xy([-1.8904, 52.4862])
    parts += [
        f'<path d="M{x - 5:.1f},{y:.1f}h10M{x:.1f},{y - 5:.1f}v10" stroke="#4a6266" stroke-width="1.5"/>',
        text(round(x + 12, 1), round(y + 17, 1), "Birmingham", 17, "#37534e", 700),
    ]
    # Offset numbered callouts, never the station positions, for near-colocated holes.
    offsets = {
        1: (18, -18),
        2: (20, 12),
        3: (20, 18),
        4: (18, -16),
        5: (-24, -16),
        6: (20, 18),
        7: (18, 12),
        8: (-26, -18),
        9: (22, 18),
        10: (-23, -15),
        11: (20, 0),
        12: (20, -10),
    }
    for number, feature in enumerate(features, 1):
        props = feature["properties"]
        x, y = xy(feature["geometry"]["coordinates"])
        dx, dy = offsets[number]
        dash = ' stroke-dasharray="3 2"' if props["quality"] != "Good" else ""
        fill = colour(props["value_mAOD"], min(values), max(values))
        title = f"{number}. {props['station_name']}: {props['value_mAOD']} mAOD; {props['observed_date']}; {props['quality']}"
        parts.append(
            f'<g class="station" data-number="{number}" tabindex="0" role="button" aria-label="{escape(title, quote=True)}"><title>{escape(title)}</title>'
        )
        parts += [
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="transparent"/>',
            f'<circle class="point" cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{fill}" stroke="#243f46" stroke-width="1.5"{dash}/>',
            f'<path d="M{x:.1f},{y:.1f}l{dx * 0.72:.1f},{dy * 0.72:.1f}" fill="none" stroke="#71898b" stroke-width="1"/>',
            f'<circle cx="{x + dx:.1f}" cy="{y + dy:.1f}" r="10" fill="white" stroke="#6d8485" stroke-width=".6"/>',
            text(
                round(x + dx, 1),
                round(y + dy + 4, 1),
                number,
                12,
                "#243f46",
                700,
                text_anchor="middle",
            ),
            "</g>",
        ]
    # Mercator scale varies with latitude; use the search-centre latitude for
    # this approximate ground-distance scale instead of projected metres.
    five_km_pixels = scale * 5 / (6371.0088 * math.cos(lat0))
    parts += [
        "</g>",
        '<g aria-label="Map key">',
        '<rect x="36" y="40" width="271" height="133" rx="9" fill="white" fill-opacity=".95"/>',
        text(52, 65, "Observed elevation (mAOD)", 16, weight=700),
    ]
    for i in range(120):
        value = min(values) + (max(values) - min(values)) * i / 119
        parts.append(
            f'<rect x="{52 + i * 1.92:.1f}" y="77" width="2" height="10" fill="{colour(value, min(values), max(values))}"/>'
        )
    parts += [
        text(52, 106, f"{min(values):.1f}", 13),
        text(282, 106, f"{max(values):.1f}", 13, text_anchor="end"),
        text(52, 129, "Dashed point outline: Unchecked", 13),
        text(52, 150, "Solid point outline: Good", 13),
        "</g>",
        '<path d="M901 92V42m-6 10 6-10 6 10" fill="none" stroke="#526b70" stroke-width="2"/>',
        text(901, 32, "N", 15, weight=700, text_anchor="middle"),
        '<rect x="36" y="732" width="388" height="51" rx="7" fill="white" fill-opacity=".94"/>',
        text(49, 752, "Outline: ONS Birmingham boundary (May 2024)", 12),
        text(49, 772, "Dashed circle: 15 km search from Birmingham centre", 12),
        '<rect x="694" y="724" width="230" height="62" rx="7" fill="white" fill-opacity=".94"/>',
        f'<path d="M714 750v6h{five_km_pixels:.1f}v-6" fill="none" stroke="#526b70" stroke-width="2"/>',
        text(714, 774, "Approx. 5 km at map centre", 11),
        "</svg>",
    ]
    return "".join(parts)


def main():
    data = json.loads(
        (DATA / "birmingham_groundwater_2026-10-29.geojson").read_text(encoding="utf-8")
    )
    with gzip.open(
        DATA / "birmingham_osm_context_2026-10-29.geojson.gz", "rt", encoding="utf-8"
    ) as source:
        context = json.load(source)
    boundary = json.loads(
        (DATA / "birmingham_ons_boundary_2024.geojson").read_text(encoding="utf-8")
    )
    assert len(data["features"]) == 12
    svg = map_svg(data, context, boundary)
    DOCS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    template = (ROOT / "scripts" / "groundwater_map_template.html").read_text(encoding="utf-8")
    encoded = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    page = template.replace("{{MAP_SVG}}", svg).replace("{{DATA_JSON}}", encoded)
    (DOCS / "birmingham-groundwater-map.html").write_text(page, encoding="utf-8", newline="\n")
    (OUT / "birmingham-groundwater-map.html").write_text(page, encoding="utf-8", newline="\n")
    # Preview SVG is a standalone publication figure with explicit source notices.
    preview = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1100" viewBox="0 0 1280 1100"><rect width="1280" height="1100" fill="white"/>'
    preview += text(32, 43, "Birmingham-area groundwater observations", 30, weight=700)
    preview += text(
        32,
        74,
        "Latest available per station; retrieved 29 October 2026. Elevation in mAOD, not depth below ground.",
        16,
    )
    preview += '<rect x="32" y="92" width="1216" height="48" rx="7" fill="#fff2d8"/>'
    preview += text(
        46,
        113,
        "Observation dates: 23 Jan 2020 to 28 Jul 2026. Ten of twelve readings are Unchecked.",
        16,
    )
    preview += text(
        46,
        132,
        "Independent points only: no current groundwater surface, contours or flow direction established.",
        14,
    )
    preview += f'<svg x="20" y="155" width="920" height="786" viewBox="0 0 {WIDTH} {HEIGHT}">{svg.split(">", 1)[1].rsplit("</svg>", 1)[0]}</svg>'
    preview += text(955, 183, "Monitoring points", 18, weight=700)
    for i, feature in enumerate(data["features"], 1):
        props = feature["properties"]
        y = 218 + (i - 1) * 58
        preview += text(955, y, f"{i}. {props['station_name']}", 15, weight=700)
        preview += text(
            955, y + 21, f"{props['value_mAOD']:g} mAOD  |  {props['observed_date']}", 13
        )
        preview += text(955, y + 38, props["quality"], 12, "#63747a")
    preview += text(
        32,
        972,
        "Contains Environment Agency information licensed under the Open Government Licence v3.0.",
        13,
    )
    preview += text(
        32,
        996,
        "Map context: © OpenStreetMap contributors, ODbL 1.0. Boundary: ONS May 2024, generalised 20 m.",
        13,
    )
    preview += text(
        32,
        1020,
        "Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right 2026.",
        12,
    )
    preview += text(
        32,
        1044,
        "Aquifer and screen-depth information is not supplied. Inspect dates and source links in the interactive version.",
        13,
    )
    preview += "</svg>"
    (DOCS / "birmingham-groundwater-preview.svg").write_text(
        preview, encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "stations": len(data["features"]),
                "context_ways": len(context["features"]),
                "html_bytes": len(page.encode()),
            }
        )
    )


if __name__ == "__main__":
    main()
