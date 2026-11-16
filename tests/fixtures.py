"""Small synthetic road graph: no downloaded city data or network required."""
import networkx as nx
import numpy as np
from utils.geo import distance


def road_world():
    coords = np.array([[51.13,71.41],[51.13,71.411],
                       [51.131,71.411],[51.131,71.41]])
    graph = nx.DiGraph()
    for u, v in [(0,1),(1,2),(2,3),(3,0)]:
        for a, b in [(u,v),(v,u)]:
            graph.add_edge(a,b,length=distance(coords[a],coords[b]))
    dest=np.array([[1,3],[0,2],[1,3],[0,2]])
    valid=np.ones_like(dest,dtype=bool)
    lengths=np.array([[graph[u][v]['length'] for v in row]
                      for u,row in enumerate(dest)])
    xy=np.column_stack([(coords[:,1]-71.41)*111320*np.cos(np.radians(51.13)),
                        (coords[:,0]-51.13)*111320])
    return dict(graph=graph,coords=coords,dest=dest,valid=valid,
                lengths=lengths,xy=xy)
