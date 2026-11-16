"""Download Astana motor-road data once; existing data survives failed downloads."""
from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.request
import urllib.parse
import os
from hospital_rules import is_hospital
from road_rules import car_directions

CITY_FILE = Path(__file__).parent / 'data' / 'astana_city_roads.json'
# Broad city-and-outskirts extract, not an administrative boundary.
BBOX = [70.95, 50.85, 71.85, 51.45]
ENDPOINT = 'https://overpass-api.de/api/interpreter'


def convert(raw):
    if raw.get('remark'):
        raise ValueError('Карта сервері толық жауап бермеді: ' + raw['remark'])
    nodes = {str(x['id']): [x['lat'], x['lon']] for x in raw['elements'] if x['type'] == 'node'}
    ways = []
    for item in raw['elements']:
        if item['type'] != 'way' or not car_directions(item.get('tags', {})):
            continue
        ids = [str(n) for n in item['nodes']]
        if len(ids) > 1 and all(n in nodes for n in ids):
            ways.append({'id': item['id'], 'nodes': ids, 'tags': item.get('tags', {})})
    if len(nodes) < 5000 or len(ways) < 500:
        raise ValueError('Қалалық жол базасы толық емес. Бұрынғы база сақталды.')
    return {'nodes': nodes, 'ways': ways, 'bbox': BBOX, 'coverage': 'city',
            'retrieved': datetime.now(timezone.utc).isoformat(),
            'source': ENDPOINT, 'attribution': '© OpenStreetMap contributors, ODbL 1.0'}


def download_city():
    west, south, east, north = BBOX
    query = f'''[out:json][timeout:180];
    way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]
    ["area"!="yes"]["access"!~"^(no|private)$"]["motor_vehicle"!="no"]["motorcar"!="no"]
    ({south},{west},{north},{east});(._;>;);out body;'''
    request = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode({'data': query}).encode(),
                                    headers={'User-Agent': 'Qadam-University-Project/1.0'})
    with urllib.request.urlopen(request, timeout=240) as response:
        data = convert(json.load(response))
    # Hospital coordinates are real OSM objects, not invented demo locations.
    hospital_query = f'''[out:json][timeout:90];
    (nwr["amenity"="hospital"]({south},{west},{north},{east});
    nwr["healthcare"="hospital"]({south},{west},{north},{east}););out center tags;'''
    request = urllib.request.Request(ENDPOINT,
        data=urllib.parse.urlencode({'data': hospital_query}).encode(),
        headers={'User-Agent': 'Qadam-University-Project/1.0'})
    with urllib.request.urlopen(request, timeout=120) as response:
        hospitals_raw = json.load(response)
    if hospitals_raw.get('remark'):
        raise ValueError('Аурухана деректері толық жүктелмеді. Кейін қайталаңыз.')
    hospitals = []
    for item in hospitals_raw.get('elements', []):
        center = item if 'lat' in item else item.get('center', {})
        if 'lat' not in center or 'lon' not in center:
            continue
        tags = item.get('tags', {})
        if not is_hospital({'tags': tags}):
            continue
        hospitals.append({'id': str(item['type'])+'/'+str(item['id']),
            'name': tags.get('name:kk') or tags.get('name') or 'Аурухана (OSM '+str(item['id'])+')',
            'lat': center['lat'], 'lon': center['lon'], 'tags': tags})
    if not hospitals:
        raise ValueError('Ауруханалар табылмады. Бұрынғы база сақталды.')
    data['hospitals'] = hospitals
    CITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CITY_FILE.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        os.replace(temporary, CITY_FILE)
    finally:
        temporary.unlink(missing_ok=True)
    return len(data['nodes']), len(data['ways'])


if __name__ == '__main__':
    print('Downloading Astana roads. Internet required; this may take several minutes.', flush=True)
    try:
        nodes, ways = download_city()
        print(f'Done: {nodes} nodes, {ways} ways. Restart the app.')
    except Exception as exc:
        print(f'Download failed: {exc}. Existing data was not changed.')
        raise SystemExit(1)
