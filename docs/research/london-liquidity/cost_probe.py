"""Free cost probes (metadata.get_cost) for the London-liquidity sample.

Reads DATABENTO_API_KEY from the environment (databento.Historical() default).
Prints only costs and sizes; never the key.
"""

from __future__ import annotations

import sys
from datetime import date

import databento as db

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from windows import DATASET, SYMBOL, sample_days, window_utc

client = db.Historical()


def cost(schema: str, start, end) -> tuple[float, int]:
    kw = dict(
        dataset=DATASET,
        symbols=[SYMBOL],
        stype_in="continuous",
        schema=schema,
        start=start,
        end=end,
    )
    return client.metadata.get_cost(**kw), client.metadata.get_billable_size(**kw)


if __name__ == "__main__":
    print(client.metadata.get_dataset_range(dataset=DATASET))
    c, s = cost("ohlcv-1m", "2026-05-01", "2026-10-31")
    print(f"ohlcv-1m 2026-05-01..2026-10-31: ${c:.4f} {s / 1e6:.2f} MB")
    for schema in ("tbbo", "mbp-1", "trades"):
        for w in ("london", "nyam"):
            d = date(2026, 10, 28)
            a, b = window_utc(d, w)
            c, s = cost(schema, a, b)
            print(f"{schema} {w} {d}: ${c:.4f} {s / 1e6:.2f} MB ({s / 80:.0f} rec@80B)")
    d = date(2026, 10, 28)
    a, b = window_utc(d, "nyam")
    c, s = cost("mbp-10", a, b)
    print(f"mbp-10 nyam {d}: ${c:.4f} {s / 1e6:.2f} MB")
    a, b = window_utc(d, "london")
    c, s = cost("mbp-10", a, b)
    print(f"mbp-10 london {d}: ${c:.4f} {s / 1e6:.2f} MB")
    print(sample_days())
