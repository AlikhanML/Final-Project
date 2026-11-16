"""Dense OSM nodes must permit sensor recovery instead of immediate failure."""
import unittest
import numpy as np
import networkx as nx
from services.simulation import simulate_roads
from algorithms.hmm import OnlineRoadHMM

class RelocalizationTests(unittest.TestCase):
    def test_dense_road_recovers_and_reaches_goal(self):
        n=60;coords=np.column_stack([np.full(n,51.13),71.41+np.arange(n)*3/(111320*np.cos(np.radians(51.13)))])
        g=nx.DiGraph();dest=np.repeat(np.arange(n)[:,None],2,axis=1);valid=np.zeros((n,2),bool);lengths=np.ones((n,2))*3
        for i in range(n):
         for a,j in enumerate((i-1,i+1)):
          if 0<=j<n:g.add_edge(i,j,length=3.,model_speed_kmh=30.);dest[i,a]=j;valid[i,a]=True
        w=dict(graph=g,coords=coords,xy=np.column_stack([np.arange(n)*3,np.zeros(n)]),lat0=51.13,lon0=71.41,dest=dest,valid=valid,lengths=lengths)
        old=simulate_roads(w,20,n-1,0.,20,0,10,False,max_relocalizations=0)
        new=simulate_roads(w,20,n-1,0.,20,0,10,False)
        self.assertEqual(old['status'],'localization_stop')
        self.assertEqual(new['status'],'reached')
        self.assertEqual(new['path'][-1],n-1)
        self.assertGreater(new['relocalizations'],0)
        self.assertTrue(np.all(np.diff(new['timestamps_s'])>0))
        self.assertAlmostEqual(sum(new['segment_times_s']),new['elapsed_s'])
        for u,v in zip(new['path'],new['path'][1:]):
            self.assertTrue(u==v or g.has_edge(u,v))
        for event in new['recovery_events']:
            i=event['index']
            self.assertEqual(new['path'][i],new['path'][i-1])
            self.assertGreaterEqual(new['segment_times_s'][i-1],event['samples']*.2)
    def test_effective_noise_does_not_change_base_sensor_model(self):
        hmm=OnlineRoadHMM(np.array([[0.,0.],[3.,0.]]),20)
        belief=hmm.update([0.,0.],observation_sigma=.5)
        self.assertGreater(belief[0],.99)
        self.assertEqual(hmm.sigma,20)
        with self.assertRaises(ValueError):hmm.update([0.,0.],observation_sigma=-1)

    def test_quick_mode_never_waits_minutes_on_uncertain_gps(self):
        from unittest.mock import patch
        from tests.test_turn_costs import junction_world
        w=junction_world()
        with patch.object(OnlineRoadHMM,'update',return_value=np.ones(5)/5):
            d=simulate_roads(w,0,2,0.,20,42,10,False,quick_recovery=True)
        self.assertEqual(d['status'],'localization_stop')
        self.assertLessEqual(d['elapsed_s'],30.+1e-8)
        self.assertGreater(len(d['recovery_events']),0)
        self.assertTrue(np.all(d['path']==0))

    def test_normal_navigation_has_no_gps_waits_or_closure(self):
        from tests.test_turn_costs import junction_world
        d=simulate_roads(junction_world(),0,2,.2,0,42,100,False,quick_recovery=True)
        self.assertEqual(d['status'],'reached')
        self.assertIsNone(d['blocked'])
        self.assertEqual(d['relocalizations'],0)
        self.assertTrue(np.all(d['path'][1:]!=d['path'][:-1]))
        self.assertAlmostEqual(d['elapsed_s'],d['eta_plan_s'])
