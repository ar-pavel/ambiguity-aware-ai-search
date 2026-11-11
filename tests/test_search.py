import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assistant import search  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
sys.path.insert(0, DATA)
import generate  # noqa: E402

CANDS = search.load()


def names(reading):
    return {c["name"] for c in search.search(reading, CANDS)}


class TestData(unittest.TestCase):
    def test_two_hundred_unique_candidates(self):
        self.assertEqual(len(CANDS), 200)
        self.assertEqual(len({c["id"] for c in CANDS}), 200)
        self.assertEqual(len({c["name"] for c in CANDS}), 200)

    def test_hand_built_candidates_are_kept_unchanged(self):
        core = json.load(open(os.path.join(DATA, "core_candidates.json"), encoding="utf-8"))
        for c in core:
            self.assertEqual({k: v for k, v in CANDS[c["id"] - 1].items() if k != "company"}, c)

    def test_generator_is_reproducible(self):
        candidates, companies, jobs = generate.build()
        self.assertEqual(candidates, CANDS)
        self.assertEqual(companies, json.load(open(os.path.join(DATA, "companies.json"), encoding="utf-8")))
        self.assertEqual(jobs, json.load(open(os.path.join(DATA, "jobs.json"), encoding="utf-8")))

    def test_every_company_and_job_links_up(self):
        companies = {c["name"] for c in json.load(open(os.path.join(DATA, "companies.json"), encoding="utf-8"))}
        jobs = json.load(open(os.path.join(DATA, "jobs.json"), encoding="utf-8"))
        self.assertTrue(all(c["company"] in companies for c in CANDS))
        self.assertTrue(all(j["company"] in companies and j["status"] in ("open", "closed") for j in jobs))

    def test_every_candidate_has_every_field(self):
        fields = {"id", "name", "current_title", "skills", "years_experience",
                  "city", "country", "work_mode", "notice", "company"}
        for c in CANDS:
            self.assertEqual(set(c), fields, c["name"])
            self.assertIn(c["notice"], search.NOTICE_ORDER)


class TestSkills(unittest.TestCase):
    def test_and_is_narrower_than_or(self):
        both = names({"skills": ["Java", "Python"], "skills_op": "AND"})
        either = names({"skills": ["Java", "Python"], "skills_op": "OR"})
        self.assertTrue(both < either)

    def test_synonyms_map_to_data_names(self):
        self.assertEqual(search.canonical("k8s"), "Kubernetes")
        self.assertEqual(search.canonical("JS"), "JavaScript")
        self.assertEqual(names({"skills": ["golang"]}), names({"skills": ["Go"]}))

    def test_phrase_skill_is_not_split(self):
        # "SAP MM" is one skill: someone with SAP and MM listed separately is not a match.
        self.assertIn("Hannah Lewis", names({"skills": ["SAP MM"]}))
        self.assertNotIn("Julia Novak", names({"skills": ["SAP MM"]}))


class TestOtherFilters(unittest.TestCase):
    def test_senior_by_title_and_by_years_differ(self):
        by_title = names({"skills": ["Java"], "seniority": {"kind": "title", "contains": "Senior"}})
        by_years = names({"skills": ["Java"], "seniority": {"kind": "years", "min": 5}})
        self.assertNotEqual(by_title, by_years)
        self.assertIn("Felix Grant", by_title - by_years)    # Senior title, 3 years
        self.assertIn("Grace Liu", by_years - by_title)      # 8 years, no Senior title

    def test_nearby_includes_commuter_towns(self):
        city = names({"location": {"value": "London", "scope": "city"}})
        near = names({"location": {"value": "London", "scope": "nearby"}})
        self.assertTrue(city < near)
        self.assertIn("Hamza Ali", near - city)  # Croydon

    def test_availability_is_inclusive(self):
        now = names({"availability": {"max_notice": "immediate"}})
        soon = names({"availability": {"max_notice": "2w"}})
        self.assertTrue(now < soon)

    def test_work_mode(self):
        remote = names({"work_mode": "remote"})
        self.assertTrue(remote)
        self.assertTrue(all(c["work_mode"] == "remote" for c in CANDS if c["name"] in remote))

    def test_overlap(self):
        a = search.search({"skills": ["Java", "Python"], "skills_op": "AND"}, CANDS)
        b = search.search({"skills": ["Java", "Python"], "skills_op": "OR"}, CANDS)
        self.assertLess(search.overlap(a, b), 0.5)
        self.assertEqual(search.overlap([], []), 1.0)
        self.assertEqual(search.overlap(a, a), 1.0)


if __name__ == "__main__":
    unittest.main()
