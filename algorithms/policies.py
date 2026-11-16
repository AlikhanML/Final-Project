"""Valid-action selection shared by learning and execution."""
import numpy as np


def best_valid_action(values, valid) -> int | None:
    """Return the highest finite value among allowed actions, or None."""
    candidates=np.flatnonzero(valid & np.isfinite(values))
    if not len(candidates):
        return None
    return int(candidates[np.argmax(values[candidates])])


def sample_valid_actions(valid, rng):
    """Uniform independent action samples; rows must contain an allowed action."""
    if not np.all(valid.any(axis=1)):
        raise ValueError('Cannot sample from a state without valid actions.')
    return np.argmax(np.where(valid,rng.random(valid.shape),-1.0),axis=1)


def future_values(q, valid, states, goal):
    """Terminal and actionless states have zero bootstrap value."""
    values=np.where(valid[states],q[states],-np.inf).max(axis=1)
    values[(states==goal)|~np.isfinite(values)]=0.0
    return values
