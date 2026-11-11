"""Typed follow-up commands (issue #42): recognised only when clearly a command, resolved to a job,
and never written without the usual confirmation."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import commands  # noqa: E402
import search  # noqa: E402
import store  # noqa: E402

PEOPLE = {"text": "Java developers"}          # acts: 45 candidates, no question
JOBS = {"text": "open Java roles"}            # acts: 3 jobs
ASKING = {"text": "senior Java developers in London"}  # the rule asks about 'senior'


class TestDetection(unittest.TestCase):
    def test_commands_are_recognised(self):
        cases = {
            "add them to the Java shortlist at Bluefin": ("shortlist", ["Java", "Bluefin"]),
            "shortlist these for the Senior Backend Engineer role": ("shortlist", ["Senior", "Backend", "Engineer"]),
            "Shortlist them": ("shortlist", []),
            "can you shortlist them for Bluefin?": ("shortlist", ["Bluefin"]),
            "put those on the shortlist for Northwind": ("shortlist", ["Northwind"]),
            "please add all of them to the shortlist": ("shortlist", []),
            "shortlist everyone": ("shortlist", []),
            "close these": ("close", []),
            "close them all": ("close", []),
            "Close them.": ("close", []),
            "please close all of these": ("close", []),
            "close the results": ("close", []),
            "close these 3 jobs": ("close", []),
        }
        for text, (action, words) in cases.items():
            with self.subTest(text=text):
                self.assertEqual(commands.parse(text), {"action": action, "job_words": words})

    def test_searches_that_contain_the_verbs_stay_searches(self):
        for text in ("close to London", "Java developers close to London", "jobs close to Manchester",
                     "close by Leeds", "closed jobs", "show me all closed jobs", "closed jobs at Bluefin",
                     "Python developers who closed deals", "shortlisted people", "shortlisted candidates",
                     "everyone on the shortlist for Bluefin", "people on the Java shortlist",
                     "who is on the shortlist", "add Python to the search", "Python developers",
                     "close Java jobs in London", "close all Java jobs in London", "", "   "):
            with self.subTest(text=text):
                self.assertIsNone(commands.parse(text))


    def test_verb_naming_the_job_is_a_command(self):
        cases = {
            "shortlist for the Senior Backend Engineer role": ["Senior", "Backend", "Engineer"],
            "Shortlist for the Java role at Bluefin": ["Java", "Bluefin"],
            "please shortlist for Northwind": ["Northwind"],
            "add to the shortlist for Bluefin": ["Bluefin"],
            "ok, put on the Java shortlist": ["Java"],
        }
        for text, words in cases.items():
            with self.subTest(text=text):
                self.assertEqual(commands.parse(text), {"action": "shortlist", "job_words": words})

    def test_verb_describing_people_is_a_search(self):
        # The recruiter is describing a search, not pointing at the results on screen.
        for text in ("shortlist Java developers in London", "Shortlist senior Python people",
                     "can you shortlist Java developers", "add Java developers to the shortlist",
                     "close", "close the jobs", "close Bluefin jobs", "close Java jobs in London"):
            with self.subTest(text=text):
                self.assertIsNone(commands.parse(text))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = store.PATH
        store.PATH = os.path.join(self.tmp.name, "state", "state.json")
        os.environ["A2_LOG"] = "on"

    def tearDown(self):
        store.PATH = self.old
        os.environ["A2_LOG"] = "off"
        self.tmp.cleanup()

    def command(self, text, search_payload=PEOPLE):
        return app.command_action({"text": text, "search": search_payload}, self.tmp.name)

    def log(self):
        path = os.path.join(self.tmp.name, "events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(x) for x in f]


class TestJobs(Base):
    def test_one_job_matches(self):
        out = self.command("shortlist these for the Senior Backend Engineer role")
        self.assertEqual(out, {"kind": "plan", "action": "shortlist", "job_id": 4,
                               "reason": "You asked to shortlist the 45 candidates on screen for "
                                         "Senior Backend Engineer at Bluefin Analytics (London)."})

    def test_shortlist_for_a_role_shortlists_what_is_on_screen(self):
        self.assertEqual(self.command("shortlist Java developers in London"), {"kind": "search"})
        out = self.command("shortlist for the Senior Backend Engineer role")
        self.assertEqual((out["kind"], out["job_id"]), ("plan", 4))
        self.assertIn("the 45 candidates on screen", out["reason"])
        self.assertFalse(os.path.exists(store.PATH))

    def test_company_and_skill_narrow_to_one_job(self):
        out = self.command("add them to the Java shortlist at Bluefin")
        self.assertEqual((out["kind"], out["job_id"]), ("plan", 4))

    def test_several_jobs_match_so_it_asks(self):
        out = self.command("shortlist them for the Java role")
        self.assertEqual(set(out), {"kind", "action", "text", "reason", "options"})
        self.assertEqual((out["kind"], out["action"], out["text"]), ("ask", "shortlist", "Which job did you mean?"))
        self.assertEqual(out["reason"], "'Java' matches 4 open jobs.")
        self.assertEqual(sorted(o["job_id"] for o in out["options"]), [6, 8, 19, 20])
        self.assertTrue(all(set(o) == {"job_id", "label"} for o in out["options"]))

    def test_several_matched_words_read_as_a_list(self):
        out = self.command("shortlist them for the Senior SAP Consultant role")
        self.assertEqual(out["kind"], "ask")
        self.assertEqual(out["reason"], "'Senior', 'SAP' and 'Consultant' match 2 open jobs.")

    def test_options_are_capped_and_the_rest_are_mentioned(self):
        out = self.command("shortlist these for a developer role")
        self.assertEqual(out["kind"], "ask")
        self.assertEqual(len(out["options"]), app.MAX_OPTIONS)
        self.assertIn("'developer' matches 10 open jobs.", out["reason"])
        self.assertIn("other 4", out["reason"])

    def test_no_job_matches_leaves_the_picker_empty(self):
        out = self.command("shortlist them for the Rust role")
        self.assertEqual((out["kind"], out["job_id"]), ("plan", None))
        self.assertIn("choose the job in the dialog", out["reason"])
        self.assertIn("'Rust'", out["reason"])
        self.assertIsNone(self.command("shortlist them")["job_id"])

    def test_closed_jobs_are_never_offered(self):
        closed = {j["id"] for j in search.load("jobs") if j["status"] == "closed"}
        out = self.command("shortlist them for Copperleaf")  # its only job is closed
        self.assertEqual((out["kind"], out["job_id"]), ("plan", None))
        for text in ("shortlist them for a Senior Engineer role", "shortlist them for SAP Consultant",
                     "shortlist these for a developer role"):
            out = self.command(text)
            ids = [o["job_id"] for o in out.get("options", [])] + [out.get("job_id")]
            with self.subTest(text=text):
                self.assertFalse(closed & set(ids))

    def test_a_job_closed_by_the_recruiter_is_not_offered(self):
        store.save({"job_status": {"4": "closed"}, "shortlists": {}, "undo": []})
        out = self.command("shortlist these for the Senior Backend Engineer role")
        self.assertNotEqual(out.get("job_id"), 4)
        self.assertNotIn(4, [o["job_id"] for o in out.get("options", [])])


class TestErrors(Base):
    def test_close_on_a_candidates_search(self):
        out = self.command("close them")
        self.assertEqual(out, {"kind": "error", "error": "This action works on jobs; the search found candidates."})

    def test_shortlist_on_a_jobs_search(self):
        out = self.command("shortlist them", JOBS)
        self.assertEqual(out, {"kind": "error", "error": "This action works on candidates; the search found jobs."})

    def test_a_command_while_the_search_is_asking(self):
        self.assertEqual(app.handle(ASKING)["mode"], "ask")
        out = self.command("shortlist these for Bluefin", ASKING)
        self.assertEqual(out, {"kind": "error", "error": app.ANSWER_FIRST})
        self.assertEqual(app.plan_action({"action": "shortlist", "search": ASKING})["error"], app.ANSWER_FIRST)

    def test_not_a_command_or_no_search_is_a_new_search(self):
        self.assertEqual(self.command("close to London"), {"kind": "search"})
        self.assertEqual(self.command("close these", {}), {"kind": "search"})
        self.assertEqual(app.command_action({"text": "close these"}), {"kind": "search"})
        self.assertEqual(self.log(), [])  # a new search is logged by /api/search, not here


class TestEndToEnd(Base):
    def test_command_then_plan_is_valid_and_nothing_is_written(self):
        before = store.read()
        out = self.command("add them to the Java shortlist at Bluefin")
        self.assertEqual(store.read(), before)
        self.assertFalse(os.path.exists(store.PATH))
        plan = app.plan_action({"action": out["action"], "job_id": out["job_id"], "search": PEOPLE})
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["job"], "Senior Backend Engineer at Bluefin Analytics (London)")
        self.assertEqual(len(plan["changes"]), app.handle(PEOPLE)["count"])
        self.assertFalse(os.path.exists(store.PATH))

    def test_close_command_then_plan(self):
        out = self.command("close them all", JOBS)
        self.assertEqual(out, {"kind": "plan", "action": "close", "job_id": None,
                               "reason": "You asked to close the 3 jobs on screen."})
        plan = app.plan_action({"action": out["action"], "job_id": out["job_id"], "search": JOBS})
        self.assertTrue(plan["valid"])
        self.assertFalse(os.path.exists(store.PATH))

    def test_an_asked_option_plans_too(self):
        out = self.command("shortlist them for the Java role")
        for option in out["options"]:
            plan = app.plan_action({"action": "shortlist", "job_id": option["job_id"], "search": PEOPLE})
            with self.subTest(job=option["label"]):
                self.assertTrue(plan["valid"])
                self.assertEqual(plan["job"], option["label"])
        self.assertFalse(os.path.exists(store.PATH))

    def test_command_turns_are_logged(self):
        self.command("shortlist these for the Senior Backend Engineer role")
        self.command("close them")
        lines = self.log()
        self.assertEqual([(x["event"], x["kind"], x["action"], x["job_id"]) for x in lines],
                         [("command", "plan", "shortlist", 4), ("command", "error", "close", None)])

    def test_the_route_is_served(self):
        self.assertIs(app.Handler.ROUTES["/api/command"], app.command_action)


if __name__ == "__main__":
    unittest.main()
