#!/usr/bin/env python3
"""MARBLE NATIONS - World Marble Race (TikTok 1080x1920, > 1 min).

  python3 marble.py sim PART SEED         # simulation seule : temps d'arrivée
  python3 marble.py search PART N          # cherche une graine avec une fin serrée
  python3 marble.py still PART SEED t...   # images fixes (debug)
  python3 marble.py render PART SEED       # vidéo -> race_PART.mp4
"""
import math, os, sys, json, random, functools, subprocess, wave
import numpy as np
import pymunk
from PIL import Image, ImageDraw, ImageFont, ImageFilter

D = os.path.dirname(os.path.abspath(__file__))
FPS, SUB = 30, 6
W, H = 1080, 1920
CW = 780                      # course width (world units = pixels)
CX0 = 160                     # course left edge on screen
VIEW_Y0 = 232                 # top of the course viewport on screen
MR = 22                       # marble radius
GATE_T = 1.3                  # gate opens (s)
LAVA_T0 = 3.0                 # lava starts rising (s)
CATCH_T = 28.0                # the lava closes the gap on the last marble around this time (s)
ANTON = D + '/assets/anton.ttf'
LUCK = D + '/assets/luckiest-guy.ttf'
EMO = D + '/assets/emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
YEL, RED, WHITE, BLACK, GREY = (255, 210, 31), (235, 60, 70), (255, 255, 255), (10, 12, 22), (160, 166, 184)
HANDLE = '@marblenations.tv'

COUNTRIES = [
    ('US', 'USA'), ('CA', 'CANADA'), ('MX', 'MEXICO'), ('BR', 'BRAZIL'), ('AR', 'ARGENTINA'), ('CO', 'COLOMBIA'),
    ('PE', 'PERU'), ('CL', 'CHILE'), ('GB', 'UK'), ('IE', 'IRELAND'), ('FR', 'FRANCE'), ('DE', 'GERMANY'),
    ('IT', 'ITALY'), ('ES', 'SPAIN'), ('PT', 'PORTUGAL'), ('NL', 'NETHERLANDS'), ('BE', 'BELGIUM'), ('PL', 'POLAND'),
    ('SE', 'SWEDEN'), ('GR', 'GREECE'), ('RO', 'ROMANIA'), ('TR', 'TURKEY'), ('MA', 'MOROCCO'), ('DZ', 'ALGERIA'),
    ('TN', 'TUNISIA'), ('EG', 'EGYPT'), ('NG', 'NIGERIA'), ('ZA', 'SOUTH AFRICA'), ('SA', 'SAUDI ARABIA'),
    ('AE', 'UAE'), ('PK', 'PAKISTAN'), ('IN', 'INDIA'), ('BD', 'BANGLADESH'), ('ID', 'INDONESIA'),
    ('PH', 'PHILIPPINES'), ('VN', 'VIETNAM'), ('TH', 'THAILAND'), ('JP', 'JAPAN'), ('KR', 'SOUTH KOREA'),
    ('AU', 'AUSTRALIA'),
]


STATE = D + '/marble_state.json'


def roster(part):
    """Countries still in the tournament at the start of this part."""
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    out = {st[str(p)] for p in range(1, part) if str(p) in st}
    return [c for c in COUNTRIES if c[1] not in out]


def clamp01(t):
    return max(0.0, min(1.0, t))


def flag_cp(iso):
    return '-'.join('%x' % (0x1F1E6 + ord(c) - 65) for c in iso)


# ======================================================================= course
class Course:
    """Static geometry + moving parts. Everything also recorded for drawing."""

    def __init__(s, space, seed):
        s.sp = space
        s.rng = random.Random(seed * 7 + 1)
        s.segs, s.pegs, s.bumpers, s.spinners, s.labels = [], [], [], [], []
        s.gate = None
        y = s.build()
        s.finish_y = y
        s.height = y + 420

    def seg(s, a, b, r=6, e=0.35, f=0.7, kind='wall'):
        sh = pymunk.Segment(s.sp.static_body, a, b, r)
        sh.elasticity, sh.friction = e, f
        s.sp.add(sh)
        s.segs.append((a, b, r, kind))
        return sh

    def peg(s, x, y, r=9):
        sh = pymunk.Circle(s.sp.static_body, r, (x, y))
        sh.elasticity, sh.friction = 0.5, 0.4
        s.sp.add(sh)
        s.pegs.append((x, y, r))

    def bumper(s, x, y, r=30):
        sh = pymunk.Circle(s.sp.static_body, r, (x, y))
        sh.elasticity, sh.friction = 1.15, 0.2
        sh.collision_type = 2
        s.sp.add(sh)
        s.bumpers.append((x, y, r))

    def spinner(s, x, y, L, w, arms=2):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position = (x, y)
        b.angular_velocity = w
        s.sp.add(b)
        for k in range(arms):
            a = math.pi * k / arms
            p = (math.cos(a) * L / 2, math.sin(a) * L / 2)
            sh = pymunk.Segment(b, (-p[0], -p[1]), p, 7)
            sh.elasticity, sh.friction = 0.6, 0.6
            s.sp.add(sh)
        s.spinners.append((b, L, arms))

    def zigzag(s, y, n, gap=140, drop=70, step=170, bumps=False):
        for k in range(n):
            left = k % 2 == 0
            if left:     # ramp from left wall down to the right, gap on the right
                a, b = (0, y), (CW - gap, y + drop)
            else:
                a, b = (CW, y), (gap, y + drop)
            s.seg(a, b, 7, kind='ramp')
            y += step
        return y + 40

    def pegfield(s, y, rows, dy=68, dx=80, r=9):
        for j in range(rows):
            off = dx / 2 if j % 2 else 0
            x = 70 + off
            while x < CW - 60:
                s.peg(x + s.rng.uniform(-4, 4), y, r)
                x += dx
            y += dy
        return y + 30

    def funnel(s, y, hole=112, depth=260):
        s.seg((0, y), (CW / 2 - hole / 2, y + depth), 7, kind='ramp')
        s.seg((CW, y), (CW / 2 + hole / 2, y + depth), 7, kind='ramp')
        return y + depth + 60

    def split(s, y, h=760, flip=False):
        """Centre divider: one fast lane (few pegs), one bumper lane."""
        fx = (lambda x: CW - x) if flip else (lambda x: x)
        s.seg((CW / 2, y + 40), (CW / 2, y + h), 9, kind='ramp')
        s.peg(CW / 2, y + 30, 16)
        for k in range(3):
            s.peg(fx(95 + (120 if k % 2 else 0)), y + 180 + k * 200, 10)
        for k in range(4):
            s.bumper(fx(CW / 2 + 95 + (150 if k % 2 else 0)), y + 150 + k * 165, 30)
        return y + h + 40

    def build(s):
        s.labels.append((40, 'START'))
        s.gate = s.seg((0, 300), (CW, 300), 6, kind='gate')
        y = 330
        y = s.pegfield(y + 30, 6, dy=80, dx=125, r=9)
        s.labels.append((y - 10, 'WINDMILLS'))
        y += 90
        for k in range(2):
            # left wheel turns clockwise, right one anticlockwise: both sweep marbles down the middle
            s.spinner(215, y + 120, 250, 2.4, arms=2)
            s.spinner(CW - 215, y + 120, 250, -2.4, arms=2)
            y += 280
        s.labels.append((y, 'THE SPLIT'))
        y = s.split(y + 60)
        s.labels.append((y, 'THE CRUSHER'))
        y = s.funnel(y + 40, hole=150, depth=240)
        s.spinner(CW / 2, y + 70, 230, 3.2, arms=2)
        y += 230
        s.labels.append((y, 'PINBALL'))
        y += 70
        for j in range(4):
            for i in range(4):
                x = 110 + i * 190 + (95 if j % 2 else 0)
                if x < CW - 60:
                    s.bumper(x, y, 28)
            y += 145
        s.labels.append((y, 'MEGA WHEEL'))
        y += 380
        s.spinner(CW / 2, y, 600, 1.3, arms=3)
        y += 380
        s.labels.append((y, 'TWIN WHEELS'))
        y += 250
        s.spinner(200, y, 330, -1.8, arms=3)
        s.spinner(CW - 200, y, 330, 1.8, arms=3)
        y += 250
        s.labels.append((y, 'SPIN CITY'))
        y += 60
        for j in range(2):
            for i in range(3):
                x = 140 + i * 250
                s.spinner(x, y + 110, 150, (2.8 if (i + j) % 2 else -2.8), arms=2)
            y += 240
        s.labels.append((y, 'THE SPLIT 2'))
        y = s.split(y + 60, flip=True)
        s.labels.append((y, 'DOUBLE CRUSHER'))
        y = s.funnel(y + 40, hole=150, depth=240)
        s.spinner(CW / 2, y + 70, 230, -3.2, arms=2)
        y += 230
        y = s.funnel(y, hole=150, depth=200)
        s.spinner(CW / 2, y + 70, 230, 3.2, arms=2)
        y += 230
        s.labels.append((y, 'BUMPER STORM'))
        y += 70
        for j in range(5):
            for i in range(4):
                x = 110 + i * 190 + (95 if j % 2 else 0)
                if x < CW - 60:
                    s.bumper(x, y, 26)
            y += 140
        s.labels.append((y, 'PLINKO'))
        y = s.pegfield(y + 40, 8, dy=72, dx=100)
        s.labels.append((y, 'MEGA WHEEL 2'))
        y += 380
        s.spinner(CW / 2, y, 600, -1.4, arms=3)
        y += 380
        s.labels.append((y, 'FINAL SPRINT'))
        y = s.pegfield(y + 30, 5, dy=85, dx=120, r=8)
        y += 200
        return y

    def walls(s):
        s.seg((0, -200), (0, s.height), 8)
        s.seg((CW, -200), (CW, s.height), 8)
        s.seg((0, s.height - 10), (CW, s.height - 10), 8)


# ======================================================================= simulation
class Race:
    def __init__(s, seed, cs=None):
        s.seed = seed
        s.sp = pymunk.Space()
        s.sp.gravity = (0, 1250)
        s.sp.damping = 0.985
        s.course = Course(s.sp, seed)
        s.course.walls()
        rng = random.Random(seed)
        random.seed(seed)             # anti-jam nudges must replay identically in headless and render
        cs = cs or COUNTRIES
        order = list(range(len(cs)))
        rng.shuffle(order)
        s.m = []
        cols = 10
        for slot, ci in enumerate(order):
            r, c = divmod(slot, cols)
            x = 50 + c * ((CW - 100) / (cols - 1)) + rng.uniform(-2, 2)
            yv = 70 + r * 52 + rng.uniform(-2, 2)
            b = pymunk.Body(1, pymunk.moment_for_circle(1, 0, MR))
            b.position = (x, yv)
            sh = pymunk.Circle(b, MR)
            sh.elasticity, sh.friction = 0.45, 0.6
            sh.collision_type = 1
            s.sp.add(b, sh)
            b.velocity_func = s.limit_velocity
            s.m.append(dict(iso=cs[ci][0], name=cs[ci][1], body=b, fin=None, still=0.0))
        s.t = 0.0
        s.finish_order = []
        s.hits = []
        s.sp.on_collision(1, None, post_solve=s.on_hit)
        s.gate_open = False
        s.lava_y, s.lava_v = -160.0, 0.0
        s.caught = None

    @staticmethod
    def limit_velocity(body, gravity, damping, dt):
        pymunk.Body.update_velocity(body, gravity, damping, dt)
        v = body.velocity.length
        if v > 1350:
            body.velocity = body.velocity * (1350 / v)

    def on_hit(s, arb, space, data):
        imp = arb.total_impulse.length
        if imp > 60:
            s.hits.append((s.t, min(imp / 600, 1.0)))

    def step(s, dt):
        if not s.gate_open and s.t > GATE_T:
            s.sp.remove(s.course.gate) if hasattr(s.course, 'gate') else None
            s.gate_open = True
        s.sp.step(dt)
        s.t += dt
        s.lava_step(dt)
        for m in s.m:
            b = m['body']
            if m['fin'] is None and b.position.y > s.course.finish_y:
                m['fin'] = s.t
                s.finish_order.append(m)
            # anti-jam nudge
            if m['fin'] is None and s.gate_open:
                if b.velocity.length < 12:
                    m['still'] += dt
                    if m['still'] > 1.0:
                        dx = 1 if b.position.x < CW / 2 else -1
                        b.apply_impulse_at_local_point((dx * random.uniform(150, 320), -random.uniform(150, 300)))
                        m['still'] = 0
                else:
                    m['still'] = 0

    def last_alive(s):
        run = [m for m in s.m if m['fin'] is None]
        return min(run, key=lambda m: m['body'].position.y) if run else None

    def lava_step(s, dt):
        """The lava is rubber-banded to the last marble: the gap it allows shrinks to 0 at CATCH_T."""
        if s.t < LAVA_T0 or s.caught is not None:
            return
        last = s.last_alive()
        if last is None:
            return
        u = clamp01((s.t - LAVA_T0) / (CATCH_T - LAVA_T0))
        gap = 1000 * (1 - u) ** 1.3 - 60 * u
        want = min(1.6 * (last["body"].position.y - gap - s.lava_y), 260 + 600 * u ** 4)
        want = max(want, 25 + 60 * u)
        s.lava_v += (want - s.lava_v) * min(1, 2.5 * dt)
        s.lava_y += s.lava_v * dt
        for m in s.m:
            if m['fin'] is None and m['body'].position.y < s.lava_y:
                s.caught = m
                s.catch_t = s.t
                break

    def ranking(s):
        fin = list(s.finish_order)
        rest = sorted((m for m in s.m if m['fin'] is None), key=lambda m: -m['body'].position.y)
        return fin + rest

    def done(s):
        return s.caught is not None or len(s.finish_order) == len(s.m)


def headless(seed, tmax=150, cs=None):
    r = Race(seed, cs)
    dt = 1 / (FPS * SUB)
    while not r.done() and r.t < tmax:
        r.step(dt)
    f = [m['fin'] for m in r.finish_order]
    if r.caught is None or not f:
        return dict(seed=seed, ok=False, n=len(f), t=r.t)
    # how long the eventual victim spent in last place, and how close the second-to-last came
    return dict(seed=seed, ok=True, first=f[0], catch=r.catch_t, n_fin=len(f), winner=r.finish_order[0]['name'],
                loser=r.caught['name'])




# ======================================================================= graphics helpers
ISO3 = dict(US='USA', CA='CAN', MX='MEX', BR='BRA', AR='ARG', CO='COL', PE='PER', CL='CHL', GB='GBR', IE='IRL',
            FR='FRA', DE='GER', IT='ITA', ES='ESP', PT='POR', NL='NED', BE='BEL', PL='POL', SE='SWE', GR='GRE',
            RO='ROU', TR='TUR', MA='MAR', DZ='ALG', TN='TUN', EG='EGY', NG='NGA', ZA='RSA', SA='KSA', AE='UAE',
            PK='PAK', IN='IND', BD='BAN', ID='INA', PH='PHI', VN='VIE', TH='THA', JP='JPN', KR='KOR', AU='AUS')


@functools.lru_cache(None)
def font(p, s):
    return ImageFont.truetype(p, s)


_tmpd = ImageDraw.Draw(Image.new('RGBA', (1, 1)))


def clamp01(t):
    return min(max(t, 0.0), 1.0)


def ease_out(t):
    return 1 - (1 - clamp01(t)) ** 3


def back_out(t, s=2.0):
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def pop(t, dur=0.2, start=0.3):
    return 0 if t < 0 else start + (1 - start) * back_out(t / dur)


def T(s, c=WHITE):
    return ('t', s, c)


def E(cp):
    return ('e', cp, None)


@functools.lru_cache(None)
def emoji(cp, size):
    return Image.open(EMO + cp + '.png').convert('RGBA').resize((size, size), Image.LANCZOS)


@functools.lru_cache(None)
def rich(pieces, fp, size, stroke=0, shadow=0):
    f = font(fp, size)
    asc, desc = f.getmetrics()
    pad = stroke + 6
    widths = [(_tmpd.textlength(v, font=f) if k == 't' else int(size * 1.25)) for k, v, c in pieces]
    im = Image.new('RGBA', (int(sum(widths)) + 2 * pad + 2 * stroke, asc + desc + 2 * pad + shadow), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    base = pad + asc
    for layer in ((0, 1) if shadow else (1,)):
        x = pad + stroke
        for (k, v, c), w in zip(pieces, widths):
            if k == 't':
                if layer == 0:
                    d.text((x, base + shadow), v, font=f, fill=(0, 0, 0, 150), anchor='ls', stroke_width=stroke,
                           stroke_fill=(0, 0, 0, 150))
                else:
                    d.text((x, base), v, font=f, fill=c, anchor='ls', stroke_width=stroke, stroke_fill=(0, 0, 0))
            elif layer == 1:
                es = int(size * 1.08)
                im.alpha_composite(emoji(v, es), (int(x + size * 0.14), int(base - es * 0.86)))
            x += w
    return im


def place(cv, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0, maxw=1040):
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


@functools.lru_cache(None)
def flag_disc(iso, size):
    """Glossy marble with the country flag."""
    S = size * 4
    f = Image.open(EMO + flag_cp(iso) + '.png').convert('RGBA')
    f = f.crop(f.getbbox())
    w, h = f.size
    s = min(w, h)
    f = f.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((S, S), Image.LANCZOS)
    base = Image.new('RGBA', (S, S), (255, 255, 255, 255))
    base.alpha_composite(f)
    a = np.asarray(base).astype(np.float32)
    y, x = np.mgrid[0:S, 0:S]
    nx, ny = (x - S / 2) / (S / 2), (y - S / 2) / (S / 2)
    rr = np.clip(nx * nx + ny * ny, 0, 1)
    a[..., :3] *= (0.62 + 0.38 * np.clip(1 - ((nx + 0.35) ** 2 + (ny + 0.45) ** 2) / 1.7, 0, 1))[..., None]
    a[..., :3] *= (1 - 0.3 * rr ** 3)[..., None]
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).ellipse([0, 0, S - 1, S - 1], fill=255)
    im.putalpha(m)
    return im.resize((size, size), Image.LANCZOS)


@functools.lru_cache(None)
def gloss(size):
    S = size * 4
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], outline=(10, 12, 22, 255), width=max(2, S // 16))
    hl = Image.new('L', (S, S), 0)
    ImageDraw.Draw(hl).ellipse([S * 0.2, S * 0.12, S * 0.52, S * 0.36], fill=210)
    hl = hl.filter(ImageFilter.GaussianBlur(S * 0.04))
    im.paste((255, 255, 255, 255), (0, 0), hl)
    return im.resize((size, size), Image.LANCZOS)


# ======================================================================= renderer
BG1, BG2 = (22, 26, 58), (10, 12, 30)
SECTION_COL = [(80, 220, 255), (255, 170, 60), (180, 120, 255), (255, 90, 140), (120, 255, 160), (255, 220, 80)]


def draw_course(course):
    Hc = int(course.height + 200)
    a = np.linspace(0, 1, Hc)[:, None, None]
    col = (np.array(BG1) * (1 - a) + np.array(BG2) * a)
    arr = np.repeat(col, CW, axis=1).astype(np.float32)
    # faint diagonal grid
    yy, xx = np.mgrid[0:Hc, 0:CW]
    grid = (((xx + yy) % 60) < 2) | (((xx - yy) % 60) < 2)
    arr[grid] += 10
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    # section labels (big, faint)
    labs = sorted(course.labels)
    for k, (y, txt) in enumerate(labs):
        c = SECTION_COL[k % len(SECTION_COL)]
        t = font(ANTON, 96)
        d.text((CW / 2, y + 70), txt, font=t, fill=tuple(int(v * 0.35 + BG1[i] * 0.65) for i, v in enumerate(c)),
               anchor='mm')

    def section_color(y):
        k = 0
        for j, (ly, _) in enumerate(labs):
            if y >= ly - 30:
                k = j
        return SECTION_COL[k % len(SECTION_COL)]

    for a_, b_, r, kind in course.segs:
        if kind == 'gate':
            continue
        if kind == 'wall':
            continue
        c = section_color(min(a_[1], b_[1]))
        d.line([a_, b_], fill=tuple(v // 3 for v in c), width=int(2 * r + 10))
        d.line([a_, b_], fill=c, width=int(2 * r))
        d.line([a_, b_], fill=tuple(min(255, v + 90) for v in c), width=max(2, int(r * 0.5)))
        for p in (a_, b_):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=c)
    for x, y, r in course.pegs:
        d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=(40, 46, 90))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(235, 238, 255))
    for x, y, r in course.bumpers:
        d.ellipse([x - r - 5, y - r - 5, x + r + 5, y + r + 5], fill=(120, 30, 70))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 80, 150), outline=(255, 200, 225), width=4)
        d.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(255, 200, 225))
    # finish line
    fy = course.finish_y
    sq = 26
    for i in range(CW // sq + 1):
        for j in range(2):
            c = WHITE if (i + j) % 2 == 0 else (18, 18, 24)
            d.rectangle([i * sq, fy - sq + j * sq, i * sq + sq, fy + j * sq], fill=c)
    d.text((CW / 2, fy + 150), 'FINISH', font=font(ANTON, 110), fill=(60, 66, 110), anchor='mm')
    # side rails
    for x in (0, CW):
        d.line([(x, 0), (x, Hc)], fill=(90, 100, 170), width=16)
        d.line([(x, 0), (x, Hc)], fill=(170, 180, 255), width=4)
    return im


class Renderer:
    def __init__(s, part, seed):
        s.part, s.seed = part, seed
        cs = roster(part)
        s.info = headless(seed, cs=cs)
        assert s.info['ok']
        s.race = Race(seed, cs)
        s.n = len(s.race.m)
        s.bg = draw_course(s.race.course)
        s.cam = 0.0
        s.audio = []          # (t, name, gain)
        s.toasts = []         # (t, pieces, color)
        s.leader = None
        s.seen_labels = set()
        s.first_fin = None
        s.five_left = None
        s.chase = None
        s.last_close = -9
        s.gaps = []           # (t, gap between lava and the last marble) -> drives the rumble
        s.end_t = None
        s.header = s.make_header()
        s.catch_t = s.info['catch']

    def make_header(s):
        im = Image.new('RGBA', (W, VIEW_Y0), BLACK + (255,))
        a = np.linspace(0, 1, VIEW_Y0)[:, None, None]
        arr = (np.array((14, 16, 40)) * (1 - a) + np.array((26, 30, 70)) * a).astype(np.uint8)
        im = Image.fromarray(np.repeat(arr, W, axis=1)).convert('RGBA')
        t = rich((T('WORLD ', WHITE), T('MARBLE RACE ', YEL), E('1f3c1')), ANTON, 84, stroke=4)
        im.alpha_composite(t, ((W - t.width) // 2, 34))
        st = rich((T(f'PART {s.part}  •  {s.n} COUNTRIES  •  CAUGHT BY THE LAVA = ', (200, 205, 230)),
                   T('OUT', RED)), ANTON, 38, stroke=2)
        im.alpha_composite(st, ((W - st.width) // 2, 150))
        d = ImageDraw.Draw(im)
        d.rectangle([0, VIEW_Y0 - 5, W, VIEW_Y0], fill=YEL)
        return im.convert('RGB')

    # ------------------------------------------------------------ camera
    def camera_target(s, rank):
        fin = len(s.race.finish_order)
        left = [m for m in rank if m['fin'] is None]
        if not s.race.gate_open:
            return 60
        if s.chase is None:
            ys = sorted((m['body'].position.y for m in rank[:5]), reverse=True)
            return 0.6 * ys[0] + 0.4 * ys[2] - 560
        if not left:
            return s.cam
        # the chase: the last marble low in the frame, the lava visible above it
        ys = sorted(m['body'].position.y for m in left[-4:])
        return 0.7 * ys[0] + 0.3 * ys[-1] - 1050

    # ------------------------------------------------------------ events
    def toast(s, t, pieces, col=WHITE, dur=1.6):
        s.toasts.append((t, pieces, col, dur))

    def events(s, t, rank):
        L = rank[0]
        if s.race.gate_open and L['fin'] is None:
            if t > 7 and s.leader is not None and L is not s.leader and t - getattr(s, 'last_lead_toast', -9) > 4:
                s.toast(t, (T('NEW LEADER: ', YEL), E(flag_cp(L['iso'])), T(' ' + L['name'], WHITE)))
                s.audio.append((t, 'whoosh', 0.35))
                s.last_lead_toast = t
            s.leader = L
            for y, txt in s.race.course.labels:
                if txt not in s.seen_labels and txt != 'START' and L['body'].position.y > y:
                    s.seen_labels.add(txt)
                    if s.chase is None:
                        s.toast(t, (T(txt + '!', (140, 230, 255)),), dur=1.2)
        fin = s.race.finish_order
        if fin and s.first_fin is None:
            s.first_fin = t
            w = fin[0]
            s.toast(t, (E('1f3c6'), T(' ' + w['name'] + ' WINS!', YEL)), dur=2.2)
            s.audio.append((t, 'win', 0.5))
            s.audio.append((t + 0.1, ('say', f"{w['name'].title()} wins!"), 1.0))
        if s.first_fin is not None and s.chase is None and t > s.first_fin + 1.6:
            s.chase = t
            s.toast(t, (E('1f525'), T(' THE LAVA IS COMING ', (255, 150, 40)), E('1f525')), dur=2.0)
            s.audio.append((t, 'whoosh', 0.5))
            s.audio.append((t + 0.2, ('say', "Now, who gets burned?"), 1.0))
        left = [m for m in rank if m['fin'] is None]
        last = s.race.last_alive()
        if last is not None and s.race.caught is None:
            gap = last['body'].position.y - s.race.lava_y
            s.gaps.append((t, gap))
            if (s.chase is not None and gap < 70 and t - s.last_close > 3.5 and t < s.catch_t - 1.2):
                s.last_close = t
                s.toast(t, (T('CLOSE CALL ', (255, 150, 40)), E(flag_cp(last['iso'])), T('!', (255, 150, 40))), dur=1.2)
                s.audio.append((t, 'whoosh', 0.45))
        if s.chase is not None and len(left) <= 5 and s.five_left is None:
            s.five_left = t
            s.audio.append((t, 'riser', 0.35))
        if s.race.done() and s.end_t is None:
            s.end_t = t
            lo = s.race.caught
            s.audio.append((t, 'sizzle', 0.7))
            s.audio.append((t + 0.05, 'boom', 0.8))
            s.audio.append((t + 0.6, ('say', f"{lo['name'].title()} is burned. Eliminated!"), 1.0))
            s.audio.append((t + 1.6, 'sting', 0.45))

    # ------------------------------------------------------------ drawing
    def draw_board(s, cv, rank, t):
        d = ImageDraw.Draw(cv)
        x0, y0, rh = 6, VIEW_Y0 + 14, 30
        d.rounded_rectangle([x0 - 2, y0 - 8, 152, y0 + rh * s.n + 6], radius=12, fill=(8, 10, 26))
        f = font(ANTON, 22)
        for i, m in enumerate(rank):
            y = y0 + i * rh
            last = i == s.n - 1
            if last and s.race.gate_open:
                blink = 0.5 + 0.5 * math.sin(t * 8)
                d.rounded_rectangle([x0, y - 1, 150, y + rh - 3], radius=6, fill=(int(120 + 100 * blink), 20, 30))
            elif m['fin'] is not None:
                d.rounded_rectangle([x0, y - 1, 150, y + rh - 3], radius=6, fill=(20, 60, 40))
            elif i < 3:
                d.rounded_rectangle([x0, y - 1, 150, y + rh - 3], radius=6, fill=(60, 52, 14))
            d.text((x0 + 22, y + rh / 2 - 2), str(i + 1), font=f, fill=(200, 205, 230), anchor='mm')
            fl = flag_disc(m['iso'], 24)
            cv.paste(fl, (x0 + 38, int(y + 1)), fl)
            d.text((x0 + 68, y + rh / 2 - 2), ISO3[m['iso']], font=f, fill=WHITE, anchor='lm')

    def draw_marbles(s, cv, cam, t, rank):
        top = VIEW_Y0
        rk = {id(m): i for i, m in enumerate(rank)}
        tags = []
        for m in s.race.m:
            b = m['body']
            x, y = b.position.x + CX0, b.position.y - cam + top
            if y < top - 40 or y > H + 40:
                continue
            size = MR * 2 + 2
            im = flag_disc(m['iso'], size).rotate(-math.degrees(b.angle), Image.BILINEAR)
            cv.paste(im, (int(x - size / 2), int(y - size / 2)), im)
            g = gloss(size)
            cv.paste(g, (int(x - size / 2), int(y - size / 2)), g)
            i = rk[id(m)]
            if m['fin'] is None and (i < 3 or i == s.n - 1):
                tags.append((x, y, m, i))
        for x, y, m, i in tags:
            col = YEL if i == 0 else (RED if i == s.n - 1 else WHITE)
            lab = rich((T(('#1 ' if i == 0 else ('LAST ' if i == s.n - 1 else f'#{i + 1} ')) + m['name'], col),),
                       ANTON, 26, stroke=3)
            place(cv, lab, x, y - MR - 20)

    def render(s, t, cam):
        cv = Image.new('RGB', (W, H), BG2)
        # course
        y0 = int(cam)
        crop = s.bg.crop((0, y0, CW, y0 + H - VIEW_Y0))
        cv.paste(crop, (CX0, VIEW_Y0))
        d = ImageDraw.Draw(cv)
        # side panels
        d.rectangle([0, VIEW_Y0, CX0 - 8, H], fill=(12, 14, 34))
        d.rectangle([CX0 + CW + 8, VIEW_Y0, W, H], fill=(12, 14, 34))
        # gate
        if not s.race.gate_open:
            gy = 300 - cam + VIEW_Y0
            d.line([(CX0, gy), (CX0 + CW, gy)], fill=RED, width=12)
        # spinners
        for b, L, arms in s.race.course.spinners:
            x, y = b.position.x + CX0, b.position.y - cam + VIEW_Y0
            if -200 < y < H + 200:
                for k in range(arms):
                    a = b.angle + math.pi * k / arms
                    dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
                    d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(90, 60, 160), width=24)
                    d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(190, 140, 255), width=14)
                d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(250, 240, 255), outline=(90, 60, 160), width=4)
        rank = s.race.ranking()
        s.draw_marbles(cv, cam, t, rank)
        s.draw_lava(cv, cam, t)
        # keep the side panels clean of lava
        d.rectangle([0, VIEW_Y0, CX0 - 8, H], fill=(12, 14, 34))
        d.rectangle([CX0 + CW + 8, VIEW_Y0, W, H], fill=(12, 14, 34))
        cv.paste(s.header, (0, 0))
        s.draw_board(cv, rank, t)
        s.draw_minimap(cv, t)
        clock = rich((T(f'{max(0, t - GATE_T):04.1f}s', WHITE),), ANTON, 40, stroke=3)
        cv.paste(clock, (W - clock.width - 8, VIEW_Y0 + 10), clock)
        return cv, rank

    def draw_lava(s, cv, cam, t):
        ly = s.race.lava_y - cam + VIEW_Y0
        if ly < VIEW_Y0 - 40:
            return
        ov = Image.new('RGBA', (CW, int(min(H, ly + 60) - VIEW_Y0) + 1), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        base = ly - VIEW_Y0
        xs = np.arange(0, CW + 12, 12)
        surf = base + 9 * np.sin(xs * 0.028 + t * 4.0) + 5 * np.sin(xs * 0.071 - t * 6.3)
        # glow just below the surface
        for k, a in ((34, 40), (20, 70)):
            d.polygon([(0, -5)] + [(x, y + k) for x, y in zip(xs, surf)] + [(CW, -5)], fill=(255, 120, 20, a))
        d.polygon([(0, -5)] + list(zip(xs, surf)) + [(CW, -5)], fill=(190, 30, 10, 255))
        d.polygon([(0, -5)] + [(x, y - 70) for x, y in zip(xs, surf)] + [(CW, -5)], fill=(120, 14, 8, 255))
        d.line(list(zip(xs, surf)), fill=(255, 190, 40, 255), width=10)
        d.line(list(zip(xs, surf - 12)), fill=(255, 110, 20, 255), width=8)
        rng = random.Random(int(t * 10))
        for _ in range(7):
            x = rng.uniform(20, CW - 20)
            y = base - rng.uniform(10, 90)
            r = rng.uniform(4, 11)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 170, 40, 220))
        cv.paste(ov, (CX0, VIEW_Y0), ov)
        c = s.race.caught
        if c is not None:
            k = t - s.race.catch_t
            b = c['body']
            x, y = b.position.x + CX0, b.position.y - cam + VIEW_Y0 + 40 * clamp01(k / 0.8)
            size = int((MR * 2 + 2) * (1 + 0.5 * math.exp(-k * 3)))
            im = flag_disc(c['iso'], size)
            red = Image.new('RGBA', im.size, (255, 60, 10, 0))
            red.putalpha(im.getchannel('A').point(lambda v: int(v * 0.55 * clamp01(k / 0.5))))
            im.alpha_composite(red)
            cv.paste(im, (int(x - size / 2), int(y - size / 2)), im)
            place(cv, rich((E('1f525'),), ANTON, 70), x, y - 40 - 10 * math.sin(k * 9), pop(k, 0.15, 0.2))

    def draw_minimap(s, cv, t):
        x0, x1 = CX0 + CW + 30, W - 30
        y0, y1 = VIEW_Y0 + 150, H - 380
        d = ImageDraw.Draw(cv)
        d.rounded_rectangle([x0, y0 - 6, x1, y1 + 6], radius=14, fill=(26, 30, 64))
        sc = (y1 - y0) / s.race.course.finish_y
        ly = y0 + max(0, s.race.lava_y) * sc
        if s.race.lava_y > 0:
            d.rounded_rectangle([x0, y0 - 6, x1, ly], radius=14, fill=(210, 50, 15))
            d.line([(x0, ly), (x1, ly)], fill=(255, 200, 60), width=5)
        d.line([(x0, y1 + 1), (x1, y1 + 1)], fill=WHITE, width=4)
        cx = (x0 + x1) / 2
        for i, m in enumerate(s.race.m):
            y = y0 + min(max(m['body'].position.y, 0), s.race.course.finish_y) * sc
            fl = flag_disc(m['iso'], 18)
            cv.paste(fl, (int(cx - 9 + ((i % 5) - 2) * 8), int(y - 9)), fl)
        f = rich((E('1f525'),), ANTON, 40)
        cv.paste(f, (int(cx - f.width / 2), int(y0 - 60)), f)

    def overlays(s, cv, t):
        # intro hook
        if t < 2.6:
            a = 1 - clamp01((t - 2.25) / 0.35)
            l1 = rich((T('THE LAVA IS COMING', WHITE),), LUCK, 92, stroke=11, shadow=8)
            l2 = rich((T('WHO SURVIVES? ', (255, 150, 40)), E('1f525')), LUCK, 118, stroke=13, shadow=9)
            l3 = rich((T('COMMENT YOURS ', WHITE), E('1f447')), LUCK, 70, stroke=9, shadow=6)
            place(cv, l1, 540, 760, pop(t, 0.2), -3, a)
            place(cv, l2, 540, 890, pop(t - 0.12, 0.2), 3, a)
            place(cv, l3, 540, 1020, pop(t - 0.3, 0.2), -2, a)
        # toasts
        ty = 1180
        for t0, pieces, col, dur in s.toasts:
            k = t - t0
            if 0 <= k < dur:
                im = rich(pieces, LUCK, 64, stroke=9, shadow=6)
                place(cv, im, 555, ty, pop(k, 0.18), -2, 1 - clamp01((k - dur + 0.3) / 0.3), maxw=900)
                ty += 90
        # five left banner
        if s.five_left is not None and s.end_t is None:
            k = t - s.five_left
            im = rich((T('WHO GETS BURNED? ', (255, 150, 40)), E('1f525')), LUCK, 70, stroke=9, shadow=6)
            place(cv, im, 555, VIEW_Y0 + 90, pop(k, 0.2) * (1 + 0.03 * math.sin(t * 7)), -2, maxw=900)
        # end card
        if s.end_t is not None:
            k = t - s.end_t
            dim = Image.new('RGB', cv.size, (0, 0, 0))
            cv.paste(Image.blend(cv, dim, 0.62 * clamp01(k / 0.3)))
            lo = s.race.caught
            if k > 0.15:
                place(cv, rich((T('ELIMINATED', RED),), ANTON, 170, stroke=10, shadow=10), 540, 560,
                      2.4 - 1.4 * ease_out((k - 0.15) / 0.15), -6)
            if k > 0.45:
                place(cv, flag_disc(lo['iso'], 300), 540, 850, pop(k - 0.45, 0.25, 0.2), 8 * math.sin(k * 3))
                place(cv, gloss(300), 540, 850, pop(k - 0.45, 0.25, 0.2))
                x = rich((E('1f525'),), LUCK, 150)
                place(cv, x, 660, 760, pop(k - 0.7, 0.2, 0.2))
            if k > 0.8:
                place(cv, rich((T(lo['name'], WHITE),), LUCK, 110, stroke=12, shadow=8), 540, 1080, pop(k - 0.8), -2)
            if k > 1.3:
                place(cv, rich((T(f'{s.n - 1} COUNTRIES LEFT', YEL),), ANTON, 76, stroke=5), 540, 1220, pop(k - 1.3))
            if k > 1.7:
                place(cv, rich((T('FOLLOW FOR PART ' + str(s.part + 1) + ' ', WHITE), E('1f440')), LUCK, 66, stroke=8,
                               shadow=6), 540, 1340, pop(k - 1.7), -2)
            if k > 2.1:
                w = s.race.finish_order[0]
                place(cv, rich((T('WINNER: ', GREY), E(flag_cp(w['iso'])), T(' ' + w['name'], YEL)), ANTON, 50,
                               stroke=4), 540, 1450, pop(k - 2.1))
        # handle watermark
        hm = rich((T(HANDLE, (150, 156, 190)),), ANTON, 30, stroke=2)
        cv.paste(hm, (W - hm.width - 10, H - 330), hm)

    def frames(s, END=5.2):
        dt = 1 / (FPS * SUB)
        t = 0.0
        s.cam = 0.0
        nhit = 0
        while True:
            if s.end_t is None:
                for _ in range(SUB):
                    s.race.step(dt)
            rank = s.race.ranking()
            s.events(t, rank)
            tgt = max(0, min(s.camera_target(rank), s.race.course.height - (H - VIEW_Y0) + 60))
            s.cam += (tgt - s.cam) * 0.16
            cv, rank = s.render(t, s.cam)
            s.overlays(cv, t)
            yield cv
            t += 1 / FPS
            if s.end_t is not None and t - s.end_t > END:
                break
        s.duration = t


# ======================================================================= audio
SR = 44100
arng = np.random.default_rng(5)


def tv(d):
    return np.arange(int(d * SR)) / SR


def norm(x):
    return x / (np.abs(x).max() + 1e-9)


def lpf(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, fc, btype='low', fs=SR, output='sos'), x)


def bpf(x, lo, hi):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)


def s_click(f=2600):
    t = tv(0.05)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.006) + 0.5 * np.sin(2 * np.pi * f * 1.7 * t) * np.exp(-t / 0.004)
    return norm(x + 0.3 * bpf(arng.standard_normal(len(t)), 3000, 9000) * np.exp(-t / 0.003))


def s_whoosh(d=0.35):
    t = tv(d)
    return norm(bpf(arng.standard_normal(len(t)), 800, 5000) * np.sin(np.pi * t / d) ** 2)


def s_riser(d=0.9):
    t = tv(d)
    f = 300 * (4 ** (t / d))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + bpf(arng.standard_normal(len(t)), 1500, 7000) * 0.6
    return norm(x * (t / d) ** 1.5 * np.clip((d - t) / 0.03, 0, 1))


def s_boom():
    t = tv(1.4)
    f = 45 + 70 * np.exp(-t / 0.08)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * np.exp(-t / 0.45) + 0.3 * lpf(arng.standard_normal(len(t)), 900) * np.exp(-t / 0.25)
    return norm(np.tanh(2.2 * x))


def arp(notes, step, dur=0.35):
    out = np.zeros(int((len(notes) * step + dur + 0.1) * SR))
    for k, f in enumerate(notes):
        t = tv(dur)
        x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.12) * (1 - np.exp(-t / 0.002))
        i = int(k * step * SR)
        out[i:i + len(x)] += x
    return norm(out)


def s_sizzle():
    t = tv(1.2)
    x = bpf(arng.standard_normal(len(t)), 2500, 11000) * (1 - np.exp(-t / 0.01)) * np.exp(-t / 0.4)
    crackle = (arng.random(len(t)) > 0.9985) * arng.standard_normal(len(t)) * 4
    return norm(x + bpf(crackle, 1500, 9000) * np.exp(-t / 0.6))


def rumble(r, n):
    """Low lava rumble that swells as the lava closes in on the last marble."""
    env = np.zeros(n)
    if r.gaps:
        ts = np.array([g[0] for g in r.gaps])
        gs = np.array([g[1] for g in r.gaps])
        lvl = np.clip(1 - gs / 900, 0, 1) ** 1.5
        env = np.interp(np.arange(n) / SR, ts, lvl, left=0, right=0)
        if r.end_t is not None:
            i = int(r.end_t * SR)
            env[i:] = env[i - 1] * np.exp(-np.arange(n - i) / (0.7 * SR)) if i > 0 else 0
    noise = lpf(arng.standard_normal(n), 140) * 6
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 42 * t + 2 * np.sin(2 * np.pi * 0.7 * t)) * 0.5
    return norm(noise + tone) * env


def s_win():
    return arp([523.25, 659.25, 783.99, 1046.5, 1318.5, 1567.98], 0.07, 0.6)


def s_sting():
    return arp([392.0, 369.99, 349.23, 293.66], 0.18, 0.7)


def music(dur, bpm=138):
    """Original upbeat loop: kick, clap, hats, bass, plucked chords. Intensity rises over time."""
    spb = 60 / bpm
    n = int(dur * SR)
    out = np.zeros(n)
    kt = tv(0.3)
    kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt / 0.03)) / SR) * np.exp(-kt / 0.14)
    ht = tv(0.06)
    hat = bpf(arng.standard_normal(len(ht)), 7000, 14000) * np.exp(-ht / 0.015)
    ct = tv(0.2)
    clap = bpf(arng.standard_normal(len(ct)), 1000, 5000) * np.exp(-ct / 0.05)
    prog = [(110.0, [220.0, 261.63, 329.63]), (87.31, [174.61, 220.0, 261.63]), (130.81, [261.63, 329.63, 392.0]),
            (98.0, [196.0, 246.94, 293.66])]

    def add(x, i, g):
        m = min(len(x), n - i)
        if m > 0 and i >= 0:
            out[i:i + m] += x[:m] * g

    k = 0
    t = 0.0
    while t < dur:
        i = int(t * SR)
        inten = 0.6 + 0.4 * (t / dur)
        add(kick, i, 0.9)
        if k % 2 == 1:
            add(clap, i, 0.35)
        add(hat, int((t + spb / 2) * SR), 0.22 * inten)
        if inten > 0.8:
            add(hat, int((t + spb / 4) * SR), 0.12)
            add(hat, int((t + 3 * spb / 4) * SR), 0.12)
        bass_f, chord = prog[(k // 8) % 4]
        bt = tv(spb * 0.9)
        add(np.tanh(2.5 * np.sin(2 * np.pi * bass_f * bt)) * np.exp(-bt / 0.3), i, 0.35)
        if k % 2 == 0:
            ct2 = tv(spb * 1.6)
            ch = sum(np.sin(2 * np.pi * f * 2 * ct2) + 0.3 * np.sin(4 * np.pi * f * 2 * ct2) for f in chord)
            add(ch * np.exp(-ct2 / 0.25) * 0.18, i, inten)
        t += spb
        k += 1
    return lpf(out, 11000)


_tts = None


def say(text):
    global _tts
    import sherpa_onnx
    if _tts is None:
        M = D + '/tts/package/kokoro-int8-en-v0_19/'
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(model=M + 'model.int8.onnx', voices=M + 'voices.bin',
                                                           tokens=M + 'tokens.txt', data_dir=M + 'espeak-ng-data'),
            num_threads=4))
        _tts = sherpa_onnx.OfflineTts(cfg)
    a = _tts.generate(text, sid=VOICE, speed=1.08)
    x = np.array(a.samples, dtype=np.float64)
    idx = np.linspace(0, len(x) - 1, int(len(x) * SR / a.sample_rate))
    return norm(np.interp(idx, np.arange(len(x)), x)) * 0.95


VOICE = int(os.environ.get('VOICE', 6))


def build_audio(r, path, intro_line):
    n = int((r.duration + 0.5) * SR)
    mus = music(r.duration + 0.5)
    end = r.end_t
    fade = np.ones(n)
    i_end = int(end * SR)
    fade[i_end:] = np.linspace(1, 0.25, n - i_end)
    out = mus[:n] * 0.32 * fade
    SFX = dict(whoosh=s_whoosh(), riser=s_riser(), boom=s_boom(), win=s_win(), sting=s_sting(), sizzle=s_sizzle())
    voice = [(0.15, ('say', intro_line), 1.0)]
    duck = np.ones(n)
    fx = rumble(r, n) * 0.35
    for t, name, g in voice + r.audio:
        i = int(t * SR)
        if isinstance(name, tuple):
            x = say(name[1])
            m = min(len(x), n - i)
            if m > 0:
                fx[i:i + m] += x[:m] * 0.9 * g
                duck[i:i + m] = np.minimum(duck[i:i + m], 0.5)
            continue
        x = SFX[name]
        m = min(len(x), n - i)
        if m > 0:
            fx[i:i + m] += x[:m] * g
    # smooth the ducking so the music dips under the voice without clicks
    k = int(0.08 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode='same')
    out = out * duck + fx
    out = np.tanh(out * 1.1)
    raw = (np.clip(np.stack([out, out], 1), -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(raw.tobytes())


# ======================================================================= CLI
if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'sim':
        print(headless(int(sys.argv[3])))
    elif cmd == 'still':
        part, seed = int(sys.argv[2]), int(sys.argv[3])
        r = Renderer(part, seed)
        want = sorted(float(x) for x in sys.argv[4:])
        os.makedirs(D + '/prev', exist_ok=True)
        for i, fr in enumerate(r.frames()):
            t = i / FPS
            for w_ in want:
                if abs(t - w_) < 0.5 / FPS:
                    fr.save(f'{D}/prev/m_{part}_{w_}.png')
            if t > want[-1]:
                break
    elif cmd == 'render':
        part, seed = int(sys.argv[2]), int(sys.argv[3])
        r = Renderer(part, seed)
        tmpv = f'{D}/_race_{part}.mp4'
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                              f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf',
                              '19', '-pix_fmt', 'yuv420p', tmpv], stdin=subprocess.PIPE)
        for i, fr in enumerate(r.frames()):
            p.stdin.write(fr.tobytes())
            if i % 300 == 0:
                print(part, i, flush=True)
        p.stdin.close()
        p.wait()
        intro = f"{r.n} countries. The lava is coming. If it gets you, you're out!"
        build_audio(r, f'{D}/_race_{part}.wav', intro)
        out = f'{D}/race_{part}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tmpv, '-i', f'{D}/_race_{part}.wav', '-c:v', 'copy',
                        '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                        '-shortest', '-movflags', '+faststart', out], check=True)
        st = json.load(open(STATE)) if os.path.exists(STATE) else {}
        st[str(part)] = r.race.caught['name']
        json.dump(st, open(STATE, 'w'), indent=1)
        print('done', out, round(r.duration, 1), r.info, flush=True)
