import sys,json,time
from pathlib import Path
import networkx as nx
import numpy as np
root=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser(description='Audit 12 road trips; no address or tile requests.')
parser.add_argument('--data',type=Path,default=root/'data/astana_roads.json')
parser.add_argument('--report',type=Path,default=root/'validation/route_audit_result.json')
args=parser.parse_args()
sys.path.insert(0,str(root))
from infrastructure.graph_builder import build_world
from services.simulation import simulate_roads
w=build_world(args.data)
nodes=sorted(max(nx.strongly_connected_components(w['graph']),key=len))
rng=np.random.default_rng(29);pairs=rng.choice(nodes,size=(6,2),replace=False)
rows=[]
for dynamic in (False,True):
 for start,goal in pairs:
  t=time.perf_counter()
  d=simulate_roads(w,int(start),int(goal),.2,0,42,100,dynamic,max_steps=1500,training_updates=30000,compute_budget_s=20,quick_recovery=True,traffic_model='corridor')
  moves=[(i,int(u),int(v)) for i,(u,v) in enumerate(zip(d['path'],d['path'][1:])) if u!=v]
  legal=all(w['graph'].has_edge(u,v) for _,u,v in moves)
  avoided=all((u,v)!=d['blocked'] for i,u,v in moves if d['phases'][i+1])
  reached=d['status']=='reached' and d['path'][-1]==goal
  rows.append(dict(start=int(start),goal=int(goal),dynamic=dynamic,status=d['status'],legal=legal,avoided=avoided,reached=bool(reached),closure=bool(d['blocked']),seconds=round(time.perf_counter()-t,3)))
  print(rows[-1],flush=True)
report={'nodes':len(w['coords']),'edges':w['graph'].number_of_edges(),'coverage':w['source'].get('coverage','district'),'rows':rows}
args.report.write_text(json.dumps(report,indent=2))
assert all(x['legal'] and x['avoided'] and x['reached'] for x in rows)
