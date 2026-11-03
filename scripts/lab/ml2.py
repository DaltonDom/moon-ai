import sys; sys.path.insert(0,'src')
import numpy as np, lightgbm as lgb
from moon_ai.lab.data import load, m
from moon_ai.lab.features import daily_range_atr
from moon_ai.lab.ml_intraday import build
from moon_ai.lab.engine import sharpe
SY=['MNQ','MES','MYM','M2K','MGC','MCL','M6E']
raw={s:load(s) for s in SY}
base=raw['MNQ']
# align all to MNQ days
import copy
grids={}
for s,g in raw.items():
    pos=np.searchsorted(base.days,g.days)
    G=copy.copy(g)
    for k in 'OHLCV':
        A=np.full(base.C.shape,np.nan); A[pos]=getattr(g,k); setattr(G,k,A)
    t=np.zeros(len(base.days),bool); t[pos]=g.tradable; G.tradable=t; G.days=base.days
    grids[s]=G
yrs=base.days.astype('datetime64[Y]').astype(int)+1970
times=list(range(m(9,40),m(15,40),10))
out={}
for main in SY:
  g=grids[main]; atr=daily_range_atr(g)
  for H in [10,30,60]:
    X,y,di,ti,names=build(grids,main,times,H,atr)
    px=g.O[di,ti]; cost=((2*g.tick*g.point_value+2.0)/(px*g.point_value))*1e4
    ok=g.tradable[di]&~np.isnan(y)&~np.isnan(atr[di])&~np.isnan(px)
    first=yrs[di][ok].min()
    daily_all=np.zeros(len(base.days)); ics=[]
    for Y in range(max(first+2,2021),2026):
        tr=ok&(yrs[di]<Y); te=ok&(yrs[di]==Y)
        if tr.sum()<5000: continue
        mdl=lgb.LGBMRegressor(n_estimators=200,learning_rate=0.03,num_leaves=15,min_child_samples=300,subsample=0.8,subsample_freq=1,colsample_bytree=0.7,verbose=-1)
        mdl.fit(X[tr],y[tr]); p_tr=mdl.predict(X[tr]); p=mdl.predict(X[te])
        ics.append(np.corrcoef(p,y[te])[0,1])
        thr=np.quantile(np.abs(p_tr),0.9)
        sel=np.abs(p)>thr
        r=(np.sign(p[sel])*y[te][sel]-cost[te][sel])*px[te][sel]*g.point_value/1e4
        np.add.at(daily_all,di[te][sel],r)
    oosd=(yrs>=max(first+2,2021))&(yrs<=2025)
    print(main,H,'IC by yr',['%.3f'%i for i in ics],'net daily sh %.3f'%sharpe(daily_all[oosd]),flush=True)
    out[(main,H)]=daily_all
np.save('/tmp/moon-ai-lab-cache/ml2_daily.npy',out,allow_pickle=True)
