Here is the structured breakdown of the **Opening Range Reversal (ORR)** strategy as presented in the video:

---

### 1. Instrument(s) and Chart Timeframe(s)
* **Instruments:** Stocks (e.g., ARM, LULU shown), Commodities (Gold, Oil), Crypto, Futures, or Forex.
* **Higher Timeframe:** Daily Chart (`1D`) — **Non-negotiable**.
* **Lower Timeframe (Execution):** Sub-1-hour intraday timeframe (1-min, 5-min, 10-min, 15-min, 30-min). **5-minute chart (`5m`) is preferred and used in examples**.

---

### 2. Session / Time Window (with Time Zone)
* **Time Window:** Market Open / Opening Range ("from the bell").
* **Time Zone:** Not stated explicitly.

---

### 3. Setup Conditions (in order)
1. **Determine Daily Trend Bias (Daily Chart):**
   * **Bullish Bias (Long):** Price on the Daily chart is trading **above** the 50-period Simple Moving Average (50 SMA).
   * **Bearish Bias (Short):** Price on the Daily chart is trading **below** the 50-period Simple Moving Average (50 SMA).
2. **Calculate Daily Range Threshold:**
   * Apply the **Average True Range (ATR 14)** indicator on the Daily chart.
   * Calculate 20% of the Daily ATR (`Daily ATR * 0.20`).
3. **Identify the "Sucker Step" (Opening Manipulation Move):**
   * At market open, price makes an aggressive move **counter to the Daily Trend Bias** (e.g., a sharp opening drop on a stock with a Bullish Daily Bias).
   * **Range Condition:** The distance from the high of the opening move to the low of the move must exceed **20% of the Daily ATR**.

---

### 4. Entry Trigger and Order Type
* **Trigger (Long Setup):**
  1. Wait for a bullish (green) candlestick to form near the bottom of the opening sell-off.
  2. Place an entry trigger right above the high of that green candlestick (or the high of the candle marking the initial low).
  3. Entry executes when a subsequent candlestick breaks/exceeds that candlestick's high.
* **Order Type:** Buy Stop / Market order upon high breakout.

---

### 5. Stop-Loss Placement
* Placed directly at/below the **Low of the Day** (the lowest price point reached during the opening sell-off).

---

### 6. Take-Profit / Exit Rules
* **Standard Target:** At least **50% retracement** of the opening move (measured from the low of the day to the high/start of the opening move).
* **Extended/Aggressive Target:** 100% retracement (back to the high/start of the opening move or previous high of day).
* **Trailing / Time Exits / Partials:** Not stated.

---

### 7. Filters
* **50 Simple Moving Average (50 SMA)** on the Daily Chart (Trend Filter).
* **14-period Average True Range (ATR)** on the Daily Chart (Volatility/Range Filter — 20% minimum opening move requirement).

---

### 8. Max Trades Per Day / Risk Per Trade
* **Not stated.**

---

### 9. Claimed Results
* **Win Rate / R:R / Sample Size:** Described as "scary accurate" with a "high accuracy rate," but specific numerical stats (win rate %, R:R ratio, backtest sample size) are **not stated**.

---

### 10. Discretionary Parts
* Filtering out "fake" reversal candles vs. "good" reversal candles when multiple small consolidation candles form at the intraday low before the break occurs.
* Choosing between the standard 50% retracement target versus holding for a full 100% retracement / High of Day target.

---

### 11. Verdict
**MOSTLY MECHANICAL**  
*The core rules for daily bias (> 50 SMA), required opening move size (> 20% Daily ATR), stop loss (Low of Day), target (50% retracement), and candle-high breakout trigger are clearly defined mathematically and visually, with only minor discretion in choosing the trigger candle during extended bottoms.*