"""User-approved Astana city hospitals. Coordinates always come from OSM."""
import re
from hospital_rules import is_hospital

APPROVED = {
    1: {'name':'№1 көпбейінді қалалық аурухана','address':'Р. Қошқарбаев даңғылы, 66',
        'house':'66','streets':('қошқарбаев','кошкарбаев','qoshqarba','koshkarba')},
    2: {'name':'№2 көпбейінді қалалық аурухана','address':'Т. Рысқұлов көшесі, 6',
        'house':'6','streets':('рысқұлов','рыскулов','ryskul','rysqul')},
    3: {'name':'№3 көпбейінді қалалық аурухана','address':'Республика даңғылы, 50/2',
        'house':'50/2','streets':('республик','respublik','republic')},
}

def approved_hospital(record):
    """Return canonical approved identity or None; fail closed on ambiguity.

    Require hospital type, city-hospital name and an unambiguous number 1–3.
    If OSM supplies street/house, reject contradictions with the user's list.
    Never infer identity from proximity alone or invent missing coordinates.
    """
    if not is_hospital(record):return None
    tags=record.get('tags',{})
    names=[str(record.get('name',''))]+[str(tags.get(k,'')) for k in ('name','name:kk','name:ru','name:en','official_name','short_name')]
    text=' '.join(names).casefold()
    if re.search(r'детск|балалар|children|pediatric|перинат|perinatal',text):return None
    numbers=set()
    for name in names:
        name=name.casefold()
        if not re.search(r'городск|қалалық|калалык|\bcity\b',name):continue
        if not re.search(r'больниц|аурухан|hospital|\bгб\b|\bмгб\b',name):continue
        numbers.update(int(n) for n in re.findall(r'(?<!\d)\d+(?!\d)',name))
    if len(numbers)!=1:return None
    number=next(iter(numbers))
    if number not in APPROVED:return None
    info=APPROVED[number]
    house=str(tags.get('addr:housenumber','')).strip().replace(' ','')
    street=str(tags.get('addr:street','')).casefold()
    if house and house!=info['house']:return None
    if street and not any(alias in street for alias in info['streets']):return None
    return {'approved_number':number,'name':info['name'],'approved_address':info['address']}
