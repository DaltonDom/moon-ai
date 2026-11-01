"""Backtest statistics: trade metrics, bootstrap CIs, the Deflated Sharpe Ratio and PBO.

docs/design.md, "Setup testing protocol" and "Verifiability".

- **Metrics** are per trade in R (net of costs) and in dollars.
- **Sharpe and Sortino** are computed on daily R (trades summed per CME
  trading day; days without trades count as 0) and annualised with sqrt(252).
- **Deflated Sharpe Ratio** (Bailey & Lopez de Prado, 2014): the probability
  that the true Sharpe is above the best Sharpe expected from `n_trials`
  unskilled trials, allowing for non-normal returns. It is computed on
  per-period (daily, not annualised) Sharpe ratios.
- **PBO** (Bailey, Borwein, Lopez de Prado & Zhu, 2017) uses combinatorially
  symmetric cross-validation: the share of in-sample/out-of-sample splits in
  which the in-sample best trial ranks in the bottom half out of sample.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from statistics import NormalDist

import numpy as np

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class Metrics:
    trades: int
    win_rate: float
    profit_factor: float  # gross $ won per gross $ lost (inf with no losses)
    expectancy_r: float  # mean net R per trade
    avg_win_r: float
    avg_loss_r: float  # negative
    max_drawdown_r: float  # most negative peak-to-trough of cumulative R (<= 0)
    net_r: float
    net_usd: float
    sharpe: float  # annualised, daily R
    sortino: float  # annualised, daily R, downside deviation


def metrics(r: Sequence[float], usd: Sequence[float], daily_r: Sequence[float]) -> Metrics:
    """`r`/`usd`: one value per closed trade, in time order. `daily_r`: R per
    trading day over the whole period, zeros included."""
    r_ = np.asarray(r, float)
    usd_ = np.asarray(usd, float)
    wins, losses = r_[r_ > 0], r_[r_ <= 0]
    gross_win, gross_loss = usd_[usd_ > 0].sum(), -usd_[usd_ <= 0].sum()
    curve = np.concatenate([[0.0], np.cumsum(r_)])
    return Metrics(
        trades=len(r_),
        win_rate=len(wins) / len(r_) if len(r_) else 0.0,
        profit_factor=(gross_win / gross_loss) if gross_loss > 0 else math.inf,
        expectancy_r=float(r_.mean()) if len(r_) else 0.0,
        avg_win_r=float(wins.mean()) if len(wins) else 0.0,
        avg_loss_r=float(losses.mean()) if len(losses) else 0.0,
        max_drawdown_r=float((curve - np.maximum.accumulate(curve)).min()),
        net_r=float(r_.sum()),
        net_usd=float(usd_.sum()),
        sharpe=sharpe(daily_r) * math.sqrt(252),
        sortino=sortino(daily_r) * math.sqrt(252),
    )


def sharpe(x: Sequence[float]) -> float:
    """Per-period Sharpe ratio (no risk-free rate): mean / sample std."""
    a = np.asarray(x, float)
    if len(a) < 2 or a.std(ddof=1) == 0:
        return 0.0
    return float(a.mean() / a.std(ddof=1))


def sortino(x: Sequence[float]) -> float:
    """Per-period Sortino ratio: mean / downside deviation (target 0)."""
    a = np.asarray(x, float)
    down = np.sqrt(np.mean(np.minimum(a, 0.0) ** 2)) if len(a) else 0.0
    return float(a.mean() / down) if down > 0 else 0.0


def bootstrap_mean_ci(
    x: Sequence[float], n: int = 10_000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean."""
    a = np.asarray(x, float)
    if len(a) == 0:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, len(a), size=(n, len(a)))].mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def probabilistic_sharpe(
    sr: float, benchmark: float, n_obs: int, skew: float, kurt: float
) -> float:
    """P(true Sharpe > benchmark), per-period Sharpe, `kurt` = raw kurtosis (3 if normal)."""
    if n_obs < 2:
        return 0.0
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr**2
    if denom <= 0:
        return 0.0
    return _N.cdf((sr - benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom))


def expected_max_sharpe(n_trials: int, var_trial_sharpe: float) -> float:
    """Expected maximum of `n_trials` unskilled per-period Sharpe ratios (SR0)."""
    if n_trials <= 1 or var_trial_sharpe <= 0:
        return 0.0
    return math.sqrt(var_trial_sharpe) * (
        (1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
        + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e))
    )


def deflated_sharpe(returns: Sequence[float], n_trials: int, var_trial_sharpe: float) -> float:
    """DSR of one return series, given how many trials were run and the
    variance of their per-period Sharpe ratios."""
    a = np.asarray(returns, float)
    if len(a) < 3 or a.std(ddof=1) == 0:
        return 0.0
    sr = sharpe(a)
    centred = a - a.mean()
    s = a.std(ddof=0)
    skew = float((centred**3).mean() / s**3)
    kurt = float((centred**4).mean() / s**4)
    return probabilistic_sharpe(
        sr, expected_max_sharpe(n_trials, var_trial_sharpe), len(a), skew, kurt
    )


def pbo(returns: np.ndarray, n_blocks: int = 16) -> float:
    """Probability of Backtest Overfitting by CSCV.

    `returns`: T x N, one column per trial, rows aligned in time (e.g. daily R).
    """
    m = np.asarray(returns, float)
    t, n = m.shape
    if n < 2:
        raise ValueError("PBO needs at least two trials")
    n_blocks -= n_blocks % 2
    if t < n_blocks:
        raise ValueError(f"need at least {n_blocks} rows, got {t}")
    blocks = np.array_split(np.arange(t), n_blocks)
    logits = []
    for chosen in combinations(range(n_blocks), n_blocks // 2):
        is_rows = np.concatenate([blocks[i] for i in chosen])
        oos_rows = np.concatenate([blocks[i] for i in range(n_blocks) if i not in chosen])
        is_sr = _col_sharpe(m[is_rows])
        oos_sr = _col_sharpe(m[oos_rows])
        best = int(np.argmax(is_sr))
        # Relative rank of the IS winner out of sample, in (0, 1).
        rank = (np.sum(oos_sr < oos_sr[best]) + 0.5 * (np.sum(oos_sr == oos_sr[best]) - 1) + 1) / (
            n + 1
        )
        logits.append(math.log(rank / (1 - rank)))
    return float(np.mean(np.asarray(logits) <= 0))


def _col_sharpe(m: np.ndarray) -> np.ndarray:
    sd = m.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, m.mean(axis=0) / sd, 0.0)
