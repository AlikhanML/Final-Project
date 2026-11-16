"""Макетке негізделген карта интерфейсі; AI логикасы astana.py ішінде сақталған."""
from pathlib import Path
from ui.traffic_layer import traffic_bands
from services.traffic_geometry import pack_traffic_bands
from environments.traffic import corridor_traffic, TRAFFIC_MODEL_VERSION
import json
import os
import hashlib
import numpy as np
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from ui.cache import load_roads, load_session_roads, simulate_roads, simulate_projected
from environments.road_world import nearest
from environments.edge_snap import build_edge_index
from environments.travel_time import prepare_free_flow
from utils.geo import distance
from services.dispatch import select_hospital
from services.edge_events import clear_call, handle_edge_event
from services.city_boundary import (
    city_geometry, OUTSIDE_CITY_MESSAGE, call_exclusion_geometry,
    call_exclusion_message, in_call_exclusion,
)
from services.address_lookup import start_automatic_address, finish_automatic_address, cancel_automatic_address
from services.demo_scenarios import SCENARIOS, queue_scenario, run_queued_scenario
from services.destination_label import destination_label
from services.landmarks import LANDMARKS
from download_city import CITY_FILE, download_city
from services.hospital_allowlist import approved_hospital, APPROVED

nav_component=components.declare_component('qadam_navigation',path=str(Path(__file__).resolve().parents[1]/'frontend'))


@st.cache_data(show_spinner=False)
def street_index(version, _world):
    w=_world;groups={}
    for u,v,edge in w['graph'].edges(data=True):
        name=edge['name']
        if name!='Атаусыз жол': groups.setdefault(name,[]).append(u)
    west,south,east,north=w['source']['bbox']
    result=[{'name':landmark.name,'lat':lat,'lng':lon,'aliases':list(landmark.aliases)}
            for landmark in LANDMARKS for lat,lon in [landmark.point]
            if south<=lat<=north and west<=lon<=east]
    for name,nodes in sorted(groups.items()):
        node=nodes[len(nodes)//2];lat,lon=w['coords'][node]
        if south<=lat<=north and west<=lon<=east:
            result.append({'name':name,'lat':float(lat),'lng':float(lon)})
    return result


@st.cache_data(show_spinner=False)
def road_lines(version, _world):
    w=_world;seen=set();lines=[]
    stride=max(1,(w['graph'].number_of_edges()+3999)//4000)
    for i,(u,v) in enumerate(w['graph'].edges()):
        if i%stride:continue
        key=tuple(sorted((u,v)))
        if key in seen: continue
        seen.add(key);lines.append(w['graph'][u][v]['geometry'])
        if len(lines)>=4000:break # fallback display only; routing retains the whole graph
    return lines






@st.cache_data(max_entries=2,show_spinner=False)
def road_summary(version, _world):
    graph=_world['graph']
    return graph.number_of_edges(),sum(e['speed_limit_kmh'] is not None for _,_,e in graph.edges(data=True))


@st.cache_data(max_entries=3,show_spinner=False)
def city_traffic_preview(version,density,seed,_world):
    return pack_traffic_bands(traffic_bands(_world,corridor_traffic(_world,density,seed),three_colors=True))


@st.fragment(run_every=.5)
def watch_call_address():
    if finish_automatic_address(st.session_state):
        st.rerun()


def main():
    st.markdown('''<style>
    [data-testid="stHeader"]{height:2.5rem}
    .block-container{max-width:none;padding:2.65rem .65rem .5rem}
    iframe{border:0;border-radius:23px}
    @media(max-width:600px){.block-container{padding:2.65rem 0 0}iframe{border-radius:0}}
    </style>''',unsafe_allow_html=True)
    try:
        with st.spinner('Жол графы ашылуда… Алғашқы іске қосу ұзағырақ болуы мүмкін.'):
            w=load_session_roads(st.session_state)
            if 'edge_index' not in w:
                w['edge_index']=build_edge_index(w)
            prepare_free_flow(w)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        st.error(f'Жол базасын ашу мүмкін болмады: {exc}')
        st.info('DOWNLOAD_CITY_WINDOWS.bat арқылы базаны жаңартып, қолданбаны қайта ашыңыз.')
        return
    if st.session_state.get('nav_dataset_version')!=w['dataset_version']:
        cancel_automatic_address(st.session_state)
        for key in list(st.session_state):
            if key.startswith('nav_'): del st.session_state[key]
        st.session_state['nav_dataset_version']=w['dataset_version']
    with st.sidebar:
        st.header('Qadam · AI баптаулары')
        st.subheader('Қорғау сценарийлері')
        st.caption('Картадан шақырту орнын таңдаңыз. Бір батырма баптауларды орнатып, маршрутты есептейді; ойнатуды картадан бастаңыз.')
        scenario_controls=st.container()

        carto_key=st.text_input('CARTO Basemaps API key',value=os.getenv('CARTO_BASEMAP_API_KEY',''),type='password',help='Dark Matter картасын қосады. Кілт браузердегі тайл сұрауларында қолданылады.').strip()
        st.markdown('[CARTO кілтін алу](https://carto.com/basemaps/apikey/)')
        density=st.slider('Кептеліс жүктемесі (модель)',0.,.7,.2,.05,key='demo_density',
                          help='0 — жол ашық. 0.20 — әдепкі қарбалас уақыт сценарийі.')
        sigma=st.slider('GPS шуы, метр',0,100,0,5,key='demo_sigma')
        seed=int(st.number_input('Seed',0,99999,42,key='demo_seed'))
        batches=st.slider('Q-learning batch саны',50,500,100,50,key='demo_batches')
        dynamic=st.checkbox('AI тәжірибесі: жасанды жол бұғаттау',False,key='demo_dynamic')
        if w['source'].get('coverage')=='city':
            st.caption('Астананың қарбалас уақыттағы қозғалысы ашық деректер бойынша модельденеді. '
                       'Жүктеме магистральдарда, қиылыстарда және көпірге кіреберістерде шоғырланады.')
        else:
            st.caption('Шағын картада кептеліс оқу сценарийі бойынша есептеледі.')
        st.caption('Старт: тек №1, №2, №3 қалалық аурухана.')
        for info in APPROVED.values():
            st.caption(info['name']+' — '+info['address'])
        st.caption('Қалалық жол базасы қосылған' if CITY_FILE.exists() else 'Қазір тек шағын аудан базасы бар')
        if st.button('Жолдар мен ауруханаларды жүктеу'):
            try:
                with st.spinner('Қала жолдары жүктелуде. Бірнеше минут кетуі мүмкін…'):
                    download_city()
                st.cache_data.clear()
                cancel_automatic_address(st.session_state)
                for key in list(st.session_state):
                    if key.startswith('nav_'): del st.session_state[key]
                st.rerun()
            except Exception as exc:
                st.error(f'Жүктеу орындалмады: {exc}. Бұрынғы база сақталды.')
    state=st.session_state
    if state.get('nav_control_version') != 'hmm-map-v10-road-class-traffic':
        cancel_automatic_address(state)
        for key in ('nav_A','nav_B','nav_result','nav_hospital','nav_route_world','nav_goal','nav_snap','nav_B_name','nav_address','nav_caller_phone'):
            state[key]=None
        state['nav_control_version']='hmm-map-v10-road-class-traffic'
    cfg=(density,sigma,seed,batches,dynamic)
    if state.get('nav_config')!=cfg or state.get('nav_traffic_model')!=TRAFFIC_MODEL_VERSION:
        state.pop('demo_active',None)
        state['nav_traffic_model']=TRAFFIC_MODEL_VERSION
        state['nav_config']=cfg;state['nav_result']=None
    for key in ['nav_A','nav_B','nav_result']: state.setdefault(key,None)
    language=state.get('qadam_language','kk')
    exclusion_message=call_exclusion_message(language)
    if state['nav_B'] is not None and in_call_exclusion(*state['nav_B']):
        clear_call(state)
        state.pop('demo_pending',None)
        state.pop('demo_active',None)
        state['nav_error']=exclusion_message
    component_key='qadam_map_'+hashlib.sha256(carto_key.encode()).hexdigest()[:12]
    # The keyed component's new value is available before building its payload.
    event=state.get(component_key)
    if (isinstance(event,dict) and event.get('id')
            and event.get('type') in {'pick','geocode','route','reset','address','address_save','contact_save','priority','theme'}
            and event['id']!=state.get('nav_event')):
        if event['type']=='theme':
            state['nav_event']=event['id']
            if event.get('theme') in ('light','dark','aurora'):
                state['qadam_theme']=event['theme'].title()
                st.rerun()
        else:
            with st.spinner('Маршрут есептелуде…' if event['type']=='route' else 'Жаңартылуда…'):
                if event['type']!='contact_save':
                    state.pop('demo_active',None)
                handle_edge_event(state,event,w,simulate_route=simulate_projected)
    with scenario_controls:
        for scenario, (label, _, _, _) in SCENARIOS.items():
            st.button(label, key='scenario_'+scenario,
                      on_click=queue_scenario, args=(state, scenario),
                      disabled=state.get('nav_hospital') is None,
                      use_container_width=True)
    start_automatic_address(state,w)
    finish_automatic_address(state)
    if state.get('demo_pending'):
        with st.spinner('Қорғау сценарийі есептелуде…'):
            run_queued_scenario(state, simulate_projected)
    if state.get('nav_error'):
        st.warning(state['nav_error'])
    a,b=state['nav_A'],state['nav_B'];d=state['nav_result']
    if d is not None and state.get('demo_active'):
        st.caption('Сценарий: '+SCENARIOS[state['demo_active']][0])
        if state['demo_active']=='blocked' and not d.get('blocked'):
            st.info('Бұл маршрутта қауіпсіз бұғаттау нүктесі табылмады. Ұзынырақ маршрут таңдаңыз.')

    payload={'language':language,'city_boundary':city_geometry(),'outside_city_message':OUTSIDE_CITY_MESSAGE,'dataset_version':w['dataset_version'],'hospital':state.get('nav_hospital'),'city':w['source'].get('coverage')=='city','a':a,'b':b,'bbox':w['source']['bbox'],'streets':street_index(w['dataset_version'],w),
             'error':state.get('nav_error',''),'sigma':sigma,'demo_scenario':state.get('demo_active'),'trip_id':state.get('nav_trip_version',0),
             'carto_key':carto_key,'reduced_motion':False,'ack':state.get('nav_event'),'trip':None,'roads':road_lines(w['dataset_version'],w)}
    payload['call_exclusion']=call_exclusion_geometry()
    payload['call_exclusion_message']=exclusion_message
    payload['focus']=state.get('nav_focus')
    payload['caller_phone']=state.get('nav_caller_phone') if b else None
    payload['theme']=state.get('qadam_theme','Dark').lower()
    payload['priority']=state.get('nav_priority','normal')
    payload['snap_a']=w['coords'][nearest(w,a)].tolist() if a else None
    snap=state.get('nav_snap')
    address=state.get('nav_address')
    payload['destination_label']=destination_label(
        w,snap,state.get('nav_B_name'),point=b,address=address,language=payload['language'],
    ) if b else None
    payload['address_status']=address.get('status','found') if address else 'not_requested'
    payload['address_nearby']=bool(address and address.get('nearby'))
    payload['address_note']=address.get('note','') if b and address else ''
    payload['snap_b']=[snap['lat'],snap['lon']] if snap else None
    rw=state.get('nav_route_world') or w
    if d is not None:
        truth=rw['xy'][d['path']]
        rmse=lambda x:float(np.sqrt(np.mean(np.sum((x-truth)**2,axis=1))))
        payload['trip']={'dataset_version':rw['dataset_version'],'priority':d.get('priority','normal'),'congestion_factor':d.get('congestion_factor',1.0),'status':d['status'],'path':rw['coords'][d['path']].tolist(),'base':rw['coords'][d['base']].tolist(),
                         'recovery_events':d['recovery_events'],'relocalizations':d['relocalizations'],'confidence':d['confidence'].tolist(),'control_mode':d['control_mode'],
                         'control_reasons':d['control_reasons'],'gps':d['gps_geo'].tolist(),'hmm':rw['coords'][d['filtered']].tolist(),
                         'blocked':rw['coords'][list(d['blocked'])].tolist() if d['blocked'] else None,
                         'event':d['event'],'fallback':d['fallback_at'],'phases':d['phases'].tolist(),
                         'timestamps_s':d['timestamps_s'].tolist(),'elapsed_s':d['elapsed_s'],'compute_s':d.get('compute_s'),
                         'signal_delays_s':d['signal_delays_s'].tolist() if 'signal_delays_s' in d else [],
                         'stop_delays_s':d.get('stop_delays_s',d['turn_delays_s']).tolist(),
                         'turn_delays_s':d['turn_delays_s'].tolist(),'turn_kinds':d['turn_kinds'],
                         'turn_total_s':d['turn_total_s'],'turn_penalties':d['turn_penalties'],'eta_breakdown':d.get('eta_breakdown'),'eta_plan_s':d['eta_plan_s'],'km':float(d['travel']/1000),'gps_rmse':rmse(d['gps']),'destination_snap':snap,
                         'hmm_rmse':rmse(rw['xy'][d['filtered']]),
                         'reached':d['status']=='reached'}
    # City traffic is an environmental layer, independent of the selected trip.
    traffic_key=(w['dataset_version'],density,seed,TRAFFIC_MODEL_VERSION)
    # Publish a complete overlay in the first map payload, cached by scenario.
    with st.spinner('Кептеліс қабаты жүктелуде…'):
        bands=city_traffic_preview(w['dataset_version']+':'+TRAFFIC_MODEL_VERSION,density,seed,w)
    payload['traffic_pending']=False
    payload['traffic_error']=None
    payload['traffic_packed']=bands
    payload['traffic_key']=traffic_key
    nav_component(payload=payload,key=component_key,default=None)
    if state.get('nav_address_future') is not None:
        watch_call_address()
