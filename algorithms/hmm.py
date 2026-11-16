"""Observation filtering; no access to simulator ground truth."""
import numpy as np
from environments.grid_world import step

def hmm_filter(observations, actions, grids, initial_grid, sigma):
    n = len(initial_grid)
    coords = np.indices((n, n)).reshape(2, -1).T
    belief = (~initial_grid).ravel().astype(float)
    belief /= belief.sum()  # Алғашқы орын алдын ала белгісіз.
    estimates, beliefs = [], []
    for t, obs in enumerate(observations):
        grid = initial_grid if t == 0 else grids[t-1]
        if t:
            prediction = np.zeros(n*n)
            for sid, cell in enumerate(coords):
                if grid[tuple(cell)]:
                    continue
                nxt = step(grid, cell, actions[t-1])
                prediction[nxt[0]*n+nxt[1]] += 0.9*belief[sid]
                prediction[sid] += 0.1*belief[sid]
            belief = prediction
        valid = (~grid).ravel()
        distance2 = np.sum((coords - obs)**2, axis=1)
        if sigma == 0:
            likelihood = (distance2 < 1e-12).astype(float)
            posterior = belief * likelihood
        else:
            # Log-space: өте кішкентай ықтималдықтардан underflow болдырмау.
            logp = np.full(n*n, -np.inf)
            supported = (belief > 0) & valid
            logp[supported] = np.log(belief[supported]) - distance2[supported]/(2*sigma**2)
            maximum = np.max(logp)
            posterior = np.exp(logp-maximum) if np.isfinite(maximum) else np.zeros(n*n)
        if posterior.sum() == 0:
            # Модель/сенсор қайшылығы: жарамды ең жақын ұяшыққа re-localization.
            posterior = np.zeros(n*n)
            posterior[np.argmin(np.where(valid, distance2, np.inf))] = 1
        belief = posterior/posterior.sum()
        estimates.append(coords[np.argmax(belief)])
        beliefs.append(belief.reshape(n, n).copy())
    return np.array(estimates), np.array(beliefs)


def filter_roads(world,gps,actions,tables,sigma, *, move_probability=0.9):
    """Дискретті түйіндер бойынша HMM. Нақты жол функцияға берілмейді."""
    if not 0<=move_probability<=1: raise ValueError('Invalid transition probability.')
    xy=world['xy'];n=len(xy)
    belief=np.ones(n)/n;estimates=[];confidence=[]
    for t,obs in enumerate(gps):
        if t:
            next_ids=tables[t-1][:,actions[t-1]]
            belief=(1-move_probability)*belief+move_probability*np.bincount(next_ids,weights=belief,minlength=n)
        d2=np.sum((xy-obs)**2,axis=1)
        if sigma==0:
            posterior=belief*(d2<1e-8)
        else:
            logp=np.full(n,-np.inf);mask=belief>0
            logp[mask]=np.log(belief[mask])-d2[mask]/(2*sigma**2)
            maximum=logp.max()
            posterior=np.exp(logp-maximum) if np.isfinite(maximum) else np.zeros(n)
        if posterior.sum()==0:
            posterior=np.zeros(n);posterior[np.argmin(d2)]=1
        belief=posterior/posterior.sum()
        estimates.append(int(np.argmax(belief)));confidence.append(float(belief.max()))
    return np.array(estimates),np.array(confidence)



class OnlineRoadHMM:
    """Online Gaussian GPS filter with command-conditioned transitions.

    A small uniform recovery prior prevents an erroneous early localization
    from becoming irreversible. Each update consumes only a sensor reading
    and the command transition map, never simulator ground truth.
    """
    def __init__(self, xy: np.ndarray, sigma: float, recovery: float = .01):
        self.xy = np.asarray(xy, dtype=float)
        if not len(self.xy) or not np.isfinite(self.xy).all():
            raise ValueError('Invalid road coordinates')
        if not np.isfinite(sigma) or sigma < 0 or not 0 <= recovery <= 1:
            raise ValueError('Invalid observation model')
        self.sigma, self.recovery = sigma, recovery
        self.belief = np.full(len(xy), 1/len(xy))

    def update(self, observation: np.ndarray, next_ids=None, *, observation_sigma=None, source_nodes=None) -> np.ndarray:
        sigma=self.sigma if observation_sigma is None else float(observation_sigma)
        if not np.isfinite(sigma) or sigma<0:raise ValueError("Invalid observation sigma")
        if next_ids is not None:
            weights=self.belief if source_nodes is None else self.belief[source_nodes]
            self.belief = np.bincount(next_ids, weights=weights, minlength=len(self.xy))
        prior = (1-self.recovery)*self.belief + self.recovery/len(self.xy)
        obs = np.asarray(observation, dtype=float)
        if obs.shape != (2,) or not np.isfinite(obs).all():
            raise ValueError('Invalid GPS observation')
        x,y=self.xy.T
        d2 = (x-obs[0])**2+(y-obs[1])**2
        if sigma == 0:
            posterior = prior*(d2 < 1e-8)
        else:
            logp = np.log(np.maximum(prior, np.finfo(float).tiny))-d2/(2*sigma**2)
            posterior = np.exp(logp-logp.max())
        total=posterior.sum()
        if total == 0:
            posterior = np.zeros(len(prior));posterior[np.argmin(d2)] = 1
            total=1.
        self.belief = posterior/total
        return self.belief.copy()
