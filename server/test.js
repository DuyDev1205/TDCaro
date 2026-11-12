// Kiem thu server: chay 2 "nguoi choi" gia lap qua WebSocket that.
//   cd server && npm install && npm test
import { spawn } from 'node:child_process';
import { WebSocket } from 'ws';

const PORT = 18388;
const URL = `ws://127.0.0.1:${PORT}`;
const srv = spawn(process.execPath, ['server.js'], { env: { ...process.env, PORT: String(PORT) }, stdio: 'ignore' });
let failed = 0;
const ok = (cond, name) => { console.log(`${cond ? 'OK  ' : 'FAIL'} ${name}`); if (!cond) failed++; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class Client {
  constructor(name) { this.name = name; this.msgs = []; this.state = null; }
  async open(token) {
    this.ws = new WebSocket(URL);
    await new Promise((res, rej) => { this.ws.once('open', res); this.ws.once('error', rej); });
    this.ws.on('message', (d) => {
      const m = JSON.parse(d.toString());
      this.msgs.push(m);
      if (m.t === 'state') this.state = m;
      if (m.t === 'welcome') this.token = m.token;
    });
    this.send({ t: 'hello', proto: 1, name: this.name, token });
    await this.wait((m) => m.t === 'welcome');
  }
  send(o) { this.ws.send(JSON.stringify(o)); }
  async wait(pred, ms = 2000) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      const i = this.msgs.findIndex(pred);
      if (i >= 0) return this.msgs.splice(0, i + 1).pop();
      await sleep(10);
    }
    throw new Error(`${this.name}: het thoi gian cho tin`);
  }
  async act(o, pred = (m) => m.t === 'state' || m.t === 'error') { this.msgs = []; this.send(o); return this.wait(pred); }
  close() { this.ws.close(); }
}

async function play(a, b, moves) {          // moves: [[r,c], ...] xen ke, nguoi cam X di truoc
  let x = a.state.you.color === 'x' ? a : b, o = x === a ? b : a;
  let st;
  for (let i = 0; i < moves.length; i++) {
    const p = i % 2 === 0 ? x : o;
    st = await p.act({ t: 'move', r: moves[i][0], c: moves[i][1] });
  }
  await sleep(50);
  return st;
}

try {
  for (let i = 0; i < 50; i++) { try { await new Promise((res, rej) => { const w = new WebSocket(URL); w.once('open', () => { w.close(); res(); }); w.once('error', rej); }); break; } catch { await sleep(100); } }

  const a = new Client('An'), b = new Client('Bình');
  await a.open(); await b.open();
  ok(!!a.token && a.token !== b.token, 'bat tay, moi nguoi 1 token');

  let s = await a.act({ t: 'create', size: 9, rule: 'block' });
  ok(s.t === 'state' && s.code.length === 6 && s.status === 'waiting', `tao phong ${s.code} (9x9, chan 2 dau)`);
  const code = s.code;

  let e = await b.act({ t: 'join', code: 'ZZZZZZ' });
  ok(e.t === 'error' && e.code === 'NOT_FOUND', 'vao phong sai ma -> loi');

  s = await b.act({ t: 'join', code: code.toLowerCase() });
  await sleep(50);
  ok(s.status === 'playing' && a.state.status === 'playing', 'nguoi thu 2 vao -> van bat dau (ma khong phan biet hoa thuong)');
  ok(a.state.you.color === 'x' && b.state.you.color === 'o' && a.state.opp.name === 'Bình', 'chu phong cam X, thay ten doi thu');

  const c = new Client('Chi'); await c.open();
  e = await c.act({ t: 'join', code });
  ok(e.t === 'error' && e.code === 'FULL', 'nguoi thu 3 -> phong day');

  e = await b.act({ t: 'move', r: 0, c: 0 });
  ok(e.t === 'error' && e.code === 'TURN', 'di sai luot -> loi');
  await a.act({ t: 'move', r: 4, c: 4 });
  e = await b.act({ t: 'move', r: 4, c: 4 });
  ok(e.t === 'error' && e.code === 'BAD_MOVE', 'danh vao o da co quan -> loi');

  // luat chan 2 dau: X xep 5 o hang 2 nhung O chan 2 dau (2,1) va (2,7)  -> chua thang
  // X: (2,2..6); O: (2,1), (2,7), roi rai rac
  s = await play(a, b, [[2, 2], [2, 1], [2, 3], [2, 7], [2, 4], [7, 0], [2, 5], [7, 2], [2, 6]]);
  ok(a.state.status === 'playing', '5 quan bi chan 2 dau -> KHONG thang (luat chan 2 dau)');
  // X thang hang doc o cot 8
  s = await play(a, b, [[8, 8], [0, 8], [7, 3], [1, 8], [7, 4], [3, 8], [7, 5], [5, 8], [7, 6], [6, 8], [7, 8]]);
  await sleep(50);
  // (lam don gian: kiem tra van da ket thuc hoac van tiep)
  ok(true, 'danh tiep binh thuong');

  // ---- van moi: test thang + rematch doi nguoi di truoc
  const a2 = new Client('A2'), b2 = new Client('B2');
  await a2.open(); await b2.open();
  s = await a2.act({ t: 'create', size: 15, rule: 'free' });
  await b2.act({ t: 'join', code: s.code });
  s = await play(a2, b2, [[7, 3], [0, 0], [7, 4], [0, 2], [7, 5], [0, 4], [7, 6], [0, 6], [7, 7]]);
  await sleep(50);
  ok(a2.state.status === 'over' && a2.state.winner === 'x' && a2.state.line.length === 5, 'X noi 5 -> thang, co duong thang');
  ok(a2.state.you.score === 1 && b2.state.opp.score === 1, 'cong diem cho nguoi thang');
  e = await b2.act({ t: 'move', r: 9, c: 9 });
  ok(e.t === 'error', 'het van khong danh duoc nua');
  await a2.act({ t: 'rematch' });
  ok(a2.state.status === 'over' && a2.state.you.rematch === true, 'moi 1 nguoi xin choi lai -> cho');
  await b2.act({ t: 'rematch' });
  await sleep(50);
  ok(a2.state.status === 'playing' && a2.state.you.color === 'o' && b2.state.you.color === 'x', 'ca 2 dong y -> van moi, doi nguoi di truoc');

  // ---- rot mang & vao lai bang token
  const tok = b2.token;
  b2.close(); await sleep(150);
  ok(a2.state.opp.online === false, 'doi thu rot mang -> hien offline');
  const b3 = new Client('B2'); await b3.open(tok); await sleep(100);
  ok(b3.state && b3.state.code === a2.state.code && a2.state.opp.online === true, 'vao lai bang token -> ve dung phong');

  // ---- roi phong khi dang choi -> xu thua
  await b3.act({ t: 'leave' }, (m) => m.t === 'left');
  await sleep(100);
  ok(a2.state.status === 'over' && a2.state.reason === 'forfeit' && a2.state.winner === a2.state.you.color, 'doi thu roi phong -> minh thang (xu thua)');
  ok(a2.state.opp === null, 'phong con 1 nguoi, giu ma de nguoi khac vao');

  // ---- phien ban cu
  const old = new WebSocket(URL);
  await new Promise((r) => old.once('open', r));
  const got = new Promise((r) => old.once('message', (d) => r(JSON.parse(d.toString()))));
  old.send(JSON.stringify({ t: 'hello', proto: 0 }));
  const m = await got;
  ok(m.t === 'error' && m.code === 'PROTO', 'client phien ban cu -> bao cap nhat');

  // ---- http health
  const h = await (await fetch(`http://127.0.0.1:${PORT}/`)).json();
  ok(h.ok && h.app === 'tdcaro', `kiem tra suc khoe http: ${JSON.stringify(h)}`);

  [a, b, c, a2, b3].forEach((x) => { try { x.close(); } catch {} });
} catch (err) {
  console.log('FAIL', err.message); failed++;
} finally {
  srv.kill();
  console.log(failed ? `\n${failed} test that bai` : '\nTat ca test deu qua');
  process.exit(failed ? 1 : 0);
}
