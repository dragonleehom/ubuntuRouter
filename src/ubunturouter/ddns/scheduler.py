"""DDNS scheduler — periodic check and update loop.

Runs every 5 minutes (configurable) checking all configured
DDNS records. Updates records when the public IP changes.
"""

import threading
import time
import logging
from typing import Optional

from . import DDNSManager

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 300  # 5 minutes


class DDNSScheduler:
    """Periodic DDNS check scheduler.

    Runs in a background thread, checking all DDNS records
    at a configurable interval.
    """

    def __init__(self, interval: int = DEFAULT_INTERVAL):
        self._manager = DDNSManager()
        self._interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_check: Optional[float] = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def last_check(self) -> Optional[float]:
        return self._last_check

    @property
    def next_check(self) -> Optional[float]:
        if self._last_check is None:
            return None
        return self._last_check + self._interval

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, value: int):
        self._interval = max(30, value)  # Minimum 30 seconds

    def start(self):
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("DDNS scheduler started (interval=%ds)", self._interval)

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("DDNS scheduler stopped")

    def check_now(self) -> dict:
        """Manually trigger a check and return results."""
        return self._manager.check_and_update()

    def _loop(self):
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                self._last_check = time.time()
                result = self._manager.check_and_update()
                if result.get("updated", 0) > 0:
                    logger.info(
                        "DDNS update: %d records updated, %d errors",
                        result.get("updated", 0),
                        result.get("errors", 0),
                    )
            except Exception as e:
                logger.error("DDNS check error: %s", e)

            self._stop_event.wait(self._interval)
