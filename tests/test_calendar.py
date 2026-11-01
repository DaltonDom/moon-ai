from datetime import UTC, date, datetime

import pytest

from moon_ai.data.calendar import SessionCalendar, easter, holidays, roll_days, session_info
from tests.helpers import bar

# NYSE full-day holidays (CME equity index: closed or halted early), 2019-2027.
HOLIDAYS = {
    2019: ["01-01", "01-21", "02-18", "04-19", "05-27", "07-04", "09-02", "11-28", "12-25"],
    2020: ["01-01", "01-20", "02-17", "04-10", "05-25", "07-03", "09-07", "11-26", "12-25"],
    2021: ["01-01", "01-18", "02-15", "04-02", "05-31", "07-05", "09-06", "11-25", "12-24"],
    2022: ["01-17", "02-21", "04-15", "05-30", "06-20", "07-04", "09-05", "11-24", "12-26"],
    2023: [
        "01-02",
        "01-16",
        "02-20",
        "04-07",
        "05-29",
        "06-19",
        "07-04",
        "09-04",
        "11-23",
        "12-25",
    ],
    2024: [
        "01-01",
        "01-15",
        "02-19",
        "03-29",
        "05-27",
        "06-19",
        "07-04",
        "09-02",
        "11-28",
        "12-25",
    ],
    2025: [
        "01-01",
        "01-09",
        "01-20",
        "02-17",
        "04-18",
        "05-26",
        "06-19",
        "07-04",
        "09-01",
        "11-27",
        "12-25",
    ],
    2026: [
        "01-01",
        "01-19",
        "02-16",
        "04-03",
        "05-25",
        "06-19",
        "07-03",
        "09-07",
        "11-26",
        "12-25",
    ],
    2027: [
        "01-01",
        "01-18",
        "02-15",
        "03-26",
        "05-31",
        "06-18",
        "07-05",
        "09-06",
        "11-25",
        "12-24",
    ],
}
EARLY = {
    2019: ["07-03", "11-29", "12-24"],
    2020: ["11-27", "12-24"],
    2021: ["11-26"],
    2022: ["11-25"],
    2023: ["07-03", "11-24"],
    2024: ["07-03", "11-29", "12-24"],
    2025: ["07-03", "11-28", "12-24"],
    2026: ["11-27", "12-24"],
    2027: ["11-26"],
}


@pytest.mark.parametrize("year", sorted(HOLIDAYS))
def test_holiday_and_early_close_dates_match_the_exchange_calendar(year):
    got = holidays(year)
    full = {d for d, s in got.items() if s.kind in ("closed", "holiday_halt")}
    early = {d for d, s in got.items() if s.kind == "early_close"}
    assert full == {date.fromisoformat(f"{year}-{md}") for md in HOLIDAYS[year]}
    assert early == {date.fromisoformat(f"{year}-{md}") for md in EARLY[year]}


def test_easter():
    assert easter(2019) == date(2019, 4, 21)
    assert easter(2024) == date(2024, 3, 31)
    assert easter(2026) == date(2026, 4, 5)


def test_session_kinds():
    assert session_info(date(2026, 10, 30)).kind == "regular"
    assert session_info(date(2026, 10, 31)).kind == "weekend"
    assert session_info(date(2026, 4, 3)).kind == "closed"  # Good Friday
    assert session_info(date(2026, 11, 26)).halt_ny is not None  # Thanksgiving halt
    assert session_info(date(2026, 11, 27)).kind == "early_close"


def test_skip_reason_covers_holidays_rolls_and_degraded_days():
    cal = SessionCalendar(
        rolls=frozenset({date(2026, 9, 14)}), degraded=frozenset({date(2026, 3, 16)})
    )
    assert cal.skip_reason(date(2026, 10, 30)) is None
    assert cal.skip_reason(date(2026, 12, 24)) == "early_close"
    assert cal.skip_reason(date(2026, 9, 14)) == "roll"
    assert cal.skip_reason(date(2026, 3, 16)) == "degraded"
    assert cal.no_new_trades(date(2026, 7, 3))


def test_roll_day_is_the_trading_day_of_the_first_new_contract_bar():
    # A bar opening Sunday 18:00 New York (22:00 UTC in September) belongs to Monday's session.
    first = bar(0, 1, 2, 0.5, 1.5, instrument_id=2, start=datetime(2026, 9, 13, 22, 0, tzinfo=UTC))
    from dataclasses import replace

    assert roll_days([replace(first, roll=True)]) == {date(2026, 9, 14)}
    assert roll_days([first]) == set()
