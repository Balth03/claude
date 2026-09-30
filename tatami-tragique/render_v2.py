#!/usr/bin/env python3
"""TATAMI TRAGIQUE - montage du Top 5 des fails d'arts martiaux (format Short 1080x1920)."""
import numpy as np, subprocess, math, os, sys, functools
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from scipy.signal import butter, sosfilt, lfilter

D = os.path.dirname(os.path.abspath(__file__))
FPS = 30
W, H = 1080, 1920
VW, VH = 1080, 1372
VY = 300
FR = np.load(os.path.join(D, 'frames.npy'), mmap_mode='r')
ANTON = D + '/assets/anton.ttf'
LUCK = D + '/assets/luckiest-guy.ttf'
EMO = D + '/assets/emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
YEL = (255, 210, 31)
RED = (230, 57, 70)
WHITE = (255, 255, 255)
BLACK = (12, 12, 14)
GREY = (165, 165, 172)
PREVIEW = '--preview' in sys.argv


@functools.lru_cache(None)
def font(p, s):
    return ImageFont.truetype(p, s)


def clamp01(t):
    return min(max(t, 0.0), 1.0)


def ease_out(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def back_out(t, s=2.2):
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def lerp(a, b, u):
    return a + (b - a) * u


def T(s, c=WHITE):
    return ('t', s, c)


def E(cp):
    return ('e', cp, None)


# ---------------------------------------------------------------- text / images
@functools.lru_cache(None)
def emoji(cp, size):
    return Image.open(EMO + cp + '.png').convert('RGBA').resize((size, size), Image.LANCZOS)


_tmpd = ImageDraw.Draw(Image.new('RGBA', (1, 1)))


@functools.lru_cache(None)
def rich(pieces, fp, size, stroke=0, shadow=0):
    f = font(fp, size)
    asc, desc = f.getmetrics()
    pad = stroke + 6
    widths = []
    for k, v, c in pieces:
        if k == 't':
            widths.append(_tmpd.textlength(v, font=f))
        else:
            widths.append(int(size * 1.25))
    Wt = int(sum(widths)) + 2 * pad + stroke * 2
    Ht = asc + desc + 2 * pad + shadow
    im = Image.new('RGBA', (Wt, Ht), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    base = pad + asc
    if shadow:
        x = pad + stroke
        for (k, v, c), w in zip(pieces, widths):
            if k == 't':
                d.text((x, base + shadow), v, font=f, fill=(0, 0, 0, 150), anchor='ls',
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
            x += w
    x = pad + stroke
    for (k, v, c), w in zip(pieces, widths):
        if k == 't':
            d.text((x, base), v, font=f, fill=c, anchor='ls', stroke_width=stroke, stroke_fill=(0, 0, 0))
        else:
            es = int(size * 1.08)
            im.alpha_composite(emoji(v, es), (int(x + size * 0.14), int(base - es * 0.86)))
        x += w
    return im


def place(cv, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0, maxw=1010):
    if im.width * scale > maxw:
        scale = maxw / im.width
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel('A').point(lambda v: int(v * alpha)))
    cv.paste(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))), im)


def pop_scale(t, dur=0.2, start=0.25):
    if t < 0:
        return 0
    return start + (1 - start) * back_out(t / dur)


# ---------------------------------------------------------------- brand
@functools.lru_cache(None)
def logo(size):
    S = 4
    s = size * S
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, s - 1, s - 1], fill=BLACK)
    d.ellipse([s * 0.04, s * 0.04, s * 0.96, s * 0.96], fill=RED)
    d.ellipse([s * 0.10, s * 0.10, s * 0.90, s * 0.90], outline=WHITE, width=int(s * 0.03))
    # belt band clipped to circle
    band = Image.new('L', (s, s), 0)
    bd = ImageDraw.Draw(band)
    bd.rectangle([0, s * 0.40, s, s * 0.58], fill=255)
    circ = Image.new('L', (s, s), 0)
    ImageDraw.Draw(circ).ellipse([s * 0.10, s * 0.10, s * 0.90, s * 0.90], fill=255)
    band = Image.fromarray(np.minimum(np.asarray(band), np.asarray(circ)))
    ol = int(s * 0.018)
    dark = Image.new('RGBA', (s, s), BLACK + (255,))
    im.paste(dark, (0, -ol), band)
    im.paste(dark, (0, ol), band)
    im.paste(Image.new('RGBA', (s, s), YEL + (255,)), (0, 0), band)
    # tails
    c = s / 2
    for sgn in (-1, 1):
        pts = [(c + sgn * s * 0.02, s * 0.52), (c + sgn * s * 0.12, s * 0.52),
               (c + sgn * s * 0.26, s * 0.86), (c + sgn * s * 0.13, s * 0.88)]
        d.polygon(pts, fill=YEL, outline=BLACK, width=ol)
    # knot
    k = s * 0.13
    d.rounded_rectangle([c - k, s * 0.49 - k, c + k, s * 0.49 + k], radius=s * 0.03, fill=YEL,
                        outline=BLACK, width=ol)
    d.line([c - k * 0.5, s * 0.49 - k * 0.7, c + k * 0.5, s * 0.49 + k * 0.7], fill=BLACK, width=ol)
    return im.resize((size, size), Image.LANCZOS)


@functools.lru_cache(None)
def header(pq):
    prog = pq / 50
    im = Image.new('RGB', (W, VY), BLACK)
    a = np.linspace(0, 1, VY)[:, None, None]
    arr = (np.array(BLACK) * (1 - a) + np.array((30, 30, 36)) * a).astype(np.uint8)
    im = Image.fromarray(np.repeat(arr, W, axis=1))
    lg = logo(176)
    im.paste(lg, (36, 58), lg)
    t = rich((T('TATAMI ', WHITE), T('TRAGIQUE', YEL)), ANTON, 108)
    im.paste(t, (228, 146 - t.height // 2 - 6), t)
    st = rich((T("TOP 5 • LES PIRES FAILS D'ARTS MARTIAUX", GREY),), ANTON, 34)
    im.paste(st, (232, 196), st)
    d = ImageDraw.Draw(im)
    x0, x1, y0, y1, gap = 40, 1040, 262, 276, 12
    sw = (x1 - x0 - 4 * gap) / 5
    for j in range(5):
        sx = x0 + j * (sw + gap)
        d.rounded_rectangle([sx, y0, sx + sw, y1], radius=7, fill=(52, 52, 58))
        fr = clamp01(prog - j)
        if fr > 0:
            d.rounded_rectangle([sx, y0, sx + max(14, sw * fr), y1], radius=7, fill=YEL)
    d.rectangle([0, VY - 4, W, VY], fill=YEL)
    return im


def make_bottom():
    im = Image.new('RGB', (W, H - VY - VH), BLACK)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 4], fill=YEL)
    t = rich((T('@TATAMITRAGIQUE', (90, 90, 96)),), ANTON, 34)
    im.paste(t, ((W - t.width) // 2, 22), t)
    return im


BOTTOM = make_bottom()

# ---------------------------------------------------------------- video layer
_sc, _bl = {}, {}


def scaled(i):
    if i not in _sc:
        if len(_sc) > 60:
            _sc.pop(next(iter(_sc)))
        _sc[i] = Image.fromarray(np.ascontiguousarray(FR[i])).resize((VW, VH), Image.LANCZOS)
    return _sc[i]


def blurred(i):
    if i not in _bl:
        if len(_bl) > 60:
            _bl.pop(next(iter(_bl)))
        _bl[i] = scaled(i).resize((270, 343), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7)) \
            .resize((VW, VH), Image.BICUBIC)
    return _bl[i]


ROW_CY = {1: 498, 2: 654, 3: 811, 4: 969, 5: 1127}
COVER = {1: 505, 2: 400, 3: 415, 4: 528, 5: 558}
LABEL = {5: 'TRAHISON AU PEPSI', 4: 'MAUVAISE CIBLE', 3: 'LE MUR A GAGNÉ', 2: 'LE FRIGO HUMAIN',
         1: 'BIJOUX EN TITANE'}
RANKCOL = {1: YEL, 2: (210, 214, 224), 3: (222, 140, 72), 4: RED, 5: RED}
X0, PH = 36, 82


@functools.lru_cache(None)
def pill_assets(k, revealed, hl, flash):
    S = 2
    mask = Image.new('L', (VW * S, VH * S), 0)
    ov = Image.new('RGBA', (VW * S, VH * S), (0, 0, 0, 0))
    md, od = ImageDraw.Draw(mask), ImageDraw.Draw(ov)
    fl = font(ANTON, 42 * S)
    for r in range(1, 6):
        cy = ROW_CY[r]
        rev = r in revealed
        lab = LABEL[r] if rev else '???'
        tw = _tmpd.textlength(lab, font=font(ANTON, 42))
        x1 = X0 + 86 + tw + 28
        x1 = max(x1, COVER[r] if r >= k else 150)
        box = [X0 * S, (cy - PH / 2) * S, x1 * S, (cy + PH / 2) * S]
        rad = PH / 2 * S
        md.rounded_rectangle(box, radius=rad, fill=255)
        if r == hl:
            g = 8 * S
            od.rounded_rectangle([box[0] - g, box[1] - g, box[2] + g, box[3] + g], radius=rad + g,
                                 fill=YEL + (60,))
        od.rounded_rectangle(box, radius=rad, fill=(0, 0, 0, 120))
        if r == hl and flash:
            od.rounded_rectangle(box, radius=rad, fill=YEL + (int(flash * 30),))
        od.rounded_rectangle(box, radius=rad, outline=(YEL + (255,)) if r == hl else (255, 255, 255, 70),
                             width=(5 if r == hl else 2) * S)
        bx = X0 + 42
        od.ellipse([(bx - 30) * S, (cy - 30) * S, (bx + 30) * S, (cy + 30) * S], fill=RANKCOL[r],
                   outline=BLACK, width=2 * S)
        od.text((bx * S, (cy + 1) * S), str(r), font=font(ANTON, 42 * S),
                fill=BLACK if r <= 3 else WHITE, anchor='mm')
        col = (WHITE if r == hl else (225, 225, 230)) if rev else (150, 150, 158)
        od.text(((X0 + 86) * S, (cy + 1) * S), lab, font=fl, fill=col, anchor='lm',
                stroke_width=S * 2, stroke_fill=(0, 0, 0))
    return mask.resize((VW, VH), Image.LANCZOS), ov.resize((VW, VH), Image.LANCZOS)


def vlayer(i, pst):
    base = scaled(i)
    if pst is None:
        return base.copy()
    m, ov = pill_assets(*pst)
    im = Image.composite(blurred(i), base, m)
    im.paste(ov, (0, 0), ov)
    return im


def zoom(im, z, cx, cy):
    if z <= 1.001:
        return im
    w, h = VW / z, VH / z
    x0 = min(max(cx - w / 2, 0), VW - w)
    y0 = min(max(cy - h / 2, 0), VH - h)
    return im.resize((VW, VH), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + h))


def dim(im, f):
    if f >= 0.999:
        return im
    return Image.fromarray((np.asarray(im).astype(np.float32) * f).astype(np.uint8))


def make_vignette():
    yy, xx = np.mgrid[0:VH, 0:VW]
    r = np.sqrt(((xx - VW / 2) / (VW / 2)) ** 2 + ((yy - VH / 2) / (VH / 2)) ** 2)
    a = (np.clip((r - 0.55) / 0.75, 0, 1) ** 1.4 * 210).astype(np.uint8)
    im = Image.new('RGBA', (VW, VH), (0, 0, 0, 0))
    im.putalpha(Image.fromarray(a))
    return im


VIGN = make_vignette()


def make_scan():
    a = np.zeros((VH, VW), np.uint8)
    a[::4] = 38
    im = Image.new('RGBA', (VW, VH), (0, 0, 0, 0))
    im.putalpha(Image.fromarray(a))
    return im


SCAN = make_scan()


def compose(video, prog, dx=0, dy=0):
    cv = Image.new('RGB', (W, H), BLACK)
    cv.paste(video, (int(dx), VY + int(dy)))
    cv.paste(BOTTOM, (0, VY + VH))
    cv.paste(header(int(round(prog * 50))), (0, 0))
    return cv


def pill_state(k, tcard):
    rev = tuple(r for r in range(1, 6) if r > k or (r == k and tcard >= 0.85))
    fl = 0
    if 0.85 <= tcard < 1.2:
        fl = round((1 - (tcard - 0.85) / 0.35) * 4) / 4
    return (k, rev, k, fl)


# ---------------------------------------------------------------- overlays
@functools.lru_cache(None)
def card(k):
    num = rich((T(f'N°{k}', YEL),), ANTON, 260, stroke=13, shadow=12)
    lab = rich((T(LABEL[k], WHITE),), LUCK, 80, stroke=10, shadow=7)
    w = max(num.width, lab.width)
    im = Image.new('RGBA', (w, num.height + lab.height - 70), (0, 0, 0, 0))
    im.alpha_composite(num, ((w - num.width) // 2, 0))
    im.alpha_composite(lab, ((w - lab.width) // 2, num.height - 70))
    return im


def draw_card(cv, k, t):
    CX, CY = 540, 830
    if t < 0 or t >= 0.85:
        return
    x, y, rot, a = CX, CY, -4, 1.0
    if t < 0.2:
        s = 2.6 - 1.6 * ease_out(t / 0.2)
        a = clamp01(t / 0.07)
    elif t < 0.3:
        s = 1.0
        rot = -4 + 2 * math.sin((t - 0.2) / 0.1 * math.pi)
    elif t < 0.55:
        s = 1.0
    else:
        u = ease_io((t - 0.55) / 0.3)
        x = lerp(CX, X0 + 200, u)
        y = lerp(CY, VY + ROW_CY[k], u)
        s = 1 - 0.8 * u
        a = 1 - 0.85 * u
        rot = -4 * (1 - u)
    place(cv, card(k), x, y, s, rot, a, maxw=1040)


@functools.lru_cache(None)
def stamp(text):
    f = font(ANTON, 132)
    tw = _tmpd.textlength(text, font=f)
    asc, desc = f.getmetrics()
    pad = 34
    w, h = int(tw + 2 * pad), int(asc + desc * 0.2 + 2 * pad - 30)
    im = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, w + 10, h + 10], radius=22, outline=RED, width=13, fill=(0, 0, 0, 70))
    d.text((10 + w / 2, 10 + h / 2 + 4), text, font=f, fill=RED, anchor='mm')
    rng = np.random.default_rng(abs(hash(text)) % 1000)
    n = rng.random((im.height // 7 + 2, im.width // 7 + 2)).astype(np.float32)
    n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)) / 255.0
    a = np.asarray(im.getchannel('A')).astype(np.float32) * (0.45 + 0.55 * (n > 0.22))
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def tri_icon(size, color, n=2, reverse=True):
    im = Image.new('RGBA', (int(size * 0.9 * n), size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for j in range(n):
        x = j * size * 0.8
        if reverse:
            d.polygon([(x, size / 2), (x + size * 0.8, 0), (x + size * 0.8, size)], fill=color)
        else:
            d.polygon([(x, 0), (x + size * 0.8, size / 2), (x, size)], fill=color)
    return im


def cursor_img():
    S = 1.5
    pts = [(0, 0), (0, 58), (15, 45), (26, 69), (37, 64), (26, 41), (44, 41)]
    pts = [(6 + x * S, 6 + y * S) for x, y in pts]
    im = Image.new('RGBA', (90, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon(pts, fill=WHITE, outline=BLACK, width=5)
    return im


CURSOR = cursor_img()

# ---------------------------------------------------------------- segments
segs = []
AUD = []   # (t, name, gain)
SRC = []   # (t_out, src_t0, src_t1, gain, speed)
TT = [0]


class Seg:
    prog = 0.0

    def __init__(self, n):
        self.n = n
        self.start = TT[0]
        TT[0] += n
        segs.append(self)

    @property
    def t0(self):
        return self.start / FPS

    def P(self, n):
        g = getattr(self, 'group', None)
        if g is None:
            return self.prog
        j, off, G = g
        return j + (off + n) / G


def sfx(t, name, gain):
    AUD.append((t, name, gain))


class Intro(Seg):
    """Cold open : les coups de pied au maître EN MOUVEMENT, pas d'image figée."""
    F0, F1 = 530, 568

    def __init__(self, n):
        super().__init__(n)
        SRC.append((self.t0, self.F0 / FPS, (self.F0 + n) / FPS, 1.0, 1.0))
        for hf in (541, 562):
            sfx(self.t0 + (hf - self.F0) / FPS, 'punch', 0.6)
        sfx(self.t0 + 0.02, 'impact', 0.6)

    def render(self, n):
        t = n / FPS
        i = min(self.F0 + n, self.F1)
        v = vlayer(i, (1, (), 0, 0))
        v = zoom(v, 1.12, 0, 520)
        v = dim(v, 0.85)
        cv = compose(v, 0)
        top5 = rich((T('TOP 5', YEL),), ANTON, 250, stroke=13, shadow=12)
        place(cv, top5, 540, 520, 2.4 - 1.4 * back_out(t / 0.18, 1.4), -4, clamp01(t / 0.05))
        l2 = rich((T("DES PIRES FAILS D'ARTS MARTIAUX", WHITE),), LUCK, 70, stroke=10, shadow=7)
        if t >= 0.12:
            place(cv, l2, 540, 700, pop_scale(t - 0.12), 0)
        if t >= 0.35:
            l4 = rich((T('(le n°1 va te faire mal ', YEL), E('1f62c'), T(')', YEL)), LUCK, 58, stroke=8, shadow=5)
            place(cv, l4, 540, 800, pop_scale(t - 0.35), 3)
        return cv


class Hold(Seg):
    """First frame of a clip held while the rank card slams in."""
    def __init__(self, n, k, frame):
        super().__init__(n)
        self.k, self.frame = k, frame
        sfx(self.t0 + 0.16, 'impact', 0.75)
        sfx(self.t0 + 0.55, 'whoosh_s', 0.25)
        sfx(self.t0 + 0.85, 'pop', 0.45)

    def render(self, n):
        t = n / FPS
        v = vlayer(self.frame, pill_state(self.k, t))
        v = dim(v, 1 - 0.35 * ease_out(t / 0.15))
        cv = compose(v, self.P(n))
        draw_card(cv, self.k, t)
        return cv


class Play(Seg):
    def __init__(self, k, f0, f1, tcard0=None, caps=(), hits=()):
        super().__init__(f1 - f0 + 1)
        self.k, self.f0, self.tcard0, self.caps = k, f0, tcard0, caps
        SRC.append((self.t0, f0 / FPS, (f1 + 1) / FPS, 1.0, 1.0))
        for hf, name, g in hits:
            sfx(self.t0 + (hf - f0) / FPS, name, g)

    def render(self, n):
        i = self.f0 + n
        tc = (self.tcard0 + n / FPS) if self.tcard0 is not None else 9
        v = vlayer(i, pill_state(self.k, tc))
        if self.tcard0 is not None and tc < 0.7:
            v = dim(v, 0.65 + 0.35 * ease_out((tc - 0.533) / 0.15))
        dx = dy = 0
        for (a, b, img, y, shake) in self.caps:
            if a <= i <= b and shake and i - a < 4:
                amp = 10 * (1 - (i - a) / 4)
                dx, dy = amp * math.sin(i * 7.1), amp * math.cos(i * 5.3)
        cv = compose(v, self.P(n), dx, dy)
        if self.tcard0 is not None:
            draw_card(cv, self.k, tc)
        for (a, b, img, y, shake) in self.caps:
            if a <= i <= b:
                tt = (i - a) / FPS
                place(cv, img, 540, y, pop_scale(tt, 0.18, 0.3), 2 * math.sin(i * 0.4))
        return cv


class Freeze(Seg):
    def __init__(self, k, frame, n, j):
        super().__init__(n)
        self.k, self.frame, self.j = k, frame, j
        t0 = self.t0
        sfx(t0, 'scratch', 0.55)
        sfx(t0 + 0.08, 'pop', 0.3)
        sfx(t0 + 0.42, j.get('punch_sfx', 'boom'), j.get('punch_gain', 0.6))
        sfx(t0 + 0.95, j['stamp_sfx'], j.get('stamp_gain', 0.7))
        self.l1 = rich(j['l1'], LUCK, 62, stroke=9, shadow=6)
        self.l2 = [rich(p, LUCK, 84, stroke=11, shadow=8) for p in j['l2']]
        self.st = stamp(j['stamp'])

    def render(self, n):
        t = n / FPS
        j = self.j
        v = vlayer(self.frame, (self.k, tuple(r for r in range(1, 6) if r >= self.k), self.k, 0))
        if 'circle' in j and t > 0.95:
            cx, cy, r = j['circle']
            d = ImageDraw.Draw(v)
            sweep = 360 * ease_out((t - 0.95) / 0.3)
            for w_ in range(0, 11):
                d.arc([cx - r - w_, cy - r * 0.8 - w_, cx + r + w_, cy + r * 0.8 + w_], -100, -100 + sweep,
                      fill=RED, width=2)
        z = 1 + 0.13 * ease_out(t / 0.14) + 0.07 * t / (self.n / FPS)
        v = zoom(v, z, *j['focus'])
        v = dim(v, 1 - 0.4 * ease_out(t / 0.25))
        v.paste(VIGN, (0, 0), VIGN)
        dx = dy = 0
        ts = t - 0.95
        if 0 <= ts < 0.18:
            amp = 18 * (1 - ts / 0.18)
            dx, dy = amp * math.sin(n * 7.3), amp * math.cos(n * 4.1)
        if t < 0.12:
            v = Image.blend(v, Image.new('RGB', v.size, WHITE), 0.55 * (1 - t / 0.12))
        cv = compose(v, self.P(n), dx, dy)
        if t >= 0.08:
            place(cv, self.l1, 540 + dx, 430 + dy, pop_scale(t - 0.08), -1.5)
        if t >= 0.42:
            y = 540
            for im in self.l2:
                place(cv, im, 540 + dx, y + dy, pop_scale(t - 0.42, 0.22, 0.2), 1.5)
                y += 98
        if ts >= 0:
            s = 2.8 - 1.8 * ease_out(ts / 0.12)
            place(cv, self.st, 560 + dx, 1250 + dy, s, 11, clamp01(ts / 0.05) * 0.95)
        return cv


class Rewind(Seg):
    def __init__(self, k, fa, fb, n):
        super().__init__(n)
        self.k, self.fa, self.fb = k, fa, fb
        sfx(self.t0, 'rewind', 0.5)

    def render(self, n):
        i = int(round(lerp(self.fa, self.fb, n / (self.n - 1))))
        v = vlayer(i, (self.k, tuple(range(self.k, 6)), self.k, 0))
        v = ImageEnhance.Color(v).enhance(0.45)
        a = np.asarray(v).copy()
        rng = np.random.default_rng(n)
        for _ in range(5):
            y = rng.integers(0, VH - 40)
            h = rng.integers(8, 40)
            a[y:y + h] = np.roll(a[y:y + h], rng.integers(-60, 60), axis=1)
        v = Image.fromarray(a)
        v.paste(SCAN, (0, 0), SCAN)
        cv = compose(v, self.P(n))
        ic = tri_icon(54, WHITE, 2, True)
        cv.paste(ic, (58, 350), ic)
        lab = rich((T('REWIND', WHITE),), ANTON, 58, stroke=4)
        cv.paste(lab, (150, 350 + 27 - lab.height // 2), lab)
        return cv


class Replay(Seg):
    def __init__(self, k, fa, fb, n, focus, z):
        super().__init__(n)
        self.k, self.fa, self.fb, self.focus, self.z = k, fa, fb, focus, z
        speed = (fb - fa) / n
        SRC.append((self.t0, fa / FPS, fb / FPS, 0.9, speed))
        self.speed = speed

    def render(self, n):
        p = lerp(self.fa, self.fb, n / (self.n - 1))
        i0 = int(math.floor(p))
        fr = p - i0
        pst = (self.k, tuple(range(self.k, 6)), self.k, 0)
        v = vlayer(i0, pst)
        if fr > 0.01 and i0 + 1 <= self.fb:
            v = Image.blend(v, vlayer(i0 + 1, pst), fr)
        v = zoom(v, self.z, *self.focus)
        v = ImageEnhance.Color(v).enhance(0.75)
        v.paste(SCAN, (0, 0), SCAN)
        v.paste(VIGN, (0, 0), VIGN)
        cv = compose(v, self.P(n))
        d = ImageDraw.Draw(cv)
        if (n // 12) % 2 == 0:
            d.ellipse([60, 362, 100, 402], fill=RED)
        lab = rich((T('REPLAY', WHITE),), ANTON, 58, stroke=4)
        cv.paste(lab, (116, 382 - lab.height // 2), lab)
        sp = rich((T('RALENTI x0.3', YEL),), ANTON, 40, stroke=3)
        cv.paste(sp, (62, 432), sp)
        return cv


class Whip(Seg):
    def __init__(self, n, full=False):
        super().__init__(n)
        self.full = full
        sfx(self.t0 - 0.05, 'whoosh', 0.5)

    def link(self, a, b):
        self.a, self.b = a, b

    def render(self, n):
        if not hasattr(self, 'A'):
            self.A = np.asarray(self.a.render(self.a.n - 1))
            self.B = self.b.render(0)
        y0, y1 = (0, H) if self.full else (VY, VY + VH)
        A = self.A[y0:y1]
        B = np.asarray(self.B)[y0:y1]
        p = ease_io((n + 1) / (self.n + 1))
        sh = int(p * W)
        comp = np.empty_like(A)
        comp[:, :W - sh] = A[:, sh:]
        comp[:, W - sh:] = B[:, :sh]
        bw = int(140 * math.sin(math.pi * p)) + 1
        if bw > 2:
            c = np.cumsum(np.pad(comp.astype(np.float32), ((0, 0), (bw, 0), (0, 0)), mode='edge'), axis=1)
            comp = ((c[:, bw:] - c[:, :-bw]) / bw)
            comp = comp[:, :W]
        fl = 0.3 * math.sin(math.pi * p)
        comp = comp * (1 - fl) + 255 * fl
        cv = self.B.copy()
        cv.paste(Image.fromarray(np.clip(comp, 0, 255).astype(np.uint8)), (0, y0))
        return cv


def make_tape(text, bg, fg, w=3600, h=92):
    im = Image.new('RGBA', (w, h), bg + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 6], fill=BLACK)
    d.rectangle([0, h - 7, w, h], fill=BLACK)
    f = font(ANTON, 54)
    x = 0
    while x < w:
        d.text((x, h / 2 + 2), text, font=f, fill=fg, anchor='lm')
        x += _tmpd.textlength(text, font=f)
    return im


class Outro(Seg):
    def __init__(self, n):
        super().__init__(n)
        t0 = self.t0
        sfx(t0 + 0.02, 'jingle', 0.5)
        sfx(t0 + 0.05, 'impact', 0.7)
        sfx(t0 + 0.45, 'pop', 0.35)
        sfx(t0 + 0.7, 'pop', 0.35)
        sfx(t0 + 1.05, 'pop', 0.4)
        sfx(t0 + 1.95, 'click', 0.8)
        sfx(t0 + 2.02, 'ding', 0.5)
        sfx(t0 + 2.35, 'pop', 0.3)
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - 800) / H) ** 2)
        g = np.clip(1 - r * 1.6, 0, 1)[..., None]
        self.bg = Image.fromarray((np.array(BLACK) + g * np.array((34, 30, 40))).astype(np.uint8))
        self.tape1 = make_tape('TATAMI TRAGIQUE  •  ', YEL, BLACK)
        self.tape2 = make_tape('ABONNE-TOI  •  ', RED, WHITE)
        self.title = rich((T('TATAMI ', WHITE), T('TRAGIQUE', YEL)), ANTON, 128, stroke=6, shadow=8)
        self.q = rich((T('LEQUEL EST LE PIRE ?', WHITE),), LUCK, 80, stroke=10, shadow=7)
        self.q2 = rich((T('DIS-LE EN COMMENTAIRE ', YEL), E('1f447')), LUCK, 60, stroke=8, shadow=6)
        self.tag1 = rich((T('...sinon le maître vient', (215, 215, 222)),), LUCK, 46, stroke=6)
        self.tag2 = rich((T('vérifier les tiens ', (215, 215, 222)), E('1f5ff')), LUCK, 46, stroke=6)

    def button(self, subbed):
        w, h = 600, 140
        im = Image.new('RGBA', (w + 20, h + 26), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 18, w + 10, h + 18], radius=70, fill=(0, 0, 0, 140))
        d.rounded_rectangle([10, 8, w + 10, h + 8], radius=70, fill=(62, 62, 70) if subbed else RED)
        if subbed:
            d.text((10 + w / 2 - 30, 8 + h / 2), 'ABONNÉ', font=font(ANTON, 72), fill=(200, 200, 206),
                   anchor='mm')
        else:
            d.text((10 + w / 2, 8 + h / 2), "S'ABONNER", font=font(ANTON, 76), fill=WHITE, anchor='mm')
        return im

    def render(self, n):
        t = n / FPS
        cv = self.bg.copy()
        off = int(t * 260) % 1200
        for tape, y, ang, sgn in ((self.tape1, 175, 6, 1), (self.tape2, 1770, -5, -1)):
            x = off if sgn > 0 else 1200 - off
            strip = tape.crop((x, 0, x + 1400, tape.height)).rotate(ang, Image.BICUBIC, expand=True)
            cv.paste(strip, (W // 2 - strip.width // 2, y - strip.height // 2), strip)
        s = 2.6 - 1.6 * back_out(t / 0.25, 1.3)
        place(cv, logo(300), 540, 560, s, 0, clamp01(t / 0.06))
        if t >= 0.15:
            place(cv, self.title, 540, 790, pop_scale(t - 0.15), 0)
        if t >= 0.45:
            place(cv, self.q, 540, 980, pop_scale(t - 0.45), -1.5)
        if t >= 0.7:
            place(cv, self.q2, 540, 1080, pop_scale(t - 0.7), 1.5)
        if t >= 1.05:
            subbed = t >= 2.0
            bs = pop_scale(t - 1.05)
            if 1.95 <= t < 2.05:
                bs *= 0.9
            place(cv, self.button(subbed), 540, 1320, bs, 0)
            if subbed:
                rot = 18 * math.sin((t - 2.0) * 26) * math.exp(-(t - 2.0) * 3)
                place(cv, emoji('1f514', 84), 540 + 150, 1320, 1, rot)
        if 1.25 <= t < 2.9:
            u = ease_io((t - 1.25) / 0.65)
            cx, cy = lerp(930, 700, u), lerp(1700, 1345, u)
            sc = 0.88 if 1.95 <= t < 2.05 else 1.0
            place(cv, CURSOR, cx + 40, cy + 55, sc, 0, 1 - clamp01((t - 2.6) / 0.3))
        if t >= 2.35:
            place(cv, self.tag1, 540, 1500, pop_scale(t - 2.35), 0)
            place(cv, self.tag2, 540, 1566, pop_scale(t - 2.42), 0)
        return cv


# ---------------------------------------------------------------- timeline
HOLD = 12


def cap(pieces, size=66, color_stroke=9):
    return rich(pieces, LUCK, size, stroke=color_stroke, shadow=6)


def group(j, seglist):
    G = sum(s.n for s in seglist)
    off = 0
    for s in seglist:
        s.group = (j, off, G)
        off += s.n


intro = Intro(38)
w0 = Whip(8)

# ---- N°5 : bottle betrayal (frames 0-94)
g5 = [Hold(HOLD, 5, 12), Play(5, 12, 65, tcard0=HOLD / FPS)]
J5 = dict(l1=(T('ELLE A LÂCHÉ LA BOUTEILLE...'),),
          l2=[(T('LE POTEAU, LUI,', YEL),), (T("N'A RIEN LÂCHÉ ", YEL), E('1f480'))],
          stamp='TIBIA 0 - 1 POTEAU', stamp_sfx='clang', focus=(0, 520))
g5 += [Freeze(5, 66, 60, J5)]
group(0, g5)
w1 = Whip(8)

# ---- N°4 : wrong target (frames 105-201)
J4 = dict(l1=(T('RÈGLE N°1 DU DOJO :'),),
          l2=[(T('NE JAMAIS SE CACHER', YEL),), (T('DERRIÈRE LE MANNEQUIN ', YEL), E('1f602'))],
          stamp='DÉGÂT COLLATÉRAL', stamp_sfx='slide', stamp_gain=0.5, focus=(0, 760),
          circle=(540, 800, 170))
g4 = [Hold(HOLD, 4, 135), Play(4, 135, 200, tcard0=HOLD / FPS), Freeze(4, 201, 62, J4)]
group(1, g4)
w2 = Whip(8)

# ---- N°3 : bad kick (frames 212-300)
J3 = dict(l1=(T('LE SAC A DÉMISSIONNÉ...'),),
          l2=[(T('LE MUR A PRIS LE RELAIS ', YEL), E('1f62d'))],
          stamp='DIGNITÉ : 0', stamp_sfx='impact', stamp_gain=0.45, punch_sfx='trombone',
          punch_gain=0.55, focus=(0, 620))
g3 = [Hold(HOLD, 3, 228), Play(3, 228, 292, tcard0=HOLD / FPS), Freeze(3, 293, 62, J3)]
group(2, g3)
w3 = Whip(8)

# ---- N°2 : nice try (frames 358-505)
J2 = dict(l1=(T('IL A VOULU PLAQUER UN FRIGO...'),),
          l2=[(T('LE FRIGO A RÉPLIQUÉ ', YEL), E('1f480'))],
          stamp='FATALITY', stamp_sfx='boom', stamp_gain=0.75, focus=(0, 860))
g2 = [Hold(HOLD, 2, 378),
      Play(2, 378, 504, tcard0=HOLD / FPS,
           caps=[(458, 504, cap((T("ATTENDS... C'EST PAS FINI ", WHITE), E('1f633')), 60), 430, False)]),
      Freeze(2, 505, 58, J2)]
group(3, g2)
w4 = Whip(8)

# ---- N°1 : balls of steel (frames 518-626)
kc = lambda s: cap((T(s, YEL),), 92, 11)
react = rich((T('RÉACTION DU MAÎTRE : 0 ', WHITE), E('1f5ff')), LUCK, 56, stroke=8, shadow=5)
J1 = dict(l1=(T('3 COUPS DE PIED. 0 RÉACTION.'),),
          l2=[(T('IL VÉRIFIE JUSTE QUE', YEL),), (T('TOUT EST ENCORE LÀ ', YEL), E('1f5ff'))],
          stamp='100% TITANE', stamp_sfx='ding_big', stamp_gain=0.7, focus=(0, 640))
g1 = [Hold(HOLD, 1, 518),
      Play(1, 518, 568, tcard0=HOLD / FPS,
           caps=[(521, 541, kc('1 COUP'), 430, True), (542, 561, kc('2 COUPS'), 430, True),
                 (562, 568, kc('3 COUPS'), 430, True), (562, 568, react, 540, False)],
           hits=[(521, 'punch', 0.6), (542, 'punch', 0.6), (562, 'punch', 0.6)]),
      Replay(1, 536, 547, 26, (0, 500), 1.35),
      Play(1, 596, 625),
      Freeze(1, 626, 64, J1)]
sfx(g1[2].t0 + (541.5 - 536) / 11 * 26 / FPS, 'ding_big', 0.55)
group(4, g1)
w5 = Whip(9, full=True)
outro = Outro(78)

order = [s for s in segs]
for idx, s in enumerate(order):
    if isinstance(s, Whip):
        s.link(order[idx - 1], order[idx + 1])

NF = TT[0]
DUR = NF / FPS
print(f'{NF} frames, {DUR:.2f}s', flush=True)


# ---------------------------------------------------------------- audio
SR = 44100
rng = np.random.default_rng(7)


def load_src():
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', D + '/src.mp4', '-vn', '-f', 'f32le',
                          '-ac', '2', '-ar', str(SR), '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


SRCA = load_src()


def tv(d):
    return np.arange(int(d * SR)) / SR


def norm(x, peak=1.0):
    return x / (np.abs(x).max() + 1e-9) * peak


def bpf(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype='band', fs=SR, output='sos'), x)


def lpf(x, fc, order=2):
    return sosfilt(butter(order, fc, btype='low', fs=SR, output='sos'), x)


def hpf(x, fc, order=2):
    return sosfilt(butter(order, fc, btype='high', fs=SR, output='sos'), x)


def var_lp(x, fcs):
    y = np.empty_like(x)
    s1 = s2 = 0.0
    a = np.exp(-2 * np.pi * fcs / SR)
    for i in range(len(x)):
        s1 = a[i] * s1 + (1 - a[i]) * x[i]
        s2 = a[i] * s2 + (1 - a[i]) * s1
        y[i] = s2
    return y


def s_whoosh(d=0.42, lo=350, hi=3200):
    t = tv(d)
    u = t / d
    fc = lo * (hi / lo) ** np.sin(np.pi * np.clip(u * 1.1, 0, 1)) ** 1.5
    x = var_lp(rng.standard_normal(len(t)), fc)
    x = hpf(x, 150)
    env = np.sin(np.pi * u) ** 2 * (0.4 + 0.6 * u)
    return norm(x * env)


def s_impact(d=0.55, f0=150, f1=40):
    t = tv(d)
    f = f1 + (f0 - f1) * np.exp(-t / 0.05)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17)
    click = lpf(rng.standard_normal(len(t)), 3500) * np.exp(-t / 0.012)
    return norm(np.tanh(2.0 * (body + 0.5 * norm(click))))


def s_boom():
    t = tv(1.3)
    f = 48 + 60 * np.exp(-t / 0.08)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * np.exp(-t / 0.42)
    x += 0.25 * lpf(rng.standard_normal(len(t)), 900) * np.exp(-t / 0.25)
    return norm(np.tanh(2.2 * x))


def s_punch():
    t = tv(0.3)
    f = 55 + 170 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.08)
    x += 0.8 * bpf(rng.standard_normal(len(t)), 800, 6000) * np.exp(-t / 0.015)
    return norm(np.tanh(2.5 * x))


def s_pop():
    t = tv(0.14)
    f = 380 + 900 * (1 - np.exp(-t / 0.02))
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * (1 - np.exp(-t / 0.002)))


def s_click():
    t = tv(0.06)
    x = hpf(rng.standard_normal(len(t)), 2000) * np.exp(-t / 0.003) + 0.5 * np.sin(2 * np.pi * 2800 * t) * np.exp(-t / 0.008)
    return norm(x)


def partials(d, fs, amps, taus, att=0.002):
    t = tv(d)
    x = sum(a * np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t / ta) for f, a, ta in zip(fs, amps, taus))
    return norm(x * (1 - np.exp(-t / att)))


def s_ding():
    return partials(1.6, [1568, 3136, 4704, 2350], [1, .35, .12, .2], [0.9, .5, .25, .4])


def s_ding_big():
    t = tv(2.2)
    base = 880
    x = partials(2.2, [base, base * 2.76, base * 5.40, base * 8.93, base * 1.5],
                 [1, .6, .35, .2, .25], [1.4, .8, .45, .25, .6])
    x = x + 0.3 * norm(hpf(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.01))
    return norm(x)


def s_clang():
    t = tv(1.6)
    base = 262
    x = partials(1.6, [base, base * 2.76, base * 5.40, base * 8.93, base * 13.3],
                 [1, .7, .45, .25, .12], [0.9, .6, .35, .2, .12])
    wob = 1 + 0.25 * np.sin(2 * np.pi * 7 * t) * np.exp(-t / 0.5)
    x = x * wob + 0.5 * norm(bpf(rng.standard_normal(len(t)), 1500, 8000) * np.exp(-t / 0.02))
    return norm(np.tanh(1.5 * x))


def s_scratch():
    seg = SRCA[int(1.0 * SR):int(1.6 * SR)].mean(1)
    d = 0.42
    t = tv(d)
    v = np.where(t < 0.1, 3.0, np.where(t < 0.24, -3.4, np.where(t < 0.34, 2.2, 0.0)))
    pos = np.cumsum(v) / SR * SR
    pos = np.clip(pos + 0.15 * SR, 0, len(seg) - 1)
    x = np.interp(pos, np.arange(len(seg)), seg)
    x = bpf(x, 250, 6000) + 0.08 * bpf(rng.standard_normal(len(t)), 1000, 5000) * np.abs(v) / 3
    env = np.clip(t / 0.01, 0, 1) * np.clip((d - t) / 0.05, 0, 1)
    return norm(x * env)


def s_slide():
    t = tv(0.75)
    u = t / 0.75
    f = 1900 * (320 / 1900) ** (u ** 0.8) * (1 + 0.03 * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.15 * np.sin(2 * ph)
    x += 0.05 * bpf(rng.standard_normal(len(t)), 1000, 4000)
    env = np.clip(t / 0.03, 0, 1) * np.clip((0.75 - t) / 0.08, 0, 1)
    return norm(x * env)


def s_trombone():
    notes = [(233.08, 0.34), (220.0, 0.34), (207.65, 0.34), (196.0, 1.1)]
    out = []
    for idx, (f0, d) in enumerate(notes):
        t = tv(d)
        u = t / d
        vib = 1 + (0.025 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.2) / 0.2, 0, 1) if idx == 3 else 0)
        ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
        bright = np.sin(np.pi * np.clip(u * 1.3, 0, 1)) if idx < 3 else np.clip(t / 0.15, 0, 1) * (1 - 0.5 * u)
        x = sum((1 / k) * np.exp(-(k - 1) / (0.6 + 5 * bright)) * np.sin(k * ph) for k in range(1, 14))
        env = np.clip(t / 0.02, 0, 1) * np.clip((d - t) / 0.05, 0, 1)
        out.append(x * env)
    return norm(np.tanh(1.3 * norm(np.concatenate(out))))


def s_rewind():
    a = SRCA[int(536 / FPS * SR):int(569 / FPS * SR)].mean(1)[::-1]
    n = int(0.34 * SR)
    x = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    t = tv(0.34)
    x = bpf(x, 400, 7000) * (1 + 0.5 * np.sin(2 * np.pi * 18 * t))
    return norm(x * np.clip((0.34 - t) / 0.04, 0, 1))


def s_jingle():
    out = np.zeros(int(1.2 * SR))
    for k, (f, st) in enumerate([(523.25, 0), (659.25, .08), (783.99, .16), (1046.5, .24)]):
        t = tv(1.2 - st)
        x = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t))
        x *= np.exp(-t / (0.25 if k < 3 else 0.6)) * (1 - np.exp(-t / 0.003))
        i0 = int(st * SR)
        m = min(len(x), len(out) - i0)
        out[i0:i0 + m] += x[:m]
    return norm(out)


SFX = dict(whoosh=s_whoosh(), whoosh_s=s_whoosh(0.3, 600, 4000), impact=s_impact(), boom=s_boom(),
           punch=s_punch(), pop=s_pop(), click=s_click(), ding=s_ding(), ding_big=s_ding_big(),
           clang=s_clang(), scratch=s_scratch(), slide=s_slide(), trombone=s_trombone(),
           rewind=s_rewind(), jingle=s_jingle())


def build_audio(path):
    n = int(DUR * SR) + SR
    out = np.zeros((n, 2), np.float32)
    for t_out, s0, s1, g, speed in SRC:
        a = SRCA[int(s0 * SR):int(s1 * SR)]
        if speed != 1.0:
            m = int(len(a) / speed)
            idx = np.linspace(0, len(a) - 1, m)
            a = np.stack([np.interp(idx, np.arange(len(a)), a[:, c]) for c in range(2)], 1)
        a = a.copy()
        f = min(int(0.006 * SR), len(a) // 2)
        ramp = np.linspace(0, 1, f)[:, None]
        a[:f] *= ramp
        a[-f:] *= ramp[::-1]
        i0 = int(t_out * SR)
        out[i0:i0 + len(a)] += a[:n - i0] * g * 0.85
    for t, name, g in AUD:
        x = SFX[name]
        i0 = max(0, int(t * SR))
        m = min(len(x), n - i0)
        out[i0:i0 + m] += (x[:m] * g * 0.7)[:, None]
    out = out[:int(DUR * SR)]
    out = np.tanh(out * 1.1) / np.tanh(1.1)
    raw = (np.clip(out, -1, 1) * 32767).astype('<i2')
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(raw.tobytes())


# ---------------------------------------------------------------- render
def frame_at(fi):
    for s in segs:
        if s.start <= fi < s.start + s.n:
            return s.render(fi - s.start)


if __name__ == '__main__':
    if PREVIEW:
        os.makedirs(D + '/prev', exist_ok=True)
        for a in sys.argv[2:]:
            fi = int(float(a) * FPS)
            frame_at(fi).save(f'{D}/prev/p_{a}.png')
        sys.exit()
    build_audio(D + '/mix_v2.wav')
    print('audio ok', flush=True)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                          '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', D + '/mix_v2.wav',
                          '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
                          '-profile:v', 'high', '-movflags', '+faststart',
                          '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                          '-shortest', D + '/out_v2.mp4'], stdin=subprocess.PIPE)
    for fi in range(NF):
        p.stdin.write(frame_at(fi).tobytes())
        if fi % 60 == 0:
            print(f'{fi}/{NF}', flush=True)
    p.stdin.close()
    p.wait()
    print('done', flush=True)
