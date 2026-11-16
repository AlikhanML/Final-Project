"""Map picks use the existing address catalogue before the online lookup."""
import unittest
from unittest.mock import patch
import networkx as nx
from services.address_lookup import local_address, lookup_address, _cache
from services.destination_label import destination_label


class MapAddressTests(unittest.TestCase):
    def setUp(self):
        _cache.clear()

    @patch('services.address_lookup._lookup', side_effect=AssertionError('Internet must not be used'))
    def test_khan_shatyr_click_resolves_offline(self, online):
        result = lookup_address((51.132505, 71.403861))
        self.assertEqual(result['label'], 'Хан Шатыр · Тұран даңғылы, 37')
        self.assertEqual(result['status'], 'found')
        online.assert_not_called()

    def test_nearby_address_has_distance_note(self):
        rows = ((51.13, 71.41, 'Түркістан көшесі, 10'),)
        with patch('services.address_lookup._local_address_points', return_value=rows):
            result = local_address(51.1301, 71.41)
        self.assertEqual(result['label'], 'Түркістан көшесі, 10')
        self.assertIn('11 м', result['note'])
        self.assertIn('орнын тексеріңіз', result['note'])

    def test_distant_house_is_never_assigned_to_point(self):
        with patch('services.address_lookup._local_address_points', return_value=((51.13, 71.41, 'Абай, 10'),)):
            self.assertIsNone(local_address(51.131, 71.41))

    @patch('services.address_lookup._local_address_points', return_value=())
    @patch('services.address_lookup._lookup', return_value={'label':'Абай, 10','status':'found','note':'OSM'})
    def test_missing_local_address_uses_online_lookup_and_cache(self, online, rows):
        first = lookup_address((51.13, 71.41))
        first['label'] = 'changed externally'
        self.assertEqual(lookup_address((51.13, 71.41))['label'], 'Абай, 10')
        online.assert_called_once_with(51.13, 71.41, timeout=6)

    @patch('services.address_lookup._lookup', return_value={'label':None,'status':'timeout','note':'Offline'})
    def test_explicit_retry_can_fall_back_to_local_address(self, online):
        self.assertEqual(lookup_address((51.132505, 71.403861), force=True)['label'],
                         'Хан Шатыр · Тұран даңғылы, 37')
        online.assert_called_once()

    def test_unknown_address_shows_coordinates(self):
        world = {'graph':nx.DiGraph()}
        self.assertEqual(destination_label(world, None, point=(51.13, 71.41)), '51.130000, 71.410000')

    def test_known_road_remains_a_road_without_an_invented_house(self):
        graph = nx.DiGraph()
        graph.add_edge(1, 2, name='Тұран даңғылы')
        self.assertEqual(destination_label({'graph':graph}, {'edge':(1, 2)}, point=(51.13, 71.41)),
                         'Тұран даңғылы маңы')


if __name__ == '__main__':
    unittest.main()
