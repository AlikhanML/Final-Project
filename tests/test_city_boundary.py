import unittest
from unittest.mock import patch
from services.city_boundary import (
    in_astana, city_geometry, OUTSIDE_CITY_MESSAGE, call_exclusion_geometry,
    in_call_exclusion, call_exclusion_message,
)
from services.edge_events import handle_edge_event

class CityBoundaryTests(unittest.TestCase):
    def test_inside(self):
        for lat,lon in [(51.1282,71.4304),(51.1694,71.4491),(51.089,71.413)]:
            self.assertTrue(in_astana(lat,lon))
    def test_outside(self):
        for lat,lon in [(43.2389,76.8897),(51.5,71.4),(50.972,71.355),(float('nan'),71.4),(51,float('inf'))]:
            self.assertFalse(in_astana(lat,lon))
    def test_boundary_included(self):
        lon,lat=city_geometry()['coordinates'][0][0][0]
        self.assertTrue(in_astana(lat,lon))
    def test_invalid_pick_preserves_previous_route(self):
        previous=object();state={'nav_B':(51.1282,71.4304),'nav_result':previous}
        with patch('services.edge_events.destination_world') as snap:
            handle_edge_event(state,{'id':'outside','type':'pick','target':'B','lat':43.2389,'lng':76.8897},{},None)
            snap.assert_not_called()
        self.assertEqual(state['nav_error'],OUTSIDE_CITY_MESSAGE)
        self.assertIs(state['nav_result'],previous)
        self.assertEqual(state['nav_B'],(51.1282,71.4304))

    def test_island_and_shoreline_are_excluded(self):
        shoreline_lon,shoreline_lat=call_exclusion_geometry()['coordinates'][0][0]
        for point in ((51.099348,71.482485),(51.100426,71.474653),(shoreline_lat,shoreline_lon)):
            self.assertTrue(in_astana(*point))
            self.assertTrue(in_call_exclusion(*point))
        for point in ((51.101194,71.481884),(51.097879,71.486347),(51.102191,71.473988)):
            self.assertTrue(in_astana(*point))
            self.assertFalse(in_call_exclusion(*point))

    def test_island_pick_and_geocode_preserve_previous_route(self):
        previous=object()
        state={'nav_B':(51.1282,71.4304),'nav_result':previous,'qadam_language':'ru'}
        island={'lat':51.099348,'lng':71.482485}
        events=[
            {'id':'pick','type':'pick','target':'B',**island},
            {'id':'search','type':'geocode','query':'Example 55'},
        ]
        with patch('services.edge_events.destination_world') as snap, patch(
            'services.edge_events.geocode_astana',return_value={**island,'label':'Example 55'},
        ):
            for event in events:
                handle_edge_event(state,event,{},None)
                self.assertEqual(state['nav_error'],call_exclusion_message('ru'))
                self.assertEqual(state['nav_event'],event['id'])
                self.assertIs(state['nav_result'],previous)
                self.assertEqual(state['nav_B'],(51.1282,71.4304))
            snap.assert_not_called()
