#!/usr/bin/env python3
"""Tailnet-only endpoint so Ben's iPhone (Scriptable) can log a case order into the
'Case Tracker' tab of the Life workbook.

  GET  /          -> {"status":"ok"}  (liveness; bot-index polls this unauthed)
  GET  /today     -> {"ok":true,"day","stores","cases"}   (authed)
  POST /log       {"store":<text>,"cases":<int>}
                  -> {"ok":true,"row","day","today":{stores,cases}}

Auth: X-Token header (or ?token=), compared against
~/Hermes/shared/case-tracker-token.txt (0600). The server refuses to start without
it and binds the Tailscale interface, so the tailnet is the first lock and the
token the second.

The write path lives in cases.py; this file is transport + auth only, so the CLI
and the phone cannot drift. Scriptable bodies are served by the hub
(scriptable-hub, :8802), not here.
"""
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import cases

TOKEN_FILE = Path(os.environ.get("CASES_TOKEN_FILE",
                                 str(Path.home() / "Hermes/shared/case-tracker-token.txt")))
BIND = os.environ.get("CASES_BIND", "100.98.176.106")
PORT = int(os.environ.get("CASES_PORT", "8807"))
MAX_BODY = 4096
LOCK = threading.Lock()


def _token():
    return TOKEN_FILE.read_text().strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "case-tracker/1.0"
    protocol_version = "HTTP/1.1"  # replies carry Content-Length, so keep-alive is safe

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self, query):
        sent = self.headers.get("X-Token") or (query.get("token") or [""])[0]
        return hmac.compare_digest(sent, _token())

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/today":
            if not self._authed(q):
                self._send(401, {"ok": False, "error": "bad or missing token"})
                return
            try:
                self._send(200, {"ok": True, "day": cases.today(), **cases.day_stats()})
            except Exception as e:  # a read that cannot reach its store must still answer
                self._send(500, {"ok": False, "error": str(e)})
        elif u.path in ("/", "/status"):
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/log":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._authed(parse_qs(u.query)):
            self._send(401, {"ok": False, "error": "bad or missing token"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                raise ValueError(f"bad content length ({n})")
            body = json.loads(self.rfile.read(n) or b"{}")
            store = str(body.get("store") or "").strip()
            cases_n = int(body["cases"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            self._send(400, {"ok": False, "error": f"bad request: {e}"})
            return
        try:
            with LOCK:
                row, day = cases.write_case(store, cases_n)
                stats = cases.day_stats(day)
        except ValueError as e:  # bad input, not a backend fault
            self._send(400, {"ok": False, "error": f"bad request: {e}"})
            return
        except Exception as e:  # a failed write must not look like a logged order
            self._send(500, {"ok": False, "error": f"write failed: {e}"})
            return
        print(f"logged {store} / {cases_n} cases (row {row}, {day})", flush=True)
        self._send(200, {"ok": True, "row": row, "day": day, "today": stats})


def main():
    if not TOKEN_FILE.exists():
        raise SystemExit(f"no token at {TOKEN_FILE} — refusing to serve unauthenticated writes")
    print(f"case-tracker endpoint on http://{BIND}:{PORT} (tab {cases.TAB})", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
