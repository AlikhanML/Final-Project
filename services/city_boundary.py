"""Offline boundary checks for Astana call locations."""
import json
import math
from pathlib import Path
from functools import lru_cache
from shapely.geometry import shape, Point

OUTSIDE_CITY_MESSAGE='Тек Астанада қаласында шақырту нүктесің таңдай аласыз'
CALL_EXCLUSION_MESSAGES = {
    'kk': 'Аралда шақырту орнын таңдауға болмайды. Жағалаудан нүкте таңдаңыз.',
    'ru': 'На острове нельзя выбрать точку вызова. Выберите точку на берегу.',
    'en': 'Call locations cannot be selected on the island. Choose a point on the riverbank.',
}

@lru_cache(maxsize=1)
def city_geometry():
    path=Path(__file__).resolve().parents[1]/'data'/'astana_boundary.geojson'
    return json.loads(path.read_text(encoding='utf-8'))['geometry']

@lru_cache(maxsize=1)
def city_shape():
    return shape(city_geometry())

def in_astana(lat, lon):
    return math.isfinite(lat) and math.isfinite(lon) and city_shape().covers(Point(lon,lat))

@lru_cache(maxsize=1)
def call_exclusion_geometry():
    path=Path(__file__).resolve().parents[1]/'data'/'astana_call_exclusion.geojson'
    return json.loads(path.read_text(encoding='utf-8'))['geometry']

@lru_cache(maxsize=1)
def _call_exclusion_shape():
    return shape(call_exclusion_geometry())

def in_call_exclusion(lat, lon):
    return math.isfinite(lat) and math.isfinite(lon) and _call_exclusion_shape().covers(Point(lon,lat))

def call_exclusion_message(language):
    return CALL_EXCLUSION_MESSAGES.get(language, CALL_EXCLUSION_MESSAGES['kk'])
