# -*- mode: python ; coding: utf-8 -*-
# Build (macOS), chay tu thu muc goc:  pyinstaller packaging/TDCaro_mac.spec  ->  dist/TDCaro.app
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
VERSION = os.environ.get('APP_VERSION', '1.0.0')

a = Analysis(
    [os.path.join(ROOT, 'src', 'Finals.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[(os.path.join(ROOT, 'assets', 'icon.png'), 'assets'),
           (os.path.join(ROOT, 'assets', 'music'), os.path.join('assets', 'music'))],
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
    icon=os.path.join(ROOT, 'assets', 'icon.png'),
    bundle_identifier='com.duydev.tdcaro',
    info_plist={
        'CFBundleDisplayName': 'TDCaro',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'NSHighResolutionCapable': True,
    },
)
