"""Non-ICT intraday setups, batch 1 (setups/intraday.py), on synthetic days."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from moon_ai.bars import Bar
from moon_ai.config import load_config
from moon_ai.engine import Context
from moon_ai.sessions import NY
from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.intraday import DayBook

SYM = "MNQ.v.0"
BASE = 15000.0
WARMUP = [date(2024, 3, 1) + timedelta(days=i) for i in range(40)]
WARMUP = [d for d in WARMUP if d.weekday() < 5][:16]  # 16 weekdays, no DST change inside
DAY = date(2024, 3, 25)  # a Monday after the warm-up


def bar(day, hh, mm, o, h=None, lo=None, c=None):
    t0 = datetime.combine(day, time(hh, mm), tzinfo=NY).astimezone(UTC)
    c = o if c is None else c
    return Bar(SYM, t0, t0 + timedelta(minutes=1), o, h or max(o, c), lo or min(o, c), c, 10, 1)


def quiet_day(day, level=BASE):
    """Overnight bars, then a cash session that ranges 10 points and closes at `level`."""
    prev = day - timedelta(days=3 if day.weekday() == 0 else 1)
    out = [bar(prev, 18, 0, level), bar(day, 2, 0, level, level + 3, level - 3)]
    for m in range(390):
        t = datetime.combine(day, time(9, 30)) + timedelta(minutes=m)
        wiggle = 5.0 if m % 2 else -5.0
        out.append(bar(day, t.hour, t.minute, level, level + abs(wiggle), level - 5, level))
    return out


def run(setup, today_bars, params=None):
    config = load_config()
    d = load_setup_defaults()[setup]
    s = REGISTRY[setup](params or d.params, config)
    ctx = Context(broker=None, journal=None)
    out = []
    for day in WARMUP:
        for b in quiet_day(day):
            ctx._append(b)
            assert s.scan(ctx) == []
    for b in today_bars:
        ctx._append(b)
        out += s.scan(ctx)
    return out


def rth(day, prices):
    """Cash-session bars from 09:30, one per price (open=close=price, +-1 point)."""
    out = []
    for m, p in enumerate(prices):
        t = datetime.combine(day, time(9, 30)) + timedelta(minutes=m)
        out.append(bar(day, t.hour, t.minute, p, p + 1, p - 1, p))
    return out


def test_daybook_waits_for_enough_finished_days():
    book = DayBook(atr_days=14)
    for day in WARMUP[:15]:
        for b in quiet_day(day):
            book.update(b)
            assert book.stats() is None  # 14 true ranges need 15 finished days
    for b in quiet_day(WARMUP[15])[:3]:
        book.update(b)
    s = book.stats()
    assert s is not None and s.prev_close == BASE and s.atr == pytest.approx(10.0)


def test_orb_goes_with_the_first_five_minutes():
    up = rth(DAY, [BASE, BASE + 2, BASE + 4, BASE + 6, BASE + 8, BASE + 8])
    cands = run("orb_5m", up)
    assert len(cands) == 1
    c = cands[0]
    assert c.side == "long" and c.entry_type == "market"
    assert c.decision_time == datetime.combine(DAY, time(9, 35), tzinfo=NY).astimezone(UTC)
    assert c.stop == BASE - 1 - 0.25  # range low minus one tick
    down = rth(DAY, [BASE, BASE - 2, BASE - 4, BASE - 6, BASE - 8, BASE - 8])
    assert run("orb_5m", down)[0].side == "short"


def test_orb_skips_a_doji():
    flat = rth(DAY, [BASE] * 10)
    assert run("orb_5m", flat) == []


def test_gap_fill_fades_toward_previous_close():
    gap_down = rth(DAY, [BASE - 4, BASE - 4])  # 0.4 ATR below the previous close
    c = run("gap_fill", gap_down)[0]
    assert c.side == "long" and c.target == BASE
    assert c.stop == pytest.approx(BASE - 4 - 4 - 0.25)
    too_big = rth(DAY, [BASE - 9, BASE - 9])  # 0.9 ATR: not traded
    assert run("gap_fill", too_big) == []


def test_overnight_breakout_needs_a_five_minute_close_beyond_the_range():
    on = [bar(DAY - timedelta(days=3), 18, 0, BASE), bar(DAY, 3, 0, BASE, BASE + 3, BASE - 3)]
    prices = [BASE] * 5 + [BASE + 5] * 6  # above the overnight high from the 09:35 bar
    cands = run("overnight_breakout", on + rth(DAY, prices))
    assert len(cands) == 1 and cands[0].side == "long"
    # That bar closes 09:36, so the first 5-minute mark beyond the range is 09:40.
    assert cands[0].decision_time == datetime.combine(DAY, time(9, 40), tzinfo=NY).astimezone(UTC)


def test_intraday_momentum_trades_the_first_half_hours_direction_at_1530():
    prices = [BASE] * 29 + [BASE + 20] + [BASE + 20] * 331  # up at 10:00, still at 15:30
    cands = run("intraday_momentum", rth(DAY, prices))
    assert len(cands) == 1
    c = cands[0]
    assert c.side == "long"
    assert c.decision_time == datetime.combine(DAY, time(15, 30), tzinfo=NY).astimezone(UTC)
    assert c.stop == pytest.approx(BASE + 20 - 1.0 - 0.25)  # 0.1 ATR


def test_noise_breakout_waits_for_a_checkpoint_outside_the_area():
    # Quiet days move 0 from the open at the close; a 40-point move is outside.
    prices = [BASE] * 20 + [BASE + 40] * 20
    cands = run("noise_breakout", rth(DAY, prices))
    assert len(cands) == 1 and cands[0].side == "long"
    assert cands[0].decision_time == datetime.combine(DAY, time(10, 0), tzinfo=NY).astimezone(UTC)


def test_noise_paper_rules_exit_back_inside_and_re_enter():
    from dataclasses import replace as dc_replace

    d = load_setup_defaults()["noise_breakout"]
    paper = d.trial_params(d.trial("paper_rules"))
    s = REGISTRY["noise_breakout"](paper, load_config())
    assert not s.once_a_day
    ctx = Context(broker=None, journal=None)
    for day in WARMUP:
        for b in quiet_day(day):
            ctx._append(b)
            s.scan(ctx)
    # Out above the area at 10:00, back to the open by 10:30, out again at 11:00.
    prices = [BASE] * 20 + [BASE + 40] * 30 + [BASE] * 30 + [BASE + 40] * 10
    cands, exits = [], []
    for b in rth(DAY, prices):
        ctx._append(b)
        new = s.scan(ctx)
        cands += new
        if cands and s.manage(cands[0], ctx):
            exits.append(to_ny_time(ctx.now))
    assert [to_ny_time(c.decision_time) for c in cands] == [time(10, 0), time(11, 0)]
    assert time(10, 30) in exits  # back inside at the 10:30 checkpoint
    simple = REGISTRY["noise_breakout"](d.params, load_config())
    assert simple.once_a_day and not simple.manage(cands[0], ctx)
    exit_only = dc_replace(d.params, exit_rule="boundary_vwap")
    assert REGISTRY["noise_breakout"](exit_only, load_config()).once_a_day


def to_ny_time(ts):
    from moon_ai.sessions import to_ny

    return to_ny(ts).time()


# --- batch 2 -------------------------------------------------------------------------------


def test_regime_compares_the_latest_atr_with_the_median():
    book = DayBook(regime_days=5)
    assert book.regime() is None
    for x in (10, 12, 11, 9, 13):
        book.atr_hist.append(x)
    assert book.regime() == "high"  # 13 > median 11
    book.atr_hist.append(8)
    assert book.regime() == "low"


def test_turn_of_month_days():
    d = load_setup_defaults()["turn_of_month"]
    s = REGISTRY["turn_of_month"](d.params, load_config())
    from moon_ai.setups.intraday import DayStats

    stats = DayStats(atr=10.0, prev_close=BASE, open=BASE, on_high=BASE, on_low=BASE)

    def fires(day):
        ny = datetime.combine(day, time(9, 31), tzinfo=NY)
        b = bar(day, 9, 30, BASE)
        return s.decide(b, ny.astimezone(UTC), ny, stats) is not None

    # May 2024: Fri 31 is the last weekday; June 3-5 (Mon-Wed) are the first three.
    assert [fires(date(2024, 5, x)) for x in (29, 30, 31)] == [False, False, True]
    assert [fires(date(2024, 6, x)) for x in (3, 4, 5, 6)] == [True, True, True, False]


def test_vwap_pullback_buys_the_first_touch_on_a_trend_day():
    # Up 10 points (1 ATR) by 10:00, then a dip to the open-side VWAP after 10:30.
    prices = [BASE + m * 0.4 for m in range(30)] + [BASE + 12] * 30 + [BASE + 6] + [BASE + 9] * 5
    rows = rth(DAY, prices)
    rows[60] = bar(DAY, 10, 30, BASE + 9, BASE + 9, BASE + 3, BASE + 9)  # wick through VWAP
    cands = run("vwap_pullback", rows)
    assert len(cands) == 1 and cands[0].side == "long"
    assert to_ny_time(cands[0].decision_time) == time(10, 31)


def test_vwap_reversion_fades_back_to_vwap():
    prices = [BASE] * 61 + [BASE - 5] * 5  # 0.5 ATR under VWAP at 10:31
    p = load_setup_defaults()["vwap_reversion"].params
    from dataclasses import replace as dc_replace

    cands = run("vwap_reversion", rth(DAY, prices), params=dc_replace(p, vol_regime="any"))
    assert len(cands) == 1
    c = cands[0]
    assert c.side == "long" and BASE - 1 < c.target <= BASE  # VWAP, pulled down a little
