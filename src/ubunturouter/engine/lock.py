"""文件锁 — fcntl 并发控制"""

import fcntl
import os
from pathlib import Path


LOCK_PATH = Path("/var/run/ubunturouter/engine.lock")


class EngineLock:
    """文件锁，确保同一时刻只有一个 Apply 操作在进行"""

    def __init__(self, lock_path: Path = LOCK_PATH):
        self.lock_path = lock_path
        self._lock = None

    def __enter__(self) -> "EngineLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = self.lock_path.open('w')
        fcntl.flock(self._lock, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        if self._lock:
            fcntl.flock(self._lock, fcntl.LOCK_UN)
            self._lock.close()
            self._lock = None
