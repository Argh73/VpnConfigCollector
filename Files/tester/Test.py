import socket
import re
import os
import random
import time
import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz
import jdatetime

PROTOCOL_DIR = "Splitted-By-Protocol"
PROTOCOL_FILES = ["Hysteria2.txt", "ShadowSocks.txt", "Trojan.txt", "Vless.txt", "Vmess.txt"]
OUTPUT_DIR = "tested"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "config_test.txt")

MAX_SUCCESSFUL_CONFIGS = 20
MAX_CONFIGS_TO_TEST = 100
TIMEOUT = 1

# Setup output folder
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
for file in os.listdir(OUTPUT_DIR):
    if os.path.isfile(os.path.join(OUTPUT_DIR, file)):
        os.remove(os.path.join(OUTPUT_DIR, file))


def clean_config_link(config):
    return config.split("#")[0]


def get_protocol(config):
    match = re.match(r"^(vless|trojan|ss|hysteria2|vmess)://", config)
    return match.group(1).lower() if match else "unknown"


def extract_host_port(config):
    try:
        # Hysteria2
        if config.startswith(("hy2://", "hysteria2://")):
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", config)
            if match:
                return match.group(1).strip("[]"), int(match.group(2))

        # Shadowsocks
        if config.startswith("ss://"):
            link = config.split("#")[0]
            b64 = link[5:]

            # 1. ss://base64(method:pass@host:port)
            try:
                padding = len(b64) % 4
                if padding:
                    b64 += "=" * (4 - padding)
                decoded = base64.b64decode(b64).decode('utf-8')
                match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", decoded)
                if match:
                    return match.group(1).strip("[]"), int(match.group(2))
            except:
                pass

            # 2. Direct ss://method:pass@host:port
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", link)
            if match:
                return match.group(1).strip("[]"), int(match.group(2))

            # 3. JSON base64
            try:
                padding = len(b64) % 4
                if padding:
                    b64 += "=" * (4 - padding)
                data = json.loads(base64.b64decode(b64).decode('utf-8'))
                host = data.get("add") or data.get("host") or data.get("server")
                port = data.get("port")
                if host and port:
                    return str(host).strip("[]"), int(port)
            except:
                pass

        # Vless / Trojan
        match = re.search(r"(vless|trojan)://.+?@\[?([^\]:]+)\]?:(\d+)", config)
        if match:
            return match.group(2).strip("[]"), int(match.group(3))

        # Vmess
        match = re.match(r"vmess://([A-Za-z0-9+/=]+)", config)
        if match:
            b64 = match.group(1)
            padding = len(b64) % 4
            if padding:
                b64 += "=" * (4 - padding)
            try:
                data = json.loads(base64.b64decode(b64).decode('utf-8'))
                host = data.get("add") or data.get("host")
                port = data.get("port")
                if host and port:
                    return str(host).strip("[]"), int(port)
            except Exception:
                return None, None

        return None, None

    except Exception:
        return None, None


def test_connection_and_ping(config, timeout=TIMEOUT):
    result = extract_host_port(config)
    if not result:
        return None
    
    host, port = result
    if not host or not port or not isinstance(port, int) or not (0 <= port <= 65535):
        return None

    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        res = sock.connect_ex((host, port))
        sock.close()
        if res == 0:
            return {
                "config": config,
                "host": host,
                "port": port,
                "ping": (time.time() - start) * 1000,
                "protocol": get_protocol(config)
            }
        return None
    except:
        return None

current_date_time = jdatetime.datetime.now(pytz.timezone('Asia/Tehran'))
final_string = current_date_time.strftime("%b-%d | %H:%M")

all_successful = []

for file_name in PROTOCOL_FILES:
    path = os.path.join(PROTOCOL_DIR, file_name)
    if not os.path.exists(path):
        continue

    with open(path, encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]

    if len(links) > MAX_CONFIGS_TO_TEST:
        links = random.sample(links, MAX_CONFIGS_TO_TEST)

    print(f"Testing {len(links)} configs from {file_name} ...")

    results = []
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(test_connection_and_ping, link): link for link in links}
        for future in as_completed(futures):
            res = future.result()
            if res and len(results) < MAX_SUCCESSFUL_CONFIGS * 2:
                results.append(res)

    results.sort(key=lambda x: x["ping"])
    all_successful.extend(results[:MAX_SUCCESSFUL_CONFIGS])

# Save results
if all_successful:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"#🌐 Updated at {final_string} | MTSRVRS\n")
        for i, item in enumerate(all_successful, 1):
            clean = clean_config_link(item["config"])
            line = f"#🌐server {i} | {item['protocol']} | {final_string} | Ping: {item['ping']:.2f}ms"
            f.write(f"{clean}{line}\n")
    print(f"✅ Successfully saved {len(all_successful)} configs to {OUTPUT_FILE}")
else:
    print("❌ No working configs found.")
