"""Offline landmark lookup for call labels and map search."""

from dataclasses import dataclass
import unicodedata

from domain.models import ASTANA_LANDMARKS
from utils.geo import distance


@dataclass(frozen=True)
class Landmark:
    name: str
    point: tuple[float, float]
    radius_m: float
    aliases: tuple[str, ...] = ()


# Coordinates are map points. The radius approximates the area of the feature
# for click matching; it does not represent its legal or cadastral boundary.
LANDMARKS = (
    Landmark('Бәйтерек', ASTANA_LANDMARKS['Бәйтерек'], 22,
             ('Байтерек', 'Бәйтерек монументі', 'Bayterek', 'Baiterek')),
    Landmark('Хан Шатыр', ASTANA_LANDMARKS['Хан Шатыр'], 65,
             ('Хан-Шатыр', 'Khan Shatyr', 'ТРЦ Хан Шатыр')),
    Landmark('Ақорда', (51.12580, 71.44647), 45,
             ('Ақ Орда', 'Ак Орда', 'Акорда', 'Ak Orda')),
    Landmark('Астана Опера', (51.13556, 71.41092), 52,
             ('Astana Opera',)),
    Landmark('Бейбітшілік пен келісім сарайы', (51.12306, 71.46361), 44,
             ('Пирамида', 'Дворец мира и согласия', 'Palace of Peace and Reconciliation')),
    Landmark('Әзірет Сұлтан мешіті', (51.12543, 71.47219), 48,
             ('Әзірет Сұлтан', 'Хазрет Султан', 'Мечеть Хазрет Султан', 'Hazrat Sultan Mosque')),
    Landmark('Ұлттық музей', (51.11811, 71.46951), 65,
             ('Ұлттық мұражай', 'Национальный музей', 'National Museum')),
    Landmark('Нұр Әлем', (51.08925, 71.41601), 42,
             ('Нур Алем', 'Nur Alem', 'ЭКСПО', 'EXPO')),
    Landmark('Астана Арена', (51.10814, 71.40273), 76,
             ('Astana Arena', 'Стадион Астана Арена')),
)


def _search_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().replace('ё', 'е').split())


_BY_NAME = {
    _search_key(name): landmark
    for landmark in LANDMARKS
    for name in (landmark.name, *landmark.aliases)
}


def find_landmark(query):
    return _BY_NAME.get(_search_key(query)) if isinstance(query, str) else None


def landmark_at(point):
    if point is None:
        return None
    nearest = None
    best = float('inf')
    for landmark in LANDMARKS:
        meters = distance(point, landmark.point)
        if meters <= landmark.radius_m and meters < best:
            nearest, best = landmark, meters
    return nearest
