"""Same-half-hour periodicity on index futures (pre-registered 2026-11-02, before any run).

Idea: Heston, Korajczyk & Sadka (2010, J. Finance) found that a stock's return in
a given half-hour of the day predicts its return in the *same* half-hour on
later days, for up to ~40 days. It was shown on the NYSE cross-section; no
replication on index futures was found (docs/research/strategy-search-3.md).
None of the ~310 versions tested so far in this project uses it.

Rule (13 half-hour slots, 09:30-16:00; the last slot ends at the 15:55 time-out):
- For slot h on day t, the signal is the sign of the average slot-h return
  (slot close minus slot open) over the previous N tradable days, in ATR units.
- Enter at the slot's first bar open in that direction, exit at the open of the
  bar after the slot ends. Disaster stop 0.5 x the 14-day ATR.
- Only the pre-registered variants below are run: N = 20 and N = 40.

The pass bar (same as screen 1, counting every version tried so far):
- MNQ: mean net R per trade > 0, day-bootstrap 95% CI above 0, DSR > 0.95.
- MES: mean net R > 0.
A pass goes to the walk-forward business test (walkforward.py), then paper.

Also printed: the raw predictive statistic (pooled correlation of a slot's
return with its N-day average), so a "no" can be told apart from "costs ate it".

Research data only (screen.load refuses the holdout by default).
Usage: uv run python scripts/research/periodicity.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import screen

from moon_ai.backtest.stats import bootstrap_mean_ci, deflated_sharpe, sharpe

SLOT = 30
LOOKBACKS = (20, 40)  # pre-registered; nothing else is run
PRIOR_VERSIONS = 312  # versions tested before this file (leaderboard + screens)


def slot_returns(mk: screen.Market) -> np.ndarray:
    """(days, 13) slot return in ATR units; the last slot ends at the 15:55 bar."""
    out = np.full((len(mk.days), 13), np.nan)
    for h in range(13):
        a, b = h * SLOT, min((h + 1) * SLOT, screen.TIMEOUT_IDX + 1)
        out[:, h] = (mk.c[:, b - 1] - mk.o[:, a]) / mk.atr
    out[~mk.tradable] = np.nan
    return out


def signals(rets: np.ndarray, n: int) -> np.ndarray:
    sig = np.zeros_like(rets)
    for t in range(n, len(rets)):
        past = rets[t - n : t]
        mean = np.nanmean(past, axis=0)
        ok = (~np.isnan(past)).sum(0) >= n // 2
        sig[t] = np.where(ok, np.sign(mean), 0)
    return sig


def run(mk: screen.Market, n: int):
    rets = slot_returns(mk)
    sig = signals(rets, n)
    # predictive statistic, before costs
    x = np.array([np.nanmean(rets[t - n : t], axis=0) for t in range(n, len(rets))])
    y = rets[n:]
    ok = ~np.isnan(x) & ~np.isnan(y)
    corr = float(np.corrcoef(x[ok], y[ok])[0, 1])
    daily = np.zeros(len(mk.days))
    trades = []
    for h in range(13):
        a = h * SLOT
        end = min((h + 1) * SLOT, screen.TIMEOUT_IDX + 1) - 1
        side = sig[:, h].astype(int)
        r = screen.simulate(mk, side, np.full(len(side), a), 0.5 * mk.atr, None, exit_idx=end)
        trades.append(r[~np.isnan(r)])
        daily += np.nan_to_num(r, nan=0.0)
    return corr, int(ok.sum()), np.concatenate(trades), daily


def main() -> int:
    mnq, mes = screen.load("MNQ.v.0"), screen.load("MES.v.0")
    print(f"MNQ {len(mnq.days)} days ({mnq.days[0]} to {mnq.days[-1]}), MES {len(mes.days)} days")
    n_trials = PRIOR_VERSIONS + len(LOOKBACKS)
    results = {n: (run(mnq, n), run(mes, n)) for n in LOOKBACKS}
    var_sr = float(np.var([results[n][0][3].mean() / results[n][0][3].std() for n in LOOKBACKS]))
    var_sr = max(var_sr, 1e-4)  # two variants say little about the spread; floor it
    for n, ((c1, k1, x1, d1), (c2, _k2, x2, _d2)) in results.items():
        lo, hi = bootstrap_mean_ci(d1)
        dsr = deflated_sharpe(d1, n_trials, var_sr)
        ok = x1.mean() > 0 and lo > 0 and dsr > 0.95 and x2.mean() > 0
        print(
            f"N={n}: corr MNQ {c1:+.4f} (n={k1}) MES {c2:+.4f} | "
            f"MNQ {len(x1)} trades {x1.mean():+.4f}R/trade, daily-R CI [{lo:+.3f}, {hi:+.3f}], "
            f"Sharpe/yr {sharpe(d1) * math.sqrt(252):+.2f}, DSR {dsr:.3f} | "
            f"MES {x2.mean():+.4f}R/trade -> {'PASS' if ok else 'fail'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
