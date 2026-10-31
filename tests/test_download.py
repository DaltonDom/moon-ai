import json
from datetime import date
from pathlib import Path

import pytest

from moon_ai.data.download import (
    CostCapExceeded,
    Downloader,
    DownloadRequest,
    MissingApiKey,
    resolve_api_key,
)


class FakeStore:
    """Stands in for databento.DBNStore."""

    def __init__(self, symbol: str):
        self.symbol = symbol

    def to_parquet(self, path, **kwargs):
        Path(path).write_text(f"bars for {self.symbol}")


class FakeMetadata:
    def __init__(self, cost: float):
        self.cost = cost
        self.cost_requests: list[dict] = []

    def get_cost(self, **kwargs):
        self.cost_requests.append(kwargs)
        return self.cost


class FakeTimeseries:
    def __init__(self):
        self.requests: list[dict] = []

    def get_range(self, **kwargs):
        self.requests.append(kwargs)
        return FakeStore(kwargs["symbols"][0])


class FakeClient:
    def __init__(self, cost: float):
        self.metadata = FakeMetadata(cost)
        self.timeseries = FakeTimeseries()


REQUEST = DownloadRequest(
    symbols=("MNQ.v.0", "NQ.v.0"),
    start=date(2024, 1, 1),
    end=date(2024, 2, 1),
)


def test_dry_run_prices_the_request_and_downloads_nothing(tmp_path: Path):
    client = FakeClient(cost=1.25)
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    result = dl.download(REQUEST, dry_run=True)

    assert result.cost_usd == 1.25
    assert result.files == ()
    assert client.timeseries.requests == []
    assert client.metadata.cost_requests == [
        {
            "dataset": "GLBX.MDP3",
            "symbols": ["MNQ.v.0", "NQ.v.0"],
            "schema": "ohlcv-1m",
            "stype_in": "continuous",
            "start": "2024-01-01",
            "end": "2024-02-01",
        }
    ]


def test_refuses_to_download_above_the_cost_cap(tmp_path: Path):
    client = FakeClient(cost=20.0)
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    with pytest.raises(CostCapExceeded, match=r"20\.00.*15\.00"):
        dl.download(REQUEST)

    assert client.timeseries.requests == []


def test_explicit_confirmation_allows_a_download_above_the_cap(tmp_path: Path):
    client = FakeClient(cost=20.0)
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    dl.download(REQUEST, confirm=True)

    assert len(client.timeseries.requests) == 2


def test_download_writes_one_parquet_file_per_symbol_under_the_cap(tmp_path: Path):
    client = FakeClient(cost=1.25)
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    result = dl.download(REQUEST)

    expected = (
        tmp_path / "GLBX.MDP3/ohlcv-1m/MNQ.v.0/2024-01-01_2024-02-01.parquet",
        tmp_path / "GLBX.MDP3/ohlcv-1m/NQ.v.0/2024-01-01_2024-02-01.parquet",
    )
    assert result.files == expected
    assert expected[1].read_text() == "bars for NQ.v.0"
    assert [r["symbols"] for r in client.timeseries.requests] == [["MNQ.v.0"], ["NQ.v.0"]]
    assert all(r["stype_in"] == "continuous" for r in client.timeseries.requests)


def test_every_paid_symbol_is_appended_to_the_spend_ledger(tmp_path: Path):
    client = FakeClient(cost=1.25)
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    dl.download(REQUEST, dry_run=True)
    dl.download(REQUEST)

    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert [e["symbols"] for e in entries] == [["MNQ.v.0"], ["NQ.v.0"]]
    assert all(e["cost_usd"] == 1.25 for e in entries)
    assert all(e["start"] == "2024-01-01" and e["end"] == "2024-02-01" for e in entries)


def test_symbols_bought_before_a_failure_stay_in_the_ledger(tmp_path: Path):
    class FailsOnSecondSymbol(FakeTimeseries):
        def get_range(self, **kwargs):
            if kwargs["symbols"] == ["NQ.v.0"]:
                raise RuntimeError("402 account_insufficient_funds")
            return super().get_range(**kwargs)

    client = FakeClient(cost=1.25)
    client.timeseries = FailsOnSecondSymbol()
    dl = Downloader(client, store_root=tmp_path, max_cost_usd=15.0)

    with pytest.raises(RuntimeError, match="insufficient_funds"):
        dl.download(REQUEST)

    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert [json.loads(line)["symbols"] for line in lines] == [["MNQ.v.0"]]


def test_api_key_comes_from_the_environment_first(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABENTO_API_KEY=from-file\n")

    key = resolve_api_key({"DATABENTO_API_KEY": "from-env"}, env_file)

    assert key == "from-env"


def test_api_key_falls_back_to_the_dotenv_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text('# moon-ai secrets\nexport DATABENTO_API_KEY="db-abc123"\nOTHER=1\n')

    assert resolve_api_key({}, env_file) == "db-abc123"


def test_missing_api_key_explains_where_to_put_it(tmp_path: Path):
    with pytest.raises(MissingApiKey, match="DATABENTO_API_KEY"):
        resolve_api_key({}, tmp_path / "missing.env")
