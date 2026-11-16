"""Road state transitions and nearest-node lookup."""
import numpy as np

def nearest(world, coord):
    """Exact legacy weighted-distance nearest node with optional KD candidates."""
    coord=np.asarray(coord,dtype=float)
    if coord.shape!=(2,) or not np.isfinite(coord).all():
        raise ValueError('Invalid destination coordinates')
    scale=np.array([1.,abs(np.cos(np.radians(coord[0])))])
    tree=world.get('spatial_index')
    coords=world['coords']
    if tree is None or scale.min()<1e-6:
        candidates=np.arange(len(coords))
    else:
        _,seed=tree.query(coord)
        radius=np.linalg.norm((coords[seed]-coord)*scale)/scale.min()
        candidates=np.array(sorted(tree.query_ball_point(coord,radius*(1+1e-12)+1e-12)))
    distance2=np.sum(((coords[candidates]-coord)*scale)**2,axis=1)
    return int(candidates[np.argmin(distance2)])


def transition_table(world,blocked):
    table=world['dest'].copy();valid=world['valid'].copy()
    if blocked is not None:
        u,v=blocked
        valid[u,table[u]==v]=False
        table[u,table[u]==v]=u
    return table,valid

