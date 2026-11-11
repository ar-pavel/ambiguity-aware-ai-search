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
COMPANIES = [c["name"] for c in search.load("companies")]
DEFAULT_YEARS = 5  # what "senior" means in years when it is read as experience
SLOTS = ("skills_op", "seniority", "location", "availability", "target")
JOB_WORDS = r"\b(jobs?|roles?|vacanc(?:y|ies)|openings?|postings?)\b"  # not 'position': "a senior position"
PEOPLE_WORDS = r"\b(candidates?|people|person|someone|anyone|profiles?)\b"


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
    elif slot == "target":
        at = " at " + reading["company"] if reading.get("company") else ""
        options = [{"target": "candidates"}, {"target": "jobs"}]
        labels = ["people who work%s" % at if at else "candidates", "jobs" + at]
        chosen = 0 if reading["target"] == "candidates" else 1
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
        if near and city in search.NEARBY:  # only offer "nearby" where nearby towns are known
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


def _company(text):
    """The company named, by full name or its first word ('at Northwind'), as (name, words) or (None, None)."""
    for name in COMPANIES:
        for term in (name, name.split()[0]):
            m = re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE)
            if m:
                return name, m.group(0)
    return None, None


def _target(text, company_words):
    """(target, ambiguity_or_None). People are searched by default; job words switch to jobs.
    Both kinds of word ("candidates for the Python role") mean people, shown as a chip so it can be
    switched. A company with neither kind of word is unclear: people who work there, or its jobs?"""
    job = re.search(JOB_WORDS, text, re.IGNORECASE)
    people = re.search(PEOPLE_WORDS, text, re.IGNORECASE)
    if job and people:
        return "candidates", (True, "you wrote '%s' and '%s'" % (people.group(0), job.group(0)))
    if job:
        return "jobs", None
    if people or not company_words:
        return "candidates", None
    return "candidates", (False, "you wrote '%s' but not whether you want people or jobs" % company_words)


def _status(text):
    """'open' or 'closed', kept whatever the target, so it still applies if the target is switched to
    jobs. It only filters jobs (candidates have no status)."""
    m = re.search(r"\b(open|closed)\b", text, re.IGNORECASE)
    return m.group(1).lower() if m else None


def for_target(reading):
    """Jobs have no notice period: drop availability and say so, rather than silently ignore it.
    Run on every reading once its target is final, including after the recruiter switches it."""
    if reading["target"] == "jobs" and reading.get("availability"):
        reading["availability"] = None
        reading["dropped"] = reading.get("dropped", []) + ["availability (jobs have no notice period)"]
        reading["ambiguities"] = [a for a in reading["ambiguities"] if a["slot"] != "availability"]
    return reading


# ---- What the request asks for that the search cannot do --------------------------------------------
# The reading lists these as "unsupported", so the page can say so instead of searching without them.
# The reason shown is chosen by code from the kind, never written by a model.
WHY = {"name": "searching by name is not supported",
       "place": "not a place in the data",
       "other": "not something I can search by"}

# Words that carry no filter: asking for everyone ("show me all candidates") uses only these.
FILLER = set("""
show me find get give list search look looking for i we need want see who are is be with and or the a an
of all any every everyone everybody anyone anybody some please our my candidate candidates people person
someone profile profiles
""".split())

_WORD = r"[A-Za-z0-9][A-Za-z0-9'+#.-]*"


def has_filters(reading):
    """True when the reading names anything the search can filter on."""
    return bool(reading["skills"]) or bool(search.describe_parts(reading))


def asks_for_everyone(text):
    """True when every word only asks for everyone ("show me all candidates"), so no filter is meant."""
    words = re.findall(_WORD, text)
    return bool(words) and all(w.lower() in FILLER for w in words)


def _known_word(word):
    """True if the word is something the search knows: a place, a company word, a skill or a target."""
    low = word.lower()
    return (low in COUNTRIES or any(c.lower() == low for c in CITIES)
            or any(low in n.lower().split() for n in COMPANIES) or low in search.SYNONYMS
            or re.fullmatch(JOB_WORDS + "|" + PEOPLE_WORDS, low, re.I) is not None)


def unsupported_rules(text, reading):
    """The stand-in's guess at what the request asks for that the search cannot do (simulated):
    a name ("named Matin", "called Matin"), a place the data doesn't know ("near Narnia"), or, when
    nothing could be searched, the words left over ("hello")."""
    found = []
    named = re.search(r"\bnamed\s+(" + _WORD + ")", text, re.I) or re.search(r"\bcalled\s+([A-Z][A-Za-z'-]*)", text)
    if named:
        found.append({"text": named.group(0), "kind": "name"})
    for m in re.finditer(r"\b(near|around|from|based in|in)\s+([A-Z][A-Za-z-]+)", text):
        if not _known_word(m.group(2)) and not any(m.group(0) in f["text"] for f in found):
            found.append({"text": m.group(0), "kind": "place" if m.group(1).lower() != "in" else "other"})
    if not has_filters(reading) and not asks_for_everyone(text):
        covered = " ".join(f["text"] for f in found).lower().split()
        rest = [w for w in re.findall(_WORD, text) if w.lower() not in FILLER and w.lower() not in covered]
        if rest:
            found.append({"text": " ".join(rest), "kind": "other"})
    return found


def checked_unsupported(items, text):
    """Keep only what the user really wrote, with a known kind (the model may not invent requests)."""
    out = []
    for item in items or []:
        quote = str(item.get("text", "")).strip()[:60]
        seen = [o["text"].lower() for o in out]
        if item.get("kind") in WHY and quote and _written(quote, text) and quote.lower() not in seen:
            out.append({"text": quote, "kind": item["kind"]})
    return out[:3]


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
    company, company_words = _company(text)
    target, target_amb = _target(text, company_words)
    reading = {"target": target, "skills": [s[2] for s in spans], "skills_op": op, "location": location,
               "seniority": seniority, "availability": availability, "work_mode": _work_mode(text),
               "company": company, "status": _status(text)}
    judged = zip(SLOTS, (op_amb, sen_amb, loc_amb, av_amb, target_amb))
    reading["ambiguities"] = [make_ambiguity(slot, reading, *j) for slot, j in judged if j]
    reading["ambiguities"] += _phrase_ambiguities(spans)
    reading["unsupported"] = unsupported_rules(text, reading)
    reading["source"] = "rules"
    return for_target(reading)


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


def _written(term, text):
    """True if the term appears in the text as a whole word (so 'Go' is not found in 'good')."""
    return re.search(r"(?<![\w.])" + re.escape(term) + r"(?![\w.])", text, re.IGNORECASE) is not None


def _checked_evidence(evidence, text):
    """Keep the model's evidence only if the words it quotes are really in the request."""
    quoted = re.findall(r"'([^']+)'", evidence or "")
    if quoted and all(q.lower() in text.lower() for q in quoted):
        return "you wrote " + ", ".join("'%s'" % q for q in quoted)
    return "from your request"


def _known_place(value):
    """Map a place the model named to one the data knows ('London, UK' -> 'London'), or None."""
    for part in [value] + [p.strip() for p in value.split(",")]:
        low = part.lower()
        if low in COUNTRIES:
            return COUNTRIES[low]
        for city in CITIES:
            if city.lower() == low:
                return city
    return None


def from_model(text, judged):
    """Check the model's judgement and build a reading from it. Returns None if it can't be trusted.

    The model judges; code checks. A skill the user never wrote is dropped (the model may not add
    requirements), a place the data doesn't know is dropped rather than silently matching nobody,
    and every option is built by make_ambiguity(), exactly as for the rules route."""
    skills, dropped = [], []
    for s in judged.get("skills", []):
        name = search.canonical(s)
        aliases = [s, name] + [k for k, v in search.SYNONYMS.items() if v == name]
        if any(_written(a, text) for a in aliases):
            if name not in skills:
                skills.append(name)
        else:
            dropped.append("skill '%s' (not in your request)" % s)
    location = judged["location"]
    if location:
        place = _known_place(location["value"])
        if place is None:
            dropped.append("location '%s' (not in the data)" % location["value"])
            location = None
        else:
            if place in COUNTRIES.values():
                scope = "country"
            else:  # a city: keep "nearby" if the model said so, otherwise the city itself
                scope = "nearby" if location["scope"] == "nearby" and place in search.NEARBY else "city"
            location = {"value": place, "scope": scope}
    company = judged.get("company")
    if company:
        known = next((n for n in COMPANIES if n.lower() == company.lower()), None)
        if known is None or not (_written(known, text) or _written(known.split()[0], text)):
            dropped.append("company '%s' (not in your request or not in the data)" % company)
            known = None
        company = known
    target = judged["target"]
    if target not in search.TARGETS:
        return None  # an unexpected target is an unusable reply: the rules are used instead
    status = judged.get("status")
    if status not in (None, "open", "closed"):
        dropped.append("status '%s' (jobs are only open or closed)" % status)
        status = None
    reading = {"target": target, "company": company,
               "status": status,
               "skills": skills, "skills_op": judged["skills_op"], "location": location,
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
        if slot == "location" and present and reading["location"]["value"] not in search.NEARBY:
            present = False  # no nearby towns are known for this city, so there is nothing to choose
        if present and slot not in seen:
            seen.add(slot)
            ambiguities.append(make_ambiguity(slot, reading, a["dominant"], _checked_evidence(a["evidence"], text)))
    phrases = [(0, 0, s) for s in skills]
    reading["ambiguities"] = ambiguities + _phrase_ambiguities(phrases)
    reading["dropped"] = dropped
    reading["unsupported"] = checked_unsupported(judged.get("unsupported"), text)
    return for_target(reading)


def interpret(text):
    """Use the live model when configured, otherwise the rules. Always returns a valid reading."""
    import model
    if model.live():
        judged = model.judge(text)
        try:
            reading = from_model(text, judged) if judged else None
        except (KeyError, TypeError, ValueError, AttributeError):
            reading = None  # a reply that doesn't match the schema is treated like no reply
        if reading is not None:
            reading["source"] = model.label()
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
