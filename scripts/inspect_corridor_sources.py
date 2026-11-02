"""Inspect fixed upstream layer identities when maintaining the corridor adapters."""
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

URLS = {
    'crt': 'https://www.arcgis.com/sharing/rest/content/items/5ab39ef2b99f46b6873547aeb7bb81dc?f=json',
    'ea': 'https://environment.data.gov.uk/geoservices/datasets/8e5be50f-d465-11e4-ba9a-f0def148f590/ogc/features/v1/collections?f=application%2Fjson',
    'dft': 'https://services5.arcgis.com/qUwnXV5uf1zyW6Y2/ArcGIS/rest/services/RoadCasualtyStatsCollision_GB_DfT_Point_2025/FeatureServer/0?f=json',
    'wards': 'https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Wards_December_2024_Boundaries_UK_BGC/FeatureServer/0?f=json',
}


def inspect(item):
    key, url = item
    try:
        req = Request(url, headers={'Accept':'application/json','User-Agent':'UK-Civil-Data/metadata-check'})
        with urlopen(req, timeout=20) as response:
            meta = json.loads(response.read(1000000))
        return key, {k:meta.get(k) for k in ('title','name','url','accessInformation','error') if meta.get(k)} | {'collections':[c.get('id') for c in meta.get('collections',[])], 'fields':[f['name'] for f in meta.get('fields',[])]}
    except (ValueError, OSError) as exc:
        return key, {'error':str(exc)}


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        print(json.dumps(dict(pool.map(inspect, URLS.items())), indent=2))
