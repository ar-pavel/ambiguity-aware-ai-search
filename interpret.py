"""Turn a plain-language request into one structured reading plus its ambiguities.

    python3 interpret.py "senior Java developers in London"
    python3 interpret.py --selftest

Two routes, same output shape:
  * rules (default, SIMULATED): a small rule-based stand-in for the language model. It follows the
    detection rules in the design spec, so it works with no key and no network.
  * live (IMPLEMENTED, needs your own key): model.py asks Claude to judge the request with
    structured outputs; from_model() checks the reply and builds the same shape. If anything fails,
    the rules route is used and the page says so.

The reading is the single object the page uses for the chips, the question, the "Read as" line and
the search. Each ambiguity lists its options as small patches to the reading, the option chosen by
default, whether one reading is dominant, and the words in the request that are the evidence.
"""
import json
import re
import sys

import search

CITIES = sorted({c["city"] for c in search.load()}, key=len, reverse=True)
COUNTRIES = {"uk": "UK", "united kingdom": "UK", "ireland": "Ireland"}
SKILL_TERMS = sorted(search.SYNONYMS, key=len, reverse=True)  # longest first, so "sap mm" beats "sap"
DEFAULT_YEARS = 5  # what "senior" means in years when it is read as experience
SLOTS = ("skills_op", "seniority", "location", "availability")


def make_ambiguity(slot, reading, dominant, evidence):
    """Build one ambiguity (options, labels, chosen) from the reading's current value for a slot.
    Both interpreter routes use this, so the chips and the question look the same either way."""
    if slot == "skills_op":
        options = [{"skills_op": "AND"}, {"skills_op": "OR"}]
        labels = ["all of these skills (AND)", "any of these skills (OR)"]
        chosen = 0 if reading["skills_op"] == "AND" else 1
    elif slot == "seniority":
        sen = reading["seniority"]
        w = sen.get("contains") or "Senior"
        years = sen.get("min") or DEFAULT_YEARS
        options = [{"seniority": {"kind": "years", "min": years}},
                   {"seniority": {"kind": "title", "contains": w}},
                   {"seniority": {"kind": "either", "min": years, "contains": w}}]
        labels = ["%d+ years' experience" % years, "'%s' in their job title" % w, "either"]
        chosen = {"years": 0, "title": 1, "either": 2}[sen["kind"]]
    elif slot == "location":
        city = reading["location"]["value"]
        options = [{"location": {"value": city, "scope": "nearby"}},
                   {"location": {"value": city, "scope": "city"}}]
        labels = ["%s and nearby towns" % city, "%s only" % city]
        chosen = 0 if reading["location"]["scope"] == "nearby" else 1
    else:
        options = [{"availability": {"max_notice": "immediate"}},
                   {"availability": {"max_notice": "2w"}}]
        labels = ["can start immediately", "notice of 2 weeks or less"]
        chosen = 0 if reading["availability"]["max_notice"] == "immediate" else 1
    return {"slot": slot, "options": options, "labels": labels, "chosen": chosen,
            "dominant": bool(dominant), "evidence": evidence}


def _find_skills(text):
    """Return [(start, end, canonical_name)] for each skill mentioned, in order, without overlaps."""
    found, taken = [], []
    for term in SKILL_TERMS:
        for m in re.finditer(r"(?<![\w.])" + re.escape(term) + r"(?![\w.])", text, re.IGNORECASE):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), m.end(), search.canonical(term)))
    found.sort()
    unique, seen = [], set()
    for s, e, name in found:
        if name not in seen:
            seen.add(name)
            unique.append((s, e, name))
    return unique


def _operator(text, spans):
    """Return (op, ambiguity_or_None) for the words between the first and last skill."""
    if len(spans) < 2:
        return "AND", None
    between = text[spans[0][1]:spans[-1][0]]
    if re.search(r"\bOR\b", between):
        return "OR", None                     # typed in capitals: stated, not ambiguous
    if re.search(r"\bAND\b", between):
        return "AND", None
    word = re.search(r"\b(and|with|or)\b|&", between, re.IGNORECASE)
    if word:
        op = "OR" if word.group(0).lower() == "or" else "AND"
        return op, (True, "you wrote '%s'" % word.group(0))
    return "AND", (False, "no 'and' or 'or' between the skills")


def _seniority(text):
    low = text.lower()
    years = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", low)
    if years:
        return {"kind": "years", "min": int(years.group(1))}, None
    titled = re.search(r"(senior|lead)\b[^.]*\b(title|titled)\b|\btitled\s+(senior|lead)", low)
    if titled:
        word = (titled.group(1) or titled.group(3)).capitalize()
        return {"kind": "title", "contains": word}, None
    word = re.search(r"\b(senior|lead)\b", low)
    if not word:
        return None, None
    return ({"kind": "years", "min": DEFAULT_YEARS, "contains": word.group(1).capitalize()},
            (False, "you wrote '%s'" % word.group(1)))


def _location(text):
    low = text.lower()
    for key, country in COUNTRIES.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            return {"value": country, "scope": "country"}, None
    for city in CITIES:
        near = re.search(r"\b(near|around|within[^,]*?of|commutable to)\s+" + city.lower() + r"\b", low)
        if near:
            return {"value": city, "scope": "nearby"}, (False, "you wrote '%s'" % near.group(1))
        if re.search(r"\b" + city.lower() + r"\b", low):
            return {"value": city, "scope": "city"}, None
    return None, None


def _availability(text):
    low = text.lower()
    weeks = re.search(r"(?:in|within)\s+(\d+)\s*weeks?", low)
    if weeks:
        return {"max_notice": "2w" if int(weeks.group(1)) <= 2 else "1m"}, None
    word = re.search(r"\b(available now|immediately|available|now|asap)\b", low)
    if not word:
        return None, None
    return {"max_notice": "immediate"}, (False, "you wrote '%s'" % word.group(1))


def _work_mode(text):
    m = re.search(r"\b(remote|hybrid|on-?site)\b", text, re.IGNORECASE)
    return m and m.group(1).lower().replace("on-site", "onsite")


def _phrase_ambiguities(spans):
    """A multi-word skill such as 'SAP MM' is kept as one phrase; show that choice as a chip."""
    out = []
    for _, _, name in spans:
        if " " in name:
            parts = name.split()
            out.append({"slot": "phrase:" + name,
                        "options": [{"phrase": name}, {"split": parts}],
                        "labels": ["'%s' as one skill" % name, " and ".join(parts) + " separately"],
                        "chosen": 0, "dominant": True,
                        "evidence": "'%s' is a known skill name" % name})
    return out


def interpret_rules(text):
    """The simulated interpreter: deterministic rules that mimic the model's job."""
    spans = _find_skills(text)
    op, op_amb = _operator(text, spans)
    seniority, sen_amb = _seniority(text)
    location, loc_amb = _location(text)
    availability, av_amb = _availability(text)
    reading = {"skills": [s[2] for s in spans], "skills_op": op, "location": location,
               "seniority": seniority, "availability": availability, "work_mode": _work_mode(text)}
    judged = zip(SLOTS, (op_amb, sen_amb, loc_amb, av_amb))
    reading["ambiguities"] = [make_ambiguity(slot, reading, *j) for slot, j in judged if j]
    reading["ambiguities"] += _phrase_ambiguities(spans)
    reading["source"] = "rules"
    return reading


def apply_option(reading, option):
    """Return a copy of the reading with one option patched in (used by chips and the rule)."""
    out = json.loads(json.dumps(reading))
    if "split" in option:
        phrase = " ".join(option["split"])
        out["skills"] = [s for s in out["skills"] if s != phrase] + option["split"]
        out["skills_op"] = "AND"
    elif "phrase" not in option:
        out.update(option)
    return out


def from_model(text, judged):
    """Check the model's judgement and build a reading from it. Returns None if it can't be trusted.

    The model judges; code checks. A skill the user never wrote is dropped (the model may not add
    requirements), and every option is built by make_ambiguity(), exactly as for the rules route."""
    low = text.lower()
    skills, dropped = [], []
    for s in judged.get("skills", []):
        name = search.canonical(s)
        if s.lower() in low or name.lower() in low:
            if name not in skills:
                skills.append(name)
        else:
            dropped.append(s)
    reading = {"skills": skills, "skills_op": judged["skills_op"], "location": judged["location"],
               "seniority": judged["seniority"], "work_mode": judged["work_mode"],
               "availability": {"max_notice": judged["availability"]} if judged["availability"] else None}
    if reading["seniority"]:
        sen = {k: v for k, v in reading["seniority"].items() if v is not None}
        if sen["kind"] == "years" and "min" not in sen:
            return None
        if sen["kind"] == "title" and not sen.get("contains"):
            return None
        reading["seniority"] = sen
    ambiguities, seen = [], set()
    for a in judged.get("ambiguities", []):
        slot = a["slot"]
        present = reading.get(slot) if slot != "skills_op" else len(skills) > 1
        if present and slot not in seen:
            seen.add(slot)
            ambiguities.append(make_ambiguity(slot, reading, a["dominant"], a["evidence"]))
    phrases = [(0, 0, s) for s in skills]
    reading["ambiguities"] = ambiguities + _phrase_ambiguities(phrases)
    reading["dropped"] = dropped
    return reading


def interpret(text):
    """Use the live model when configured, otherwise the rules. Always returns a valid reading."""
    import model
    if model.live():
        judged = model.judge(text)
        reading = from_model(text, judged) if judged else None
        if reading is not None:
            reading["source"] = "Claude (%s)" % model.MODEL
            return reading
        fallback = interpret_rules(text)
        fallback["source"] = "rules (the live model was unavailable or its reply was unusable)"
        return fallback
    return interpret_rules(text)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        r = interpret_rules("senior Java developers in London")
        assert r["skills"] == ["Java"] and r["ambiguities"][0]["slot"] == "seniority"
        print("ok: rules interpreter")
    else:
        print(json.dumps(interpret(" ".join(sys.argv[1:])), indent=1))
