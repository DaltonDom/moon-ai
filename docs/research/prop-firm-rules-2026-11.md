# Prop-firm account rules for the simulator (2026-11)

Researched 2026-11-02. These are the account rules for Lucid Trading and Tradeify 50K plans, set out so a simulator can replay trades through them.

## How this was sourced

- The sandbox could not fetch any of the four firm domains. `support.lucidtrading.com`, `lucidtrading.com`, `help.tradeify.co` and `tradeify.co` all failed to resolve or were refused by the proxy.
- Every figure below therefore came from **web search restricted to the firm's own domain**. The search tool returns short excerpts and summaries, not full pages. Quoted text is what the search excerpt showed.
- No figure here was read on a full page. Before going live, re-check each one on the live help article or the checkout page.
- **UNVERIFIED** marks anything that no first-party excerpt supports.
- Page ages come from the search tool where it showed them. Most Lucid and Tradeify help articles showed as updated about 12 to 16 days ago (mid-October 2026). The Tradeify "Essential Trading Rules Overview" showed as about 111 days old.

## Rules common to both firms (model these first)

- **Drawdown.** Every plan here uses an end-of-day (EOD) trailing max loss.
  - The floor is recalculated only from the end-of-day closing balance, and it only moves up.
  - Tradeify says the limit is **enforced in real time**. If net liquidation value (open P&L included) touches the floor intraday, the account fails, even if it recovers before the close.
  - Lucid's excerpts say the MLL is set from the highest EOD closing balance. Whether Lucid also enforces it intraday on open equity is **UNVERIFIED**. Simulate it as real-time to be safe.
- **Lock.** On a 50K account the floor starts $2,000 below the high-water mark. It stops trailing once the EOD balance reaches $52,100, at a floor of $50,100 (starting balance + $100). A payout request also locks it at once.
- **Flat by 4:45 PM ET, Monday to Friday.** Both firms auto-close open positions at that time, and the auto-close is not a breach. No overnight holds. Tradeify's holiday early close is 12:59 PM ET.
- **Session.** 6:00 PM ET to 5:00 PM ET the next day. A "trading day" uses this session.

---

## Lucid Trading — LucidFlex 50K (primary)

### Evaluation
- **Price:** $130. Reset: $80.75. These come from a lucidtrading.com product-category listing, which may be stale.
  - The price depends on add-ons. Turning the daily loss limit on lowers the price, and the 50% consistency add-on raises it. The exact deltas are **UNVERIFIED**.
  - There is no activation fee: "no activation fees to upgrade to funded account".
- **Profit target:** $3,000.
- **Max loss:** $2,000, EOD trailing. The table lists "Initial Trail Balance $52,100, Locked MLL Balance $50,100" for 50K.
  - The Drawdown article says that "evaluation and funded accounts use an End-of-Day Drawdown". The lock table appears to apply to both phases, but whether the evaluation also locks is not stated outright.
- **Daily loss limit:** Optional, chosen at checkout. It is a soft breach: "you will simply be locked out until the next trading session." The LucidFlex 50K DLL dollar amount is **UNVERIFIED**. LucidPro uses $1,200 for 50K, which is a plausible default.
- **Consistency:** 40%: the largest single day's profit must be at most 40% of total account profit. With the paid add-on it is 50%.
  - This applies to the evaluation only.
  - Effective minimum days: 3 at 40%, or 2 at 50% ("pass in as few as 3 days").
- **Minimum days:** No separate minimum. The consistency rule implies at least 3 days (2 with the add-on).
- **Max size:** 4 minis or 40 micros. There is no scaling in the evaluation.

### Funded
- **Max loss:** $2,000, EOD trailing. It locks at a $50,100 floor once the EOD balance reaches $52,100. "Once you request a payout from LucidFlex, your MLL automatically adjusts to the Locked MLL Balance."
- **Daily loss limit:** Optional, set at purchase, and a soft breach. If the DLL is on, intraday on-demand payouts are possible, and they pause trading for the rest of that day.
- **Consistency:** None.
- **Scaling (50K):** The cap starts at 2 minis or 20 micros and rises with profit to 4 minis or 40 micros.
  - Tiers are recalculated at the session close, not intraday.
  - The excerpt's table columns were ambiguous. The exact 50K profit thresholds for the 3-mini and 4-mini tiers are **UNVERIFIED**.
- **Payout rules:**
  - You need at least 5 days in the cycle with at least $150 profit each, and the cycle's net profit must be positive. The day count resets after each payout.
  - Minimum request: $500. Maximum: 50% of profit, up to $2,000 per request.
  - There is no fixed payout window. You can request on any day once eligible, and funds arrive within 2 business days.
  - Buffer: none ("no payout buffer").
  - Split: 90/10.
- **Payout count before moving to live:** Conflicting.
  - The Payouts article says "up to 5 payouts … after which they will be moved live".
  - The "LucidFlex Live (Legacy)" article says the move happens after the "sixth and final" payout.
  - Treat 5 as current and 6 as legacy (**conflict**).
- **News:** Allowed on Flex, Pro and Direct.
- **Microscalping:** Flagged if more than 50% of profit comes from trades held 5 seconds or less.

## Lucid Trading — LucidPro 50K (exists)

### Evaluation
- **Price:** **UNVERIFIED.** The product page excerpt showed the rules but not the price. A reset product exists at lucidtrading.com/product/lucidreset-50k-nt-tdv/, but its price is also **UNVERIFIED**.
  - Billing is a one-time fee with no rebilling.
- **Profit target:** $3,000.
- **Max loss:** $2,000, EOD trailing.
- **Daily loss limit:** $1,200, fixed. It is a soft breach.
  - A newer "LucidPro Customization" article makes the DLL optional at purchase. That conflicts with the fixed $1,200 listed on the product page.
- **Consistency:** "Consistency Rule: None" in the evaluation, per the product page.
- **Max size:** 4 minis or 40 micros.

### Funded
- **Max loss:** $2,000, EOD trailing. The trail starts at $52,100 and locks at a $50,100 floor.
- **Daily loss limit:** Optional and a soft breach.
  - The table shows both a fixed $1,200 DLL and a "scaling DLL" tied to "60% of Peak EOD Balance" (presumably 60% of peak EOD profit).
  - Which one applies is **UNVERIFIED** and conflicting.
- **Scaling:** No scaling plan. The full 4 minis or 40 micros are available immediately.
- **Consistency:** 40% for accounts bought or reset on or after 11/28/2025 at 3:00 PM ET (35% before that).
  - Formula: the largest single-day profit divided by total profit in the payout cycle must be at most 40%.
  - It applies to payouts and resets after each payout.
- **Payout rules:**
  - You need at least $500 profit in the cycle. Minimum request: $500.
  - Caps: $2,000 for the first payout, then $2,500.
  - There is no minimum number of days, and you can request on any day once eligible.
  - Buffer: the balance must stay at least $52,100 (initial MLL + $100) after the payout. Trading after a request that dips into the buffer can get it denied.
  - The FAQ also mentions "buffer requirements", which is consistent with this.
  - Split: 90/10.
  - Accounts bought or reset on or before 2/27/26 move to live after the 6th payout. The rule for current accounts is **UNVERIFIED**.

## Lucid automation policy
- Bots and copiers are allowed.
  - The FAQ answers "Are EAs/bots allowed?" with yes.
  - The "Other Trading Activities" article permits automated systems and copiers, and the trader is liable for any malfunction.
- **Conflict:** The 2025-05-19 LucidDirect Account Agreement requires written approval before using automated software. See `prop-firms-and-order-routing.md`.

---

## Tradeify — Growth 50K

### Evaluation
- **Price:** $145. Reset: $95. No activation fee, per the Pricing Reference, which was about 14 days old.
  - Older Tradeify blog posts list about $97. Treat those as stale.
- **Profit target:** $3,000.
- **Max loss:** $2,000, EOD trailing, enforced in real time on net liquidation value.
  - "Evaluation accounts do not have drawdown locking", so the floor keeps trailing during the evaluation.
- **Daily loss limit:** $1,250. It is a soft breach: it "pauses trading until 6:00 PM ET, does not fail the account."
- **Consistency:** None in the evaluation.
- **Minimum days:** 1.
- **Max size:** 4 minis or 40 micros for accounts bought after 2025-09-12.
  - **Conflict:** a table on the same page shows 5 contracts. The value 5 is the legacy limit for accounts bought before 2025-09-12.

### Funded
- **Max loss:** $2,000, EOD trailing. It locks at a $50,100 floor once the EOD balance reaches $52,100, or immediately on a payout request.
- **Daily loss limit:** Starts at $1,250 and becomes $2,000 once the balance reaches $53,000. The increase takes effect the next session. It is a soft breach.
- **Consistency:** 35%: no single day may be more than 35% of total profit. It applies to payouts.
- **Scaling:** None found for Growth. The size is fixed at 4 minis or 40 micros. Scaling is **UNVERIFIED**.
- **Payout rules:**
  - You need at least 5 trading days with more than $150 profit each. The count resets after each payout.
  - The balance must be at least $53,000 to request, and it must stay there until the payout is approved.
  - Minimum request: $500.
  - Maximum request: $1,500 for payout 1, $2,000 for payout 2, $2,500 for payout 3, and $3,000 for payout 4 and later. An older-purchase tier table shows $1,500 and then $1,750 (**conflict, legacy**).
  - Split: 90/10 from the first payout.

## Tradeify — Select 50K

### Evaluation
- **Price:** $165. Reset: $109. With the 50% consistency add-on: $205, reset $135. No activation fee.
  - A Tradeify blog post said "$107 as of July 15, 2026". Treat it as stale.
- **Profit target:** $3,000 under Tradeify 3.0. Accounts bought before the dashboard launch keep $2,500.
- **Max loss:** $2,000, EOD trailing. It does not lock in the evaluation.
- **Daily loss limit:** None.
- **Consistency:** 40%: no single day may exceed 40% of total profit, or 50% with the add-on. It applies to the evaluation only.
- **Minimum days:** In effect 3 at 40%, or 2 at 50%.
- **Max size:** **UNVERIFIED** for the evaluation. The Select scaling plan is described for funded accounts.

### Funded
At activation you choose either **Select Flex** or **Select Daily**. The choice is permanent.

- **Both policies:**
  - Max loss is $2,000, EOD trailing. It locks at a $50,100 floor when the EOD balance reaches $52,100, or immediately on a payout request.
  - There is no consistency rule in the funded phase. One help page implies a setting tied to the Daily path (**minor conflict**).
  - Each cycle needs positive net profit.
  - Split: 90/10.
- **Scaling (50K):**
  - The cap starts at 2 minis or 20 micros.
  - At an EOD balance of $51,500 or more it becomes 3 minis or 30 micros, starting the next day.
  - At an EOD balance of $52,000 or more it becomes 4 minis or 40 micros.
- **Select Flex:**
  - No daily loss limit.
  - You can request after 5 winning days, with no minimum balance. The per-day profit needed for a "winning day" is **UNVERIFIED**.
  - Cap: 50% of profit, up to $2,500 for accounts bought after 2026-09-01 ($3,000 before). Pages **conflict** on these caps.
  - Minimum request: $250.
- **Select Daily:**
  - Daily loss limit: $1,000, soft.
  - You can request daily once the balance clears a $2,100 buffer (that is, $52,100).
  - Cap: 2× the profit made since the last request, up to $1,250 for accounts bought after 2026-09-01 ($1,000 before).
  - Minimum request: $250.

## Tradeify — Lightning 50K (instant funded; no evaluation)

- **Price:** $492, one time. It cannot be reset; a failed account must be bought again. No activation fee.
  - An older blog post lists $356. Treat it as stale.
- **Max loss:** $2,000, EOD trailing. It locks at a $50,100 floor once the EOD balance reaches $52,100, or on a payout request.
- **Daily loss limit:** $1,250, soft.
- **Max size:** 4 minis or 40 micros for accounts bought after 2025-09-12 (legacy accounts: 5 minis or 50 micros). No scaling plan found.
- **Payout rules:**
  - Profit goals: $3,000 of new profit for payout 1, then $2,000 of new profit for each later payout.
  - There is no minimum number of trading days.
  - Minimum request: $1,000.
  - Caps: $2,000 for payouts 1 to 3, then $2,500 from payout 4.
  - Split: 90/10.
- **Consistency:** Progressive, and it applies to payouts: 20% for payout 1, 25% for payout 2, and 30% for payout 3 and later. Legacy accounts stay at 20%.

## Tradeify policies (all plans)
- **News trading:** "allowed with no restrictions".
- **Microscalping (funded only):** More than 50% of trades must last longer than 10 seconds, and more than 50% of profit must come from those trades.
- **Automation:** Personal bots are allowed. VPS trading is allowed "at your own risk", but logging in through a VPN or VPS is not.
  - You must prove sole ownership of the bot, and you may be asked for a video showing it running on your own PC.
  - Third-party bot services sold across firms are banned.
  - See `prop-firms-and-order-routing.md` (Guidelines for Traders; Common FAQs).
- **Tradeify 3.0:** All three plans now feed the "Tradeify Elite" live program. Subscriptions were replaced by one-time fees.

---

## Simulator parameters

All amounts are in USD. "EOD-trail (RT)" means the floor is updated from the EOD balance but enforced in real time on net liquidation value. "Lock" means the floor freezes at that value. All plans are flat by 4:45 PM ET.

| Plan | Phase | Target | Max loss | Drawdown type | Lock rule | Daily limit | Consistency rule | Min days | Max micros | Payout rule summary | Split | Flat by (ET) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LucidFlex 50K | Eval | 3,000 | 2,000 | EOD-trail (RT enforcement UNVERIFIED) | Floor 50,100 once EOD ≥ 52,100 (applies to eval: likely, not explicit) | Optional, soft; amount UNVERIFIED (~1,200?) | Best day ≤ 40% of total profit (50% add-on) | 3 (2 w/ add-on), implied | 40 | n/a | n/a | 16:45 |
| LucidFlex 50K | Funded | n/a | 2,000 | EOD-trail | Floor 50,100 once EOD ≥ 52,100, or on first payout request | Optional, soft; amount UNVERIFIED | None | 5 days ≥ $150 per cycle | 20 → 40 (scaling by profit; thresholds UNVERIFIED) | Net cycle profit > 0; min 500; max 50% of profit up to 2,000; any day; no buffer; 5 payouts then live (conflict: 6) | 90/10 | 16:45 |
| LucidPro 50K | Eval | 3,000 | 2,000 | EOD-trail | Floor 50,100 at EOD 52,100 (assumed same as funded) | 1,200 fixed, soft (optional per newer page: conflict) | None | none stated | 40 | n/a | n/a | 16:45 |
| LucidPro 50K | Funded | n/a | 2,000 | EOD-trail | Floor 50,100 once EOD ≥ 52,100 | Optional, soft; 1,200 fixed or 60%-of-peak scaling (conflict) | Best day ≤ 40% of cycle profit (resets per payout) | none | 40 (no scaling) | ≥ 500 cycle profit; min 500; max 2,000 then 2,500; balance must stay ≥ 52,100 | 90/10 | 16:45 |
| Tradeify Growth 50K | Eval | 3,000 | 2,000 | EOD-trail (RT) | No lock in eval | 1,250 soft | None | 1 | 40 (legacy 50) | n/a | n/a | 16:45 |
| Tradeify Growth 50K | Funded | n/a | 2,000 | EOD-trail (RT) | Floor 50,100 once EOD ≥ 52,100, or on payout request | 1,250 soft; 2,000 once bal ≥ 53,000 (next session) | Best day ≤ 35% of total profit | 5 days > $150 per cycle | 40 | Balance ≥ 53,000; min 500; max 1,500 / 2,000 / 2,500 / 3,000 (payouts 1, 2, 3, 4+) | 90/10 | 16:45 |
| Tradeify Select 50K | Eval | 3,000 (legacy 2,500) | 2,000 | EOD-trail (RT) | No lock in eval | None | Best day ≤ 40% of total profit (50% add-on) | 3 (2 w/ add-on), implied | UNVERIFIED (assume 40) | n/a | n/a | 16:45 |
| Tradeify Select 50K (Flex) | Funded | n/a | 2,000 | EOD-trail (RT) | Floor 50,100 once EOD ≥ 52,100, or on payout request | None | None | 5 winning days (threshold UNVERIFIED) | 20 → 30 at EOD 51,500 → 40 at 52,000 | Net cycle > 0; min 250; max 50% of profit up to 2,500 (3,000 pre 2026-09-01; conflict) | 90/10 | 16:45 |
| Tradeify Select 50K (Daily) | Funded | n/a | 2,000 | EOD-trail (RT) | Same as Flex | 1,000 soft | None | none; daily once over buffer | 20 → 30 → 40 (as Flex) | Balance > 52,100 buffer; min 250; max 2× profit since last request, up to 1,250 | 90/10 | 16:45 |
| Tradeify Lightning 50K | Funded (instant) | n/a | 2,000 | EOD-trail (RT) | Floor 50,100 once EOD ≥ 52,100, or on payout request | 1,250 soft | Best day ≤ 20% / 25% / 30% of profit (payouts 1, 2, 3+) | none | 40 (legacy 50) | New profit 3,000 for payout 1, then 2,000 each; min 1,000; max 2,000 for payouts 1–3, then 2,500 | 90/10 | 16:45 |

## Sources (all reached via domain-restricted web search on 2026-11-02; no direct fetch)

**Lucid Trading**
- LucidFlex Evaluation Account — https://support.lucidtrading.com/en/articles/12945790-lucidflex-evaluation-account
- LucidFlex Funded Account — https://support.lucidtrading.com/en/articles/12945795-lucidflex-funded-account
- LucidFlex Drawdown — https://support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown
- LucidFlex Consistency Percentage — https://support.lucidtrading.com/en/articles/12945805-lucidflex-consistency-percentage
- LucidFlex Scaling Plan — https://support.lucidtrading.com/en/articles/12945808-lucidflex-scaling-plan
- LucidFlex Payouts — https://support.lucidtrading.com/en/articles/12945796-lucidflex-payouts
- LucidFlex Customization — https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization
- LucidFlex Live (Legacy) — https://support.lucidtrading.com/en/articles/13424914-lucidflex-live-legacy
- LucidFlex category (prices) — https://lucidtrading.com/product-category/lucidflex/
- LucidPro Evaluation Account — https://support.lucidtrading.com/en/articles/12890029-lucidpro-evaluation-account
- LucidPro Funded Account — https://support.lucidtrading.com/en/articles/12890069-lucidpro-funded-account
- LucidPro Drawdown — https://support.lucidtrading.com/en/articles/12890136-lucidpro-drawdown
- LucidPro Daily Loss Limit — https://support.lucidtrading.com/en/articles/12890122-lucidpro-daily-loss-limit
- LucidPro Consistency Percentage — https://support.lucidtrading.com/en/articles/12890109-lucidpro-consistency-percentage
- LucidPro Payouts — https://support.lucidtrading.com/en/articles/12890092-lucidpro-payouts
- LucidPro Customization — https://support.lucidtrading.com/en/articles/16226068-lucidpro-customization
- LucidPro 50K product page — https://lucidtrading.com/product/lucidtest-50k/
- Allowed Trading Times — https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times
- Other Trading Activities — https://support.lucidtrading.com/en/articles/11404728-other-trading-activities
- General FAQ — https://lucidtrading.com/general-faq/

**Tradeify**
- GROWTH Evaluation Accounts — https://help.tradeify.co/en/articles/10495915-growth-evaluation-accounts
- Growth Funded: Account Payout Policy — https://help.tradeify.co/en/articles/11083796-growth-funded-account-payout-policy
- Select Evaluation Accounts — https://help.tradeify.co/en/articles/12853921-select-evaluation-accounts
- Select Flex and Select Daily Payout Policies — https://help.tradeify.co/en/articles/12853966-select-flex-and-select-daily-payout-policies
- SELECT vs Growth — https://help.tradeify.co/en/articles/13252431-select-vs-growth-choosing-your-evaluation-type
- Lightning Funded Accounts — https://help.tradeify.co/en/articles/10495938-lightning-funded-accounts
- Lightning Funded: Account Payout Policy — https://help.tradeify.co/en/articles/10495932-lightning-funded-account-payout-policy
- Rules: Trailing Max Drawdowns — https://help.tradeify.co/en/articles/10495897-rules-trailing-max-drawdowns
- Rules: Daily Loss Limit — https://help.tradeify.co/en/articles/10468321-rules-daily-loss-limit
- Rules: Consistency Rule — https://help.tradeify.co/en/articles/10468320-rules-consistency-rule
- Rules: Permitted Times to Trade — https://help.tradeify.co/en/articles/10495876-rules-permitted-times-to-trade
- Rules: News Trading — https://help.tradeify.co/en/articles/10495874-rules-news-trading
- Tradeify Pricing Reference — https://help.tradeify.co/en/articles/14369021-tradeify-pricing-reference
- Are There Activation Fees? — https://help.tradeify.co/en/articles/10468246-are-there-activation-fees
- Essential Trading Rules Overview (~111 days old) — https://help.tradeify.co/en/articles/12268167-essential-trading-rules-overview
- Tradeify 3.0 announcement — https://tradeify.co/post/tradeify-3-0-here-and-everything-just-changed
