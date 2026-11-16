"""Geography for the weekday rush-hour scenario on the Astana OSM graph."""
from collections import defaultdict

import numpy as np


KABANBAY = 'Қабанбай Батыр даңғылы'
MANGILIK = 'Мәңгілік Ел даңғылы'
TURAN = 'Тұран даңғылы'
SYGANAK = 'Сығанақ көшесі'
AITMATOV = 'Шыңғыс Айтматов көшесі'
SARAYSHYK = 'Сарайшық көшесі'
DOSTYK = 'Достық көшесі'
KONAEV = 'Қонаев көшесі'
ULY_DALA = 'Ұлы Дала даңғылы'
KORGALZHYN = 'Қорғалжын тас жолы'
AKMESHIT = 'Ақмешіт көшесі'
TURKISTAN = 'Түркістан көшесі'

# (South, west, north, east, slowdown at the default density).
# The reported corridors have lighter load between the modeled queues.
# https://rus.baq.kz/news/probki-v-astane-sokratilis-na-10-12-kakie-dorogi-razgruzyat-i-kuda-prodlyat-lrt-320051315/
# https://www.gov.kz/memleket/entities/astana/press/news/details/616900?lang=ru
CORRIDORS = {
    KABANBAY: (51.094, 71.396, 51.153, 71.429, .49),
    MANGILIK: (51.093, 71.420, 51.138, 71.446, .56),
    TURAN: (51.097, 71.390, 51.158, 71.417, .52),
    SYGANAK: (51.122, 71.3616, 51.134, 71.4131, .60),
    AITMATOV: (51.106, 71.350, 51.159, 71.375, .33),
    SARAYSHYK: (51.129, 71.406, 51.140, 71.459, .48),
    KONAEV: (51.127, 71.413, 51.137, 71.443, .30),
    DOSTYK: (51.122, 71.410, 51.132, 71.443, .37),
    ULY_DALA: (51.089, 71.375, 51.106, 71.468, .23),
}

# OSM intersection positions. Sergek ITS identifies frequent queues here.
# https://www.vechastana.kz/news/top-15-zagruzhennyh-perekrestkov-astany
INTERSECTIONS = (
    (51.14610, 71.41205, TURAN, KORGALZHYN),
    (51.12625, 71.42770, DOSTYK, AKMESHIT),
    (51.13720, 71.40865, TURAN, SARAYSHYK),
    (51.12565, 71.43140, DOSTYK, TURKISTAN),
    (51.13395, 71.43080, SARAYSHYK, AKMESHIT),
    (51.13645, 71.41575, KABANBAY, SARAYSHYK),
    (51.13320, 71.41440, KABANBAY, KONAEV),
    (51.12845, 71.41360, KABANBAY, DOSTYK),
    (51.13030, 71.43320, KONAEV, TURKISTAN),
    (51.14710, 71.42250, KABANBAY, KORGALZHYN),
    (51.13680, 71.46680, 'Тәуелсіздік даңғылы', 'Бауыржан Момышұлы даңғылы'),
    (51.16380, 71.41460, 'Кенесары көшесі', 'Жеңіс даңғылы'),
    (51.17140, 71.42570, 'Республика даңғылы', 'Сәкен Сейфуллин көшесі'),
    (51.17290, 71.43830, 'Шоқан Уәлиханов көшесі', 'Сәкен Сейфуллин көшесі'),
    # Additional scenario bottlenecks on the corridors cited by the city.
    (51.12936, 71.43938, MANGILIK, KONAEV),
    (51.12473, 71.43751, MANGILIK, DOSTYK),
    (51.11307, 71.43324, MANGILIK, 'Керей Және Жәнібек Хандар көшесі'),
    (51.09553, 71.42695, MANGILIK, ULY_DALA),
    (51.13247, 71.36176, SYGANAK, AITMATOV),
    (51.12702, 71.40462, SYGANAK, TURAN),
    (51.12570, 71.41305, SYGANAK, KABANBAY),
    (51.14801, 71.36830, AITMATOV, KORGALZHYN),
    (51.10007, 71.39496, ULY_DALA, TURAN),
    (51.09851, 71.40589, ULY_DALA, KABANBAY),
)

# Named river crossings. Anchor queues to bridge entries in each direction.
# https://vlast.kz/gorod/68765-kak-v-astane-resaut-problemu-s-probkami.html
BRIDGES = {
    'Тұран көпірі', 'Қараөткел көпірі', 'Арқар көпірі (М-1) көшесі',
    'Арыс көпірі көшесі', 'Марал көпірі көшесі',
}
ALIASES = {
    'проспект Туран': TURAN,
    'Кенесары Хан көшесі': 'Кенесары көшесі',
    'улица Сейфуллина': 'Сәкен Сейфуллин көшесі',
}


def _approaches(indices, starts, ends, point):
    """Pick the nearest incoming edge in each direction of a named road."""
    incoming = ends[indices] - starts[indices]
    offsets = point - starts[indices]
    fractions = np.sum(offsets * incoming, axis=1) / np.sum(incoming**2, axis=1)
    delta = offsets - np.clip(fractions, 0, 1)[:, None] * incoming
    lateral = np.linalg.norm(delta, axis=1)
    endpoint = np.linalg.norm(point - ends[indices], axis=1)
    scores = endpoint + lateral
    nearest = np.argmin(lateral)
    directions = incoming @ incoming[nearest]
    # A split carriageway can pass slightly to one side of the junction point.
    candidates = (lateral <= 65.) & (endpoint <= 130.) & (fractions > 0)
    for direction in (directions > 0, directions < 0):
        options = np.flatnonzero(candidates & direction)
        if len(options):
            yield indices[options[np.argmin(scores[options])]]


def astana_traffic(world, rows, actions, targets, edges, density, seed):
    """Compute the background slowdown and seeded queue parameters."""
    named = defaultdict(list)
    bridge_edges = set()
    bridge_ids = {
        str(way.get('id', i)) for i, way in enumerate(world['source'].get('ways', ()))
        if way['tags'].get('name') in BRIDGES and way['tags'].get('bridge') in ('yes', 'viaduct')
    }
    relevant = CORRIDORS.keys() | {name for _, _, *names in INTERSECTIONS for name in names}
    for i, edge in enumerate(edges):
        name = edge.get('name')
        name = ALIASES.get(name, name)
        if name in relevant:
            named[name].append(i)
        if edge.get('way_id') in bridge_ids:
            bridge_edges.add((int(rows[i]), int(targets[i]), i))

    background = np.zeros(len(rows))
    load = (density / .2)**.8
    coords = world['coords']
    for name, (south, west, north, east, level) in CORRIDORS.items():
        indices = np.asarray(named[name], dtype=int)
        lat, lon = ((coords[rows[indices]] + coords[targets[indices]]) / 2).T
        # A short taper avoids an abrupt boundary between central and outer sections.
        offset = np.maximum.reduce((south - lat, lat - north, .63 * (west - lon), .63 * (lon - east)))
        background[indices] = level * load * np.clip(1 - offset / .003, 0, 1)

    starts, ends = world['xy'][rows], world['xy'][targets]
    east_scale = 111320 * np.cos(np.radians(world['lat0']))
    rng = np.random.default_rng(seed)
    queues = {}
    for lat, lon, *names in INTERSECTIONS:
        point = np.array([(lon - world['lon0']) * east_scale, (lat - world['lat0']) * 111320])
        for name in names:
            indices = np.asarray(named[name], dtype=int)
            if len(indices):
                for index in _approaches(indices, starts, ends, point):
                    queues[index] = (rng.uniform(350., 680.), rng.uniform(1.3, 2.15))

    crossings = {(u, v) for u, v, _ in bridge_edges}
    graph = world['graph']
    for u, v, index in sorted(bridge_edges):
        if any(p != v and (p, u) in crossings for p in graph.predecessors(u)):
            continue
        # The queue is upstream of the entry, so allow for the entry segment length.
        length = world['lengths'][u, actions[index]]
        queues[index] = (length + rng.uniform(380., 690.), rng.uniform(1.4, 2.25))

    length_scale = min(1.6, (density / .2)**.5)
    return background, [(i, length * length_scale, level * load)
                        for i, (length, level) in queues.items()]
