// TDCaro - server phong choi online (Node.js + WebSocket)
// ------------------------------------------------------------------
// Server giu trang thai van co (chong gian lan): kiem tra luot, nuoc di,
// thang/thua theo luat "chan 2 dau" hoac "tu do", hoa khi kin ban.
// Moi thay doi -> gui "state" day du cho ca 2 nguoi (ban co <= 20x20, rat nhe).
//
// Giao thuc (JSON):
//  client -> server
//    {t:'hello', proto, token?, name}        bat tay (token: de vao lai phong khi rot mang)
//    {t:'create', size, rule}                tao phong (rule: 'block' | 'free')
//    {t:'join', code}                        vao phong bang ma
//    {t:'move', r, c}                        danh 1 nuoc
//    {t:'rematch'}                           xin choi van moi (ca 2 dong y -> doi nguoi di truoc)
//    {t:'leave'}                             roi phong (dang choi -> xu thua)
//    {t:'name', name}                        doi ten
//    {t:'ping'}
//  server -> client
//    {t:'welcome', token, name}
//    {t:'state', ...}                        trang thai phong (xem roomState)
//    {t:'left'}                              da roi phong
//    {t:'error', code, msg}
//    {t:'pong'}
import http from 'node:http';
import crypto from 'node:crypto';
import { WebSocketServer } from 'ws';

const PORT = Number(process.env.PORT) || 8388;
const HOST = process.env.HOST || '127.0.0.1';
const PROTO = 1;
const MIN_SIZE = 5, MAX_SIZE = 20;
const MAX_ROOMS = 500;
const GRACE_MS = 60_000;             // rot mang: giu cho 60 giay
const WAIT_ROOM_TTL = 30 * 60_000;   // phong cho qua 30 phut -> xoa
const IDLE_ROOM_TTL = 2 * 60 * 60_000;
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

const rooms = new Map();      // code -> room
const sessions = new Map();   // token -> session {token, name, ws, code}

const now = () => Date.now();
const log = (...a) => console.log(new Date().toISOString(), ...a);

function cleanName(s) {
  s = String(s ?? '').replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 16);
  return s || 'Người chơi';
}

function newCode() {
  for (;;) {
    let c = '';
    const b = crypto.randomBytes(6);
    for (let i = 0; i < 6; i++) c += CODE_CHARS[b[i] % CODE_CHARS.length];
    if (!rooms.has(c)) return c;
  }
}

// ------------------------------------------------------------------ luat
// board: mang N*N, '' | 'x' | 'o'
function winLine(board, n, r, c, block) {
  const me = board[r * n + c];
  if (!me) return null;
  const opp = me === 'x' ? 'o' : 'x';
  for (const [dr, dc] of [[0, 1], [1, 0], [1, 1], [1, -1]]) {
    const cells = [[r, c]];
    const ends = [];
    for (const s of [1, -1]) {
      let rr = r + dr * s, cc = c + dc * s;
      while (rr >= 0 && rr < n && cc >= 0 && cc < n && board[rr * n + cc] === me) {
        cells.push([rr, cc]); rr += dr * s; cc += dc * s;
      }
      ends.push(rr >= 0 && rr < n && cc >= 0 && cc < n && board[rr * n + cc] === opp);
    }
    // luat chan 2 dau: bi quan doi thu chan ca 2 dau thi khong thang (bien khong tinh)
    if (cells.length >= 5 && !(block && ends[0] && ends[1])) {
      return cells.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    }
  }
  return null;
}

// ------------------------------------------------------------------ phong
function makeRoom(owner, size, rule) {
  const code = newCode();
  const room = {
    code, size, rule,
    seats: [owner.token, null],        // seats[0] cam 'x' o van dau
    xSeat: 0,                          // ghe dang cam X (X luon di truoc)
    names: [owner.name, null],
    scores: [0, 0, 0],                 // ghe0, ghe1, hoa
    board: [], turn: 'x', moves: [], status: 'waiting',
    winner: null, line: null, reason: null, rematch: [false, false],
    created: now(), active: now(), dropAt: [null, null],
  };
  rooms.set(code, room);
  return room;
}

function resetGame(room) {
  room.board = new Array(room.size * room.size).fill('');
  room.turn = 'x';
  room.moves = [];
  room.status = 'playing';
  room.winner = null; room.line = null; room.reason = null;
  room.rematch = [false, false];
  room.active = now();
}

const seatOf = (room, token) => room.seats.indexOf(token);
const colorOf = (room, seat) => (seat === room.xSeat ? 'x' : 'o');

function roomState(room, seat) {
  const other = 1 - seat;
  const sess = (i) => (room.seats[i] ? sessions.get(room.seats[i]) : null);
  const pl = (i) => room.seats[i] ? {
    name: room.names[i], color: colorOf(room, i), score: room.scores[i],
    online: !!(sess(i) && sess(i).ws && sess(i).code === room.code),
    rematch: room.rematch[i],
  } : null;
  return {
    t: 'state', code: room.code, size: room.size, rule: room.rule, status: room.status,
    you: pl(seat), opp: pl(other), draws: room.scores[2],
    // moves: [[r, c], ...] theo thu tu; nuoc chan (0, 2, ...) la X (X luon di truoc)
    turn: room.turn, moves: room.moves,
    winner: room.winner, line: room.line, reason: room.reason,
  };
}

function send(ws, obj) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
}

function broadcast(room) {
  room.seats.forEach((tok, i) => {
    const s = tok && sessions.get(tok);
    if (s && s.ws && s.code === room.code) send(s.ws, roomState(room, i));
  });
}

function finish(room, winnerColor, line, reason) {
  room.status = 'over';
  room.winner = winnerColor;        // 'x' | 'o' | 'draw'
  room.line = line || null;
  room.reason = reason;             // 'five' | 'full' | 'forfeit'
  if (winnerColor === 'draw') room.scores[2]++;
  else room.scores[winnerColor === 'x' ? room.xSeat : 1 - room.xSeat]++;
  log('room', room.code, 'over', winnerColor, reason);
}

function leaveRoom(sess, why = 'leave') {
  const room = sess.code && rooms.get(sess.code);
  sess.code = null;
  if (!room) return;
  const seat = seatOf(room, sess.token);
  if (seat < 0) return;
  if (room.status === 'playing') finish(room, colorOf(room, 1 - seat), null, 'forfeit');
  room.seats[seat] = null;
  room.names[seat] = null;
  room.rematch = [false, false];
  room.dropAt[seat] = null;
  if (!room.seats[0] && !room.seats[1]) {
    rooms.delete(room.code);
    log('room', room.code, 'closed', why);
    return;
  }
  // nguoi con lai cho nguoi moi vao (giu ma phong)
  if (room.status === 'playing') room.status = 'waiting';
  broadcast(room);
}

// ------------------------------------------------------------------ xu ly tin
function handle(sess, ws, msg) {
  switch (msg.t) {
    case 'ping':
      return send(ws, { t: 'pong' });
    case 'name': {
      sess.name = cleanName(msg.name);
      const room = sess.code && rooms.get(sess.code);
      if (room) { room.names[seatOf(room, sess.token)] = sess.name; broadcast(room); }
      return;
    }
    case 'create': {
      if (sess.code) leaveRoom(sess);
      if (rooms.size >= MAX_ROOMS) return send(ws, { t: 'error', code: 'BUSY', msg: 'Máy chủ đang quá tải, thử lại sau.' });
      const size = Math.max(MIN_SIZE, Math.min(MAX_SIZE, Math.floor(Number(msg.size) || 15)));
      const rule = msg.rule === 'free' ? 'free' : 'block';
      const room = makeRoom(sess, size, rule);
      sess.code = room.code;
      log('room', room.code, 'created', size, rule);
      return broadcast(room);
    }
    case 'join': {
      const code = String(msg.code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
      const room = rooms.get(code);
      if (!room) return send(ws, { t: 'error', code: 'NOT_FOUND', msg: `Không tìm thấy phòng ${code || ''}`.trim() });
      if (seatOf(room, sess.token) >= 0) { sess.code = code; return broadcast(room); }
      const free = room.seats.indexOf(null);
      if (free < 0) return send(ws, { t: 'error', code: 'FULL', msg: 'Phòng đã đủ 2 người.' });
      if (sess.code) leaveRoom(sess);
      room.seats[free] = sess.token;
      room.names[free] = sess.name;
      room.scores = [0, 0, 0];               // cap dau moi -> ti so moi
      sess.code = code;
      if (room.seats[0] && room.seats[1]) resetGame(room);
      log('room', code, 'join', sess.name);
      return broadcast(room);
    }
    case 'move': {
      const room = sess.code && rooms.get(sess.code);
      if (!room || room.status !== 'playing') return send(ws, { t: 'error', code: 'NO_GAME', msg: 'Ván chưa bắt đầu.' });
      const seat = seatOf(room, sess.token);
      if (colorOf(room, seat) !== room.turn) return send(ws, { t: 'error', code: 'TURN', msg: 'Chưa đến lượt bạn.' });
      const r = Math.floor(Number(msg.r)), c = Math.floor(Number(msg.c)), n = room.size;
      if (!(r >= 0 && r < n && c >= 0 && c < n) || room.board[r * n + c]) {
        return send(ws, { t: 'error', code: 'BAD_MOVE', msg: 'Nước đi không hợp lệ.' });
      }
      room.board[r * n + c] = room.turn;
      room.moves.push([r, c]);
      room.active = now();
      const line = winLine(room.board, n, r, c, room.rule === 'block');
      if (line) finish(room, room.turn, line, 'five');
      else if (room.moves.length >= n * n) finish(room, 'draw', null, 'full');
      else room.turn = room.turn === 'x' ? 'o' : 'x';
      return broadcast(room);
    }
    case 'rematch': {
      const room = sess.code && rooms.get(sess.code);
      if (!room || room.status !== 'over' || !room.seats[0] || !room.seats[1]) return;
      room.rematch[seatOf(room, sess.token)] = true;
      if (room.rematch[0] && room.rematch[1]) {
        room.xSeat = 1 - room.xSeat;         // doi nguoi di truoc
        resetGame(room);
      }
      return broadcast(room);
    }
    case 'leave':
      leaveRoom(sess);
      return send(ws, { t: 'left' });
    default:
      return send(ws, { t: 'error', code: 'UNKNOWN', msg: 'Yêu cầu không hợp lệ.' });
  }
}

// ------------------------------------------------------------------ server
const httpServer = http.createServer((req, res) => {
  res.writeHead(200, { 'content-type': 'application/json', 'access-control-allow-origin': '*' });
  res.end(JSON.stringify({ ok: true, app: 'tdcaro', proto: PROTO, rooms: rooms.size, players: sessions.size }));
});

const wss = new WebSocketServer({ server: httpServer, maxPayload: 4096 });

wss.on('connection', (ws) => {
  let sess = null;
  let budget = 30, last = now();            // gioi han ~20 tin/giay
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('message', (data) => {
    const t = now();
    budget = Math.min(30, budget + ((t - last) / 1000) * 20); last = t;
    if (--budget < 0) return;
    let msg;
    try { msg = JSON.parse(data.toString()); } catch { return; }
    if (!msg || typeof msg !== 'object') return;
    if (!sess) {
      if (msg.t !== 'hello') return;
      if (msg.proto !== PROTO) {
        send(ws, { t: 'error', code: 'PROTO', msg: 'Phiên bản game đã cũ, hãy cập nhật để chơi online.' });
        return ws.close();
      }
      let s = msg.token && sessions.get(String(msg.token));
      if (s) {                                 // vao lai (rot mang / mo lai game)
        if (s.ws && s.ws !== ws) { try { s.ws.close(4000, 'replaced'); } catch {} }
        s.ws = ws;
      } else {
        s = { token: crypto.randomBytes(16).toString('hex'), name: 'Người chơi', ws, code: null };
        sessions.set(s.token, s);
      }
      if (msg.name) s.name = cleanName(msg.name);
      sess = s;
      send(ws, { t: 'welcome', token: s.token, name: s.name });
      const room = s.code && rooms.get(s.code);
      if (room) {
        const seat = seatOf(room, s.token);
        if (seat >= 0) { room.dropAt[seat] = null; room.names[seat] = s.name; broadcast(room); }
        else s.code = null;
      }
      return;
    }
    try { handle(sess, ws, msg); } catch (e) { log('error', e); }
  });

  ws.on('close', () => {
    if (!sess || sess.ws !== ws) return;
    sess.ws = null;
    const room = sess.code && rooms.get(sess.code);
    if (room) {
      const seat = seatOf(room, sess.token);
      if (seat >= 0) room.dropAt[seat] = now();
      broadcast(room);
    } else {
      sessions.delete(sess.token);
    }
  });
});

// ping giu ket noi + don dep phong / nguoi roi mang qua lau
setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.isAlive) { ws.terminate(); continue; }
    ws.isAlive = false;
    try { ws.ping(); } catch {}
  }
  const t = now();
  for (const room of rooms.values()) {
    room.dropAt.forEach((at, seat) => {
      if (at && t - at > GRACE_MS) {
        const s = sessions.get(room.seats[seat]);
        if (s) { leaveRoom(s, 'timeout'); sessions.delete(s.token); }
      }
    });
    if (!rooms.has(room.code)) continue;
    const ttl = room.status === 'waiting' ? WAIT_ROOM_TTL : IDLE_ROOM_TTL;
    if (t - room.active > ttl) {
      room.seats.forEach((tok) => { const s = tok && sessions.get(tok); if (s) { s.code = null; send(s.ws, { t: 'left' }); } });
      rooms.delete(room.code);
      log('room', room.code, 'expired');
    }
  }
  for (const s of sessions.values()) if (!s.ws && !s.code) sessions.delete(s.token);
}, 15_000);

httpServer.listen(PORT, HOST, () => log(`TDCaro server tai http://${HOST}:${PORT} (proto ${PROTO})`));
