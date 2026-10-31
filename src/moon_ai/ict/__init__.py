"""ICT primitives: pure functions over one symbol's closed bars, oldest first.

Every output carries `known_at`, the moment it became knowable. Computing a
primitive on `bars[:t]` gives exactly the outputs of the full series whose
`known_at` is at or before `bars[t-1].ts_close` (tests/test_ict_lookahead.py).
No primitive spans a contract roll (an `instrument_id` change).
"""
