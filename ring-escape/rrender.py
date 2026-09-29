#!/usr/bin/env python3
"""Ring Escape - 'hors serie' : 9 rings, 1 ball. python3 rrender.py [still t...] """
import sys, os, math, random, colorsys, subprocess, multiprocessing as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rsim import simulate, NR, BR, SUB, ring_r
import raudio

SEED = 30
FPS = 30
W, H = 1080, 1920
CX, CY = 540, 930
SS = 2                              # supersampling of the crisp layer
Y0, Y1 = 150, 1650                  # crisp region rows
A = os.path.dirname(os.path.abspath(__file__)) + '/../assets/'
ANTON = A + 'anton.ttf'
EMO = A + 'emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
HANDLE = '@ring.escape'

SIM = simulate(SEED)
ST = SIM['states']; EV = SIM['ev']; ESC = SIM['esc']; TF = ESC[-1]
SLOW = 0.30
S0, S1 = TF - 0.6, TF + 0.3                       # slow-mo window (sim time)
V0 = S0; V1 = S0 + (S1 - S0) / SLOW               # same window in video time
TAIL = 1.9
DUR = (TF + 0.3) - (S1 - S0) + (S1 - S0) / SLOW + TAIL - 0.3
NF = int(DUR * FPS)

def st(vt):                                        # video time -> sim time
    if vt < V0: return vt
    if vt < V1: return S0 + (vt - V0) * SLOW
    return S1 + (vt - V1)
def vt_of(s):                                      # sim time -> video time
    if s < S0: return s
    if s < S1: return V0 + (s - S0) / SLOW
    return V1 + (s - S1)

ESC_V = [vt_of(e) for e in ESC]
BOUNCES = [(e[0], e[1], e[2], e[3], e[4], e[5]) for e in EV if e[1] == 'b']

def ring_col(k, lit=1.0):
    h = (0.52 + 0.058 * k) % 1.0                   # cyan -> blue -> violet -> magenta -> orange
    if k >= 7: h = 0.97 - 0.09 * (k - 7)
    r, g, b = colorsys.hsv_to_rgb(h, 0.72 - 0.25 * lit * 0.4, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))

def font(s): return ImageFont.truetype(ANTON, s)
_em = {}
def emoji(code, size):
    k = (code, size)
    if k not in _em:
        _em[k] = Image.open(EMO + f'{code:x}.png').convert('RGBA').resize((size, size), Image.LANCZOS)
    return _em[k]

def text_c(img, xy, s, size, fill=(255, 255, 255), stroke=8, sc=(8, 10, 24), emo=None, scale=1.0):
    """centered text with outline; optional trailing emoji"""
    f = font(int(size * scale))
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), s, font=f, stroke_width=int(stroke * scale))
    w = bb[2] - bb[0]
    es = int(size * scale * 0.95) if emo else 0
    tot = w + (es + 14 if emo else 0)
    x = xy[0] - tot / 2 - bb[0]; y = xy[1] - (bb[3] - bb[1]) / 2 - bb[1]
    d.text((x, y), s, font=f, fill=fill, stroke_width=int(stroke * scale), stroke_fill=sc)
    if emo:
        img.alpha_composite(emoji(emo, es), (int(x + w + 14 + bb[0]), int(xy[1] - es / 2))) if img.mode == 'RGBA' else img.paste(emoji(emo, es), (int(x + w + 14 + bb[0]), int(xy[1] - es / 2)), emoji(emo, es))

# ---------------------------------------------------------------- background
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
_R = np.hypot(XX - CX, YY - CY) / 900.0
BG_BASE = np.clip(1.0 - _R, 0, 1) ** 1.6
VIG = np.clip(1.15 - np.hypot((XX - W / 2) / (W * .75), (YY - H / 2) / (H * .62)) ** 2 * .55, .25, 1.0)[..., None]

def background(t, k, pulse):
    col = np.array(ring_col(min(k, NR - 1)), np.float32) / 255
    base = np.array([7, 9, 22], np.float32)
    glow = (0.10 + 0.14 * pulse)
    img = base[None, None, :] + (BG_BASE[..., None] * col[None, None, :] * 255 * glow)
    return np.clip(img * VIG, 0, 255)

# ---------------------------------------------------------------- particles (deterministic)
_prng = random.Random(77)
SHARDS = []
for j in range(NR):
    R = ring_r(j)
    lst = []
    for i in range(46):
        a = _prng.uniform(0, 2 * math.pi)
        sp = _prng.uniform(500, 1250)
        lst.append((R * math.cos(a), R * math.sin(a), math.cos(a) * sp + _prng.uniform(-150, 150),
                    math.sin(a) * sp + _prng.uniform(-150, 150) - 250, _prng.uniform(10, 26), _prng.uniform(0, 6.28), _prng.uniform(0.55, 1.0)))
    SHARDS.append(lst)

def lerp(a, b, u): return a + (b - a) * u

# ---------------------------------------------------------------- one frame
def frame(fi, dbg=False):
    vt = fi / FPS
    s = st(vt)
    i = min(int(s * SUB), len(ST) - 2); u = s * SUB - i
    bx = lerp(ST[i][0], ST[i + 1][0], u); by = lerp(ST[i][1], ST[i + 1][1], u)
    angs = ST[i][2]; cur = ST[i][3]
    if s * SUB >= len(ST) - 1: bx, by = ST[-1][0], ST[-1][1]
    k_done = sum(1 for e in ESC_V if e <= vt)           # rings already escaped
    kk = min(k_done, NR - 1)
    beat = (vt % raudio.BEAT) / raudio.BEAT
    in_slow = V0 <= vt < V1 + 0.25
    pulse = 0.0 if in_slow else math.exp(-beat * 5.0)
    # last escape / punch
    last_e = max([e for e in ESC_V if e <= vt], default=-9)
    tau = vt - last_e
    punch = math.exp(-tau / 0.13) if tau >= 0 else 0
    shake = 14 * math.exp(-tau / 0.16) if tau >= 0 else 0
    if k_done == NR: shake *= 2.2; punch *= 1.7
    zoom = 1.0 + 0.045 * punch + 0.012 * pulse
    if vt < 0.5: zoom *= 1 + 0.16 * (1 - vt / 0.5) ** 2          # opening punch-in
    camx = camy = 0.0
    if V0 - 0.3 <= vt < V1 + 0.3:                                # slow-mo: lean toward the ball
        w = min(1, (vt - (V0 - 0.3)) / 0.4) * min(1, (V1 + 0.3 - vt) / 0.3)
        zoom *= 1 + 0.22 * w; camx = bx * 0.55 * w; camy = by * 0.55 * w
    rng = random.Random(fi)
    ox = rng.uniform(-1, 1) * shake; oy = rng.uniform(-1, 1) * shake
    def T(x, y): return (CX + ox + (x - camx) * zoom, CY + oy + (y - camy) * zoom)

    # ---- background
    fr = background(vt, kk, pulse)
    # ---- glow layer (1/4 scale) + crisp layer (SS x)
    GS = 4
    gl = Image.new('RGB', (W // GS, H // GS), (0, 0, 0)); gd = ImageDraw.Draw(gl)
    cr = Image.new('RGBA', (W * SS, (Y1 - Y0) * SS), (0, 0, 0, 0)); cd = ImageDraw.Draw(cr)
    def P(x, y, S): return ((x) * S, (y - (Y0 if S == SS else 0)) * S) if False else None
    def cp(x, y): return (x * SS, (y - Y0) * SS)
    lit = {}
    for (tb, _, rk, sp, px, py) in BOUNCES:
        if rk == cur and 0 <= s - tb < 0.25: lit[rk] = max(lit.get(rk, 0), math.exp(-(s - tb) / 0.07))
    for k in range(NR):
        if k < k_done or ESC_V[k] <= vt and k < len(ESC_V): continue
        R = ring_r(k) * zoom
        col = ring_col(k)
        l = lit.get(k, 0)
        a0 = angs[k]; g = SIM['rings'][k]['gap']
        ccx, ccy = T(0, 0)
        c2 = cp(ccx, ccy)
        bb = [c2[0] - R * SS, c2[1] - R * SS, c2[0] + R * SS, c2[1] + R * SS]
        wdt = int((9 + 6 * l) * SS * (1 + 0.04 * (zoom - 1) * 10))
        c_draw = tuple(min(255, int(c + (255 - c) * l * 0.7)) for c in col)
        st_deg = math.degrees(a0 + g); en_deg = math.degrees(a0 + 2 * math.pi)
        cd.arc(bb, st_deg, en_deg, fill=c_draw + (255,), width=wdt)
        for ang in (a0 + g, a0 + 2 * math.pi):                 # round caps
            ex = c2[0] + R * SS * math.cos(ang); ey = c2[1] + R * SS * math.sin(ang)
            cd.ellipse([ex - wdt / 2, ey - wdt / 2, ex + wdt / 2, ey + wdt / 2], fill=c_draw + (255,))
        # glow
        gb = [ccx / GS - R / GS, ccy / GS - R / GS, ccx / GS + R / GS, ccy / GS + R / GS]
        gd.arc(gb, st_deg, en_deg, fill=tuple(int(c * (0.75 + 0.25 * l)) for c in col), width=int(5 + 4 * l))
    # ---- shockwaves + shards of escaped rings
    for j, te in enumerate(ESC_V):
        tt = vt - te
        if 0 <= tt < 0.9:
            col = ring_col(j)
            Rr = (ring_r(j) + 1400 * (1 - math.exp(-tt * 5.5))) * zoom
            a = max(0.0, 1 - tt / 0.6)
            ccx, ccy = T(0, 0); c2 = cp(ccx, ccy)
            if a > 0:
                cd.ellipse([c2[0] - Rr * SS, c2[1] - Rr * SS, c2[0] + Rr * SS, c2[1] + Rr * SS],
                           outline=tuple(int(255 * a * 0.9 + c * (1 - a)) if False else c for c in col) + (int(230 * a),), width=int((14 * a + 2) * SS))
                gd.ellipse([ccx / GS - Rr / GS, ccy / GS - Rr / GS, ccx / GS + Rr / GS, ccy / GS + Rr / GS], outline=tuple(int(c * a) for c in col), width=4)
            for (x0, y0, vx, vy, sz, rot, life) in SHARDS[j]:
                if tt > life: continue
                f = tt / life
                x = x0 + vx * tt; y = y0 + vy * tt + 900 * tt * tt
                px_, py_ = T(x, y)
                p2 = cp(px_, py_)
                ln = sz * 1.6 * zoom; ang = math.atan2(vy + 1800 * tt, vx)
                dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
                al = int(255 * (1 - f))
                cd.line([p2[0] - dx * SS, p2[1] - dy * SS, p2[0] + dx * SS, p2[1] + dy * SS], fill=col + (al,), width=int(sz * 0.55 * SS * (1 - f * .6)))
    # ---- impact sparks
    for (tb, _, rk, sp, px, py) in BOUNCES:
        ts = s - tb
        if 0 <= ts < 0.22:
            f = ts / 0.22; sx, sy = T(px, py); s2 = cp(sx, sy)
            col = ring_col(rk)
            r_ = (14 + 46 * f) * SS
            cd.ellipse([s2[0] - r_, s2[1] - r_, s2[0] + r_, s2[1] + r_], outline=(255, 255, 255, int(255 * (1 - f))), width=int((6 * (1 - f) + 1) * SS))
    # ---- ball trail + ball
    ccol = ring_col(min(cur, NR - 1))
    for n in range(14, 0, -1):
        sn = s - n * 0.0075
        if sn < 0: continue
        j = min(int(sn * SUB), len(ST) - 1)
        tx, ty = T(ST[j][0], ST[j][1]); t2 = cp(tx, ty)
        f = 1 - n / 14
        rr = BR * zoom * SS * (0.35 + 0.65 * f)
        cd.ellipse([t2[0] - rr, t2[1] - rr, t2[0] + rr, t2[1] + rr], fill=ccol + (int(150 * f * f),))
    bxs, bys = T(bx, by); b2 = cp(bxs, bys)
    rr = BR * zoom * SS
    gd.ellipse([bxs / GS - BR * zoom / GS * 2.6, bys / GS - BR * zoom / GS * 2.6, bxs / GS + BR * zoom / GS * 2.6, bys / GS + BR * zoom / GS * 2.6], fill=tuple(int(c * 0.9) for c in ccol))
    cd.ellipse([b2[0] - rr * 1.25, b2[1] - rr * 1.25, b2[0] + rr * 1.25, b2[1] + rr * 1.25], fill=ccol + (255,))
    cd.ellipse([b2[0] - rr, b2[1] - rr, b2[0] + rr, b2[1] + rr], fill=(255, 255, 255, 255))
    cd.ellipse([b2[0] - rr * .45, b2[1] - rr * .6, b2[0] + rr * .05, b2[1] - rr * .1], fill=(255, 255, 255, 255))
    # ---- compose
    glow = np.asarray(gl.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(10)), np.float32)
    fr = np.clip(fr + glow * 0.95, 0, 255)
    img = Image.fromarray(fr.astype(np.uint8)).convert('RGBA')
    crisp = cr.resize((W, Y1 - Y0), Image.BOX)
    img.alpha_composite(crisp, (0, Y0))
    # flash
    if 0 <= tau < 0.12: 
        fl = Image.new('RGBA', (W, H), (255, 255, 255, int(120 * (1 - tau / 0.12) * (2.0 if k_done == NR else 1.0))))
        img.alpha_composite(fl)
    # ---- UI text
    ui = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ov = fi / FPS
    esc_n = k_done
    final_ring = (esc_n == NR - 1)
    if k_done == NR and vt > ESC_V[-1] + 0.55:
        u_ = min(1, (vt - ESC_V[-1] - 0.55) / 0.25); sc_ = 1 + 0.25 * (1 - u_) ** 2
        text_c(ui, (540, 250), "IT ESCAPED!", 118, (255, 255, 255), 9, scale=sc_)
        text_c(ui, (540, 520), "9/9", 230, (120, 255, 190), 10, scale=sc_)
        text_c(ui, (540, 1500), "PART 2: 20 RINGS", 82, (255, 220, 60), 8, emo=0x1F608)
        text_c(ui, (540, 1610), "FOLLOW • " + HANDLE, 60, (255, 255, 255), 7)
    elif vt < 2.1:
        u_ = min(1, vt / 0.15); sc_ = 1.0 + 0.3 * (1 - u_) ** 2
        text_c(ui, (540, 240), "9 RINGS", 176, (255, 224, 70), 11, scale=sc_)
        text_c(ui, (540, 400), "CAN IT ESCAPE?", 118, (255, 255, 255), 9, scale=sc_)
    else:
        bump = 1 + 0.35 * punch
        if final_ring and vt - ESC_V[-2] < 1.5:
            text_c(ui, (540, 250), "LAST RING", 130, (255, 90, 110), 10, emo=0x1F630)
        elif final_ring:
            text_c(ui, (540, 250), "WILL IT MAKE IT?", 118, (255, 255, 255), 10)
        else:
            text_c(ui, (540, 250), f"RING {esc_n + 1}/9", 128, (255, 255, 255), 9, scale=bump)
        if final_ring and vt - ESC_V[-2] >= 1.5:
            text_c(ui, (540, 400), "1 = YES   •   2 = NO", 96, (255, 224, 70), 8, emo=0x1F447)
        elif esc_n in (4, 5) and vt - ESC_V[esc_n - 1] < 1.6 and esc_n >= 5:
            text_c(ui, (540, 400), "ONLY 4 LEFT!", 96, (255, 224, 70), 8)
    # progress pips
    if not (k_done == NR and vt > ESC_V[-1] + 0.55):
        for j in range(NR):
            x = 540 + (j - (NR - 1) / 2) * 52
            on = j < esc_n
            col = ring_col(j) if on else (60, 66, 90)
            r_ = 15 if not (j == esc_n - 1 and tau < 0.25) else 19
            ImageDraw.Draw(ui).ellipse([x - r_, 1500 - r_, x + r_, 1500 + r_], fill=col + (255,), outline=(255, 255, 255, 255) if on else (10, 12, 24, 255), width=3)
    img.alpha_composite(ui)
    return img.convert('RGB')

def _f(fi): return frame(fi).tobytes()

def render(out):
    tmp = out.replace('.mp4', '_v.mp4'); wav = out.replace('.mp4', '.wav')
    ev_v = [(vt_of(e[0]), e[1], e[2], e[3]) for e in EV]
    raudio.build(ev_v, DUR, ESC_V, slow=(V0, V1), out=wav)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp], stdin=subprocess.PIPE)
    with mp.Pool(4) as pool:
        for n, b in enumerate(pool.imap(_f, range(NF), chunksize=3)):
            p.stdin.write(b)
            if n % 60 == 0: print(n, '/', NF, flush=True)
    p.stdin.close(); p.wait()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-i', wav, '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out], check=True)

if __name__ == '__main__':
    print('duration', round(DUR, 2), 'frames', NF, 'escapes(video)', [round(x, 2) for x in ESC_V])
    if len(sys.argv) > 1 and sys.argv[1] == 'still':
        for t in sys.argv[2:]:
            frame(int(float(t) * FPS)).save(f'still_{t}.png')
    else:
        render(sys.argv[1] if len(sys.argv) > 1 else 'ring_escape.mp4')
