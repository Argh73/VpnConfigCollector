from __future__ import annotations

import asyncio
import re
import socket
import urllib.parse
from typing import Dict, List, Optional, Tuple

from v2ray_tester.constants import SPEED_MIN_MBPS
from v2ray_tester.parsers import parse_link
from v2ray_tester.display import _get_config_name, ProxyResult

try:
    from ipwhois import IPWhois
except ImportError:
    IPWhois = None


_COUNTRY_MAP = {
    "us": "United States", "usa": "United States", "america": "United States",
    "de": "Germany", "germany": "Germany", "deutschland": "Germany",
    "fr": "France", "france": "France",
    "gb": "United Kingdom", "uk": "United Kingdom", "united kingdom": "United Kingdom",
    "nl": "Netherlands", "netherlands": "Netherlands", "holland": "Netherlands",
    "jp": "Japan", "japan": "Japan",
    "sg": "Singapore", "singapore": "Singapore",
    "kr": "South Korea", "korea": "South Korea",
    "ca": "Canada", "canada": "Canada",
    "au": "Australia", "australia": "Australia",
    "ru": "Russia", "russia": "Russia",
    "cn": "China", "china": "China",
    "tw": "Taiwan", "taiwan": "Taiwan",
    "hk": "Hong Kong", "hong kong": "Hong Kong",
    "in": "India", "india": "India",
    "br": "Brazil", "brazil": "Brazil",
    "it": "Italy", "italy": "Italy",
    "es": "Spain", "spain": "Spain",
    "se": "Sweden", "sweden": "Sweden",
    "no": "Norway", "norway": "Norway",
    "fi": "Finland", "finland": "Finland",
    "dk": "Denmark", "denmark": "Denmark",
    "pl": "Poland", "poland": "Poland",
    "cz": "Czech Republic", "czech": "Czech Republic",
    "at": "Austria", "austria": "Austria",
    "ch": "Switzerland", "switzerland": "Switzerland",
    "ie": "Ireland", "ireland": "Ireland",
    "be": "Belgium", "belgium": "Belgium",
    "il": "Israel", "israel": "Israel",
    "tr": "Turkey", "turkey": "Turkey",
    "ae": "UAE", "uae": "UAE",
    "za": "South Africa", "south africa": "South Africa",
    "mx": "Mexico", "mexico": "Mexico",
    "ar": "Argentina", "argentina": "Argentina",
}


def _get_country_from_remark(link: str) -> str:
    name = _get_config_name(link)
    if not name:
        return ""
    name_lower = name.lower()
    for key, country in sorted(_COUNTRY_MAP.items(), key=lambda x: -len(x[0])):
        if len(key) > 3:
            if key in name_lower:
                return country
    for key, country in _COUNTRY_MAP.items():
        if len(key) <= 3 and re.search(rf'(?:^|[^a-z]){re.escape(key)}(?:$|[^a-z])', name_lower):
            return country
    return ""


def _extract_host(address: str) -> str:
    if ":" in address:
        return address.rsplit(":", 1)[0]
    return address


def rename_config_link(link: str, rank: int, total: int, country: str, speed_mbps: float, ping_ms: float) -> str:
    width = len(str(total))
    new_name = f"[{rank:0{width}d} - {country} - {speed_mbps:.1f}MB/s - {ping_ms:.0f}ms]"
    encoded = urllib.parse.quote(new_name, safe="")
    if "#" in link:
        base, _ = link.rsplit("#", 1)
        return base + "#" + encoded
    return link + "#" + encoded


def _rank_and_rename(results: List[ProxyResult]) -> int:
    ranked = [r for r in results if r.speed_mbps is not None and r.speed_mbps >= SPEED_MIN_MBPS]
    ranked.sort(key=lambda r: r.speed_mbps, reverse=True)
    total = len(ranked)
    for rank_num, r in enumerate(ranked, 1):
        country = r.country if r.country else "??"
        ping = r.ping_ms if r.ping_ms is not None else 0
        r.link = rename_config_link(r.link, rank_num, total, country, r.speed_mbps, ping)
    return total


async def _lookup_countries(results: List[ProxyResult], max_workers: int = 10) -> None:
    if IPWhois is None:
        return
    targets = [(i, r) for i, r in enumerate(results) if r.speed_mbps is not None and r.address]
    if not targets:
        return

    for i, r in targets:
        remark_country = _get_country_from_remark(r.link)
        if remark_country:
            r.country = remark_country

    cache: Dict[str, str] = {}
    sem = asyncio.Semaphore(max_workers)
    ipwhois = IPWhois().set_timeout(5)

    async def resolve_and_lookup(i: int, r: ProxyResult) -> None:
        if r.country:
            return
        host = _extract_host(r.address)
        if host in cache:
            r.country = cache[host]
            return
        ip = host
        if not host.replace(".", "").isdigit():
            try:
                loop = asyncio.get_running_loop()
                ip = await asyncio.wait_for(
                    loop.run_in_executor(None, socket.gethostbyname, host),
                    timeout=5,
                )
            except Exception:
                cache[host] = "??"
                r.country = "??"
                return
        if ip in cache:
            r.country = cache[ip]
            return
        async with sem:
            try:
                loop = asyncio.get_running_loop()
                info = await asyncio.wait_for(
                    loop.run_in_executor(None, ipwhois.lookup, ip),
                    timeout=6,
                )
                if info.get("success"):
                    country = info.get("country", "??")
                    cache[host] = country
                    cache[ip] = country
                    r.country = country
                    return
            except Exception:
                pass
        cache[host] = "??"
        cache[ip] = "??"
        r.country = "??"

    tasks = [resolve_and_lookup(i, r) for i, r in targets]
    await asyncio.gather(*tasks)
