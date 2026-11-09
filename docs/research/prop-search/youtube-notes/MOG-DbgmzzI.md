Here is the exact trading strategy extracted from the video:

### 1. Instrument(s) and chart timeframe(s)
* **Instruments:** US Equities & Index ETFs (tested across 600+ stock symbols including SPY, QQQ, TSLA, META, NVDA, AAPL, etc.).
* **Chart Timeframe:** Opening Range timeframes of **5-Minute**, **15-Minute**, and **30-Minute** (backtested using 1-minute candle data).

---

### 2. Session / time window (with time zone)
* **Session Window:** Begins at market open to establish the initial Opening Range (5, 15, or 30 minutes). Time zone is not explicitly stated.
* **Exit Window:** Trades remaining open are liquidated at End of Day (EOD).

---

### 3. Setup conditions (every condition, in order)
1. At market open, observe price action for the chosen duration (**5-Min**, **15-Min**, or **30-Min**) to establish the **Opening Range High** and **Opening Range Low**.
2. Calculate the **Opening Range Width** ($\text{Range High} - \text{Range Low}$).
3. Wait for price to move outside the Opening Range boundaries.

---

### 4. Entry trigger and order type
* **Long Entry:** Price breaks out above the Opening Range High.
* **Short Entry:** Price breaks out below the Opening Range Low.
* **Order Type:** Not stated.

---

### 5. Stop-loss placement
Tested under two specific rule sets:
* **Full Stop:** Placed at 1.0x Opening Range width from entry (opposite side of the Opening Range).
* **Half Stop:** Placed at 0.5x Opening Range width from entry (midpoint of the Opening Range).

---

### 6. Take-profit / exit rules (incl. time exits, trailing, partials, breakeven)
* **Full Target:** 1.0x Opening Range width projected from the breakout entry price.
* **Half Target:** 0.5x Opening Range width projected from the breakout entry price.
* **End of Day (EOD) Exit:** Any trade that reaches neither target nor stop-loss by market close is exited at EOD.
* **Trailing / Partials / Breakeven:** Not stated.

---

### 7. Filters (news, days, bias, indicators with exact settings)
* **Directional Bias Filter:** Long and Short setups evaluated independently (Short trades resolve faster; Long trades yield larger average gains).
* **Symbol-Specific Selection Filter:** Matching specific stocks to their optimal timeframe (e.g., TSLA performs best on 30-min; META performs best on 5-min; index ETFs like SPY and QQQ show ~50% baseline win rates across all timeframes).
* **Technical Indicators / News / Day Filters:** Not stated.

---

### 8. Max trades per day / risk per trade
* **Max trades per day:** Not stated.
* **Risk per trade:** Not stated.

---

### 9. Claimed results (win rate, R:R, sample size, period, how tested: live/backtest/manual)
* **How Tested:** Programmatic backtest via ORB Setups backtester using 1-minute historical candle data.
* **Sample Size & Period:** 1.17 million trades backtested across 600+ symbols over 300+ trading days.

#### Baseline Timeframe Performance (Half Target / Full Stop across 600+ symbols):
* **5-Min ORB:** 53.78% Win Rate | Avg Range Width: $0.76 | Unresolved at EOD: 3.3%
* **15-Min ORB:** 50.97% Win Rate | Avg Range Width: $0.94
* **30-Min ORB:** 49.38% Win Rate | Avg Range Width: $1.04 | Unresolved at EOD: 12.8%

#### 5-Minute ORB Rule Combinations:
* **Half Target / Full Stop:** 68.87% Win Rate | Expectancy (EV): $0.018 / trade
* **Half Target / Half Stop:** 54.12% Win Rate | Expectancy (EV): $0.012 / trade
* **Full Target / Full Stop:** 46.82% Win Rate | Expectancy (EV): $0.044 / trade *(Best EV overall)*
* **Full Target / Half Stop:** 39.12% Win Rate | Expectancy (EV): $0.008 / trade

#### Symbol Performance Examples:
* **TSLA:** 57.46% WR (5-Min), 52.10% WR (15-Min), $0.996 EV / trade (30-Min)
* **META:** 56.54% WR (5-Min), 37.67% WR (15-Min), 49.2% WR (30-Min)
* **SPY / QQQ:** ~50% Win Rate across all timeframes

#### Longs vs. Shorts (5-Minute Timeframe):
* **Short Trades:** 54.14% Win Rate | Avg Win: 0.4 | Avg Loss: 0.7 | 1x Baseline PnL
* **Long Trades:** 53.42% Win Rate | Avg Win: 0.8 | Avg Loss: 0.7 | ~2x Short PnL

---

### 10. Discretionary parts
* Selecting symbol-specific timeframes and choosing target/stop combinations based on individual trader risk preference.

---

### 11. Verdict
**FULLY MECHANICAL**  
*Reason:* The Opening Range definition, breakout entry, stop-loss, profit-target multiples, and EOD time exits are defined entirely by strict mathematical rules suitable for automated trading.