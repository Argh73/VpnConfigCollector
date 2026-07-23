#!/usr/bin/env python3
"""
v2ray-bulk-tester.py — High-performance headless V2Ray/Xray bulk proxy tester.

Tests thousands of proxy configurations using the official xray binary.
Outputs only working configurations with real latency measurements.

Usage:
    python v2ray-bulk-tester.py -i configs.txt -o working.txt -c 50
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

from v2ray_tester.constants import (
    IS_WINDOWS, CPU_CORES, PORT_START, PORT_END, DEFAULT_CONCURRENCY,
    TEST_URL, REQUEST_TIMEOUT, XRAY_START_TIMEOUT, XRAY_POLL_INTERVAL,
)
from v2ray_tester.parsers import parse_link
from v2ray_tester.xray import build_xray_config
from v2ray_tester.process import PortManager, find_xray

try:
    from aiohttp import ClientSession, ClientTimeout
    from aiohttp_socks import ProxyConnector, ProxyType, ProxyError, ProxyConnectionError
except ImportError:
    print("Required: pip install aiohttp aiohttp-socks")
    sys.exit(1)

try:
    from tqdm.asyncio import tqdm as async_tqdm
except ImportError:
    async_tqdm = None

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

_running_procs: Set[asyncio.subprocess.Process] = set()
_temp_files: List[str] = []


def play_notification():
    if IS_WINDOWS:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
    else:
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass


async def _kill_all_procs():
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


async def wait_for_port(host: str, port: int, timeout: float = XRAY_START_TIMEOUT) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=max(0.5, timeout / 4),
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
            await asyncio.sleep(XRAY_POLL_INTERVAL)
    return False


async def test_config(
    link: str,
    port_mgr: PortManager,
    xray_path: str,
) -> Optional[Tuple[str, float]]:
    cfg = parse_link(link)
    if cfg is None:
        return None

    local_port = await port_mgr.acquire()
    tmp_path: Optional[str] = None
    proc: Optional[asyncio.subprocess.Process] = None

    try:
        xray_cfg = build_xray_config(cfg, local_port)
        if xray_cfg is None:
            return None

        config_json = json.dumps(xray_cfg, indent=None, separators=(",", ":"))
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="xray_")
        os.write(fd, config_json.encode())
        os.close(fd)
        _temp_files.append(tmp_path)

        proc = await asyncio.create_subprocess_exec(
            xray_path, "run", "-c", tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
        _running_procs.add(proc)

        if not await wait_for_port("127.0.0.1", local_port, XRAY_START_TIMEOUT):
            return None

        latency = await _measure_latency(local_port)
        if latency is None:
            return None
        return (link, latency)

    finally:
        if proc is not None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2)
            except ProcessLookupError:
                pass
            _running_procs.discard(proc)
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            try:
                _temp_files.remove(tmp_path)
            except ValueError:
                pass
        port_mgr.release(local_port)


async def _measure_latency(local_port: int) -> Optional[float]:
    connector = ProxyConnector(
        proxy_type=ProxyType.SOCKS5,
        host="127.0.0.1",
        port=local_port,
    )
    timeout = ClientTimeout(total=REQUEST_TIMEOUT)
    start = time.monotonic()
    try:
        async with ClientSession(connector=connector) as session:
            async with session.get(TEST_URL, timeout=timeout) as resp:
                if resp.status not in (200, 204):
                    return None
                return (time.monotonic() - start) * 1000
    except (ProxyError, ProxyConnectionError, OSError, asyncio.TimeoutError, Exception):
        return None


def count_lines(path: str) -> int:
    count = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def iter_configs(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                yield stripped


@dataclass
class Counters:
    tested: int = 0
    working: int = 0


async def async_main(args: Namespace) -> None:
    xray_path = find_xray()
    if not xray_path:
        print("[!] xray binary not found. Place xray (or xray.exe) next to this script.")
        print("    Download: https://github.com/xtls/xray-core/releases")
        sys.exit(1)
    print(f"[*] Xray: {xray_path}")

    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"[!] Input file not found: {input_path}")
        sys.exit(1)

    total = count_lines(input_path)
    if total == 0:
        print("[!] No configs found in input file")
        return
    print(f"[*] Configs loaded: {total}  |  CPU: {CPU_CORES} cores  |  Concurrency: {args.concurrency}")

    port_count = args.end_port - args.start_port + 1
    max_workers = min(args.concurrency, port_count, total)
    if max_workers < args.concurrency:
        print(f"[*] Concurrency reduced to {max_workers} (port range: {port_count})")

    port_mgr = PortManager(args.start_port, args.end_port)
    cnt = Counters()
    progress = (
        async_tqdm(total=total, desc="Testing", unit="cfg", ncols=80,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        if async_tqdm and not args.no_progress
        else None
    )

    work_queue: asyncio.Queue = asyncio.Queue(maxsize=max_workers * 4)
    stop_sentinel = object()

    async def producer():
        for link in iter_configs(input_path):
            await work_queue.put(link)
        for _ in range(max_workers):
            await work_queue.put(stop_sentinel)

    async def worker():
        while True:
            item = await work_queue.get()
            if item is stop_sentinel:
                work_queue.task_done()
                return
            link: str = item
            try:
                result = await test_config(link, port_mgr, xray_path)
                if result:
                    url, lat = result
                    out.write(f"{url} | {lat:.0f}ms\n")
                    out.flush()
                    cnt.working += 1
            except Exception:
                pass
            finally:
                cnt.tested += 1
                if progress:
                    progress.update(1)
                work_queue.task_done()

    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("# V2Ray/Xray working configs\n")
            out.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            out.write("# Format: <config_url> | <latency_ms>\n\n")
            out.flush()

            workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
            prod_task = asyncio.create_task(producer())

            await prod_task
            await work_queue.join()

            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[!] Interrupted \u2014 cleaning up...")
        raise
    finally:
        await _kill_all_procs()
        if progress:
            progress.close()
        print(f"\n[*] Done \u2014 {cnt.working}/{cnt.tested} working configs written to {args.output}")


def parse_args(argv: Optional[List[str]] = None) -> Namespace:
    p = ArgumentParser(
        prog="v2ray-bulk-tester",
        description="High-performance headless V2Ray/Xray bulk proxy tester.",
    )
    p.add_argument("-i", "--input", required=True, help="Input file (one proxy URL per line)")
    p.add_argument("-o", "--output", default="working_configs.txt",
                   help="Output file for working configs")
    p.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"Max concurrent tests (default: {DEFAULT_CONCURRENCY}, based on {CPU_CORES} CPU cores)")
    p.add_argument("--start-port", type=int, default=PORT_START,
                   help=f"Start of local port range (default: {PORT_START})")
    p.add_argument("--end-port", type=int, default=PORT_END,
                   help=f"End of local port range (default: {PORT_END})")
    p.add_argument("--no-progress", action="store_true", help="Disable tqdm progress bar")
    p.add_argument("--latency-timeout", type=float, default=REQUEST_TIMEOUT,
                   help=f"Latency test timeout in seconds (default: {REQUEST_TIMEOUT})")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(async_main(args))
        play_notification()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[!] Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
