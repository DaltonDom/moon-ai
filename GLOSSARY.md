# moon-ai

An autonomous ICT trading bot for CME micro futures: fixed ICT rules propose trades, and an ML filter decides which ones to take.

## Language

### Candidates and labels

**Candidate**:
One trade proposed by a setup's rules, with a planned entry, stop and target, whether or not it is ever taken.
_Avoid_: signal, opportunity

**Decision time**:
The close of the bar that completes a setup and places the candidate's order. Everything the ML filter sees is frozen at this moment.
_Avoid_: entry time, fill time, signal time

**Time-out**:
A setup's latest exit time. A candidate still open then is closed at market. It is the third barrier, after the stop and the target.
_Avoid_: vertical barrier, session end

**Label**:
1 if a candidate's target is hit before its stop and its time-out, otherwise 0. It is judged as if the candidate were taken on its own.
_Avoid_: outcome, result, win

**Unfilled candidate**:
A candidate whose limit entry is never reached. It has no label.
_Avoid_: missed trade

**Feature vector**:
The candidate's facts as known at its decision time, from which the ML filter predicts the label.
_Avoid_: signal context, snapshot

### Learning

**ML filter**:
The single model, pooled across all go-forward setups, that decides take or skip for each candidate.
_Avoid_: meta-model, classifier, the AI
