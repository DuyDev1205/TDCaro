# -*- coding: utf-8 -*-
"""
Soan nhac nen lo-fi cho TDCaro -> assets/music/*.ogg

100% tu tong hop bang code (khong dung mau / nhac co ban quyen). Moi bai gom:
  - hop am jazz mau (maj9, m9, 13) tren piano dien FM / pad / guitar nylon
  - bass tron, trong boom-bap swing "lui nhip" kieu lo-fi, sidechain nhe
  - giai dieu phat trien tu motif (lap lai + bien tau) tren thang ngu cung
  - "chat" lo-fi: bang cassette cao/chao (wow & flutter), loc am, bao hoa,
    tieng dia than, mua / song bien, vang (reverb) tong hop

Can (chi cho cong cu nay, KHONG dong goi vao game):
    pip install numpy soundfile
Chay:
    python tools/make_music.py
"""
import math
import os
import random

import numpy as np
import soundfile as sf

SR = 32000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'assets', 'music')


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def tvec(sec):
    return np.arange(int(sec * SR)) / SR


# ------------------------------------------------------------------ DSP
def fft_filter(x, lp=None, hp=None, order=2):
    """Loc pha-0 bang FFT (tren ca bai -> khong tre pha)."""
    n = x.shape[-1]
    F = np.fft.rfft(x, axis=-1)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = np.ones_like(f)
    if lp:
        H /= np.sqrt(1 + (f / lp) ** (2 * order))
    if hp:
        r = (f / hp) ** order
        H *= r / np.sqrt(1 + r * r)
    return np.fft.irfft(F * H, n=n, axis=-1)


def fft_conv(x, ir):
    n = x.shape[-1] + ir.shape[-1]
    size = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)
    return y[:x.shape[-1]]


def reverb(st, rng, secs=2.4, lp=3800, predelay=0.025):
    """Vang tong hop: nhieu suy giam theo ham mu, rieng moi kenh -> rong."""
    n = int(secs * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-6.9 * t / secs)
    ir = fft_filter(ir, lp=lp, hp=200)
    ir[:, :int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    ir = np.concatenate([np.zeros((2, int(predelay * SR))), ir], axis=1)
    ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    mid = st.mean(axis=0)
    return np.stack([fft_conv(mid, ir[0]), fft_conv(mid, ir[1])])


def wow_flutter(st, rng, depth_ms=3.2, flutter_ms=0.22):
    """Bang cassette: toc do chao cham (wow) + rung nhanh (flutter) -> cao do lung lay nhe."""
    n = st.shape[-1]
    t = np.arange(n) / SR
    ph = rng.uniform(0, 6.28, 3)
    slow = (0.65 * np.sin(2 * np.pi * 0.31 * t + ph[0]) + 0.35 * np.sin(2 * np.pi * 0.53 * t + ph[1]))
    off = depth_ms / 1000 * slow + flutter_ms / 1000 * np.sin(2 * np.pi * 5.7 * t + ph[2])
    src = np.clip((t - off - depth_ms / 1000) * SR, 0, n - 1)
    idx = np.arange(n)
    return np.stack([np.interp(src, idx, st[c]) for c in range(st.shape[0])])


def smooth_noise(n, rng, rate_hz):
    """Nhieu tron (bien thien cham) trong khoang ~[-1, 1]."""
    k = max(2, int(n / SR * rate_hz) + 2)
    pts = rng.uniform(-1, 1, k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)


# ------------------------------------------------------------------ nhac cu
def ep(m, dur, vel):
    """Piano dien kieu Rhodes (FM ti le 1:1, chi so dieu che giam dan) + tieng 'tine'."""
    f = midi(m)
    t = tvec(dur + 1.6)
    idx = (0.6 + 1.6 * vel) * np.exp(-t * 3.2) + 0.12
    car = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    tine = 0.10 * np.sin(2 * np.pi * f * 7.1 * t) * np.exp(-t * 22)
    amp = np.exp(-t * 0.85) * np.minimum(1, t / 0.005)
    rel = np.where(t < dur, 1.0, np.exp(-(t - dur) * 5.5))
    trem = 1 + 0.07 * np.sin(2 * np.pi * 4.3 * t)
    return (car + tine) * amp * rel * trem * vel


def pad(m, dur, vel):
    """Pad am: 3 giong lech nhe, it hoa am, vao/ra cham."""
    f = midi(m)
    t = tvec(dur + 2.2)
    out = np.zeros_like(t)
    for cents, ph in ((-7, 0.3), (0, 1.7), (6, 4.1)):
        fr = f * 2 ** (cents / 1200)
        for k in range(1, 6):
            if fr * k < SR / 2.3:
                out += np.sin(2 * np.pi * fr * k * t + ph * k) / (k ** 1.6)
    att = np.clip(t / 1.1, 0, 1) ** 2
    rel = np.where(t < dur, 1.0, np.exp(-(t - dur) * 2.2))
    return out * att * rel * vel / 3


def nylon(m, dur, vel):
    """Guitar nylon gay: hoa am tat nhanh dan theo bac."""
    f = midi(m)
    L = min(dur + 1.2, 2.2)
    t = tvec(L)
    out = np.zeros_like(t)
    for k in range(1, 9):
        fk = f * k * (1 + 0.0003 * k * k)
        if fk > SR / 2.2:
            break
        out += np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.6 + 0.55 * k * k)) / k ** 1.2
    att = np.minimum(1, t / 0.003)
    rel = np.where(t < dur, 1.0, np.exp(-(t - dur) * 7))
    return out * att * rel * vel


def bell(m, dur, vel):
    """Kalimba / hop nhac: hoa am le (khong dieu hoa), tat em."""
    f = midi(m)
    t = tvec(dur + 2.5)
    out = (np.sin(2 * np.pi * f * t) * np.exp(-t * 1.9)
           + 0.22 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
           + 0.07 * np.sin(2 * np.pi * f * 5.40 * t) * np.exp(-t * 13))
    return out * np.minimum(1, t / 0.002) * vel


def lead_ep(m, dur, vel):
    return ep(m, dur, vel) * 0.9


def bass(m, dur, vel):
    f = midi(m)
    t = tvec(dur + 0.25)
    out = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t) + 0.06 * np.sin(6 * np.pi * f * t)
    amp = np.exp(-t * 0.7) * np.minimum(1, t / 0.008)
    rel = np.where(t < dur, 1.0, np.exp(-(t - dur) * 25))
    return np.tanh(out * 1.2) * amp * rel * vel


def kick(rng, vel):
    t = tvec(0.5)
    f = 46 + 85 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.15
    return np.tanh((body + click) * 1.6) * vel


def snare(rng, vel):
    t = tvec(0.4)
    nz = fft_filter(rng.standard_normal(len(t)), lp=4200, hp=350) * np.exp(-t * 17)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 28) * 0.45
    return (nz * 0.9 + tone) * vel


def rim(rng, vel):
    t = tvec(0.12)
    return (np.sin(2 * np.pi * 1650 * t) * np.exp(-t * 70)
            + 0.4 * rng.standard_normal(len(t)) * np.exp(-t * 160)) * vel


def hat(rng, vel, open_=False):
    t = tvec(0.35 if open_ else 0.08)
    nz = fft_filter(rng.standard_normal(len(t)), hp=6500, lp=11000)
    return nz * np.exp(-t * (13 if open_ else 75)) * vel


def shaker(rng, vel):
    t = tvec(0.12)
    nz = fft_filter(rng.standard_normal(len(t)), hp=3500, lp=9000)
    env = np.minimum(1, t / 0.018) * np.exp(-t * 38)
    return nz * env * vel


INSTR = {'ep': ep, 'pad': pad, 'nylon': nylon, 'bell': bell, 'lead_ep': lead_ep}


# ------------------------------------------------------------------ bai hat
class Song:
    def __init__(self, cfg):
        self.cfg = cfg
        self.bpm = cfg['bpm']
        self.beat = 60.0 / self.bpm
        self.bar = 4 * self.beat
        self.bars = cfg['bars']
        self.length = self.bars * self.bar
        self.N = int((self.length + 3.5) * SR)
        self.rng = np.random.default_rng(cfg['seed'])
        self.r = random.Random(cfg['seed'])
        self.buses = {}
        self.kicks = []

    def bus(self, name):
        if name not in self.buses:
            self.buses[name] = np.zeros((2, self.N))
        return self.buses[name]

    def add(self, name, t0, sig, pan=0.0, gain=1.0):
        b = self.bus(name)
        i0 = int(round(t0 * SR))
        if i0 < 0:
            sig, i0 = sig[-i0:], 0
        n = min(len(sig), self.N - i0)
        if n <= 0:
            return
        a = (pan + 1) * math.pi / 4
        b[0, i0:i0 + n] += sig[:n] * math.cos(a) * math.sqrt(2) * gain
        b[1, i0:i0 + n] += sig[:n] * math.sin(a) * math.sqrt(2) * gain

    def hum(self, ms=9):
        return self.r.gauss(0, ms / 1000)

    def swing(self, eighth):
        """Vi tri not moc den theo phach, co swing kieu lo-fi."""
        return eighth * 0.5 + (self.cfg.get('swing', 0.09) if eighth % 2 else 0.0)

    # ---- hop am theo tung nhip: list (so phach, bass, voicing)
    def chords_at(self, bar):
        prog = self.cfg['prog_b'] if (self.cfg.get('prog_b') and 12 <= bar < 20) else self.cfg['prog']
        return prog[bar % len(prog)]

    def chord_at_time(self, bar, beat):
        acc = 0.0
        for beats, root, voicing in self.chords_at(bar):
            if beat < acc + beats:
                return root, voicing
            acc += beats
        return self.chords_at(bar)[-1][1:]

    # ---- cac lop
    def comp(self):
        cfg = self.cfg
        inst = cfg['comp']
        for bar in range(self.bars):
            t_bar = bar * self.bar
            beat0 = 0.0
            for beats, root, voicing in self.chords_at(bar):
                t0 = t_bar + beat0 * self.beat
                dur = beats * self.beat
                if inst == 'pad':
                    for m in voicing:
                        self.add('chords', t0, pad(m, dur, 0.09), pan=self.r.uniform(-0.4, 0.4))
                elif inst == 'ep':
                    lag = self.r.choice((0.0, 0.0, self.beat * 0.5 * -1)) if beat0 == 0 and bar % 4 == 0 else 0.0
                    for k, m in enumerate(voicing):
                        v = 0.13 * self.r.uniform(0.85, 1.05)
                        self.add('chords', t0 + lag + k * 0.014 + self.hum(6), ep(m, dur * 0.9, v), pan=-0.15 + 0.1 * k)
                    if beats >= 4 and self.r.random() < 0.7:          # nhac lai nhe o "va" cua phach 2
                        t1 = t0 + self.swing(3) * self.beat
                        for k, m in enumerate(voicing[1:]):
                            self.add('chords', t1 + k * 0.01, ep(m, self.beat * 1.2, 0.06), pan=0.1)
                elif inst == 'nylon':
                    tones = list(voicing) + [voicing[1] + 12, voicing[2] + 12]
                    order = [0, 2, 1, 3, 4, 3, 5, 2]
                    for e in range(int(beats * 2)):
                        m = tones[order[e % len(order)] % len(tones)]
                        st = t0 + self.swing(e) * self.beat + self.hum(7)
                        self.add('chords', st, nylon(m, self.beat * 0.9, 0.16 * self.r.uniform(0.75, 1.0)),
                                 pan=0.25 + self.r.uniform(-0.1, 0.1))
                beat0 += beats
            if cfg.get('pad_under'):
                for beats, root, voicing in [self.chords_at(bar)[0]]:
                    for m in voicing[:3]:
                        self.add('pad', t_bar, pad(m - 12 if m > 60 else m, self.bar, 0.05), pan=self.r.uniform(-0.6, 0.6))

    def bassline(self):
        start, end = self.cfg['drums_from'], self.bars - 1
        for bar in range(start, end):
            t_bar = bar * self.bar
            beat0 = 0.0
            for beats, root, voicing in self.chords_at(bar):
                t0 = t_bar + beat0 * self.beat
                self.add('bass', t0 + self.hum(5), bass(root, min(beats, 2.5) * self.beat * 0.95, 0.42))
                if beats >= 4:
                    if self.r.random() < 0.6:
                        self.add('bass', t0 + self.swing(5) * self.beat, bass(root + 12, self.beat * 0.4, 0.22))
                    nxt = self.chords_at(bar + 1)[0][1]
                    appr = nxt + (1 if self.r.random() < 0.5 else -2)
                    self.add('bass', t0 + self.swing(7) * self.beat, bass(appr, self.beat * 0.35, 0.25))
                beat0 += beats

    def drums(self):
        style = self.cfg['drums']
        start = self.cfg['drums_from']
        stop = self.bars - 2
        rng = self.rng
        for bar in range(start, stop):
            t_bar = bar * self.bar
            fill = (bar % 4 == 3)
            if style == 'boombap':
                kicks = [0.0, 2.5] + ([1.75] if self.r.random() < 0.45 else []) + ([3.75] if fill else [])
                for b in kicks:
                    tk = t_bar + b * self.beat + self.hum(4)
                    self.kicks.append(tk)
                    self.add('drums', tk, kick(rng, 0.55 if b in (0.0, 2.5) else 0.38))
                for b in (1, 3):                                  # snare hoi tre nhip -> "luoi"
                    self.add('drums', t_bar + b * self.beat + 0.018 + self.hum(4), snare(rng, 0.30))
                if self.r.random() < 0.5:
                    self.add('drums', t_bar + 3.75 * self.beat, snare(rng, 0.08))   # not ma
                for e in range(8):
                    if e == 7 and fill:
                        self.add('drums', t_bar + self.swing(e) * self.beat, hat(rng, 0.10, True), pan=0.3)
                        continue
                    v = 0.12 if e % 2 == 0 else 0.07
                    self.add('drums', t_bar + self.swing(e) * self.beat + self.hum(5), hat(rng, v), pan=0.3)
            else:   # 'soft': kick em + rim + shaker
                for b in (0.0, 2.5):
                    tk = t_bar + b * self.beat + self.hum(4)
                    self.kicks.append(tk)
                    self.add('drums', tk, kick(rng, 0.42))
                for b in (1, 3):
                    self.add('drums', t_bar + b * self.beat + 0.015, rim(rng, 0.10), pan=-0.2)
                for e in range(8):
                    self.add('drums', t_bar + self.swing(e) * self.beat + self.hum(6),
                             shaker(rng, 0.07 if e % 2 else 0.10), pan=0.35)

    def melody(self):
        cfg = self.cfg
        lo, hi = cfg['mel_range']
        scale = [m for m in range(lo, hi + 1) if m % 12 in cfg['scale']]
        inst = INSTR[cfg['lead']]
        pool = [
            [(0, 1.0), (1.5, 0.5), (2, 1.5)],
            [(0.5, 0.5), (1, 1.0), (2.5, 1.5)],
            [(0, 1.5), (2, 0.5), (2.5, 0.5), (3, 1.0)],
            [(1, 2.0), (3, 1.0)],
            [(0, 0.5), (0.5, 0.5), (1, 2.5)],
            [(0, 3.0)],
        ]
        r = self.r

        def new_motif():
            rhythm = [r.choice(pool[:5]), r.choice(pool[3:])]
            steps = [r.choice((-2, -1, -1, 1, 1, 2, 0)) for _ in range(sum(len(x) for x in rhythm))]
            return rhythm, steps

        def realize(bar0, motif, anchor):
            rhythm, steps = motif
            idx = min(range(len(scale)), key=lambda i: abs(scale[i] - anchor))
            k = 0
            for bi, bar_r in enumerate(rhythm):
                bar = bar0 + bi
                for pos, dur in bar_r:
                    idx = max(0, min(len(scale) - 1, idx + steps[k]))
                    k += 1
                    root, voicing = self.chord_at_time(bar, pos)
                    pcs = {x % 12 for x in voicing} | {root % 12}
                    if float(pos).is_integer() and scale[idx] % 12 not in pcs:   # phach manh -> not hop am
                        for d in (1, -1, 2, -2):
                            j = idx + d
                            if 0 <= j < len(scale) and scale[j] % 12 in pcs:
                                idx = j
                                break
                    eighth = int(pos * 2)
                    st = bar * self.bar + (self.swing(eighth) if pos * 2 == eighth else pos) * self.beat + self.hum(10)
                    v = 0.17 * r.uniform(0.8, 1.0) * (1.0 if float(pos).is_integer() else 0.85)
                    self.add('lead', st, inst(scale[idx], dur * self.beat * 0.95, v), pan=0.12)

        a, b = new_motif(), new_motif()
        anchor = (lo + hi) // 2
        plan = cfg.get('mel_plan', [(12, a), (14, a), (16, b), (18, a)])
        for bar0, motif in plan:
            realize(bar0, motif, anchor + r.choice((-2, 0, 2)))

    def textures(self):
        n = self.N
        rng = self.rng
        tex = np.zeros((2, n))
        # dia than: tieng xi + lach tach
        tex += fft_filter(rng.standard_normal((2, n)), lp=5000, hp=900) * 0.006
        crack = np.zeros((2, n))
        cnt = int(self.length * 9)
        pos = rng.integers(0, n - 64, cnt)
        amp = rng.lognormal(-4.4, 0.7, cnt) * rng.choice((-1, 1), cnt)
        ch = rng.integers(0, 2, cnt)
        shape = np.exp(-np.arange(48) / 5.0)
        for p, a, c in zip(pos, amp, ch):
            crack[c, p:p + 48] += a * shape
        tex += fft_filter(crack, hp=1200, lp=7000)
        amb = self.cfg.get('ambience')
        if amb == 'rain':
            f = np.fft.rfftfreq(n, 1 / SR)
            spec = np.fft.rfft(rng.standard_normal((2, n)), axis=-1) / np.sqrt(np.maximum(f, 20))
            rain = np.fft.irfft(spec, n=n, axis=-1)
            rain = fft_filter(rain, hp=350, lp=6500)
            rain /= np.abs(rain).max()
            rain *= 0.85 + 0.15 * smooth_noise(n, rng, 0.2)
            tex += rain * 0.10
            drops = np.zeros((2, n))
            td = tvec(0.012)
            for _ in range(int(self.length * 22)):
                p = rng.integers(0, n - len(td))
                fr = rng.uniform(2500, 6500)
                drops[rng.integers(0, 2), p:p + len(td)] += np.sin(2 * np.pi * fr * td) * np.exp(-td * 450) * rng.uniform(0.004, 0.018)
            tex += drops
        elif amb == 'waves':
            base = fft_filter(rng.standard_normal((2, n)), lp=1800, hp=120)
            base /= np.abs(base).max()
            t = np.arange(n) / SR
            swell = (0.5 + 0.5 * np.sin(2 * np.pi * t / 9.5 + 0.7 * smooth_noise(n, rng, 0.05))) ** 2
            tex += base * swell * 0.16
        self.bus('tex')[:] += tex

    # ---- tron & master
    def render(self):
        self.comp()
        self.bassline()
        self.drums()
        self.melody()
        self.textures()
        n, rng = self.N, self.rng
        t = np.arange(n) / SR
        # sidechain: hop am "tho" theo tieng kick
        sc = np.ones(n)
        for tk in self.kicks:
            i0 = int(tk * SR)
            seg = t[i0:i0 + int(0.5 * SR)] - tk
            sc[i0:i0 + len(seg)] *= 1 - 0.28 * np.exp(-seg / 0.16)
        g = self.cfg['gains']
        chords = self.bus('chords') * sc * g['chords'] + self.bus('pad') * sc * g.get('pad', 1.0)
        lead = self.bus('lead') * g['lead']
        # vang cham doi cho giai dieu (bong ban trai/phai)
        d = int(self.beat * 0.75 * SR)
        echo = np.zeros_like(lead)
        for tap, gg in ((1, 0.30), (2, 0.16), (3, 0.08)):
            sh = np.zeros_like(lead)
            sh[:, d * tap:] = lead[:, :-d * tap]
            if tap % 2:
                sh = sh[::-1]                 # dao kenh trai/phai -> vang "bong ban"
            echo += sh * gg
        lead = lead + fft_filter(echo, lp=3000)
        drums = fft_filter(self.bus('drums'), lp=7000) * g['drums']
        bass_b = fft_filter(self.bus('bass'), lp=900) * g['bass']
        music = chords + lead + bass_b
        wet = reverb(chords + lead + drums * 0.15, rng, secs=self.cfg.get('verb', 2.4))
        music = music + wet * self.cfg.get('verb_mix', 0.30)
        music = wow_flutter(music, rng, depth_ms=self.cfg.get('wow', 3.2))
        music = music + drums                                   # trong khong chao theo bang
        # mo dau: loc toi dan sang (intro "nghe qua tuong")
        intro = self.cfg['drums_from'] * self.bar
        dark = fft_filter(music, lp=700)
        k = np.clip(t / max(0.1, intro), 0, 1) ** 1.5
        music = dark * (1 - k) + music * k
        mix = music + self.bus('tex') * g['tex']
        # master: am, nen mem, bao hoa nhe
        mix = fft_filter(mix, lp=self.cfg.get('master_lp', 6500), hp=35)
        mix /= np.sqrt(np.mean(mix ** 2)) / 10 ** (-19 / 20)       # RMS ~ -19 dBFS
        mix = np.tanh(mix * 1.15) / 1.15
        # cat & fade
        L = int((self.length + 2.5) * SR)
        mix = mix[:, :L]
        fi, fo = int(1.5 * SR), int(5.0 * SR)
        mix[:, :fi] *= np.linspace(0, 1, fi) ** 2
        mix[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
        peak = np.abs(mix).max()
        if peak > 0.97:
            mix *= 0.97 / peak
        return mix


# ------------------------------------------------------------------ 3 bai
SONGS = [
    dict(
        file='01_mua_dem.ogg', title='Mưa đêm', bpm=72, bars=24, seed=11,
        # Dm9 | G13 | Cmaj9 | Am9   (ii - V - I - vi)
        prog=[[(4, 38, [53, 57, 60, 64])], [(4, 43, [53, 59, 64, 69])],
              [(4, 36, [52, 59, 62, 67])], [(4, 45, [55, 60, 64, 71])]],
        comp='ep', pad_under=True, drums='boombap', drums_from=4,
        lead='lead_ep', mel_range=(67, 84), scale={0, 2, 4, 7, 9},
        ambience='rain', swing=0.10, verb=2.6, verb_mix=0.32, wow=3.6,
        gains=dict(chords=1.0, pad=0.9, lead=0.8, drums=0.68, bass=0.62, tex=1.0),
    ),
    dict(
        file='02_ca_phe_sang.ogg', title='Cà phê sáng', bpm=76, bars=24, seed=27,
        # Bbmaj9 | Am7 | Gm9 | Fmaj9      / B: Bbmaj9 | Am7 | Gm7 C9 | Fmaj9
        prog=[[(4, 46, [57, 60, 62, 65])], [(4, 45, [55, 60, 64, 67])],
              [(4, 43, [53, 57, 58, 62])], [(4, 41, [52, 55, 57, 60])]],
        prog_b=[[(4, 46, [57, 60, 62, 65])], [(4, 45, [55, 60, 64, 67])],
                [(2, 43, [53, 58, 62, 65]), (2, 36, [52, 55, 58, 62])], [(4, 41, [52, 55, 57, 60])]],
        comp='nylon', pad_under=True, drums='boombap', drums_from=4,
        lead='bell', mel_range=(72, 88), scale={5, 7, 9, 0, 2},
        ambience=None, swing=0.085, verb=2.2, verb_mix=0.26, wow=2.8,
        gains=dict(chords=1.0, pad=1.0, lead=0.85, drums=0.68, bass=0.65, tex=1.3),
    ),
    dict(
        file='03_hoang_hon.ogg', title='Hoàng hôn', bpm=68, bars=24, seed=43,
        # Abmaj9 | Gm7 | Fm9 Bb13 | Ebmaj9
        prog=[[(4, 44, [55, 58, 60, 63])], [(4, 43, [53, 58, 62, 65])],
              [(2, 41, [51, 56, 60, 67]), (2, 46, [56, 62, 67, 72])], [(4, 39, [50, 55, 58, 65])]],
        comp='pad', pad_under=False, drums='soft', drums_from=4,
        lead='bell', mel_range=(70, 89), scale={3, 5, 7, 10, 0},
        ambience='waves', swing=0.09, verb=3.2, verb_mix=0.40, wow=3.0,
        gains=dict(chords=1.6, lead=0.9, drums=0.9, bass=0.75, tex=1.0),
        extra_ep=True,
    ),
]


def build(cfg):
    song = Song(cfg)
    if cfg.get('extra_ep'):      # bai 3: them piano dien rat nhe tren nen pad
        for bar in range(song.bars):
            for beats, root, voicing in song.chords_at(bar)[:1]:
                for k, m in enumerate(voicing):
                    song.add('chords', bar * song.bar + 0.02 * k, ep(m + 12, song.beat * 2, 0.035), pan=0.2)
    mix = song.render()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, cfg['file'])
    data = np.ascontiguousarray(mix.T, dtype=np.float32)
    # libsndfile bi crash neu ghi 1 khoi Vorbis qua lon -> ghi tung khoi nho
    with sf.SoundFile(path, 'w', SR, 2, format='OGG', subtype='VORBIS') as f:
        for i in range(0, len(data), 8192):
            f.write(data[i:i + 8192])
    rms = 20 * np.log10(np.sqrt(np.mean(mix ** 2)))
    print(f"{cfg['file']:<22} {cfg['title']:<12} {mix.shape[1] / SR:5.1f}s  RMS {rms:5.1f} dBFS  "
          f"{os.path.getsize(path) / 1e6:.2f} MB")


if __name__ == '__main__':
    try:
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    for c in SONGS:
        build(c)
