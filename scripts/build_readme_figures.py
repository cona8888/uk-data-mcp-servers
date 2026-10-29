"""Generate original SVG README figures from the dated public example.

Uses only the standard library. The checked-in PNGs are raster exports of these
SVGs (rendered with Sharp); neither is an application screenshot or a site plan.
"""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
NAVY, TEAL, INK, MUTED = "#183B42", "#087F70", "#17343A", "#536B70"
PAPER, LINE = "#F4F7F4", "#D6E3DD"


def text(x, y, value, *, size=20, colour=INK, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{colour}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif">{escape(str(value))}</text>'
    )


def rect(x, y, width, height, fill, radius=0, stroke=None):
    outline = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}"{outline}/>'
    )


def save(name, height, title, description, body):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{height}" '
        f'viewBox="0 0 1280 {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
        + "".join(body) + "</svg>\n"
    )
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8", newline="\n")


def workflow():
    body = [rect(0, 0, 1280, 418, NAVY, 24)]
    body += [text(44, 49, "GROUNDWORK", size=16, colour="#A2DBCC", weight=700),
             text(44, 99, "From a site question to a review plan", size=34,
                  colour="white", weight=700)]
    steps = [
        ("01", "Define", "Location and proposed works", ["Use an explicit search point.", "Keep the project scope clear."]),
        ("02", "Gather", "Cited public evidence", ["Geology and record indexes.", "Dates, licences and coverage."]),
        ("03", "Review", "Records and evidence gaps", ["Check original-record relevance.", "Add notes and track GI gaps."]),
        ("04", "Save", "A study you can return to", ["Editable JSON workspace.", "Printable report and registers."]),
    ]
    for index, (number, title, subtitle, lines) in enumerate(steps):
        x = 44 + index * 304
        body += [rect(x, 133, 280, 205, "white", 15),
                 text(x + 20, 167, number, size=15, colour=TEAL, weight=700),
                 text(x + 20, 208, title, size=30, weight=700),
                 text(x + 20, 241, subtitle, size=15, colour=TEAL, weight=700),
                 text(x + 20, 277, lines[0], size=15, colour=MUTED),
                 text(x + 20, 301, lines[1], size=15, colour=MUTED)]
        if index < 3:
            body.append(f'<path d="M {x+286} 230 h 11 m -5 -5 l 5 5 -5 5" '
                        'fill="none" stroke="#A2DBCC" stroke-width="2"/>')
    body += [text(44, 381, "Keep source evidence visible. Use professional judgement before design or excavation.",
                  size=18, colour="#D2E8DF")]
    save("groundwork-workflow", 418, "How Groundwork works",
         "Define a location and works, gather cited public evidence, review record relevance and GI gaps, then save the study.", body)


def example():
    path = ROOT / "examples" / "leeds_small_house_example_2026-10-29.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = data["summary"]["investigation_count"]
    tasks = data["summary"]["open_gap_count"]
    unknowns = sum(p["value"] is None for p in data["design_parameters"].values())
    assert (candidates, tasks, unknowns) == (20, 12, 7)
    assert data["project"]["development_type"] == "housing"
    body = [rect(0, 0, 1280, 640, PAPER, 24),
            text(44, 45, "SAVED EXAMPLE  /  PUBLIC EVIDENCE: 29 OCTOBER 2026", size=15,
                 colour=TEAL, weight=700),
            text(44, 96, "A small house in Leeds", size=38, weight=700),
            text(44, 130, "Hypothetical project: two storeys, around 100 m², no basement", size=21, colour=MUTED),
            rect(44, 166, 325, 345, NAVY, 18)]
    # Original diagram: intentionally schematic, with no ground profile or foundations.
    body += [
        '<path d="M 91 305 L 205 219 L 319 305" stroke="#9BDFCD" stroke-width="7" '
        'stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
        '<path d="M 111 294 V 432 H 300 V 294" stroke="white" stroke-width="6" fill="none"/>',
        rect(139, 318, 40, 35, "#9BDFCD", 3), rect(231, 318, 40, 35, "#9BDFCD", 3),
        rect(139, 379, 40, 34, "#9BDFCD", 3), rect(231, 377, 39, 55, "#F1CB86", 3),
        '<path d="M 86 448 H 326" stroke="#8EB4B1" stroke-width="3"/>',
        text(206, 485, "Illustration, not a site plan", size=15, colour="#D2E8DF", anchor="middle"),
    ]
    cards = [(candidates, "Index candidates", "Originals need review"),
             (tasks, "Open review tasks", "Questions, not hazards"),
             (unknowns, "Values still unknown", "Design / site checks")]
    for index, (number, title, subtitle) in enumerate(cards):
        x = 397 + index * 280
        body += [rect(x, 166, 259, 170, "white", 14, LINE),
                 text(x + 20, 229, number, size=49, colour=TEAL, weight=700),
                 text(x + 20, 270, title, size=20, weight=700),
                 text(x + 20, 304, subtitle, size=16, colour=MUTED)]
    body += [text(397, 380, "What comes next?", size=25, weight=700)]
    for index, label in enumerate([
        "Confirm the actual site, loads, layout and movement criteria.",
        "Review original records, relevance and possible duplicates.",
        "Resolve ground-model and groundwater gaps before design.",
    ]):
        y = 419 + index * 37
        body += [f'<circle cx="407" cy="{y-6}" r="5" fill="{TEAL}"/>',
                 text(425, y, label, size=19, colour=INK)]
    body += [rect(44, 541, 1192, 65, "#E3EEE7", 12),
             text(63, 567, "20 candidates = 10 borehole-index + 10 investigation-file-index records. They are not 20 distinct holes at the site.",
                  size=16, colour=INK),
             text(63, 590, "Search uses an enclosing rectangle. Records outside the requested circle remain visible. Source dates and limits stay with the study.",
                  size=15, colour=MUTED)]
    save("leeds-house-example", 640, "Leeds small-house example",
         "Illustrated example using the saved Leeds workspace: 20 index candidates, 12 open review tasks and seven unknown design or check values. The house is hypothetical, not an actual parcel or design.", body)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    workflow()
    example()
    print("Generated two SVG figures from the saved public example.")
