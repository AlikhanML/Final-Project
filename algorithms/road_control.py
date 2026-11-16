"""MAP controller and physical heading commands; never receives true position."""
from dataclasses import dataclass
import numpy as np
import networkx as nx
from algorithms.astar import astar_roads
from algorithms.policies import best_valid_action
from environments.road_world import transition_table

@dataclass(frozen=True)
class Decision:
    heading: float | None
    reason: str


class CommandModel:
    """Precompute legal bearings once per trip/closure, shared by HMM and physics."""
    def __init__(self, world, blocked=None, reachable=None):
        self.dest, self.valid = transition_table(world, blocked)
        if reachable is not None:
            self.valid &= reachable[self.dest]
        delta = world['xy'][self.dest] - world['xy'][:, None, :]
        angles = np.arctan2(delta[..., 1], delta[..., 0])
        self.cos, self.sin = np.cos(angles), np.sin(angles)
        self.nodes = np.arange(len(self.dest))

    def transition(self, heading, nodes=None):
        subset=nodes is not None
        nodes=self.nodes if nodes is None else nodes
        if heading is None:
            return nodes, np.full(len(nodes), -1, dtype=int)
        cos,sin,valid=(self.cos[nodes],self.sin[nodes],self.valid[nodes]) if subset else (self.cos,self.sin,self.valid)
        # Cosine similarity avoids per-step array trigonometry and geometry copies.
        score = cos*np.cos(heading) + sin*np.sin(heading)
        score[~valid] = -np.inf
        actions = np.argmax(score, axis=1)
        matched = score[np.arange(len(nodes)) if subset else nodes, actions] >= np.cos(np.pi/6)-1e-14
        return (np.where(matched, self.dest[nodes, actions], nodes),
                np.where(matched, actions, -1))


def command_transitions(world, heading: float | None, blocked=None, *, reachable=None):
    """Compatibility entry point; simulations reuse CommandModel instead."""
    return CommandModel(world, blocked, reachable).transition(heading)


class RoutePlan:
    """Trip-local route suffix cache; receives estimated nodes, never truth.

    World, goal and traffic are fixed for the lifetime of this object. A new
    trip must create a new instance. Closure changes or leaving the remaining
    route invalidate the plan. Waiting at the same node keeps it intact.
    """
    def __init__(self, world, goal, traffic, turn_model=None, *, initial_path=None):
        self.world, self.goal, self.traffic = world, goal, traffic
        self.turn_model=turn_model
        self.initial_previous=None
        self.path = [] if initial_path is None else initial_path
        self.positions = {node:i for i,node in enumerate(self.path)}
        self.cursor = 0
        self.blocked = None
        self.searches = 0

    def next_node(self, estimated_node, blocked, previous=None):
        index = self.positions.get(estimated_node, -1)
        expected=self.path[index-1] if index>0 else self.initial_previous
        wrong_entry=self.turn_model is not None and previous!=expected
        if not self.path or blocked != self.blocked or index < self.cursor or wrong_entry:
            self.searches += 1
            # Invalidate first: failed search must not leave a usable old plan.
            self.path = []; self.positions = {}; self.cursor = 0
            self.initial_previous=previous
            self.path = (self.turn_model.route(estimated_node,self.goal,blocked,previous)
                         if self.turn_model is not None else
                         astar_roads(self.world, estimated_node, self.goal,blocked,self.traffic,cost='time'))
            self.positions = {node:i for i,node in enumerate(self.path)}
            self.blocked = blocked
            index = 0
        self.cursor = index
        return self.path[index+1]


def choose_command(world, belief, goal, q, traffic, blocked=None, *, use_q=False,
                   min_confidence=.55, planner=None, previous=None, turn_model=None) -> Decision:
    """Certainty-equivalent MAP policy, not a full belief-space POMDP solver."""
    state = int(np.argmax(belief))
    if belief[state] < min_confidence:
        return Decision(None, 'uncertain')
    if state == goal:
        return Decision(None, 'estimated_arrival' if belief[state]>=.95 else 'uncertain')
    table=world['dest'][state]
    valid=world['valid'][state].copy()
    if blocked is not None and state==blocked[0]:valid[table==blocked[1]]=False
    if not valid.any():
        return Decision(None, 'no_valid_actions')
    if use_q:
        row=turn_model.state_id(previous,state) if turn_model is not None else state
        action = best_valid_action(q[row], valid)
    else:
        try:
            nxt = (planner.next_node(state, blocked, previous) if planner is not None else
                   (turn_model.route(state,goal,blocked,previous) if turn_model is not None else
                    astar_roads(world,state,goal,blocked,traffic,cost='time'))[1])
        except nx.NetworkXNoPath:
            return Decision(None, 'no_route')
        action = int(np.flatnonzero((table == nxt) & valid)[0])
    if action is None:
        return Decision(None, 'no_valid_actions')
    delta = world['xy'][table[action]] - world['xy'][state]
    return Decision(float(np.arctan2(delta[1], delta[0])), 'q_learning' if use_q else 'astar')
