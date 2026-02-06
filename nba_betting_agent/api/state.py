"""In-memory store for tracking analysis runs."""

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class AnalysisRun:
    """Represents a single analysis run."""

    run_id: str
    status: str = "pending"  # pending, running, completed, error
    query: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_step: Optional[str] = None
    result: Optional[dict] = None
    errors: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[int]:
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return int((end - self.started_at) * 1000)


class AnalysisStore:
    """Thread-safe in-memory store for analysis runs.

    Keeps the last `max_runs` runs in memory.
    """

    def __init__(self, max_runs: int = 20):
        self._runs: dict[str, AnalysisRun] = {}
        self._order: list[str] = []
        self._lock = Lock()
        self._max_runs = max_runs

    def create_run(self, query: str) -> AnalysisRun:
        run_id = uuid.uuid4().hex[:12]
        run = AnalysisRun(run_id=run_id, query=query)
        with self._lock:
            self._runs[run_id] = run
            self._order.append(run_id)
            # Evict oldest if over limit
            while len(self._order) > self._max_runs:
                old_id = self._order.pop(0)
                self._runs.pop(old_id, None)
        return run

    def get_run(self, run_id: str) -> Optional[AnalysisRun]:
        with self._lock:
            return self._runs.get(run_id)

    def get_latest(self) -> Optional[AnalysisRun]:
        with self._lock:
            # Find the latest completed run
            for run_id in reversed(self._order):
                run = self._runs.get(run_id)
                if run and run.status == "completed":
                    return run
            return None

    def list_runs(self) -> list[AnalysisRun]:
        with self._lock:
            return [self._runs[rid] for rid in self._order if rid in self._runs]


# Global singleton
analysis_store = AnalysisStore()
