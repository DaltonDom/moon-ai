# Can judgment rescue the ICT setups? (2026-11-03)

**Answer: no.** Neither Tanja Trades' stated cues nor the walk-forward ML filter turns the ICT setups profitable. Most "judgment" made results worse out of sample.

## What was tested

- **The setups:** NY AM Silver Bullet, NY PM Silver Bullet, OTE pullback and the 2022 model, each with its pre-registered default. They were backtested on MNQ and MES, 2019-06-03 to 2025-11-01 (in-sample only), using `scripts/research/judgment_backtest.py`. Every one of the eight runs lost money.
- **Each candidate is labelled as if taken:** 3,193 candidates in all, scored in net R after costs.
- **Three cues from Tanja's own description** ([strategy video](https://youtu.be/qUETEAyp-DE), stream titles):
  - The sweep was of a major level (opening range, overnight, prior day, Asia, London) rather than a minor swing.
  - The traded index was the right one: stronger for longs and weaker for shorts, MNQ vs MES, measured since 09:30 and over the last 60 minutes.
  - The FVG was fresh rather than old.
- **Judged two ways** (`scripts/research/judgment_study.py`):
  - As fixed rules, with nothing fitted.
  - Through the repo's ML filter (`moon_ai.ml.train`), scored only on trades it never trained on (purged walk-forward). Run once with the v1 features and once with v1 plus Tanja's cues.

## Results, net R per trade

| | Candidates | Mean R | 95% CI |
|---|---|---|---|
| Take every candidate (pooled) | 3,193 | −0.32 | −0.37 to −0.27 |
| Major-level sweep only | 25 | −0.26 | −0.83 to +0.42 |
| Right index (since 09:30) | 643 | −0.30 | −0.40 to −0.20 |
| Wrong index (since 09:30) | 594 | −0.27 | −0.39 to −0.15 |
| Fresh FVG (≤ 15 min) | 751 | −0.37 | −0.47 to −0.26 |

**ML filter, out of sample:**

| Group | Take all | Filter, v1 | Filter, v1 + Tanja |
|---|---|---|---|
| All setups, MNQ + MES | −0.29R | −0.44R (6% kept) | −0.57R (8% kept) |
| All setups, MNQ only | −0.23R | −0.54R | −0.56R |
| NY AM Silver Bullet | −0.21R | −0.10R (34% kept) | −0.14R |
| NY PM Silver Bullet | −0.53R | −0.82R | −0.66R |
| OTE pullback | −0.27R | −0.04R (4% kept) | +0.13R on 30 trades in 6 years (1% kept) |

## Reading

- **No cue flips the sign.** Trading the "right" index is no better than trading the wrong one.
- **Major-level sweeps are rare** (25 in 6 years across both markets) and still negative.
- **The ML filter mostly makes things worse out of sample.** That's the signature of fitting noise.
- **The one positive cell (OTE, 30 trades) is too small to mean anything.** It's one of about a dozen cells looked at.
- **Whatever edge Tanja has is not in rules a bot can measure from price.** It may be in discretion that doesn't reduce to these cues, or not there at all; her streams aren't an audited record.

**Recommendation:** stop working on ICT variants and move to the families the evidence favours (opening-range breakout, multi-day trend following).
