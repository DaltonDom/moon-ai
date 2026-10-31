# PROTOTYPE: ground-truth review page (ticket #11), throwaway

Answers: how does the user check ~50 days of detections against their own ICT reading?
Not production code; lives only on this branch, never merged.

```bash
uv run moon-ai download --symbols MNQ.v.0 --start 2026-10-25 --end 2026-10-31 --store /tmp/bars
cd prototypes/ground_truth_review
uv run python build.py /tmp/bars/GLBX.MDP3/ohlcv-1m/MNQ.v.0/2026-10-25_2026-10-31.parquet 2026-10-27 2026-10-28 2026-10-29
open review.html
```

`review.html` embeds Databento bars, so it is git-ignored.
