"""Private, disposable disk cache for worlds built by this installation.

Pickles are only read from the app's own local cache, never from uploaded files.
Content/source/dependency fingerprints invalidate incompatible entries.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import logging
import os
import pickle
import sys
import tempfile
from infrastructure.graph_builder import build_world
from infrastructure.repository import snapshot_identity

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def cache_root():
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')
    return base/'Qadam'/'road-graphs-v1'


def cache_key(path, version):
    sources = ['infrastructure/graph_builder.py', 'infrastructure/speeds.py',
               'infrastructure/repository.py', 'environments/travel_time.py',
               'environments/edge_snap.py', 'utils/geo.py', 'road_rules.py',
               'infrastructure/graph_cache.py']
    digest = hashlib.sha256()
    for name in sources:
        digest.update((ROOT/name).read_bytes())
    dependencies = [(name, importlib.metadata.version(name))
                    for name in ('networkx','numpy','scipy','shapely','pyproj')]
    digest.update(json.dumps([str(Path(path).resolve()), version, sys.version,
                              dependencies], sort_keys=True).encode())
    return digest.hexdigest()


def load_cached_world(path, expected_version, *, directory=None):
    """Load a private snapshot, rebuilding corrupt/missing caches atomically.

    Source identity is checked before and after I/O. Failed cache writes never
    prevent using a freshly built graph. Each load returns a separate world.
    """
    path = Path(path)
    def check_source():
        if snapshot_identity(path)[1] != expected_version:
            raise ValueError('Карта файлы өзгерді. Қайта жүктеңіз.')
    check_source()
    directory = Path(directory) if directory is not None else cache_root()
    target = directory/(cache_key(path, expected_version)+'.bin')
    world = None
    try:
        with target.open('rb') as f:
            checksum = f.read(32)
            payload = f.read()
        if hashlib.sha256(payload).digest() != checksum:
            raise ValueError('Cache checksum mismatch')
        world = pickle.loads(payload)
        if not isinstance(world, dict) or world.get('dataset_version') != expected_version:
            raise ValueError('Cache version mismatch')
    except (OSError, ValueError, EOFError, pickle.UnpicklingError, ImportError, AttributeError, TypeError):
        world = None
    if world is not None:
        check_source()
        return world
    world = build_world(path, expected_version=expected_version)
    check_source()
    temporary = None
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = pickle.dumps(world, protocol=pickle.HIGHEST_PROTOCOL)
        with tempfile.NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            f.write(hashlib.sha256(payload).digest())
            f.write(payload)
        check_source()
        os.replace(temporary, target)
    except OSError as exc:
        LOG.warning('Road disk cache unavailable: %s', exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return world
