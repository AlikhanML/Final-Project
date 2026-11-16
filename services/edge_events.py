"""Destination-edge snapping for the main navigation UI."""
import re

import networkx as nx
from services.city_boundary import in_astana, OUTSIDE_CITY_MESSAGE, in_call_exclusion, call_exclusion_message
from environments.edge_snap import destination_world, build_edge_index, NoRoadInReach
from services.dispatch import NoHospitalPath, reachable_hospital_nodes, select_hospital
from services.address_lookup import cancel_automatic_address, lookup_address
from services.manual_address import save_manual_address
from services.call_priority import set_call_priority
from services.geocoding import geocode_astana
from services.landmarks import find_landmark, landmark_at


def clear_call(state):
    cancel_automatic_address(state)
    state['nav_priority']='normal'
    state.pop('nav_caller_phone', None)
    for key in ('nav_A','nav_B','nav_hospital','nav_result','nav_route_world','nav_snap','nav_goal','nav_B_name','nav_address','nav_focus'):
        state[key]=None


def _save_caller_phone(state, event):
    point = state.get('nav_B')
    call_id = (state.get('nav_focus') or {}).get('id')
    if point is None or list(point) != event.get('point') or call_id != event.get('call_id'):
        state['nav_error'] = 'Шақырту нүктесі өзгерді. Нөмірді қайта енгізіңіз.'
        return
    value = event.get('phone')
    if isinstance(value, str) and re.fullmatch(r'\+7[0-9]{10}', value):
        state['nav_caller_phone'] = value
        return
    state['nav_error'] = '+7 кодынан кейін 10 цифр енгізіңіз.'


def handle_edge_event(state,event,world,simulate_route):
    if not event or event.get('id')==state.get('nav_event'):return
    state['nav_event']=event.get('id');state['nav_error']=''
    kind=event.get('type')
    geocoded = None
    if kind=='geocode':
        query = event.get('query')
        if landmark := find_landmark(query):
            lat, lng = landmark.point
            event={**event,'target':'B','lat':lat,'lng':lng,'place_name':landmark.name}
        else:
            try:
                geocoded = geocode_astana(query)
            except ValueError as exc:
                state['nav_error']=str(exc)
                return
            event={**event,'target':'B','lat':geocoded['lat'],'lng':geocoded['lng'],
                   'place_name':geocoded['label']}
        kind='pick'
    if kind=='priority':
        had_route=state.get('nav_result') is not None
        previous=state.get('nav_priority','normal')
        set_call_priority(state,event.get('priority'))
        if state.get('nav_error') or previous==state.get('nav_priority') or not had_route:
            return
        # Recompute once when switching an already calculated call.
        kind='route'
    if kind=='reset':
        clear_call(state)
        return
    if kind=='pick':
        if event.get('target')!='B':
            state['nav_error']='Старт ауруханадан автоматты таңдалады.';return
        try:
            point=(float(event['lat']),float(event['lng']))
            if not in_astana(*point):
                raise ValueError(OUTSIDE_CITY_MESSAGE)
            if in_call_exclusion(*point):
                raise ValueError(call_exclusion_message(state.get('qadam_language')))
            west,south,east,north=world['source']['bbox']
            if not (south<=point[0]<=north and west<=point[1]<=east):
                raise ValueError('Шақырту орны жүктелген жол базасынан тыс.')
            if 'edge_index' not in world:
                world['edge_index']=build_edge_index(world)
            route_world,goal,snap=destination_world(world,point,include_road_graph=False)
            address={'label':None,'status':'selected','note':''}
            if not (geocoded and geocoded.get('house_number')) and landmark_at(point):
                address['status']='landmark'
            elif geocoded:
                address={**geocoded,'status':'found','note':'© OpenStreetMap · Nominatim'}
            # Accept the call point even if there is no reachable hospital.
            cancel_automatic_address(state)
            state.setdefault('nav_priority','normal')
            state.pop('nav_caller_phone', None)
            state.update(nav_B=point,nav_B_name=event.get('place_name'),nav_A=None,nav_hospital=None,nav_result=None,
                         nav_route_world=route_world,nav_goal=goal,nav_snap=snap,
                         nav_address=address,
                         nav_focus={'id':event.get('id'),'lat':point[0],'lng':point[1]})
            try:
                hospital = select_hospital(route_world, point, goal=goal, hospital_world=world)
            except NoHospitalPath:
                hospital = None
            if hospital is None:
                # Drop the rejected graph copy before constructing the next overlay.
                state['nav_route_world'] = None
                del route_world
                reachable = reachable_hospital_nodes(world)
                route_world, goal, snap = destination_world(world, point, reachable=reachable, include_road_graph=False)
                hospital = select_hospital(route_world, point, goal=goal, hospital_world=world)
                state.update(nav_route_world=route_world, nav_goal=goal, nav_snap=snap)
            state['nav_hospital']=hospital
            state['nav_A']=(hospital['lat'],hospital['lon'])
            _calculate_route(state,simulate_route)
        except NoRoadInReach as exc:
            state['nav_snap'] = state['nav_goal'] = None
            state['nav_error'] = exc.messages.get(state.get('qadam_language'), str(exc))
        except (ValueError,KeyError,TypeError,nx.NetworkXNoPath) as exc:
            state['nav_error']=str(exc)
    elif kind=='address_save':
        save_manual_address(state,event)
        if not state['nav_error']:
            cancel_automatic_address(state)
    elif kind=='contact_save':
        _save_caller_phone(state,event)
    elif kind=='address':
        if state.get('nav_B') is not None:
            cancel_automatic_address(state)
            state['nav_address']=lookup_address(state['nav_B'],force=True,world=world)
    elif kind=='route':
        if state.get('nav_B') is None or state.get('nav_hospital') is None:
            state['nav_error']='Алдымен жолы бар шақырту орнын таңдаңыз.';return
        _calculate_route(state,simulate_route)


def _calculate_route(state, simulate_route):
    try:
        route_world=state['nav_route_world'];hospital=state['nav_hospital']
        state['nav_result']=simulate_route(route_world,hospital['node'],state['nav_goal'],
            *state['nav_config'],**({'priority':'urgent'} if state.get('nav_priority')=='urgent' else {}))
        state['nav_trip_version']=state.get('nav_trip_version',0)+1
    except (ValueError,TimeoutError,nx.NetworkXNoPath) as exc:
        state['nav_result']=None;state['nav_error']=str(exc)
