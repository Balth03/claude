import sys, marble
from multiprocessing import Pool
PART = int(sys.argv[1])
CS = marble.roster(PART)
def f(sd): return marble.headless(sd, tmax=60, cs=CS)
if __name__ == '__main__':
    a, b = int(sys.argv[2]), int(sys.argv[3])
    with Pool(4) as p:
        res = p.map(f, range(a, b))
    n = len(CS)
    # good race: winner decided early, lava catches someone late with a pack of 3-8 still fighting
    ok = [r for r in res if r['ok'] and 27 <= r['catch'] <= 32 and n - 8 <= r['n_fin'] <= n - 3 and r['first'] < 21]
    ok.sort(key=lambda r: -r['catch'])
    print(n, 'countries;', len(ok), 'good')
    for r in ok[:5]:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
