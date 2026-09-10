"""The controlled pre-production scenario. Task H.

One client. Two domains. At most three contacts each. Deterministic fake
providers, a deterministic fake model, approval required before anything is
push eligible, cadence prepared, payloads built, and a reply that pauses a
whole company.

Nothing is sent. No credit is spent. No model is called over a network. This is
the dress rehearsal, run end to end, offline, and asserted exactly.
"""
import json
import io
import os
import shutil
import tempfile
import unittest

from src import (approval, approve, cadence, clients, events, ingest, lint,
                 push, report, run, store)
from tests.base import FIXTURES, ProviderTest, qualify_everything

BATCH = os.path.join(FIXTURES, "preprod-batch.csv")
SUPPRESS = os.path.join(FIXTURES, "preprod-suppress.txt")

# ASSERTS NOTHING ABOUT THEM. This opened "you are running the finance side of
# a team working across several offices" - a statement about somebody else's
# company on a record that carries no `offices` fact. `test_e2e.py` had a
# near-identical copy under a constant named GOOD_BODY, and `demo.py` had two
# more; the claim rule added on 2026-09-10 found all four. Rewritten to
# generalise and ask, which is what the real canary note does.
BODY = ("{first}, month end stops being an afternoon and starts being a week "
        "of chasing once finance runs across more than one place. The question "
        "I would put to you is how long it takes to know which client work "
        "actually made money, because most teams can answer revenue quickly "
        "and margin slowly.\n\nIs that roughly the shape of it, or have you "
        "already put something in place?")


class FakeModel:
    """Deterministic and offline. Reads the prompt, returns the contract."""

    name = "preproduction-fake"

    def __init__(self):
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        if "# persona_angle" in prompt:
            title = "Head of Finance"
            for line in prompt.splitlines():
                if '"title"' in line:
                    title = line.split(":", 1)[1].strip().strip(",").strip('"')
                    break
            return json.dumps({"angle": "finance", "evidence": [title]})
        if "# draft" in prompt:
            first = "there"
            for token in ("Ćuk", "Ana", "Iris", "Petra", "梁伟"):
                if token in prompt:
                    first = token
                    break
            return json.dumps({"subject": "one week of month end, every month",
                               "body": BODY.format(first=first)})
        raise AssertionError(f"unexpected prompt: {prompt[:60]}")


class PreProduction(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-preprod-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out
        # Same reason as `tests/test_e2e.py`: the runner now screens MX before
        # spending a verification credit, and a fictional domain publishes no
        # MX record. Seeding it is the fixture describing a real agency.
        self.mx_cache = os.path.join(self.tmp, "mx-cache.json")
        self._prev_mx = os.environ.get("MX_CACHE")
        os.environ["MX_CACHE"] = self.mx_cache
        import json as _json
        io.open(self.mx_cache, "w", encoding="utf-8").write(_json.dumps(
            {d: {"mx_records": ["aspmx.l.google.com"], "status": "ok",
                 "checked_at": "2026-09-07T00:00:00+00:00"}
             for d in ("clean.test", "catchall-safe.test", "fallback.test",
                       "collision.test", "redwood.test", "skyline.test",
                       "rebrand.test", "replied.test", "unsubscribed.test",
                       "catchall-unsafe.test", "invalid.test")}))
        self.model = FakeModel()

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def walk(self):
        """Ingest, then run the pipeline to a fixed point. Nothing is sent."""
        ingest.run(BATCH, client="productive", lane="domains",
                   suppress_path=SUPPRESS)
        # The verdict these companies would have reached before anybody spent
        # a person credit on them. Person-level enrichment is gated on one, so
        # without this the walk exercises the ICP gate rather than the
        # pre-production scope it is here to prove. See the helper for why it
        # is stated rather than scored; `tests/test_icp_spend_gate.py` holds
        # the other side of the rule.
        qualify_everything()
        for _ in range(3):
            report_ = run.run(spend=True, model=self.model)
        return report_

    def rec(self, rid):
        return store.get(rid)

    def approve_all(self, by="operator"):
        with store.transaction() as recs:
            results = []
            for rec in recs:
                results.append(approve.approve_record(
                    rec, by=by, config=clients.load(rec["client"])))
        return results


class TestTheControlledScope(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_exactly_one_client_and_two_domains(self):
        recs = store.load()
        self.assertEqual({r["client"] for r in recs}, {"productive"})
        self.assertEqual(sorted(r["domain"] for r in recs),
                         ["catchall-safe.test", "clean.test"])

    def test_no_more_than_three_contacts_per_domain(self):
        for rec in store.load():
            self.assertLessEqual(len(rec["contacts"]), 3, rec["id"])

    def test_the_caps_are_what_kept_it_to_three(self):
        rec = self.rec("clearwater")
        personas = [c["persona"] for c in rec["contacts"]]
        self.assertEqual(personas.count("champion"), 2)
        self.assertEqual(personas.count("economic_buyer"), 1)
        self.assertTrue(any("over the cap" in e["why"] for e in rec["excluded"]))

    def test_every_contact_kept_is_verified_or_says_why_not(self):
        """Sendable, or held with a countable shortfall. Never neither.

        `harborview` is the cleared catch-all: ContactOut said `accept_all`
        and only Reoon vouched for it, which is one confirmation of the two
        the policy requires. It keeps its record, its drafts and its LinkedIn
        steps; what it does not get is an email.
        """
        from src import verification
        for rec in store.load():
            for contact in rec["contacts"]:
                if not contact.get("email"):
                    continue
                if lint.sendable(contact):
                    continue
                decision = verification.resolve(contact)
                self.assertLess(decision["confirmation_count"],
                                decision["required_confirmations"],
                                f"{rec['id']}:{contact['key']} is not sendable "
                                "and not short of confirmations either")

    def test_the_cleared_catch_all_is_one_confirmation_short(self):
        from src import verification
        contact = self.rec("harborview")["contacts"][0]
        decision = verification.resolve(contact)
        self.assertEqual(decision["confirmation_count"], 1)
        self.assertEqual(decision["confirmed_by"], ["reoon"])

    def test_the_catch_all_cleared_through_reoon_before_being_used(self):
        contact = self.rec("harborview")["contacts"][0]
        self.assertEqual(contact["verdict"], "accept_all")
        self.assertIs(contact["reoon"]["is_safe_to_send"], True)


class TestApprovalIsRequired(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_before_approval_nothing_is_push_eligible(self):
        prepared = push.run(day=30)
        self.assertEqual(prepared["ready"], [])
        self.assertEqual(prepared["counts"]["email"], 0)
        self.assertEqual(prepared["counts"]["linkedin"], 0)

    def test_the_operator_sees_exactly_what_is_waiting(self):
        waiting = approve.pending()["waiting"]
        self.assertTrue(waiting)
        for entry in waiting:
            self.assertIn(entry["channel"], ("email", "linkedin"))
            self.assertTrue(entry["subject"])

    def test_after_approval_the_payloads_appear(self):
        self.approve_all()
        prepared = push.run(day=30, campaign_id=7, linkedin_account_id=2)
        self.assertGreater(prepared["counts"]["email"], 0)
        self.assertGreater(prepared["counts"]["linkedin"], 0)

    def test_the_approval_is_attributed_to_a_person(self):
        self.approve_all(by="operator")
        stamp = approval.approval_of(self.rec("clearwater"),
                                     self.rec("clearwater")["contacts"][0]["key"],
                                     "day1")
        self.assertEqual(stamp["by"], "operator")

    def test_editing_after_approval_pulls_it_back_out_of_the_payload(self):
        self.approve_all()
        before = {i["push_id"] for i in push.run(day=30)["ready"]}
        key = self.rec("clearwater")["contacts"][0]["key"]
        with store.transaction() as recs:
            rec = store.get("clearwater", recs)
            rec["cadence"][key]["day1"]["body"] += "\n\nOne more line, added after sign off."
        after = {i["push_id"] for i in push.run(day=30)["ready"]}
        self.assertIn(f"clearwater:{key}:day1:email", before)
        self.assertNotIn(f"clearwater:{key}:day1:email", after)


class TestTheCadenceIsPrepared(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()
        self.approve_all()

    def test_each_contact_has_the_full_seven_step_timeline(self):
        timeline = cadence.build(self.rec("clearwater"))
        for key, steps in timeline["contacts"].items():
            self.assertEqual(sorted(steps),
                             ["day1", "day10", "day15", "day21", "day3", "day5", "day8"],
                             key)

    def test_only_two_emails_per_contact_were_written_by_the_model(self):
        for rec in store.load():
            for key, steps in (rec.get("cadence") or {}).items():
                generated = [k for k, s in steps.items() if s.get("generated")]
                self.assertTrue(set(generated) <= {"day1", "day15"}, f"{rec['id']}:{key}")

    def test_the_buyer_starts_behind_the_champion(self):
        timeline = cadence.build(self.rec("clearwater"))
        contacts = {c["key"]: c["persona"] for c in self.rec("clearwater")["contacts"]}
        champion = min(s["day"] for k, steps in timeline["contacts"].items()
                       if contacts[k] == "champion" for s in steps.values())
        buyer = min(s["day"] for k, steps in timeline["contacts"].items()
                    if contacts[k] == "economic_buyer" for s in steps.values())
        self.assertEqual(buyer, champion + 5)

    def test_every_prepared_email_passes_lint_as_a_finished_email(self):
        for item in push.run(day=30)["ready"]:
            if item["channel"] != "email":
                continue
            self.assertEqual(lint.check(item["record"], item["contact_key"],
                                        item["step"]), [])


class TestThePayloadsAreReady(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()
        self.approve_all()
        self.prepared = push.run(day=30, campaign_id=7, linkedin_account_id=2)

    def test_the_emailbison_payload_is_the_documented_shape(self):
        payload = self.prepared["payloads"]["emailbison"]
        self.assertTrue(payload["endpoint"].endswith("/campaigns/7/leads"))
        for lead in payload["body"]["leads"]:
            self.assertEqual(set(lead["custom_variables"]),
                             {"subject", "body", "title",
                              "record_id", "contact_key", "client",
                              # Which human owns the relationship and which
                              # inbox carries it. Identifiers, not
                              # credentials - `tests/test_push.py` greps the
                              # payload for anything credential-shaped.
                              "sender_id", "sender_account_id",
                              "provider_account_id"})

    def test_the_heyreach_payload_is_the_documented_shape(self):
        payload = self.prepared["payloads"]["heyreach"]
        self.assertTrue(payload["endpoint"].endswith("AddLeadsToCampaignV2"))
        for pair in payload["body"]["accountLeadPairs"]:
            self.assertEqual(pair["linkedInAccountId"], 2)
            self.assertTrue(pair["lead"]["profileUrl"])

    def test_nothing_was_sent_and_nothing_could_be(self):
        self.assertEqual([u for u in self.cassette.urls() if "leads" in u.lower()], [])
        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(day=30, live=True)

    def test_every_prepared_step_has_a_unique_identity(self):
        ids = [i["push_id"] for i in self.prepared["ready"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestAReplyStopsTheCompany(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()
        # Give the other company's contact an angle.
        #
        # The cassette returns her with none, and `default_angle` leaves a
        # multi-angle persona alone because the choice is evidence-led. Both
        # channels now hold a contact with no angle - email always did, and
        # LinkedIn joined it once the guard stopped covering only the blocked
        # channel. That is correct, and it is not what this test is about:
        # the subject here is that a reply at one company must not stop
        # another, which needs the other company to have a live step at all.
        from src import store
        recs = store.load()
        for rec in recs:
            if rec["id"] == "harborview":
                for contact in rec.get("contacts") or []:
                    if not contact.get("angle"):
                        # The key exists and is None, so setdefault is a no-op.
                        contact["angle"] = "ops"
        store.save(recs)
        self.approve_all()

    def test_an_email_reply_pauses_every_contact_on_both_channels(self):
        key = self.rec("clearwater")["contacts"][0]["key"]
        events.ingest([events.neutral(
            record_id="clearwater", contact_key=key, channel="email",
            type=events.REPLY_RECEIVED, provider="emailbison",
            provider_event_id="eb-preprod-1")])

        timeline = cadence.build(self.rec("clearwater"))
        statuses = {s["status"] for steps in timeline["contacts"].values()
                    for s in steps.values()}
        self.assertEqual(statuses, {"paused"})
        self.assertEqual({s["channel"] for steps in timeline["contacts"].values()
                          for s in steps.values()}, {"email", "linkedin"})

    def test_the_other_company_is_untouched(self):
        key = self.rec("clearwater")["contacts"][0]["key"]
        events.ingest([events.neutral(
            record_id="clearwater", contact_key=key, channel="email",
            type=events.REPLY_RECEIVED, provider="emailbison",
            provider_event_id="eb-preprod-2")])
        prepared = push.run(day=30)
        # harborview is held for a second confirmation, so its LinkedIn steps
        # are what remain: the pause must not touch them either.
        self.assertTrue(any(i["record"]["id"] == "harborview" for i in prepared["ready"]),
                        "the other company stopped when clearwater replied")
        self.assertFalse(any(i["record"]["id"] == "clearwater" for i in prepared["ready"]))

    def test_the_pause_is_reportable(self):
        key = self.rec("clearwater")["contacts"][0]["key"]
        events.ingest([events.neutral(
            record_id="clearwater", contact_key=key, channel="email",
            type=events.REPLY_RECEIVED, provider="emailbison",
            provider_event_id="eb-preprod-3")])
        stats = report.funnel()
        self.assertEqual(stats["replies"], 1)
        self.assertEqual(stats["companies_paused"], 1)
        by_channel = report.by_dimension("channel")
        self.assertEqual(by_channel["email"]["replies"], 1)


class TestTheWholeRunIsAccountedFor(PreProduction):
    def setUp(self):
        super().setUp()
        self.walk()
        self.approve_all()

    def test_the_funnel_adds_up(self):
        stats = report.funnel()
        self.assertEqual(stats["domains"], 2)
        self.assertEqual(stats["suppressed"], 0)
        self.assertGreater(stats["contacts_found"], 0)
        # Not every found contact clears: the cleared catch-all is one
        # independent confirmation short, and is held rather than sent.
        self.assertGreater(stats["verified"], 0)
        self.assertLessEqual(stats["verified"], stats["contacts_found"])
        self.assertGreater(stats["drafts_approved"], 0)
        self.assertEqual(stats["pushed"], 0)          # nothing was sent
        self.assertEqual(stats["delivered"], 0)       # and nothing came back

    def test_the_run_is_reportable_by_every_dimension(self):
        for dimension in report.DIMENSIONS:
            grouped = report.by_dimension(dimension)
            self.assertTrue(grouped, dimension)

    def test_a_second_identical_run_changes_nothing(self):
        before = {r["id"]: r["state"] for r in store.load()}
        run.run(spend=True, model=self.model)
        self.assertEqual({r["id"]: r["state"] for r in store.load()}, before)

    def test_no_credential_was_needed_and_no_call_left_the_machine(self):
        for call in self.cassette.calls:
            self.assertNotIn("leads", call["url"].lower())
            self.assertNotIn("AddLeads", call["url"])
        self.assertTrue(self.cassette.calls)          # providers were exercised

    def test_the_queue_is_the_only_record_state_written(self):
        """RECORD state, which is the invariant. The spend ledger is not that.

        This asserted the queue was the only file at all. `spend-ledger.jsonl`
        now sits beside it because a client's committed spend cannot live on a
        record: the question it answers is "what has this client spent today
        across every run", and no per-record field can hold that.

        It is registered in `store.STATE_OVERRIDES`, so an isolated run moves
        it, and it holds no record state - only provider, call, cost and day.
        The invariant being protected here is that nothing needed to RESUME a
        record lives outside the queue, and that still holds.
        """
        work = os.path.dirname(self.queue)
        self.assertEqual(sorted(os.listdir(work)),
                         ["queue.jsonl", "spend-ledger.jsonl"])
        from src import spendledger
        for row in spendledger.load():
            self.assertEqual(set(row) - {"at", "day", "client", "provider",
                                         "call", "expected_cost", "run_id"},
                             set(), "the spend ledger grew a record field")


if __name__ == "__main__":
    unittest.main()
