"""Metric road projection and a private, directed destination-node overlay."""
from dataclasses import dataclass
import hashlib
import numpy as np
import networkx as nx
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from shapely.ops import substring
from pyproj import Transformer

class NoRoadInReach(ValueError):
    messages = {
        'kk': 'Шақырту орнынан 500 м ішінде ауруханадан көлікпен жетуге болатын жол табылмады. Жақын көшені немесе кіреберісті таңдаңыз.',
        'ru': 'В пределах 500 м от точки вызова нет дороги, доступной от больницы. Выберите ближайшую улицу или подъезд.',
        'en': 'No road within 500 m of the call is reachable from a hospital. Choose a nearby street or entrance.',
    }


@dataclass
class EdgeIndex:
    edges: list
    lines: list
    tree: cKDTree
    max_radius: float
    forward: Transformer
    inverse: Transformer


def build_edge_index(world) -> EdgeIndex:
    """Build once per snapshot. Project graph's [lat,lon] geometries to UTM 42N.

    Uses the same directed driving graph as A*/Q, not pedestrian OSM ways.
    """
    forward=Transformer.from_crs(4326,32642,always_xy=True)
    inverse=Transformer.from_crs(32642,4326,always_xy=True)
    # Imported OSM graph retains every shape vertex: batch two-point segments.
    # Generic polyline worlds still use the exact implementation below.
    records=list(world['graph'].edges(data=True))
    if records and all(len(d.get('geometry', (u,v)))==2 for u,v,d in records):
        from shapely import linestrings
        edges=[(u,v) for u,v,_ in records]
        geo=np.asarray([d['geometry'] if 'geometry' in d else world['coords'][[u,v]] for u,v,d in records],dtype=float)
        if geo.shape!=(len(edges),2,2) or not np.isfinite(geo).all():
            raise ValueError('Жол геометриясы жарамсыз.')
        origins=world['coords'][[u for u,v in edges]]
        reverse=np.linalg.norm(geo[:,1]-origins,axis=1)<np.linalg.norm(geo[:,0]-origins,axis=1)
        geo[reverse]=geo[reverse,::-1]
        x,y=forward.transform(geo[:,:,1],geo[:,:,0],errcheck=True)
        xy=np.stack((x,y),axis=-1)
        lengths=np.linalg.norm(xy[:,1]-xy[:,0],axis=1)
        keep=lengths>0
        xy=xy[keep];edges=[e for e,k in zip(edges,keep) if k]
        if not edges:raise ValueError('Проекциялауға жарамды жол жоқ.')
        centers=xy.mean(axis=1)
        return EdgeIndex(edges,list(linestrings(xy)),cKDTree(centers),float(lengths[keep].max()/2),forward,inverse)
    edges=[];lines=[];centers=[];radii=[]
    for u,v,data in world['graph'].edges(data=True):
        geo=np.asarray(data.get('geometry',world['coords'][[u,v]]),dtype=float)
        if geo.ndim!=2 or geo.shape[1]!=2 or len(geo)<2 or not np.isfinite(geo).all():
            raise ValueError('Жол геометриясы жарамсыз.')
        # Normalize stored geometry to u -> v.
        if np.linalg.norm(geo[-1]-world['coords'][u]) < np.linalg.norm(geo[0]-world['coords'][u]):
            geo=geo[::-1]
        x,y=forward.transform(geo[:,1],geo[:,0],errcheck=True)
        xy=np.column_stack((x,y));line=LineString(xy)
        if line.length<=0:continue
        lo=xy.min(axis=0);hi=xy.max(axis=0)
        edges.append((u,v));lines.append(line);centers.append((lo+hi)/2)
        radii.append(float(np.linalg.norm(hi-lo)/2))
    if not edges:raise ValueError('Проекциялауға жарамды жол жоқ.')
    return EdgeIndex(edges,lines,cKDTree(centers),max(radii),forward,inverse)


def project_to_nearest_edge(index: EdgeIndex, lat: float, lon: float,
                            max_distance_m: float=500., *, reachable=None) -> dict:
    """Exact nearest LineString in the chosen metric CRS, with bounded KD query."""
    if not np.isfinite([lat,lon,max_distance_m]).all() or not (-90<=lat<=90 and -180<=lon<=180) or max_distance_m<0:
        raise ValueError('Координата немесе қашықтық шегі жарамсыз.')
    x,y=index.forward.transform(lon,lat,errcheck=True);point=Point(x,y)
    if reachable is None:
        _,first=index.tree.query([x,y]);bound=index.lines[int(first)].distance(point)
        candidates=index.tree.query_ball_point([x,y],bound+index.max_radius+1e-6)
    else:
        nearby = index.tree.query_ball_point([x,y], max_distance_m + index.max_radius + 1e-6)
        candidates = []
        for i in nearby:
            u, v = index.edges[i]
            line = index.lines[i]
            if line.distance(point) > max_distance_m:
                continue
            # An interior point is reachable from the upstream end only.
            # At the exact downstream endpoint the existing node is reused.
            if u in reachable or (v in reachable and line.length - line.project(point) < .001):
                candidates.append(i)
        if not candidates:
            raise NoRoadInReach(NoRoadInReach.messages['kk'])
    best=min(candidates,key=lambda i:(index.lines[i].distance(point),i))
    line=index.lines[best];along=float(line.project(point));snap=line.interpolate(along)
    distance=float(point.distance(snap))
    if distance>max_distance_m:raise ValueError(f'Жақын көлік жолы {distance:.0f} м жерде (шек {max_distance_m:.0f} м).')
    snapped_lon,snapped_lat=index.inverse.transform(snap.x,snap.y)
    return dict(edge=index.edges[best],index=best,lat=float(snapped_lat),lon=float(snapped_lon),
                distance_m=distance,fraction=along/line.length,along_geometry_m=along,
                offset_vector_m=(snap.x-x,snap.y-y))


def _routing_graph_copy(base, u, v):
    """Copy the adjacency dictionaries modified by the destination split."""
    graph=nx.DiGraph()
    graph.graph.update(base.graph)
    graph._node=base._node.copy()
    graph._succ=base._succ.copy()
    graph._pred=base._pred.copy()
    for node in {u,v}:
        graph._succ[node]=graph._succ[node].copy()
        graph._pred[node]=graph._pred[node].copy()
    return graph


def destination_world(world, point, *, index=None, reachable=None, include_road_graph=True):
    """Return (world, goal id, snap) without modifying the cached base graph.

    Split the chosen directed edge. Split its reverse only when that existing
    reverse edge has identical geometry. No new reverse permission is created.
    Routing-only callers receive a frozen graph sharing unchanged attributes.
    """
    index=index or world.get('edge_index') or build_edge_index(world)
    snap=project_to_nearest_edge(index,*point,reachable=reachable)
    u,v=snap['edge'];line=index.lines[snap['index']]
    if snap['along_geometry_m']<.001:goal=u
    elif line.length-snap['along_geometry_m']<.001:goal=v
    else:goal=None
    if goal is not None:
        snap.update(lat=float(world['coords'][goal,0]),lon=float(world['coords'][goal,1]))
        return world,goal,snap
    base=world['graph']
    share_topology=not include_road_graph and type(base) is nx.DiGraph
    graph=_routing_graph_copy(base,u,v) if share_topology else base.copy()
    goal=len(world['coords'])
    coords=np.vstack([world['coords'],[snap['lat'],snap['lon']]])
    pairs=[(u,v,line,snap['along_geometry_m'])]
    if graph.has_edge(v,u):
        data=graph[v][u];geo=np.asarray(data.get('geometry',world['coords'][[v,u]]))
        x,y=index.forward.transform(geo[:,1],geo[:,0]);reverse=LineString(np.column_stack((x,y)))
        if reverse.equals(line):pairs.append((v,u,LineString(list(line.coords)[::-1]),line.length-snap['along_geometry_m']))
    traffic_sources={}
    for a,b,geometry,along in pairs:
        attrs=dict(graph[a][b]);graph.remove_edge(a,b)
        for start,end,lo,hi in ((a,goal,0,along),(goal,b,along,geometry.length)):
            piece=substring(geometry,lo,hi)
            lon,lat=index.inverse.transform(*np.asarray(piece.coords).T)
            data=dict(attrs);data['length']=attrs['length']*(hi-lo)/geometry.length
            data['geometry']=np.column_stack((lat,lon)).tolist()
            data['free_flow_time_s']=data['length']/(data.get('model_speed_kmh',30.)/3.6)
            graph.add_edge(start,end,**data)
            traffic_sources[start,end]=(a,b)
    # Only split-edge endpoints and the new node have changed actions.
    n=len(coords);k=max(world['dest'].shape[1],graph.out_degree(goal))
    dest=np.repeat(np.arange(n)[:,None],k,axis=1)
    valid=np.zeros((n,k),bool);lengths=np.ones((n,k))
    old_k=world['dest'].shape[1]
    dest[:-1,:old_k]=world['dest'];valid[:-1,:old_k]=world['valid'];lengths[:-1,:old_k]=world['lengths']
    for a in {u,v,goal}:
        dest[a]=a;valid[a]=False;lengths[a]=1
        neighbors=sorted(graph.successors(a),key=lambda b:np.arctan2(coords[b,0]-coords[a,0],coords[b,1]-coords[a,1]))
        for action,b in enumerate(neighbors):
            dest[a,action]=b;valid[a,action]=True;lengths[a,action]=graph[a][b]['length']
    result=dict(world)
    # Keep the city traffic scenario stable when a road is split at the call.
    result['_traffic_parent']=world
    result['_traffic_sources']=traffic_sources
    result['_traffic_rows']=(u,v,goal)
    result.pop('edge_index',None) # base index must never be reused for this split graph
    result.pop('_traffic_cache',None) # the split rows are derived from the parent traffic
    result.pop('_routing_static',None)
    xy=np.column_stack([(coords[:,1]-world['lon0'])*111320*np.cos(np.radians(world['lat0'])),
                        (coords[:,0]-world['lat0'])*111320])
    token=hashlib.sha256(repr((snap['edge'],snap['fraction'])).encode()).hexdigest()[:16]
    if share_topology:
        nx.freeze(graph)
    result.update(graph=graph,road_graph=nx.MultiDiGraph(graph) if include_road_graph else None,coords=coords,xy=xy,
                  dest=dest,valid=valid,lengths=lengths,spatial_index=cKDTree(coords),
                  dataset_version=world.get('dataset_version','fixture')+':snap:'+token,
                  original_node_ids=list(world.get('original_node_ids',range(goal)))+['destination'])
    return result,goal,snap
