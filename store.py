"""The recruiter's changes: the only module that writes data.

    state/state.json      (ignored by git; set A2_STATE to use another file)

The generated files in data/ are the starting world and are never changed. This file holds only
what the recruiter changed on top of them, plus what is needed to undo the last changes:
    job_status   {job id: "open" | "closed"}
    shortlists   {job id: [candidate ids]}
    undo         a stack of {summary, previous values of exactly the records that were touched}
"""
import copy
import json
import os
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("A2_STATE") or os.path.join(HERE, "state", "state.json")
LOCK = threading.RLock()  # the server answers requests on several threads
EMPTY = {"job_status": {}, "shortlists": {}, "undo": []}
UNDO_LIMIT = 20


def read():
    """The current changes (an empty set if nothing has been changed yet)."""
    if not os.path.exists(PATH):
        return copy.deepcopy(EMPTY)
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def save(state):
    """Write the whole state at once: a temporary file, then a rename, so a crash never leaves half a file."""
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, PATH)


def overlay(jobs):
    """The jobs with the recruiter's changes applied, as copies (the loaded data is never modified)."""
    state = read()
    return [dict(j, status=state["job_status"].get(str(j["id"]), j["status"]),
                 shortlist=state["shortlists"].get(str(j["id"]), [])) for j in jobs]
