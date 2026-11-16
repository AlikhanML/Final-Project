"""Repeatable defense presets; use the user's selected call and approved hospital."""
import networkx as nx

SCENARIOS = {
    'normal': ('Қалыпты шақырту', .2, 0, False),
    'blocked': ('Жол бұғатталды', .2, 0, True),
    'gps': ('GPS шуы', .2, 30, False),
}


def queue_scenario(state, scenario):
    """Streamlit callback: change widget values before the next script run."""
    _, density, sigma, dynamic = SCENARIOS[scenario]
    state.update(demo_density=density, demo_sigma=sigma, demo_dynamic=dynamic,
                 demo_seed=42, demo_batches=100, demo_pending=scenario)


def run_queued_scenario(state, simulate):
    """Compute once; never fabricate successful arrival or a closure."""
    scenario = state.pop('demo_pending', None)
    if scenario is None:
        return
    state['demo_active'] = scenario
    state['nav_priority'] = 'normal'
    state['nav_result'] = None
    state['nav_error'] = ''
    if state.get('nav_hospital') is None or state.get('nav_goal') is None:
        state['nav_error'] = 'Алдымен ауруханадан жолы бар шақырту орнын таңдаңыз.'
        return
    try:
        result = simulate(state['nav_route_world'], state['nav_hospital']['node'],
                          state['nav_goal'], *state['nav_config'])
        state['nav_result'] = result
        state['nav_trip_version'] = state.get('nav_trip_version', 0) + 1
    except (ValueError, TimeoutError, nx.NetworkXNoPath) as exc:
        state['nav_error'] = str(exc)
