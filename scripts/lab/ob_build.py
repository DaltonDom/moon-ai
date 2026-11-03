import sys, numpy as np, pandas as pd, databento as db
D='/tmp/moon-ai-lab-cache/ob/'
def grid(path, out):
    df=db.DBNStore.from_file(path).to_df()
    df=df[['bid_px_00','ask_px_00','bid_sz_00','ask_sz_00','price','size','side','instrument_id']]
    df=df[(df.bid_px_00>0)&(df.ask_px_00>df.bid_px_00)]
    ts=df.index.tz_convert('America/New_York')
    sec=(ts.hour*3600+ts.minute*60+ts.second).to_numpy()
    keep=(sec>=9*3600+30*60)&(sec<16*3600)
    df=df[keep]; sec=sec[keep]; d=ts[keep].normalize().tz_localize(None).to_numpy()
    days=np.unique(d); di=np.searchsorted(days,d); si=sec-(9*3600+30*60)
    S=6*3600+30*60
    A={k:np.full((len(days),S),np.nan) for k in ['bid','ask','bsz','asz','tside','tsize','inst']}
    for k,c in [('bid','bid_px_00'),('ask','ask_px_00'),('bsz','bid_sz_00'),('asz','ask_sz_00'),('tsize','size'),('inst','instrument_id')]:
        A[k][di,si]=df[c].to_numpy()
    A['tside'][di,si]=np.where(df.side.to_numpy()=='A',-1,np.where(df.side.to_numpy()=='B',1,0))  # A=sell aggressor, B=buy aggressor
    # forward fill book
    for k in ['bid','ask','bsz','asz','inst']:
        X=A[k]
        for i in range(len(days)):
            r=X[i]; m=np.isnan(r); idx=np.where(~m,np.arange(S),0); np.maximum.accumulate(idx,out=idx); X[i]=r[idx]; X[i][:np.argmax(~m)]=np.nan
    np.savez(out,days=days,**A); print(out,len(days))
grid(D+'NQ.v.0_bbo-1s_2025-05-01_2025-11-01.dbn.zst',D+'NQ_1s.npz')
grid(D+'ES.v.0_bbo-1s_2025-07-01_2025-11-01.dbn.zst',D+'ES_1s.npz')
