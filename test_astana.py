"""Нақты OSM графының бағыттары, A*, HMM және бұғаттау тесттері."""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import ui.cache as road_cache
import networkx as nx
import numpy as np
from astana import load_roads,nearest,astar_roads,simulate_roads

class AstanaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        fixture=Path(cls.temp.name)/'astana_roads.json'
        shutil.copyfile(Path(__file__).parent/'data/astana_roads.json',fixture)
        cls.patch=patch.object(road_cache,'DATA',fixture)
        cls.patch.start()
        cls.addClassCleanup(cls.patch.stop)
        cls.addClassCleanup(load_roads.clear)
        cls.addClassCleanup(simulate_roads.clear)
        load_roads.clear();simulate_roads.clear()
        cls.w=load_roads()
        cls.a=nearest(cls.w,(51.13251,71.40387))
        cls.b=nearest(cls.w,(51.12829,71.43046))

    def test_astar_optimal_distance(self):
        path=astar_roads(self.w,self.a,self.b)
        actual=sum(self.w['graph'][u][v]['length'] for u,v in zip(path,path[1:]))
        expected=nx.dijkstra_path_length(self.w['graph'],self.a,self.b,weight='length')
        self.assertAlmostEqual(actual,expected,places=5)

    def test_dynamic_trip(self):
        d=simulate_roads(self.a,self.b,.2,20,42,2000,True)
        self.assertEqual(d['path'][-1],self.b)
        self.assertIsNotNone(d['blocked'])
        for i,(u,v) in enumerate(zip(d['path'],d['path'][1:])):
            self.assertTrue(u==v or self.w['graph'].has_edge(u,v))
            if d['phases'][i+1]: self.assertNotEqual((u,v),d['blocked'])
        self.assertTrue(np.all((d['confidence']>=0)&(d['confidence']<=1)))

    def test_zero_noise_reverse_route(self):
        d=simulate_roads(self.b,self.a,0.,0,7,2000,False)
        self.assertEqual(d['path'][-1],self.a)
        np.testing.assert_array_equal(d['path'],d['filtered'])

if __name__=='__main__': unittest.main()
