"""Simulation priority: road yielding reduces congestion delay only."""
PRIORITIES = {'normal': 'Қалыпты', 'urgent': 'Шұғыл'}


def set_call_priority(state: dict, value: str) -> None:
    """Validate priority; discard results calculated for a different mode."""
    if not isinstance(value, str) or value not in PRIORITIES:
        state['nav_error'] = 'Шақырту басымдығы дұрыс таңдалмады.'
        return
    if state.get('nav_B') is None:
        state['nav_error'] = 'Алдымен шақырту орнын таңдаңыз.'
        return
    if state.get('nav_priority','normal') != value:
        state['nav_result'] = None
    state['nav_priority'] = value


def congestion_factor(priority: str) -> float:
    """Educational assumption: urgent vehicles incur 35% of congestion delay."""
    if priority not in PRIORITIES:
        raise ValueError('Unknown call priority')
    return .35 if priority == 'urgent' else 1.0
