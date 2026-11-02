"""moon_ai.research.studies on hand-made bars."""

from datetime import UTC, date, datetime, timedelta

import polars as pl

from moon_ai.research import studies as S


def bars(day: date, path: dict[str, float], start_px: float = 100.0) -> list[dict]:
    """A CME session of flat 1-minute bars (18:00 the day before to 16:00) with
    {"HH:MM": price} jumps; each listed minute's bar trades to that price."""
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    t = datetime.combine(day - timedelta(days=1), datetime.min.time().replace(hour=18), ny)
    end = datetime.combine(day, datetime.min.time().replace(hour=16), ny)
    px, rows = start_px, []
    while t < end:
        new = path.get(t.strftime("%H:%M"), px)
        rows.append(
            {
                "ts_event": t.astimezone(UTC),
                "open": px,
                "high": max(px, new) + 0.25,
                "low": min(px, new) - 0.25,
                "close": new,
                "instrument_id": 1,
            }
        )
        px, t = new, t + timedelta(minutes=1)
    return rows


def test_rate_has_a_wilson_interval():
    assert S.rate(0, 0) == "no cases"
    assert S.rate(50, 100) == "50/100 = 50% (40%-60%)"


def test_frame_uses_the_cme_trading_day_and_new_york_clock():
    df = S.frame(pl.DataFrame(bars(date(2026, 7, 15), {})), date(2026, 7, 15), date(2026, 7, 16))
    assert df["tday"].unique().to_list() == [date(2026, 7, 15)]
    # Minutes after midnight, New York: the session runs 18:00 (1080) to 16:00 (959).
    assert df["hm"][0] == 18 * 60 and df["hm"][-1] == 16 * 60 - 1


def test_midnight_open_counts_a_buy_below_the_midnight_open():
    # Midnight at 100, dip to 95 before 09:30, rally to 110 by 11:00.
    day = bars(date(2026, 7, 15), {"05:00": 95.0, "10:30": 110.0})
    df = S.frame(pl.DataFrame(day), date(2026, 7, 15), date(2026, 7, 16))
    out = "\n".join(S.midnight_open(df))
    assert "09:30 below midnight open -> 11:00 up: 1/1" in out


def test_engineered_candle_scalp_wins_when_the_next_candle_is_fully_traded():
    # Overnight range 99.75-100.25. 08:30 bar closes at 102 (above it). The 08:35 bar
    # ranges 101.75-125 (EO candle). Later price returns to 101.75, then rallies to 126.
    path = {"08:30": 102.0, "08:35": 125.0, "08:39": 102.0, "08:45": 101.75, "09:10": 126.0}
    df = S.frame(pl.DataFrame(bars(date(2026, 7, 15), path)), date(2026, 7, 15), date(2026, 7, 16))
    out = "\n".join(S.engineered_candle(df))
    assert "trades 1" in out and "win rate 1/1" in out
