"""Run all regression tests locally with outbound connections disabled."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

if __name__ == '__main__':
    root=Path(__file__).resolve().parent
    suite=unittest.defaultTestLoader.discover(str(root),pattern='test_*.py',top_level_dir=str(root))
    with patch('socket.socket.connect',side_effect=AssertionError('Tests must not access network')), \
         patch('socket.create_connection',side_effect=AssertionError('Tests must not access network')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
