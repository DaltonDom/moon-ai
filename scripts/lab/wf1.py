import sys; sys.path.insert(0,'src')
import numpy as np
from moon_ai.lab.library import build
from moon_ai.lab.wf import walk_forward, years_of
from moon_ai.lab.engine import sharpe
lib=build()
yrs=years_of(lib['days'])
for kw in [dict(min_t=2.0),dict(min_t=2.5),dict(min_t=3.0),dict(min_t=2.5,top_per_group=3),dict(min_t=2.0,group_key=("sym",)),dict(min_t=2.5,lookback_years=3)]:
    p,lo,oos,picks=walk_forward(lib,**kw)
    print(kw,'OOS daily sh %.3f'%sharpe(p[oos]),'by yr',[('%.2f'%sharpe(p[yrs==y])) for y in range(2021,2026)],'n picks',[len(v) for v in picks.values()])
