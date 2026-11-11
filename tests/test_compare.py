"""The comparison script: its expected outcomes must hold for the stand-in, so a live model's misses
are the model's, not the script's."""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("compare", os.path.join(ROOT, "tools", "compare.py"))
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class TestCompare(unittest.TestCase):
    def tearDown(self):
        compare.use("rules")

    def test_the_stand_in_meets_every_expectation(self):
        rows = compare.run("rules")
        self.assertEqual([r["text"] for r in rows if not r["match"]], [])
        self.assertFalse(any(r["fell_back"] for r in rows))

    def test_a_model_that_cannot_be_reached_is_reported_as_a_fallback(self):
        os.environ["A2_OLLAMA_URL"] = "http://127.0.0.1:9/api/chat"   # nothing listens on port 9
        try:
            rows = compare.run("ollama:qwen3:14b")
        finally:
            os.environ.pop("A2_OLLAMA_URL", None)
        self.assertTrue(all(r["fell_back"] for r in rows))

    def test_the_table_has_a_summary_per_interpreter(self):
        text = compare.markdown({"rules": compare.run("rules")})
        self.assertIn("## rules: %d of %d as expected" % (len(compare.REQUESTS), len(compare.REQUESTS)), text)


if __name__ == "__main__":
    unittest.main()
