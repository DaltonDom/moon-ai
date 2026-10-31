from pathlib import Path

import pytest

from moon_ai.cli import main
from tests.test_download import FakeClient

ARGS = ["download", "--symbols", "MNQ.v.0", "--start", "2024-01-01", "--end", "2024-02-01"]


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "db-test")


def test_dry_run_prints_the_cost_and_fetches_nothing(api_key, tmp_path: Path, capsys):
    client = FakeClient(cost=0.42)

    code = main([*ARGS, "--dry-run", "--store", str(tmp_path)], client_factory=lambda key: client)

    assert code == 0
    assert "$0.42" in capsys.readouterr().out
    assert client.timeseries.requests == []


def test_over_the_cap_exits_nonzero_without_downloading(api_key, tmp_path: Path, capsys):
    client = FakeClient(cost=99.0)

    code = main(
        [*ARGS, "--max-cost", "10", "--store", str(tmp_path)], client_factory=lambda key: client
    )

    assert code == 2
    assert "above the cap" in capsys.readouterr().err
    assert client.timeseries.requests == []


def test_confirm_flag_downloads_above_the_cap(api_key, tmp_path: Path):
    client = FakeClient(cost=99.0)

    code = main(
        [*ARGS, "--max-cost", "10", "--confirm", "--store", str(tmp_path)],
        client_factory=lambda key: client,
    )

    assert code == 0
    assert len(client.timeseries.requests) == 1


def test_missing_key_exits_nonzero(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.setattr("moon_ai.cli.DEFAULT_ENV_FILE", tmp_path / "none.env")

    code = main([*ARGS, "--dry-run"], client_factory=lambda key: FakeClient(0.0))

    assert code == 2
    assert "DATABENTO_API_KEY" in capsys.readouterr().err
