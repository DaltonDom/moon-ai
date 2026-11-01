"""The dashboard's API (FastAPI), served at http://localhost:8000.

Read-only views for the six pages, plus two actions: queue a backtest, and
approve or reject a proposal.

Safety, since anything on the Mac (including a web page in the browser) can
reach localhost:
- It binds to 127.0.0.1 only (`moon-ai dashboard`).
- It answers only `Host: localhost` / `127.0.0.1`, which blocks DNS rebinding.
- Every write needs an `X-Moon-AI: 1` header. A web page on another site can't
  send a custom header without a CORS preflight, which this app never allows.
"""

import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from moon_ai.config import Config, load_config
from moon_ai.dashboard import data
from moon_ai.dashboard.jobs import JobQueue
from moon_ai.dashboard.proposals import GitHub, NoGitHub, RestGitHub, approve, reject, summarize
from moon_ai.nightly.job import Paths

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
WRITE_HEADER = "X-Moon-AI"


class BacktestRequest(BaseModel):
    setup: str
    start: date | None = None
    end: date | None = None
    trial: str | None = None


def create_app(
    paths: Paths | None = None,
    config: Config | None = None,
    runs_root: Path | None = None,
    reports_root: Path = Path("reports"),
    github: Callable[[], GitHub] = RestGitHub,
    jobs: JobQueue | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    static_dir: Path | None = None,
    run_worker: bool = False,
) -> FastAPI:
    paths = paths or Paths()
    config = config or load_config()
    runs_root = runs_root or paths.root / "runs"
    queue = jobs or JobQueue(paths.root / "jobs")
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = None
        if run_worker:
            worker = threading.Thread(target=queue.worker, args=(stop,), daemon=True)
            worker.start()
        yield
        stop.set()

    app = FastAPI(title="moon-ai dashboard", lifespan=lifespan, docs_url="/api/docs")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    def journal() -> data.Journal:
        return data.Journal.load(paths.journal)

    def writer(x_moon_ai: str | None = Header(default=None)) -> None:
        if x_moon_ai != "1":
            raise HTTPException(403, f"writes need the {WRITE_HEADER}: 1 header")

    def gh() -> GitHub:
        try:
            return github()
        except NoGitHub as exc:
            raise HTTPException(503, str(exc)) from exc

    J = Annotated[data.Journal, Depends(journal)]
    G = Annotated[GitHub, Depends(gh)]

    def open_proposals() -> int:
        try:
            return sum(summarize(i)["needs_you"] for i in github().proposals())
        except Exception:  # no token or GitHub down: Today still loads
            return 0

    # --- read-only views -----------------------------------------------------------

    @app.get("/api/health")
    def health(j: J) -> dict[str, Any]:
        return data.health(paths, j, now())

    @app.get("/api/today")
    def today(j: J) -> dict[str, Any]:
        return data.today(j, config, now(), proposals=open_proposals())

    @app.get("/api/setups")
    def setups(j: J) -> list[dict[str, Any]]:
        out = data.setups(j, config, runs_root)
        for s in out:
            w = config.sessions.windows.get(s["window"])
            s["window_ny"] = f"{w.start:%H:%M}-{w.end:%H:%M}" if w else s["window"]
        return out

    @app.get("/api/models")
    def models(j: J) -> dict[str, Any]:
        return data.models(j)

    @app.get("/api/trades")
    def trades(
        j: J,
        filter: str = Query("all"),
        setup: str | None = None,
        bucket: str | None = None,
        limit: int = Query(200, ge=1, le=2000),
    ) -> list[dict[str, Any]]:
        try:
            return data.trades(j, filter, setup, bucket, limit)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/trades/{candidate_id:path}/chart")
    def chart(candidate_id: str, j: J) -> FileResponse:
        t = next((t for t in j.trades if t["candidate_id"] == candidate_id), None)
        if t is None or not t["chart_path"]:
            raise HTTPException(404, "no chart for this trade")
        path = Path(t["chart_path"])
        path = path if path.is_absolute() else paths.root.parent / path
        charts = (paths.root / "charts").resolve()
        if not path.resolve().is_relative_to(charts) or not path.exists():
            raise HTTPException(404, "no chart for this trade")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/trades/{candidate_id:path}")
    def trade(candidate_id: str, j: J) -> dict[str, Any]:
        d = data.trade_detail(j, candidate_id)
        if d is None:
            raise HTTPException(404, "no such paper trade")
        return d

    @app.get("/api/weekly")
    def weekly() -> list[dict[str, str]]:
        return data.weekly_list(reports_root)

    @app.get("/api/weekly/{week}", response_class=PlainTextResponse)
    def weekly_one(week: str) -> str:
        text = data.weekly_report(reports_root, week)
        if text is None:
            raise HTTPException(404, "no report for that week")
        return text

    @app.get("/api/nightly")
    def nightly(j: J) -> list[dict[str, Any]]:
        return data.nightly_runs(j.events)[:14]

    @app.get("/api/proposals")
    def proposals(g: G) -> list[dict[str, Any]]:
        return [summarize(i) for i in g.proposals()]

    @app.get("/api/backtests")
    def backtests() -> list[dict[str, Any]]:
        return [JobQueue.as_dict(j) for j in queue.list()[:50]]

    @app.get("/api/backtests/{job_id}/log", response_class=PlainTextResponse)
    def backtest_log(job_id: str) -> str:
        text = queue.log(job_id)
        if text is None:
            raise HTTPException(404, "no log for that job")
        return text

    # --- actions -------------------------------------------------------------------

    @app.post("/api/backtests", status_code=202, dependencies=[Depends(writer)])
    def queue_backtest(req: BacktestRequest) -> dict[str, Any]:
        start, end = req.start, req.end
        if start is None or end is None:
            window = data.last_protocol_window(runs_root)
            if window is None:
                raise HTTPException(
                    422, "give start and end dates; no `backtest --all` run to copy them from"
                )
            start, end = start or window[0], end or window[1]
        try:
            job = queue.submit(req.setup, start, end, req.trial)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JobQueue.as_dict(job)

    @app.post("/api/proposals/{number}/{action}", dependencies=[Depends(writer)])
    def act(number: int, action: str, g: G) -> dict[str, Any]:
        if action not in ("approve", "reject"):
            raise HTTPException(404, "use approve or reject")
        issue = next((i for i in g.proposals() if i["number"] == number), None)
        if issue is None:
            raise HTTPException(404, f"#{number} isn't a proposal")
        try:
            new = approve(g, issue) if action == "approve" else reject(g, issue)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"number": number, "stage": new}

    if static_dir and static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return app
