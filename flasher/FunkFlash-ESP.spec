# FunkFlash-ESP.spec
# PyInstaller spec — bundles firmware .bin files and esptool

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
        'esptool',
        'esptool.targets',
        'esptool.loader',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
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
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
