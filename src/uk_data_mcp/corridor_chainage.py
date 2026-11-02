"""Locate actual plan contacts on a directed alignment, preserving repeated traversals."""
from bisect import bisect_right
from collections import defaultdict
from itertools import accumulate, pairwise
from math import fsum

from shapely import STRtree
from shapely.geometry import LineString, Point

EVENT_LIMIT = 32


def _merged(spans):
    """Union closed intervals in 1-D. Do not snap or bridge positive gaps."""
    out = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


class RouteAxis:
    def __init__(self, route):
        self.segments = [LineString([a, b]) for a, b in pairwise(route.coords)]
        self.chain = list(accumulate((s.length for s in self.segments), initial=0.0))
        self.tree = STRtree(self.segments)

    def _collect(self, geom, index, spans, points):
        segment = self.segments[index]
        a, b = list(segment.coords)

        def locate(xy):
            if xy[:2] == a[:2]:
                return self.chain[index]
            if xy[:2] == b[:2]:
                return self.chain[index + 1]
            return self.chain[index] + segment.project(Point(xy[:2]))

        stack = [geom]
        while stack:
            item = stack.pop()
            if item.is_empty:
                continue
            if item.geom_type == 'Point':
                points.add(locate(item.coords[0]))
            elif item.geom_type == 'LineString':
                spans.append(tuple(sorted((locate(item.coords[0]), locate(item.coords[-1])))))
            elif hasattr(item, 'geoms'):
                stack.extend(item.geoms)
            else:
                raise ValueError('Unexpected non-linear segment intersection.')

    def contacts(self, geom):
        area = geom.geom_type in ('Polygon', 'MultiPolygon')
        spans, points = defaultdict(list), set()
        indices = self.tree.query(geom, predicate='intersects')
        boundary = geom.boundary if area and len(indices) else None
        for i in indices:
            contact = self.segments[i].intersection(geom)
            if area:
                self._collect(contact.intersection(boundary), i, spans['area_boundary'], points)
                self._collect(contact.difference(boundary), i, spans['area_interior'], points)
            else:
                self._collect(contact, i, spans['line_overlap'], points)

        events = [(a, b, kind) for kind, intervals in spans.items() for a, b in _merged(intervals)]
        covered = _merged((a, b) for a, b, _ in events)
        starts = [a for a, _ in covered]
        for p in points:
            j = bisect_right(starts, p) - 1
            if j < 0 or p > covered[j][1]:
                events.append((p, p, 'point_contact'))
        events.sort()
        total = len(events)
        interior = fsum(b - a for a, b, k in events if k == 'area_interior')
        edge = fsum(b - a for a, b, k in events if k == 'area_boundary')
        result = {
            'relation': ('nearby_only' if not total else 'interior_traversed' if interior else
                         'boundary_followed' if edge else 'boundary_touch' if area else
                         'linear_overlap' if any(b > a for a, b, _ in events) else 'point_contact'),
            'count': total, 'truncated': total > EVENT_LIMIT,
            'events': [{'kind': k, 'start_m': round(a, 6), 'end_m': round(b, 6)}
                       for a, b, k in events[:EVENT_LIMIT]],
        }
        if area:
            result.update(interior_length_m=round(interior, 3), boundary_length_m=round(edge, 3),
                          covered_length_m=round(interior + edge, 3))
        return result
