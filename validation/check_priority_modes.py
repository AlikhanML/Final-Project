import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from infrastructure.graph_builder import build_world
from environments.edge_snap import destination_world
from services.dispatch import select_hospital
from services.simulation import simulate_roads
w=build_world(Path('data/astana_city_roads.json'))
rw,goal,snap=destination_world(w,(51.1997645,71.3053036))
h=select_hospital(rw,(51.1997645,71.3053036),goal=goal,hospital_world=w)
rows=[]
for density,seed in ((.7,42),(0.,42)):
 results=[]
 for priority in ('normal','urgent'):
  d=simulate_roads(rw,h['node'],goal,density,0,seed,100,False,priority=priority,traffic_model='corridor',quick_recovery=True,max_steps=1500)
  assert d['status']=='reached'
  assert all(u==v or rw['graph'].has_edge(u,v) for u,v in zip(d['path'],d['path'][1:]))
  assert abs(d['eta_plan_s']-d['elapsed_s'])<1e-6
  results.append(d)
  row=dict(density=density,seed=seed,priority=priority,hospital=h['name'],eta_s=d['eta_plan_s'],elapsed_s=d['elapsed_s'],breakdown=d['eta_breakdown'],status=d['status'],legal=True)
  rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
 normal,urgent=results
 np.testing.assert_array_equal(normal['ambient_traffic'],urgent['ambient_traffic'])
 np.testing.assert_allclose(urgent['traffic'],normal['traffic']*.35)
 if density:
  assert normal['eta_breakdown']['traffic_delay_s']>0
  assert urgent['eta_plan_s']<normal['eta_plan_s']
 else:
  # With no traffic, signal waits can still make normal trips slower.
  for result in results:
   breakdown = result['eta_breakdown']
   np.testing.assert_allclose(breakdown['traffic_delay_s'], 0, atol=1e-6)
   np.testing.assert_allclose(
    breakdown['normal_same_path_s'] - breakdown['urgent_same_path_s'],
    breakdown['normal_signal_delay_s'], atol=1e-6)
  assert urgent['eta_plan_s'] <= normal['eta_plan_s'] + 1e-6
 for result in results:
  breakdown = result['eta_breakdown']
  np.testing.assert_allclose(result['eta_plan_s'], sum(breakdown[key] for key in (
   'free_flow_s', 'traffic_delay_s', 'turn_delay_s', 'signal_delay_s')), atol=1e-6)
 np.testing.assert_allclose(urgent['eta_breakdown']['signal_delay_s'], 0, atol=1e-6)
 assert normal['eta_breakdown']['signal_delay_s'] > 0
Path('validation/priority_city_result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2), encoding='utf-8')
