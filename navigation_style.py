"""Қараңғы навигатордың визуал стилі. Есептеу алгоритмдеріне әсер етпейді."""
import streamlit as st
from branca.element import MacroElement, Template


def apply_theme():
    st.markdown('''<style>
    :root {color-scheme:dark}
    .stApp,[data-testid="stAppViewContainer"]{background:#171b20;color:#edf2ed}
    [data-testid="stHeader"]{background:#171b20}
    .block-container{max-width:1800px;padding:1rem 1.35rem 2rem}
    [data-testid="stSidebar"]{background:#20252a;border-right:1px solid #30373d}
    [data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#edf2ed}
    .stApp h1,.stApp h2,.stApp h3,.stApp label,.stApp p{color:#e5ebe7}
    [data-testid="stCaptionContainer"] p{color:#96a49d!important;font-size:12px}
    .stButton button,.stDownloadButton button{background:#282f34;color:#e8eeea;border:1px solid #3a4349;border-radius:13px;min-height:44px}
    .stButton button:hover{border-color:#43db81;color:#43db81;background:#29392f}
    .stButton button[kind="primary"]{background:#39d778;color:#102419;border:0;font-weight:700}
    .stButton button[kind="primary"] p{color:#102419!important}
    .stButton button:disabled{opacity:.38}
    [data-baseweb="select"]>div,[data-baseweb="input"]{background:#2b3238;color:#e8eeea;border-color:#424a50}
    [data-baseweb="select"] span,[data-baseweb="input"] input{color:#e8eeea}
    [data-testid="stMetric"]{background:#252c31;border:1px solid #394239;border-radius:15px;padding:15px}
    [data-testid="stMetricValue"]{color:#4ce68c;font-size:1.7rem}
    [data-testid="stExpander"]{background:#20262b;border-color:#353e44;border-radius:12px}
    [data-testid="stAlert"]{background:#23342c;border:1px solid #365141;color:#dcebe0;border-radius:13px}
    iframe{border-radius:20px}
    .q-top{display:flex;align-items:center;justify-content:space-between;margin:4px 0 15px}
    .q-logo{font:800 25px Arial;letter-spacing:-1px;color:#f3f8f5}.q-logo b{color:#44df83}
    .q-sub{color:#92a09a;font-size:12px;margin-top:4px}.q-live{border:1px solid #365043;color:#57e18d;background:#23322b;border-radius:30px;padding:8px 14px;font-size:12px}
    .q-hint{padding:11px 15px;background:#252d32;border:1px solid #36413b;border-radius:12px;color:#b7c8bd;margin-bottom:10px;font-size:14px}
    @media(max-width:700px){.block-container{padding:.65rem .5rem}.q-live{font-size:10px;padding:6px 9px}.q-logo{font-size:22px}}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="q-top"><div><div class="q-logo">qadam<b>↗</b></div>'
                '<div class="q-sub">АСТАНА · АҚЫЛДЫ НАВИГАТОР</div></div>'
                '<div class="q-live">● AI СИМУЛЯЦИЯ</div></div>',unsafe_allow_html=True)


def add_map_chrome(m, status, detail, center):
    """Картаның ішінде қара панельдер мен жұмыс істейтін орталау батырмасы."""
    overlay=MacroElement()
    overlay._name='QadamChrome'
    overlay.status=status
    overlay.detail=detail
    overlay.center=list(center)
    overlay._template=Template('''
    {% macro header(this, kwargs) %}
    <style>
    .leaflet-dark_tiles-pane{filter:invert(.92) hue-rotate(180deg) saturate(.55) brightness(.78)}
    .leaflet-container{background:#20282c;font-family:Arial,sans-serif!important}
    .leaflet-control-zoom,.leaflet-control-layers{border:0!important;box-shadow:0 4px 15px #0006!important;border-radius:15px!important;overflow:hidden}
    .leaflet-control-zoom a{background:#101416!important;color:#f0f4f1!important;border-color:#30363b!important;width:45px!important;height:44px!important;line-height:42px!important;font-size:27px!important}
    .leaflet-control-layers{background:#151b1f!important;color:#e3ece6!important;padding:5px!important}
    .leaflet-control-layers-expanded{padding:14px!important}
    .leaflet-control-attribution{background:#171e22dd!important;color:#a9b8af!important;font-size:9px!important}
    .leaflet-control-attribution a{color:#bdd0c1!important}
    .q-map-status{position:absolute;top:18px;left:18px;z-index:900;background:#101416ed;color:#e7f1e9;border:1px solid #39423b;border-radius:16px;padding:12px 17px;box-shadow:0 5px 20px #0004;pointer-events:none;font:600 13px Arial}
    .q-map-status span{color:#47df84;margin-right:7px}
    .q-route-hud{position:absolute;bottom:34px;left:18px;right:76px;z-index:900;border-radius:17px;padding:17px 19px;background:#111719ee;border:1px solid #38443c;box-shadow:0 5px 20px #0006;pointer-events:none}
    .q-route-hud strong{color:#eaf2ec;font:600 16px Arial;display:block;margin-bottom:5px}
    .q-route-hud small{color:#9baaa1;font:12px Arial}
    .q-compass{position:absolute;top:88px;right:12px;z-index:900;color:#4ce88a;background:#111719;border:1px solid #37463c;border-radius:50%;width:38px;height:38px;line-height:38px;text-align:center;pointer-events:none;font:bold 16px Arial}
    .q-locate{position:absolute;bottom:45px;right:12px;z-index:1000;background:#111719;color:#e5f2e9;border:1px solid #37463c;border-radius:14px;width:46px;height:46px;cursor:pointer;font-size:23px}
    .leaflet-bottom.leaflet-right{bottom:110px}
    .leaflet-bottom.leaflet-right .leaflet-control-attribution{position:fixed;bottom:0;right:0}
    @media(max-width:550px){.q-map-status{font-size:11px;left:10px;top:12px;padding:10px}.q-route-hud{left:10px;padding:13px}.q-route-hud strong{font-size:14px}}
    </style>
    {% endmacro %}
    {% macro html(this, kwargs) %}
    <div class="q-map-status"><span>●</span> Астана · нақты көшелер</div>
    <div class="q-compass">N ↑</div>
    <div class="q-route-hud"><strong>{{ this.status | e }}</strong><small>{{ this.detail | e }}</small></div>
    <button type="button" aria-label="Көлікке немесе стартқа оралу" title="Көлікке / стартқа оралу" class="q-locate" id="{{ this.get_name() }}_locate">➤</button>
    {% endmacro %}
    {% macro script(this, kwargs) %}
    document.getElementById('{{ this.get_name() }}_locate').onclick=function(e){
      e.stopPropagation();{{ this._parent.get_name() }}.setView({{ this.center | tojson }},16);
    };
    {% endmacro %}
    ''')
    m.add_child(overlay)
