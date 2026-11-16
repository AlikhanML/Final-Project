"""Route reuse, invalidation and separation between trips."""
import unittest
import numpy as np
import networkx as nx
from algorithms.road_control import RoutePlan, choose_command
from tests.fixtures import road_world

class RoutePlanTests(unittest.TestCase):
    def setUp(self):
        self.w=road_world();self.traffic=np.zeros_like(self.w['lengths'])
        self.plan=RoutePlan(self.w,2,self.traffic)
    def test_wait_and_progress_reuse_plan(self):
        nxt=self.plan.next_node(0,None)
        self.assertEqual(self.plan.next_node(0,None),nxt)
        self.assertEqual(self.plan.next_node(nxt,None),2)
        self.assertEqual(self.plan.searches,1)
    def test_off_route_replans(self):
        self.plan.next_node(0,None)
        outside=next(i for i in range(4) if i not in self.plan.path)
        self.plan.next_node(outside,None)
        self.assertEqual(self.plan.searches,2)
    def test_return_to_passed_node_replans(self):
        nxt=self.plan.next_node(0,None)
        self.plan.next_node(nxt,None)
        self.plan.next_node(0,None)
        self.assertEqual(self.plan.searches,2)
    def test_closure_invalidates_and_is_avoided(self):
        nxt=self.plan.next_node(0,None)
        alternative=self.plan.next_node(0,(0,nxt))
        self.assertNotEqual(alternative,nxt)
        self.assertEqual(self.plan.searches,2)
    def test_no_route_clears_old_path(self):
        self.plan.next_node(0,None)
        self.w['graph'].remove_edges_from(list(self.w['graph'].out_edges(0)))
        with self.assertRaises(nx.NetworkXNoPath):self.plan.next_node(0,(0,1))
        self.assertEqual(self.plan.path,[])
    def test_new_trip_has_independent_cache(self):
        self.plan.next_node(0,None)
        other=RoutePlan(self.w,1,self.traffic.copy())
        self.assertEqual(other.next_node(0,None),1)
        self.assertEqual(other.searches,1)
        self.assertEqual(self.plan.goal,2)
    def test_low_confidence_does_not_search(self):
        d=choose_command(self.w,np.ones(4)/4,2,np.zeros_like(self.traffic),
                         self.traffic,planner=self.plan)
        self.assertEqual(d.reason,'uncertain');self.assertEqual(self.plan.searches,0)
