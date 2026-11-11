"""2-D grid-metre screening of complete feature geometries against a polyline."""
import math
from dataclasses import dataclass
from functools import cached_property

from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
from shapely.ops import nearest_points, transform

from .corridor_chainage import RouteAxis


@dataclass
class Corridor:
    line: LineString
    radius: float
    forward: Transformer
    inverse: Transformer
    bbox: list
    gb_box: list
    input_crs: str

    @classmethod
    def make(cls, alignment, radius_m, input_crs='OGC:CRS84'):
        if input_crs not in ('OGC:CRS84','EPSG:27700'):
            raise ValueError('Use OGC:CRS84 (longitude, latitude) or EPSG:27700 (easting, northing).')
        if type(radius_m) not in (int,float) or not 1 <= radius_m <= 2000:
            raise ValueError('radius_m is the distance on each side; use 1–2000 metres.')
        if not isinstance(alignment,dict) or alignment.get('type') != 'LineString' or 'crs' in alignment:
            raise ValueError('Pass a 2-D LineString geometry; declare its units only in input_crs.')
        xy = alignment.get('coordinates')
        if not isinstance(xy,list) or not 2 <= len(xy) <= 256:
            raise ValueError('The alignment requires 2–256 vertices.')
        fw = Transformer.from_crs(4326,27700,always_xy=True,allow_ballpark=False)
        inv = Transformer.from_crs(27700,4326,always_xy=True,allow_ballpark=False)
        vertices = []
        for pair in xy:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2 or not all(type(n) in (int,float) and math.isfinite(n) for n in pair):
                raise ValueError('Each vertex must have two finite numeric coordinates.')
            x,y = pair
            if input_crs == 'OGC:CRS84':
                if not (-9 <= x <= 2 and 49.5 <= y <= 61.1):
                    raise ValueError('Outside the GB screening envelope; coordinates must be longitude first.')
                x,y = fw.transform(x,y,errcheck=True)
            if not (0 <= x <= 700000 and 0 <= y <= 1300000):
                raise ValueError('Outside the supported British National Grid extent.')
            vertices.append((x,y))
        line = LineString(vertices)
        if not 1 <= line.length <= 20000 or any(a==b for a,b in zip(vertices,vertices[1:])):
            raise ValueError('Use a 1 m–20 km alignment without consecutive duplicate vertices; split longer routes.')
        # Network filters only select candidates. Densify the inverse bounds and allow a
        # screening margin for coordinate-operation differences between provider services.
        a,b,c,d = line.bounds
        pad = radius_m + 25
        grid_box = [a-pad,b-pad,c+pad,d+pad]
        box = list(inv.transform_bounds(*grid_box,densify_pts=41,errcheck=True))
        return cls(line,float(radius_m),fw,inv,box,grid_box,input_crs)

    def metric(self, feature, *, tolerance_m=0):
        raw = feature.get('geometry')
        if not isinstance(raw,dict) or raw.get('type') not in ('Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon'):
            raise ValueError('Missing or unsupported feature geometry.')
        geom = shape(raw)
        if geom.is_empty or not geom.is_valid:
            raise ValueError('Empty or invalid source geometry; not silently repaired.')
        a,b,c,d = geom.bounds
        if not (-12 <= a <= c <= 4 and 48 <= b <= d <= 63):
            raise ValueError('Source coordinates are not plausible GB longitude/latitude.')
        grid = transform(self.forward.transform, geom)
        if grid.is_empty or not grid.is_valid or not all(math.isfinite(n) for n in grid.bounds):
            raise ValueError('Geometry invalid after projection.')
        return self.measure(grid, tolerance_m=tolerance_m)

    @cached_property
    def axis(self):
        return RouteAxis(self.line)

    def measure(self, grid, *, tolerance_m=0):
        """Inclusive threshold against the entire geometry, not its centroid or sampled vertices."""
        distance = self.line.distance(grid)
        if not math.isfinite(distance):
            raise ValueError('Distance is not finite.')
        if distance > self.radius + tolerance_m:
            return None
        on_route,on_feature = nearest_points(self.line,grid)
        x,y = self.inverse.transform(on_feature.x,on_feature.y,errcheck=True)
        out = {'within_corridor':distance <= self.radius,
               'threshold_sensitive':abs(distance-self.radius) <= 25,
               'offset_m':round(distance,3),'chainage_m':round(self.line.project(on_route),3),
               'nearest_feature_lonlat':[round(x,7),round(y,7)],
               'nearest_route_bng_m':[round(on_route.x,3),round(on_route.y,3)],
               'nearest_feature_bng_m':[round(on_feature.x,3),round(on_feature.y,3)],
               'geometry_type':grid.geom_type,'centreline_intersects':self.line.intersects(grid)}
        contacts = self.axis.contacts(grid)
        out['centreline_contacts'] = contacts
        if 'covered_length_m' in contacts:
            out['centreline_length_in_area_m'] = contacts['covered_length_m']
        return out

    def bgs_point(self, properties):
        x,y = properties.get('easting'),properties.get('northing')
        if all(type(n) in (int,float) and math.isfinite(n) for n in (x,y)) and 0<x<=700000 and 0<y<=1300000:
            return Point(x,y)
        return None
