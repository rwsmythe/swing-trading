"""Background thread emitting lease heartbeats. Stops cleanly via Event."""
from __future__ import annotations

import threading

from swing.data.repos.pipeline import LeaseRevoked
from swing.pipeline.lease import Lease


class Heartbeat:
    def __init__(self, *, lease: Lease, interval_seconds: float = 30.0):
        self.lease = lease
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.lease.heartbeat()
            except LeaseRevoked:
                return
            except Exception:
                pass
            self._stop.wait(self.interval)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
