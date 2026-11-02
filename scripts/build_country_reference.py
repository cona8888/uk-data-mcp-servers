"""Generate conservative 5 km interior cells from fixed-edition ONS country polygons (BNG)."""
import base64
import hashlib
import json
import sys
import zlib
from pathlib import Path

import httpx
import shapefile
import shapely
from shapely.geometry import box, shape

URL = ('https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/'
       'Countries_December_2024_Boundaries_UK_BGC/FeatureServer/0/query')
CODES = ('E92000001', 'W92000004', 'S92000003')


def build():
    cells = bytearray(140 * 260)
    hashes = {}
    for idx, code in enumerate(CODES, 1):
        res = httpx.get(URL, params={'f':'json','where':f"CTRY24CD='{code}'",'outFields':'CTRY24CD',
                        'returnGeometry':'true','outSR':'27700'}, timeout=60)
        res.raise_for_status()
        doc = res.json()
        assert doc['spatialReference'].get('latestWkid',doc['spatialReference']['wkid']) == 27700
        feature, = doc['features']
        assert feature['attributes']['CTRY24CD'] == code
        rings = feature['geometry']['rings']
        s = shapefile.Shape(shapefile.POLYGON)
        s.points = [p[:2] for r in rings for p in r]
        from itertools import accumulate
        s.parts = list(accumulate((len(r) for r in rings[:-1]), initial=0))
        poly = shape(s.__geo_interface__)
        if not poly.is_valid:
            poly = shapely.make_valid(poly)
        shapely.prepare(poly)
        hashes[code] = hashlib.sha256(res.content).hexdigest()
        for j in range(260):
            for i in range(140):
                # Additional 100 m guard on top of product's 20 m generalisation.
                square = box(5000*i-100,5000*j-100,5000*(i+1)+100,5000*(j+1)+100)
                if poly.covers(square):
                    assert cells[140*j+i] == 0
                    cells[140*j+i] = idx
        print(code,cells.count(idx),flush=True)
    assert all(cells.count(i)>400 for i in (1,2,3))
    return {'source':URL,'edition':'2024-12 BGC','hashes':hashes,'shape':[260,140],
            'cell_m':5000,'guard_m':100,'sha256':hashlib.sha256(cells).hexdigest(),
            'zlib_base64':base64.b64encode(zlib.compress(cells,9)).decode('ascii')}


if __name__ == '__main__':
    data=build()
    (Path(sys.argv[1])/'country_grid.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('REFERENCE',json.dumps(data))
