"""Seconds-based road costs; traffic is a synthetic non-negative slowdown."""
import math
import numpy as np


def travel_time_s(length_m: float, speed_kmh: float, slowdown: float = 0.0) -> float:
    values=(length_m,speed_kmh,slowdown)
    if not all(math.isfinite(v) for v in values) or length_m<0 or speed_kmh<=0 or slowdown<0:
        raise ValueError('Invalid road length, speed or traffic slowdown.')
    return length_m/(speed_kmh/3.6)*(1.0+slowdown)


def edge_seconds(edge, slowdown=0.0):
    # 30 km/h is an explicit fixture/legacy model default, never a legal claim.
    return travel_time_s(float(edge['length']),float(edge.get('model_speed_kmh',30.)),float(slowdown))


def _free_flow_seconds(world):
    result=np.zeros_like(world['lengths'],dtype=float)
    rows,actions=np.nonzero(world['valid'])
    graph=world['graph']
    edges=[graph[u][v] for u,v in zip(rows.tolist(),world['dest'][rows,actions].tolist())]
    lengths=np.fromiter((float(edge['length']) for edge in edges),dtype=float,count=len(edges))
    speeds=np.fromiter((float(edge.get('model_speed_kmh',30.)) for edge in edges),dtype=float,count=len(edges))
    if (not all(np.isfinite(values).all() for values in (lengths,speeds))
            or (lengths<0).any() or (speeds<=0).any()):
        raise ValueError('Invalid road length, speed or traffic slowdown.')
    result[rows,actions]=lengths/(speeds/3.6)
    return result


def prepare_free_flow(world):
    """Reuse free-flow costs only in a session with a stable road snapshot."""
    cache=world.get('_routing_static')
    if cache is None:
        return _free_flow_seconds(world)
    if 'free_flow' not in cache:
        cache['free_flow']=_free_flow_seconds(world)
    return cache['free_flow']


def action_seconds(world, traffic):
    parent=world.get('_traffic_parent')
    if parent is not None and '_routing_static' in parent:
        cached=prepare_free_flow(parent)
        free_flow=np.zeros_like(world['lengths'],dtype=float)
        rows,columns=cached.shape
        free_flow[:rows,:columns]=cached
        for u in world['_traffic_rows']:
            free_flow[u]=0.
            for action in np.flatnonzero(world['valid'][u]):
                free_flow[u,action]=edge_seconds(world['graph'][u][world['dest'][u,action]])
    else:
        free_flow=prepare_free_flow(world)
    valid=world['valid']
    slowdown=np.asarray(traffic[valid],dtype=float)
    if not np.isfinite(slowdown).all() or (slowdown<0).any():
        raise ValueError('Invalid road length, speed or traffic slowdown.')
    result=np.zeros_like(free_flow)
    result[valid]=free_flow[valid]*(1.+slowdown)
    return result


def max_speed_mps(world):
    return max(float(e.get('model_speed_kmh',30.))/3.6 for _,_,e in world['graph'].edges(data=True))


def route_seconds(world,path,traffic=None):
    total=0.0
    for u,v in zip(path,path[1:]):
        a=int(np.flatnonzero((world['dest'][u]==v)&world['valid'][u])[0])
        total+=edge_seconds(world['graph'][u][v],0 if traffic is None else traffic[u,a])
    return total
