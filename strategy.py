"""Choose whether to act, show the reading, or ask one question, and say why.

    python3 strategy.py "senior Java developers in London"

The rule is a hand-set design choice (Horvitz 1999: thresholds "can be directly assessed by
designers"), not a learned policy. For each ambiguity it compares the shortlists the first two
readings would give:
    no ambiguity                                          -> act
    every ambiguity has a dominant reading, or its
    shortlists overlap at least THETA                     -> show
    otherwise                                             -> ask about the lowest-overlap ambiguity
"""
import json
import sys

import interpret
import search

# Below this overlap, two readings give clearly different shortlists, so a wrong guess is costly
# enough to ask. 0.5 = the two lists share fewer than half of their candidates.
THETA = 0.5

SLOT_WORDS = {"skills_op": "AND vs OR", "seniority": "'senior'", "location": "the location",
              "availability": "'available'", "target": "people vs jobs"}


FORCED = {"act": "Searched straight away with my best reading.",
          "show": "Showing my reading so you can edit it.",
          "ask": "Checking with you before searching."}


def slot_words(reading, slot):
    """How to name a slot in a reason; seniority quotes the word written ('senior' or 'lead')."""
    if slot == "seniority" and (reading.get("seniority") or {}).get("contains"):
        return "'%s'" % reading["seniority"]["contains"].lower()
    return SLOT_WORDS.get(slot, slot)


def _lists(c):
    """'5 vs 16', or 'two different groups of 1' when the sizes match but the people differ."""
    if c["chosen"] == c["other"]:
        return "two different groups of %d" % c["chosen"]
    return "%d vs %d" % (c["chosen"], c["other"])


def _run(reading, candidates):
    """Search; a test's own candidate list is used only for readings that search candidates."""
    use = candidates if reading.get("target", "candidates") == "candidates" else None
    return search.search(reading, use)


def _compare(reading, amb, candidates):
    """Shortlists for the chosen reading and its main alternative, and their overlap."""
    chosen = amb["chosen"]
    other = 1 if chosen == 0 else 0
    a = _run(interpret.apply_option(reading, amb["options"][chosen]), candidates)
    b = _run(interpret.apply_option(reading, amb["options"][other]), candidates)
    return {"slot": amb["slot"], "chosen": len(a), "other": len(b),
            "chosen_label": amb["labels"][chosen], "other_label": amb["labels"][other], "overlap": search.overlap(a, b),
            "dominant": amb["dominant"], "evidence": amb["evidence"]}


def decide(reading, theta=THETA, force=None, candidates=None):
    """Return {mode, reason, hint, ask_slot, comparisons}. force = 'act' | 'show' | 'ask' overrides the rule."""
    comps = [_compare(reading, a, candidates) for a in reading["ambiguities"]]
    askable = sorted((c for c in comps if not c["dominant"] and c["overlap"] < theta),
                     key=lambda c: c["overlap"])

    hint = None  # how to change the reading, from the screen; a frozen turn drops it
    if not comps:
        mode, reason = "act", "Nothing in your request was unclear, so I searched straight away."
    elif askable:
        c = askable[0]
        mode = "ask"
        reason = "Asking because %s gives two different lists (%s)." % (slot_words(reading, c["slot"]), _lists(c))
    else:
        mode = "show"
        low = [c for c in comps if c["overlap"] < theta]
        if low:
            c = low[0]
            if c["slot"] == "skills_op":
                op = reading["skills_op"]
                hint = "Tap %s ⇄ to switch to %s." % (op, "OR" if op == "AND" else "AND")
            else:
                hint = "Change it with the chip marked ▾."
            reason = "Used my reading because %s. Choosing %s would give a different list (%s). %s" % (
                c["evidence"], c["other_label"], _lists(c), hint)
        else:
            worst = min(c["overlap"] for c in comps)
            reason = "Showing my reading: the other choices change little (overlap %d%%)." % round(worst * 100)

    ask_slot = askable[0]["slot"] if askable else (
        min(comps, key=lambda c: c["overlap"])["slot"] if comps else None)
    rule_mode = mode  # what the rule chose, before any setting overrides it
    if force and force != mode:
        if force == "ask" and not comps:
            reason = "Nothing was unclear, so there is nothing to ask. Searched straight away."
            force = "act"
        else:
            # user-facing; the rule's own choice is in rule_mode, the Why? section and the log
            reason, hint = FORCED[force], None
        mode = force
    return {"mode": mode, "reason": reason, "hint": hint, "ask_slot": ask_slot if mode == "ask" else None,
            "theta": theta, "comparisons": comps, "rule_mode": rule_mode}


if __name__ == "__main__":
    r = interpret.interpret(" ".join(sys.argv[1:]))
    print(json.dumps(decide(r), indent=1))
