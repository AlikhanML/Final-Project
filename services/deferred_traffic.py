"""Compute display-only traffic off the Streamlit script thread."""
from concurrent.futures import ThreadPoolExecutor
from environments.traffic import corridor_traffic
from services.traffic_geometry import traffic_bands

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='qadam-traffic')


def _build(world, density, seed, traffic):
    return traffic_bands(world, corridor_traffic(world,density,seed) if traffic is None else traffic)


def poll_traffic(state, key, world, density, seed, traffic=None):
    """Return (bands, pending, error). At most one outstanding job per session.

    Old results are never displayed for a new dataset/configuration/trip.
    Workers receive data only, never Streamlit or session state.
    """
    job=state.get('_traffic_job')
    if job is not None and job['key']!=key:
        if not job['future'].done():
            return [[],[],[],[]], True, None
        job=None
    if job is None:
        job={'key':key,'future':_EXECUTOR.submit(_build,world,density,seed,traffic)}
        state['_traffic_job']=job
        # Always render the map once before publishing a new overlay.
        return [[],[],[],[]], True, None
    if not job['future'].done():
        return [[],[],[],[]], True, None
    try:
        return job['future'].result(), False, None
    except Exception as exc:
        return [[],[],[],[]], False, str(exc)
