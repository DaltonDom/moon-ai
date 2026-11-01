from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.silver_bullet import NyPmSilverBullet
from tests.test_setup_silver_bullet import ny, scan_all

PM = load_setup_defaults()["ny_pm_silver_bullet"].params

# Lunch range low 97 is swept at 14:04, then the same displacement pattern as the AM test.
PM_BARS = {
    (12, 30): (100.0, 100.25, 97.0, 100.0),  # lunch low: the pool to sweep
    (10, 30): (100.0, 112.0, 99.75, 100.0),  # AM-session high: the draw on liquidity
    (14, 1): (100.0, 100.25, 99.75, 100.0),
    (14, 2): (100.0, 100.75, 99.75, 100.25),
    (14, 3): (100.25, 100.5, 98.5, 98.75),
    (14, 4): (98.75, 99.0, 96.5, 98.0),
    (14, 5): (98.0, 100.0, 97.75, 99.75),
    (14, 6): (99.75, 102.0, 99.5, 101.75),
    (14, 7): (101.75, 102.25, 100.5, 102.0),
}


def pm_day(special):
    from tests.test_setup_silver_bullet import day

    return day(special, end=(14, 30), overnight_high=100.25)


def test_a_textbook_pm_silver_bullet():
    (c,) = scan_all(pm_day(PM_BARS), PM, cls=NyPmSilverBullet)
    assert c.setup == "ny_pm_silver_bullet" and c.side == "long"
    assert c.decision_time == ny(14, 7)
    assert (c.entry, c.stop, c.target) == (99.5, 96.25, 112.0)
    assert c.rule_results["swept_pool"] == "lunch"
    assert c.entry_deadline == ny(15, 0)
    assert REGISTRY["ny_pm_silver_bullet"] is NyPmSilverBullet


def test_the_am_window_does_not_trigger_the_pm_setup():
    shifted = {(h - 4, m) if h == 14 else (h, m): b for (h, m), b in PM_BARS.items()}
    assert scan_all(pm_day(shifted), PM, cls=NyPmSilverBullet) == []
