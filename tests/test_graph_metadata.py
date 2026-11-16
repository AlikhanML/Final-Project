"""Small OSM snapshots verify geometry, speed provenance and cache invalidation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import networkx as nx
from infrastructure.graph_builder import build_world
from infrastructure.repository import snapshot_identity
from infrastructure.speeds import parse_speed, speed_metadata
import ui.cache as cache


def snapshot():
    return {'bbox':[71,51,72,52], 'nodes':{'a':[51.13,71.41],
        'b':[51.131,71.411],'c':[51.132,71.41]},
        'ways':[{'id':10,'nodes':['a','b','c'],'tags':{'highway':'residential',
                'maxspeed:forward':'40','maxspeed:backward':'20'}},
                {'id':20,'nodes':['a','b'],'tags':{'highway':'residential','maxspeed':'60'}}]}

class GraphMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'astana_roads.json'
        self.write(snapshot())
    def write(self,data):
        self.path.write_text(json.dumps(data),encoding='utf-8')
    def test_speed_units_and_unknown_values(self):
        self.assertEqual(parse_speed('60'),60)
        self.assertAlmostEqual(parse_speed('50 mph'),80.4672)
        for raw in ('none','signals','KZ:urban','30;50','0','-5','nan',None):
            self.assertIsNone(parse_speed(raw))
    def test_direction_and_fallback_provenance(self):
        tags={'highway':'service','maxspeed':'50','maxspeed:backward':'unknown'}
        self.assertEqual(speed_metadata(tags,1)['speed_limit_kmh'],50)
        reverse=speed_metadata(tags,-1)
        self.assertIsNone(reverse['speed_limit_kmh'])
        self.assertEqual(reverse['speed_source'],'model_default')
    def test_conditional_kept_without_claiming_evaluation(self):
        result=speed_metadata({'maxspeed':'50','maxspeed:conditional':'30 @ (wet)'},1)
        self.assertTrue(result['has_conditional_speed'])
        self.assertIn('maxspeed:conditional',result['speed_tags'])
    def test_all_geometry_vertices_and_reverse_order_preserved(self):
        w=build_world(self.path)
        self.assertEqual(len(w['coords']),3)
        edge=w['graph'][1][2]
        self.assertEqual(edge['geometry'],[[51.131,71.411],[51.132,71.41]])
        self.assertEqual(w['graph'][2][1]['geometry'],list(reversed(edge['geometry'])))
        self.assertEqual(edge['speed_limit_kmh'],40)
        self.assertEqual(w['graph'][2][1]['speed_limit_kmh'],20)
    def test_parallel_roads_are_not_overwritten(self):
        w=build_world(self.path)
        self.assertEqual(w['road_graph'].number_of_edges(0,1),2)
        self.assertEqual(w['graph'][0][1]['way_id'],'20')
        self.assertEqual(w['graph'][0][1]['speed_limit_kmh'],60)
    def test_one_way_branch_is_retained(self):
        data=snapshot();data['ways']=[{'id':1,'nodes':['a','b','c'],
            'tags':{'highway':'residential','oneway':'yes'}}];self.write(data)
        w=build_world(self.path)
        self.assertEqual(nx.shortest_path(w['graph'],0,2),[0,1,2])
        self.assertFalse(nx.has_path(w['graph'],2,0))
        self.assertFalse(w['valid'][2].any())
    def test_file_change_invalidates_graph_cache(self):
        with patch.object(cache,'DATA',self.path):
            first=cache.load_roads()
            data=snapshot();data['ways'][1]['tags']['maxspeed']='80';self.write(data)
            second=cache.load_roads()
            self.assertNotEqual(first['dataset_version'],second['dataset_version'])
            self.assertEqual(second['graph'][0][1]['speed_limit_kmh'],80)
    def test_changed_file_rejects_old_node_identity(self):
        with patch.object(cache,'DATA',self.path):
            first=cache.load_roads();data=snapshot();data['ways'][0]['id']=99;self.write(data)
            with self.assertRaises(ValueError):
                cache.simulate_roads(0,1,0,0,42,10,False,expected_version=first['dataset_version'])
    def test_build_rejects_snapshot_changed_during_load(self):
        _,version=snapshot_identity(self.path)
        data=snapshot();data['ways'][0]['id']=99;self.write(data)
        with self.assertRaises(ValueError):build_world(self.path,version)
    def test_missing_geometry_and_nan_are_rejected(self):
        data=snapshot();del data['nodes']['b'];self.write(data)
        with self.assertRaises(ValueError):build_world(self.path)
        data=snapshot();data['nodes']['b'][0]=float('nan');self.write(data)
        with self.assertRaises(ValueError):build_world(self.path)

    def test_route_cache_also_changes_with_snapshot(self):
        with patch.object(cache,'DATA',self.path), patch.object(cache,'simulate_road_world',return_value={'status':'reached'}) as simulate:
            cache.simulate_roads.clear()
            cache.simulate_roads(0,1,0,0,42,10,False)
            cache.simulate_roads(0,1,0,0,42,10,False)
            self.assertEqual(simulate.call_count,1)
            data=snapshot();data['ways'][1]['tags']['maxspeed']='80';self.write(data)
            cache.simulate_roads(0,1,0,0,42,10,False)
            self.assertEqual(simulate.call_count,2)
            cache.simulate_roads.clear()
