"""Optional live language model for the interpreter.

Set these in your shell to use your own model (never write them into a file):
    A2_MODEL=http
    A2_MODEL_URL=<an OpenAI-compatible chat-completions endpoint>
    A2_API_KEY=<your key>

Without them, the rule-based stand-in in interpret.py is used. The reply must match the reading
shape; anything else is rejected, and the page says it fell back to the rules.
"""
import json
import os
import urllib.request

SYSTEM = """You turn a recruiter's candidate-search request into JSON. Reply with JSON only:
{"skills": [..], "skills_op": "AND"|"OR",
 "location": null | {"value": city or country, "scope": "city"|"nearby"|"country"},
 "seniority": null | {"kind": "years", "min": n} | {"kind": "title", "contains": word},
 "availability": null | {"max_notice": "immediate"|"2w"|"1m"|"3m"},
 "work_mode": null | "remote"|"hybrid"|"onsite",
 "ambiguities": [{"slot": "skills_op"|"seniority"|"location"|"availability",
                  "options": [patches], "labels": [short text], "chosen": index,
                  "dominant": true|false, "evidence": "you wrote '...'"}]}
Rules: never change the user's 'and' into OR. A lower-case 'and', 'with' or 'or' is dominant
evidence for the operator; capital AND/OR is stated, not ambiguous. 'senior' or 'lead' without a
number is ambiguous between years and title. Only 'near', 'around', 'within' or 'commutable' make
a location ambiguous. Do not invent skills the user did not write."""

REQUIRED = {"skills", "skills_op", "location", "seniority", "availability", "work_mode", "ambiguities"}


def live():
    return (os.environ.get("A2_MODEL") == "http" and os.environ.get("A2_MODEL_URL")
            and os.environ.get("A2_API_KEY"))


def _valid(reading):
    return (isinstance(reading, dict) and REQUIRED <= set(reading)
            and reading["skills_op"] in ("AND", "OR") and isinstance(reading["ambiguities"], list)
            and all({"slot", "options", "labels", "chosen", "dominant", "evidence"} <= set(a)
                    for a in reading["ambiguities"]))


def interpret(text, timeout=20):
    """Return a validated reading from the live model, or None if anything goes wrong."""
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request(
        os.environ["A2_MODEL_URL"], data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["A2_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        reading = json.loads(reply)
    except Exception:  # network, auth or JSON problems all mean: fall back to the rules
        return None
    return reading if _valid(reading) else None
