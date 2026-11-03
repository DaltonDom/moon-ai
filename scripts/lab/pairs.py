import sys; sys.path.insert(0,'src')
import numpy as np
from moon_ai.lab.data import load, m
from moon_ai.lab.engine import sharpe
a=load('MNQ'); b=load('MES')
assert (a.days==b.days).all()
yrs=a.days.astype('datetime64[Y]').astype(int)+1970
o=m(9,30)
la=np.log(a.C); lb=np.log(b.C)
ra=la-la[:,[o]]; rb=lb-lb[:,[o]]
# rolling beta from prior 60 days of 5-min returns
n=len(a.days)
beta=np.full(n,np.nan)
r5a=np.diff(la[:,o:m(16,0):5],axis=1); r5b=np.diff(lb[:,o:m(16,0):5],axis=1)
for i in range(60,n):
    x=r5b[i-60:i].ravel(); y=r5a[i-60:i].ravel(); k=~(np.isnan(x)|np.isnan(y))
    beta[i]=np.dot(x[k],y[k])/np.dot(x[k],x[k])
spread=ra-beta[:,None]*rb   # log units, since open
# trailing sd of spread at 60 min after open
sd=np.full(n,np.nan)
s_end=np.nanstd(spread[:,o:m(16,0)],axis=1)
for i in range(20,n): sd[i]=np.nanmean(s_end[i-20:i])
# trade: at check times every 15 min, if |z|>k fade spread, hold h minutes. pnl in $ of notional: 1 MNQ micro vs beta*notional MES micros (fractional ok for research)
pa=a.point_value; pb=b.point_value
res={}
for k in [1.0,1.5,2.0,3.0]:
  for h in [15,30,60]:
    daily=np.zeros(n)
    for t in range(m(10,0),m(15,30),15):
        z=spread[:,t-1]/sd
        side=np.where(np.abs(z)>k,-np.sign(z),0); side=np.nan_to_num(side)
        te=min(t+h,m(15,59))
        da=(a.O[:,te]-a.O[:,t])*pa; db=(b.O[:,te]-b.O[:,t])*pb
        hedge=beta*(a.O[:,t]*pa)/(b.O[:,t]*pb)  # MES micros per MNQ micro
        pnl=side*(da-hedge*db)
        cost=np.abs(side)*( (2*a.tick*pa+2) + hedge*(2*b.tick*pb+2) )
        daily+=np.nan_to_num(pnl-0*cost)*a.tradable
    res[(k,h)]=daily
    print(k,h,'sh %.3f'%sharpe(daily[60:]),[('%.2f'%sharpe(daily[yrs==y])) for y in range(2019,2026)])
