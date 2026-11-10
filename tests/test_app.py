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
