import numpy as np
import streamlit as st
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from navigation_style import apply_theme, add_map_chrome
from utils.geo import distance
from environments.road_world import nearest
from ui.cache import load_roads, simulate_roads

def map_figure(w,d,t,layers,start,goal):
    fig=go.Figure()
    def trace(coords,name,color,width=4,mode='lines',size=8):
        fig.add_trace(go.Scattermap(lat=coords[:,0],lon=coords[:,1],mode=mode,name=name,
                                   line=dict(color=color,width=width),marker=dict(color=color,size=size)))
    if d is not None and 'Кептеліс' in layers:
        for low,high,color,label in [(0,.99,'#d6b545','Баяу'),(.99,2,'#ee8a35','Кептеліс'),(2,4,'#df5450','Қатты кептеліс')]:
            lat=[];lon=[]
            for u,a in np.argwhere((d['traffic']>low)&(d['traffic']<=high)&w['valid']):
                v=w['dest'][u,a]
                lat.extend([w['coords'][u,0],w['coords'][v,0],None]);lon.extend([w['coords'][u,1],w['coords'][v,1],None])
            fig.add_trace(go.Scattermap(lat=lat,lon=lon,mode='lines',line=dict(color=color,width=3),name=label,hoverinfo='name'))
    if d is not None:
        if 'A* жоспары' in layers: trace(w['coords'][d['base']],'A* бастапқы маршрут','#7896be',5)
        trace(w['coords'][d['path'][:t+1]],'Жүріп өткен жол','#1679ed',7)
        if 'GPS' in layers: trace(d['gps_geo'][:t+1],'Шулы GPS','#ef7e38',mode='markers',size=6)
        if 'HMM' in layers: trace(w['coords'][d['filtered'][:t+1]],'HMM орын бағасы','#8658cf',mode='markers',size=7)
        if d['blocked'] is not None and d['phases'][t]:
            trace(w['coords'][list(d['blocked'])],'Жабылған жол','#d51f36',9)
        trace(w['coords'][[d['path'][t]]],'Көлік','#1679ed',mode='markers',size=16)
    for node,name,color in [(start,'A · Бастау','#15945b'),(goal,'B · Мақсат','#e95157')]:
        trace(w['coords'][[node]],name,color,mode='markers',size=17)
    fig.update_layout(map=dict(style='open-street-map',center=dict(lat=51.130,lon=71.418),zoom=13.5),
                      height=650,margin=dict(l=0,r=0,t=0,b=0),uirevision=f'{start}-{goal}',
                      legend=dict(orientation='h',y=-.02),font=dict(family='Arial'))
    return fig


def accept_map_click(state, clicked, bbox):
    """Клик → A/B; қайталанған компонент оқиғасы екінші нүктеге айналмайды."""
    if not clicked or state.get('pick_target', 'A') == 'view':
        return False
    point = (float(clicked['lat']), float(clicked['lng']))
    token = (state.get('click_epoch', 0), *point)
    if state.get('last_map_click') == token:
        return False
    state['last_map_click'] = token
    west, south, east, north = bbox
    if not (south <= point[0] <= north and west <= point[1] <= east):
        state['pick_error'] = 'Жасыл шекараның ішінен нүкте таңдаңыз. Бұл ауданнан тыс жол деректері толық емес.'
        return False
    target = state.get('pick_target', 'A')
    state['astana_a' if target == 'A' else 'astana_b'] = point
    state['pick_target'] = 'B' if target == 'A' else 'view'
    state['pick_error'] = ''
    state['astana_result'] = None
    # Жаңа компонент ескі клик мәнін қайта қолданбайды.
    state['click_epoch'] = state.get('click_epoch', 0) + 1
    return True


def clickable_map(w, d, t, layers, a, b, center, zoom):
    m = folium.Map(location=center, zoom_start=zoom, tiles=None,
                   control_scale=True, prefer_canvas=True, zoom_control=False)
    folium.map.CustomPane('dark_tiles',z_index=200).add_to(m)
    folium.TileLayer('OpenStreetMap',name='Қараңғы карта',pane='dark_tiles',show=True).add_to(m)
    folium.TileLayer('OpenStreetMap',name='Жарық карта',show=False).add_to(m)
    folium.map.CustomPane('route_glow',z_index=410).add_to(m)
    from branca.element import MacroElement, Template
    zoom_control=MacroElement()
    zoom_control._template=Template('{% macro script(this, kwargs) %}L.control.zoom({position:"bottomright"}).addTo({{ this._parent.get_name() }});{% endmacro %}')
    m.add_child(zoom_control)
    west,south,east,north = w['source']['bbox']
    folium.Rectangle([(south,west),(north,east)],color='#3ccd79',weight=1,opacity=.5,
                     fill=False,dash_array='6 6',interactive=False).add_to(m)
    if d is not None:
        if 'Кептеліс' in layers:
            # GeoJSON бір қабатта көптеген сегментті жылдам көрсетеді.
            features=[]
            for u,action in np.argwhere((d['traffic']>0)&w['valid']):
                v=w['dest'][u,action];level=d['traffic'][u,action]
                color='#d6b545' if level<1 else '#ee8a35' if level<2 else '#df5450'
                features.append({'type':'Feature','properties':{'color':color},
                    'geometry':{'type':'LineString','coordinates':[
                        w['coords'][u,::-1].tolist(),w['coords'][v,::-1].tolist()]}})
            folium.GeoJson({'type':'FeatureCollection','features':features},
                           style_function=lambda f: {'color':f['properties']['color'],'weight':3},
                           interactive=False).add_to(m)
        if 'A* жоспары' in layers:
            folium.PolyLine(w['coords'][d['base']].tolist(),color='#77a7f2',weight=5,opacity=.8,
                            tooltip='A* бастапқы маршрут').add_to(m)
        if t>0:
            folium.PolyLine(w['coords'][d['path'][:t+1]].tolist(),color='#1679ed',weight=6,
                            tooltip='Жүріп өткен жол').add_to(m)
        if 'GPS' in layers:
            for loc in d['gps_geo'][:t+1]:
                folium.CircleMarker(loc.tolist(),radius=3,color='#ef7e38',fill=True,
                                    fill_opacity=.7,interactive=False).add_to(m)
        if 'HMM' in layers:
            for node in d['filtered'][:t+1]:
                folium.CircleMarker(w['coords'][node].tolist(),radius=3,color='#8658cf',
                                    fill=True,interactive=False).add_to(m)
        if d['blocked'] is not None and d['phases'][t]:
            folium.PolyLine(w['coords'][list(d['blocked'])].tolist(),color='#d51f36',weight=9,
                            tooltip='Жабылған жол').add_to(m)
        position=w['coords'][d['path'][t]].tolist()
        folium.CircleMarker(position,radius=27,color='#2b8aff',weight=0,
                            fill=True,fill_color='#2684ff',fill_opacity=.16,interactive=False).add_to(m)
        folium.Marker(position,tooltip='Көлік',icon=folium.DivIcon(
            html='<div style="background:#207ef1;color:white;border:3px solid white;'
                 'width:38px;height:38px;border-radius:50%;text-align:center;line-height:33px;'
                 'font-size:22px;box-shadow:0 0 0 6px #278aff44,0 0 24px #278aff88">➤</div>',
            icon_size=(38,38),icon_anchor=(19,19))).add_to(m)
    for point,label,color in [(a,'A','#15945b'),(b,'B','#e95157')]:
        if point is None: continue
        snapped=w['coords'][nearest(w,point)]
        folium.PolyLine([point,snapped.tolist()],color=color,weight=2,dash_array='4 5',
                        interactive=False).add_to(m)
        folium.CircleMarker(snapped.tolist(),radius=4,color=color,fill=True,
                            tooltip=f'{label}: жолға бекітілген орын').add_to(m)
        folium.Marker(point,tooltip=f'{label}: таңдалған нүкте',icon=folium.DivIcon(
            html=f'<div style="background:{color};color:white;border:3px solid white;'
                 f'border-radius:50%;width:30px;height:30px;text-align:center;line-height:24px;'
                 f'font:bold 18px Arial;box-shadow:0 2px 7px #888">{label}</div>',
            icon_size=(30,30),icon_anchor=(15,15))).add_to(m)
    folium.LayerControl(position='topright',collapsed=True).add_to(m)
    if d is not None:
        position=w['coords'][d['path'][t]].tolist()
        remaining=len(d['path'])-1-t
        status='Мақсатқа жетті' if remaining==0 and d['path'][-1]==nearest(w,b) else f'Сапар · {remaining} қадам қалды'
        detail=f'Толық сапар: {d["travel"]/1000:.2f} км  ·  Көк — маршрут, күлгін — HMM'
    else:
        position=a if a is not None else center
        status='Старт нүктесін таңдаңыз' if a is None else 'Мақсат нүктесін таңдаңыз' if b is None else 'Екі нүкте таңдалды'
        detail='Картадан A және B таңдаңыз · Төменде маршрутты есептеу'
    add_map_chrome(m,status,detail,position)
    return m


def main():
    apply_theme()
    try: w=load_roads()
    except (OSError,ValueError,nx.NetworkXException) as exc:
        st.error(f'Жол деректері ашылмады: {exc}. ZIP архивін толық шығарыңыз: data бумасы қажет.');return
    with st.sidebar:
        st.subheader('Астана бойынша маршрут')
        st.session_state.setdefault('pick_target','A')
        st.session_state.setdefault('click_epoch',0)
        st.session_state.setdefault('astana_a',None)
        st.session_state.setdefault('astana_b',None)
        a=st.session_state.astana_a;b=st.session_state.astana_b
        st.write('Картадан старт пен мақсатты таңдаңыз:')
        buttons=st.columns(2)
        with buttons[0]:
            if st.button('📍 Старт A',width='stretch'):
                st.session_state.pick_target='A';st.session_state.click_epoch+=1
        with buttons[1]:
            if st.button('🏁 Мақсат B',width='stretch'):
                st.session_state.pick_target='B';st.session_state.click_epoch+=1
        controls=st.columns(2)
        with controls[0]:
            if st.button('↔ Орын ауыстыру',disabled=a is None or b is None,width='stretch'):
                st.session_state.astana_a,st.session_state.astana_b=b,a
                st.session_state.click_epoch+=1;st.session_state.pick_target='view'
                st.rerun()
        with controls[1]:
            if st.button('↺ Тазалау',width='stretch'):
                st.session_state.astana_a=None;st.session_state.astana_b=None
                st.session_state.pick_target='A';st.session_state.click_epoch+=1
                st.session_state.pick_error='';st.rerun()
        if st.button('Хан Шатыр → Бәйтерек · демо',width='stretch'):
            st.session_state.astana_a=(51.13251,71.40387)
            st.session_state.astana_b=(51.12829,71.43046)
            st.session_state.pick_target='view';st.session_state.click_epoch+=1
            st.rerun()
        start=nearest(w,a) if a is not None else None
        goal=nearest(w,b) if b is not None else None
        for label,point,node in [('A',a,start),('B',b,goal)]:
            if point is None: st.caption(f'{label}: картадан таңдаңыз')
            else:
                st.caption(f'{label}: {point[0]:.5f}, {point[1]:.5f} · жолға {distance(point,w["coords"][node]):.0f} м')
        st.caption('Үлкен A/B белгісі — таңдаған орын. Кішкентай нүкте — маршрут басталатын/аяқталатын жол түйіні.')
        with st.expander('AI баптаулары'):
            density=st.slider('Жасанды кептеліс тығыздығы',0.,.7,.2,.05)
            sigma=st.slider('GPS шуы, метр',0,100,20,5)
            seed=int(st.number_input('Seed',0,99999,42))
            batches=st.slider('Q-learning batch саны',500,4000,2000,500)
            dynamic=st.checkbox('Сапар кезінде бір жолды жабу',True)
        layers=st.multiselect('Карта қабаттары',['A* жоспары','Кептеліс','GPS','HMM'],default=['A* жоспары','HMM'])
        run=st.button('↗ Маршрутты есептеу',type='primary',width='stretch',disabled=start is None or goal is None)
        st.info('Карта мен көшелер нақты. Кептеліс, бұғаттау және GPS деректері — симуляция.')
    st.caption('Хан Шатыр – Бәйтерек · Жасыл шекара — маршрут есептелетін аудан')
    sig=(start,goal,density,sigma,seed,batches,dynamic)
    if st.session_state.get('astana_signature')!=sig:
        st.session_state.astana_signature=sig;st.session_state.astana_result=None;st.session_state.astana_step=0
    requested=st.session_state.pop('route_requested',False)
    run=run or requested
    if run:
        if start is None or goal is None:
            st.warning('Картадан екі нүктені таңдаңыз.')
        elif start==goal: st.warning('Екі нүкте бір жол түйініне түсті. Басқа орынды таңдаңыз.')
        else:
            with st.spinner('Нақты жол желісінде AI есептелуде…'):
                st.session_state.astana_result=simulate_roads(*sig)
            st.session_state.astana_step=0
    d=st.session_state.get('astana_result');t=0
    if d is not None:
        t=st.slider('Қозғалыс қадамы',0,len(d['path'])-1,key='astana_step')
        phase='A*' if not d['phases'][t] else 'Q-learning'
        if d['fallback_at'] is not None and t>=d['fallback_at']: phase='A* резерві'
        st.caption(f'Басқару: {phase} · Қадам {t}/{len(d["path"])-1} · HMM ең жоғары сенімі: {d["confidence"][t]:.1%}')
    target=st.session_state.pick_target
    if target=='A': st.info('📍 Картадағы жасыл шекара ішінен СТАРТ нүктесін басыңыз.')
    elif target=='B': st.info('🏁 Енді МАҚСАТ нүктесін басыңыз.')
    else: st.caption('Екі нүкте таңдалды. «Маршрутты есептеу» басыңыз. Өзгерту үшін «Старт A» немесе «Мақсат B» таңдаңыз.')
    error_box=st.empty()
    if st.session_state.get('pick_error'): error_box.warning(st.session_state.pick_error)
    m=clickable_map(w,d,t,layers,a,b,st.session_state.get('map_center',(51.13,71.418)),
                    st.session_state.get('map_zoom',14))
    event=st_folium(m,height=720,use_container_width=True,
                    key=f'astana_picker_{st.session_state.click_epoch}',
                    returned_objects=['last_clicked','center','zoom'])
    if event:
        center=event.get('center')
        if isinstance(center,dict) and 'lat' in center:
            st.session_state.map_center=(center['lat'],center['lng'])
        if event.get('zoom') is not None: st.session_state.map_zoom=event['zoom']
        if accept_map_click(st.session_state,event.get('last_clicked'),w['source']['bbox']):
            st.rerun()
        elif st.session_state.get('pick_error'):
            error_box.warning(st.session_state.pick_error)
    # Карта астындағы негізгі әрекеттер: телефон мен ноутбукте бірдей қолжетімді.
    bar=st.columns([1,1,2,1])
    with bar[0]:
        if st.button('📍 Старт',key='bottom_start',width='stretch'):
            st.session_state.pick_target='A';st.session_state.click_epoch+=1;st.rerun()
    with bar[1]:
        if st.button('🏁 Мақсат',key='bottom_goal',width='stretch'):
            st.session_state.pick_target='B';st.session_state.click_epoch+=1;st.rerun()
    with bar[2]:
        if st.button('↗ Маршрут',key='bottom_route',type='primary',width='stretch',disabled=start is None or goal is None):
            st.session_state.route_requested=True;st.rerun()
    with bar[3]:
        if st.button('↺',key='bottom_reset',help='Таңдауды тазалау',width='stretch'):
            st.session_state.astana_a=None;st.session_state.astana_b=None
            st.session_state.pick_target='A';st.session_state.click_epoch+=1;st.rerun()
    st.caption('Карта және жол деректері: [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright). '
                'Жол желісінің көшірмесі: 16.10.2026. Фондық картаға интернет қажет.')
    if d is not None:
        cols=st.columns(3)
        cols[0].metric('Толық сапар қашықтығы',f'{d["travel"]/1000:.2f} км')
        error=lambda x: np.sqrt(np.mean(np.sum((x-w['xy'][d['path']])**2,axis=1)))
        cols[1].metric('GPS RMSE',f'{error(d["gps"]):.1f} м')
        cols[2].metric('HMM RMSE',f'{error(w["xy"][d["filtered"]]):.1f} м')
        if t==len(d['path'])-1:
            if d['path'][-1]==goal: st.success('Мақсатқа жетті.')
            else: st.error('Қадам лимиті аяқталды; мақсатқа жеткен жоқ.')
        if d['fallback_at'] is not None: st.warning(f'Қадам {d["fallback_at"]}-ден бастап Q саясатының цикліне байланысты A* резерві қолданылды.')
        with st.expander('Маршрут көшелері және AI диагностикасы'):
            streets=[]
            for u,v in zip(d['path'],d['path'][1:]):
                if u!=v:
                    name=w['graph'][u][v]['name']
                    if not streets or streets[-1]!=name: streets.append(name)
            st.write(' → '.join(streets))
            st.line_chart({'Орташа |TD|':d['history']})
            st.caption('Бір индекс = 100 batch. Бұл график оптималдыққа кепілдік бермейді.')
    with st.expander('Нақты карта режимінің моделі'):
        st.write('Қалалық симуляциядағы A* эвристикасы — Haversine қашықтығы / ең үлкен модельдік жылдамдық. Манхэттен эвристикасы бастапқы Grid World режимінде сақталған. '
                 'OSM біржақты жолдары ескерілген; бұрылыс шектеулері, бағдаршамдар мен барлық уақытша ережелер модельденбейді.')
        st.write('Q-learning әрекеті — түйіндегі шығаберістің тұрақты индексі. Сегмент толық жүріп өтіледі; уақыт секундпен өлшенеді; '
                 'кептеліс жол шығынын арттырады. HMM осы әрекеттер мен GPS-тен түйін ықтималдығын есептейді. '
                 'Басқару HMM MAP бағалауына сүйенеді; сенім төмен болса қайта өлшеу үшін тоқтайды.')
        st.write('Қадам ұзындығы — OSM түйіндері арасындағы қашықтық; қадамдар бірдей секундқа тең емес. '
                 'Көрсетілген қашықтық көліктің толық симуляциялық сапарына қатысты. Бұл жедел қызметке арналған дайын навигация емес.')

