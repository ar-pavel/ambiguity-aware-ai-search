"""The evaluation script: its scoring is checked on requests whose behaviour is already pinned in
test_strategy.py, so the held-out requests are never needed to trust the arithmetic."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
spec = importlib.util.spec_from_file_location("evaluate", os.path.join(ROOT, "tools", "evaluate.py"))
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

from tests.test_strategy import EXPECTED  # noqa: E402

LONDON = {"value": "London", "scope": "city"}
KNOWN = {"requests": [
    {"id": "x1", "category": "clear", "text": "Java developers in London",
     "base": {"skills": ["Java"], "location": LONDON}},
    {"id": "x2", "category": "connective", "text": "Python and AWS people with Senior in the title",
     "base": {"skills": ["Python", "AWS"], "seniority": {"kind": "title", "contains": "Senior"}},
     "open": {"skills_op": ["AND", "OR"]}},
    {"id": "x4", "category": "connective", "text": "Java Python devs in London",
     "base": {"skills": ["Java", "Python"], "location": LONDON},
     "open": {"skills_op": ["AND", "OR"]}},
    {"id": "x3", "category": "seniority", "text": "senior Java developers",
     "base": {"skills": ["Java"]},
     "open": {"seniority": [{"kind": "years", "min": 5}, {"kind": "title", "contains": "Senior"}]}},
]}


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(KNOWN, f)
        cls.path = f.name
        cls.cases = {c["id"]: c for c in evaluate.load_cases(cls.path)}

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.path)

    def test_every_request_counts_once(self):
        self.assertEqual(sorted(self.cases), ["x1", "x2.1", "x2.2", "x3.1", "x3.2", "x4.1", "x4.2"])
        for request in ("x1", "x2", "x3", "x4"):
            self.assertEqual(sum(c["weight"] for c in self.cases.values() if c["request"] == request), 1.0)

    def test_a_clear_request_is_right_and_never_interrupted(self):
        for mode in ("act", "show", "ask", "auto"):
            r = evaluate.play(self.cases["x1"], mode)
            self.assertFalse(r["asked"], mode)   # there is nothing to ask, even under always ask
            self.assertEqual(evaluate.expected(r, 0.25)[0], 0, mode)

    def test_acting_delivers_the_misreading(self):
        r = evaluate.play(self.cases["x2.2"], "act")  # they wrote 'and' but meant any of the skills
        self.assertTrue(r["first_wrong"])
        self.assertEqual(evaluate.expected(r, 1.0), (1.0, 0.0))

    def test_showing_is_only_as_good_as_the_noticing(self):
        r = evaluate.play(self.cases["x2.2"], "auto")
        self.assertEqual(r["first"], "show")
        self.assertEqual(evaluate.expected(r, 1.0), (0.0, 1.0))
        self.assertEqual(evaluate.expected(r, 0.25), (0.75, 0.25))

    def test_a_right_reading_needs_no_edit(self):
        r = evaluate.play(self.cases["x2.1"], "show")
        self.assertEqual(evaluate.expected(r, 0.5), (0.0, 0.0))

    def test_an_answer_fixes_the_part_that_was_asked_about(self):
        # x3 is asked about 'senior', x4 about AND or OR; either answer must be enough on its own.
        for case in ("x3.1", "x3.2", "x4.1", "x4.2"):
            r = evaluate.play(self.cases[case], "auto")
            self.assertTrue(r["asked"], case)
            self.assertEqual(evaluate.expected(r, 0.25), (0.0, 0.0), case)  # no noticing or edit needed after an answer

    def test_the_summary_is_in_requests(self):
        cases = list(self.cases.values())
        results = [evaluate.play(c, "auto") for c in cases]
        for r in results:
            r["act_high_impact"] = False
        s = evaluate.summarise(cases, results, 0.5)
        self.assertEqual(s["interruptions"], 2.0)   # 'senior Java developers' and 'Java Python devs', once each
        self.assertEqual(s["wrong"], 0.25)          # half of x2's meanings, noticed half the time


class TestRequestsFile(unittest.TestCase):
    """The held-out requests are checked for form only. Nothing here runs the interpreter or the rule."""

    @classmethod
    def setUpClass(cls):
        with open(evaluate.REQUESTS, encoding="utf-8") as f:
            cls.requests = json.load(f)["requests"]

    def test_ids_and_texts_are_unique_and_held_out(self):
        self.assertEqual(len({r["id"] for r in self.requests}), len(self.requests))
        self.assertEqual(len({r["text"].lower() for r in self.requests}), len(self.requests))
        self.assertFalse({r["text"].lower() for r in self.requests} & {t.lower() for t in EXPECTED})

    def test_every_open_part_has_two_different_meanings(self):
        for r in self.requests:
            for slot, values in r.get("open", {}).items():
                with self.subTest(request=r["id"], slot=slot):
                    self.assertIn(slot, evaluate.PARTS)
                    self.assertEqual(len(values), 2)
                    self.assertNotEqual(values[0], values[1])

    def test_the_meanings_of_a_request_give_different_lists(self):
        # Otherwise a misreading could not be seen in the result, and the case would test nothing.
        by_request = {}
        for c in evaluate.load_cases():
            by_request.setdefault(c["request"], []).append(evaluate.intended_list(c["intended"]))
        for request, lists in by_request.items():
            with self.subTest(request=request):
                self.assertEqual(len(set(lists)), len(lists))
                self.assertTrue(any(lists), "no meaning of this request finds anyone")


if __name__ == "__main__":
    unittest.main()
