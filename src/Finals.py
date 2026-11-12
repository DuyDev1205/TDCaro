# -*- coding: utf-8 -*-
"""
TDCARO  -  giao dien pygame-ce
=========================================
- Phan AI ENGINE (tinh toan caro) duoc giu NGUYEN VAN tu ban cu.
- Phan giao dien duoc viet lai hoan toan bang pygame-ce.

Chay:        python src/Finals.py
Build .exe:  packaging/build_exe.bat   (hoac: pyinstaller packaging/TDCaro.spec)
"""
import os
import sys
import math
import random
import threading
import time
from array import array

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

IS_WEB = sys.platform == 'emscripten'      # ban web (pygbag / WebAssembly)


# ==========================================
# BOARD LOGIC & AI ENGINE (PRESERVED CORE)
# ==========================================

def make_empty_board(sz):
    b = []
    for i in range(sz):
        b.append([" "]*sz)
    return b

def is_empty(b):
    return b == [[' ']*len(b)]*len(b)

def is_in(b, y, x):
    return 0 <= y < len(b) and 0 <= x < len(b)

def find_winning_line(b, col):
    size = len(b)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for y in range(size):
        for x in range(size):
            if b[y][x] == col:
                for dy, dx in directions:
                    count_forward = 0
                    count_backward = 0
                    ny, nx = y + dy, x + dx
                    while is_in(b, ny, nx) and b[ny][nx] == col:
                        count_forward += 1
                        ny += dy
                        nx += dx
                    ny, nx = y - dy, x - dx
                    while is_in(b, ny, nx) and b[ny][nx] == col:
                        count_backward += 1
                        ny -= dy
                        nx -= dx
                    total_count = count_forward + count_backward + 1
                    if total_count >= 5:
                        start_y = y - count_backward * dy
                        start_x = x - count_backward * dx
                        end_y = start_y + 4 * dy
                        end_x = start_x + 4 * dx
                        return (start_y, start_x, end_y, end_x)
    return None

def is_win(b):
    red = score_of_col(b, 'r')
    white = score_of_col(b, 'w')
    sum_sumcol_values(red)
    sum_sumcol_values(white)
    if 5 in red and red[5] == 1:
        return 'Player Win'
    elif 5 in white and white[5] == 1:
        return 'NPC Win'
    if sum(red.values()) == red[-1] and sum(white.values()) == white[-1] or possible_moves(b) == []:
        return 'Draw'
    return 'Continue playing'

def march(b, y, x, dy, dx, length):
    yf = y + length * dy
    xf = x + length * dx
    while not is_in(b, yf, xf):
        yf -= dy
        xf -= dx
    return yf, xf

def score_ready(scorecol):
    sumcol = {0: {}, 1: {}, 2: {}, 3: {}, 4: {}, 5: {}, -1: {}}
    for key in scorecol:
        for score in scorecol[key]:
            if key in sumcol[score]:
                sumcol[score][key] += 1
            else:
                sumcol[score][key] = 1
    return sumcol

def sum_sumcol_values(sumcol):
    for key in sumcol:
        if key == 5:
            sumcol[5] = int(1 in sumcol[5].values())
        else:
            sumcol[key] = sum(sumcol[key].values())

def score_of_list(lis, col):
    blank = lis.count(' ')
    filled = lis.count(col)
    if blank + filled < 5:
        return -1
    elif blank == 5:
        return 0
    else:
        return filled

def row_to_list(b, y, x, dy, dx, yf, xf):
    row = []
    while y != yf + dy or x != xf + dx:
        row.append(b[y][x])
        y += dy
        x += dx
    return row

def score_of_row(b, cordi, dy, dx, cordf, col):
    colscores = []
    y, x = cordi
    yf, xf = cordf
    row = row_to_list(b, y, x, dy, dx, yf, xf)
    for start in range(len(row) - 4):
        score = score_of_list(row[start:start + 5], col)
        colscores.append(score)
    return colscores

def score_of_col(b, col):
    f = len(b)
    scores = {(0, 1): [], (-1, 1): [], (1, 0): [], (1, 1): []}
    for start in range(len(b)):
        scores[(0, 1)].extend(score_of_row(b, (start, 0), 0, 1, (start, f - 1), col))
        scores[(1, 0)].extend(score_of_row(b, (0, start), 1, 0, (f - 1, start), col))
        scores[(1, 1)].extend(score_of_row(b, (start, 0), 1, 1, (f - 1, f - 1 - start), col))
        scores[(-1, 1)].extend(score_of_row(b, (start, 0), -1, 1, (0, start), col))
        if start + 1 < len(b):
            scores[(1, 1)].extend(score_of_row(b, (0, start + 1), 1, 1, (f - 2 - start, f - 1), col))
            scores[(-1, 1)].extend(score_of_row(b, (f - 1, start + 1), -1, 1, (start + 1, f - 1), col))
    return score_ready(scores)

def score_of_col_one(b, col, y, x):
    scores = {(0, 1): [], (-1, 1): [], (1, 0): [], (1, 1): []}
    scores[(0, 1)].extend(score_of_row(b, march(b, y, x, 0, -1, 4), 0, 1, march(b, y, x, 0, 1, 4), col))
    scores[(1, 0)].extend(score_of_row(b, march(b, y, x, -1, 0, 4), 1, 0, march(b, y, x, 1, 0, 4), col))
    scores[(1, 1)].extend(score_of_row(b, march(b, y, x, -1, -1, 4), 1, 1, march(b, y, x, 1, 1, 4), col))
    scores[(-1, 1)].extend(score_of_row(b, march(b, y, x, -1, 1, 4), 1, -1, march(b, y, x, 1, -1, 4), col))
    return score_ready(scores)

def possible_moves(b):
    taken = []
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (-1, 1), (1, -1)]
    cord = {}
    for i in range(len(b)):
        for j in range(len(b)):
            if b[i][j] != ' ':
                taken.append((i, j))
    for direction in directions:
        dy, dx = direction
        for coord in taken:
            y, x = coord
            for length in [1, 2, 3, 4]:
                move = march(b, y, x, dy, dx, length)
                if move not in taken and move not in cord:
                    cord[move] = False
    return cord

def TF34score(score3, score4):
    for key4 in score4:
        if score4[key4] >= 1:
            for key3 in score3:
                if key3 != key4 and score3[key3] >= 2:
                    return True
    return False

def stupid_score(b, col, anticol, y, x):
    M = 1000
    res, adv, dis = 0, 0, 0
    b[y][x] = col
    sumcol = score_of_col_one(b, col, y, x)
    a = winning_situation(sumcol)
    adv += a * M
    sum_sumcol_values(sumcol)
    adv += sumcol[-1] + sumcol[1] + 4 * sumcol[2] + 8 * sumcol[3] + 16 * sumcol[4]

    b[y][x] = anticol
    sumanticol = score_of_col_one(b, anticol, y, x)
    d = winning_situation(sumanticol)
    dis += d * (M - 100)
    sum_sumcol_values(sumanticol)
    dis += sumanticol[-1] + sumanticol[1] + 4 * sumanticol[2] + 8 * sumanticol[3] + 16 * sumanticol[4]

    res = adv + dis
    b[y][x] = ' '
    return res

def winning_situation(sumcol):
    if 1 in sumcol[5].values():
        return 5
    elif len(sumcol[4]) >= 2 or (len(sumcol[4]) >= 1 and max(sumcol[4].values()) >= 2):
        return 4
    elif TF34score(sumcol[3], sumcol[4]):
        return 4
    else:
        score3 = sorted(sumcol[3].values(), reverse=True)
        if len(score3) >= 2 and score3[0] >= score3[1] >= 2:
            return 3
    return 0

def best_move(b, col):
    if col == 'w':
        anticol = 'r'
    else:
        anticol = 'w'
    movecol = (0, 0)
    maxscorecol = ''
    if is_empty(b):
        movecol = (int(len(b) * random.random()), int(len(b[0]) * random.random()))
    else:
        moves = possible_moves(b)
        for move in moves:
            y, x = move
            if maxscorecol == '':
                scorecol = stupid_score(b, col, anticol, y, x)
                maxscorecol = scorecol
                movecol = move
            else:
                scorecol = stupid_score(b, col, anticol, y, x)
                if scorecol > maxscorecol:
                    maxscorecol = scorecol
                    movecol = move
    return movecol


# ==========================================================================
# ======================  GIAO DIEN MOI (pygame-ce)  =======================
# ==========================================================================

import ai_engine_v2
import updater
import shortcuts
import online

APP_VERSION = '1.0.0'

LEVELS = [('easy', 'Dễ'), ('normal', 'Bình thường'), ('hard', 'Khó'), ('expert', 'Cực khó')]
LEVEL_NAMES = dict(LEVELS)
MUSIC_END = pygame.USEREVENT + 7
TRACK_TITLES = {'01_mua_dem': 'Mưa đêm', '02_ca_phe_sang': 'Cà phê sáng', '03_hoang_hon': 'Hoàng hôn'}


RULES = [('free', 'Tự do'), ('block', 'Chặn 2 đầu')]


def rule_win_cells(board, r, c, block):
    """Kiem tra thang qua nuoc vua danh (r, c). Tra ve danh sach o (row, col) cua day thang, hoac None.
    block=True: day >= 5 bi quan doi thu chan CA HAI DAU thi khong thang (bien khong tinh la chan)."""
    col = board[r][c]
    if col == ' ':
        return None
    n = len(board)
    opp = 'w' if col == 'r' else 'r'
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        cells = [(r, c)]
        ends = []
        for sgn in (1, -1):
            rr, cc = r + dr * sgn, c + dc * sgn
            while 0 <= rr < n and 0 <= cc < n and board[rr][cc] == col:
                cells.append((rr, cc))
                rr += dr * sgn
                cc += dc * sgn
            ends.append(0 <= rr < n and 0 <= cc < n and board[rr][cc] == opp)
        if len(cells) >= 5 and not (block and ends[0] and ends[1]):
            return sorted(cells)
    return None


def ai_move(board, col, level, block=False):
    """Chon nuoc theo do kho. 'easy' = AI GOC (best_move) giu nguyen."""
    if level == 'easy':
        return best_move(board, col)
    return ai_engine_v2.choose_move(board, col, level, base_score=stupid_score, base_moves=possible_moves,
                                    block=block)


COL_LETTERS = [chr(65 + i) for i in range(26)]
MIN_SIZE, MAX_SIZE = 5, 20
AI_MIN_THINK = 0.45          # giay - de nguoi choi kip thay AI "suy nghi"
BASE_W, BASE_H = 1280, 800   # kich thuoc thiet ke goc, UI tu co gian theo cua so


# ---------------------------- tien ich mau / so ----------------------------

def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def darken(c, f):
    return lerp_color(c, (0, 0, 0), f)

def lighten(c, f):
    return lerp_color(c, (255, 255, 255), f)

def approach(cur, target, dt, speed=12.0):
    return cur + (target - cur) * min(1.0, dt * speed)

def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def fmt_time(sec):
    sec = int(max(0, sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"

def coord_name(c, r):
    return f"{COL_LETTERS[c]}{r + 1}"


# --------------------------------- THEMES ---------------------------------

THEME_DEFS = {
    'midnight': dict(
        name='Midnight Neon', dark=True, glow=True, style='tiles',
        bg_top='#0E1330', bg_bottom='#1B0F2E', blob1='#6D4BFF', blob2='#00B8F0', blob_alpha=80,
        bg_text='#EEF1FF', bg_text_dim='#8C94C0', bg_accent='#A996FF',
        panel='#151A33', panel_alt='#1D2342', border='#2B3360',
        board='#1A2040', board_edge='#0A0E24', cell_a='#232B55', cell_b='#1D2449', grid='#2E3870',
        text='#EEF1FF', text_dim='#8C94C0',
        x='#FF4F8B', o='#35D5FF', accent='#7B61FF', gold='#FFC857',
        shadow_alpha=150, float_alpha=30),
    'wood': dict(
        name='Gỗ Cổ Điển', dark=False, glow=False, style='grid',
        bg_top='#F6EEE3', bg_bottom='#E5D1B8', blob1='#F5BE85', blob2='#C98B5A', blob_alpha=70,
        bg_text='#3E2A17', bg_text_dim='#8F7458', bg_accent='#B8642E',
        panel='#FFFBF5', panel_alt='#F6EDE1', border='#E6D5BF',
        board='#E8C48C', board_edge='#A26C38', cell_a='#EBC994', cell_b='#E6C189', grid='#9C6B3A',
        text='#3E2A17', text_dim='#8F7458',
        x='#C0392B', o='#1F3A5F', accent='#B8642E', gold='#F0A020',
        shadow_alpha=80, float_alpha=32),
    'ocean': dict(
        name='Đại Dương', dark=False, glow=False, style='tiles',
        bg_top='#34E5D7', bg_bottom='#12B3C6', blob1='#A8FFF5', blob2='#0A86A8', blob_alpha=80,
        bg_text='#0E2A47', bg_text_dim='#14506B', bg_accent='#FFFFFF',
        panel='#F6FFFE', panel_alt='#E6F7F6', border='#BFE9E6',
        board='#FFF9EC', board_edge='#1E3A5F', cell_a='#FFF6E2', cell_b='#7FE0D6', grid='#1E3A5F',
        text='#123250', text_dim='#56788F',
        x='#1E3A5F', o='#FF6B5B', accent='#0C93A5', gold='#FFB703',
        shadow_alpha=90, float_alpha=50),
    'sakura': dict(
        name='Hoa Anh Đào', dark=False, glow=False, style='tiles',
        bg_top='#FFF0F5', bg_bottom='#EDE2FF', blob1='#FFB3CF', blob2='#C3B1FF', blob_alpha=90,
        bg_text='#3B1F3F', bg_text_dim='#9C7C9A', bg_accent='#E8467C',
        panel='#FFFFFF', panel_alt='#FBF2F8', border='#F0D9E7',
        board='#FFFFFF', board_edge='#E5BCD3', cell_a='#FFF6FA', cell_b='#FBE6F0', grid='#EBCFE0',
        text='#3B1F3F', text_dim='#9C7C9A',
        x='#E8467C', o='#6F4BE8', accent='#E8467C', gold='#FFB020',
        shadow_alpha=70, float_alpha=38),
}


def _build_themes():
    themes = {}
    for key, d in THEME_DEFS.items():
        t = {}
        for k, v in d.items():
            t[k] = hex2rgb(v) if isinstance(v, str) and v.startswith('#') else v
        t['key'] = key
        t['accent_hover'] = lighten(t['accent'], 0.15)
        t['hover_tint'] = lerp_color(t['panel_alt'], t['accent'], 0.14)
        t['on_accent'] = (255, 255, 255)
        themes[key] = t
    return themes


THEMES = _build_themes()
THEME_KEYS = list(THEME_DEFS)


# ------------------------------ UI scale ----------------------------------

class UI:
    s = 1.0


def px(v):
    return max(1, int(round(v * UI.s)))


# ------------------------------ graphics cache -----------------------------

_gfx = {}
_text_cache = {}
_font_cache = {}


def cached(key, make):
    v = _gfx.get(key)
    if v is None:
        v = make()
        _gfx[key] = v
    return v


def clear_gfx():
    _gfx.clear()
    _text_cache.clear()


_FONT_FILES = {
    'regular': ('segoeui.ttf', 'arial.ttf'),
    'semibold': ('seguisb.ttf', 'segoeuib.ttf', 'arialbd.ttf'),
    'bold': ('segoeuib.ttf', 'arialbd.ttf'),
    'black': ('seguibl.ttf', 'segoeuib.ttf', 'ariblk.ttf'),
}


_BUNDLED_FONT = {'regular': 'Regular', 'semibold': 'SemiBold', 'bold': 'Bold', 'black': 'Black'}


def get_font(size, weight='regular'):
    key = (size, weight)
    f = _font_cache.get(key)
    if f is not None:
        return f
    fdir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    if os.environ.get('TDCARO_FONT') != 'bundled':
        for name in _FONT_FILES.get(weight, _FONT_FILES['regular']):
            p = os.path.join(fdir, name)
            if os.path.isfile(p):
                try:
                    f = pygame.font.Font(p, size)
                    break
                except Exception:
                    f = None
    if f is None:
        # khong co phong Windows (web, macOS): dung phong kem theo game (ho tro tieng Viet day du)
        try:
            p = resource_path(os.path.join('assets', 'fonts', f'BeVietnamPro-{_BUNDLED_FONT.get(weight, "Regular")}.ttf'))
            if os.path.isfile(p):
                f = pygame.font.Font(p, int(size * 0.94))      # Be Vietnam Pro rong hon Segoe UI mot chut
        except Exception:
            f = None
    if f is None:
        f = pygame.font.SysFont('segoeui,arial,dejavusans,tahoma', size, bold=(weight != 'regular'))
    _font_cache[key] = f
    return f


def text_surf(txt, size, color, weight='regular'):
    key = (txt, size, color, weight)
    s = _text_cache.get(key)
    if s is None:
        if len(_text_cache) > 1500:
            _text_cache.clear()
        s = get_font(size, weight).render(txt, True, color)
        _text_cache[key] = s
    return s


def draw_text(surf, txt, size, color, pos, weight='regular', anchor='topleft'):
    s = text_surf(txt, size, color, weight)
    r = s.get_rect(**{anchor: pos})
    surf.blit(s, r)
    return r


def spaced_text_surf(txt, size, color, weight='bold', spacing=2):
    key = ('sp', txt, size, color, weight, spacing)

    def make():
        f = get_font(size, weight)
        chars = [f.render(ch, True, color) for ch in txt]
        w = sum(c.get_width() for c in chars) + spacing * (len(chars) - 1)
        h = max(c.get_height() for c in chars)
        s = pygame.Surface((max(1, w), h), pygame.SRCALPHA, 32)
        x = 0
        for c in chars:
            s.blit(c, (x, 0))
            x += c.get_width() + spacing
        return s
    return cached(key, make)


def draw_spaced(surf, txt, size, color, pos, weight='bold', spacing=None, anchor='topleft'):
    s = spaced_text_surf(txt, size, color, weight, px(2) if spacing is None else spacing)
    r = s.get_rect(**{anchor: pos})
    surf.blit(s, r)
    return r


def gradient(w, h, c1, c2, vertical=True):
    n = 64
    g = pygame.Surface((1, n) if vertical else (n, 1), 0, 32)
    for i in range(n):
        g.set_at((0, i) if vertical else (i, 0), lerp_color(c1, c2, i / (n - 1)))
    return pygame.transform.smoothscale(g, (max(1, w), max(1, h)))


def gradient_text(txt, size, weight, c1, c2):
    key = ('gt', txt, size, weight, c1, c2)

    def make():
        base = get_font(size, weight).render(txt, True, (255, 255, 255))
        base = base.subsurface(base.get_bounding_rect()).copy()
        w, h = base.get_size()
        g = gradient(w, h, c1, c2, vertical=False)
        base.blit(g, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        return base
    return cached(key, make)


def blur(s, f):
    w, h = s.get_size()
    small = pygame.transform.smoothscale(s, (max(1, int(w / f)), max(1, int(h / f))))
    return pygame.transform.smoothscale(small, (w, h))


SS = 3  # supersampling cho hinh bo goc muot


def round_rect_surf(w, h, r, color, border=None, bw=0):
    w, h = max(1, int(w)), max(1, int(h))
    r = int(min(r, w // 2, h // 2))
    key = ('rr', w, h, r, color, border, bw)

    def make():
        W, H = w * SS, h * SS
        s = pygame.Surface((W, H), pygame.SRCALPHA, 32)
        fillc = color if len(color) == 4 else (*color, 255)
        s.fill((*fillc[:3], 0))
        if border is not None and bw > 0:
            pygame.draw.rect(s, border, (0, 0, W, H), border_radius=r * SS)
            b = bw * SS
            pygame.draw.rect(s, fillc, (b, b, W - 2 * b, H - 2 * b), border_radius=max(0, (r - bw) * SS))
        else:
            pygame.draw.rect(s, fillc, (0, 0, W, H), border_radius=r * SS)
        return pygame.transform.smoothscale(s, (w, h))
    return cached(key, make)


def shadow_surf(w, h, r, blur_px, alpha, color=(0, 0, 0)):
    w, h = max(1, int(w)), max(1, int(h))
    key = ('sh', w, h, r, blur_px, alpha, color)

    def make():
        pad = blur_px * 2
        W, H = w + pad * 2, h + pad * 2
        s = pygame.Surface((W, H), pygame.SRCALPHA, 32)
        s.fill((*color, 0))
        pygame.draw.rect(s, (*color, alpha), (pad, pad, w, h), border_radius=int(min(r, w // 2, h // 2)))
        f = max(2, blur_px / 2)
        s = blur(s, f)
        s = blur(s, f)
        return s, pad
    return cached(key, make)


def draw_card(surf, rect, r, color, border=None, bw=1, shadow=None):
    if shadow:
        blur_px, alpha, dy = shadow
        sh, pad = shadow_surf(rect.w, rect.h, r, blur_px, alpha)
        surf.blit(sh, (rect.x - pad, rect.y - pad + dy))
    surf.blit(round_rect_surf(rect.w, rect.h, r, color, border, bw), rect.topleft)


def background(w, h, th):
    key = ('bg', w, h, th['key'])

    def make():
        s = gradient(w, h, th['bg_top'], th['bg_bottom'])   # giu dinh dang XRGB (khong convert theo man hinh)
        sw, sh = max(8, w // 8), max(8, h // 8)
        a = th['blob_alpha']
        for col, (fx, fy), fr in ((th['blob1'], (0.12, 0.18), 0.75), (th['blob2'], (0.95, 0.95), 0.8)):
            blob = pygame.Surface((sw, sh), pygame.SRCALPHA, 32)
            blob.fill((*col, 0))
            R = sh * fr
            steps = 48
            for i in range(steps):
                k = i / steps                      # 0 = ngoai cung, ~1 = tam
                pygame.draw.circle(blob, (*col, int(min(255, a * 1.3) * k ** 1.5)), (sw * fx, sh * fy), R * (1 - k))
            s.blit(pygame.transform.smoothscale(blob, (w, h)), (0, 0))
        return s
    return cached(key, make)


def thick_line(s, color, p1, p2, w):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    pygame.draw.polygon(s, color, [(p1[0] + nx, p1[1] + ny), (p2[0] + nx, p2[1] + ny),
                                   (p2[0] - nx, p2[1] - ny), (p1[0] - nx, p1[1] - ny)])
    pygame.draw.circle(s, color, p1, w / 2)
    pygame.draw.circle(s, color, p2, w / 2)


def _shape(kind, W, color):
    s = pygame.Surface((W, W), pygame.SRCALPHA, 32)
    s.fill((*color[:3], 0))
    c = W / 2
    if kind == 'x':
        o = W * 0.29
        th = W * 0.17
        thick_line(s, color, (c - o, c - o), (c + o, c + o), th)
        thick_line(s, color, (c + o, c - o), (c - o, c + o), th)
    else:
        r = W * 0.35
        th = W * 0.15
        pygame.draw.circle(s, color, (c, c), r)
        pygame.draw.circle(s, (*color[:3], 0), (c, c), r - th)
    return s


def piece_sprite(kind, size, color, glow=False, shadow_alpha=0):
    """Quan co X / O khu rang cua, co do day 3D + glow (theme toi) hoac bong do (theme sang)."""
    size = max(4, int(size))
    key = ('pc', kind, size, color, glow, shadow_alpha)

    def make():
        k = 4
        canvas = int(size * 1.7)
        C, W = canvas * k, size * k
        big = pygame.Surface((C, C), pygame.SRCALPHA, 32)
        big.fill((*color, 0))
        off = (C - W) // 2
        dep = max(1, int(W * 0.05))
        big.blit(_shape(kind, W, darken(color, 0.38)), (off, off + dep))
        big.blit(_shape(kind, W, color), (off, off))
        spr = pygame.transform.smoothscale(big, (canvas, canvas))
        if not glow and not shadow_alpha:
            return spr
        out = pygame.Surface((canvas, canvas), pygame.SRCALPHA, 32)
        out.fill((*color, 0))
        if glow:
            g = pygame.Surface((canvas, canvas), pygame.SRCALPHA, 32)
            g.fill((*color, 0))
            gs = int(size * 1.15)
            g.blit(pygame.transform.smoothscale(_shape(kind, gs * 2, color), (gs, gs)),
                   ((canvas - gs) // 2, (canvas - gs) // 2))
            g = blur(blur(g, 5), 3)
            g.fill((255, 255, 255, 210), special_flags=pygame.BLEND_RGBA_MULT)
            out.blit(g, (0, 0))
        if shadow_alpha:
            sh = pygame.Surface((canvas, canvas), pygame.SRCALPHA, 32)
            sh.fill((0, 0, 0, 0))
            shp = pygame.transform.smoothscale(_shape(kind, size * 2, (0, 0, 0)), (size, size))
            sh.blit(shp, ((canvas - size) // 2 + int(size * 0.03), (canvas - size) // 2 + int(size * 0.1)))
            sh = blur(sh, 4)
            sh.fill((255, 255, 255, shadow_alpha), special_flags=pygame.BLEND_RGBA_MULT)
            out.blit(sh, (0, 0))
        out.blit(spr, (0, 0))
        return out
    return cached(key, make)


def themed_piece(kind, size, th, effects=True):
    color = th['x'] if kind == 'x' else th['o']
    if not effects:
        return piece_sprite(kind, size, color)
    if th['glow']:
        return piece_sprite(kind, size, color, glow=True)
    return piece_sprite(kind, size, color, shadow_alpha=110)


def flat_sprite(kind, size, color, alpha):
    key = ('flat', kind, size, color, alpha)

    def make():
        s = pygame.transform.smoothscale(_shape(kind, size * 3, color), (size, size))
        s.set_alpha(alpha)
        return s
    return cached(key, make)


def blit_center(surf, spr, pos):
    surf.blit(spr, spr.get_rect(center=(int(pos[0]), int(pos[1]))))


# ------------------------------------ SOUND --------------------------------

class SoundFX:
    """Am thanh tong hop bang code -> khong can file ngoai khi build exe."""

    def __init__(self, app):
        self.app = app
        self.sounds = {}
        try:
            init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, fmt, self.ch = init
            if fmt != -16:
                return
            self.sounds = {
                'click': self._tone([(1250, 0.035)], 0.12, 70),
                'place': self._tone([(880, 0.10)], 0.30, 32),
                'ai': self._tone([(587, 0.10)], 0.28, 32),
                'hint': self._tone([(988, 0.08), (1319, 0.12)], 0.18, 18),
                'win': self._tone([(523, 0.11), (659, 0.11), (784, 0.11), (1047, 0.38)], 0.26, 7),
                'lose': self._tone([(440, 0.16), (370, 0.16), (294, 0.40)], 0.26, 6),
                'draw': self._tone([(587, 0.14), (587, 0.26)], 0.22, 8),
            }
        except Exception:
            self.sounds = {}

    def _tone(self, notes, vol, decay):
        buf = array('h')
        rate = self.rate
        for f, d in notes:
            n = int(rate * d)
            for i in range(n):
                t = i / rate
                env = math.exp(-decay * t) * min(1.0, i / (rate * 0.004))
                v = (math.sin(2 * math.pi * f * t) + 0.25 * math.sin(4 * math.pi * f * t)) * env * vol
                sample = int(clamp(v, -1.0, 1.0) * 32767)
                for _ in range(self.ch):
                    buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.app.settings['sound'] and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass


# ----------------------------------- BUTTON --------------------------------

class Button:
    def __init__(self, label, action, style='secondary', hotkey=None, enabled=None,
                 selected=None, icon=None, font_size=15, radius=12):
        self.label = label
        self.action = action
        self.style = style
        self.hotkey = hotkey
        self._enabled = enabled
        self._selected = selected
        self.icon = icon            # callable(th) -> (kind, size)
        self.font_size = font_size
        self.radius = radius
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.h = 0.0
        self.down = False
        self.hovered = False

    def enabled(self):
        return self._enabled() if self._enabled else True

    def selected(self):
        return self._selected() if self._selected else False

    def text(self):
        return self.label() if callable(self.label) else self.label

    def update(self, dt, mouse):
        self.hovered = self.enabled() and self.rect.collidepoint(mouse)
        self.h = approach(self.h, 1.0 if self.hovered else 0.0, dt, 16)

    def handle(self, ev, app):
        if not self.enabled():
            self.down = False
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.down = True
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.down:
            self.down = False
            if self.rect.collidepoint(ev.pos):
                app.sound.play('click')
                self.action()
                return True
        return False

    def colors(self, th):
        en, sel = self.enabled(), self.selected()
        hq = round(self.h * 6) / 6 if en else 0
        if not en:
            return th['panel_alt'], th['text_dim'], th['text_dim'], th['border'], False, hq
        if self.style == 'primary' or sel:
            col = lerp_color(th['accent'], th['accent_hover'], hq)
            return col, th['on_accent'], lerp_color(th['on_accent'], th['accent'], 0.3), None, True, hq
        col = lerp_color(th['panel_alt'], th['hover_tint'], hq)
        border = lerp_color(th['border'], th['accent'], hq * 0.7)
        return col, th['text'], th['text_dim'], border, False, hq

    def draw(self, surf, th, ox=0, oy=0):
        if self.rect.w <= 0:
            return
        col, fg, fg_dim, border, filled, hq = self.colors(th)
        r = self.rect.move(-ox, -oy - int(px(2) * hq))
        if self.down and self.hovered:
            r = r.move(0, px(1))
        rad = min(px(self.radius), r.h // 2)
        if filled:
            sh, pad = shadow_surf(r.w, r.h, rad, px(14), 120 if th['dark'] else 85, th['accent'])
            surf.blit(sh, (r.x - pad, r.y - pad + px(5)))
        surf.blit(round_rect_surf(r.w, r.h, rad, col, border, 1 if border else 0), r.topleft)
        self.draw_content(surf, th, r, fg, fg_dim, col)

    def draw_content(self, surf, th, r, fg, fg_dim, col):
        ts = text_surf(self.text(), px(self.font_size), fg, 'semibold')
        icon_w, ispr = 0, None
        if self.icon:
            kind, isz = self.icon(th)
            ispr = themed_piece(kind, isz, th, effects=False)
            icon_w = isz + px(8)
        total = icon_w + ts.get_width()
        cx = r.centerx - total // 2
        if self.hotkey:
            hk = text_surf(self.hotkey, px(10), fg_dim, 'bold')
            chip_w, chip_h = hk.get_width() + px(12), px(20)
            if r.w - total > 2 * chip_w + px(36):
                cr = pygame.Rect(r.right - px(10) - chip_w, r.centery - chip_h // 2, chip_w, chip_h)
                surf.blit(round_rect_surf(cr.w, cr.h, px(6), lerp_color(col, fg, 0.13)), cr)
                surf.blit(hk, hk.get_rect(center=cr.center))
        if ispr:
            blit_center(surf, ispr, (cx + icon_w // 2 - px(4), r.centery))
        surf.blit(ts, (cx + icon_w, r.centery - ts.get_height() // 2))


class ThemeSwatch(Button):
    def __init__(self, key, app):
        super().__init__('', lambda: app.set_theme(key), selected=lambda: app.settings['theme'] == key)
        self.key = key

    def draw(self, surf, th, ox=0, oy=0):
        t2 = THEMES[self.key]
        sel = self.selected()
        hq = round(self.h * 6) / 6
        r = self.rect.move(-ox, -oy - int(px(2) * hq))
        bg = lerp_color(th['panel_alt'], th['hover_tint'], hq)
        border = th['accent'] if sel else lerp_color(th['border'], th['accent'], hq * 0.7)
        if sel:
            sh, pad = shadow_surf(r.w, r.h, px(14), px(12), 90 if th['dark'] else 60, th['accent'])
            surf.blit(sh, (r.x - pad, r.y - pad + px(4)))
        surf.blit(round_rect_surf(r.w, r.h, px(14), bg, border, px(2) if sel else 1), r)
        pr = pygame.Rect(r.x + px(8), r.y + px(8), r.w - px(16), r.h - px(38))
        surf.blit(round_rect_surf(pr.w, pr.h, px(10), t2['board'], t2['board_edge'], px(2)), pr)
        isz = min(px(24), pr.h - px(10))
        blit_center(surf, piece_sprite('x', isz, t2['x']), (pr.centerx - isz * 0.6, pr.centery))
        blit_center(surf, piece_sprite('o', isz, t2['o']), (pr.centerx + isz * 0.6, pr.centery))
        draw_text(surf, t2['name'], px(12), th['text'] if sel else th['text_dim'],
                  (r.centerx, r.bottom - px(15)), 'semibold', 'center')


# ------------------------------ background FX -------------------------------

class FloatingSymbols:
    def __init__(self):
        self.items = []
        self.w = self.h = 0

    def reset(self, w, h):
        self.w, self.h = w, h
        rnd = random.Random(7)
        sizes = [px(26), px(38), px(54), px(72)]
        self.items = [dict(x=rnd.uniform(0, w), y=rnd.uniform(0, h), size=rnd.choice(sizes),
                           kind=rnd.choice('xo'), vy=-rnd.uniform(6, 18) * UI.s,
                           vx=rnd.uniform(-5, 5) * UI.s, ph=rnd.uniform(0, 6.28))
                      for _ in range(18)]

    def update(self, dt):
        for it in self.items:
            it['y'] += it['vy'] * dt
            it['x'] += it['vx'] * dt
            if it['y'] < -it['size']:
                it['y'] = self.h + it['size']
                it['x'] = random.uniform(0, self.w)
            if it['x'] < -it['size']:
                it['x'] = self.w + it['size']
            elif it['x'] > self.w + it['size']:
                it['x'] = -it['size']

    def draw(self, surf, th, t):
        for it in self.items:
            color = th['x'] if it['kind'] == 'x' else th['o']
            spr = flat_sprite(it['kind'], it['size'], color, th['float_alpha'])
            blit_center(surf, spr, (it['x'], it['y'] + math.sin(t * 0.8 + it['ph']) * px(6)))


class Confetti:
    def __init__(self):
        self.parts = []

    def burst(self, x, y, colors, n=150):
        for _ in range(n):
            ang = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            spd = random.uniform(300, 800) * UI.s
            self.parts.append(dict(x=x, y=y, vx=math.cos(ang) * spd, vy=math.sin(ang) * spd,
                                   rot=random.uniform(0, 6.28), vr=random.uniform(-9, 9),
                                   w=random.uniform(5, 9) * UI.s, h=random.uniform(9, 15) * UI.s,
                                   c=random.choice(colors), life=random.uniform(2.2, 3.4)))

    def clear(self):
        self.parts = []

    def update(self, dt, H):
        alive = []
        for p in self.parts:
            p['vy'] += 900 * UI.s * dt
            p['vx'] *= (1 - 1.2 * dt)
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['rot'] += p['vr'] * dt
            p['life'] -= dt
            if p['life'] > 0 and p['y'] < H + 40:
                alive.append(p)
        self.parts = alive

    def draw(self, surf):
        for p in self.parts:
            c, s = math.cos(p['rot']), math.sin(p['rot'])
            hw, hh = p['w'] / 2, p['h'] / 2 * abs(math.sin(p['rot'] * 0.7) + 0.3)
            pts = [(p['x'] + dx * c - dy * s, p['y'] + dx * s + dy * c)
                   for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            pygame.draw.polygon(surf, p['c'], pts)


# ================================ MENU SCREEN ===============================

class MenuScreen:
    PRESETS = [9, 13, 15, 19, 20]

    def __init__(self, app):
        self.app = app
        st = app.settings
        self.btn_start = Button('BẮT ĐẦU CHƠI', app.start_game, 'primary', 'SPACE', font_size=18, radius=16)
        self.btn_online = Button('CHƠI ONLINE', app.go_online, hotkey='O', font_size=16, radius=14)
        self.btn_quit = Button('Thoát', app.quit, hotkey='ESC')
        self.btn_sound = Button(lambda: 'Âm thanh: Bật' if st['sound'] else 'Âm thanh: Tắt', app.toggle_sound, hotkey='M')
        self.btn_minus = Button('−', lambda: self.change_size(-1), font_size=24, radius=14,
                                enabled=lambda: st['size'] > MIN_SIZE)
        self.btn_plus = Button('+', lambda: self.change_size(1), font_size=24, radius=14,
                               enabled=lambda: st['size'] < MAX_SIZE)
        self.chips = [Button(f'{n} × {n}', (lambda n=n: self.set_size(n)), style='chip', font_size=13,
                             selected=(lambda n=n: st['size'] == n)) for n in self.PRESETS]
        self.btn_first_p = Button('Bạn đi trước', lambda: self.set_first('player'), style='chip', font_size=14,
                                  selected=lambda: st['first'] == 'player', icon=lambda th: ('x', px(18)))
        self.btn_first_a = Button('AI đi trước', lambda: self.set_first('ai'), style='chip', font_size=14,
                                  selected=lambda: st['first'] == 'ai', icon=lambda th: ('o', px(18)))
        self.level_chips = [Button(name, (lambda k=k: self.set_level(k)), style='chip', font_size=13,
                                   selected=(lambda k=k: st['level'] == k)) for k, name in LEVELS]
        self.rule_chips = [Button(name, (lambda k=k: self.set_rule(k)), style='chip', font_size=13,
                                  selected=(lambda k=k: st['rule'] == k)) for k, name in RULES]
        self.swatches = [ThemeSwatch(k, app) for k in THEME_KEYS]
        self.btn_update = Button(lambda: app.updater.label(), app.updater.start, 'primary', font_size=13,
                                 radius=20, enabled=lambda: app.updater.state in ('available', 'error'))
        self.btn_full = Button(lambda: 'Thoát toàn màn hình' if app.fullscreen else 'Toàn màn hình',
                               app.toggle_fullscreen, font_size=13, radius=20)
        self.btn_music = Button(lambda: ('Nhạc: ' + (app.track_title or 'Bật')) if st['music'] else 'Nhạc nền: Tắt',
                                app.toggle_music, font_size=13, radius=20)
        self.btn_reset = Button('Đặt lại', app.reset_scores, font_size=13, radius=18,
                                enabled=lambda: any(app.scores.values()))
        self.btn_next = Button('Bài tiếp', app.skip_track, font_size=13, radius=20,
                               enabled=lambda: app.music_ok and len(app.tracks) > 1)
        self.buttons = ([self.btn_update, self.btn_full, self.btn_next, self.btn_music, self.btn_reset, self.btn_start,
                         self.btn_online, self.btn_quit, self.btn_sound, self.btn_minus, self.btn_plus,
                         self.btn_first_p, self.btn_first_a] + self.chips + self.level_chips + self.rule_chips +
                        self.swatches)
        self.size_pulse = 0.0
        self.want_hand = False

    # ---- actions
    def change_size(self, d):
        self.set_size(clamp(self.app.settings['size'] + d, MIN_SIZE, MAX_SIZE))

    def set_size(self, n):
        if n != self.app.settings['size']:
            self.app.settings['size'] = n
            self.size_pulse = 1.0

    def set_first(self, who):
        self.app.settings['first'] = who

    def set_level(self, k):
        self.app.settings['level'] = k

    def set_rule(self, k):
        self.app.settings['rule'] = k

    def toggle_rule(self):
        self.set_rule('free' if self.app.settings['rule'] == 'block' else 'block')

    def cycle_level(self):
        keys = [k for k, _ in LEVELS]
        i = keys.index(self.app.settings['level'])
        self.set_level(keys[(i + 1) % len(keys)])

    # ---- layout
    def layout(self):
        W, H = self.app.size
        colL, colR, gap = px(440), px(500), px(90)
        lx = (W - (colL + gap + colR)) // 2
        rx = lx + colL + gap
        self.lx, self.colL = lx, colL

        # right card
        pad, lbl_h, sec = px(26), px(20), px(18)
        card_h = (pad + lbl_h + px(10) + px(54) + px(12) + px(36) + sec +
                  lbl_h + px(10) + px(40) + sec +
                  lbl_h + px(10) + px(46) + sec + lbl_h + px(10) + px(38) + px(10) + px(44) + sec +
                  lbl_h + px(10) + px(90) + pad)
        self.card = pygame.Rect(rx, (H - card_h) // 2 - px(12), colR, card_h)
        ix, iw = self.card.x + pad, self.card.w - 2 * pad
        y = self.card.y + pad
        self.lbl_size = (ix, y)
        y += lbl_h + px(10)
        self.btn_minus.rect = pygame.Rect(ix, y, px(54), px(54))
        self.btn_plus.rect = pygame.Rect(ix + iw - px(54), y, px(54), px(54))
        self.size_rect = pygame.Rect(ix + px(66), y, iw - 2 * px(66), px(54))
        y += px(54) + px(12)
        g = px(10)
        nc = len(self.chips)
        cw = (iw - (nc - 1) * g) // nc
        for i, b in enumerate(self.chips):
            b.rect = pygame.Rect(ix + i * (cw + g), y, cw, px(36))
        y += px(36) + sec
        self.lbl_level = (ix, y)
        y += lbl_h + px(10)
        g3 = px(8)
        lw = (iw - 3 * g3) // 4
        for i, b in enumerate(self.level_chips):
            b.rect = pygame.Rect(ix + i * (lw + g3), y, lw, px(40))
        y += px(40) + sec
        self.lbl_first = (ix, y)
        y += lbl_h + px(10)
        hw = (iw - g) // 2
        self.btn_first_p.rect = pygame.Rect(ix, y, hw, px(46))
        self.btn_first_a.rect = pygame.Rect(ix + hw + g, y, iw - hw - g, px(46))
        y += px(46) + sec
        self.lbl_rule = (ix, y)
        y += lbl_h + px(10)
        rw = (iw - g) // 2
        for i, b in enumerate(self.rule_chips):
            b.rect = pygame.Rect(ix + i * (rw + g), y, rw if i == 0 else iw - rw - g, px(38))
        y += px(38) + px(10)
        self.rule_info = pygame.Rect(ix, y, iw, px(44))      # o minh hoa luat
        y += px(44) + sec
        self.lbl_theme = (ix, y)
        y += lbl_h + px(10)
        g2 = px(12)
        sw = (iw - 3 * g2) // 4
        for i, s in enumerate(self.swatches):
            s.rect = pygame.Rect(ix + i * (sw + g2), y, sw, px(90))

        # left column
        self.title_s = gradient_text('TDCaro', px(108), 'black', self.app.th['x'], self.app.th['o'])
        left_h = px(84) + px(10) + self.title_s.get_height() + px(14) + px(30) + px(16) + px(48) + px(24) + px(48) + px(28) + px(60) + px(12) + px(50) + px(12) + px(46)
        y = (H - left_h) // 2 - px(12)
        self.ly = y
        self.logo_y = y + px(42)
        y += px(84) + px(10)
        self.title_y = y
        y += self.title_s.get_height() + px(14)
        self.sub_y = y
        y += px(30) + px(16)
        self.desc_y = y
        y += px(48) + px(24)
        self.score_y = y
        y += px(48) + px(28)
        bw = px(380)
        self.btn_start.rect = pygame.Rect(lx, y, bw, px(60))
        y += px(60) + px(12)
        self.btn_online.rect = pygame.Rect(lx, y, bw, px(50))
        y += px(50) + px(12)
        hw = (bw - px(12)) // 2
        self.btn_quit.rect = pygame.Rect(lx, y, hw, px(46))
        self.btn_sound.rect = pygame.Rect(lx + hw + px(12), y, bw - hw - px(12), px(46))
        if IS_WEB:                      # trinh duyet: khong co "Thoat"
            self.btn_quit.rect = pygame.Rect(0, 0, 0, 0)
            self.btn_sound.rect = pygame.Rect(lx, y, bw, px(46))

    # ---- loop
    def handle(self, ev):
        for b in self.buttons:
            if b.handle(ev, self.app):
                return
        if ev.type == pygame.MOUSEWHEEL and self.size_rect.collidepoint(pygame.mouse.get_pos()):
            self.change_size(1 if ev.y > 0 else -1)
            return
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.app.start_game()
            elif k in (pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_DOWN):
                self.change_size(-1)
            elif k in (pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_UP):
                self.change_size(1)
            elif k == pygame.K_t:
                self.app.cycle_theme()
            elif k == pygame.K_f:
                self.set_first('ai' if self.app.settings['first'] == 'player' else 'player')
            elif k == pygame.K_l:
                self.toggle_rule()
            elif k == pygame.K_o:
                self.app.go_online()
            elif k == pygame.K_d:
                self.cycle_level()
            elif k == pygame.K_m:
                self.app.toggle_sound()
            elif k == pygame.K_b:
                self.app.toggle_music()
            elif k == pygame.K_r:
                self.app.reset_scores()
            elif k == pygame.K_ESCAPE and self.app.fullscreen:
                self.app.toggle_fullscreen()
            elif k in (pygame.K_ESCAPE, pygame.K_q):
                self.app.quit()

    def draw_rule_info(self, surf, th, block):
        """O minh hoa luat: so do quan co + cau giai thich."""
        r = self.rule_info
        accent = th['x'] if block else th['o']
        bg = lerp_color(th['panel_alt'], accent, 0.07)
        surf.blit(round_rect_surf(r.w, r.h, px(12), bg, lerp_color(th['border'], accent, 0.35), 1), r.topleft)
        # so do: cac quan co tren 1 "rang" nho
        ps, step = px(22), px(23)
        seq = 'oxxxxxo' if block else 'xxxxx'
        x0, cy = r.x + px(12), r.centery
        for i, k in enumerate(seq):
            blit_center(surf, themed_piece(k, ps, th, effects=False), (x0 + i * step + step // 2, cy))
        dw = len(seq) * step
        if block:
            # gach ngang qua day X bi chan 2 dau -> "khong tinh"
            xa, xb = x0 + step + px(2), x0 + 6 * step - px(2)
            pygame.draw.line(surf, th['text'], (xa, cy), (xb, cy), max(2, px(2)))
        # nhan ket qua (ben phai)
        label = 'KHÔNG THẮNG' if block else 'THẮNG'
        ls = spaced_text_surf(label, px(11), accent, 'bold', px(1))
        bw, bh = ls.get_width() + px(20), px(24)
        br = pygame.Rect(r.right - px(10) - bw, cy - bh // 2, bw, bh)
        surf.blit(round_rect_surf(bw, bh, bh // 2, lerp_color(th['panel_alt'], accent, 0.22)), br.topleft)
        surf.blit(ls, ls.get_rect(center=br.center))
        # mo ta
        title = 'Bị chặn hai đầu' if block else '5 quân liên tiếp'
        draw_text(surf, title, px(14), th['text'], (x0 + dw + px(12), cy), 'semibold', 'midleft')

    def score_pill(self, th):
        sc = self.app.scores
        lab = spaced_text_surf('TỈ SỐ', px(11), th['text_dim'], 'bold', px(2))
        t1 = text_surf('Bạn', px(15), th['text'], 'semibold')
        n1 = text_surf(str(sc['player']), px(20), th['x'], 'black')
        dash = text_surf('–', px(18), th['text_dim'], 'semibold')
        n2 = text_surf(str(sc['ai']), px(20), th['o'], 'black')
        t2 = text_surf('AI', px(15), th['text'], 'semibold')
        parts = [lab, t1, n1, dash, n2, t2]
        gaps = [px(16), px(8), px(10), px(10), px(8)]
        pw = sum(p.get_width() for p in parts) + sum(gaps) + px(40)
        return parts, gaps, pygame.Rect(self.lx, self.score_y, pw, px(48))

    def update(self, dt):
        mouse = pygame.mouse.get_pos()
        pr = self.score_pill(self.app.th)[2]
        rw = text_surf('Đặt lại', px(13), (0, 0, 0), 'semibold').get_width() + px(36)
        self.btn_reset.rect = pygame.Rect(pr.right + px(12), pr.centery - px(18), rw, px(36))
        up = self.app.updater
        W = self.app.size[0]
        fw = text_surf(self.btn_full.text(), px(13), (0, 0, 0), 'semibold').get_width() + px(40)
        self.btn_full.rect = pygame.Rect(W - px(24) - fw, px(20), fw, px(40))
        nw = text_surf(self.btn_next.text(), px(13), (0, 0, 0), 'semibold').get_width() + px(40)
        self.btn_next.rect = pygame.Rect(self.btn_full.rect.x - px(12) - nw, px(20), nw, px(40))
        mw = text_surf(self.btn_music.text(), px(13), (0, 0, 0), 'semibold').get_width() + px(40)
        self.btn_music.rect = pygame.Rect(self.btn_next.rect.x - px(8) - mw, px(20), mw, px(40))
        if up.visible():
            tw = text_surf(up.label(), px(13), (0, 0, 0), 'semibold').get_width()
            self.btn_update.rect = pygame.Rect(self.btn_music.rect.x - px(12) - tw - px(40), px(20), tw + px(40), px(40))
        else:
            self.btn_update.rect = pygame.Rect(0, 0, 0, 0)
        for b in self.buttons:
            b.update(dt, mouse)
        self.size_pulse = approach(self.size_pulse, 0.0, dt, 8)
        self.want_hand = any(b.hovered for b in self.buttons)

    def draw(self, surf):
        app, th, now = self.app, self.app.th, self.app.now
        W, H = app.size
        surf.blit(background(W, H, th), (0, 0))
        app.floats.draw(surf, th, now)

        # ----- left hero column
        x = self.lx
        bob = math.sin(now * 2.2) * px(5)
        blit_center(surf, themed_piece('x', px(68), th), (x + px(36), self.logo_y + bob))
        blit_center(surf, themed_piece('o', px(68), th), (x + px(36) + px(80), self.logo_y - bob))
        title = gradient_text('TDCaro', px(108), 'black', th['x'], th['o'])
        sh = title.copy()
        sh.fill((0, 0, 0, 70 if not th['dark'] else 140), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(sh, (x + px(2), self.title_y + px(6)))
        surf.blit(title, (x - px(2), self.title_y))
        draw_spaced(surf, 'AI CHALLENGE  ·  GOMOKU', px(20), th['bg_accent'], (x, self.sub_y), 'bold', px(4))
        draw_text(surf, 'Nối 5 quân liên tiếp theo hàng ngang, dọc hoặc chéo',
                  px(16), th['bg_text_dim'], (x, self.desc_y))
        draw_text(surf, 'để giành chiến thắng trước trí tuệ nhân tạo.',
                  px(16), th['bg_text_dim'], (x, self.desc_y + px(24)))

        # score pill
        parts, gaps, pr = self.score_pill(th)
        draw_card(surf, pr, px(24), th['panel'], th['border'], 1, (px(16), th['shadow_alpha'] // 2, px(5)))
        cx = pr.x + px(20)
        for i, p in enumerate(parts):
            surf.blit(p, p.get_rect(midleft=(cx, pr.centery)))
            cx += p.get_width() + (gaps[i] if i < len(gaps) else 0)

        self.btn_reset.draw(surf, th)
        for b in (self.btn_start, self.btn_online, self.btn_quit, self.btn_sound):
            b.draw(surf, th)

        # ----- settings card
        draw_card(surf, self.card, px(24), th['panel'], th['border'], 1, (px(34), th['shadow_alpha'], px(14)))
        draw_spaced(surf, 'KÍCH THƯỚC BÀN CỜ', px(12), th['text_dim'], self.lbl_size, 'bold')
        sr = self.size_rect
        surf.blit(round_rect_surf(sr.w, sr.h, px(14), th['panel_alt'], th['border'], 1), sr)
        n = app.settings['size']
        fs = px(28) + int(px(6) * self.size_pulse)
        draw_text(surf, f'{n} × {n}', fs, th['accent'], sr.center, 'black', 'center')
        draw_spaced(surf, 'ĐỘ KHÓ', px(12), th['text_dim'], self.lbl_level, 'bold')
        draw_spaced(surf, 'NGƯỜI ĐI TRƯỚC', px(12), th['text_dim'], self.lbl_first, 'bold')
        draw_spaced(surf, 'LUẬT CHƠI', px(12), th['text_dim'], self.lbl_rule, 'bold')
        self.draw_rule_info(surf, th, app.settings['rule'] == 'block')
        draw_spaced(surf, 'GIAO DIỆN', px(12), th['text_dim'], self.lbl_theme, 'bold')
        for b in ([self.btn_minus, self.btn_plus, self.btn_first_p, self.btn_first_a] + self.chips +
                  self.level_chips + self.rule_chips + self.swatches):
            b.draw(surf, th)

        # footer
        draw_text(surf, 'Space: bắt đầu  ·  Mũi tên: kích thước  ·  D: độ khó  ·  L: luật  ·  F: người đi trước  ·  T: giao diện  ·  M: âm thanh  ·  R: đặt lại tỉ số  ·  B: nhạc  ·  K: đổi bài  ·  F11: toàn màn hình  ·  Esc: thoát',
                  px(13), th['bg_text_dim'], (W // 2, H - px(22)), 'regular', 'center')
        draw_text(surf, f'v{APP_VERSION}', px(12), th['bg_text_dim'], (W - px(20), H - px(22)), 'semibold', 'midright')
        self.btn_full.draw(surf, th)
        self.btn_music.draw(surf, th)
        self.btn_next.draw(surf, th)
        if app.updater.visible():
            self.btn_update.draw(surf, th)


# ================================ GAME SCREEN ===============================

class GameScreen:
    def __init__(self, app):
        self.app = app
        st = app.settings
        self.online = False             # True: dang choi online (doi thu la nguoi that)
        self.ost = None                 # trang thai phong moi nhat tu server
        self.btn_new = Button(self.new_label, self.new_game, 'primary', 'N', font_size=15,
                              enabled=lambda: not self.online or self.rematch_ok())
        self.btn_undo = Button('Đi lại', self.undo, hotkey='U', enabled=self.can_undo, font_size=14)
        self.btn_hint = Button('Gợi ý', self.request_hint, hotkey='H', enabled=self.can_hint, font_size=14)
        self.btn_theme = Button('Giao diện', app.cycle_theme, hotkey='T', font_size=14)
        self.btn_sound = Button(lambda: 'Âm thanh: Bật' if st['sound'] else 'Âm thanh: Tắt',
                                app.toggle_sound, hotkey='M', font_size=14)
        self.btn_menu = Button(lambda: 'Rời phòng' if self.online else 'Về menu', self.go_back, hotkey='ESC', font_size=14)
        self.btn_full = Button(lambda: 'Thu nhỏ' if app.fullscreen else 'Toàn màn hình',
                               app.toggle_fullscreen, hotkey='F11', font_size=14)
        self.btn_music = Button(lambda: 'Nhạc nền: Bật' if st['music'] else 'Nhạc nền: Tắt',
                                app.toggle_music, hotkey='B', font_size=14)
        self.buttons = [self.btn_new, self.btn_undo, self.btn_hint, self.btn_theme, self.btn_sound, self.btn_menu,
                        self.btn_full, self.btn_music]
        modal_ok = lambda: self.modal_t > 0.85
        self.btn_again = Button(self.new_label, self.new_game, 'primary', 'N',
                                enabled=lambda: modal_ok() and (not self.online or self.rematch_ok()), font_size=15)
        self.btn_view = Button('Xem bàn cờ', self.hide_modal, enabled=modal_ok, font_size=15)
        self.modal_buttons = [self.btn_again, self.btn_view]
        self.confetti = Confetti()
        self.token = 0
        self.want_hand = False
        self.reset_state()

    # ------------------------------------------------------------ state
    def reset_state(self):
        self.N = self.app.settings['size']
        self.level = self.app.settings.get('level', 'normal')
        self.block = self.app.settings.get('rule', 'block') == 'block'
        self.rule_line = None
        self.board = make_empty_board(self.N)
        self.moves = []                 # (col, row, who)  who in {'player','ai'}
        self.anim = {}
        self.turn = 'player'
        self.over = False
        self.result = None
        self.win_cells = []
        self.win_t0 = 0.0
        self.ai_job = None
        self.hint_job = None
        self.hint = None
        self.hint_t0 = 0.0
        self.hover = None
        self.modal_visible = False
        self.modal_pending = False
        self.modal_show_at = 0.0
        self.modal_t = 0.0
        self.confetti_pending = False
        self.confetti.clear()
        self.start_time = time.perf_counter()
        self.end_time = None
        self.toast = None
        self.pill_rect = pygame.Rect(0, 0, 0, 0)
        self.pending = False            # online: da gui nuoc, cho server xac nhan

    # ------------------------------------------------------------ online
    def new_label(self):
        if not self.online:
            return 'Ván mới'
        st = self.ost or {}
        if (st.get('you') or {}).get('rematch'):
            return 'Đang chờ đối thủ…'
        if (st.get('opp') or {}).get('rematch'):
            return 'Đồng ý chơi lại'
        return 'Chơi lại'

    def rematch_ok(self):
        st = self.ost or {}
        return st.get('status') == 'over' and st.get('opp') is not None and not (st.get('you') or {}).get('rematch')

    def go_back(self):
        if self.online:
            self.app.leave_online_game()
        else:
            self.app.go_menu()

    def start_online(self, st):
        self.online = True
        self.token += 1
        self.ost = None
        self._online_reset(st)
        self.apply_state(st)

    def stop_online(self):
        self.online = False
        self.ost = None
        self.cancel_jobs()

    def _online_reset(self, st):
        self.reset_state()
        self.N = st['size']
        self.block = st['rule'] == 'block'
        self.board = make_empty_board(self.N)
        self.layout()

    def apply_state(self, st):
        """Dong bo ban co voi trang thai phong tu server (server la trong tai)."""
        prev = self.ost
        self.ost = st
        self.pending = False
        me = (st.get('you') or {}).get('color', 'x')
        moves = st.get('moves') or []
        mine = [(r, c) for (c, r, _) in self.moves]
        new_game = (prev is not None and prev.get('status') == 'over' and st.get('status') == 'playing') or \
            len(moves) < len(mine) or [tuple(m) for m in moves[:len(mine)]] != mine or st['size'] != self.N
        if new_game:
            self._online_reset(st)
            if prev is not None:
                self.show_toast('Ván mới bắt đầu!' if st.get('status') == 'playing' else 'Đã đồng bộ lại bàn cờ')
        start = len(self.moves)
        for i in range(start, len(moves)):
            r, c = moves[i]
            color = 'x' if i % 2 == 0 else 'o'
            who = 'player' if color == me else 'ai'
            self.board[r][c] = 'r' if who == 'player' else 'w'
            self.moves.append((c, r, who))
            if i == len(moves) - 1:
                self.anim[(c, r)] = self.app.now
                self.app.sound.play('place' if who == 'player' else 'ai')
        status = st.get('status')
        if status == 'playing':
            self.turn = 'player' if st.get('turn') == me else 'ai'
        if status == 'over' and not self.over:
            w = st.get('winner')
            res = 'Draw' if w == 'draw' else ('Player Win' if w == me else 'NPC Win')
            self.rule_line = [tuple(x) for x in (st.get('line') or [])] or None
            self.finish(res)
        # doi thu vua roi phong / mat ket noi -> bao
        if prev is not None:
            po, no = prev.get('opp'), st.get('opp')
            if po and not no:
                self.show_toast('Đối thủ đã rời phòng')
            elif po and no and po.get('online') and not no.get('online'):
                self.show_toast(f'{no["name"]} mất kết nối — chờ tối đa 60 giây')
            elif po and no and not po.get('online') and no.get('online'):
                self.show_toast(f'{no["name"]} đã quay lại')
            elif no and no.get('rematch') and not (po or {}).get('rematch'):
                self.show_toast(f'{no["name"]} muốn chơi ván nữa')

    def on_net(self, msgs):
        net = self.app.net
        if any(m.get('t') == 'state' for m in msgs) and net.state:
            self.apply_state(net.state)
        for m in msgs:
            if m.get('t') == 'error':
                self.pending = False
                self.show_toast(m.get('msg') or 'Có lỗi xảy ra')
            elif m.get('t') == '_offline':
                self.show_toast('Mất kết nối — đang kết nối lại…')
            elif m.get('t') == 'left':
                self.app.leave_online_game(already_left=True)

    def opp_name(self):
        return ((self.ost or {}).get('opp') or {}).get('name') or 'Đối thủ'

    def new_game(self):
        if self.online:
            if self.rematch_ok():
                self.app.net.rematch()
                self.show_toast('Đã gửi lời mời chơi lại')
            return
        self.token += 1
        self.reset_state()
        self.layout()
        if self.app.settings['first'] == 'ai':
            self.turn = 'ai'
            self.start_ai()

    def cancel_jobs(self):
        self.token += 1
        self.ai_job = None
        self.hint_job = None

    def _run_job(self, color, level):
        board_copy = [row[:] for row in self.board]
        block = self.block
        job = {'token': self.token, 'done': False, 'result': None, 't0': time.perf_counter()}

        def work():
            try:
                job['result'] = ai_move(board_copy, color, level, block)   # 'easy' = AI ENGINE GOC
            except Exception:
                try:
                    job['result'] = best_move(board_copy, color)
                except Exception:
                    job['result'] = None
            job['done'] = True
        if IS_WEB:
            job['work'] = work          # WebAssembly khong co luong: chay o update() sau khi da ve 1 frame
        else:
            threading.Thread(target=work, daemon=True).start()
        return job

    def start_ai(self):
        if self.online:
            return
        self.ai_job = self._run_job('w', self.level)

    def can_play(self):
        if self.online:
            return (not self.over and self.turn == 'player' and not self.pending and not self.modal_visible and
                    (self.ost or {}).get('status') == 'playing')
        return not self.over and self.turn == 'player' and self.ai_job is None and not self.modal_visible

    def can_undo(self):
        return not self.online and self.ai_job is None and any(m[2] == 'player' for m in self.moves) and (self.over or self.turn == 'player')

    def can_hint(self):
        return not self.online and self.can_play() and self.hint_job is None

    def request_hint(self):
        if self.can_hint():
            self.hint_job = self._run_job('r', 'hard')

    def place(self, c, r, who):
        if self.online:
            # online: chi gui nuoc len server; ban co cap nhat khi server xac nhan (apply_state)
            if who == 'player' and self.app.net and self.app.net.move(r, c):
                self.pending = True
            return
        self.board[r][c] = 'r' if who == 'player' else 'w'
        self.moves.append((c, r, who))
        self.anim[(c, r)] = self.app.now
        self.hint = None
        self.app.sound.play('place' if who == 'player' else 'ai')
        if self.block:
            # luat chan hai dau: kiem tra day thang qua nuoc vua danh
            self.rule_line = rule_win_cells(self.board, r, c, True)
            res = ('Player Win' if who == 'player' else 'NPC Win') if self.rule_line else 'Continue playing'
        else:
            res = is_win(self.board)                               # AI ENGINE GOC (luat tu do)
        if res == 'Continue playing' and all(cell != ' ' for row in self.board for cell in row):
            res = 'Draw'          # ban co da kin -> hoa
        if res != 'Continue playing':
            self.finish(res)
            return
        self.turn = 'ai' if who == 'player' else 'player'
        if self.turn == 'ai':
            self.start_ai()

    def finish(self, res):
        now = self.app.now
        self.over = True
        self.result = res
        self.turn = None
        self.end_time = time.perf_counter()
        col = None
        scores = self.app.scores if not self.online else {'player': 0, 'ai': 0, 'draw': 0}   # online: ti so do server giu
        if res == 'Player Win':
            scores['player'] += 1
            col = 'r'
            self.app.sound.play('win')
            self.confetti_pending = True
        elif res == 'NPC Win':
            scores['ai'] += 1
            col = 'w'
            self.app.sound.play('lose')
        else:
            scores['draw'] += 1
            self.app.sound.play('draw')
        self.win_cells = []
        if col and self.online:
            self.win_cells = [(cc, rr) for rr, cc in (self.rule_line or [])]
        elif col and self.block and self.rule_line:
            self.win_cells = [(cc, rr) for rr, cc in self.rule_line]
        elif col:
            line = find_winning_line(self.board, col)              # AI ENGINE GOC
            if line:
                sy, sx, ey, ex = line
                dy = (ey > sy) - (ey < sy)
                dx = (ex > sx) - (ex < sx)
                self.win_cells = [(sx + i * dx, sy + i * dy) for i in range(5)]
        self.win_t0 = now
        self.modal_pending = True
        self.modal_show_at = now + (1.1 if self.win_cells else 0.4)

    def undo(self):
        if not self.can_undo():
            return
        if self.over:
            key = {'Player Win': 'player', 'NPC Win': 'ai'}.get(self.result, 'draw')
            self.app.scores[key] = max(0, self.app.scores[key] - 1)
            self.over = False
            self.result = None
            self.win_cells = []
            self.modal_visible = self.modal_pending = self.confetti_pending = False
            self.confetti.clear()
            self.end_time = None
        self.cancel_jobs()
        if self.moves and self.moves[-1][2] == 'ai':
            c, r, _ = self.moves.pop()
            self.board[r][c] = ' '
        if self.moves and self.moves[-1][2] == 'player':
            c, r, _ = self.moves.pop()
            self.board[r][c] = ' '
        self.turn = 'player'
        self.hint = None
        self.show_toast('Đã lùi lại một nước')

    def hide_modal(self):
        self.modal_visible = False

    def show_toast(self, txt):
        self.toast = (txt, self.app.now)

    # ------------------------------------------------------------ layout
    def layout(self):
        W, H = self.app.size
        m = px(24)
        pw = px(340)
        self.panel = pygame.Rect(W - pw - m, m, pw, H - 2 * m)
        self.area = pygame.Rect(m, m, self.panel.x - 2 * m, H - 2 * m)
        N = self.N
        lm, pad, depth = px(30), px(14), px(10)
        avail = min(self.area.w - 2 * lm, self.area.h - 2 * lm - depth) - 2 * pad
        self.cell = max(12, int(avail // N))
        gw = self.cell * N
        sw = gw + 2 * pad
        self.pad, self.depth = pad, depth
        self.slab = pygame.Rect(self.area.centerx - sw // 2, self.area.centery - (sw + depth) // 2, sw, sw)
        self.gx, self.gy = self.slab.x + pad, self.slab.y + pad
        self.line_layer = pygame.Surface(self.slab.size, pygame.SRCALPHA, 32)

        p = self.panel
        pd = px(20)
        x, w, y = p.x + pd, p.w - 2 * pd, p.y + pd
        self.r_header = pygame.Rect(x, y, w, px(50))
        y += px(50) + px(14)
        cw = (w - px(12)) // 2
        ch = px(126)
        self.r_card_p = pygame.Rect(x, y, cw, ch)
        self.r_card_a = pygame.Rect(x + cw + px(12), y, w - cw - px(12), ch)
        y += ch + px(12)
        self.r_status = pygame.Rect(x, y, w, px(30))
        y += px(30) + px(12)
        g = px(10)
        tw = (w - 2 * g) // 3
        self.r_stats = [pygame.Rect(x + i * (tw + g), y, tw, px(62)) for i in range(3)]
        y += px(62) + px(16)
        self.r_hist_title = (x, y)
        y += px(20) + px(8)
        bh, g = px(44), px(10)
        by = p.bottom - pd - bh
        half = (w - g) // 2
        self.btn_menu.rect = pygame.Rect(x, by, w, bh)
        by -= bh + g
        self.btn_theme.rect = pygame.Rect(x, by, half, bh)
        self.btn_full.rect = pygame.Rect(x + half + g, by, w - half - g, bh)
        by -= bh + g
        self.btn_sound.rect = pygame.Rect(x, by, half, bh)
        self.btn_music.rect = pygame.Rect(x + half + g, by, w - half - g, bh)
        by -= bh + g
        self.btn_undo.rect = pygame.Rect(x, by, half, bh)
        self.btn_hint.rect = pygame.Rect(x + half + g, by, w - half - g, bh)
        by -= bh + g
        self.btn_new.rect = pygame.Rect(x, by, w, bh)
        self.r_hist = pygame.Rect(x, y, w, max(px(36), by - px(16) - y))

    def cell_at(self, pos):
        c = (pos[0] - self.gx) // self.cell
        r = (pos[1] - self.gy) // self.cell
        if 0 <= c < self.N and 0 <= r < self.N:
            return int(c), int(r)
        return None

    def cell_center(self, c, r):
        return (self.gx + c * self.cell + self.cell / 2, self.gy + r * self.cell + self.cell / 2)

    # ------------------------------------------------------------ loop
    def handle(self, ev):
        if self.modal_visible:
            for b in self.modal_buttons:
                if b.handle(ev, self.app):
                    return
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                return
        for b in self.buttons:
            if b.handle(ev, self.app):
                return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.over and not self.modal_visible and self.pill_rect.collidepoint(ev.pos):
                self.modal_visible = True
                return
            cell = self.cell_at(ev.pos)
            if cell and self.can_play():
                c, r = cell
                if self.board[r][c] == ' ':
                    self.place(c, r, 'player')
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_n, pygame.K_SPACE, pygame.K_F2) or (k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.over):
                self.new_game()
            elif k == pygame.K_u or (k == pygame.K_z and ev.mod & pygame.KMOD_CTRL):
                self.undo()
            elif k == pygame.K_h:
                self.request_hint()
            elif k == pygame.K_t:
                self.app.cycle_theme()
            elif k == pygame.K_m:
                self.app.toggle_sound()
            elif k == pygame.K_b:
                self.app.toggle_music()
            elif k == pygame.K_r and not self.online:
                self.app.reset_scores()
            elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.go_back()

    def update(self, dt):
        app, now = self.app, self.app.now
        mouse = pygame.mouse.get_pos()
        modal_on = self.modal_visible
        for b in self.buttons:
            b.update(dt, mouse if not modal_on else (-999, -999))
        for b in self.modal_buttons:
            b.update(dt, mouse if modal_on else (-999, -999))

        # web: chay viec AI dang cho (sau khi da ve it nhat 1 frame "dang suy nghi")
        for j in (self.ai_job, self.hint_job):
            if j and 'work' in j and time.perf_counter() - j['t0'] > 0.06:
                j.pop('work')()
        # ket qua AI
        job = self.ai_job
        if job and job['done'] and time.perf_counter() - job['t0'] >= AI_MIN_THINK:
            self.ai_job = None
            if job['token'] == self.token and not self.over and self.turn == 'ai':
                mv = job['result']
                if mv is None or not (0 <= mv[0] < self.N and 0 <= mv[1] < self.N) or self.board[mv[0]][mv[1]] != ' ':
                    empties = [(r, c) for r in range(self.N) for c in range(self.N) if self.board[r][c] == ' ']
                    mv = random.choice(empties) if empties else None
                if mv:
                    r, c = mv
                    self.place(c, r, 'ai')
        hj = self.hint_job
        if hj and hj['done']:
            self.hint_job = None
            if hj['token'] == self.token and self.can_play() and hj['result']:
                r, c = hj['result']
                if self.board[r][c] == ' ':
                    self.hint = (c, r)
                    self.hint_t0 = now
                    app.sound.play('hint')
        if self.hint and now - self.hint_t0 > 5:
            self.hint = None

        if self.over and self.modal_pending and now >= self.modal_show_at:
            self.modal_pending = False
            self.modal_visible = True
        self.modal_t = approach(self.modal_t, 1.0 if self.modal_visible else 0.0, dt, 9)

        if self.confetti_pending and now >= self.win_t0 + 0.55:
            self.confetti_pending = False
            if self.win_cells:
                cx, cy = self.cell_center(*self.win_cells[2])
            else:
                cx, cy = self.slab.center
            th = app.th
            self.confetti.burst(cx, cy, [th['x'], th['o'], th['gold'], th['accent'], (255, 255, 255)])
        self.confetti.update(dt, app.size[1])

        self.hover = None
        if self.can_play():
            cell = self.cell_at(mouse)
            if cell and self.board[cell[1]][cell[0]] == ' ':
                self.hover = cell

        # vi tri modal (truot len khi hien)
        mw, mh = px(440), px(340)
        mr = pygame.Rect(0, 0, mw, mh)
        mr.center = (self.area.centerx, self.area.centery + int((1 - ease_out_cubic(self.modal_t)) * px(40)))
        self.modal_rect = mr
        bw = (mw - 2 * px(28) - px(12)) // 2
        by = mr.bottom - px(28) - px(48)
        self.btn_again.rect = pygame.Rect(mr.x + px(28), by, bw, px(48))
        self.btn_view.rect = pygame.Rect(mr.x + px(28) + bw + px(12), by, bw, px(48))

        pill_hover = self.over and not self.modal_visible and self.pill_rect.collidepoint(mouse)
        self.want_hand = (any(b.hovered for b in self.buttons) or self.hover is not None or pill_hover or
                          (modal_on and any(b.hovered for b in self.modal_buttons)))

    # ------------------------------------------------------------ drawing
    def board_surface(self, th):
        key = ('board', self.N, self.cell, self.pad, self.depth, th['key'])

        def make():
            N, cell, pad, depth = self.N, self.cell, self.pad, self.depth
            W = cell * N + 2 * pad
            s = pygame.Surface((W, W + depth), pygame.SRCALPHA, 32)
            s.fill((0, 0, 0, 0))
            rad = px(18)
            s.blit(round_rect_surf(W, W, rad, th['board_edge']), (0, depth))
            s.blit(round_rect_surf(W, W, rad, th['board'], lighten(th['board'], 0.25), max(1, px(2))), (0, 0))
            if th['style'] == 'grid':
                inner = pygame.Rect(pad, pad, cell * N, cell * N)
                rnd = random.Random(3)
                grain = pygame.Surface((W, W), pygame.SRCALPHA, 32)
                for _ in range(46):
                    yy = rnd.uniform(px(6), W - px(6))
                    c = (*darken(th['board'], rnd.uniform(0.05, 0.14)), rnd.randint(30, 70))
                    pts = [(xx, yy + math.sin(xx / rnd.uniform(40, 90) + rnd.random() * 6) * px(2))
                           for xx in range(px(10), W - px(10), 8)]
                    if len(pts) > 1:
                        pygame.draw.lines(grain, c, False, pts, 1)
                s.blit(grain, (0, 0))
                for i in range(N + 1):
                    w = max(1, px(2)) if i in (0, N) else 1
                    pygame.draw.line(s, th['grid'], (inner.x + i * cell, inner.y), (inner.x + i * cell, inner.bottom), w)
                    pygame.draw.line(s, th['grid'], (inner.x, inner.y + i * cell), (inner.right, inner.y + i * cell), w)
            else:
                gap = max(1, round(cell * 0.05))
                tsz = cell - 2 * gap
                trad = max(2, int(cell * 0.2))
                ta = round_rect_surf(tsz, tsz, trad, th['cell_a'])
                tb = round_rect_surf(tsz, tsz, trad, th['cell_b'])
                for rr in range(N):
                    for cc in range(N):
                        s.blit(ta if (rr + cc) % 2 == 0 else tb, (pad + cc * cell + gap, pad + rr * cell + gap))
            return s
        return cached(key, make)

    def draw_board(self, surf, th, now):
        slab, cell = self.slab, self.cell
        sh, pad = shadow_surf(slab.w, slab.h + self.depth, px(18), px(26), th['shadow_alpha'])
        surf.blit(sh, (slab.x - pad, slab.y - pad + px(14)))
        surf.blit(self.board_surface(th), slab.topleft)

        fs = int(clamp(cell * 0.3, px(10), px(15)))
        for i in range(self.N):
            cx, cy = self.cell_center(i, i)
            draw_text(surf, COL_LETTERS[i], fs, th['bg_text_dim'], (cx, slab.y - px(14)), 'bold', 'center')
            draw_text(surf, str(i + 1), fs, th['bg_text_dim'], (slab.x - px(16), cy), 'bold', 'center')

        gap = max(1, round(cell * 0.05))
        tsz = cell - 2 * gap
        trad = max(2, int(cell * 0.2))
        psize = int(cell * 0.78)

        # goi y
        if self.hint:
            c, r = self.hint
            a = int(110 + 80 * math.sin(now * 7))
            t = round_rect_surf(tsz, tsz, trad, (*th['gold'], 255)).copy()
            t.set_alpha(a)
            surf.blit(t, (self.gx + c * cell + gap, self.gy + r * cell + gap))
            g = piece_sprite('x', psize, th['x']).copy()
            g.set_alpha(120)
            blit_center(surf, g, self.cell_center(c, r))
        # hover
        if self.hover:
            c, r = self.hover
            surf.blit(round_rect_surf(tsz, tsz, trad, (*th['accent'], 70 if th['dark'] else 55)),
                      (self.gx + c * cell + gap, self.gy + r * cell + gap))
            g = flat_sprite('x', psize, th['x'], 110)
            blit_center(surf, g, self.cell_center(c, r))

        # quan co
        win_done = self.win_cells and now - self.win_t0 > 0.55
        win_idx = {c: i for i, c in enumerate(self.win_cells)}
        last = self.moves[-1] if self.moves else None
        for (c, r, who) in self.moves:
            kind = 'x' if who == 'player' else 'o'
            spr = themed_piece(kind, psize, th)
            scale = 1.0
            t0 = self.anim.get((c, r))
            if t0 is not None:
                k = (now - t0) / 0.3
                if k < 1:
                    scale = max(0.05, ease_out_back(k))
                else:
                    del self.anim[(c, r)]
            if win_done and (c, r) in win_idx:
                scale *= 1 + 0.09 * max(0.0, math.sin(now * 5 - win_idx[(c, r)] * 0.6))
            if abs(scale - 1.0) > 0.01:
                w = max(1, int(spr.get_width() * scale))
                spr = pygame.transform.smoothscale(spr, (w, w))
            blit_center(surf, spr, self.cell_center(c, r))

        # danh dau nuoc vua di
        if last and not self.over:
            c, r, _ = last
            ring = round_rect_surf(cell - 2, cell - 2, trad + 1, (*th['gold'], 0), th['gold'], max(2, px(2)))
            rr = ring.copy()
            rr.set_alpha(int(170 + 85 * math.sin(now * 5)))
            surf.blit(rr, (self.gx + c * cell + 1, self.gy + r * cell + 1))

        # duong thang
        if self.win_cells:
            k = ease_out_cubic(clamp((now - self.win_t0) / 0.55, 0, 1))
            lay = self.line_layer
            lay.fill((0, 0, 0, 0))
            p1 = self.cell_center(*self.win_cells[0])
            p2 = self.cell_center(*self.win_cells[-1])
            p1 = (p1[0] - self.slab.x, p1[1] - self.slab.y)
            p2 = (p2[0] - self.slab.x, p2[1] - self.slab.y)
            pe = (p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)
            gcol = th['gold']
            thick_line(lay, (*gcol, 55), p1, pe, cell * 0.5)
            thick_line(lay, (*gcol, 120), p1, pe, cell * 0.28)
            thick_line(lay, (*lighten(gcol, 0.45), 255), p1, pe, max(3, cell * 0.11))
            surf.blit(lay, self.slab.topleft)

    def draw_player_card(self, surf, r, who, th, now):
        active = (not self.over and self.turn == who)
        won = self.over and ((who == 'player' and self.result == 'Player Win') or (who == 'ai' and self.result == 'NPC Win'))
        kind = 'x' if who == 'player' else 'o'
        color = th[kind]
        hl = active or won
        if hl:
            sh, pad = shadow_surf(r.w, r.h, px(16), px(16), 140 if th['dark'] else 90, color)
            surf.blit(sh, (r.x - pad, r.y - pad + px(4)))
        bg = lerp_color(th['panel_alt'], color, 0.07) if hl else th['panel_alt']
        surf.blit(round_rect_surf(r.w, r.h, px(16), bg, color if hl else th['border'], px(2) if hl else 1), r)
        bob = math.sin(now * 4) * px(2) if active else 0
        blit_center(surf, themed_piece(kind, px(34), th), (r.centerx, r.y + px(32) + bob))
        if self.online:
            st = self.ost or {}
            pl = st.get('you') if who == 'player' else st.get('opp')
            name = 'BẠN' if who == 'player' else (pl['name'].upper() if pl else 'ĐANG CHỜ…')
            while text_surf(name, px(11), th['text_dim'], 'bold').get_width() > r.w - px(24) and len(name) > 3:
                name = name[:-2] + '…'
            sc = pl['score'] if pl else 0
            if who == 'ai' and pl and not pl.get('online'):
                tag = spaced_text_surf('MẤT KẾT NỐI', px(9), th['on_accent'], 'bold', px(1))
                trr = pygame.Rect(0, 0, tag.get_width() + px(16), px(20))
                trr.center = (r.centerx, r.bottom)
                surf.blit(round_rect_surf(trr.w, trr.h, px(9), th['gold']), trr)
                surf.blit(tag, tag.get_rect(center=trr.center))
        else:
            name = 'BẠN' if who == 'player' else 'MÁY (AI)'
            sc = self.app.scores['player' if who == 'player' else 'ai']
        draw_spaced(surf, name, px(11), th['text_dim'], (r.centerx, r.y + px(64)), 'bold', anchor='center')
        draw_text(surf, str(sc), px(30), color if hl else th['text'], (r.centerx, r.y + px(96)), 'black', 'center')
        if active or won:
            tag = 'ĐẾN LƯỢT' if active else 'CHIẾN THẮNG'
            ts = spaced_text_surf(tag, px(9), th['on_accent'], 'bold', px(1))
            tr = pygame.Rect(0, 0, ts.get_width() + px(16), px(20))
            tr.center = (r.centerx, r.y)
            surf.blit(round_rect_surf(tr.w, tr.h, px(9), color), tr)
            surf.blit(ts, ts.get_rect(center=tr.center))

    def draw_panel(self, surf, th, now):
        p = self.panel
        draw_card(surf, p, px(24), th['panel'], th['border'], 1, (px(30), th['shadow_alpha'], px(12)))
        # header
        r = self.r_header
        blit_center(surf, themed_piece('x', px(26), th, False), (r.x + px(13), r.centery))
        blit_center(surf, themed_piece('o', px(26), th, False), (r.x + px(37), r.centery))
        tx = r.x + px(58)
        draw_text(surf, 'TDCaro', px(21), th['text'], (tx, r.centery + px(4)), 'black', 'bottomleft')
        draw_text(surf, 'Luật chặn 2 đầu' if self.block else 'Nối 5 để thắng', px(12), th['text_dim'], (tx, r.centery + px(2)), 'regular', 'topleft')
        mode = f'Online · {(self.ost or {}).get("code", "")}' if self.online else LEVEL_NAMES[self.level]
        ts = text_surf(f'{self.N}×{self.N} · {mode}', px(12), th['text'], 'bold')
        pr = pygame.Rect(0, 0, ts.get_width() + px(20), px(28))
        pr.midright = r.midright
        surf.blit(round_rect_surf(pr.w, pr.h, px(14), th['panel_alt'], th['border'], 1), pr)
        surf.blit(ts, ts.get_rect(center=pr.center))

        # player cards + VS
        self.draw_player_card(surf, self.r_card_p, 'player', th, now)
        self.draw_player_card(surf, self.r_card_a, 'ai', th, now)
        vc = ((self.r_card_p.right + self.r_card_a.x) // 2, self.r_card_p.centery)
        vr = pygame.Rect(0, 0, px(32), px(32))
        vr.center = vc
        surf.blit(round_rect_surf(vr.w, vr.h, px(16), th['panel'], th['border'], 1), vr)
        draw_text(surf, 'VS', px(11), th['text_dim'], vc, 'black', 'center')

        # status
        rs = self.r_status
        opp_label = self.opp_name() if self.online else 'AI'
        if self.online and self.over and (self.ost or {}).get('reason') == 'forfeit' and self.result == 'Player Win':
            draw_text(surf, 'Đối thủ bỏ cuộc — bạn thắng!', px(17), th['x'], rs.center, 'bold', 'center')
        elif self.over:
            txt, col = {'Player Win': ('Bạn đã chiến thắng!', th['x']),
                        'NPC Win': (f'{opp_label} đã chiến thắng!', th['o'])}.get(self.result, ('Hòa cờ!', th['gold']))
            draw_text(surf, txt, px(18), col, rs.center, 'bold', 'center')
        elif self.online and (self.ost or {}).get('status') != 'playing':
            draw_text(surf, 'Đang chờ đối thủ…', px(16), th['text_dim'], rs.center, 'bold', 'center')
        elif self.turn == 'player':
            draw_text(surf, 'Lượt của bạn — hãy đặt quân X', px(16), th['x'], rs.center, 'bold', 'center')
        else:
            ts = text_surf(f'{opp_label} đang suy nghĩ' if self.online else 'AI đang suy nghĩ', px(16), th['o'], 'bold')
            while ts.get_width() > rs.w - px(40) and len(opp_label) > 4:
                opp_label = opp_label[:-2] + '…'
                ts = text_surf(f'{opp_label} đang suy nghĩ', px(16), th['o'], 'bold')
            dots_w = px(26)
            x0 = rs.centerx - (ts.get_width() + dots_w) // 2
            surf.blit(ts, ts.get_rect(midleft=(x0, rs.centery)))
            for i in range(3):
                dy = -abs(math.sin(now * 6 - i * 0.7)) * px(5)
                pygame.draw.circle(surf, th['o'], (x0 + ts.get_width() + px(7) + i * px(8), rs.centery + px(4) + dy), max(2, px(3)))

        # stats
        last = self.moves[-1] if self.moves else None
        elapsed = (self.end_time or time.perf_counter()) - self.start_time
        stats = [('NƯỚC ĐI', str(len(self.moves)), th['text']),
                 ('VỪA ĐI', coord_name(last[0], last[1]) if last else '—',
                  (th['x'] if last[2] == 'player' else th['o']) if last else th['text_dim']),
                 ('THỜI GIAN', fmt_time(elapsed), th['text'])]
        for rt, (lab, val, col) in zip(self.r_stats, stats):
            surf.blit(round_rect_surf(rt.w, rt.h, px(14), th['panel_alt'], th['border'], 1), rt)
            draw_spaced(surf, lab, px(9), th['text_dim'], (rt.centerx, rt.y + px(16)), 'bold', px(1), 'center')
            draw_text(surf, val, px(19), col, (rt.centerx, rt.y + px(41)), 'black', 'center')

        # history
        draw_spaced(surf, 'LỊCH SỬ NƯỚC ĐI', px(11), th['text_dim'], self.r_hist_title, 'bold')
        hr = self.r_hist
        surf.blit(round_rect_surf(hr.w, hr.h, px(14), th['panel_alt'], th['border'], 1), hr)
        n = len(self.moves)
        if n == 0:
            draw_text(surf, 'Chưa có nước đi nào', px(13), th['text_dim'], hr.center, 'regular', 'center')
        else:
            rowh = px(26)
            rows = (n + 1) // 2
            vis = max(1, (hr.h - px(12)) // rowh)
            start = max(0, rows - vis)
            colw = (hr.w - px(56)) // 2
            for i, row in enumerate(range(start, rows)):
                y = hr.y + px(6) + i * rowh + rowh // 2
                draw_text(surf, f'{row + 1}.', px(12), th['text_dim'], (hr.x + px(14), y), 'semibold', 'midleft')
                for j in (0, 1):
                    k = row * 2 + j
                    if k >= n:
                        break
                    c, r, who = self.moves[k]
                    x0 = hr.x + px(50) + j * colw
                    blit_center(surf, themed_piece('x' if who == 'player' else 'o', px(14), th, False), (x0 + px(7), y))
                    latest = (k == n - 1)
                    draw_text(surf, coord_name(c, r), px(13), th['accent'] if latest else th['text'],
                              (x0 + px(20), y), 'black' if latest else 'semibold', 'midleft')

        for b in self.buttons:
            b.draw(surf, th)

    def draw_modal(self, surf, th, now):
        t = ease_out_cubic(clamp(self.modal_t, 0, 1))
        if t <= 0.01:
            return
        size = self.app.size
        dim = cached(('dim', size), lambda: pygame.Surface(size, pygame.SRCALPHA, 32))
        dim.fill((0, 0, 0, int((130 if th['dark'] else 90) * t)))
        surf.blit(dim, (0, 0))

        mr = self.modal_rect
        pad = px(44)
        tmp = pygame.Surface((mr.w + 2 * pad, mr.h + 2 * pad), pygame.SRCALPHA, 32)
        tmp.fill((0, 0, 0, 0))
        ox, oy = mr.x - pad, mr.y - pad
        card = pygame.Rect(pad, pad, mr.w, mr.h)
        draw_card(tmp, card, px(26), th['panel'], th['border'], 1, (px(36), 160 if th['dark'] else 110, px(16)))

        res = self.result
        opp = self.opp_name() if self.online else 'AI'
        forfeit = self.online and (self.ost or {}).get('reason') == 'forfeit'
        if res == 'Player Win':
            col, title = th['x'], 'CHIẾN THẮNG!'
            sub = f'{opp} đã rời phòng.' if forfeit else 'Bạn đã nối thành công 5 quân liên tiếp.'
        elif res == 'NPC Win':
            col, title = th['o'], 'THẤT BẠI!'
            sub = 'Bạn đã rời ván.' if forfeit else f'{opp} đã nối được 5 quân. Thử lại nhé!'
        else:
            col, title, sub = th['gold'], 'HÒA CỜ!', 'Không bên nào có thể giành chiến thắng.'
        ic = (card.centerx, card.y + px(66))
        circ = round_rect_surf(px(84), px(84), px(42), (*col, 45))
        blit_center(tmp, circ, ic)
        bob = math.sin(now * 3) * px(3)
        if res == 'Player Win':
            blit_center(tmp, themed_piece('x', px(52), th), (ic[0], ic[1] + bob))
        elif res == 'NPC Win':
            blit_center(tmp, themed_piece('o', px(52), th), (ic[0], ic[1] + bob))
        else:
            blit_center(tmp, themed_piece('x', px(36), th), (ic[0] - px(16), ic[1] + bob))
            blit_center(tmp, themed_piece('o', px(36), th), (ic[0] + px(16), ic[1] - bob))
        draw_text(tmp, title, px(32), col, (card.centerx, card.y + px(140)), 'black', 'center')
        draw_text(tmp, sub, px(15), th['text_dim'], (card.centerx, card.y + px(178)), 'regular', 'center')
        elapsed = (self.end_time or time.perf_counter()) - self.start_time
        if self.online:
            st = self.ost or {}
            sc = {'player': (st.get('you') or {}).get('score', 0), 'ai': (st.get('opp') or {}).get('score', 0)}
        else:
            sc = self.app.scores
        info = f'{len(self.moves)} nước đi   ·   {fmt_time(elapsed)}   ·   Tỉ số {sc["player"]} – {sc["ai"]}'
        ir = pygame.Rect(0, 0, card.w - px(56), px(34))
        ir.center = (card.centerx, card.y + px(220))
        tmp.blit(round_rect_surf(ir.w, ir.h, px(17), th['panel_alt'], th['border'], 1), ir)
        draw_text(tmp, info, px(13), th['text'], ir.center, 'semibold', 'center')
        for b in self.modal_buttons:
            b.draw(tmp, th, ox, oy)
        tmp.set_alpha(int(255 * t))
        surf.blit(tmp, (ox, oy))

    def draw_overlays(self, surf, th, now):
        # pill sau khi an modal
        self.pill_rect = pygame.Rect(0, 0, 0, 0)
        if self.over and self.modal_t < 0.05:
            txt = {'Player Win': 'Bạn thắng', 'NPC Win': f'{self.opp_name() if self.online else "AI"} thắng'}.get(self.result, 'Hòa cờ')
            act = 'Nhấn N để chơi lại' if self.online else 'Nhấn N để chơi ván mới'
            ts = text_surf(f'{txt}  ·  {act}  ·  Bấm vào đây để xem kết quả', px(13), th['on_accent'], 'semibold')
            pr = pygame.Rect(0, 0, ts.get_width() + px(32), px(36))
            pr.center = (self.area.centerx, self.slab.bottom + self.depth + px(4))
            draw_card(surf, pr, px(18), th['accent'], None, 0, (px(14), 110, px(5)))
            surf.blit(ts, ts.get_rect(center=pr.center))
            self.pill_rect = pr
        # toast
        if self.toast:
            txt, t0 = self.toast
            age = now - t0
            if age > 1.8:
                self.toast = None
            else:
                a = clamp(min(age / 0.15, (1.8 - age) / 0.3), 0, 1)
                ts = text_surf(txt, px(13), th['text'], 'semibold')
                tr = pygame.Rect(0, 0, ts.get_width() + px(30), px(34))
                base_y = self.slab.bottom + self.depth + px(4) - (px(44) if self.pill_rect.w else 0)
                tr.center = (self.area.centerx, base_y - int(px(6) * a))
                tmp = pygame.Surface((tr.w + px(40), tr.h + px(40)), pygame.SRCALPHA, 32)
                tmp.fill((0, 0, 0, 0))
                draw_card(tmp, pygame.Rect(px(20), px(20), tr.w, tr.h), px(17), th['panel'], th['border'], 1, (px(10), 80, px(4)))
                tmp.blit(ts, ts.get_rect(center=(px(20) + tr.w // 2, px(20) + tr.h // 2)))
                tmp.set_alpha(int(255 * a))
                surf.blit(tmp, (tr.x - px(20), tr.y - px(20)))

    def draw(self, surf):
        app, th, now = self.app, self.app.th, self.app.now
        W, H = app.size
        surf.blit(background(W, H, th), (0, 0))
        app.floats.draw(surf, th, now)
        self.draw_board(surf, th, now)
        self.draw_panel(surf, th, now)
        self.draw_overlays(surf, th, now)
        self.draw_modal(surf, th, now)
        self.confetti.draw(surf)


# ================================ ONLINE: O NHAP CHU =========================

class TextField:
    def __init__(self, placeholder, max_len=16, upper=False, allowed=None, on_enter=None):
        self.placeholder = placeholder
        self.max_len = max_len
        self.upper = upper
        self.allowed = allowed          # chuoi ky tu cho phep (None = moi ky tu)
        self.on_enter = on_enter
        self.text = ''
        self.focus = False
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.t_focus = 0.0

    def _accept(self, s):
        if self.upper:
            s = s.upper()
        if self.allowed is not None:
            s = ''.join(ch for ch in s if ch in self.allowed)
        s = ''.join(ch for ch in s if ch.isprintable())
        self.text = (self.text + s)[:self.max_len]

    def handle(self, ev, now):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            was = self.focus
            self.focus = self.rect.collidepoint(ev.pos)
            if self.focus and not was:
                self.t_focus = now
            return self.focus
        if not self.focus:
            return False
        if ev.type == pygame.TEXTINPUT:
            self._accept(ev.text)
            return True
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_enter:
                    self.on_enter()
            elif ev.key == pygame.K_v and ev.mod & pygame.KMOD_CTRL:
                try:
                    self._accept(pygame.scrap.get_text() or '')
                except Exception:
                    pass
            elif ev.key == pygame.K_ESCAPE:
                self.focus = False
            return True       # khi dang go, khong de phim tat khac an phim
        return False

    def draw(self, surf, th, now, font_size=16, center=False):
        r = self.rect
        border = th['accent'] if self.focus else th['border']
        surf.blit(round_rect_surf(r.w, r.h, px(12), th['panel_alt'], border, px(2) if self.focus else 1), r.topleft)
        txt = self.text
        col = th['text'] if txt else th['text_dim']
        ts = text_surf(txt or self.placeholder, px(font_size), col, 'bold' if (center and txt) else 'semibold')
        if center:
            tr = ts.get_rect(center=r.center)
        else:
            tr = ts.get_rect(midleft=(r.x + px(14), r.centery))
        surf.blit(ts, tr)
        if self.focus and int((now - self.t_focus) * 2) % 2 == 0:
            cx = (tr.right + px(2)) if txt else (tr.x if not center else r.centerx)
            pygame.draw.line(surf, th['accent'], (cx, r.centery - px(11)), (cx, r.centery + px(11)), max(2, px(2)))


# ================================ ONLINE: SANH CHO ===========================

CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


class LobbyScreen:
    def __init__(self, app):
        self.app = app
        self.name_f = TextField('Tên của bạn', 16, on_enter=self.commit_name)
        self.code_f = TextField('MÃ PHÒNG', 6, upper=True, allowed=CODE_ALPHABET, on_enter=self.join)
        self.btn_create = Button('Tạo phòng', self.create, 'primary', font_size=15, enabled=self.ready)
        self.btn_join = Button('Vào phòng', self.join, 'primary', font_size=15,
                               enabled=lambda: self.ready() and len(self.code_f.text) == 6)
        self.btn_back = Button('Quay lại', self.back, hotkey='ESC', font_size=14)
        self.btn_copy = Button(lambda: 'Đã sao chép!' if self.app.now - self.copied_t < 1.5 else 'Sao chép mã',
                               self.copy_code, 'primary', font_size=15)
        self.btn_cancel = Button('Huỷ phòng', self.cancel_room, font_size=15)
        self.copied_t = -9.0
        self.want_hand = False

    # ---- trang thai
    @property
    def net(self):
        return self.app.net

    def ready(self):
        return self.net is not None and self.net.status == 'online'

    def waiting_room(self):
        """Phong minh tao (hoac con lai sau khi doi thu roi) dang cho nguoi vao."""
        st = self.net.state if self.net else None
        return st if (st and st.get('opp') is None) else None

    def enter(self):
        self.name_f.text = self.net.name
        self.code_f.text = ''
        self.name_f.focus = self.code_f.focus = False
        self.layout()

    # ---- hanh dong
    def commit_name(self):
        if self.net and self.name_f.text.strip() and self.name_f.text.strip() != self.net.name:
            self.net.set_name(self.name_f.text)
        self.name_f.focus = False

    def create(self):
        self.commit_name()
        st = self.app.settings
        self.net.create(st['size'], st['rule'])

    def join(self):
        if len(self.code_f.text) == 6 and self.ready():
            self.commit_name()
            self.net.join(self.code_f.text)

    def copy_code(self):
        st = self.waiting_room()
        if not st:
            return
        try:
            pygame.scrap.put_text(st['code'])
        except Exception:
            try:
                if sys.platform == 'emscripten':
                    import platform as _pf
                    _pf.window.navigator.clipboard.writeText(st['code'])
            except Exception:
                pass
        self.copied_t = self.app.now

    def cancel_room(self):
        if self.net:
            self.net.leave()

    def back(self):
        if self.waiting_room():
            self.cancel_room()
            return
        self.app.leave_online_lobby()

    # ---- mang
    def on_net(self, msgs):
        st = self.net.state
        if st and IS_WEB and st.get('code') != getattr(self, '_logged_code', None):
            self._logged_code = st.get('code')
            _wlog(f'phong {st.get("code")}')
        if st and st.get('opp') and st.get('status') in ('playing', 'over'):
            self.app.start_online_game(st)

    # ---- bo cuc
    def layout(self):
        W, H = self.app.size
        cw, ch = px(560), px(560)
        self.card = pygame.Rect((W - cw) // 2, (H - ch) // 2, cw, ch)
        c = self.card
        pad = px(36)
        x, w = c.x + pad, c.w - 2 * pad
        y = c.y + px(118)
        self.lbl_name = (x, y)
        self.name_f.rect = pygame.Rect(x, y + px(26), w, px(48))
        y += px(26) + px(48) + px(30)
        self.lbl_create = (x, y)
        bw = px(150)
        self.r_create_info = pygame.Rect(x, y + px(26), w - bw - px(12), px(48))
        self.btn_create.rect = pygame.Rect(x + w - bw, y + px(26), bw, px(48))
        y += px(26) + px(48) + px(30)
        self.lbl_join = (x, y)
        self.code_f.rect = pygame.Rect(x, y + px(26), w - bw - px(12), px(48))
        self.btn_join.rect = pygame.Rect(x + w - bw, y + px(26), bw, px(48))
        y += px(26) + px(48) + px(22)
        self.r_err = pygame.Rect(x, y, w, px(24))
        self.btn_back.rect = pygame.Rect(x, c.bottom - pad - px(44), px(150), px(44))
        # phong cho
        self.r_code = pygame.Rect(x, c.y + px(150), w, px(84))
        hw = (w - px(12)) // 2
        self.btn_copy.rect = pygame.Rect(x, c.y + px(330), hw, px(50))
        self.btn_cancel.rect = pygame.Rect(x + hw + px(12), c.y + px(330), w - hw - px(12), px(50))

    def buttons(self):
        if self.waiting_room():
            return [self.btn_copy, self.btn_cancel, self.btn_back]
        return [self.btn_create, self.btn_join, self.btn_back]

    # ---- vong lap
    def handle(self, ev):
        now = self.app.now
        waiting = self.waiting_room()
        if not waiting:
            for f in (self.name_f, self.code_f):
                if f.handle(ev, now):
                    if f is self.code_f and f.focus and self.name_f.focus:
                        self.name_f.focus = False
                    if ev.type == pygame.MOUSEBUTTONDOWN:
                        other = self.code_f if f is self.name_f else self.name_f
                        if other.focus:
                            other.focus = False
                    return
            if ev.type == pygame.MOUSEBUTTONDOWN and self.name_f.text.strip() != (self.net.name if self.net else ''):
                self.commit_name()
        for b in self.buttons():
            if b.handle(ev, self.app):
                return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.back()
            elif waiting and ev.key == pygame.K_c and ev.mod & pygame.KMOD_CTRL:
                self.copy_code()

    @property
    def typing(self):
        return self.name_f.focus or self.code_f.focus

    def update(self, dt):
        mouse = pygame.mouse.get_pos()
        bs = self.buttons()
        for b in (self.btn_create, self.btn_join, self.btn_back, self.btn_copy, self.btn_cancel):
            b.update(dt, mouse if b in bs else (-999, -999))
        over_field = (not self.waiting_room()) and (self.name_f.rect.collidepoint(mouse) or self.code_f.rect.collidepoint(mouse))
        self.want_hand = any(b.hovered for b in bs) or over_field

    def draw(self, surf):
        app, th, now = self.app, self.app.th, self.app.now
        W, H = app.size
        surf.blit(background(W, H, th), (0, 0))
        app.floats.draw(surf, th, now)
        c = self.card
        draw_card(surf, c, px(26), th['panel'], th['border'], 1, (px(34), th['shadow_alpha'], px(14)))
        pad = px(36)
        # tieu de + trang thai ket noi
        blit_center(surf, themed_piece('x', px(30), th, False), (c.x + pad + px(15), c.y + px(52)))
        blit_center(surf, themed_piece('o', px(30), th, False), (c.x + pad + px(43), c.y + px(52)))
        draw_text(surf, 'Chơi online', px(26), th['text'], (c.x + pad + px(68), c.y + px(52)), 'black', 'midleft')
        st = self.net.status if self.net else 'idle'
        label, col = {'online': ('Đã kết nối', (70, 200, 120))}.get(st, ('Đang kết nối…', th['gold']))
        ts = text_surf(label, px(12), th['text'], 'semibold')
        pr = pygame.Rect(0, 0, ts.get_width() + px(36), px(28))
        pr.midright = (c.right - pad, c.y + px(52))
        surf.blit(round_rect_surf(pr.w, pr.h, px(14), th['panel_alt'], th['border'], 1), pr.topleft)
        a = 1.0 if st == 'online' else 0.45 + 0.55 * abs(math.sin(now * 3))
        pygame.draw.circle(surf, lerp_color(th['panel_alt'], col, a), (pr.x + px(15), pr.centery), max(3, px(4)))
        surf.blit(ts, ts.get_rect(midleft=(pr.x + px(25), pr.centery)))
        draw_text(surf, 'Chơi cùng bạn bè qua Internet: một người tạo phòng, người kia nhập mã.', px(13),
                  th['text_dim'], (c.x + pad, c.y + px(86)), 'regular', 'midleft')

        room = self.waiting_room()
        if room:
            self.draw_waiting(surf, th, now, room)
        else:
            draw_spaced(surf, 'TÊN CỦA BẠN', px(11), th['text_dim'], self.lbl_name, 'bold')
            self.name_f.draw(surf, th, now)
            draw_spaced(surf, 'TẠO PHÒNG MỚI', px(11), th['text_dim'], self.lbl_create, 'bold')
            r = self.r_create_info
            surf.blit(round_rect_surf(r.w, r.h, px(12), th['panel_alt'], th['border'], 1), r.topleft)
            sett = app.settings
            info = f'Bàn {sett["size"]}×{sett["size"]}  ·  ' + ('Luật chặn 2 đầu' if sett['rule'] == 'block' else 'Luật tự do')
            draw_text(surf, info, px(14), th['text'], (r.x + px(14), r.centery), 'semibold', 'midleft')
            draw_text(surf, 'đổi ở menu', px(11), th['text_dim'], (r.right - px(12), r.centery), 'regular', 'midright')
            draw_spaced(surf, 'VÀO PHÒNG CỦA BẠN BÈ', px(11), th['text_dim'], self.lbl_join, 'bold')
            self.code_f.draw(surf, th, now, font_size=20, center=True)
            err = self.net.error if self.net else None
            if err:
                draw_text(surf, err[1], px(13), th['x'], self.r_err.center, 'semibold', 'center')
            elif st != 'online':
                draw_text(surf, 'Đang kết nối mạng chuyển tiếp… (cần có Internet)', px(13),
                          th['text_dim'], self.r_err.center, 'regular', 'center')
        for b in self.buttons():
            b.draw(surf, th)

    def draw_waiting(self, surf, th, now, room):
        c = self.card
        pad = px(36)
        draw_spaced(surf, 'MÃ PHÒNG', px(11), th['text_dim'], (c.x + pad, c.y + px(122)), 'bold')
        code = room['code']
        r = self.r_code
        n = len(code)
        g = px(10)
        bw = (r.w - (n - 1) * g) // n
        for i, ch in enumerate(code):
            br = pygame.Rect(r.x + i * (bw + g), r.y, bw, r.h)
            lift = int(abs(math.sin(now * 2 - i * 0.5)) * px(3))
            surf.blit(round_rect_surf(br.w, br.h, px(14), th['panel_alt'], th['accent'], px(2)), (br.x, br.y - lift))
            draw_text(surf, ch, px(40), th['accent'], (br.centerx, br.centery - lift), 'black', 'center')
        sett = f'Bàn {room["size"]}×{room["size"]}  ·  ' + ('Luật chặn 2 đầu' if room['rule'] == 'block' else 'Luật tự do')
        draw_text(surf, sett, px(14), th['text'], (c.centerx, c.y + px(262)), 'semibold', 'center')
        ts = text_surf('Gửi mã này cho bạn bè — đang chờ đối thủ vào phòng', px(13), th['text_dim'], 'regular')
        x0 = c.centerx - (ts.get_width() + px(26)) // 2
        surf.blit(ts, ts.get_rect(midleft=(x0, c.y + px(292))))
        for i in range(3):
            dy = -abs(math.sin(now * 5 - i * 0.7)) * px(4)
            pygame.draw.circle(surf, th['accent'], (x0 + ts.get_width() + px(8) + i * px(8), c.y + px(296) + dy), max(2, px(3)))
        draw_text(surf, 'Bạn bè mở TDCaro → Chơi online → nhập mã → Vào phòng', px(12), th['text_dim'],
                  (c.centerx, c.y + px(410)), 'regular', 'center')
        draw_text(surf, 'Hãy giữ game mở — phòng chơi chạy ngay trên máy của bạn', px(12), th['gold'],
                  (c.centerx, c.y + px(432)), 'semibold', 'center')


# ==================================== APP ===================================

def _enable_dpi_awareness():
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _dark_title_bar():
    """Windows 10/11: thanh tieu de + vien cua so mau den (DWM)."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = wintypes.HWND(pygame.display.get_wm_info()['window'])
        dwm = ctypes.windll.dwmapi

        def setattr_(attr, value):
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        # che do toi (Win10 1809+: 19, Win10 20H1+/Win11: 20)
        if setattr_(20, 1) != 0:
            setattr_(19, 1)
        # Win11: mau thanh tieu de / vien / chu (COLORREF 0x00BBGGRR)
        setattr_(35, 0x000000)   # DWMWA_CAPTION_COLOR = den
        setattr_(34, 0x000000)   # DWMWA_BORDER_COLOR = den
        setattr_(36, 0xFFFFFF)   # DWMWA_TEXT_COLOR = trang
    except Exception:
        pass


def resource_path(name):
    # exe: thu muc giai nen cua PyInstaller; ma nguon: thu muc goc du an (cha cua src/)
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, name)


def make_icon():
    try:
        return pygame.image.load(resource_path(os.path.join('assets', 'icon.png')))
    except Exception:
        pass
    s = pygame.Surface((64, 64), pygame.SRCALPHA, 32)
    th = THEMES['midnight']
    s.blit(round_rect_surf(64, 64, 14, th['accent']), (0, 0))
    blit_center(s, piece_sprite('x', 40, (255, 255, 255)), (32, 32))
    return s


def _web_canvas_size():
    """Khung 16:10 lon nhat vua cua so trinh duyet, nhan devicePixelRatio (toi da 2560 px ngang)."""
    try:
        import platform as _pf
        win = _pf.window
        dpr = float(win.devicePixelRatio or 1)
        vw, vh = float(win.innerWidth), float(win.innerHeight)
        fw = min(vw, vh * 1.6)
        w = fw * dpr
        if w > 2560:
            w = 2560
        w = max(960, int(w))
        return w, int(w / 1.6)
    except Exception:
        return 1280, 800


def _wlog(stage):
    if IS_WEB:
        print(f'[tdcaro] {stage}', flush=True)


class App:
    def __init__(self):
        _enable_dpi_awareness()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except Exception:
            pass
        pygame.init()
        info = pygame.display.Info()
        sw, sh = info.current_w or 1366, info.current_h or 768
        w = int(min(sw * 0.82, sh * 0.85 * 1.6))
        h = int(w / 1.6)
        w, h = max(960, w), max(620, h)
        if IS_WEB:
            # web: canvas = dung kich thuoc hien thi that x mat do diem anh (net, khong bi phong to/mo)
            w, h = _web_canvas_size()
            _wlog(f'set_mode {w}x{h}')
            self.screen = pygame.display.set_mode((w, h))
        else:
            try:
                pygame.display.set_icon(make_icon())
            except Exception:
                pass
            self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            pygame.display.set_caption('TDCaro')
            _dark_title_bar()
            try:
                pygame.Window.from_display_module().minimum_size = (900, 600)
            except Exception:
                pass

        self.settings = {'size': 15, 'theme': 'midnight', 'first': 'player', 'sound': True, 'music': True,
                         'level': 'normal', 'rule': 'block'}
        self.scores = {'player': 0, 'ai': 0, 'draw': 0}
        self.now = 0.0
        self.running = True
        _wlog('sound')
        self.sound = SoundFX(self)
        _wlog('music')
        self.music_ok = self._start_music()
        _wlog('screens')
        self.updater = updater.Updater(APP_VERSION)
        if not os.environ.get('CARO_NO_UPDATE') and not IS_WEB:
            self.updater.check_async()
        shortcuts.ensure_async(APP_VERSION)        # shortcut Desktop + Start Menu (lan dau / sau cap nhat)
        self.floats = FloatingSymbols()
        self.menu = MenuScreen(self)
        self.game = GameScreen(self)
        self.net = None                  # online.OnlineClient (tao khi vao "Choi online")
        self.lobby = LobbyScreen(self)
        self.state = 'menu'
        self.cursor_hand = None
        self.fullscreen = False
        _wlog('on_resize')
        self.on_resize()
        _wlog('init xong')

    # ---- properties / actions
    @property
    def size(self):
        return self.screen.get_size()

    @property
    def th(self):
        return THEMES[self.settings['theme']]

    @property
    def current(self):
        return {'menu': self.menu, 'game': self.game, 'lobby': self.lobby}[self.state]

    def on_resize(self):
        self.screen = pygame.display.get_surface()
        W, H = self.size
        # Ve moi thu len 1 canvas DUC (XRGB, khong kenh alpha) roi moi dua ra man hinh.
        # macOS: man hinh co kenh alpha -> blit trong suot len nen bi chep nguyen mau
        # (chu thanh thanh dac, bong do thanh khoi den). Canvas rieng giup moi nen tang giong nhau.
        self.canvas = pygame.Surface((W, H), 0, 32)
        UI.s = clamp(min(W / BASE_W, H / BASE_H), 0.6, 3.0)
        clear_gfx()
        self.floats.reset(W, H)
        self.menu.layout()
        self.game.layout()
        self.lobby.layout()

    def set_theme(self, key):
        self.settings['theme'] = key
        clear_gfx()
        self.menu.layout()
        if self.state == 'game':
            self.game.show_toast(f'Giao diện: {THEMES[key]["name"]}')

    def cycle_theme(self):
        i = THEME_KEYS.index(self.settings['theme'])
        self.set_theme(THEME_KEYS[(i + 1) % len(THEME_KEYS)])

    def toggle_fullscreen(self):
        """Chuyen qua lai giua cua so va toan man hinh (borderless, khong doi do phan giai)."""
        target = not self.fullscreen
        try:
            win = pygame.Window.from_display_module()
            if target:
                self._windowed_size = win.size
                win.set_fullscreen(desktop=True)
            else:
                win.set_windowed()
                if getattr(self, '_windowed_size', None):
                    win.size = self._windowed_size
                    win.position = pygame.WINDOWPOS_CENTERED
                _dark_title_bar()
        except Exception:
            pygame.display.toggle_fullscreen()
        self.fullscreen = target
        self.on_resize()
        self._last_size = self.size
        if self.state == 'game':
            self.game.show_toast('Toàn màn hình: ' + ('Bật' if target else 'Tắt'))

    def _start_music(self):
        """Danh sach nhac nen lo-fi (assets/music/*.ogg, tu soan bang tools/make_music.py).
        Phat ngau nhien, het bai tu chuyen bai."""
        self.track_idx = -1
        self.tracks = []
        try:
            if not pygame.mixer.get_init():
                return False
            folder = resource_path(os.path.join('assets', 'music'))
            self.tracks = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.ogg'))
            if not self.tracks:
                return False
            random.shuffle(self.tracks)
            pygame.mixer.music.set_endevent(MUSIC_END)
            return self.next_track(fade_ms=2500)
        except Exception:
            return False

    @property
    def track_title(self):
        if not self.tracks or self.track_idx < 0:
            return ''
        key = os.path.splitext(os.path.basename(self.tracks[self.track_idx]))[0]
        return TRACK_TITLES.get(key, key)

    def next_track(self, fade_ms=1200):
        if not self.tracks:
            return False
        try:
            self.track_idx = (self.track_idx + 1) % len(self.tracks)
            pygame.mixer.music.load(self.tracks[self.track_idx])
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(0, fade_ms=fade_ms)
            self._track_t0 = time.time()
            if not self.settings['music']:
                pygame.mixer.music.pause()
            return True
        except Exception:
            return False

    def skip_track(self):
        if self.music_ok and self.next_track() and self.state == 'game':
            self.game.show_toast('Đang phát: ' + self.track_title)

    def toggle_music(self):
        self.settings['music'] = not self.settings['music']
        if self.music_ok:
            try:
                if self.settings['music']:
                    pygame.mixer.music.unpause()
                else:
                    pygame.mixer.music.pause()
            except Exception:
                pass
        if self.state == 'game':
            on = self.settings['music']
            self.game.show_toast('Nhạc nền: Bật · ' + self.track_title if on and self.music_ok else
                                 'Nhạc nền: ' + ('Bật' if on else 'Tắt'))

    def reset_scores(self):
        for k in self.scores:
            self.scores[k] = 0
        if self.state == 'game':
            self.game.show_toast('Đã đặt lại tỉ số')

    def toggle_sound(self):
        self.settings['sound'] = not self.settings['sound']
        if self.state == 'game':
            self.game.show_toast('Âm thanh: ' + ('Bật' if self.settings['sound'] else 'Tắt'))

    def start_game(self):
        self.game.new_game()
        self.state = 'game'

    def go_menu(self):
        self.game.cancel_jobs()
        self.menu.layout()
        self.state = 'menu'

    # ---- online
    def go_online(self):
        if self.net is None:
            self.net = online.OnlineClient()
        self.net.connect()
        self.game.stop_online()
        self.lobby.enter()
        self.state = 'lobby'

    def start_online_game(self, st):
        self.game.start_online(st)
        self.state = 'game'

    def leave_online_game(self, already_left=False):
        if self.net and not already_left:
            self.net.leave()
        self.game.stop_online()
        self.lobby.enter()
        self.state = 'lobby'

    def leave_online_lobby(self):
        if self.net:
            if self.net.state:
                self.net.leave()
            self.net.disconnect()
        self.go_menu()

    def quit(self):
        self.running = False

    def shutdown_net(self):
        """Thoat game khi dang online: bao cho doi thu (chu phong dong phong / khach roi phong)."""
        if self.net:
            try:
                self.net.disconnect()
                time.sleep(0.2)
            except Exception:
                pass

    # ---- main loop
    def frame(self, events, dt):
        self.now += dt
        for ev in events:
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                if pygame.display.get_surface().get_size() != getattr(self, '_last_size', None):
                    self._last_size = pygame.display.get_surface().get_size()
                    self.on_resize()
            elif ev.type == MUSIC_END:
                # load() bai moi cung ban ra MUSIC_END cua bai cu -> bo qua neu bai vua bat dau
                if time.time() - getattr(self, '_track_t0', 0) > 1.0:
                    self.next_track()
            elif self.state == 'lobby' and self.lobby.typing and ev.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
                self.lobby.handle(ev)            # dang go chu: khong de phim tat (K, F11...) an phim
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_k:
                self.skip_track()
            elif ev.type == pygame.KEYDOWN and (ev.key == pygame.K_F11 or (
                    ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and ev.mod & pygame.KMOD_ALT)):
                self.toggle_fullscreen()
            else:
                self.current.handle(ev)
        if self.updater.want_quit:
            self.running = False
        if self.net:
            msgs = self.net.poll()
            if msgs:
                if self.state == 'lobby':
                    self.lobby.on_net(msgs)
                elif self.state == 'game' and self.game.online:
                    self.game.on_net(msgs)
        scr = self.current
        self.floats.update(dt)
        scr.update(dt)
        scr.draw(self.canvas)
        self.screen.blit(self.canvas, (0, 0))
        want = scr.want_hand
        if want != self.cursor_hand:
            self.cursor_hand = want
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if want else pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                pass

    async def run_async(self):
        """Vong lap cho ban web (pygbag): moi frame nhuong quyen cho trinh duyet."""
        import asyncio
        clock = pygame.time.Clock()
        self._last_size = self.size
        n = 0
        while self.running:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            if n < 2:
                _wlog(f'frame {n}')
            self.frame(pygame.event.get(), dt)
            pygame.display.flip()
            if n < 2:
                _wlog(f'frame {n} xong')
            n += 1
            await asyncio.sleep(0)
        self.shutdown_net()

    def run(self):
        clock = pygame.time.Clock()
        self._last_size = self.size
        while self.running:
            thinking = self.state == 'game' and (self.game.ai_job or self.game.hint_job)
            # khi AI dang nghi: giam FPS de nhuong CPU (GIL) cho luong AI
            dt = min(clock.tick(30 if thinking else 60) / 1000.0, 0.05)
            self.frame(pygame.event.get(), dt)
            pygame.display.flip()
        self.shutdown_net()
        pygame.quit()


if __name__ == '__main__':
    App().run()
