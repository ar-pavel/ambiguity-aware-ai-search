"""Serve the page and answer its requests.

    python3 app.py            # then open http://127.0.0.1:8770 (Ctrl+C to stop)
    python3 app.py --port 8771

Standard library only. Each route is a plain function, so it can be tested without a server:
    /api/search   handle()          read the request, choose act / show / ask, search
    /api/plan     plan_action()     what a write would change; writes nothing
    /api/apply    apply_action()    write a confirmed plan
    /api/undo     undo_action()     put back the last write
    /api/command  command_action()  is a typed follow-up a write command, and for which job?
What the page shows is built in replies.py.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import actions
import commands
import interpret
import log
import replies
import search
import store
import strategy

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}


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


def _theta(value):
    """The overlap threshold from the request, kept between 0 and 1 (default if not a number)."""
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return strategy.THETA


def handle(payload):
    """Interpret the request, choose a mode, run the search and describe what ran."""
    return _run(payload)[0]


# Words that carry no filter: asking for everyone ("show me all candidates") uses only these.
FILLER = set("""
show me find get give list search look looking for i we need want see who are is be with and or the a an
of all any every everyone everybody anyone anybody some please our my candidate candidates people person
someone profile profiles
""".split())


def _unused_words(reading, text):
    """The words of a request with no filter that the search could not use. Empty when the request only
    asks for everyone ("all candidates"), so that one still searches everyone."""
    if reading["skills"] or search.describe_parts(reading):
        return None   # it named something to search for
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'+#.-]*", text) if w.lower() not in FILLER] or (
        None if re.search(interpret.PEOPLE_WORDS, text, re.I) or re.search(r"\bevery(?:one|body)\b", text, re.I)
        else [text])


def _run(payload):
    """handle(), plus the records themselves (the write actions work on exactly these)."""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"error": "Type a request, for example: senior Java developers in London"}, []
    reading = interpret.interpret(text)
    unused = _unused_words(reading, text)
    if unused:
        # Searching would return every record and call it "nothing was unclear", which is not what
        # "hello" or "candidates named Matin" meant. Reported like an error, so nothing is searched,
        # planned or logged, but worded as a reply.
        unusable = " ".join(unused)
        lead = ("I can't search for “%s”." % unusable if unusable.lower() == text.lower().strip(" .!?")
                else "I didn't find anything I can search for in “%s”: I can't use “%s”." % (text, unusable))
        return {"error": lead + " I search by skill, place, company, role or seniority, for example "
                                "“Java developers in London” or “open jobs at Bluefin”.",
                "nothing": True, "text": text}, []
    named = re.search(r"\b(?:named|called)\s+([A-Za-z][A-Za-z'-]*)", text, re.I)
    if named:  # names are not searched: say so instead of quietly searching without it
        note = "the name “%s” (searching by name is not supported)" % named.group(1)
        reading["dropped"] = reading.get("dropped", []) + [note]
    edited = _apply_edits(reading, payload.get("choices") or {}, payload.get("op"))
    reading = interpret.for_target(reading)  # the target may have just been switched
    decision = strategy.decide(reading, theta=_theta(payload.get("theta", strategy.THETA)),
                               force=payload.get("mode") if payload.get("mode") != "auto" else None)
    # "Search anyway" is the recruiter's own choice to skip the question, not a strategy setting.
    last = payload.get("last") if isinstance(payload.get("last"), dict) else {}
    anyway = bool(last.get("anyway")) and decision["rule_mode"] == "ask"
    explained = replies.why(reading, decision, edited, forced=decision["mode"] != decision["rule_mode"], anyway=anyway)
    if anyway and not edited:
        decision = dict(decision, reason="Searched with my best guess, as you asked. Change it with the chip marked ▾.",
                        hint="Change it with the chip marked ▾.")
    if edited:  # the recruiter has taken control: keep the chips in view and say what happened
        decision = dict(decision, mode="show")
    results = search.search(reading)
    target = reading.get("target") or "candidates"
    if edited:
        decision["reason"] = replies.change_message(reading, payload.get("last"), len(results),
                                            "job" if target == "jobs" else "candidate")
        decision["hint"] = None
    return {
        "text": text,
        "reading": reading,
        "mode": decision["mode"],
        "reason": decision["reason"],
        "hint": decision.get("hint"),  # the "how to change it" sentence at the end of reason, if any
        "read_as": search.describe(reading),
        "chips": replies.chips(reading),
        "question": replies.question(reading, decision["ask_slot"]) if decision["mode"] == "ask" else None,
        "target": target,
        "noun": "job" if target == "jobs" else "candidate",
        "table": replies.table(results, target),
        "count": len(results),
        "searched": search.SEARCHED[target],
        "not_searched": search.NOT_SEARCHED[target],
        "interpreter": replies.interpreter_label(reading.get("source", "rules")),
        "dropped": reading.get("dropped", []),
        "theta": decision["theta"],
        "why": explained,
    }, results


ANSWER_FIRST = "Answer the question first, so it is clear which records you mean."
MAX_OPTIONS = 6  # job choices offered for an unclear typed command; more than this reads as a list, not a question


def _plan(payload):
    """Re-run the recruiter's search on the server and plan the action on its records."""
    result, records = _run(payload.get("search") or {})
    if "error" in result:
        return result, {"valid": False, "error": result["error"]}
    if result["mode"] == "ask":
        return result, {"valid": False, "error": ANSWER_FIRST}
    job_id = payload.get("job_id")
    try:
        job_id = int(job_id) if job_id not in (None, "") else None
    except (TypeError, ValueError):
        job_id = None
    plan = actions.plan(payload.get("action"), records, result["target"], job_id)
    plan["read_as"] = result["read_as"]
    return result, plan


def plan_action(payload):
    """What a write would change. Writes nothing (so Cancel needs nothing undone)."""
    return _plan(payload)[1]


def apply_action(payload, log_dir=None):
    """Apply a confirmed plan: recomputed now, and refused unless it is exactly what was confirmed."""
    with store.LOCK:
        result, plan = _plan(payload)
        out = actions.apply(plan, payload.get("fingerprint"))
    if out["ok"]:
        log.write_event({"event": "write", "action": plan["action"], "job_id": plan.get("job_id"),
                         "text": result.get("text"), "read_as": plan.get("read_as"), "changed": out["changed"],
                         "skipped": out["skipped"], "fingerprint": plan["fingerprint"]}, log_dir)
    return out


def _quoted(words):
    return " or ".join("'%s'" % w for w in words)


def _command(text, search_payload):
    """The answer to a typed follow-up. Reads only: the page still confirms before anything is written."""
    cmd = commands.parse(text)
    if cmd is None or not (search_payload.get("text") or "").strip():
        return {"kind": "search"}
    result, records = _run(search_payload)
    if "error" in result:
        return {"kind": "search"}
    if result["mode"] == "ask":
        return {"kind": "error", "error": ANSWER_FIRST}
    action = cmd["action"]
    if actions.wrong_target(action, result["target"]):
        return {"kind": "error", "error": actions.wrong_target(action, result["target"])}
    n = len(records)
    on_screen = "the %d %s%s on screen" % (n, result["noun"], "" if n == 1 else "s")
    if action == "close":
        return {"kind": "plan", "action": "close", "job_id": None, "reason": "You asked to close %s." % on_screen}
    jobs = [j for j in search.load("jobs") if j["status"] == "open"]  # a closed job is never offered
    found, matched, every = commands.match_jobs(cmd["job_words"], jobs)
    if len(found) == 1:
        return {"kind": "plan", "action": "shortlist", "job_id": found[0]["id"],
                "reason": "You asked to shortlist %s for %s." % (on_screen, actions.job_label(found[0]))}
    if not found:
        why = ("no open job matches %s, so " % _quoted(cmd["job_words"])) if cmd["job_words"] else ""
        return {"kind": "plan", "action": "shortlist", "job_id": None,
                "reason": "You asked to shortlist %s; %schoose the job in the dialog." % (on_screen, why)}
    labels = {j["id"]: j["label"] for j in actions.open_jobs()}
    order = list(labels)  # the picker's order (company, then title)
    found.sort(key=lambda j: order.index(j["id"]))
    if len(matched) == 1:
        reason = "%s matches %d open jobs." % (_quoted(matched), len(found))
    elif every:
        quoted = ["'%s'" % w for w in matched]
        reason = "%s and %s match %d open jobs." % (", ".join(quoted[:-1]), quoted[-1], len(found))
    else:
        reason = "%d open jobs match %s." % (len(found), _quoted(matched))
    if len(found) > MAX_OPTIONS:
        reason += " Showing the first %d; choose the job in the dialog for the other %d." % (
            MAX_OPTIONS, len(found) - MAX_OPTIONS)
    return {"kind": "ask", "action": "shortlist", "text": "Which job did you mean?", "reason": reason,
            "options": [{"job_id": j["id"], "label": labels[j["id"]]} for j in found[:MAX_OPTIONS]]}


def command_action(payload, log_dir=None):
    """A typed follow-up such as "add them to the Java shortlist at Bluefin": is it a write command,
    and for which job? Returns one of {"kind": "search" | "plan" | "ask" | "error", ...}. Writes nothing."""
    text = (payload.get("text") or "").strip()
    out = _command(text, payload.get("search") or {})
    if out["kind"] != "search":  # a new search is logged by /api/search itself
        action = out.get("action") or commands.parse(text)["action"]
        log.write_event({"event": "command", "text": text, "kind": out["kind"], "action": action,
                         "job_id": out.get("job_id"), "error": out.get("error")}, log_dir)
    return out


def undo_action(log_dir=None):
    """Put back the last write, and log it."""
    out = actions.undo()
    if out["ok"]:
        log.write_event({"event": "undo", "done": out["done"]}, log_dir)
    return out


class Handler(BaseHTTPRequestHandler):
    """Serves web/ and the JSON routes, to this machine only."""

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

    ROUTES = {"/api/search": handle, "/api/plan": plan_action, "/api/apply": apply_action,
              "/api/command": command_action,
              "/api/undo": lambda payload: undo_action()}

    def do_POST(self):
        route = self.ROUTES.get(self.path)
        if route is None:
            return self._send(404, {"error": "not found"})
        if not self._local() or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send(403, {"error": "requests must come from this page"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = route(payload)
            if route is handle:
                log.write(payload, result)
            self._send(200, result)
        except (ValueError, KeyError) as e:
            self._send(400, {"error": "bad request: %s" % e})

    def log_message(self, *args):  # keep the terminal quiet
        pass


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8770
    print("Open http://127.0.0.1:%d  (Ctrl+C to stop)" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
