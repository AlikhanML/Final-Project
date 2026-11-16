"""Behavior contracts to preserve when extracting algorithms into modules."""
import unittest
import numpy as np
import networkx as nx
from algorithms.astar import astar_roads
from environments.road_world import transition_table
from algorithms.hmm import filter_roads
from algorithms.q_learning import q_train
from tests.fixtures import road_world


class BaselineContracts(unittest.TestCase):
    def setUp(self):
        self.world = road_world()

    def test_astar_matches_dijkstra_for_all_pairs(self):
        g=self.world['graph']
        for start in g:
            for goal in g:
                path=astar_roads(self.world,start,goal)
                actual=sum(g[u][v]['length'] for u,v in zip(path,path[1:]))
                expected=nx.dijkstra_path_length(g,start,goal,weight='length')
                self.assertAlmostEqual(actual,expected)

    def test_start_equals_goal(self):
        self.assertEqual(astar_roads(self.world,1,1),[1])

    def test_blockage_detour_and_world_unchanged(self):
        original=self.world['dest'].copy()
        path=astar_roads(self.world,0,1,blocked=(0,1))
        self.assertNotIn((0,1),list(zip(path,path[1:])))
        self.assertEqual(path,[0,3,2,1])
        np.testing.assert_array_equal(original,self.world['dest'])
        self.assertTrue(self.world['graph'].has_edge(0,1))

    def test_no_route_is_explicit(self):
        self.world['graph'].remove_edges_from([(0,1),(0,3)])
        with self.assertRaises(nx.NetworkXNoPath):
            astar_roads(self.world,0,2)

    def test_blocked_transition_does_not_mutate_world(self):
        table,valid=transition_table(self.world,(0,1))
        self.assertEqual(table[0,0],0)
        self.assertFalse(valid[0,0])
        self.assertEqual(self.world['dest'][0,0],1)
        self.assertTrue(self.world['valid'][0,0])

    def test_hmm_exact_observations(self):
        truth=np.array([0,1,2])
        estimates,confidence=filter_roads(self.world,self.world['xy'][truth],
            [0,1],[self.world['dest']]*2,0)
        np.testing.assert_array_equal(estimates,truth)
        np.testing.assert_allclose(confidence,1)

    def test_hmm_noisy_observations_remain_finite(self):
        observations=self.world['xy'][[0,1,2]]+np.array([[4,-3],[8,2],[-6,4]])
        estimates,confidence=filter_roads(self.world,observations,
            [0,1],[self.world['dest']]*2,20)
        self.assertTrue(np.isfinite(confidence).all())
        self.assertTrue(((confidence>=0)&(confidence<=1)).all())
        self.assertTrue(((estimates>=0)&(estimates<4)).all())

    def test_q_training_is_seeded_and_does_not_mutate_world(self):
        traffic=np.zeros_like(self.world['lengths'])
        original=self.world['dest'].copy()
        q1,h1=q_train(self.world,2,None,traffic,42,40)
        q2,h2=q_train(self.world,2,None,traffic,42,40)
        np.testing.assert_array_equal(q1,q2)
        self.assertEqual(h1,h2)
        np.testing.assert_array_equal(q1[2],0)
        np.testing.assert_array_equal(self.world['dest'],original)
