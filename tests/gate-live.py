#!/usr/bin/env python3
"""G3/G4 gate: drive the real endpoint against a THROWAWAY tab and read the rows back.

Starts a second case-tracker instance on a scratch port with CASES_TAB pointed at a
zz_ tab, POSTs through the live HTTP path, reads the tab back with cases.py, checks
auth + bad input change nothing, and asserts the LIVE tab was untouched. Deletes the
zz_ tab and stops the server in a finally.
"""
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
BIND = "100.98.176.106"
PORT = "8897"
GATE_TAB = "zz_case_gate"
TOKEN = (Path.home() / "Hermes" / "shared" / "case-tracker-token.txt").read_text().strip()


def _req(path, method="GET", body=None, token=TOKEN):
    data = body.encode() if body else None
    r = urllib.request.Request(f"http://{BIND}:{PORT}{path}", data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-Token", token)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            import json
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        import json
        return e.code, json.loads(e.read() or b"{}")


def main():
    env = {**os.environ, "CASES_TAB": GATE_TAB, "CASES_PORT": PORT, "CASES_BIND": BIND}
    srv = subprocess.Popen(["/usr/bin/python3", str(PROJ / "server.py")], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import cases
    cases.TAB = GATE_TAB
    try:
        for _ in range(30):
            try:
                if _req("/")[0] == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        else:
            raise SystemExit("server never came up\n" + (srv.stdout.read() if srv.stdout else ""))

        s1, r1 = _req("/log", "POST", '{"store":"01234","cases":5}')
        s2, r2 = _req("/log", "POST", '{"store":"5678","cases":3}')
        assert s1 == 200 and r1["ok"] and r1["row"] == 3, (s1, r1)
        assert s2 == 200 and r2["ok"] and r2["row"] == 4, (s2, r2)
        assert r2["today"] == {"stores": 2, "cases": 8}, r2

        s3, r3 = _req("/today")
        assert s3 == 200 and r3["stores"] == 2 and r3["cases"] == 8, r3

        s4, _ = _req("/log", "POST", '{"store":"9","cases":1}', token="nope")
        assert s4 == 401, s4
        s5, _ = _req("/log", "POST", '{"store":"","cases":5}')
        assert s5 == 400, s5

        grid = cases.xs.read_grid(GATE_TAB)
        row3 = [str(cases._cell(grid, 3, c)) for c in (1, 2, 3)]
        row4 = [str(cases._cell(grid, 4, c)) for c in (1, 2, 3)]
        assert row3[1] == "01234" and row3[2] == "5", row3  # leading zero survived (TEXT)
        assert row3[0] == cases.today(), row3
        assert row4[0] == "" and row4[1] == "5678", row4  # same day: no second date
        assert cases._last_row(grid) == 4, grid  # the rejections wrote nothing

        live = cases.xs.read_grid("Case Tracker")
        assert cases._last_row(live) == 2, f"LIVE tab was written: {live}"
        print("gate OK — G3/G4 hold; throwaway rows:", row3, row4, "(live tab untouched)")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:  # noqa: BLE001
            srv.kill()
        cases.TAB = GATE_TAB
        cases.xs.delete_tab(GATE_TAB)


if __name__ == "__main__":
    main()
