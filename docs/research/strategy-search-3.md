# Strategy search 3: outside research, the edge the goal needs, and two new tests (2026-11-02)

The question: is there a proven strategy or AI model that makes about $2,000 a month on prop accounts (design.md, Revision 2026-11-02b)?

**Short answer: not yet, and nothing public is proven.** This round found:

- what the goal needs, worked out precisely;
- that no published intraday rule or open AI model has out-of-sample trading evidence after costs;
- two genuinely untested ideas, now built and ready to run.

No market data was bought or used. The Databento account returned `402 account_insufficient_funds`, and this session's network blocks every other data source.

## 1. What the goal needs (`required_edge.py`)

Synthetic trades of a known edge were run through the same business simulation the walk-forward uses:

- buy an evaluation, then pass it or blow it;
- take funded payouts by the plan's rules, and replace blown accounts;
- 3 copy-traded accounts, with at most $500 a month on evaluation fees;
- 2R target, 1R stop ($50 a micro), 24 months, 300 paths per cell;
- the best plan and risk per edge, out of LucidFlex 50K, Tradeify Growth 50K or Tradeify Select Flex 50K, at $200–800 a trade.

"Edge" is the mean R per trade **after costs**. The income columns are a month's total across the 3 accounts, after fees. "Typical" is the median path and "bad case" the 10th percentile. The last column is the share of paths that made money in at least 6 of 8 quarters.

**One trade a day:**

| Edge | Best plan and risk | Typical month | Bad case (p10) | Paths at $2k+ a month | 6 of 8 quarters | Evaluations a year |
|---|---|---|---|---|---|---|
| +0.00R | lucidflex_50k $600 | $302 | $-258 | 5% | 4% | 11.4 |
| +0.05R | lucidflex_50k $600 | $706 | $-120 | 17% | 11% | 10.9 |
| +0.10R | tradeify_growth_50k $600 | $1,435 | $-7 | 35% | 21% | 8.0 |
| +0.15R | tradeify_growth_50k $600 | $2,588 | $463 | 62% | 42% | 6.2 |
| +0.20R | tradeify_growth_50k $600 | $4,084 | $1,470 | 82% | 65% | 4.5 |
| +0.30R | tradeify_select_flex_50k $800 | $7,373 | $1,930 | 90% | 67% | 5.1 |
| +0.40R | tradeify_select_flex_50k $600 | $10,714 | $6,993 | 100% | 98% | 2.9 |

**Two independent trades a day:**

| Edge | Best plan and risk | Typical month | Bad case (p10) | Paths at $2k+ a month | 6 of 8 quarters | Evaluations a year |
|---|---|---|---|---|---|---|
| +0.00R | tradeify_growth_50k $800 | $781 | $-435 | 29% | 14% | 7.3 |
| +0.05R | tradeify_growth_50k $800 | $2,501 | $-267 | 56% | 36% | 5.6 |
| +0.10R | tradeify_growth_50k $800 | $3,878 | $578 | 77% | 56% | 4.5 |
| +0.15R | tradeify_growth_50k $800 | $5,337 | $1,865 | 90% | 72% | 3.5 |
| +0.20R | tradeify_growth_50k $800 | $6,876 | $4,188 | 98% | 86% | 2.6 |
| +0.30R | tradeify_select_flex_50k $600 | $12,271 | $3,242 | 93% | 80% | 4.6 |
| +0.40R | tradeify_select_flex_50k $600 | $16,852 | $12,186 | 99% | 97% | 2.3 |

Logs are in `walkforward-logs/required-edge-{1,2}perday.log`.

**Reading:**

- **About +0.15R a trade at one trade a day is the minimum.** That takes the typical path to about $2.5k a month. Reaching the goal in at least 6 of 8 quarters reliably needs about +0.2R.
  - In win-rate terms, a 2R target breaks even at 33.3%. The goal needs about 38–40% winners *after* costs.
- **A second, uncorrelated trade a day halves the edge needed** (+0.05 to +0.10R). More independent bets is the strongest lever. This argues for several small, unrelated signals over one strong one.
- **A zero-edge strategy shows a small positive median (+$300 to +$800 a month).** This is the option value of the prop structure: the most an account can lose is its fee, while payouts are real money.
  - Don't read this as free money. Real strategies with "no edge" lose costs, and the honest walk-forwards (−$400 to +$375 a month) show that.
  - The simulation is also kinder than reality in three ways: trades are independent with no losing streaks bunched by regime, stops fill exactly, and Lucid's 5-payout limit before live review isn't modelled.
  - It does explain why the best honest results so far land just above zero.
- **Where the search stands against the bar.** The best honest signal found, first-hour momentum, made +0.11R a trade in-sample and −0.06R on the fresh year. The bar is roughly double the in-sample number, and must hold out of sample.

## 2. Outside research: is anything proven?

The full notes are in the session's research file and are summarised here. Most sources were read through search excerpts: the network blocked arXiv, SSRN and the firms' help centres, and only GitHub could be read in full.

### Published intraday effects not yet tested here

No post-2020 published rule tradable from 1-minute OHLCV has an out-of-sample trading record.

| Effect | Evidence | Usable here? |
|---|---|---|
| Dealer-gamma intraday momentum (Baltussen, Da, Lammers, Martens, JFE 2021) | Strong in 1974–2020, *conditional on dealers being short gamma*. A vendor measurement over 1,085 SPX sessions in the 0DTE era finds the unconditional effect near zero (t = 0.6). | Needs options open-interest data. Without it, it is Gao's last-half-hour momentum, already retired. |
| 0DTE gamma regime (Dim, Eraker & Vilkov; Adams et al. 2025) | Regressions only, no trading test. | Needs options data. |
| Pre-FOMC drift (Lucca & Moench) | Gone after 2015 (Kurov, Wolfe & Gilbert 2021). | No. |
| Macro-announcement-day premium | A daily effect; a 2022 paper attributes it to day of month. | No (only 8–12 days a year). |
| Leveraged-ETF rebalancing into the close | Real but modest, and absorbed by the market. It is momentum into the close. | Overlaps Gao, already retired. |
| **Same-half-hour periodicity (Heston, Korajczyk & Sadka, JF 2010)** | Strong on NYSE stocks; **no index-futures replication found**. | **Yes. Built: `periodicity.py`.** |
| OPEX week, pre-holiday, Monday | Weak or decaying; small samples. | Not worth the trials. |

### "Proven" AI models

None has independent out-of-sample trading profit after costs. The papers report forecasting metrics.

- **Kronos** (AAAI 2026; MIT license; mini 4M, small 25M, base 102M parameters).
  - Pre-trained on candlesticks from 45 exchanges.
  - Its headline result is a forecasting metric (RankIC).
  - The repo's backtest is a Chinese daily-stock demo with no costs, and the repo calls itself "not production-ready."
  - It runs on a CPU. **Built: `kronos_test.py`, zero-shot, no tuning.**
- **Chronos / Chronos-Bolt, TimesFM, Moirai, Lag-Llama.**
  - A Nov 2025 test of zero-shot Chronos on daily stock returns gave a Sharpe of 0.07, against 6.79 for a plain CatBoost.
  - A 2026 benchmark finds the foundation models significant in only 2 cases, with no costs modelled.
- **The closest match to this project:** a 2026 preprint, "Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ."
  - Out-of-sample accuracy was 50.0–50.9% on 5-minute MNQ bars, against a 51.8% base rate (permutation p = 0.135 and 0.515).
  - That matches this project's own ML result (AUC 0.45–0.48).
- **DeepLOB / TransLOB** need full order-book data. Their profit tests reportedly ignore fees.

### Prop-firm rules (third-party sources, July–Oct 2026; confirm on the firms' pages)

- **Lucid and Tradeify both ban hedging** across a trader's own accounts and across firms (Lucid's "Prohibited Hedging" article; Tradeify's trading rules). Long-on-one, short-on-another schemes are off the table.
- **LucidFlex 50K:**
  - about $136;
  - $3k target, $2k EOD trailing drawdown that locks at +$100;
  - the evaluation consistency rule is 50%, or possibly 40% since 2026-10-19;
  - payouts need 5 winning days of $150 or more, and each is at most 50% of profit and at most $2k;
  - live review after 5 payouts.
- **Tradeify Growth 50K:**
  - $145;
  - $1,250 soft daily limit;
  - 35% funded consistency;
  - the balance must reach $53k before a payout;
  - payout caps of $1.5k, $2k and $2.5k.
- **`config/prop_firms.toml` matches these within the stated uncertainty.** The open differences are Lucid's consistency rule (40% vs 50%) and the fee ($130 vs $136).

## 3. The two new tests (pre-registered here, before any run)

Both are fixed in code and add 4 versions to the luck count (now about 316).

1. **`scripts/research/periodicity.py`: same-half-hour periodicity.**
   - In each of 13 half-hours, trade the sign of that half-hour's average return over the last N days (N = 20 or 40).
   - Exit at the end of the half-hour, with a 0.5 ATR disaster stop.
   - It also prints the raw predictive correlation, so "no signal" can be told apart from "costs ate it".
   - Up to 13 small trades a day: the "many independent bets" shape that section 1 favours.
2. **`scripts/research/kronos_test.py`: Kronos-small, zero-shot.**
   - At 10:30 and 13:00, forecast the next 60 minutes from the last 400 five-minute bars, and trade the sign.
   - Stop 0.25 ATR; exit after 60 minutes.
   - Forecasts are saved, so any later threshold idea is a cheap walk-forward on the saved file.

**Pass bar for both:** MNQ mean R above 0 with a day-bootstrap CI above 0, DSR above 0.95, and MES mean above 0. A pass then needs the walk-forward business test **at the section 1 bar (+0.15R a trade at one trade a day, or the equivalent)**, a holdout look and paper trading.

**To run** (on the Mac, where the data is; or here after a Databento top-up of about $20 for MNQ and MES 2019-05 to 2025-10):

```sh
uv run python scripts/research/periodicity.py
git clone https://github.com/shiyu-coder/Kronos ../Kronos
uv pip install torch einops huggingface_hub safetensors
uv run python scripts/research/kronos_test.py --kronos-dir ../Kronos --limit 60   # smoke test
uv run python scripts/research/kronos_test.py --kronos-dir ../Kronos              # full, a few hours on CPU
```

## 4. What would most likely change the answer

In order of expected value per dollar:

1. **Run the two tests above.** They cost nothing on the Mac.
2. **Order-flow data** (Databento `tbbo` or `mbp-1` for MNQ). This is information the 1-minute bars don't have: aggressor side and book imbalance. Price it first with `moon-ai download --schema tbbo --dry-run`.
3. **Forward testing.** Both "winners" that were checked on the fresh year lost there. The only fully fresh data left is from November 2026 onward. Paper-trade any candidate before buying an evaluation.

**Not recommended:**

- more rule variants on 1-minute bars (about 310 tried, and the luck bar keeps rising);
- cross-account hedging (banned);
- any vendor "AI bot" without a verifiable live record.
