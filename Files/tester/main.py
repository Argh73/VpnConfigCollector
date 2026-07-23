#!/usr/bin/env python3
"""
v2ray-tester — interactive proxy config tester.

Usage:
    python main.py

Then paste configs and watch results live.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Dict, List, Optional

from v2ray_tester.constants import (
    IS_WINDOWS, CPU_CORES, PORT_START, PORT_END, DEFAULT_CONCURRENCY,
    SPEED_MIN_MBPS, _HAS_RICH, _RICH_CONSOLE,
)
from v2ray_tester.process import find_xray, PortManager, kill_all
from v2ray_tester.display import (
    ProxyResult, init_results, print_final_summary, print_rich_summary,
    _dedup_results, _print_dedup_summary, _print_drop_summary, _print_skip_msg,
    _get_config_name,
)
from v2ray_tester.tester import (
    run_stage_with_retry, run_stage, test_ping, test_latency, test_speed,
    OverallEstimator, _fmt_eta,
)
from v2ray_tester.subs import (
    load_subs, save_subs, fetch_all_subs,
    _print_sub_fetch_status, _archive_bad_subs,
    _smart_sub_cleanup, prompt_prune_subs,
)
from v2ray_tester.geo import _lookup_countries, _rank_and_rename, _extract_host
from v2ray_tester.options import TestOptions, StageLimits, parse_size_bytes, parse_limit
from v2ray_tester.output import LiveResultWriter


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


def ask_concurrency() -> int:
    MAX_PORTS = PORT_END - PORT_START + 1
    low = CPU_CORES
    medium = CPU_CORES * 2
    high = DEFAULT_CONCURRENCY
    max_val = min(CPU_CORES * (4 if IS_WINDOWS else 8), MAX_PORTS)

    print()
    print(f" System: {CPU_CORES} CPU cores  |  Available ports: {MAX_PORTS}  |  OS: {'Windows' if IS_WINDOWS else 'Linux/Mac'}")
    print()
    print(" How many concurrent tests should run?")
    print(f"   [L] Low     (1x CPU  = {low})")
    print(f"   [M] Medium  (2x CPU  = {medium})")
    print(f"   [H] High    ({'3x' if IS_WINDOWS else '4x'} CPU  = {high})  (default)")
    print(f"   [X] Max     ({'4x' if IS_WINDOWS else '8x'} CPU  = {max_val})")
    print(f"   [C] Custom  (enter a number)")
    print()
    while True:
        try:
            choice = input(" Choose [L/M/H/X/C] (default: H): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return high
        if not choice:
            return high
        if choice in ("l", "low"):
            return low
        if choice in ("m", "medium"):
            return medium
        if choice in ("h", "high"):
            return high
        if choice in ("x", "max"):
            return max_val
        if choice in ("c", "custom"):
            try:
                val = input(f" Enter concurrency (1-{MAX_PORTS}): ").strip()
            except (EOFError, KeyboardInterrupt):
                return high
            if val:
                try:
                    n = int(val)
                except ValueError:
                    print(" Invalid number.")
                    continue
                if 1 <= n <= MAX_PORTS:
                    return n
                else:
                    print(f" Must be between 1 and {MAX_PORTS}.")
            continue
        print(" Invalid choice. Try again.")


def ask_test_options() -> TestOptions:
    opts = TestOptions()
    print()
    print(" === Test Options ===")
    print()

    try:
        ans = input(f" Ping timeout seconds [{opts.ping_timeout}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans:
        try:
            opts.ping_timeout = float(ans)
        except ValueError:
            pass

    try:
        ans = input(f" Latency timeout seconds [{opts.latency_timeout}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans:
        try:
            opts.latency_timeout = float(ans)
        except ValueError:
            pass

    try:
        ans = input(f" Speed timeout seconds [{opts.speed_timeout}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans:
        try:
            opts.speed_timeout = float(ans)
        except ValueError:
            pass

    try:
        ans = input(f" Speed download size [{opts.speed_size // (1024*1024)}MB, e.g. 500KB, 1MB]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans:
        opts.speed_size = parse_size_bytes(ans)

    print()
    try:
        ans = input(f" Ping limit [all]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    opts.limits.ping = parse_limit(ans)

    try:
        ans = input(f" Latency limit [all]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    opts.limits.latency = parse_limit(ans)

    try:
        ans = input(f" Speed limit [all]: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    opts.limits.speed = parse_limit(ans)

    print()
    try:
        ans = input(" Enable live file updates? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans == "n":
        opts.live_output = False

    try:
        ans = input(" Enable similarity boost (find similar configs faster)? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans == "n":
        opts.similarity_boost = False

    try:
        ans = input(" Enable skip key (press S to skip current stage)? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans == "n":
        opts.skip_key_enabled = False

    return opts


def read_configs_interactive() -> List[str]:
    print()
    print(" Enter your proxy configs (one per line).")
    print(" Press Enter twice (blank line) when done.\n")
    lines: List[str] = []
    try:
        while True:
            raw = input("> ").strip()
            if not raw:
                break
            if raw.lower() in ("done", "exit", "quit"):
                break
            lines.append(raw)
    except (KeyboardInterrupt, EOFError):
        pass
    seen: set = set()
    unique: List[str] = []
    for l in lines:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique


def read_configs_from_file(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except (OSError, UnicodeDecodeError) as e:
        print(f" Failed to read input file: {e}")
        sys.exit(1)
    seen: set = set()
    unique: List[str] = []
    for l in lines:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique


async def main(concurrency: int = DEFAULT_CONCURRENCY, input_file: str = "",
               no_subs: bool = False, auto: bool = False,
               options: Optional[TestOptions] = None) -> None:
    xray_path = find_xray()
    if not xray_path:
        print(" xray binary not found. Place xray.exe next to this script.")
        print(" Download: https://github.com/xtls/xray-core/releases")
        sys.exit(1)

    if options is None:
        options = TestOptions()

    print(f" CPU cores: {CPU_CORES}  |  Concurrency: {concurrency}  |  Ports: {PORT_START}-{PORT_END}")
    print(f" Ping: {options.ping_timeout}s  |  Latency: {options.latency_timeout}s  |  Speed: {options.speed_timeout}s / {options.speed_size // (1024*1024)}MB")
    if options.limits.ping or options.limits.latency or options.limits.speed:
        print(f" Limits: ping={options.limits.ping or 'all'} latency={options.limits.latency or 'all'} speed={options.limits.speed or 'all'}")
    print()

    subs = [] if no_subs else load_subs()
    sub_fetched_links: List[str] = []
    config_to_sub: Dict[str, str] = {}
    using_subs = False

    if subs:
        try:
            ans = input(" Fetch configs from subscriptions? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "n":
            using_subs = True
            print(f" Fetching {len(subs)} sub(s) with concurrency {concurrency}...")
            sub_fetched_links, config_to_sub, fetch_status = await fetch_all_subs(subs, concurrency)
            success_subs, failed_subs = _print_sub_fetch_status(fetch_status)
            print(f"\n Extracted {len(sub_fetched_links)} config(s) from {success_subs}/{len(subs)} sub(s).")

            if failed_subs > 0:
                print()
                try:
                    ans = input(f" Remove {failed_subs} sub(s) with 0 configs? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "n"
                if ans == "y":
                    good_urls = [url for url, count in fetch_status if count > 0]
                    save_subs(good_urls)
                    print(f" Removed {failed_subs} sub(s). {len(good_urls)} remaining.")
                    subs = good_urls

            if sub_fetched_links:
                print()
                try:
                    ans = input(f" Copy all {len(sub_fetched_links)} extracted configs to console? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "n"
                if ans == "y":
                    for c in sub_fetched_links:
                        print(c)

    links: List[str] = []
    input_mode = ""

    if sub_fetched_links:
        print()
        try:
            ans = input(" Config source: [M] Manual paste/file  [E] Extracted from subs: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "m"
        if ans == "e":
            input_mode = "extracted"
            try:
                ans = input(" Use all configs or chunk? [A/c]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "a"
            if ans == "c":
                try:
                    max_n_str = input(" Max configs to test? (e.g. 10000): ").strip()
                    max_n = int(max_n_str) if max_n_str else len(sub_fetched_links)
                except (EOFError, KeyboardInterrupt, ValueError):
                    max_n = len(sub_fetched_links)
                links = sub_fetched_links[:max_n]
                print(f" Testing first {len(links)} of {len(sub_fetched_links)} configs.")
            else:
                links = sub_fetched_links

    if not links:
        input_mode = "manual"
        if input_file:
            links = read_configs_from_file(input_file)
            print(f" Read {len(links)} config(s) from {input_file}")
        else:
            try:
                ans = input(" Read configs from file? (Enter path, or press Enter to paste): ").strip()
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans:
                links = read_configs_from_file(ans)
                print(f" Read {len(links)} config(s) from {ans}")
                print()
            else:
                links = read_configs_interactive()

    if not links:
        print(" No configs entered. Exiting.")
        return

    results = init_results(links)
    total = len(results)
    parse_errs = sum(1 for r in results if not r.protocol)
    valid_count = total - parse_errs

    if config_to_sub:
        for r in results:
            if r.link in config_to_sub:
                r.sub_url = config_to_sub[r.link]

    if valid_count == 0:
        print(" No valid configs found. Exiting.")
        return

    if parse_errs:
        print(f" {parse_errs} config(s) could not be parsed (shown as ERROR)")

    out_path = ""
    if input_file:
        out_path = options.output_path or "working.txt"
        print(f" Results will be saved to {out_path}")
    else:
        try:
            ans = input("\n Save working configs to file? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "n":
            try:
                out_path = input(" Filename [working.txt]: ").strip() or "working.txt"
            except (EOFError, KeyboardInterrupt):
                out_path = ""
            if out_path:
                options.output_path = out_path

    live_writer = None
    if out_path and options.live_output:
        live_writer = LiveResultWriter(out_path, valid_count)

    port_mgr = PortManager(PORT_START, PORT_END)
    max_ports = PORT_END - PORT_START + 1
    skip_event = asyncio.Event()
    estimator = OverallEstimator()

    try:
        dedup_count = _dedup_results(results)
        if dedup_count:
            _print_dedup_summary(dedup_count)
            valid_count -= dedup_count

        if valid_count == 0:
            print(" No unique configs remaining. Exiting.")
            return

        print()
        if options.skip_key_enabled:
            print(" Press [S] at any time during a stage to skip to the next stage.")
            print()

        await run_stage_with_retry(results, port_mgr, xray_path,
                                   "PING", test_ping,
                                   "ping_ms", "ping_error",
                                   concurrency, max_ports,
                                   options=options, skip_event=skip_event,
                                   live_writer=live_writer, overall_estimator=estimator)
        await kill_all()

        if skip_event.is_set():
            print("\n Skipping remaining stages (ping was skipped).")
        else:
            ping_indices = [i for i, r in enumerate(results) if r.ping_ms is not None]
            failed_ping = [r for r in results if r.ping_ms is None and r.protocol]
            if failed_ping:
                _print_drop_summary("PING", len(ping_indices), len(failed_ping))
            if not ping_indices:
                _print_skip_msg("Latency test \u2014 no configs passed ping")
            else:
                await run_stage_with_retry(results, port_mgr, xray_path,
                                           "LATENCY", test_latency,
                                           "latency_ms", "latency_error",
                                           concurrency, max_ports,
                                           indices=ping_indices,
                                           options=options, skip_event=skip_event,
                                           live_writer=live_writer, overall_estimator=estimator)
            await kill_all()

            if using_subs and subs:
                subs = _smart_sub_cleanup(results, subs)
                print()

            working_links = [r.link for r in results if r.latency_ms is not None]
            if working_links:
                try:
                    ans = input(f" Copy {len(working_links)} working (latency-passed) configs? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "n"
                if ans == "y":
                    for c in working_links:
                        print(c)
                    print()

            speed_indices = [i for i, r in enumerate(results) if r.latency_ms is not None]
            failed_latency = [r for r in results if r.latency_ms is None and r.ping_ms is not None]
            if failed_latency:
                _print_drop_summary("LATENCY", len(speed_indices), len(failed_latency))
            if not speed_indices:
                _print_skip_msg("Speed test \u2014 no configs passed latency")
            else:
                await run_stage(results, port_mgr, xray_path,
                                "SPEED", test_speed,
                                "speed_mbps", "speed_error",
                                concurrency, max_ports,
                                indices=speed_indices,
                                stage_concurrency=1,
                                options=options, skip_event=skip_event,
                                live_writer=live_writer, overall_estimator=estimator)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n Interrupted.")
        raise
    finally:
        await kill_all()

    try:
        await _lookup_countries(results, min(concurrency, 10))
    except Exception:
        pass

    renamed_count = _rank_and_rename(results)
    if renamed_count:
        if _HAS_RICH:
            from rich.panel import Panel
            from rich import box
            _RICH_CONSOLE.print(Panel(
                f"[bold green]RANKED & RENAMED[/] \u2014 {renamed_count} config(s) to [RANK - COUNTRY - SPEED - PING]",
                box=box.ASCII
            ))
        else:
            print(f"\n RANKED & RENAMED \u2014 {renamed_count} config(s) to [RANK - COUNTRY - SPEED - PING]")

    working = [r for r in results if r.latency_ms is not None]
    fast_enough = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    ping_ok = [r for r in results if r.ping_ms is not None]
    has_speed = any(r.speed_mbps is not None for r in results)

    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print()
        _RICH_CONSOLE.print(Panel(
            f"[bold cyan]TOTAL VALID[/]   {valid_count}\n"
            f"[bold green]PASSED PING[/]   {len(ping_ok)}\n"
            f"[bold green]PASSED LATENCY[/] {len(working)}\n"
            + (f"[bold green]FAST ENOUGH[/]  {len(fast_enough)} (>{SPEED_MIN_MBPS} MB/s)" if has_speed else ""),
            title="[bold]FINAL RESULTS[/]",
            box=box.ASCII
        ))
        print_rich_summary(results)
    else:
        print(f"\n{'='*70}")
        print(f"  FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"  Total valid configs: {valid_count}")
        print(f"  Passed ping:         {len(ping_ok)}")
        print(f"  Passed latency:      {len(working)}")
        if has_speed:
            print(f"  Passed speed test:   {len(fast_enough)} (>{SPEED_MIN_MBPS} MB/s)")
        print()
        print_final_summary(results)

    top10 = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    top10.sort(key=lambda r: r.speed_mbps, reverse=True)
    top10 = top10[:10]
    if top10:
        try:
            ans = input(f"\n Copy top {len(top10)} ranked configs? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans == "y":
            for r in top10:
                print(r.link)

    if out_path:
        if live_writer:
            live_writer.update_results(results)
            live_writer.flush()
        else:
            try:
                _write_results_file(out_path, results, valid_count)
                print(f" Saved to {out_path}")
            except OSError as e:
                print(f" Failed to save: {e}")

    if using_subs and subs:
        prompt_prune_subs(results, subs)
        print()


def _write_results_file(out_path: str, results: List[ProxyResult], valid_count: int):
    working = [r for r in results if r.latency_ms is not None]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# v2ray working configs \u2014 {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# {len(working)}/{valid_count} working\n\n")

        ping_ok_list = [r for r in results if r.ping_ms is not None]
        lat_ok_list = [r for r in results if r.latency_ms is not None]
        speed_zero = [r for r in results if r.speed_mbps is not None and r.speed_mbps < SPEED_MIN_MBPS]
        speed_fast = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]

        f.write(f"=== PING PASSED ({len(ping_ok_list)}) ===\n")
        for r in ping_ok_list:
            f.write(f"{r.link} | {r.ping_ms:.0f}ms\n")
        f.write("\n")

        f.write(f"=== LATENCY PASSED ({len(lat_ok_list)}) ===\n")
        for r in lat_ok_list:
            f.write(f"{r.link} | {r.latency_ms:.0f}ms\n")
        f.write("\n")

        if speed_zero:
            f.write(f"=== SPEED SLOW ({len(speed_zero)}) \u2014 < {SPEED_MIN_MBPS} MB/s ===\n")
            for r in speed_zero:
                f.write(f"{r.link} | {r.latency_ms:.0f}ms | {r.speed_mbps:.2f}MB/s\n")
            f.write("\n")

        if speed_fast:
            f.write(f"=== SPEED FAST ({len(speed_fast)}) \u2014 >= {SPEED_MIN_MBPS} MB/s ===\n")
            for r in speed_fast:
                f.write(f"{r.link} | {r.latency_ms:.0f}ms | {r.speed_mbps:.2f}MB/s\n")
            f.write("\n")


async def auto_main(concurrency: int, options: Optional[TestOptions] = None) -> None:
    xray_path = find_xray()
    if not xray_path:
        print(" xray binary not found.")
        sys.exit(1)

    if options is None:
        options = TestOptions()

    max_ports = PORT_END - PORT_START + 1
    concurrency = min(concurrency, max_ports)
    print(f" CPU cores: {CPU_CORES}  |  Concurrency: {concurrency} (medium)  |  Ports: {PORT_START}-{PORT_END}")
    print(f" Ping: {options.ping_timeout}s  |  Latency: {options.latency_timeout}s  |  Speed: {options.speed_timeout}s / {options.speed_size // (1024*1024)}MB")

    subs = load_subs()
    if not subs:
        print(" No subscriptions found in subs.txt. Exiting.")
        return

    print(f" Fetching {len(subs)} subscription(s)...")
    configs, config_to_sub, status = await fetch_all_subs(subs, concurrency)
    success_subs, failed_subs = _print_sub_fetch_status(status)
    print(f"\n Extracted {len(configs)} config(s) from {success_subs}/{len(subs)} sub(s).")

    if failed_subs:
        good_urls = [url for url, count in status if count > 0]
        bad_urls = [url for url, count in status if count == 0]
        _archive_bad_subs(bad_urls)
        save_subs(good_urls)
        print(f" Removed {failed_subs} dead sub(s). {len(good_urls)} remaining.")
        subs = good_urls

    if not configs:
        print(" No configs extracted. Exiting.")
        return

    links = configs
    print(f" Testing all {len(links)} configs.")

    results = init_results(links)
    valid_count = sum(1 for r in results if r.protocol)
    parse_errs = len(links) - valid_count

    for r in results:
        if r.link in config_to_sub:
            r.sub_url = config_to_sub[r.link]

    if valid_count == 0:
        print(" No valid configs. Exiting.")
        return

    if parse_errs:
        print(f" {parse_errs} config(s) could not be parsed.")

    out_path = options.output_path or "working.txt"
    print(f" Results will be saved to {out_path}")

    live_writer = None
    if options.live_output:
        live_writer = LiveResultWriter(out_path, valid_count)

    port_mgr = PortManager(PORT_START, PORT_END)
    skip_event = asyncio.Event()
    estimator = OverallEstimator()

    try:
        dedup_count = _dedup_results(results)
        if dedup_count:
            _print_dedup_summary(dedup_count)
            valid_count -= dedup_count
        if valid_count == 0:
            print(" No unique configs remaining.")
            return

        await run_stage_with_retry(results, port_mgr, xray_path,
                                   "PING", test_ping,
                                   "ping_ms", "ping_error",
                                   concurrency, max_ports,
                                   options=options, skip_event=skip_event,
                                   live_writer=live_writer, overall_estimator=estimator)
        await kill_all()

        if not skip_event.is_set():
            ping_indices = [i for i, r in enumerate(results) if r.ping_ms is not None]
            failed_ping = [r for r in results if r.ping_ms is None and r.protocol]
            if failed_ping:
                _print_drop_summary("PING", len(ping_indices), len(failed_ping))
            if not ping_indices:
                _print_skip_msg("Latency test \u2014 no configs passed ping")
            else:
                await run_stage_with_retry(results, port_mgr, xray_path,
                                           "LATENCY", test_latency,
                                           "latency_ms", "latency_error",
                                           concurrency, max_ports,
                                           indices=ping_indices,
                                           options=options, skip_event=skip_event,
                                           live_writer=live_writer, overall_estimator=estimator)
            await kill_all()

            if subs:
                good_subs: set = set()
                for r in results:
                    if r.latency_ms is not None and r.sub_url:
                        good_subs.add(r.sub_url)
                dead_subs = [u for u in subs if u not in good_subs]
                if dead_subs:
                    print(f" Pruning {len(dead_subs)} sub(s) with no working configs (auto)...")
                    subs = [u for u in subs if u in good_subs]
                    _archive_bad_subs(dead_subs)
                    save_subs(subs)
                    print(f" Removed {len(dead_subs)} sub(s). {len(subs)} remaining.")
                else:
                    print(" All subs have working configs.")

            working_links = [r.link for r in results if r.latency_ms is not None]
            if working_links:
                print(f" Working (latency-passed) configs ({len(working_links)}):")
                for c in working_links:
                    print(c)

            speed_indices = [i for i, r in enumerate(results) if r.latency_ms is not None]
            failed_latency = [r for r in results if r.latency_ms is None and r.ping_ms is not None]
            if failed_latency:
                _print_drop_summary("LATENCY", len(speed_indices), len(failed_latency))
            if not speed_indices:
                _print_skip_msg("Speed test \u2014 no configs passed latency")
            else:
                await run_stage(results, port_mgr, xray_path,
                                "SPEED", test_speed,
                                "speed_mbps", "speed_error",
                                concurrency, max_ports,
                                indices=speed_indices,
                                stage_concurrency=1,
                                options=options, skip_event=skip_event,
                                live_writer=live_writer, overall_estimator=estimator)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n Interrupted.")
        raise
    finally:
        await kill_all()

    try:
        await _lookup_countries(results, min(concurrency, 10))
    except Exception:
        pass

    renamed_count = _rank_and_rename(results)
    if renamed_count:
        if _HAS_RICH:
            from rich.panel import Panel
            from rich import box
            _RICH_CONSOLE.print()
            _RICH_CONSOLE.print(Panel(
                f"[bold green]RANKED & RENAMED[/] \u2014 {renamed_count} config(s) to [RANK - COUNTRY - SPEED - PING]",
                box=box.ASCII
            ))
        else:
            print(f"\n RANKED & RENAMED \u2014 {renamed_count} config(s) to [RANK - COUNTRY - SPEED - PING]")

    working = [r for r in results if r.latency_ms is not None]
    fast_enough = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    ping_ok = [r for r in results if r.ping_ms is not None]
    has_speed = any(r.speed_mbps is not None for r in results)

    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print()
        _RICH_CONSOLE.print(Panel(
            f"[bold cyan]TOTAL VALID[/]   {valid_count}\n"
            f"[bold green]PASSED PING[/]   {len(ping_ok)}\n"
            f"[bold green]PASSED LATENCY[/] {len(working)}\n"
            + (f"[bold green]FAST ENOUGH[/]  {len(fast_enough)} (>{SPEED_MIN_MBPS} MB/s)" if has_speed else ""),
            title="[bold]FINAL RESULTS[/]",
            box=box.ASCII
        ))
        print_rich_summary(results)
    else:
        print(f"\n{'='*70}")
        print(f"  FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"  Total valid configs: {valid_count}")
        print(f"  Passed ping:         {len(ping_ok)}")
        print(f"  Passed latency:      {len(working)}")
        if has_speed:
            print(f"  Passed speed test:   {len(fast_enough)} (>{SPEED_MIN_MBPS} MB/s)")
        print()
        print_final_summary(results)

    if live_writer:
        live_writer.update_results(results)
        live_writer.flush()
    else:
        try:
            _write_results_file(out_path, results, valid_count)
            print(f" Saved to {out_path}")
        except OSError as e:
            print(f" Failed to save: {e}")


_PROTO_PREFIXES = ("vless://", "vmess://", "ss://", "trojan://", "hy2://", "hysteria2://")


def _read_configs_rank(path: str) -> List[str]:
    lines: List[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("==="):
                continue
            parts = line.split(" | ", 1)
            url = parts[0].strip()
            if any(url.startswith(p) for p in _PROTO_PREFIXES):
                lines.append(url)
    seen: set = set()
    return [x for x in lines if not (x in seen or seen.add(x))]


async def speedrank_main(concurrency: int, input_file: str, output_file: str,
                         options: Optional[TestOptions] = None) -> None:
    xray_path = find_xray()
    if not xray_path:
        print(" xray binary not found.")
        sys.exit(1)

    if options is None:
        options = TestOptions()

    max_ports = PORT_END - PORT_START + 1
    concurrency = min(concurrency, max_ports)

    links = _read_configs_rank(input_file)
    if not links:
        print(f" No configs found in {input_file}")
        return
    print(f" Loaded {len(links)} config(s) from {input_file}")
    print(f" Xray: {xray_path}  |  Concurrency: {concurrency}  |  Ports: {PORT_START}-{PORT_END}")
    print()

    results = init_results(links)
    valid = sum(1 for r in results if r.protocol)
    if valid == 0:
        print(" No valid configs found.")
        return
    print(f"  Valid configs: {valid}/{len(results)}")
    print()

    live_writer = None
    if options.live_output and output_file:
        live_writer = LiveResultWriter(output_file, valid)

    port_mgr = PortManager(PORT_START, PORT_END)
    skip_event = asyncio.Event()
    estimator = OverallEstimator()

    try:
        dedup_count = _dedup_results(results)
        if dedup_count:
            print(f"  Dedup: removed {dedup_count} duplicate(s)")
            valid -= dedup_count
        if valid == 0:
            print(" No unique configs remaining.")
            return

        await run_stage_with_retry(results, port_mgr, xray_path,
                                   "PING", test_ping,
                                   "ping_ms", "ping_error",
                                   concurrency, max_ports,
                                   options=options, skip_event=skip_event,
                                   live_writer=live_writer, overall_estimator=estimator)
        await kill_all()

        if not skip_event.is_set():
            ping_ok_idx = [i for i, r in enumerate(results) if r.ping_ms is not None and r.protocol]
            if not ping_ok_idx:
                print("  LATENCY (no configs passed ping)")
            else:
                await run_stage_with_retry(results, port_mgr, xray_path,
                                           "LATENCY", test_latency,
                                           "latency_ms", "latency_error",
                                           concurrency, max_ports,
                                           indices=ping_ok_idx,
                                           options=options, skip_event=skip_event,
                                           live_writer=live_writer, overall_estimator=estimator)
            await kill_all()

            speed_indices = [i for i, r in enumerate(results) if r.latency_ms is not None]
            if not speed_indices:
                print("  SPEED (no configs passed latency)")
            else:
                await run_stage(results, port_mgr, xray_path,
                                "SPEED", test_speed,
                                "speed_mbps", "speed_error",
                                concurrency, max_ports,
                                indices=speed_indices,
                                stage_concurrency=1,
                                options=options, skip_event=skip_event,
                                live_writer=live_writer, overall_estimator=estimator)
            await kill_all()

            speed_ok = [r for r in results if r.speed_mbps is not None]
            if speed_ok:
                print(f"  COUNTRY LOOKUP ({len(speed_ok)} configs)...", end=" ", flush=True)
                try:
                    await _lookup_countries(results, min(concurrency, 10))
                except Exception:
                    pass
                print("done")
            print()

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n Interrupted.")
        return
    finally:
        await kill_all()

    renamed_count = _rank_and_rename(results)
    if renamed_count:
        print(f"  Ranked & renamed {renamed_count} config(s) to [RANK - COUNTRY - SPEED - PING]")
        print()

    ranked = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    ranked.sort(key=lambda r: r.speed_mbps, reverse=True)
    print(f"  {'Rank':<6} {'Country':<12} {'Speed':<14} {'Ping':<10} {'Name'}")
    print(f"  {'-'*6} {'-'*12} {'-'*14} {'-'*10} {'-'*30}")
    for rank_num, r in enumerate(ranked, 1):
        country = r.country if r.country else "??"
        speed_str = f"{r.speed_mbps:.1f}MB/s"
        ping_str = f"{r.ping_ms:.0f}ms" if r.ping_ms is not None else "?ms"
        name = _get_config_name(r.link) or _extract_host(r.address)
        print(f"  [{rank_num:<3}] {country:<12} {speed_str:<14} {ping_str:<10} {name[:30]}")

    all_ranked = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    all_ranked.sort(key=lambda r: r.speed_mbps, reverse=True)
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"# Ranked configs \u2014 {now}\n")
            f.write("# Format: [RANK - COUNTRY - SPEED - PING]\n")
            f.write(f"# {len(all_ranked)} working out of {valid} valid\n\n")
            for r in all_ranked:
                f.write(r.link + "\n")
        print()
        print(f" Saved {len(all_ranked)} ranked config(s) to {output_file}")
    except OSError as e:
        print(f" Failed to save: {e}")

    top10 = ranked[:10]
    if top10:
        try:
            ans = input(f"\n Copy top {len(top10)} ranked configs? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans == "y":
            for r in top10:
                print(r.link)


def entry() -> None:
    p = argparse.ArgumentParser(description="V2Ray/Xray proxy tester")
    p.add_argument("-c", "--concurrency", type=int, default=0,
                   help=f"Concurrent tests (default: prompt)")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Skip concurrency prompt, use default concurrency")
    p.add_argument("-i", "--input", type=str, default="",
                   help="Read configs from a file (one per line)")
    p.add_argument("--no-subs", action="store_true",
                   help="Skip subscription fetching even if subs.txt exists")
    p.add_argument("-a", "--auto", action="store_true",
                   help="Auto mode (no prompts, reads subs.txt, medium concurrency)")
    p.add_argument("-r", "--rank", action="store_true",
                   help="Rank mode: speed-test, rank & rename configs from file")
    p.add_argument("-o", "--output", type=str, default="",
                   help="Output file (rank mode: default ranked_configs.txt)")
    p.add_argument("--ping-timeout", type=float, default=0,
                   help="Ping timeout in seconds (default: 3)")
    p.add_argument("--latency-timeout", type=float, default=0,
                   help="Latency timeout in seconds (default: 5)")
    p.add_argument("--speed-timeout", type=float, default=0,
                   help="Speed test timeout in seconds (default: 120)")
    p.add_argument("--speed-size", type=str, default="",
                   help="Speed download size (e.g. 500KB, 1MB, 5MB)")
    p.add_argument("--ping-limit", type=str, default="",
                   help="Max configs to pass ping stage (default: all)")
    p.add_argument("--latency-limit", type=str, default="",
                   help="Max configs to pass latency stage (default: all)")
    p.add_argument("--speed-limit", type=str, default="",
                   help="Max configs to pass speed stage (default: all)")
    p.add_argument("--no-live-output", action="store_true",
                   help="Disable live file updates")
    p.add_argument("--no-skip-key", action="store_true",
                   help="Disable skip key (S) during stages")
    p.add_argument("--no-similarity-boost", action="store_true",
                   help="Disable similarity-based prioritization")
    p.add_argument("--no-interactive-options", action="store_true",
                   help="Skip interactive test options prompts (use CLI args or defaults)")
    args = p.parse_args()

    options = TestOptions()
    if args.ping_timeout > 0:
        options.ping_timeout = args.ping_timeout
    if args.latency_timeout > 0:
        options.latency_timeout = args.latency_timeout
    if args.speed_timeout > 0:
        options.speed_timeout = args.speed_timeout
    if args.speed_size:
        options.speed_size = parse_size_bytes(args.speed_size)
    if args.ping_limit:
        options.limits.ping = parse_limit(args.ping_limit)
    if args.latency_limit:
        options.limits.latency = parse_limit(args.latency_limit)
    if args.speed_limit:
        options.limits.speed = parse_limit(args.speed_limit)
    if args.no_live_output:
        options.live_output = False
    if args.no_skip_key:
        options.skip_key_enabled = False
    if args.no_similarity_boost:
        options.similarity_boost = False
    if args.output:
        options.output_path = args.output

    if args.rank:
        if not args.input:
            print("  --input (-i) is required in rank mode")
            sys.exit(1)
        c = args.concurrency if args.concurrency > 0 else DEFAULT_CONCURRENCY
        out = args.output or "ranked_configs.txt"
        options.output_path = out
        try:
            asyncio.run(speedrank_main(c, args.input, out, options))
            play_notification()
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n Bye!")
            sys.exit(1)
        return

    if args.auto:
        medium = CPU_CORES * 2
        c = args.concurrency if args.concurrency > 0 else medium
        try:
            asyncio.run(auto_main(c, options))
            play_notification()
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n Bye!")
            sys.exit(1)
        return

    concurrency = args.concurrency
    if concurrency == 0 and not args.yes:
        concurrency = ask_concurrency()
    elif concurrency == 0:
        concurrency = DEFAULT_CONCURRENCY

    if not args.no_interactive_options:
        options = ask_test_options()

    try:
        asyncio.run(main(concurrency, args.input, args.no_subs, options=options))
        play_notification()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n Bye!")
        sys.exit(1)


if __name__ == "__main__":
    entry()
