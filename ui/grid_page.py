import io
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st
from ui.cache import simulate

def draw(ax, grid, traffic, title):
    n = len(grid)
    ax.imshow(np.ma.masked_where(grid, traffic), cmap='YlOrRd', vmin=0, vmax=6)
    ax.imshow(np.ma.masked_where(~grid, grid), cmap='gray_r', vmin=0, vmax=1)
    ax.scatter([0, n-1], [0, n-1], c=['limegreen', 'purple'], s=80, marker='s')
    ax.set(title=title, xlabel='Баған (x)', ylabel='Жол (y)')
    ax.set_xticks(np.arange(-.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-.5, n, 1), minor=True)
    ax.grid(which='minor', alpha=.18)


def line(ax, points, label, color, **kwargs):
    ax.plot(points[:, 1], points[:, 0], label=label, color=color, **kwargs)


def city_map(d, t, layers, start, goal, vehicle, revision):
    n = len(d['grid'])
    grid = d['new'] if d['phases'][t] else d['grid']
    traffic = d['traffic2'] if d['phases'][t] else d['traffic']
    fig = go.Figure()
    shapes = []
    # Қозғалыс түйіндері ақ жолдардың қиылысында орналасады.
    # Жол екі бос ұяшықты ғана жалғайды: карта мен граф сәйкес.
    rng = np.random.default_rng(7)
    for r in range(n-1):
        for c in range(n-1):
            park = (r*7+c*3) % 11 == 0
            shapes.append(dict(type='rect', x0=c+.16, x1=c+.84,
                               y0=r+.16, y1=r+.84,
                               fillcolor='#cee3bd' if park else '#e3dfd5',
                               line=dict(color='#c3d4b6' if park else '#d2cec5', width=1), layer='below'))
            if not park:
                inset = float(rng.uniform(.22, .3))
                shapes.append(dict(type='rect', x0=c+inset, x1=c+.74,
                                   y0=r+inset, y1=r+.73, fillcolor='#d2cec6',
                                   line=dict(color='#c7c2b8', width=1), layer='below'))
    road_x, road_y = [], []
    traffic_segments = {2: ([], []), 4: ([], []), 6: ([], [])}
    for r, c in np.argwhere(~grid):
        for dr, dc in [(0, 1), (1, 0)]:
            nr, nc = r+dr, c+dc
            if nr < n and nc < n and not grid[nr, nc]:
                road_x.extend([c, nc, None]); road_y.extend([r, nr, None])
                cost = max(traffic[r, c], traffic[nr, nc])
                if cost > 0:
                    key = 2 if cost <= 2 else 4 if cost <= 4 else 6
                    traffic_segments[key][0].extend([c, nc, None])
                    traffic_segments[key][1].extend([r, nr, None])
    fig.add_trace(go.Scatter(x=road_x, y=road_y, mode='lines', line=dict(color='white', width=10),
                             hoverinfo='skip', showlegend=False))
    if 'Кептеліс' in layers:
        for level, color in [(2, '#c2ce48'), (4, '#f0ac45'), (6, '#e67666')]:
            x, y = traffic_segments[level]
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(color=color, width=4),
                                    name={2:'Баяу қозғалыс',4:'Кептеліс',6:'Қатты кептеліс'}[level], hoverinfo='name'))
    if 'A* жоспары' in layers:
        p = d['baseline']
        fig.add_trace(go.Scatter(x=p[:,1], y=p[:,0], mode='lines', name='Бастапқы A*',
                                 line=dict(color='#849db9', width=4, dash='dot')))
    p = d['path'][:t+1]
    # Ақ контур маршрутты ғимараттар мен кептелістен ажыратады.
    fig.add_trace(go.Scatter(x=p[:,1], y=p[:,0], mode='lines', showlegend=False,
                            hoverinfo='skip', line=dict(color='white', width=11)))
    fig.add_trace(go.Scatter(x=p[:,1], y=p[:,0], mode='lines', name='Жүріп өткен жол',
                            line=dict(color='#2385f5', width=7)))
    if 'GPS өлшемдері' in layers:
        p = d['gps'][:t+1]
        fig.add_trace(go.Scatter(x=p[:,1], y=p[:,0], mode='markers', name='Шулы GPS',
                                marker=dict(color='#ee815e',size=6,opacity=.7)))
    if 'HMM бағасы' in layers:
        p = d['filtered'][:t+1]
        fig.add_trace(go.Scatter(x=p[:,1], y=p[:,0], mode='lines+markers', name='HMM бағасы',
                                line=dict(color='#7957ca',width=2,dash='dot'),marker=dict(size=5)))
    if 'HMM сенімі' in layers:
        belief = np.where(d['beliefs'][t] > .001, d['beliefs'][t], np.nan)
        fig.add_trace(go.Heatmap(z=belief, zmin=0, zmax=1, opacity=.55,
                                colorscale='Purples',showscale=False,name='HMM сенімі',
                                hovertemplate='Баған %{x}, жол %{y}<br>P=%{z:.3f}<extra></extra>'))
    closed = np.argwhere(grid)
    fig.add_trace(go.Scatter(x=closed[:,1],y=closed[:,0],mode='markers',name='Жабық ұяшық',
                            marker=dict(symbol='x',size=9,color='#aaa69d'),
                            hovertemplate='Жабық ұяшық (%{y}, %{x})<extra></extra>'))
    if d['blocked'] is not None and d['phases'][t]:
        r,c = d['blocked']
        fig.add_trace(go.Scatter(x=[c],y=[r],mode='markers',name='Жаңа бұғат',
                                marker=dict(symbol='x',size=20,color='#ef5552',line=dict(width=3))))
    for pos, label, color in [(start,'A','#263e37'),(goal,'B','#21a366')]:
        fig.add_trace(go.Scatter(x=[pos[1]], y=[pos[0]], mode='markers+text',
                                text=[label],textfont=dict(color='white',size=14),
                                marker=dict(size=30,color=color,line=dict(color='white',width=3)),
                                name='Бастау' if label=='A' else 'Мақсат',showlegend=False))
    pos = d['path'][t]
    fig.add_trace(go.Scatter(x=[pos[1]],y=[pos[0]],mode='markers',name=vehicle,
                            marker=dict(size=20,color='#2385f5',symbol='diamond',
                                        line=dict(color='white',width=3)),
                            hovertemplate='Көлік: (%{y}, %{x})<extra></extra>'))
    fig.update_layout(height=660,margin=dict(l=12,r=12,t=12,b=12),
                      paper_bgcolor='#f2f0e9',plot_bgcolor='#f2f0e9',shapes=shapes,
                      dragmode='pan',uirevision=revision,
                      font=dict(family='Arial',color='#35443f'),
                      legend=dict(orientation='h',yanchor='top',y=-.01,x=0,
                                  bgcolor='rgba(255,255,255,.88)',font=dict(size=11)),
                      xaxis=dict(visible=False,range=[-.7,n-.3],fixedrange=False,constrain='domain'),
                      yaxis=dict(visible=False,range=[n-.3,-.7],scaleanchor='x',scaleratio=1,fixedrange=False))
    return fig


def grid_main():
    st.set_page_config(page_title='Qadam • Smart Route',page_icon='🧭',layout='wide',initial_sidebar_state='expanded')
    st.markdown('''<style>
    .stApp {background:#f7f8fa;color:#20352b}
    .block-container {padding:1.2rem 1.5rem 2rem;max-width:1800px}
    [data-testid="stSidebar"] {background:#fff;border-right:1px solid #e6eae6}
    [data-testid="stSidebar"] .block-container {padding:1rem}
    h1,h2,h3 {letter-spacing:-.035em}
    div.stButton>button[kind="primary"] {background:#24a568;border:0;border-radius:12px}
    [data-testid="stMetric"] {background:white;border:1px solid #e6eae6;border-radius:14px;padding:12px 16px}
    [data-testid="stMetricValue"] {font-size:1.5rem}
    [data-testid="stPlotlyChart"] {border-radius:18px;overflow:hidden;border:1px solid #dedfd8}
    .brand {font-size:29px;font-weight:800;letter-spacing:-1.2px;color:#163e2d;margin-bottom:0}
    .brand span {color:#23a568}.sub {color:#84918a;font-size:12px;margin-bottom:22px}
    .route-card {background:#f2faf5;border:1px solid #cfe8d8;border-radius:14px;padding:16px;margin:14px 0}
    .route-card b {color:#187a48;font-size:18px}.route-card p {margin:5px 0;color:#62746a;font-size:13px}
    .tag {display:inline-block;background:#e9f5ed;color:#24834f;border-radius:20px;padding:5px 12px;font-size:12px}
    </style>''',unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="brand">qadam<span>↗</span></div><div class="sub">EMERGENCY SMART ROUTE</div>',unsafe_allow_html=True)
        st.subheader('Маршрут құру')
        vehicle = st.radio('Көлік түрі',['🚑 Жедел жәрдем','🚁 Дрон-курьер'],horizontal=True)
        with st.expander('Қала және AI баптаулары'):
            n = st.slider('Сетка өлшемі',8,24,12)
            density = st.slider('Кептеліс тығыздығы',0.0,.7,.25,.05)
            sigma = st.slider('GPS шуы (σ, ұяшық)',0.0,3.0,1.0,.1)
            seed = int(st.number_input('Кездейсоқтық seed',0,99999,42))
            sweeps = st.slider('Q-learning оқыту batch саны',500,4000,1800,100)
            dynamic = st.checkbox('Кенет бұғаттау',True)
        places = {'Жедел жәрдем станциясы':(0,0),'Солтүстік жеткізу пункті':(0,n//2),
                  'Орталық емхана':(n//2,n-1),'Қалалық аурухана':(n-1,n-1)}
        start_name = st.selectbox('A · Қай жерден?',list(places),index=0)
        goal_name = st.selectbox('B · Қай жерге?',list(places),index=3)
        start,goal = places[start_name],places[goal_name]
        st.caption('Нысандар — модельдік қаладағы демо орындар. Екі көлік те бір 2D қозғалыс моделін қолданады.')
        if start==goal:
            st.info('Бастау мен мақсат үшін әртүрлі орын таңдаңыз.')
            st.stop()
        signature=(n,density,sigma,seed,sweeps,dynamic,start,goal)
        if st.session_state.get('trip_signature') != signature:
            st.session_state.trip_signature=signature
            st.session_state.trip_step=0
        if st.button('↗ Маршрутты басынан көрсету',type='primary',width='stretch'):
            st.session_state.trip_step=0
        with st.spinner('Маршрут есептелуде…'):
            d=simulate(n,density,sigma,seed,sweeps,dynamic,start,goal)
        reached=tuple(d['path'][-1])==goal
        st.markdown(f'<div class="route-card"><b>{len(d["path"])-1} қозғалыс қадамы</b>'
                    f'<p>Сапар құны: {d["elapsed"]:.0f} шартты уақыт бірлігі</p>'
                    '<p>A* бастапқы жоспар · Q-learning басқару</p></div>',unsafe_allow_html=True)
        st.subheader('Карта қабаттары')
        layers=st.multiselect('Көрсетілетін ақпарат',['Кептеліс','A* жоспары','GPS өлшемдері','HMM бағасы','HMM сенімі'],
                              default=['Кептеліс','A* жоспары','HMM бағасы'],label_visibility='collapsed')
        st.caption('Картаны тышқанмен жылжытыңыз. Дөңгелекпен үлкейтіңіз. Екі рет басу бастапқы көріністі қайтарады.')
    left,right=st.columns([4,1])
    with left:
        st.markdown('### Қала картасы')
        st.caption(f'{start_name} → {goal_name}')
    with right:
        st.markdown('<span class="tag">● Модельдік қала · DEMO</span>',unsafe_allow_html=True)
    nav=st.columns([1,1,1,7])
    end=len(d['path'])-1
    st.session_state.trip_step=min(st.session_state.trip_step,end)
    with nav[0]:
        if st.button('⏮',help='Басына',width='stretch'): st.session_state.trip_step=0
    with nav[1]:
        if st.button('◀',help='Алдыңғы қадам',width='stretch'): st.session_state.trip_step=max(0,st.session_state.trip_step-1)
    with nav[2]:
        if st.button('▶',help='Келесі қадам',width='stretch'): st.session_state.trip_step=min(end,st.session_state.trip_step+1)
    with nav[3]:
        t=st.slider('Сапар қадамы',0,end,key='trip_step',label_visibility='collapsed')
    phase='Q-learning' if d['phases'][t] else 'A*'
    if d['fallback'] and d['phases'][t]: phase='Q-learning / A* резерві'
    st.caption(f'Қадам {t}/{end}  •  Басқару: {phase}  •  Көлік: ({d["path"][t,0]}, {d["path"][t,1]})')
    st.plotly_chart(city_map(d,t,layers,start,goal,vehicle,str((n,seed,start,goal))),
                    width='stretch',theme=None,key='navigator',
                    config={'scrollZoom':True,'displaylogo':False,'modeBarButtonsToRemove':['select2d','lasso2d']})
    if t==end:
        if reached: st.success('Мақсатқа жетті. Сапар аяқталды.')
        else: st.error({'no_route':'Қолжетімді маршрут жоқ.', 'no_valid_actions':'Рұқсат етілген бағыт жоқ.', 'step_limit':'Қадам лимиті аяқталды. Мақсатқа жеткен жоқ.'}.get(d['status'],'Сапар тоқтады.'))
    elif d['phases'][t] and d['blocked'] is not None:
        st.warning(f'Жол жабылды: {d["blocked"]}. Жаңартылған карта бойынша қозғалыс.')
    else:
        st.caption('▶ батырмасы немесе слайдер арқылы көліктің қозғалысын көрсетіңіз.')
    if d['fallback']: st.warning('Осы сапарда Q саясаты қайталанатын күйлерге түсті; A* резерві қолданылды.')
    gps_rmse=float(np.sqrt(np.mean(np.sum((d['gps']-d['path'])**2,axis=1))))
    hmm_rmse=float(np.sqrt(np.mean(np.sum((d['filtered']-d['path'])**2,axis=1))))
    cols=st.columns(4)
    cols[0].metric('A* бастапқы жолы',f'{len(d["baseline"])-1} қадам')
    cols[1].metric('Толық сапар құны',f'{d["elapsed"]:.0f} бірлік')
    cols[2].metric('GPS RMSE',f'{gps_rmse:.3f}')
    cols[3].metric('HMM RMSE',f'{hmm_rmse:.3f}')
    with st.expander('AI зертханасы · алгоритмдерді салыстыру'):
        st.caption('Үш график қорғау үшін сақталды. RMSE толық сапар бойынша, ұяшықпен өлшенеді.')
        fig,axes=plt.subplots(1,3,figsize=(16,5))
        grid=d['new'] if d['phases'][t] else d['grid']
        traffic=d['traffic2'] if d['phases'][t] else d['traffic']
        for ax,title in zip(axes,['A* жоспары','GPS өлшемдері','HMM бағасы']):
            draw(ax,grid,traffic,title)
            # draw ішіндегі әдепкі бұрыш маркерлерін жаңа орындармен ауыстыру.
            ax.collections[-1].remove()
            ax.scatter([start[1],goal[1]],[start[0],goal[0]],c=['limegreen','purple'],s=80,marker='s')
        line(axes[0],d['baseline'],'Бастапқы A*','royalblue')
        line(axes[1],d['path'][:t+1],'Нақты жол','royalblue')
        line(axes[1],d['gps'][:t+1],'GPS','orangered',marker='.',linestyle=':')
        line(axes[2],d['path'][:t+1],'Нақты жол','royalblue',alpha=.4)
        line(axes[2],d['filtered'][:t+1],'HMM MAP','teal',marker='.')
        for ax in axes: ax.legend(fontsize=8)
        fig.tight_layout(); st.pyplot(fig); plt.close(fig)
        st.caption('HMM MAP сызығы — ықтимал орындар тізбегі; физикалық маршрут емес.')
        st.line_chart({'Бастапқы карта: |TD|':d['h0'],'Өзгерген карта: |TD|':d['h1']})
        st.caption('Ось индексінің әр бірлігі — 50 оқыту batch-ы. TD қатесі оптималдықтың дәлелі емес.')
    with st.expander('Жоба туралы'):
        st.write('Бұл — 2GIS стиліндегі оқу навигаторы. Картадағы ғимараттар, нысандар мен жолдар модельдік. '
                 'Нақты мекенжайлар мен live трафик қосылмаған. Көлік белгісі бірдей 2D қозғалыс моделін қолданады.')
        st.write('Басқарушы симулятордағы нақты күйді біледі. HMM GPS пен әрекеттерден орынды бөлек бағалайды. '
                 'HMM сеніміне сүйенетін толық басқару үшін POMDP кеңейту қажет.')
    buffer=io.StringIO()
    rows=np.column_stack([np.arange(len(d['path'])),d['path'],d['gps'],d['filtered'],d['phases']])
    np.savetxt(buffer,rows,delimiter=',',header='t,true_row,true_col,gps_row,gps_col,hmm_row,hmm_col,changed',comments='')
    st.download_button('↓ Сапар деректері · CSV',buffer.getvalue(),'trajectory.csv','text/csv')

