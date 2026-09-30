import fight as F, sys, itertools, statistics
from multiprocessing import Pool
def run(args):
    ep, mods, n = args
    res=[]
    for seed in range(n):
        e=getattr(F,'ep_'+ep)()
        for i,f in enumerate(e['fighters']):
            for k,v in mods.get(f['team'],{}).items(): f[k]=v
        r=F.headless(e,seed,60)
        if r: res.append(r)
    if not res: return (mods,0,0,0)
    w=sum(r['winner']==0 for r in res)/len(res)
    return (mods, round(w,2), round(statistics.median(r['t'] for r in res),1), len(res))
if __name__=='__main__':
    ep=sys.argv[1]
    if ep=='E2':
        grid=[{0:dict(dmg=bd),1:dict(dmg=1,period=p)} for bd in (7,8) for p in (1.6,1.8,2.0)]
    else:
        grid=[{0:dict(dmg=bd,spin=sp),1:dict(dmg=wd,hp=wh)} for bd in (4,) for sp in (110,150) for wd in (1,2) for wh in (16,22)]
    with Pool(4) as p:
        for r in p.map(run,[(ep,g,24) for g in grid]): print(r, flush=True)
