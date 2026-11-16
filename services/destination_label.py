"""Readable call labels from addresses and the local road snapshot."""

import re
from shapely.geometry import Point
from shapely.strtree import STRtree
from services.landmarks import find_landmark, landmark_at

COORDINATE_PAIR = re.compile(
    r'[+-]?\d+(?:[.,]\d+)?\s*[,;\s]\s*[+-]?\d+(?:[.,]\d+)?'
)
ROAD_PREFIX = re.compile(r'^(?:улица|проспект|переулок|проезд|бульвар|шоссе)\s+', re.IGNORECASE)
ROAD_SUFFIX = re.compile(
    r'(?:[ -])(?:көшесінің|көшесі|көше|даңғылы|даңғыл|орамы|орам|тас жолы|'
    r'желекжолы|көпірі|бульвары|аллеясы|улица|проспект|переулок|проезд|бульвар|шоссе)$',
    re.IGNORECASE,
)
ROAD_CODE = re.compile(r'[^\W\d_][ -]?\d+[^\W\d_]?')
HOUSE_NUMBER = r'(?:№\s*)?(\d+[^\W_]*(?:[/-]\d+[^\W_]*)*)'
APPROXIMATE_ADDRESS = re.compile(r'\bмаңы\b|^(?:рядом с|около|возле|near)\s+', re.IGNORECASE)
NEARBY_STREET_M = 500


def _label(value):
    if not isinstance(value, str):
        return None
    value = ' '.join(value.split())
    if not value or COORDINATE_PAIR.fullmatch(value.strip('()[] ')):
        return None
    return value[:200]


def _street_name(edge):
    name = _label(edge.get('name'))
    return name if name != 'Атаусыз жол' else None


def _nearby(name, language):
    name = name.removesuffix(' маңы')
    if language == 'ru':
        return f'Рядом с {name}'
    if language == 'en':
        return f'Near {name}'
    return f'{name} маңы'


def _kk_street_name(street):
    name = street.removesuffix(' маңы')
    return ROAD_SUFFIX.sub('', ROAD_PREFIX.sub('', name)).strip() or name


def _kk_street_label(street, *, nearby, number=None):
    street = street.removesuffix(' маңы')
    if street.casefold().endswith(' даңғылы'):
        label = _nearby(street, 'kk') if nearby else street
        if number:
            return f'{label} ({number}-үй)' if nearby else f'{label}, {number}'
        return label
    name = _kk_street_name(street)
    if nearby:
        label = f'{name} көшесінің маңы'
        return f'{label} ({number}-үй)' if number else label
    label = f'{name} көшесі'
    return f'{label}, {number}' if number else label


def _address_parts(label):
    """Read a street and optional house number from an older or manual label."""
    parts = [part.strip() for part in label.split(',') if part.strip()]
    if not parts:
        return None, None
    if len(parts) > 1:
        for i, part in enumerate(parts):
            if number := re.fullmatch(HOUSE_NUMBER, part):
                street = parts[i - 1] if i else parts[1]
                return street, number.group(1)
    street = next((part for part in parts if ROAD_PREFIX.match(part) or ROAD_SUFFIX.search(part)), parts[0])
    if not ROAD_CODE.fullmatch(street) and not re.fullmatch(HOUSE_NUMBER, ROAD_PREFIX.sub('', street)):
        if address := re.fullmatch(rf'(.+?)\s+{HOUSE_NUMBER}', street):
            return address.group(1), address.group(2)
    return street, None


def manual_address_parts(value):
    label = _label(value)
    if not label or APPROXIMATE_ADDRESS.search(label):
        return None, None
    street, number = _address_parts(label)
    if street and number and any(character.isalpha() for character in street):
        return street, number
    return None, None


def _nearby_street(name, language):
    if language in ('ru', 'en'):
        return _nearby(name, language)
    return _kk_street_label(name, nearby=True)


def _nearest_named_street(world, point):
    index = world.get('edge_index')
    if index is None or point is None:
        return None
    if '_named_streets' not in world:
        names, lines = [], []
        graph = world['graph']
        for edge, line in zip(index.edges, index.lines):
            if name := _street_name(graph.edges[edge]):
                names.append(name)
                lines.append(line)
        world['_named_streets'] = STRtree(lines), names
    tree, names = world['_named_streets']
    if not names:
        return None
    lat, lon = point
    x, y = index.forward.transform(lon, lat, errcheck=True)
    indices, distances = tree.query_nearest(Point(x, y), return_distance=True)
    return min(names[i] for i in indices), float(distances[0])


def _distance_label(name, meters, language):
    if language == 'en':
        measure = f'{meters / 1000:.1f} km' if meters >= 1000 else f'{meters:.0f} m'
        return f'About {measure} from {name}'
    measure = f'{meters / 1000:.1f} км'.replace('.', ',') if meters >= 1000 else f'{meters:.0f} м'
    if language == 'ru':
        return f'{name} · около {measure} по прямой'
    return f'{_kk_street_name(name)} көшесінен шамамен {measure}'


def destination_label(world, snap, selected_name=None, *, point=None, address=None, language='kk', exact_only=False):
    """Show a landmark, a resolved address or a nearby mapped street."""
    has_specific_address = address and (
        address.get('status') == 'manual'
        or (address.get('house_number') and not address.get('nearby'))
    )
    if not exact_only and not has_specific_address:
        if landmark := landmark_at(point):
            return landmark.name
    if exact_only:
        if not address or address.get('nearby'):
            return None
        if address.get('status') == 'manual':
            street, number = manual_address_parts(address.get('label'))
            if not street:
                return None
            address = {**address, 'street': street, 'house_number': number}
        elif (address.get('status') != 'found' or not _label(address.get('house_number'))
              or not (_label(address.get('street')) or address.get('place_only'))):
            return None
    if address and (name := _label(address.get('label'))):
        if exact_only and APPROXIMATE_ADDRESS.search(name):
            return None
        nearby = bool(address.get('nearby'))
        if language in ('ru', 'en') or address.get('place_only'):
            return _nearby(name, language) if nearby else name
        street = _label(address.get('street'))
        number = _label(address.get('house_number'))
        if street is None:
            street, number = _address_parts(name)
        if street:
            return _kk_street_label(street, nearby=nearby, number=number)
    if exact_only:
        return None
    if name := _label(selected_name):
        if find_landmark(name.removesuffix(' маңы')):
            return _nearby(name, language)
        return _nearby_street(name, language)
    if nearest := _nearest_named_street(world, point):
        name, meters = nearest
        if meters <= NEARBY_STREET_M:
            return _nearby_street(name, language)
        return _distance_label(name, meters, language)
    if snap and snap.get('edge'):
        u, v = snap['edge']
        edge = world['graph'].get_edge_data(u, v) or {}
        if name := _street_name(edge):
            return _nearby_street(name, language)
    if point is not None:
        return f'{point[0]:.6f}, {point[1]:.6f}'
    return {'ru': 'Астана', 'en': 'Astana'}.get(language, 'Астана қаласы')
