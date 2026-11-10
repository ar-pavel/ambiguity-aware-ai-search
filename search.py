"""Structured search over the synthetic candidates and jobs.

    python3 search.py --selftest

A reading is a plain dict (see interpret.py). Every filter is explicit, so the page can say exactly
why each record is in the list. There are no embeddings: matching is by canonical skill name.

A reading's "target" says what to search: "candidates" (the default) or "jobs". The same filters
work for both: a job's title, required skills, minimum years, city, work mode and company stand in
for a candidate's title, skills, years, city, work mode and current employer.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
TARGETS = ("candidates", "jobs")
DATA_FILES = TARGETS + ("companies",)

# Common shorthand mapped to the skill names used in the data.
SYNONYMS = {
    "js": "JavaScript", "javascript": "JavaScript", "ts": "TypeScript", "typescript": "TypeScript",
    "golang": "Go", "go": "Go", "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "py": "Python", "python": "Python", "java": "Java", "aws": "AWS", "amazon web services": "AWS",
    "react": "React", "reactjs": "React", "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "sap mm": "SAP MM", "sap sd": "SAP SD", "sap": "SAP", "sql": "SQL", "terraform": "Terraform",
}

# Towns counted as "near" a city when the location scope is "nearby".
NEARBY = {"London": ["Croydon", "Watford", "Slough", "Reading"]}

# Notice periods from shortest to longest, so "available within X" is a simple comparison.
NOTICE_ORDER = ["immediate", "2w", "1m", "3m"]


_CACHE = {}


def load(name="candidates"):
    """Records from data/<name>.json: 'candidates', 'jobs' or 'companies'. Read once, then reused."""
    if name not in DATA_FILES:  # never open a file named by anything else (e.g. a model reply)
        raise ValueError("unknown data set: %r" % (name,))
    if name not in _CACHE:
        with open(os.path.join(DATA_DIR, name + ".json"), encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def is_job(rec):
    return "min_years" in rec


def _title(rec):
    return rec["title"] if is_job(rec) else rec["current_title"]


def _years(rec):
    return rec["min_years"] if is_job(rec) else rec["years_experience"]


def canonical(skill):
    """Return the data's name for a skill, e.g. 'k8s' -> 'Kubernetes'."""
    return SYNONYMS.get(skill.strip().lower(), skill.strip())


def _skills_match(cand, skills, op):
    if not skills:
        return True
    have = {s.lower() for s in cand["skills"]}
    hits = [canonical(s).lower() in have for s in skills]
    return all(hits) if op == "AND" else any(hits)


def _location_match(cand, loc):
    if not loc:
        return True
    value, scope = loc["value"], loc.get("scope", "city")
    if scope == "country":
        return cand["country"].lower() == value.lower()
    if scope == "nearby":
        return cand["city"] == value or cand["city"] in NEARBY.get(value, [])
    return cand["city"].lower() == value.lower()


def _seniority_match(cand, sen):
    if not sen:
        return True
    by_years = _years(cand) >= sen.get("min", 0)
    by_title = sen.get("contains", "").lower() in _title(cand).lower()
    kind = sen["kind"]
    if kind == "years":
        return by_years
    if kind == "title":
        return by_title
    return by_years or by_title  # "either"


def _work_mode_match(cand, mode):
    return not mode or cand["work_mode"] == mode


def _company_match(rec, company):
    return not company or rec["company"] == company


def _status_match(rec, status):
    return not status or not is_job(rec) or rec["status"] == status


def _availability_match(cand, avail):
    if not avail or is_job(cand):  # jobs have no notice period
        return True
    return NOTICE_ORDER.index(cand["notice"]) <= NOTICE_ORDER.index(avail["max_notice"])


def search(reading, records=None):
    """Return the records (candidates or jobs, by the reading's target) that match every filter."""
    candidates = records if records is not None else load(reading.get("target") or "candidates")
    return [c for c in candidates
            if _skills_match(c, reading.get("skills", []), reading.get("skills_op", "AND"))
            and _location_match(c, reading.get("location"))
            and _seniority_match(c, reading.get("seniority"))
            and _availability_match(c, reading.get("availability"))
            and _work_mode_match(c, reading.get("work_mode"))
            and _company_match(c, reading.get("company"))
            and _status_match(c, reading.get("status"))]


# Shown under every result list, so nobody assumes more was searched than really was.
SEARCHED = {"candidates": "Searched candidates: job title, skills, years of experience, location, "
                          "notice period, work mode, current company.",
            "jobs": "Searched jobs: title, required skills, minimum years, location, work mode, company, status."}
NOT_SEARCHED = {"candidates": "Not searched: CV text, notes, emails.",
                "jobs": "Not searched: job descriptions, notes, emails."}


def describe_parts(reading):
    """One short phrase per filter that search() applies, keyed by slot (used by the chips)."""
    parts = {}
    jobs = reading.get("target") == "jobs"
    if jobs or any(a["slot"] == "target" for a in reading.get("ambiguities", [])):
        # candidates are the default, so that is said only when it was in doubt
        parts["target"] = ((reading.get("status") or "") + " jobs").strip() if jobs else "candidates"
    if reading.get("company"):
        parts["company"] = ("at " if jobs else "works at ") + reading["company"]
    loc = reading.get("location")
    if loc:
        parts["location"] = {"city": loc["value"], "nearby": "%s and nearby" % loc["value"],
                             "country": loc["value"]}[loc.get("scope", "city")]
    sen = reading.get("seniority")
    if sen:
        years = ("asks for %d+ years" if jobs else "%d+ years") % sen.get("min", 0)
        title = "'%s' in title" % sen.get("contains", "")
        parts["seniority"] = {"years": years, "title": title, "either": years + " or " + title}[sen["kind"]]
    av = reading.get("availability")
    if av and not jobs:
        parts["availability"] = {"immediate": "can start now", "2w": "notice ≤ 2 weeks",
                                 "1m": "notice ≤ 1 month", "3m": "notice ≤ 3 months"}[av["max_notice"]]
    if reading.get("work_mode"):
        parts["work_mode"] = reading["work_mode"]
    return parts


def describe(reading):
    """The 'Read as' line, built from the same filters search() applies (never from model text)."""
    skills = reading.get("skills") or []
    head = [(" %s " % reading.get("skills_op", "AND")).join(canonical(s) for s in skills)] if skills else []
    rest = describe_parts(reading)
    target = [rest.pop("target")] if "target" in rest else []
    parts = target + head + list(rest.values())
    if parts:
        return " · ".join(parts)
    return "all jobs (no filters)" if reading.get("target") == "jobs" else "everyone (no filters)"


def overlap(a, b):
    """Jaccard overlap of two shortlists. Both empty counts as 1. A job and a candidate never match."""
    ia, ib = {(is_job(c), c["id"]) for c in a}, {(is_job(c), c["id"]) for c in b}
    if not ia and not ib:
        return 1.0
    return len(ia & ib) / len(ia | ib)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        cands = load()
        assert len(cands) == 200 and len({c["id"] for c in cands}) == 200
        both = search({"skills": ["Java", "Python"], "skills_op": "AND"}, cands)
        either = search({"skills": ["Java", "Python"], "skills_op": "OR"}, cands)
        assert len(both) < len(either)
        print("ok: %d candidates" % len(cands))
