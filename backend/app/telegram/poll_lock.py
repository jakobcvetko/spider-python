from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_LOCK_PATH = Path(os.environ.get("TMPDIR", "/tmp")) / "spider-telegram-poll.lock"
_holder: object | None = None


def try_acquire_polling_lock() -> bool:
    """Ensure only one local process long-polls getUpdates for this bot."""
    global _holder
    try:
        import fcntl
    except ImportError:
        return True

    handle = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False

    handle.write(str(os.getpid()))
    handle.flush()
    _holder = handle
    return True


def release_polling_lock() -> None:
    global _holder
    if _holder is None:
        return
    try:
        import fcntl

        fcntl.flock(_holder.fileno(), fcntl.LOCK_UN)
    except Exception:
        log.debug("telegram: failed to unlock poll lock", exc_info=True)
    try:
        _holder.close()
    except Exception:
        pass
    _holder = None
