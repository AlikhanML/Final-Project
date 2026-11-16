"""Cache keys include snapshot bytes and graph/routing schema versions."""
from pathlib import Path
from time import perf_counter
import streamlit as st
from environments.traffic import TRAFFIC_MODEL_VERSION
from infrastructure.graph_cache import load_cached_world
from infrastructure.repository import snapshot_identity
from services.simulation import simulate as simulate_grid
from services.simulation import simulate_roads as simulate_road_world

DATA = Path(__file__).resolve().parents[1]/'data'/'astana_roads.json'

def active_identity():
    city=DATA.with_name('astana_city_roads.json')
    return snapshot_identity(city if city.exists() else DATA)

@st.cache_data(max_entries=2,show_spinner=False)
def _load_roads(path: str, version: str):
    return load_cached_world(Path(path),expected_version=version)

def load_roads():
    return _load_roads(*active_identity())

@st.cache_data(max_entries=6,show_spinner=False)
def _simulate_roads(path,version,start,goal,density,sigma,seed,batches,dynamic,control_version):
    return simulate_road_world(_load_roads(path,version),start,goal,density,sigma,seed,batches,dynamic)

def simulate_roads(start,goal,density,sigma,seed,batches,dynamic,*,expected_version=None):
    path,version=active_identity()
    if expected_version is not None and version!=expected_version:
        raise ValueError('Карта жаңарды. Шақырту нүктесін қайта таңдаңыз.')
    return _simulate_roads(path,version,start,goal,density,sigma,seed,batches,dynamic,"hmm-map-v8-signals")

# Keep existing test and notebook cache-reset API.
load_roads.clear=_load_roads.clear
simulate_roads.clear=_simulate_roads.clear
simulate = st.cache_data(max_entries=8,show_spinner=False)(simulate_grid)


def load_session_roads(state):
    """Load a private disk snapshot once per session.

    Avoid serializing the entire loaded graph again into Streamlit cache_data.
    Separate sessions still load independent worlds; no shared mutable graph.
    """
    identity=active_identity()
    if state.get('_road_world_identity')!=identity:
        started=perf_counter()
        world=load_cached_world(Path(identity[0]),identity[1])
        world['_traffic_cache']={}
        world['_routing_static']={}
        state['_road_load_seconds']=perf_counter()-started
        state['_road_world']=world
        state['_road_world_identity']=identity
    return state['_road_world']


@st.cache_data(max_entries=4,show_spinner=False)
def _simulate_projected(version,start,goal,density,sigma,seed,batches,dynamic,recovery_version,priority,_world):
    return simulate_road_world(_world,start,goal,density,sigma,seed,batches,dynamic,
                               training_updates=240_000,compute_budget_s=20.,max_steps=1500,quick_recovery=True,traffic_model="corridor",priority=priority)

def simulate_projected(world,start,goal,density,sigma,seed,batches,dynamic,*,priority="normal"):
    return _simulate_projected(world['dataset_version'],start,goal,density,sigma,seed,batches,dynamic,
                               f"priority-signals-v6:{TRAFFIC_MODEL_VERSION}",priority,world)
