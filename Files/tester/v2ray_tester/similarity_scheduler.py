from __future__ import annotations

import asyncio
import threading
from typing import List, Optional, Set


class SimilarityScheduler:
    """
    Simple FIFO queue scheduler (original behavior).
    No similarity boost - processes configs in original order.
    """
    def __init__(self, results: List, indices: Optional[List[int]] = None,
                 stage_limit: Optional[int] = None, enable_boost: bool = True):
        self.results = results
        self.stage_limit = stage_limit
        self.enable_boost = False  # Always disabled - original behavior

        if indices is None:
            indices = [i for i, r in enumerate(results)
                       if r.protocol and not getattr(r, "ping_error", "").startswith("bad url")]

        self.all_indices = list(indices)
        self.total = len(self.all_indices)
        
        self._lock = threading.Lock()
        self._tested: Set[int] = set()
        self._passed: Set[int] = set()
        self._failed: Set[int] = set()
        self._skipped: Set[int] = set()
        
        # Simple queue - FIFO order
        self._queue = asyncio.Queue()
        for idx in self.all_indices:
            self._queue.put_nowait(idx)

    def get_next(self) -> Optional[int]:
        # Not used with asyncio.Queue pattern, kept for compatibility
        return None

    async def aget_next(self) -> Optional[int]:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def record_result(self, idx: int, passed: bool):
        with self._lock:
            self._tested.add(idx)
            if passed:
                self._passed.add(idx)
            else:
                self._failed.add(idx)

    def mark_skipped(self, idx: int):
        with self._lock:
            self._skipped.add(idx)

    def skip_remaining(self) -> int:
        with self._lock:
            count = 0
            # Can't easily remove from asyncio.Queue, just mark as skipped
            for idx in self.all_indices:
                if idx not in self._tested and idx not in self._skipped:
                    self._skipped.add(idx)
                    count += 1
            return count

    def limit_reached(self) -> bool:
        if self.stage_limit is None:
            return False
        return len(self._passed) >= self.stage_limit

    @property
    def tested_count(self) -> int:
        return len(self._tested)

    @property
    def passed_count(self) -> int:
        return len(self._passed)

    @property
    def failed_count(self) -> int:
        return len(self._failed)

    @property
    def skipped_count(self) -> int:
        return len(self._skipped)

    @property
    def pending_count(self) -> int:
        return sum(1 for i in self.all_indices if i not in self._tested and i not in self._skipped)
