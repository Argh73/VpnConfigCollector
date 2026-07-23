from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import List, Optional

from v2ray_tester.constants import SPEED_MIN_MBPS


class LiveResultWriter:
    def __init__(self, output_path: str, total_valid: int):
        self.output_path = output_path
        self.total_valid = total_valid
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._current_stage = ""
        self._stage_progress = ""
        self._eta_text = ""
        self._results: list = []
        self._stages_completed: List[str] = []

    def set_stage(self, name: str, progress: str = "", eta: str = ""):
        with self._lock:
            self._current_stage = name
            self._stage_progress = progress
            self._eta_text = eta
        self.flush()

    def set_progress(self, progress: str, eta: str = ""):
        with self._lock:
            self._stage_progress = progress
            if eta:
                self._eta_text = eta
        self.flush()

    def set_eta(self, eta: str):
        with self._lock:
            self._eta_text = eta
        self.flush()

    def stage_completed(self, name: str):
        with self._lock:
            self._stages_completed.append(name)
            if name == self._current_stage:
                self._current_stage = ""
        self.flush()

    def flush(self):
        if not self.output_path:
            return
        with self._lock:
            try:
                content = self._build_content()
                fd, tmp_path = tempfile.mkstemp(
                    dir=os.path.dirname(self.output_path) or ".",
                    prefix=".working_",
                    suffix=".tmp",
                )
                os.write(fd, content.encode("utf-8"))
                os.close(fd)
                os.replace(tmp_path, self.output_path)
            except OSError:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _build_content(self) -> str:
        lines: List[str] = []
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed = time.monotonic() - self._start_time
        elapsed_str = _fmt_duration(elapsed)

        lines.append(f"# v2ray working configs")
        lines.append(f"# Updated: {now}")
        lines.append(f"# Elapsed: {elapsed_str}")
        if self._eta_text:
            lines.append(f"# ETA: {self._eta_text}")
        if self._stage_progress:
            lines.append(f"# Progress: {self._stage_progress}")
        lines.append("")

        ping_ok = [r for r in self._results if r.ping_ms is not None]
        ping_fail = [r for r in self._results if r.ping_ms is None and r.protocol and not r.ping_error.startswith("bad url")]
        ping_skip = [r for r in self._results if r.ping_error.startswith("bad url") or (not r.protocol and r.ping_error)]

        lat_ok = [r for r in self._results if r.latency_ms is not None]
        lat_fail = [r for r in self._results if r.latency_ms is None and r.ping_ms is not None]

        speed_fast = [r for r in self._results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
        speed_slow = [r for r in self._results if r.speed_mbps is not None and r.speed_mbps < SPEED_MIN_MBPS]

        lines.append(f"=== PING PASSED ({len(ping_ok)}) ===")
        for r in ping_ok:
            name = _get_name(r.link)
            lines.append(f"{r.link} | {r.ping_ms:.0f}ms | {name}")
        lines.append("")

        if ping_fail:
            lines.append(f"=== PING FAILED ({len(ping_fail)}) ===")
            for r in ping_fail:
                name = _get_name(r.link)
                err = r.ping_error[:50] if r.ping_error else "FAIL"
                lines.append(f"{r.link} | {err} | {name}")
            lines.append("")

        if lat_ok:
            lines.append(f"=== LATENCY PASSED ({len(lat_ok)}) ===")
            for r in lat_ok:
                name = _get_name(r.link)
                lines.append(f"{r.link} | {r.latency_ms:.0f}ms | {name}")
            lines.append("")

        if lat_fail:
            lines.append(f"=== LATENCY FAILED ({len(lat_fail)}) ===")
            for r in lat_fail:
                name = _get_name(r.link)
                err = r.latency_error[:50] if r.latency_error else "FAIL"
                lines.append(f"{r.link} | {err} | {name}")
            lines.append("")

        if speed_fast:
            lines.append(f"=== SPEED FAST ({len(speed_fast)}) ===")
            for r in speed_fast:
                name = _get_name(r.link)
                lines.append(f"{r.link} | {r.latency_ms:.0f}ms | {r.speed_mbps:.2f}MB/s | {name}")
            lines.append("")

        if speed_slow:
            lines.append(f"=== SPEED SLOW ({len(speed_slow)}) ===")
            for r in speed_slow:
                name = _get_name(r.link)
                lines.append(f"{r.link} | {r.latency_ms:.0f}ms | {r.speed_mbps:.2f}MB/s | {name}")
            lines.append("")

        return "\n".join(lines) + "\n"

    def update_results(self, results: list):
        with self._lock:
            self._results = results
        self.flush()


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f"{m:02d}:{s:02d}"
    h = m // 60
    m = m % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _get_name(link: str) -> str:
    import urllib.parse
    if "#" in link:
        name = link.split("#", 1)[1]
        try:
            name = urllib.parse.unquote(name)
        except Exception:
            pass
        return name.strip()[:60]
    return ""
