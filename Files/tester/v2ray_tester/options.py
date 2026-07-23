from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


def parse_size_bytes(s: str) -> int:
    s = s.strip().lower()
    multipliers = {
        "b": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024 * 1024,
        "mib": 1024 * 1024,
        "gb": 1024 * 1024 * 1024,
        "gib": 1024 * 1024 * 1024,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            num_part = s[: -len(suffix)].strip()
            if not num_part:
                return mult
            try:
                return int(float(num_part) * mult)
            except ValueError:
                continue
    try:
        return int(float(s))
    except ValueError:
        return 5 * 1024 * 1024


def parse_limit(s: str) -> Optional[int]:
    s = s.strip().lower()
    if not s or s in ("all", "none", "0", "unlimited", ""):
        return None
    try:
        n = int(s)
        return None if n <= 0 else n
    except ValueError:
        return None


@dataclass
class StageLimits:
    ping: Optional[int] = None
    latency: Optional[int] = None
    speed: Optional[int] = None
    country: Optional[int] = None

    def for_stage(self, stage_name: str) -> Optional[int]:
        name = stage_name.upper().strip()
        if "PING" in name:
            return self.ping
        if "LATENCY" in name:
            return self.latency
        if "SPEED" in name:
            return self.speed
        if "COUNTRY" in name or "GEO" in name:
            return self.country
        return None


@dataclass
class TestOptions:
    ping_timeout: float = 3.0
    latency_timeout: float = 5.0
    speed_timeout: float = 120.0
    speed_size: int = 5 * 1024 * 1024
    limits: StageLimits = field(default_factory=StageLimits)
    live_output: bool = True
    skip_key_enabled: bool = True
    similarity_boost: bool = True
    output_path: str = ""
    concurrency: int = 0
    skip_stages: list = field(default_factory=list)
