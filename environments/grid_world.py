"""Grid movement and deterministic environment generation."""
import numpy as np
MOVES = np.array([[-1,0],[0,1],[1,0],[0,-1]])

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def step(grid, pos, action):
    r, c = np.asarray(pos) + MOVES[action]
    n = len(grid)
    if 0 <= r < n and 0 <= c < n and not grid[r, c]:
        return (int(r), int(c))
    return tuple(pos)


def make_world(n, density, seed):
    rng = np.random.default_rng(seed)
    grid = rng.random((n, n)) < 0.18
    # Демонстрацияға бастапқы қолжетімді жол қалдырамыз.
    grid[0, :] = False
    grid[:, -1] = False
    traffic = (rng.random((n, n)) < density) * rng.integers(2, 7, (n, n))
    traffic[grid] = 0
    traffic[0, 0] = traffic[-1, -1] = 0
    return grid, traffic.astype(float)

