"""Ring Escape - simulation. Ball escapes nested rotating rings. Deterministic per seed."""
import math, random
import pymunk

NR = 9                      # rings
R0, DR = 118.0, 46.0        # radius of innermost ring, spacing
BR = 17.0                   # ball radius
SUB = 240                   # sim steps / s
G = 1000.0
def ring_r(k): return R0 + DR * k

def make(seed):
    rnd = random.Random(seed)
    sp = pymunk.Space(); sp.gravity = (0, G)          # y down (screen coords)
    sp.iterations = 20
    rings = []
    for k in range(NR):
        gap = math.radians(rnd.uniform(58, 74) - k * 3.2)      # inner rings easy, outer ones tighter
        gap = max(gap, math.radians(38))
        if k == NR - 1: gap = math.radians(34)
        w = rnd.choice([-1, 1]) * rnd.uniform(0.9, 1.9) * (1 + 0.08 * k)
        if k > 0 and rnd.random() < .7: w = -math.copysign(w, rings[-1]['w'])
        a0 = rnd.uniform(0, 2 * math.pi)
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC); b.position = (0, 0); b.angle = a0; b.angular_velocity = w
        R = ring_r(k)
        n = int(2 * math.pi * R / 9)
        shapes = []
        for i in range(n):
            a1 = gap + (2 * math.pi - gap) * i / n
            a2 = gap + (2 * math.pi - gap) * (i + 1) / n
            s = pymunk.Segment(b, (R * math.cos(a1), R * math.sin(a1)), (R * math.cos(a2), R * math.sin(a2)), 4.5)
            s.elasticity = 1.0; s.friction = 0.0
            shapes.append(s)
        sp.add(b, *shapes)
        rings.append(dict(body=b, shapes=shapes, gap=gap, w=w, a0=a0, R=R, alive=True))
    ball = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BR))
    ang = rnd.uniform(0, 2 * math.pi); rr = rnd.uniform(0, 30)
    ball.position = (rr * math.cos(ang), rr * math.sin(ang) - 20)
    sp_ = rnd.uniform(950, 1150); va = rnd.uniform(0, 2 * math.pi)
    ball.velocity = (sp_ * math.cos(va), sp_ * math.sin(va))
    bs = pymunk.Circle(ball, BR); bs.elasticity = 1.0; bs.friction = 0.0
    sp.add(ball, bs)
    return sp, rings, ball, bs

def simulate(seed, tmax=40.0, gapfix=None):
    sp, rings, ball, bs = make(seed)
    cur = 0
    ev = []          # (t, kind, k, speed)
    states = []      # per step: (bx, by, [ring angles])
    bounce_cool = 0
    t = 0.0
    dt = 1.0 / SUB
    # collision detection via post-solve callback
    hits = []
    def post(arbiter, space, data):
        hits.append(arbiter.total_impulse.length)
    sp.on_collision(post_solve=post) if hasattr(sp, 'on_collision') else None
    esc_t = []
    t_done = None
    while t < tmax and (cur < NR or t < t_done + 0.9):
        hits.clear()
        sp.step(dt); t += dt
        v = ball.velocity; spd = v.length
        # keep the ball lively
        if spd < 900:
            ball.velocity = v * (900 / max(spd, 1e-6))
        elif spd > 1500:
            ball.velocity = v * (1500 / spd)
        if hits and t - bounce_cool > 0.03:
            ev.append((t, 'b', cur, spd, ball.position.x, ball.position.y)); bounce_cool = t
        d = math.hypot(*ball.position)
        states.append((ball.position.x, ball.position.y, tuple(r['body'].angle for r in rings), cur))
        if cur < NR and d > rings[cur]['R'] + BR + 8:
            r = rings[cur]
            sp.remove(r['body'], *r['shapes']); r['alive'] = False
            ev.append((t, 'e', cur, spd)); esc_t.append(t)
            cur += 1
            if cur >= NR: t_done = t
            ball.velocity = ball.velocity * 1.02
    return dict(t_done=t_done, ev=ev, states=states, esc=esc_t, T=t, rings=[dict(gap=r['gap'], R=r['R'], w=r['w']) for r in rings], done=cur >= NR)

if __name__ == '__main__':
    import sys
    r = simulate(int(sys.argv[1]))
    print(r['T'], r['done'], [round(x, 2) for x in r['esc']])
