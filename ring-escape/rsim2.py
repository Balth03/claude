"""Ring Escape v2 - DOUBLING. Every ring that breaks doubles the balls (1,2,4..256 -> 512).
Each ring's gap/spin is tuned (deterministically) so the breaks land on the beat grid."""
import math, random, pickle, sys, time
import numpy as np
import pymunk

NR = 9
R0, DR = 100.0, 50.0
G = 1000.0
SUB = 240
BEAT = 60.0 / 132.0
FILT = pymunk.ShapeFilter(group=1)          # balls never collide with each other
def ring_r(k): return R0 + DR * k
def brad(k): return max(5.5, 17.0 * 0.88 ** k)

def run_ring(k, balls, gap, w, a0, tmax, record=False, seed=0):
    """balls: array (N,5) x,y,vx,vy,gen. Returns t_break (or None), balls_after, frames, bounces."""
    sp = pymunk.Space(); sp.gravity = (0, G); sp.iterations = 10
    R = ring_r(k); r = brad(k)
    b = pymunk.Body(body_type=pymunk.Body.KINEMATIC); b.position = (0, 0); b.angle = a0; b.angular_velocity = w
    n = int(2 * math.pi * R / 9)
    segs = []
    for i in range(n):
        a1 = gap + (2 * math.pi - gap) * i / n; a2 = gap + (2 * math.pi - gap) * (i + 1) / n
        s = pymunk.Segment(b, (R * math.cos(a1), R * math.sin(a1)), (R * math.cos(a2), R * math.sin(a2)), 4.5)
        s.elasticity = 1.0; s.friction = 0.0
        segs.append(s)
    sp.add(b, *segs)
    bodies = []
    for (x, y, vx, vy, g) in balls:
        bd = pymunk.Body(1, pymunk.moment_for_circle(1, 0, r)); bd.position = (x, y); bd.velocity = (vx, vy)
        sh = pymunk.Circle(bd, r); sh.elasticity = 1.0; sh.friction = 0.0; sh.filter = FILT
        sp.add(bd, sh); bodies.append(bd)
    idx = {bd: i for i, bd in enumerate(bodies)}
    hits = []
    def post(arb, space, data):
        hits.append(idx[arb.shapes[0].body] if arb.shapes[0].body in idx else idx[arb.shapes[1].body])
    sp.on_collision(post_solve=post)
    gens = balls[:, 4].copy()
    frames = []; bounces = []
    dt = 1.0 / SUB; t = 0.0; tb = None
    thr = R + r + 5
    while t < tmax:
        hits.clear()
        sp.step(dt); t += dt
        P = np.array([bd.position for bd in bodies], np.float32)
        V = np.array([bd.velocity for bd in bodies], np.float64)
        spd = np.hypot(V[:, 0], V[:, 1])
        low = spd < 900; high = spd > 1500
        if low.any() or high.any():
            for i in np.nonzero(low | high)[0]:
                bodies[i].velocity = tuple(V[i] * ((900 if low[i] else 1500) / max(spd[i], 1e-6)))
        if record:
            frames.append((k, b.angle, P))
            for h in set(hits): bounces.append((t, k, float(spd[h]), float(P[h][0]), float(P[h][1]), int(len(bodies))))
        if (np.hypot(P[:, 0], P[:, 1]) > thr).any():
            tb = t; break
    after = np.array([[bd.position.x, bd.position.y, bd.velocity.x, bd.velocity.y, gens[i]] for i, bd in enumerate(bodies)])
    return tb, after, frames, bounces, gens

def split(balls, k, rnd):
    out = [tuple(b) for b in balls]
    for (x, y, vx, vy, g) in balls:
        a = rnd.choice([-1, 1]) * rnd.uniform(0.4, 1.1)
        c, s = math.cos(a), math.sin(a)
        sp_ = rnd.uniform(0.95, 1.15)
        out.append((x, y, (vx * c - vy * s) * sp_, (vx * s + vy * c) * sp_, k + 1))
    return np.array(out)

def build(seed=1, verbose=True):
    rnd = random.Random(seed)
    T = [BEAT * 1] + [BEAT * (3 + 2 * i) for i in range(7)]         # ring 0..7 break on the beat grid
    T_FINAL_DUR = 2.7
    ang = rnd.uniform(0, 6.28)
    balls = np.array([[8 * math.cos(ang), 8 * math.sin(ang) - 10, 1000 * math.cos(ang + 1.3), 1000 * math.sin(ang + 1.3), 0]])
    t0 = 0.0
    frames = []; bounces = []; stage_gens = []; rings = []; esc = []
    for k in range(NR):
        R = ring_r(k); r = brad(k)
        target = (T[k] - t0) if k < 8 else T_FINAL_DUR
        best = None
        for c in range(28):
            L = (rnd.uniform(1.3, 2.6) if k == 8 else rnd.uniform(3.0, 6.5)) * 2 * r                    # gap arc length in px
            gap = min(L / R, 1.6)
            w = rnd.choice([-1, 1]) * rnd.uniform(0.9, 2.3)
            a0 = rnd.uniform(0, 2 * math.pi)
            tb, *_ = run_ring(k, balls, gap, w, a0, tmax=target * 2.5 + 0.6)
            if tb is None: continue
            score = abs(tb - target)
            if best is None or score < best[0]: best = (score, gap, w, a0, tb)
            if score < 0.04: break
        if best is None:                                          # fallback: wide gap
            best = (9, 1.4, 1.5, 0.0, None)
        _, gap, w, a0, _ = best
        tb, after, fr, bo, gens = run_ring(k, balls, gap, w, a0, tmax=30, record=True)
        for (i, f) in enumerate(fr): frames.append((f[0], f[1], f[2], gens, t0 + (i + 1) / SUB))
        bounces += [(t0 + b_[0],) + b_[1:] for b_ in bo]
        rings.append(dict(gap=gap, w=w, a0=a0, R=R))
        t0 += tb; esc.append(t0)
        if verbose: print(f'ring {k}: N={len(balls)} target {target:.2f} got {tb:.2f} -> break at {t0:.2f}', flush=True)
        balls = split(after, k, rnd)
    # free flight after the last ring: radial burst
    burst = []
    for (x, y, vx, vy, g) in balls:
        a = math.atan2(y, x) + rnd.uniform(-0.5, 0.5); sp_ = rnd.uniform(500, 1500)
        burst.append((x, y, math.cos(a) * sp_, math.sin(a) * sp_ - 300, g))
    burst = np.array(burst)
    P = burst[:, :2].copy(); V = burst[:, 2:4].copy(); gens = burst[:, 4]
    for i in range(int(2.2 * SUB)):
        V[:, 1] += G / SUB; P += V / SUB
        frames.append((NR, 0.0, P.astype(np.float32).copy(), gens, t0 + (i + 1) / SUB))
    return dict(frames=frames, bounces=bounces, rings=rings, esc=esc)

if __name__ == '__main__':
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    t = time.time(); d = build(seed)
    print('sim wall', round(time.time() - t, 1), 'frames', len(d['frames']), 'bounces', len(d['bounces']))
    pickle.dump(d, open(f'sim2_{seed}.pkl', 'wb'))
