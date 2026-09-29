import sys, marble
from multiprocessing import Pool
PART = int(sys.argv[1])
CS = marble.roster(PART)
def f(sd): return marble.headless(sd, tmax=110, cs=CS)
if __name__ == '__main__':
    a, b = int(sys.argv[2]), int(sys.argv[3])
    with Pool(4) as p:
        res = p.map(f, range(a, b))
    ok = [r for r in res if r['ok'] and 61 <= r['last'] <= 72]
    ok.sort(key=lambda r: r['gap'])
    print(len(CS), 'countries;', len(ok), 'good')
    for r in ok[:5]:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
