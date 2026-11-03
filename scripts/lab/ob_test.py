import sys, numpy as np, lightgbm as lgb, warnings; warnings.filterwarnings('ignore')
D='/tmp/moon-ai-lab-cache/ob/'
N=dict(np.load(D+'NQ_1s.npz')); E=dict(np.load(D+'ES_1s.npz'))
PV=20.0; COMM=5.0
def prep(A):
    mid=(A['bid']+A['ask'])/2; spr=A['ask']-A['bid']
    imb=(A['bsz']-A['asz'])/(A['bsz']+A['asz'])
    flow=np.nan_to_num(A['tside']*A['tsize'])
    roll=np.array([np.nanmin(r)!=np.nanmax(r) for r in A['inst']])
    return mid,spr,imb,flow,roll
nm,ns,ni,nf,nroll=prep(N); em,es,ei,ef,eroll=prep(E)
nd=N['days']; ed=E['days']
# align ES rows to NQ days
epos={d:i for i,d in enumerate(ed)}
S=nm.shape[1]; step=5
ts=np.arange(310,S-310,step)
def lagret(x,t,k): return x[:,t]-x[:,t-k]
def csum(f):
    c=np.cumsum(f,axis=1); return c
ncf=csum(nf)
rows=[]
H=[10,30,60,300]
feat=[];names=[]
def add(n,v): names.append(n); feat.append(v)
for k in [1,5,15,30,60,300]: add(f'nq_r{k}',lagret(nm,ts,k))
add('nq_imb',ni[:,ts]); add('nq_spr',ns[:,ts])
add('nq_micro',(ni[:,ts]*ns[:,ts]/2))
for k in [10,60,300]: add(f'nq_flow{k}',ncf[:,ts]-ncf[:,ts-k])
EM=np.full_like(nm,np.nan); EI=np.full_like(nm,np.nan); EF=np.zeros_like(nm)
for i,d in enumerate(nd):
    if d in epos: j=epos[d]; EM[i]=em[j]; EI[i]=ei[j]; EF[i]=ef[j]
ecf=np.cumsum(EF,axis=1)
for k in [1,5,15,30,60,300]: add(f'es_r{k}',lagret(EM,ts,k)/np.nanmean(em)*np.nanmean(nm))
add('es_imb',EI[:,ts])
for k in [10,60]: add(f'es_flow{k}',ecf[:,ts]-ecf[:,ts-k])
add('tod',np.broadcast_to(ts,(len(nd),len(ts))).astype(float))
X=np.stack(feat,-1)  # days x times x f
month=nd.astype('datetime64[M]')
print('days',len(nd),'roll days',nroll.sum())
for h in H:
    y=nm[:,ts+1+h]-nm[:,ts+1]
    net=None
    # trade P&L in points if long/short at t+1 crossing spread, exit crossing spread at t+1+h
    longpl=nm[:,ts+1+h]-ns[:,ts+1+h]/2-(nm[:,ts+1]+ns[:,ts+1]/2)
    shortpl=(nm[:,ts+1]-ns[:,ts+1]/2)-(nm[:,ts+1+h]+ns[:,ts+1+h]/2)
    # univariate ICs per month
    print(f'\n== h={h}s  sd(y)={np.nanstd(y):.3f}pts  mean spread={np.nanmean(ns):.3f}')
    for fn in ['nq_imb','nq_flow60','nq_r60','es_r5','es_r30','es_imb']:
        fi=names.index(fn); out=[]
        for mo in np.unique(month):
            mk=(month==mo)&~nroll
            a=X[mk][:,:,fi].ravel(); b=y[mk].ravel(); ok=~(np.isnan(a)|np.isnan(b))
            out.append('%.3f'%np.corrcoef(a[ok],b[ok])[0,1] if ok.sum()>1000 else '  -  ')
        print(f'{fn:10s} IC by month',out)
    for tag,tr_m,te_m in [('nq-only',month<np.datetime64('2025-09'),month>=np.datetime64('2025-09')),
                          ('with-es',(month>=np.datetime64('2025-07'))&(month<np.datetime64('2025-09')),month>=np.datetime64('2025-09'))]:
        cols=[i for i,n in enumerate(names) if (tag=='with-es' or not n.startswith('es_'))]
        tr=tr_m&~nroll; te=te_m&~nroll
        Xtr=X[tr][:,:,cols].reshape(-1,len(cols)); ytr=y[tr].ravel(); ok=~np.isnan(ytr)
        mdl=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.03,num_leaves=31,min_child_samples=2000,subsample=0.5,subsample_freq=1,verbose=-1)
        mdl.fit(Xtr[ok],ytr[ok])
        Xte=X[te][:,:,cols]; p=mdl.predict(Xte.reshape(-1,len(cols))).reshape(Xte.shape[:2])
        yt=y[te]; ok2=~np.isnan(yt)
        ic=np.corrcoef(p[ok2],yt[ok2])[0,1]
        res=[]
        for thr in [0.25,0.5,1.0,2.0]:
            # non-overlapping trades per day: take signal, skip h seconds
            pls=[]; daily=[]
            for di in range(p.shape[0]):
                tot=0; j=0
                while j<p.shape[1]:
                    if abs(p[di,j])>thr and not np.isnan(longpl[te][di,j]):
                        pl=(longpl[te][di,j] if p[di,j]>0 else shortpl[te][di,j])*PV-COMM
                        pls.append(pl); tot+=pl; j+=h//step+1
                    else: j+=1
                daily.append(tot)
            pls=np.array(pls); daily=np.array(daily)
            res.append(f'thr{thr}: n={len(pls)} $/tr={pls.mean() if len(pls) else 0:.2f} daily$={daily.mean():.0f} sh={daily.mean()/daily.std() if daily.std()>0 else 0:.2f}')
        print(f'{tag} test Sep-Oct IC={ic:.3f} |', ' | '.join(res))
