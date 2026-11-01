"""The committed news calendar, data_public/news_events.csv (built by
scripts/build_news_history.py), loads cleanly and holds known releases."""

from collections import Counter
from datetime import UTC, datetime

import pytest

from moon_ai.data.news import NEWS_CSV, load_events
from moon_ai.sessions import NY

EVENTS = load_events(NEWS_CSV)
BY_ID = {e.event_id: e for e in EVENTS}
HAS_BLS = any(e.publisher == "BLS" for e in EVENTS)
NEEDS_BLS = pytest.mark.skipif(
    not HAS_BLS,
    reason="no BLS rows yet: www.bls.gov refused the builder (HTTP 403); CPI/NFP/PPI missing",
)


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def per_year(kind):
    return Counter(e.at.year for e in EVENTS if e.event_type == kind)


@NEEDS_BLS
def test_full_calendar_has_at_least_700_rows():
    assert len(EVENTS) >= 700


def test_bea_and_fed_rows_are_all_there():
    # GDP, PCE, FOMC and Chair rows for 2019 through Oct 2026, without BLS.
    assert len(EVENTS) >= 520
    for kind in ("GDP", "PCE"):
        years = per_year(kind)
        assert all(10 <= years[y] <= 12 for y in range(2019, 2027)), (kind, years)


def test_every_row_points_at_an_official_page():
    hosts = ("https://www.bea.gov/", "https://www.federalreserve.gov/", "https://www.bls.gov/")
    assert all(e.source_url.startswith(hosts) for e in EVENTS)
    assert all(e.verified_by.startswith("builder") for e in EVENTS)


def test_march_15_2020_emergency_cut_is_unscheduled_at_5pm():
    e = BY_ID["fomc-2020-03-15"]
    assert e.event_type == "FOMC_STATEMENT"
    assert e.at == utc(2020, 3, 15, 21, 0)  # 17:00 EDT
    assert not e.scheduled


def test_other_unscheduled_fomc_statements():
    assert BY_ID["fomc-2020-03-03"].at == utc(2020, 3, 3, 15, 0)  # 10:00 EST
    assert BY_ID["fomc-2020-03-23"].at == utc(2020, 3, 23, 12, 0)  # 08:00 EDT
    # The Oct 4, 2019 unscheduled meeting announced nothing that day; its
    # statement came out on Oct 11 at 11:00.
    assert BY_ID["fomc-2019-10-11"].at == utc(2019, 10, 11, 15, 0)
    assert "fomc-2019-10-04" not in BY_ID
    unscheduled = {e.event_id for e in EVENTS if not e.scheduled}
    assert unscheduled == {
        "fomc-2019-10-11",
        "fomc-2020-03-03",
        "fomc-2020-03-15",
        "fomc-2020-03-23",
    }


def test_scheduled_fomc_meetings_are_eight_a_year_at_2pm():
    statements = [e for e in EVENTS if e.event_type == "FOMC_STATEMENT" and e.scheduled]
    years = Counter(e.at.year for e in statements)
    # 2020: the March 17-18 meeting was cancelled (replaced by the Mar 15 action).
    assert years == {2019: 8, 2020: 7, 2021: 8, 2022: 8, 2023: 8, 2024: 8, 2025: 8, 2026: 7}
    assert all(e.at.astimezone(NY).strftime("%H:%M") == "14:00" for e in statements)


def test_pce_comes_out_with_gdp_from_feb_20_2026():
    assert BY_ID["gdp-2026-02-20"].at == BY_ID["pce-2026-02-20"].at == utc(2026, 2, 20, 13, 30)
    assert BY_ID["gdp-2026-10-29"].at == BY_ID["pce-2026-10-29"].at == utc(2026, 10, 29, 12, 30)


def test_shutdown_delayed_bea_releases_sit_on_their_actual_dates():
    # Sep 2025 PIO, delayed by the Oct-Nov 2025 lapse, came out Dec 5 at 10:00 ET.
    assert BY_ID["pce-2025-12-05"].at == utc(2025, 12, 5, 15, 0)
    assert BY_ID["gdp-2025-12-23"].event_type == "GDP"
    assert not any(
        e.event_type in ("GDP", "PCE") and utc(2025, 10, 1) <= e.at < utc(2025, 12, 1)
        for e in EVENTS
    )


def test_jackson_hole_keynotes():
    assert BY_ID["jackson-hole-2023-08-25"].at == utc(2023, 8, 25, 14, 5)  # 10:05 EDT
    assert per_year("JACKSON_HOLE") == {y: 1 for y in range(2019, 2027)}


def test_humphrey_hawkins_hearings_come_in_pairs():
    days = {e.at.date() for e in EVENTS if e.event_type == "FED_CHAIR_TESTIMONY"}
    counts = Counter(d.year for d in days)
    assert all(counts[y] == 4 for y in range(2019, 2026))
    assert counts[2026] == 2  # no hearing in the first half of 2026; Jul 14-15 were held
