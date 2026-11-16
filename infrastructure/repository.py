"""Snapshot identity used by graph and route caches."""
from pathlib import Path
import hashlib
import sys
from functools import lru_cache

SCHEMA_VERSION='roads-v5-edge'
RULES_VERSION='car-rules-v1-speed-v1-time-v1'

def _signature(path: Path) -> tuple:
    stat=path.stat()
    return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)

@lru_cache(maxsize=8)
def _digest(path: str, signature: tuple) -> str:
    resolved=Path(path)
    content=resolved.read_bytes()
    if _signature(resolved)!=signature:
        raise ValueError('Карта файлы оқу кезінде өзгерді. Қайта жүктеңіз.')
    return hashlib.sha256(content).hexdigest()

def snapshot_identity(path: Path) -> tuple[str,str]:
    """Reuse digest while file metadata is unchanged; verify bytes on rebuild.

    POSIX metadata permits digest reuse. Windows ctime can represent creation
    time, so Windows always reads bytes, even if size and mtime are unchanged.
    """
    resolved=path.resolve()
    signature=_signature(resolved)
    if sys.platform == "win32":
        # Bypass only the digest LRU; graph and simulation caches remain active.
        digest=_digest.__wrapped__(str(resolved),signature)
    else:
        digest=_digest(str(resolved),signature)
    return str(resolved), f'{SCHEMA_VERSION}:{RULES_VERSION}:{digest}'

def bytes_version(content: bytes) -> str:
    return f'{SCHEMA_VERSION}:{RULES_VERSION}:{hashlib.sha256(content).hexdigest()}'
