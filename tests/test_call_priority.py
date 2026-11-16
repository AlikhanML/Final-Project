import unittest
from services.call_priority import set_call_priority

class CallPriorityTests(unittest.TestCase):
    def test_invalidates_route(self):
        route = object()
        state = {'nav_B': (51, 71), 'nav_result': route}
        for priority in ('urgent', 'normal'):
            set_call_priority(state, priority)
            self.assertEqual(state['nav_priority'], priority)
            self.assertIsNone(state['nav_result'])
    def test_requires_destination(self):
        state = {}
        set_call_priority(state, 'urgent')
        self.assertNotIn('nav_priority', state)
        self.assertTrue(state['nav_error'])
    def test_invalid_values(self):
        for value in ('fastest', None, [], 1):
            state = {'nav_B': (51, 71), 'nav_priority': 'normal'}
            set_call_priority(state, value)
            self.assertEqual(state['nav_priority'], 'normal')
            self.assertTrue(state['nav_error'])
