"""Jobs as a second target, and the company filter (issue #25)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assistant import interpret, replies, search, server, strategy  # noqa: E402

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
        q = replies.question(r, "target")
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
        r = server.handle({"text": "open Python jobs"})
        self.assertEqual((r["target"], r["noun"]), ("jobs", "job"))
        self.assertEqual(r["table"]["headers"][:2], ["Job", "Company"])
        self.assertEqual(len(r["table"]["rows"]), r["count"])
        self.assertIn("Searched jobs", r["searched"])
        self.assertEqual(r["read_as"].split(" · ")[0], "open jobs")


class TestNothingChangesSilently(unittest.TestCase):
    """Review of #30: switching the target, or mixed wording, must not hide a change."""

    def test_switching_to_jobs_lists_availability_as_ignored(self):
        r = server.handle({"text": "React developers at Bluefin available now", "choices": {"target": 1}})
        self.assertEqual(r["target"], "jobs")
        self.assertEqual(r["dropped"], ["availability (jobs have no notice period)"])
        self.assertNotIn("availability", [c.get("slot") for c in r["chips"]])

    def test_switching_to_jobs_keeps_open(self):
        r = server.handle({"text": "open Java developers at Bluefin", "choices": {"target": 1}})
        self.assertEqual(r["read_as"].split(" · ")[0], "open jobs")
        status = r["table"]["headers"].index("Status")
        self.assertTrue(all(row[status] == "open" for row in r["table"]["rows"]))

    def test_people_and_job_words_search_people_with_a_chip(self):
        for text in ("candidates for the Python role at Moorgate", "people who held lead roles in Python"):
            with self.subTest(text=text):
                r = server.handle({"text": text})
                self.assertEqual(r["target"], "candidates")
                self.assertNotEqual(r["mode"], "act")
                chip = next(c for c in r["chips"] if c.get("slot") == "target")
                self.assertIn("jobs", " ".join(chip["options"]))

    def test_reason_quotes_the_word_the_user_wrote(self):
        r = server.handle({"text": "people who held lead roles in Python"})
        self.assertIn("'lead'", r["reason"])
        self.assertNotIn("'senior'", r["reason"])

    def test_position_is_not_a_job_word(self):
        self.assertEqual(read("Java developers looking for a senior position")["target"], "candidates")


class TestCompany(unittest.TestCase):
    def test_company_filters_candidates_by_current_employer(self):
        found = search.search(read("Python people at Ironbridge Bank"))
        self.assertEqual(len(found), 8)
        self.assertTrue(all(c["company"] == "Ironbridge Bank" for c in found))

    def test_answering_the_question_switches_the_table(self):
        r = server.handle({"text": "Java developers at Bluefin", "choices": {"target": 1}})
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

    def test_unexpected_target_falls_back_to_the_rules(self):
        for target in ("people", "companies", "../secrets"):
            with self.subTest(target=target):
                self.assertIsNone(interpret.from_model("Java jobs", dict(self.BASE, target=target)))

    def test_unexpected_status_is_dropped_and_said_so(self):
        r = interpret.from_model("Java jobs", dict(self.BASE, target="jobs", status="pending"))
        self.assertIsNone(r["status"])
        self.assertIn("status 'pending' (jobs are only open or closed)", r["dropped"])

    def test_only_the_known_data_files_can_be_loaded(self):
        with self.assertRaises(ValueError):
            search.load("../.env")

    def test_status_does_not_filter_candidates(self):
        r = interpret.from_model("open Java developers", dict(self.BASE, status="open"))
        self.assertEqual(search.search(r), search.search(dict(r, status=None)))
        self.assertNotIn("open", search.describe(r))


if __name__ == "__main__":
    unittest.main()
