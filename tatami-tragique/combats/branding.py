#!/usr/bin/env python3
"""TATAMI TRAGIQUE - image de profil (800x800) et bannière YouTube (2560x1440)."""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from fight import (logo, rich, place, font, T, E, ANTON, LUCK, YEL, RED, WHITE, BLACK, GREY, mix, D)

TAT1, TAT2, TATL = (58, 66, 44), (66, 75, 50), (38, 44, 28)


def tatami(w, h, m=320):
    im = Image.new('RGB', (w, h), TAT1)
    d = ImageDraw.Draw(im)
    for i in range(w // m + 2):
        for j in range(h // m + 2):
            horiz = (i + j) % 2 == 0
            x0, y0 = i * m, j * m
            c = TAT1 if horiz else TAT2
            d.rectangle([x0, y0, x0 + m, y0 + m], fill=c)
            for k in range(0, m, 14):
                if horiz:
                    d.line([x0, y0 + k, x0 + m, y0 + k], fill=mix(c, BLACK, 0.9), width=2)
                else:
                    d.line([x0 + k, y0, x0 + k, y0 + m], fill=mix(c, BLACK, 0.9), width=2)
            d.rectangle([x0, y0, x0 + m, y0 + m], outline=TATL, width=6)
    return im


def ball(d, x, y, r, col, ang=None, weapon=None, L=0, look=0.0, belt=BLACK, ko=False):
    """Boule-combattant du format 'Combat de boules' (mêmes codes visuels que les épisodes)."""
    if weapon:
        c, s = math.cos(ang), math.sin(ang)
        nx, ny = -s, c

        def pt(a, b=0.0):
            return (x + c * a + nx * b, y + s * a + ny * b)
        if weapon == 'katana':
            d.line([pt(r * 0.5), pt(r + 16 * r / 80)], fill=(30, 14, 16), width=int(r * 0.2))
            k = r / 80
            d.polygon([pt(r + 14 * k, -20 * k), pt(r + 22 * k, -20 * k), pt(r + 22 * k, 20 * k), pt(r + 14 * k, 20 * k)],
                      fill=(214, 170, 60), outline=BLACK)
            d.polygon([pt(r + 22 * k, -10 * k), pt(r + 22 * k, 10 * k), pt(r + L - 22 * k, 7 * k), pt(r + L, -3 * k),
                       pt(r + L - 26 * k, -11 * k)], fill=(222, 228, 238), outline=(60, 64, 74))
        elif weapon == 'nunchaku':
            j = r + L * 0.48
            d.line([pt(r * 0.5), pt(j)], fill=(120, 72, 36), width=int(r * 0.22))
            c2, s2 = math.cos(ang - 0.35), math.sin(ang - 0.35)
            jx, jy = pt(j)
            d.line([(jx, jy), (jx + c2 * (r + L - j), jy + s2 * (r + L - j))], fill=(120, 72, 36), width=int(r * 0.22))
            d.ellipse([jx - r * 0.1, jy - r * 0.1, jx + r * 0.1, jy + r * 0.1], fill=(190, 190, 200), outline=BLACK)
        elif weapon == 'bo':
            d.line([pt(-L), pt(L)], fill=(92, 56, 28), width=int(r * 0.26))
            d.line([pt(-L), pt(L)], fill=(160, 104, 52), width=int(r * 0.13))
    d.ellipse([x - r - r * 0.07, y - r - r * 0.07, x + r + r * 0.07, y + r + r * 0.07], fill=BLACK)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=mix(col, BLACK, 0.45), width=max(3, int(r * 0.06)))
    by = y + r * 0.35
    hw = math.sqrt(r * r - (r * 0.35) ** 2)
    d.line([(x - hw + 3, by), (x + hw - 3, by)], fill=belt, width=int(r * 0.22))
    d.rectangle([x - r * 0.12, by - r * 0.14, x + r * 0.12, by + r * 0.14], fill=belt)
    er = r * 0.2
    for sx in (-1, 1):
        ex, ey = x + sx * r * 0.32, y - r * 0.18
        if ko:
            w = er * 0.8
            d.line([(ex - w, ey - w), (ex + w, ey + w)], fill=BLACK, width=max(3, int(r * 0.07)))
            d.line([(ex - w, ey + w), (ex + w, ey - w)], fill=BLACK, width=max(3, int(r * 0.07)))
        else:
            d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=WHITE, outline=BLACK, width=max(2, int(r * 0.03)))
            px, py = ex + math.cos(look) * er * 0.45, ey + math.sin(look) * er * 0.45
            d.ellipse([px - er * 0.5, py - er * 0.5, px + er * 0.5, py + er * 0.5], fill=BLACK)
        bx, byy = x + sx * r * 0.32, y - r * 0.18 - er * 1.35
        d.line([(bx - sx * er, byy - er * 0.35), (bx + sx * er, byy + er * 0.3)], fill=BLACK, width=max(3, int(r * 0.06)))


def sparks(d, x, y, n, rad, rng, col=YEL, w=8):
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r0, r1 = rad * rng.uniform(0.3, 0.6), rad * rng.uniform(0.8, 1.2)
        d.line([(x + math.cos(a) * r0, y + math.sin(a) * r0), (x + math.cos(a) * r1, y + math.sin(a) * r1)], fill=col,
               width=w)


def tape(text, bg, fg, w, h, fs):
    im = Image.new('RGBA', (w, h), bg + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 7], fill=BLACK)
    d.rectangle([0, h - 8, w, h], fill=BLACK)
    f = font(ANTON, fs)
    x = 0
    while x < w:
        d.text((x, h / 2 + 2), text, font=f, fill=fg, anchor='lm')
        x += ImageDraw.Draw(im).textlength(text, font=f)
    return im


def avatar(path):
    S = 2
    N = 800 * S
    im = Image.new('RGB', (N, N), BLACK)
    # radial burst yellow/dark behind logo
    yy, xx = np.mgrid[0:N, 0:N]
    ang = np.arctan2(yy - N / 2, xx - N / 2)
    rays = (np.sin(ang * 12) > 0)
    base = np.where(rays[..., None], np.array((255, 196, 20)), np.array((255, 214, 60))).astype(np.uint8)
    im = Image.fromarray(base)
    d = ImageDraw.Draw(im)
    lg = logo(int(N * 0.86))
    im.paste(lg, ((N - lg.width) // 2, (N - lg.height) // 2), lg)
    im = im.resize((800, 800), Image.LANCZOS)
    im.save(path)
    # preview of the circular crop YouTube applies
    m = Image.new('L', (800, 800), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
    pv = Image.new('RGB', (800, 800), (255, 255, 255))
    pv.paste(im, (0, 0), m)
    pv.save(path.replace('.png', '_apercu_rond.png'))


def banner(path):
    Wb, Hb = 2560, 1440
    rng = random.Random(4)
    im = tatami(Wb, Hb)
    # darken toward the center band so text pops
    yy = np.linspace(-1, 1, Hb)[:, None]
    xx = np.linspace(-1, 1, Wb)[None, :]
    v = np.clip(1 - 0.55 * np.exp(-(yy / 0.33) ** 2 - (xx / 0.75) ** 2) - 0.25 * (np.abs(yy) > 0.6), 0, 1)
    arr = (np.asarray(im).astype(np.float32) * v[..., None]).astype(np.uint8)
    im = Image.fromarray(arr)
    # caution tapes (visible on TV/desktop outside the safe area)
    for text, bg, fg, y, a in (('TATAMI TRAGIQUE  •  ', YEL, BLACK, 330, 4),
                               ('NOUVEAU SHORT CHAQUE JOUR  •  ', RED, WHITE, 1110, -3)):
        t = tape(text, bg, fg, 3400, 96, 56).rotate(a, Image.BICUBIC, expand=True)
        im.paste(t, (Wb // 2 - t.width // 2, y - t.height // 2), t)
    d = ImageDraw.Draw(im)
    # safe area: 1546 x 423 centered -> x 507..2053, y 508..931
    cx, cy = Wb // 2, Hb // 2
    # fighters on both sides (inside the tablet/desktop zone, just outside the phone-safe text block)
    ball(d, 612, 735, 100, (232, 62, 74), ang=math.radians(-28), weapon='katana', L=190, look=-0.3)
    ball(d, 1948, 735, 100, (45, 150, 255), ang=math.radians(208), weapon='nunchaku', L=150, look=math.pi + 0.3)
    sparks(d, 880, 590, 9, 60, rng)
    sparks(d, 1680, 590, 9, 60, rng)
    ball(d, 330, 470, 60, (226, 142, 60), ang=math.radians(20), weapon='bo', L=110, look=0.5)
    ball(d, 2250, 980, 60, (165, 95, 235), look=math.pi)
    ball(d, 2300, 450, 44, (245, 245, 245), look=math.pi, belt=(225, 225, 232), ko=True)
    ball(d, 270, 980, 44, (245, 245, 245), look=0, belt=(225, 225, 232))
    t = rich((T('TATAMI ', WHITE), T('TRAGIQUE', YEL)), ANTON, 170, stroke=8, shadow=12)
    place(im, t, cx, cy - 60, maxw=980)
    sub = rich((T('COMBATS  •  FAILS  •  CEINTURES NOIRES DE LA HONTE', (225, 225, 230)),), ANTON, 44, stroke=4)
    place(im, sub, cx, cy + 70, maxw=960)
    tag = rich((T('QUI VA GAGNER ? ', YEL), E('1f447')), LUCK, 56, stroke=8, shadow=6)
    place(im, tag, cx, cy + 150, rot=-2, maxw=900)
    im.save(path)
    # preview with the safe areas drawn
    pv = im.copy()
    pd = ImageDraw.Draw(pv)
    pd.rectangle([507, 508, 2053, 931], outline=(0, 255, 120), width=6)
    pd.rectangle([0, 0, Wb - 1, Hb - 1], outline=(255, 0, 255), width=6)
    pd.rectangle([(Wb - 1855) // 2, 508, (Wb + 1855) // 2, 931], outline=(0, 180, 255), width=4)
    pv.resize((1280, 720), Image.LANCZOS).save(path.replace('.png', '_zones.png'))
    im.crop((507, 508, 2053, 931)).save(path.replace('.png', '_apercu_mobile.png'))


if __name__ == '__main__':
    out = os.path.join(D, 'brand')
    os.makedirs(out, exist_ok=True)
    avatar(os.path.join(out, 'photo_profil.png'))
    banner(os.path.join(out, 'banniere.png'))
    print('ok')
