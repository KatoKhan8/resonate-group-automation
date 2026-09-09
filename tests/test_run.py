"""The runner. BUILD-SPEC phase 8.

Resumable, isolated per record, dry by default. The crash-and-resume test is
the one that matters: a batch that dies at record 40 of 500 must not pay for
records 1 to 39 again.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import enrich, generate, llm, personas, push, run, store
from tests.base import FIXTURES, ProviderTest, qualify_everything

BODY = ("Ivana, you run finance across five offices in three countries, which is the "
        "point where month end stops being an afternoon and starts being a week. The "
        "part I would ask about is how long it takes to know which client work actually "
        "made money, because most teams that size can answer revenue quickly and margin "
        "slowly.\n\nIs that the shape of it, or have you already solved it?")


def scripted(n=60):
    answers = []
    for _ in range(n):
        answers.append(json.dumps({"angle": "finance", "evidence": ["Zagreb HR"]}))
        answers.append(json.dumps({"subject": "five offices, one finance function",
                                   "body": BODY}))
    return llm.ScriptedModel(*answers)


class RunnerTest(ProviderTest):
    fixture = "phase4.jsonl"

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-runner-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, self.fixture), self.queue)
        self._prev = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out
        # This suite is about the runner - which stages run, what resumes,
        # what is not paid for twice. Person-level enrichment is gated on an
        # ICP verdict, and without one every record stays `partial` waiting
        # for a later pass, which is correct but is not what these tests
        # measure. `tests/test_icp_spend_gate.py` covers the gate itself.
        qualify_everything()

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def rec(self, rid):
        return store.get(rid)


class TestDryByDefault(RunnerTest):
    def test_a_default_run_calls_no_provider_and_no_model(self):
        run.run()
        self.assertEqual(self.cassette.calls, [])

    def test_a_default_run_reports_what_it_would_do(self):
        report = run.run()
        self.assertFalse(report["spend"])
        self.assertIn("enrich", report)
        self.assertIn("render", report)
        self.assertIn("push", report)

    def test_live_is_refused_at_the_runner_too(self):
        with self.assertRaises(push.LiveSendNotEnabled):
            run.run(live=True)

    def test_the_cli_refuses_live_without_running_anything(self):
        self.assertEqual(run.main(["--live"]), 2)
        self.assertEqual(self.cassette.calls, [])

    def test_a_dry_run_never_marks_a_stage_done(self):
        run.run()
        for rec in store.load():
            self.assertNotEqual(rec["stages"]["enrich"]["status"], "done")


class TestTheWholePipeline(RunnerTest):
    def test_a_spending_run_walks_every_stage(self):
        report = run.run(spend=True, model=scripted())
        self.assertGreater(report["enrich"]["records"], 0)
        self.assertGreater(report["personas"]["records"], 0)
        self.assertIn("render", report)
        self.assertIn("push", report)
        self.assertEqual(report["failures"], [])

    def test_it_writes_the_review_sheet_and_the_push_file(self):
        run.run(spend=True, model=scripted())
        for name in ("review.html", "emailbison.csv", "summary.json"):
            self.assertTrue(os.path.exists(os.path.join(self.out, name)), name)

    def test_stages_are_recorded_on_each_record(self):
        run.run(spend=True, model=scripted())
        for rec in store.load():
            if rec["state"] in ("dropped", "pushed"):
                continue
            self.assertEqual(rec["stages"]["enrich"]["status"], "done")

    def test_a_run_can_be_limited_to_named_records(self):
        run.run(spend=True, model=scripted(), ids=["meridian"])
        self.assertEqual(self.rec("meridian")["stages"]["enrich"]["status"], "done")
        self.assertNotIn("enrich", self.rec("samename").get("stages", {}))


class TestResume(RunnerTest):
    """The phase 8 requirement: crash at record 40 of 500, restart at 40."""

    def test_a_finished_stage_is_not_paid_for_twice(self):
        run.run(spend=True, model=scripted())
        calls_after_first = len(self.cassette.calls)
        run.run(spend=True, model=scripted())
        self.assertEqual(len(self.cassette.calls), calls_after_first)

    def test_a_crash_mid_batch_leaves_the_finished_records_finished(self):
        original = enrich.enrich_record
        done = []

        def crash_on_third(rec, budget, live=False, log=None, **kw):
            if len(done) >= 2:
                raise RuntimeError("simulated crash at record 3")
            done.append(rec["id"])
            return original(rec, budget, live=live, log=log, **kw)

        enrich.enrich_record = crash_on_third
        try:
            report = run.run(spend=True, model=scripted())
        finally:
            enrich.enrich_record = original

        finished = [r["id"] for r in store.load()
                    if r.get("stages", {}).get("enrich", {}).get("status") == "done"]
        failed = [f["id"] for f in report["failures"]]
        self.assertEqual(len(finished), 2)
        self.assertTrue(failed)
        self.assertIn("simulated crash", str(report["failures"]))

    def test_the_resume_run_only_does_the_records_that_were_left(self):
        original = enrich.enrich_record
        done = []

        def crash_on_third(rec, budget, live=False, log=None, **kw):
            if len(done) >= 2:
                raise RuntimeError("simulated crash")
            done.append(rec["id"])
            return original(rec, budget, live=live, log=log, **kw)

        enrich.enrich_record = crash_on_third
        try:
            run.run(spend=True, model=scripted())
        finally:
            enrich.enrich_record = original

        already = {r["id"] for r in store.load()
                   if r.get("stages", {}).get("enrich", {}).get("status") == "done"}
        seen = []
        enrich_original = enrich.enrich_record

        def watch(rec, budget, live=False, log=None, **kw):
            seen.append(rec["id"])
            return enrich_original(rec, budget, live=live, log=log)

        enrich.enrich_record = watch
        try:
            run.run(spend=True, model=scripted())
        finally:
            enrich.enrich_record = enrich_original

        self.assertEqual(set(seen) & already, set())
        self.assertTrue(seen)

    def test_a_failed_record_carries_its_reason_for_a_human(self):
        original = personas.select

        def explode(rec, config=None):
            if rec["id"] == "meridian":
                raise RuntimeError("config went missing")
            return original(rec, config)

        personas.select = explode
        try:
            report = run.run(spend=True, model=scripted())
        finally:
            personas.select = original

        failure = next(f for f in report["failures"] if f["id"] == "meridian")
        self.assertEqual(failure["stage"], "personas")
        self.assertIn("config went missing", failure["why"])

    def test_one_bad_record_does_not_stop_the_others(self):
        original = personas.select

        def explode(rec, config=None):
            if rec["id"] == "meridian":
                raise RuntimeError("boom")
            return original(rec, config)

        personas.select = explode
        try:
            run.run(spend=True, model=scripted())
        finally:
            personas.select = original

        others = [r for r in store.load() if r["id"] != "meridian"
                  and r["state"] not in ("dropped", "pushed")]
        self.assertTrue(others)
        for rec in others:
            self.assertEqual(rec["stages"]["personas"]["status"], "done", rec["id"])

    def test_a_rerun_is_deterministic(self):
        run.run(spend=True, model=scripted())
        first = json.dumps({r["id"]: r["state"] for r in store.load()}, sort_keys=True)
        run.run(spend=True, model=scripted())
        second = json.dumps({r["id"]: r["state"] for r in store.load()}, sort_keys=True)
        self.assertEqual(first, second)

    def test_the_queue_never_shrinks_across_runs(self):
        before = len(store.load())
        run.run(spend=True, model=scripted())
        run.run(spend=True, model=scripted())
        self.assertEqual(len(store.load()), before)


class TestCostControl(RunnerTest):
    def test_the_cap_is_enforced_across_the_whole_batch(self):
        report = run.run(spend=True, model=scripted(), cap=1)
        self.assertLessEqual(report["enrich"]["spent"], 1)
        self.assertTrue(report["enrich"]["refused"])

    def test_without_spend_no_model_is_called_even_if_one_is_passed(self):
        model = scripted()
        run.run(model=model)
        self.assertEqual(model.prompts, [])

    def test_a_terminal_record_is_never_reprocessed(self):
        store.drop("meridian", "suppressed (live account)")
        run.run(spend=True, model=scripted())
        self.assertNotIn("enrich", self.rec("meridian").get("stages", {}))


class TestIngestStage(RunnerTest):
    def test_the_runner_can_ingest_first(self):
        path = os.path.join(self.tmp, "batch.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("company,domain,lane,client\nNewco,newco.test,domains,productive\n")
        report = run.run(source=path, client="productive", lane="domains")
        self.assertEqual(report["ingest"]["queued"], 1)
        self.assertIsNotNone(store.get("newco"))


class TestStateIsSufficient(RunnerTest):
    def test_everything_needed_to_resume_lives_in_the_queue_file(self):
        run.run(spend=True, model=scripted())
        with open(self.queue, encoding="utf-8") as f:
            raw = json.loads(f.readline())
        self.assertIn("stages", raw)
        self.assertIn("state", raw)
        self.assertIn("log", raw)

    def test_no_second_state_file_is_created(self):
        run.run(spend=True, model=scripted())
        work = os.path.dirname(self.queue)
        self.assertEqual(sorted(os.listdir(work)), ["queue.jsonl"])


if __name__ == "__main__":
    unittest.main()
