"""What the page shows, built only from what ran: the results table, the chips, the one question,
the sentence after an edit, and the "Why?" section.

Nothing here decides anything or calls a model. Every word is built from the reading the search used
and the numbers strategy.decide() returned, so the screen cannot claim more than the code did.
"""
import interpret
import search
import strategy

NOTICE = {"immediate": "now", "2w": "2 weeks", "1m": "1 month", "3m": "3 months"}
# The results table for each target: (header, how to show one record's cell).
COLUMNS = {
    "candidates": [("Name", "name"), ("Title", "current_title"), ("Skills", "skills"),
                   ("Years", "years_experience"), ("City", "city"), ("Company", "company"),
                   ("Work mode", "work_mode"), ("Notice", "notice")],
    "jobs": [("Job", "title"), ("Company", "company"), ("Skills", "skills"), ("Min. years", "min_years"),
             ("City", "city"), ("Work mode", "work_mode"), ("Status", "status"), ("Shortlist", "shortlist")],
}


def cell(rec, key):
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
    return {"headers": [h for h, _ in cols], "rows": [[cell(r, k) for _, k in cols] for r in records]}


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


def pct(x, theta):
    """A share as a percentage; one decimal when rounding would hide which side of θ it is on."""
    whole = round(x * 100)
    if whole == round(theta * 100) and x != theta:
        return "%.1f%%" % (x * 100)
    return "%d%%" % whole


def why(reading, decision, edited, forced, anyway=False):
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
                     "overlap": round(c["overlap"], 2), "share": pct(c["overlap"], theta), "dominant": c["dominant"], "verdict": verdict})
    if not rows:
        summary = "Nothing in the request was unclear, so there was nothing to compare: act."
    else:
        summary = "The rule compares the lists each unclear part could give. It asks only when a part has no clear reading and its lists share less than θ = %d%%." % round(theta * 100)
    notes = []
    if anyway:  # the recruiter skipped the question; no setting was involved
        notes.append("You chose to search without answering; the rule would have asked first.")
    elif forced:
        notes.append("The strategy setting chose %s; the rule alone would have chosen %s." % (decision["mode"], decision["rule_mode"]))
    if edited:
        notes.append("You changed the reading, so the chips stay in view. The rows describe the reading as it is now.")
    return {"summary": summary, "rows": rows, "theta": theta, "rule_mode": decision["rule_mode"], "notes": notes}


def interpreter_label(source):
    """Say plainly which interpreter read the request, using the agreed status words."""
    if source == "rules":
        return "rule-based stand-in (simulated)"
    if source.startswith("rules"):  # live mode was on but the model could not be used
        return "rule-based stand-in (simulated): the live model was unavailable or its reply was unusable"
    return source
