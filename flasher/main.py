#!/usr/bin/env python3
"""
FunkFlash-ESP — Cross-platform ESP32 firmware flasher
Flashes esp32-isotp-ble-bridge-c7vag firmware (BLE / WiFi AP / WiFi Station)

Usage: run the executable, select mode, click Flash.
"""
import sys
import os
import threading
import pathlib
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, font as tkfont

# Resolve firmware directory (works both as script and frozen EXE)
if getattr(sys, "frozen", False):
    BASE_DIR = pathlib.Path(sys._MEIPASS)
else:
    BASE_DIR = pathlib.Path(__file__).parent

FIRMWARE_DIR = BASE_DIR / "firmware"

FLASH_TARGETS = {
    "BLE":     {"label": "BLE (mobile / Bluetooth)",
                "desc":  "Pairs with phone via Bluetooth. Use with simos-suite and VAG-CP PWA.",
                "bins":  [
                    (0x1000,  "bootloader.bin"),
                    (0x8000,  "partition-table.bin"),
                    (0x10000, "funkbridge-ble.bin"),
                ]},
    "WiFi AP":  {"label": "WiFi AP (instant bench — captive portal)",
                 "desc":  "Creates FunkBridge network. Any device connects and browser opens automatically.",
                 "bins":  [
                    (0x1000,  "bootloader.bin"),
                    (0x8000,  "partition-table.bin"),
                    (0x10000, "funkbridge-ap.bin"),
                 ]},
    "WiFi STA": {"label": "WiFi Station (join your network)",
                 "desc":  "Joins your existing WiFi. Access at http://funkbridge.local from any device.",
                 "bins":  [
                    (0x1000,  "bootloader.bin"),
                    (0x8000,  "partition-table.bin"),
                    (0x10000, "funkbridge-sta.bin"),
                 ]},
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
        self.title("FunkFlash-ESP")
        self.configure(bg=PAL["bg"])
        self.resizable(False, False)
        self.geometry("520x600")

        self._mode_var = tk.StringVar(value="BLE")
        self._port_var = tk.StringVar(value="")
        self._ssid_var = tk.StringVar()
        self._pass_var = tk.StringVar()
        self._progress = tk.DoubleVar(value=0)
        self._status   = tk.StringVar(value="Ready")

        self._build_ui()
        self._scan_ports()

    # ── Build UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        mono  = ("Courier New", 10)
        head  = ("Arial Narrow", 12, "bold")
        large = ("Arial Narrow", 22, "bold")

        # Header
        hdr = tk.Frame(self, bg=PAL["surface"],
                       highlightbackground=PAL["border"], highlightthickness=1)
        hdr.pack(fill="x")
        tk.Label(hdr, text="FUNK", bg=PAL["surface"], fg=PAL["green"],
                 font=("Arial Narrow", 26, "bold")).pack(side="left", padx=(16,0), pady=10)
        tk.Label(hdr, text="FLASH", bg=PAL["surface"], fg=PAL["dim"],
                 font=("Arial Narrow", 26, "bold")).pack(side="left")
        tk.Label(hdr, text="-ESP", bg=PAL["surface"], fg=PAL["dim"],
                 font=("Arial Narrow", 14)).pack(side="left", pady=10)

        body = tk.Frame(self, bg=PAL["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Device detection
        self._section(body, "DEVICE")
        port_row = tk.Frame(body, bg=PAL["bg"])
        port_row.pack(fill="x", pady=(0,8))
        self._port_menu = ttk.Combobox(port_row, textvariable=self._port_var,
                                        state="readonly", width=28,
                                        font=mono)
        self._port_menu.pack(side="left")
        self._btn(port_row, "⟳ SCAN", self._scan_ports, "green").pack(
            side="left", padx=(8,0))
        self._dev_lbl = tk.Label(body, text="plug in ESP32 via USB-C",
                                  bg=PAL["bg"], fg=PAL["dim"], font=mono)
        self._dev_lbl.pack(anchor="w")

        # Mode selection
        self._section(body, "FIRMWARE MODE")
        for key, info in FLASH_TARGETS.items():
            row = tk.Frame(body, bg=PAL["bg"])
            row.pack(fill="x", pady=1)
            rb = tk.Radiobutton(row, text=info["label"],
                                 variable=self._mode_var, value=key,
                                 bg=PAL["bg"], fg=PAL["text"],
                                 selectcolor=PAL["surface"],
                                 activebackground=PAL["bg"],
                                 activeforeground=PAL["green"],
                                 font=mono, command=self._on_mode_change)
            rb.pack(side="left")
        self._desc_lbl = tk.Label(body, text=FLASH_TARGETS["BLE"]["desc"],
                                   bg=PAL["bg"], fg=PAL["dim"],
                                   font=("Courier New", 9),
                                   wraplength=480, justify="left")
        self._desc_lbl.pack(anchor="w", pady=(4,0))

        # WiFi credentials (station mode only)
        self._sta_frame = tk.Frame(body, bg=PAL["bg"])
        tk.Label(self._sta_frame, text="SSID",     bg=PAL["bg"], fg=PAL["dim"],
                 font=mono, width=10, anchor="w").grid(row=0, col=0, sticky="w", pady=2)
        tk.Entry(self._sta_frame, textvariable=self._ssid_var, font=mono,
                 bg=PAL["surface"], fg=PAL["text"], insertbackground=PAL["green"],
                 relief="flat", width=32).grid(row=0, column=1, sticky="ew")
        tk.Label(self._sta_frame, text="Password", bg=PAL["bg"], fg=PAL["dim"],
                 font=mono, width=10, anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(self._sta_frame, textvariable=self._pass_var, font=mono,
                 bg=PAL["surface"], fg=PAL["text"], insertbackground=PAL["green"],
                 relief="flat", width=32, show="•").grid(row=1, column=1, sticky="ew")

        # Progress
        self._section(body, "PROGRESS")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Funk.Horizontal.TProgressbar",
                         troughcolor=PAL["surface"],
                         background=PAL["green"],
                         thickness=14)
        self._pbar = ttk.Progressbar(body, variable=self._progress,
                                      maximum=100,
                                      style="Funk.Horizontal.TProgressbar")
        self._pbar.pack(fill="x", pady=(0,6))
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
                             relief="flat", wrap="word",
                             state="disabled")
        self._log.pack(fill="both", expand=True, padx=6, pady=4)
        self._log.tag_config("ok",   foreground=PAL["green"])
        self._log.tag_config("err",  foreground=PAL["red"])
        self._log.tag_config("warn", foreground=PAL["amber"])

        # Flash button
        self._flash_btn = self._btn(body, "⚡  FLASH FIRMWARE", self._do_flash,
                                    "green", large=True)
        self._flash_btn.pack(fill="x", ipady=10)

        # Footer
        tk.Label(self, text="github.com/dspl1236/FunkFlash-ESP  ·  GPL v3",
                 bg=PAL["bg"], fg=PAL["dim"],
                 font=("Courier New", 8)).pack(pady=(0,6))

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=PAL["bg"])
        f.pack(fill="x", pady=(10,4))
        tk.Label(f, text=text, bg=PAL["bg"], fg=PAL["dim"],
                 font=("Arial Narrow", 9, "bold"),
                 letterSpacing=3).pack(side="left")
        tk.Frame(f, bg=PAL["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _btn(self, parent, text, cmd, color="text", large=False):
        sz = 13 if not large else 15
        b = tk.Button(parent, text=text, command=cmd,
                       bg=PAL["bg"], fg=PAL[color],
                       activebackground=PAL["surface"],
                       activeforeground=PAL[color],
                       relief="solid", bd=1,
                       font=("Courier New", sz),
                       cursor="hand2",
                       highlightbackground=PAL[color],
                       highlightthickness=1)
        return b

    # ── Port scan ─────────────────────────────────────────────────────────
    def _scan_ports(self):
        ports = serial.tools.list_ports.comports()
        # Filter for CP210x or CH340 (ESP32 USB-UART bridges)
        esp_ports = [
            p for p in ports
            if (p.vid in (0x10C4, 0x1A86) or
                "CP210" in (p.description or "") or
                "CH340" in (p.description or "") or
                "Silicon" in (p.description or ""))
        ]
        all_ports = esp_ports or ports  # fallback: show all
        names = [f"{p.device}  ({p.description or 'unknown'})" for p in all_ports]
        self._port_menu["values"] = names

        if esp_ports:
            self._port_var.set(names[0])
            self._dev_lbl.config(
                text=f"✓ Found: {esp_ports[0].description}",
                fg=PAL["green"])
        elif ports:
            self._port_var.set(names[0])
            self._dev_lbl.config(text="No ESP32 detected — select port manually",
                                  fg=PAL["amber"])
        else:
            self._dev_lbl.config(text="No serial ports found",
                                  fg=PAL["red"])

    def _on_mode_change(self):
        mode = self._mode_var.get()
        self._desc_lbl.config(text=FLASH_TARGETS[mode]["desc"])
        if mode == "WiFi STA":
            self._sta_frame.pack(fill="x", pady=(4,0))
        else:
            self._sta_frame.pack_forget()

    # ── Log ───────────────────────────────────────────────────────────────
    def _log_msg(self, msg, tag=""):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _set_status(self, msg, color="text"):
        self._status.set(msg)
        self._status_lbl.config(fg=PAL.get(color, PAL["text"]))

    # ── Flash ─────────────────────────────────────────────────────────────
    def _do_flash(self):
        port_str = self._port_var.get()
        if not port_str:
            self._log_msg("No port selected", "err")
            return
        # Extract device path (everything before first space)
        port = port_str.split()[0]
        mode = self._mode_var.get()
        targets = FLASH_TARGETS[mode]["bins"]

        # Verify all bin files exist
        missing = []
        for _, fname in targets:
            p = FIRMWARE_DIR / fname
            if not p.exists() or p.read_bytes() == b"PLACEHOLDER":
                missing.append(fname)
        if missing:
            self._log_msg(f"Missing firmware: {missing}", "err")
            self._log_msg("Download a release build or run fetch_firmware.py", "warn")
            return

        self._flash_btn.config(state="disabled")
        self._progress.set(0)
        threading.Thread(target=self._flash_thread,
                         args=(port, mode, targets), daemon=True).start()

    def _flash_thread(self, port, mode, targets):
        try:
            import esptool
        except ImportError:
            self.after(0, self._log_msg, "esptool not installed", "err")
            self.after(0, self._flash_btn.config, {"state": "normal"})
            return

        self.after(0, self._set_status, "Connecting to ESP32...", "amber")
        self.after(0, self._log_msg, f"Port: {port}  Mode: {mode}")

        # Build esptool args
        args = ["--chip", "esp32", "--port", port, "--baud", "460800",
                "--before", "default_reset", "--after", "hard_reset",
                "write_flash", "--flash_mode", "dio",
                "--flash_freq", "40m", "--flash_size", "detect"]
        for addr, fname in targets:
            args += [str(hex(addr)), str(FIRMWARE_DIR / fname)]

        self.after(0, self._log_msg, f"esptool.py {" ".join(args[:6])}...")

        # Custom progress callback
        total_steps = len(targets)

        class ProgressCapture:
            def __init__(self, app, total):
                self.app   = app
                self.total = total
                self.step  = 0
                self._buf  = ""
            def write(self, s):
                self._buf += s
                if "Writing at" in s or "%" in s:
                    try:
                        import re
                        m = re.search(r"(\d+)\s*%", s)
                        if m:
                            pct = int(m.group(1))
                            base = (self.step / self.total) * 100
                            chunk = (1 / self.total) * pct
                            self.app.after(0, self.app._progress.set, base + chunk)
                    except: pass
                if "\n" in s:
                    line = self._buf.strip()
                    if line:
                        tag = "ok" if "Hash of data" in line else ""
                        self.app.after(0, self.app._log_msg, line, tag)
                    self._buf = ""
            def flush(self): pass

        cap = ProgressCapture(self, total_steps)
        old_out = sys.stdout
        sys.stdout = cap

        try:
            esptool.main(args)
            self.after(0, self._progress.set, 100)
            self.after(0, self._set_status, f"✓ Flashed {mode} firmware successfully!", "green")
            self.after(0, self._log_msg, "Flash complete!", "ok")
            if mode == "WiFi AP":
                self.after(0, self._log_msg,
                    "Connect to 'FunkBridge' WiFi → browser opens automatically", "ok")
            elif mode == "WiFi STA":
                self.after(0, self._log_msg,
                    "ESP32 will join your WiFi → open http://funkbridge.local", "ok")
            else:
                self.after(0, self._log_msg,
                    "BLE ready — scan for BLE_TO_ISOTP20 in your app", "ok")
        except SystemExit as e:
            if e.code == 0:
                self.after(0, self._progress.set, 100)
                self.after(0, self._set_status, "✓ Flash complete", "green")
            else:
                self.after(0, self._set_status, "✗ Flash failed", "red")
                self.after(0, self._log_msg, "Flash failed — check port and try again", "err")
        except Exception as e:
            self.after(0, self._set_status, f"Error: {e}", "red")
            self.after(0, self._log_msg, str(e), "err")
        finally:
            sys.stdout = old_out
            self.after(0, self._flash_btn.config, {"state": "normal"})


if __name__ == "__main__":
    app = FunkFlashApp()
    app.mainloop()
