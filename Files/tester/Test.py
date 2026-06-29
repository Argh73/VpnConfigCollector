import socket
import re
import os
import random
import time
import base64
import binascii
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

# Setup output directory
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
for file in os.listdir(OUTPUT_DIR):
    if os.path.isfile(os.path.join(OUTPUT_DIR, file)):
        os.remove(os.path.join(OUTPUT_DIR, file))


def clean_config_link(config):
    protocol_match = re.match(r"^(vless|trojan|ss|hysteria2|vmess)://", config)
    if not protocol_match:
        print(f"Error: Invalid protocol in link: {config[:50]}...")
        return config
    return config.split("#")[0]


def get_protocol(config):
    match = re.match(r"^(vless|trojan|ss|hysteria2|vmess)://", config)
    return match.group(1).lower() if match else "unknown"


def extract_host_port(config):
    try:
        # === Hysteria2 ===
        if config.startswith(("hy2://", "hysteria2://")):
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", config)
            if match:
                return match.group(1).strip("[]"), int(match.group(2))

        # === Shadowsocks ===
        if config.startswith("ss://"):
            link = config[5:].split("#")[0].split("/")[0]
            
            # Case 1: Base64 JSON (most common in your list)
            try:
                padding = len(link) % 4
                if padding:
                    link += "=" * (4 - padding)
                decoded = base64.b64decode(link).decode('utf-8')
                data = json.loads(decoded)
                host = data.get("add") or data.get("host") or data.get("server")
                port = data.get("port")
                if host and port:
                    return str(host).strip("[]"), int(port)
            except:
                pass

            # Case 2: Standard ss://method:pass@host:port
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", config)
            if match:
                return match.group(1).strip("[]"), int(match.group(2))

        # === Vless / Trojan ===
        match = re.search(r"(vless|trojan)://.+?@\[?([^\]:]+)\]?:(\d+)", config)
        if match:
            return match.group(2).strip("[]"), int(match.group(3))

        match = re.search(r"(vless|trojan)://\[?([^\]:]+)\]?:(\d+)", config)
        if match:
            return match.group(2).strip("[]"), int(match.group(3))

        # === Vmess ===
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
            except Exception as e:
                print(f"VMess decode error: {e} | {config[:60]}...")
                return None, None

        print(f"Unsupported link: {config[:80]}...")
        return None, None

    except Exception as e:
        print(f"Extract error: {e} | {config[:60]}...")
        return None, None


def test_connection_and_ping(config, timeout=TIMEOUT):
    host, port = extract_host_port(config)
    if not host or not port or not (0 <= port <= 65535):
        return None
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
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
        
    with open(path, 'r', encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]
    
    if len(links) > MAX_CONFIGS_TO_TEST:
        links = random.sample(links, MAX_CONFIGS_TO_TEST)
    
    print(f"Testing {len(links)} configs from {file_name} ...")
    
    results = []
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(test_connection_and_ping, link): link for link in links}
        for future in as_completed(futures):
            res = future.result()
            if res and len(results) < MAX_SUCCESSFUL_CONFIGS:
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
    print(f"✅ Successfully saved to {OUTPUT_FILE} ({len(all_successful)} configs)")
else:
    print("❌ No working configs found.")
