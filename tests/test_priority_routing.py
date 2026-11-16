import unittest
from unittest.mock import patch
import numpy as np
from services.simulation import simulate_roads
from services.edge_events import handle_edge_event
from tests.test_turn_costs import junction_world

class PriorityRoutingTests(unittest.TestCase):
    def simulate(self, priority, density):
        return simulate_roads(junction_world(),0,2,density,0,42,10,False,
                              priority=priority,quick_recovery=True,max_steps=100)
    def test_urgent_reduces_eta_and_actual_timeline(self):
        normal=self.simulate('normal',1.)
        urgent=self.simulate('urgent',1.)
        np.testing.assert_array_equal(normal['ambient_traffic'],urgent['ambient_traffic'])
        np.testing.assert_allclose(urgent['traffic'],normal['traffic']*.35)
        self.assertLess(urgent['eta_plan_s'],normal['eta_plan_s'])
        self.assertEqual(normal['status'],'reached')
        self.assertEqual(urgent['status'],'reached')
        self.assertLess(urgent['elapsed_s'],normal['elapsed_s'])
        self.assertAlmostEqual(urgent['timestamps_s'][-1],urgent['elapsed_s'])
    def test_clear_road_has_no_fabricated_saving(self):
        normal=self.simulate('normal',0.)
        urgent=self.simulate('urgent',0.)
        self.assertAlmostEqual(normal['eta_plan_s'],urgent['eta_plan_s'])
        self.assertEqual(normal['turn_penalties'],urgent['turn_penalties'])
    def test_switch_recomputes_existing_route(self):
        result={'priority':'urgent'}
        state={'nav_B':(51,71),'nav_priority':'normal','nav_result':{},'nav_hospital':{'node':0},
               'nav_goal':2,'nav_route_world':{},'nav_config':(.2,0,42,10,False)}
        with patch('builtins.print'):
            calls=[]
            def simulate(*args,**kwargs):calls.append(kwargs);return result
            event={'id':'priority-1','type':'priority','priority':'urgent'}
            handle_edge_event(state,event,{},simulate)
            handle_edge_event(state,event,{},simulate)
        self.assertEqual(calls,[{'priority':'urgent'}])
        self.assertIs(state['nav_result'],result)
        self.assertEqual(state['nav_trip_version'],1)

    def test_eta_breakdown_matches_planner_and_savings(self):
        for priority in ('normal','urgent'):
            d=self.simulate(priority,1.)
            parts=d['eta_breakdown']
            self.assertAlmostEqual(d['eta_plan_s'],sum(parts[k] for k in ('free_flow_s','traffic_delay_s','turn_delay_s')))
            self.assertGreater(parts['traffic_delay_s'],0)
            if priority=='urgent':self.assertAlmostEqual(parts['same_path_saving_s'],parts['traffic_delay_s']/.35*.65)
            else:self.assertEqual(parts['same_path_saving_s'],0.)
        d=self.simulate('urgent',0.)['eta_breakdown']
        self.assertEqual(d['traffic_delay_s'],0.)
        self.assertEqual(d['same_path_saving_s'],0.)

    def test_same_path_comparison_keeps_free_flow_and_turns(self):
        for priority in ('normal','urgent'):
            d=self.simulate(priority,1.)
            parts=d['eta_breakdown']
            self.assertAlmostEqual(parts[priority+'_same_path_s'],d['eta_plan_s'])
            fixed=parts['free_flow_s']+parts['turn_delay_s']
            self.assertAlmostEqual(parts['urgent_same_path_s']-fixed,
                                   .35*(parts['normal_same_path_s']-fixed))

    def test_production_cache_separates_modes_and_returns_to_normal(self):
        from ui.cache import simulate_projected, _simulate_projected
        w=junction_world();w['dataset_version']='priority-regression-junction-v1'
        _simulate_projected.clear()
        self.addCleanup(_simulate_projected.clear)
        results=[simulate_projected(w,0,2,.7,0,0,10,False,priority=p)
                 for p in ('normal','urgent','normal')]
        normal,urgent,again=results
        self.assertGreater(normal['eta_plan_s'],urgent['eta_plan_s'])
        self.assertGreater(normal['elapsed_s'],urgent['elapsed_s'])
        self.assertEqual(normal['eta_plan_s'],again['eta_plan_s'])
        self.assertEqual(normal['priority'],again['priority'])
        np.testing.assert_array_equal(normal['ambient_traffic'],urgent['ambient_traffic'])
