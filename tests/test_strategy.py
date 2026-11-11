import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import interpret  # noqa: E402
import strategy  # noqa: E402

# The scripted requests and the mode the rule should choose for each (design spec, section 8).
EXPECTED = {
    "Java with Python in London": "show",       # 'with' is dominant evidence for AND
    "Java Python devs in London": "ask",        # no connective; AND and OR lists differ a lot
    "senior Java developers": "ask",            # years vs title give different lists
    "Python devs near London": "show",          # nearby towns change the list little
    "Python devs in London": "act",             # nothing unclear
    "React people available now": "ask",        # immediate vs 2 weeks differ
    "SAP MM consultant": "show",                # the phrase is dominant
    "Java AND Python in London, 5+ years": "act",
    "Java developers in London": "act",
    "Python and AWS people with Senior in the title": "show",   # the A1 incident request
}


def decide(text, **kw):
    return strategy.decide(interpret.interpret_rules(text), **kw)


class TestRule(unittest.TestCase):
    def test_expected_mode_for_every_scripted_request(self):
        for text, mode in EXPECTED.items():
            with self.subTest(text=text):
                self.assertEqual(decide(text)["mode"], mode)

    def test_every_mode_explains_itself(self):
        for text in EXPECTED:
            self.assertTrue(decide(text)["reason"].strip(), text)

    def test_ask_names_one_slot_only(self):
        d = decide("senior Java developers")
        self.assertEqual(d["ask_slot"], "seniority")
        self.assertIn("'senior'", d["reason"])

    def test_threshold_changes_the_decision(self):
        # With a very low threshold, nothing differs "enough" to ask.
        self.assertEqual(decide("senior Java developers", theta=0.0)["mode"], "show")

    def test_manual_override_is_reported(self):
        d = decide("senior Java developers", force="act")
        self.assertEqual(d["mode"], "act")
        self.assertEqual(d["rule_mode"], "ask")  # reported in Why? and the log (UX review fix 8)
        self.assertEqual(d["reason"], strategy.FORCED["act"])

    def test_cannot_ask_when_nothing_is_unclear(self):
        d = decide("Java developers in London", force="ask")
        self.assertEqual(d["mode"], "act")


if __name__ == "__main__":
    unittest.main()
