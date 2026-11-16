"""Modeled slowdown and directional queues on the road graph."""
import numpy as np
from domain.models import ASTANA_LANDMARKS
from environments.astana_traffic import astana_traffic

TRAFFIC_MODEL_VERSION = 'astana-rush-hour-v5'
TRAFFIC_CELL_M = 2500.
ASTANA_CENTER = (51.14, 71.43)
CENTRAL_RADIUS_M = 5000.
CENTRAL_CELL_M = 850.
PLACE_APPROACH_M = 40.
ROAD_LOAD = {
    'motorway': (3., 4.), 'motorway_link': (5., 4.),
    'trunk': (7., 4.), 'trunk_link': (7., 4.),
    'primary': (8., 4.), 'primary_link': (8., 4.),
    'secondary': (6., 4.), 'secondary_link': (6., 4.),
    'tertiary': (3., 3.), 'tertiary_link': (3., 3.),
    'unclassified': (0., 0.), 'residential': (0., 0.),
    'service': (0., 0.), 'living_street': (0., 0.),
}


def road_load(edge):
    return ROAD_LOAD.get(edge.get('highway'), (1., 4.))


def _place_approaches(world, rows, targets):
    protected=np.zeros(len(rows),dtype=bool)
    if not len(rows):
        return protected
    source=world.get('source',{})
    places=[(float(record['lat']),float(record['lon'])) for record in source.get('hospitals',())]
    bbox=source.get('bbox')
    if bbox is not None:
        west,south,east,north=bbox
        places.extend((lat,lon) for lat,lon in ASTANA_LANDMARKS.values()
                      if south<=lat<=north and west<=lon<=east)
    if not places:
        return protected
    starts=world['xy'][rows]
    segments=world['xy'][targets]-starts
    squared_length=np.maximum(np.sum(segments*segments,axis=1),1e-12)
    east_scale=111320*np.cos(np.radians(world['lat0']))
    for lat,lon in places:
        point=[(lon-world['lon0'])*east_scale,(lat-world['lat0'])*111320]
        offset=point-starts
        fraction=np.clip(np.sum(offset*segments,axis=1)/squared_length,0.,1.)
        delta=offset-fraction[:,None]*segments
        protected|=np.sum(delta*delta,axis=1)<=PLACE_APPROACH_M**2
    return protected


def _queue_cells(midpoints, weights, cell_size=TRAFFIC_CELL_M):
    cells=np.floor(midpoints/cell_size).astype(int)
    _,groups=np.unique(cells,axis=0,return_inverse=True)
    order=np.argsort(groups,kind='stable')
    splits=np.flatnonzero(np.diff(groups[order]))+1
    return [(edges,np.cumsum(weights[edges])) for edges in np.split(order,splits)]


def _central_edges(world, midpoints):
    bbox=world.get('source',{}).get('bbox')
    lat,lon=ASTANA_CENTER
    if bbox is None or not (bbox[0]<=lon<=bbox[2] and bbox[1]<=lat<=bbox[3]):
        return np.empty(0,dtype=int)
    east_scale=111320*np.cos(np.radians(world['lat0']))
    center=[(lon-world['lon0'])*east_scale,(lat-world['lat0'])*111320]
    offsets=midpoints-center
    return np.flatnonzero(np.sum(offsets*offsets,axis=1)<=CENTRAL_RADIUS_M**2)


def _apply_queues(world, traffic, rows, actions, targets, queues):
    graph=world['graph']
    xy=world['xy']
    slots={(u,v):a for u,v,a in zip(rows.tolist(),targets.tolist(),actions.tolist())}
    for index,queue_length,severity in queues:
        u=int(rows[index]);v=int(targets[index])
        travelled=0.;seen={v}
        for _ in range(128):
            if u in seen:break
            seen.add(u);a=slots[u,v]
            # The strongest delay is near the bottleneck; taper upstream.
            cap=road_load(graph[u][v])[1]
            level=min(cap,severity*(.2+.8*max(0.,1.-travelled/queue_length)))
            traffic[u,a]=max(traffic[u,a],level)
            travelled+=float(world['lengths'][u,a])
            if travelled>=queue_length:break
            outgoing=xy[v]-xy[u];norm=np.linalg.norm(outgoing)
            if norm<1e-9:break
            name=graph[u][v].get('name','');choices=[]
            for p in graph.predecessors(u):
                if p in seen or (p,u) not in slots:continue
                # Do not extend a main-road queue into a courtyard/access road.
                if road_load(graph[p][u])[1]<cap:continue
                incoming=xy[u]-xy[p];scale=np.linalg.norm(incoming)*norm
                if scale<1e-9:continue
                alignment=float(incoming@outgoing/scale)
                if alignment<.70710678:continue
                same=bool(name and name!='Атаусыз жол' and graph[p][u].get('name')==name)
                choices.append((same,alignment,-int(p),int(p)))
            if not choices:break
            v,u=u,max(choices)[-1]


def _sample_queues(cells, count, rng, length_range, severity_range):
    for i in range(count):
        cell_index=i%len(cells)
        if cell_index==0:
            order=rng.permutation(len(cells))
        members,cumulative=cells[order[cell_index]]
        index=np.searchsorted(cumulative,rng.random()*cumulative[-1])
        yield (members[min(index,len(members)-1)], rng.uniform(*length_range),
               rng.uniform(*severity_range))


def corridor_traffic(world, density: float, seed: int) -> np.ndarray:
    """Return nonnegative slowdown: time = free_flow_seconds * (1 + slowdown).

    The city snapshot models reported Astana corridors and bridge approaches.
    Smaller snapshots and synthetic graphs use sampled bottlenecks.
    """
    if not np.isfinite(density) or not 0 <= density <= 1:
        raise ValueError('Traffic density must be between 0 and 1.')
    parent=world.get('_traffic_parent')
    if parent is not None:
        original=corridor_traffic(parent,density,seed)
        traffic=np.zeros_like(world['lengths'],dtype=float)
        n,k=original.shape
        traffic[:n,:k]=original
        sources=world['_traffic_sources']
        # Only split endpoints and the virtual destination have changed slots.
        for u in world['_traffic_rows']:
            traffic[u]=0.
            for action in np.flatnonzero(world['valid'][u]):
                v=int(world['dest'][u,action])
                a,b=sources.get((u,v),(u,v))
                old_action=int(np.flatnonzero(parent['valid'][a] & (parent['dest'][a]==b))[0])
                traffic[u,action]=original[a,old_action]
        return traffic
    cache=world.get('_traffic_cache')
    key=(TRAFFIC_MODEL_VERSION,density,seed)
    if cache is not None and key in cache:
        return cache[key].copy()
    traffic=np.zeros_like(world['lengths'],dtype=float)
    rows,actions=np.nonzero(world['valid'])
    if density==0 or not len(rows):return traffic
    graph=world['graph'];dest=world['dest'];xy=world['xy']
    targets=dest[rows,actions]
    edges=[graph[u][v] for u,v in zip(rows.tolist(),targets.tolist())]
    road_weights,caps=np.array([road_load(edge) for edge in edges]).T
    eligible=road_weights>0
    source=world.get('source',{})
    addressed_ways={str(way.get('id',i)) for i,way in enumerate(source.get('ways',()))
                    if way.get('tags',{}).get('addr:housenumber')}
    if addressed_ways:
        eligible&=np.fromiter((edge.get('way_id') not in addressed_ways for edge in edges),
                              dtype=bool,count=len(edges))
    main=np.flatnonzero(eligible)
    eligible[main]&=~_place_approaches(world,rows[main],targets[main])
    rows,actions,targets=rows[eligible],actions[eligible],targets[eligible]
    if not len(rows):return traffic
    caps=caps[eligible]
    if source.get('coverage')=='city':
        main_edges=[edges[i] for i in np.flatnonzero(eligible)]
        background,queues=astana_traffic(world,rows,actions,targets,main_edges,density,seed)
        traffic[rows,actions]=np.minimum(caps,background)
        _apply_queues(world,traffic,rows,actions,targets,queues)
    else:
        lengths=world['lengths'][rows,actions]
        # Length and road class weight the choice only within the selected cell.
        weights=lengths*road_weights[eligible]*(1.+(world['valid'].sum(axis=1)[targets]>=2))
        midpoints=(xy[rows]+xy[targets])/2
        count=min(1000,max(1,int(np.ceil(lengths.sum()*density/550.))))
        if source.get('bbox') is not None:
            traffic[rows,actions]=np.minimum(caps,max(.06,.75*density))
        queues=_sample_queues(_queue_cells(midpoints,weights),count,np.random.default_rng(seed),
                              (200.,900.),(.6,4.))
        _apply_queues(world,traffic,rows,actions,targets,queues)
        central=_central_edges(world,midpoints)
        if len(central):
            count=min(900,int(np.ceil(lengths[central].sum()*density/185.)))
            cells=_queue_cells(midpoints[central],weights[central],CENTRAL_CELL_M)
            central_rng=np.random.default_rng(np.random.SeedSequence([int(seed),1]))
            queues=_sample_queues(cells,count,central_rng,(200.,650.),(1.4,2.1))
            _apply_queues(world,traffic,rows[central],actions[central],targets[central],queues)
    if cache is not None:
        cache[key]=traffic.copy()
        if len(cache)>3:
            cache.pop(next(iter(cache)))
    return traffic
