"""OSM lookup for a selected call location, independent of routing."""
import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import OrderedDict
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from numbers import Real
from threading import Lock
from shapely.geometry import Point, Polygon
from domain.models import ASTANA_LANDMARKS
from utils.geo import distance

_log = logging.getLogger(__name__)
_address_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix='qadam-address')
EXACT_ADDRESS_NODE_M = 1.
NEARBY_ADDRESS_M = 30.


def parse_address(raw, lat, lon):
    """Prefer an addressed area containing the click, then a point within 30m."""
    if not isinstance(raw, dict) or raw.get('remark'):
        return None
    sx = 111320 * math.cos(math.radians(lat))
    candidates = []
    for obj in raw.get('elements', []):
        tags = obj.get('tags', {})
        street = tags.get('addr:street') or tags.get('addr:street:kk') or tags.get('addr:street:ru')
        place = tags.get('addr:place')
        number = tags.get('addr:housenumber')
        name = street or place
        label = f'{name}, {number}' if name and number else tags.get('addr:full')
        if not isinstance(label,str) or not label.strip():
            continue
        center = obj if 'lat' in obj else obj.get('center', {})
        dist = math.inf
        if 'lat' in center and 'lon' in center:
            dist = math.hypot((center['lon']-lon)*sx, (center['lat']-lat)*111320)
        exact_node = obj.get('type') == 'node' and dist <= EXACT_ADDRESS_NODE_M
        inside = False
        geometry = obj.get('geometry', [])
        if len(geometry) >= 4:
            coords = [(p['lon'],p['lat']) for p in geometry if 'lat' in p and 'lon' in p]
            if len(coords) >= 4 and coords[0] == coords[-1]:
                polygon = Polygon(coords)
                inside = polygon.is_valid and polygon.covers(Point(lon, lat))
                if polygon.is_valid:
                    metric = Polygon([((x-lon)*sx,(y-lat)*111320) for x,y in coords])
                    dist = metric.distance(Point(0,0))
        if inside or dist <= NEARBY_ADDRESS_M:
            nearby = not (inside or exact_node)
            note = 'OSM · жақын мекенжай, орнын тексеріңіз' if nearby else 'OSM'
            if inside:
                note = 'OSM · таңдалған ғимарат'
            candidates.append((not inside, dist, {'label':label.strip(), 'nearby': nearby,
                'street':(tags.get('addr:street:kk') or street) if number else None, 'house_number':number,
                'place_only':not street and bool(place and number),
                'note':note}))
    return min(candidates,key=lambda x:x[:2])[2] if candidates else None


def _local_address_points():
    # The venue publishes this address at https://khanshatyr.com/kontakty.
    lat, lon = ASTANA_LANDMARKS['Хан Шатыр']
    return ((lat, lon, 'Хан Шатыр · Тұран даңғылы, 37'),)


def _landmark_address(point):
    nearest = min(((distance(point, (lat, lon)), label)
                   for lat, lon, label in _local_address_points()), default=None)
    if nearest is None or nearest[0] > NEARBY_ADDRESS_M:
        return None
    meters, label = nearest
    street, _, number = label.rpartition(',')
    nearby = meters > EXACT_ADDRESS_NODE_M
    note = f'Жергілікті мекенжай · шамамен {meters:.0f} м, орнын тексеріңіз' if nearby else 'Жергілікті карта дерегі'
    return {'label': label, 'status': 'found', 'nearby': nearby, 'note': note,
            'street': street.rpartition(' · ')[-1].strip(), 'house_number': number.strip()}


def _snapshot_address(point, world):
    if not isinstance(world, Mapping):
        return None
    source = world.get('source', world)
    if not isinstance(source, Mapping):
        return None
    elements = list(source.get('elements', ()))
    addresses = source.get('addresses', ())
    elements.extend(addresses.values() if isinstance(addresses, Mapping) else addresses)
    for hospital in source.get('hospitals', ()):
        kind = str(hospital.get('id', '')).partition('/')[0]
        elements.append({'type': kind, **hospital})
    nodes = source.get('nodes', {})
    for way in source.get('ways', ()):
        tags = way.get('tags', {})
        if tags.get('highway') or not (tags.get('addr:housenumber') or tags.get('addr:full')):
            continue
        if 'geometry' in way:
            elements.append(way)
            continue
        ids = way.get('nodes', ())
        if len(ids) < 4 or ids[0] != ids[-1] or not all(str(node) in nodes for node in ids):
            continue
        geometry = [{'lat': nodes[str(node)][0], 'lon': nodes[str(node)][1]} for node in ids]
        elements.append({'type': 'way', 'tags': tags, 'geometry': geometry})
    address = parse_address({'elements': elements}, *point)
    return {**address, 'status': 'found'} if address else None


def local_address(point, world=None):
    """Resolve a local address from a coordinate pair or two separate coordinates."""
    # Accept the world-first form used by the map's other address helpers.
    if isinstance(point, Mapping):
        point, world = world, point
    elif isinstance(point, Real) and isinstance(world, Real):
        point, world = (point, world), None
    if point is None:
        return None
    snapshot = _snapshot_address(point, world)
    if snapshot and not snapshot['nearby']:
        return snapshot
    return _landmark_address(point) or snapshot


_cache = OrderedDict()
_cache_lock = Lock()


def failure(status, note):
    return {'label': None, 'status': status, 'note': note}


def _lookup(lat, lon, timeout=6):
    query = f'''[out:json][timeout:{max(3,timeout-1)}];
    (node["addr:housenumber"](around:120,{lat},{lon});
     way["addr:housenumber"](around:120,{lat},{lon});
     node["addr:full"](around:120,{lat},{lon});
     way["addr:full"](around:120,{lat},{lon}););out body geom;'''
    endpoint = os.getenv('QADAM_ADDRESS_ENDPOINT','https://overpass-api.de/api/interpreter')
    request = urllib.request.Request(endpoint,
        data=urllib.parse.urlencode({'data':query}).encode(),
        headers={'User-Agent':'Qadam-University-Project/1.1'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            data=response.read(2_000_001)
        if len(data)>2_000_000:
            return failure('large_response','Сервер жауабы тым үлкен. Ғимаратқа жақынырақ нүкте таңдаңыз.')
        raw=json.loads(data)
        if not isinstance(raw,dict):raise ValueError('Invalid response')
        if raw.get('remark'):
            return failure('server_incomplete','OSM сервері толық жауап бермеді. Қайта іздеп көріңіз.')
        result=parse_address(raw,lat,lon)
        if result:
            return {**result,'status':'found'}
        return failure('no_address','Осы нүкте маңындағы OSM дерегінде көше мен үй нөмірі бірге табылмады. Ғимараттың үстінен таңдаңыз.')
    except urllib.error.HTTPError as exc:
        return failure('http_error',f'Мекенжай сервері HTTP {exc.code} қатесін қайтарды. Қайта іздеп көріңіз.')
    except TimeoutError:
        return failure('timeout','Мекенжай серверінен жауап күту уақыты аяқталды. Қайта іздеп көріңіз.')
    except OSError:
        return failure('network_error','Мекенжай серверіне қосылу мүмкін болмады. Интернет байланысын тексеріңіз.')
    except (ValueError,TypeError,KeyError):
        return failure('invalid_response','Мекенжай серверінің жауабы оқылмады. Қайта іздеп көріңіз.')


def lookup_address(point, force=False, *, world=None):
    """Prefer a verified local address and cache successful remote lookups."""
    if isinstance(force, Mapping) and world is None:
        world, force = force, False
    local = local_address(point, world)
    if not force and local and not local.get('nearby'):
        return local
    key=(round(float(point[0]),6),round(float(point[1]),6))
    now=time.monotonic()
    with _cache_lock:
        cached=_cache.get(key)
        if not force and cached and now-cached[0]<86400:
            return cached[1].copy()
    result=_lookup(*key,timeout=12 if force else 6)
    if result.get('label'):
        with _cache_lock:
            _cache[key]=(now,result.copy())
            _cache.move_to_end(key)
            while len(_cache)>256:_cache.popitem(last=False)
    if local and (not result.get('label') or (result.get('nearby') and not local['nearby'])):
        return local
    return result


def start_automatic_address(state, world=None):
    point = state.get('nav_B')
    address = state.get('nav_address') or {}
    if point is not None and address.get('status') == 'selected':
        state['nav_address_future'] = _address_workers.submit(lookup_address, point, world=world)
        state['nav_address'] = failure('auto_pending', '')


def cancel_automatic_address(state):
    future = state.pop('nav_address_future', None)
    if future is not None:
        future.cancel()


def finish_automatic_address(state):
    """Publish a verified house number when the current call's job completes."""
    future = state.get('nav_address_future')
    if future is None or not future.done():
        return False
    del state['nav_address_future']
    try:
        address = future.result()
    except Exception:
        _log.exception('Automatic address lookup failed')
        address = None
    if address and address.get('label') and address.get('house_number') and address.get('nearby') is False:
        state['nav_address'] = address
    else:
        state['nav_address'] = failure('auto_unavailable', '')
    return True
