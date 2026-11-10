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


def _apply_edits(reading, choices, op):
    """Apply the recruiter's chip edits to a fresh reading. Returns True if anything changed."""
    edited = False
    for amb in reading["ambiguities"]:
        idx = choices.get(amb["slot"])
        if idx is not None and 0 <= int(idx) < len(amb["options"]):
            reading.update({k: v for k, v in interpret.apply_option(reading, amb["options"][int(idx)]).items()
                            if k != "ambiguities"})
            amb["chosen"], amb["edited"] = int(idx), True
            edited = True
    if op in ("AND", "OR") and op != reading["skills_op"]:
        reading["skills_op"], reading["op_edited"] = op, True
        edited = True
    return edited


def chips(reading):
    """Everything the reading assumed, as chips. Open choices are marked 'guessed' until edited."""
    by_slot = {a["slot"]: a for a in reading["ambiguities"]}
    out = [{"kind": "skill", "text": s} for s in reading["skills"]]
    if len(reading["skills"]) > 1:
        amb = by_slot.get("skills_op")
        out.insert(1, {"kind": "op", "value": reading["skills_op"],
                       "evidence": amb["evidence"] if amb else "you typed it in capitals",
                       "guessed": bool(amb and not amb["dominant"]) and not reading.get("op_edited")})
    for slot, text in search.describe_parts(reading).items():
        amb = by_slot.get(slot)
        chip = {"kind": "slot", "slot": slot, "text": text}
        if amb:
            chip.update(options=amb["labels"], chosen=amb["chosen"], evidence=amb["evidence"],
                        guessed=not amb["dominant"] and not amb.get("edited"))
        out.append(chip)
    for amb in reading["ambiguities"]:
        if amb["slot"].startswith("phrase:"):
            out.append({"kind": "slot", "slot": amb["slot"], "text": amb["labels"][amb["chosen"]],
                        "options": amb["labels"], "chosen": amb["chosen"], "evidence": amb["evidence"],
                        "guessed": False})
    return out


QUESTIONS = {
    "skills_op": "Should candidates have all of these skills, or any one of them?",
    "seniority": "What do you mean by %s?",
    "location": "Where should candidates be?",
    "availability": "How soon do they need to start?",
}


def question(reading, slot):
    """One clarifying question for one slot, each option with the number of candidates it would give."""
    amb = next(a for a in reading["ambiguities"] if a["slot"] == slot)
    text = QUESTIONS.get(slot, "Which did you mean?")
    if "%s" in text:  # built from the reading, never from model text
        text %= "'%s'" % reading["seniority"].get("contains", "Senior").lower()
    options = [{"label": label, "count": len(search.search(interpret.apply_option(reading, opt)))}
               for label, opt in zip(amb["labels"], amb["options"])]
    return {"slot": slot, "text": text, "options": options, "default": amb["chosen"],
            "evidence": amb["evidence"]}


def _interpreter_label(source):
    """Say plainly which interpreter read the request, using the agreed status words."""
    if source == "rules":
        return "rule-based stand-in (simulated)"
    return source


def handle(payload):
    """Interpret the request, choose a mode, run the search and describe what ran."""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"error": "Type a request, for example: senior Java developers in London"}
    reading = interpret.interpret(text)
    edited = _apply_edits(reading, payload.get("choices") or {}, payload.get("op"))
    decision = strategy.decide(reading, theta=float(payload.get("theta", strategy.THETA)),
                               force=payload.get("mode") if payload.get("mode") != "auto" else None)
    if edited:  # the recruiter has taken control: keep the chips in view and say what happened
        decision = dict(decision, mode="show", reason="Updated with your changes. Tap a chip to change it again.")
    results = search.search(reading)
    return {
        "text": text,
        "reading": reading,
        "mode": decision["mode"],
        "reason": decision["reason"],
        "read_as": search.describe(reading),
        "chips": chips(reading),
        "question": question(reading, decision["ask_slot"]) if decision["mode"] == "ask" else None,
        "results": [{k: c[k] for k in FIELDS} for c in results],
        "count": len(results),
        "searched": search.SEARCHED,
        "not_searched": search.NOT_SEARCHED,
        "interpreter": _interpreter_label(reading.get("source", "rules")),
        "dropped": reading.get("dropped", []),
        "theta": decision["theta"],
    }


class Handler(BaseHTTPRequestHandler):
    def _local(self):
        """Only answer requests addressed to this machine (blocks DNS-rebinding pages)."""
        port = self.server.server_port
        allowed = {"127.0.0.1:%d" % port, "localhost:%d" % port}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {"http://" + h for h in allowed}

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._local():
            return self._send(403, {"error": "open the page at http://127.0.0.1:%d" % self.server.server_port})
        name = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB) or not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self._send(200, f.read(), TYPES.get(os.path.splitext(path)[1], "text/plain"))

    def do_POST(self):
        if self.path != "/api/search":
            return self._send(404, {"error": "not found"})
        if not self._local() or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send(403, {"error": "requests must come from this page"})
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
