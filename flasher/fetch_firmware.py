#!/usr/bin/env python3
"""
fetch_firmware.py — Downloads latest firmware .bin files from ESP32 fork releases.
Run before PyInstaller build. Saves to flasher/firmware/.
"""
import requests, pathlib, sys

REPO    = "dspl1236/esp32-isotp-ble-bridge-c7vag"
API     = f"https://api.github.com/repos/{REPO}/releases/latest"
OUT_DIR = pathlib.Path(__file__).parent / "firmware"
OUT_DIR.mkdir(exist_ok=True)

print(f"Fetching latest release from {REPO}...")
r = requests.get(API, timeout=30)
if r.status_code == 404:
    print("No release yet — using placeholder binaries")
    # Create empty placeholder files so PyInstaller doesn't fail
    for name in ["funkbridge-ble.bin", "funkbridge-ap.bin",
                 "funkbridge-sta.bin", "bootloader.bin",
                 "partition-table.bin"]:
        p = OUT_DIR / name
        if not p.exists():
            p.write_bytes(b"PLACEHOLDER")
    sys.exit(0)

rel = r.json()
print(f"Latest release: {rel.get('tag_name','?')}")
assets = {a['name']: a['browser_download_url'] for a in rel.get('assets', [])}

wanted = [
    "funkbridge-ble.bin",
    "funkbridge-ap.bin",
    "funkbridge-sta.bin",
    "bootloader.bin",
    "partition-table.bin",
]
for name in wanted:
    if name in assets:
        print(f"  Downloading {name}...")
        data = requests.get(assets[name], timeout=60).content
        (OUT_DIR / name).write_bytes(data)
        print(f"  Saved {len(data):,} bytes")
    else:
        print(f"  {name}: not in release (using placeholder)")
        p = OUT_DIR / name
        if not p.exists():
            p.write_bytes(b"PLACEHOLDER")

print("Done.")
