"""Hospital selection based on directed road distance."""
from heapq import heappop, heappush
from itertools import count

import networkx as nx
from domain.models import RoadWorld, HospitalSelection
from utils.geo import distance
from environments.road_world import nearest
from services.hospital_allowlist import approved_hospital

class NoHospitalPath(ValueError):
    """Approved hospitals exist, but none can reach this road segment."""


def hospital_starts(world):
    hospitals=[]
    for record in world['source'].get('hospitals', []):
        approved=approved_hospital(record)
        if approved is not None:hospitals.append({**record,**approved})
    if not hospitals:
        raise ValueError('Рұқсат етілген №1, №2, №3 қалалық ауруханалар базадан табылмады. Қала базасын жаңартыңыз. Басқа мекеме старт ретінде таңдалмайды.')
    for hospital in hospitals:
        point = (float(hospital['lat']), float(hospital['lon']))
        node = nearest(world, point)
        if distance(point, world['coords'][node]) <= 500:
            yield hospital, node


def reachable_hospital_nodes(world):
    starts = [node for _, node in hospital_starts(world)]
    if not starts:
        raise ValueError('Ауруханаларға жақын көлік жолы базадан табылмады.')
    return set(nx.multi_source_dijkstra_path_length(world['graph'], starts, weight=None))


def select_hospital(world: RoadWorld, destination: tuple[float, float], *, goal=None, hospital_world=None) -> HospitalSelection:
    """Minimum directed road distance hospital -> call; unreachable sites excluded."""
    goal = nearest(world, destination) if goal is None else goal
    hospital_world = world if hospital_world is None else hospital_world
    hospitals = {}
    for hospital, node in hospital_starts(hospital_world):
        hospitals.setdefault(node, []).append(hospital)
    candidates = []
    if hospitals:
        # Explore incoming roads until the first hospital distance is settled.
        # Finish that distance level to preserve ID-based ties.
        incoming = world['graph'].pred
        serial = count()
        heap = [(0., next(serial), goal)]
        distances = {goal: 0.}
        best = float('inf')
        while heap:
            meters, _, node = heappop(heap)
            if meters > best:
                break
            if meters != distances[node]:
                continue
            if node in hospitals:
                best = meters
                candidates.extend((str(h.get('id', '')), h, node) for h in hospitals[node])
            for upstream, edge in incoming[node].items():
                length = edge.get('length', 1)
                if length is None:
                    continue
                candidate = meters + length
                if candidate <= best and candidate < distances.get(upstream, float('inf')):
                    distances[upstream] = candidate
                    heappush(heap, (candidate, next(serial), upstream))
    if not candidates:
        raise NoHospitalPath('№1, №2, №3 ауруханалардың ішінен шақыртуға жолы бары табылмады. Қала базасын жаңартыңыз.')
    _, hospital, node = min(candidates, key=lambda x: x[0])
    return {**hospital, 'road_m': float(best), 'node': int(node)}

