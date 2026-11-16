import unittest
from road_rules import car_directions

class RoadRulesTests(unittest.TestCase):
    def test_no_foot_or_cycle_routes(self):
        for kind in ('footway','path','pedestrian','cycleway','steps','bridleway','construction'):
            self.assertEqual(car_directions({'highway':kind,'motorcar':'yes'}),())
    def test_restrictions(self):
        for key in ('motorcar','motor_vehicle','vehicle','access'):
            for value in ('no','private','destination','customers'):
                self.assertEqual(car_directions({'highway':'service',key:value}),())
    def test_specific_access_override(self):
        self.assertEqual(car_directions({'highway':'residential','access':'no','motorcar':'yes'}),(1,-1))
    def test_oneway(self):
        self.assertEqual(car_directions({'highway':'primary','oneway':'-1'}),(-1,))
        self.assertEqual(car_directions({'highway':'primary','oneway':'yes'}),(1,))
    def test_directional_and_conditional(self):
        self.assertEqual(car_directions({'highway':'residential','motor_vehicle:forward':'no'}),(-1,))
        self.assertEqual(car_directions({'highway':'residential','access:conditional':'no @ (Mo-Fr)'}),())
    def test_normal_road_with_sidewalk(self):
        self.assertEqual(car_directions({'highway':'residential','sidewalk':'both'}),(1,-1))
