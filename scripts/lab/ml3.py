import sys,warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'src')
import numpy as np, lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from moon_ai.lab.data import load, m
from moon_ai.lab.features import daily_range_atr
from moon_ai.lab.engine import run, sharpe
a=load('MNQ'); b=load('MES')
yrs=a.days.astype('datetime64[Y]').astype(int)+1970
def feats(g):
    o=m(9,30); c=g.C[:,m(16,0)-1]; pc=np.r_[np.nan,c[:-1]]
    f=[np.log(g.C[:,o-1]/pc)]           # overnight
    for k in (1,2,5,10,20):
        f.append(np.r_[[np.nan]*(k+1), np.log(c[k:-1]/c[:-k-1])])  # past k-day returns (to yesterday)
    rth=np.log(c/g.O[:,o]); f.append(np.r_[np.nan,rth[:-1]])
    atr=daily_range_atr(g); f.append(atr/g.C[:,o-1]); f.append(np.r_[np.nan,np.nan,(atr[2:]/atr[1:-1])])
    f.append(np.log(g.C[:,o-1]/g.C[:,m(2,0)]))  # EU session
    return np.column_stack(f)
X=np.hstack([feats(a),feats(b),((a.days.view('int64')+3)%7)[:,None]])
for (en,ex,name) in [((9,30),(15,55),'rth'),((9,30),(12,0),'am'),((12,0),(15,55),'pm')]:
    y=np.log(a.O[:,m(*ex)]/a.O[:,m(*en)])
    ok=~np.isnan(X).any(1)&~np.isnan(y)&a.tradable
    for mdl_name in ['lgb','logit']:
        side=np.zeros(len(y),int)
        for Y in range(2021,2026):
            tr=ok&(yrs<Y); te=ok&(yrs==Y)
            if mdl_name=='lgb':
                mdl=lgb.LGBMClassifier(n_estimators=150,learning_rate=0.03,num_leaves=7,min_child_samples=50,verbose=-1)
            else:
                mdl=LogisticRegression(C=0.1,max_iter=500)
            mu=X[tr].mean(0); sd=X[tr].std(0)
            mdl.fit((X[tr]-mu)/sd,(y[tr]>0).astype(int))
            p=mdl.predict_proba((X[te]-mu)/sd)[:,1]
            side[te]=np.where(p>0.5,1,-1)
        pnl,mae,_=run(a,m(*en),side,0.0,0.0,m(*ex))
        oos=(yrs>=2021)
        print(name,mdl_name,'OOS sh %.3f'%sharpe(pnl[oos]),[('%.2f'%sharpe(pnl[yrs==Y])) for Y in range(2021,2026)])
