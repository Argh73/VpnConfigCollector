from __future__ import annotations

import os
import platform
import sys
import warnings

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

TEST_URL = "https://www.google.com/generate_204"
PING_TEST_URL = "https://www.google.com/generate_204"
REQUEST_TIMEOUT = 5
PING_TIMEOUT = 3
SPEED_TEST_URL = "https://cachefly.cachefly.net/50mb.test"
SPEED_TEST_TIMEOUT = 120
SPEED_READ_LIMIT = 5 * 1024 * 1024
SPEED_MIN_MBPS = 0.1
XRAY_START_TIMEOUT = 4
XRAY_POLL_INTERVAL = 0.05
PORT_START = 20000
PORT_END = 20499
CPU_CORES = os.cpu_count() or 4
_DEFAULT_MULTIPLIER = 2 if IS_WINDOWS else 4
DEFAULT_CONCURRENCY = min(CPU_CORES * _DEFAULT_MULTIPLIER, PORT_END - PORT_START + 1)

_HAS_RICH = False
_RICH_CONSOLE = None
try:
    from rich.table import Table
    from rich import box
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    _RICH_CONSOLE = Console()
    _HAS_RICH = True
except ImportError:
    pass

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

try:
    from aiohttp import ClientSession, ClientTimeout
    from aiohttp_socks import ProxyConnector, ProxyType, ProxyError, ProxyConnectionError
    warnings.filterwarnings("ignore", message=".*SSL.*", category=UserWarning)
except ImportError:
    print("Missing dependencies. Install with: pip install aiohttp aiohttp-socks")
    sys.exit(1)
