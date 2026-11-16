"""Offline repeatable before/after benchmark on the bundled district snapshot."""
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
import numpy as np
from infrastructure.graph_builder import build_world
from environments.road_world import nearest
from algorithms.road_control import choose_command
from services.simulation import simulate_roads

def main():
    world=build_world(Path(__file__).parent/'data'/'astana_roads.json')
    a=nearest(world,(51.13251,71.40387));b=nearest(world,(51.12829,71.43046))
    def uncached(*args,**kwargs):
        kwargs['planner']=None
        return choose_command(*args,**kwargs)
    begin=perf_counter()
    with patch('services.simulation.choose_command',uncached):
        old=simulate_roads(world,a,b,.2,20,42,2000,True)
    before=perf_counter()-begin
    begin=perf_counter()
    new=simulate_roads(world,a,b,.2,20,42,2000,True)
    after=perf_counter()-begin
    for key in ('path','filtered','gps','confidence','timestamps_s','phases','traffic'):
        np.testing.assert_array_equal(old[key],new[key])
    assert old['status']==new['status']
    print(f'Without route reuse: {before:.3f}s; with reuse: {after:.3f}s; ratio: {before/after:.2f}x')
    print(f'Controller A* searches: {new["astar_searches"]}. Scenario outputs identical.')
    print('One local run; not a full-city or browser performance guarantee.')

if __name__=='__main__':main()
