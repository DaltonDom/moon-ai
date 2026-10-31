"""Cost-guarded Databento downloader.

Every request is priced first with the free `metadata.get_cost` call, using
exactly the parameters of the data request. Anything above `max_cost_usd` is
refused unless the caller explicitly confirms. Each paid download is appended
to `<store_root>/ledger.jsonl`.

Bars land as raw Parquet, one file per symbol:
`<store_root>/<dataset>/<schema>/<symbol>/<start>_<end>.parquet`. `ts_event`
in those files is the bar's *open*; the bar loader shifts it to the close.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

DEFAULT_ENV_FILE = Path.home() / ".config" / "moon-ai" / ".env"
API_KEY_VAR = "DATABENTO_API_KEY"


class CostCapExceeded(RuntimeError):
    """The request's estimated cost is above the configured cap."""


class MissingApiKey(RuntimeError):
    """No Databento API key in the environment or the .env file."""


class _Metadata(Protocol):
    def get_cost(self, **kwargs: Any) -> float: ...


class _Timeseries(Protocol):
    def get_range(self, **kwargs: Any) -> Any: ...


class HistoricalClient(Protocol):
    """The slice of `databento.Historical` the downloader uses."""

    metadata: _Metadata
    timeseries: _Timeseries


@dataclass(frozen=True)
class DownloadRequest:
    symbols: tuple[str, ...]
    start: date
    end: date  # exclusive
    dataset: str = "GLBX.MDP3"
    schema: str = "ohlcv-1m"
    stype_in: str = "continuous"

    def params(self, symbols: tuple[str, ...] | None = None) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "symbols": list(symbols if symbols is not None else self.symbols),
            "schema": self.schema,
            "stype_in": self.stype_in,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


@dataclass(frozen=True)
class DownloadResult:
    cost_usd: float
    files: tuple[Path, ...]


class Downloader:
    def __init__(self, client: HistoricalClient, store_root: Path, max_cost_usd: float):
        self._client = client
        self._root = Path(store_root)
        self._cap = max_cost_usd

    def estimate(self, request: DownloadRequest) -> float:
        """Free cost estimate in USD for the whole request."""
        return float(self._client.metadata.get_cost(**request.params()))

    def download(
        self, request: DownloadRequest, *, confirm: bool = False, dry_run: bool = False
    ) -> DownloadResult:
        """Price the request, then (unless `dry_run`) fetch and store it.

        Raises CostCapExceeded if the estimate is above the cap and `confirm`
        is False. Nothing is fetched in that case.
        """
        cost = self.estimate(request)
        if dry_run:
            return DownloadResult(cost_usd=cost, files=())
        if cost > self._cap and not confirm:
            raise CostCapExceeded(
                f"estimated cost ${cost:.2f} is above the cap ${self._cap:.2f}; "
                "re-run with explicit confirmation to proceed"
            )

        files = []
        for symbol in request.symbols:
            store = self._client.timeseries.get_range(**request.params((symbol,)))
            path = self._path_for(request, symbol)
            path.parent.mkdir(parents=True, exist_ok=True)
            store.to_parquet(path, price_type="float", map_symbols=True)
            files.append(path)

        self._record_spend(request, cost)
        return DownloadResult(cost_usd=cost, files=tuple(files))

    def _path_for(self, request: DownloadRequest, symbol: str) -> Path:
        name = f"{request.start.isoformat()}_{request.end.isoformat()}.parquet"
        return self._root / request.dataset / request.schema / symbol / name

    def _record_spend(self, request: DownloadRequest, cost: float) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        entry = {"at": datetime.now(UTC).isoformat(), "cost_usd": cost, **request.params()}
        with (self._root / "ledger.jsonl").open("a") as fh:
            fh.write(json.dumps(entry) + "\n")


def resolve_api_key(
    environ: Mapping[str, str] | None = None, env_file: Path = DEFAULT_ENV_FILE
) -> str:
    """DATABENTO_API_KEY from the environment, else from `env_file`."""
    environ = os.environ if environ is None else environ
    if environ.get(API_KEY_VAR):
        return environ[API_KEY_VAR]
    value = _read_dotenv(env_file).get(API_KEY_VAR)
    if value:
        return value
    raise MissingApiKey(
        f"set {API_KEY_VAR} in the environment or in {env_file} "
        f"(a line like {API_KEY_VAR}=db-...); never commit it"
    )


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def databento_client(api_key: str) -> HistoricalClient:
    """The real client. Imported lazily so tests never need the package or a key."""
    import databento

    return databento.Historical(api_key)
