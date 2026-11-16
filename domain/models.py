"""Shared typed contracts. Coordinates are latitude/longitude; lengths are meters."""
from typing import Any, TypedDict
from scipy.spatial import cKDTree
import networkx as nx
import numpy as np
from numpy.typing import NDArray

ASTANA_LANDMARKS = {
    'Хан Шатыр': (51.13251, 71.40387),
    'Бәйтерек': (51.12829, 71.43046),
}


class RoadWorld(TypedDict):
    graph: nx.DiGraph
    road_graph: nx.MultiDiGraph | None
    dataset_version: str
    dataset_path: str
    spatial_index: cKDTree
    original_node_ids: list[str]
    coords: NDArray[np.float64]
    dest: NDArray[np.int64]
    valid: NDArray[np.bool_]
    lengths: NDArray[np.float64]
    xy: NDArray[np.float64]
    lat0: float
    lon0: float
    source: dict[str, Any]


class HospitalSelection(TypedDict):
    id: str
    name: str
    lat: float
    lon: float
    tags: dict[str, str]
    road_m: float
    node: int
