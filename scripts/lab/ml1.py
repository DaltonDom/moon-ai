import sys; sys.path.insert(0,'src')
import numpy as np, lightgbm as lgb
from moon_ai.lab.data import load, m
from moon_ai.lab.features import daily_range_atr
from moon_ai.lab.ml_intraday import build
from moon_ai.lab.engine import sharpe
grids={s:load(s) for s in ['MNQ','MES']}
main='MNQ'; g=grids[main]
atr=daily_range_atr(g)
H=int(sys.argv[1]) if len(sys.argv)>1 else 30
times=list(range(m(9,45),m(15,30),15))
X,y,di,ti,names=build(grids,main,times,H,atr)
yrs=g.days.astype('datetime64[Y]').astype(int)+1970
yr=yrs[di]
ok=g.tradable[di]&~np.isnan(y)&~np.isnan(atr[di])
pv=g.point_value
# cost in bps: 2 ticks slippage + $2 comm per micro
px=g.O[di,ti]
cost_bps=( (2*g.tick*pv+2.0)/(px*pv) )*1e4
print('median cost bps',np.nanmedian(cost_bps),'std y',np.nanstd(y[ok]))
for Y in range(2021,2026):
    tr=ok&(yr<Y); te=ok&(yr==Y)
    mdl=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.03,num_leaves=15,min_child_samples=200,subsample=0.8,subsample_freq=1,colsample_bytree=0.8,verbose=-1)
    mdl.fit(X[tr],y[tr])
    p_tr=mdl.predict(X[tr]); p=mdl.predict(X[te])
    ic=np.corrcoef(p,y[te])[0,1]
    for q in [0.8,0.9,0.95]:
        thr=np.quantile(np.abs(p_tr),q)
        sel=np.abs(p)>thr
        r=np.sign(p[sel])*y[te][sel]-cost_bps[te][sel]
        # daily pnl in bps of notional summed
        dd=np.zeros(len(g.days)); np.add.at(dd,di[te][sel],r)
        days=np.unique(di[te])
        print(Y,'IC %.3f'%ic,'q',q,'trades',sel.sum(),'mean bps %.2f'%r.mean(),'daily sh %.3f'%sharpe(dd[days]))
