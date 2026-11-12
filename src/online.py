# -*- coding: utf-8 -*-
"""
Ket noi choi online (client). Server: server/server.js (Node + WebSocket) chay tren VPS.

 - May tinh: thu vien `websocket-client`, chay o 1 luong rieng -> giao dien khong bi giat.
 - Trinh duyet (pygbag): dung WebSocket cua trinh duyet qua lop JS `window.tdNet` (xem web/).
 - Tu ket noi lai khi rot mang (gui lai token -> ve dung phong, van khong mat).
 - Ten + token luu o %APPDATA%\\TDCaro\\online.json (web: localStorage).

Doi server khi can:  bien moi truong TDCARO_SERVER=wss://...
"""
import json
import os
import queue
import random
import sys
import threading
import time

PROTO = 1
DEFAULT_SERVER = 'wss://vlxd.tail24e2ba.ts.net:10000'
IS_WEB = sys.platform == 'emscripten'


def server_url():
    if IS_WEB:
        # doi server tam thoi bang tham so link:  ...?server=wss://ten-mien-khac
        try:
            import platform as _pf
            from urllib.parse import parse_qs
            q = parse_qs(str(_pf.window.location.search).lstrip('?'))
            if q.get('server'):
                return q['server'][0]
        except Exception:
            pass
    return os.environ.get('TDCARO_SERVER') or DEFAULT_SERVER


# ------------------------------------------------------------------ luu ten / token
def _store_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'TDCaro', 'online.json')


def load_profile():
    try:
        if IS_WEB:
            import platform as _pf
            raw = _pf.window.localStorage.getItem('tdcaro_online')
            raw = str(raw) if raw is not None else ''
            return json.loads(raw) if raw and raw not in ('null', 'undefined') else {}
        with open(_store_path(), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_profile(data):
    try:
        if IS_WEB:
            import platform as _pf
            _pf.window.localStorage.setItem('tdcaro_online', json.dumps(data))
            return
        p = _store_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def default_name():
    return f'Người chơi {random.randint(100, 999)}'


# ------------------------------------------------------------------ backend: may tinh
class _ThreadBackend:
    """websocket-client trong 1 luong; tin nhan nhan ve dua vao queue."""

    def __init__(self, url, on_open_hello):
        self.url = url
        self.hello = on_open_hello
        self.inbox = queue.Queue()
        self.ws = None
        self.lock = threading.Lock()
        self.stop = False
        self.status = 'connecting'
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import websocket
        try:
            import certifi
            sslopt = {'ca_certs': certifi.where()}
        except Exception:
            sslopt = {}
        delay = 1.0
        while not self.stop:
            try:
                self.status = 'connecting'
                ws = websocket.create_connection(self.url, timeout=10, sslopt=sslopt, enable_multithread=True)
                ws.settimeout(None)
                with self.lock:
                    self.ws = ws
                self.status = 'online'
                delay = 1.0
                self._send_raw(json.dumps(self.hello()))
                while not self.stop:
                    data = ws.recv()
                    if not data:
                        break
                    try:
                        self.inbox.put(json.loads(data))
                    except ValueError:
                        pass
            except Exception:
                pass
            with self.lock:
                try:
                    if self.ws:
                        self.ws.close()
                except Exception:
                    pass
                self.ws = None
            if self.stop:
                break
            self.status = 'offline'
            self.inbox.put({'t': '_offline'})
            time.sleep(delay)
            delay = min(delay * 1.7, 8.0)

    def _send_raw(self, text):
        with self.lock:
            if self.ws:
                try:
                    self.ws.send(text)
                    return True
                except Exception:
                    return False
        return False

    def send(self, obj):
        return self._send_raw(json.dumps(obj))

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        self.stop = True
        with self.lock:
            try:
                if self.ws:
                    self.ws.close()
            except Exception:
                pass


# ------------------------------------------------------------------ backend: trinh duyet
class _WebBackend:
    """Goi lop JS window.tdNet (web/net.js): connect/send/poll bang chuoi JSON."""

    def __init__(self, url, on_open_hello):
        import platform as _pf
        self.js = _pf.window.tdNet
        self.hello = on_open_hello
        self.status = 'connecting'
        self.js.connect(url)
        self._was_open = False

    def send(self, obj):
        return bool(self.js.send(json.dumps(obj)))

    def poll(self):
        out = []
        st = str(self.js.status())
        if st == 'open' and not self._was_open:
            self._was_open = True
            self.send(self.hello())
        elif st != 'open' and self._was_open:
            self._was_open = False
            out.append({'t': '_offline'})
        self.status = {'open': 'online', 'connecting': 'connecting'}.get(st, 'offline')
        raw = str(self.js.poll())
        if raw and raw != '[]':
            for s in json.loads(raw):
                try:
                    out.append(json.loads(s))
                except ValueError:
                    pass
        return out

    def close(self):
        try:
            self.js.close()
        except Exception:
            pass


# ------------------------------------------------------------------ client
class OnlineClient:
    def __init__(self):
        prof = load_profile()
        self.name = prof.get('name') or default_name()
        self.token = prof.get('token')
        self.backend = None
        self.state = None          # trang thai phong moi nhat tu server
        self.error = None          # (code, msg)
        self.welcomed = False

    @property
    def status(self):
        if not self.backend:
            return 'idle'
        if self.backend.status == 'online' and not self.welcomed:
            return 'connecting'
        return self.backend.status

    def _hello(self):
        return {'t': 'hello', 'proto': PROTO, 'token': self.token, 'name': self.name}

    def connect(self):
        if self.backend:
            return
        self.welcomed = False
        url = server_url()
        self.backend = (_WebBackend if IS_WEB else _ThreadBackend)(url, self._hello)

    def disconnect(self):
        if self.backend:
            self.backend.close()
        self.backend = None
        self.welcomed = False

    def send(self, obj):
        return bool(self.backend) and self.backend.send(obj)

    def set_name(self, name):
        name = (name or '').strip()[:16] or self.name
        self.name = name
        save_profile({'name': self.name, 'token': self.token})
        self.send({'t': 'name', 'name': name})

    def poll(self):
        """Tra ve danh sach tin moi (da cap nhat self.state / self.error)."""
        if not self.backend:
            return []
        msgs = self.backend.poll()
        for m in msgs:
            t = m.get('t')
            if t == 'welcome':
                self.welcomed = True
                self.token = m.get('token')
                self.name = m.get('name') or self.name
                save_profile({'name': self.name, 'token': self.token})
            elif t == '_offline':
                self.welcomed = False
            elif t == 'state':
                self.state = m
                self.error = None
            elif t == 'left':
                self.state = None
            elif t == 'error':
                self.error = (m.get('code'), m.get('msg') or 'Có lỗi xảy ra.')
        return msgs

    # ---- hanh dong
    def create(self, size, rule):
        self.error = None
        return self.send({'t': 'create', 'size': size, 'rule': rule})

    def join(self, code):
        self.error = None
        return self.send({'t': 'join', 'code': code})

    def move(self, r, c):
        return self.send({'t': 'move', 'r': r, 'c': c})

    def rematch(self):
        return self.send({'t': 'rematch'})

    def leave(self):
        self.state = None
        return self.send({'t': 'leave'})
