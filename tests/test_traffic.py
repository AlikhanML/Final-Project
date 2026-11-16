import unittest
import numpy as np
from environments.traffic import corridor_traffic
from tests.test_turn_costs import junction_world
from services.simulation import simulate_roads

class CorridorTrafficTests(unittest.TestCase):
    def test_zero_density_and_illegal_slots(self):
        w=junction_world()
        self.assertFalse(corridor_traffic(w,0,42).any())
        t=corridor_traffic(w,.7,42)
        self.assertFalse(t[~w['valid']].any())
        self.assertTrue(np.isfinite(t).all())
        self.assertTrue((t>=0).all());self.assertTrue((t<=4).all())

    def test_repeatable_and_increasing_load(self):
        w=junction_world()
        a=corridor_traffic(w,.2,42);b=corridor_traffic(w,.7,42)
        np.testing.assert_array_equal(a,corridor_traffic(w,.2,42))
        self.assertTrue(np.all(b>=a))

    def test_cost_and_motion_use_the_same_congestion(self):
        w=junction_world()
        clear=simulate_roads(w,0,2,0,0,42,10,False,traffic_model='corridor')
        busy=simulate_roads(w,0,2,.7,0,42,10,False,traffic_model='corridor')
        self.assertEqual(busy['status'],'reached')
        self.assertGreaterEqual(busy['eta_plan_s'],clear['eta_plan_s'])
        self.assertAlmostEqual(busy['elapsed_s'],busy['eta_plan_s'])
        self.assertIsNone(busy['blocked'])

    def test_invalid_density(self):
        for density in (-1,2,float('nan')):
            with self.assertRaises(ValueError):corridor_traffic(junction_world(),density,42)

    def test_distant_main_roads_share_queues_and_access_stays_green(self):
        import networkx as nx
        lat,lon=51.14,71.43
        scale=111320*np.cos(np.radians(lat))
        x=np.array([0,2000,3500,5500,7500,7550,9500,9550,12500,12560])
        ways=('primary','primary','residential','primary','primary')
        graph=nx.DiGraph()
        graph.add_nodes_from(range(len(x)))
        for i,highway in enumerate(ways):
            graph.add_edge(2*i,2*i+1,highway=highway,way_id=str(i))
        world=dict(
            graph=graph, dest=(np.arange(len(x))|1)[:,None],
            valid=(np.arange(len(x))%2==0)[:,None],
            lengths=np.repeat(np.diff(x)[::2],2)[:,None],
            xy=np.column_stack([x,np.zeros(len(x))]), lat0=lat,lon0=lon,
            source={'bbox':[lon-.2,lat-.2,lon+.2,lat+.2],
                    'ways':[{'id':3,'tags':{'addr:housenumber':'17'}}],
                    'hospitals':[{'lat':lat,'lon':lon+12520/scale}]},
        )
        samples=np.array([corridor_traffic(world,.5,seed)[:,0] for seed in range(12)])
        self.assertTrue((samples[:,[0,2]]>=.6).all())
        self.assertTrue((samples[:,[0,2]]>=1.).any(axis=0).all())
        self.assertFalse(samples[:,[4,6,8]].any())
        self.assertFalse(corridor_traffic(world,0.,42).any())

    def test_queue_is_connected_and_directional(self):
        import networkx as nx
        n=20;g=nx.DiGraph();g.add_edges_from((i,i+1,{'name':'Test road'}) for i in range(n-1))
        dest=np.arange(1,n+1)[:,None];dest[-1]=n-1
        valid=np.ones((n,1),bool);valid[-1]=False
        w=dict(graph=g,dest=dest,valid=valid,lengths=np.full((n,1),100.),xy=np.column_stack([np.arange(n)*100.,np.zeros(n)]))
        t=corridor_traffic(w,.001,42)[:,0];ids=np.flatnonzero(t)
        self.assertGreater(len(ids),1)
        self.assertTrue(np.all(np.diff(ids)==1))
        self.assertTrue(np.all(np.diff(t[ids])>0))

    def test_central_main_road_has_more_red_stretches_than_outskirts(self):
        import networkx as nx

        lat,lon=51.14,71.43
        n=73
        graph=nx.DiGraph()
        graph.add_edges_from((i,i+1,{'highway':'primary','name':'Test road'}) for i in range(n-1))
        world=dict(
            graph=graph, dest=np.minimum(np.arange(1,n+1),n-1)[:,None],
            valid=(np.arange(n)<n-1)[:,None], lengths=np.full((n,1),50.),
            xy=np.column_stack([np.arange(n)*50.,np.zeros(n)]),
            lat0=lat,lon0=lon,source={'bbox':[lon-.3,lat-.2,lon+.3,lat+.2]},
        )
        central=corridor_traffic(world,.2,42)
        outskirts=corridor_traffic(dict(world,lon0=lon+.15),.2,42)
        self.assertGreater(np.count_nonzero(central>=1.),np.count_nonzero(outskirts>=1.))
        self.assertTrue(np.any((central>.05) & (central<1.)))
        self.assertTrue(np.all(central>=outskirts))

class ProjectedTrafficTests(unittest.TestCase):
    def test_destination_split_preserves_city_delays_in_both_directions(self):
        from tests.fixtures import road_world
        from environments.edge_snap import destination_world
        from environments.travel_time import route_seconds
        w=road_world();w.update(lat0=51.13,lon0=71.41,dataset_version='test')
        rw,goal,snap=destination_world(w,(51.1299,71.4105))
        for seed in (1,42,99):
            original=corridor_traffic(w,.7,seed)
            projected=corridor_traffic(rw,.7,seed)
            for u,v in rw['graph'].edges():
                a,b=rw['_traffic_sources'].get((u,v),(u,v))
                ai=np.flatnonzero(w['valid'][a] & (w['dest'][a]==b))[0]
                bi=np.flatnonzero(rw['valid'][u] & (rw['dest'][u]==v))[0]
                self.assertEqual(original[a,ai],projected[u,bi])
            u,v=snap['edge']
            self.assertAlmostEqual(route_seconds(w,[u,v],original),route_seconds(rw,[u,goal,v],projected))
            self.assertFalse(projected[~rw['valid']].any())


class AstanaTrafficTests(unittest.TestCase):
    def test_real_junction_builds_upstream_queue_and_other_roads_stay_clear(self):
        import networkx as nx

        lat, lon = 51.14610, 71.41205  # Тұран – Қорғалжын
        xy = np.array([
            [0, -500], [0, -290], [0, -110], [0, 0], [0, 110], [0, 290],
            [-120, 0], [0, -700], [1500, 0], [1500, 100],
        ], dtype=float)
        coords = np.column_stack((lat + xy[:, 1] / 111320,
                                  lon + xy[:, 0] / (111320 * np.cos(np.radians(lat)))))
        graph = nx.DiGraph()
        graph.add_nodes_from(range(len(xy)))
        roads = [(i, i + 1, 'Тұран даңғылы', 'primary') for i in range(5)]
        roads += [(6, 3, 'Қорғалжын тас жолы', 'secondary'),
                  (7, 0, 'Аула', 'service'), (8, 9, 'Басқа магистраль', 'primary')]
        dest = np.arange(len(xy))[:, None]
        valid = np.zeros_like(dest, dtype=bool)
        lengths = np.ones_like(dest, dtype=float)
        for u, v, name, highway in roads:
            graph.add_edge(u, v, name=name, highway=highway)
            dest[u, 0], valid[u, 0] = v, True
            lengths[u, 0] = np.linalg.norm(xy[v] - xy[u])
        world = dict(graph=graph, coords=coords, dest=dest, valid=valid, lengths=lengths,
                     xy=xy, lat0=lat, lon0=lon, source={'coverage': 'city'})

        quiet = corridor_traffic(world, .05, 42)[:, 0]
        peak = corridor_traffic(world, .2, 42)[:, 0]
        self.assertTrue(np.all(quiet <= peak))
        self.assertLess(peak[1], peak[2])
        self.assertGreaterEqual(peak[2], 1.)
        self.assertGreaterEqual(peak[6], 1.)
        self.assertTrue(0.05 < peak[3] < 1.)
        self.assertEqual(peak[7], 0.)
        self.assertEqual(peak[8], 0.)


class RoadClassTrafficTests(unittest.TestCase):
    def test_access_streets_stay_green_at_maximum_density(self):
        for kind in ('service','living_street','residential','unclassified'):
            w=junction_world()
            for _,_,edge in w['graph'].edges(data=True):edge['highway']=kind
            for seed in range(12):
                self.assertFalse(corridor_traffic(w,1.,seed).any())

    def test_main_roads_receive_more_congestion_on_equal_geometry(self):
        # Two disconnected, otherwise identical junctions: isolate road class.
        import networkx as nx
        a=junction_world();n=len(a['coords'])
        graph=nx.compose(a['graph'],nx.relabel_nodes(a['graph'],{i:i+n for i in a['graph']}))
        for u,v,e in graph.edges(data=True):e['highway']='primary' if u<n else 'service'
        w=dict(graph=graph,dest=np.vstack([a['dest'],a['dest']+n]),
               valid=np.vstack([a['valid'],a['valid']]),lengths=np.vstack([a['lengths'],a['lengths']]),
               xy=np.vstack([a['xy'],a['xy']+[10000,0]]))
        totals=np.zeros(2)
        for seed in range(40):
            t=corridor_traffic(w,.7,seed)
            totals += [t[:n].sum(),t[n:].sum()]
        self.assertGreater(totals[0],totals[1]*10)
