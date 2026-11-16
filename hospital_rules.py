"""Conservative hospital eligibility; untyped legacy records are not trusted."""
import re

EXCLUDED = {'pharmacy', 'clinic', 'doctors', 'dentist', 'laboratory',
            'optometrist', 'physiotherapist', 'alternative', 'yes'}


def is_hospital(record):
    tags = record.get('tags')
    if not isinstance(tags, dict):
        return False
    amenity = str(tags.get('amenity', '')).lower().strip()
    healthcare = str(tags.get('healthcare', '')).lower().strip()
    if amenity in EXCLUDED - {'yes'} or healthcare in EXCLUDED - {'yes'}:
        return False
    if amenity != 'hospital' and healthcare != 'hospital':
        return False
    if tags.get('disused') == 'yes' or tags.get('abandoned') == 'yes':
        return False
    names = ' '.join(str(tags.get(k, '')) for k in ('name', 'name:kk', 'name:ru', 'name:en'))
    names += ' ' + str(record.get('name', ''))
    # Conflicting names are rejected even if the source incorrectly tags a hospital.
    return not re.search(r'аптек|дәріхан|дарихан|pharmacy|drugstore|поликлиник|емхан|стоматолог|dental', names, re.I)
