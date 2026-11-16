import sys,json,time,statistics
from pathlib import Path
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from infrastructure.graph_builder import build_world
from environments.road_world import nearest
from services.simulation import simulate_roads
mode=sys.argv[2] if len(sys.argv)>2 else 'fast'
fast=mode=='fast';load_times=[];route_times=[];statuses=[]
for _ in range(3):
    t=time.perf_counter();w=build_world(root/'data/astana_roads.json');load_times.append(time.perf_counter()-t)
    a=nearest(w,(51.13251,71.40387));b=nearest(w,(51.12829,71.43046))
    opts=dict(training_updates=240000,compute_budget_s=20,max_steps=1500) if fast else {}
    t=time.perf_counter();d=simulate_roads(w,a,b,.2,20,42,100 if fast else 2000,True,**opts);route_times.append(time.perf_counter()-t);statuses.append(d['status'])
print(json.dumps(dict(mode=mode,nodes=len(w['coords']),edges=w['graph'].number_of_edges(),load_median_s=statistics.median(load_times),route_median_s=statistics.median(route_times),load_times=load_times,route_times=route_times,statuses=statuses)))
