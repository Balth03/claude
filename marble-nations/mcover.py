#!/usr/bin/env python3
"""MARBLE NATIONS - couverture TikTok par partie (1080x1920)."""
import sys, math, random
import numpy as np
from PIL import Image, ImageDraw
import marble as M


def cover(part, eliminated_before, out):
    cs = [c for c in M.COUNTRIES if c[1] not in eliminated_before]
    W, H = 1080, 1920
    a = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array((30, 36, 90)) * (1 - a) + np.array((8, 10, 26)) * a).astype(np.uint8)
    im = Image.fromarray(np.repeat(arr, W, axis=1)).convert('RGBA')
    rng = random.Random(part)
    # a pile of flag marbles filling the lower half
    pts = []
    for c in cs * 2:
        for _ in range(40):
            x, y = rng.uniform(60, W - 60), rng.uniform(900, H - 60)
            if all((x - px) ** 2 + (y - py) ** 2 > 120 ** 2 for px, py, _ in pts):
                pts.append((x, y, c))
                break
    for x, y, c in sorted(pts, key=lambda p: p[1]):
        f = M.flag_disc(c[0], 120)
        g = M.gloss(120)
        im.alpha_composite(f, (int(x - 60), int(y - 60)))
        im.alpha_composite(g, (int(x - 60), int(y - 60)))
    d = ImageDraw.Draw(im)
    M.place(im, M.rich((M.T('WORLD ', M.WHITE), M.T('MARBLE RACE', M.YEL)), M.ANTON, 120, stroke=7, shadow=8), 540, 250)
    M.place(im, M.rich((M.T(f'PART {part}', M.WHITE),), M.LUCK, 230, stroke=16, shadow=12), 540, 470, 1, -3)
    M.place(im, M.rich((M.T(f'{len(cs)} COUNTRIES LEFT', M.YEL),), M.ANTON, 96, stroke=6, shadow=8), 540, 660)
    M.place(im, M.rich((M.T('WHO GETS ELIMINATED? ', M.RED), M.E('26a0-fe0f')), M.LUCK, 76, stroke=10, shadow=8),
            540, 800, 1, -2)
    im.convert('RGB').save(out)


if __name__ == '__main__':
    import json
    st = json.load(open(M.STATE))
    for p in range(1, 6):
        cover(p, {st[str(k)] for k in range(1, p) if str(k) in st}, f'cover_{p}.png')
