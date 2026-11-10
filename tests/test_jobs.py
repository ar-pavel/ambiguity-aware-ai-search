"""Jobs as a second target, and the company filter (issue #25)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import interpret  # noqa: E402
import search  # noqa: E402
import strategy  # noqa: E402

JOBS = search.load("jobs")


def read(text):
    return interpret.interpret_rules(text)


class TestTarget(unittest.TestCase):
    def test_job_words_search_jobs(self):
        for text in ("open Java roles in London", "Python jobs", "React vacancies", "AWS openings"):
            with self.subTest(text=text):
                self.assertEqual(read(text)["target"], "jobs")

    def test_people_are_the_default(self):
        for text in ("Java developers in London", "senior Python engineers", "Python people at Bluefin"):
            with self.subTest(text=text):
                r = read(text)
                self.assertEqual(r["target"], "candidates")
                self.assertNotIn("target", [a["slot"] for a in r["ambiguities"]])

    def test_company_without_people_or_job_words_is_unclear_and_asked(self):
        r = read("Java developers at Bluefin")
        self.assertEqual(r["company"], "Bluefin Analytics")
        d = strategy.decide(r)
        self.assertEqual((d["mode"], d["ask_slot"]), ("ask", "target"))
        q = app.question(r, "target")
        self.assertEqual([o["label"] for o in q["options"]],
                         ["people who work at Bluefin Analytics", "jobs at Bluefin Analytics"])
        self.assertEqual([o["count"] for o in q["options"]], [5, 1])

    def test_a_job_and_a_candidate_with_the_same_id_never_overlap(self):
        self.assertEqual(search.overlap([search.load()[0]], [JOBS[0]]), 0.0)


class TestJobSearch(unittest.TestCase):
    def test_filters_apply_to_jobs(self):
        r = read("open Java roles in London")
        found = search.search(r)
        self.assertTrue(found)
        for j in found:
            self.assertIn("Java", j["skills"])
            self.assertEqual((j["city"], j["status"]), ("London", "open"))

    def test_senior_on_a_job_means_its_minimum_years_or_its_title(self):
        years = search.search({"target": "jobs", "seniority": {"kind": "years", "min": 5}})
        title = search.search({"target": "jobs", "seniority": {"kind": "title", "contains": "Senior"}})
        self.assertTrue(all(j["min_years"] >= 5 for j in years))
        self.assertTrue(all("Senior" in j["title"] for j in title))

    def test_availability_is_dropped_for_jobs_and_said_so(self):
        r = read("Python jobs available now")
        self.assertIsNone(r["availability"])
        self.assertEqual(r["dropped"], ["availability (jobs have no notice period)"])
        self.assertNotIn("availability", [a["slot"] for a in r["ambiguities"]])

    def test_page_gets_a_jobs_table_and_scope(self):
        r = app.handle({"text": "open Python jobs"})
        self.assertEqual((r["target"], r["noun"]), ("jobs", "job"))
        self.assertEqual(r["table"]["headers"][:2], ["Job", "Company"])
        self.assertEqual(len(r["table"]["rows"]), r["count"])
        self.assertIn("Searched jobs", r["searched"])
        self.assertEqual(r["read_as"].split(" · ")[0], "open jobs")


class TestCompany(unittest.TestCase):
    def test_company_filters_candidates_by_current_employer(self):
        found = search.search(read("Python people at Ironbridge Bank"))
        self.assertEqual(len(found), 8)
        self.assertTrue(all(c["company"] == "Ironbridge Bank" for c in found))

    def test_answering_the_question_switches_the_table(self):
        r = app.handle({"text": "Java developers at Bluefin", "choices": {"target": 1}})
        self.assertEqual((r["mode"], r["target"], r["count"]), ("show", "jobs", 1))
        self.assertIn("jobs at Bluefin Analytics", [o for c in r["chips"] for o in c.get("options", [])])


class TestModelReply(unittest.TestCase):
    BASE = {"target": "candidates", "company": None, "status": None, "skills": ["Java"], "skills_op": "AND",
            "location": None, "seniority": None, "availability": None, "work_mode": None, "ambiguities": []}

    def test_company_must_be_written_and_known(self):
        made_up = interpret.from_model("Java developers", dict(self.BASE, company="Bluefin Analytics"))
        self.assertIsNone(made_up["company"])
        self.assertTrue(made_up["dropped"])
        real = interpret.from_model("Java developers at bluefin", dict(self.BASE, company="Bluefin Analytics"))
        self.assertEqual(real["company"], "Bluefin Analytics")

    def test_target_ambiguity_from_the_model_gets_the_same_options(self):
        judged = dict(self.BASE, company="Bluefin Analytics",
                      ambiguities=[{"slot": "target", "dominant": False, "evidence": "you wrote 'at Bluefin'"}])
        r = interpret.from_model("Java developers at Bluefin", judged)
        expected = dict(read("Java developers at Bluefin")["ambiguities"][0], evidence="you wrote 'at Bluefin'")
        self.assertEqual(r["ambiguities"][0], expected)  # dict() rather than |, which needs Python 3.9

    def test_status_is_ignored_for_candidates(self):
        r = interpret.from_model("Java developers", dict(self.BASE, status="open"))
        self.assertIsNone(r["status"])


if __name__ == "__main__":
    unittest.main()
