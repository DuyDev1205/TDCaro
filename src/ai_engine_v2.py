# -*- coding: utf-8 -*-
"""
AI ENGINE NANG CAO cho Caro (luat tu do: 5 quan tro len lien tiep la thang)
==========================================================================
Engine goc (best_move / stupid_score trong Finals.py) duoc GIU NGUYEN = muc "De".
File nay bo sung 3 muc:

  normal  (Binh thuong): heuristic GOC stupid_score + luat uu tien chien thuat
                         (thang ngay > chan 5 > tao 4 mo > chan 3 mo) + khai cuoc o tam.
  hard    (Kho)        : danh gia theo mau hinh (bon mo, bon, ba mo, ...),
                         tim chuoi ep thang VCF, alpha-beta ~4 nuoc voi beam search.
  expert  (Cuc kho)    : nhu hard + VCT (chuoi de doa ba/bon), chu dong pha VCF cua doi thu,
                         alpha-beta dao sau dan (iterative deepening) + bang chuyen vi Zobrist.

API:  choose_move(grid, col, level, base_score=None, base_moves=None) -> (row, col)
      grid: list[list[str]] voi ' ', 'r', 'w'  (giong ban co cua Finals.py)
"""
import random
import time

EMPTY, BORDER = 0, 3
PAD = 5
NONE, TWO, OPEN2, THREE, OPEN3, FOUR, OPEN4, FIVE = range(8)
WIN = 10 ** 9
INF = 10 ** 12

# --------------------------------------------------------------------------
# Phan loai mau hinh tai 1 o theo 1 huong (chuoi 11 ky tu, o giua = quan vua dat)
#   x = quan minh, o = quan doi thu / bien, _ = trong
# --------------------------------------------------------------------------
_TYPE_PATTERNS = (
    (FIVE, ('xxxxx',)),
    (OPEN4, ('_xxxx_',)),
    (FOUR, ('xxxx_', '_xxxx', 'xxx_x', 'x_xxx', 'xx_xx')),
    (OPEN3, ('__xxx_', '_xxx__', '_xx_x_', '_x_xx_')),
    (THREE, ('xxx__', '__xxx', 'xx_x_', '_x_xx', 'x_xx_', '_xx_x', 'xx__x', 'x__xx', 'x_x_x', '_xxx_')),
    (OPEN2, ('__xx__', '__xx_', '_xx__', '_x_x_', '_x__x_')),
    (TWO, ('xx___', '___xx', 'x_x__', '__x_x', 'x__x_', '_x__x', 'x___x')),
)
_MAPS = {1: ('_', 'x', 'o', 'o'), 2: ('_', 'o', 'x', 'o')}
_OFFS = tuple(range(-5, 6))
_type_cache = {}


def _classify(s):
    t = _type_cache.get(s)
    if t is not None:
        return t
    t = NONE
    for typ, pats in _TYPE_PATTERNS:
        for p in pats:
            L = len(p)
            for st in range(max(0, 6 - L), min(5, 11 - L) + 1):
                if s.startswith(p, st):
                    t = typ
                    break
            if t != NONE:
                break
        if t != NONE:
            break
    _type_cache[s] = t
    return t


# Tra cuu nhanh: chuoi gia tri o (bytes 0..3) -> ky tu theo goc nhin cua tung phe (chay bang C)
_BT = {1: bytes.maketrans(b'\x00\x01\x02\x03', b'_xoo'), 2: bytes.maketrans(b'\x00\x01\x02\x03', b'_oxo')}
_fast_cache = {}


def _classify_key(key):
    """key: bytes 11 ky tu, o giua dang '_' -> coi nhu quan vua dat."""
    t = _fast_cache.get(key)
    if t is None:
        s = key.decode()
        t = _classify(s[:5] + 'x' + s[6:])
        _fast_cache[key] = t
    return t


_TV = (0, 10, 45, 60, 450, 700, 6000, 200000)


def _tval(types):
    """Gia tri chien thuat cua 1 nuoc (dung de sap xep nuoc di)."""
    if FIVE in types:
        return 1000000
    s = 0
    n4 = n3 = 0
    for t in types:
        s += _TV[t]
        if t == FOUR or t == OPEN4:
            n4 += 1
        elif t == OPEN3:
            n3 += 1
    if OPEN4 in types or n4 >= 2:
        s += 60000           # chac thang
    elif n4 and n3:
        s += 25000           # bon - ba
    elif n3 >= 2:
        s += 9000            # ba - ba
    return s


# --------------------------------------------------------------------------
# Danh gia tinh ca ban co theo tung duong (hang/cot/cheo), co cache
# --------------------------------------------------------------------------
_LINE_PATS = (   # (mau, diem, so "bon", so "ba mo")
    ('_xxxx_', 200000, 2, 0),
    ('xxxx_', 9000, 1, 0), ('_xxxx', 9000, 1, 0), ('xxx_x', 9000, 1, 0),
    ('x_xxx', 9000, 1, 0), ('xx_xx', 9000, 1, 0),
    ('__xxx_', 1300, 0, 1), ('_xxx__', 1300, 0, 1), ('_xx_x_', 1100, 0, 1), ('_x_xx_', 1100, 0, 1),
    ('xxx__', 160, 0, 0), ('__xxx', 160, 0, 0), ('xx_x_', 140, 0, 0), ('_x_xx', 140, 0, 0),
    ('x_xx_', 140, 0, 0), ('_xx_x', 140, 0, 0), ('x_x_x', 120, 0, 0), ('xx__x', 110, 0, 0),
    ('x__xx', 110, 0, 0),
    ('__xx__', 120, 0, 0), ('__xx_', 50, 0, 0), ('_xx__', 50, 0, 0), ('_x_x_', 55, 0, 0),
    ('_x__x_', 30, 0, 0),
)
_TRANS = {1: str.maketrans('012', '_xo'), 2: str.maketrans('012', '_ox')}
_line_cache = {}
_CH = ('0', '1', '2', '3')


def _line_eval(key):
    v = _line_cache.get(key)
    if v is not None:
        return v
    res = []
    for p in (1, 2):
        s = 'o' + key.translate(_TRANS[p]) + 'o'
        if 'xxxxx' in s:
            res.append((10 ** 7, 9, 0))
            continue
        sc = f = t = 0
        for pat, w, ff, tt in _LINE_PATS:
            n = s.count(pat)
            if n:
                sc += w * n
                f += ff * n
                t += tt * n
        res.append((sc, f, t))
    v = (res[0], res[1])
    _line_cache[key] = v
    return v


class _Timeout(Exception):
    pass


# --------------------------------------------------------------------------
# ENGINE
# --------------------------------------------------------------------------
class Engine:
    def __init__(self, grid, me):
        n = len(grid)
        W = n + 2 * PAD
        self.n, self.W, self.me = n, W, me
        conv = {' ': 0, 'w': 1, 'r': 2}
        cells = [BORDER] * (W * W)
        self.stones = []
        self.stones_of = {1: [], 2: []}
        for r in range(n):
            for c in range(n):
                i = (r + PAD) * W + c + PAD
                v = conv.get(grid[r][c], 0)
                cells[i] = v
                if v:
                    self.stones.append(i)
                    self.stones_of[v].append(i)
        self.cells = cells
        self.dirs = (1, W, W + 1, W - 1)
        self.dir_offs = [tuple(k * d for k in _OFFS) for d in self.dirs]
        self.near = [dr * W + dc for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc] + \
                    [2 * dr * W + 2 * dc for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
        self.center = ((n // 2) + PAD) * W + (n // 2) + PAD
        rnd = random.Random(20240601)
        self.zob = (None, [rnd.getrandbits(64) for _ in range(W * W)], [rnd.getrandbits(64) for _ in range(W * W)])
        self.hash = 0
        for i in self.stones:
            self.hash ^= self.zob[cells[i]][i]
        # duong de danh gia tinh
        self.line_cells = []
        self.line_of = [[-1] * (W * W) for _ in range(4)]
        for di, d in enumerate(self.dirs):
            for r in range(n):
                for c in range(n):
                    i = (r + PAD) * W + c + PAD
                    if cells[i - d] == BORDER:
                        L = []
                        j = i
                        lid = len(self.line_cells)
                        while cells[j] != BORDER:
                            L.append(j)
                            self.line_of[di][j] = lid
                            j += d
                        self.line_cells.append(L)
        self.line_val = [None] * len(self.line_cells)
        self.S = [0, 0, 0]
        self.F = [0, 0, 0]
        self.T = [0, 0, 0]
        for lid in range(len(self.line_cells)):
            self._update_line(lid)
        self.tt = {}
        self.vcf_fail = {}
        self.vct_fail = {}
        self.deadline = INF
        self.vdeadline = INF
        self.nodes = 0
        self.beam = (12, 8, 6, 5)
        self.max_ply = 12

    # ---------------- toa do
    def idx(self, r, c):
        return (r + PAD) * self.W + c + PAD

    def rc(self, i):
        return i // self.W - PAD, i % self.W - PAD

    # ---------------- cap nhat ban co
    def _update_line(self, lid):
        c = self.cells
        key = ''.join([_CH[c[j]] for j in self.line_cells[lid]])
        new = _line_eval(key)
        old = self.line_val[lid]
        S, F, T = self.S, self.F, self.T
        if old is not None:
            for p in (1, 2):
                sc, f, t = old[p - 1]
                S[p] -= sc
                F[p] -= f
                T[p] -= t
        for p in (1, 2):
            sc, f, t = new[p - 1]
            S[p] += sc
            F[p] += f
            T[p] += t
        self.line_val[lid] = new

    def place(self, i, p):
        self.cells[i] = p
        self.stones.append(i)
        self.stones_of[p].append(i)
        self.hash ^= self.zob[p][i]
        lo = self.line_of
        for di in range(4):
            self._update_line(lo[di][i])

    def undo(self, i, p):
        self.cells[i] = 0
        self.stones.pop()
        self.stones_of[p].pop()
        self.hash ^= self.zob[p][i]
        lo = self.line_of
        for di in range(4):
            self._update_line(lo[di][i])

    # ---------------- mau hinh
    def types_at(self, i, p):
        c = self.cells
        bt = _BT[p]
        fc = _fast_cache
        out = []
        for offs in self.dir_offs:
            key = bytes([c[i + o] for o in offs]).translate(bt)
            t = fc.get(key)
            out.append(t if t is not None else _classify_key(key))
        return out

    def types_both(self, i):
        """Mau hinh tai o i cho ca 2 phe (doc ban co 1 lan)."""
        c = self.cells
        b1, b2 = _BT[1], _BT[2]
        fc = _fast_cache
        t1, t2 = [], []
        for offs in self.dir_offs:
            raw = bytes([c[i + o] for o in offs])
            k1 = raw.translate(b1)
            k2 = raw.translate(b2)
            a = fc.get(k1)
            b = fc.get(k2)
            t1.append(a if a is not None else _classify_key(k1))
            t2.append(b if b is not None else _classify_key(k2))
        return t1, t2

    def type_dir(self, i, p, d):
        c = self.cells
        m = _MAPS[p]
        c[i] = p
        t = _classify(''.join([m[c[i + k * d]] for k in _OFFS]))
        c[i] = 0
        return t

    def candidates(self):
        c = self.cells
        out = set()
        for s in self.stones:
            for o in self.near:
                j = s + o
                if c[j] == 0:
                    out.add(j)
        return out

    def ordered(self, p, jitter=0.0):
        res = []
        for i in self.candidates():
            t1, t2 = self.types_both(i)
            ta, td = (t1, t2) if p == 1 else (t2, t1)
            sc = _tval(ta) + 0.9 * _tval(td)
            if jitter:
                sc += random.random() * jitter
            res.append((sc, i, ta, td))
        res.sort(key=lambda x: -x[0])
        return res

    def threat_cells(self, p):
        """(fives, fours): o trong ma p dat vao se thanh 5 / thanh 4."""
        c = self.cells
        fives, fours = set(), set()
        seen = set()
        for s in self.stones_of[p]:
            for d in self.dirs:
                for st in range(-4, 1):
                    base = s + st * d
                    if (base, d) in seen:
                        continue
                    seen.add((base, d))
                    cnt = 0
                    emp = []
                    ok = True
                    for k in range(5):
                        j = base + k * d
                        v = c[j]
                        if v == p:
                            cnt += 1
                        elif v == 0:
                            emp.append(j)
                        else:
                            ok = False
                            break
                    if not ok:
                        continue
                    if cnt == 4:
                        fives.update(emp)
                    elif cnt == 3:
                        fours.update(emp)
        return fives, fours - fives

    def fives_through(self, m, p):
        c = self.cells
        out = set()
        for d in self.dirs:
            for st in range(-4, 1):
                base = m + st * d
                cnt = 0
                emp = None
                ok = True
                for k in range(5):
                    j = base + k * d
                    v = c[j]
                    if v == p:
                        cnt += 1
                    elif v == 0:
                        if emp is not None:
                            ok = False
                            break
                        emp = j
                    else:
                        ok = False
                        break
                if ok and cnt == 4 and emp is not None:
                    out.add(emp)
        return out

    def open4_points_near(self, m, p, d=None):
        """O trong gan m ma p dat vao tao bon mo (= p dang co ba mo qua m)."""
        c = self.cells
        out = set()
        for dd in ((d,) if d else self.dirs):
            for k in range(-5, 6):
                j = m + k * dd
                if c[j] == 0 and self.type_dir(j, p, dd) == OPEN4:
                    out.add(j)
        return out

    # ---------------- danh gia tinh
    def evaluate(self, p):
        o = 3 - p
        F, T, S = self.F, self.T, self.S
        if F[p] > 0:
            return WIN // 10
        if F[o] >= 2:
            return -WIN // 10
        if T[p] > 0 and F[o] == 0:
            return WIN // 20
        return int(S[p] * 1.15 - S[o])

    # ---------------- VCF: thang bang chuoi "bon" lien tiep
    def vcf(self, p, depth):
        if time.perf_counter() > self.vdeadline:
            raise _Timeout
        o = 3 - p
        key = (self.hash, p)
        if self.vcf_fail.get(key, -1) >= depth:
            return None
        myF, myFours = self.threat_cells(p)
        if myF:
            return next(iter(myF))
        if depth <= 0:
            return None
        opF, _ = self.threat_cells(o)
        if len(opF) >= 2:
            self.vcf_fail[key] = depth
            return None
        if opF:
            b = next(iter(opF))
            cand = [b] if b in myFours else []
        else:
            cand = sorted(myFours, key=lambda i: -_tval(self.types_at(i, p)))
        for m in cand:
            self.place(m, p)
            f = self.fives_through(m, p)
            if len(f) >= 2:
                self.undo(m, p)
                return m
            if len(f) == 1:
                d = next(iter(f))
                self.place(d, o)
                try:
                    r = self.vcf(p, depth - 1)
                finally:
                    self.undo(d, o)
                if r is not None:
                    self.undo(m, p)
                    return m
            self.undo(m, p)
        self.vcf_fail[key] = depth
        return None

    def try_vcf(self, p, depth, budget):
        self.vdeadline = min(time.perf_counter() + budget, self.deadline)
        try:
            return self.vcf(p, depth)
        except _Timeout:
            return None
        finally:
            self.vdeadline = INF

    # ---------------- VCT: chuoi de doa (ba mo / bon) ep thang
    def _line_defenses(self, m, p, d):
        c = self.cells
        out = []
        for k in range(-4, 5):
            e = m + k * d
            if c[e] != 0:
                continue
            c[e] = 3 - p
            still = False
            for k2 in range(-5, 6):
                j = m + k2 * d
                if c[j] == 0 and self.type_dir(j, p, d) == OPEN4:
                    still = True
                    break
            c[e] = 0
            if not still:
                out.append(e)
        return out

    def vct(self, p, depth):
        if time.perf_counter() > self.vdeadline:
            raise _Timeout
        o = 3 - p
        r = self.vcf(p, 8)
        if r is not None:
            return r
        if depth <= 0:
            return None
        key = (self.hash, p)
        if self.vct_fail.get(key, -1) >= depth:
            return None
        opF, opFours = self.threat_cells(o)
        if opF:
            if len(opF) >= 2:
                return None
            b = next(iter(opF))
            self.place(b, p)
            try:
                r = self.vct(p, depth - 1)
            finally:
                self.undo(b, p)
            return b if r is not None else None
        # doi thu dang co ba mo -> khong the tan cong bang ba
        for s in self.stones_of[o][-3:]:
            if self.open4_points_near(s, o):
                self.vct_fail[key] = depth
                return None
        cands = []
        for i in self.candidates():
            ta = self.types_at(i, p)
            if OPEN3 in ta:
                cands.append((_tval(ta), i, ta))
        cands.sort(key=lambda x: -x[0])
        for _, m, ta in cands[:7]:
            self.place(m, p)
            try:
                defs = set()
                for di, d in enumerate(self.dirs):
                    if ta[di] == OPEN3:
                        defs.update(self._line_defenses(m, p, d))
                _, oF4 = self.threat_cells(o)
                defs |= oF4
                all_win = True
                for d in defs:
                    self.place(d, o)
                    try:
                        r = self.vct(p, depth - 1)
                    finally:
                        self.undo(d, o)
                    if r is None:
                        all_win = False
                        break
            finally:
                self.undo(m, p)
            if all_win and defs:
                return m
        self.vct_fail[key] = depth
        return None

    def try_vct(self, p, depth, budget):
        self.vdeadline = min(time.perf_counter() + budget, self.deadline)
        try:
            return self.vct(p, depth)
        except _Timeout:
            return None
        finally:
            self.vdeadline = INF

    # ---------------- Alpha-beta (negamax) co nuoc ep
    def _gen(self, p, ply, tt_move=None):
        """Sinh nuoc: tra ve ('win'|'lose'|None, moves, forced)"""
        o = 3 - p
        myF, _ = self.threat_cells(p)
        if myF:
            return 'win', [next(iter(myF))], True
        opF, _ = self.threat_cells(o)
        if len(opF) >= 2:
            return 'lose', [next(iter(opF))], True
        if opF:
            return None, [next(iter(opF))], True
        scored = self.ordered(p)
        if not scored:
            return None, [], False
        for sc, i, ta, td in scored[:4]:
            if OPEN4 in ta or (ta.count(FOUR) + ta.count(OPEN4)) >= 2:
                return 'win2', [i], True
        opp_open = {i for sc, i, ta, td in scored if OPEN4 in td}
        if opp_open:
            moves = [i for sc, i, ta, td in scored if i in opp_open or FOUR in ta]
        else:
            k = self.beam[min(ply, len(self.beam) - 1)]
            moves = [i for sc, i, ta, td in scored[:k]]
        if tt_move is not None and tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)
        return None, moves, False

    def search(self, p, depth, alpha, beta, ply):
        self.nodes += 1
        if (self.nodes & 63) == 0 and time.perf_counter() > self.deadline:
            raise _Timeout
        o = 3 - p
        if depth <= 0 or ply >= self.max_ply:
            # chi kiem tra nhanh: con nuoc 5 ngay?
            if self.F[p] > 0:
                return WIN - ply
            return self.evaluate(p)
        key = (self.hash, p)
        ent = self.tt.get(key)
        tt_move = None
        if ent is not None:
            e_depth, e_val, e_flag, tt_move = ent
            if e_depth >= depth:
                if e_flag == 0:
                    return e_val
                if e_flag == 1 and e_val >= beta:
                    return e_val
                if e_flag == -1 and e_val <= alpha:
                    return e_val
        status, moves, forced = self._gen(p, ply, tt_move)
        if status == 'win':
            return WIN - ply
        if status == 'lose':
            return -(WIN - ply - 1)
        if status == 'win2':
            return WIN - ply - 2
        if not moves:
            return 0
        a0 = alpha
        best, best_m = -INF, moves[0]
        nd = depth if (forced and ply < self.max_ply - 2) else depth - 1
        for m in moves:
            self.place(m, p)
            try:
                v = -self.search(o, nd, -beta, -alpha, ply + 1)
            finally:
                self.undo(m, p)
            if v > best:
                best, best_m = v, m
            if v > alpha:
                alpha = v
            if alpha >= beta:
                break
        flag = 0 if a0 < best < beta else (1 if best >= beta else -1)
        self.tt[key] = (depth, best, flag, best_m)
        return best

    def root_search(self, p, root_moves, max_depth, budget):
        self.deadline = time.perf_counter() + budget
        o = 3 - p
        best = root_moves[0]
        order = list(root_moves)
        for depth in range(1, max_depth + 1):
            try:
                alpha = -INF
                vals = []
                cur = order[0]
                for m in order:
                    self.place(m, p)
                    try:
                        v = -self.search(o, depth - 1, -INF, -alpha, 1)
                    finally:
                        self.undo(m, p)
                    vals.append((v, m))
                    if v > alpha:
                        alpha, cur = v, m
                best = cur
                vals.sort(key=lambda x: -x[0])
                order = [m for v, m in vals]
                if alpha >= WIN - 100 or alpha <= -(WIN - 100):
                    break
            except _Timeout:
                break
        self.deadline = INF
        return best


# --------------------------------------------------------------------------
# CAC MUC DO
# --------------------------------------------------------------------------
def _opening(eng):
    n = eng.n
    if not eng.stones:
        c = n // 2
        return c, c
    if len(eng.stones) == 1:
        r, c = eng.rc(eng.stones[0])
        opts = [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr or dc)
                and 0 <= r + dr < n and 0 <= c + dc < n]
        # uu tien o huong vao tam ban
        mid = (n - 1) / 2
        opts.sort(key=lambda rc: (rc[0] - mid) ** 2 + (rc[1] - mid) ** 2)
        return random.choice(opts[:3])
    return None


def _tactical(eng, p):
    """Cac nuoc bat buoc. Tra ve (move|None, scored, opp_open_points)."""
    o = 3 - p
    myF, _ = eng.threat_cells(p)
    if myF:
        return next(iter(myF)), None, None
    opF, _ = eng.threat_cells(o)
    if opF:
        return next(iter(opF)), None, None
    scored = eng.ordered(p)
    for sc, i, ta, td in scored:
        if OPEN4 in ta or (ta.count(FOUR) + ta.count(OPEN4)) >= 2:
            return i, scored, None
    opp_open = [i for sc, i, ta, td in scored if OPEN4 in td]
    return None, scored, opp_open


def _normal(grid, col, base_score, base_moves):
    me = 1 if col == 'w' else 2
    eng = Engine(grid, me)
    op = _opening(eng)
    if op:
        return op
    mv, scored, opp_open = _tactical(eng, me)
    if mv is not None:
        return eng.rc(mv)
    anticol = 'r' if col == 'w' else 'w'
    work = [row[:] for row in grid]
    me_ = me
    if base_score is None:   # du phong neu khong co ham goc
        base_score = lambda b, c1, c2, y, x: dict((eng.rc(x_[1]), x_[0]) for x_ in scored).get((y, x), 0)
    if opp_open:
        # doi thu co ba mo: chan, hoac phan cong bang bon
        allowed = {i for sc, i, ta, td in scored if i in set(opp_open) or FOUR in ta}
        moves = [eng.rc(i) for i in allowed]
    else:
        moves = list(base_moves(work)) if base_moves else [eng.rc(i) for sc, i, ta, td in scored]
    # xep hang bang heuristic GOC (stupid_score)
    ranked = sorted(((base_score(work, col, anticol, y, x), random.random(), (y, x)) for (y, x) in moves),
                    reverse=True)
    # nhin truoc 1 buoc: bo nuoc khien doi thu co chuoi "bon" ep thang (VCF)
    deadline = time.perf_counter() + 0.35
    for s, _, (y, x) in ranked[:6]:
        if time.perf_counter() > deadline:
            break
        i = eng.idx(y, x)
        eng.place(i, me_)
        try:
            bad = eng.try_vcf(3 - me_, 10, 0.06) is not None
        finally:
            eng.undo(i, me_)
        if not bad:
            return (y, x)
    return ranked[0][2]


def _search_level(grid, col, level):
    me = 1 if col == 'w' else 2
    op_ = 3 - me
    eng = Engine(grid, me)
    op = _opening(eng)
    if op:
        return op
    t_start = time.perf_counter()
    expert = (level == 'expert')
    budget = 1.8 if expert else 0.6      # tong thoi gian suy nghi toi da (giay)
    mv, scored, opp_open = _tactical(eng, me)
    if mv is not None:
        return eng.rc(mv)
    if not scored:
        return None
    # 1) tu tim chuoi ep thang
    v = eng.try_vcf(me, 16 if expert else 10, 0.25 if expert else 0.12)
    if v is not None:
        return eng.rc(v)
    if expert and not opp_open:
        v = eng.try_vct(me, 3, 0.3)
        if v is not None:
            return eng.rc(v)
    # 2) cac nuoc goc
    if opp_open:
        root = [i for sc, i, ta, td in scored if i in set(opp_open) or FOUR in ta]
    else:
        root = [i for sc, i, ta, td in scored[:16 if expert else 12]]
    # 3) loai nuoc de doi thu co chuoi ep thang: VCF (kho + cuc kho), VCT (cuc kho)
    if len(root) > 1:
        safe = []
        lim = time.perf_counter() + (0.35 if expert else 0.18)
        for m in root:
            if time.perf_counter() > lim:
                safe.append(m)
                continue
            eng.place(m, me)
            try:
                bad = eng.try_vcf(op_, 16 if expert else 12, 0.05) is not None
            finally:
                eng.undo(m, me)
            if not bad:
                safe.append(m)
        if safe:
            root = safe
    if expert and len(root) > 1:
        safe = []
        lim = time.perf_counter() + 0.35
        for m in root[:8]:
            if time.perf_counter() > lim:
                safe.append(m)
                continue
            eng.place(m, me)
            try:
                bad = eng.try_vct(op_, 2, 0.06) is not None
            finally:
                eng.undo(m, me)
            if not bad:
                safe.append(m)
        if safe:
            root = safe + [m for m in root[8:]]
    if len(root) == 1:
        return eng.rc(root[0])
    # 4) alpha-beta dao sau dan
    if expert:
        eng.beam = (16, 12, 10, 8, 7, 6, 5, 5, 4, 4, 4, 4)
        eng.max_ply = 18
        max_depth = 12
    else:
        eng.beam = (10, 8, 6, 5, 4, 4)
        eng.max_ply = 10
        max_depth = 6
    remain = max(0.15, budget - (time.perf_counter() - t_start))
    best = eng.root_search(me, root, max_depth, remain)
    return eng.rc(best)


def choose_move(grid, col, level, base_score=None, base_moves=None):
    """Tra ve (row, col) cho phe `col` ('w' hoac 'r')."""
    if level == 'normal':
        return _normal(grid, col, base_score, base_moves)
    return _search_level(grid, col, level)
