"""Time objective and timeline contracts, independent of live OSM data."""
import unittest
import numpy as np
from algorithms.astar import astar_roads
from algorithms.q_learning import q_train
from environments.travel_time import travel_time_s, route_seconds, edge_seconds
from services.simulation import simulate_roads
from tests.fixtures import road_world
import networkx as nx

class TravelTimeTests(unittest.TestCase):
    def world(self):
        w=road_world();w.update(lat0=51.13,lon0=71.41)
        for u,v,e in w['graph'].edges(data=True):e['model_speed_kmh']=36.
        return w
    def test_units_and_slowdown(self):
        self.assertEqual(travel_time_s(1000,36),100)
        self.assertEqual(travel_time_s(1000,36,1),200)
    def test_invalid_parameters_rejected(self):
        for args in ((-1,30,0),(1,0,0),(1,30,-1),(1,float('nan'),0)):
            with self.assertRaises(ValueError):travel_time_s(*args)
    def test_shortest_and_fastest_routes_differ(self):
        w=self.world()
        for u,v,e in w['graph'].edges(data=True):
            e['model_speed_kmh']=5. if 1 in (u,v) else 90.
            if 1 not in (u,v):e['length']*=2
        self.assertEqual(astar_roads(w,0,2),[0,1,2])
        self.assertEqual(astar_roads(w,0,2,cost='time'),[0,3,2])
    def test_time_astar_matches_dijkstra(self):
        w=self.world();traffic=np.full_like(w['lengths'],.7)
        for start in range(4):
            for goal in range(4):
                route=astar_roads(w,start,goal,traffic=traffic,cost='time')
                expected=nx.dijkstra_path_length(w['graph'],start,goal,weight=lambda u,v,e:edge_seconds(e,.7))
                self.assertAlmostEqual(route_seconds(w,route,traffic),expected)
    def test_more_geometry_vertices_do_not_add_time(self):
        results=[]
        for n in (2,11):
            g=nx.DiGraph();coords=np.column_stack([np.full(n,51.13),np.linspace(71.41,71.411,n)])
            dest=np.repeat(np.arange(n)[:,None],2,axis=1);valid=np.zeros((n,2),bool)
            lengths=np.ones((n,2))
            for u in range(n):
                for a,v in enumerate((u-1,u+1)):
                    if 0<=v<n:
                        g.add_edge(u,v,length=1000/(n-1),model_speed_kmh=36.)
                        dest[u,a]=v;valid[u,a]=True;lengths[u,a]=1000/(n-1)
            w=dict(graph=g,coords=coords,dest=dest,valid=valid,lengths=lengths,
                   xy=np.column_stack([np.linspace(0,70,n),np.zeros(n)]),lat0=51.13,lon0=71.41)
            d=simulate_roads(w,0,n-1,0.,0,42,10,False)
            self.assertEqual(d['status'],'reached')
            self.assertEqual(len(d['path']),n)
            results.append(d['elapsed_s'])
        np.testing.assert_allclose(results,[100,100])
    def test_timeline_and_eta_agree_without_changes(self):
        w=self.world();d=simulate_roads(w,0,2,.3,0,42,30,False)
        self.assertEqual(d['status'],'reached')
        self.assertEqual(len(d['timestamps_s']),len(d['path']))
        self.assertTrue(np.all(np.diff(d['timestamps_s'])>0))
        self.assertAlmostEqual(d['elapsed_s'],d['eta_plan_s'])
        self.assertAlmostEqual(d['elapsed_s'],sum(d['segment_times_s']))
        np.testing.assert_array_equal(d['filtered'],d['path'])
    def test_terminal_has_zero_duration(self):
        d=simulate_roads(self.world(),0,0,0.,0,42,10,True)
        self.assertEqual(d['eta_plan_s'],0)
        self.assertEqual(d['elapsed_s'],0)
        np.testing.assert_array_equal(d['timestamps_s'],[0])
    def test_q_reward_is_seconds_and_terminal_not_bootstrapped(self):
        w=self.world()
        # Restrict each state to one allowed action, leading straight to the goal.
        w['valid'][:]=False;w['valid'][0,0]=True
        w['graph'][0][1]['length']=1000
        w['lengths'][0,0]=1000
        q,_=q_train(w,1,None,np.zeros_like(w['lengths']),42,1)
        self.assertAlmostEqual(q[0,0],-100*(.6/(1+1/100)))
        np.testing.assert_array_equal(q[1],0)
