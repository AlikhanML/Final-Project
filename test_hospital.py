import unittest
import networkx as nx
import numpy as np
from services.dispatch import select_hospital
from services.events import handle_event

class HospitalTests(unittest.TestCase):
    def setUp(self):
        g=nx.DiGraph()
        g.add_weighted_edges_from([(0,2,1000),(1,2,200),(2,0,1),(2,1,2000)],weight='length')
        self.w={'graph':g,'coords':np.array([[51.13,71.41],[51.14,71.42],[51.15,71.43]]),
            'source':{'bbox':[71,51,72,52],'hospitals':[
                {'id':'a','name':'Городская больница №1','tags':{'amenity':'hospital'},'lat':51.13,'lon':71.41},
                {'id':'b','name':'Городская больница №2','tags':{'amenity':'hospital'},'lat':51.14,'lon':71.42}]}}
    def test_directed_distance(self):
        h=select_hospital(self.w,(51.15,71.43))
        self.assertEqual(h['id'],'b')
        self.assertEqual(h['road_m'],200)
    def test_destination_reselects_start(self):
        state={}
        handle_event(state,{'id':'1','type':'pick','target':'B','lat':51.15,'lng':71.43},self.w)
        self.assertEqual(state['nav_hospital']['id'],'b')
        handle_event(state,{'id':'2','type':'pick','target':'B','lat':51.13,'lng':71.41},self.w)
        self.assertEqual(state['nav_hospital']['id'],'a')
        before=state['nav_A']
        handle_event(state,{'id':'3','type':'pick','target':'A','lat':51.14,'lng':71.42},self.w)
        self.assertEqual(state['nav_A'],before)
    def test_no_hospitals(self):
        self.w['source']['hospitals']=[]
        with self.assertRaises(ValueError):select_hospital(self.w,(51.15,71.43))
    def test_unreachable_hospital(self):
        self.w['graph'].remove_edge(1,2)
        self.assertEqual(select_hospital(self.w,(51.15,71.43))['id'],'a')

    def test_nearest_pharmacy_is_skipped(self):
        self.w['source']['hospitals'][1]['tags']={'amenity':'pharmacy','healthcare':'hospital'}
        self.assertEqual(select_hospital(self.w,(51.15,71.43))['id'],'a')
    def test_old_untyped_records_rejected(self):
        for h in self.w['source']['hospitals']:h.pop('tags')
        with self.assertRaises(ValueError):select_hospital(self.w,(51.15,71.43))
    def test_conflicting_name_rejected(self):
        self.w['source']['hospitals'][1]['name']='Дәріхана 24'
        self.assertEqual(select_hospital(self.w,(51.15,71.43))['id'],'a')
