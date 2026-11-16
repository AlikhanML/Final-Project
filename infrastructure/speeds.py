"""OSM speed metadata. Defaults are simulation assumptions, not legal limits."""
import re

DEFAULT_KMH = {'motorway':90.,'motorway_link':40.,'trunk':70.,'trunk_link':40.,
 'primary':50.,'primary_link':30.,'secondary':50.,'secondary_link':30.,
 'tertiary':40.,'tertiary_link':30.,'residential':30.,'living_street':15.,
 'service':15.,'unclassified':30.}

def parse_speed(raw) -> float | None:
    """Parse a positive numeric km/h, mph or knots value; unknown values stay unknown."""
    if raw is None:return None
    match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(km/h|kmh|kph|mph|knots)?\s*',str(raw).lower())
    if not match:return None
    speed=float(match[1])*({'mph':1.609344,'knots':1.852}.get(match[2],1.))
    return speed if 0<speed<=300 else None

def speed_metadata(tags, direction: int) -> dict:
    suffix='forward' if direction==1 else 'backward'
    key='maxspeed:'+suffix if 'maxspeed:'+suffix in tags else 'maxspeed'
    raw=tags.get(key)
    limit=parse_speed(raw)
    return {'maxspeed_raw':raw, 'speed_limit_kmh':limit,
            'model_speed_kmh':limit if limit is not None else DEFAULT_KMH.get(tags.get('highway'),30.),
            'speed_source':'osm:'+key if limit is not None else 'model_default',
            'speed_tags':{k:v for k,v in tags.items() if k.startswith('maxspeed')},
            'has_conditional_speed':any(k.startswith('maxspeed') and 'conditional' in k for k in tags)}
