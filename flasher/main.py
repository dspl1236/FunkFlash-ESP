#!/usr/bin/env python3
"""
FunkFlash-ESP — Cross-platform ESP32 firmware flasher
Hardware: Regular ESP32 (38-pin DevKit) + TJA1051T + MCP2515 CAN module

Flashes esp32-isotp-ble-bridge-c7vag firmware variants:
  BLE      — Bluetooth LE bridge to simos-suite / VAG-CP PWA
  WiFi AP  — Captive portal, access at 192.168.4.1
  WiFi STA — Joins existing network, access at funkbridge.local
"""
import sys
import os
import threading
import pathlib
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk

# Resolve firmware directory (works both as script and frozen EXE)
if getattr(sys, "frozen", False):
    BASE_DIR = pathlib.Path(sys._MEIPASS)
else:
    BASE_DIR = pathlib.Path(__file__).parent

FIRMWARE_DIR = BASE_DIR / "firmware"

FLASH_TARGETS = {
    "BLE": {
        "label": "BLE (Bluetooth — simos-suite / phone)",
        "desc":  "Bluetooth LE bridge. Pairs with simos-suite on PC or VAG-CP PWA on phone. "
                 "Dual-CAN: TWAI (Drive Train 500k) + MCP2515 (Convenience CAN 100k).",
        "bins":  [
            (0x1000,  "bootloader.bin"),
            (0x8000,  "partition-table.bin"),
            (0x10000, "funkbridge-ble.bin"),
        ],
        "spiffs": None,
    },
    "WiFi AP": {
        "label": "WiFi AP (instant bench — no router needed)",
        "desc":  "Creates \'FunkBridge\' WiFi hotspot. Connect phone/laptop to it, "
                 "browser opens VAG-CP Tool automatically at 192.168.4.1.",
        "bins":  [
            (0x1000,  "bootloader.bin"),
            (0x8000,  "partition-table.bin"),
            (0x10000, "funkbridge-ap.bin"),
        ],
        "spiffs": (0xD0000, "funkbridge-spiffs.bin"),
    },
    "WiFi STA": {
        "label": "WiFi Station (join your network)",
        "desc":  "Joins your home/shop WiFi. Access VAG-CP Tool from any device at "
                 "http://funkbridge.local — falls back to AP if network unavailable.",
        "bins":  [
            (0x1000,  "bootloader.bin"),
            (0x8000,  "partition-table.bin"),
            (0x10000, "funkbridge-sta.bin"),
        ],
        "spiffs": (0xD0000, "funkbridge-spiffs.bin"),
    },
}

PAL = {
    "bg":      "#07090a",
    "surface": "#0d1214",
    "border":  "#1a2a1a",
    "green":   "#00e676",
    "amber":   "#ffb300",
    "red":     "#ff1744",
    "blue":    "#00b0ff",
    "dim":     "#3a4a3a",
    "text":    "#c8d8c8",
}


class FunkFlashApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FunkFlash-ESP  v2")
        self.configure(bg=PAL["bg"])
        self.resizable(False, False)
        self.geometry("540x620")

        self._mode_var = tk.StringVar(value="BLE")
        self._port_var = tk.StringVar(value="")
        self._ssid_var = tk.StringVar()
        self._pass_var = tk.StringVar()
        self._progress = tk.DoubleVar(value=0)
        self._status   = tk.StringVar(value="Ready — plug in ESP32 via USB")

        self._build_ui()
        self._scan_ports()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        mono  = ("Courier New", 10)
        large = ("Courier New", 14)

        # Header
        hdr = tk.Frame(self, bg=PAL["surface"],
                       highlightbackground=PAL["border"], highlightthickness=1)
        hdr.pack(fill="x")
        tk.Label(hdr, text="FUNK", bg=PAL["surface"], fg=PAL["green"],
                 font=("Arial Narrow", 28, "bold")).pack(side="left", padx=(16,0), pady=10)
        tk.Label(hdr, text="FLASH", bg=PAL["surface"], fg=PAL["dim"],
                 font=("Arial Narrow", 28, "bold")).pack(side="left")
        tk.Label(hdr, text="-ESP  v2", bg=PAL["surface"], fg=PAL["dim"],
                 font=("Arial Narrow", 15)).pack(side="left", pady=10)
        tk.Label(hdr, text="ESP32 + TJA1051T + MCP2515",
                 bg=PAL["surface"], fg=PAL["dim"],
                 font=("Courier New", 8)).pack(side="right", padx=14)

        body = tk.Frame(self, bg=PAL["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Device
        self._section(body, "DEVICE")
        port_row = tk.Frame(body, bg=PAL["bg"])
        port_row.pack(fill="x", pady=(0,6))
        self._port_menu = ttk.Combobox(port_row, textvariable=self._port_var,
                                        state="readonly", width=30, font=mono)
        self._port_menu.pack(side="left")
        self._btn(port_row, "⟳ SCAN", self._scan_ports, "green").pack(
            side="left", padx=(8,0))
        self._dev_lbl = tk.Label(body, text="plug in ESP32 via USB-C",
                                  bg=PAL["bg"], fg=PAL["dim"], font=mono)
        self._dev_lbl.pack(anchor="w")

        # Mode
        self._section(body, "FIRMWARE MODE")
        for key, info in FLASH_TARGETS.items():
            row = tk.Frame(body, bg=PAL["bg"])
            row.pack(fill="x", pady=1)
            tk.Radiobutton(row, text=info["label"],
                           variable=self._mode_var, value=key,
                           bg=PAL["bg"], fg=PAL["text"],
                           selectcolor=PAL["surface"],
                           activebackground=PAL["bg"],
                           activeforeground=PAL["green"],
                           font=mono, command=self._on_mode_change).pack(side="left")
        self._desc_lbl = tk.Label(body, text=FLASH_TARGETS["BLE"]["desc"],
                                   bg=PAL["bg"], fg=PAL["dim"],
                                   font=("Courier New", 9),
                                   wraplength=500, justify="left")
        self._desc_lbl.pack(anchor="w", pady=(4,0))

        # WiFi STA credentials
        self._sta_frame = tk.Frame(body, bg=PAL["bg"])
        for row_idx, (lbl, var, show) in enumerate([
            ("SSID",     self._ssid_var, ""),
            ("Password", self._pass_var, "•"),
        ]):
            tk.Label(self._sta_frame, text=lbl, bg=PAL["bg"], fg=PAL["dim"],
                     font=mono, width=10, anchor="w").grid(
                     row=row_idx, column=0, sticky="w", pady=2)
            tk.Entry(self._sta_frame, textvariable=var, font=mono,
                     bg=PAL["surface"], fg=PAL["text"],
                     insertbackground=PAL["green"],
                     relief="flat", width=34, show=show).grid(
                     row=row_idx, column=1, sticky="ew")

        # Progress
        self._section(body, "PROGRESS")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Funk.Horizontal.TProgressbar",
                         troughcolor=PAL["surface"],
                         background=PAL["green"], thickness=14)
        ttk.Progressbar(body, variable=self._progress,
                        maximum=100,
                        style="Funk.Horizontal.TProgressbar").pack(
                        fill="x", pady=(0,5))
        self._status_lbl = tk.Label(body, textvariable=self._status,
                                     bg=PAL["bg"], fg=PAL["dim"], font=mono)
        self._status_lbl.pack(anchor="w")

        # Log
        self._section(body, "LOG")
        log_frame = tk.Frame(body, bg=PAL["surface"],
                              highlightbackground=PAL["border"], highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(0,8))
        self._log = tk.Text(log_frame, bg=PAL["surface"], fg=PAL["dim"],
                             font=("Courier New", 9), height=6,
                             relief="flat", wrap="word", state="disabled")
        self._log.pack(fill="both", expand=True, padx=6, pady=4)
        self._log.tag_config("ok",  foreground=PAL["green"])
        self._log.tag_config("err", foreground=PAL["red"])
        self._log.tag_config("warn",foreground=PAL["amber"])

        # Flash button
        self._flash_btn = self._btn(body, "⚡  FLASH FIRMWARE",
                                    self._do_flash, "green", large=True)
        self._flash_btn.pack(fill="x", ipady=10)

        tk.Label(self, text="github.com/dspl1236/FunkFlash-ESP  ·  GPL v3",
                 bg=PAL["bg"], fg=PAL["dim"],
                 font=("Courier New", 8)).pack(pady=(0,6))

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=PAL["bg"])
        f.pack(fill="x", pady=(10,4))
        tk.Label(f, text=text, bg=PAL["bg"], fg=PAL["dim"],
                 font=("Arial Narrow", 9, "bold")).pack(side="left")
        tk.Frame(f, bg=PAL["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _btn(self, parent, text, cmd, color="text", large=False):
        sz = 13 if not large else 15
        return tk.Button(parent, text=text, command=cmd,
                         bg=PAL["bg"], fg=PAL[color],
                         activebackground=PAL["surface"],
                         activeforeground=PAL[color],
                         relief="solid", bd=1,
                         font=("Courier New", sz),
                         cursor="hand2",
                         highlightbackground=PAL[color],
                         highlightthickness=1)

    def _scan_ports(self):
        ports = serial.tools.list_ports.comports()
        esp = [p for p in ports
               if (p.vid in (0x10C4, 0x1A86) or
                   any(k in (p.description or "") for k in
                       ("CP210", "CH340", "CH341", "Silicon", "USB Serial")))]
        all_ports = esp or ports
        names = [f"{p.device}  ({p.description or 'unknown'})" for p in all_ports]
        self._port_menu["values"] = names
        if esp:
            self._port_var.set(names[0])
            self._dev_lbl.config(text=f"✓ Found: {esp[0].description}", fg=PAL["green"])
        elif ports:
            self._port_var.set(names[0])
            self._dev_lbl.config(text="No ESP32 detected — select port manually",
                                  fg=PAL["amber"])
        else:
            self._dev_lbl.config(text="No serial ports found", fg=PAL["red"])

    def _on_mode_change(self):
        mode = self._mode_var.get()
        self._desc_lbl.config(text=FLASH_TARGETS[mode]["desc"])
        if mode == "WiFi STA":
            self._sta_frame.pack(fill="x", pady=(4,0))
        else:
            self._sta_frame.pack_forget()

    def _log_msg(self, msg, tag=""):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _set_status(self, msg, color="text"):
        self._status.set(msg)
        self._status_lbl.config(fg=PAL.get(color, PAL["text"]))

    def _do_flash(self):
        port_str = self._port_var.get()
        if not port_str:
            self._log_msg("No port selected", "err"); return
        port = port_str.split()[0]
        mode = self._mode_var.get()
        spiffs = FLASH_TARGETS[mode].get("spiffs")
        all_bins = list(FLASH_TARGETS[mode]["bins"]) + ([spiffs] if spiffs else [])

        missing = [fname for _, fname in all_bins
                   if not (FIRMWARE_DIR / fname).exists() or
                   (FIRMWARE_DIR / fname).read_bytes() == b"PLACEHOLDER"]
        if missing:
            self._log_msg(f"Missing firmware: {missing}", "err")
            self._log_msg("Download a release or run fetch_firmware.py", "warn")
            return

        # Verify firmware integrity against checksums if available
        checksums_file = FIRMWARE_DIR / "checksums.json"
        if checksums_file.exists():
            import json, hashlib
            expected = json.loads(checksums_file.read_text())
            for _, fname in all_bins:
                if fname in expected:
                    actual = hashlib.sha256((FIRMWARE_DIR / fname).read_bytes()).hexdigest()
                    if actual != expected[fname]:
                        self._log_msg(f"CHECKSUM MISMATCH: {fname}", "err")
                        self._log_msg("Re-download firmware or run fetch_firmware.py", "err")
                        return

        if mode == "WiFi STA" and not self._ssid_var.get().strip():
            self._log_msg("WiFi Station requires an SSID", "err"); return

        self._flash_btn.config(state="disabled")
        self._progress.set(0)
        threading.Thread(target=self._flash_thread,
                         args=(port, mode, all_bins), daemon=True).start()

    def _flash_thread(self, port, mode, targets):
        try:
            import esptool
        except ImportError:
            self.after(0, self._log_msg, "esptool not installed — pip install esptool", "err")
            self.after(0, self._flash_btn.config, {"state": "normal"})
            return

        self.after(0, self._set_status, "Connecting to ESP32...", "amber")
        self.after(0, self._log_msg, f"Port: {port}  Mode: {mode}")

        # --chip auto detects regular ESP32, S2, S3, C3 automatically
        args = ["--chip", "auto", "--port", port, "--baud", "460800",
                "--before", "default_reset", "--after", "hard_reset",
                "write_flash", "--flash_mode", "dio",
                "--flash_freq", "40m", "--flash_size", "detect"]
        for addr, fname in targets:
            args += [str(hex(addr)), str(FIRMWARE_DIR / fname)]

        # Write WiFi credentials via NVS for STA mode
        if mode == "WiFi STA":
            ssid = self._ssid_var.get().strip()
            pwd  = self._pass_var.get().strip()
            if ssid:
                self.after(0, self._log_msg, f"WiFi: SSID={ssid}")
                import tempfile, os
                nvs_csv = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
                nvs_csv.write("key,type,encoding,value\n")
                nvs_csv.write("wifi_mode,data,u8,2\n")
                nvs_csv.write(f"wifi_ssid,data,string,{ssid}\n")
                nvs_csv.write(f"wifi_pass,data,string,{pwd}\n")
                nvs_csv.close()
                nvs_bin = nvs_csv.name.replace(".csv", ".bin")
                try:
                    import nvs_flash_gen
                    nvs_flash_gen.main(["generate", nvs_csv.name, nvs_bin, "0x6000"])
                    args += [str(hex(0x9000)), nvs_bin]
                    self.after(0, self._log_msg, "NVS credentials prepared", "ok")
                except Exception as e:
                    self.after(0, self._log_msg, f"NVS gen note: {e}", "warn")
                finally:
                    os.unlink(nvs_csv.name)
                    # Clean up NVS bin (contains plaintext credentials)
                    if os.path.exists(nvs_bin):
                        os.unlink(nvs_bin)

        class ProgressCapture:
            def __init__(self, app, total):
                self.app = app; self.total = total
                self.step = 0; self._buf = ""
            def write(self, s):
                self._buf += s
                if "%" in s:
                    import re
                    m = re.search(r"(\d+)\s*%", s)
                    if m:
                        pct = int(m.group(1))
                        self.app.after(0, self.app._progress.set,
                                       (self.step / self.total * 100) +
                                       (1 / self.total * pct))
                if "\n" in s:
                    line = self._buf.strip()
                    if line:
                        tag = "ok" if "Hash of data" in line else ""
                        self.app.after(0, self.app._log_msg, line, tag)
                    self._buf = ""
            def flush(self): pass

        cap = ProgressCapture(self, len(targets))
        old_out = sys.stdout; sys.stdout = cap
        try:
            esptool.main(args)
            self.after(0, self._progress.set, 100)
            self.after(0, self._set_status, f"✓ Flashed {mode} successfully!", "green")
            self.after(0, self._log_msg, "Flash complete!", "ok")
            if mode in ("WiFi AP", "WiFi STA"):
                self.after(0, self._log_msg, "SPIFFS web app ready", "ok")
            if mode == "WiFi AP":
                self.after(0, self._log_msg,
                           "Connect to 'FunkBridge' WiFi (password: FunkBridge1) → browser auto-opens", "ok")
            elif mode == "WiFi STA":
                self.after(0, self._log_msg,
                           "Join your WiFi → open http://funkbridge.local", "ok")
            else:
                self.after(0, self._log_msg,
                           "BLE ready — scan for BLE_TO_ISOTP20 in simos-suite", "ok")
        except SystemExit as e:
            if e.code == 0:
                self.after(0, self._progress.set, 100)
                self.after(0, self._set_status, "✓ Flash complete", "green")
            else:
                self.after(0, self._set_status, "✗ Flash failed", "red")
                self.after(0, self._log_msg,
                           "Failed — check port, hold BOOT button during connect", "err")
        except Exception as e:
            self.after(0, self._set_status, f"Error: {e}", "red")
            self.after(0, self._log_msg, str(e), "err")
        finally:
            sys.stdout = old_out
            self.after(0, self._flash_btn.config, {"state": "normal"})


if __name__ == "__main__":
    app = FunkFlashApp()
    app.mainloop()
