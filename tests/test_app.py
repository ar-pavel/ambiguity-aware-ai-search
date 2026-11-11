import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import replies  # noqa: E402
import model  # noqa: E402
import search  # noqa: E402


class TestHandle(unittest.TestCase):
    def test_clear_request_acts(self):
        r = app.handle({"text": "Java developers in London"})
        self.assertEqual(r["mode"], "act")
        self.assertEqual(r["read_as"], "Java · London")
        self.assertEqual(r["count"], len(r["table"]["rows"]))
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


    def test_hint_is_sent_apart_so_an_earlier_turn_can_drop_it(self):
        r = app.handle({"text": "Java with Python in London"})
        self.assertEqual(r["mode"], "show")
        self.assertEqual(r["hint"], "Tap AND ⇄ to switch to OR.")
        self.assertTrue(r["reason"].endswith(" " + r["hint"]))
        edited = app.handle({"text": "Java with Python in London", "op": "OR", "last": {"op": True}})
        self.assertIsNone(edited["hint"])  # after an edit the reason says what changed, with no hint
        self.assertIsNone(app.handle({"text": "Java developers in London"})["hint"])


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

    def test_question_text_never_uses_model_wording(self):
        os.environ["A2_MODEL"] = "claude"
        saved = model.judge
        model.judge = lambda t: {
            "skills": ["Java"], "skills_op": "AND", "location": None, "availability": None,
            "work_mode": None, "seniority": {"kind": "years", "min": 5, "contains": "Senior"},
            "ambiguities": [{"slot": "seniority", "dominant": False,
                             "evidence": "The recruiter said senior without a number"}]}
        try:
            r = app.handle({"text": "senior Java developers"})
            self.assertEqual(r["question"]["text"], "What do you mean by 'senior'?")
        finally:
            model.judge = saved
            os.environ.pop("A2_MODEL", None)

    def test_only_one_question_even_with_several_unclear_parts(self):
        r = app.handle({"text": "senior Java Python devs available now"})
        self.assertEqual(r["mode"], "ask")
        self.assertIsInstance(r["question"], dict)


class TestHonestNotes(unittest.TestCase):
    """Why? must never blame the strategy setting for something the recruiter did."""

    def test_answering_with_auto_mentions_no_setting(self):
        r = app.handle({"text": "senior Java developers", "mode": "auto", "choices": {"seniority": 1},
                        "last": {"slot": "seniority", "answered": True}})
        self.assertEqual(r["mode"], "show")
        self.assertFalse(any("strategy setting" in n for n in r["why"]["notes"]))

    def test_search_anyway_is_the_recruiters_choice(self):
        r = app.handle({"text": "senior Java developers", "mode": "show", "last": {"anyway": True}})
        self.assertEqual(r["mode"], "show")
        self.assertIn("You chose to search without answering; the rule would have asked first.", r["why"]["notes"])
        self.assertFalse(any("strategy setting" in n for n in r["why"]["notes"]))
        self.assertTrue(r["reason"].startswith("Searched with my best guess, as you asked."))
        self.assertTrue(r["reason"].endswith(" " + r["hint"]))

    def test_a_real_setting_is_still_reported(self):
        r = app.handle({"text": "senior Java developers", "mode": "show"})
        self.assertTrue(any("strategy setting chose show" in n for n in r["why"]["notes"]))


class TestControls(unittest.TestCase):
    def test_every_strategy_can_be_forced_for_comparison(self):
        for mode in ("act", "show", "ask"):
            self.assertEqual(app.handle({"text": "senior Java developers", "mode": mode})["mode"], mode)

    def test_threshold_is_used_and_reported(self):
        r = app.handle({"text": "senior Java developers", "theta": 0.1})
        self.assertEqual(r["theta"], 0.1)
        self.assertEqual(r["mode"], "show")  # the lists share 17%, which is above 10%

    def test_interpreter_is_labelled_with_its_status(self):
        self.assertEqual(app.handle({"text": "Java developers"})["interpreter"],
                         "rule-based stand-in (simulated)")

    def test_fallback_keeps_the_simulated_label(self):
        os.environ["A2_MODEL"] = "claude"
        saved, model.judge = model.judge, (lambda t: None)
        try:
            label = app.handle({"text": "Java developers"})["interpreter"]
            self.assertTrue(label.startswith("rule-based stand-in (simulated)"))
            self.assertIn("live model was unavailable", label)
        finally:
            model.judge = saved
            os.environ.pop("A2_MODEL", None)

    def test_threshold_is_kept_in_range(self):
        self.assertEqual(app.handle({"text": "senior Java developers", "theta": 5})["theta"], 1.0)
        self.assertEqual(app.handle({"text": "senior Java developers", "theta": -1})["theta"], 0.0)
        self.assertEqual(app.handle({"text": "senior Java developers", "theta": "abc"})["theta"], 0.5)

    def test_dropped_items_are_reported(self):
        self.assertEqual(app.handle({"text": "Java developers"})["dropped"], [])


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


class TestWhy(unittest.TestCase):
    """Issue #27: the "Why?" rows are the rule's own comparison, not a separate story."""

    def test_rows_match_the_rule(self):
        import interpret
        import strategy
        for text in ("senior Java developers", "Python devs near London", "Java Python devs in London"):
            with self.subTest(text=text):
                r = app.handle({"text": text})
                d = strategy.decide(interpret.interpret_rules(text))
                self.assertEqual(len(r["why"]["rows"]), len(d["comparisons"]))
                for row, c in zip(r["why"]["rows"], d["comparisons"]):
                    self.assertEqual([x["count"] for x in row["readings"]], [c["chosen"], c["other"]])
                    self.assertEqual(row["overlap"], round(c["overlap"], 2))
                self.assertEqual(r["why"]["rule_mode"], d["mode"])

    def test_verdict_follows_theta(self):
        ask = app.handle({"text": "Python devs near London", "theta": 0.9})["why"]["rows"][0]["verdict"]
        show = app.handle({"text": "Python devs near London", "theta": 0.1})["why"]["rows"][0]["verdict"]
        self.assertEqual(ask, "below θ (90%): ask")
        self.assertEqual(show, "at least θ (10%): show, don't ask")

    def test_overrides_are_explained(self):
        forced = app.handle({"text": "senior Java developers", "mode": "act"})["why"]
        self.assertIn("the rule alone would have chosen ask", forced["notes"][0])
        edited = app.handle({"text": "senior Java developers", "choices": {"seniority": 1}})["why"]
        self.assertTrue(any("You changed the reading" in n for n in edited["notes"]))

    def test_nothing_unclear_says_so(self):
        w = app.handle({"text": "Java developers in London"})["why"]
        self.assertEqual(w["rows"], [])
        self.assertIn("nothing to compare", w["summary"])

    def test_percent_never_hides_which_side_of_theta(self):
        self.assertEqual(replies.pct(0.497, 0.5), "49.7%")
        self.assertEqual(replies.pct(0.5, 0.5), "50%")


class TestChangeMessages(unittest.TestCase):
    """UX review fix 1: after an edit, the reason line says what changed and what it gave."""

    def test_operator_switch(self):
        r = app.handle({"text": "Java with Python in London", "op": "OR", "last": {"op": True}})
        self.assertEqual(r["reason"], "You switched AND → OR: %d candidates." % r["count"])

    def test_answer_echoes_the_question(self):
        r = app.handle({"text": "senior Java developers", "choices": {"seniority": 1},
                        "last": {"slot": "seniority", "answered": True}})
        self.assertTrue(r["reason"].startswith("I asked what you meant by 'senior'; you chose 'Senior' in their job title"))

    def test_chip_edit(self):
        r = app.handle({"text": "Python devs near London", "choices": {"location": 1}, "last": {"slot": "location"}})
        self.assertEqual(r["reason"], "You chose London only: %d candidates." % r["count"])

    def test_unknown_last_control_still_reports_the_count(self):
        r = app.handle({"text": "Python devs near London", "choices": {"location": 1}, "last": "nonsense"})
        self.assertEqual(r["reason"], "Updated with your changes: %d candidates." % r["count"])

    def test_forced_mode_copy_is_for_the_recruiter_and_the_rule_is_logged(self):
        import log
        r = app.handle({"text": "senior Java developers", "mode": "show"})
        self.assertEqual(r["reason"], "Showing my reading so you can edit it.")
        self.assertEqual(log.entry({"mode": "show"}, r)["rule_mode"], "ask")
