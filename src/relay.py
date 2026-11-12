# -*- coding: utf-8 -*-
"""
Duong chuyen tiep cho che do choi online: MQTT broker CONG CONG qua WebSocket (giong Co Ty Phu).
Khong can server rieng, khong Tailscale. Client MQTT 3.1.1 toi gian, chi QoS 0.

 - May tinh: websocket-client trong 1 luong / broker.
 - Trinh duyet (pygbag): WebSocket cua trinh duyet qua lop JS window.tdSock (web/tdcaro.tmpl).
 - Ket noi CUNG LUC nhieu broker, gui tin len tat ca, loc tin trung bang 'mid'
   -> 1 broker truc trac van choi duoc.
"""
import base64
import json
import os
import queue
import random
import sys
import threading
import time

IS_WEB = sys.platform == 'emscripten'
BROKERS = [
    'wss://broker.emqx.io:8084/mqtt',
    'wss://broker.hivemq.com:8884/mqtt',
    'wss://test.mosquitto.org:8081/mqtt',
]
USE_BROKERS = 2          # so broker ket noi cung luc


def brokers():
    env = os.environ.get('TDCARO_BROKERS')
    if env:
        return [b for b in env.split(',') if b]
    return BROKERS[:USE_BROKERS]


# ------------------------------------------------------------------ goi MQTT
def _s(text):
    b = text.encode('utf-8')
    return bytes([len(b) >> 8, len(b) & 255]) + b


def _packet(ptype, body):
    out = bytearray([ptype])
    n = len(body)
    while True:
        d = n % 128
        n //= 128
        out.append(d | (128 if n else 0))
        if not n:
            break
    return bytes(out) + body


def p_connect(client_id, keepalive=30):
    return _packet(0x10, _s('MQTT') + bytes([4, 0x02, keepalive >> 8, keepalive & 255]) + _s(client_id))


def p_subscribe(pid, topic):
    return _packet(0x82, bytes([pid >> 8, pid & 255]) + _s(topic) + b'\x00')


def p_publish(topic, payload):
    return _packet(0x30, _s(topic) + payload)


P_PING = b'\xc0\x00'


# ------------------------------------------------------------------ socket: may tinh
class _DesktopSock:
    def __init__(self, url):
        self.url = url
        self.inbox = queue.Queue()
        self.ws = None
        self.lock = threading.Lock()
        self.stop = False
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
                ws = websocket.create_connection(self.url, timeout=10, subprotocols=['mqtt'], sslopt=sslopt,
                                                 enable_multithread=True)
                ws.settimeout(None)
                with self.lock:
                    self.ws = ws
                self.inbox.put(('open', None))
                delay = 1.0
                while not self.stop:
                    op, data = ws.recv_data()
                    if op == websocket.ABNF.OPCODE_CLOSE:
                        break
                    if op in (websocket.ABNF.OPCODE_BINARY, websocket.ABNF.OPCODE_TEXT) and data:
                        self.inbox.put(('data', data if isinstance(data, bytes) else data.encode()))
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
            self.inbox.put(('close', None))
            time.sleep(delay)
            delay = min(delay * 2, 8.0)

    def send(self, data):
        with self.lock:
            if self.ws:
                try:
                    self.ws.send_binary(data)
                    return True
                except Exception:
                    return False
        return False

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


# ------------------------------------------------------------------ socket: trinh duyet
class _WebSock:
    def __init__(self, url):
        import platform as _pf
        self.js = _pf.window.tdSock
        self.url = url
        self.id = None
        self.was_open = False
        self.down = False
        self.next_try = 0.0
        self.delay = 1.0
        self._open()

    def _open(self):
        self.id = int(self.js.open(self.url, 'mqtt'))
        self.was_open = False
        self.down = False

    def poll(self):
        out = []
        if self.id is None:
            if time.time() >= self.next_try:
                self._open()
            return out
        st = str(self.js.status(self.id))
        if st == 'open' and not self.was_open:
            self.was_open = True
            self.delay = 1.0
            out.append(('open', None))
        raw = str(self.js.poll(self.id))
        if raw and raw != '[]':
            for s in json.loads(raw):
                out.append(('data', base64.b64decode(s)))
        if st == 'closed':
            out.append(('close', None))
            self.js.close(self.id)
            self.id = None
            self.next_try = time.time() + self.delay
            self.delay = min(self.delay * 2, 8.0)
        return out

    def send(self, data):
        if self.id is None:
            return False
        return bool(self.js.send(self.id, base64.b64encode(data).decode('ascii')))

    def close(self):
        if self.id is not None:
            self.js.close(self.id)
        self.id = None
        self.next_try = float('inf')


# ------------------------------------------------------------------ 1 ket noi MQTT
class MqttConn:
    def __init__(self, url):
        self.url = url
        self.sock = (_WebSock if IS_WEB else _DesktopSock)(url)
        self.ready = False
        self.buf = b''
        self.subs = []
        self.pid = 1
        self.last_ping = time.time()
        self.cid = 'tdc' + ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(10))

    def _send(self, data):
        return self.sock.send(data)

    def subscribe(self, topic):
        if topic not in self.subs:
            self.subs.append(topic)
            if self.ready:
                self._sub(topic)

    def _sub(self, topic):
        self.pid = self.pid % 65000 + 1
        self._send(p_subscribe(self.pid, topic))

    def publish(self, topic, payload):
        return self.ready and self._send(p_publish(topic, payload))

    def poll(self):
        msgs = []
        for kind, data in self.sock.poll():
            if kind == 'open':
                self.buf = b''
                self._send(p_connect(self.cid))
            elif kind == 'close':
                self.ready = False
            else:
                self.buf += data
                msgs.extend(self._parse())
        if self.ready and time.time() - self.last_ping > 20:
            self.last_ping = time.time()
            self._send(P_PING)
        return msgs

    def _parse(self):
        out = []
        b = self.buf
        i = 0
        while i + 2 <= len(b):
            n, mul, k = 0, 1, i + 1
            while True:
                if k >= len(b):
                    self.buf = b[i:]
                    return out
                byte = b[k]
                k += 1
                n += (byte & 127) * mul
                mul *= 128
                if not byte & 128:
                    break
            if k + n > len(b):
                break
            ptype, body = b[i] & 0xF0, b[k:k + n]
            i = k + n
            if ptype == 0x20:                       # CONNACK
                if len(body) >= 2 and body[1] == 0:
                    self.ready = True
                    self.last_ping = time.time()
                    for t in self.subs:
                        self._sub(t)
            elif ptype == 0x30 and len(body) >= 2:  # PUBLISH (QoS 0)
                tl = (body[0] << 8) | body[1]
                out.append((body[2:2 + tl].decode('utf-8', 'replace'), body[2 + tl:]))
        self.buf = b[i:]
        return out

    def close(self):
        self.sock.close()
        self.ready = False


# ------------------------------------------------------------------ nhieu broker cung luc
class Relay:
    def __init__(self, urls=None):
        self.conns = [MqttConn(u) for u in (urls or brokers())]
        self.seen = []
        self.seen_set = set()

    @property
    def status(self):
        return 'online' if any(c.ready for c in self.conns) else 'connecting'

    def subscribe(self, topic):
        for c in self.conns:
            c.subscribe(topic)

    def publish(self, topic, obj):
        obj = dict(obj, mid=''.join(random.choice('0123456789abcdef') for _ in range(12)))
        data = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        sent = False
        for c in self.conns:
            sent = c.publish(topic, data) or sent
        return sent

    def poll(self):
        out = []
        for c in self.conns:
            for topic, payload in c.poll():
                try:
                    obj = json.loads(payload.decode('utf-8'))
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                mid = obj.get('mid')
                if mid:
                    if mid in self.seen_set:
                        continue                    # cung 1 tin den tu broker khac
                    self.seen.append(mid)
                    self.seen_set.add(mid)
                    if len(self.seen) > 600:
                        self.seen_set.discard(self.seen.pop(0))
                out.append((topic, obj))
        return out

    def close(self):
        for c in self.conns:
            c.close()
