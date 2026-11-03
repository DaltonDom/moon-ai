import sys
import time
from datetime import date
from pathlib import Path

from moon_ai import holdout
from moon_ai.backtest.runner import run_backtest

setup, symbol = sys.argv[1], sys.argv[2]
start, end = date(2019, 6, 3), date(2025, 11, 1)
holdout.guard(start, end)
t = time.time()
r = run_backtest(
    setup,
    start,
    end,
    symbol=symbol,
    runs_root=Path("data/runs/judgment"),
    run_id=f"{setup}.default.{symbol}",
    extra_notes={"purpose": "judgment filter study"},
)
print(f"{setup} {symbol} {time.time() - t:.0f}s {r.line()}", flush=True)
