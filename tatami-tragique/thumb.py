#!/usr/bin/env python3
"""TATAMI TRAGIQUE - miniatures verticales 1080x1920 pour les Shorts."""
import sys, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from fight import logo, rich, place, T, E, ANTON, LUCK, YEL, RED, WHITE, BLACK, D

W, H = 1080, 1920


def cover(img, cx, cy, z):
    """Scale img to cover 1080x1920, zoom z, centred on (cx, cy) in source pixels."""
    s = max(W / img.width, H / img.height) * z
    w, h = W / s, H / s
    x0 = min(max(cx - w / 2, 0), img.width - w)
    y0 = min(max(cy - h / 2, 0), img.height - h)
    return img.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))


def grade(im):
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = ImageEnhance.Color(im).enhance(1.3)
    yy = np.linspace(0, 1, H)[:, None, None]
    shade = 1 - 0.75 * np.clip((0.36 - yy) / 0.36, 0, 1) ** 1.3 - 0.8 * np.clip((yy - 0.72) / 0.28, 0, 1) ** 1.3
    return Image.fromarray((np.asarray(im).astype(np.float32) * shade).astype(np.uint8))


def ring(im, cx, cy, rx, ry, arrow_from=None):
    d = ImageDraw.Draw(im)
    for w in range(14):
        d.ellipse([cx - rx - w, cy - ry - w, cx + rx + w, cy + ry + w], outline=RED)
    if arrow_from:
        ax, ay = arrow_from
        ang = math.atan2(cy - ay, cx - ax)
        ex, ey = cx - math.cos(ang) * (rx + 30), cy - math.sin(ang) * (ry + 30)
        d.line([(ax, ay), (ex, ey)], fill=RED, width=26)
        for sgn in (-1, 1):
            a2 = ang + math.pi + sgn * 0.5
            d.line([(ex, ey), (ex + math.cos(a2) * 80, ey + math.sin(a2) * 80)], fill=RED, width=26)


def unlabel(img, boxes):
    """Blur the source video's own ranking text."""
    img = img.copy()
    for b in boxes:
        img.paste(img.crop(b).filter(ImageFilter.GaussianBlur(10)), b[:2])
    return img


def make(frame, focus, z, lines_top, lines_bot, rings, out):
    im = grade(cover(frame, *focus, z))
    for r in rings:
        ring(im, *r)
    lg = logo(150)
    im.paste(lg, (40, 60), lg)
    y = 390
    for pieces, size, rot in lines_top:
        t = rich(pieces, LUCK, size, stroke=int(size * 0.13), shadow=int(size * 0.1))
        place(im, t, 540, y, 1, rot, maxw=1000)
        y += int(size * 1.15)
    y = 1560
    for pieces, size, rot in lines_bot:
        t = rich(pieces, ANTON, size, stroke=int(size * 0.08), shadow=int(size * 0.08))
        place(im, t, 540, y, 1, rot, maxw=1000)
        y += int(size * 1.08)
    im.save(out)
    im.resize((360, 640), Image.LANCZOS).save(out.replace('.png', '_petit.png'))


if __name__ == '__main__':
    which = sys.argv[1]
    if which == 'fails2':
        FR = np.load(D + '/frames2.npy', mmap_mode='r')
        fr = unlabel(Image.fromarray(np.ascontiguousarray(FR[485])), [(70, y - 32, x1, y + 32) for y, x1 in ((162, 300), (408, 280), (688, 470), (970, 340), (1284, 290))])
        make(fr, (560, 1150), 1.25,
             [((T('99% DU LOOPING...', WHITE),), 108, -2)],
             [((T('LA GRAVITÉ', YEL),), 170, -3), ((T('A GAGNÉ ', WHITE), E('1f480')), 150, -3)],
             [(470, 1250, 170, 150, (180, 900))], D + '/thumb_fails2.png')
    elif which == 'v2':
        FR = np.load(D + '/frames.npy', mmap_mode='r')
        fr = unlabel(Image.fromarray(np.ascontiguousarray(FR[542])), [(30, y - 36, 400, y + 36) for y in (335, 438, 544, 648, 756)] + [(230, 868, 560, 925)])
        make(fr, (440, 520), 1.0,
             [((T('3 COUPS DE PIED...', WHITE),), 104, -2)],
             [((T('0 RÉACTION ', YEL), E('1f5ff')), 170, -3), ((T('100% TITANE', WHITE),), 130, -3)],
             [(519, 1113, 150, 120, (200, 760))], D + '/thumb_v2.png')
