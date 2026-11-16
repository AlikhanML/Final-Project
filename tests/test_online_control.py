"""Stage 6: online sensing, consistent commands, road safety and bounded stops."""
import inspect
import unittest
from unittest.mock import patch
import numpy as np
from algorithms.hmm import OnlineRoadHMM
from algorithms.road_control import choose_command, command_transitions
from services.simulation import simulate_roads
from tests.fixtures import road_world

class OnlineControlTests(unittest.TestCase):
    def setUp(self):
        self.w=road_world();self.w.update(lat0=51.13,lon0=71.41)
        self.q=np.zeros_like(self.w['lengths']);self.traffic=self.q.copy()

    def test_controller_has_no_truth_argument(self):
        self.assertEqual(list(inspect.signature(choose_command).parameters),
            ['world','belief','goal','q','traffic','blocked','use_q','min_confidence','planner','previous','turn_model'])

    def test_observation_changes_control_including_q(self):
        for use_q in (False,True):
            commands=[]
            for node in (0,3):
                hmm=OnlineRoadHMM(self.w['xy'],0)
                belief=hmm.update(self.w['xy'][node])
                commands.append(choose_command(self.w,belief,2,self.q,self.traffic,use_q=use_q))
            self.assertNotEqual(commands[0].heading,commands[1].heading)

    def test_heading_is_not_local_action_index(self):
        nxt,actions=command_transitions(self.w,0.) # east
        self.assertEqual(nxt[0],1)
        self.assertEqual(nxt[3],2)
        self.assertNotEqual(actions[0],actions[3])
        self.assertEqual(nxt[1],1) # no eastbound edge => hold

    def test_closed_edge_never_used(self):
        for heading in np.linspace(-np.pi,np.pi,80):
            nxt,_=command_transitions(self.w,heading,(0,1))
            self.assertNotEqual(nxt[0],1)
            for u,v in enumerate(nxt):
                self.assertTrue(u==v or self.w['graph'].has_edge(u,int(v)))

    def test_prediction_matches_actuator(self):
        hmm=OnlineRoadHMM(self.w['xy'],0,recovery=0)
        hmm.update(self.w['xy'][0])
        nxt,_=command_transitions(self.w,0.)
        belief=hmm.update(self.w['xy'][1],nxt)
        self.assertEqual(belief.argmax(),1)
        self.assertAlmostEqual(belief.sum(),1)

    def test_low_confidence_holds(self):
        d=choose_command(self.w,np.ones(4)/4,2,self.q,self.traffic)
        self.assertIsNone(d.heading)
        self.assertEqual(d.reason,'uncertain')

    def test_recovery_from_wrong_initial_fix(self):
        hmm=OnlineRoadHMM(self.w['xy'],0)
        hmm.update(self.w['xy'][3])
        self.assertEqual(hmm.update(self.w['xy'][0],np.arange(4)).argmax(),0)

    def test_nonfinite_sensor_rejected(self):
        hmm=OnlineRoadHMM(self.w['xy'],20)
        with self.assertRaises(ValueError):hmm.update([float('nan'),0])

    def test_noisy_run_bounded_and_legal(self):
        d=simulate_roads(self.w,0,2,0.,100000,42,10,False)
        self.assertEqual(d['status'],'localization_stop')
        self.assertLessEqual(len(d['path']),109)
        self.assertEqual(len(d['confidence']),len(d['path']))
        self.assertEqual(len(d['control_reasons']),len(d['path'])-1)

    def test_decision_after_each_online_update(self):
        calls=[]
        original=OnlineRoadHMM.update
        def update(obj,*args,**kwargs):
            calls.append('sense');return original(obj,*args,**kwargs)
        def choose(*args,**kwargs):
            calls.append('control');return choose_command(*args,**kwargs)
        with patch.object(OnlineRoadHMM,'update',update),patch('services.simulation.choose_command',choose):
            d=simulate_roads(self.w,0,2,0.,0,42,10,False)
        self.assertEqual(d['status'],'reached')
        self.assertEqual(calls,['sense','control']*len(d['path']))

    def test_false_arrival_is_not_success(self):
        fake=np.array([0.,0.,1.,0.])
        with patch.object(OnlineRoadHMM,'update',return_value=fake):
            d=simulate_roads(self.w,0,2,0.,20,42,10,False)
        self.assertEqual(d['status'],'localization_stop')
        self.assertEqual(d['path'][-1],0)
