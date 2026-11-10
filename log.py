"""Append one line per turn to a local log, for evaluating the strategies later.

    logs/events.jsonl      (ignored by git; set A2_LOG=off to turn logging off)

Each line records what was asked, which interpreter read it, which strategy ran and why, what the
recruiter changed, and how many candidates came back. It never leaves this machine.
"""
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")


def enabled():
    return os.environ.get("A2_LOG", "on").strip().lower() != "off"


def entry(payload, result):
    """The fields worth keeping from one request and its answer."""
    edited = bool(payload.get("choices") or payload.get("op"))
    return {
        "t": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": "edit" if edited else "search",
        "text": result.get("text"),
        "interpreter": result.get("interpreter"),
        "strategy_setting": payload.get("mode", "auto"),
        "theta": result.get("theta"),
        "target": result.get("target"),
        "mode": result.get("mode"),
        "reason": result.get("reason"),
        "ambiguities": [a["slot"] for a in (result.get("reading") or {}).get("ambiguities", [])],
        "asked": (result.get("question") or {}).get("slot"),
        "choices": payload.get("choices") or {},
        "op": payload.get("op"),
        "read_as": result.get("read_as"),
        "count": result.get("count"),
        "dropped": result.get("dropped", []),
    }


def write(payload, result, log_dir=None):
    """Append one line. Errors and empty requests are not logged."""
    if not enabled() or "error" in result:
        return None
    log_dir = log_dir or LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    line = entry(payload, result)
    with open(os.path.join(log_dir, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    return line
