import unittest
import numpy as np
from tests.test_turn_costs import junction_world
from environments.traffic_signals import signal_waits
from services.simulation import simulate_roads

class SignalTests(unittest.TestCase):
    def world(self):
        w=junction_world()
        for u,v in w['graph'].edges:w['graph'][u][v]['highway']='primary'
        return w
    def test_main_junction_and_repeatable(self):
        w=self.world();seed=next(s for s in range(100) if signal_waits(w,s)[1]>0)
        a=signal_waits(w,seed)
        np.testing.assert_array_equal(a,signal_waits(w,seed))
        self.assertEqual(np.flatnonzero(a).tolist(),[1])
        self.assertTrue(10<=a[1]<=30)
        for u,v in w['graph'].edges:w['graph'][u][v]['highway']='service'
        self.assertFalse(signal_waits(w,seed).any())
    def test_wait_and_eta(self):
        w=self.world();seed=next(s for s in range(100) if signal_waits(w,s)[1]>0)
        results={p:simulate_roads(w,0,3,0,0,seed,10,False,priority=p,max_steps=100) for p in ('normal','urgent')}
        n,u=results['normal'],results['urgent']
        for p,d in results.items():
            self.assertEqual(d['status'],'reached')
            parts=d['eta_breakdown']
            self.assertAlmostEqual(d['eta_plan_s'],sum(parts[k] for k in ('free_flow_s','traffic_delay_s','turn_delay_s','signal_delay_s')))
            self.assertAlmostEqual(d['eta_plan_s'],d['elapsed_s'])
            self.assertAlmostEqual(parts[p+'_same_path_s'],d['eta_plan_s'])
            self.assertEqual(len(d['stop_delays_s']),len(d['path'])-1)
            self.assertTrue(np.all(np.diff(d['timestamps_s'])>0))
        self.assertGreater(n['signal_delays_s'].sum(),0)
        self.assertEqual(u['signal_delays_s'].sum(),0)
        self.assertAlmostEqual(n['elapsed_s']-u['elapsed_s'],n['signal_delays_s'].sum())
    def test_green(self):
        w=self.world();seed=next(s for s in range(100) if signal_waits(w,s)[1]==0)
        d=simulate_roads(w,0,3,0,0,seed,10,False,max_steps=100)
        self.assertEqual(d['signal_delays_s'].sum(),0)
