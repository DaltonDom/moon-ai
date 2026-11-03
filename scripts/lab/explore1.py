import sys; sys.path.insert(0,'src')
import numpy as np, itertools
from moon_ai.lab.data import load, m
from moon_ai.lab.engine import run, sharpe
from moon_ai.lab.features import prev_close, daily_range_atr, first_cross
for sym in ['MNQ','MES']:
    g=load(sym); atr=daily_range_atr(g); pc=prev_close(g)
    yrs=g.days.astype('datetime64[Y]').astype(int)+1970
    print('==',sym)
    # ORB
    res=[]
    for k,stopf,tgtR,exh in itertools.product([5,15,30,60],[0.5,1.0],[0,1,2,3],[12,16]):
        a=m(9,30); b=a+k
        hi=np.nanmax(g.H[:,a:b],1); lo=np.nanmin(g.L[:,a:b],1); r=hi-lo
        ext=m(exh,0) if exh==12 else m(15,55)
        side,idx=first_cross(g.C[:,b:ext-5],hi,lo)
        ent=np.where(side!=0, b+idx+1, -1)
        sd=np.maximum(r*stopf, 4*g.tick)
        pnl,mae,_=run(g,ent,side,sd,sd*tgtR,ext)
        ok=~np.isnan(atr)
        res.append((sharpe(pnl[ok]),k,stopf,tgtR,exh,pnl[ok].mean(),(ent>=0).mean()))
    res.sort(reverse=True)
    for r in res[:5]: print('ORB',['%.3f'%r[0]]+list(r[1:5]),'mean$ %.2f'%r[5],'freq %.2f'%r[6])
    # overnight drift: long at 18:00 open .. exit at times
    for en,ex in [((18,0),(9,30)),((18,0),(4,0)),((1,0),(4,0)),((2,0),(4,0)),((18,0),(2,0)),((9,30),(16,0)),((15,0),(16,0)),((4,0),(9,30))]:
        e=m(*en); x=m(*ex)
        pnl,mae,_=run(g,np.full(len(g.days),e),1,0,0,x)
        print('long',en,ex,'sh %.3f mean %.2f'%(sharpe(pnl),pnl.mean()), ' by yr',[('%.2f'%sharpe(pnl[yrs==y])) for y in range(2019,2026)])
