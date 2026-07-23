from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import threading
import time
from typing import List, Optional, Set, Tuple

from v2ray_tester.constants import (
    IS_WINDOWS, TEST_URL, PING_TEST_URL, SPEED_TEST_URL,
    REQUEST_TIMEOUT, PING_TIMEOUT, SPEED_TEST_TIMEOUT, SPEED_READ_LIMIT,
    XRAY_START_TIMEOUT,
)
from v2ray_tester.parsers import parse_link
from v2ray_tester.xray import build_xray_config
from v2ray_tester.process import PortManager, wait_for_port, _running_procs, _temp_files
from v2ray_tester.options import TestOptions
from v2ray_tester.similarity_scheduler import SimilarityScheduler

try:
    from aiohttp import ClientSession, ClientTimeout
    from aiohttp_socks import ProxyConnector, ProxyType, ProxyError, ProxyConnectionError
except ImportError:
    pass


async def _run_xray_test(link: str, port_mgr: PortManager, xray_path: str,
                         timeout: float, url: str, measure_speed: bool = False,
                         speed_read_limit: int = SPEED_READ_LIMIT) -> Tuple[str, Optional[float], str]:
    cfg = parse_link(link)
    if cfg is None:
        return (link, None, "parse failed")

    local_port = await port_mgr.acquire()
    tmp_path: Optional[str] = None
    proc: Optional[asyncio.subprocess.Process] = None

    try:
        xc = build_xray_config(cfg, local_port)
        if xc is None:
            return (link, None, "build config failed")

        config_json = json.dumps(xc, indent=None, separators=(",", ":"))
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="xray_")
        os.write(fd, config_json.encode())
        os.close(fd)
        _temp_files.append(tmp_path)

        proc = await asyncio.create_subprocess_exec(
            xray_path, "run", "-c", tmp_path,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
        _running_procs.add(proc)

        if not await wait_for_port("127.0.0.1", local_port, XRAY_START_TIMEOUT):
            return (link, None, "xray port timeout")

        connector = ProxyConnector(proxy_type=ProxyType.SOCKS5, host="127.0.0.1", port=local_port)
        client_timeout = ClientTimeout(total=timeout)
        start = time.monotonic()
        try:
            async with ClientSession(connector=connector) as session:
                async with session.get(url, timeout=client_timeout) as resp:
                    if not measure_speed:
                        if resp.status not in (200, 204):
                            return (link, None, f"HTTP {resp.status}")
                        return (link, (time.monotonic() - start) * 1000, "")
                    else:
                        if resp.status != 200:
                            return (link, None, f"HTTP {resp.status}")
                        downloaded = 0
                        async for chunk in resp.content.iter_chunked(65536):
                            downloaded += len(chunk)
                            if downloaded >= speed_read_limit:
                                break
                        elapsed = time.monotonic() - start
                        if elapsed < 0.5:
                            return (link, None, "speed: too fast")
                        speed_mbps = (downloaded / elapsed) / (1024 * 1024)
                        return (link, speed_mbps, "")
        except ProxyError as e:
            return (link, None, f"proxy: {e}")
        except ProxyConnectionError as e:
            return (link, None, f"proxy conn: {e}")
        except asyncio.TimeoutError:
            return (link, None, f"timeout {timeout}s")
        except OSError as e:
            msg = str(e) or "connection error"
            return (link, None, f"socket: {msg}")
        except Exception as e:
            return (link, None, str(e)[:60])
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
        await asyncio.sleep(0.05)


async def test_latency(link: str, port_mgr: PortManager, xray_path: str,
                       timeout: float = REQUEST_TIMEOUT,
                       speed_read_limit: int = SPEED_READ_LIMIT) -> Tuple[str, Optional[float], str]:
    return await _run_xray_test(link, port_mgr, xray_path, timeout, TEST_URL, measure_speed=False)


async def test_ping(link: str, port_mgr: PortManager, xray_path: str,
                    timeout: float = PING_TIMEOUT,
                    speed_read_limit: int = SPEED_READ_LIMIT) -> Tuple[str, Optional[float], str]:
    return await _run_xray_test(link, port_mgr, xray_path, timeout, PING_TEST_URL, measure_speed=False)


async def test_speed(link: str, port_mgr: PortManager, xray_path: str,
                     timeout: float = SPEED_TEST_TIMEOUT,
                     speed_read_limit: int = SPEED_READ_LIMIT) -> Tuple[str, Optional[float], str]:
    return await _run_xray_test(link, port_mgr, xray_path, timeout, SPEED_TEST_URL,
                                measure_speed=True, speed_read_limit=speed_read_limit)


def _fmt_eta(seconds: float) -> str:
    if seconds < 0:
        return "??:??"
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f"{m:02d}:{s:02d}"
    h = m // 60
    m = m % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _consume_skip_key():
    if IS_WINDOWS:
        try:
            import msvcrt
            while msvcrt.kbhit():
                ch = msvcrt.getwche()
                if ch in ("s", "S", "\x1b"):
                    return True
        except Exception:
            pass
    return False


async def run_stage(results: list, port_mgr: PortManager, xray_path: str,
                    stage_name: str, test_fn, attr_value: str, attr_error: str,
                    concurrency: int, max_ports: int,
                    indices: Optional[List[int]] = None,
                    stage_concurrency: Optional[int] = None,
                    options: Optional[TestOptions] = None,
                    skip_event: Optional[asyncio.Event] = None,
                    live_writer=None,
                    overall_estimator=None):
    from v2ray_tester.display import (
        _print_stage_header, _print_ok, _print_fail,
        _print_skip_summary, _short_addr,
    )
    from v2ray_tester.constants import _HAS_RICH, _RICH_CONSOLE

    if indices is None:
        indices = [i for i, r in enumerate(results)
                   if r.protocol and not getattr(r, "ping_error", "").startswith("bad url")]
    if not indices:
        return

    effective_conc = stage_concurrency if stage_concurrency is not None else concurrency
    max_workers = min(effective_conc, max_ports, len(indices))

    stage_limit = None
    if options and options.limits:
        stage_limit = options.limits.for_stage(stage_name)

    scheduler = SimilarityScheduler(
        results, indices, stage_limit=stage_limit,
        enable_boost=(options.similarity_boost if options else True),
    )

    skip_key_enabled = (options.skip_key_enabled if options else True)
    local_skip = asyncio.Event()
    if skip_event:
        async def _watch_skip():
            while not skip_event.is_set() and not local_skip.is_set():
                await asyncio.sleep(0.2)
            local_skip.set()
        asyncio.create_task(_watch_skip())

    test_kwargs = {}
    if options:
        if "ping" in stage_name.lower():
            test_kwargs["timeout"] = options.ping_timeout
        elif "latency" in stage_name.lower():
            test_kwargs["timeout"] = options.latency_timeout
        elif "speed" in stage_name.lower():
            test_kwargs["timeout"] = options.speed_timeout
            test_kwargs["speed_read_limit"] = options.speed_size

    start_time = time.monotonic()
    _print_stage_header(stage_name, scheduler.total, is_retry="retry" in stage_name.lower())

    finished = 0
    status_ctx = None
    if _HAS_RICH:
        status_ctx = _RICH_CONSOLE.status(f"[cyan]{stage_name}...[/] 0/{scheduler.total}")

    def _update_status():
        nonlocal status_ctx
        if not _HAS_RICH or status_ctx is None:
            return
        elapsed_so_far = time.monotonic() - start_time
        tested = scheduler.tested_count
        passed_cnt = scheduler.passed_count
        failed_cnt = scheduler.failed_count
        skipped_cnt = scheduler.skipped_count
        pending_cnt = scheduler.pending_count
        total = scheduler.total
        if tested > 0:
            avg_per_test = elapsed_so_far / tested
            eta_remaining = avg_per_test * pending_cnt
            overall_eta = eta_remaining
            if overall_estimator:
                overall_eta = overall_estimator.estimate_remaining(stage_name, pending_cnt, avg_per_test)
            eta_str = _fmt_eta(overall_eta)
        else:
            eta_str = "??:??"
        progress_str = (f"{stage_name} {tested}/{total} tested | "
                        f"{passed_cnt} passed | {failed_cnt} failed | "
                        f"{skipped_cnt} skipped | {pending_cnt} pending | ETA {eta_str}")
        status_ctx.update(f"[cyan]{progress_str}[/]")
        if live_writer and live_writer.output_path:
            live_writer.set_progress(progress_str, eta_str)

    async def worker():
        nonlocal finished
        while True:
            if local_skip.is_set():
                return
            try:
                idx = scheduler._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            r = results[idx]
            try:
                _, val, err = await test_fn(r.link, port_mgr, xray_path, **test_kwargs)
                setattr(results[idx], attr_value, val)
                setattr(results[idx], attr_error, err)
                passed = val is not None
                scheduler.record_result(idx, passed)
            except Exception as e:
                setattr(results[idx], attr_value, None)
                setattr(results[idx], attr_error, str(e)[:60])
                scheduler.record_result(idx, False)
            finally:
                finished += 1
                r2 = results[idx]
                val = getattr(r2, attr_value)
                err = getattr(r2, attr_error)
                proto = r2.protocol.upper()[:7]
                addr = _short_addr(r2.address)

                if val is not None:
                    is_speed = "speed" in stage_name.lower()
                    val_str = f"{val:5.2f}M" if is_speed else f"{val:6.0f}ms"
                    _print_ok(proto, addr, val_str)
                else:
                    err_msg = err[:35] if err else "FAIL"
                    _print_fail(proto, addr, err_msg)
                _update_status()

    try:
        if status_ctx:
            status_ctx.__enter__()
        
        workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
        while not local_skip.is_set() and not scheduler.limit_reached():
            await asyncio.sleep(0.15)
            _update_status()
            # Check if all workers are done (queue empty and no pending)
            if scheduler.pending_count == 0 and scheduler.tested_count == scheduler.total:
                break
            if skip_key_enabled and _consume_skip_key():
                local_skip.set()
                break

        if not local_skip.is_set():
            # Normal completion or limit reached - wait for workers to finish
            await asyncio.gather(*workers, return_exceptions=True)
        else:
            # Skip pressed - cancel remaining workers
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            skipped_now = scheduler.skip_remaining()
            _print_skip_summary(stage_name, scheduler.passed_count, skipped_now)

            if live_writer and live_writer.output_path:
                progress_str = (f"{stage_name} COMPLETE (skipped) | "
                                f"{scheduler.passed_count} passed | "
                                f"{skipped_now} skipped")
                live_writer.set_progress(progress_str, "")
                live_writer.stage_completed(stage_name + " (skipped)")

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n Interrupted.")
        raise
    finally:
        if status_ctx:
            try:
                status_ctx.__exit__(None, None, None)
            except Exception:
                pass

    if live_writer and live_writer.output_path:
        tested = scheduler.tested_count
        passed_cnt = scheduler.passed_count
        failed_cnt = scheduler.failed_count
        skipped_cnt = scheduler.skipped_count
        progress_str = (f"{stage_name} COMPLETE | "
                        f"{tested} tested | {passed_cnt} passed | "
                        f"{failed_cnt} failed | {skipped_cnt} skipped")
        live_writer.set_progress(progress_str, "")
        live_writer.stage_completed(stage_name)


async def run_stage_with_retry(results: list, port_mgr: PortManager, xray_path: str,
                               stage_name: str, test_fn, attr_value: str, attr_error: str,
                               concurrency: int, max_ports: int,
                               indices: Optional[List[int]] = None,
                               stage_concurrency: Optional[int] = None,
                               options: Optional[TestOptions] = None,
                               skip_event: Optional[asyncio.Event] = None,
                               live_writer=None,
                               overall_estimator=None):
    from v2ray_tester.display import _print_retry_header

    if indices is None:
        indices = [i for i, r in enumerate(results)
                   if r.protocol and not getattr(r, "ping_error", "").startswith("bad url")]
    if not indices:
        return

    await run_stage(results, port_mgr, xray_path, stage_name, test_fn,
                    attr_value, attr_error, concurrency, max_ports,
                    indices=indices, stage_concurrency=stage_concurrency,
                    options=options, skip_event=skip_event,
                    live_writer=live_writer, overall_estimator=overall_estimator)

    if skip_event and skip_event.is_set():
        return

    retry_indices = [i for i in indices
                     if getattr(results[i], attr_value) is None]
    if retry_indices:
        skipped = len(indices) - len(retry_indices)
        _print_retry_header(stage_name, len(retry_indices), skipped)
        for i in retry_indices:
            setattr(results[i], attr_value, None)
            setattr(results[i], attr_error, "")
        await run_stage(results, port_mgr, xray_path, f"{stage_name} retry", test_fn,
                        attr_value, attr_error, concurrency, max_ports,
                        indices=retry_indices, stage_concurrency=stage_concurrency,
                        options=options, skip_event=skip_event,
                        live_writer=live_writer, overall_estimator=overall_estimator)


class OverallEstimator:
    def __init__(self):
        self._stage_avg: dict = {}
        self._stage_remaining: dict = {}
        self._stages_done: List[str] = []

    def record_stage_avg(self, stage_name: str, avg_per_test: float):
        self._stage_avg[stage_name.upper()] = avg_per_test

    def set_remaining(self, stage_name: str, count: int):
        self._stage_remaining[stage_name.upper()] = count

    def stage_done(self, stage_name: str):
        self._stages_done.append(stage_name.upper())

    def estimate_remaining(self, current_stage: str, current_remaining: int, current_avg: float) -> float:
        return current_avg * current_remaining
