"""Optimization invariants, bounded training and explicit deadline behavior."""
import unittest
from unittest.mock import patch
import numpy as np
from algorithms.road_control import CommandModel
from environments.road_world import transition_table
from environments.turn_costs import TurnModel
from algorithms.q_learning import q_train_turns
from services.simulation import simulate_roads
from tests.test_turn_costs import junction_world

class FastModeTests(unittest.TestCase):
    def test_precomputed_commands_match_reference(self):
        w=junction_world();reachable=np.ones(5,bool);reachable[4]=False
        for blocked in (None,(1,2)):
            table,valid=transition_table(w,blocked);valid &= reachable[table]
            delta=w['xy'][table]-w['xy'][:,None,:]
            angles=np.arctan2(delta[...,1],delta[...,0]);model=CommandModel(w,blocked,reachable)
            for heading in np.linspace(-np.pi,np.pi,73):
                error=np.abs(np.arctan2(np.sin(angles-heading),np.cos(angles-heading)))
                error[~valid]=np.inf;actions=error.argmin(axis=1)
                match=error[np.arange(5),actions]<=np.pi/6+1e-14
                nxt=np.where(match,table[np.arange(5),actions],np.arange(5))
                actual,_=model.transition(heading)
                np.testing.assert_array_equal(actual,nxt)

    def test_vectorized_turn_costs_match_scalar(self):
        w=junction_world();m=TurnModel(w,np.zeros_like(w['lengths']))
        for sid,(previous,u) in enumerate(m.states):
            for action in np.flatnonzero(m.valid[sid]):
                v=w['dest'][u,action]
                self.assertAlmostEqual(m.delays[sid,action],m.penalty(previous,u,v)[0])

    def test_q_training_respects_update_budget(self):
        w=junction_world();m=TurnModel(w,np.zeros_like(w['lengths']))
        q,_=q_train_turns(m,2,None,42,4000,max_updates=3)
        self.assertEqual(np.count_nonzero(q),3)

    def test_no_unused_q_training_for_static_trip(self):
        with patch('services.simulation.q_train_turns',side_effect=AssertionError('unused training')):
            d=simulate_roads(junction_world(),0,2,0,0,42,4000,False)
        self.assertEqual(d['status'],'reached');self.assertEqual(d['history'],[])

    def test_expired_route_deadline_is_explicit(self):
        w=junction_world();m=TurnModel(w,np.zeros_like(w['lengths']));m.deadline=0
        with self.assertRaises(TimeoutError):m.route(0,2)
