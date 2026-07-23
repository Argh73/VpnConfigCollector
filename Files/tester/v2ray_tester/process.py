from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Set

from v2ray_tester.constants import IS_WINDOWS, XRAY_START_TIMEOUT, XRAY_POLL_INTERVAL

_running_procs: Set[asyncio.subprocess.Process] = set()
_temp_files: List[str] = []


async def kill_all():
    for p in list(_running_procs):
        try:
            p.terminate()
        except ProcessLookupError:
            pass
    if _running_procs:
        await asyncio.sleep(0.3)
    for p in list(_running_procs):
        try:
            if p.returncode is None:
                p.kill()
                await asyncio.wait_for(p.wait(), timeout=2)
        except (ProcessLookupError, asyncio.TimeoutError):
            pass
    _running_procs.clear()
    for path in _temp_files:
        try:
            os.unlink(path)
        except OSError:
            pass
    _temp_files.clear()


class PortManager:
    def __init__(self, start: int, end: int):
        self._queue: asyncio.Queue = asyncio.Queue()
        for p in range(start, end + 1):
            self._queue.put_nowait(p)

    async def acquire(self) -> int:
        return await self._queue.get()

    def release(self, port: int):
        self._queue.put_nowait(port)


async def wait_for_port(host: str, port: int, timeout: float = XRAY_START_TIMEOUT) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=max(0.5, timeout / 4))
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
            await asyncio.sleep(XRAY_POLL_INTERVAL)
    return False


def find_xray() -> Optional[str]:
    script_dir = Path(__file__).resolve().parent.parent
    candidates: List[Path] = [script_dir]
    for sub in ("Xray-windows-64", "xray-windows-64", "xray-linux-64",
                "Xray-linux-64", "xray-macos-64", "Xray-macos-64", "xray"):
        p = script_dir / sub
        if p.is_dir():
            candidates.append(p)
    for name in ("xray.exe", "xray"):
        for folder in candidates:
            exe = folder / name
            if exe.is_file():
                return str(exe.resolve())
        found = shutil.which(name)
        if found:
            return str(Path(found).resolve())
    return None
