# Case Tracker — GATES.md

Runnable ledger. Every gate is checked by a command whose observed output is the evidence.

## G1 — grouping, gutter row, date-once
- CHECK: `python3 cases.py --selfcheck`
- EXPECT: `selfcheck OK`
- EVIDENCE: `selfcheck OK — grouping, gutter row and date-once all hold` (2026-11-04)

## G2 — tab exists with title + headers + house styling
- CHECK: `python3 cases.py --init` then `python3 cases.py`
- EXPECT: row 1 `Case Tracker`, row 2 `Date | Store | Cases`
- EVIDENCE: `tab 'Case Tracker' ready (columns Date, Store, Cases)`; grid read row1 `Case Tracker`,
  row2 `Date | Store | Cases` (2026-11-04)

## G3 — endpoint logs against the tab (throwaway-tab isolated)
- CHECK: `python3 tests/gate-live.py`
- EXPECT: `{"ok":true,...}`, rows land in `zz_case_gate`, live tab untouched
- EVIDENCE: `gate OK — G3/G4 hold; throwaway rows: ['2026-11-04', '01234', '5'] ['', '5678', '3']
  (live tab untouched)` (2026-11-04). Leading zero survived -> store stored as TEXT.

## G4 — auth and bad input change nothing
- CHECK: bad token -> 401; empty store -> 400 (both inside `tests/gate-live.py`)
- EXPECT: no row written either time
- EVIDENCE: 401 and 400 asserted; throwaway tab read back held exactly 2 rows (2026-11-04)

## G5 — phone script parses and holds no secret
- CHECK: `node --check "Case Tracker.js"` + token scan
- EXPECT: parses; no token-like string in the file
- EVIDENCE: `node --check` clean; `no token in file` (2026-11-04)

## G6 — hub serves the body, index registered
- CHECK: `curl -s "http://100.98.176.106:8802/scripts"`; `curl -s ".../script?name=Case%20Tracker"`
- EXPECT: `Case Tracker` listed; body served
- EVIDENCE: listed in `/scripts`; body head returned (2026-11-04). `case-tracker` bot-index entry
  written with `process_check` (2026-11-04).
