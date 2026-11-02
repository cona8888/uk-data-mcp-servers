"""Render a saved corridor report as a self-contained HTML locator map. No web requests."""
import argparse
import html
import json
import math
from pathlib import Path

LAYERS = {'boreholes':('Borehole records','#3b648b'), 'bridges':('Canal-network bridges','#ac5124'),
          'flood_defences':('Defence records','#147867'), 'collisions':('Injury collisions','#994438'),
          'communities':('Ward polygons','#7054a3')}


def esc(value):
    return html.escape(str(value),quote=True)


def render(report):
    if report.get('kind')!='civil_corridor_screen' or report.get('metric',{}).get('crs')!='EPSG:27700':
        raise ValueError('Expected a British National Grid corridor report.')
    m=report['metric']
    pts=m['route_bng_m']
    radius=float(report['request']['radius_m'])
    if not 1<=radius<=2000 or not 2<=len(pts)<=256:
        raise ValueError('Invalid route or radius.')
    xs,ys=zip(*pts)
    margin=radius+85
    x0,y0,x1,y1=min(xs)-margin,min(ys)-margin,max(xs)+margin,max(ys)+margin
    W,H=x1-x0,y1-y0
    def pixel(p):
        x,y=map(float,p)
        if not math.isfinite(x+y):
            raise ValueError('Nonfinite locator.')
        return x-x0,y1-y
    route=' '.join('%.3f,%.3f'%pixel(p) for p in pts)
    svg=[f'<svg viewBox="-20 -20 {W+40:.3f} {H+40:.3f}" role="img" aria-label="Corridor plan in the British National Grid; north is up"><rect width="{W:.2f}" height="{H:.2f}" fill="#f7faf9"/>',
         f'<polyline points="{route}" stroke="#d4e8e1" stroke-width="{2*radius}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>']
    step=10**math.floor(math.log10(max(W,H)/4))
    if max(W,H)/step>8:
        step*=2
    for x in range(math.ceil(x0/step)*step,math.ceil(x1/step)*step,step):
        svg.append(f'<path d="M{x-x0:.1f},0v{H:.1f}" stroke="#b6c7c1" stroke-width="1"/><text x="{x-x0+3:.1f}" y="{H-10:.1f}" font-size="{W/60:.2f}">{x:,} E</text>')
    for y in range(math.ceil(y0/step)*step,math.ceil(y1/step)*step,step):
        svg.append(f'<path d="M0,{y1-y:.1f}h{W:.1f}" stroke="#b6c7c1" stroke-width="1"/><text x="4" y="{y1-y-4:.1f}" font-size="{W/60:.2f}">{y:,} N</text>')
    svg.append(f'<polyline points="{route}" stroke="#173a35" stroke-width="{W/230:.2f}" fill="none" stroke-linejoin="round"/>')
    switches=[]
    cards=[]
    rows=[]
    credits=[]
    scale=W/150
    for key,(name,color) in LAYERS.items():
        if key not in report['results']:
            continue
        layer=report['results'][key]
        switches.append(f'<label><input type="checkbox" data-toggle="{key}" checked> <b style="color:{color}">●</b> {name}</label>')
        qty=layer.get('matched_examined')
        display='—' if qty is None else str(qty)
        cards.append(f'<div><strong>{esc(display)}</strong>{name}<small>{esc(layer["status"])} · {len(layer["data"])} displayed</small></div>')
        credits.append(f'<p><b>{esc(layer["product"])}</b> · {esc(layer["coverage"])}<br>{esc(layer["attribution_and_limits"])}<br><code>{esc(layer["source_page"])}</code></p>')
        svg.append(f'<g data-layer="{key}" fill="{color}" stroke="white" stroke-width="{scale*.24:.2f}">')
        for item in layer['data']:
            x,y=pixel(item['nearest_feature_bng_m'])
            props=item['attributes']
            label=next((props[n] for n in ('wd24nm','reference','asset_id','collision_index','asset_name','name') if props.get(n)),item['source_feature_id'])
            ident=esc(label)
            offset=float(item['offset_m'])
            chain=float(item['chainage_m'])
            svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{scale:.2f}"><title>{esc(name)}: {ident} · offset {offset:.1f} m · chainage {chain:.1f} m</title></circle>')
            rows.append(f'<tr data-layer="{key}"><td>{esc(name)}</td><td>{ident}</td><td>{offset:.1f}</td><td>{chain:.1f}</td><td>{"Yes" if item["centreline_intersects"] else "No"}</td></tr>')
        svg.append('</g>')
    for idx,name in [(0,'Start'),(-1,'End')]:
        x,y=pixel(pts[idx])
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{scale*.55:.2f}" fill="#152f2b"/><text x="{x+scale*1.6:.2f}" y="{y-scale*1.5:.2f}" font-size="{W/43:.2f}" fill="#152f2b" stroke="white" stroke-width="3" paint-order="stroke">{name}</text>')
    svg.append('</svg>')
    css='''*{box-sizing:border-box}body{margin:0;background:#eef3f1;color:#15302c;font:16px/1.5 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:32px}header,article,aside,details{background:white;border:1px solid #c9d6d0;border-radius:12px;padding:22px 26px;margin-bottom:16px}h1{font-size:clamp(28px,4vw,44px);line-height:1.1;margin:8px 0}h2{font-size:21px;margin:0 0 10px}.eyebrow{letter-spacing:.14em;font-weight:700;font-size:12px;color:#45695e}.muted,small{color:#4b625c}.grid{display:grid;grid-template-columns:minmax(0,1.5fr) 1fr;gap:16px}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px}.metrics div{border-top:1px solid #dce5e1;padding:7px 0}.metrics strong,.metrics small{display:block}.metrics strong{font-size:28px}svg{width:100%;max-height:660px}.controls label{display:block;margin:6px 0}.tablewrap{max-height:420px;overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px;border-bottom:1px solid #dae5e0}th{position:sticky;top:0;background:#edf3f0}td:nth-child(3),td:nth-child(4){font-variant-numeric:tabular-nums}summary{cursor:pointer;font-weight:bold}code{overflow-wrap:anywhere;font-size:.84em}[hidden]{display:none!important}@media(max-width:750px){main{padding:12px}.grid{grid-template-columns:1fr}header,article,aside,details{padding:16px}}'''
    js="document.querySelectorAll('[data-toggle]').forEach(box=>box.addEventListener('change',()=>document.querySelectorAll('[data-layer='+box.dataset.toggle+']').forEach(node=>node.toggleAttribute('hidden',!box.checked))));"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Civil corridor | Evidence map</title><style>{css}</style></head><body><main><header><div class="eyebrow">UK CIVIL DATA / CORRIDOR SCREEN</div><h1>Alignment evidence map</h1><p>{esc(report.get("example","User-supplied alignment"))}</p><b>{m["length_m"]:,.1f} m alignment · {radius:g} m each side</b><div class="muted">Retrieved {esc(report["retrieved_at_utc"])} · Screen status: {esc(report["status"])}</div></header><div class="grid"><article><h2>Plan view</h2><p class="muted">British National Grid, metres. North is up. The shaded area is the search corridor.</p>'
            +''.join(svg)+'</article><aside><h2>Records within the corridor</h2><div class="metrics">'+''.join(cards)+'</div><h2 style="margin-top:22px">Visible layers</h2><div class="controls">'+''.join(switches)+'</div><p class="muted">For lines and polygons, each dot is one closest point, not the full feature. Ward contact does not establish who uses the route.</p></aside></div><article><h2>Feature register</h2><div class="tablewrap"><table><thead><tr><th>Layer</th><th>Name or source ID</th><th>Offset (m)</th><th>Chainage (m)</th><th>Crosses or touches centreline?</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></article><details><summary>Sources, rights and screening limits</summary>'+''.join(credits)+''.join('<p>'+esc(n)+'</p>' for n in report['limitations'])+f'</details></main><script>{js}</script></body></html>')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.write_text(render(json.loads(args.report.read_text(encoding='utf-8'))),encoding='utf-8')
