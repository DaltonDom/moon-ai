"""Claude trade reviews (docs/design.md, "Claude trade review").

Each night, after the paper replay:

1. **Collect** last night's batch. A valid answer is stored as `done`. A
   refusal, an API error or an answer that fails validation counts as one
   attempt: the trade goes back to `pending`, and after 3 attempts it is
   `failed`.
2. **Submit** every closed trade that needs a review as one Message Batch
   (half price), each with its journal entry, the setup's pinned rules and
   its chart.

Rules the code keeps, whatever Claude says:

- `code_flags` are computed here and copied into the review. A trade with any
  flag is bucket `rule_break`, checked first.
- Reasons may cite only features in the journal entry or the setup's rules.
- Every billed answer is logged as a `claude_spend` event. The month's total
  is held under a hard $10 cap: when the next batch might cross it, nothing
  more is sent, and the user is alerted.

Reviews are commentary: nothing here feeds trading, labels or the model.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from moon_ai.config import Config
from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.setups import load_setup_defaults

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "review-v1"
MAX_ATTEMPTS = 3
MONTHLY_CAP_USD = 10.0
# Opus 5.5 per 1M tokens, halved by the Batches API.
BATCH_PRICE = {"input": 4.0 / 2, "output": 20.0 / 2, "cache_read": 0.20 / 2, "cache_write": 5.0 / 2}
EST_COST_USD = 0.08  # a conservative per-review estimate, for the cap check before sending
BUCKETS = ("rule_break", "good_won", "good_lost", "bad_won", "bad_lost")
FIELDS = (
    "bucket",
    "summary",
    "reasons",
    "setup_quality",
    "confidence",
    "execution_notes",
    "follow_up",
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bucket": {"type": "string", "enum": list(BUCKETS)},
        "summary": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "setup_quality": {"type": "string", "enum": ["good", "bad"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "execution_notes": {"type": "string"},
        "follow_up": {"type": "string"},
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}

SYSTEM = """You review one paper trade taken by an automated ICT trading bot on MNQ futures.

You get the trade's journal entry (the plan, fills, the code's rule checks, the model's
probability, the feature vector, MAE/MFE, R and exit reason), the setup's pinned rules,
the code's flags, and a chart of the setup window and the trade.

Pick exactly one bucket:
- rule_break: rule break or execution error. Required whenever code_flags is non-empty.
- good_won: good setup, won.
- good_lost: good setup, unlucky loss.
- bad_won: bad setup, lucky win.
- bad_lost: bad setup, lost; the filter should have rejected it.

"Good" or "bad" means whether the trade matched the setup's rules in spirit, not the outcome.

Write:
- summary: 2-3 plain-English sentences a non-trader can follow.
- reasons: each cites a feature by name and value exactly as in the journal entry
  (e.g. "sweep_depth_ticks = 3") or a rule by its name in the setup rules. Cite nothing else.
- setup_quality and your confidence in it.
- execution_notes: fills or slippage worth noting, or an empty string.
- follow_up: one idea worth testing, or an empty string.

Your review is commentary for the user. It never changes the rules or the model."""


# --- code flags ----------------------------------------------------------------------


def code_flags(
    cand: dict[str, Any],
    orders: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    events: list[dict[str, Any]],
    config: Config,
) -> list[str]:
    """The deterministic checks Claude can't override."""
    flags = []
    b = config.broker
    allowed = {
        "entry": max(
            b.entry_slippage_ticks, b.london_entry_slippage_ticks, b.london_large_slippage_ticks
        ),
        "stop": max(
            b.stop_slippage_ticks, b.london_stop_slippage_ticks, b.london_large_slippage_ticks
        ),
    }
    for f in fills:
        limit = allowed.get(f["reason"], 0) * b.slippage_multiplier
        if (f["slippage_ticks"] or 0) > limit + 1e-9:
            flags.append(
                f"{f['reason']} fill slipped {f['slippage_ticks']:g} ticks "
                f"(assumed at most {limit:g})"
            )
    failed = [k for k, v in (cand["rule_results"] or {}).items() if v is False]
    if failed:
        flags.append("failed rule check: " + ", ".join(sorted(failed)))
    entry = [o for o in orders if o["candidate_id"] == cand["candidate_id"]]
    if entry and any(o["stop"] is None or o["target"] is None for o in entry):
        flags.append("entry order sent without a broker-side stop or target")
    if any(
        e["step"] == "order_rejected"
        and (e["data"] or {}).get("candidate_id") == cand["candidate_id"]
        for e in events
    ):
        flags.append("an order was rejected")
    return flags


# --- validation ----------------------------------------------------------------------


class InvalidReview(ValueError):
    pass


_CITE = re.compile(r"\b([a-z][a-z0-9_]*)\s*=")


def validate(raw: str, flags: list[str], citable: set[str]) -> dict[str, Any]:
    """Parse and check one answer. Raises InvalidReview; never stores a bad one."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidReview(f"not JSON: {exc}") from exc
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise InvalidReview("wrong fields")
    if data["bucket"] not in BUCKETS:
        raise InvalidReview(f"unknown bucket {data['bucket']!r}")
    if flags and data["bucket"] != "rule_break":
        raise InvalidReview("code flags are set, so the bucket must be rule_break")
    if data["setup_quality"] not in ("good", "bad") or data["confidence"] not in (
        "low",
        "medium",
        "high",
    ):
        raise InvalidReview("bad setup_quality or confidence")
    if not isinstance(data["summary"], str) or not data["summary"].strip():
        raise InvalidReview("empty summary")
    if not isinstance(data["reasons"], list) or not data["reasons"]:
        raise InvalidReview("no reasons")
    for r in data["reasons"]:
        if not isinstance(r, str):
            raise InvalidReview("a reason isn't text")
        named = set(_CITE.findall(r))
        unknown = named - citable
        if unknown:
            raise InvalidReview(f"cites names not in the journal entry: {sorted(unknown)}")
        if not named and not any(re.search(rf"\b{re.escape(c)}\b", r) for c in citable):
            raise InvalidReview(f"reason cites no feature or rule: {r!r}")
    return {**data, "code_flags": flags}


# --- cost ----------------------------------------------------------------------------


def cost_usd(usage: Any) -> float:
    g = lambda k: getattr(usage, k, 0) or 0  # noqa: E731
    return (
        g("input_tokens") * BATCH_PRICE["input"]
        + g("output_tokens") * BATCH_PRICE["output"]
        + g("cache_read_input_tokens") * BATCH_PRICE["cache_read"]
        + g("cache_creation_input_tokens") * BATCH_PRICE["cache_write"]
    ) / 1e6


def month_spend(events: list[dict[str, Any]], now: datetime) -> float:
    return sum(
        (e["data"] or {}).get("cost_usd", 0.0)
        for e in events
        if e["step"] == "claude_spend" and e["ts"].year == now.year and e["ts"].month == now.month
    )


# --- the nightly step ----------------------------------------------------------------


@dataclass
class ReviewResult:
    submitted: int = 0
    done: int = 0
    retry: int = 0
    failed: int = 0
    in_flight: int = 0
    cost_usd: float = 0.0
    capped: bool = False
    notes: list[str] = field(default_factory=list)

    def message(self) -> str:
        parts = [f"{self.done} review(s) back", f"{self.submitted} sent"]
        if self.retry:
            parts.append(f"{self.retry} to retry")
        if self.failed:
            parts.append(f"{self.failed} failed for good")
        if self.in_flight:
            parts.append(f"{self.in_flight} still with Claude")
        if self.capped:
            parts.append(
                f"the ${MONTHLY_CAP_USD:.0f} monthly cap is reached, so reviews are paused"
            )
        return ", ".join(parts) + f" (${self.cost_usd:.2f})."


class Reviewer:
    def __init__(
        self,
        db: SQLiteStore,
        run_id: str,
        config: Config,
        client: Any,
        charts: Path,
        bars_for: Callable[[dict[str, Any], dict[str, Any]], list] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        cap_usd: float = MONTHLY_CAP_USD,
    ):
        self.db, self.run_id, self.config, self.client = db, run_id, config, client
        self.charts, self.bars_for, self.now, self.cap = charts, bars_for, now, cap_usd

    # tables
    def _rows(self, table: str) -> list[dict[str, Any]]:
        return decode_json(self.db.read(table, self.run_id), table)

    def run(self) -> ReviewResult:
        res = ReviewResult()
        self.collect(res)
        self.submit(res)
        return res

    # 1. collect
    def collect(self, res: ReviewResult) -> None:
        reviews = [r for r in self._rows("reviews") if r["status"] == "submitted"]
        batches = sorted({r["fields"]["batch_id"] for r in reviews})
        for batch_id in batches:
            if self.client.messages.batches.retrieve(batch_id).processing_status != "ended":
                res.in_flight += sum(r["fields"]["batch_id"] == batch_id for r in reviews)
                continue
            mine = {r["candidate_id"]: r for r in reviews if r["fields"]["batch_id"] == batch_id}
            ids = {self._custom_id(c): c for c in mine}
            seen = set()
            for item in self.client.messages.batches.results(batch_id):
                cid = ids.get(item.custom_id)
                if cid is None:
                    continue
                seen.add(cid)
                self._apply(cid, mine[cid], item.result, res)
            for cid in set(mine) - seen:  # missing from the results: try again
                self._attempt_failed(cid, mine[cid], "missing from the batch results", res)

    def _apply(self, cid: str, row: dict[str, Any], result: Any, res: ReviewResult) -> None:
        if result.type != "succeeded":
            self._attempt_failed(cid, row, f"batch request {result.type}", res)
            return
        msg = result.message
        cost = cost_usd(msg.usage)
        self._spend(cost, cid)
        res.cost_usd += cost
        if msg.stop_reason == "refusal":
            cat = getattr(getattr(msg, "stop_details", None), "category", None)
            self._attempt_failed(cid, row, f"Claude declined ({cat or 'no category'})", res)
            return
        if msg.stop_reason != "end_turn":
            self._attempt_failed(cid, row, f"stopped early ({msg.stop_reason})", res)
            return
        text = next((b.text for b in msg.content if b.type == "text"), "")
        flags, citable = row["fields"]["code_flags"], set(row["fields"]["citable"])
        try:
            fields = validate(text, flags, citable)
        except InvalidReview as exc:
            self._attempt_failed(cid, row, f"invalid answer: {exc}", res)
            return
        self.db.set_review(
            cid,
            status="done",
            bucket=fields["bucket"],
            fields={**fields, "prompt_version": PROMPT_VERSION},
            model=msg.model,
            cost_usd=cost,
            updated_at=self.now(),
        )
        res.done += 1

    def _attempt_failed(self, cid: str, row: dict[str, Any], why: str, res: ReviewResult) -> None:
        attempts = (row["attempts"] or 0) + 1
        final = attempts >= MAX_ATTEMPTS
        self.db.set_review(
            cid,
            status="failed" if final else "pending",
            attempts=attempts,
            fields={"last_error": why},
            updated_at=self.now(),
        )
        if final:
            res.failed += 1
        else:
            res.retry += 1
        res.notes.append(f"{cid}: {why}")

    def _spend(self, usd: float, cid: str) -> None:
        now = self.now()
        self.db.insert(
            "events",
            {
                "event_id": f"spend:{cid}:{now.isoformat()}:{uuid.uuid4().hex[:6]}",
                "run_id": self.run_id,
                "ts": now,
                "step": "claude_spend",
                "status": "info",
                "message": f"${usd:.4f} for the review of {cid}",
                "data": {"cost_usd": usd, "candidate_id": cid},
            },
        )

    # 2. submit
    def due(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        reviews = {r["candidate_id"]: r for r in self._rows("reviews")}
        cands = {c["candidate_id"]: c for c in self._rows("candidates")}
        out = []
        for t in self._rows("trades"):
            if t["exit_time"] is None or t["candidate_id"] not in cands:
                continue
            rv = reviews.get(t["candidate_id"])
            if rv is None or rv["status"] == "pending":
                out.append((cands[t["candidate_id"]], t))
        return sorted(out, key=lambda ct: ct[1]["exit_time"])

    def submit(self, res: ReviewResult) -> None:
        due = self.due()
        if not due:
            return
        spent = month_spend(self._rows("events"), self.now())
        room = int((self.cap - spent) // EST_COST_USD)
        if room < len(due):
            res.capped = True
        due = due[: max(room, 0)]
        if not due:
            return
        orders, fills, events = self._rows("orders"), self._rows("fills"), self._rows("events")
        defaults = load_setup_defaults()
        requests, meta = [], {}
        for cand, trade in due:
            cid = cand["candidate_id"]
            flags = code_flags(
                cand,
                orders,
                [f for f in fills if f["candidate_id"] == cid],
                events,
                self.config,
            )
            rules = defaults[cand["setup"]].params if cand["setup"] in defaults else None
            rule_dict = {k: _plain(v) for k, v in vars(rules).items()} if rules else {}
            citable = set(cand["features"] or {}) | set(rule_dict) | set(cand["rule_results"] or {})
            citable |= {"mae_r", "mfe_r", "r", "ml_p", "ml_threshold", "exit_reason"}
            chart = self._chart(cand, trade)
            requests.append(self._request(cid, cand, trade, flags, rule_dict, chart))
            meta[cid] = {"code_flags": flags, "citable": sorted(citable)}
        batch = self.client.messages.batches.create(requests=requests)
        for cid, m in meta.items():
            prior = next((r for r in self._rows("reviews") if r["candidate_id"] == cid), None)
            first = {"run_id": self.run_id} if prior is None else {}
            self.db.set_review(
                cid,
                **first,
                status="submitted",
                attempts=(prior or {}).get("attempts") or 0,
                fields={**m, "batch_id": batch.id},
                model=MODEL,
                updated_at=self.now(),
            )
        res.submitted = len(requests)

    def _chart(self, cand: dict[str, Any], trade: dict[str, Any]) -> Path | None:
        if trade["chart_path"]:
            p = Path(trade["chart_path"])
            if p.exists():
                return p
        if self.bars_for is None:
            return None
        from moon_ai.review.charts import render

        path = render(cand, trade, self.bars_for(cand, trade), self.charts)
        self.db.close_trade(cand["candidate_id"], chart_path=str(path))
        return path

    @staticmethod
    def _custom_id(cid: str) -> str:
        # custom_id allows only [a-zA-Z0-9_-]{1,64}: a stable short hash of the id.
        import hashlib

        return "t" + hashlib.sha256(cid.encode()).hexdigest()[:40]

    def _request(
        self,
        cid: str,
        cand: dict[str, Any],
        trade: dict[str, Any],
        flags: list[str],
        rules: dict[str, Any],
        chart: Path | None,
    ) -> dict[str, Any]:
        entry = {
            "plan": {
                k: cand[k] for k in ("setup", "side", "entry_type", "entry", "stop", "target")
            },
            "decision_time": cand["decision_time"].isoformat(),
            "rule_checks": cand["rule_results"],
            "ml_p": cand["ml_p"],
            "ml_threshold": cand["ml_threshold"],
            "features": cand["features"],
            "result": {
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in trade.items()
                if k not in ("run_id", "chart_path", "candidate_id")
            },
        }
        content: list[dict[str, Any]] = []
        if chart is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.standard_b64encode(chart.read_bytes()).decode(),
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": "Journal entry:\n"
                + json.dumps(entry, sort_keys=True, default=str)
                + "\n\nSetup rules (config/defaults.toml):\n"
                + json.dumps(rules, sort_keys=True, default=str)
                + "\n\ncode_flags (read-only): "
                + json.dumps(flags),
            }
        )
        return {
            "custom_id": self._custom_id(cid),
            "params": {
                "model": MODEL,
                "max_tokens": 16000,
                "system": SYSTEM,
                "output_config": {
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
                "messages": [{"role": "user", "content": content}],
            },
        }


def _plain(v: Any) -> Any:
    if isinstance(v, str | int | float | bool | type(None)):
        return v
    if isinstance(v, list | tuple):
        return [_plain(x) for x in v]
    return str(v)
