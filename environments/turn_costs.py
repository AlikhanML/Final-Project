"""Incoming-edge states for consistent turn-aware A*, Q and elapsed time."""
import heapq
from time import perf_counter
from itertools import count
import math
import numpy as np
import networkx as nx
from environments.travel_time import action_seconds, max_speed_mps
from utils.geo import distance
from domain.models import RoadWorld

DEFAULT_TURNS={'right':4.,'left':15.,'uturn':40.}

class TurnModel:
    """Trip-local immutable costs. xy is east/north in meters.

    A real junction has >=3 distinct adjacent nodes. Degree-two shape vertices
    and virtual destination splits incur no left/right cost. Returning along
    the incoming edge always incurs U-turn cost. OSM restriction relations are
    not inferred from these illustrative penalties.
    """
    def __init__(self, world: RoadWorld, traffic: np.ndarray, penalties: dict[str, float] | None = None, node_waits=None):
        self.world=world;self.penalties=dict(DEFAULT_TURNS if penalties is None else penalties)
        if set(self.penalties)!=set(DEFAULT_TURNS) or any(not math.isfinite(x) or x<0 for x in self.penalties.values()):
            raise ValueError('Turn penalties must be finite nonnegative seconds.')
        graph=world['graph'];self.junctions={u for u in graph if len(set(graph.predecessors(u))|set(graph.successors(u)))>=3}
        self.states=[(None,u) for u in range(len(world['coords']))]+list(graph.edges())
        self.ids={state:i for i,state in enumerate(self.states)}
        self.current=np.array([u for _,u in self.states],dtype=int)
        self.valid=world['valid'][self.current].copy()
        self.next_ids=np.repeat(np.arange(len(self.states))[:,None],self.valid.shape[1],axis=1)
        self.base_seconds=action_seconds(world,traffic)
        if node_waits is not None:self.base_seconds=self.base_seconds+np.asarray(node_waits)[:,None]
        self.costs=self.base_seconds[self.current].copy()
        self.deadline=None
        self.delays=np.zeros_like(self.costs)
        self.speed=max_speed_mps(world)
        # Compute valid state/action pairs in vectorized batches rather than
        # repeated Python geometry operations for every incoming edge.
        edge_ids=np.zeros_like(world['dest'])
        rows,actions=np.nonzero(world['valid'])
        edges=zip(rows.tolist(),world['dest'][rows,actions].tolist())
        edge_ids[rows,actions]=np.fromiter((self.ids[edge] for edge in edges),dtype=int,count=len(rows))
        self.next_ids=np.where(self.valid,edge_ids[self.current],self.next_ids)
        previous=np.array([-1 if p is None else p for p,_ in self.states])
        junction=np.zeros(len(world['coords']),bool);junction[list(self.junctions)]=True
        for action in range(self.valid.shape[1]):
            ids=np.flatnonzero(self.valid[:,action] & (previous>=0))
            u=self.current[ids];p=previous[ids];v=world['dest'][u,action]
            a=world['xy'][u]-world['xy'][p];b=world['xy'][v]-world['xy'][u]
            angle=np.degrees(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],np.sum(a*b,axis=1)))
            usable=junction[u] & (np.linalg.norm(a,axis=1)>=1e-9) & (np.linalg.norm(b,axis=1)>=1e-9)
            delay=np.where(usable & (np.abs(angle)>20),
                           np.where(np.abs(angle)>=150,self.penalties['uturn'],
                                    np.where(angle>0,self.penalties['left'],self.penalties['right'])),0.)
            delay[p==v]=self.penalties['uturn']
            self.delays[ids,action]=delay
        self.costs+=self.delays

    def penalty(self, previous: int | None, u: int, v: int) -> tuple[float, str]:
        if previous is None or not self.world['graph'].has_edge(previous,u):return 0.,'straight'
        if previous==v:return self.penalties['uturn'],'uturn'
        if u not in self.junctions:return 0.,'straight'
        # The importer retains every OSM shape vertex, so each action is one
        # straight geometry segment; use the adjoining incoming/outgoing vectors.
        xy=self.world['xy'];a=xy[u]-xy[previous];b=xy[v]-xy[u]
        if np.linalg.norm(a)<1e-9 or np.linalg.norm(b)<1e-9:return 0.,'straight'
        angle=math.degrees(math.atan2(a[0]*b[1]-a[1]*b[0],float(a@b)))
        kind='straight' if abs(angle)<=20 else 'uturn' if abs(angle)>=150 else 'left' if angle>0 else 'right'
        return self.penalties.get(kind,0.),kind

    def state_id(self, previous: int | None, current: int) -> int:
        return self.ids.get((previous,current),self.ids[None,current])

    def allowed(self,blocked=None,goal=None):
        valid=self.valid.copy()
        if blocked is not None:
            u,v=blocked
            valid[(self.current==u)[:,None] & (self.world['dest'][self.current]==v)]=False
        if goal is not None:valid[self.current==goal]=False
        return valid

    def route(self, start: int, goal: int, blocked: tuple[int, int] | None = None, previous: int | None = None) -> list[int]:
        """A* over (incoming node, current node), with admissible time heuristic."""
        valid=self.valid;initial=self.state_id(previous,start)
        serial=count();costs={initial:0.};parents={};heap=[(0.,next(serial),initial,0.)]
        heuristic={};expansions=0
        while heap:
            if expansions%256==0 and self.deadline is not None and perf_counter()>=self.deadline:
                raise TimeoutError('Есептеу уақыт шегіне жетті. GPS шуын немесе Q-learning циклдерін азайтып қайталаңыз.')
            expansions+=1
            _,_,sid,elapsed=heapq.heappop(heap)
            if elapsed!=costs[sid]:continue
            u=int(self.current[sid])
            if u==goal:
                path=[u]
                while sid!=initial:sid=parents[sid];path.append(int(self.current[sid]))
                return path[::-1]
            for a in valid[sid].nonzero()[0]:
                nxt=int(self.next_ids[sid,a]);v=int(self.current[nxt])
                if blocked is not None and (u,v)==blocked:continue
                candidate=elapsed+self.costs[sid,a]
                if candidate<costs.get(nxt,float('inf')):
                    costs[nxt]=candidate;parents[nxt]=sid
                    if v not in heuristic:heuristic[v]=distance(self.world['coords'][v],self.world['coords'][goal])/self.speed
                    heapq.heappush(heap,(candidate+heuristic[v],next(serial),nxt,candidate))
        raise nx.NetworkXNoPath('Бұрылыс ескерілген маршрут жоқ.')

    def route_time(self, path: list[int], previous: int | None = None) -> float:
        total=0.
        for u,v in zip(path,path[1:]):
            a=int(np.flatnonzero((self.world['dest'][u]==v)&self.world['valid'][u])[0])
            total+=self.costs[self.state_id(previous,u),a];previous=u
        return float(total)
