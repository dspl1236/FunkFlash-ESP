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

import hashlib

checksums = {}
for name in WANTED:
    if name in assets:
        url = assets[name]
        # Validate download URL points to GitHub
        if not (url.startswith("https://github.com/") or
                url.startswith("https://objects.githubusercontent.com/")):
            print(f"  {name}: SKIPPED — untrusted download URL: {url}")
            continue
        print(f"  Downloading {name}...")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.content
        # Validate bootloader magic byte
        if name == "bootloader.bin" and len(data) > 0 and data[0] != 0xE9:
            print(f"  WARNING: {name} missing ESP32 magic byte (0xE9) — may be corrupt")
        (OUT_DIR / name).write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        checksums[name] = sha
        print(f"  {name}: {len(data):,} bytes  SHA256: {sha[:16]}...")
    else:
        print(f"  {name}: not in release (placeholder)")
        p = OUT_DIR / name
        if not p.exists():
            p.write_bytes(b"PLACEHOLDER")

# Write checksums file for flasher verification
import json
(OUT_DIR / "checksums.json").write_text(json.dumps(checksums, indent=2))
print(f"Wrote checksums.json ({len(checksums)} files)")
print("Done.")
