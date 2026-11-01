# -*- mode: python ; coding: utf-8 -*-
# Build tren macOS:  pyinstaller TDCaro_mac.spec   ->  dist/TDCaro.app
import os

VERSION = os.environ.get('APP_VERSION', '1.0.0')

a = Analysis(
    ['Finals.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TDCaro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TDCaro')
app = BUNDLE(
    coll,
    name='TDCaro.app',
    icon='icon.png',
    bundle_identifier='com.duydev.tdcaro',
    info_plist={
        'CFBundleDisplayName': 'TDCaro',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'NSHighResolutionCapable': True,
    },
)
