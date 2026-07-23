#!/usr/bin/env python3
import base64
import subprocess
from pathlib import Path

print("=== V2RAY TEST RUNNER STARTED ===")

# دانلود و decode ساب
raw_url = "https://raw.githubusercontent.com/Argh73/VpnConfigCollector/refs/heads/main/All_Configs_Sub.txt"
print(f"Downloading from: {raw_url}")

import requests
resp = requests.get(raw_url, timeout=30)
content = resp.text.strip()

# اگر Base64 باشه decode کن
if not content.startswith("vmess://") and not content.startswith("vless://"):
    try:
        decoded = base64.b64decode(content + "==").decode('utf-8')
        configs = [line.strip() for line in decoded.splitlines() if line.strip()]
        print(f"Decoded Base64 → {len(configs)} configs")
    except:
        configs = [line.strip() for line in content.splitlines() if line.strip()]
else:
    configs = [line.strip() for line in content.splitlines() if line.strip()]

# ذخیره configs
with open("configs.txt", "w") as f:
    for c in configs[:1000]:   # حداکثر ۵۰۰۰ تا
        f.write(c + "\n")

print(f"Total configs saved: {len(configs)}")

# اجرا
print("Running bulk tester on configs.txt...")
subprocess.run([
    "python", "v2ray-bulk-tester.py",
    "-i", "configs.txt",
    "-o", "Test.txt",
    "-c", "20"
], timeout=1800)

print("Runner finished.")
