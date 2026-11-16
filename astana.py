"""Compatibility imports for previous notebooks; implementations live in packages."""
from utils.geo import distance, to_latlon
from infrastructure.graph_builder import build_world
from environments.road_world import nearest, transition_table
from algorithms.astar import astar_roads
from algorithms.q_learning import q_train
from algorithms.hmm import filter_roads
from ui.cache import DATA, load_roads, simulate_roads

def main():
    from ui.legacy_folium import main as legacy_main
    legacy_main()



