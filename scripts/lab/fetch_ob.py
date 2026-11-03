"""Download the order-book feasibility sample (2026-11-03). Costs logged to ledger_ob.jsonl."""
import json, os, sys, datetime
import databento as db
out = sys.argv[1]
c = db.Historical(os.environ['DATABENTO_API_KEY'])
plan = [('bbo-1s','NQ.v.0','2025-05-01','2025-11-01'), ('bbo-1s','ES.v.0','2025-05-01','2025-11-01'),
        ('tbbo','NQ.v.0','2025-08-18','2025-11-01')]
for sch, sym, s, e in plan:
    path = f"{out}/{sym}_{sch}_{s}_{e}.dbn.zst"
    if os.path.exists(path):
        continue
    cost = c.metadata.get_cost(dataset='GLBX.MDP3', symbols=[sym], stype_in='continuous', schema=sch, start=s, end=e)
    c.timeseries.get_range(dataset='GLBX.MDP3', symbols=[sym], stype_in='continuous', schema=sch,
                           start=s, end=e, path=path + '.part')
    os.rename(path + '.part', path)
    with open(f"{out}/ledger_ob.jsonl", 'a') as f:
        f.write(json.dumps({'at': datetime.datetime.now(datetime.UTC).isoformat(), 'schema': sch, 'symbol': sym,
                            'start': s, 'end': e, 'cost_usd': cost}) + '\n')
    print('done', path, cost, flush=True)
