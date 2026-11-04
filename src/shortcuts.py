# -*- coding: utf-8 -*-
"""
Tao shortcut "TDCaro" (Desktop + Start Menu) cho ban .exe tren Windows.

 - Tao khi mo game LAN DAU, khi vua CAP NHAT (phien ban khac lan truoc) hoac khi exe bi DOI CHO.
 - Neu nguoi dung tu xoa shortcut thi khong tao lai cho toi lan cap nhat sau.
 - Tao bang PowerShell (WScript.Shell) chay AN (CREATE_NO_WINDOW) -> khong hien console.
 - Trang thai luu o %APPDATA%\\TDCaro\\install.json
"""
import json
import os
import subprocess
import sys
import threading

NAME = 'TDCaro'
_PS = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TD_LNK); "
       "$s.TargetPath = $env:TD_EXE; $s.WorkingDirectory = $env:TD_DIR; "
       "$s.IconLocation = $env:TD_EXE + ',0'; $s.Description = 'TDCaro - Caro AI'; $s.Save()")


def _known_dir(csidl):
    """Thu muc dac biet cua Windows (dung ca khi Desktop bi OneDrive chuyen huong)."""
    import ctypes
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0:
        return buf.value
    return None


def default_dirs():
    desktop = _known_dir(0x0010)          # CSIDL_DESKTOPDIRECTORY
    programs = _known_dir(0x0002)         # CSIDL_PROGRAMS (Start Menu\Programs)
    return [d for d in (desktop, programs) if d]


def state_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(base, NAME, 'install.json')


def create_shortcut(lnk, exe):
    env = dict(os.environ, TD_LNK=lnk, TD_EXE=exe, TD_DIR=os.path.dirname(exe))
    r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                        '-Command', _PS], env=env, creationflags=0x08000000,     # CREATE_NO_WINDOW
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    return r.returncode == 0 and os.path.exists(lnk)


def ensure(version, exe=None, dirs=None, state_file=None):
    """Tao/cap nhat shortcut neu can. Tra ve so shortcut da tao (0 neu khong can)."""
    exe = os.path.abspath(exe or sys.executable)
    state_file = state_file or state_path()
    try:
        with open(state_file, encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        st = {}
    if st.get('exe') == exe and st.get('version') == version:
        return 0
    made = 0
    for d in (dirs if dirs is not None else default_dirs()):
        try:
            os.makedirs(d, exist_ok=True)
            if create_shortcut(os.path.join(d, NAME + '.lnk'), exe):
                made += 1
        except Exception:
            pass
    try:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({'exe': exe, 'version': version}, f)
    except Exception:
        pass
    return made


def ensure_async(version):
    """Goi khi mo game: chi ban exe dong goi tren Windows; chay nen, khong lam cham game."""
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return
    if os.environ.get('CARO_NO_SHORTCUT') or os.environ.get('CARO_NO_UPDATE'):
        return
    threading.Thread(target=ensure, args=(version,), daemon=True).start()
