from __future__ import annotations

import base64
import json
import re
import urllib.parse
from typing import Optional


def _strip_prefix(s: str, prefix: str) -> str:
    return s[len(prefix):] if s.startswith(prefix) else s


def _decode_b64(s: str) -> str:
    s = s.strip()
    for variant in (s.replace("-", "+").replace("_", "/"), s):
        try:
            raw = variant
            pad = 4 - len(raw) % 4
            if pad != 4:
                raw += "=" * pad
            return base64.b64decode(raw).decode("utf-8")
        except Exception:
            continue
    return ""


def _as_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("1", "true", "yes")


def parse_vmess(link: str) -> Optional[dict]:
    raw = _strip_prefix(link, "vmess://").strip()
    decoded = _decode_b64(raw)
    if not decoded:
        return None
    try:
        j = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    out = {
        "protocol": "vmess",
        "address": (j.get("add") or j.get("address") or "").strip(),
        "port": int(j.get("port", 0)),
        "id": j.get("id", "").strip(),
        "alterId": int(j.get("aid", 0) or j.get("alterId", 0)),
        "security": j.get("scy") or j.get("security", "auto"),
        "network": j.get("net") or j.get("network", "tcp"),
        "type": j.get("type", "none"),
        "host": j.get("host", ""),
        "path": j.get("path", ""),
        "tls": j.get("tls", "none"),
        "sni": j.get("sni", ""),
        "alpn": j.get("alpn", ""),
        "fp": j.get("fp", ""),
        "allowInsecure": _as_bool(j.get("allowInsecure", False)),
    }
    if not out["address"] or not out["port"] or not out["id"]:
        return None
    out["security_proto"] = "tls" if out["tls"] in ("tls", "1", "true") else "none"
    return out


def _fix_url(link: str) -> str:
    if "?" not in link and "@" in link:
        m = re.match(r"^(\w+://[^@]+@[^:]+:\d+)(.*)$", link)
        if m and m.group(2):
            link = m.group(1) + "?" + m.group(2)
    scheme_end = link.find("://")
    if scheme_end >= 0:
        rest = link[scheme_end + 3:]
        path_start = len(rest)
        for sep in ("/", "?", "#"):
            idx = rest.find(sep)
            if idx >= 0 and idx < path_start:
                path_start = idx
        netloc = rest[:path_start]
        host_part = netloc.split("@", 1)[-1] if "@" in netloc else netloc
        if host_part.count(":") > 1 and not host_part.startswith("["):
            m = re.match(r"^(.+):(\d+)$", host_part)
            if m:
                host_part = f"[{m.group(1)}]:{m.group(2)}"
            else:
                host_part = f"[{host_part}]"
            at_idx = netloc.find("@")
            if at_idx >= 0:
                new_netloc = netloc[:at_idx + 1] + host_part
            else:
                new_netloc = host_part
            link = link[:scheme_end + 3] + new_netloc + rest[path_start:]
    return link


def _urlparse(link: str) -> Optional[urllib.parse.ParseResult]:
    try:
        return urllib.parse.urlparse(_fix_url(link))
    except ValueError:
        return None


def _safe_port(parsed: urllib.parse.ParseResult, default: int = 443) -> int:
    try:
        return parsed.port or default
    except ValueError:
        return default


def parse_vless(link: str) -> Optional[dict]:
    parsed = _urlparse(link)
    if parsed is None or parsed.scheme != "vless" or not parsed.hostname:
        return None
    q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def g(name: str, fb: str = "") -> str:
        return q.get(name, [fb])[0]

    out = {
        "protocol": "vless",
        "address": parsed.hostname,
        "port": _safe_port(parsed),
        "id": (parsed.username or "").strip(),
        "flow": g("flow"),
        "encryption": g("encryption", "none"),
        "network": g("type", "tcp"),
        "type": g("headerType", g("type", "none")),
        "host": g("host"),
        "path": g("path"),
        "security_proto": g("security", "none"),
        "sni": g("sni"),
        "alpn": g("alpn"),
        "fp": g("fp"),
        "pbk": g("pbk"),
        "sid": g("sid"),
        "spx": g("spx"),
        "serviceName": g("serviceName"),
        "mode": g("mode"),
        "seed": g("seed"),
        "quicSecurity": g("quicSecurity"),
        "key": g("key"),
        "allowInsecure": _as_bool(g("allowInsecure")),
    }
    return out if out["id"] else None


def parse_ss(link: str) -> Optional[dict]:
    raw = _strip_prefix(link, "ss://").strip()
    remark = ""
    if "#" in raw:
        raw, remark = raw.rsplit("#", 1)

    method = password = ""
    host_part = ""
    at_idx = raw.rfind("@")

    if at_idx > 0:
        b64_part = raw[:at_idx]
        host_part = raw[at_idx + 1:]
        decoded = _decode_b64(b64_part)
        if decoded and ":" in decoded:
            method, password = decoded.split(":", 1)
    else:
        decoded = _decode_b64(raw)
        if decoded and "@" in decoded:
            ui, host_part = decoded.split("@", 1)
            if ":" in ui:
                method, password = ui.split(":", 1)

    if not method or not password or not host_part:
        return None

    host_part = host_part.strip().split("?")[0].split("#")[0]
    if host_part.startswith("["):
        ipv6_end = host_part.find("]")
        if ipv6_end == -1:
            return None
        address = host_part[1:ipv6_end]
        port_str = host_part[ipv6_end + 1:].lstrip(":")
    else:
        *addr_parts, port_str = host_part.rsplit(":", 1) if ":" in host_part else [host_part, ""]
        address = ":".join(addr_parts) if addr_parts else ""

    if not address or not port_str:
        return None

    try:
        port_num = int(port_str)
    except (ValueError, TypeError):
        return None

    return {
        "protocol": "shadowsocks",
        "address": address,
        "port": port_num,
        "method": method,
        "password": password,
        "remark": remark.strip(),
    }


def parse_trojan(link: str) -> Optional[dict]:
    parsed = _urlparse(link)
    if parsed is None or parsed.scheme != "trojan" or not parsed.hostname:
        return None
    q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def g(name: str, fb: str = "") -> str:
        return q.get(name, [fb])[0]

    return {
        "protocol": "trojan",
        "address": parsed.hostname,
        "port": _safe_port(parsed),
        "password": (parsed.username or "").strip(),
        "flow": g("flow"),
        "security_proto": g("security", "tls"),
        "sni": g("sni"),
        "fp": g("fp"),
        "alpn": g("alpn"),
        "allowInsecure": _as_bool(g("allowInsecure")),
        "network": g("type", "tcp"),
        "host": g("host"),
        "path": g("path"),
    }


def parse_hy2(link: str) -> Optional[dict]:
    parsed = _urlparse(link)
    if parsed is None or parsed.scheme not in ("hy2", "hysteria2") or not parsed.hostname:
        return None
    q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def g(name: str, fb: str = "") -> str:
        return q.get(name, [fb])[0]

    return {
        "protocol": "hysteria2",
        "address": parsed.hostname,
        "port": _safe_port(parsed),
        "password": (parsed.username or "").strip(),
        "sni": g("sni"),
        "allowInsecure": _as_bool(g("insecure")),
        "alpn": g("alpn"),
    }


def parse_link(link: str) -> Optional[dict]:
    link = link.strip()
    if link and link[0] == "\ufeff":
        link = link[1:]
    if not link:
        return None
    handlers = (
        ("vmess://", parse_vmess),
        ("vless://", parse_vless),
        ("ss://", parse_ss),
        ("trojan://", parse_trojan),
        ("hy2://", parse_hy2),
        ("hysteria2://", parse_hy2),
    )
    for prefix, handler in handlers:
        if link.startswith(prefix):
            return handler(link)
    return None
