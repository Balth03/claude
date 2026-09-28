"""Procedural sound design for the Opus 5.5 piece.

No samples, no music: every sound is synthesised from oscillators and noise, and placed
from the same src/timeline.json cues that drive the picture, so sync is exact by design.

    python3 audio.py  ->  build/sound.wav (48 kHz, stereo, 24-bit)
"""
import json
import os

import numpy as np
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(ROOT, "src", "timeline.json")))
DUR = TL["duration"]
N = int(DUR * SR)
rng = np.random.default_rng(1234)

dry = np.zeros((2, N + SR * 4))
wet = np.zeros((2, N + SR * 4))  # reverb send


def tt(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR))


def add(x, t, pan=0.0, gain=1.0, send=0.0):
    """Place a mono signal at time t (seconds) with equal-power pan and reverb send."""
    i = int(round(t * SR))
    if i < 0:
        x = x[-i:]
        i = 0
    n = min(len(x), dry.shape[1] - i)
    if n <= 0:
        return
    a = (pan + 1) * np.pi / 4
    for ch, g in enumerate((np.cos(a), np.sin(a))):
        dry[ch, i:i + n] += x[:n] * g * gain
        wet[ch, i:i + n] += x[:n] * g * gain * send


def add_st(l, r, t, gain=1.0, send=0.0):
    i = int(round(t * SR))
    n = min(len(l), dry.shape[1] - i)
    for ch, x in enumerate((l, r)):
        dry[ch, i:i + n] += x[:n] * gain
        wet[ch, i:i + n] += x[:n] * gain * send


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="high", fs=SR, output="sos"), x)


def sweep_filter(x, f0, f1, width=0.6, curve=1.0):
    """Band-pass whose centre glides from f0 to f1 (log scale), done in the STFT domain."""
    nper = 1024
    f, fr, Z = signal.stft(x, fs=SR, nperseg=nper, noverlap=nper * 3 // 4, boundary="even")
    u = np.clip(fr / (len(x) / SR), 0, 1) ** curve
    fc = np.exp(np.log(f0) + (np.log(f1) - np.log(f0)) * u)
    lf = np.log(np.maximum(f, 1.0))[:, None]
    mask = np.exp(-0.5 * ((lf - np.log(fc)[None, :]) / width) ** 2)
    _, y = signal.istft(Z * mask, fs=SR, nperseg=nper, noverlap=nper * 3 // 4, boundary=True)
    return y[: len(x)]


def chirp_sine(f0, f1, d, shape="exp"):
    t = tt(d)
    if shape == "exp":
        f = f0 * (f1 / f0) ** (t / d)
    else:
        f = f0 + (f1 - f0) * (t / d)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def kick(f_hi=180, f_lo=50, drop=35, decay=0.3, d=0.8, click=0.5):
    t = tt(d)
    f = f_lo + (f_hi - f_lo) * np.exp(-t * drop)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    cl = hp(noise(d), 2000) * np.exp(-t * 180) * click
    return np.tanh((body + cl) * 1.6) / np.tanh(1.6)


def fade(x, a=0.002, b=0.01):
    n = len(x)
    ia, ib = int(a * SR), int(b * SR)
    e = np.ones(n)
    if ia:
        e[:ia] = np.linspace(0, 1, ia)
    if ib:
        e[-ib:] *= np.linspace(1, 0, ib)
    return x * e


# ------------------------------------------------------------------ sound palette
def s_key(c):
    d = 0.05
    t = tt(d)
    v = c["v"]
    soft = c.get("soft", 0)
    x = hp(noise(d), 1800 + 1500 * v) * np.exp(-t * 260)
    x += np.sin(2 * np.pi * (2400 + 1400 * v) * t) * np.exp(-t * 320) * 0.5
    x += np.sin(2 * np.pi * (180 + 40 * v) * t) * np.exp(-t * 90) * 0.35
    add(fade(x), c["t"], pan=(v - 0.5) * 0.5, gain=0.16 if soft else 0.22, send=0.12)


def s_tick(c):
    d = 0.03
    t = tt(d)
    x = hp(noise(d), 3000) * np.exp(-t * 400) + np.sin(2 * np.pi * (3200 + 900 * c["v"]) * t) * np.exp(-t * 500) * 0.4
    add(fade(x), c["t"], pan=(c["v"] - 0.5) * 1.2, gain=0.2, send=0.05)


def s_suck(c):
    d = c["d"]
    t = tt(d)
    x = sweep_filter(noise(d), 400, 7000, 0.5, curve=2.0) * (t / d) ** 3 * 2.2
    x += chirp_sine(90, 420, d) * (t / d) ** 2 * 0.35
    add(fade(x, 0.01, 0.004), c["t"], gain=0.5, send=0.25)


def s_bigbang(c):
    d = 2.6
    t = tt(d)
    body = kick(f_hi=160, f_lo=38, drop=18, decay=0.9, d=d, click=1.0)
    crash = lp(noise(d), 5000) * np.exp(-t * 2.2) * 0.55 + hp(noise(d), 4000) * np.exp(-t * 6) * 0.35
    down = sweep_filter(noise(d), 6000, 120, 0.7, curve=0.5) * np.exp(-t * 1.4) * 1.4
    x = np.tanh((body * 1.2 + crash + down) * 1.3)
    add(x, c["t"], gain=0.95, send=0.5)
    # stereo width: decorrelated debris
    l = hp(noise(d), 1500) * np.exp(-t * 4) * 0.25
    r = hp(noise(d), 1500) * np.exp(-t * 4) * 0.25
    add_st(l, r, c["t"], gain=0.6, send=0.4)


def s_word(c):
    i, p = c["i"], c["p"]
    d = 0.5
    t = tt(d)
    big = i in (0, 1, 8, 13, 15)
    x = kick(f_hi=190 + 60 * p, f_lo=48 + 10 * p, drop=42, decay=0.2 if not big else 0.32, d=d, click=0.7)
    snap = bp(noise(d), 1200 + 1500 * p, 7000) * np.exp(-t * 38) * 0.7
    x = x + snap
    add(x, c["t"], pan=((i % 3) - 1) * 0.25, gain=0.62 if big else 0.5, send=0.18)
    # short air whoosh into each word
    w = sweep_filter(noise(0.12), 800, 5000, 0.5, curve=1.5) * np.linspace(0, 1, int(0.12 * SR)) ** 2
    add(w, c["t"] - 0.12, pan=-((i % 3) - 1) * 0.4, gain=0.25, send=0.1)


def s_whoosh(c):
    d, up, big = c["d"], c.get("up", 1), c.get("big", 0)
    t = tt(d)
    if up:
        x = sweep_filter(noise(d), 200 if big else 500, 9000, 0.55, curve=1.6) * (t / d) ** 2.2
        x = fade(x, 0.005, 0.004)
    else:
        x = sweep_filter(noise(d), 7000, 250, 0.6, curve=0.6) * np.exp(-t / (d * 0.5)) * np.minimum(1, t / 0.03)
        x = fade(x, 0.003, 0.05)
    if big:
        x += chirp_sine(60, 240, d) * (t / d) ** 2 * 0.4
    add(x, c["t"], gain=0.75 if big else 0.5, send=0.3)


def s_swell(c):
    d = c["d"]
    t = tt(d)
    env = np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 0.2)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.35 * t)
    tone = (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 55.4 * t + 1) + 0.35 * np.sin(2 * np.pi * 110.3 * t)) * 0.22
    air = sweep_filter(noise(d), 300, 1400, 0.5) * (0.35 + 0.35 * lfo) * 0.5
    x = (tone + air) * env
    l = x + lp(noise(d), 600) * env * 0.05
    r = x * 0.97 + lp(noise(d), 600) * env * 0.05
    add_st(l, r, c["t"], gain=0.5, send=0.35)


def s_soft(c):
    d = 0.9
    t = tt(d)
    x = kick(f_hi=120, f_lo=52, drop=20, decay=0.35, d=d, click=0.15) * 0.8
    x += sweep_filter(noise(d), 3000, 600, 0.5) * np.exp(-t * 7) * 0.4
    add(x, c["t"], gain=0.45, send=0.4)


def s_ping(c):
    d = 0.8
    t = tt(d)
    f = 1100 + 2200 * c["p"]
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 12)) * np.exp(-t * 7)
    add(fade(x, 0.001, 0.05), c["t"], pan=c["pan"] * 0.8, gain=0.07, send=0.55)


def s_flashhit(c):
    d = 1.6
    t = tt(d)
    x = kick(f_hi=200, f_lo=45, drop=26, decay=0.5, d=d, click=1.0)
    x += lp(noise(d), 7000) * np.exp(-t * 5) * 0.5
    add(np.tanh(x * 1.2), c["t"], gain=0.8, send=0.45)


def s_pop(c):
    d = 0.12
    t = tt(d)
    x = chirp_sine(500, 1100, d) * np.exp(-t * 45) + hp(noise(d), 2500) * np.exp(-t * 300) * 0.4
    x += np.sin(2 * np.pi * 90 * t) * np.exp(-t * 40) * 0.6
    add(fade(x), c["t"], pan=rng.uniform(-0.6, 0.6), gain=0.28, send=0.2)


def s_blip(c):
    d = 0.06
    t = tt(d)
    f = 1300 + 900 * c["k"]
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 60)
    add(fade(x, 0.001, 0.01), c["t"], pan=rng.uniform(-0.3, 0.3), gain=0.075, send=0.2)


def s_riser(c):
    d, lo, hi, q = c["d"], c["lo"], c["hi"], c["q"]
    t = tt(d)
    u = t / d
    env = u ** 2.4
    x = sweep_filter(noise(d), lo * 2, hi * 4, 0.45, curve=1.8) * env * 1.4
    trem_rate = 4 + 26 * u ** 2
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(trem_rate) / SR)
    x = x * trem
    tone = chirp_sine(lo, hi, d) + 0.5 * chirp_sine(lo * 1.5, hi * 1.5, d)
    x += tone * env * 0.22 * q
    add_st(fade(x, 0.02, 0.003), fade(np.roll(x, 90), 0.02, 0.003), c["t"], gain=0.55 + 0.25 * q, send=0.2)


def s_stamp(c):
    d = 1.8
    t = tt(d)
    x = kick(f_hi=170, f_lo=42, drop=30, decay=0.45, d=d, click=1.0) * 1.1
    clank = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((320, 0.5), (873, 0.4), (1451, 0.3), (2213, 0.25), (3407, 0.15)))
    x += clank * np.exp(-t * 9) * 0.45
    x += bp(noise(d), 800, 6000) * np.exp(-t * 25) * 0.6
    add(np.tanh(x * 1.3), c["t"], gain=0.85, send=0.45)


def s_glitch(c):
    d = c["d"]
    n = int(d * SR)
    x = np.zeros(n)
    seg = int(0.022 * SR)
    for k in range(0, n, seg):
        m = min(seg, n - k)
        tk = np.arange(m) / SR
        f = rng.uniform(80, 2400)
        sq = np.sign(np.sin(2 * np.pi * f * tk))
        crush = np.round(noise(m / SR) * 3) / 3 * rng.uniform(0, 0.6)
        x[k:k + m] = (sq * rng.uniform(0.2, 0.8) + crush) * (rng.random() > 0.15)
    x = np.round(x * 6) / 6
    add(fade(lp(x, 9000), 0.002, 0.005), c["t"], gain=0.28, send=0.1)


def s_rev(c):
    d = c["d"]
    t = tt(d)
    x = hp(noise(d), 3000) * (t / d) ** 3 + sweep_filter(noise(d), 500, 5000, 0.5) * (t / d) ** 2 * 0.6
    add(fade(x, 0.01, 0.003), c["t"], gain=0.4, send=0.3)


def s_morph(c):
    d = 1.2
    t = tt(d)
    x = chirp_sine(260, 55, 0.35)
    x = np.concatenate([x, np.zeros(int(d * SR) - len(x))]) * np.exp(-t * 4)
    x += sweep_filter(noise(d), 5000, 300, 0.6, curve=0.5) * np.exp(-t * 5) * 0.7
    x += kick(f_hi=120, f_lo=45, drop=25, decay=0.3, d=d, click=0.3) * 0.7
    add(x, c["t"], gain=0.55, send=0.5)


def s_shimmer(c):
    soft = c.get("soft", 0)
    d = 2.2
    t = tt(d)
    l = np.zeros(len(t))
    r = np.zeros(len(t))
    for k in range(14):
        f = rng.uniform(2200, 6500)
        dl = rng.uniform(0, 0.5)
        e = np.where(t >= dl, np.exp(-(t - dl) * rng.uniform(2.5, 5)), 0) * np.minimum(1, np.maximum(0, (t - dl) / 0.01))
        s = np.sin(2 * np.pi * f * t) * e * 0.1
        p = rng.uniform(0, 1)
        l += s * np.cos(p * np.pi / 2)
        r += s * np.sin(p * np.pi / 2)
    add_st(l, r, c["t"], gain=0.45 if soft else 0.6, send=0.7)


def s_warp(c):
    d = 1.4
    t = tt(d)
    x = sweep_filter(noise(d), 6000, 150, 0.7, curve=0.5) * np.exp(-t * 2.5) * np.minimum(1, t / 0.02)
    x += kick(f_hi=140, f_lo=40, drop=12, decay=0.6, d=d, click=0.8) * 0.9
    add(np.tanh(x), c["t"], gain=0.8, send=0.4)
    # engine rumble running under the whole warp (riser adds the rise)
    s6 = TL["s6"]
    dd = s6["collapse"] - s6["start"]
    tr = tt(dd)
    u = tr / dd
    rumble = lp(noise(dd), 160) * 3 * (0.3 + 0.7 * u ** 1.5)
    rumble += np.sin(2 * np.pi * np.cumsum(38 + 40 * u ** 2) / SR) * 0.35 * (0.3 + 0.7 * u)
    add(fade(rumble, 0.3, 0.004), s6["start"], gain=0.5, send=0.1)


def s_ring(c):
    i = c["i"]
    d = 0.32
    t = tt(d)
    # pass-by: rises into the pass point (at 60% of the sound), doppler drop after
    tp = d * 0.6
    env = np.where(t < tp, (t / tp) ** 3, np.exp(-(t - tp) * 22))
    x = sweep_filter(noise(d), 2500, 600, 0.45, curve=1.0) * env
    x += kick(f_hi=110, f_lo=50, drop=30, decay=0.12, d=d, click=0.2) * np.concatenate([np.zeros(int(tp * SR)), np.ones(len(t) - int(tp * SR))]) * 0.6
    side = 1 if i % 2 else -1
    pan_env = np.clip(np.where(t < tp, -side * (1 - t / tp), side * (t - tp) / (d - tp)), -1, 1)
    a = (pan_env + 1) * np.pi / 4
    add_st(x * np.cos(a), x * np.sin(a), c["t"] - tp, gain=0.55 + 0.03 * i, send=0.2)


def s_implode(c):
    d = c["d"]
    t = tt(d)
    u = t / d
    x = sweep_filter(noise(d), 300, 12000, 0.5, curve=2.5) * u ** 2 * 1.6
    x += chirp_sine(120, 1800, d) * u ** 3 * 0.35
    add(fade(x, 0.01, 0.002), c["t"], gain=0.8, send=0.0)


def s_inhale(c):
    d = c["d"]
    t = tt(d)
    u = t / d
    x = hp(noise(d), 5000) * u ** 4 * 0.5
    # reversed hit sucking into the boom
    rv = kick(f_hi=200, f_lo=60, drop=30, decay=0.12, d=d, click=1.0)[::-1] * u ** 6 * 0.35
    add(fade(x + rv, 0.02, 0.002), c["t"], gain=0.5, send=0.0)


def s_boom(c):
    d = 6.5
    t = tt(d)
    sub = np.sin(2 * np.pi * np.cumsum(34 + 110 * np.exp(-t * 9)) / SR) * np.exp(-t / 1.6)
    punch = kick(f_hi=220, f_lo=50, drop=40, decay=0.25, d=d, click=1.0)
    blast = sweep_filter(noise(d), 9000, 90, 0.8, curve=0.35) * np.exp(-t / 0.75) * 1.3
    crackle = hp(noise(d), 3000) * (rng.random(len(t)) > 0.995) * np.exp(-t * 1.8) * 3
    x = np.tanh((sub * 1.3 + punch * 0.9 + blast) * 1.4) + crackle * 0.3
    add(x, c["t"], gain=1.0, send=0.6)
    l = lp(noise(d), 2500) * np.exp(-t / 0.9) * 0.35
    r = lp(noise(d), 2500) * np.exp(-t / 0.9) * 0.35
    add_st(l, r, c["t"], gain=0.7, send=0.6)
    # after-glow: low warm air under the title, fading with the picture
    s7 = TL["s7"]
    dd = s7["black"] - c["t"] + 0.3
    ta = tt(dd)
    env = np.minimum(1, ta / 1.5) * np.clip((s7["black"] + 0.3 - c["t"] - ta) / (s7["black"] - s7["fade"]), 0, 1)
    glow = sweep_filter(noise(dd), 180, 700, 0.5) * 0.5 + np.sin(2 * np.pi * 55 * ta) * 0.12 + np.sin(2 * np.pi * 82.4 * ta) * 0.06
    add_st(glow * env, np.roll(glow, 400) * env, c["t"], gain=0.2, send=0.3)


PLAY = {
    "key": s_key, "tick": s_tick, "suck": s_suck, "bigbang": s_bigbang, "word": s_word, "whoosh": s_whoosh,
    "swell": s_swell, "soft": s_soft, "ping": s_ping, "flashHit": s_flashhit, "pop": s_pop, "blip": s_blip,
    "riser": s_riser, "stamp": s_stamp, "glitch": s_glitch, "rev": s_rev, "morph": s_morph, "shimmer": s_shimmer,
    "warp": s_warp, "ring": s_ring, "implode": s_implode, "inhale": s_inhale, "boom": s_boom,
}

def machine_bed():
    # low, pulsing machine-room bed under the build scene so it never drops into a hole
    s4 = TL["s4"]
    d = s4["stamp"] - s4["start"]
    t = tt(d)
    env = np.minimum(1, t / 0.4) * np.minimum(1, (d - t) / 0.05)
    pulse = 0.55 + 0.45 * np.sin(2 * np.pi * 4.0 * t) ** 2
    x = lp(noise(d), 220) * 2.2 * pulse + np.sin(2 * np.pi * 46 * t) * 0.25 + sweep_filter(noise(d), 900, 1600, 0.35) * 0.12
    add_st(x * env, np.roll(x, 300) * env, s4["start"], gain=0.42, send=0.15)


machine_bed()
missing = sorted({c["type"] for c in TL["cues"]} - PLAY.keys())
assert not missing, f"no sound for cue types: {missing}"
for c in TL["cues"]:
    PLAY[c["type"]](c)

# ------------------------------------------------------------------ reverb (synthetic stereo IR)
ir_len = 2.4
ti = tt(ir_len)
ir = []
for ch in range(2):
    n = rng.standard_normal(len(ti)) * np.exp(-ti * 3.2)
    n = lp(n, 6000) * (1 - np.exp(-ti * 200))
    ir.append(n / np.sqrt(np.sum(n ** 2)))
rev = np.stack([signal.fftconvolve(wet[ch], ir[ch])[: dry.shape[1]] for ch in range(2)])
mix = dry + rev * 0.9

# the held breath before the boom must be (almost) silent: duck everything but the inhale
s6 = TL["s6"]
a, b = int(s6["dark"] * SR), int(s6["end"] * SR)
mix[:, a:b] *= np.linspace(0.15, 0.4, b - a)

mix = hp(mix, 25)
mix = mix[:, :N]
# gentle bus saturation, then peak-normalise to -1 dBFS
mix = np.tanh(mix * 0.9)
mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))
# tiny fade at both ends to avoid clicks
f = int(0.005 * SR)
mix[:, :f] *= np.linspace(0, 1, f)
mix[:, -int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))

os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
out = os.path.join(ROOT, "build", "sound.wav")
pcm = np.clip(mix.T, -1, 1)
pcm24 = (pcm * (2 ** 23 - 1)).astype(np.int32)
import wave  # noqa: E402

with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(3)
    w.setframerate(SR)
    b24 = pcm24.astype("<i4").tobytes()
    # keep the 3 low bytes of each little-endian int32
    arr = np.frombuffer(b24, dtype=np.uint8).reshape(-1, 4)[:, :3]
    w.writeframes(arr.tobytes())
rms = 20 * np.log10(np.sqrt(np.mean(mix ** 2)) + 1e-12)
print(f"sound: {out}  {DUR:.1f}s  {len(TL['cues'])} cues  peak -1.0 dBFS  rms {rms:.1f} dBFS")
