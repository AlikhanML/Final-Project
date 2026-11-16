"""Correctness gates for stage 7 optimizations, without timing thresholds."""
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from scipy.spatial import cKDTree
from environments.road_world import nearest
from infrastructure.repository import snapshot_identity, _digest

class PerformanceTests(unittest.TestCase):
    def test_index_matches_full_scan(self):
        rng=np.random.default_rng(42)
        coords=rng.uniform([50.85,70.95],[51.45,71.85],(10000,2))
        indexed=dict(coords=coords,spatial_index=cKDTree(coords))
        for query in rng.uniform([50.5,70.5],[52,72],(100,2)):
            self.assertEqual(nearest(indexed,query),nearest(dict(coords=coords),query))
    def test_ties_duplicate_nodes_and_poles(self):
        coords=np.array([[51.,71.],[51.,71.],[51.,72.]])
        w=dict(coords=coords,spatial_index=cKDTree(coords))
        for point in ([51.,71.],[90.,71.],[-90.,72.]):
            self.assertEqual(nearest(w,point),nearest(dict(coords=coords),point))
    def test_unchanged_file_is_read_once(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'roads.json';p.write_bytes(b'one');_digest.cache_clear()
            original=Path.read_bytes
            calls=[]
            def read(path):calls.append(path);return original(path)
            with patch.object(Path,'read_bytes',read):
                first=snapshot_identity(p);second=snapshot_identity(p)
            self.assertEqual(first,second);self.assertEqual(len(calls),2 if sys.platform=="win32" else 1)
    def test_same_size_edit_with_restored_mtime_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'roads.json';p.write_bytes(b'one')
            before=p.stat();first=snapshot_identity(p)
            p.write_bytes(b'two');os.utime(p,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertNotEqual(first,snapshot_identity(p))
    def test_atomic_replacement_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'roads.json';p.write_bytes(b'one');first=snapshot_identity(p)
            new=p.with_suffix('.tmp');new.write_bytes(b'two');new.replace(p)
            self.assertNotEqual(first,snapshot_identity(p))

    def test_windows_detects_change_even_with_identical_metadata(self):
        # Model Windows creation-time semantics on any host OS.
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'roads.json';p.write_bytes(b'one')
            with patch('infrastructure.repository.sys.platform','win32'), \
                 patch('infrastructure.repository._signature',return_value=(1,2,3,4,5)):
                first=snapshot_identity(p)
                p.write_bytes(b'two')
                second=snapshot_identity(p)
                self.assertNotEqual(first,second)
                self.assertEqual(second,snapshot_identity(p))
