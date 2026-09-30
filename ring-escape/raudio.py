"""Ring Escape - music. Every bounce plays the next note of a hook; escapes lift the key. numpy only (+scipy)."""
import numpy as np, math, wave
from scipy import signal
SR = 48000
BPM = 132.0
BEAT = 60.0 / BPM
GRID = BEAT / 8                       # 1/32 note: bounce notes snap to it (max +-28 ms)
A3 = 220.0
MINOR = [0, 2, 3, 5, 7, 8, 10]        # A natural minor
PROG = [0, 5, 2, 6]                   # Am F C G (scale degrees)

def deg_hz(d, shift=0, base=A3):
    o, i = divmod(d, 7)
    return base * 2 ** ((MINOR[i] + 12 * o + shift) / 12)

def bell(f, dur, vel=1.0, bright=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    env = np.exp(-t * 6.0)
    idx = 2.2 * bright * np.exp(-t * 9)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * 2 * t)) * env
    y += 0.35 * np.sin(2 * np.pi * f * 4.01 * t) * np.exp(-t * 18)
    y += 0.25 * np.sin(2 * np.pi * f * 0.5 * t) * np.exp(-t * 4)   # warmth
    a = int(0.002 * SR); y[:a] *= np.linspace(0, 1, a)
    return y * vel

def pluck(f, dur, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * k * t) * (1 / k) ** 1.3 for k in range(1, 8))
    y *= np.exp(-t * 7)
    return y * vel * 0.5

def kick(dur=0.32):
    n = int(dur * SR); t = np.arange(n) / SR
    ph = 2 * np.pi * (48 * t + 110 * (1 - np.exp(-t * 32)) / 32 * 1.0)
    y = np.sin(ph) * np.exp(-t * 11)
    y += 0.5 * np.exp(-t * 220) * np.sign(np.sin(2 * np.pi * 900 * t))
    return y

def hat(dur=0.09, open_=False):
    n = int((0.22 if open_ else dur) * SR); t = np.arange(n) / SR
    x = np.random.RandomState(4).randn(n)
    sos = signal.butter(4, 7000 / (SR / 2), 'high', output='sos')
    return signal.sosfilt(sos, x) * np.exp(-t * (18 if open_ else 55)) * 0.5

def clap(dur=0.25):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.random.RandomState(9).randn(n)
    sos = signal.butter(2, [1200 / (SR / 2), 6500 / (SR / 2)], 'band', output='sos')
    x = signal.sosfilt(sos, x)
    env = np.exp(-t * 22) + 0.7 * np.exp(-np.maximum(t - 0.012, 0) * 22) * (t > 0.012) + 0.5 * np.exp(-np.maximum(t - 0.024, 0) * 22) * (t > 0.024)
    return x * env * 0.8

def riser(dur, f0=300, f1=6000):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.random.RandomState(1).randn(n)
    out = np.zeros(n)
    # swept band-pass in blocks
    B = 1024
    for i in range(0, n, B):
        fc = f0 * (f1 / f0) ** (i / n)
        sos = signal.butter(2, [fc * 0.7 / (SR / 2), min(fc * 1.3 / (SR / 2), 0.99)], 'band', output='sos')
        out[i:i + B] = signal.sosfilt(sos, x[i:i + B])
    return out * (t / dur) ** 2 * 0.9

def boom(dur=1.6):
    n = int(dur * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * (38 + 90 * np.exp(-t * 6)) * t) * np.exp(-t * 2.0)
    x = np.random.RandomState(2).randn(n)
    sos = signal.butter(2, 3500 / (SR / 2), 'low', output='sos')
    y += 0.5 * signal.sosfilt(sos, x) * np.exp(-t * 2.5)
    return y

def scratch(dur=0.42):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 1100 * np.exp(-t * 6.5) + 60
    y = signal.sawtooth(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
    x = np.random.RandomState(6).randn(n)
    sos = signal.butter(2, [800 / (SR / 2), 7000 / (SR / 2)], 'band', output='sos')
    return (0.6 * y + 0.5 * signal.sosfilt(sos, x) * np.exp(-t * 9)) * 0.9

def airhorn(dur=0.3):
    n = int(dur * SR); t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 6 * t)
    y = np.zeros(n)
    for m, g in ((1.0, 1.0), (1.26, 0.8), (1.5, 0.7), (2.0, 0.4)):
        y += g * signal.sawtooth(2 * np.pi * np.cumsum(466 * m * vib) / SR)
    sos = signal.butter(2, 5200 / (SR / 2), 'low', output='sos')
    y = signal.sosfilt(sos, y)
    env = np.minimum(1, t / 0.012) * np.minimum(1, (dur - t) / 0.05)
    return y * env * 0.35

def add(buf, y, t, gain=1.0):
    i = int(round(t * SR))
    if i < 0: y = y[-i:]; i = 0
    if i >= len(buf): return
    m = min(len(y), len(buf) - i)
    buf[i:i + m] += y[:m] * gain

def reverb(x, sec=1.4, seed=3):
    n = int(sec * SR); t = np.arange(n) / SR
    ir = np.random.RandomState(seed).randn(n) * np.exp(-t * 3.2)
    sos = signal.butter(2, 5500 / (SR / 2), 'low', output='sos'); ir = signal.sosfilt(sos, ir)
    ir[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    ir /= np.sqrt((ir ** 2).sum())
    return signal.fftconvolve(x, ir)[:len(x)]

HOOK = [0, 1, 2, 1, 3, 2, 1, 2, 4, 3, 2, 3, 5, 4, 3, 1]   # index into chord tones (up two octaves)

def build(ev, dur, esc_vt, slow=None, out='ring.wav'):
    """ev: [(vt, kind, ring, speed)] in VIDEO time; esc_vt: escape times (video time); slow: (t0,t1) slow-mo window."""
    N = int((dur + 0.6) * SR)
    lead = np.zeros(N); mel = np.zeros(N); drums = np.zeros(N); bass = np.zeros(N); pad = np.zeros(N); fx = np.zeros(N)
    kicks = []
    def shift_at(t):
        c = sum(1 for e in esc_vt if e <= t)
        return 0 if c < 4 else (2 if c < 8 else 4)          # key lifts as the rings fall
    def prog_at(t):
        return PROG[int(t // (BEAT * 4)) % 4]
    slow0, slow1 = slow if slow else (1e9, 1e9)
    final_t = esc_vt[-1]
    # ---- drums / bass / pad on the clock
    bar = BEAT * 4
    nb = int(math.ceil((dur + 0.5) / BEAT))
    for b in range(nb):
        t = b * BEAT
        in_slow = slow0 <= t < slow1
        c = sum(1 for e in esc_vt if e <= t)
        if not in_slow:
            add(drums, kick(), t, 1.0); kicks.append(t)
            add(drums, hat(open_=True), t + BEAT / 2, 0.5)
            if c >= 2 and b % 2 == 1: add(drums, clap(), t, 0.9)
            if c >= 5:
                for s in (0.25, 0.75): add(drums, hat(), t + BEAT * s, 0.4)
        else:
            if b % 1 == 0: add(drums, kick(), t, 0.55); kicks.append(t)      # heartbeat
    # snare-ish roll into the final escape: accelerating claps
    if slow:
        t = slow0; step = 0.16
        while t < final_t - 0.02:
            add(drums, clap(0.15), t, 0.45 + 0.4 * (t - slow0) / max(final_t - slow0, .1)); t += step; step = max(0.04, step * 0.86)
        add(fx, riser(max(final_t - slow0, .3)), slow0, 0.5)
        add(fx, scratch(), slow0 - 0.03, 0.8)          # record-scratch meme beat as time slows
    # bass: root per bar, 8th pulse
    for b in range(int(dur / bar) + 2):
        t0 = b * bar
        d = prog_at(t0); sh = shift_at(t0)
        f = deg_hz(d, sh, base=A3 / 4)
        for i in range(8):
            t = t0 + i * BEAT / 2
            if slow0 <= t < slow1 or t > dur + 0.2: continue
            n = int(BEAT / 2 * 0.95 * SR); tt = np.arange(n) / SR
            y = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt)
            y *= np.exp(-tt * 3.0) * (1.0 if i % 2 == 0 else 0.7)
            add(bass, y, t, 0.55)
        # pad: chord tones, saws lowpassed, cutoff rises
        c = sum(1 for e in esc_vt if e <= t0)
        n = int(bar * SR); tt = np.arange(n) / SR
        y = np.zeros(n)
        for tone in (d, d + 2, d + 4, d + 7):
            fq = deg_hz(tone, sh, base=A3)
            for det in (-0.006, 0.0, 0.006):
                y += signal.sawtooth(2 * np.pi * fq * (1 + det) * tt)
        cut = 700 + 500 * c
        sos = signal.butter(2, min(cut, 9000) / (SR / 2), 'low', output='sos')
        y = signal.sosfilt(sos, y)
        env = np.minimum(1, tt / 0.05) * np.minimum(1, (bar - tt) / 0.08)
        add(pad, y * env, t0, 0.028)

    # ---- lead hook: a real melody looping on 8ths, so the track hooks even between bounces
    LEAD = [4, 2, 0, 2, 4, 5, 4, 2, 3, 1, 0, 1, 3, 4, 3, 1]      # index in chord tones (2 octaves)
    n8 = int((dur + 0.3) / (BEAT / 2))
    for i in range(n8):
        t = i * BEAT / 2
        if slow0 <= t < slow1 - 0.0 or t > dur: continue
        c = sum(1 for e in esc_vt if e <= t)
        d = prog_at(t); sh = shift_at(t)
        tones = [d, d + 2, d + 4, d + 7, d + 9, d + 11, d + 14]
        idx = LEAD[i % 16]
        if i % 16 in (0, 8): pass
        vel = 0.5 + 0.08 * min(c, 6)
        f = deg_hz(tones[idx], sh, base=A3 * 2)
        add(lead, pluck(f, 0.32, vel), t, 0.30)
        if c >= 4 and i % 2 == 0: add(lead, pluck(f * 2, 0.22, vel), t, 0.12)
    # ---- melody: bounces play the hook; dense clouds of bounces (many balls) become chords + glitter
    slots = {}
    for (t, kind, ring, spd) in ev:
        if kind != 'b': continue
        ts = round(t / GRID)
        c_, m_ = slots.get(ts, (0, 0))
        slots[ts] = (c_ + 1, max(m_, spd))
    k = 0
    for ts_i in sorted(slots):
        ts = ts_i * GRID
        cnt, spd = slots[ts_i]
        d = prog_at(ts); sh = shift_at(ts)
        tones = [d, d + 2, d + 4, d + 7, d + 9, d + 11]
        idx = HOOK[k % len(HOOK)]
        oct_up = 7 * (1 if sum(1 for e in esc_vt if e <= ts) >= 3 else 0)
        vel = 0.5 + 0.5 * min(1.0, max(0.0, (spd - 900) / 500))
        dens = min(1.0, math.log2(1 + cnt) / 3)
        voices = [idx] + ([(idx + 2) % 6] if cnt >= 3 else []) + ([(idx + 4) % 6] if cnt >= 8 else [])
        for vi, ix in enumerate(voices):
            f = deg_hz(tones[ix] + oct_up, sh, base=A3 * 2)
            add(mel, bell(f, 0.9, vel), ts + 0.006 * vi, 0.5 * (1 - 0.25 * vi) * (0.7 + 0.3 * dens))
        f = deg_hz(tones[idx] + oct_up, sh, base=A3 * 2)
        add(mel, pluck(f * 2, 0.35, vel), ts, 0.14)
        k += 1
    # ---- escape events: sparkle arpeggio + pop, final = big drop
    for j, te in enumerate(esc_vt):
        d = prog_at(te); sh = shift_at(te + 0.05)
        last = j == len(esc_vt) - 1
        tones = [d + 4, d + 7, d + 9, d + 11, d + 14, d + 16] if not last else [d, d + 2, d + 4, d + 7, d + 9, d + 11, d + 14, d + 16]
        for i, tone in enumerate(tones):
            add(fx, bell(deg_hz(tone, sh, base=A3 * 2), 1.1 if last else 0.7, 0.9), te + i * (0.035 if not last else 0.05), 0.5)
        n = int(0.08 * SR); tt = np.arange(n) / SR
        add(fx, np.sin(2 * np.pi * (1400 - 9000 * tt) * tt) * np.exp(-tt * 40), te, 0.6)   # pop
        nb_ = int(0.16 * SR); tb_ = np.arange(nb_) / SR                                       # 'x2' bloop, higher every ring
        f0_ = 260 * 2 ** (j / 4.5)
        add(fx, np.sin(2 * np.pi * np.cumsum(f0_ * (1 + 1.2 * tb_ / 0.16)) / SR) * np.exp(-tb_ * 14), te, 0.55)
        if j == len(esc_vt) - 2: add(fx, boom(1.0), te, 0.7)   # vine-boom-ish hit: 'oh no, last ring'
        if last:
            add(fx, boom(), te, 1.0)
            for q, dq in ((0.0, 0.16), (0.22, 0.16), (0.44, 0.55)): add(fx, airhorn(dq), te + q, 0.9)   # meme airhorn
            add(drums, hat(open_=True), te, 0.9)
            add(drums, clap(0.4), te, 1.0)
            for tone in (d, d + 2, d + 4, d + 7):
                y = bell(deg_hz(tone, sh, base=A3), 1.6, 1.0); add(mel, y, te, 0.5)
    # ---- sidechain on kicks
    duck = np.ones(N)
    for t in kicks:
        i = int(t * SR); m = int(0.22 * SR)
        if i < N:
            seg = min(m, N - i)
            duck[i:i + seg] = np.minimum(duck[i:i + seg], 0.35 + 0.65 * (np.arange(seg) / m) ** 1.5)
    # bells with reverb
    wet = reverb(mel + 0.6 * fx + 0.5 * lead)
    mix = lead * 1.0 + 0.9 * mel + 0.8 * fx + 0.35 * wet + 0.9 * drums * 0.6 + duck * (0.9 * bass + pad)
    # a tiny lowpass "muffle" inside the slow-mo window is skipped: keep clean
    # fade
    n_end = int(dur * SR)
    mix = mix[:n_end + int(0.4 * SR)]
    fade = int(0.35 * SR); mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(np.abs(mix).max(), 1e-6) / 0.85
    st = np.stack([mix, np.roll(mix, int(0.0006 * SR)) * 0.98], 1)   # hint of width
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype('<i2').tobytes())
    return out

if __name__ == '__main__':
    ev = [(0.02 + 0.13 * i, 'b', 0, 1000 + (i % 5) * 80) for i in range(120)]
    esc = [0.45, 2.0, 3.6, 5.2, 7.0, 9.0, 11.5, 14.0, 17.0]
    build(ev, 18.0, esc, slow=(16.0, 17.6), out='test_audio.wav')
