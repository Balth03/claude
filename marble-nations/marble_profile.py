#!/usr/bin/env python3
"""MARBLE NATIONS - photo de profil TikTok (1080x1080)."""
import math, numpy as np
from PIL import Image, ImageDraw, ImageFilter
E = 'assets/emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
S = 2048


def flag(cp):
    f = Image.open(E + cp + '.png').convert('RGBA')
    f = f.crop(f.getbbox())
    w, h = f.size
    s = min(w, h)
    f = f.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((512, 512), Image.LANCZOS)
    bg = Image.new('RGBA', f.size, (255, 255, 255, 255))
    bg.alpha_composite(f)
    return bg


def globe():
    g = Image.new('RGBA', (1024, 1024), (40, 120, 230, 255))
    gd = ImageDraw.Draw(g)
    rng = np.random.default_rng(3)
    for cx, cy, rx, ry in ((330, 380, 210, 170), (420, 640, 130, 210), (730, 330, 170, 120), (760, 560, 110, 170),
                           (640, 820, 160, 80)):
        pts = [(cx + rx * math.cos(t) * (0.75 + 0.3 * rng.random()), cy + ry * math.sin(t) * (0.75 + 0.3 * rng.random()))
               for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        gd.polygon(pts, fill=(70, 190, 90, 255))
    return g


def marble(im, cx, cy, R, tex):
    t = tex.resize((int(2 * R), int(2 * R)), Image.LANCZOS).convert('RGBA')
    m = Image.new('L', t.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, t.width - 1, t.height - 1], fill=255)
    a = np.asarray(t).astype(np.float32)
    y, x = np.mgrid[0:t.height, 0:t.width]
    nx, ny = (x - R) / R, (y - R) / R
    rr = np.clip(nx * nx + ny * ny, 0, 1)
    a[..., :3] *= (0.55 + 0.45 * np.clip(1 - ((nx + 0.35) ** 2 + (ny + 0.45) ** 2) / 1.6, 0, 1))[..., None]
    a[..., :3] *= (1 - 0.35 * rr ** 3)[..., None]
    t = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    sh = Image.new('L', (S, S), 0)
    ImageDraw.Draw(sh).ellipse([cx - R * 0.95, cy + R * 0.7, cx + R * 0.95, cy + R * 1.12], fill=110)
    im.paste((0, 0, 20), (0, 0), sh.filter(ImageFilter.GaussianBlur(R * 0.12)))
    ImageDraw.Draw(im).ellipse([cx - R * 1.05, cy - R * 1.05, cx + R * 1.05, cy + R * 1.05], fill=(10, 14, 30))
    im.paste(t, (int(cx - R), int(cy - R)), m)
    hl = Image.new('L', (S, S), 0)
    ImageDraw.Draw(hl).ellipse([cx - R * 0.62, cy - R * 0.78, cx - R * 0.05, cy - R * 0.38], fill=200)
    im.paste((255, 255, 255), (0, 0), hl.filter(ImageFilter.GaussianBlur(R * 0.07)))


yy, xx = np.mgrid[0:S, 0:S]
r = np.hypot(xx - S / 2, yy - S * 0.45) / S
bg = np.stack([20 + 40 * (1 - r), 40 + 60 * (1 - r), 110 + 90 * (1 - r)], -1)
ang = np.arctan2(yy - S * 0.45, xx - S / 2)
bg += (np.sin(ang * 14) > 0)[..., None] * np.array([10, 14, 22]) * (1 - r)[..., None]
im = Image.fromarray(bg.clip(0, 255).astype(np.uint8))
marble(im, 1230, 820, 500, globe())
d = ImageDraw.Draw(im)
for y, x0, l in ((1330, 170, 520), (1470, 90, 420), (1610, 60, 330)):
    d.rounded_rectangle([x0, y - 16, x0 + l, y + 16], radius=16, fill=(235, 240, 255))
marble(im, 1060, 1320, 185, flag('1f1fa-1f1f8'))
marble(im, 760, 1470, 185, flag('1f1eb-1f1f7'))
marble(im, 470, 1610, 150, flag('1f1e7-1f1f7'))
out = im.resize((1080, 1080), Image.LANCZOS)
out.save('marble/profile.png')
m = Image.new('L', (1080, 1080), 0)
ImageDraw.Draw(m).ellipse([0, 0, 1079, 1079], fill=255)
pv = Image.new('RGB', (1080, 1080), (255, 255, 255))
pv.paste(out, (0, 0), m)
pv.resize((360, 360), Image.LANCZOS).save('marble/profile_rond.png')
