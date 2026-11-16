"""Synthetic trip-local red lights; these are not live OSM signal phases."""
import hashlib
import numpy as np

MAIN_ROADS={'primary','secondary','tertiary','trunk'}

def signal_waits(world, seed):
    """Stable red/green scenario: 45% red, 10–30 s at major junctions.

    Explicit traffic_signals node tags are respected when available. Otherwise
    only branching junctions with at least three main-road neighbors qualify;
    courtyard entrances and ordinary road geometry vertices do not.
    """
    graph=world['graph'];waits=np.zeros(len(world['coords']))
    main_neighbors={}
    for u,v,edge in graph.edges(data=True):
        if edge.get('highway') in MAIN_ROADS:
            main_neighbors.setdefault(u,set()).add(v)
            main_neighbors.setdefault(v,set()).add(u)
    for u,node in graph.nodes(data=True):
        if node.get('highway')!='traffic_signals' and len(main_neighbors.get(u,()))<3:continue
        coord=world['coords'][u]
        key=f'{seed}:{coord[0]:.7f}:{coord[1]:.7f}'.encode()
        value=int.from_bytes(hashlib.sha256(key).digest()[:8],'big')
        if value%100<45:waits[u]=10+(value//100)%21
    return waits
