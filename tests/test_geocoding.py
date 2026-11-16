import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch, Mock
from geopy.exc import GeocoderTimedOut
from services import geocoding
from services.address_lookup import finish_automatic_address
from services.edge_events import handle_edge_event
from services.simulation import simulate_roads
from tests import test_edge_snap


def place(lat=51.13,lng=71.41,number='55'):
    return SimpleNamespace(latitude=lat,longitude=lng,address='Мәңгілік Ел, 55, Астана',raw={'address':{'house_number':number}})


class GeocodingTests(unittest.TestCase):
    def setUp(self):
        geocoding._cache.clear()
        geocoding._last_request=0
        self.mock=patch('services.geocoding.Nominatim').start()
        self.addCleanup(patch.stopall)
        self.api=self.mock.return_value.geocode
        self.api.return_value=[place()]

    def test_bounds_country_address_and_cache(self):
        first=geocoding.geocode_astana('Мәңгілік Ел 55')
        second=geocoding.geocode_astana('  Мәңгілік   Ел 55 ')
        self.assertEqual(first,second)
        self.assertEqual(self.api.call_count,1)
        kwargs=self.api.call_args.kwargs
        self.assertTrue(kwargs['bounded'])
        self.assertEqual(kwargs['country_codes'],'kz')
        self.assertTrue(kwargs['addressdetails'])
        self.assertEqual(len(kwargs['viewbox']),2)
        self.assertIn('Астана',self.api.call_args.args[0])
        first['lat']=0
        self.assertEqual(geocoding.geocode_astana('Мәңгілік Ел 55')['lat'],51.13)

    def test_outside_city_rejected(self):
        self.api.return_value=[place(43.24,76.89)]
        with self.assertRaisesRegex(ValueError,'табылмады'):
            geocoding.geocode_astana('Мәңгілік Ел 55')

    def test_street_is_not_presented_as_house(self):
        self.api.return_value=[place(number='')]
        with self.assertRaisesRegex(ValueError,'табылмады'):
            geocoding.geocode_astana('Мәңгілік Ел 55')

    def test_timeout_reported(self):
        self.api.side_effect=GeocoderTimedOut('timeout')
        with self.assertRaisesRegex(ValueError,'уақыты аяқталды'):
            geocoding.geocode_astana('Мәңгілік Ел 55')

    def test_empty_and_invalid_query_never_request(self):
        for query in ['',None,[],42,'a','a'*201]:
            with self.assertRaises(ValueError):geocoding.geocode_astana(query)
        self.api.assert_not_called()

    @patch('services.geocoding.time.sleep')
    def test_rate_limit_across_different_queries(self,sleep):
        geocoding.geocode_astana('Мәңгілік Ел 55')
        geocoding.geocode_astana('Түркістан 55')
        sleep.assert_called_once()
        self.assertGreater(sleep.call_args.args[0],0)


class DestinationWorkflowTests(unittest.TestCase):
    def setUp(self):
        fixture=test_edge_snap.EdgeSnapTests();fixture.setUp()
        self.world=fixture.w;self.point=fixture.point
        self.state={'nav_config':(0.,0,42,10,False)}
        self.simulate=Mock(wraps=simulate_roads)

    def test_click_calculates_immediately_and_deduplicates(self):
        event={'id':'click1','type':'pick','target':'B','lat':self.point[0],'lng':self.point[1]}
        handle_edge_event(self.state,event,self.world,self.simulate)
        self.assertEqual(self.state['nav_result']['status'],'reached')
        self.assertGreater(self.state['nav_result']['eta_plan_s'],0)
        self.assertEqual(self.state['nav_focus']['id'],'click1')
        handle_edge_event(self.state,event,self.world,self.simulate)
        self.assertEqual(self.simulate.call_count,1)
        event={**event,'id':'click2','lng':71.4107}
        handle_edge_event(self.state,event,self.world,self.simulate)
        self.assertEqual(self.simulate.call_count,2)
        self.assertEqual(self.state['nav_B'],(self.point[0],71.4107))
        self.assertEqual(self.state['nav_trip_version'],2)

    @patch('services.edge_events.geocode_astana')
    def test_search_uses_same_route_pipeline(self,geocode):
        geocode.return_value={'lat':self.point[0],'lng':self.point[1],'label':'Example, 55'}
        handle_edge_event(self.state,{'id':'search1','type':'geocode','query':'Example 55'},self.world,self.simulate)
        self.assertEqual(self.state['nav_result']['status'],'reached')
        self.assertEqual(self.state['nav_address']['label'],'Example, 55')
        self.assertEqual(self.state['nav_B'],self.point)
        self.assertEqual(self.state['nav_focus']['id'],'search1')

    @patch('services.edge_events.geocode_astana',side_effect=ValueError('Not found'))
    def test_failed_search_preserves_destination_and_route(self,geocode):
        self.state.update(nav_B=self.point,nav_result={'previous':True})
        handle_edge_event(self.state,{'id':'bad','type':'geocode','query':'bad'},self.world,self.simulate)
        self.assertEqual(self.state['nav_B'],self.point)
        self.assertEqual(self.state['nav_result'],{'previous':True})
        self.simulate.assert_not_called()

    def test_completed_old_lookup_cannot_overwrite_a_new_call(self):
        future=Future()
        future.set_result({'label':'Абай көшесі, 10','house_number':'10','nearby':False,'status':'found'})
        self.state['nav_address_future']=future
        handle_edge_event(self.state,{'id':'next','type':'pick','target':'B',
                                      'lat':self.point[0],'lng':self.point[1]},self.world,self.simulate)
        self.assertFalse(finish_automatic_address(self.state))
        self.assertEqual(self.state['nav_address']['status'],'selected')

    def test_manual_address_cancels_pending_lookup(self):
        future=Future()
        self.state.update(nav_B=self.point,nav_address_future=future)
        handle_edge_event(self.state,{'id':'manual','type':'address_save','point':list(self.point),
                                      'address':'Аңырақай көшесі, 37'},self.world,self.simulate)
        self.assertTrue(future.cancelled())
        self.assertFalse(finish_automatic_address(self.state))
        self.assertEqual(self.state['nav_address']['label'],'Аңырақай көшесі, 37')
