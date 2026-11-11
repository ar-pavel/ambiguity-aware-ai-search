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

import actions
import commands
import interpret
import log
import store
import search
import strategy

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
NOTICE = {"immediate": "now", "2w": "2 weeks", "1m": "1 month", "3m": "3 months"}
# The results table for each target: (header, how to show one record's cell).
COLUMNS = {
    "candidates": [("Name", "name"), ("Title", "current_title"), ("Skills", "skills"),
                   ("Years", "years_experience"), ("City", "city"), ("Company", "company"),
                   ("Work mode", "work_mode"), ("Notice", "notice")],
    "jobs": [("Job", "title"), ("Company", "company"), ("Skills", "skills"), ("Min. years", "min_years"),
             ("City", "city"), ("Work mode", "work_mode"), ("Status", "status"), ("Shortlist", "shortlist")],
}


def _cell(rec, key):
    value = rec[key]
    if key == "skills":
        return ", ".join(value)
    if key == "shortlist":
        return str(len(value))
    if key == "notice":
        return NOTICE[value]
    return str(value)


def table(records, target):
    """Headers and rows of plain strings, so the page needs no knowledge of either record type."""
    cols = COLUMNS[target]
    return {"headers": [h for h, _ in cols], "rows": [[_cell(r, k) for _, k in cols] for r in records]}


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
    "target": "Are you looking for people or for jobs?",
}


def question(reading, slot):
    """One clarifying question for one slot, each option with the number of results it would give."""
    amb = next(a for a in reading["ambiguities"] if a["slot"] == slot)
    text = QUESTIONS.get(slot, "Which did you mean?")
    if "%s" in text:  # built from the reading, never from model text
        text %= "'%s'" % reading["seniority"].get("contains", "Senior").lower()
    options = []
    for label, opt in zip(amb["labels"], amb["options"]):
        variant = interpret.apply_option(reading, opt)
        options.append({"label": label, "count": len(search.search(variant)),
                        "noun": "job" if variant.get("target") == "jobs" else "candidate"})
    return {"slot": slot, "text": text, "options": options, "default": amb["chosen"],
            "evidence": amb["evidence"]}


ASKED = {
    "skills_op": "whether they need all the skills or any one",
    "seniority": "what you meant by %s",
    "location": "where they should be",
    "availability": "how soon they need to start",
    "target": "whether you wanted people or jobs",
}


def change_message(reading, last, count, noun):
    """After an edit, say what changed and what it gave (UX review fix 1), built from the reading.
    `last` is the control the recruiter just used: {"op": true} or {"slot": ..., "answered": bool}."""
    found = "%d %s%s" % (count, noun, "" if count == 1 else "s")
    last = last if isinstance(last, dict) else {}
    if last.get("op"):
        new = reading["skills_op"]
        return "You switched %s → %s: %s." % ("OR" if new == "AND" else "AND", new, found)
    amb = next((a for a in reading["ambiguities"] if a["slot"] == last.get("slot")), None)
    if amb is None:
        return "Updated with your changes: %s." % found
    chosen = amb["labels"][amb["chosen"]]
    if last.get("answered"):
        asked = ASKED.get(amb["slot"], "which you meant")
        if "%s" in asked:
            asked %= "'%s'" % (reading.get("seniority") or {}).get("contains", "senior").lower()
        return "I asked %s; you chose %s: %s." % (asked, chosen, found)
    return "You chose %s: %s." % (chosen, found)


def _pct(x, theta):
    """A share as a percentage; one decimal when rounding would hide which side of θ it is on."""
    whole = round(x * 100)
    if whole == round(theta * 100) and x != theta:
        return "%.1f%%" % (x * 100)
    return "%d%%" % whole


def why(reading, decision, edited, forced):
    """The rule's own comparison, row by row, for the collapsible "Why?" section (Amershi G11).
    Every number comes from strategy.decide(), so the explanation cannot drift from the decision."""
    theta = decision["theta"]
    rows = []
    for c in decision["comparisons"]:
        if c["dominant"]:
            verdict = "no need to ask: %s" % c["evidence"]
        elif c["overlap"] >= theta:
            verdict = "at least θ (%d%%): show, don't ask" % round(theta * 100)
        else:
            verdict = "below θ (%d%%): ask" % round(theta * 100)
        rows.append({"part": strategy.slot_words(reading, c["slot"]).replace("phrase:", ""),
                     "readings": [{"label": c["chosen_label"], "count": c["chosen"], "used": True},
                                  {"label": c["other_label"], "count": c["other"], "used": False}],
                     "overlap": round(c["overlap"], 2), "share": _pct(c["overlap"], theta), "dominant": c["dominant"], "verdict": verdict})
    if not rows:
        summary = "Nothing in the request was unclear, so there was nothing to compare: act."
    else:
        summary = "The rule compares the lists each unclear part could give. It asks only when a part has no clear reading and its lists share less than θ = %d%%." % round(theta * 100)
    notes = []
    if forced:
        notes.append("The strategy setting chose %s; the rule alone would have chosen %s." % (decision["mode"], decision["rule_mode"]))
    if edited:
        notes.append("You changed the reading, so the chips stay in view. The rows describe the reading as it is now.")
    return {"summary": summary, "rows": rows, "theta": theta, "rule_mode": decision["rule_mode"], "notes": notes}


def _interpreter_label(source):
    """Say plainly which interpreter read the request, using the agreed status words."""
    if source == "rules":
        return "rule-based stand-in (simulated)"
    if source.startswith("rules"):  # live mode was on but the model could not be used
        return "rule-based stand-in (simulated): the live model was unavailable or its reply was unusable"
    return source


def _theta(value):
    """The overlap threshold from the request, kept between 0 and 1 (default if not a number)."""
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return strategy.THETA


def handle(payload):
    """Interpret the request, choose a mode, run the search and describe what ran."""
    return _run(payload)[0]


def _run(payload):
    """handle(), plus the records themselves (the write actions work on exactly these)."""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"error": "Type a request, for example: senior Java developers in London"}, []
    reading = interpret.interpret(text)
    edited = _apply_edits(reading, payload.get("choices") or {}, payload.get("op"))
    reading = interpret.for_target(reading)  # the target may have just been switched
    decision = strategy.decide(reading, theta=_theta(payload.get("theta", strategy.THETA)),
                               force=payload.get("mode") if payload.get("mode") != "auto" else None)
    explained = why(reading, decision, edited, forced=decision["mode"] != decision["rule_mode"])
    if edited:  # the recruiter has taken control: keep the chips in view and say what happened
        decision = dict(decision, mode="show")
    results = search.search(reading)
    target = reading.get("target") or "candidates"
    if edited:
        decision["reason"] = change_message(reading, payload.get("last"), len(results),
                                            "job" if target == "jobs" else "candidate")
    return {
        "text": text,
        "reading": reading,
        "mode": decision["mode"],
        "reason": decision["reason"],
        "read_as": search.describe(reading),
        "chips": chips(reading),
        "question": question(reading, decision["ask_slot"]) if decision["mode"] == "ask" else None,
        "target": target,
        "noun": "job" if target == "jobs" else "candidate",
        "table": table(results, target),
        "count": len(results),
        "searched": search.SEARCHED[target],
        "not_searched": search.NOT_SEARCHED[target],
        "interpreter": _interpreter_label(reading.get("source", "rules")),
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
                "reason": "You asked to shortlist %s for %s." % (on_screen, actions._job_label(found[0]))}
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
        reason = "%s match %d open jobs." % (" and ".join("'%s'" % w for w in matched), len(found))
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
    out = actions.undo()
    if out["ok"]:
        log.write_event({"event": "undo", "done": out["done"]}, log_dir)
    return out


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
