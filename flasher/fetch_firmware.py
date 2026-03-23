#!/usr/bin/env python3
"""
fetch_firmware.py — Downloads latest firmware from esp32-isotp-ble-bridge-c7vag releases.
Run before PyInstaller build to populate flasher/firmware/.
"""
import requests, pathlib, sys

REPO    = "dspl1236/esp32-isotp-ble-bridge-c7vag"
API     = f"https://api.github.com/repos/{REPO}/releases/latest"
OUT_DIR = pathlib.Path(__file__).parent / "firmware"
OUT_DIR.mkdir(exist_ok=True)

WANTED = [
    "bootloader.bin",
    "partition-table.bin",
    "funkbridge-ble.bin",          # BLE bridge firmware
    "funkbridge-ap.bin",           # WiFi AP firmware
    "funkbridge-sta.bin",          # WiFi STA firmware
    "funkbridge-spiffs.bin",       # Web app SPIFFS image (WiFi modes)
]

print(f"Fetching latest release from {REPO}...")
r = requests.get(API, timeout=30)
if r.status_code == 404:
    print("No release yet — creating placeholder binaries")
    for name in WANTED:
        p = OUT_DIR / name
        if not p.exists():
            p.write_bytes(b"PLACEHOLDER")
    sys.exit(0)

rel = r.json()
print(f"Latest release: {rel.get('tag_name', '?')}")
assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}

for name in WANTED:
    if name in assets:
        print(f"  Downloading {name}...")
        data = requests.get(assets[name], timeout=60).content
        (OUT_DIR / name).write_bytes(data)
        print(f"  {name}: {len(data):,} bytes")
    else:
        print(f"  {name}: not in release (placeholder)")
        p = OUT_DIR / name
        if not p.exists():
            p.write_bytes(b"PLACEHOLDER")

print("Done.")
