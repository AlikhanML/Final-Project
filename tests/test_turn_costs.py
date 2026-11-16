"""Turn-aware optimality, learning and simulation regression checks."""
import unittest
import networkx as nx
import numpy as np
from environments.turn_costs import TurnModel
from algorithms.q_learning import q_train_turns
from services.simulation import simulate_roads
from utils.geo import distance


def junction_world():
    xy=np.array([[-100,0],[0,0],[0,100],[100,0],[0,-100]],float)
    coords=np.column_stack([51.13+xy[:,1]/111320,71.41+xy[:,0]/(111320*np.cos(np.radians(51.13)))])
    g=nx.DiGraph()
    for v in (0,2,3,4):
        for a,b in ((1,v),(v,1)):
            g.add_edge(a,b,length=distance(coords[a],coords[b]),model_speed_kmh=36.)
    dest=np.repeat(np.arange(5)[:,None],4,axis=1);valid=np.zeros((5,4),bool);lengths=np.ones((5,4))
    for u in range(5):
        for a,v in enumerate(g.successors(u)):
            dest[u,a]=v;valid[u,a]=True;lengths[u,a]=g[u][v]['length']
    return dict(graph=g,coords=coords,xy=xy,dest=dest,valid=valid,lengths=lengths,lat0=51.13,lon0=71.41)


class TurnTests(unittest.TestCase):
    def model(self):
        w=junction_world()
        return TurnModel(w,np.zeros_like(w['lengths']))

    def test_signed_turns(self):
        m=self.model()
        for target,expected in ((2,(15.,'left')),(4,(4.,'right')),(3,(0.,'straight')),(0,(40.,'uturn'))):
            self.assertEqual(m.penalty(0,1,target),expected)
        self.assertEqual(m.penalty(None,1,2),(0.,'straight'))

    def test_shape_bend_is_not_intersection(self):
        m=self.model();m.junctions.clear()
        self.assertEqual(m.penalty(0,1,2),(0.,'straight'))
        self.assertEqual(m.penalty(0,1,0),(40.,'uturn'))

    def test_astar_matches_expanded_dijkstra(self):
        m=self.model();expanded=nx.DiGraph();expanded.add_nodes_from(range(len(m.states)))
        for sid in range(len(m.states)):
            for a in np.flatnonzero(m.valid[sid]):
                expanded.add_edge(sid,int(m.next_ids[sid,a]),weight=m.costs[sid,a])
        for sid,(previous,start) in enumerate(m.states):
            lengths=nx.single_source_dijkstra_path_length(expanded,sid)
            for goal in range(5):
                expected=min(d for state,d in lengths.items() if m.current[state]==goal)
                path=m.route(start,goal,previous=previous)
                self.assertAlmostEqual(m.route_time(path,previous),expected)

    def test_incoming_direction_changes_q_reward(self):
        m=self.model();goal=2
        m.valid[:]=False
        action=int(np.flatnonzero(m.world['dest'][1]==goal)[0])
        m.valid[m.current==1,action]=True
        q,_=q_train_turns(m,goal,None,42,1)
        for previous in (0,3):
            sid=m.state_id(previous,1)
            self.assertAlmostEqual(q[sid,action],-m.costs[sid,action]*.6/1.01)
        self.assertNotEqual(q[m.state_id(0,1),action],q[m.state_id(3,1),action])
        self.assertTrue(np.all(q[m.current==goal]==0))

    def test_simulation_eta_includes_turn_pause(self):
        d=simulate_roads(junction_world(),0,2,0,0,42,10,False)
        self.assertEqual(d['status'],'reached')
        self.assertEqual(d['turn_total_s'],15.)
        self.assertAlmostEqual(d['elapsed_s'],d['eta_plan_s'])
        self.assertAlmostEqual(sum(d['segment_times_s']),d['elapsed_s'])
        self.assertEqual(len(d['turn_delays_s']),len(d['path'])-1)

    def test_closed_direction_has_no_transition(self):
        m=self.model();valid=m.allowed((1,2))
        self.assertFalse(np.any(valid[(m.current==1)[:,None] & (m.world['dest'][m.current]==2)]))
        with self.assertRaises(nx.NetworkXNoPath):m.route(0,2,(1,2))

    def test_invalid_penalties(self):
        w=junction_world()
        for value in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):TurnModel(w,np.zeros_like(w['lengths']),dict(left=value,right=4,uturn=40))

    def test_actuator_excludes_unreachable_branches(self):
        from algorithms.road_control import command_transitions
        w=junction_world();reachable=np.ones(5,bool);reachable[3]=False
        destinations,actions=command_transitions(w,0.,reachable=reachable)
        self.assertEqual(destinations[1],1)
        self.assertEqual(actions[1],-1)

    def test_plan_reuses_correct_entry_and_replans_wrong_entry(self):
        from algorithms.road_control import RoutePlan
        m=self.model();plan=RoutePlan(m.world,2,np.zeros_like(m.world['lengths']),m)
        self.assertEqual(plan.next_node(1,None,0),2)
        plan.next_node(1,None,0);self.assertEqual(plan.searches,1)
        plan.next_node(1,None,3);self.assertEqual(plan.searches,2)
