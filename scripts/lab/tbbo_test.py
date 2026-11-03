import numpy as np, pandas as pd, databento as db, lightgbm as lgb, warnings; warnings.filterwarnings('ignore')
df=db.DBNStore.from_file('/tmp/moon-ai-lab-cache/ob/NQ.v.0_tbbo_2025-10-13_2025-11-01.dbn.zst').to_df()
df.index=df.index.tz_convert('America/New_York')
t=df.index.hour*60+df.index.minute
df=df[(t>=570)&(t<960)]
print('trades',len(df),'contracts',df['size'].sum())
sgn=np.where(df.side=='B',1,np.where(df.side=='A',-1,0))
df['sv']=sgn*df['size']; df['mid']=(df.bid_px_00+df.ask_px_00)/2; df['spr']=df.ask_px_00-df.bid_px_00
df['big']=df['sv']*(df['size']>=10)
# 1-second bars
g=df.resample('1s')
s=pd.DataFrame({'sv':g.sv.sum(),'big':g.big.sum(),'n':g.size.count() if False else g['size'].count(),'mid':g.mid.last(),'bid':g.bid_px_00.last(),'ask':g.ask_px_00.last(),'imb':g.apply(lambda x: ((x.bid_sz_00-x.ask_sz_00)/(x.bid_sz_00+x.ask_sz_00)).iloc[-1] if len(x) else np.nan)})
s=s[(s.index.hour*60+s.index.minute>=570)&(s.index.hour*60+s.index.minute<960)]
s[['mid','bid','ask','imb']]=s[['mid','bid','ask','imb']].groupby(s.index.date).ffill()
s['day']=s.index.date
F={}
for k in [1,5,15,60,300]:
    F[f'sv{k}']=s.groupby('day').sv.transform(lambda x: x.rolling(k,min_periods=1).sum())
    F[f'big{k}']=s.groupby('day').big.transform(lambda x: x.rolling(k,min_periods=1).sum())
    F[f'r{k}']=s.groupby('day').mid.transform(lambda x: x-x.shift(k))
    F[f'n{k}']=s.groupby('day').n.transform(lambda x: x.rolling(k,min_periods=1).sum())
F['imb']=s.imb; F['spr']=s.ask-s.bid
X=pd.DataFrame(F)
days=sorted(s.day.unique()); split=days[10]
print('train days',days[0],'..',days[9],' test',split,'..',days[-1])
for h in [5,15,60,300]:
    fwd_mid=s.groupby('day').mid.shift(-(h+1)); m1=s.groupby('day').mid.shift(-1)
    y=fwd_mid-m1
    ask1=s.groupby('day').ask.shift(-1); bid1=s.groupby('day').bid.shift(-1)
    askh=s.groupby('day').ask.shift(-(h+1)); bidh=s.groupby('day').bid.shift(-(h+1))
    longpl=bidh-ask1; shortpl=bid1-askh
    ok=y.notna()&X.notna().all(1)
    tr=ok&(s.day<split); te=ok&(s.day>=split)
    ics={c:np.corrcoef(X.loc[te,c],y[te])[0,1] for c in ['sv5','sv60','big60','imb','r60']}
    mdl=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.03,num_leaves=31,min_child_samples=2000,subsample=0.5,subsample_freq=1,verbose=-1).fit(X[tr],y[tr])
    p=pd.Series(mdl.predict(X[te]),index=X[te].index)
    ic=np.corrcoef(p,y[te])[0,1]
    out=[]
    for thr in [0.5,1,2,4]:
        sel=p.abs()>thr
        idx=p.index[sel]
        # thin to non-overlapping: keep signals at least h seconds apart
        keep=[];last=None
        for ts_ in idx:
            if last is None or (ts_-last).total_seconds()>h: keep.append(ts_); last=ts_
        pl=np.where(p[keep]>0,longpl[keep],shortpl[keep])*20-5
        out.append(f'thr{thr}: n={len(pl)} $/tr={np.nanmean(pl) if len(pl) else 0:.1f}')
    print(f'h={h}s test IC model={ic:.3f}', {k:round(v,3) for k,v in ics.items()}, '|', ' | '.join(out))
