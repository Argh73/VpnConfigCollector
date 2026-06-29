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
PROTOCOL_FILES = [
    "Hysteria2.txt",
    "ShadowSocks.txt",
    "Trojan.txt",
    "Vless.txt",
    "Vmess.txt"
]
OUTPUT_DIR = "tested"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "config_test.txt")
MAX_SUCCESSFUL_CONFIGS = 20
MAX_CONFIGS_TO_TEST = 100
TIMEOUT = 1

# Create output directory
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Clean previous results
for file in os.listdir(OUTPUT_DIR):
    file_path = os.path.join(OUTPUT_DIR, file)
    if os.path.isfile(file_path):
        os.remove(file_path)


def clean_config_link(config):
    protocol_match = re.match(r"^(vless|trojan|ss|hysteria2|vmess)://", config)
    if not protocol_match:
        print(f"Error: Invalid protocol in link: {config[:50]}...")
        return config
    
    protocol = protocol_match.group(1)
    
    if protocol == "vmess":
        try:
            vmess_match = re.match(r"vmess://([A-Za-z0-9+/=]+)", config)
            if vmess_match:
                encoded_data = vmess_match.group(1)
                padding_needed = len(encoded_data) % 4
                if padding_needed:
                    encoded_data += '=' * (4 - padding_needed)
                decoded_json = base64.b64decode(encoded_data).decode('utf-8')
                vmess_obj = json.loads(decoded_json)
                vmess_obj['ps'] = f"server-{random.randint(1, 1000)}"
                cleaned_json = json.dumps(vmess_obj)
                cleaned_encoded = base64.b64encode(cleaned_json.encode('utf-8')).decode('utf-8')
                return f"vmess://{cleaned_encoded}"
        except (binascii.Error, json.JSONDecodeError, ValueError):
            print(f"Error decoding VMess: {config[:50]}...")
            return config.split("#")[0]
    else:
        cleaned = config.split("#")[0]
        if protocol == "trojan":
            if not re.search(r"(security|type|sni)=[^&]+", cleaned):
                print(f"Warning: Incomplete Trojan link: {cleaned[:50]}...")
        return cleaned


def get_protocol(config):
    protocol_match = re.match(r"^(vless|trojan|ss|hysteria2|vmess)://", config)
    return protocol_match.group(1).lower() if protocol_match else "unknown"


def extract_host_port(config):
    try:
        # Hysteria2
        if config.startswith(("hy2://", "hysteria2://")):
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", config)
            if match:
                host = match.group(1).strip("[]")
                port = int(match.group(2))
                return host, port

        # Shadowsocks (base64 + plain)
        if config.startswith("ss://"):
            # base64 encoded part
            try:
                b64_part = config[5:].split("#")[0].split("/")[0]
                padding = len(b64_part) % 4
                if padding:
                    b64_part += "=" * (4 - padding)
                decoded = base64.b64decode(b64_part).decode("utf-8")
                match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", decoded)
                if match:
                    host = match.group(1).strip("[]")
                    port = int(match.group(2))
                    return host, port
            except:
                pass

            # Plain ss://method:pass@host:port
            match = re.search(r"@\[?([^\]:]+)\]?:(\d+)", config)
            if match:
                host = match.group(1).strip("[]")
                port = int(match.group(2))
                return host, port

        # Vless / Trojan
        for pattern in [
            r"(vless|trojan)://.+?@\[?([^\]:]+)\]?:(\d+)",
            r"(vless|trojan)://\[?([^\]:]+)\]?:(\d+)"
        ]:
            match = re.search(pattern, config)
            if match:
                host = match.group(2 if len(match.groups()) > 1 else 1)
                port = int(match.group(3 if len(match.groups()) > 2 else 2))
                return host.strip("[]"), port

        # Vmess
        vmess_pattern = r"vmess://([A-Za-z0-9+/=]+)"
        vmess_match = re.match(vmess_pattern, config)
        if vmess_match:
            try:
                encoded_data = vmess_match.group(1)
                padding_needed = len(encoded_data) % 4
                if padding_needed:
                    encoded_data += "=" * (4 - padding_needed)
                decoded_json = base64.b64decode(encoded_data).decode("utf-8")
                vmess_obj = json.loads(decoded_json)
                host = vmess_obj.get("add") or vmess_obj.get("host")
                port = vmess_obj.get("port")
                if host and port:
                    return str(host).strip("[]"), int(port)
            except (binascii.Error, json.JSONDecodeError, ValueError) as e:
                print(f"Error decoding VMess: {e} - {config[:50]}...")
                return None, None

        print(f"Error: Invalid link or unsupported protocol: {config[:80]}...")
        return None, None

    except Exception as e:
        print(f"Error extracting host/port: {e} | Link: {config[:60]}...")
        return None, None


def test_connection_and_ping(config, timeout=TIMEOUT):
    host, port = extract_host_port(config)
    if not host or not port or not (0 <= port <= 65535):
        return None
    
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            ping_time = (time.time() - start_time) * 1000
            return {
                "config": config,
                "host": host,
                "port": port,
                "ping": ping_time,
                "protocol": get_protocol(config)
            }
        return None
    except Exception:
        return None

current_date_time = jdatetime.datetime.now(pytz.timezone('Asia/Tehran'))
final_string = current_date_time.strftime("%b-%d | %H:%M")

all_successful_configs = []

for protocol_file in PROTOCOL_FILES:
    file_path = os.path.join(PROTOCOL_DIR, protocol_file)
    
    config_links = []
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            config_links = [line.strip() for line in f if line.strip()]
    
    if len(config_links) > MAX_CONFIGS_TO_TEST:
        config_links = random.sample(config_links, MAX_CONFIGS_TO_TEST)
    
    print(f"Testing {len(config_links)} configs from {protocol_file} ...")
    
    configs_with_ping = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_config = {executor.submit(test_connection_and_ping, config): config for config in config_links}
        for future in as_completed(future_to_config):
            result = future.result()
            if result and len(configs_with_ping) < MAX_SUCCESSFUL_CONFIGS:
                configs_with_ping.append(result)
    
    configs_with_ping.sort(key=lambda x: x["ping"])
    successful_configs = configs_with_ping[:MAX_SUCCESSFUL_CONFIGS]
    all_successful_configs.extend(successful_configs)
  

if all_successful_configs:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(f"#🌐 Updated at {final_string} | MTSRVRS\n")
        for i, result in enumerate(all_successful_configs, 1):
            cleaned_config = clean_config_link(result['config'])
            config_string = f"#🌐server {i} | {result['protocol']} | {final_string} | Ping: {result['ping']:.2f}ms"
            file.write(f"{cleaned_config}{config_string}\n")
    print(f"✅ All results saved to {OUTPUT_FILE}")
else:
    print("❌ No successful configs found.")
