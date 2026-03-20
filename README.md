# FunkFlash-ESP

**Cross-platform firmware flasher for the [esp32-isotp-ble-bridge-c7vag](https://github.com/dspl1236/esp32-isotp-ble-bridge-c7vag) ESP32 ISO-TP CAN bridge.**

One click. No Python. No ESP-IDF. No command line.

[![Build FunkFlash-ESP](https://github.com/dspl1236/FunkFlash-ESP/actions/workflows/build-flasher.yml/badge.svg)](https://github.com/dspl1236/FunkFlash-ESP/actions/workflows/build-flasher.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

---

## Download

Go to [Releases](https://github.com/dspl1236/FunkFlash-ESP/releases/latest) and download for your platform:

| Platform | File |
|----------|------|
| Windows  | `FunkFlash-ESP-Windows.exe` |
| macOS    | `FunkFlash-ESP-macOS` |
| Linux    | `FunkFlash-ESP-Linux` |

---

## What it does

FunkFlash-ESP flashes three firmware modes onto your ESP32 OBD bridge:

### BLE mode
The ESP32 advertises as `BLE_TO_ISOTP20` over Bluetooth.  
Use with:
- [simos-suite](https://github.com/dspl1236/simos-suite) desktop diagnostic tool
- [VAG-CP PWA](https://dspl1236.github.io/VAG-CP-Docs/) — phone-based IKA key reader

### WiFi AP mode — instant bench use
The ESP32 creates a **FunkBridge** WiFi access point (no password).  
Connect your phone or laptop to it — a browser opens automatically via captive portal.  
The diagnostic web app loads at `http://192.168.4.1` or `http://funkbridge.local`.  
**No setup. No typing URLs. Just connect.**

### WiFi Station mode — shop/bench integration
The ESP32 joins your existing WiFi network.  
Access from any device on the network at `http://funkbridge.local`.  
Enter your WiFi credentials in FunkFlash-ESP before flashing.  
Falls back to AP mode automatically if the network is unavailable.

---

## Hardware

Designed for the **ESP32 A0 OBD-II bridge** (Switchleg1 hardware).  
Compatible with any ESP32 board with:
- TWAI (CAN) controller wired to the OBD port
- CP210x or CH340 USB-UART bridge
- 4MB flash

Plug in via USB-C, select your mode, click Flash.

---

## How it works

```
┌──────────────────────────────────────────┐
│  FunkFlash-ESP                           │
│                                          │
│  Device:  COM4 — CP210x USB to UART  ⟳  │
│  Current: v1.1.0-BLE                     │
│                                          │
│  Firmware mode:                          │
│  ◉ BLE          mobile / Bluetooth       │
│  ○ WiFi AP      instant bench            │
│  ○ WiFi Station join your network        │
│                                          │
│  [████████████░░░░] 72%                 │
│                                          │
│  ⚡  FLASH FIRMWARE                      │
└──────────────────────────────────────────┘
```

FunkFlash-ESP bundles `esptool.py` — Espressif's official flash tool — so no
separate installation is needed. It auto-detects your ESP32 serial port,
shows current firmware version, and flashes all three binary files
(bootloader + partition table + application) in one operation.

---

## WiFi architecture

### AP mode (captive portal)
```
Your device connects to "FunkBridge" (open WiFi)
    ↓
DNS server on ESP32 catches all queries → 192.168.4.1
    ↓
Browser auto-opens (Android notification / iOS auto-redirect / Windows prompt)
    ↓
Diagnostic web app loads from ESP32 SPIFFS filesystem
    ↓
WebSocket ws://192.168.4.1/ws bridges to CAN bus
```

### Station mode
```
ESP32 joins your WiFi network
    ↓
mDNS announces "funkbridge.local"
    ↓
Any device on network: http://funkbridge.local
    ↓
WebSocket ws://funkbridge.local/ws bridges to CAN bus
```

The WebSocket frame format is **identical to the BLE protocol** —
the same web app works over both BLE and WiFi without any changes.

---

## Build from source

```bash
git clone https://github.com/dspl1236/FunkFlash-ESP
cd FunkFlash-ESP/flasher
pip install -r requirements.txt
python fetch_firmware.py        # downloads latest .bin files
pyinstaller FunkFlash-ESP.spec  # builds standalone executable
```

---

## Firmware source

The firmware flashed by FunkFlash-ESP lives at:  
[dspl1236/esp32-isotp-ble-bridge-c7vag](https://github.com/dspl1236/esp32-isotp-ble-bridge-c7vag)

Forked from [Switchleg1/esp32-isotp-ble-bridge](https://github.com/Switchleg1/esp32-isotp-ble-bridge)  
with additions:
- Raw CAN sniff mode (`BRG_SETTING_RAW_SNIFF`)
- WiFi AP + Station mode with captive portal
- mDNS `funkbridge.local`
- SPIFFS web app hosting
- Version string (`FUNKBRIDGE_VERSION`)

---

## Related projects

- **[simos-suite](https://github.com/dspl1236/simos-suite)** — Desktop ECU diagnostic tool (Simos8.5, C7 A6/A7)
- **[VAG-CP-Docs](https://github.com/dspl1236/VAG-CP-Docs)** — Component Protection research documentation
- **[VAG-CP PWA](https://dspl1236.github.io/VAG-CP-Docs/)** — Browser-based diagnostic tool (phone friendly)

---

## License

GPL v3 — see [LICENSE](LICENSE)

This software is provided for vehicle owners, independent repair shops, and
right-to-repair advocates. It is not affiliated with Volkswagen AG or any
VAG brand.
