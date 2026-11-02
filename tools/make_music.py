# -*- coding: utf-8 -*-
"""
Tao nhac nen goc cho TDCaro (lo-fi nhe nhang, lap lien mach) -> assets/music.wav

Tu tong hop 100% bang code (khong dung mau/nhac co ban quyen):
  - piano dien (Rhodes) danh hop am 7
  - bass tron
  - giai dieu gay day (Karplus-Strong) tren thang ngu cung
  - trong nhe (kick, brush, hi-hat swing) + tieng dia than lo-fi

Chay:  python tools/make_music.py
"""
import math
import os
import random
import struct
import wave

RATE = 22050
BPM = 80
BEAT = 60.0 / BPM            # 0.75 s
BAR = 4 * BEAT               # 3 s
BARS = 16                    # 48 s
LENGTH = int(BARS * BAR * RATE)
TAIL = int(4 * RATE)         # duoi vang -> cong vong ve dau de lap lien mach

rnd = random.Random(1205)
mix = [0.0] * (LENGTH + TAIL)


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def add(buf, start, samples, gain=1.0):
    i0 = int(start * RATE)
    n = min(len(samples), len(buf) - i0)
    for i in range(n):
        buf[i0 + i] += samples[i] * gain


# ------------------------------------------------------------------ voices
def rhodes(m, dur, vel):
    f = midi_hz(m)
    n = int((dur + 1.2) * RATE)
    out = [0.0] * n
    w1, w2, w3 = 2 * math.pi * f / RATE, 2 * math.pi * f * 2.0 / RATE, 2 * math.pi * f * 3.0 / RATE
    trem = 2 * math.pi * 4.2 / RATE
    for i in range(n):
        t = i / RATE
        att = min(1.0, t / 0.012)
        body = math.exp(-t * 1.1)
        bell = math.exp(-t * 7.0)
        rel = 1.0 if t < dur else math.exp(-(t - dur) * 6.0)
        v = math.sin(w1 * i) + 0.35 * bell * math.sin(w2 * i) + 0.12 * bell * math.sin(w3 * i)
        out[i] = v * att * body * rel * vel * (1.0 + 0.06 * math.sin(trem * i))
    return out


def bass(m, dur, vel):
    f = midi_hz(m)
    n = int((dur + 0.3) * RATE)
    out = [0.0] * n
    w = 2 * math.pi * f / RATE
    for i in range(n):
        t = i / RATE
        att = min(1.0, t / 0.01)
        rel = 1.0 if t < dur else math.exp(-(t - dur) * 14.0)
        v = math.sin(w * i) + 0.18 * math.sin(2 * w * i)
        out[i] = v * att * math.exp(-t * 0.9) * rel * vel
    return out


def pluck(m, dur, vel):
    """Karplus-Strong: tieng gay day am, mem."""
    f = midi_hz(m)
    period = max(2, int(RATE / f))
    ring = [rnd.uniform(-1, 1) for _ in range(period)]
    # lam mem tieng gay ban dau
    for _ in range(2):
        ring = [(ring[i] + ring[i - 1]) * 0.5 for i in range(period)]
    n = int(dur * RATE)
    out = [0.0] * n
    idx = 0
    damp = 0.996
    for i in range(n):
        a = ring[idx]
        b = ring[(idx + 1) % period]
        ring[idx] = (a + b) * 0.5 * damp
        out[i] = a * vel
        idx = (idx + 1) % period
    return out


def kick(vel):
    n = int(0.35 * RATE)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / RATE
        f = 48 + 70 * math.exp(-t * 28)
        ph += 2 * math.pi * f / RATE
        out[i] = math.sin(ph) * math.exp(-t * 11) * vel
    return out


def noise_hit(dur, decay, vel, hp=0.0, lp=1.0):
    n = int(dur * RATE)
    out = [0.0] * n
    lo = prev = 0.0
    for i in range(n):
        x = rnd.uniform(-1, 1)
        lo += lp * (x - lo)                     # loc thong thap
        y = lo - hp * prev                      # loc thong cao don gian
        prev = lo
        out[i] = y * math.exp(-i / RATE * decay) * vel
    return out


# ------------------------------------------------------------------ score
# Fmaj7 | Em7 | Dm7 | Cmaj7  (lap lai, nua sau them giai dieu)
CHORDS = [
    (41, [57, 60, 64, 65]),   # F  : A3 C4 E4 F4
    (40, [55, 59, 62, 64]),   # Em7: G3 B3 D4 E4
    (38, [53, 57, 60, 62]),   # Dm7: F3 A3 C4 D4
    (36, [52, 55, 59, 60]),   # Cmaj7: E3 G3 B3 C4
]
PENTA = [60, 62, 64, 67, 69, 72, 74, 76, 79]   # C ngu cung (C4..G5)
SWING = 0.06

for bar in range(BARS):
    t0 = bar * BAR
    root, notes = CHORDS[bar % 4]
    # piano dien: phach 1 + nhac lai nhe o "va" cua phach 3, hoi rai ngon
    for k, m in enumerate(notes):
        add(mix, t0 + k * 0.012, rhodes(m, BEAT * 2.4, 0.075))
        add(mix, t0 + 2.5 * BEAT + k * 0.01, rhodes(m, BEAT * 1.3, 0.045))
    # bass
    add(mix, t0, bass(root, BEAT * 2.6, 0.30))
    add(mix, t0 + 3.5 * BEAT, bass(root + 7, BEAT * 0.45, 0.20))
    # trong (tu o nhip 2)
    if bar >= 1:
        add(mix, t0, kick(0.45))
        add(mix, t0 + 2.5 * BEAT, kick(0.32))
        for b in (1, 3):
            add(mix, t0 + b * BEAT, noise_hit(0.22, 16, 0.10, hp=0.6, lp=0.45))
        for e in range(8):
            st = t0 + e * BEAT / 2 + (SWING if e % 2 else 0.0)
            add(mix, st, noise_hit(0.05, 70, 0.045 if e % 2 else 0.06, hp=0.95, lp=0.9))

# giai dieu: tu nhip 5, di bo ngau nhien tren ngu cung, thua thot
melody = [0.0] * len(mix)
pos = 4
for bar in range(4, BARS):
    t0 = bar * BAR
    if bar % 4 == 3 and rnd.random() < 0.6:
        continue                                 # nghi de "tho"
    e = 0
    while e < 8:
        if rnd.random() < 0.55:
            pos = max(0, min(len(PENTA) - 1, pos + rnd.choice((-2, -1, -1, 1, 1, 2))))
            length = rnd.choice((1, 1, 2, 2, 3))
            st = t0 + e * BEAT / 2 + (SWING if e % 2 else 0.0)
            add(melody, st, pluck(PENTA[pos], BEAT * 0.5 * length + 0.6, 0.16))
            e += length
        else:
            e += 1
# vang (delay cham doi) cho giai dieu
d = int(BEAT * 0.75 * RATE)
for tap, g in ((1, 0.32), (2, 0.14)):
    off = d * tap
    for i in range(len(melody) - 1, off - 1, -1):
        melody[i] += melody[i - off] * g
for i in range(len(mix)):
    mix[i] += melody[i]

# tieng dia than: lach tach thua thot + nen am rat nho
lo = 0.0
for i in range(len(mix)):
    lo += 0.08 * (rnd.uniform(-1, 1) - lo)
    mix[i] += lo * 0.012
for _ in range(int(BARS * BAR * 7)):
    i = rnd.randrange(len(mix) - 40)
    a = rnd.uniform(0.02, 0.06) * rnd.choice((-1, 1))
    for k in range(30):
        mix[i + k] += a * math.exp(-k / 4.0)

# ------------------------------------------------------------------ master
# cong duoi vang vao dau -> lap lien mach
out = mix[:LENGTH]
for i in range(TAIL):
    out[i] += mix[LENGTH + i]
# loc am ap (thong thap 1 cuc) + nen mem
lo = 0.0
for x in out[-2000:]:          # lam nong bo loc bang doan cuoi -> cho noi vong khong bi "tach"
    lo += 0.55 * (x - lo)
for i in range(LENGTH):
    lo += 0.55 * (out[i] - lo)
    out[i] = lo
peak = max(abs(x) for x in out) or 1.0
gain = 0.85 / peak
frames = bytearray()
for x in out:
    v = math.tanh(x * gain * 1.1) / math.tanh(1.1)
    frames += struct.pack('<h', int(max(-1.0, min(1.0, v)) * 32000))

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(root, 'assets', 'music.wav')
with wave.open(path, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(bytes(frames))
print(f'{path}: {LENGTH / RATE:.1f}s, {os.path.getsize(path) / 1e6:.2f} MB, peak gain {gain:.2f}')
