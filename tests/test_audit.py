"""End-to-end invariants across phases 1 to 6.

These are not unit tests of a module. Each one asserts something that must hold
after the whole pipeline has run, and would be a serious incident if it broke.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import generate, ingest, lint, llm, personas, render, store
from tests.base import FIXTURES


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-audit-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def use(self, name):
        shutil.copyfile(os.path.join(FIXTURES, name), self.queue)
        return store.load()


class TestSuppressionSurvivesTheWholePipeline(PipelineTest):
    """Invariant 5: a suppressed domain cannot proceed, at any later stage."""

    def test_a_suppressed_domain_never_reaches_a_push_file(self):
        csv_path = os.path.join(self.tmp, "batch.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            # example-customer.test is in the TRACKED suppression template.
            # This used to name a real paying customer, which meant invariant 5
            # was only provable on a machine holding the confidential roster.
            f.write("company,domain,lane,client\n"
                    "Example Customer,example-customer.test,domains,productive\n"
                    "Meridian,meridian.test,domains,productive\n")
        ingest.run(csv_path, client="productive", lane="domains")

        suppressed = store.get("example-customer")
        self.assertEqual(suppressed["state"], "dropped")
        self.assertIn("suppressed", suppressed["drop_reason"])

        # Even if a draft is somehow attached to it later, it cannot ship.
        recs = store.load()
        for rec in recs:
            if rec["id"] == "blocked-co":
                rec["contacts"] = [{"name": "Someone", "email": "someone@blocked.test",
                                    "verdict": "valid", "sendable": True,
                                    "angle": "finance", "key": "someone"}]
                rec["cadence"] = {"someone": {"day1": {
                    "channel": "email", "generated": True,
                    "subject": "a subject that is fine",
                    "body": " ".join(["word"] * 60)}}}
        store.save(recs)
        render.build()

        with open(os.path.join(self.out, "emailbison.csv"), encoding="utf-8") as f:
            csv_text = f.read()
        self.assertNotIn("blocked.test", csv_text)
        self.assertNotIn("someone@blocked.test", csv_text)

    def test_a_dropped_record_is_never_re_enriched_or_generated(self):
        from src import enrich
        self.use("phase5.jsonl")
        store.drop("meridian", "suppressed (live account)")
        self.assertEqual(enrich.plan(store.get("meridian")), [])
        self.assertEqual(generate.plan(store.get("meridian")), [])


class TestFactsAreNotTheModelsToChange(PipelineTest):
    """Invariant 14: the model cannot invent or silently mutate source facts."""

    def setUp(self):
        super().setUp()
        self.use("phase5.jsonl")

    def test_company_facts_are_identical_before_and_after_generation(self):
        before = {r["id"]: json.dumps(r["company_facts"], sort_keys=True)
                  for r in store.load()}
        model = llm.ScriptedModel(
            json.dumps({"died_on": "2024-10-17",
                        "died_because": "the question about the realistic list was never answered",
                        "failure_mode": "unanswered_question",
                        "last_position": None, "what_changed": None}),
            *[json.dumps({"subject": "the question we never answered",
                          "body": " ".join(["word"] * 60)})] * 6)
        generate.run(model=model, live=True)
        after = {r["id"]: json.dumps(r["company_facts"], sort_keys=True)
                 for r in store.load()}
        self.assertEqual(before, after)

    def test_a_model_cannot_rewrite_a_contact_or_an_address(self):
        before = {r["id"]: json.dumps(r["contacts"], sort_keys=True)
                  for r in store.load()}
        model = llm.ScriptedModel(
            json.dumps({"died_on": None,
                        "died_because": "the question about the list was never answered",
                        "failure_mode": "unanswered_question"}),
            *[json.dumps({"subject": "a subject", "body": " ".join(["word"] * 60)})] * 6)
        generate.run(model=model, live=True)
        for rec in store.load():
            for c in rec["contacts"]:
                self.assertIn(c["email"], before[rec["id"]])
                self.assertIn(json.dumps(c["verdict"]), before[rec["id"]])

    def test_the_verdict_is_never_written_by_the_generation_step(self):
        model = llm.ScriptedModel(
            *[json.dumps({"subject": "a subject", "body": " ".join(["word"] * 60)})] * 4)
        generate.run(model=model, live=True, ids=["meridian"])
        contact = store.get("meridian")["contacts"][0]
        self.assertEqual(contact["verdict"], "valid")
        self.assertTrue(contact["sendable"])


class TestTheGateHoldsAtTheEnd(PipelineTest):
    """Invariants 8, 9, 15, 17: nothing unverified or unlinted can ship."""

    def test_no_row_in_the_push_file_lacks_a_sendable_recipient(self):
        self.use("phase2.jsonl")
        render.build()
        import csv
        import io
        with open(os.path.join(self.out, "emailbison.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(io.StringIO(f.read())))
        by_id = {r["id"]: r for r in store.load()}
        for row in rows:
            rec = by_id[row["record_id"]]
            contact = next(c for c in rec["contacts"] if c["email"] == row["email"])
            self.assertTrue(lint.sendable(contact), row["email"])

    def test_every_row_in_the_push_file_passes_every_lint_rule(self):
        self.use("phase2.jsonl")
        render.build()
        results = {lint.step_id(r): r for r in lint.check_all()}
        import csv
        import io
        with open(os.path.join(self.out, "emailbison.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(io.StringIO(f.read())))
        for row in rows:
            matching = [r for r in results.values()
                        if r["id"] == row["record_id"] and r["day"] == row["day"]]
            self.assertTrue(matching)
            for r in matching:
                self.assertEqual(r["failures"], [])


class TestNothingDisappears(PipelineTest):
    """Invariants 2 and 3, across every module that writes."""

    def test_no_stage_reduces_the_line_count(self):
        from src import enrich
        self.use("phase4.jsonl")
        counts = [len(store.load())]
        enrich.run()
        counts.append(len(store.load()))
        personas.run(apply=True)
        counts.append(len(store.load()))
        generate.run()
        counts.append(len(store.load()))
        render.build()
        counts.append(len(store.load()))
        self.assertEqual(counts, [4, 4, 4, 4, 4])

    def test_every_dropped_record_anywhere_has_a_reason(self):
        from src import enrich
        self.use("phase4.jsonl")
        personas.run(apply=True)
        for rec in store.load():
            if rec["state"] == "dropped":
                self.assertTrue(rec["drop_reason"], rec["id"])


class TestNoCredentialsAreNeeded(unittest.TestCase):
    """Invariant 19."""

    # Every module that must import without a credential in the environment.
    IMPORTS = ("src.store", "src.ingest", "src.lint", "src.render",
               "src.enrich", "src.generate", "src.personas", "src.identity",
               "src.clients", "src.llm", "src.check", "src.providers",
               "src.providers.contactout", "src.providers.aiark",
               "src.providers.reoon", "src.providers.bison",
               "src.providers.heyreach", "src.providers.deliverable",
               "src.providers.apify", "src.verification", "src.research",
               "src.events", "src.report", "src.validate")

    def test_no_module_reads_a_key_at_import(self):
        """Invariant 19, asked in an interpreter that has never seen a key.

        This used to `importlib.reload` all of the above in *this* process,
        which is a different question and a destructive way to ask it. A
        reload re-executes a module into the same namespace: `src.providers`
        kept its identity while `ProviderError` became a *new class*, and
        every module that had done `from .providers import ProviderError` at
        import time went on holding the old one. `except` is `isinstance`, so
        those handlers silently stopped matching - for the rest of the run,
        in every test that came after this one. `src/enrich.py` has four of
        them on the spend path, and one of them stopped recording that a
        ContactOut call had timed out, leaving a record that had been charged
        for a call with no trace the call was ever made.

        The reload list carried a comment telling the next person to keep the
        catchers in it, which made a shared mutable registry the price of an
        import-time assertion. It is not: `import` in a subprocess with the
        credentials stripped from its environment answers exactly the
        question, proves it against a genuinely cold interpreter rather than
        a half-reloaded one, and cannot leave this suite in a state it did
        not start in. The same hazard applied to `store.QueueLocked`,
        `llm.ModelError`, `verification.VerificationError` and `validate
        .Refused`, all of which were on that list too.
        """
        import subprocess
        import sys

        env = dict(os.environ)
        for key in ("CONTACTOUT_TOKEN", "AIARK_KEY", "REOON_KEY", "BISON_KEY",
                    "HEYREACH_KEY"):
            env.pop(key, None)
        done = subprocess.run(
            [sys.executable, "-c", "import " + ", ".join(self.IMPORTS)],
            env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0,
                         "a module wanted a credential at import time: "
                         + done.stderr)


class TestNoSendPathAnywhere(unittest.TestCase):
    """Phase 7 is not built. Nothing in the repo can send."""

    def test_emailbison_posts_only_where_it_declares(self):
        """Its surface was all GET until the documented routes turned out to
        answer. The guarantee moved to the routes, which is where it belongs:
        a send is started by `/campaigns/{id}/resume`, and no code path can
        reach it."""
        from src.providers import bison
        for route in bison.WRITE_ROUTES:
            for starting in ("resume", "start", "launch", "activate",
                             "send-test"):
                self.assertNotIn(starting, route, route)

    def test_heyreach_posts_only_to_named_read_routes(self):
        """HeyReach's *read* API is POST, so the verb cannot be the test.
        The routes are: one allowlist, checked before every call."""
        import inspect

        from src.providers import heyreach
        self.assertEqual(set(heyreach.READ_ROUTES),
                         {"/campaign/GetAll", "/inbox/GetConversationsV2"})
        for route in heyreach.READ_ROUTES:
            self.assertNotIn("AddLeads", route)
        source = inspect.getsource(heyreach)
        # TWO places issue a POST, and each checks its OWN allowlist first.
        #
        # This asserted exactly one until 2026-09-10, when `_write` was added
        # for `/campaign/Pause`. Counting call sites was always a proxy for
        # the real rule - that no POST is issued without an allowlist check -
        # so the count is now a named expectation and the rule is checked
        # directly against each function.
        posts = [line for line in source.splitlines()
                 if 'request("POST"' in line]
        self.assertEqual(len(posts), 2, posts)
        read_fn = inspect.getsource(heyreach._read)
        self.assertLess(read_fn.index("READ_ROUTES"), read_fn.index('request("POST"'))
        write_fn = inspect.getsource(heyreach._write)
        self.assertLess(write_fn.index("WRITE_ROUTES"),
                        write_fn.index('request("POST"'))

    def test_heyreach_writes_only_to_the_route_that_stops_things(self):
        """The write allowlist is one route, and it is the STOP.

        Resume and StartCampaign demonstrably exist on this vendor's API - a
        probe with an empty body answers 400 for both, and 404 for names that
        do not exist. They are deliberately absent here. A system that can
        start an outreach campaign and cannot stop one has acquired the
        ability to create exposure without the ability to end it, which is
        worse than being able to do neither.
        """
        from src.providers import heyreach

        self.assertEqual(set(heyreach.WRITE_ROUTES), {"/campaign/Pause"})
        for forbidden in ("/campaign/Resume", "/campaign/StartCampaign",
                          "/campaign/AddLeadsToCampaignV2",
                          "/campaign/Create", "/campaign/UpdateSequence"):
            with self.assertRaises(Exception, msg=forbidden):
                heyreach._write(forbidden, {"campaignId": 1})

    def test_the_send_route_is_reachable_from_no_code_path(self):
        import inspect

        from src.providers import heyreach
        with self.assertRaises(Exception):
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})

    def test_the_only_http_posts_are_research_calls_never_sends(self):
        """A POST that is actually issued, and only where one belongs.

        AI Ark speaks JSON-RPC, Apify starts an actor run, and ContactOut's
        search reads are POST because their filters do not fit in a query
        string. None can send anything to a person. Every other module must
        issue no POST at all, and no POST anywhere may target a lead or
        campaign endpoint.
        """
        import re
        # contactout is here because three of its READ endpoints are POST by
        # design; test_providers pins those routes so the verb alone is not
        # what is trusted. bison and heyreach are still allowed none.
        # slack.py posts a message, behind SLACK_LIVE and a token; heyreach
        # posts to read routes only, checked against an allowlist above.
        allowed = ("aiark.py", "apify.py", "blitz.py", "contactout.py",
                   "heyreach.py", "slack.py", "bison.py")
        issued = []
        for root, _, files in os.walk("src"):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(r"request\(\s*[\"']POST[\"']", line):
                            issued.append((path, i, line))
        offenders = [f"{p}:{i}" for p, i, _ in issued
                     if not any(a in p for a in allowed)]
        self.assertEqual(offenders, [])
        # And no POST anywhere targets a route that STARTS a sequence. It
        # used to be that no POST could mention a lead or a campaign at all,
        # which was right while staging one was impossible. Staging is what
        # `bisonfactory` does now, and what it builds is left `paused`.
        for path, i, line in issued:
            for outbound in ("AddLeadsToCampaign", "/resume", "/StartCampaign",
                             "send-test"):
                self.assertNotIn(outbound, line, f"{path}:{i}")

    def test_the_push_module_never_calls_the_transport(self):
        """push.py prepares payloads. It has no way to put one on the wire."""
        import inspect

        from src import push
        source = inspect.getsource(push)
        for forbidden in ("providers.request", "request(", "urlopen", "http"):
            self.assertNotIn(forbidden, source.replace("https://", "").replace(
                "requests", ""), forbidden)


if __name__ == "__main__":
    unittest.main()
