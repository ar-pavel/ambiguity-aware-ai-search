"""Build the synthetic data set. Everything here is invented: no real people, companies or jobs.

    python3 data/generate.py

Keeps the 40 hand-built candidates in data/core_candidates.json (they carry the ambiguity design the
tests rely on), gives every candidate a company, and adds generated candidates, companies and jobs.
A fixed seed means running it again gives exactly the same files.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 26
N_EXTRA = 160  # 40 hand-built + 160 generated = 200 candidates

COMPANIES = [  # invented names
    ("Northwind Labs", "London", "Fintech"), ("Bluefin Analytics", "London", "Data"),
    ("Harbor & Pine", "Manchester", "Retail"), ("Copperleaf Systems", "Leeds", "Software"),
    ("Brightwater Health", "Birmingham", "Healthcare"), ("Kestrel Logistics", "Reading", "Logistics"),
    ("Quillmark Media", "London", "Media"), ("Ironbridge Bank", "London", "Banking"),
    ("Saltmarsh Energy", "Leeds", "Energy"), ("Oakline Insurance", "Croydon", "Insurance"),
    ("Tidewater Games", "Watford", "Games"), ("Granite Cloud", "Slough", "Cloud"),
    ("Fernhill Retail", "Birmingham", "Retail"), ("Lumen Mobility", "Manchester", "Transport"),
    ("Wrenfield Software", "Dublin", "Software"), ("Silverbirch Consulting", "London", "Consulting"),
    ("Moorgate Payments", "London", "Fintech"), ("Hollowell Pharma", "Reading", "Healthcare"),
]

FIRST = ["Aisha", "Ben", "Carla", "Daniel", "Eve", "Farah", "George", "Hana", "Imran", "Jade", "Karl",
         "Leah", "Mohammed", "Nina", "Oscar", "Pia", "Rahul", "Sara", "Tom", "Uma", "Victor", "Wen",
         "Yara", "Zain", "Alice", "Bilal", "Chen", "Diana", "Emre", "Freya", "Hugo", "Ines", "Jamal",
         "Kira", "Luca", "Maya", "Nils", "Olga", "Priya", "Ravi"]
LAST = ["Adams", "Bose", "Clarke", "Dunn", "Ellis", "Fox", "Gill", "Hart", "Iqbal", "Jones", "Khan",
        "Lowe", "Mehta", "Nolan", "Owens", "Patel", "Quinn", "Reyes", "Shah", "Turner", "Usman", "Vance",
        "Walsh", "Xu", "Young", "Zhou", "Barker", "Cole", "Doyle", "Evans"]

ROLES = [  # (title stem, skill pool)
    ("Java Developer", ["Java", "Spring", "SQL", "Kotlin", "AWS"]),
    ("Python Developer", ["Python", "Django", "Flask", "SQL", "AWS"]),
    ("Backend Engineer", ["Java", "Python", "Go", "SQL", "Kubernetes", "AWS"]),
    ("Frontend Developer", ["JavaScript", "React", "TypeScript", "Vue"]),
    ("Full Stack Engineer", ["JavaScript", "React", "Node.js", "Python", "AWS"]),
    ("Data Engineer", ["Python", "SQL", "AWS", "Java"]),
    ("DevOps Engineer", ["AWS", "Kubernetes", "Terraform", "Python", "Go"]),
    ("Machine Learning Engineer", ["Python", "PyTorch", "SQL"]),
    ("SAP Consultant", ["SAP", "SAP MM", "SAP SD"]),
]
CITIES = ["London"] * 6 + ["Croydon", "Watford", "Slough", "Reading", "Manchester", "Manchester",
                          "Leeds", "Birmingham", "Birmingham", "Dublin"]
NOTICE = ["immediate", "2w", "2w", "1m", "1m", "3m"]
MODES = ["remote", "hybrid", "hybrid", "onsite"]


def title_for(rng, stem, years):
    """Titles don't always match experience, on purpose: that is what makes 'senior' ambiguous."""
    roll = rng.random()
    if years >= 8 and roll < 0.45 or years >= 4 and roll < 0.15:
        return ("Lead " if rng.random() < 0.2 else "Senior ") + stem
    return stem


def build():
    """The candidates, companies and jobs, the same every time for the same SEED."""
    rng = random.Random(SEED)
    with open(os.path.join(HERE, "core_candidates.json"), encoding="utf-8") as f:
        core = json.load(f)
    companies = [{"id": i + 1, "name": n, "city": c, "industry": ind} for i, (n, c, ind) in enumerate(COMPANIES)]
    by_city = {}
    for co in companies:
        by_city.setdefault(co["city"], []).append(co["name"])

    def company_in(city):
        return rng.choice(by_city.get(city, [c["name"] for c in companies]))

    candidates = [dict(c, company=company_in(c["city"])) for c in core]
    names = {c["name"] for c in candidates}
    while len(candidates) < len(core) + N_EXTRA:
        name = "%s %s" % (rng.choice(FIRST), rng.choice(LAST))
        if name in names:
            continue
        names.add(name)
        stem, pool = rng.choice(ROLES)
        years = rng.randint(1, 15)
        city = rng.choice(CITIES)
        skills = rng.sample(pool, k=min(len(pool), rng.randint(1, 3)))
        candidates.append({"id": len(candidates) + 1, "name": name, "current_title": title_for(rng, stem, years),
                           "skills": skills, "years_experience": years, "city": city,
                           "country": "Ireland" if city == "Dublin" else "UK",
                           "work_mode": rng.choice(MODES), "notice": rng.choice(NOTICE),
                           "company": company_in(city)})

    jobs = []
    for i in range(30):
        stem, pool = rng.choice(ROLES)
        co = rng.choice(companies)
        senior = rng.random() < 0.4
        jobs.append({"id": i + 1, "title": ("Senior " if senior else "") + stem, "company": co["name"],
                     "skills": rng.sample(pool, k=min(len(pool), rng.randint(1, 3))),
                     "city": co["city"], "min_years": rng.choice([5, 6, 8]) if senior else rng.choice([1, 2, 3]),
                     "work_mode": rng.choice(MODES), "status": "open" if rng.random() < 0.8 else "closed"})
    return candidates, companies, jobs


if __name__ == "__main__":
    candidates, companies, jobs = build()
    for name, rows in (("candidates", candidates), ("companies", companies), ("jobs", jobs)):
        with open(os.path.join(HERE, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
            f.write("\n")
        print("%s: %d" % (name, len(rows)))
