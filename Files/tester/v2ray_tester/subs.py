from __future__ import annotations

import asyncio
import base64
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from v2ray_tester.display import ProxyResult, _print_sub_fetch_status
from v2ray_tester.constants import _HAS_RICH, _RICH_CONSOLE

try:
    from aiohttp import ClientSession, ClientTimeout
except ImportError:
    pass


SUBS_FILE = "subs.txt"
BAD_SUBS_FILE = "bad_subs.txt"
_CONFIG_REGEX = re.compile(r"(?:vless|vmess|ss|trojan|socks5|hy2|hysteria2|tuic):\/\/[^\s\"']+", re.IGNORECASE)


def _base64_decode_sub(s: str) -> str:
    try:
        raw = base64.b64decode(s.replace("-", "+").replace("_", "/") + "==").decode("utf-8", errors="replace")
        return raw
    except Exception:
        return s


def extract_configs_from_sub_content(text: str) -> List[str]:
    content = text.strip()
    if "://" not in content:
        try:
            decoded = _base64_decode_sub(content)
            if "://" in decoded:
                content = decoded
        except Exception:
            pass
    matches = _CONFIG_REGEX.findall(content)
    if not matches and "://" not in content:
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if line and "://" not in line:
                try:
                    decoded = _base64_decode_sub(line)
                    matches.extend(_CONFIG_REGEX.findall(decoded))
                except Exception:
                    pass
    return list(dict.fromkeys(matches))


def load_subs() -> List[str]:
    path = Path(SUBS_FILE)
    if not path.is_file():
        return []
    seen: Set[str] = set()
    urls: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if line not in seen:
                    seen.add(line)
                    urls.append(line)
    return urls


def save_subs(urls: List[str]) -> None:
    seen: Set[str] = set()
    with open(SUBS_FILE, "w", encoding="utf-8") as f:
        for u in urls:
            if u not in seen:
                seen.add(u)
                f.write(u + "\n")


async def fetch_sub(session: ClientSession, url: str, timeout: int = 15) -> Tuple[str, List[str]]:
    try:
        async with session.get(url, timeout=ClientTimeout(total=timeout), ssl=False) as resp:
            if resp.status != 200:
                return url, []
            text = await resp.text(encoding="utf-8", errors="replace")
            configs = extract_configs_from_sub_content(text)
            return url, configs
    except Exception:
        return url, []


async def fetch_all_subs(urls: List[str], concurrency: int) -> Tuple[List[str], Dict[str, str], List[Tuple[str, int]]]:
    connector = ClientTimeout(total=30)
    async with ClientSession(timeout=connector) as session:
        sem = asyncio.Semaphore(concurrency)

        async def bound_fetch(url: str) -> Tuple[str, List[str]]:
            async with sem:
                return await fetch_sub(session, url)

        tasks = [bound_fetch(url) for url in urls]
        results = await asyncio.gather(*tasks)

    all_configs: List[str] = []
    config_to_sub: Dict[str, str] = {}
    status: List[Tuple[str, int]] = []
    for url, configs in results:
        status.append((url, len(configs)))
        for cfg in configs:
            if cfg not in config_to_sub:
                config_to_sub[cfg] = url
                all_configs.append(cfg)

    return all_configs, config_to_sub, status


def _archive_bad_subs(bad_urls: List[str]) -> None:
    if not bad_urls:
        return
    try:
        with open(BAD_SUBS_FILE, "a", encoding="utf-8") as f:
            f.write(f"# Pruned {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            for u in bad_urls:
                f.write(u + "\n")
    except OSError:
        pass


def _smart_sub_cleanup(results: List[ProxyResult], subs: List[str]) -> List[str]:
    if not subs:
        return subs

    sub_total: Dict[str, int] = {}
    sub_working: Dict[str, int] = {}
    for r in results:
        if r.sub_url:
            sub_total[r.sub_url] = sub_total.get(r.sub_url, 0) + 1
            if r.latency_ms is not None:
                sub_working[r.sub_url] = sub_working.get(r.sub_url, 0) + 1

    if not sub_total:
        return subs

    _em = "\u2014"
    line_wide = "\u2500" * 50
    line_narrow = "\u2500" * 6
    print()
    print(" \u2500\u2500 Smart Sub Cleanup (Stage 4) \u2500\u2500")
    print(f"  {'Sub':<50} {'Total':>6} {'Working':>8}")
    print(f"  {line_wide} {line_narrow} {line_narrow}")
    dead_subs = []
    alive_subs = []
    for url in subs:
        total = sub_total.get(url, 0)
        working = sub_working.get(url, 0)
        short = url.split("/")[-1] if "/" in url else url
        if working > 0:
            alive_subs.append(url)
            print(f"  {short:<50} {total:6} {working:8}")
        else:
            dead_subs.append(url)
            print(f"  {short:<50} {total:6} {_em:>8}")

    if not dead_subs:
        print(f"\n All {len(subs)} sub(s) have working configs.")
        return subs

    print(f"\n {len(dead_subs)} of {len(subs)} sub(s) had NO configs passing latency.")
    try:
        ans = input(" Keep only subs with working configs? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"
    if ans == "y":
        _archive_bad_subs(dead_subs)
        save_subs(alive_subs)
        print(f" Pruned {len(dead_subs)} sub(s). {len(alive_subs)} remaining.")
        return alive_subs
    return subs


def prompt_prune_subs(results: List[ProxyResult], subs: List[str]) -> List[str]:
    if not subs:
        return subs

    good_subs: Set[str] = set()
    for r in results:
        if r.latency_ms is not None and r.sub_url:
            good_subs.add(r.sub_url)

    bad_count = len(subs) - len(good_subs)
    if bad_count == 0:
        print(f"\n All {len(subs)} subscription(s) have working configs \u2014 nothing to prune.")
        return subs

    print()
    print(f" {bad_count} of {len(subs)} subscription(s) had NO configs passing latency test.")
    try:
        ans = input(" Keep only subs with working configs? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"
    if ans == "y":
        kept = [u for u in subs if u in good_subs]
        bad = [u for u in subs if u not in good_subs]
        _archive_bad_subs(bad)
        print(f" Pruned {bad_count} sub(s). {len(kept)} remaining.")
        save_subs(kept)
        return kept
    return subs
