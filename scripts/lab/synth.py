import sys; sys.path.insert(0,'src')
import numpy as np
from moon_ai.lab.propfirm import evaluate
rng=np.random.default_rng(0)
n=1500
for sh in [0.1,0.15,0.2,0.3,0.4,0.5]:
    best=None
    for rf in [0.1,0.15,0.2,0.3,0.4,0.6]:
      for coast in [0,1.0,0.5]:
        rs=[]
        for rep in range(3):
            pnl=rng.normal(sh,1.0,n)*20  # $ per unit; sd $20/micro/day
            low=np.minimum(0,pnl)-np.abs(rng.normal(0,10,n))
            ur=np.full(n,40.0)
            rs.append(evaluate(pnl,low,ur,risk_frac=rf,coast=coast))
        pr=np.mean([r.pass_rate for r in rs]); fr=np.mean([r.full_rate for r in rs])
        if best is None or pr+fr>best[0]: best=(pr+fr,rf,coast,pr,fr,np.mean([r.median_days for r in rs]))
    print(f"daily sharpe {sh}: best rf={best[1]} coast={best[2]} pass={best[3]:.1%} full={best[4]:.1%} med={best[5]:.1f}")
