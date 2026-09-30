#!/usr/bin/env python3
"""Ring Escape v2 - DOUBLING: 1 ball, every ring that breaks doubles it (1 -> 512).
   python3 rrender2.py [still t...] | [out.mp4]"""
import sys, os, math, random, colorsys, subprocess, pickle, bisect, multiprocessing as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import raudio
from rsim2 import NR, SUB, BEAT, ring_r, brad, G

SEED = 1
FPS = 30
W, H = 1080, 1920
CX, CY = 540, 930
SS = 2
Y0, Y1 = 150, 1650
A = os.path.dirname(os.path.abspath(__file__)) + '/../assets/'
ANTON = A + 'anton.ttf'
EMO = A + 'emoji-datasource-twitter-16.0.0/package/img/twitter/64/'
HANDLE = '@ring.escape'

D = pickle.load(open(os.path.dirname(os.path.abspath(__file__)) + f'/sim2_{SEED}.pkl', 'rb'))
FR = D['frames']; RINGS = D['rings']; ESC = D['esc']; TF = ESC[-1]
T0S = [0.0] + ESC[:-1]                                        # stage start of each ring
BOUNCE_T = [b[0] for b in D['bounces']]
SLOW = 0.30
S0, S1 = TF - 0.6, TF + 0.3
KV = [0.0] + [BEAT * 1] + [BEAT * (3 + 2 * i) for i in range(7)]          # video times of breaks 0..7 (on the beat)
KS = [0.0] + ESC[:8]
V0 = KV[-1] + 2.08; KV.append(V0); KS.append(S0)
V1 = V0 + (S1 - S0) / SLOW
TFV = V0 + (TF - S0) / SLOW
TAIL = 2.6
DUR = TFV + TAIL
NF = int(DUR * FPS)

def st(vt):
    if vt < V0: return float(np.interp(vt, KV, KS))
    if vt < V1: return S0 + (vt - V0) * SLOW
    return S1 + (vt - V1)
def vt_of(s):
    if s < S0: return float(np.interp(s, KS, KV))
    if s < S1: return V0 + (s - S0) / SLOW
    return V1 + (s - S1)
ESC_V = [vt_of(e) for e in ESC]

def ring_col(k):
    h = (0.52 + 0.058 * k) % 1.0
    if k >= 7: h = 0.97 - 0.09 * (k - 7)
    r, g, b = colorsys.hsv_to_rgb(h, 0.68, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))
def gen_col(g, s=0.75):
    h = (0.52 + 0.075 * g) % 1.0
    r, gg, b = colorsys.hsv_to_rgb(h, s, 1.0)
    return (int(r * 255), int(gg * 255), int(b * 255))

def font(s): return ImageFont.truetype(ANTON, s)
_em = {}
def emoji(code, size):
    k = (code, size)
    if k not in _em: _em[k] = Image.open(EMO + f'{code:x}.png').convert('RGBA').resize((size, size), Image.LANCZOS)
    return _em[k]
def text_c(img, xy, s, size, fill=(255, 255, 255), stroke=8, sc=(8, 10, 24), emo=None, scale=1.0):
    f = font(int(size * scale)); d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), s, font=f, stroke_width=int(stroke * scale))
    w = bb[2] - bb[0]; es = int(size * scale * 0.95) if emo else 0
    tot = w + (es + 14 if emo else 0)
    x = xy[0] - tot / 2 - bb[0]; y = xy[1] - (bb[3] - bb[1]) / 2 - bb[1]
    d.text((x, y), s, font=f, fill=fill, stroke_width=int(stroke * scale), stroke_fill=sc)
    if emo: img.alpha_composite(emoji(emo, es), (int(x + w + 14 + bb[0]), int(xy[1] - es / 2)))

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
BG_BASE = np.clip(1.0 - np.hypot(XX - CX, YY - CY) / 900.0, 0, 1) ** 1.6
VIG = np.clip(1.15 - np.hypot((XX - W / 2) / (W * .75), (YY - H / 2) / (H * .62)) ** 2 * .55, .25, 1.0)[..., None]
def background(k, pulse):
    col = np.array(ring_col(min(k, NR - 1)), np.float32) / 255
    img = np.array([7, 9, 22], np.float32)[None, None, :] + BG_BASE[..., None] * col[None, None, :] * 255 * (0.10 + 0.14 * pulse)
    return np.clip(img * VIG, 0, 255)

_pr = random.Random(77)
SHARDS = []
for j in range(NR):
    R = ring_r(j); lst = []
    for i in range(46):
        a = _pr.uniform(0, 2 * math.pi); sp = _pr.uniform(500, 1250)
        lst.append((R * math.cos(a), R * math.sin(a), math.cos(a) * sp + _pr.uniform(-150, 150), math.sin(a) * sp + _pr.uniform(-150, 150) - 250, _pr.uniform(10, 26), _pr.uniform(0.55, 1.0)))
    SHARDS.append(lst)

def lerp(a, b, u): return a + (b - a) * u
def ring_angle(k, t): return RINGS[k]['a0'] + RINGS[k]['w'] * (t - T0S[k])

def fmt(n): return f'{n:,}'

def frame(fi):
    vt = fi / FPS; s = st(vt)
    i = max(0, min(int(s * SUB) - 1, len(FR) - 2)); u = min(1.0, max(0.0, s * SUB - (i + 1)))
    k, _, P, gens, _t = FR[i]
    k2, _, P2, gens2, _ = FR[i + 1]
    if len(P2) == len(P) and k2 == k: P = P + (P2 - P) * u
    N = len(P)
    k_done = sum(1 for e in ESC_V if e <= vt)
    cur = min(k, NR - 1)
    r_ball = brad(cur)
    beat = (vt % BEAT) / BEAT
    in_slow = V0 <= vt < V1 + 0.25
    pulse = 0.0 if in_slow else math.exp(-beat * 5.0)
    last_e = max([e for e in ESC_V if e <= vt], default=-9); tau = vt - last_e
    punch = math.exp(-tau / 0.13) if tau >= 0 else 0
    shake = (14 if k_done < NR else 34) * math.exp(-tau / 0.16) if tau >= 0 else 0
    zoom = 1.0 + 0.045 * punch * (1.7 if k_done == NR else 1) + 0.012 * pulse
    if vt < 0.5: zoom *= 1 + 0.16 * (1 - vt / 0.5) ** 2
    if V0 - 0.3 <= vt < V1 + 0.3:
        w = min(1, (vt - (V0 - 0.3)) / 0.4) * min(1, (V1 + 0.3 - vt) / 0.3); zoom *= 1 + 0.16 * w
    rng = random.Random(fi); ox = rng.uniform(-1, 1) * shake; oy = rng.uniform(-1, 1) * shake
    def T(x, y): return (CX + ox + x * zoom, CY + oy + y * zoom)
    def cp(x, y): return (x * SS, (y - Y0) * SS)

    fr = background(cur if k_done < NR else NR - 1, pulse)
    GS = 4
    gl = Image.new('RGB', (W // GS, H // GS), (0, 0, 0)); gd = ImageDraw.Draw(gl)
    cr = Image.new('RGBA', (W * SS, (Y1 - Y0) * SS), (0, 0, 0, 0)); cd = ImageDraw.Draw(cr)
    # bounce light on the live ring
    lo = bisect.bisect_left(BOUNCE_T, s - 0.08); hi = bisect.bisect_right(BOUNCE_T, s)
    lit_amt = min(1.0, (hi - lo) / 3.0)
    ccx, ccy = T(0, 0); c2 = cp(ccx, ccy)
    for kk in range(NR):
        if kk < k_done: continue
        R = ring_r(kk) * zoom; col = ring_col(kk)
        l = lit_amt if kk == cur and k_done < NR else 0.0
        a0 = ring_angle(kk, s); g = RINGS[kk]['gap']
        bb = [c2[0] - R * SS, c2[1] - R * SS, c2[0] + R * SS, c2[1] + R * SS]
        wdt = int((9 + 5 * l) * SS)
        cdr = tuple(min(255, int(c + (255 - c) * l * 0.7)) for c in col)
        sd, ed = math.degrees(a0 + g), math.degrees(a0 + 2 * math.pi)
        cd.arc(bb, sd, ed, fill=cdr + (255,), width=wdt)
        for ang in (a0 + g, a0 + 2 * math.pi):
            ex = c2[0] + R * SS * math.cos(ang); ey = c2[1] + R * SS * math.sin(ang)
            cd.ellipse([ex - wdt / 2, ey - wdt / 2, ex + wdt / 2, ey + wdt / 2], fill=cdr + (255,))
        gd.arc([ccx / GS - R / GS, ccy / GS - R / GS, ccx / GS + R / GS, ccy / GS + R / GS], sd, ed, fill=tuple(int(c * (0.75 + 0.25 * l)) for c in col), width=int(5 + 4 * l))
    # shockwaves + shards
    for j, te in enumerate(ESC_V):
        tt = vt - te
        if 0 <= tt < 0.9:
            col = ring_col(j); Rr = (ring_r(j) + 1400 * (1 - math.exp(-tt * 5.5))) * zoom; a = max(0.0, 1 - tt / 0.6)
            if a > 0:
                cd.ellipse([c2[0] - Rr * SS, c2[1] - Rr * SS, c2[0] + Rr * SS, c2[1] + Rr * SS], outline=col + (int(230 * a),), width=int((14 * a + 2) * SS))
                gd.ellipse([ccx / GS - Rr / GS, ccy / GS - Rr / GS, ccx / GS + Rr / GS, ccy / GS + Rr / GS], outline=tuple(int(c * a) for c in col), width=4)
            for (x0, y0, vx, vy, sz, life) in SHARDS[j]:
                if tt > life: continue
                f = tt / life; x = x0 + vx * tt; y = y0 + vy * tt + 900 * tt * tt
                p2 = cp(*T(x, y)); ln = sz * 1.6 * zoom; ang = math.atan2(vy + 1800 * tt, vx)
                dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
                cd.line([p2[0] - dx * SS, p2[1] - dy * SS, p2[0] + dx * SS, p2[1] + dy * SS], fill=col + (int(255 * (1 - f)),), width=int(sz * 0.55 * SS * (1 - f * .6)))
    # ---- balls (trail = line to where it was 20 ms ago)
    ip = max(0, i - 5)
    Pp = FR[ip][2] if len(FR[ip][2]) == N else P
    rr = r_ball * zoom
    for n in range(N):
        x, y = P[n]; px, py = Pp[n]
        col = gen_col(gens[n]); bx_, by_ = T(x, y)
        if not (-60 < bx_ < W + 60 and -60 < by_ < H + 60): continue
        b2 = cp(bx_, by_); q2 = cp(*T(px, py))
        gd.ellipse([bx_ / GS - rr * 2.4 / GS, by_ / GS - rr * 2.4 / GS, bx_ / GS + rr * 2.4 / GS, by_ / GS + rr * 2.4 / GS], fill=tuple(int(c * (0.9 if N < 40 else 0.5)) for c in col))
        if abs(b2[0] - q2[0]) + abs(b2[1] - q2[1]) > 2:
            cd.line([q2[0], q2[1], b2[0], b2[1]], fill=col + (150,), width=max(2, int(rr * 1.5 * SS)))
        R_ = rr * SS
        cd.ellipse([b2[0] - R_ * 1.2, b2[1] - R_ * 1.2, b2[0] + R_ * 1.2, b2[1] + R_ * 1.2], fill=col + (255,))
        cd.ellipse([b2[0] - R_ * .5, b2[1] - R_ * .5, b2[0] + R_ * .5, b2[1] + R_ * .5], fill=(255, 255, 255, 255))
    glow = np.asarray(gl.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(10)), np.float32)
    fr = np.clip(fr + glow * 0.95, 0, 255)
    img = Image.fromarray(fr.astype(np.uint8)).convert('RGBA')
    img.alpha_composite(cr.resize((W, Y1 - Y0), Image.BOX), (0, Y0))
    if 0 <= tau < 0.12:
        img.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(70 * (1 - tau / 0.12) * (1.8 if k_done == NR else 1.0)))))

    # ---- UI
    ui = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    nballs = 2 ** k_done
    bump = 1 + 0.35 * punch
    cnt_col = (255, 255, 255) if k_done < 5 else ((255, 224, 70) if k_done < 8 else (255, 110, 170))
    if k_done == NR: cnt_col = (120, 255, 190)
    text_c(ui, (540, 250), f'{fmt(nballs)} BALL' + ('S' if nballs > 1 else ''), 170, cnt_col, 11, scale=bump)
    if vt < 2.3:
        u_ = min(1, vt / 0.15)
        text_c(ui, (540, 400), 'DOUBLES EVERY RING', 104, (255, 255, 255), 9, scale=1.0 + 0.3 * (1 - u_) ** 2)
    elif k_done == NR:
        text_c(ui, (540, 400), 'THEY ALL MADE IT', 100, (255, 255, 255), 9, emo=0x1F92F)
    elif k_done == NR - 1:
        text_c(ui, (540, 400), 'LAST RING. ONE GAP.', 100, (255, 90, 110), 9)
    else:
        text_c(ui, (540, 400), f'RING {k_done + 1}/9', 92, (255, 224, 70), 8)
    # giant x2 at each break
    if k_done > 0 and tau < 0.55 and k_done < NR + 1:
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        uu = min(1, tau / 0.10); sc = (1.6 - 0.6 * uu) * (1 + 0.15 * (tau / 0.55))
        text_c(lay, (540, 930), '×2' if k_done < NR else '×2', 330, ring_col(k_done - 1), 14, scale=sc)
        al = max(0.0, 1 - tau / 0.55) ** 0.7
        lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al * 0.9)))
        ui.alpha_composite(lay)
    # pips / end card
    if k_done == NR and vt > ESC_V[-1] + 0.9:
        text_c(ui, (540, 1440), 'PART 2: 20 RINGS', 84, (255, 224, 70), 8)
        text_c(ui, (540, 1540), '= 1,048,576 BALLS', 76, (255, 255, 255), 8, emo=0x1F633)
        text_c(ui, (540, 1640), 'FOLLOW • ' + HANDLE, 56, (200, 205, 225), 6)
    else:
        for j in range(NR):
            x = 540 + (j - (NR - 1) / 2) * 52; on = j < k_done
            col = ring_col(j) if on else (60, 66, 90)
            r_ = 15 if not (j == k_done - 1 and tau < 0.25) else 19
            ImageDraw.Draw(ui).ellipse([x - r_, 1500 - r_, x + r_, 1500 + r_], fill=col + (255,), outline=(255, 255, 255, 255) if on else (10, 12, 24, 255), width=3)
    img.alpha_composite(ui)
    return img.convert('RGB')

def _f(fi): return frame(fi).tobytes()

def render(out):
    tmp = out.replace('.mp4', '_v.mp4'); wav = out.replace('.mp4', '.wav')
    ev_v = [(vt_of(b[0]), 'b', b[1], b[2]) for b in D['bounces']]
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
    print('duration', round(DUR, 2), 'frames', NF, 'breaks(video)', [round(x, 2) for x in ESC_V], 'V0', round(V0, 2), 'V1', round(V1, 2))
    if len(sys.argv) > 1 and sys.argv[1] == 'still':
        for t in sys.argv[2:]: frame(int(float(t) * FPS)).save(f'still2_{t}.png')
    else:
        render(sys.argv[1] if len(sys.argv) > 1 else 'ring_escape2.mp4')
