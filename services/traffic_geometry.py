"""Full-network display: merge adjacent same-color edges without dropping roads."""
import base64

import numpy as np


def _write_uint(buffer, value):
    while value >= 128:
        buffer.append((value & 127) | 128)
        value >>= 7
    buffer.append(value)


def pack_traffic_bands(bands):
    """Encode display polylines as Base64 varints at OSM's 7-digit precision."""
    packed = []
    for band in bands:
        buffer = bytearray()
        for line in band:
            _write_uint(buffer, len(line))
            previous = [0, 0]
            for point in line:
                for axis, value in enumerate(point):
                    coordinate = round(value * 10_000_000)
                    delta = coordinate - previous[axis]
                    previous[axis] = coordinate
                    _write_uint(buffer, 2 * delta if delta >= 0 else -2 * delta - 1)
        packed.append(base64.b64encode(buffer).decode('ascii'))
    return packed


def traffic_bands(world, traffic, *, three_colors=False):
    """Four lists of polylines. Shared centerlines show the busier direction.

    Merging changes display only; routing keeps directional slowdown values.
    No viewport/radius/segment-count cutoffs. All input graph edges are covered.
    """
    levels={}
    rows,actions=np.nonzero(world['valid'])
    targets=world['dest'][rows,actions]
    values=traffic[rows,actions]
    for u,v,value in zip(rows.tolist(),targets.tolist(),values.tolist()):
        edge=(u,v) if u<=v else (v,u)
        levels[edge]=max(levels.get(edge,0.),value)
    bands=[[],[],[],[]]
    adjacency=[{} for _ in bands]
    for (u,v),value in levels.items():
        band=0 if value<=.05 else 1 if value<1 else 2 if value<2 and not three_colors else 3
        adjacency[band].setdefault(u,[]).append(v)
        adjacency[band].setdefault(v,[]).append(u)
    for band,neighbors in enumerate(adjacency):
        visited=set()
        def walk(start,nxt):
            path=[start];u,v=start,nxt
            while (min(u,v),max(u,v)) not in visited:
                visited.add((min(u,v),max(u,v)));path.append(v)
                if len(neighbors[v])!=2:break
                choices=neighbors[v];u,v=v,choices[1] if choices[0]==u else choices[0]
            bands[band].append(world['coords'][path].tolist())
        # First open chains, then closed rings with degree two everywhere.
        for u,vs in neighbors.items():
            if len(vs)!=2:
                for v in vs:
                    if (min(u,v),max(u,v)) not in visited:walk(u,v)
        for u,vs in neighbors.items():
            for v in vs:
                if (min(u,v),max(u,v)) not in visited:walk(u,v)
    return bands
