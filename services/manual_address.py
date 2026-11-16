"""User-confirmed label; never changes dispatch or route coordinates."""

from services.destination_label import manual_address_parts


def save_manual_address(state, event):
    point = state.get('nav_B')
    if point is None or list(point) != event.get('point'):
        state['nav_error'] = 'Шақырту нүктесі өзгерді. Мекенжайды қайта енгізіңіз.'
        return
    value = event.get('address')
    if not isinstance(value, str) or not 3 <= len(value.strip()) <= 200:
        state['nav_error'] = 'Көше мен үй нөмірін енгізіңіз (3–200 таңба).'
        return
    if not manual_address_parts(value)[0]:
        state['nav_error'] = 'Көше мен үй нөмірін енгізіңіз.'
        return
    state['nav_address'] = {'label': ' '.join(value.split()), 'status': 'manual',
                            'note': 'Қолмен нақтыланған мекенжай · картадағы нүкте өзгерген жоқ'}
