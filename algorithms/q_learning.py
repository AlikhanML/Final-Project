"""Tabular learning for grid and road environments."""
import numpy as np
from time import perf_counter
from environments.grid_world import step
from environments.road_world import transition_table
from algorithms.policies import sample_valid_actions, future_values
from environments.travel_time import action_seconds

def train_q(grid, traffic, goal, seed, sweeps=1800, initial=None):
    n = len(grid)
    cells = np.argwhere(~grid)
    ids = cells[:, 0] * n + cells[:, 1]
    target = goal[0] * n + goal[1]
    next_ids = np.empty((len(ids), 4), dtype=int)
    for i, cell in enumerate(cells):
        for a in range(4):
            nxt = step(grid, cell, a)
            next_ids[i, a] = nxt[0] * n + nxt[1]
    q = np.zeros((n*n, 4)) if initial is None else initial.copy()
    q[target] = 0
    q[grid.ravel()] = 0
    valid=np.zeros_like(q,dtype=bool)
    valid[ids]=next_ids != ids[:,None]
    valid[target]=False
    q[~valid]=0
    active=valid[ids].any(axis=1)
    ids=ids[active];next_ids=next_ids[active]
    visits = np.zeros_like(q)
    rng = np.random.default_rng(seed)
    history = []
    for k in range(sweeps):
        if not len(ids):
            break
        actions = sample_valid_actions(valid[ids],rng)
        intended = next_ids[np.arange(len(ids)), actions]
        nxt = np.where(rng.random(len(ids)) < 0.9, intended, ids)
        collision = intended == ids
        reward = -1.0 - traffic.ravel()[nxt] - 5.0 * collision
        reward[nxt == target] += 100.0
        reward[ids == target] = 0
        # Terminal күйде bootstrap жоқ.
        future = future_values(q,valid,nxt,target)
        delta = reward + 0.97 * future - q[ids, actions]
        visits[ids, actions] += 1
        alpha = 0.6 / (1 + visits[ids, actions] / 100)
        q[ids, actions] += alpha * delta
        q[target] = 0
        if k % 50 == 0:
            history.append(float(np.mean(np.abs(delta[ids != target]))))
    return q, history


def q_train(world,goal,blocked,traffic,seed,batches):
    table,valid=transition_table(world,blocked)
    n,k=table.shape
    valid[goal]=False
    active=np.flatnonzero(valid.any(axis=1))
    seconds=action_seconds(world,traffic)
    rng=np.random.default_rng(seed)
    q=np.zeros((n,k));visits=np.zeros((n,k));history=[]
    for batch in range(batches):
        if not len(active): break
        ids=active if len(active)<=8000 else rng.choice(active,8000,replace=False)
        act=sample_valid_actions(valid[ids],rng)
        intended=table[ids,act]
        # Road actions traverse a segment. No per-segment random waits:
        # adding extra OSM vertices must not add artificial stopping time.
        nxt=intended
        costs=seconds[ids,act]
        reward=-costs
        future=future_values(q,valid,nxt,goal)
        # Episodic shortest-path objective: all costs are in seconds.
        delta=reward+future-q[ids,act]
        visits[ids,act]+=1
        q[ids,act]+=(.6/(1+visits[ids,act]/100))*delta
        q[goal]=0
        if batch%100==0: history.append(float(np.mean(np.abs(delta))))
    return q,history



def q_train_turns(model,goal,blocked,seed,batches, *, max_updates=None):
    """Tabular Q-learning on incoming-edge states, with seconds incl. turns."""
    valid=model.allowed(blocked,goal)
    active=np.flatnonzero(valid.any(axis=1));q=np.zeros_like(model.costs);visits=np.zeros_like(q)
    rng=np.random.default_rng(seed);history=[]
    updates=0
    for batch in range(batches):
        if model.deadline is not None and perf_counter()>=model.deadline:break
        if not len(active):break
        size=min(len(active),8000)
        if max_updates is not None:size=min(size,max_updates-updates)
        if size<=0:break
        ids=active if size==len(active) else rng.choice(active,size,replace=False)
        updates+=size
        actions=sample_valid_actions(valid[ids],rng)
        nxt=model.next_ids[ids,actions]
        future=np.where(valid[nxt],q[nxt],-np.inf).max(axis=1)
        future[~np.isfinite(future)]=0.
        delta=-model.costs[ids,actions]+future-q[ids,actions]
        visits[ids,actions]+=1
        q[ids,actions]+=.6/(1+visits[ids,actions]/100)*delta
        if batch%100==0:history.append(float(np.mean(np.abs(delta))))
    return q,history
