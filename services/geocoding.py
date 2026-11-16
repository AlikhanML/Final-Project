"""User-submitted Astana address search, with bounded, cached Nominatim calls."""
import os
import re
import time
from collections import OrderedDict
from threading import Lock
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError, GeocoderTimedOut
from geopy.adapters import URLLibAdapter
from services.city_boundary import city_shape, in_astana

_lock = Lock()
_cache = OrderedDict()
_last_request = 0.0


def geocode_astana(query):
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 200:
        raise ValueError('Көше атауы мен үй нөмірін енгізіңіз (3–200 таңба).')
    query = ' '.join(query.split())
    key = query.casefold()
    # Serialize requests across all sessions in this Python server.
    global _last_request
    with _lock:
        now = time.monotonic()
        cached = _cache.get(key)
        if cached and now - cached[0] < 86400:
            _cache.move_to_end(key)
            result = cached[1]
        else:
            wait = 1.1 - (now - _last_request)
            if wait > 0:
                time.sleep(wait)
            locator = Nominatim(
                user_agent=os.getenv('QADAM_GEOCODER_USER_AGENT', 'Qadam-University-Route/2.0'),
                domain=os.getenv('QADAM_NOMINATIM_DOMAIN', 'nominatim.openstreetmap.org'),
                timeout=10, adapter_factory=URLLibAdapter,
            )
            west, south, east, north = city_shape().bounds
            _last_request = time.monotonic()
            try:
                locations = locator.geocode(
                    query + ', Астана, Қазақстан', exactly_one=False, limit=5,
                    country_codes='kz', viewbox=[(south, west), (north, east)],
                    bounded=True, addressdetails=True, language='kk,ru,en',
                ) or []
            except GeocoderTimedOut as exc:
                raise ValueError('Мекенжай іздеу уақыты аяқталды. Қайта көріңіз.') from exc
            except (GeopyError, OSError) as exc:
                raise ValueError('Мекенжай іздеу сервері қолжетімсіз. Интернетті тексеріп, қайта көріңіз.') from exc
            result = None
            for location in locations:
                lat, lng = float(location.latitude), float(location.longitude)
                if not in_astana(lat, lng):
                    continue
                address = location.raw.get('address') or {}
                # Never present a whole street as a located house number.
                number = re.search(r'(\d+[\w/-]*)\s*$', query)
                if number and str(address.get('house_number', '')).casefold() != number.group(1).casefold():
                    continue
                result = {'lat': lat, 'lng': lng, 'label': location.address}
                if street := address.get('road'):
                    house_number = address.get('house_number')
                    result.update(street=street, house_number=house_number, nearby=not house_number)
                elif location.raw.get('addresstype') in {'city','district','suburb','neighbourhood','quarter'}:
                    result.update(place_only=True, nearby=True)
                break
            _cache[key] = (time.monotonic(), result)
            _cache.move_to_end(key)
            while len(_cache) > 256:
                _cache.popitem(last=False)
    if result is None:
        raise ValueError('Астанада бұл мекенжай табылмады. Атауын тексеріңіз немесе картадан таңдаңыз.')
    return result.copy()
