import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import log  # noqa: E402


class TestLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("A2_LOG", None)

    def lines(self):
        with open(os.path.join(self.tmp.name, "events.jsonl"), encoding="utf-8") as f:
            return [json.loads(x) for x in f]

    def test_one_line_per_turn_with_the_strategy_and_outcome(self):
        payload = {"text": "senior Java developers"}
        log.write(payload, app.handle(payload), self.tmp.name)
        edit = {"text": "senior Java developers", "choices": {"seniority": 1}, "mode": "show"}
        log.write(edit, app.handle(edit), self.tmp.name)
        first, second = self.lines()
        self.assertEqual((first["event"], first["mode"], first["asked"]), ("search", "ask", "seniority"))
        self.assertEqual(first["ambiguities"], ["seniority"])
        self.assertEqual((second["event"], second["mode"], second["count"]), ("edit", "show", 12))
        self.assertEqual(second["choices"], {"seniority": 1})
        self.assertEqual(second["target"], "candidates")

    def test_errors_are_not_logged(self):
        self.assertIsNone(log.write({"text": ""}, app.handle({"text": ""}), self.tmp.name))

    def test_logging_can_be_turned_off(self):
        os.environ["A2_LOG"] = "off"
        payload = {"text": "Java developers"}
        self.assertIsNone(log.write(payload, app.handle(payload), self.tmp.name))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "events.jsonl")))


if __name__ == "__main__":
    unittest.main()
