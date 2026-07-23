from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Dict

from v2ray_tester.constants import _HAS_RICH, _RICH_CONSOLE
from v2ray_tester.parsers import parse_link


@dataclass
class ProxyResult:
    link: str
    protocol: str
    address: str
    ping_ms: Optional[float] = None
    ping_error: str = ""
    latency_ms: Optional[float] = None
    latency_error: str = ""
    speed_mbps: Optional[float] = None
    speed_error: str = ""
    sub_url: str = ""
    country: str = ""


def _get_config_name(link: str) -> str:
    if "#" in link:
        name = link.split("#", 1)[1]
        try:
            name = urllib.parse.unquote(name)
        except Exception:
            pass
        return name.strip()
    return ""


def _short_addr(addr: str) -> str:
    return addr if len(addr) <= 32 else addr[:29] + "..."


def init_results(links: List[str]) -> List[ProxyResult]:
    results: List[ProxyResult] = []
    for link in links:
        cfg = parse_link(link)
        if cfg is None:
            results.append(ProxyResult(link=link, protocol="", address="", ping_error="bad url"))
        else:
            results.append(ProxyResult(link=link, protocol=cfg["protocol"], address=f"{cfg['address']}:{cfg['port']}"))
    return results


def _dedup_results(results: List[ProxyResult]) -> int:
    seen: Set[str] = set()
    removed = 0
    for r in results:
        if not r.protocol:
            continue
        cfg = parse_link(r.link)
        if cfg is None:
            continue
        if cfg["protocol"] in ("vmess", "vless"):
            key = cfg.get("id", "")
        elif cfg["protocol"] == "shadowsocks":
            key = f"{cfg.get('method', '')}:{cfg.get('password', '')}"
        elif cfg["protocol"] in ("trojan", "hysteria2"):
            key = cfg.get("password", "")
        else:
            key = ""
        net = cfg.get("network", "tcp")
        sec = cfg.get("security_proto", "none")
        fingerprint = f"{r.protocol}:{r.address}:{key}:{net}:{sec}"
        if fingerprint in seen:
            r.protocol = ""
            r.ping_error = "duplicate"
            removed += 1
        else:
            seen.add(fingerprint)
    return removed


def print_final_summary(results: List[ProxyResult]):
    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    heading = f"  {'#':<3} {'Protocol':<8} {'Server':<30} {'Ping':<7} {'Latency':<8} {'Speed':<7} {'Status'}"
    print(heading)
    print("  " + "-" * len(heading))

    show_speed = any(r.speed_mbps is not None for r in results)
    for i, r in enumerate(results, 1):
        proto = r.protocol.upper() if r.protocol else "ERROR"
        addr = _short_addr(r.address)

        if r.ping_ms is not None:
            ping_s = f"{r.ping_ms:5.0f}ms"
        elif r.ping_error:
            ping_s = "FAIL"
        else:
            ping_s = "-"

        if r.latency_ms is not None:
            lat_s = f"{r.latency_ms:6.0f}ms"
        elif r.latency_error:
            lat_s = "FAIL"
        else:
            lat_s = "-"

        if r.speed_mbps is not None:
            spd_s = f"{r.speed_mbps:5.2f}" if show_speed else ""
        elif r.speed_error:
            spd_s = "FAIL"
        else:
            spd_s = ""

        if ping_s != "FAIL" and lat_s != "FAIL":
            status = "[OK]"
        else:
            err = r.latency_error or r.ping_error or ""
            status = err[:35] if err else "FAIL"

        if show_speed:
            print(f"  {i:<3} {proto:<8} {addr:<30} {ping_s:<7} {lat_s:<8} {spd_s:<7} {status}")
        else:
            print(f"  {i:<3} {proto:<8} {addr:<30} {ping_s:<7} {lat_s:<8} {status}")

    speed_results = [(i+1, r) for i, r in enumerate(results) if r.speed_mbps is not None]
    if speed_results:
        speed_results.sort(key=lambda x: _balanced_score(x[1].latency_ms, x[1].speed_mbps), reverse=True)
        print()
        print(f"  SPEED RANKINGS  [rank - country - latency - speed - name]")
        print("  " + "-" * 60)
        for rank, (orig_idx, r) in enumerate(speed_results, 1):
            name = _get_config_name(r.link) or _short_addr(r.address)
            country = r.country if r.country else "??"
            print(f"  [{rank:2}]  {country:>3}  {r.latency_ms:6.0f}ms  {r.speed_mbps:6.2f}MB/s  {name}")
    print()


def print_rich_summary(results: List[ProxyResult]):
    from rich.table import Table
    from rich import box

    console = _RICH_CONSOLE
    show_speed = any(r.speed_mbps is not None for r in results)

    cols = [
        ("#", "dim"),
        ("Protocol", ""),
        ("Server", ""),
        ("Ping", ""),
        ("Latency", ""),
    ]
    if show_speed:
        cols.append(("Speed", ""))
    cols.append(("Status/Error", ""))

    tbl = Table(box=box.ASCII, header_style="bold cyan")
    for name, style in cols:
        tbl.add_column(name, style=style, width=(32 if name == "Server" else None))

    for i, r in enumerate(results, 1):
        proto = r.protocol.upper() if r.protocol else "ERROR"
        addr = _short_addr(r.address)

        ping_s = f"{r.ping_ms:5.0f}ms" if r.ping_ms is not None else ("FAIL" if r.ping_error else "-")
        lat_s = f"{r.latency_ms:6.0f}ms" if r.latency_ms is not None else ("FAIL" if r.latency_error else "-")

        if r.speed_mbps is not None:
            spd_s = f"{r.speed_mbps:.2f}"
        elif r.speed_error:
            spd_s = "FAIL"
        else:
            spd_s = ""

        if r.ping_ms is not None and r.latency_ms is not None:
            status = "[OK]"
        else:
            err = r.latency_error or r.ping_error or ""
            status = err[:35] if err else "FAIL"

        row = [str(i), proto, addr, ping_s, lat_s]
        if show_speed:
            row.append(spd_s)
        row.append(status)
        tbl.add_row(*row)

    console.print(tbl)

    speed_results = [(i+1, r) for i, r in enumerate(results) if r.speed_mbps is not None]
    if speed_results:
        speed_results.sort(key=lambda x: _balanced_score(x[1].latency_ms, x[1].speed_mbps), reverse=True)
        rtbl = Table(box=box.ASCII, header_style="bold yellow", title="SPEED RANKINGS [rank - country - latency - speed - name]")
        rtbl.add_column("Rank", justify="right", width=5)
        rtbl.add_column("Country", justify="center", width=7)
        rtbl.add_column("Latency", justify="right", width=8)
        rtbl.add_column("Speed", justify="right", width=10)
        rtbl.add_column("Name", width=50)
        for rank, (_, r) in enumerate(speed_results, 1):
            name = _get_config_name(r.link) or _short_addr(r.address)
            country = r.country if r.country else "??"
            rtbl.add_row(
                f"[{rank}]",
                f"{country:>3}",
                f"{r.latency_ms:.0f}ms",
                f"{r.speed_mbps:.2f}MB/s",
                name,
            )
        console.print()
        console.print(rtbl)


def _balanced_score(latency_ms: float, speed_mbps: float) -> float:
    if latency_ms <= 0 or speed_mbps <= 0:
        return 0
    return speed_mbps * 100.0 / latency_ms


def _print_stage_header(name: str, count: int, is_retry: bool = False):
    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        style = "bold yellow" if is_retry else "bold cyan"
        _RICH_CONSOLE.print(Panel(
            f"[{style}]{name}[/] \u2014 [white]{count}[/] config(s)",
            box=box.ASCII
        ))
    else:
        label = f" {name} " if is_retry else f" {name} "
        print(f"\n---{label:-^66}")


def _print_retry_header(name: str, retry_count: int, skipped_count: int):
    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print(Panel(
            f"[bold yellow]{name} retry[/] \u2014 [white]{retry_count}[/] config(s) "
            f"(skipping {skipped_count} already OK)",
            box=box.ASCII
        ))
    else:
        print(f"\n {name} retry \u2014 {retry_count} config(s) (skipping {skipped_count} already OK)")


def _print_ok(proto: str, addr: str, val: str):
    if _HAS_RICH:
        _RICH_CONSOLE.print(f"  [bold green]OK[/]  {proto:7} {addr:30}  [green]{val}[/]")
    else:
        print(f"  OK  {proto:7} {addr:30}  {val}")


def _print_fail(proto: str, addr: str, err: str):
    if _HAS_RICH:
        _RICH_CONSOLE.print(f"  [bold red]FAIL[/] {proto:7} {addr:30}  [red]{err}[/]")
    else:
        print(f"  FAIL {proto:7} {addr:30}  {err}")


def _status_spinner(text: str):
    if _HAS_RICH:
        return _RICH_CONSOLE.status(text, spinner="dots")
    else:
        import contextlib
        return contextlib.nullcontext()


def _print_drop_summary(stage: str, passed: int, failed: int):
    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print(Panel(
            f"[bold yellow]{stage} complete[/] \u2014 {passed} passed, {failed} dropped",
            box=box.ASCII
        ))
    else:
        print(f"\n {stage} \u2014 {passed} passed, {failed} dropped")


def _print_skip_msg(msg: str):
    if _HAS_RICH:
        _RICH_CONSOLE.print(f"  [dim]{msg}[/]")
    else:
        print(f"  {msg}")


def _print_skip_summary(stage_name: str, passed: int, skipped: int):
    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print(Panel(
            f"[bold yellow]{stage_name} SKIPPED[/] \u2014 {passed} passed, {skipped} skipped (pending tests not run)",
            box=box.ASCII
        ))
    else:
        print(f"\n {stage_name} SKIPPED \u2014 {passed} passed, {skipped} skipped")


def _print_dedup_summary(count: int):
    if _HAS_RICH:
        from rich.panel import Panel
        from rich import box
        _RICH_CONSOLE.print(Panel(
            f"[bold cyan]DEDUP[/] \u2014 [white]{count}[/] duplicate(s) removed",
            box=box.ASCII
        ))
    else:
        print(f"\n DEDUP \u2014 {count} duplicate(s) removed")


def _print_sub_fetch_status(status: List[Tuple[str, int]]) -> Tuple[int, int]:
    success = 0
    failed = 0
    for url, count in status:
        short = url.split("/")[-1] if "/" in url else url
        if count > 0:
            print(f"  [OK]   {short:50} {count:4} configs")
            success += 1
        else:
            print(f"  [FAIL] {short:50} \u2014")
            failed += 1
    return success, failed
