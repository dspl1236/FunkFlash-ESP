# FunkFlash-ESP.spec
# PyInstaller spec for Windows EXE build
# Explicit hidden imports for esptool and pyserial

import sys
from pathlib import Path

block_cipher = None

firmware_dir = Path('firmware')
firmware_data = [(str(f), 'firmware') for f in firmware_dir.glob('*.bin')]
firmware_data += [(str(f), 'firmware') for f in firmware_dir.glob('*.txt')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=firmware_data,
    hiddenimports=[
        # esptool and all chip targets
        'esptool',
        'esptool.targets',
        'esptool.targets.esp32',
        'esptool.targets.esp32s2',
        'esptool.targets.esp32s3',
        'esptool.targets.esp32c3',
        'esptool.loader',
        'esptool.cmds',
        'esptool.bin_image',
        'esptool.config',
        'esptool.util',
        'esptool.uf2_writer',
        'esptool.reset',
        # pyserial
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_windows',
        'serial.tools.list_ports_posix',
        'serial.tools.list_ports_osx',
        # tkinter (usually auto-detected but explicit for CI)
        'tkinter',
        'tkinter.ttk',
        'tkinter.font',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Collect all esptool data files (chip stubs etc)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
a.datas += collect_data_files('esptool')

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='FunkFlash-ESP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # no console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
