# -*- coding: utf-8 -*-
"""
Tu dong cap nhat qua GitHub Releases.
 - Khi mo game: kiem tra release moi nhat (chay nen, khong lam cham game).
 - Windows (.exe): tai ban moi -> dong game -> thay file -> mo lai.
 - macOS (.app): tai .dmg -> dong game -> thay app -> mo lai (that bai thi mo .dmg).
 - Chay tu ma nguon: mo trang release tren trinh duyet.
"""
import os
import re
import sys
import json
import shlex
import ssl
import tempfile
import threading
import subprocess
import platform
import urllib.request
import webbrowser

REPO = 'DuyDev1205/TDCaro'
API_LATEST = f'https://api.github.com/repos/{REPO}/releases/latest'
UA = {'User-Agent': 'TDCaro-Updater', 'Accept': 'application/vnd.github+json'}


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def parse_version(s):
    nums = re.findall(r'\d+', s or '')
    return tuple(int(x) for x in (nums + ['0', '0', '0'])[:3])


def _is_frozen():
    return getattr(sys, 'frozen', False)


def _asset_matches(name):
    n = name.lower()
    if sys.platform == 'win32':
        return n.endswith('.exe')
    if sys.platform == 'darwin':
        if not n.endswith('.dmg'):
            return False
        arm = platform.machine().lower() in ('arm64', 'aarch64')
        return ('applesilicon' in n) if arm else ('intel' in n)
    return False


class Updater:
    def __init__(self, current_version):
        self.current = current_version
        self.state = 'idle'        # idle|checking|uptodate|available|downloading|installing|error
        self.latest = None
        self.page_url = f'https://github.com/{REPO}/releases/latest'
        self.asset_url = None
        self.asset_name = None
        self.progress = 0.0
        self.error = ''
        self.want_quit = False

    # ------------------------------------------------------------ check
    def check_async(self):
        if self.state in ('checking', 'downloading', 'installing'):
            return
        self.state = 'checking'
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            req = urllib.request.Request(API_LATEST, headers=UA)
            with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx()) as r:
                data = json.loads(r.read().decode('utf-8'))
            tag = data.get('tag_name', '')
            self.page_url = data.get('html_url', self.page_url)
            if parse_version(tag) > parse_version(self.current):
                self.latest = tag
                for a in data.get('assets', []):
                    if _asset_matches(a.get('name', '')):
                        self.asset_url = a.get('browser_download_url')
                        self.asset_name = a.get('name')
                        break
                self.state = 'available'
            else:
                self.state = 'uptodate'
        except Exception as e:      # khong co mang / chua co release ... -> im lang
            self.error = str(e)
            self.state = 'idle'

    # ------------------------------------------------------------ install
    def start(self):
        if self.state not in ('available', 'error'):
            return
        if not _is_frozen() or not self.asset_url or sys.platform not in ('win32', 'darwin'):
            webbrowser.open(self.page_url)
            return
        self.state = 'downloading'
        self.progress = 0.0
        threading.Thread(target=self._download_install, daemon=True).start()

    def _download(self, dest):
        req = urllib.request.Request(self.asset_url, headers={'User-Agent': UA['User-Agent']})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as r, open(dest, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0)
            done = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    self.progress = done / total
        if total and done < total:
            raise IOError('Tải về không đủ dữ liệu')

    def _download_install(self):
        try:
            tmpdir = tempfile.mkdtemp(prefix='tdcaro_update_')
            dest = os.path.join(tmpdir, self.asset_name)
            self._download(dest)
            if sys.platform == 'win32':
                self._install_windows(dest, tmpdir)
            else:
                self._install_macos(dest, tmpdir)
            self.state = 'installing'
            self.want_quit = True
        except Exception as e:
            self.error = str(e)
            self.state = 'error'

    def _install_windows(self, new_exe, tmpdir):
        exe = os.path.abspath(sys.executable)
        bat = os.path.join(tmpdir, 'update.bat')
        script = f'''@echo off
set /a n=0
:retry
move /Y "{new_exe}" "{exe}" >NUL 2>&1
if errorlevel 1 (
  set /a n+=1
  if %n% GEQ 60 goto fail
  timeout /t 1 /nobreak >NUL
  goto retry
)
start "" "{exe}"
goto end
:fail
start "" "{os.path.dirname(new_exe)}"
:end
del "%~f0"
'''
        with open(bat, 'w', encoding='mbcs' if os.name == 'nt' else 'utf-8') as f:
            f.write(script)
        flags = 0x08000000 | 0x00000008     # CREATE_NO_WINDOW | DETACHED_PROCESS
        subprocess.Popen(['cmd', '/c', bat], creationflags=flags, close_fds=True)

    def _install_macos(self, dmg, tmpdir):
        exe = os.path.abspath(sys.executable)
        app = os.path.abspath(os.path.join(os.path.dirname(exe), '..', '..'))
        q = shlex.quote
        if not app.endswith('.app'):
            subprocess.Popen(['open', dmg])
            return
        sh = os.path.join(tmpdir, 'update.sh')
        script = f'''#!/bin/sh
while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.5; done
MNT=$(mktemp -d /tmp/tdcaro.XXXXXX)
if ! hdiutil attach -nobrowse -quiet -mountpoint "$MNT" {q(dmg)}; then open {q(dmg)}; exit 1; fi
SRC=$(find "$MNT" -maxdepth 1 -name "*.app" | head -n 1)
rm -rf {q(app + '.old')}
if mv {q(app)} {q(app + '.old')} && ditto "$SRC" {q(app)}; then
  rm -rf {q(app + '.old')}
  hdiutil detach -quiet "$MNT"
  xattr -dr com.apple.quarantine {q(app)} 2>/dev/null
  open {q(app)}
else
  [ -d {q(app + '.old')} ] && mv {q(app + '.old')} {q(app)}
  hdiutil detach -quiet "$MNT"
  open {q(dmg)}
fi
'''
        with open(sh, 'w') as f:
            f.write(script)
        subprocess.Popen(['/bin/sh', sh], start_new_session=True, close_fds=True)

    # ------------------------------------------------------------ UI text
    def label(self):
        if self.state == 'available':
            return f'Có bản mới {self.latest} — Cập nhật ngay'
        if self.state == 'downloading':
            return f'Đang tải bản cập nhật... {int(self.progress * 100)}%'
        if self.state == 'installing':
            return 'Đang cài đặt, game sẽ tự mở lại...'
        if self.state == 'error':
            return 'Cập nhật lỗi — bấm để thử lại'
        return ''

    def visible(self):
        return self.state in ('available', 'downloading', 'installing', 'error')
