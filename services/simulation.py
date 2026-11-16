from environments.traffic import corridor_traffic
from services.call_priority import congestion_factor
from environments.traffic_signals import signal_waits
from time import perf_counter
"""Simulation orchestration; framework-free and deterministic by seed."""
from algorithms.road_control import choose_command, command_transitions, RoutePlan, CommandModel
from algorithms.hmm import OnlineRoadHMM
import numpy as np
import networkx as nx
from algorithms.astar import astar, astar_roads
from algorithms.q_learning import train_q, q_train, q_train_turns
from environments.turn_costs import TurnModel
from algorithms.hmm import hmm_filter, filter_roads
from environments.grid_world import make_world, step
from environments.road_world import transition_table
from utils.geo import to_latlon
from algorithms.policies import best_valid_action
from environments.travel_time import action_seconds, route_seconds

def execute(old, new, old_traffic, new_traffic, baseline, q, event_at, seed, start=None, goal=None, *, dynamic=True, diagnostics=None, max_steps=None):
    rng = np.random.default_rng(seed)
    n = len(old)
    goal = (n-1, n-1) if goal is None else tuple(goal)
    pos = (0, 0) if start is None else tuple(start)
    path, actions, grids, phases = [pos], [], [], [False]
    elapsed, fallback = 0.0, False
    seen = {}
    status='step_limit'
    for t in range(6*n*n if max_steps is None else max_steps):
        if pos == goal:
            break
        changed = dynamic and t >= event_at
        grid, traffic = (new, new_traffic) if changed else (old, old_traffic)
        if not changed:
            plan = astar(grid, pos, goal)
            if not plan:
                status="no_route"
                break
            action = next(a for a in range(4) if step(grid, pos, a) == plan[1])
        else:
            seen[pos] = seen.get(pos, 0) + 1
            if seen[pos] > 4:
                fallback = True
            if fallback:
                plan = astar(grid, pos, goal, traffic)
                if not plan:
                    status="no_route"
                    break
                action = next(a for a in range(4) if step(grid, pos, a) == plan[1])
            else:
                allowed=np.array([step(grid,pos,a)!=pos for a in range(4)])
                action=best_valid_action(q[pos[0]*n+pos[1]],allowed)
                if action is None:
                    status='no_valid_actions'
                    break
        intended = step(grid, pos, action)
        nxt = intended if rng.random() < 0.9 else pos
        elapsed += 1 + traffic[nxt]
        actions.append(action)
        grids.append(grid)
        pos = nxt
        path.append(pos)
        phases.append(changed)
        if pos == goal:
            break
    if pos==goal: status='reached'
    if diagnostics is not None: diagnostics['status']=status
    return np.array(path), actions, grids, np.array(phases), elapsed, fallback


def simulate(n, density, sigma, seed, sweeps, dynamic, start=None, goal=None):
    grid, traffic = make_world(n, density, seed)
    start = (0, 0) if start is None else tuple(start)
    goal = (n-1, n-1) if goal is None else tuple(goal)
    baseline = astar(grid, start, goal)
    if not baseline:
        raise ValueError("Бастау мен мақсат арасында жол жоқ.")
    event_at = max(2, len(baseline)//3)
    new = grid.copy()
    traffic2 = traffic.copy()
    blocked = None
    if dynamic:
        # Бұғаттау уақытында көлік әлі жете алмайтын ұяшық таңдалады.
        for cell in baseline[event_at+2:-1]:
            candidate = grid.copy()
            candidate[cell] = True
            if astar(candidate, start, goal):
                new, blocked = candidate, cell
                break
        rng = np.random.default_rng(seed+1)
        traffic2 = (rng.random((n, n)) < density)*rng.integers(2, 7, (n, n))
        traffic2 = traffic2.astype(float)
        traffic2[new] = 0
        traffic2[0, 0] = traffic2[goal] = 0
    # Екі режим бөлек стационар MDP ретінде үйретіледі.
    # Екіншісінің Q кестесі біріншіден басталады (warm start).
    q0, h0 = train_q(grid, traffic, goal, seed+2, sweeps)
    q1, h1 = train_q(new, traffic2, goal, seed+3, sweeps, q0)
    diagnostics={}
    path, actions, grids, phases, elapsed, fallback = execute(
        grid, new, traffic, traffic2, baseline, q1, event_at, seed+4, start, goal, dynamic=dynamic, diagnostics=diagnostics)
    gps = path + np.random.default_rng(seed+5).normal(0, sigma, path.shape)
    filtered, beliefs = hmm_filter(gps, actions, grids, grid, sigma)
    return dict(grid=grid, new=new, traffic=traffic, traffic2=traffic2,
                baseline=np.array(baseline), path=path, gps=gps, filtered=filtered,
                beliefs=beliefs, phases=phases, elapsed=elapsed, fallback=fallback,
                event_at=event_at, blocked=blocked, h0=h0, h1=h1,status=diagnostics["status"])


def simulate_roads(w,start,goal,density,sigma,seed,batches,dynamic, *, max_steps=None, max_relocalizations=8, turn_penalties=None, training_updates=None, compute_budget_s=None, quick_recovery=False, traffic_model="independent", priority="normal"):
    """Time-weighted road simulation. ETA and playback timestamps are seconds.

    Traffic is synthetic and fixed for this trip. The closure becomes known
    at a node after one third of the initial ETA. HMM observes arrivals and waiting samples before each control decision.
    """
    started=perf_counter()
    if traffic_model=='corridor':
        traffic=corridor_traffic(w,density,seed)
    elif traffic_model=='independent':
        rng=np.random.default_rng(seed)
        traffic=(rng.random(w['dest'].shape)<density)*rng.uniform(.5,3,w['dest'].shape)
        traffic[~w['valid']]=0
    else:
        raise ValueError('Unknown traffic model')
    factor=congestion_factor(priority)
    ambient_traffic=traffic.copy()
    traffic=traffic*factor
    normal_signals=signal_waits(w,seed)
    normal_signals[start]=0.
    signals=normal_signals if priority=='normal' else np.zeros_like(normal_signals)
    turns=TurnModel(w,traffic,turn_penalties,node_waits=signals)
    turns.deadline=None if compute_budget_s is None else started+compute_budget_s
    seconds=turns.base_seconds
    base=turns.route(start,goal)
    eta_plan_s=turns.route_time(base)
    free_flow_s=route_seconds(w,base)
    ambient_delay_s=max(0.,route_seconds(w,base,ambient_traffic)-free_flow_s)
    traffic_delay_s=ambient_delay_s*factor
    signal_delay_s=float(sum(signals[u] for u in base[:-1]))
    normal_signal_s=float(sum(normal_signals[u] for u in base[:-1]))
    eta_breakdown=dict(signal_delay_s=signal_delay_s,normal_signal_delay_s=normal_signal_s,free_flow_s=free_flow_s,traffic_delay_s=traffic_delay_s,
                       turn_delay_s=max(0.,eta_plan_s-free_flow_s-traffic_delay_s-signal_delay_s),
                       same_path_saving_s=ambient_delay_s-traffic_delay_s+(normal_signal_s if priority=='urgent' else 0.))
    # Compare identical road geometry; each mode may otherwise choose a different route.
    fixed_s=free_flow_s+eta_breakdown['turn_delay_s']
    eta_breakdown['normal_same_path_s']=fixed_s+ambient_delay_s+normal_signal_s
    eta_breakdown['urgent_same_path_s']=fixed_s+ambient_delay_s*congestion_factor('urgent')
    event_time_s=eta_plan_s/3
    blocked=None
    reachable_before=nx.ancestors(w['graph'],goal)|{goal}
    if dynamic:
        cumulative=0.0;previous_base=None;trigger_node=None;trigger_previous=None;closure_attempts=0
        for u,v in zip(base,base[1:]):
            if cumulative>=event_time_s and closure_attempts<8:
                closure_attempts+=1
                if trigger_node is None:trigger_node=u;trigger_previous=previous_base
                try:
                    turns.route(trigger_node,goal,(u,v),trigger_previous)
                    # Synthetic events must not trap a vehicle that deviated
                    # from the nominal route because of noisy localization.
                    view=nx.subgraph_view(w['graph'],filter_edge=lambda a,b: (a,b)!=(u,v))
                    if (nx.ancestors(view,goal)|{goal}) == reachable_before:
                        blocked=(u,v);break
                except nx.NetworkXNoPath: pass
            a=int(np.flatnonzero((w['dest'][u]==v)&w['valid'][u])[0])
            cumulative+=seconds[u,a]+turns.penalty(previous_base,u,v)[0]
            previous_base=u
    # Known-map actuator guard: never enter a one-way dead end that cannot
    # reach the goal. Shared with the HMM transition model, not truth-based.
    reachable_mask=np.zeros(len(w['coords']),dtype=bool)
    reachable_mask[list(reachable_before)]=True
    # Accepted closures preserve the entire reachable set.
    command_model=CommandModel(w,None,reachable_mask)
    blocked_model=CommandModel(w,blocked,reachable_mask) if blocked is not None else None
    # No changed environment => policy uses A*, no unused Q training.
    q,hist=(q_train_turns(turns,goal,blocked,seed+1,batches,max_updates=training_updates)
            if blocked is not None else (None,[]))
    pos=start;path=[pos];phases=[False]
    timestamps=[0.0];segment_times=[]
    visits={};fallback_at=None;travel=0.;elapsed=0.;event=None
    sensor=np.random.default_rng(seed+3)
    hmm=OnlineRoadHMM(w['xy'],sigma)
    gps=[w['xy'][pos]+sensor.normal(0,sigma,2)]
    belief=hmm.update(gps[-1])
    estimates=[int(belief.argmax())];confidence=[float(belief.max())]
    reasons=[];headings=[];waits=0;arrival_confirmations=0;relocalizations=0
    recovery_events=[]
    stationary_s=0.
    recovery_waits=3 if quick_recovery else 12
    stationary_limit=30. if quick_recovery else float('inf')
    status='step_limit'
    planner=RoutePlan(w,goal,traffic,turns,initial_path=base)
    previous_true=None;last_estimate=None;previous_estimate=None
    turn_delays=[];turn_kinds=[];signal_delays=[]
    for t in range(max(3000,len(base)*5) if max_steps is None else max_steps):
        if compute_budget_s is not None and perf_counter()-started>=compute_budget_s:
            status='compute_limit';break
        changed=bool(dynamic and blocked is not None and elapsed>=event_time_s)
        if changed and event is None:event=len(path)-1
        estimate=int(belief.argmax())
        if last_estimate is not None and estimate!=last_estimate:
            previous_estimate=last_estimate if w['graph'].has_edge(last_estimate,estimate) else None
        last_estimate=estimate
        visits[estimate]=visits.get(estimate,0)+1
        if visits[estimate]>4 and fallback_at is None:fallback_at=len(path)-1
        decision=choose_command(w,belief,goal,q,traffic,blocked if changed else None,
                                use_q=changed and fallback_at is None,planner=planner,previous=previous_estimate,turn_model=turns)
        # Arrival is decided from the posterior; truth is used only to score it.
        if decision.reason=='estimated_arrival':
            arrival_confirmations+=1
            if sigma==0 or arrival_confirmations>=3:
                status='reached' if pos==goal else 'localization_stop'
                break
        else: arrival_confirmations=0
        model=blocked_model if changed else command_model
        if sigma==0:
            actuator_ids,actuator_actions=model.transition(decision.heading,np.array([pos]))
            action,nxt=int(actuator_actions[0]),int(actuator_ids[0])
            next_ids=None
        else:
            next_ids,actuator_actions=model.transition(decision.heading)
            action,nxt=int(actuator_actions[pos]),int(next_ids[pos])
        # Physics alone reads true state to execute a global physical command.
        delay,kind=turns.penalty(previous_true,pos,nxt) if action>=0 else (0.,'wait')
        duration=float(seconds[pos,action])+delay if action>=0 else min(2.0,max(0.,stationary_limit-stationary_s))
        turn_delays.append(delay);turn_kinds.append(kind)
        signal_delays.append(float(signals[pos]) if action>=0 else 0.)
        if action>=0:travel+=w['lengths'][pos,action]
        waits=waits+1 if action<0 else 0
        if nxt!=pos:previous_true=pos
        elapsed+=duration;pos=nxt;path.append(pos);phases.append(changed)
        timestamps.append(elapsed);segment_times.append(duration)
        reasons.append(decision.reason);headings.append(decision.heading)
        observation=w['xy'][pos]+sensor.normal(0,sigma,2)
        raw_observation=observation.copy()
        observation_sigma=sigma
        if waits>=recovery_waits and relocalizations<max_relocalizations and stationary_s+duration<=stationary_limit-.2:
            # Stationary independent sensor samples; no true state reaches policy.
            # Each sample takes 0.2 s. Average only this new, disjoint batch.
            samples=64*min(relocalizations+1,3)
            if quick_recovery:samples=min(samples,int((stationary_limit-stationary_s-duration)/.2+1e-9))
            observations=w['xy'][pos]+sensor.normal(0,sigma,(samples,2))
            observation=observations.mean(axis=0)
            observation_sigma=sigma/np.sqrt(samples)
            extra_time=samples*.2
            elapsed+=extra_time;timestamps[-1]=elapsed;segment_times[-1]+=extra_time
            # Discard a possibly wrong prior before relocalizing from new readings.
            hmm.belief[:]=1/len(hmm.belief)
            relocalizations+=1;waits=0;arrival_confirmations=0
            previous_estimate=None;last_estimate=None
            recovery_events.append({'index':len(path)-1,'samples':samples,'sigma_m':float(observation_sigma)})
        gps.append(raw_observation)
        source_nodes=None
        if sigma==0:
            # Exact observations have sparse support. Physics and HMM still
            # execute the same command independently of each other's state.
            source_nodes=np.flatnonzero(hmm.belief)
            next_ids,_=model.transition(decision.heading,source_nodes)
        belief=hmm.update(observation,None if observation_sigma!=sigma else next_ids,
                          observation_sigma=observation_sigma,source_nodes=source_nodes)
        estimate=int(belief.argmax())
        estimates.append(estimate);confidence.append(float(belief[estimate]))
        stationary_s=stationary_s+segment_times[-1] if path[-1]==path[-2] else 0.
        # Never accumulate minutes of stationary recovery at the same place.
        # This is an explicit failed localization, not a fabricated arrival.
        if waits>=12 or stationary_s>=stationary_limit-1e-9:
            status='localization_stop';break
    path=np.array(path);gps=np.array(gps)
    est=np.array(estimates);conf=np.array(confidence)
    return dict(base=base,path=path,phases=np.array(phases),blocked=blocked,event=event,
                event_time_s=event_time_s,traffic=traffic,ambient_traffic=ambient_traffic,priority=priority,congestion_factor=factor,gps=gps,gps_geo=to_latlon(w,gps),
                filtered=est,confidence=conf,travel=travel,cost=elapsed,elapsed_s=elapsed,
                eta_plan_s=eta_plan_s,eta_breakdown=eta_breakdown,timestamps_s=np.array(timestamps),
                segment_times_s=np.array(segment_times),fallback_at=fallback_at,history=hist,status=status,control_reasons=reasons,
                headings=headings,control_mode="hmm_map",astar_searches=planner.searches,relocalizations=relocalizations,recovery_events=recovery_events,
                turn_delays_s=np.array(turn_delays),turn_kinds=turn_kinds,
                signal_delays_s=np.array(signal_delays),stop_delays_s=np.array(turn_delays)+np.array(signal_delays),
                traffic_model=traffic_model,turn_penalties=turns.penalties,turn_total_s=float(sum(turn_delays)),compute_s=perf_counter()-started)
