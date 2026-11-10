"""Structured search over the synthetic candidates.

    python3 search.py --selftest

A reading is a plain dict (see interpret.py). Every filter is explicit, so the page can say exactly
why each candidate is in the list. There are no embeddings: matching is by canonical skill name.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "candidates.json")

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


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


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
    by_years = cand["years_experience"] >= sen.get("min", 0)
    by_title = sen.get("contains", "").lower() in cand["current_title"].lower()
    kind = sen["kind"]
    if kind == "years":
        return by_years
    if kind == "title":
        return by_title
    return by_years or by_title  # "either"


def _availability_match(cand, avail):
    if not avail:
        return True
    return NOTICE_ORDER.index(cand["notice"]) <= NOTICE_ORDER.index(avail["max_notice"])


def search(reading, candidates=None):
    """Return the candidates that match every filter in the reading."""
    candidates = candidates if candidates is not None else load()
    return [c for c in candidates
            if _skills_match(c, reading.get("skills", []), reading.get("skills_op", "AND"))
            and _location_match(c, reading.get("location"))
            and _seniority_match(c, reading.get("seniority"))
            and _availability_match(c, reading.get("availability"))]


def overlap(a, b):
    """Jaccard overlap of two shortlists (lists of candidates). Both empty counts as 1."""
    ia, ib = {c["id"] for c in a}, {c["id"] for c in b}
    if not ia and not ib:
        return 1.0
    return len(ia & ib) / len(ia | ib)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        cands = load()
        assert len(cands) == 40 and len({c["id"] for c in cands}) == 40
        both = search({"skills": ["Java", "Python"], "skills_op": "AND"}, cands)
        either = search({"skills": ["Java", "Python"], "skills_op": "OR"}, cands)
        assert len(both) < len(either)
        print("ok: %d candidates" % len(cands))
