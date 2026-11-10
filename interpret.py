"""Turn a plain-language request into one structured reading plus its ambiguities.

    python3 interpret.py "senior Java developers in London"
    python3 interpret.py --selftest

Two routes, same output shape:
  * rules (default, SIMULATED): a small rule-based stand-in for the language model. It follows the
    detection rules in the design spec, so it works with no key and no network.
  * live (IMPLEMENTED, needs your own key): model.py asks a language model for the same JSON shape.
    The reply is validated; if it is unusable the rules route is used and the page says so.

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
    options = [{"skills_op": "AND"}, {"skills_op": "OR"}]
    labels = ["all of these skills (AND)", "any of these skills (OR)"]
    if word:
        op = "OR" if word.group(0).lower() == "or" else "AND"
        return op, {"slot": "skills_op", "options": options, "labels": labels,
                    "chosen": 0 if op == "AND" else 1, "dominant": True,
                    "evidence": "you wrote '%s'" % word.group(0)}
    return "AND", {"slot": "skills_op", "options": options, "labels": labels,
                   "chosen": 0, "dominant": False, "evidence": "no 'and' or 'or' between the skills"}


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
    w = word.group(1).capitalize()
    options = [{"seniority": {"kind": "years", "min": DEFAULT_YEARS}},
               {"seniority": {"kind": "title", "contains": w}},
               {"seniority": {"kind": "either", "min": DEFAULT_YEARS, "contains": w}}]
    labels = ["%d+ years' experience" % DEFAULT_YEARS, "'%s' in their job title" % w, "either"]
    return options[0]["seniority"], {"slot": "seniority", "options": options, "labels": labels,
                                     "chosen": 0, "dominant": False,
                                     "evidence": "you wrote '%s'" % word.group(1)}


def _location(text):
    low = text.lower()
    for key, country in COUNTRIES.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            return {"value": country, "scope": "country"}, None
    for city in CITIES:
        near = re.search(r"\b(near|around|within[^,]*?of|commutable to)\s+" + city.lower() + r"\b", low)
        if near:
            options = [{"location": {"value": city, "scope": "nearby"}},
                       {"location": {"value": city, "scope": "city"}}]
            labels = ["%s and nearby towns" % city, "%s only" % city]
            return options[0]["location"], {"slot": "location", "options": options, "labels": labels,
                                             "chosen": 0, "dominant": False,
                                             "evidence": "you wrote '%s'" % near.group(1)}
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
    options = [{"availability": {"max_notice": "immediate"}},
               {"availability": {"max_notice": "2w"}}]
    labels = ["can start immediately", "notice of 2 weeks or less"]
    return options[0]["availability"], {"slot": "availability", "options": options, "labels": labels,
                                        "chosen": 0, "dominant": False,
                                        "evidence": "you wrote '%s'" % word.group(1)}


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
    reading["ambiguities"] = [a for a in (op_amb, sen_amb, loc_amb, av_amb) if a] + _phrase_ambiguities(spans)
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


def interpret(text):
    """Use the live model when configured, otherwise the rules. Always returns a valid reading."""
    import model
    if model.live():
        reading = model.interpret(text)
        if reading is not None:
            reading["source"] = "live"
            return reading
        fallback = interpret_rules(text)
        fallback["source"] = "rules (live model reply was unusable)"
        return fallback
    return interpret_rules(text)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        r = interpret_rules("senior Java developers in London")
        assert r["skills"] == ["Java"] and r["ambiguities"][0]["slot"] == "seniority"
        print("ok: rules interpreter")
    else:
        print(json.dumps(interpret(" ".join(sys.argv[1:])), indent=1))
