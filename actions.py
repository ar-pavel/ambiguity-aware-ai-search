"""Write actions: shortlist candidates for a job, and close jobs.

Reads follow act / show / ask. Writes always confirm (W4 L12: "can it be undone, and will the
person notice?"). The flow is plan -> confirm -> apply -> (undo):

  plan()   says exactly which records would change, which would not and why. It writes nothing,
           so Cancel needs no clean-up. Its fingerprint identifies exactly this set of changes.
  apply()  recomputes the plan and refuses if the fingerprint differs from the one the recruiter
           confirmed (the data or the search changed in between). Otherwise it writes and keeps
           the previous values for undo.
  undo()   restores the previous values of exactly the records the last write touched.

The records always come from the server's own search, never from a list of ids sent by the page.
"""
import hashlib
import json

import search
import store

ACTIONS = {"close": "jobs", "shortlist": "candidates"}  # the target each action works on


def _job_label(job):
    return "%s at %s (%s)" % (job["title"], job["company"], job["city"])


def open_jobs():
    """Jobs a candidate can be shortlisted for, for the page's job picker."""
    jobs = [j for j in search.load("jobs") if j["status"] == "open"]
    return [{"id": j["id"], "label": _job_label(j)} for j in sorted(jobs, key=lambda j: (j["company"], j["title"]))]


def _fingerprint(action, job_id, changes, skipped):
    key = [action, job_id, [(c["id"], c["before"]) for c in changes], [s["id"] for s in skipped]]
    return hashlib.sha256(json.dumps(key).encode("utf-8")).hexdigest()[:16]


def plan(action, records, target, job_id=None):
    """What the action would do to these records. Writes nothing."""
    if action not in ACTIONS:
        return {"valid": False, "error": "Unknown action."}
    if ACTIONS[action] != target:
        need = "jobs" if ACTIONS[action] == "jobs" else "candidates"
        return {"valid": False, "error": "This action works on %s; the search found %s." % (need, target)}
    changes, skipped, out = [], [], {"action": action, "job_id": job_id}
    if action == "close":
        for j in records:
            item = {"id": j["id"], "label": _job_label(j)}
            if j["status"] == "closed":
                skipped.append(dict(item, why="already closed"))
            else:
                changes.append(dict(item, before=j["status"], after="closed"))
        n = len(changes)
        out["summary"] = "Close %d job%s." % (n, "" if n == 1 else "s")
        out["confirm_label"] = "Close %d job%s" % (n, "" if n == 1 else "s")
    else:
        out["jobs"] = open_jobs()
        job = next((j for j in search.load("jobs") if j["id"] == job_id), None)
        listed = set(job["shortlist"]) if job else set()
        for c in records:
            item = {"id": c["id"], "label": "%s, %s" % (c["name"], c["current_title"])}
            if c["id"] in listed:
                skipped.append(dict(item, why="already on this shortlist"))
            else:
                changes.append(dict(item, before="not shortlisted", after="shortlisted"))
        n = len(changes)
        if job is None:
            out.update(valid=False, error="Choose a job to shortlist them for.", changes=changes, skipped=skipped,
                       summary="Shortlist %d candidate%s for a job." % (n, "" if n == 1 else "s"))
            return out
        if job["status"] != "open":
            out.update(valid=False, error="That job is closed.", changes=[], skipped=[])
            return out
        out["job"] = _job_label(job)
        out["summary"] = "Add %d candidate%s to the shortlist for %s." % (n, "" if n == 1 else "s", _job_label(job))
        out["confirm_label"] = "Shortlist %d candidate%s" % (n, "" if n == 1 else "s")
    out.update(changes=changes, skipped=skipped, valid=bool(changes),
               fingerprint=_fingerprint(action, job_id, changes, skipped))
    if not changes:
        out["error"] = "Nothing to change: %s." % ("all of them are " + skipped[0]["why"] if skipped else "no records")
    return out


def apply(current, fingerprint):
    """Write the plan the recruiter confirmed. `current` is the plan recomputed now, under store.LOCK."""
    if not current.get("valid"):
        return {"ok": False, "error": current.get("error", "Nothing to change."), "plan": current}
    if current["fingerprint"] != fingerprint:
        return {"ok": False, "error": "The records changed since you confirmed. Check the new list.", "plan": current}
    state = store.read()
    ids = [str(c["id"]) for c in current["changes"]]
    if current["action"] == "close":
        previous = {"job_status": {i: state["job_status"].get(i) for i in ids}}
        for i in ids:
            state["job_status"][i] = "closed"
        done = "Closed %d job%s" % (len(ids), "" if len(ids) == 1 else "s")
        undone = "Reopened the %d job%s you closed" % (len(ids), "" if len(ids) == 1 else "s")
    else:
        job = str(current["job_id"])
        previous = {"shortlists": {job: state["shortlists"].get(job)}}
        state["shortlists"][job] = (state["shortlists"].get(job) or []) + [c["id"] for c in current["changes"]]
        done = "Shortlisted %d candidate%s for %s" % (len(ids), "" if len(ids) == 1 else "s", current["job"])
        undone = "Took the %d candidate%s off the shortlist for %s" % (len(ids), "" if len(ids) == 1 else "s", current["job"])
    state["undo"] = (state["undo"] + [{"summary": done, "undone": undone, "previous": previous}])[-store.UNDO_LIMIT:]
    store.save(state)
    return {"ok": True, "done": done, "changed": len(ids), "skipped": len(current["skipped"])}


def undo():
    """Put back the previous values of exactly the records the last write changed."""
    with store.LOCK:
        state = store.read()
        if not state["undo"]:
            return {"ok": False, "error": "Nothing to undo."}
        last = state["undo"].pop()
        for field, values in last["previous"].items():
            for key, value in values.items():
                if value is None:
                    state[field].pop(key, None)  # there was no change on top of the data before
                else:
                    state[field][key] = value
        store.save(state)
    # Say what undo did in its own words; older state files have only the summary.
    return {"ok": True, "done": last.get("undone") or "Undone: " + last["summary"]}
