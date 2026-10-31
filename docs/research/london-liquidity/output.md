
## 1-minute bar statistics (ohlcv-1m, 2026-05-01..2026-10-30)

| window | days | bars present % | volume/min median (p25-p75) | 1m range ticks p50/p75/p90 | 15m range ticks p50/p75/p90 | window range ticks p50/p75/p90 |
|---|---:|---:|---:|---:|---:|---:|
| London 02:00-05:00 | 131 | 100.0 | 635 (412-956); mean 758 | 39 / 54 / 74 | 158 / 213 / 290 | 588 / 752 / 1013 |
| NY AM 09:30-11:00 | 131 | 100.0 | 7576 (5188-10536); mean 8038 | 107 / 151 / 202 | 415 / 587 / 760 | 1023 / 1409 / 1770 |
| Silver Bullet 10:00-11:00 | 131 | 100.0 | 6605 (4660-8898); mean 6916 | 96 / 135 / 180 | 369 / 514 / 669 | 736 / 1000 / 1311 |

## Sweep-and-reverse stop distance (ohlcv-1m proxy, ticks)

| setup proxy | days with a sweep | sweep-bar range p50/p75/p90 | stop A (enter on close-back) p50/p75/p90 | MSS confirmed | stop B (enter on MSS close) p50/p75/p90 |
|---|---:|---:|---:|---:|---:|
| London (sweep of Asian range 20:00-00:00) | 86 | 42 / 58 / 82 | 44 / 69 / 117 | 39 | 89 / 130 / 169 |
| NY AM 09:30-11:00 (sweep of London 02:00-05:00 range) | 98 | 154 / 215 / 289 | 174 / 254 / 322 | 28 | 239 / 354 / 418 |
| Silver Bullet 10-11 (sweep of 09:30-10:00 range) | 111 | 131 / 188 / 267 | 104 / 148 / 198 | 30 | 268 / 339 / 456 |

### Generic local sweep (prior 15-bar high/low taken by >=1 tick, closes back inside)

| window | events/day | sweep-bar range p50/p75/p90 | stop (close -> extreme+1 tick) p50/p75/p90 |
|---|---:|---:|---:|
| London 02:00-05:00 | 23.3 | 43 / 59 / 77 | 24 / 38 / 56 |
| NY AM 09:30-11:00 | 10.8 | 103 / 146 / 194 | 56 / 91 / 131 |
| Silver Bullet 10:00-11:00 | 6.4 | 94 / 134 / 178 | 51 / 79 / 120 |

## Top of book, sampled every second (bbo-1s, 10 days 2026-10-16..29)

| window | seconds | spread ticks p50/p75/p90/p99 | % time spread > 1 tick | mean spread | bid size p50 (p10) | ask size p50 (p10) | % time touch size < N lots, N=1..5 (bid/ask avg) |
|---|---:|---:|---:|---:|---:|---:|---|
| London 02:00-05:00 | 107889 | 2 / 3 / 3 / 3 | 97.0 | 2.28 | 4 (1) | 4 (1) | 0 / 15 / 29 / 45 / 61 |
| NY AM 09:30-11:00 | 54000 | 2 / 2 / 2 / 3 | 76.5 | 1.82 | 4 (1) | 4 (1) | 0 / 18 / 34 / 49 / 63 |
| Silver Bullet 10:00-11:00 | 36000 | 2 / 2 / 2 / 3 | 72.9 | 1.74 | 4 (1) | 4 (1) | 0 / 15 / 29 / 43 / 57 |

(last column: % of seconds where the touch on a side shows fewer than N lots, N = 1..5, averaged over bid and ask; N=1 means the side is empty)

## Trades and spread at trade time (tbbo)

| window | days | trades/min mean | contracts/min mean | median trade size | spread before trade p50/p90 ticks | % trades with spread > 1 tick |
|---|---:|---:|---:|---:|---:|---:|
| London 02:00-05:00 | 10 | 482 | 940 | 1 | 2 / 3 | 72.7 |
| NY AM 09:30-11:00 | 2 | 4023 | 7615 | 1 | 1 / 2 | 43.3 |
| Silver Bullet 10:00-11:00 | 2 | 3178 | 6206 | 1 | 1 / 2 | 39.1 |

## Stop-order slippage when a fresh 15-minute high/low is taken (tbbo)

Event: first trade in a minute at or beyond (prior-15-bar extreme + 1 tick) = a resting stop at S is elected. Gap = trigger trade price beyond S. Fill for N lots = walk the post-trigger touch (BBO of the first tbbo record from a later matching event; size beyond the touch assumed 1 tick worse per touch-size). Slippage = fill - S in ticks.

| window | events | trigger gap ticks p50/p90/max | triggering order runs past S, ticks p50/p90/max | N=1 slip mean / p90 | N=3 slip mean / p90 | N=5 slip mean / p90 | % events: touch < 5 lots after trigger |
|---|---:|---:|---:|---:|---:|---:|---:|
| London 02:00-05:00 | 549 | 0 / 0 / 2 | 1 / 3 / 13 | 0.49 / 2 | 0.78 / 2 | 1.15 / 3 | 63 |
| NY AM 09:30-11:00 | 56 | 0 / 0 / 0 | 2 / 10 / 21 | 2.57 / 10 | 2.79 / 10 | 3.05 / 10 | 41 |

## Market entry at a bar close (bbo-1s at minute boundaries, 10 days)

(Pooled over buys and sells the mean equals the half-spread by construction; the p90 is the one-sided cost a single fill can see.)

| window | boundaries | half-spread ticks mean | buy at ask vs bar close, mean / p90 ticks | buy at ask vs next bar open, mean / p90 ticks |
|---|---:|---:|---:|---:|
| London 02:00-05:00 | 1799 | 1.14 | 1.14 / 3 | 1.14 / 3 |
| NY AM 09:30-11:00 | 900 | 0.90 | 0.90 / 2 | 0.90 / 2 |
| Silver Bullet 10:00-11:00 | 600 | 0.87 | 0.87 / 2 | 0.87 / 2 |

## Depth and market-order walk (mbp-10, 2026-10-28, London 03:00-03:15 and NY 10:00-10:05)

| window | seconds | cum. size within 1 / 3 / 5 levels (median, per side) | market buy N=1/3/5/10/20 slippage vs touch, mean ticks | N=5 / N=20 p90 | vs mid, N=1 / N=5 mean ticks |
|---|---:|---:|---:|---:|---:|
<!-- mbp-10 cross-check London 03:00-03:15: spread p50 2, % > 1 tick 94 -->
| London 03:00-03:15 | 900 | 4 / 21 / 39 | 0.00 / 0.13 / 0.27 / 0.61 / 1.22 | 0.80 / 1.70 | 1.03 / 1.29 |
<!-- mbp-10 cross-check NY AM 10:00-10:05: spread p50 2, % > 1 tick 67 -->
| NY AM 10:00-10:05 | 300 | 5 / 28 / 57 | 0.00 / 0.16 / 0.28 / 0.53 / 0.99 | 0.80 / 1.45 | 0.83 / 1.11 |

Round-trip commission: 2 x $0.62 = $1.24 = 2.48 ticks per contract
