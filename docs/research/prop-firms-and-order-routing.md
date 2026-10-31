# Research: Futures Prop Firms and Order Routing for a Fully Automated Python Bot

*Compiled 2026-10-31. Companion to [`ict-ml-trading-bot.md`](./ict-ml-trading-bot.md); that file covers brokers, frameworks and data in general. This one covers only prop firms and the routes from a cloud-hosted Python engine to a prop account. The product is CME Micro E-mini Nasdaq-100 / S&P 500 (MNQ/MES).*

> **How this was sourced, and what that means for you.** The research sandbox's network policy blocked direct fetches of every firm and vendor domain (help.topstep.com, support.apextraderfunding.com, api.tradovate.com, tradingview.com, rithmic.com, nautilustrader.io and others). First-party pages were therefore read **through search-engine excerpts restricted to each firm's own domain**, not by opening the page. Quotes below are the excerpt text attributed to the cited URL. Where the excerpt showed the page's age, it is given as "page ~N days old at 2026-10-31". Anything not backed by a first-party excerpt is marked **UNVERIFIED**. Prop-firm rules change monthly. **Get written confirmation from the firm's support (email or ticket) before you run a bot on a funded account**, and keep that confirmation.

## Table of contents

1. [Bottom line](#1-bottom-line)
2. [Prop-firm automation policies](#2-prop-firm-automation-policies)
3. [Order-routing paths](#3-order-routing-paths)
4. [Cheap simulation for the paper phase](#4-cheap-simulation-for-the-paper-phase)
5. [Cloud hosting](#5-cloud-hosting)
6. [Recommendation](#6-recommendation)
7. [Open questions to send to firms](#7-open-questions-to-send-to-firms)
- [Sources](#sources)

---

## 1. Bottom line

- **No firm clearly allows all of these at once:** a fully automated bot, on a funded account, run from a cloud server, through an API. Each firm restricts at least one of them.
- **Ruled out:** Apex (bans automation on all accounts), Alpha Futures (bans hands-off automation), Topstep (API is sim-only on Live Funded accounts, and VPS/remote servers are banned for order flow), TradeDay (bans third-party bots; doesn't expose Tradovate API access).
- **Shortlist** (bots allowed in funded accounts per first-party text, and no first-party VPS ban found): **Lucid Trading, Tradeify, MyFundedFutures, Bulenox**, plus FundedNext Futures with caveats (IP-consistency rule).
- **The Tradovate API itself is closed to prop accounts.** Tradovate says prop firm and evaluation accounts are not eligible. So a Python engine can't call the Tradovate REST/WebSocket API on a prop account directly. The usable routes are:
  1. NinjaTrader 8 on a Windows VPS, bridged to Python.
  2. Rithmic R|Protocol on Linux (needs Rithmic conformance and firm permission).
  3. A third-party webhook bridge (TradersPost, PickMyTrade, CrossTrade) that already has partner access.

## 2. Prop-firm automation policies

### 2.1 Per-firm findings

#### Topstep — automation allowed, but **not usable for a cloud bot**
- **Automation:** "Can I use automated trading strategies? Yes, with conditions. Topstep won't help set up or troubleshoot automated strategies, and no exceptions are made for errant trades or malfunctions." This is on both the [Trading Combine parameters](https://help.topstep.com/en/articles/8284197-trading-combine-parameters) and [XFA parameters](https://help.topstep.com/en/articles/8284215-express-funded-account-parameters) pages.
- **API:** Custom bots are allowed via the TopstepX/ProjectX API. However, "Live funded accounts are not allowed to trade through the ProjectX API. The API Gateway is built for the simulated environment and isn't available on Live." ([TopstepX API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access), page ~43 days old). The [LFA parameters](https://help.topstep.com/en/articles/10657969-live-funded-account-parameters) page (~7 days old) says automated strategies are "not possible at this time in the Live Funded Account".
- **VPS / cloud:** "All trading activity must originate from your personal device. The use of VPS, VPNs, and remote servers is prohibited by Topstep's Terms of Use." A private server may be used only for work that doesn't touch order flow, such as data storage, backtesting, logging or read-only dashboards ([API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)). The [Terms of Use](https://www.topstep.com/terms-of-use) copy says use of "any VPN or VPS on Accounts is strictly prohibited". [Prohibited Conduct](https://help.topstep.com/en/articles/10296582-prohibited-conduct) bans VPNs, proxies and identity masking.
- **Platforms:** TopstepX (ProjectX). Quantower connects through TopstepX credentials, Combine and XFA only ([Quantower instructions](https://help.topstep.com/en/articles/8284179-quantower-connection-instructions)). Whether NinjaTrader or Tradovate are still offered: **UNVERIFIED** (not found in first-party excerpts).
- **API cost:** $29/mo, or $14.50/mo with code `topstep` ([API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)).
- **Rules (50K):**
  - Standard plan $49/mo plus a $149 activation fee, or a No-Activation-Fee path at $95/mo.
  - Profit target $3,000.
  - Maximum Loss Limit $2,000, end-of-day trailing. It locks at the start balance, and in the XFA it locks at $0 once the balance reaches $2,000.
  - Optional $1,000 daily loss limit.
  - 90/10 split.
  - A Static 50K Combine sells for $149 one-time ([MLL](https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit), [Payout policy](https://help.topstep.com/en/articles/8284233-topstep-payout-policy), [Pricing](https://help.topstep.com/en/articles/14289835-topstep-pricing-and-payment-questions), [DLL](https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account)).
- **Copy trading:** The Trade Copier works on Combine and XFA, not LFA ([API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)).

#### Apex Trader Funding — **automation prohibited**
- From [Prohibited Activities](https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities): "The use of automation is strictly prohibited on all account types. This includes any form of AI (Artificial Intelligence), Autobots, algorithms, fully automated trading systems, and high-frequency trading (HFTs)." The page adds: "These types of systems that trade without active human intervention are not allowed. Using these types of automation will result in the immediate closure of your PA or Live account and the forfeiture of all funds and balances."
- From [PA and Compliance](https://support.apextraderfunding.com/hc/en-us/articles/31519788944411-Performance-Account-PA-and-Compliance): PA and Live accounts must not be "managed or influenced by any other party, person, system, automated trading bot, copy trading service, or trade mirroring software."
- **Platforms:** Rithmic, Tradovate and WealthCharts. You can't convert between them ([Choosing the Right Platform](https://apextraderfunding.com/help-center/getting-started/choosing-the-right-platform/)).
- **Fees:** The 50K PA activation fee varies by page, from about $125 to $160, and the homepage now says "No Activation Fee". The split is "100% … No split in Sim Funded" on the homepage, while the legacy policy is 100% of the first $25k and then 90%. Treat both as **conflicting** ([How to Activate a PA](https://support.apextraderfunding.com/hc/en-us/articles/31519770974235-How-to-Activate-a-PA), [Legacy products](https://apextraderfunding.com/legacy-products/), [homepage](https://apextraderfunding.com/)).

#### MyFundedFutures (MFFU) — **automation allowed (first-party)**
- From [Fair Play and Prohibited Trading Practices](https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices) (page ~67 days old): "High-frequency Trading is not allowed on our plans. Traders may make use of automated trading strategies tailored to their own specific settings so long as these automated tools do not aim to exploit the favorable fills offered in the Simulated Environment." The page adds that live accounts using automation "must abide by CME guidelines". It bans tier-1 economic-release trading, tight-bracket fill exploitation, and shared devices.
- **Conflict:** A vendor blog says MFFU "prohibits fully autonomous bots" ([TradersPost](https://blog.traderspost.io/article/automate-my-funded-futures-with-traderspost)). The first-party text above does not say that. Confirm with support.
- **Other rules:**
  - Copy trading is allowed on all account types ([Copy Trading](https://help.myfundedfutures.com/en/articles/10771500-copy-trading-at-myfundedfutures)).
  - Cross-instrument position limits apply: mixing minis and micros to exceed the limit is not permitted ([Cross Instrument](https://help.myfundedfutures.com/en/articles/10244682-cross-instrument-policy)).
  - Positions auto-close at session end, and there is a 7-day inactivity rule ([Traders Evaluation Simplified](https://help.myfundedfutures.com/en/articles/11802636-traders-evaluation-simplified)).
- **Platforms:** TradingView, NinjaTrader, Tradovate, Quantower, DeepCharts and others ([help center](https://help.myfundedfutures.com/en/articles/11553762-industry-leading-futures-prop-firm-start-trading-with-myfundedfutures)).
- **Plans:** Rapid (intraday DD), Rapid EOD, Builder and Pro. The split is 90% on Rapid and 80% on Builder/Pro per the blog, but sources conflict. Tradovate challenge pricing was $145 for 25K and $209 for 50K with a $0 activation fee, at promo prices ([How it works](https://myfundedfutures.com/how-it-works), [challenge page](https://myfundedfutures.com/challenge?id=48&platform=Tradovate)). Treat the split and prices as **UNVERIFIED**.
- **VPS:** No first-party statement found. Possible conflict with the "shared devices strictly forbidden" rule ([Can someone else trade my account?](https://help.myfundedfutures.com/en/articles/8230018-can-someone-else-trade-my-account)).

#### Tradeify — **personal bots allowed; VPS trading allowed "at your own risk"**
- From [Guidelines for Traders](https://help.tradeify.co/en/articles/10468318-guidelines-for-traders) (page ~14 days old):
  - The trader must prove "the Trader is the sole owner of the bot or strategy and that no one else has access to or is using it."
  - Tradeify scans for similar orders on other accounts.
  - "will also require a live video of you enabling the code on your own PC."
- From the [Funded Trader Agreement](https://tradeify.co/funded-trader-agreement) (dated October 2026):
  - Personal bots are permitted unless they are HFT.
  - Using the same bot across multiple prop firms violates policy. Personal brokerage accounts are fine.
  - At least one trade per calendar week is required.
- From [Common FAQs](https://help.tradeify.co/en/articles/12268494-common-faqs): you cannot *log in* through a VPN or VPS, but "after logging in normally, you may use VPS for trading at your own risk". The [Terms of Use](https://tradeify.co/terms-of-use) bar VPS use that hides or alters Tradeify's ability to verify device, network or location.
- **Microscalping rule (funded only):** More than 50% of trades must last longer than 10 seconds, and more than 50% of profit must come from those trades ([Guidelines](https://help.tradeify.co/en/articles/10468318-guidelines-for-traders)).
- **Platforms:** Tradovate (NinjaTrader, TradingView), Rithmic (Tradesea, Quantower, Sierra Chart, R|Trader) or WealthCharts. All brokers are the same price, and switching brokers requires a new account ([Supported Platforms](https://help.tradeify.co/en/articles/10468221-supported-platforms)).
- **Pricing and split:** The checkout showed a Growth 25k at $99. Lightning is a 90% split with EOD trailing drawdown according to a third party. Treat these as **UNVERIFIED** ([Pricing reference](https://help.tradeify.co/en/articles/14369021-tradeify-pricing-reference)).

#### Take Profit Trader (TPT) — **automation policy unclear**
- The [Terms of Service](https://takeprofittrader.com/terms) (page ~795 days old) say: "Traders are fully responsible for the use of any trade copiers or third-party automation tools connected to their TakeProfit Trader accounts." They also bar accessing TPT "Resources through any automated … means", which concerns site access. No explicit EA or bot rule was found: **UNVERIFIED**.
- **PRO rules:** intraday trailing drawdown, max contracts per size, and "no news trading on specific major events" ([homepage](https://takeprofittrader.com/)).
- **Split:** PRO 80%, PRO+ 90%. The 50K test is about $170/mo and activation about $130, often waived by promo ([TPT vs Topstep](https://takeprofittrader.com/blog/take-profit-trader-vs-topstep)). Pricing is **UNVERIFIED**.
- **Platforms:** Tradovate, NinjaTrader and Rithmic, with Tradovate as the PRO+ broker (same source).

#### Lucid Trading — **automation and copiers allowed**
- From the [FAQ](https://lucidtrading.com/general-faq/): "Are EAs/bots allowed?" The answer is yes, for automated strategies and in-platform or third-party trade copiers, with the trader responsible for software failures.
- [Other Activities](https://support.lucidtrading.com/en/articles/11404728-other-activities) says automated trading systems and trade copiers are permitted, must follow Lucid's rules, and leave the trader fully liable for malfunctions.
- **Bans:**
  - HFT ([HFT policy](https://support.lucidtrading.com/en/articles/11404736-prohibited-high-frequency-trading); escalating penalties).
  - Microscalping: flagged if more than 50% of profit comes from trades held 5 seconds or less ([Microscalping](https://support.lucidtrading.com/en/articles/11404742-prohibited-microscalping)).
- **Conflict:** The [LucidDirect Account Agreement](https://lucidtrading.com/wp-content/uploads/2025/05/LucidDirect-Account-Agreement-5-19.pdf) (last modified 2025-05-19) requires "written approval from us prior to using any Automated Trading Software". Get written approval anyway.
- **Platforms:**
  - CQG feed: NinjaTrader, Tradovate, TradingView.
  - Rithmic feed: Quantower, Tradesea, Sierra Chart, R|Trader Pro, MotiveWave, ATAS, Bookmap, Jigsaw, MultiCharts.
  - All platforms work across LucidFlex and LucidPro ([Supported Platforms](https://support.lucidtrading.com/en/articles/11404614-lucid-trading-supported-platforms)).
- **Split and rules:**
  - 90/10 on LucidPro, LucidFlex and LucidDirect ([FAQ](https://lucidtrading.com/general-faq/)).
  - LucidFlex 25K, per a secondary subdomain listing: $110, target $1,250, **no daily loss limit**, max loss $1,000 EOD, 2 minis or 20 micros, **no consistency rule** ([sb1 listing](https://sb1.lucidtrading.com/product/lucidflex-25k-rithmic/)). Treat the price as **UNVERIFIED**.
  - Positions are auto-closed at 4:45 PM ET ([Allowed Trading Times](https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times)).
  - LucidDaily treats red-folder news as a hard breach ([LucidDaily](https://support.lucidtrading.com/en/articles/15997244-luciddaily-funded-account)).
- **VPS:** No first-party statement found.

#### Alpha Futures — **full automation prohibited**
- From [Prohibited Trading Practices](https://help.alpha-futures.com/en/articles/9508585-prohibited-trading-practices): HFT systems are restricted, especially those placing more than 100 trades a day. Semi-automated tools are allowed only if the trader places, monitors and manages each trade. Hands-off automation is banned.
- Direct accounts: AI, bots and full automation are prohibited ([Direct page](https://alpha-futures.com/posts/straight-to-funded-futures-prop-firm-2026)).
- Automated copy trading is prohibited ([Copy Trading](https://help.alpha-futures.com/en/articles/10573989-copy-trading)).
- **Platform change:** Alpha says it ended its NinjaTrader relationship on **2026-07-12**, which also cut Tradovate and TradingView-via-Tradovate. The current platforms are AlphaTrader, TradingView via Plus500, WealthCharts, Quantower and DeepChart ([Platforms](https://alpha-futures.com/platforms)).
- **Rules:** EOD trailing MLL on all plans and a 90% split (same source and [homepage](https://alpha-futures.com/)).

#### Bulenox — **personal bots allowed; $100/mo third-party API fee**
- [FAQ](https://bulenox.com/faq): bots, algorithms and trade copiers are allowed if they are user-built for the account owner's own use. Commercial, shared, rented or publicly distributed tools are excluded.
- **Third-party API fee:** Connecting through a "third-party API or composite software" costs an extra **$100/month**.
- **Approval:** The sign-up terms say third-party algorithms need management approval, and that paying the connection fee "does not constitute approval of any specific algorithm".
- **Bans:** "scalping" algorithms, DTC Protocol Bridge API, and "hundreds or thousand of rapid trades" ([Account SignUp terms](https://bulenox.com/member/signup)). The older [Terms PDF](https://bulenox.com/legal/Terms_of_Use.pdf) is dated July 2021.
- **Platforms:** Rithmic data, NinjaTrader partner, a free NT8 licence on the Master account, and about 20 platforms ([homepage](https://bulenox.com/), [FAQ](https://bulenox.com/faq)).
- **50K Qualification:** $175 one-time (30 days), 7 contracts, $3,000 target, $2,500 trailing DD, no DLL ([Accounts & Pricing](https://bulenox.com/accounts-pricing)).
- **Drawdown options** are fixed for the account's life: Option 1 is trailing including open P/L; Option 2 is EOD with a DLL and scaling.
- **Split:** 90/10. Master payouts are processed on Wednesdays ([FAQ](https://bulenox.com/faq)).
- **VPS:** No first-party statement found.

#### FundedNext Futures — **bots allowed via Tradovate integrations; IP rule**
- [Futures General Rules](https://fundednext.com/general-rules/futures/what-is-allowed): EAs and bots are allowed on Challenge and funded accounts, with the instruction "Use automated strategies through any platform integration that connects to Tradovate." There is no support for setup. Exploiting latency, pricing errors or platform vulnerabilities is abuse, and tick scalping and bot HFT are banned ([HFT](https://help.fundednext.com/en/articles/11982271-does-fundednext-allow-hft-high-frequency-trading)).
- [Futures Challenge Terms](https://fundednext.com/futures-challenge-terms) §2.2.6: violating automated systems will be disabled, and FundedNext may request the system for review. Using **different IP addresses to access the dashboard and execute trades without prior approval** is barred. That matters for a cloud bot.
- The general [VPN/VPS article](https://help.fundednext.com/en/articles/8223809-can-i-use-a-vpn-or-vps) says VPS is not permitted on accounts of $50k and above, but it appears to be CFD-oriented. Whether it applies to Futures is **UNVERIFIED**.
- The [Terms of Service](https://fundednext.com/terms-of-service) prohibit unauthorised bots, and also VMs or VPS clusters used to suggest coordination.
- **Platforms:** Tradovate, NinjaTrader and TradingView ([Futures page](https://fundednext.com/futures)).
- **Rapid challenge:** EOD trailing DD. Rapid Pro has a 40% consistency rule in funded; Rapid Daily has a DLL. Entry from $79.99 one-time, split about 90% ([Rapid explained](https://fundednext.com/blog/futures-rapid-pro-rapid-daily-explained)). Pricing is **UNVERIFIED**.

#### Earn2Trade — **unclear; trade copiers banned**
- [Prohibited Conduct](https://help.earn2trade.com/en/articles/9286647-prohibited-conduct-in-earn2trade-evaluations-and-in-the-livesim-live-trading-environment) bans "utilizing software, artificial intelligence, or ultra-fast data entry techniques that could potentially manipulate the trading environment or provide an unfair advantage". There is no explicit bot permission or ban.
- Trade copiers are "strictly forbidden on funded and evaluation accounts" ([Copy trades](https://help.earn2trade.com/en/articles/12034590-am-i-allowed-to-copy-trades-across-multiple-accounts)).
- **Gauntlet Mini 50K:** $2,000 EOD DD in eval and LiveSim, trailing in Live, $1,100 DLL, 6 contracts ([Gauntlet Mini](https://www.earn2trade.com/gauntlet-mini)).
- **Split:** for GM 50, 50% below $2,250 per withdrawal and 80% above ([Withdrawal policy](https://help.earn2trade.com/en/articles/5452472-what-is-the-withdrawal-policy)).
- **Flat window:** you must be flat 3:50–5:00 PM CT ([evaluation rules](https://help.earn2trade.com/en/articles/5941958-what-are-the-evaluation-rules)).
- Platforms and price: **UNVERIFIED**.

#### TradeDay — **third-party bots banned; self-built unclear**
- [Terms and Conditions](https://www.tradeday.com/terms-and-conditions) (page ~81 days old) prohibit "Using trading bots or Automated Trading Systems (ATS) purchased from a third party. Or multiple users using the same trading bots and ATS'." They also state: "We do not allow strategies that produce more than 200 trades in a day." HFT scalping and gaming the sim matching engine are banned. Funded traders may not trade within 2% of a price limit.
- A linked bot/ATS policy page was not retrieved. **Whether a self-built bot is allowed is UNVERIFIED.**
- CrossTrade says TradeDay "doesn't expose Tradovate API access for automated systems" ([CrossTrade/TradeDay](https://crosstrade.io/prop-firms/tradeday)). This is a vendor claim.
- **Platforms:** Tradovate, and Rithmic per a [blog post](https://www.tradeday.com/blog-posts/rithmic-is-now-available), although the About page says "Coming Soon", so the status conflicts.

#### Other notable
- **The Futures Desk:** reported by TradersPost as the only other ProjectX venue besides TopstepX as of September 2026 ([TradersPost](https://blog.traderspost.io/article/what-is-projectx-prop-firms)). **UNVERIFIED**; not checked first-party.

### 2.2 Comparison table

Legend: ✅ allowed per first-party text · ⚠️ conditional or conflicting · ❌ prohibited · ? not found.

| Firm | Bots in eval | Bots in funded | Cloud/VPS | Python route | Platforms / feeds | Drawdown | Price (50K unless noted) | Split |
|---|---|---|---|---|---|---|---|---|
| Topstep | ✅ | ⚠️ XFA yes; **LFA no API** | ❌ VPS/remote servers banned for order flow | ProjectX API ($14.50–29/mo), sim accounts only | TopstepX, Quantower | EOD trailing MLL; optional DLL | $49/mo + $149 activation, or $95/mo | 90/10 |
| Apex | ❌ | ❌ | n/a | none permitted | Rithmic, Tradovate, WealthCharts | intraday or EOD variants | PA activation ~$125–160 (conflicting) | 100% then 90% (conflicting) |
| MyFundedFutures | ✅ | ✅ (vendor blog disagrees) | ? (shared devices banned) | bridge via Tradovate, or NT8 | Tradovate, NinjaTrader, TradingView, Quantower | Rapid intraday; EOD plans | ~$209 one-time, $0 activation (promo; UNVERIFIED) | 80–90% |
| Tradeify | ✅ | ✅ own bot; video proof | ⚠️ "use VPS for trading at your own risk"; no VPS login | bridge via Tradovate, NT8, or Rithmic API (permission ?) | Tradovate (NT, TV), Rithmic, WealthCharts | EOD (UNVERIFIED) | Growth 25k $99 (UNVERIFIED) | 90% (UNVERIFIED) |
| Take Profit Trader | ? | ? | ? | bridge or NT8 | Tradovate, NinjaTrader, Rithmic | intraday trailing (PRO) | ~$170/mo + $130 activation (UNVERIFIED) | 80% PRO / 90% PRO+ |
| Lucid Trading | ✅ | ✅ (LucidDirect agreement wants written approval) | ? | NT8 (CQG), bridge, or Rithmic API (permission ?) | CQG: NT, Tradovate, TV; Rithmic: many | EOD; Flex has no DLL or consistency rule | Flex 25K $110 (UNVERIFIED) | 90/10 |
| Alpha Futures | ❌ full auto | ❌ | n/a | none | AlphaTrader, Quantower, WealthCharts, TV via Plus500 (NT/Tradovate dropped 2026-07-12) | EOD trailing | $139–169/mo (conflicting) | 90% |
| Bulenox | ✅ own use | ✅ own use (+ approval) | ? | Rithmic API (+$100/mo) or NT8 | Rithmic; NT8 licence free on Master | trailing or EOD+DLL | $175 one-time | 90/10 |
| FundedNext Futures | ✅ | ✅ "via platform integration that connects to Tradovate" | ⚠️ IP-consistency rule; VPS ≥$50k rule possibly CFD-only | bridge via Tradovate | Tradovate, NinjaTrader, TradingView | EOD trailing | from $79.99 one-time (UNVERIFIED) | ~90% |
| Earn2Trade | ? | ? (copiers banned) | ? | ? | UNVERIFIED | EOD eval, trailing Live | UNVERIFIED | 50%/80% by withdrawal size |
| TradeDay | ⚠️ self-built? | ⚠️ third-party bots ❌ | ? | NT8 or Rithmic (Tradovate API not exposed, per vendor) | Tradovate, Rithmic (conflicting) | per plan | $59–131 (old pages) | UNVERIFIED |

### 2.3 Shortlist: a fully automated bot plausibly allowed in funded accounts

Ranked by how explicit the first-party permission is and how well the firm fits a cloud deployment:

1. **Lucid Trading.** The FAQ and support center both say yes to bots, and LucidFlex has EOD drawdown, no DLL, no consistency rule and a 90% split. Gaps: no VPS statement, and the 2025 LucidDirect agreement requires written approval.
2. **Tradeify.** It is the only firm that explicitly says VPS trading is allowed (after a normal login). Gaps: you must prove sole ownership and record a live video "enabling the code on your own PC", and the 10-second microscalping rule applies.
3. **Bulenox.** User-built bots are allowed, and there is an explicit, priced third-party API path ($100/mo) on Rithmic, the cleanest headless Linux route. Gaps: management approval required, VPS not addressed, and the terms are partly 2021-dated.
4. **MyFundedFutures.** First-party text allows automation. Gaps: a vendor blog contradicts it, and the "shared devices" rule may be read against a VPS.
5. **FundedNext Futures (conditional).** Bots are allowed through Tradovate integrations. Gaps: the IP-consistency clause means you should log into the dashboard from the same server IP or get prior approval, and the VPS rule may apply.

## 3. Order-routing paths

### 3.1 Tradovate API (REST + WebSocket)
- **What it is:** The NinjaTrader-branded developer docs now host it, describing REST for auth, orders, positions and risk, and WebSocket market data on `live.tradovateapi.com`, `demo.tradovateapi.com` and `md.tradovateapi.com`. Tokens last about 90 minutes, so call `renewAccessToken`. A `cid`/`sec` pair is issued by NinjaTrader, plus a device ID. An OAuth flow exists for third-party apps ([Getting Started](https://docs.ninjatrader.com/api/getting-started), [Authentication](https://docs.ninjatrader.com/api/authentication), [WebSockets](https://docs.ninjatrader.com/api/websockets), [OAuth](https://docs.ninjatrader.com/api/oauth)).
- **Access and cost:** "To generate an API key, you must first have a live, funded Tradovate account with a minimum balance of $1,000, plus an active subscription to the API Access Add-on" at **$25/month**. Real-time data is **not included**; streaming CME data via the API requires a CME Information License Agreement as a sub-vendor ([Tradovate API Access](https://support.tradovate.com/s/article/Tradovate-API-Access?language=en_US), page ~711 days old per index; the API Access tab is shown only to live accounts with ≥$1,000 per [Settings Overview](https://support.tradovate.com/s/article/Tradovate-Settings-Overview?language=en_US), page ~74 days old).
- **Prop accounts:** The same article says "prop firm and evaluation accounts are not eligible for API access." Prop credentials are separate from personal logins, and prop accounts are accessed in Simulation mode ([Using Your Prop or Evaluation Account](https://support.tradovate.com/s/article/Prop-Firm-and-Evaluation-Account-Inquiries-Tradovate?language=en_US)).
- **Demo:** `demo.tradovateapi.com` exists, but you still need a qualifying live account to get keys.
- **NinjaTrader MCP (beta):** an AI-agent server with `place_order`, available "only for live and demo NinjaTrader and Tradovate Brokerage accounts. Prop firm accounts are not supported at this time" ([support.tradovate.com](https://support.tradovate.com/s/article/NinjaTrader-MCP?language=en_US), [docs](https://docs.ninjatrader.com/mcp)).
- **Headless Linux:** yes; it's a pure network API. **Latency:** cloud-to-cloud, fine for minute bars.
- **Python:** no official SDK. The official samples are JavaScript, with a TypeScript SDK "coming soon" ([Samples](https://docs.ninjatrader.com/api/samples)). The PyPI `tradovate` package is v0.0.1 from 2022, effectively abandoned ([PyPI](https://pypi.org/project/tradovate/)). **No NautilusTrader adapter** (verified against the adapter list in the `nautilus_trader` 1.231.0 wheel: architect_ax, betfair, binance, bitmex, bybit, databento, deribit, dydx, hyperliquid, interactive_brokers, kraken, okx, polymarket, sandbox, tardis).
- **Verdict:** good for a *personal* Tradovate account. **Not usable directly on a prop account.**

### 3.2 NinjaTrader 8 (desktop)
- NinjaScript is C# running inside the Windows desktop app. External programs can drive it through the **Automated Trading Interface (ATI)**: Order Instruction Files dropped into an `incoming` folder, or a DLL interface on a configurable port ([File Interface](https://static.ninjatrader.com/support/helpGuides/nt8/file_interface.htm), [ATI options](https://static.ninjatrader.com/support/helpGuides/nt8/options_ati.htm)).
- **Windows-only:** the current official minimum-requirements page was not retrieved, so the exact Windows versions are **UNVERIFIED** ([requirements](https://ninjatrader.com/support/helpGuides/nt8/minimum_system_requirements.htm)). It cannot run headless on Linux.
- **Prop compatibility:** Most Tradovate- and Rithmic-backed prop accounts connect to NT8 (Lucid, MFFU, Tradeify via Tradovate credentials, Bulenox, TPT, FundedNext). This is the most broadly compatible route to a prop account, and it carries the prop feed's real-time data.
- **Python bridge options:**
  1. Write a NinjaScript add-on or strategy that opens a localhost TCP or WebSocket server and relays bars and orders to and from the Python engine. This is free and fully under your control.
  2. Use ATI OIF files from Python.
  3. Use CrossTrade's REST API on its Pro plan, $49/mo, which also supports Tradovate routing. Standard is $29/mo (webhooks only), Elite $99/mo ([CrossTrade pricing](https://crosstrade.io/pricing), [CrossTrade API](https://crosstrade.io/crosstrade-api)). These are vendor figures.
- **Corporate:** NinjaTrader acquired Tradovate in January 2022, about $115M ([NinjaTrader release](https://ninjatrader.com/NewsReleases/NinjaTrader-Acquires-Tradovate), [Finance Magnates](https://www.financemagnates.com/forex/ninjatrader-buys-tradovate-in-115-million-deal/)). Kraken acquired NinjaTrader in 2025 (see the companion doc).
- **Python / Nautilus:** no NautilusTrader adapter.

### 3.3 TradingView (alerts → webhooks)
- **Webhook constraints:**
  - Webhooks require 2FA.
  - Only ports 80 and 443 are accepted.
  - The receiver must respond within **3 seconds**.
  - 5xx responses (except 504) are retried after 5 s, up to 3 times ([Configure webhooks](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/), [Ports](https://www.tradingview.com/support/solutions/43000529314-i-cannot-send-webhook-to-a-url-with-a-port-number/), [Errors](https://www.tradingview.com/support/solutions/43000776894-what-do-errors-mean-when-sending-webhooks/), [Resubmission](https://www.tradingview.com/support/solutions/43000735201-webhook-resubmission/)).
  - Which plan tier includes webhooks: **UNVERIFIED** ([Pricing](https://www.tradingview.com/pricing/?feature=alertsWebhook)).
- **Broker integration:** TradingView's Trade panel supports Tradovate, and prop users log in with prop credentials. "Prop and evaluation users do not need to subscribe to the TradingView add-on"; availability is "managed entirely by your prop firm". A Tradovate market-data subscription is needed for charts ([Tradovate TradingView guide](https://support.tradovate.com/s/article/Connecting-Your-Tradovate-Account-to-TradingView?language=en_US)). This is manual trading, not an API.
- **Fit for this project:** Pine Script can't host the Python ML filter, so TradingView would be just a signal source. **Skip TradingView** and have the Python engine POST directly to a bridge (§3.4). Pine Script resource limits were not researched, because TradingView isn't on the recommended path.

### 3.4 Webhook bridges (TradersPost, PickMyTrade, CrossTrade)
- These hold partner or OAuth access to Tradovate (and ProjectX), which lets a Python engine on Linux route orders to a **Tradovate-backed prop account** without the Tradovate API add-on.
- **TradersPost:**
  - Starter is $41.65/mo billed yearly, with live auto-submit on one broker. Extra accounts are $10/mo live and $5/mo paper.
  - The free tier auto-submits to paper only ([Pricing](https://traderspost.io/pricing)).
  - It advertises prop automation via Tradovate and ProjectX ([homepage](https://traderspost.io/)).
  - Webhook rate limit is 60/min and 500/hr ([compare](https://traderspost.io/compare)).
- **PickMyTrade:** about $50/mo, per competitor-written pages only: **UNVERIFIED** ([CrossTrade comparison](https://crosstrade.io/pricing), [PickMyTrade blog](https://blog.pickmytrade.trade/crosstrade-alternative/)).
- **CrossTrade:** see §3.2.
- **Prop-firm stance:**
  - Apex and Alpha ban bot or copy-service management.
  - TradeDay bans *third-party purchased* bots. A bridge only transports your own signals, but TradeDay's wording is broad.
  - Tradeify bans third-party bot *services* marketed across firms.
  - FundedNext explicitly permits "any platform integration that connects to Tradovate".
  - Lucid permits third-party copiers.
  - **Always disclose the bridge to the firm.**
- **Latency:** adds an extra HTTP hop and the vendor's queue, on the order of hundreds of ms (**UNVERIFIED**). That's acceptable for minute-bar ICT setups.
- **Data gap:** a bridge only sends orders. The Python engine still needs its own real-time CME data, from Databento live or another licensed feed, at extra cost (§4).

### 3.5 ProjectX / TopstepX Gateway API
- **Cost:** $29/mo. "Access covers all environments utilizing ProjectX … you only need one subscription" ([ProjectX API](https://www.projectx.com/api), [refund policy](https://dashboard.projectx.com/refund-policy)).
- **Limits:**
  - Session tokens are valid for 24 h.
  - Rate limits are 50 requests / 30 s for `History/retrieveBars` and 200 / 60 s for everything else ([Rate limits](https://gateway.docs.projectx.com/docs/getting-started/rate-limits/)).
  - REST plus realtime hubs ([Realtime](https://gateway.docs.projectx.com/docs/category/realtime-updates/)).
- **Which firms:** ProjectX announced it would "wind down our ProjectX third-party service offering for most of our partners", supporting partners through **2026-02-28**, and pointed traders to TopstepX ([projectx.com](https://www.projectx.com/)). In practice that leaves Topstep, plus possibly The Futures Desk (**UNVERIFIED**). **Correction:** older lists naming Alpha Futures, Blusky, Blue Guardian and others as ProjectX firms predate the wind-down and are stale.
- **Funded accounts:** Topstep says the API is not available on Live Funded accounts, and VPS/remote servers are banned (§2.1).
- **Python:** [`project-x-py`](https://pypi.org/project/project-x-py/) v4.4.2 (2026-10-29), MIT, third-party. No NautilusTrader adapter.
- **Verdict:** great for *paper testing* if you already pay for a Topstep Combine. It's a dead end for a cloud bot on a funded account.

### 3.6 Rithmic (R|API+, R|Protocol API)
- **R|Protocol** is Protocol Buffers over WebSockets, with "Conformance testing included". You can build against the test system without conformance, but you must pass conformance before connecting to production systems (Rithmic 01, Rithmic Paper Trading) or any FCM ID ([API suite](https://www.rithmic.com/products/api-suite), [Products](https://www.rithmic.com/products), [Exchange Simulator](https://www.rithmic.com/products/exchange-simulator)).
- **Cost:** No current conformance fee or retail licence terms were found (**UNVERIFIED**). An old FAQ lists Rithmic Paper Trading at $49.99/month plus data ([FAQ](https://www.rithmic.com/support/faq), dated).
- **Prop access:** Bulenox charges $100/mo for a third-party API or composite connection ([FAQ](https://bulenox.com/faq)). Lucid, Tradeify and Apex Rithmic accounts exist, but whether a self-built R|Protocol app is permitted: **UNVERIFIED**. Apex bans automation in any case.
- **Headless Linux:** yes. It gives both real-time data and orders on the prop account's own feed, so no separate data subscription is needed (data-licensing terms **UNVERIFIED**).
- **Python:**
  - [`async_rithmic`](https://pypi.org/project/async-rithmic/) v1.6.6 (2026-08-21), MIT. It requires a `system_name`, `app_name` and `app_version`, and production gateways are available only after conformance ([connection docs](https://async-rithmic.readthedocs.io/en/stable/connection.html)).
  - NautilusTrader: **no official adapter**. There's an open [RFC #3768](https://github.com/nautechsystems/nautilus_trader/issues/3768) and an unofficial [`rithmic-nt-connect`](https://github.com/ozeron/rithmic-nt-connect) targeting 1.231.x, where order submission is "gated".
- **Verdict:** technically the best headless route to a prop account. It is gated by Rithmic conformance (you may need to register an app name) and by firm approval.

### 3.7 Routing summary

| Path | Works on prop funded? | Headless Linux | Python client | Nautilus adapter | Recurring cost | Data included |
|---|---|---|---|---|---|---|
| Tradovate API (direct) | ❌ not eligible | ✅ | community, stale | ❌ | $25/mo add-on + live acct ≥$1,000 + CME ILA for data | ❌ |
| NinjaTrader 8 + NinjaScript/ATI bridge | ✅ (most Tradovate/Rithmic firms) | ❌ Windows | self-built socket bridge, or CrossTrade API | ❌ | Windows VPS ~$30–70/mo; CrossTrade $49 optional | ✅ prop feed |
| Webhook bridge (TradersPost etc.) → Tradovate | ✅ where the firm allows | ✅ | plain HTTPS POST | n/a | ~$42–50/mo | ❌ (need own feed) |
| ProjectX Gateway | sim/XFA only (Topstep) | ✅ | `project-x-py` | ❌ | $14.50–29/mo | ✅ L1 |
| Rithmic R\|Protocol | ✅ if firm approves (Bulenox +$100/mo) | ✅ | `async_rithmic` | ❌ (community only) | $100/mo at Bulenox; conformance fee ? | ✅ prop feed |

## 4. Cheap simulation for the paper phase

| Option | Cost | Real-time CME data | Python access |
|---|---|---|---|
| **NinjaTrader free sim** | Platform sim free, no time limit | 14-day free live-data trial, then delayed, or **Sim+ $35/mo** (US, no live NT brokerage account) for L1 CME bundle; funded NT brokerage accounts get L1 free ([Simulator](https://ninjatrader.com/trading-platform/trading-simulator/), [Pricing](https://ninjatrader.com/pricing/)) | Via NinjaScript bridge on Windows |
| **Tradovate demo** | 2-week free trial with real-time data; then **Extended Simulation Membership $12.95/mo** plus data ([Trial](https://www.tradovate.com/trial/), [Market data](https://support.tradovate.com/s/article/Subscribing-to-Tradovate-Market-Data?language=en_US)) | CME bundle **$12/mo L1**, $41/mo L2 on an old page; NinjaTrader's newer fee page lists $48 for L2 ([NT account fees](https://ninjatrader.com/pricing/account-fees/)) | API keys still need a live ≥$1,000 account, so not practical |
| **TopstepX Practice account** | Free 150K sim, but only with an **active Trading Combine subscription** (from $49/mo); resets free, up to 10/day ([Practice Account](https://help.topstep.com/en/articles/8284134-practice-account)) | L1 free on sim accounts; L2 $38/mo ([L1/L2](https://help.topstep.com/en/articles/8284120-level-1-and-level-2-market-data)) | ProjectX API on Practice uses the same endpoints; no separate sandbox ([API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)); $14.50/mo |
| **Prop evaluation itself** | One-time $79–209 (Lucid, Bulenox, MFFU, FundedNext) | Included with the eval feed (**UNVERIFIED** per firm) | Same route as funded |
| **Rithmic Paper Trading** | $49.99/mo on an old page (**UNVERIFIED**) | Plus data fees | `async_rithmic` after conformance |
| **Own simulator + Databento live** | Databento CME plans $199 / $1,750 / $4,500 per month (see companion doc; tier mapping **UNVERIFIED**) | Yes | Native Python; NautilusTrader Databento adapter |
| **IBKR paper** (companion doc) | Free paper with an IBKR account; CME L1 about $1.55–5/mo | Yes | `ib_async`, NautilusTrader IB adapter |

**Cheapest realistic paper setup for the recommended path:** NinjaTrader free sim plus Sim+ at $35/mo, on the same Windows VPS that will later run the prop account. The bridge code is then identical in paper and funded. The cheapest Linux-native alternative is IBKR paper, but it doesn't exercise the prop routing.

## 5. Cloud hosting

- **Linux VPS** for ProjectX, Rithmic R|Protocol, webhook bridges or Databento: about $4–5/mo for small instances (DigitalOcean Basic Droplet from $4/mo, per [DigitalOcean](https://www.digitalocean.com/pricing/droplets); Hetzner CX22 about $4.35–4.60/mo after its April 2026 price change, per third-party listings and **UNVERIFIED**). An ML filter (LightGBM inference) plus a journal DB fits in 2–4 GB RAM, so budget about $10–25/mo for headroom. A Chicago region is optional for minute-bar trading.
- **Windows VPS** for NinjaTrader 8: trading-specialist hosts near CME (Aurora/Chicago) start around **$30–60/mo**. QuantVPS lists "from $29.99/mo" on a newer page and "$59.99" on an older one; its entry tier is 4 cores / 8 GB, and it advertises about 0.5–1 ms to CME ([QuantVPS pricing](https://www.quantvps.com/pricing), [VPSBenchmarks](https://www.vpsbenchmarks.com/hosters/quantvps)). CrossTrade resells VPS Lite at $34.40/mo ([CrossTrade VPS](https://crosstrade.io/vps)). Prices conflict across dates.
- **Data-center IP restrictions by firm:**
  - **Topstep:** VPS, VPN and remote servers prohibited for trading. This is the only explicit ban found.
  - **Tradeify:** no login via VPN or VPS, but VPS *trading* allowed "at your own risk"; may block setups that obscure device or location.
  - **FundedNext Futures:** using different IPs for dashboard and trading requires prior approval; VPS possibly not permitted at $50k or more (CFD article; Futures applicability **UNVERIFIED**).
  - **MFFU:** shared devices forbidden; VPS not addressed.
  - **Lucid, Bulenox, TPT, Earn2Trade, TradeDay:** no first-party VPS statement found (**UNVERIFIED**).
  - **Practical rule:** use a dedicated single-tenant VPS with a static IP, never shared with anyone. Log into the firm dashboard *from that same VPS* (for example over RDP) so device and IP stay consistent, and never use a VPN.

## 6. Recommendation

> **This section is opinion built on the facts above.** Every option below needs written confirmation from the firm first (§7).

### Best: Lucid Trading (LucidFlex) + NinjaTrader 8 on a Chicago Windows VPS, bridged to the Python engine

- **Why Lucid:**
  - The clearest first-party "yes" to EAs, bots and copiers in funded accounts (FAQ and support article).
  - A 90/10 split.
  - LucidFlex has EOD drawdown, **no daily loss limit and no consistency rule**, which suits a bot that will have streaky days.
  - It supports both the CQG/Tradovate stack (NinjaTrader) and Rithmic, so you can switch routes without switching firms.
- **Why NinjaTrader 8:**
  - It's the user's preferred platform.
  - It's the one route that works across nearly every bot-friendly firm (Lucid, Tradeify, MFFU, Bulenox, FundedNext).
  - It carries the prop feed's real-time data, so you don't need a separate $199+/mo data subscription.
  - It doesn't depend on the Tradovate API, which prop accounts can't use.
- **Architecture:**
  - The Python engine and ML filter run on the same Windows VPS (Python runs fine on Windows), or on a Linux box that talks to the VPS over a private, authenticated tunnel.
  - A small self-written NinjaScript add-on exposes bars, fills and order commands on `localhost` over TCP or WebSocket.
  - CrossTrade's $49/mo REST API is the buy-not-build alternative.
- **Monthly cost estimate (steady state):**
  - Windows VPS: about $35–60.
  - NT8 platform licence for prop accounts: often free (Bulenox includes it). For Lucid: **UNVERIFIED**.
  - Data: included in the prop account feed (**UNVERIFIED**).
  - Optional CrossTrade: $49.
  - **Total about $35–110/mo**, plus one-time evaluation fees (LucidFlex 25K listed at $110; 50K price **UNVERIFIED**) and resets.
  - Paper phase before buying an eval: VPS plus NinjaTrader Sim+ at $35/mo, so **about $70–95/mo**.
- **Tradeoffs:**
  - Windows instead of Linux.
  - Two languages (a thin C# bridge plus Python).
  - NT8 desktop needs auto-restart and auto-login handling.
  - Lucid hasn't said anything about VPS use.
  - The 2025 LucidDirect agreement requires written approval for automated software.

### Runner-up: Bulenox (or Tradeify Rithmic) + Rithmic R|Protocol via `async_rithmic` on a Linux VPS

- **Why:**
  - Fully headless Linux and pure Python.
  - Data and orders arrive on one connection.
  - Bulenox publishes an explicit, priced third-party API path ($100/mo) and allows user-built bots. Tradeify is the only firm that explicitly tolerates VPS trading.
- **Cost:** Linux VPS about $10–25, plus the $100 Bulenox API fee, so **about $110–125/mo**, plus a $175 Qualification fee. Rithmic conformance fee: **UNVERIFIED**.
- **Tradeoffs:**
  - You must pass Rithmic conformance (you may need to register your own app name) and get Bulenox management approval.
  - Bulenox's terms are partly 2021-dated.
  - There's no NautilusTrader adapter; the unofficial one has order entry gated.
  - Tradeify adds video proof of running the code "on your own PC", and the 10-second rule.

### Simplest fallback: Tradovate-backed prop account (Lucid, MFFU or FundedNext) + TradersPost webhooks from a Linux VPS
- About $42–50/mo for the bridge plus $5–25 for the VPS. However, you need your own real-time data feed for the engine, which often costs more than everything else (Databento live, or IBKR market data on a separate account). Use this if the C# bridge is unwanted and the firm confirms that bridges are allowed.

### Avoid for this project
Apex and Alpha Futures (automation banned), and Topstep (API sim-only on Live, VPS banned). Topstep's TopstepX Practice account plus the $14.50 ProjectX API is still a reasonable **paper-testing sandbox** if you're already paying for a Combine.

## 7. Open questions to send to firms

Ask each shortlisted firm in writing:
1. Is a **self-built, fully automated** strategy (no human order entry) allowed in the **funded** account and in any live-transition account?
2. May it run on a **dedicated single-tenant cloud VPS** (state the provider and the static IP), and should I log into the dashboard from that VPS?
3. Which connection is permitted: NinjaTrader 8 strategy or add-on, a Rithmic R|Protocol app (which app name and conformance), or a webhook bridge (name it)?
4. Any per-day trade-count cap, minimum hold time, or news blackout that applies to automated trading?
5. For Lucid: does the LucidDirect "written approval" clause also apply to LucidFlex and LucidPro?

---

## Sources

*All first-party pages were read via domain-restricted search excerpts on 2026-10-31 (direct fetch blocked by sandbox network policy). Page ages, where shown, are as reported by the search index.*

**Topstep / ProjectX**
- TopstepX API Access — https://help.topstep.com/en/articles/11187768-topstepx-api-access
- Live Funded Account Parameters — https://help.topstep.com/en/articles/10657969-live-funded-account-parameters
- Trading Combine Parameters — https://help.topstep.com/en/articles/8284197-trading-combine-parameters
- Express Funded Account Parameters — https://help.topstep.com/en/articles/8284215-express-funded-account-parameters
- Prohibited Conduct — https://help.topstep.com/en/articles/10296582-prohibited-conduct
- Terms of Use — https://www.topstep.com/terms-of-use
- Quantower Connection Instructions — https://help.topstep.com/en/articles/8284179-quantower-connection-instructions
- Maximum Loss Limit — https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit
- Payout Policy — https://help.topstep.com/en/articles/8284233-topstep-payout-policy
- Pricing and Payment — https://help.topstep.com/en/articles/14289835-topstep-pricing-and-payment-questions
- Daily Loss Limit — https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account
- Practice Account — https://help.topstep.com/en/articles/8284134-practice-account
- Level 1 and Level 2 Market Data — https://help.topstep.com/en/articles/8284120-level-1-and-level-2-market-data
- ProjectX API — https://www.projectx.com/api ; homepage (wind-down notice) https://www.projectx.com/ ; refund policy https://dashboard.projectx.com/refund-policy
- ProjectX Gateway docs, rate limits — https://gateway.docs.projectx.com/docs/getting-started/rate-limits/ ; realtime https://gateway.docs.projectx.com/docs/category/realtime-updates/
- TradersPost on ProjectX firms (secondary) — https://blog.traderspost.io/article/what-is-projectx-prop-firms

**Apex Trader Funding**
- Prohibited Activities — https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities
- PA and Compliance — https://support.apextraderfunding.com/hc/en-us/articles/31519788944411-Performance-Account-PA-and-Compliance
- Choosing the Right Platform — https://apextraderfunding.com/help-center/getting-started/choosing-the-right-platform/
- How to Activate a PA — https://support.apextraderfunding.com/hc/en-us/articles/31519770974235-How-to-Activate-a-PA
- Legacy products — https://apextraderfunding.com/legacy-products/ ; homepage https://apextraderfunding.com/

**MyFundedFutures**
- Fair Play and Prohibited Trading Practices — https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices
- Copy Trading — https://help.myfundedfutures.com/en/articles/10771500-copy-trading-at-myfundedfutures
- Cross Instrument Policy — https://help.myfundedfutures.com/en/articles/10244682-cross-instrument-policy
- Traders Evaluation Simplified — https://help.myfundedfutures.com/en/articles/11802636-traders-evaluation-simplified
- Can someone else trade my account? — https://help.myfundedfutures.com/en/articles/8230018-can-someone-else-trade-my-account
- Start trading (platforms) — https://help.myfundedfutures.com/en/articles/11553762-industry-leading-futures-prop-firm-start-trading-with-myfundedfutures
- How it works — https://myfundedfutures.com/how-it-works ; challenge page https://myfundedfutures.com/challenge?id=48&platform=Tradovate
- TradersPost on MFFU (secondary) — https://blog.traderspost.io/article/automate-my-funded-futures-with-traderspost

**Tradeify**
- Guidelines for Traders — https://help.tradeify.co/en/articles/10468318-guidelines-for-traders
- Funded Trader Agreement — https://tradeify.co/funded-trader-agreement
- Common FAQs — https://help.tradeify.co/en/articles/12268494-common-faqs
- Terms of Use — https://tradeify.co/terms-of-use
- Supported Platforms — https://help.tradeify.co/en/articles/10468221-supported-platforms
- Pricing Reference — https://help.tradeify.co/en/articles/14369021-tradeify-pricing-reference

**Take Profit Trader**
- Terms of Service — https://takeprofittrader.com/terms ; homepage https://takeprofittrader.com/ ; TPT vs Topstep https://takeprofittrader.com/blog/take-profit-trader-vs-topstep

**Lucid Trading**
- General FAQ — https://lucidtrading.com/general-faq/
- Other Activities — https://support.lucidtrading.com/en/articles/11404728-other-activities
- Prohibited HFT — https://support.lucidtrading.com/en/articles/11404736-prohibited-high-frequency-trading
- Prohibited Microscalping — https://support.lucidtrading.com/en/articles/11404742-prohibited-microscalping
- Supported Platforms — https://support.lucidtrading.com/en/articles/11404614-lucid-trading-supported-platforms
- Allowed Trading Times — https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times
- LucidDaily — https://support.lucidtrading.com/en/articles/15997244-luciddaily-funded-account
- LucidDirect Account Agreement (2025-05-19) — https://lucidtrading.com/wp-content/uploads/2025/05/LucidDirect-Account-Agreement-5-19.pdf
- LucidFlex 25K listing — https://sb1.lucidtrading.com/product/lucidflex-25k-rithmic/

**Alpha Futures**
- Prohibited Trading Practices — https://help.alpha-futures.com/en/articles/9508585-prohibited-trading-practices
- Copy Trading — https://help.alpha-futures.com/en/articles/10573989-copy-trading
- Direct accounts — https://alpha-futures.com/posts/straight-to-funded-futures-prop-firm-2026
- Platforms — https://alpha-futures.com/platforms ; homepage https://alpha-futures.com/

**Bulenox**
- FAQ — https://bulenox.com/faq ; Accounts & Pricing https://bulenox.com/accounts-pricing ; sign-up terms https://bulenox.com/member/signup ; Terms PDF (2021) https://bulenox.com/legal/Terms_of_Use.pdf ; homepage https://bulenox.com/

**FundedNext**
- Futures General Rules — https://fundednext.com/general-rules/futures/what-is-allowed
- Futures Challenge Terms — https://fundednext.com/futures-challenge-terms
- Terms of Service — https://fundednext.com/terms-of-service
- VPN/VPS article — https://help.fundednext.com/en/articles/8223809-can-i-use-a-vpn-or-vps
- HFT — https://help.fundednext.com/en/articles/11982271-does-fundednext-allow-hft-high-frequency-trading
- Futures page — https://fundednext.com/futures ; Rapid explained https://fundednext.com/blog/futures-rapid-pro-rapid-daily-explained

**Earn2Trade**
- Prohibited Conduct — https://help.earn2trade.com/en/articles/9286647-prohibited-conduct-in-earn2trade-evaluations-and-in-the-livesim-live-trading-environment
- Copy trades — https://help.earn2trade.com/en/articles/12034590-am-i-allowed-to-copy-trades-across-multiple-accounts
- Evaluation rules — https://help.earn2trade.com/en/articles/5941958-what-are-the-evaluation-rules
- Withdrawal policy — https://help.earn2trade.com/en/articles/5452472-what-is-the-withdrawal-policy
- Gauntlet Mini — https://www.earn2trade.com/gauntlet-mini

**TradeDay**
- Terms and Conditions — https://www.tradeday.com/terms-and-conditions ; Rithmic post https://www.tradeday.com/blog-posts/rithmic-is-now-available
- CrossTrade on TradeDay (vendor) — https://crosstrade.io/prop-firms/tradeday

**Tradovate / NinjaTrader**
- Tradovate API Access — https://support.tradovate.com/s/article/Tradovate-API-Access?language=en_US
- Tradovate Settings Overview — https://support.tradovate.com/s/article/Tradovate-Settings-Overview?language=en_US
- Using Your Prop or Evaluation Account — https://support.tradovate.com/s/article/Prop-Firm-and-Evaluation-Account-Inquiries-Tradovate?language=en_US
- TradingView connection guide (Tradovate) — https://support.tradovate.com/s/article/Connecting-Your-Tradovate-Account-to-TradingView?language=en_US
- NinjaTrader MCP (Beta) — https://support.tradovate.com/s/article/NinjaTrader-MCP?language=en_US ; https://docs.ninjatrader.com/mcp
- Subscribing to Market Data — https://support.tradovate.com/s/article/Subscribing-to-Tradovate-Market-Data?language=en_US ; trial https://www.tradovate.com/trial/
- NinjaTrader developer docs — https://docs.ninjatrader.com/api/getting-started ; https://docs.ninjatrader.com/api/authentication ; https://docs.ninjatrader.com/api/websockets ; https://docs.ninjatrader.com/api/oauth ; https://docs.ninjatrader.com/api/samples
- NT8 ATI — https://static.ninjatrader.com/support/helpGuides/nt8/file_interface.htm ; https://static.ninjatrader.com/support/helpGuides/nt8/options_ati.htm ; requirements https://ninjatrader.com/support/helpGuides/nt8/minimum_system_requirements.htm
- NinjaTrader simulator — https://ninjatrader.com/trading-platform/trading-simulator/ ; pricing https://ninjatrader.com/pricing/ ; account fees https://ninjatrader.com/pricing/account-fees/
- NinjaTrader acquires Tradovate — https://ninjatrader.com/NewsReleases/NinjaTrader-Acquires-Tradovate ; https://www.financemagnates.com/forex/ninjatrader-buys-tradovate-in-115-million-deal/

**TradingView**
- Configure webhook alerts — https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
- Port numbers — https://www.tradingview.com/support/solutions/43000529314-i-cannot-send-webhook-to-a-url-with-a-port-number/
- Webhook errors — https://www.tradingview.com/support/solutions/43000776894-what-do-errors-mean-when-sending-webhooks/
- Webhook resubmission — https://www.tradingview.com/support/solutions/43000735201-webhook-resubmission/
- Pricing — https://www.tradingview.com/pricing/?feature=alertsWebhook

**Rithmic**
- API suite — https://www.rithmic.com/products/api-suite ; products https://www.rithmic.com/products ; exchange simulator https://www.rithmic.com/products/exchange-simulator ; FAQ https://www.rithmic.com/support/faq
- async_rithmic — https://pypi.org/project/async-rithmic/ ; https://async-rithmic.readthedocs.io/en/stable/connection.html

**Bridges, frameworks, hosting**
- TradersPost — https://traderspost.io/pricing ; https://traderspost.io/ ; https://traderspost.io/compare
- CrossTrade — https://crosstrade.io/pricing ; https://crosstrade.io/crosstrade-api ; https://crosstrade.io/vps
- PickMyTrade (competitor comparison) — https://blog.pickmytrade.trade/crosstrade-alternative/
- project-x-py — https://pypi.org/project/project-x-py/
- tradovate (PyPI) — https://pypi.org/project/tradovate/
- NautilusTrader 1.231.0 wheel (adapter list inspected) — https://pypi.org/project/nautilus-trader/ ; Rithmic RFC https://github.com/nautechsystems/nautilus_trader/issues/3768 ; community adapter https://github.com/ozeron/rithmic-nt-connect
- QuantVPS — https://www.quantvps.com/pricing ; https://www.vpsbenchmarks.com/hosters/quantvps
- DigitalOcean Droplets — https://www.digitalocean.com/pricing/droplets
- Hetzner CX22 (third-party listing) — https://vpsbenchmarks.com/hosters/hetzner/plans/cx22
