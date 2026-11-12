# -*- coding: utf-8 -*-
"""
Choi online 1 vs 1 - KHONG CAN SERVER RIENG (giong Co Ty Phu).

 - Hai may gui tin cho nhau qua MQTT broker cong cong (relay.py), ket noi cung luc 2 broker.
 - CHU PHONG lam trong tai: phong (HostRoom: luot, nuoc di, thang/thua, luat chan 2 dau)
   chay ngay trong game cua nguoi tao phong. Khach chi gui hanh dong va nhan trang thai.
 - Ban may tinh va ban web dung CHUNG code nay -> choi cheo duoc voi nhau.
 - Tin co the bi roi (QoS 0): chu phong gui lai trang thai moi 3 giay, khach gui lai nuoc di
   neu chua thay duoc xac nhan. Moi trang thai co 'seq' tang dan.
 - Ten + token luu o %APPDATA%\\TDCaro\\online.json (web: localStorage).

Dinh dang 'state' giong het ban dung server truoc day -> giao dien khong phai doi.
"""
import json
import os
import random
import secrets
import sys
import time

import relay

PROTO = 2
IS_WEB = sys.platform == 'emscripten'
TOPIC_ROOT = 'tdcaro-vn-2026'
CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
MIN_SIZE, MAX_SIZE = 5, 20

HEARTBEAT = 3.0          # chu phong gui lai trang thai / khach gui "con day"
GUEST_LOST = 12.0        # khong nghe khach qua lau -> bao mat ket noi
GUEST_DROP = 60.0        # mat ket noi qua 60s -> xu thua, roi phong
HOST_LOST = 12.0         # khach khong nghe chu phong qua lau -> bao mat ket noi
JOIN_TIMEOUT = 10.0
RESEND = 2.5


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


def clean_name(s):
    s = ''.join(ch for ch in str(s or '') if ch.isprintable()).strip()[:16]
    return s or 'Người chơi'


def new_code():
    return ''.join(secrets.choice(CODE_CHARS) for _ in range(6))


# ------------------------------------------------------------------ luat (giong server cu)
def win_line(board, n, r, c, block):
    me = board[r * n + c]
    if not me:
        return None
    opp = 'o' if me == 'x' else 'x'
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        cells = [(r, c)]
        ends = []
        for s in (1, -1):
            rr, cc = r + dr * s, c + dc * s
            while 0 <= rr < n and 0 <= cc < n and board[rr * n + cc] == me:
                cells.append((rr, cc))
                rr += dr * s
                cc += dc * s
            ends.append(0 <= rr < n and 0 <= cc < n and board[rr * n + cc] == opp)
        # luat chan 2 dau: bi chan ca 2 dau thi khong thang (bien khong tinh)
        if len(cells) >= 5 and not (block and ends[0] and ends[1]):
            return [list(x) for x in sorted(cells)]
    return None


class HostRoom:
    """Phong choi chay trong game cua chu phong (trong tai)."""

    def __init__(self, code, size, rule, host_token, host_name):
        self.code = code
        self.size = max(MIN_SIZE, min(MAX_SIZE, int(size)))
        self.rule = 'free' if rule == 'free' else 'block'
        self.seats = [host_token, None]
        self.names = [host_name, None]
        self.online = [True, False]
        self.x_seat = 0                    # ghe dang cam X (X luon di truoc)
        self.scores = [0, 0, 0]            # ghe 0, ghe 1, hoa
        self.board = []
        self.turn = 'x'
        self.moves = []
        self.status = 'waiting'
        self.winner = self.line = self.reason = None
        self.rematch = [False, False]
        self.seq = 0

    def seat_of(self, token):
        return self.seats.index(token) if token in self.seats else -1

    def color_of(self, seat):
        return 'x' if seat == self.x_seat else 'o'

    def reset_game(self):
        self.board = [''] * (self.size * self.size)
        self.turn = 'x'
        self.moves = []
        self.status = 'playing'
        self.winner = self.line = self.reason = None
        self.rematch = [False, False]

    def finish(self, winner, line, reason):
        self.status = 'over'
        self.winner, self.line, self.reason = winner, line, reason
        if winner == 'draw':
            self.scores[2] += 1
        else:
            self.scores[self.x_seat if winner == 'x' else 1 - self.x_seat] += 1

    def join(self, token, name):
        if self.seat_of(token) >= 0:
            self.online[self.seat_of(token)] = True
            return None
        if self.seats[1] is not None:
            return ('FULL', 'Phòng đã đủ 2 người.')
        self.seats[1], self.names[1], self.online[1] = token, clean_name(name), True
        self.scores = [0, 0, 0]
        self.reset_game()
        return None

    def move(self, token, r, c):
        seat = self.seat_of(token)
        if seat < 0 or self.status != 'playing':
            return ('NO_GAME', 'Ván chưa bắt đầu.')
        if self.color_of(seat) != self.turn:
            return ('TURN', 'Chưa đến lượt bạn.')
        n = self.size
        try:
            r, c = int(r), int(c)
        except (TypeError, ValueError):
            return ('BAD_MOVE', 'Nước đi không hợp lệ.')
        if not (0 <= r < n and 0 <= c < n) or self.board[r * n + c]:
            return ('BAD_MOVE', 'Nước đi không hợp lệ.')
        self.board[r * n + c] = self.turn
        self.moves.append([r, c])
        line = win_line(self.board, n, r, c, self.rule == 'block')
        if line:
            self.finish(self.turn, line, 'five')
        elif len(self.moves) >= n * n:
            self.finish('draw', None, 'full')
        else:
            self.turn = 'o' if self.turn == 'x' else 'x'
        return None

    def ask_rematch(self, token):
        seat = self.seat_of(token)
        if seat < 0 or self.status != 'over' or self.seats[1] is None:
            return
        self.rematch[seat] = True
        if all(self.rematch):
            self.x_seat = 1 - self.x_seat          # doi nguoi di truoc
            self.reset_game()

    def leave(self, token):
        seat = self.seat_of(token)
        if seat < 0:
            return
        if self.status == 'playing':
            self.finish(self.color_of(1 - seat), None, 'forfeit')
        self.seats[seat] = self.names[seat] = None
        self.online[seat] = False
        self.rematch = [False, False]

    def state_for(self, token):
        seat = self.seat_of(token)
        other = 1 - seat

        def pl(i):
            if self.seats[i] is None:
                return None
            return {'name': self.names[i], 'color': self.color_of(i), 'score': self.scores[i],
                    'online': self.online[i], 'rematch': self.rematch[i]}
        return {'t': 'state', 'seq': self.seq, 'code': self.code, 'size': self.size, 'rule': self.rule,
                'status': self.status, 'you': pl(seat), 'opp': pl(other), 'draws': self.scores[2],
                'turn': self.turn, 'moves': [list(m) for m in self.moves],
                'winner': self.winner, 'line': self.line, 'reason': self.reason}


# ------------------------------------------------------------------ client
class OnlineClient:
    def __init__(self):
        prof = load_profile()
        self.name = prof.get('name') or default_name()
        self.token = prof.get('token') or secrets.token_hex(16)
        save_profile({'name': self.name, 'token': self.token})
        self.relay = None
        self.role = None            # None | 'host' | 'guest'
        self.code = None
        self.room = None            # HostRoom (khi la chu phong)
        self.state = None           # trang thai phong moi nhat (goc nhin cua minh)
        self.error = None           # (code, msg)
        self._out = []
        self._reset_timers()

    def _reset_timers(self):
        now = time.time()
        self.t_beat = 0.0
        self.guest_seen = now
        self.host_seen = now
        self.host_lost = False
        self.join_until = 0.0
        self.t_join = 0.0
        self.pending = None         # khach: (r, c, so nuoc luc gui, thoi diem gui)
        self.last_seq = -1

    # ---- trang thai ket noi
    @property
    def status(self):
        if not self.relay:
            return 'idle'
        return self.relay.status

    def connect(self):
        if not self.relay:
            self.relay = relay.Relay()

    def disconnect(self):
        if self.state or self.role:
            self.leave()
        if self.relay:
            self.relay.close()
        self.relay = None

    def _topic(self, *parts):
        return '/'.join((TOPIC_ROOT, self.code) + parts)

    def _send_host(self, obj):
        obj = dict(obj, token=self.token, proto=PROTO)
        return self.relay.publish(self._topic('h'), obj)

    def _send_guest(self, token, obj):
        return self.relay.publish(self._topic('g', token), obj)

    # ---- chu phong: day trang thai
    def _host_push(self, bump=True):
        r = self.room
        if bump:
            r.seq += 1
        self.state = r.state_for(self.token)
        self._out.append(self.state)
        if r.seats[1]:
            self._send_guest(r.seats[1], r.state_for(r.seats[1]))
        self.t_beat = time.time()

    # ---- hanh dong (giao dien goi)
    def set_name(self, name):
        self.name = clean_name(name)
        save_profile({'name': self.name, 'token': self.token})
        if self.role == 'host' and self.room:
            self.room.names[0] = self.name
            self._host_push()
        elif self.role == 'guest':
            self._send_host({'t': 'name', 'name': self.name})

    def create(self, size, rule):
        self.leave()
        self.error = None
        self.role, self.code = 'host', new_code()
        self.room = HostRoom(self.code, size, rule, self.token, self.name)
        self._reset_timers()
        self.relay.subscribe(self._topic('h'))
        self._host_push()
        return True

    def join(self, code):
        code = ''.join(ch for ch in str(code).upper() if ch in CODE_CHARS)[:6]
        if len(code) != 6:
            self.error = ('NOT_FOUND', 'Mã phòng không hợp lệ.')
            return False
        self.leave()
        self.error = None
        self.role, self.code = 'guest', code
        self._reset_timers()
        self.join_until = time.time() + JOIN_TIMEOUT
        self.relay.subscribe(self._topic('g', self.token))
        self._send_join()
        return True

    def _send_join(self):
        self.t_join = time.time()
        self._send_host({'t': 'join', 'name': self.name})

    def move(self, r, c):
        if self.role == 'host' and self.room:
            err = self.room.move(self.token, r, c)
            if err:
                self._out.append({'t': 'error', 'code': err[0], 'msg': err[1]})
                return False
            self._host_push()
            return True
        if self.role == 'guest' and self.state:
            self.pending = (r, c, len(self.state.get('moves') or []), time.time())
            return self._send_host({'t': 'move', 'r': r, 'c': c}) or True
        return False

    def rematch(self):
        if self.role == 'host' and self.room:
            self.room.ask_rematch(self.token)
            self._host_push()
        elif self.role == 'guest':
            self._send_host({'t': 'rematch'})

    def leave(self):
        if self.role == 'host' and self.room and self.room.seats[1]:
            self._send_guest(self.room.seats[1], {'t': 'closed'})
        elif self.role == 'guest' and self.code:
            self._send_host({'t': 'leave'})
        self.role = self.code = self.room = self.state = None
        self._reset_timers()
        return True

    # ---- vong lap (moi frame)
    def poll(self):
        if not self.relay:
            return []
        out, self._out = self._out, []
        now = time.time()
        for topic, m in self.relay.poll():
            if not self.code or not topic.startswith(f'{TOPIC_ROOT}/{self.code}/'):
                continue
            if self.role == 'host' and topic.endswith('/h'):
                self._host_handle(m)
            elif self.role == 'guest':
                out.extend(self._guest_handle(m))
        if self.role == 'host' and self.room:
            self._host_tick(now)
        elif self.role == 'guest':
            out.extend(self._guest_tick(now))
        out.extend(self._out)
        self._out = []
        return out

    def _host_handle(self, m):
        r, tok, t = self.room, str(m.get('token') or ''), m.get('t')
        if not tok or tok == self.token:
            return
        if m.get('proto') != PROTO:
            self._send_guest(tok, {'t': 'error', 'code': 'PROTO',
                                   'msg': 'Hai bên đang dùng phiên bản TDCaro khác nhau, hãy cập nhật.'})
            return
        if t == 'join':
            err = r.join(tok, m.get('name'))
            if err:
                self._send_guest(tok, {'t': 'error', 'code': err[0], 'msg': err[1]})
                return
            self.guest_seen = time.time()
            self._host_push()
            return
        if r.seat_of(tok) != 1:
            return
        self.guest_seen = time.time()
        if not r.online[1]:
            r.online[1] = True
            self._host_push()
        if t == 'move':
            mv = [m.get('r'), m.get('c')]
            if r.moves and r.moves[-1] == mv:      # gui lai (tin truoc da toi) -> chi gui lai trang thai
                self._host_push(bump=False)
                return
            err = r.move(tok, m.get('r'), m.get('c'))
            if err:
                self._send_guest(tok, {'t': 'error', 'code': err[0], 'msg': err[1]})
            self._host_push(bump=not err)
        elif t == 'rematch':
            r.ask_rematch(tok)
            self._host_push()
        elif t == 'name':
            r.names[1] = clean_name(m.get('name'))
            self._host_push()
        elif t == 'leave':
            r.leave(tok)
            self._host_push()

    def _host_tick(self, now):
        r = self.room
        if r.seats[1]:
            gone = now - self.guest_seen
            if gone > GUEST_DROP:
                r.leave(r.seats[1])
                self._host_push()
                return
            if gone > GUEST_LOST and r.online[1]:
                r.online[1] = False
                self._host_push()
                return
        if now - self.t_beat > HEARTBEAT:
            self._host_push(bump=False)          # nhip tim + dong bo lai neu khach mat tin

    def _guest_handle(self, m):
        t = m.get('t')
        self.host_seen = time.time()
        if t == 'state':
            seq = int(m.get('seq') or 0)
            if self.host_lost:
                self.host_lost = False
            if seq < self.last_seq:
                return []
            changed = seq > self.last_seq or self.state is None
            self.last_seq = seq
            self.join_until = 0.0
            m = {k: v for k, v in m.items() if k != 'mid'}
            if self.pending and len(m.get('moves') or []) > self.pending[2]:
                self.pending = None
            if changed or (self.state and self.state.get('opp') and not self.state['opp'].get('online')):
                self.state = m
                self.error = None
                return [m]
            return []
        if t == 'error':
            self.error = (m.get('code'), m.get('msg') or 'Có lỗi xảy ra.')
            self.pending = None
            if self.state is None:               # vao phong that bai
                self.role = self.code = None
            return [{'t': 'error', 'code': m.get('code'), 'msg': self.error[1]}]
        if t == 'closed':
            self.role = self.code = self.state = None
            self.error = ('CLOSED', 'Chủ phòng đã rời phòng.')
            return [{'t': 'error', 'code': 'CLOSED', 'msg': 'Chủ phòng đã rời phòng.'}, {'t': 'left'}]
        return []

    def _guest_tick(self, now):
        out = []
        if self.state is None:
            if self.join_until and now > self.join_until:
                self.role = self.code = None
                self.join_until = 0.0
                self.error = ('NOT_FOUND', 'Không tìm thấy phòng (sai mã hoặc chủ phòng đã thoát).')
                out.append({'t': 'error', 'code': 'NOT_FOUND', 'msg': self.error[1]})
            elif self.join_until and now - self.t_join > RESEND:
                self._send_join()
            return out
        if now - self.t_beat > HEARTBEAT:
            self.t_beat = now
            self._send_host({'t': 'ping'})
        if self.pending and now - self.pending[3] > RESEND:
            r, c, n, _ = self.pending
            self.pending = (r, c, n, now)
            self._send_host({'t': 'move', 'r': r, 'c': c})
        if not self.host_lost and now - self.host_seen > HOST_LOST:
            self.host_lost = True
            st = dict(self.state)
            if st.get('opp'):
                st['opp'] = dict(st['opp'], online=False)
            self.state = st
            out.append(st)
            out.append({'t': '_offline'})
        return out
