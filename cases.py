#!/usr/bin/env python3
"""Log a case order into the 'Case Tracker' tab of the Life Google Sheet.

  cases.py --log 1234 5      # store number, then cases
  cases.py --init            # create the tab (title + headers) if absent
  cases.py                   # show the day groups
  cases.py --selfcheck       # throwaway-tab self-test (creates + deletes a zz_ tab)

Layout contract (Ben, 2026-11-04): one row per store, columns
Date | Store | Cases, grouped by the day the order was placed. A blank GUTTER ROW
separates one day's group from the next, and the date is written ONLY on the top
row of each group -- continuation rows of the same day leave Date empty.

So a two-day log reads:

    Date        Store   Cases
    2026-11-04  1234    5
                5678    3
                (blank gutter row)
    2026-11-05  9012    4

Writes go through ~/Hermes/shared/gsheet_sheet.py into the 'Life' workbook.
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Hermes" / "shared"))
import gsheet_sheet as xs  # noqa: E402

TAB = os.environ.get("CASES_TAB", "Case Tracker")
TITLE = "Case Tracker"
COL = 1
HEADERS = ["Date", "Store", "Cases"]
NCOLS = len(HEADERS)
FIRST_DATA_ROW = 3

GREY = {"red": 0.4, "green": 0.4, "blue": 0.4}


def today():
    """Today in ET (the VM's local zone is America/New_York)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:  # noqa: BLE001  (no tzdata: fall back to the system clock)
        return datetime.now().date().isoformat()


# ---------- sheet helpers ----------

def _cell(grid, row, col):
    r = grid[row - 1] if 0 < row <= len(grid) else []
    return r[col - 1] if 0 < col <= len(r) else ""


def _last_row(grid, col=COL, ncols=NCOLS):
    """Last row (1-based) with any content in this band. Gutter rows are fully
    blank, so they never count -- which is exactly what makes the append target
    the bottom of the newest group rather than the gutter above it."""
    last = 0
    for i, r in enumerate(grid):
        if any(str(_cell(grid, i + 1, c)).strip() for c in range(col, col + ncols)):
            last = i + 1
    return last


def _last_date(grid, col=COL):
    """The bottom group's date: the last ISO date in the Date column. Dates only
    appear on a group's top row, so this is the current group's day."""
    d = None
    for i in range(len(grid)):
        v = str(_cell(grid, i + 1, col)).strip()
        if xs._is_day(v):
            d = v
    return d


def _store_cell(store):
    """Store numbers are TEXT (Ben, 2026-11-04): a leading apostrophe keeps a
    '01234' from being eaten to 1234 by USER_ENTERED."""
    s = str(store).strip()
    return "'" + s if s.isdigit() else s


def _cases_int(cases):
    n = int(float(cases))
    if not 0 < n < 100000:
        raise ValueError(f"implausible case count: {cases!r}")
    return n


# ---------- the write ----------

def write_case(store, cases, day=None):
    """Append one store's order, opening a new day group (gutter + dated top row)
    when the day changes. Returns (row, day)."""
    store = str(store).strip()
    if not store:
        raise ValueError("store number is required")
    if len(store) > 24:
        raise ValueError("store number is too long")
    n = _cases_int(cases)
    day = day or today()

    with xs.writing():
        xs.ensure_section(xs.load(), TAB, TITLE, HEADERS, COL)
        grid = xs.read_grid(TAB)
        last = _last_row(grid)
        prev = _last_date(grid)
        if last < FIRST_DATA_ROW:
            row, values = FIRST_DATA_ROW, [day, _store_cell(store), n]
        elif prev == day:
            # same day: continue the group -- no date, no gutter
            row, values = last + 1, ["", _store_cell(store), n]
        else:
            # new day: leave a blank gutter row, then a dated top row
            row, values = last + 2, [day, _store_cell(store), n]
        xs._write(TAB, COL, row, [values])
    return row, day


def day_stats(day=None):
    """{stores, cases} for one day's group -- the phone's read-back."""
    day = day or today()
    grid = xs.read_grid(TAB)
    start = None
    for i in range(len(grid)):
        v = str(_cell(grid, i + 1, COL)).strip()
        if v == day:
            start = i
    if start is None:
        return {"stores": 0, "cases": 0}
    stores = total = 0
    for i in range(start, len(grid)):
        a = str(_cell(grid, i + 1, COL)).strip()
        if i > start and xs._is_day(a):
            break  # the next group's top row ends this one
        c = _cell(grid, i + 1, COL + 2)
        if str(c).strip() == "":
            continue
        stores += 1
        total += int(float(c))
    return {"stores": stores, "cases": total}


# ---------- styling (the house look: bold title + grey bold header band) ----------

def _sid(tab):
    return next(s["properties"]["sheetId"] for s in xs._meta()["sheets"]
                if s["properties"]["title"] == tab)


def style_tab(tab=None):
    tab = tab or TAB
    sid = _sid(tab)
    reqs = [
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2,
                      "startColumnIndex": 0, "endColumnIndex": NCOLS},
            "cell": {"userEnteredFormat": {"backgroundColor": GREY}},
            "fields": "userEnteredFormat.backgroundColor"}},
    ] + [{"autoResizeDimensions": {"dimensions": {
        "sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}}}
        for c in range(NCOLS)]
    xs._batch(reqs)


# ---------- CLI ----------

def init():
    xs.ensure_section(xs.load(), TAB, TITLE, HEADERS, COL)
    style_tab()
    print(f"tab '{TAB}' ready (columns {', '.join(HEADERS)})")


def show():
    grid = xs.read_grid(TAB)
    print(f"tab '{TAB}' -- {max(_last_row(grid) - 2, 0)} rows")
    for i, r in enumerate(grid[: _last_row(grid) or 1]):
        print(f"{i + 1:>3} | " + " | ".join(str(_cell(grid, i + 1, c)) for c in range(1, NCOLS + 1)))
    print("today:", day_stats())


def selfcheck():
    """Assert the grouping contract on a throwaway tab, then delete it."""
    global TAB
    real, TAB = TAB, "zz_cases_selfcheck"
    try:
        xs.ensure_tab(xs.load(), TAB)
        write_case("1234", 5, day="2026-11-04")
        write_case("5678", 3, day="2026-11-04")   # same day: no new date, no gutter
        write_case("9012", 4, day="2026-11-05")   # new day: gutter + dated top row
        g = xs.read_grid(TAB)
        assert _cell(g, 1, 1) == TITLE, g[:1]
        assert [_cell(g, 2, c) for c in (1, 2, 3)] == HEADERS
        assert [_cell(g, 3, c) for c in (1, 2, 3)] == ["2026-11-04", "1234", "5"], g[2]
        assert [_cell(g, 4, c) for c in (1, 2, 3)] == ["", "5678", "3"], g[3]
        assert [_cell(g, 5, c) for c in (1, 2, 3)] == ["", "", ""], g[4]  # the gutter
        assert [_cell(g, 6, c) for c in (1, 2, 3)] == ["2026-11-05", "9012", "4"], g[5]
        assert _last_row(g) == 6
        assert day_stats("2026-11-04") == {"stores": 2, "cases": 8}, day_stats("2026-11-04")
        assert day_stats("2026-11-05") == {"stores": 1, "cases": 4}
    finally:
        xs.delete_tab(TAB)
        TAB = real
    print("selfcheck OK — grouping, gutter row and date-once all hold")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", nargs=2, metavar=("STORE", "CASES"))
    p.add_argument("--init", action="store_true")
    p.add_argument("--selfcheck", action="store_true")
    p.add_argument("--day")
    a = p.parse_args()
    if a.selfcheck:
        selfcheck()
    elif a.init:
        init()
    elif a.log:
        row, day = write_case(a.log[0], a.log[1], day=a.day)
        print(f"logged {a.log[0]} / {a.log[1]} cases as row {row} on {day}")
        print("today:", day_stats(day))
    else:
        show()


if __name__ == "__main__":
    main()
