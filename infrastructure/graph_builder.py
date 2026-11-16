from pathlib import Path
from domain.models import RoadWorld
import json
import numpy as np
import networkx as nx
from utils.geo import distance
from road_rules import car_directions
from scipy.spatial import cKDTree
from environments.edge_snap import build_edge_index
from infrastructure.speeds import speed_metadata
from infrastructure.repository import bytes_version
from environments.travel_time import edge_seconds

def build_world(path: Path, expected_version: str | None = None) -> RoadWorld:
    """Read a road snapshot and construct a new independent world."""
    content=path.read_bytes()
    version=bytes_version(content)
    if expected_version is not None and version!=expected_version:
        raise ValueError('Карта файлы есептеу кезінде өзгерді. Қайта есептеңіз.')
    data=json.loads(content.decode('utf-8'))
    if not isinstance(data.get('nodes'),dict) or not isinstance(data.get('ways'),list):
        raise ValueError('Жол базасының құрылымы қате.')
    for coord in data['nodes'].values():
        if len(coord)!=2 or not np.isfinite(coord).all() or not (-90<=coord[0]<=90 and -180<=coord[1]<=180):
            raise ValueError('Жол базасында жарамсыз координат бар.')
    # First retain only legal, nonzero segments. Allocate final integer IDs
    # before building either graph, avoiding two full relabel copies.
    segments=[];used=set();way_directions={}
    for way_index,w in enumerate(data['ways']):
        directions=car_directions(w['tags'])
        if not directions:continue
        way_directions[way_index]=directions
        for segment_index,(a,b) in enumerate(zip(w['nodes'],w['nodes'][1:])):
            if a not in data['nodes'] or b not in data['nodes']:
                raise ValueError('Жол сегментінің координаты жоқ. Базаны жаңартыңыз.')
            if a==b:continue
            length=distance(data['nodes'][a],data['nodes'][b])
            if length<.01:continue
            segments.append((way_index,segment_index,a,b,length))
            used.update((a,b))
    if not used:
        raise ValueError('Көлікке рұқсат етілген жолдар табылмады. Қала базасын жаңартыңыз.')
    names=sorted(used);mapping={name:i for i,name in enumerate(names)}
    roads=nx.MultiDiGraph();g=nx.DiGraph()
    for way_index,segment_index,a,b,length in segments:
        w=data['ways'][way_index];tags=w['tags'];directions=way_directions[way_index]
        edges=[(a,b) if d==1 else (b,a) for d in directions]
        for u,v in edges:
            direction=1 if (u,v)==(a,b) else -1
            metadata=dict(length=length,name=tags.get('name','Атаусыз жол'),
                highway=tags.get('highway'),way_id=str(w.get('id',way_index)),
                segment_index=segment_index,direction=direction,
                geometry=[list(data['nodes'][u]),list(data['nodes'][v])],
                **speed_metadata(tags,direction))
            metadata['free_flow_time_s']=edge_seconds(metadata)
            key=f"{metadata['way_id']}:{way_index}:{segment_index}:{direction}"
            node_u,node_v=mapping[u],mapping[v]
            roads.add_edge(node_u,node_v,key=key,**metadata)
            # Q/HMM still use node-neighbor actions. Preserve all alternatives
            # in road_graph, with a deterministic free-flow-time projection for algorithms.
            rank=(metadata['free_flow_time_s'],length,metadata['way_id'])
            if not g.has_edge(node_u,node_v) or rank<g[node_u][node_v]['selection_rank']:
                g.add_edge(node_u,node_v,**metadata,road_key=key,selection_rank=rank)
    del segments,used,mapping,way_directions
    coords=np.array([data['nodes'][x] for x in names])
    k=max(1,max(dict(g.out_degree()).values()))
    dest=np.repeat(np.arange(len(coords))[:,None],k,axis=1)
    valid=np.zeros_like(dest,dtype=bool)
    lengths=np.ones_like(dest,dtype=float)
    for u in g:
        # Әрекет = осы түйіндегі шығаберістің тұрақты индексі.
        neighbors=sorted(g.successors(u),key=lambda v: np.arctan2(coords[v,0]-coords[u,0],coords[v,1]-coords[u,1]))
        for a,v in enumerate(neighbors):
            dest[u,a]=v;valid[u,a]=True;lengths[u,a]=g[u][v]['length']
    lat0=float(coords[:,0].mean());lon0=float(coords[:,1].mean())
    xy=np.column_stack([(coords[:,1]-lon0)*111320*np.cos(np.radians(lat0)),(coords[:,0]-lat0)*111320])
    world=dict(graph=g,road_graph=roads,dataset_version=version,dataset_path=str(path.resolve()),
                spatial_index=cKDTree(coords,copy_data=True),original_node_ids=names,coords=coords,dest=dest,valid=valid,lengths=lengths,xy=xy,lat0=lat0,lon0=lon0,source=data)


    # The spatial edge index is built on the first destination click, not startup.
    return world
