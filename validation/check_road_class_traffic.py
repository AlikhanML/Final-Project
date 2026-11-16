"""Audit synthetic congestion by OSM road class on the unchanged city snapshot."""
import sys,json
from pathlib import Path
from collections import defaultdict
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from infrastructure.graph_builder import build_world
from environments.traffic import corridor_traffic, TRAFFIC_MODEL_VERSION
w=build_world(root/'data/astana_city_roads.json')
t=corridor_traffic(w,.2,42)
stats=defaultdict(lambda:dict(edges=0,red=0,slow=0,length=0.,delay_weight=0.))
for u,a in np.argwhere(w['valid']):
    v=int(w['dest'][u,a]);edge=w['graph'][int(u)][v]
    s=stats[edge.get('highway','unknown')];value=float(t[u,a]);length=float(edge['length'])
    s['edges']+=1;s['red']+=int(value>=2);s['slow']+=int(value>.05)
    s['length']+=length;s['delay_weight']+=length*value
for s in stats.values():s['mean_slowdown_by_length']=s.pop('delay_weight')/s.pop('length')
for kind in ('service','living_street','residential'):
    if kind in stats:assert stats[kind]['red']==0
assert stats['primary']['red']>0
assert stats['primary']['mean_slowdown_by_length']>stats['service']['mean_slowdown_by_length']
report=dict(model=TRAFFIC_MODEL_VERSION,density=.2,seed=42,classes=dict(stats))
(root/'validation/road_class_traffic_result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
