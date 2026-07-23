from __future__ import annotations

from typing import Optional


def build_stream_settings(cfg: dict) -> dict:
    s: dict = {}
    network = cfg.get("network", "tcp")
    s["network"] = network
    sec = cfg.get("security_proto", "none")
    s["security"] = sec

    if network in ("ws", "websocket"):
        ws: dict = {}
        if cfg.get("path"):
            ws["path"] = cfg["path"]
        if cfg.get("host"):
            ws["headers"] = {"Host": cfg["host"]}
        if ws:
            s["wsSettings"] = ws
    elif network in ("kcp", "mkcp"):
        kcp: dict = {}
        if cfg.get("seed"):
            kcp["seed"] = cfg["seed"]
        htype = cfg.get("type", "none")
        if htype and htype != "none":
            kcp["header"] = {"type": htype}
        if kcp:
            s["kcpSettings"] = kcp
    elif network in ("h2", "http"):
        h2: dict = {}
        if cfg.get("path"):
            h2["path"] = cfg["path"]
        if cfg.get("host"):
            h2["host"] = [cfg["host"]]
        if h2:
            s["httpSettings"] = h2
    elif network == "quic":
        quic: dict = {}
        qs = cfg.get("quicSecurity", "")
        if qs and qs != "none":
            quic["security"] = qs
            if cfg.get("key"):
                quic["key"] = cfg["key"]
        htype = cfg.get("type", "none")
        if htype and htype != "none":
            quic["header"] = {"type": htype}
        if quic:
            s["quicSettings"] = quic
    elif network == "grpc":
        grpc: dict = {}
        if cfg.get("serviceName"):
            grpc["serviceName"] = cfg["serviceName"]
        if cfg.get("mode") == "multi":
            grpc["multiMode"] = True
        if grpc:
            s["grpcSettings"] = grpc

    if sec == "tls":
        tls: dict = {}
        sni = cfg.get("sni") or cfg.get("host") or ""
        if sni:
            tls["serverName"] = sni
        fp = cfg.get("fp", "")
        if fp:
            if fp == "random":
                fp = "randomized"
            tls["fingerprint"] = fp
        if cfg.get("alpn"):
            tls["alpn"] = [a.strip() for a in cfg["alpn"].split(",") if a.strip()]
        if tls:
            s["tlsSettings"] = tls
    elif sec == "reality":
        rl: dict = {"show": False}
        sni = cfg.get("sni") or cfg.get("host") or ""
        if sni:
            rl["serverName"] = sni
        if cfg.get("fp"):
            rl["fingerprint"] = cfg["fp"]
        if cfg.get("pbk"):
            rl["publicKey"] = cfg["pbk"]
        if cfg.get("sid"):
            rl["shortId"] = cfg["sid"]
        if cfg.get("spx"):
            rl["spiderX"] = cfg["spx"]
        s["realitySettings"] = rl
    return s


def build_xray_config(cfg: dict, local_port: int) -> Optional[dict]:
    proto = cfg.get("protocol", "")
    addr = cfg.get("address", "")
    port = cfg.get("port", 0)
    if not addr or not port:
        return None

    ob: dict = {"tag": "proxy", "protocol": proto, "settings": {}, "streamSettings": build_stream_settings(cfg)}

    if proto == "vmess":
        ob["settings"] = {"vnext": [{"address": addr, "port": port, "users": [{"id": cfg["id"], "alterId": cfg.get("alterId", 0), "security": cfg.get("security", "auto")}]}]}
    elif proto == "vless":
        ob["settings"] = {"vnext": [{"address": addr, "port": port, "users": [{"id": cfg["id"], "flow": cfg.get("flow", ""), "encryption": cfg.get("encryption", "none")}]}]}
    elif proto == "shadowsocks":
        ob["settings"] = {"servers": [{"address": addr, "port": port, "method": cfg.get("method", ""), "password": cfg.get("password", "")}]}
    elif proto == "trojan":
        ob["settings"] = {"servers": [{"address": addr, "port": port, "password": cfg.get("password", ""), "flow": cfg.get("flow", "")}]}
    elif proto == "hysteria2":
        ob["settings"] = {"server": f"{addr}:{port}", "password": cfg.get("password", "")}
    else:
        return None

    return {
        "log": {"loglevel": "error"},
        "inbounds": [{"tag": "socks-in", "protocol": "socks", "listen": "127.0.0.1", "port": local_port, "settings": {"udp": False, "auth": "noauth"}}],
        "outbounds": [ob],
        "routing": {"domainStrategy": "AsIs", "rules": [{"type": "field", "inboundTag": ["socks-in"], "outboundTag": "proxy"}]},
    }
