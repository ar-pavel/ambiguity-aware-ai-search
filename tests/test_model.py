"""Tests for the live interpreter, using a fake HTTPS call: no key, no network, no cost."""
import json
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import interpret  # noqa: E402
import model  # noqa: E402

SENIOR = {"skills": ["Java"], "skills_op": "AND", "location": {"value": "London", "scope": "city"},
          "seniority": {"kind": "years", "min": 5, "contains": "Senior"}, "availability": None,
          "work_mode": None, "ambiguities": [{"slot": "seniority", "dominant": False,
                                             "evidence": "you wrote 'senior'"}]}


class FakePost:
    """Stands in for the HTTPS call: records the request body and returns a canned reply, or raises."""
    def __init__(self, reply=None, stop="end_turn", error=None):
        self.reply, self.stop, self.error, self.sent = reply, stop, error, None

    def __call__(self, body):
        if self.error:
            raise self.error
        self.sent = body
        return {"stop_reason": self.stop, "content": [{"type": "text", "text": json.dumps(self.reply)}]}


class TestEnvFile(unittest.TestCase):
    def test_env_file_is_read_without_overriding_the_shell(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("# comment\nA2_TEST_NEW=from-file\nA2_TEST_SET=from-file\nA2_TEST_EMPTY=\n")
        os.environ["A2_TEST_SET"] = "from-shell"
        try:
            model.load_env(f.name)
            self.assertEqual(os.environ["A2_TEST_NEW"], "from-file")
            self.assertEqual(os.environ["A2_TEST_SET"], "from-shell")
            self.assertNotIn("A2_TEST_EMPTY", os.environ)
        finally:
            for k in ("A2_TEST_NEW", "A2_TEST_SET"):
                os.environ.pop(k, None)
            os.remove(f.name)

    def test_missing_env_file_is_fine(self):
        model.load_env("/nonexistent/.env")


class TestJudge(unittest.TestCase):
    def test_request_uses_structured_output_and_fallback(self):
        post = FakePost(SENIOR)
        self.assertEqual(model.judge("senior Java developers in London", post), SENIOR)
        self.assertEqual(post.sent["model"], model.MODEL)
        self.assertEqual(post.sent["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(post.sent["fallbacks"], "default")

    def test_refusal_or_error_gives_none(self):
        self.assertIsNone(model.judge("x", FakePost(SENIOR, stop="refusal")))
        self.assertIsNone(model.judge("x", FakePost(error=OSError("network down"))))
        self.assertIsNone(model.judge("x", FakePost(error=KeyError("ANTHROPIC_API_KEY"))))


class TestFromModel(unittest.TestCase):
    def test_builds_the_same_shape_as_the_rules(self):
        r = interpret.from_model("senior Java developers in London", SENIOR)
        a = r["ambiguities"][0]
        self.assertEqual(a["slot"], "seniority")
        self.assertEqual(a["labels"], ["5+ years' experience", "'Senior' in their job title", "either"])
        self.assertFalse(a["dominant"])

    def test_invented_skill_is_dropped(self):
        judged = dict(SENIOR, skills=["Java", "Kubernetes"])
        r = interpret.from_model("senior Java developers", judged)
        self.assertEqual(r["skills"], ["Java"])
        self.assertEqual(r["dropped"], ["skill 'Kubernetes' (not in your request)"])

    def test_ambiguity_for_a_missing_slot_is_ignored(self):
        judged = dict(SENIOR, ambiguities=[{"slot": "location", "dominant": False, "evidence": "?"}],
                      location=None)
        self.assertEqual(interpret.from_model("Java developers", judged)["ambiguities"], [])


class TestChecks(unittest.TestCase):
    """The model judges; code checks. Each test is a way a model reply could mislead the page."""
    BASE = {"skills_op": "AND", "location": None, "seniority": None, "availability": None,
            "work_mode": None, "ambiguities": []}

    def test_skill_must_be_a_whole_word(self):
        r = interpret.from_model("good React developers", dict(self.BASE, skills=["React", "Go"]))
        self.assertEqual(r["skills"], ["React"])
        r = interpret.from_model("JavaScript devs", dict(self.BASE, skills=["Java"]))
        self.assertEqual(r["skills"], [])

    def test_synonym_written_by_the_user_counts(self):
        r = interpret.from_model("k8s engineers", dict(self.BASE, skills=["Kubernetes"]))
        self.assertEqual(r["skills"], ["Kubernetes"])

    def test_place_is_mapped_to_the_data_or_dropped(self):
        r = interpret.from_model("Java devs in London", dict(self.BASE, skills=["Java"],
                                 location={"value": "London, UK", "scope": "city"}))
        self.assertEqual(r["location"], {"value": "London", "scope": "city"})
        r = interpret.from_model("Java devs in Paris", dict(self.BASE, skills=["Java"],
                                 location={"value": "Paris", "scope": "city"}))
        self.assertIsNone(r["location"])
        self.assertIn("location 'Paris' (not in the data)", r["dropped"])

    def test_malformed_reply_falls_back_instead_of_crashing(self):
        os.environ["A2_MODEL"] = "claude"
        saved, model.judge = model.judge, (lambda text: {"skills": ["Java"]})
        try:
            r = interpret.interpret("Java devs")
            self.assertIn("rules", r["source"])
        finally:
            model.judge = saved
            os.environ.pop("A2_MODEL", None)


class TestRouting(unittest.TestCase):
    def setUp(self):
        self._judge = model.judge

    def tearDown(self):
        model.judge = self._judge
        os.environ.pop("A2_MODEL", None)

    def test_live_reading_is_labelled(self):
        os.environ["A2_MODEL"] = "claude"
        model.judge = lambda text: SENIOR
        self.assertIn("Claude", interpret.interpret("senior Java developers in London")["source"])

    def test_failure_falls_back_to_rules_and_says_so(self):
        os.environ["A2_MODEL"] = "claude"
        model.judge = lambda text: None
        r = interpret.interpret("senior Java developers in London")
        self.assertIn("rules", r["source"])
        self.assertIn("unavailable", r["source"])
        self.assertEqual(r["ambiguities"][0]["slot"], "seniority")

    def test_without_live_mode_no_model_is_called(self):
        model.judge = lambda text: self.fail("model called without A2_MODEL=claude")
        self.assertEqual(interpret.interpret("Java developers")["source"], "rules")


if __name__ == "__main__":
    unittest.main()
