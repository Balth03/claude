#!/usr/bin/env python3
"""TATAMI TRAGIQUE - combats de boules armées (Shorts 1080x1920).

  python3 fight.py search E1        # cherche les graines qui donnent un combat serré
  python3 fight.py render E1 SEED   # rend la vidéo  -> fight_E1.mp4
  python3 fight.py still E1 SEED t  # image fixe à t secondes (debug)
"""
import math, os, sys, random, functools, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import butter, sosfilt

D = os.path.dirname(os.path.abspath(__file__))
FPS, SUB = 30, 8
DT = 1 / (FPS * SUB)
W, H = 1080, 1920
AX, AY, AS = 70, 520, 940          # arène : x, y, côté
SS = 2                              # supersampling de l'arène
STEER = 4.0                         # rad/s : les boules se cherchent
ANTON = D + '/assets/anton.ttf'
LUCK = D + '/assets/luckiest-guy.ttf'
EMO = D + '/assets/emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
YEL, RED, WHITE, BLACK, GREY = (255, 210, 31), (230, 57, 70), (255, 255, 255), (12, 12, 14), (165, 165, 172)


# ======================================================================= episodes
def ep_E1():
    return dict(
        title=('KATANA', 'NUNCHAKU'), next='BÔ vs SHURIKENS',
        fighters=[
            dict(name='KATANA', team=0, color=(232, 62, 74), kind='katana', L=150, spin=190, dmg=2,
                 rule='dmg', inc=2, hp=100, r=80, speed=600),
            dict(name='NUNCHAKU', team=1, color=(45, 150, 255), kind='nunchaku', L=112, spin=230, dmg=5,
                 rule='spin', inc=60, hp=100, r=80, speed=600),
        ])


def ep_E2():
    return dict(
        title=('BÔ', 'SHURIKENS'), next='1 CEINTURE NOIRE vs 10 BLANCHES',
        fighters=[
            dict(name='BÔ', team=0, color=(226, 142, 60), kind='bo', L=135, spin=150, dmg=7,
                 rule='len', inc=10, hp=100, r=76, speed=560),
            dict(name='SHURIKENS', team=1, color=(165, 95, 235), kind='shuriken', L=0, spin=0, dmg=1,
                 rule='star', inc=1, hp=100, r=76, speed=600, period=1.8),
        ])


def ep_E3():
    f = [dict(name='CEINTURE NOIRE', team=0, color=(30, 30, 34), kind='katana', L=150, spin=110, dmg=4,
              rule='none', hp=100, r=84, speed=380, outline=YEL)]
    for k in range(10):
        f.append(dict(name='BLANCHE', team=1, color=(245, 245, 245), kind='none', L=0, spin=0, dmg=1,
                      rule='none', hp=16, r=44, speed=430))
    return dict(title=('1 NOIRE', '10 BLANCHES'), next='LE GRAND TOURNOI', fighters=f, team_names=(
        'CEINTURE NOIRE', 'CEINTURES BLANCHES'))


def ep_E4():
    return dict(
        title=('KATANA', 'BÔ'), next='NUNCHAKU vs SHURIKENS',
        fighters=[
            dict(name='KATANA', team=0, color=(232, 62, 74), kind='katana', L=150, spin=190, dmg=2,
                 rule='dmg', inc=2, hp=100, r=80, speed=600),
            dict(name='BÔ', team=1, color=(226, 142, 60), kind='bo', L=135, spin=150, dmg=7,
                 rule='len', inc=10, hp=100, r=76, speed=560),
        ])


EPISODES = dict(E1=ep_E1, E2=ep_E2, E3=ep_E3, E4=ep_E4)


# ======================================================================= physics
def seg_pt(ax, ay, bx, by, px, py):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), cx, cy


def seg_seg(a, b, c, d):
    return min(seg_pt(*a, *b, *c)[0], seg_pt(*a, *b, *d)[0], seg_pt(*c, *d, *a)[0], seg_pt(*c, *d, *b)[0])


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def seg_cross(a, b, c, d):
    return _ccw(a, c, d) != _ccw(b, c, d) and _ccw(a, b, c) != _ccw(a, b, d)


class Fighter:
    def __init__(s, idx, cfg, x, y, ang, rng):
        s.i = idx
        s.__dict__.update(cfg)
        s.x, s.y = x, y
        a = rng.uniform(0, 2 * math.pi)
        s.vx, s.vy = math.cos(a) * s.speed, math.sin(a) * s.speed
        s.ang = ang
        s.hpmax = s.hp
        s.hits = 0
        s.alive = True
        s.timer = cfg.get('period', 1) * 0.6

    def seg(s):
        c, si = math.cos(s.ang), math.sin(s.ang)
        if s.kind in ('katana', 'nunchaku'):
            return (s.x + c * s.r * 0.5, s.y + si * s.r * 0.5), (s.x + c * (s.r + s.L), s.y + si * (s.r + s.L))
        if s.kind == 'bo':
            return (s.x - c * s.L, s.y - si * s.L), (s.x + c * s.L, s.y + si * s.L)
        return None

    def stat(s):
        if s.rule == 'dmg':
            return f'DÉGÂTS : {s.dmg}', f'+{s.inc} DÉGÂTS PAR TOUCHE'
        if s.rule == 'spin':
            return f'ROTATION : {abs(int(s.spin))}°/S', f'+{s.inc}°/S PAR TOUCHE'
        if s.rule == 'len':
            return f'PORTÉE : {int(s.L * 2)}', f'+{2 * s.inc} DE PORTÉE PAR TOUCHE'
        if s.rule == 'star':
            return f'SHURIKENS : {1 + s.hits}', '+1 SHURIKEN PAR TOUCHE'
        return '', ''


class Sim:
    def __init__(s, ep, seed):
        s.ep = ep
        rng = random.Random(seed)
        s.rng = rng
        s.t = 0.0
        s.f = []
        cfgs = ep['fighters']
        n1 = sum(1 for c in cfgs if c['team'] == 1)
        k1 = 0
        for i, c in enumerate(cfgs):
            if c['team'] == 0:
                x, y = AS * 0.28, AS * 0.5 + rng.uniform(-60, 60)
            elif n1 == 1:
                x, y = AS * 0.72, AS * 0.5 + rng.uniform(-60, 60)
            else:
                col, row = k1 % 2, k1 // 2
                x, y = AS * (0.66 + 0.16 * col) + rng.uniform(-10, 10), AS * (0.14 + 0.18 * row)
                k1 += 1
            s.f.append(Fighter(i, c, x, y, rng.uniform(0, 6.28), rng))
        s.proj = []
        s.cd = {}
        s.events = []
        s.over = False
        s.winner = None

    def ev(s, *a):
        s.events.append((s.t,) + a)

    def team_hp(s, team):
        fs = [f for f in s.f if f.team == team]
        return sum(max(0, f.hp) for f in fs), sum(f.hpmax for f in fs)

    def hit(s, a, b, dmg, px, py, kind='hit'):
        key = (a.i, b.i)
        if s.cd.get(key, -1) > s.t:
            return False
        s.cd[key] = s.t + 0.3
        b.hp -= dmg
        # knockback
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy) or 1
        b.vx, b.vy = b.vx * 0.3 + dx / d * b.speed, b.vy * 0.3 + dy / d * b.speed
        a.hits += 1
        if a.rule == 'dmg':
            a.dmg += a.inc
        elif a.rule == 'spin':
            a.spin += a.inc * (1 if a.spin >= 0 else -1)
        elif a.rule == 'len':
            a.L += a.inc
        s.ev(kind, a.i, b.i, dmg, px, py)
        if b.hp <= 0 and b.alive:
            b.alive = False
            b.hp = 0
            s.ev('ko', b.i, a.i, b.x, b.y)
            alive_teams = {f.team for f in s.f if f.alive}
            if len(alive_teams) == 1:
                s.over = True
                s.winner = alive_teams.pop()
        return True

    def step(s):
        dt = DT
        s.t += dt
        F = [f for f in s.f if f.alive]
        for f in F:
            f.ang += math.radians(f.spin) * dt
            f.x += f.vx * dt
            f.y += f.vy * dt
            if f.x < f.r:
                f.x, f.vx = f.r, abs(f.vx)
            if f.x > AS - f.r:
                f.x, f.vx = AS - f.r, -abs(f.vx)
            if f.y < f.r:
                f.y, f.vy = f.r, abs(f.vy)
            if f.y > AS - f.r:
                f.y, f.vy = AS - f.r, -abs(f.vy)
        # ball-ball
        for i in range(len(F)):
            a = F[i]
            for j in range(i + 1, len(F)):
                b = F[j]
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if d < a.r + b.r and d > 0:
                    nx, ny = dx / d, dy / d
                    ov = a.r + b.r - d
                    ma, mb = a.r ** 2, b.r ** 2
                    a.x -= nx * ov * mb / (ma + mb)
                    a.y -= ny * ov * mb / (ma + mb)
                    b.x += nx * ov * ma / (ma + mb)
                    b.y += ny * ov * ma / (ma + mb)
                    va, vb = a.vx * nx + a.vy * ny, b.vx * nx + b.vy * ny
                    if va - vb > 0:
                        a.vx += (vb - va) * nx
                        a.vy += (vb - va) * ny
                        b.vx += (va - vb) * nx
                        b.vy += (va - vb) * ny
                    if a.team != b.team:
                        px, py = a.x + nx * a.r, a.y + ny * a.r
                        for p, q in ((a, b), (b, a)):
                            if p.kind == 'none':
                                s.hit(p, q, p.dmg, px, py, 'bump')
        # weapons
        for a in F:
            sg = a.seg()
            if not sg:
                continue
            for b in F:
                if b.team == a.team or not b.alive:
                    continue
                d, cx, cy = seg_pt(*sg[0], *sg[1], b.x, b.y)
                if d < b.r:
                    s.hit(a, b, a.dmg, cx, cy)
                sb = b.seg()
                if sb and b.i > a.i:
                    key = ('p', a.i, b.i)
                    if s.cd.get(key, -1) < s.t and (seg_cross(*sg, *sb) or seg_seg(*sg, *sb) < 8):
                        s.cd[key] = s.t + 0.25
                        a.spin, b.spin = -a.spin, -b.spin
                        mx, my = (sg[1][0] + sb[1][0]) / 2, (sg[1][1] + sb[1][1]) / 2
                        s.ev('parry', a.i, b.i, mx, my)
            # parry projectiles
            for p in s.proj:
                if p['team'] != a.team and seg_pt(*sg[0], *sg[1], p['x'], p['y'])[0] < 14:
                    p['dead'] = True
                    s.ev('tink', p['x'], p['y'])
        # shuriken launchers
        for a in F:
            if a.kind != 'shuriken':
                continue
            a.timer -= dt
            if a.timer <= 0:
                a.timer = a.period
                tg = [b for b in F if b.team != a.team]
                if not tg:
                    continue
                b = tg[0]
                base = math.atan2(b.y - a.y, b.x - a.x) + s.rng.uniform(-0.35, 0.35)
                n = 1 + a.hits
                spread = min(0.22, 1.6 / max(n, 1))
                for k in range(n):
                    ang = base + (k - (n - 1) / 2) * spread
                    s.proj.append(dict(x=a.x + math.cos(ang) * (a.r + 10), y=a.y + math.sin(ang) * (a.r + 10),
                                       vx=math.cos(ang) * 640, vy=math.sin(ang) * 640, team=a.team, src=a.i,
                                       rot=0.0, dead=False))
                s.ev('throw', a.i, n)
        for p in s.proj:
            if p['dead']:
                continue
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['rot'] += 18 * dt
            if not (0 < p['x'] < AS and 0 < p['y'] < AS):
                p['dead'] = True
                continue
            for b in F:
                if b.team != p['team'] and b.alive and math.hypot(b.x - p['x'], b.y - p['y']) < b.r + 12:
                    p['dead'] = True
                    src = s.f[p['src']]
                    s.cd.pop((src.i, b.i), None)
                    s.hit(src, b, src.dmg, p['x'], p['y'], 'star')
                    break
        s.proj = [p for p in s.proj if not p['dead']]
        for f in F:
            en = [g for g in F if g.team != f.team]
            if en and STEER:
                g = min(en, key=lambda g: (g.x - f.x) ** 2 + (g.y - f.y) ** 2)
                want = math.atan2(g.y - f.y, g.x - f.x)
                cur = math.atan2(f.vy, f.vx)
                dlt = (want - cur + math.pi) % (2 * math.pi) - math.pi
                rot = max(-STEER * dt, min(STEER * dt, dlt))
                c, si = math.cos(rot), math.sin(rot)
                f.vx, f.vy = f.vx * c - f.vy * si, f.vx * si + f.vy * c
            v = math.hypot(f.vx, f.vy) or 1
            f.vx, f.vy = f.vx / v * f.speed, f.vy / v * f.speed


def headless(ep, seed, tmax=60):
    s = Sim(ep, seed)
    diffs = []
    k = 0
    while not s.over and s.t < tmax:
        s.step()
        k += 1
        if k % 24 == 0:
            a, am = s.team_hp(0)
            b, bm = s.team_hp(1)
            diffs.append(a / am - b / bm)
    lead, cur = 0, 0
    for d in diffs:
        sg = 1 if d > 0.06 else (-1 if d < -0.06 else 0)
        if sg and sg != cur:
            if cur:
                lead += 1
            cur = sg
    if not s.over:
        return None
    hp, hm = s.team_hp(s.winner)
    return dict(seed=seed, t=s.t, winner=s.winner, hp=hp, frac=hp / hm, lead=lead)


# ======================================================================= graphics helpers
@functools.lru_cache(None)
def font(p, s):
    return ImageFont.truetype(p, s)


_tmpd = ImageDraw.Draw(Image.new('RGBA', (1, 1)))


def clamp01(t):
    return min(max(t, 0.0), 1.0)


def ease_out(t):
    return 1 - (1 - clamp01(t)) ** 3


def back_out(t, s=2.2):
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


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


def place(cv, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0, maxw=1020):
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


def pop(t, dur=0.2, start=0.25):
    return 0 if t < 0 else start + (1 - start) * back_out(t / dur)


@functools.lru_cache(None)
def logo(size):
    S = 4
    s = size * S
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, s - 1, s - 1], fill=BLACK)
    d.ellipse([s * 0.04, s * 0.04, s * 0.96, s * 0.96], fill=RED)
    d.ellipse([s * 0.10, s * 0.10, s * 0.90, s * 0.90], outline=WHITE, width=int(s * 0.03))
    band = Image.new('L', (s, s), 0)
    ImageDraw.Draw(band).rectangle([0, s * 0.40, s, s * 0.58], fill=255)
    circ = Image.new('L', (s, s), 0)
    ImageDraw.Draw(circ).ellipse([s * 0.10, s * 0.10, s * 0.90, s * 0.90], fill=255)
    band = Image.fromarray(np.minimum(np.asarray(band), np.asarray(circ)))
    ol = int(s * 0.018)
    dark = Image.new('RGBA', (s, s), BLACK + (255,))
    im.paste(dark, (0, -ol), band)
    im.paste(dark, (0, ol), band)
    im.paste(Image.new('RGBA', (s, s), YEL + (255,)), (0, 0), band)
    c = s / 2
    for sgn in (-1, 1):
        d.polygon([(c + sgn * s * 0.02, s * 0.52), (c + sgn * s * 0.12, s * 0.52), (c + sgn * s * 0.26, s * 0.86),
                   (c + sgn * s * 0.13, s * 0.88)], fill=YEL, outline=BLACK, width=ol)
    k = s * 0.13
    d.rounded_rectangle([c - k, s * 0.49 - k, c + k, s * 0.49 + k], radius=s * 0.03, fill=YEL, outline=BLACK, width=ol)
    d.line([c - k * 0.5, s * 0.49 - k * 0.7, c + k * 0.5, s * 0.49 + k * 0.7], fill=BLACK, width=ol)
    return im.resize((size, size), Image.LANCZOS)


def mix(c, bg, a):
    return tuple(int(c[i] * a + bg[i] * (1 - a)) for i in range(3))


# ======================================================================= renderer
TATAMI = (58, 66, 44)
TATAMI2 = (66, 75, 50)


def make_arena_bg():
    s = AS * SS
    im = Image.new('RGB', (s, s), TATAMI)
    d = ImageDraw.Draw(im)
    m = s // 4
    for i in range(4):
        for j in range(4):
            horiz = (i + j) % 2 == 0
            x0, y0 = i * m, j * m
            d.rectangle([x0, y0, x0 + m, y0 + m], fill=TATAMI if horiz else TATAMI2)
            for k in range(0, m, 10 * SS):
                if horiz:
                    d.line([x0, y0 + k, x0 + m, y0 + k], fill=mix(TATAMI, BLACK, 0.9), width=1)
                else:
                    d.line([x0 + k, y0, x0 + k, y0 + m], fill=mix(TATAMI2, BLACK, 0.9), width=1)
            d.rectangle([x0, y0, x0 + m, y0 + m], outline=(38, 44, 28), width=3 * SS)
    # center mark
    c = s / 2
    d.ellipse([c - 150 * SS, c - 150 * SS, c + 150 * SS, c + 150 * SS], outline=(84, 94, 64), width=4 * SS)
    lg = logo(200 * SS)
    a = lg.getchannel('A').point(lambda v: int(v * 0.10))
    lg.putalpha(a)
    im.paste(lg, (int(c - lg.width / 2), int(c - lg.height / 2)), lg)
    return im


class Renderer:
    def __init__(s, epname, seed):
        s.epname = epname
        s.ep = EPISODES[epname]()
        s.seed = seed
        info = headless(s.ep, seed)
        s.tko = info['t']
        s.info = info
        s.sim = Sim(s.ep, seed)
        s.arena_bg = make_arena_bg()
        s.base = s.make_base()
        s.parts, s.pops, s.trails = [], [], {}
        s.shake = 0.0
        s.flash = {}
        s.audio = []
        s.stat_pop = {}
        s.last_stat = {}

    # ---------------------------------------------------------- static layout
    def make_base(s):
        cv = Image.new('RGB', (W, H), BLACK)
        a = np.linspace(0, 1, H)[:, None, None]
        arr = (np.array((20, 18, 24)) * (1 - a) + np.array(BLACK) * a).astype(np.uint8)
        cv = Image.fromarray(np.repeat(arr, W, axis=1))
        lg = logo(120)
        cv.paste(lg, (40, 46), lg)
        t = rich((T('TATAMI ', WHITE), T('TRAGIQUE', YEL)), ANTON, 76)
        cv.paste(t, (176, 40), t)
        st = rich((T('COMBAT DE BOULES • ÉPISODE ' + s.epname[1:], GREY),), ANTON, 30)
        cv.paste(st, (180, 146), st)
        d = ImageDraw.Draw(cv)
        d.rectangle([0, 206, W, 210], fill=YEL)
        d.rounded_rectangle([AX - 12, AY - 12, AX + AS + 12, AY + AS + 12], radius=18, fill=(24, 22, 18),
                            outline=YEL, width=5)
        return cv

    # ---------------------------------------------------------- panel
    def team_color(s, team):
        return next(f.color for f in s.sim.f if f.team == team)

    def draw_panel(s, cv, tnow):
        d = ImageDraw.Draw(cv)
        names = s.ep.get('team_names', s.ep['title'])
        for team in (0, 1):
            col = s.team_color(team)
            if col[0] + col[1] + col[2] < 150:
                col = (235, 235, 240)
            nm = rich((T(names[team], col),), ANTON, 58 if len(names[team]) < 12 else 46, stroke=3)
            x = 60 if team == 0 else W - 60 - nm.width
            cv.paste(nm, (int(x), 236), nm)
            hp, hm = s.sim.team_hp(team)
            bw, bh, by = 430, 44, 330
            bx = 60 if team == 0 else W - 60 - bw
            d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, fill=(44, 44, 50), outline=BLACK, width=3)
            ghost = s.ghost.setdefault(team, hp)
            if ghost > hp:
                s.ghost[team] = max(hp, ghost - hm * 0.012)
            gw = bw * s.ghost[team] / hm
            w = bw * hp / hm
            fillc = s.team_color(team)
            if fillc[0] + fillc[1] + fillc[2] < 150:
                fillc = (120, 120, 130)
            if team == 0:
                if gw > 4:
                    d.rounded_rectangle([bx, by, bx + gw, by + bh], radius=12, fill=WHITE)
                if w > 4:
                    d.rounded_rectangle([bx, by, bx + w, by + bh], radius=12, fill=fillc)
            else:
                if gw > 4:
                    d.rounded_rectangle([bx + bw - gw, by, bx + bw, by + bh], radius=12, fill=WHITE)
                if w > 4:
                    d.rounded_rectangle([bx + bw - w, by, bx + bw, by + bh], radius=12, fill=fillc)
            d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, outline=BLACK, width=3)
            lab = rich((T(f'{int(math.ceil(hp))} PV', WHITE),), ANTON, 32, stroke=3)
            cv.paste(lab, (int(bx + bw / 2 - lab.width / 2), by + bh // 2 - lab.height // 2), lab)
            # stat line
            fs = [f for f in s.sim.f if f.team == team]
            if len(fs) == 1:
                stat, rule = fs[0].stat()
            else:
                stat, rule = f'{sum(f.alive for f in fs)}/{len(fs)} DEBOUT', ''
            if s.epname == 'E3' and team == 0:
                stat, rule = f'DÉGÂTS : {fs[0].dmg}', 'SEUL CONTRE TOUS'
            if s.epname == 'E3' and team == 1:
                rule = '1 DÉGÂT PAR CONTACT'
            if stat:
                if s.last_stat.get(team) != stat:
                    if team in s.last_stat:
                        s.stat_pop[team] = tnow
                    s.last_stat[team] = stat
                age = tnow - s.stat_pop.get(team, -9)
                hot = age < 0.35
                im = rich((T(stat, YEL if hot else WHITE),), ANTON, 40, stroke=3)
                sc = 1 + 0.25 * (1 - clamp01(age / 0.35)) if hot else 1
                cx = bx + im.width * sc / 2 if team == 0 else bx + bw - im.width * sc / 2
                place(cv, im, cx, 408, sc)
            if rule:
                im = rich((T(rule, GREY),), ANTON, 26, stroke=2)
                cx = bx + im.width / 2 if team == 0 else bx + bw - im.width / 2
                place(cv, im, cx, 458)
        vs = rich((T('VS', YEL),), LUCK, 70, stroke=8)
        place(cv, vs, 540, 350, 1 + 0.05 * math.sin(tnow * 6))

    # ---------------------------------------------------------- arena drawing
    def P(s, x, y):
        return x * SS, y * SS

    def draw_weapon(s, d, f):
        c, si = math.cos(f.ang), math.sin(f.ang)
        nx, ny = -si, c

        def pt(a, b=0.0):
            return ((f.x + c * a + nx * b) * SS, (f.y + si * a + ny * b) * SS)

        if f.kind == 'katana':
            r = f.r
            d.line([pt(r * 0.5), pt(r + 16)], fill=(30, 14, 16), width=16 * SS)
            for k in range(3):
                a = r * 0.6 + k * 12
                d.line([pt(a, -6), pt(a + 6, 6)], fill=(200, 40, 50), width=3 * SS)
            d.polygon([pt(r + 14, -20), pt(r + 22, -20), pt(r + 22, 20), pt(r + 14, 20)], fill=(214, 170, 60),
                      outline=BLACK)
            L = f.L
            d.polygon([pt(r + 22, -10), pt(r + 22, 10), pt(r + L - 22, 7), pt(r + L, -3), pt(r + L - 26, -11)],
                      fill=(222, 228, 238), outline=(60, 64, 74))
            d.line([pt(r + 24, 3), pt(r + L - 20, 2)], fill=(255, 255, 255), width=2 * SS)
        elif f.kind == 'nunchaku':
            r, L = f.r, f.L
            j = r + L * 0.48
            d.line([pt(r * 0.5), pt(j - 4)], fill=(120, 72, 36), width=17 * SS)
            d.line([pt(r * 0.5), pt(j - 4)], fill=(150, 95, 50), width=5 * SS)
            bend = -0.3 if f.spin > 0 else 0.3
            c2, s2 = math.cos(f.ang + bend), math.sin(f.ang + bend)
            jx, jy = f.x + c * j, f.y + si * j
            ex, ey = jx + c2 * (L * 0.52 + r - j + r * 0.0), jy + s2 * (L * 0.52)
            ex, ey = jx + c2 * (r + L - j), jy + s2 * (r + L - j)
            d.line([(jx * SS, jy * SS), (ex * SS, ey * SS)], fill=(120, 72, 36), width=17 * SS)
            d.line([(jx * SS, jy * SS), (ex * SS, ey * SS)], fill=(150, 95, 50), width=5 * SS)
            d.ellipse([jx * SS - 7 * SS, jy * SS - 7 * SS, jx * SS + 7 * SS, jy * SS + 7 * SS], fill=(190, 190, 200),
                      outline=BLACK)
        elif f.kind == 'bo':
            L = f.L
            d.line([pt(-L), pt(L)], fill=(92, 56, 28), width=21 * SS)
            d.line([pt(-L), pt(L)], fill=(160, 104, 52), width=11 * SS)
            for a in (-L + 8, -L + 20, L - 20, L - 8):
                d.line([pt(a, -8), pt(a, 8)], fill=(40, 28, 20), width=5 * SS)

    def star(s, d, x, y, rot, size=15, fill=(200, 205, 215)):
        pts = []
        for k in range(8):
            rr = size if k % 2 == 0 else size * 0.38
            a = rot + k * math.pi / 4
            pts.append(((x + math.cos(a) * rr) * SS, (y + math.sin(a) * rr) * SS))
        d.polygon(pts, fill=fill, outline=(40, 40, 46))
        d.ellipse([(x - 3) * SS, (y - 3) * SS, (x + 3) * SS, (y + 3) * SS], fill=(40, 40, 46))

    def draw_ball(s, d, f, tnow):
        x, y, r = f.x * SS, f.y * SS, f.r * SS
        fl = s.flash.get(f.i, -9)
        hit = tnow - fl < 0.07
        col = WHITE if hit else f.color
        outline = f.__dict__.get('outline', mix(f.color, BLACK, 0.45))
        d.ellipse([x - r - 5 * SS, y - r - 5 * SS, x + r + 5 * SS, y + r + 5 * SS], fill=BLACK)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=outline, width=4 * SS)
        # belt
        belt = BLACK if f.team == 0 and f.color[0] > 60 else (WHITE if f.color[0] < 60 else (40, 40, 40))
        if f.color == (245, 245, 245):
            belt = (250, 250, 250)
            d.ellipse([x - r, y - r, x + r, y + r], outline=(150, 150, 160), width=3 * SS)
        by = y + r * 0.35
        hw = math.sqrt(max(r * r - (r * 0.35) ** 2, 0))
        if f.color != (245, 245, 245):
            d.line([(x - hw + 3 * SS, by), (x + hw - 3 * SS, by)], fill=belt if not hit else WHITE,
                   width=int(r * 0.22))
            d.rectangle([x - r * 0.12, by - r * 0.14, x + r * 0.12, by + r * 0.14], fill=belt)
        else:
            d.line([(x - hw + 3 * SS, by), (x + hw - 3 * SS, by)], fill=(225, 225, 232), width=int(r * 0.22))
        # eyes toward nearest enemy
        en = [g for g in s.sim.f if g.team != f.team and g.alive]
        if en:
            g = min(en, key=lambda g: (g.x - f.x) ** 2 + (g.y - f.y) ** 2)
            a = math.atan2(g.y - f.y, g.x - f.x)
        else:
            a = math.atan2(f.vy, f.vx)
        er = r * 0.2
        for sx in (-1, 1):
            ex, ey = x + sx * r * 0.32, y - r * 0.18
            if not f.alive or hit:
                w = er * 0.8
                d.line([(ex - w, ey - w), (ex + w, ey + w)], fill=BLACK, width=3 * SS)
                d.line([(ex - w, ey + w), (ex + w, ey - w)], fill=BLACK, width=3 * SS)
            else:
                d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=WHITE, outline=BLACK, width=2 * SS)
                px, py = ex + math.cos(a) * er * 0.45, ey + math.sin(a) * er * 0.45
                pr = er * 0.5
                d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=BLACK)
        # angry brows
        for sx in (-1, 1):
            ex, ey = x + sx * r * 0.32, y - r * 0.18 - er * 1.35
            d.line([(ex - sx * er, ey - er * 0.35), (ex + sx * er, ey + er * 0.3)], fill=BLACK, width=int(3.5 * SS))

    def draw_arena(s, tnow, zoom=1.0, zc=None):
        im = s.arena_bg.copy()
        d = ImageDraw.Draw(im)
        # trails
        for f in s.sim.f:
            tr = s.trails.get(f.i, [])
            if len(tr) > 1 and f.alive:
                for k in range(1, len(tr)):
                    a = k / len(tr)
                    col = mix(WHITE if f.kind != 'bo' else (230, 200, 150), TATAMI, 0.45 * a)
                    d.line([tr[k - 1], tr[k]], fill=col, width=int((3 + 7 * a) * SS))
        for f in s.sim.f:
            if f.alive:
                s.draw_weapon(d, f)
        for f in sorted(s.sim.f, key=lambda f: f.alive):
            if f.alive:
                s.draw_ball(d, f, tnow)
        for p in s.sim.proj:
            s.star(d, p['x'], p['y'], p['rot'], 20)
        for f in s.sim.f:
            if f.alive and f.kind == 'shuriken':
                s.star(d, f.x, f.y - f.r - 2, tnow * 6, 12, YEL)
        # particles
        for p in s.parts:
            a = clamp01(p['life'] / p['max'])
            x, y = p['x'] * SS, p['y'] * SS
            if p['kind'] == 'spark':
                d.line([(x, y), (x - p['vx'] * 0.02 * SS, y - p['vy'] * 0.02 * SS)], fill=mix(p['c'], TATAMI, a),
                       width=int(4 * SS))
            else:
                rr = p['r'] * SS * (0.4 + 0.6 * a)
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=mix(p['c'], TATAMI, min(1, a * 1.5)))
        im = im.resize((AS, AS), Image.LANCZOS)
        if zoom > 1.001 and zc:
            w = AS / zoom
            x0 = min(max(zc[0] - w / 2, 0), AS - w)
            y0 = min(max(zc[1] - w / 2, 0), AS - w)
            im = im.resize((AS, AS), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + w))
        return im

    # ---------------------------------------------------------- effects
    def burst(s, x, y, col, n=14, speed=520, kind='spark', life=0.35, r=6):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.3, 1) * speed
            s.parts.append(dict(x=x, y=y, vx=math.cos(a) * v, vy=math.sin(a) * v, life=life, max=life, c=col,
                                kind=kind, r=r))

    def update_fx(s, dt):
        for p in s.parts:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vx'] *= 0.9
            p['vy'] *= 0.9
            p['life'] -= dt
        s.parts = [p for p in s.parts if p['life'] > 0]
        s.shake *= 0.82

    def handle_events(s, tout):
        hs = 0
        for ev in s.sim.events:
            kind = ev[1]
            if kind in ('hit', 'bump', 'star'):
                _, _, ai, bi, dmg, px, py = ev
                a, b = s.sim.f[ai], s.sim.f[bi]
                if kind != 'bump':
                    s.flash[bi] = tout
                s.burst(px, py, WHITE, 10 + min(dmg, 20))
                s.burst(px, py, b.color, 8, 300, 'blob', 0.45, 7)
                s.pops.append(dict(x=px, y=py - 20, t=tout, txt=f'-{dmg}', big=dmg >= 8))
                s.shake = max(s.shake, min(6 + dmg * 1.4, 26))
                hs = max(hs, 1 + min(dmg // 6, 3))
                s.audio.append((tout, 'punch' if kind != 'star' else 'slice', 0.55))
                s.audio.append((tout, ('note', a.team, a.hits), 0.35))
            elif kind == 'parry':
                _, _, ai, bi, mx, my = ev
                s.burst(mx, my, YEL, 16, 650)
                s.shake = max(s.shake, 8)
                s.audio.append((tout, 'clang', 0.4))
                hs = max(hs, 1)
            elif kind == 'tink':
                _, _, x, y = ev
                s.burst(x, y, YEL, 6, 400)
                s.audio.append((tout, 'tink', 0.35))
            elif kind == 'throw':
                s.audio.append((tout, 'whoosh_s', 0.18))
            elif kind == 'ko':
                _, _, bi, ai, x, y = ev
                b = s.sim.f[bi]
                s.burst(x, y, b.color, 40, 900, 'blob', 0.9, 11)
                s.burst(x, y, WHITE, 30, 1100)
                s.shake = 30
                s.audio.append((tout, 'boom' if s.sim.over else 'pop_ko', 0.7 if s.sim.over else 0.5))
        s.sim.events.clear()
        return hs

    # ---------------------------------------------------------- main loop
    def frames(s):
        s.ghost = {}
        tout, n = 0.0, 0
        slow_from = s.tko - 0.35
        hold = 0
        ko_out = None
        END = 3.4
        while True:
            if ko_out is None:
                if hold > 0:
                    hold -= 1
                else:
                    steps = SUB if s.sim.t < slow_from else 2
                    for _ in range(steps):
                        if s.sim.over:
                            break
                        s.sim.step()
                    hold = s.handle_events(tout)
                    if s.sim.over:
                        ko_out = tout
                        s.audio.append((tout + 0.05, 'impact', 0.6))
                        s.audio.append((tout + 0.55, 'stamp', 0.7))
                        s.audio.append((tout + 1.15, 'jingle', 0.5))
                        s.audio.append((tout + 1.3, 'pop', 0.4))
                        s.audio.append((tout + 1.55, 'pop', 0.4))
                        s.audio.append((tout + 1.8, 'pop', 0.4))
            for f in s.sim.f:
                sg = f.seg()
                if sg and f.alive:
                    tip = sg[1]
                    tr = s.trails.setdefault(f.i, [])
                    tr.append((tip[0] * SS, tip[1] * SS))
                    if f.kind == 'bo':
                        pass
                    del tr[:-6]
            s.update_fx(1 / FPS)
            yield s.render(tout, ko_out)
            tout += 1 / FPS
            n += 1
            if ko_out is not None and tout - ko_out > END:
                break
        s.duration = tout

    def render(s, tout, ko_out):
        cv = s.base.copy()
        slow = s.sim.t >= s.tko - 0.35 and ko_out is None
        zoom, zc = 1.0, None
        loser = None
        if s.sim.over or slow:
            los = [f for f in s.sim.f if f.team != s.info['winner']]
            loser = min(los, key=lambda f: f.hp)
        if slow:
            u = clamp01((s.sim.t - (s.tko - 0.35)) / 0.35)
            zoom, zc = 1 + 0.35 * ease_out(u), (loser.x, loser.y)
        elif ko_out is not None:
            u = clamp01((tout - ko_out) / 0.25)
            zoom, zc = 1.35 - 0.35 * ease_out(u), (loser.x, loser.y)
        ar = s.draw_arena(tout, zoom, zc)
        dx = random.uniform(-1, 1) * s.shake
        dy = random.uniform(-1, 1) * s.shake
        if ko_out is not None and tout - ko_out > 0.9:
            k = clamp01((tout - ko_out - 0.9) / 0.3)
            ar = Image.blend(ar, Image.new('RGB', ar.size, BLACK), 0.62 * k)
        if ko_out is not None and tout - ko_out < 0.1:
            ar = Image.blend(ar, Image.new('RGB', ar.size, WHITE), 0.7 * (1 - (tout - ko_out) / 0.1))
        cv.paste(ar, (AX + int(dx), AY + int(dy)))
        d = ImageDraw.Draw(cv)
        d.rounded_rectangle([AX - 12, AY - 12, AX + AS + 12, AY + AS + 12], radius=18, outline=YEL, width=5)
        s.draw_panel(cv, tout)
        # popups (arena coords -> screen)
        for p in s.pops:
            age = tout - p['t']
            if age > 0.8 or zoom > 1.001:
                continue
            im = rich((T(p['txt'], YEL if p['big'] else WHITE),), LUCK, 58 if p['big'] else 44, stroke=7)
            place(cv, im, AX + p['x'] + dx, AY + p['y'] - 70 * ease_out(age / 0.8) + dy, pop(age, 0.15, 0.4),
                  0, 1 - clamp01((age - 0.5) / 0.3))
        s.pops = [p for p in s.pops if tout - p['t'] < 0.9]
        # intro overlay
        if tout < 1.6:
            q = rich((T('QUI VA GAGNER ?', YEL),), LUCK, 104, stroke=12, shadow=8)
            a = 1 - clamp01((tout - 1.25) / 0.35)
            place(cv, q, 540, AY + 150, pop(tout, 0.25, 0.3), -3, a)
        # bottom
        if ko_out is None:
            b = rich((T('COMMENTE TON CHOIX ', WHITE), E('1f447')), LUCK, 50, stroke=7)
            place(cv, b, 540, 1540, 1 + 0.04 * math.sin(tout * 5))
        else:
            k = tout - ko_out
            ko = rich((T('K.O. !', RED),), ANTON, 250, stroke=14, shadow=12)
            if 0.5 <= k < 1.15:
                place(cv, ko, 540, AY + AS / 2, 2.6 - 1.6 * ease_out((k - 0.5) / 0.12), 8,
                      1 - clamp01((k - 0.95) / 0.2))
            if k >= 1.15:
                w = s.info['winner']
                names = s.ep.get('team_names', s.ep['title'])
                col = s.team_color(w)
                if sum(col) < 150:
                    col = WHITE
                cup = emoji('1f3c6', 150)
                place(cv, cup, 540, AY + 190, pop(k - 1.15, 0.25, 0.2), 6 * math.sin(k * 4))
                wn = rich((T(names[w], col),), LUCK, 108, stroke=12, shadow=8)
                place(cv, wn, 540, AY + 360, pop(k - 1.3), -2)
                g = rich((T('GAGNENT !' if names[w].endswith('S') else 'GAGNE !', WHITE),), LUCK, 108, stroke=12, shadow=8)
                place(cv, g, 540, AY + 480, pop(k - 1.4), 2)
                hp = int(math.ceil(s.info['hp']))
                sub = rich((T(f'AVEC SEULEMENT {hp} PV !' if s.info['frac'] < 0.25 else f'AVEC {hp} PV RESTANTS', YEL),),
                           LUCK, 58, stroke=8, shadow=5)
                place(cv, sub, 540, AY + 600, pop(k - 1.55))
                ok = rich((T('TU AVAIS BON ? ', WHITE), E('1f447')), LUCK, 64, stroke=8, shadow=5)
                place(cv, ok, 540, AY + 740, pop(k - 1.8), -2)
                nx = rich((T('PROCHAIN COMBAT : ', GREY), T(s.ep['next'], YEL)), ANTON, 40, stroke=3)
                place(cv, nx, 540, 1540, pop(k - 2.1))
        return cv


# ======================================================================= audio
SR = 44100
arng = np.random.default_rng(3)


def tv(d):
    return np.arange(int(d * SR)) / SR


def norm(x):
    return x / (np.abs(x).max() + 1e-9)


def bpf(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)


def lpf(x, fc):
    return sosfilt(butter(2, fc, btype='low', fs=SR, output='sos'), x)


def hpf(x, fc):
    return sosfilt(butter(2, fc, btype='high', fs=SR, output='sos'), x)


def s_punch():
    t = tv(0.28)
    f = 55 + 190 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07)
    x += 0.9 * bpf(arng.standard_normal(len(t)), 900, 7000) * np.exp(-t / 0.014)
    return norm(np.tanh(2.5 * x))


def s_slice():
    t = tv(0.22)
    fc = np.linspace(6000, 1500, len(t))
    x = bpf(arng.standard_normal(len(t)), 1500, 9000) * np.exp(-t / 0.05)
    x += 0.4 * np.sin(2 * np.pi * np.cumsum(fc) / SR) * np.exp(-t / 0.03)
    return norm(x)


def partials(d, fs, amps, taus):
    t = tv(d)
    x = sum(a * np.sin(2 * np.pi * f * t + arng.random() * 6) * np.exp(-t / ta) for f, a, ta in zip(fs, amps, taus))
    return norm(x * (1 - np.exp(-t / 0.002)))


def s_clang():
    b = 520
    x = partials(0.9, [b, b * 2.76, b * 5.4, b * 8.93], [1, .6, .35, .2], [0.5, .3, .18, .1])
    t = tv(0.9)
    return norm(x + 0.5 * norm(bpf(arng.standard_normal(len(t)), 2000, 9000) * np.exp(-t / 0.01)))


def s_tink():
    return partials(0.4, [2400, 5100, 7300], [1, .5, .3], [0.15, .08, .05])


def s_boom():
    t = tv(1.4)
    f = 45 + 70 * np.exp(-t / 0.08)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * np.exp(-t / 0.45) + 0.3 * lpf(arng.standard_normal(len(t)), 900) * np.exp(-t / 0.25)
    return norm(np.tanh(2.2 * x))


def s_impact():
    t = tv(0.5)
    f = 40 + 110 * np.exp(-t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17) + 0.5 * lpf(arng.standard_normal(len(t)), 3500) * np.exp(-t / 0.012)
    return norm(np.tanh(2 * x))


def s_pop():
    t = tv(0.14)
    f = 380 + 900 * (1 - np.exp(-t / 0.02))
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * (1 - np.exp(-t / 0.002)))


def s_pop_ko():
    t = tv(0.4)
    f = 900 * np.exp(-t / 0.15) + 120
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12))


def s_whoosh(d=0.25):
    t = tv(d)
    x = bpf(arng.standard_normal(len(t)), 1500, 6000) * np.sin(np.pi * t / d) ** 2
    return norm(x)


def s_jingle():
    out = np.zeros(int(1.6 * SR))
    for k, (f, st) in enumerate([(523.25, 0), (659.25, .1), (783.99, .2), (1046.5, .3), (1318.5, .4)]):
        t = tv(1.6 - st)
        x = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * np.exp(-t / (0.25 if k < 4 else 0.8))
        x *= 1 - np.exp(-t / 0.003)
        i0 = int(st * SR)
        m = min(len(x), len(out) - i0)
        out[i0:i0 + m] += x[:m]
    return norm(out)


def s_note(team, k):
    scale = [0, 2, 4, 7, 9]
    base = 261.63 if team == 0 else 392.0
    step = min(k - 1, 14)
    semi = scale[step % 5] + 12 * (step // 5)
    f = base * 2 ** (semi / 12)
    t = tv(0.5)
    x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t))
    return norm(x * np.exp(-t / 0.16) * (1 - np.exp(-t / 0.002)))


def beat(dur, bpm=128):
    n = int(dur * SR)
    out = np.zeros(n)
    spb = 60 / bpm
    kick = (lambda t: np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.18))(tv(0.35))
    hat = hpf(arng.standard_normal(int(0.05 * SR)), 7000) * np.exp(-tv(0.05) / 0.012)
    clap = bpf(arng.standard_normal(int(0.2 * SR)), 800, 4000) * np.exp(-tv(0.2) / 0.05)
    bassn = [55.0, 55.0, 65.41, 49.0]
    k = 0
    t = 0.0
    while t < dur:
        i = int(t * SR)
        def add(x, g):
            m = min(len(x), n - i)
            if m > 0:
                out[i:i + m] += x[:m] * g
        add(kick, 0.9)
        bar = (k // 4) % 4
        bt = tv(spb * 0.9)
        bf = bassn[bar]
        add(np.tanh(3 * np.sin(2 * np.pi * bf * bt)) * np.exp(-bt / 0.25) * 0.5, 0.5)
        if k % 2 == 1:
            add(clap, 0.35)
        j = int((t + spb / 2) * SR)
        if j < n:
            m = min(len(hat), n - j)
            out[j:j + m] += hat[:m] * 0.25
        t += spb
        k += 1
    return lpf(out, 9000)


def build_audio(r, path):
    n = int((r.duration + 0.5) * SR)
    out = np.zeros(n)
    SFX = dict(punch=s_punch(), slice=s_slice(), clang=s_clang(), tink=s_tink(), boom=s_boom(), impact=s_impact(),
               pop=s_pop(), pop_ko=s_pop_ko(), whoosh_s=s_whoosh(), jingle=s_jingle(), stamp=s_impact())
    notes = {}
    for t, name, g in r.audio:
        if isinstance(name, tuple):
            key = (name[1], name[2])
            if key not in notes:
                notes[key] = s_note(*key)
            x = notes[key]
        else:
            x = SFX[name]
        i = int(t * SR)
        m = min(len(x), n - i)
        if m > 0:
            out[i:i + m] += x[:m] * g
    ko = next((t for t, nme, g in r.audio if nme == 'boom'), r.duration)
    b = beat(ko + 0.2)
    b[-int(0.2 * SR):] *= np.linspace(1, 0, int(0.2 * SR))
    out[:len(b)] += b * 0.22
    out = np.tanh(out * 0.9)
    st = np.stack([out, out], 1)
    raw = (np.clip(st, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(raw.tobytes())


# ======================================================================= CLI
def search(epname, n=400):
    ep = EPISODES[epname]
    res = []
    for seed in range(n):
        r = headless(ep(), seed)
        if r:
            res.append(r)
    wins = [r['winner'] for r in res]
    print(f'{len(res)} finished, team0 wins {wins.count(0)}, team1 wins {wins.count(1)}')
    ts = sorted(r['t'] for r in res)
    print('durations p10/p50/p90', ts[len(ts) // 10], ts[len(ts) // 2], ts[9 * len(ts) // 10])
    good = [r for r in res if 18 <= r['t'] <= 36 and r['frac'] <= 0.2 and r['hp'] > 0]
    good.sort(key=lambda r: (-r['lead'], r['frac']))
    for r in good[:10]:
        print(r)
    return good


if __name__ == '__main__':
    cmd, epname = sys.argv[1], sys.argv[2]
    if cmd == 'search':
        search(epname, int(sys.argv[3]) if len(sys.argv) > 3 else 400)
    elif cmd == 'still':
        r = Renderer(epname, int(sys.argv[3]))
        want = [float(x) for x in sys.argv[4:]]
        for i, fr in enumerate(r.frames()):
            t = i / FPS
            for w_ in want:
                if abs(t - w_) < 0.5 / FPS:
                    fr.save(f'{D}/prev/f_{epname}_{w_}.png')
            if t > max(want):
                break
    elif cmd == 'render':
        seed = int(sys.argv[3])
        r = Renderer(epname, seed)
        out = f'{D}/fight_{epname}.mp4'
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                              f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf',
                              '19', '-pix_fmt', 'yuv420p', f'{D}/_v_{epname}.mp4'], stdin=subprocess.PIPE)
        for i, fr in enumerate(r.frames()):
            p.stdin.write(fr.tobytes())
            if i % 150 == 0:
                print(epname, i, flush=True)
        p.stdin.close()
        p.wait()
        build_audio(r, f'{D}/_a_{epname}.wav')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{D}/_v_{epname}.mp4', '-i',
                        f'{D}/_a_{epname}.wav', '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac',
                        '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out], check=True)
        print('done', out, r.duration, flush=True)
