"""End-to-end road scenarios: OSM tags -> graph -> planner -> vehicle path."""
import json
from pathlib import Path
import tempfile
import unittest
import networkx as nx
import numpy as np
from infrastructure.graph_builder import build_world
from environments.turn_costs import TurnModel
from environments.edge_snap import destination_world
from services.simulation import simulate_roads


class RouteAcceptanceTests(unittest.TestCase):
    def world(self, nodes, ways):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'roads.json'
            path.write_text(json.dumps({'nodes':nodes,'ways':ways,'bbox':[71,51,72,52]}))
            return build_world(path)

    @staticmethod
    def way(nodes, **tags):
        return {'nodes':nodes,'tags':{'highway':'residential','maxspeed':'36',**tags}}

    def assert_legal_trip(self,w,result,goal):
        self.assertEqual(result['status'],'reached')
        self.assertEqual(result['path'][-1],goal)
        self.assertTrue(np.isfinite(result['timestamps_s']).all())
        self.assertTrue(np.all(np.diff(result['timestamps_s'])>=0))
        length=0.
        for i,(u,v) in enumerate(zip(result['path'],result['path'][1:])):
            if u==v:continue  # HMM hold or GPS recovery
            self.assertTrue(w['graph'].has_edge(u,v),(u,v))
            if result['phases'][i+1]:self.assertNotEqual((u,v),result['blocked'])
            length+=w['graph'][u][v]['length']
        self.assertAlmostEqual(result['travel'],length)
        self.assertAlmostEqual(result['timestamps_s'][-1],result['elapsed_s'])
        self.assertAlmostEqual(sum(result['segment_times_s']),result['elapsed_s'])

    def test_reverse_oneway_has_no_illegal_return(self):
        w=self.world({'a':[51.13,71.41],'b':[51.13,71.411],'c':[51.13,71.412]},
                     [self.way(['a','b','c'],oneway='-1')])
        d=simulate_roads(w,2,0,0,0,42,20,False)
        self.assert_legal_trip(w,d,0)
        self.assertEqual(d['path'].tolist(),[2,1,0])
        with self.assertRaises(nx.NetworkXNoPath):simulate_roads(w,0,2,0,0,42,20,False)

    def test_roundabout_respects_direction(self):
        nodes={'a':[51.13,71.41],'b':[51.13,71.411],
               'c':[51.131,71.411],'d':[51.131,71.41]}
        w=self.world(nodes,[self.way(['a','b','c','d','a'],junction='roundabout')])
        d=simulate_roads(w,1,0,0,0,42,20,False)
        self.assert_legal_trip(w,d,0)
        self.assertEqual(d['path'].tolist(),[1,2,3,0])

    def test_shortcut_sidewalk_and_private_road_excluded(self):
        nodes={'a':[51.13,71.41],'b':[51.131,71.41],'c':[51.13,71.411]}
        for tags in ({'highway':'footway'},{'highway':'cycleway'},
                     {'highway':'service','access':'private'}, {'highway':'construction'}):
            with self.subTest(tags=tags):
                w=self.world(nodes,[self.way(['a','b','c']),self.way(['a','c'],**tags)])
                self.assertFalse(w['graph'].has_edge(0,2))
                d=simulate_roads(w,0,2,0,0,42,20,False)
                self.assert_legal_trip(w,d,2)
                self.assertEqual(d['path'].tolist(),[0,1,2])

    def grid(self):
        nodes={str(i*3+j):[51.13+i*.001,71.41+j*.001] for i in range(3) for j in range(3)}
        ways=[self.way([str(i*3+j) for j in range(3)]) for i in range(3)]
        ways += [self.way([str(i*3+j) for i in range(3)]) for j in range(3)]
        return self.world(nodes,ways)

    def test_dynamic_closure_detours_without_crossing_block(self):
        w=self.grid()
        for seed in (1,7,42):
            with self.subTest(seed=seed):
                d=simulate_roads(w,0,8,0,0,seed,100,True,max_steps=300,training_updates=30000)
                self.assertIsNotNone(d['blocked'])
                self.assertTrue(d['phases'].any())
                self.assert_legal_trip(w,d,8)

    def test_projected_goal_reached_in_both_directions(self):
        w=self.grid();before=set(w['graph'].edges)
        rw,goal,snap=destination_world(w,(51.12995,71.4105))
        self.assertGreaterEqual(goal,len(w['coords']))
        for start in (0,8):
            with self.subTest(start=start):
                d=simulate_roads(rw,start,goal,0,0,42,20,False)
                self.assert_legal_trip(rw,d,goal)
                np.testing.assert_allclose(rw['coords'][d['path'][-1]],[snap['lat'],snap['lon']])
        self.assertEqual(set(w['graph'].edges),before)

    def test_disconnected_goal_reports_no_path(self):
        w=self.world({'a':[51.13,71.41],'b':[51.13,71.411],
                      'c':[51.14,71.42],'d':[51.14,71.421]},
                     [self.way(['a','b']),self.way(['c','d'])])
        with self.assertRaises(nx.NetworkXNoPath):simulate_roads(w,0,3,0,0,42,20,False)

    def test_closure_replans_cached_route(self):
        from algorithms.road_control import RoutePlan
        w=self.grid();traffic=np.zeros_like(w['lengths']);model=TurnModel(w,traffic)
        planner=RoutePlan(w,8,traffic,model)
        first=planner.next_node(0,None,None)
        second=planner.next_node(0,(0,first),None)
        self.assertNotEqual(first,second)
        self.assertTrue(w['graph'].has_edge(0,second))
        self.assertEqual(planner.searches,2)

if __name__=='__main__':unittest.main()
