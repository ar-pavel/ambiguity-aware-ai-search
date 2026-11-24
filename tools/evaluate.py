"""The scripted evaluation: what each strategy costs in questions, and how many wrong lists it lets through.

    python3 tools/evaluate.py                              # the rule-based stand-in
    python3 tools/evaluate.py --with bedrock               # one run with a live model as the interpreter
    python3 tools/evaluate.py --out evaluation/results     # also write <interpreter>.json and .md there

Each request in evaluation/requests.json says what a recruiter could have meant. Every plausible
meaning is taken as the intended one in turn (a "case"), and the list it gives is the right answer.
Each case then goes through the same code as the page, under four strategies: always act, always
show, always ask, and the rule (adaptive). A scripted recruiter stands in for a person:

  * after an act, they take the list as it is;
  * asked a question, they answer it as they meant it (that is one interruption);
  * shown the reading, they notice each wrong part with a fixed probability (the noticing rate) and
    correct it with the control the page offers; a wrong part with no control cannot be corrected.

The score is the outcome: a delivered list that is not the intended list is a wrong shortlist. No
random numbers are drawn; every "expected" figure is the exact average over what could be noticed.
Each request counts once however many meanings it has, so all totals are in requests.
"""
import argparse
import copy
import datetime
import itertools
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.environ["A2_LOG"] = "off"
# The recruiter's own saved changes (closed jobs, shortlists) must not leak into the run.
os.environ["A2_STATE"] = os.path.join(tempfile.gettempdir(), "a2-evaluation-no-state.json")

from compare import use  # noqa: E402  (points the app at one interpreter)

from assistant import interpret, search, server, strategy  # noqa: E402

REQUESTS = os.path.join(ROOT, "evaluation", "requests.json")
FROZEN_AT = "v1.2-a2"   # the rule, the stand-in interpreter, the search and the data were fixed here
FROZEN = ("assistant/strategy.py", "assistant/interpret.py", "assistant/search.py", "assistant/replies.py",
          "assistant/server.py", "data")     # model.py is left out: adding a live back-end does not change the rule
CONDITIONS = {"always act": "act", "always show": "show", "always ask": "ask", "adaptive": "auto"}
NOTICING = (1.0, 0.75, 0.5, 0.25)            # share of wrong shown parts the scripted recruiter spots
THETAS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
PARTS = ("skills_op", "seniority", "location", "availability", "target")


def load_cases(path=REQUESTS):
    """One case per request and intended meaning: {id, request, text, category, phrasing, intended, weight}.
    The weights of one request's cases add up to 1, so every request counts once."""
    with open(path, encoding="utf-8") as f:
        requests = json.load(f)["requests"]
    cases = []
    for r in requests:
        slots = sorted(r.get("open", {}))
        combos = list(itertools.product(*(r["open"][s] for s in slots)))
        for n, combo in enumerate(combos):
            intended = dict(copy.deepcopy(r["base"]), **dict(zip(slots, copy.deepcopy(combo))))
            cases.append({"id": "%s.%d" % (r["id"], n + 1) if slots else r["id"], "request": r["id"],
                          "text": r["text"], "category": r["category"], "phrasing": r.get("phrasing", ""),
                          "intended": intended, "weight": 1.0 / len(combos)})
    return cases


def ids(records):
    """A list as a set of record keys, so two lists can be compared whatever their order."""
    return frozenset((search.is_job(r), r["id"]) for r in records)


def intended_list(intended):
    """The right answer for a case: the search run on the meaning itself, with no interpreter involved."""
    return ids(search.search(dict({"target": "candidates", "skills": [], "skills_op": "AND"}, **intended)))


def part(reading, slot):
    """One part of a reading in a form that can be compared, keeping only what the search uses."""
    if slot == "skills_op":
        return reading.get("skills_op", "AND") if len(reading.get("skills") or []) > 1 else None
    if slot == "target":
        return reading.get("target") or "candidates"
    value = reading.get(slot)
    if not value:
        return None
    if slot == "location":
        return (value["value"], value.get("scope", "city"))
    if slot == "availability":
        return value["max_notice"]
    kind = value["kind"]
    return (kind, value.get("min") if kind != "title" else None,
            (value.get("contains") or "").lower() if kind != "years" else None)


def option_for(reading, slot, intended):
    """The index of the option, in a chip's menu or a question, that is what was meant; None if none is."""
    for amb in reading["ambiguities"]:
        if amb["slot"] == slot:
            for index, option in enumerate(amb["options"]):
                if part(interpret.apply_option(reading, option), slot) == part(intended, slot):
                    return index
    return None


def control_for(reading, slot, intended):
    """The control on the page that would set this part to what was meant: ("op", value) for the
    AND/OR chip, ("choice", index) for a chip's menu, or None if the page offers none."""
    if slot == "skills_op":
        return ("op", intended.get("skills_op", "AND")) if len(reading.get("skills") or []) > 1 else None
    index = option_for(reading, slot, intended)
    return None if index is None else ("choice", index)


def _turn(case, mode, theta, edits=(), last=None):
    """One request to the server, with the recruiter's edits so far. Returns (reply, records)."""
    payload = {"text": case["text"], "mode": mode, "theta": theta, "choices": {}}
    for slot, (kind, value) in edits:
        if kind == "op":
            payload["op"] = value
        else:
            payload["choices"][slot] = value
    if last:
        payload["last"] = last
    return server._run(payload)  # the same function the page's search uses; it also returns the records


def play(case, mode, theta=strategy.THETA):
    """One case under one strategy. Returns what happened, with the outcome for every set of wrong
    parts the recruiter might notice, so any noticing rate can be worked out afterwards."""
    right = intended_list(case["intended"])
    reply, records = _turn(case, mode, theta)
    if "error" in reply:  # "I can't search for that": nothing was delivered, which is not a wrong list
        return {"first": "nothing", "asked": False, "refused": True, "first_wrong": False,
                "lost": 0, "unwanted": 0, "wanted": len(right), "visible": False, "outcomes": [(0, False)]}
    first = reply["mode"]
    got = ids(records)
    out = {"first": first, "asked": first == "ask", "refused": False, "first_wrong": got != right,
           "ignored": list(reply.get("dropped", [])),
           "lost": len(right - got), "unwanted": len(got - right), "wanted": len(right)}
    edits = []
    if first == "ask":
        slot = reply["question"]["slot"]
        answer = option_for(reply["reading"], slot, case["intended"])
        # If no option is what they meant, they take the one already selected.
        edits.append((slot, ("choice", reply["question"]["default"] if answer is None else answer)))
        reply, records = _turn(case, mode, theta, edits, {"slot": slot, "answered": True})
    fixable = []
    if first != "act":  # after an act the recruiter takes the list as it is
        reading = reply["reading"]
        for slot in PARTS:
            if part(reading, slot) != part(case["intended"], slot):
                control = control_for(reading, slot, case["intended"])
                if control:
                    fixable.append((slot, control))
    out["visible"] = first != "act"
    outcomes = []
    for k in range(len(fixable) + 1):
        for noticed in itertools.combinations(fixable, k):
            if noticed:
                _, records = _turn(case, mode, theta, edits + list(noticed), {"slot": noticed[-1][0]})
            outcomes.append((k, ids(records) != right))
    out["outcomes"] = outcomes
    out["fixable"] = len(fixable)
    return out


def expected(result, notice):
    """(chance the delivered list is wrong, edits made) at a noticing rate, as exact averages."""
    n = result.get("fixable", 0)
    wrong = edits = 0.0
    for k, is_wrong in result["outcomes"]:
        p = (notice ** k) * ((1 - notice) ** (n - k))
        wrong += p * is_wrong
        edits += p * k
    return wrong, edits


def high_impact(result):
    """True when acting on the first reading loses at least half of the people wanted, or adds at
    least as many unwanted as were wanted. Measured against the intended list, not the rule's overlap."""
    if not result["first_wrong"]:
        return False
    wanted = result["wanted"]
    return (result["lost"] > 0 and 2 * result["lost"] >= wanted) or result["unwanted"] >= max(1, wanted)


def summarise(cases, results, notice):
    """Totals for one strategy at one noticing rate, in requests (each request counts once)."""
    total = {"interruptions": 0.0, "needless_questions": 0.0, "questions_on_clear": 0.0, "wrong": 0.0,
             "wrong_high_impact": 0.0, "wrong_on_clear": 0.0, "refused": 0.0, "edits": 0.0}
    for case, r in zip(cases, results):
        w = case["weight"]
        wrong, edits = expected(r, notice)
        total["interruptions"] += w * r["asked"]
        total["needless_questions"] += w * (r["asked"] and not r["first_wrong"])
        total["questions_on_clear"] += w * (r["asked"] and case["category"] == "clear")
        total["wrong"] += w * wrong
        total["wrong_high_impact"] += w * wrong * r["act_high_impact"]
        total["wrong_on_clear"] += w * wrong * (case["category"] == "clear")
        total["refused"] += w * r["refused"]
        total["edits"] += w * edits
    return {k: round(v, 3) for k, v in total.items()}


def frozen():
    """True if the files in FROZEN are exactly as released at FROZEN_AT, False if not, None if git can't say."""
    try:
        done = subprocess.run(["git", "diff", "--quiet", FROZEN_AT, "--"] + list(FROZEN), cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    return {0: True, 1: False}.get(done.returncode)


def run(interpreter="rules", path=REQUESTS):
    """The whole evaluation with one interpreter, as a dict ready to save."""
    use(interpreter)
    cases = load_cases(path)
    read, real = {}, interpret.interpret

    def once(text):
        # Each request is read once and the reading reused, so a live model gives every strategy the
        # same reading and its replies are on record.
        if text not in read:
            read[text] = real(text)
        return copy.deepcopy(read[text])

    interpret.interpret = once
    try:
        act = [play(c, "act") for c in cases]
        by_condition = {}
        for name, mode in CONDITIONS.items():
            results = act if mode == "act" else [play(c, mode) for c in cases]
            for r, a in zip(results, act):
                r["act_high_impact"] = high_impact(a)
            by_condition[name] = results
        sweep = {}
        for theta in THETAS:
            results = [play(c, "auto", theta) for c in cases]
            for r, a in zip(results, act):
                r["act_high_impact"] = high_impact(a)
            sweep[str(theta)] = {str(n): summarise(cases, results, n) for n in NOTICING}
    finally:
        interpret.interpret = real
        use("rules")
    requests = len({c["request"] for c in cases})
    rows = []
    for i, c in enumerate(cases):
        a = act[i]
        rows.append({"id": c["id"], "text": c["text"], "category": c["category"], "phrasing": c["phrasing"],
                     "intended": search.describe(dict({"skills": [], "ambiguities": []}, **c["intended"])),
                     "wanted": a["wanted"], "lost": a["lost"], "unwanted": a["unwanted"],
                     "high_impact": high_impact(a), "ignored": a.get("ignored", []),
                     "modes": {name: by_condition[name][i]["first"] for name in CONDITIONS},
                     "wrong_if_all_noticed": {name: expected(by_condition[name][i], 1.0)[0] for name in CONDITIONS}})
    return {
        "interpreter": interpreter,
        "date": datetime.date.today().isoformat(),
        "frozen_at": FROZEN_AT, "code_and_data_unchanged_since_freeze": frozen(),
        "theta": strategy.THETA, "requests": requests, "cases": len(cases),
        "clear_requests": len({c["request"] for c in cases if c["category"] == "clear"}),
        "high_impact_requests": round(sum(c["weight"] for c, a in zip(cases, act) if high_impact(a)), 3),
        "wrong_if_acted_on": round(sum(c["weight"] for c, a in zip(cases, act) if a["first_wrong"]), 3),
        "fell_back_to_stand_in": sorted(t for t, r in read.items()
                                        if interpreter != "rules" and r.get("source", "").startswith("rules")),
        "summary": {name: {str(n): summarise(cases, results, n) for n in NOTICING}
                    for name, results in by_condition.items()},
        "theta_sweep_adaptive": sweep,
        "rows": rows,
        "readings": {t: {k: v for k, v in r.items() if k != "ambiguities"} for t, r in read.items()},
    }


def markdown(result):
    """The run as tables: a summary per strategy and noticing rate, the threshold sweep, and every case."""
    out = ["# Scripted evaluation: %s" % result["interpreter"], "",
           "%d requests (%d clear controls), %d cases, θ = %s, run on %s. "
           "Rule, stand-in, search and data unchanged since %s: %s."
           % (result["requests"], result["clear_requests"], result["cases"], result["theta"], result["date"],
              result["frozen_at"], {True: "yes", False: "NO", None: "not checked"}[
                  result["code_and_data_unchanged_since_freeze"]]),
           "Acting on the first reading gives a wrong list for %s of the requests; %s are high impact."
           % (result["wrong_if_acted_on"], result["high_impact_requests"]), "",
           "All figures are in requests. Each request counts once however many meanings it has.", "",
           "| Strategy | Noticing rate | Questions | Needless questions | Wrong lists | High-impact wrong | "
           "Wrong on clear | Refused | Edits |", "|---|---|---|---|---|---|---|---|---|"]
    for name, by_notice in result["summary"].items():
        for notice, s in by_notice.items():
            out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                name, notice, s["interruptions"], s["needless_questions"], s["wrong"], s["wrong_high_impact"],
                s["wrong_on_clear"], s["refused"], s["edits"]))
            if name == "always act":
                break  # nothing is noticed after an act, so the rate changes nothing
    out += ["", "## The rule at other thresholds", "",
            "| θ | Questions | Wrong lists at noticing rate " + " | ".join(str(n) for n in NOTICING) + " |",
            "|---|---|" + "---|" * len(NOTICING)]
    for theta, by_notice in result["theta_sweep_adaptive"].items():
        out.append("| %s | %s | %s |" % (theta, by_notice["1.0"]["interruptions"],
                                         " | ".join(str(by_notice[str(n)]["wrong"]) for n in NOTICING)))
    out += ["", "## Every case", "",
            "| Case | Request | Meant | Wanted | Lost | Unwanted | High impact | act / show / ask / adaptive | "
            "Still wrong when everything shown is noticed |", "|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        still = [n for n, w in r["wrong_if_all_noticed"].items() if w]
        out.append("| %s | %s | %s | %d | %d | %d | %s | %s | %s |" % (
            r["id"], r["text"], r["intended"], r["wanted"], r["lost"], r["unwanted"],
            "yes" if r["high_impact"] else "", " / ".join(r["modes"][n] for n in CONDITIONS), ", ".join(still)))
    if result["fell_back_to_stand_in"]:
        out += ["", "The live model could not be used for: %s." % "; ".join(result["fell_back_to_stand_in"])]
    return "\n".join(out) + "\n"


def main(argv=None):
    """Parse the arguments, run each interpreter, print the tables and optionally save them."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--with", dest="interpreters", default="rules",
                        help="comma-separated: rules, ollama:<model>, claude, openai, bedrock")
    parser.add_argument("--out", help="a folder to write <interpreter>.json and <interpreter>.md into")
    args = parser.parse_args(argv)
    for name in (n.strip() for n in args.interpreters.split(",") if n.strip()):
        result = run(name)
        text = markdown(result)
        print(text)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            stem = os.path.join(args.out, name.replace(":", "-").replace("/", "-"))
            with open(stem + ".json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=1, ensure_ascii=False)
            with open(stem + ".md", "w", encoding="utf-8") as f:
                f.write(text)


if __name__ == "__main__":
    main()
