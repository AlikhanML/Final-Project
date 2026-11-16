"""Projection, graph splitting, directed reachability and UI event integration."""
import unittest
from unittest.mock import patch
import numpy as np
import networkx as nx
from shapely.geometry import Point
from environments.edge_snap import build_edge_index,project_to_nearest_edge,destination_world
from services.simulation import simulate_roads
from services.edge_events import handle_edge_event
from tests.fixtures import road_world

class EdgeSnapTests(unittest.TestCase):
    def setUp(self):
        self.w=road_world();self.w.update(lat0=51.13,lon0=71.41,dataset_version='test',
            source={'bbox':[71,51,72,52],'hospitals':[{'id':'h','name':'Городская больница №1','lat':51.13,'lon':71.41,'tags':{'amenity':'hospital'}}]})
        self.index=build_edge_index(self.w)
        self.point=(51.1299,71.4105)
    def test_mid_edge_not_nearest_endpoint(self):
        snap=project_to_nearest_edge(self.index,*self.point)
        self.assertAlmostEqual(snap['lon'],71.4105,places=6)
        self.assertAlmostEqual(snap['lat'],51.13,places=6)
        self.assertTrue(.49<snap['fraction']<.51)
        self.assertTrue(10<snap['distance_m']<12)
    def test_index_matches_brute_force(self):
        for point in np.random.default_rng(1).uniform([51.129,71.409],[51.132,71.412],(100,2)):
            result=project_to_nearest_edge(self.index,*point)
            xy=self.index.forward.transform(point[1],point[0])
            self.assertAlmostEqual(result['distance_m'],min(line.distance(Point(xy)) for line in self.index.lines),places=7)
    def test_split_preserves_length_and_source(self):
        before=list(self.w['graph'].edges(data=True))
        rw,goal,snap=destination_world(self.w,self.point,index=self.index)
        u,v=snap['edge'];g=rw['graph']
        self.assertAlmostEqual(g[u][goal]['length']+g[goal][v]['length'],self.w['graph'][u][v]['length'])
        self.assertTrue(g.has_edge(v,goal));self.assertTrue(g.has_edge(goal,u))
        self.assertFalse(g.has_edge(u,v))
        self.assertEqual(before,list(self.w['graph'].edges(data=True)))
        self.assertEqual(len(self.w['coords']),4)
    def test_oneway_not_made_bidirectional(self):
        w=self.w;w['graph'].remove_edges_from([(1,0),(0,3),(3,0),(1,2),(2,1),(2,3),(3,2)])
        rw,goal,_=destination_world(w,self.point)
        self.assertTrue(nx.has_path(rw['graph'],0,goal))
        self.assertFalse(nx.has_path(rw['graph'],1,goal))
        self.assertFalse(rw['graph'].has_edge(goal,0))
    def test_endpoint_reuses_existing_node(self):
        rw,goal,_=destination_world(self.w,tuple(self.w['coords'][0]))
        self.assertIs(rw,self.w);self.assertEqual(goal,0)
    def test_far_and_invalid_rejected(self):
        for pt in ((float('nan'),71.4),(52.,72.)):
            with self.assertRaises(ValueError):project_to_nearest_edge(self.index,*pt)
    def test_simulation_arrives_at_projected_node(self):
        rw,goal,snap=destination_world(self.w,self.point)
        d=simulate_roads(rw,0,goal,0.,0,42,10,False)
        self.assertEqual(d['status'],'reached')
        np.testing.assert_allclose(rw['coords'][d['path'][-1]],[snap['lat'],snap['lon']])
    @patch('services.edge_events.lookup_address',return_value=None)
    def test_pick_then_route_uses_virtual_goal(self, _address_lookup):
        state={'nav_config':(0.,0,42,10,False)}
        handle_edge_event(state,{'id':'1','type':'pick','target':'B','lat':self.point[0],'lng':self.point[1]},self.w,simulate_roads)
        self.assertEqual(state['nav_error'],'')
        self.assertEqual(state['nav_goal'],4)
        handle_edge_event(state,{'id':'2','type':'route'},self.w,simulate_roads)
        self.assertEqual(state['nav_result']['status'],'reached')
        handle_edge_event(state,{'id':'3','type':'reset'},self.w,simulate_roads)
        self.assertIsNone(state['nav_snap']);self.assertIsNone(state['nav_route_world'])

    @patch('services.edge_events.lookup_address',return_value=None)
    def test_new_destination_keeps_urgent_and_uses_reduced_delay(self, _lookup):
        state={'nav_config':(1.,0,42,10,False),'nav_priority':'urgent'}
        handle_edge_event(state,{'id':'urgent-pick','type':'pick','target':'B',
                                'lat':self.point[0],'lng':self.point[1]},self.w,simulate_roads)
        self.assertEqual(state['nav_priority'],'urgent')
        handle_edge_event(state,{'id':'urgent-route','type':'route'},self.w,simulate_roads)
        urgent=state['nav_result']
        handle_edge_event(state,{'id':'normal-switch','type':'priority','priority':'normal'},self.w,simulate_roads)
        normal=state['nav_result']
        self.assertEqual(urgent['priority'],'urgent')
        self.assertLess(urgent['eta_plan_s'],normal['eta_plan_s'])
        self.assertLess(urgent['elapsed_s'],normal['elapsed_s'])
        handle_edge_event(state,{'id':'urgent-switch','type':'priority','priority':'urgent'},self.w,simulate_roads)
        self.assertAlmostEqual(state['nav_result']['eta_plan_s'],urgent['eta_plan_s'])
