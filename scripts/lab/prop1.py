import sys,warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'src')
import numpy as np
from moon_ai.lab.data import load, m
from moon_ai.lab.engine import run, sharpe
from moon_ai.lab.features import first_cross
from moon_ai.lab.propfirm import evaluate
g=load('MNQ'); yrs=g.days.astype('datetime64[Y]').astype(int)+1970
a=m(9,30); b=a+60; hi=np.nanmax(g.H[:,a:b],1); lo=np.nanmin(g.L[:,a:b],1); r=hi-lo
side,idx=first_cross(g.C[:,b:m(15,50)],hi,lo); ent=np.where(side!=0,b+idx+1,-1)
pnl,mae,_=run(g,ent,side,r,r*2,m(15,55))
streams={'ORB60 MNQ':(pnl,mae)}
ml=np.load('/tmp/moon-ai-lab-cache/ml2_daily.npy',allow_pickle=True).item()
p=ml[('MNQ',30)]; streams['ML MNQ 30m']=(p,np.minimum(p,0)*1.5)
oos=yrs>=2021
for name,(p,lo) in streams.items():
    p=np.nan_to_num(p); lo=np.nan_to_num(lo)
    # causal unit risk: 95th pct of past 250-day per-unit worst intraday loss
    ur=np.full(len(p),np.nan)
    for i in range(250,len(p)): ur[i]=-np.quantile(lo[i-250:i],0.05)
    P,L,U=p[oos],lo[oos],ur[oos]
    print(name,'OOS daily sh %.3f'%sharpe(P))
    for rf in [1.2,2.0,3.0]:
        print('  risk',rf,evaluate(P,L,U,risk_frac=rf,coast=1.0))
