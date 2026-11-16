"""Regression tests for stage 3: illegal moves, dead ends and termination."""
import unittest
from unittest.mock import patch
import numpy as np
from algorithms.policies import best_valid_action, future_values, sample_valid_actions
from algorithms.q_learning import q_train, train_q
from services.simulation import execute, simulate_roads
from environments.grid_world import step
from tests.fixtures import road_world

class PolicySafetyTests(unittest.TestCase):
    def test_large_invalid_value_never_wins(self):
        self.assertEqual(best_valid_action(np.array([999.,-5.]),np.array([False,True])),1)
        self.assertIsNone(best_valid_action(np.array([1.,2.]),np.array([False,False])))

    def test_bootstrap_ignores_invalid_terminal_and_dead_ends(self):
        q=np.array([[999.,-4.],[100.,100.],[200.,200.]])
        valid=np.array([[False,True],[True,True],[False,False]])
        np.testing.assert_array_equal(future_values(q,valid,np.array([0,1,2]),1),[-4,0,0])

    def test_exploration_samples_only_allowed_actions(self):
        valid=np.array([[False,True,False],[True,False,True]])
        rng=np.random.default_rng(42)
        for _ in range(100):
            a=sample_valid_actions(valid,rng)
            self.assertTrue(valid[np.arange(2),a].all())

    def test_training_leaves_blocked_and_terminal_actions_unused(self):
        w=road_world()
        q,_=q_train(w,2,(0,1),np.zeros_like(w['lengths']),42,100)
        self.assertEqual(q[0,0],0)
        np.testing.assert_array_equal(q[2],0)
        self.assertTrue(np.isfinite(q).all())

    def test_grid_warm_start_drops_invalid_values(self):
        grid=np.zeros((2,2),dtype=bool)
        q,_=train_q(grid,np.zeros((2,2)),(1,1),42,10,np.full((4,4),999.))
        self.assertEqual(q[0,0],0)  # up, out of bounds
        self.assertEqual(q[0,3],0)  # left, out of bounds
        np.testing.assert_array_equal(q[3],0)

    def test_isolated_state_has_no_action(self):
        grid=np.ones((3,3),dtype=bool);grid[0,0]=grid[2,2]=False
        q,h=train_q(grid,np.zeros((3,3)),(2,2),42,10)
        self.assertTrue(np.isfinite(q).all())
        info={}
        result=execute(grid,grid,np.zeros((3,3)),np.zeros((3,3)),[],q,0,42,diagnostics=info)
        self.assertEqual(info['status'],'no_valid_actions')
        self.assertEqual(len(result[0]),1)

    def test_bad_policy_cycles_then_astar_reaches_goal(self):
        grid=np.zeros((3,3),dtype=bool);traffic=np.zeros((3,3))
        q=np.zeros((9,4));q[:,0]=10  # repeatedly tries to return upwards
        info={}
        path,actions,_,_,_,fallback=execute(grid,grid,traffic,traffic,[],q,0,42,diagnostics=info)
        self.assertTrue(fallback)
        self.assertEqual(info['status'],'reached')
        for pos,action in zip(path,actions):
            self.assertNotEqual(step(grid,pos,action),tuple(pos))

    def test_disabled_dynamics_never_uses_q_policy(self):
        w=road_world();w.update(lat0=51.13,lon0=71.41)
        with patch('algorithms.road_control.best_valid_action',side_effect=AssertionError('Q must not be used')):
            result=simulate_roads(w,0,2,0.,0,42,20,False)
        self.assertEqual(result['status'],'reached')
        self.assertFalse(result['phases'].any())

    def test_step_limit_reported(self):
        w=road_world();w.update(lat0=51.13,lon0=71.41)
        result=simulate_roads(w,0,2,0.,0,42,20,False,max_steps=0)
        self.assertEqual(result['status'],'step_limit')
        np.testing.assert_array_equal(result['path'],[0])

    def test_start_at_goal_is_terminal(self):
        w=road_world();w.update(lat0=51.13,lon0=71.41)
        result=simulate_roads(w,0,0,0.,0,42,20,True)
        self.assertEqual(result['status'],'reached')
        self.assertEqual(result['travel'],0)
        np.testing.assert_array_equal(result['path'],[0])
