from datetime import date

from moon_ai.data.quality import degraded_sessions, fetch_degraded_dates, load_degraded_dates


def test_committed_list_has_databentos_degraded_days():
    dates = load_degraded_dates()
    assert len(dates) == 18
    assert {date(2020, 2, 27), date(2020, 2, 28), date(2020, 5, 5)} <= dates


def test_a_degraded_utc_date_skips_both_sessions_it_touches():
    # 2020-02-27 UTC overlaps the session closing that afternoon and the one opening that evening.
    assert degraded_sessions([date(2020, 2, 27)]) == {date(2020, 2, 27), date(2020, 2, 28)}


def test_fetch_keeps_only_non_available_dates():
    class Meta:
        def get_dataset_condition(self, **kw):
            assert kw == {
                "dataset": "GLBX.MDP3",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            }
            return [
                {"date": "2026-01-30", "condition": "available"},
                {"date": "2026-01-31", "condition": "degraded"},
                {"date": "2026-01-29", "condition": "pending"},
            ]

    class Client:
        metadata = Meta()

    got = fetch_degraded_dates(Client(), date(2026, 1, 1), date(2026, 1, 31))
    assert got == {date(2026, 1, 31), date(2026, 1, 29)}
