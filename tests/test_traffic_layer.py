import unittest
import numpy as np
from ui.traffic_layer import traffic_bands

class CityTrafficLayerTests(unittest.TestCase):
    def world(self,n):
        dest=np.column_stack([np.maximum(0,np.arange(n)-1),np.minimum(n-1,np.arange(n)+1)])
        valid=dest!=np.arange(n)[:,None]
        return dict(coords=np.column_stack([np.arange(n),np.zeros(n)]),dest=dest,valid=valid)

    def test_all_edges_beyond_previous_limit_are_preserved(self):
        w=self.world(3005);t=np.zeros_like(w['dest'],dtype=float)
        bands=traffic_bands(w,t)
        self.assertEqual(len(bands[0]),1)
        self.assertEqual(len(bands[0][0]),3005)
        self.assertFalse(any(bands[1:]))

    def test_colors_and_busier_direction(self):
        w=self.world(5);t=np.zeros_like(w['dest'],dtype=float)
        t[1,1]=.5;t[2,1]=1.5;t[4,0]=3.
        bands=traffic_bands(w,t)
        self.assertEqual([len(b) for b in bands],[1,1,1,1])
        self.assertEqual(bands[3][0],[[3.,0.],[4.,0.]])
        three=traffic_bands(w,t,three_colors=True)
        self.assertEqual([len(b) for b in three],[1,1,0,1])
        self.assertEqual(three[3][0],[[2.,0.],[3.,0.],[4.,0.]])

    def test_closed_loop_is_not_dropped(self):
        w=dict(coords=np.array([[0,0],[1,0],[1,1]]),dest=np.array([[1,2],[0,2],[0,1]]),valid=np.ones((3,2),bool))
        bands=traffic_bands(w,np.zeros((3,2)))
        self.assertEqual(len(bands[0]),1)
        self.assertEqual(len(bands[0][0]),4)
        self.assertEqual(bands[0][0][0],bands[0][0][-1])
