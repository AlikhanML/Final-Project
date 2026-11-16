"""Conservative car routing subset; never route through foot/cycle infrastructure."""
CAR_ROADS = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary',
             'unclassified', 'residential', 'living_street', 'service',
             'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'}
ACCESS_KEYS = ('motorcar', 'motor_vehicle', 'vehicle', 'access')


def car_access(tags, direction=None):
    for key in ACCESS_KEYS:
        if direction and key+':'+direction in tags:
            return str(tags[key+':'+direction]).lower() in {'yes', 'permissive', 'designated'}
        if key in tags:
            return str(tags[key]).lower() in {'yes', 'permissive', 'designated'}
    return True


def car_directions(tags):
    """Return +1/-1 permitted way directions; empty means excluded."""
    if tags.get('highway') not in CAR_ROADS or tags.get('area') == 'yes':
        return ()
    if tags.get('footway') in {'sidewalk', 'crossing'} or tags.get('cycleway') == 'track' and tags.get('highway') == 'service':
        return ()
    if any(tags.get(k) == 'yes' for k in ('disused', 'abandoned', 'construction')):
        return ()
    # Conditional restrictions need a time-aware router; omit them conservatively.
    if any(k.endswith(':conditional') and k.split(':')[0] in (*ACCESS_KEYS, 'oneway') for k in tags):
        return ()
    oneway = str(tags.get('oneway:motorcar', tags.get('oneway:motor_vehicle',
        tags.get('oneway', 'yes' if tags.get('junction') == 'roundabout' or tags.get('highway') == 'motorway' else 'no')))).lower()
    directions = (1,) if oneway in {'yes', '1', 'true'} else (-1,) if oneway == '-1' else (1,-1) if oneway in {'no','0','false'} else ()
    return tuple(d for d in directions if car_access(tags, 'forward' if d==1 else 'backward'))
