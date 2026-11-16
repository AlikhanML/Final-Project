"""Navigation commands. UI provides state and simulation dependency."""
import networkx as nx
from utils.geo import distance
from environments.road_world import nearest
from services.dispatch import select_hospital

def handle_event(state,event,w,simulate_route=None):
    """Only destination is user-controlled; start is always a hospital."""
    if not event or event.get('id')==state.get('nav_event'): return
    state['nav_event']=event.get('id')
    kind=event.get('type');state['nav_error']=''
    if kind=='pick':
        if event.get('target') != 'B':
            state['nav_error']='Старт ауруханадан автоматты таңдалады.';return
        try: point=(float(event['lat']),float(event['lng']))
        except (KeyError,TypeError,ValueError): return
        west,south,east,north=w['source']['bbox']
        if not (south<=point[0]<=north and west<=point[1]<=east):
            state['nav_error']='Шақырту орны жүктелген жол базасынан тыс.';return
        if distance(point,w['coords'][nearest(w,point)])>500:
            state['nav_error']='500 м ішінде қолжетімді жол жоқ. Жолға жақынырақ таңдаңыз.';return
        state['nav_B']=point
        state['nav_A']=None;state['nav_hospital']=None;state['nav_result']=None
        try:
            hospital=select_hospital(w,point)
            state['nav_hospital']=hospital
            state['nav_A']=(hospital['lat'],hospital['lon'])
        except ValueError as exc: state['nav_error']=str(exc)
    elif kind=='reset':
        state['nav_A']=state['nav_B']=state['nav_hospital']=state['nav_result']=None
    elif kind=='route':
        if simulate_route is None:
            raise ValueError('A simulation callback is required for route events.')
        b=state.get('nav_B')
        if b is None:
            state['nav_error']='Алдымен шақырту орнын таңдаңыз.';return
        try:
            hospital=select_hospital(w,b)
            state['nav_hospital']=hospital
            state['nav_A']=(hospital['lat'],hospital['lon'])
            state['nav_result']=simulate_route(hospital['node'],nearest(w,b),*state['nav_config'])
            state['nav_trip_version']=state.get('nav_trip_version',0)+1
        except (ValueError,nx.NetworkXNoPath) as exc:
            state['nav_result']=None;state['nav_error']=str(exc)

