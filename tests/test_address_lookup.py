import unittest
from concurrent.futures import Future
from unittest.mock import patch
from services.address_lookup import (
    parse_address, _lookup, local_address, lookup_address, _cache,
    start_automatic_address, finish_automatic_address,
)
from services.destination_label import destination_label

class AddressLookupTests(unittest.TestCase):
    def test_full_address_tag(self):
        raw={'elements':[{'lat':51.,'lon':71.,'tags':{'addr:full':'Астана, Абай көшесі, 10'}}]}
        self.assertEqual(parse_address(raw,51,71)['label'],'Астана, Абай көшесі, 10')
    def test_localized_street(self):
        raw={'elements':[{'lat':51.,'lon':71.,'tags':{'addr:street:kk':'Абай көшесі','addr:housenumber':'10'}}]}
        self.assertEqual(parse_address(raw,51,71)['label'],'Абай көшесі, 10')
    def test_inside_preferred(self):
        near={'type':'node','lat':51.,'lon':71.,'tags':{'addr:street':'Басқа','addr:housenumber':'2'}}
        building={'type':'way','center':{'lat':51.,'lon':71.},'tags':{'addr:street':'Түркістан','addr:housenumber':'10'},'geometry':[{'lat':a,'lon':b} for a,b in [(50.999,70.999),(50.999,71.001),(51.001,71.001),(51.001,70.999),(50.999,70.999)]]}
        self.assertEqual(parse_address({'elements':[near,building]},51,71)['label'],'Түркістан, 10')
    def test_near_is_explicit(self):
        result=parse_address({'elements':[{'lat':51.,'lon':71.,'tags':{'addr:street':'Абай','addr:housenumber':'3'}}]},51,71)
        self.assertIn('жақын',result['note'])
    def test_far_rejected(self):
        self.assertIsNone(parse_address({'elements':[{'lat':52.,'lon':71.,'tags':{'addr:street':'Абай','addr:housenumber':'3'}}]},51,71))
    def test_incomplete_rejected(self):
        self.assertIsNone(parse_address({'elements':[{'lat':51.,'lon':71.,'tags':{'addr:street':'Абай'}}]},51,71))
    def test_timeout_not_cached(self):
        _cache.clear()
        with patch('services.address_lookup.urllib.request.urlopen',side_effect=TimeoutError) as request:
            self.assertEqual(lookup_address((51,71))['status'],'timeout')
            self.assertEqual(lookup_address((51,71))['status'],'timeout')
            self.assertEqual(request.call_count,2)
    def test_success_cache_and_retry(self):
        _cache.clear()
        with patch('services.address_lookup._lookup',return_value={'label':'Абай, 1','status':'found','note':'OSM'}) as request:
            lookup_address((51,71));lookup_address((51,71))
            self.assertEqual(request.call_count,1)
            lookup_address((51,71),force=True)
            self.assertEqual(request.call_count,2)
    def test_building_edge_distance(self):
        # The click is 11m outside the wall, but >30m from the centroid.
        obj={'center':{'lat':51.,'lon':71.},'tags':{'addr:street':'Абай','addr:housenumber':'5'},
             'geometry':[{'lat':a,'lon':b} for a,b in [(50.9995,70.9995),(50.9995,71.0005),(51.0005,71.0005),(51.0005,70.9995),(50.9995,70.9995)]]}
        self.assertEqual(parse_address({'elements':[obj]},51.0006,71)['label'],'Абай, 5')
    def test_addressed_building_geometry_without_center(self):
        building={'type':'way','tags':{'addr:street':'Аңырақай көшесі','addr:housenumber':'37'},
                  'geometry':[{'lat':lat,'lon':lon} for lat,lon in
                              [(51.,71.),(51.,71.001),(51.001,71.001),(51.001,71.),(51.,71.)]]}
        exact=parse_address({'elements':[building]},51.0005,71.0005)
        self.assertFalse(exact['nearby'])
        self.assertEqual(exact['house_number'],'37')
        nearby=parse_address({'elements':[building]},51.0011,71.0005)
        self.assertTrue(nearby['nearby'])
    def test_address_node_requires_a_point_match(self):
        node={'type':'node','lat':51.,'lon':71.,
              'tags':{'addr:street':'Аңырақай көшесі','addr:housenumber':'37'}}
        self.assertFalse(parse_address({'elements':[node]},51.000001,71.)['nearby'])
        self.assertTrue(parse_address({'elements':[node]},51.0001,71.)['nearby'])
    def test_http_error_visible(self):
        from urllib.error import HTTPError
        with patch('services.address_lookup.urllib.request.urlopen',side_effect=HTTPError('url',429,'busy',None,None)):
            self.assertIn('429',_lookup(51,71)['note'])


class AutomaticAddressTests(unittest.TestCase):
    def test_schedule_once_and_only_publish_verified_numbers(self):
        point=(51.,71.)
        full={'label':'Аңырақай көшесі, 37','street':'Аңырақай көшесі','house_number':'37',
              'nearby':False,'status':'found','note':'OSM'}
        for result,expected in [
            (full,'Аңырақай көшесі, 37'),
            ({**full,'nearby':True},'Аңырақай көшесінің маңы'),
            ({**full,'house_number':None},'Аңырақай көшесінің маңы'),
            ({'label':None,'status':'timeout'},'Аңырақай көшесінің маңы'),
        ]:
            with self.subTest(result=result):
                future=Future()
                route=object()
                state={'nav_B':point,'nav_address':{'status':'selected'},'nav_result':route}
                with patch('services.address_lookup._address_workers.submit',return_value=future) as submit:
                    start_automatic_address(state)
                    start_automatic_address(state)
                    submit.assert_called_once_with(lookup_address,point,world=None)
                self.assertFalse(finish_automatic_address(state))
                self.assertEqual(state['nav_address']['status'],'auto_pending')
                future.set_result(result)
                self.assertTrue(finish_automatic_address(state))
                self.assertIs(state['nav_result'],route)
                self.assertEqual(state['nav_B'],point)
                self.assertEqual(destination_label({},None,'Аңырақай көшесі',address=state['nav_address']),expected)

    def test_exact_display_excludes_street_only_and_nearby_results(self):
        address={'status':'found','label':'Аңырақай көшесі, 37','street':'Аңырақай көшесі',
                 'house_number':'37','nearby':False}
        for incomplete in (None, {**address,'nearby':True}, {**address,'house_number':None},
                           {**address,'street':None}, {'status':'manual','label':'Аңырақай көшесі'}):
            self.assertIsNone(destination_label({},None,'Аңырақай көшесі',address=incomplete,exact_only=True))
        self.assertEqual(destination_label({},None,address=address,exact_only=True),'Аңырақай көшесі, 37')
        manual={'status':'manual','label':'E 100 37'}
        self.assertEqual(destination_label({},None,address=manual,exact_only=True),'E 100 көшесі, 37')


class LocalAddressTests(unittest.TestCase):
    point = (51.0005, 71.0005)
    tags = {'addr:street':'Аңырақай көшесі','addr:housenumber':'37'}
    source = {
        'nodes':{'1':[51.,71.],'2':[51.,71.001],'3':[51.001,71.001],'4':[51.001,71.]},
        'ways':[{'nodes':['1','2','3','4','1'],'tags':{**tags,'building':'yes'}}],
    }

    def test_local_building_lookup_reuses_exact_address_format(self):
        world={'source':self.source}
        for address in (local_address(self.point,world),local_address(world,self.point)):
            self.assertFalse(address['nearby'])
            self.assertEqual(destination_label({},None,address=address,exact_only=True),'Аңырақай көшесі, 37')

    def test_local_match_skips_remote_request(self):
        with patch('services.address_lookup._lookup') as remote:
            address=lookup_address(self.point,world={'source':self.source})
        remote.assert_not_called()
        self.assertEqual(address['label'],'Аңырақай көшесі, 37')

    def test_addressed_road_is_not_a_building(self):
        source={**self.source,'ways':[{'nodes':['1','3'],
                                      'tags':{**self.tags,'highway':'residential'}}]}
        self.assertIsNone(local_address(self.point,source))

if __name__=='__main__':unittest.main()
