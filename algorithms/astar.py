"""Shortest path algorithms independent of UI and storage."""
import heapq
from domain.models import RoadWorld
import numpy as np
import networkx as nx
from utils.geo import distance
from environments.travel_time import edge_seconds, max_speed_mps
from environments.grid_world import step, manhattan

def astar(grid, start, goal, traffic=None):
    queue = [(manhattan(start, goal), 0.0, start)]
    costs, parent = {start: 0.0}, {}
    while queue:
        _, cost, current = heapq.heappop(queue)
        if cost > costs[current]:
            continue
        if current == goal:
            path = [current]
            while current in parent:
                current = parent[current]
                path.append(current)
            return path[::-1]
        for action in range(4):
            nxt = step(grid, current, action)
            if nxt == current:
                continue
            new_cost = cost + 1 + (0 if traffic is None else traffic[nxt])
            if new_cost < costs.get(nxt, float('inf')):
                costs[nxt], parent[nxt] = new_cost, current
                heapq.heappush(queue, (new_cost + manhattan(nxt, goal), new_cost, nxt))
    return []


def astar_roads(world: RoadWorld, start: int, goal: int, blocked: tuple[int, int] | None = None, traffic=None, *, cost: str = "distance") -> list[int]:
    if cost not in ('distance','time'): raise ValueError('Unknown route cost.')
    speed=max_speed_mps(world) if cost=='time' else 1.0
    graph=world['graph']
    if blocked is not None:
        graph=nx.subgraph_view(graph,filter_edge=lambda u,v:(u,v)!=blocked)
    def weight(u,v,attr):
        a=int(np.flatnonzero((world['dest'][u]==v)&world['valid'][u])[0])
        slowdown=0.0 if traffic is None else traffic[u,a]
        return edge_seconds(attr,slowdown) if cost=='time' else attr['length']*(1+slowdown)
    return nx.astar_path(graph,start,goal,
                         heuristic=lambda u,v: distance(world['coords'][u],world['coords'][v])/speed,weight=weight)

