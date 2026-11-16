import unittest
from unittest.mock import patch
from ui.cache import load_session_roads

class SessionCacheTests(unittest.TestCase):
    def test_reuses_private_world_until_identity_changes(self):
        state={}
        with patch('ui.cache.active_identity',return_value=('file','v1')) as identity, \
             patch('ui.cache.load_cached_world',side_effect=lambda *args:{'version':args[1]}) as load:
            first=load_session_roads(state)
            self.assertIs(first,load_session_roads(state));self.assertEqual(load.call_count,1)
            other=load_session_roads({});self.assertIsNot(first,other)
            identity.return_value=('file','v2')
            updated=load_session_roads(state)
            self.assertEqual(updated['version'],'v2');self.assertIsNot(first,updated)
