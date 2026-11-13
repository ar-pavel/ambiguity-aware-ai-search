"""Tests for the live interpreter, using a fake HTTPS call: no key, no network, no cost."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assistant import interpret, model  # noqa: E402

SENIOR = {"target": "candidates", "company": None, "status": None, "skills": ["Java"], "skills_op": "AND",
          "location": {"value": "London", "scope": "city"},
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


class FakeOpenAI:
    """Stands in for the OpenAI HTTPS call."""
    def __init__(self, reply=None, finish="stop", refusal=None):
        self.reply, self.finish, self.refusal, self.sent = reply, finish, refusal, None

    def __call__(self, body):
        self.sent = body
        return {"choices": [{"finish_reason": self.finish, "message": {
            "content": json.dumps(self.reply), "refusal": self.refusal}}]}


class TestOpenAI(unittest.TestCase):
    def setUp(self):
        os.environ["A2_MODEL"] = "openai"

    def tearDown(self):
        for k in ("A2_MODEL", "A2_OPENAI_MODEL"):
            os.environ.pop(k, None)

    def test_request_uses_strict_structured_output_with_the_same_prompt_and_schema(self):
        post = FakeOpenAI(SENIOR)
        self.assertEqual(model.judge("senior Java developers in London", post), SENIOR)
        fmt = post.sent["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertTrue(fmt["json_schema"]["strict"])
        self.assertIs(fmt["json_schema"]["schema"], model.SCHEMA)
        self.assertEqual(post.sent["messages"][0], {"role": "system", "content": model.SYSTEM})

    def test_model_name_can_be_set(self):
        os.environ["A2_OPENAI_MODEL"] = "my-model"
        post = FakeOpenAI(SENIOR)
        model.judge("x", post)
        self.assertEqual(post.sent["model"], "my-model")
        self.assertEqual(model.label(), "OpenAI (my-model)")

    def test_refusal_or_truncation_gives_none(self):
        self.assertIsNone(model.judge("x", FakeOpenAI(SENIOR, refusal="I can't help with that.")))
        self.assertIsNone(model.judge("x", FakeOpenAI(SENIOR, finish="length")))

    def test_reply_goes_through_the_same_checks(self):
        judged = dict(SENIOR, skills=["Java", "Go"])
        r = interpret.from_model("senior Java developers in London", model.judge("x", FakeOpenAI(judged)))
        self.assertEqual(r["skills"], ["Java"])

    def test_unknown_provider_means_rules(self):
        os.environ["A2_MODEL"] = "something-else"
        self.assertFalse(model.live())


class FakeOllama:
    """Stands in for the local Ollama server."""
    def __init__(self, reply=None, done="stop", error=None):
        self.reply, self.done, self.error, self.sent = reply, done, error, None

    def __call__(self, body):
        if self.error:
            raise self.error
        self.sent = body
        return {"done_reason": self.done, "message": {"role": "assistant", "content": json.dumps(self.reply)}}


class TestOllama(unittest.TestCase):
    """A local model: same prompt, schema and checks; no key; nothing leaves the machine."""
    def setUp(self):
        os.environ["A2_MODEL"] = "ollama"

    def tearDown(self):
        for k in ("A2_MODEL", "A2_OLLAMA_MODEL"):
            os.environ.pop(k, None)

    def test_request_constrains_output_to_the_schema(self):
        post = FakeOllama(SENIOR)
        self.assertEqual(model.judge("senior Java developers in London", post), SENIOR)
        self.assertIs(post.sent["format"], model.SCHEMA)
        self.assertFalse(post.sent["stream"])
        self.assertEqual(post.sent["options"]["temperature"], 0)
        self.assertEqual(post.sent["messages"][0], {"role": "system", "content": model.SYSTEM})
        self.assertEqual(post.sent["model"], model.OLLAMA_DEFAULT_MODEL)

    def test_thinking_is_off_where_it_can_be(self):
        post = FakeOllama(SENIOR)
        model.judge("x", post)
        self.assertIs(post.sent["think"], False)          # qwen3: off
        os.environ["A2_OLLAMA_MODEL"] = "gpt-oss:20b"
        model.judge("x", post)
        self.assertEqual(post.sent["think"], "low")       # gpt-oss cannot turn it off
        os.environ["A2_OLLAMA_MODEL"] = "gemma3:12b"
        model.judge("x", post)
        self.assertNotIn("think", post.sent)              # not a reasoning model
        self.assertEqual(model.label(), "local model (gemma3:12b, Ollama)")

    def test_not_running_or_truncated_gives_none(self):
        self.assertIsNone(model.judge("x", FakeOllama(error=OSError("connection refused"))))
        self.assertIsNone(model.judge("x", FakeOllama(SENIOR, done="length")))

    def test_ollama_not_running_falls_back_to_the_stand_in_and_says_so(self):
        saved, model._post_ollama = model._post_ollama, FakeOllama(error=OSError("connection refused"))
        try:
            r = interpret.interpret("senior Java developers in London")
            self.assertIn("unavailable", r["source"])
        finally:
            model._post_ollama = saved


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
    BASE = {"target": "candidates", "company": None, "status": None, "skills_op": "AND", "location": None,
            "seniority": None, "availability": None,
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

    def test_company_short_name_is_mapped_to_the_data(self):
        # A model echoes what the user wrote ("Bluefin"); the stand-in accepts the first word, so must the check.
        for said in ("Bluefin", "bluefin analytics"):
            r = interpret.from_model("Java developers at Bluefin", dict(self.BASE, skills=["Java"], company=said))
            self.assertEqual(r["company"], "Bluefin Analytics")
            self.assertEqual(r["dropped"], [])
        r = interpret.from_model("Java developers at Acme", dict(self.BASE, skills=["Java"], company="Acme"))
        self.assertIsNone(r["company"])
        self.assertIn("company 'Acme' (not in your request or not in the data)", r["dropped"])

    def test_and_written_by_the_user_is_never_widened_to_or(self):
        # The failure this project starts from: "Python and AWS" silently searched as OR.
        for text, word in (("Python and AWS people", "and"), ("Python with AWS", "with"),
                           ("Python & AWS", "&"), ("Python AND AWS", "AND")):
            r = interpret.from_model(text, dict(self.BASE, skills=["Python", "AWS"], skills_op="OR"))
            self.assertEqual(r["skills_op"], "AND", text)
            self.assertIn("OR between the skills (you wrote '%s')" % word, r["dropped"])
        # The model may still flag "and" as ambiguous; the chip then offers OR, with AND chosen.
        judged = dict(self.BASE, skills=["Python", "AWS"], skills_op="OR",
                      ambiguities=[{"slot": "skills_op", "dominant": True, "evidence": "you wrote 'and'"}])
        r = interpret.from_model("Python and AWS people", judged)
        self.assertEqual(r["ambiguities"][0]["chosen"], 0)
        # Where the user wrote "or", or no word at all, the model's OR stands, including for skills
        # the stand-in doesn't know, and where "or" sits next to "with".
        for text in ("Python or AWS people", "Python AWS people", "Python or Rust developers",
                     "Rust or Haskell developers", "Python with Java or Go"):
            skills = [w for w in re.findall(r"[A-Za-z]+", text) if w not in ("or", "with", "people", "developers")]
            r = interpret.from_model(text, dict(self.BASE, skills=skills, skills_op="OR"))
            self.assertEqual((r["skills_op"], r["dropped"]), ("OR", []), text)
        # A skill the stand-in doesn't know, joined with "and", is still kept as AND.
        judged = dict(self.BASE, skills=["Rust", "Haskell"], skills_op="OR")
        r = interpret.from_model("Rust and Haskell developers", judged)
        self.assertEqual(r["skills_op"], "AND")

    def test_evidence_is_kept_only_if_its_quote_is_in_the_request(self):
        judged = dict(SENIOR, ambiguities=[{"slot": "seniority", "dominant": False,
                                            "evidence": "you wrote 'senior'"}])
        r = interpret.from_model("senior Java developers", judged)
        self.assertEqual(r["ambiguities"][0]["evidence"], "you wrote 'senior'")
        judged["ambiguities"][0]["evidence"] = "you wrote 'very experienced'"
        r = interpret.from_model("senior Java developers", judged)
        self.assertEqual(r["ambiguities"][0]["evidence"], "from your request")

    def test_nearby_is_only_offered_where_nearby_towns_are_known(self):
        judged = dict(self.BASE, skills=["Python"], location={"value": "Reading", "scope": "nearby"},
                      ambiguities=[{"slot": "location", "dominant": False, "evidence": "you wrote 'near'"}])
        r = interpret.from_model("Python devs near Reading", judged)
        self.assertEqual(r["location"], {"value": "Reading", "scope": "city"})
        self.assertEqual(r["ambiguities"], [])

    def test_unsupported_must_quote_the_user_and_use_a_known_kind(self):
        judged = dict(self.BASE, skills=["Java"], unsupported=[
            {"text": "named Matin", "kind": "name"},          # kept: written, known kind
            {"text": "with a PhD", "kind": "other"},          # dropped: not in the request
            {"text": "Java", "kind": "salary"},               # dropped: unknown kind
        ])
        r = interpret.from_model("Java developers named Matin", judged)
        self.assertEqual(r["unsupported"], [{"text": "named Matin", "kind": "name"}])

    def test_reason_on_screen_is_chosen_by_code(self):
        self.assertEqual(set(interpret.WHY), {"name", "place", "other"})
        self.assertEqual(model.SCHEMA["properties"]["unsupported"]["items"]["properties"]["kind"]["enum"],
                         ["name", "place", "other"])

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
