# -*- coding: utf-8 -*-
"""
Cho cac muc AI dau voi nhau de so sanh suc manh.
Chay:  .venv\\Scripts\\python tools\\benchmark.py [so_van_moi_cap] [kich_thuoc_ban]
Moi van: 2 nuoc mo dau ngau nhien gan tam (de cac van khac nhau), doi luot di truoc moi van.
"""
import os
import sys
import time
import random

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Finals as F  # noqa: E402

NAMES = {'easy': 'De', 'normal': 'Binh thuong', 'hard': 'Kho', 'expert': 'Cuc kho'}


def play(level_a, level_b, size, a_first, seed):
    """Tra ve 'A', 'B' hoac 'D'. A cam quan 'w' neu di truoc..."""
    rnd = random.Random(seed)
    b = F.make_empty_board(size)
    first, second = ('A', 'B') if a_first else ('B', 'A')
    cols = {first: 'r', second: 'w'}
    lv = {'A': level_a, 'B': level_b}
    c = size // 2
    # 2 nuoc mo dau ngau nhien
    b[c][c] = cols[first]
    while True:
        r, cc = c + rnd.randint(-2, 2), c + rnd.randint(-2, 2)
        if b[r][cc] == ' ':
            b[r][cc] = cols[second]
            break
    turn = first
    for _ in range(size * size):
        col = cols[turn]
        y, x = F.ai_move([row[:] for row in b], col, lv[turn])
        if b[y][x] != ' ':
            empt = [(i, j) for i in range(size) for j in range(size) if b[i][j] == ' ']
            if not empt:
                return 'D'
            y, x = empt[0]
        b[y][x] = col
        if F.find_winning_line(b, col):
            return turn
        if all(v != ' ' for row in b for v in row):
            return 'D'
        turn = second if turn == first else first
    return 'D'


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    pairs = [('normal', 'easy'), ('hard', 'easy'), ('hard', 'normal'), ('expert', 'easy'),
             ('expert', 'normal'), ('expert', 'hard')]
    if len(sys.argv) > 3:
        pairs = [tuple(p.split(':')) for p in sys.argv[3].split(',')]
    print(f'Ban {size}x{size}, {games} van moi cap\n')
    for a, b in pairs:
        res = {'A': 0, 'B': 0, 'D': 0}
        t0 = time.perf_counter()
        for g in range(games):
            res[play(a, b, size, g % 2 == 0, 1000 + g)] += 1
        dt = time.perf_counter() - t0
        print(f'{NAMES[a]:>12} vs {NAMES[b]:<12}: {res["A"]:>2} thang - {res["B"]:>2} thua - {res["D"]:>2} hoa'
              f'   ({dt:.0f}s)', flush=True)


if __name__ == '__main__':
    main()
