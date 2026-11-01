from datetime import UTC, date, datetime, timedelta

import pytest

from moon_ai.data.news import COLUMNS, Blackout, NewsCalendarError, load_events

ROWS = [
    # event_id, type, publisher, local ET, utc, scheduled
    ("cpi-2026-10", "CPI", "BLS", "2026-10-14T08:30", "2026-10-14T12:30:00Z", "true"),
    ("ppi-2026-10", "PPI", "BLS", "2026-10-14T08:30", "2026-10-14T12:30:00Z", "true"),
    ("ism-2026-10", "ISM_MANUFACTURING", "ISM", "2026-10-01T10:00", "2026-10-01T14:00:00Z", "true"),
    ("fomc-2026-10", "FOMC_STATEMENT", "FRB", "2026-10-28T14:00", "2026-10-28T18:00:00Z", "true"),
    ("presser-2026-10", "FOMC_PRESSER", "FRB", "2026-10-28T14:30", "2026-10-28T18:30:00Z", "true"),
    ("nfp-2026-01", "NFP", "BLS", "2026-01-09T08:30", "2026-01-09T13:30:00Z", "true"),
    (
        "fomc-2020-03-15",
        "FOMC_STATEMENT",
        "FRB",
        "2020-03-15T17:00",
        "2020-03-15T21:00:00Z",
        "false",
    ),
]


def write(tmp_path, rows=ROWS, header=COLUMNS):
    p = tmp_path / "news.csv"
    lines = [",".join(header)] + [",".join([*r, "https://example.gov", "test"]) for r in rows]
    p.write_text("\n".join(lines) + "\n")
    return p


def utc(*a):
    return datetime(*a, tzinfo=UTC)


@pytest.fixture
def bo(tmp_path):
    return Blackout(load_events(write(tmp_path)))


def test_blocking_release_gets_plus_minus_15_minutes(bo):
    # CPI and PPI at the same 08:30 merge into one window.
    w = bo.window_at(utc(2026, 10, 14, 12, 30))
    assert (w.start, w.end) == (utc(2026, 10, 14, 12, 15), utc(2026, 10, 14, 12, 45))
    assert set(w.events) == {"cpi-2026-10", "ppi-2026-10"}
    assert bo.in_blackout(utc(2026, 10, 14, 12, 15))
    assert not bo.in_blackout(utc(2026, 10, 14, 12, 45))
    assert not bo.in_blackout(utc(2026, 10, 14, 12, 14, 59))


def test_winter_release_uses_est(bo):
    assert bo.in_blackout(utc(2026, 1, 9, 13, 30))  # 08:30 EST = 13:30 UTC


def test_fomc_day_is_blocked_from_13_45_to_15_30(bo):
    w = bo.window_at(utc(2026, 10, 28, 19, 0))
    assert (w.start, w.end) == (utc(2026, 10, 28, 17, 45), utc(2026, 10, 28, 19, 30))
    assert set(w.events) == {"fomc-2026-10", "presser-2026-10"}
    assert bo.is_fomc_day(date(2026, 10, 28)) and not bo.is_fomc_day(date(2026, 10, 27))


def test_recorded_and_unscheduled_events_never_block(bo):
    assert not bo.in_blackout(utc(2026, 10, 1, 14, 0))  # ISM
    assert not bo.in_blackout(utc(2020, 3, 15, 21, 0))  # emergency cut
    assert not bo.is_fomc_day(date(2020, 3, 15))


def test_events_near_never_sees_an_unscheduled_event_early(bo):
    ids = lambda es: {e.event_id for e in es}  # noqa: E731
    hour = timedelta(hours=1)
    assert ids(bo.events_near(utc(2026, 10, 1, 13, 30), hour, hour)) == {"ism-2026-10"}
    assert (
        ids(bo.events_near(utc(2026, 10, 1, 13, 30), hour, hour, include_recorded=False)) == set()
    )
    assert ids(bo.events_near(utc(2020, 3, 15, 20, 50), hour, hour)) == set()
    assert ids(bo.events_near(utc(2020, 3, 15, 21, 10), hour, hour)) == {"fomc-2020-03-15"}


def test_starts_between_gives_the_windows_that_cancel_entries(bo):
    got = bo.starts_between(utc(2026, 10, 14, 12, 0), utc(2026, 10, 14, 12, 15))
    assert [w.start for w in got] == [utc(2026, 10, 14, 12, 15)]
    assert bo.starts_between(utc(2026, 10, 14, 12, 15), utc(2026, 10, 14, 13, 0)) == []


@pytest.mark.parametrize(
    ("row", "match"),
    [
        (("x", "CPI", "BLS", "2026-10-14T08:30", "2026-10-14T13:30:00Z", "true"), "doesn't match"),
        (("x", "RUMOUR", "BLS", "2026-10-14T08:30", "2026-10-14T12:30:00Z", "true"), "event_type"),
        (
            ("x", "CPI", "BLS", "2026-10-14T08:30-04:00", "2026-10-14T12:30:00Z", "true"),
            "wall-clock",
        ),
        (("x", "CPI", "BLS", "2026-10-14T08:30", "2026-10-14T12:30:00Z", "yes"), "true or false"),
        (
            ("cpi-2026-10", "CPI", "BLS", "2026-10-14T08:30", "2026-10-14T12:30:00Z", "true"),
            "duplicate",
        ),
    ],
)
def test_bad_rows_are_rejected(tmp_path, row, match):
    with pytest.raises(NewsCalendarError, match=match):
        load_events(write(tmp_path, [ROWS[0], row]))


def test_columns_are_checked(tmp_path):
    with pytest.raises(NewsCalendarError, match="columns"):
        load_events(write(tmp_path, header=COLUMNS[:-1]))
