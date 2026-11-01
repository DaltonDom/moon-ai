import json
from datetime import date

from moon_ai.data.store import BarStore
from moon_ai.groundtruth import check, detect, import_verdicts, key
from moon_ai.groundtruth.page import build
from tests.test_backtest_runner import SETUP, WIN, session_rows
from tests.test_store import write

DAY = date(2026, 7, 15)


def store_with_setup(tmp_path):
    rows = session_rows(date(2026, 7, 14), {}) + session_rows(DAY, {**SETUP, **WIN})
    write(tmp_path / "bars", "MNQ.v.0", "2026-07-13_2026-07-16", rows)
    return BarStore(tmp_path / "bars")


def fixture(tmp_path, verdicts, missed=()):
    store = store_with_setup(tmp_path)
    export = {
        "setup": "ny_am_silver_bullet",
        "symbol": "MNQ.v.0",
        "days": {DAY.isoformat(): {"verdicts": verdicts, "missed": list(missed)}},
    }
    (tmp_path / "export.json").write_text(json.dumps(export))
    import_verdicts(tmp_path / "export.json", store, root=tmp_path / "gt")
    return tmp_path / "gt"


FOUND = "2026-07-15T10:07:long"


def test_detection_key(tmp_path):
    (c,), _ = detect("ny_am_silver_bullet", store_with_setup(tmp_path), DAY)
    assert key(c) == FOUND


def test_agreed_detections_pass(tmp_path):
    assert check("ny_am_silver_bullet", fixture(tmp_path, {FOUND: "agree"})) == []
    assert check("ny_am_silver_bullet", fixture(tmp_path / "u", {FOUND: "unsure"})) == []


def test_both_directions_are_checked(tmp_path):
    rejected = check("ny_am_silver_bullet", fixture(tmp_path / "a", {FOUND: "disagree"}))
    assert ["rejected" in p.message for p in rejected] == [True]
    unreviewed = check("ny_am_silver_bullet", fixture(tmp_path / "b", {}))
    assert "wasn't reviewed" in unreviewed[0].message
    vanished = check(
        "ny_am_silver_bullet",
        fixture(tmp_path / "c", {FOUND: "agree", "2026-07-15T10:40:short": "agree"}),
    )
    assert "no longer detects 2026-07-15T10:40:short" in vanished[0].message
    missed = check(
        "ny_am_silver_bullet",
        fixture(tmp_path / "d", {FOUND: "agree"}, [{"t": "2026-07-15T10:30", "side": "short"}]),
    )
    assert "misses the setup the review added at 2026-07-15T10:30" in missed[0].message
    near = check(
        "ny_am_silver_bullet",
        fixture(tmp_path / "e", {FOUND: "agree"}, [{"t": "2026-07-15T10:09", "side": "long"}]),
    )
    assert near == []  # within 5 minutes of the detection


def test_review_page_embeds_the_days_and_an_export_template(tmp_path):
    page = build("ny_am_silver_bullet", [DAY], store_with_setup(tmp_path))
    assert "NY AM Silver Bullet: does the bot see what you see?" in page
    assert FOUND in page and "Export my verdicts" in page
