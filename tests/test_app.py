import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import search  # noqa: E402


class TestHandle(unittest.TestCase):
    def test_clear_request_acts(self):
        r = app.handle({"text": "Java developers in London"})
        self.assertEqual(r["mode"], "act")
        self.assertEqual(r["read_as"], "Java · London")
        self.assertEqual(r["count"], len(r["results"]))
        self.assertTrue(r["reason"])

    def test_read_as_is_built_from_the_filters_that_ran(self):
        # The line must describe exactly the reading used for the search.
        r = app.handle({"text": "Java with Python in London"})
        self.assertEqual(r["read_as"], search.describe(r["reading"]))
        self.assertEqual(r["count"], len(search.search(r["reading"])))
        self.assertIn("Java AND Python", r["read_as"])

    def test_scope_line_says_what_was_not_searched(self):
        r = app.handle({"text": "Python devs"})
        self.assertIn("Not searched", r["not_searched"])

    def test_empty_request_is_explained(self):
        self.assertIn("error", app.handle({"text": "  "}))

    def test_manual_mode(self):
        self.assertEqual(app.handle({"text": "senior Java developers", "mode": "act"})["mode"], "act")
        self.assertEqual(app.handle({"text": "senior Java developers", "mode": "auto"})["mode"], "ask")


class TestShowMode(unittest.TestCase):
    def test_flipping_and_to_or_changes_the_count(self):
        before = app.handle({"text": "Java with Python in London"})
        after = app.handle({"text": "Java with Python in London", "op": "OR"})
        self.assertGreater(after["count"], before["count"])
        self.assertIn("Java OR Python", after["read_as"])
        self.assertEqual(after["mode"], "show")

    def test_choosing_an_option_re_runs_the_search(self):
        r = app.handle({"text": "senior Java developers in London", "choices": {"seniority": 1}})
        self.assertIn("'Senior' in title", r["read_as"])
        self.assertEqual(r["count"], len(search.search(r["reading"])))

    def test_open_choices_are_marked_guessed_until_edited(self):
        chips = {c.get("slot", c["kind"]): c for c in app.handle({"text": "senior Java developers"})["chips"]}
        self.assertTrue(chips["seniority"]["guessed"])
        edited = {c.get("slot", c["kind"]): c for c in
                  app.handle({"text": "senior Java developers", "choices": {"seniority": 0}})["chips"]}
        self.assertFalse(edited["seniority"]["guessed"])

    def test_operator_chip_shows_its_evidence(self):
        op = [c for c in app.handle({"text": "Java with Python"})["chips"] if c["kind"] == "op"][0]
        self.assertIn("with", op["evidence"])

    def test_bad_choice_is_ignored(self):
        r = app.handle({"text": "senior Java developers", "choices": {"seniority": 99}})
        self.assertNotIn("error", r)


class TestAskMode(unittest.TestCase):
    def test_ask_returns_one_question_with_real_counts(self):
        r = app.handle({"text": "senior Java developers"})
        self.assertEqual(r["mode"], "ask")
        q = r["question"]
        self.assertEqual(q["slot"], "seniority")
        self.assertIn("'senior'", q["text"])
        for opt, amb_opt in zip(q["options"], [a for a in r["reading"]["ambiguities"]
                                               if a["slot"] == "seniority"][0]["options"]):
            reading = app.interpret.apply_option(r["reading"], amb_opt)
            self.assertEqual(opt["count"], len(search.search(reading)))

    def test_no_question_outside_ask_mode(self):
        self.assertIsNone(app.handle({"text": "Java developers in London"})["question"])
        self.assertIsNone(app.handle({"text": "Java with Python in London"})["question"])

    def test_answering_gives_show_mode_with_that_choice(self):
        r = app.handle({"text": "senior Java developers", "choices": {"seniority": 1}, "mode": "show"})
        self.assertEqual(r["mode"], "show")
        self.assertIn("'Senior' in title", r["read_as"])
        self.assertIsNone(r["question"])

    def test_only_one_question_even_with_several_unclear_parts(self):
        r = app.handle({"text": "senior Java Python devs available now"})
        self.assertEqual(r["mode"], "ask")
        self.assertIsInstance(r["question"], dict)


class TestDescribe(unittest.TestCase):
    def test_every_filter_appears(self):
        line = search.describe({"skills": ["Java", "Python"], "skills_op": "OR",
                                "location": {"value": "London", "scope": "nearby"},
                                "seniority": {"kind": "title", "contains": "Senior"},
                                "availability": {"max_notice": "2w"}, "work_mode": "remote"})
        for part in ["Java OR Python", "London and nearby", "'Senior' in title", "notice ≤ 2 weeks", "remote"]:
            self.assertIn(part, line)

    def test_no_filters(self):
        self.assertEqual(search.describe({}), "everyone (no filters)")


if __name__ == "__main__":
    unittest.main()
