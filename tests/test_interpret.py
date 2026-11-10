import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import interpret  # noqa: E402

read = interpret.interpret_rules


def slots(text):
    return {a["slot"]: a for a in read(text)["ambiguities"]}


class TestSkillsAndOperator(unittest.TestCase):
    def test_lower_case_connective_is_dominant_evidence(self):
        a = slots("Java with Python in London")["skills_op"]
        self.assertTrue(a["dominant"])
        self.assertIn("with", a["evidence"])
        self.assertEqual(read("Java with Python")["skills_op"], "AND")

    def test_no_connective_is_open(self):
        self.assertFalse(slots("Java Python devs")["skills_op"]["dominant"])

    def test_capital_operator_is_stated(self):
        self.assertNotIn("skills_op", slots("Java AND Python in London"))
        self.assertEqual(read("Java OR Python")["skills_op"], "OR")

    def test_and_is_never_widened_to_or(self):
        # The motivating failure: a user's "and" silently became OR.
        self.assertEqual(read("Python and AWS people")["skills_op"], "AND")

    def test_synonyms_and_phrases(self):
        self.assertEqual(read("JS and k8s")["skills"], ["JavaScript", "Kubernetes"])
        self.assertEqual(read("SAP MM consultant")["skills"], ["SAP MM"])
        self.assertTrue(slots("SAP MM consultant")["phrase:SAP MM"]["dominant"])


class TestOtherSlots(unittest.TestCase):
    def test_senior_is_open_between_years_and_title(self):
        a = slots("senior Java developers")["seniority"]
        self.assertFalse(a["dominant"])
        kinds = [o["seniority"]["kind"] for o in a["options"]]
        self.assertEqual(kinds, ["years", "title", "either"])

    def test_title_or_years_stated_removes_senior_ambiguity(self):
        self.assertNotIn("seniority", slots("Python people with Senior in the title"))
        self.assertEqual(read("Python people with Senior in the title")["seniority"]["kind"], "title")
        self.assertNotIn("seniority", slots("senior devops with 5 years"))

    def test_in_city_is_not_ambiguous_but_near_is(self):
        self.assertNotIn("location", slots("Python devs in London"))
        self.assertIn("location", slots("Python devs near London"))

    def test_near_a_city_without_known_nearby_towns_is_just_that_city(self):
        self.assertNotIn("location", slots("Python devs near Reading"))
        self.assertEqual(read("Python devs near Reading")["location"], {"value": "Reading", "scope": "city"})

    def test_country(self):
        self.assertEqual(read("Go engineers in UK")["location"], {"value": "UK", "scope": "country"})

    def test_availability_and_work_mode(self):
        self.assertIn("availability", slots("React people available now"))
        self.assertEqual(read("React people available in 2 weeks")["availability"], {"max_notice": "2w"})
        self.assertEqual(read("JS and k8s, remote")["work_mode"], "remote")


class TestApplyOption(unittest.TestCase):
    def test_apply_option_patches_a_copy(self):
        r = read("Java with Python")
        flipped = interpret.apply_option(r, {"skills_op": "OR"})
        self.assertEqual(flipped["skills_op"], "OR")
        self.assertEqual(r["skills_op"], "AND")

    def test_split_phrase(self):
        r = interpret.apply_option(read("SAP MM consultant"), {"split": ["SAP", "MM"]})
        self.assertEqual(r["skills"], ["SAP", "MM"])

    def test_without_a_key_the_rules_route_is_used(self):
        os.environ.pop("A2_MODEL", None)
        self.assertEqual(interpret.interpret("Java developers")["source"], "rules")


if __name__ == "__main__":
    unittest.main()
