Here is the structured breakdown of the trading strategy presented in the video:

### 1. Instrument(s) and Chart Timeframe(s)
* **Instruments:** Forex currency pairs (e.g., EUR/USD, USD/CAD) and Commodities (e.g., Silver).
* **Timeframes:** 
  * **15-minute:** Used for identifying session ranges and the initial 15-minute Opening Range candle.
  * **5-minute:** Used for execution, entry signals, and displacement confirmation.

---

### 2. Session / Time Window (with Time Zone)
* **Time Zone:** New York Time (`UTC-5` / `UTC-4`).
* **Opening Range Window:** 09:30 to 09:45 NY Time (first 15-minute candle of the NYSE open).
* **Trading Session:** New York Session only.
* **Session Mapping:**
  * **Asia Session:** Range formation (liquidity build-up).
  * **London Session:** Directional push/swing (sweeping Asia liquidity).
  * **New York Session:** Reversal trading window.

---

### 3. Setup Conditions (in Order)
1. **Define Opening Range (Step 01):** Mark the High and Low of the first 15-minute candle of the NY session (09:30–09:45 NY time).
2. **Session Alignment Filter (Step 02):**
   * Identify Asia range (high and low).
   * Identify London push direction (must sweep either the Asian high or low).
   * **Bias Rule:** If London pushes down and sweeps the Asia low, look for a **Bullish NY Reversal**. If London pushes up and sweeps the Asia high, look for a **Bearish NY Reversal**.
   * *Exception:* If London sweeps **both** top and bottom of the Asia range, look for **NY Continuation** instead of a reversal.
3. **Displacement Confirmation (5-min chart):**
   * Wait for an impulsive push out of the top/bottom of the 15-min Opening Range.
   * A 5-minute candle must **close** outside the range boundary (wicks without a candle body close do not count).
   * Move must consist of **3 to 4 strong/large candles in a row** breaking recent market structure (taking out a recent high or low).
4. **Point of Interest (POI) Identification:**
   * Identify a **Demand Zone** (last opposite-colored candle before the explosive move) or a **Fair Value Gap (FVG)** created during the displacement move.

---

### 4. Entry Trigger and Order Type
* **Order Type:** Market Entry upon pullback to the POI.
* **Triggers:**
  * **Primary Trigger (Ideal):** A 5-minute Bullish/Bearish Engulfing candle pattern closing inside or at the boundary of the Demand/Supply zone or FVG.
  * **Secondary Trigger:** Price wicking into and holding the Demand/Supply zone / FVG level, entering as price breaks back out of the zone (used when an engulfing pattern does not form).

---

### 5. Stop-Loss Placement
* Placed just below the bottom of the Demand zone (for longs) or above the Supply zone (for shorts).
* Alternatively, placed around the mid-line / below the Fair Value Gap zone.

---

### 6. Take-Profit / Exit Rules
* **Fixed R:R Target:** 1:1.5 to 1:2.2 Risk-to-Reward ratio.
* **Structural Target:** Previous swing high/low, or Session liquidity levels (e.g., London Session high/low, Asia High/Low).
* **Partial Exits:** Scaling out of positions as major session liquidity target levels are reached.

---

### 7. Filters
* **Indicator Settings:**
  * **LuxAlgo - ORB & Targets (`Opening Range with Breakouts & Targets`):**
    * *Time Period:* 15 min
    * *Custom Range:* 09:30 to 09:45
    * *Time Zone:* UTC-5 (New York)
  * **Session Range Indicator:** (e.g., `FXN - Asian Session Range`) to highlight Asia, London, and NY session blocks.
* **Directional Filter:** Only trade NY reversals in the opposite direction of the London push unless both sides of the Asia range were swept.

---

### 8. Max Trades per Day / Risk per Trade
* **Max Trades per Day:** *Not stated*
* **Risk per Trade:** *Not stated*

---

### 9. Claimed Results
* **Win Rate:** 79.45%
* **Risk-to-Reward Ratio:** 1:1.5 – 1:2.2
* **Sample Size:** 1,017 trades
* **Testing Method:** Backtested 1,000+ times on a software platform combined with live trading.

---

### 10. Discretionary Parts
* Judging whether candles in a breakout are "large/strong" enough to count as true "displacement."
* Selecting between Demand/Supply zones versus Fair Value Gaps for POI placement.
* Determining entry timing when a clear engulfing candle does not form (entering on "level holding").
* Choosing between fixed Risk-to-Reward targets (1.5R–2.2R) and structural liquidity targets.

---

### 11. Verdict
**DISCRETIONARY**
*While the session ranges and 15-minute Opening Range boundaries can be coded systematically, identifying displacement quality, selecting entry POIs (FVG vs. Demand), and choosing variable exit rules require manual trader judgment.*