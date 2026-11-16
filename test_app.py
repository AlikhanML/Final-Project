"""Негізгі математикалық қасиеттер мен шеткі баптауларды тексеру."""
import unittest
from collections import deque
import numpy as np
from app import astar, step, make_world, simulate

class RouteTests(unittest.TestCase):
    def test_astar_matches_bfs(self):
        for seed in range(10):
            grid, _ = make_world(12, .4, seed)
            queue, seen = deque([((0, 0), 0)]), {(0, 0)}
            while queue:
                pos, distance = queue.popleft()
                if pos == (11, 11):
                    self.assertEqual(len(astar(grid, (0, 0), pos))-1, distance)
                    break
                for action in range(4):
                    nxt = step(grid, pos, action)
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append((nxt, distance+1))

    def test_simulation(self):
        for n, density, sigma, seed, dynamic in [
            (12, .25, 1, 42, True), (8, 0, 0, 1, False), (24, .7, 3, 17, True)
        ]:
            with self.subTest(n=n, sigma=sigma):
                d = simulate(n, density, sigma, seed, 1800, dynamic)
                self.assertEqual(tuple(d['path'][-1]), (n-1, n-1))
                self.assertTrue(np.allclose(d['beliefs'].sum(axis=(1, 2)), 1))
                self.assertTrue(np.all(np.abs(np.diff(d['path'], axis=0)).sum(axis=1) <= 1))
                for pos, changed in zip(d['path'], d['phases']):
                    grid = d['new'] if changed else d['grid']
                    self.assertFalse(grid[tuple(pos)])
                if sigma == 0:
                    np.testing.assert_array_equal(d['filtered'], d['path'])

    def test_no_route(self):
        grid = np.zeros((4, 4), dtype=bool)
        grid[1, :] = True
        self.assertEqual(astar(grid, (0, 0), (3, 3)), [])

if __name__ == '__main__':
    unittest.main()
