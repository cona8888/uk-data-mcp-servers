"""One read-only engineering corridor search; bounded retrieval is not a full inventory."""
import asyncio
import math

from pyproj.exceptions import ProjError
from shapely.errors import ShapelyError

from .corridor_geo import Corridor
from .corridor_policy import PRODUCTS
from .corridor_validation import geojson_features, page_contract
from .jurisdiction import verify_jurisdiction
from .transport import DataAccessError, utc_now

# Keep source identifiers and dates, not whole provider payloads or person-level fields.
FIELDS = {
    'boreholes':'bgs_id reference name precision year_known length date_updated scan_url',
    'bridges':'asset_id assetid asset_name assetname common_name location name bridge_name description status',
    'flood_defences':'asset_id asset_ref asset_type asset_sub_type asset_name assetname id assettype assettype_desc description primary_purpose asset_reference asset_number',
    'collisions':'collision_index collision_ref_no collision_year collision_severity date first_road_class first_road_number',
    'communities':'wd24cd wd24nm lad24cd lad24nm',
}
TYPES = {'boreholes':('Point',),'bridges':('Point','MultiPoint'),'collisions':('Point',),
         'communities':('Polygon','MultiPolygon'),'flood_defences':('Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon')}


def bad(message):
    raise DataAccessError(message, code='invalid_response')


def features(payload):
    return geojson_features(payload)


async def pages(http, layer, route, budget, audit):
    """Yield bounded pages; never follow a URL or query expression coming from an upstream record."""
    url = PRODUCTS[layer][0]

    async def get(params):
        reply = await http.get_json(url, params=params)
        audit['requests'].append(reply.provenance())
        return reply.data

    if layer in ('boreholes','flood_defences'):
        start = 0
        while start < budget:
            limit = min(100,budget-start)
            params = {'bbox':','.join(f'{x:.8f}' for x in route.bbox),'limit':limit}
            if layer == 'boreholes':
                params.update(f='json',offset=start,skipGeometry='false')
            else:
                params.update(f='application/geo+json',startIndex=start)
            doc = await get(params)
            rows = features(doc)
            if len(rows) > limit:
                bad('Provider ignored the requested feature limit.')
            total, more = page_contract(doc, start, len(rows), audit['bbox_candidate_count'])
            audit['bbox_candidate_count'] = total
            start += len(rows)
            yield rows
            if not more and (start>=total if total is not None else len(rows)<limit):
                return
            if not rows:
                audit['issues'].append('Page did not advance although more candidates were indicated.')
                return
        audit['issues'].append('Candidate budget reached before completeness could be established.')
        return

    params = {'f':'json','where':'1=1','geometry':','.join(f'{x:.3f}' for x in route.gb_box),
              'geometryType':'esriGeometryEnvelope','inSR':27700,'spatialRel':'esriSpatialRelIntersects',
              'returnIdsOnly':'true'}
    response = await get(params)
    if not isinstance(response,dict) or 'error' in response or 'objectIds' not in response:
        bad('ArcGIS spatial ID query returned an invalid response.')
    ids = response['objectIds']
    if ids is None:
        ids = []  # ArcGIS uses null for an empty ID set on some layers.
    if not isinstance(ids,list) or not all(type(x) is int and x>=0 for x in ids) or len(set(ids))!=len(ids):
        bad('Invalid or duplicate object IDs in spatial query.')
    if 'exceededTransferLimit' in response and type(response['exceededTransferLimit']) is not bool:
        bad('Invalid ArcGIS transfer-limit flag.')
    if response.get('exceededTransferLimit'):
        audit['issues'].append('Upstream capped the spatial ID list.')
    audit['bbox_candidate_count'] = len(ids)
    if len(ids)>budget:
        audit['issues'].append('Candidate budget reached: not every bounding-box candidate was examined.')
    field = response.get('objectIdFieldName')
    if ids and (not isinstance(field,str) or not field.isidentifier()):
        bad('Missing ArcGIS object-ID field.')
    ids = sorted(ids)[:budget]
    for start in range(0,len(ids),40):
        batch = ids[start:start+40]
        fields = '*' if layer=='bridges' else ','.join([field,*('WD24CD WD24NM LAD24CD LAD24NM'.split() if layer=='communities' else FIELDS[layer].split())])
        doc = await get({'f':'geojson','objectIds':','.join(map(str,batch)),'outSR':4326,
                         'outFields':fields,'returnGeometry':'true','returnZ':'false','returnM':'false'})
        rows = features(doc)
        returned = set()
        for row in rows:
            oid = (row.get('properties') or {}).get(field, row.get('id')) if isinstance(row,dict) else None
            if type(oid) is not int or oid not in batch or oid in returned:
                bad('ArcGIS returned a different or duplicate feature ID.')
            row['id'] = oid
            returned.add(oid)
        if len(returned)!=len(batch) or doc.get('exceededTransferLimit'):
            audit['issues'].append('Some spatial IDs were missing from the feature page.')
        yield rows


def inspect_feature(route,layer,row):
    if not isinstance(row,dict) or row.get('type')!='Feature' or not isinstance(row.get('properties'),dict):
        raise ValueError('Invalid source feature.')
    attrs = {k.lower():v for k,v in row['properties'].items()}
    # Some services supply CamelCase, others use underscores. Keep provider keys in output.
    wanted = {key.replace('_','') for key in FIELDS[layer].split()}
    props = {k:v for k,v in attrs.items() if k.replace('_','') in wanted and (v is None or type(v) in (int,float,str))}
    ident = row.get('id')
    if type(ident) not in (str,int,float) or str(ident).strip()=='' or len(str(ident))>200:
        raise ValueError('Feature has no usable identifier.')
    if layer=='collisions' and (str(attrs.get('collision_year'))!='2025' or not attrs.get('collision_index')):
        raise ValueError('Missing collision identity or wrong edition.')
    if layer=='communities' and not (attrs.get('wd24cd') and attrs.get('wd24nm')):
        raise ValueError('Missing ward identity.')
    pt = route.bgs_point(attrs) if layer=='boreholes' else None
    if pt is not None:
        measurement = route.measure(pt, tolerance_m=25)
        source_position = {'crs':'EPSG:27700', 'coordinates':[pt.x, pt.y]}
        basis = 'published BNG easting/northing'
    else:
        geom = row.get('geometry')
        if not isinstance(geom,dict) or geom.get('type') not in TYPES[layer]:
            raise ValueError('Missing or unexpected source geometry.')
        measurement = route.metric(row, tolerance_m=25)
        source_position = {'crs':'OGC:CRS84', 'geometry_type':geom['type']}
        if geom['type'] == 'Point':
            source_position['coordinates'] = geom['coordinates']
        basis = 'source geometry projected to EPSG:27700'
    if measurement is None:
        return str(ident),None
    return str(ident), {'source_feature_id':str(ident),'attributes':props,'position_basis':basis,'source_position':source_position,**measurement}


async def _layer(http,layer,route,nation,budget,limit):
    _,title,coverage,url,terms = PRODUCTS[layer]
    audit = {'product':title,'source_page':url,'coverage':coverage,'attribution_and_limits':terms,
             'requests':[],'bbox_candidate_count':None,'features_examined':0,'unlocatable_or_invalid':0,
             'outside_corridor':0,'duplicate_candidates':0,'issues':[],'data':[],
             'inventory_complete':False, 'coverage_status':'verified_for_declared_nation', 'boundary_candidates':[],
             'boundary_candidates_count':0, 'boundary_candidates_truncated':False,
             'boundary_review_margin_m':25, 'threshold_sensitive_matched':0}
    if (layer=='flood_defences' and nation!='England') or (layer=='bridges' and nation=='Scotland'):
        return {**audit,'status':'not_applicable','coverage_status':'not_applicable',
                'candidate_scan_complete':False,'returned':0,'more_matches_than_shown':False,
                'matched_examined':None,'issues':['Product not configured for the declared nation. Split cross-border routes.']}
    seen, hits, borderline = set(), [], []
    try:
        async for rows in pages(http,layer,route,budget,audit):
            for row in rows:
                audit['features_examined']+=1
                try:
                    fid,hit = inspect_feature(route,layer,row)
                except (ValueError,TypeError,KeyError,IndexError,OverflowError,ProjError,ShapelyError):
                    audit['unlocatable_or_invalid']+=1
                    continue
                if fid in seen:
                    audit['duplicate_candidates']+=1
                    continue
                seen.add(fid)
                if hit is None or not hit['within_corridor']:
                    audit['outside_corridor']+=1
                    if hit is not None:
                        borderline.append(hit)
                else:
                    hits.append(hit)
    except (DataAccessError, ValueError, TypeError, TimeoutError) as exc:
        audit['error']={'code':getattr(exc,'code','invalid_response'),'message':str(exc),'url':getattr(exc,'url',None)}
        audit['issues'].append('Source retrieval failed; no inference about missing features.')
    if audit['unlocatable_or_invalid'] or audit['duplicate_candidates']:
        audit['issues'].append('Invalid, unlocatable or duplicate candidates prevent a complete determination.')
    hits.sort(key=lambda x:(x['offset_m'],x['chainage_m'],x['source_feature_id']))
    borderline.sort(key=lambda x:(x['offset_m'],x['chainage_m'],x['source_feature_id']))
    audit.update(boundary_candidates=borderline[:limit], boundary_candidates_count=len(borderline),
                 boundary_candidates_truncated=len(borderline)>limit,
                 threshold_sensitive_matched=sum(hit['threshold_sensitive'] for hit in hits),
                 membership_stability='review_required' if borderline or any(hit['threshold_sensitive'] for hit in hits)
                                      else 'no_candidates_in_fixed_review_band')
    failed = 'error' in audit and not audit['features_examined']
    audit.update(status='error' if failed else 'partial' if audit['issues'] else 'ok' if hits else 'empty',
                 matched_examined=None if failed else len(hits), data=hits[:limit],
                 returned=len(hits[:limit]),more_matches_than_shown=len(hits)>limit,
                 candidate_scan_complete=not bool(audit['issues']))
    return audit


async def corridor_query(http, alignment, nation, radius_m=250, input_crs='OGC:CRS84',
                         layers=None, candidate_budget=500, limit=25):
    """Evaluate an inclusive 2-D distance predicate; input alignment is not a road-network match."""
    if nation not in ('England','Scotland','Wales'):
        raise ValueError('This version supports single-nation Great Britain routes; Northern Ireland is not integrated.')
    if type(limit) is not int or not 1<=limit<=100 or type(candidate_budget) is not int or not 1<=candidate_budget<=1000:
        raise ValueError('Use limit 1–100 and candidate_budget 1–1000 per source.')
    layers = list(PRODUCTS) if layers is None else layers
    if not isinstance(layers,list) or not 1<=len(layers)<=len(PRODUCTS) or any(not isinstance(k,str) or k not in PRODUCTS for k in layers) or len(set(layers))!=len(layers):
        raise ValueError('Select distinct layers from: '+', '.join(PRODUCTS))
    route = Corridor.make(alignment,radius_m,input_crs)
    jurisdiction = await verify_jurisdiction(http, route, nation)
    if jurisdiction['status'] != 'verified':
        return {'kind':'civil_corridor_screen', 'schema_version':'1.1', 'status':'error',
                'error':jurisdiction['error'], 'jurisdiction':jurisdiction, 'results':{},
                'data':[], 'inventory_complete':False,
                'note':'Asset searches were not run. Coverage could not be established; this is not a zero result.'}
    results = dict(zip(layers, await asyncio.gather(*(_layer(http,k,route,nation,candidate_budget,limit) for k in layers))))
    states = [r['status'] for r in results.values()]
    status = 'error' if all(s=='error' for s in states) else 'partial' if any(s in ('partial','error','not_applicable') for s in states) else 'empty' if all(s=='empty' for s in states) else 'ok'
    op = route.inverse.get_last_used_operation()
    return {'kind':'civil_corridor_screen','schema_version':'1.1','status':status,
            'jurisdiction':jurisdiction,'inventory_complete':False,'retrieved_at_utc':utc_now(),
            'request':{'alignment':alignment,'input_crs':input_crs,'nation':nation,'radius_m':radius_m,'candidate_budget':candidate_budget,'limit':limit,'layers':layers},
            'metric':{'crs':'EPSG:27700','length_m':round(route.line.length,3),'route_bng_m':[list(p) for p in route.line.coords],
                      'candidate_bbox_crs84':route.bbox,'inverse_coordinate_operation':op.description,
                      'inverse_operation_accuracy_m':op.accuracy if math.isfinite(op.accuracy) and op.accuracy>=0 else None,
                      'rule':'Unrounded minimum 2-D grid distance to the complete centreline <= radius_m; round end caps. Chainage is one nearest location, not every crossing.'},
            'results':results,'limitations':['Nation verified for the entire padded envelope against ONS December 2024 polygons. Not a survey or a statutory search.',
            'Results close to the threshold depend on positional precision, coordinate transformation and map generalisation.',
            'The 25 m threshold-review band is a screening heuristic, not a surveyed accuracy or confidence interval.',
            'An offset is plan distance, not vertical clearance, hydraulic protection, structural condition, collision attribution or a service catchment.',
            'Matched counts apply to uniquely identified, located records examined. Output is limited per layer; inspect issues and candidate_scan_complete. Faults and empty queries do not prove absence.']}
