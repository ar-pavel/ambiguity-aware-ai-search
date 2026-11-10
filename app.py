"""Serve the page and answer search requests.

    python3 app.py            # then open http://127.0.0.1:8770
    python3 app.py --port 8771

Standard library only. The page posts {"text": "..."} to /api/search; handle() does the work, so it
can be tested without a server.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import interpret
import search
import strategy

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
FIELDS = ("name", "current_title", "skills", "years_experience", "city", "work_mode", "notice")


def handle(payload):
    """Interpret the request, choose a mode, run the search and describe what ran."""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"error": "Type a request, for example: senior Java developers in London"}
    reading = interpret.interpret(text)
    decision = strategy.decide(reading, theta=float(payload.get("theta", strategy.THETA)),
                               force=payload.get("mode") if payload.get("mode") != "auto" else None)
    results = search.search(reading)
    return {
        "text": text,
        "reading": reading,
        "mode": decision["mode"],
        "reason": decision["reason"],
        "read_as": search.describe(reading),
        "results": [{k: c[k] for k in FIELDS} for c in results],
        "count": len(results),
        "searched": search.SEARCHED,
        "not_searched": search.NOT_SEARCHED,
        "interpreter": reading.get("source", "rules"),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        name = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB) or not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self._send(200, f.read(), TYPES.get(os.path.splitext(path)[1], "text/plain"))

    def do_POST(self):
        if self.path != "/api/search":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, handle(payload))
        except (ValueError, KeyError) as e:
            self._send(400, {"error": "bad request: %s" % e})

    def log_message(self, *args):  # keep the terminal quiet
        pass


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8770
    print("Open http://127.0.0.1:%d  (Ctrl+C to stop)" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
