"""Write actions (issue #26): no write without confirming, Cancel changes nothing, Undo restores."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import store  # noqa: E402

CLOSE = {"action": "close", "search": {"text": "open Java roles"}}
SHORT = {"action": "shortlist", "search": {"text": "Python people at Ironbridge Bank"}}


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

    def confirm(self, payload):
        plan = app.plan_action(payload)
        return plan, app.apply_action(dict(payload, fingerprint=plan.get("fingerprint")), self.tmp.name)

    def log(self):
        path = os.path.join(self.tmp.name, "events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(x) for x in f]


class TestConfirm(Base):
    def test_plan_lists_exactly_the_records_and_writes_nothing(self):
        plan = app.plan_action(CLOSE)
        found = app.handle(CLOSE["search"])
        self.assertTrue(plan["valid"])
        self.assertEqual(len(plan["changes"]), found["count"])
        self.assertEqual(plan["read_as"], found["read_as"])
        self.assertFalse(os.path.exists(store.PATH))  # Cancel = nothing to undo

    def test_no_write_without_the_confirmed_fingerprint(self):
        for fingerprint in (None, "", "0000000000000000"):
            with self.subTest(fingerprint=fingerprint):
                out = app.apply_action(dict(CLOSE, fingerprint=fingerprint), self.tmp.name)
                self.assertFalse(out["ok"])
                self.assertFalse(os.path.exists(store.PATH))

    def test_a_stale_confirmation_is_refused_with_the_new_list(self):
        old = app.plan_action(CLOSE)
        self.confirm({"action": "close", "search": {"text": "open Java roles at Bluefin"}})  # one of them closes
        out = app.apply_action(dict(CLOSE, fingerprint=old["fingerprint"]), self.tmp.name)
        self.assertFalse(out["ok"])
        self.assertEqual(len(out["plan"]["changes"]), len(old["changes"]) - 1)

    def test_writes_are_refused_while_a_question_is_open(self):
        plan = app.plan_action({"action": "shortlist", "job_id": 1, "search": {"text": "senior Java developers"}})
        self.assertFalse(plan["valid"])
        self.assertIn("Answer the question first", plan["error"])

    def test_action_must_fit_the_target(self):
        self.assertFalse(app.plan_action({"action": "close", "search": {"text": "Java developers"}})["valid"])
        self.assertFalse(app.plan_action({"action": "delete", "search": {"text": "Java roles"}})["valid"])


class TestClose(Base):
    def test_closed_jobs_leave_an_open_roles_search_at_once(self):
        before = app.handle(CLOSE["search"])["count"]
        plan, out = self.confirm(CLOSE)
        self.assertTrue(out["ok"])
        self.assertEqual(out["changed"], before)
        self.assertEqual(app.handle(CLOSE["search"])["count"], 0)

    def test_already_closed_jobs_are_skipped_and_said_so(self):
        self.confirm({"action": "close", "search": {"text": "Java roles at Bluefin"}})
        plan = app.plan_action({"action": "close", "search": {"text": "Java roles"}})
        self.assertTrue(plan["skipped"])
        self.assertTrue(all(s["why"] == "already closed" for s in plan["skipped"]))

    def test_undo_restores_the_exact_previous_state(self):
        before = store.read()
        self.confirm(CLOSE)
        self.assertTrue(app.undo_action(self.tmp.name)["ok"])
        self.assertEqual(store.read(), before)
        self.assertFalse(app.undo_action(self.tmp.name)["ok"])  # nothing left to undo

    def test_undo_says_what_it_did(self):
        plan, out = self.confirm(CLOSE)
        self.assertEqual(app.undo_action(self.tmp.name)["done"],
                         "Reopened the %d job%s you closed" % (out["changed"], "" if out["changed"] == 1 else "s"))


class TestShortlist(Base):
    def test_a_job_must_be_chosen_and_open(self):
        self.assertIn("Choose a job", app.plan_action(SHORT)["error"])
        closed = next(j for j in app.search.load("jobs") if j["status"] == "closed")
        self.assertFalse(app.plan_action(dict(SHORT, job_id=closed["id"]))["valid"])

    def test_shortlist_then_repeat_skips_those_already_on_it(self):
        plan, out = self.confirm(dict(SHORT, job_id=1))
        self.assertEqual(out["changed"], 8)
        again = app.plan_action(dict(SHORT, job_id=1))
        self.assertFalse(again["valid"])
        self.assertEqual(len(again["skipped"]), 8)
        job = next(j for j in app.search.load("jobs") if j["id"] == 1)
        self.assertEqual(len(job["shortlist"]), 8)

    def test_undo_takes_back_only_the_last_shortlist(self):
        self.confirm(dict(SHORT, job_id=1))
        first = store.read()["shortlists"]
        self.confirm({"action": "shortlist", "job_id": 1, "search": {"text": "Go people"}})
        done = app.undo_action(self.tmp.name)["done"]
        self.assertEqual(store.read()["shortlists"], first)
        self.assertTrue(done.startswith("Took the ") and "off the shortlist for " in done, done)


class TestLog(Base):
    def test_every_write_and_undo_is_logged(self):
        self.confirm(CLOSE)
        app.undo_action(self.tmp.name)
        events = [e["event"] for e in self.log()]
        self.assertEqual(events, ["write", "undo"])
        self.assertEqual(self.log()[0]["action"], "close")

    def test_refused_writes_are_not_logged_as_writes(self):
        app.apply_action(dict(CLOSE, fingerprint="nope"), self.tmp.name)
        self.assertEqual(self.log(), [])


if __name__ == "__main__":
    unittest.main()
