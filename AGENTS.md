# Case Tracker — AGENTS.md

Inherits `~/.hermes/PROJECT_RULES.md`. This file is the contract for the project; keep it current.

## What it is

Ben types a case order into one prompt on his iPhone — the **store number, then the number of
cases**, space-separated (`1234 5`) — and the order lands in the **`Case Tracker` tab** of the
**`Life` Google Sheet** (`LIFE_SID`), grouped by the day it was placed. Orders for one day sit in
one contiguous group; a blank **gutter row** separates one day's group from the next, and the
**date is written only on the top row of each group**.

Two halves, one folder each inside `~/0-Projects/1-scriptable/`:

| Piece | Path | Runs where |
|---|---|---|
| Phone body | `Case Tracker/Case Tracker.js` | Scriptable (JavaScriptCore) on the iPhone, fetched from the hub at run time |
| Backend | `Case Tracker/case-tracker/` (this project) | `hermes`, as `case-tracker.service` |

Placed under the `1-scriptable` container because the phone script *is* the client and the hub
serves it from there; `case-tracker/` is a project like any other (`~/srv/case-tracker`).

## Flow

1. The stub in the app (installed by the phone's New Script sync pass; `GET /scripts` on the hub
   lists `Case Tracker`) fetches the body.
2. One `Alert` with a single text field: the **store number first, then the cases**, space between.
   The script posts `{store, cases}` to `POST /log`.
3. `cases.write_case` opens a new day group (gutter + dated top row) when the day changes, or
   continues the current group (no date, no gutter) when it does not. The phone shows the day and
   today's running stores/cases count.

## Layout contract (Ben, 2026-11-04)

Tab `Case Tracker`: row 1 title, row 2 header `Date | Store | Cases`, data from row 3. Columns A–C.

```
Date        Store   Cases
2026-11-04  1234    5
            5678    3
            (blank gutter row)
2026-11-05  9012    4
```

- `RULE:` **date on the top row of a group only.** Continuation rows of the same day leave Date empty.
- `RULE:` **blank gutter row between day groups**, never between same-day rows.
- `RULE:` **store number is stored as TEXT** — a leading apostrophe keeps `01234` from being eaten to
  `1234` by `USER_ENTERED`. Cases are stored as a number.
- `TRAP:` the gutter row is fully blank, so `gsheet_sheet._band_last_row` / `cases._last_row` skip it —
  that is what makes the next append land at the bottom of the newest group. Never "helpfully" write a
  zero or a dash into the gutter: that makes it count as a data row and the next same-day append fills
  the wrong row.

## How to run it

```bash
python3 cases.py --init          # create the tab (title + headers) + house styling
python3 cases.py --log 1234 5    # store then cases (today)
python3 cases.py                 # show the groups + today's stats
python3 cases.py --selfcheck     # grouping contract on a throwaway zz_ tab, then deletes it
```

## Key files

- `cases.py` — the whole write path: grouping logic (`write_case`), the day read-back (`day_stats`),
  the house styling (`style_tab`), the CLI and the `--selfcheck`.
- `server.py` — tailnet-only HTTP endpoint (:8807), token auth, the lock around the sheet write.
  Transport only; all writes go through `cases.py` so the CLI and the phone cannot drift.
- `GATES.md` — the runnable ledger of what was proven.

## Live service and records

- `case-tracker.service` — `User=ubuntu`, `/usr/bin/python3 /home/ubuntu/srv/case-tracker/server.py`,
  tailnet-bound at `100.98.176.106:8807`, `Restart=always`.
- Token: `~/Hermes/shared/case-tracker-token.txt` (0600). The service refuses to start without it.
- Bot index: `case-tracker` (registered `--no-port --process-check`: the tailnet bind makes a
  `127.0.0.1` port probe fail for the right reason).
- **Store:** the `Life` Google Sheet's `Case Tracker` tab (spreadsheet id `LIFE_SID`).

## Standing rules for this project

- `RULE:` the store is a **Google Sheet**, written through `~/Hermes/shared/gsheet_sheet.py`.
  `gsheet_sheet.load(path)` ignores its path and always reads `LIFE_SID`, and `save()` is a no-op — so
  there is no throwaway copy. Isolate a test by **tab** (`CASES_TAB=zz_...`), never by file path.
- `RULE:` one field, not a form (Ben's standing preference). Do not split the prompt into two fields
  without asking.
- `RULE:` the phone does **not** retry `/log` — a hand-typed entry has no idempotency key.
- `TRAP:` if the write path's day-grouping logic changes, `--selfcheck` is the oracle. It writes a
  throwaway `zz_cases_selfcheck` tab and deletes it in a `finally`; never point it at the live tab.
- `TRAP:` the on-VM bare `python3` is Hermes's venv; the systemd unit runs `/usr/bin/python3`. Keep
  the endpoint stdlib-only so it does not matter.
