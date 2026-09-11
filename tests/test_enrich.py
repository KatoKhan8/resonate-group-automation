"""The enrichment waterfall. BUILD-SPEC phase 4, sections 5, 6 and 9.

Acceptance test, section 10: a catch-all domain ends `held` with drafts intact
and nothing in the push file.

Every test runs offline against cassettes. No credit is spent, ever.
"""
import os
import unittest

from src import enrich, lint, render, store
from tests.base import ProviderTest, qualify_everything


class EnrichTest(ProviderTest):
    """Provider harness plus a throwaway queue and out directory."""

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile
        from tests.base import FIXTURES
        self.tmp = tempfile.mkdtemp(prefix="rga-enrich-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase4.jsonl"), self.queue)
        self._queue_env = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out
        # These fixtures are the *waterfall* under test - which call runs
        # first, what a fallback costs, how a collision is excluded. Person-
        # level enrichment is gated on an ICP verdict, so without one they
        # would be asserting the gate instead. `tests/test_icp_spend_gate.py`
        # holds the other side of that rule.
        qualify_everything()
        self._shutil = shutil

    def tearDown(self):
        q, o = self._queue_env
        for name, value in (("QUEUE", q), ("OUT", o)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self._shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def rec(self, rid):
        return store.get(rid)

    def out_file(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as f:
            return f.read()


class TestTheAcceptanceTest(EnrichTest):
    """A catch-all domain ends held, with drafts intact, and nothing shipped."""

    def setUp(self):
        super().setUp()
        enrich.run(live=True)
        render.build()

    def test_the_catch_all_record_is_held(self):
        rec = self.rec("lumen")
        self.assertEqual(rec["state"], "held")
        self.assertIsNone(rec["drop_reason"])

    def test_its_address_was_checked_by_both_verifiers(self):
        contact = self.rec("lumen")["contacts"][0]
        self.assertEqual(contact["verdict"], "accept_all")
        self.assertIs(contact["reoon"]["is_safe_to_send"], False)
        self.assertIs(contact["sendable"], False)

    def test_its_draft_is_intact(self):
        step = self.rec("lumen")["cadence"]["luka-peric"]["day1"]
        self.assertEqual(step["subject"], "utilisation across four delivery teams")
        self.assertIn("capacity planning", step["body"])

    def test_nothing_of_it_reaches_the_push_file(self):
        csv_text = self.out_file("emailbison.csv")
        self.assertNotIn("luka.peric@lumen.test", csv_text)
        self.assertNotIn("lumen", csv_text)

    def test_it_is_visible_amber_for_review(self):
        html = self.out_file("review.html")
        self.assertIn('<article class="held">', html)
        self.assertIn("utilisation across four delivery teams", html)

    def test_the_verified_record_still_ships(self):
        """Section 10: good records carry on when another is held."""
        self.assertEqual(self.rec("meridian")["state"], "verified")
        self.assertIn("tomislav.baric@meridian.test", self.out_file("emailbison.csv"))


class TestTheWaterfallOrder(EnrichTest):
    def test_a_record_with_an_address_does_not_buy_decision_makers(self):
        enrich.run(live=True, ids=["meridian"])
        urls = " ".join(self.cassette.urls())
        self.assertNotIn("decision-makers", urls)
        self.assertIn("contactout.com/v1/email/verify", urls)

    def test_reoon_escalates_wherever_a_second_confirmation_is_still_missing(self):
        """It used to run only on a catch-all. It now also runs as the
        escalation that supplies confirmation number two - which, while
        Deliverable's response contract is unread and it refuses, is every
        address ContactOut cleared. Once that contract is read, Deliverable
        closes the pair and this drops back to catch-alls only.
        """
        enrich.run(live=True)
        reoon_calls = [u for u in self.cassette.urls() if "reoon" in u]
        self.assertTrue(any("luka.peric" in u for u in reoon_calls),
                        "the catch-all must still escalate")
        self.assertTrue(reoon_calls)

    def test_ai_ark_runs_only_after_contactout_finds_nobody(self):
        enrich.run(live=True, ids=["meridian"])
        self.assertNotIn("ai-ark", " ".join(self.cassette.urls()))

    def test_the_free_count_comes_before_any_paid_call(self):
        enrich.run(live=True, ids=["parked"])
        urls = self.cassette.urls()
        self.assertIn("people/count", urls[0])

    def test_a_second_pass_does_not_re_buy_what_it_has(self):
        enrich.run(live=True)
        before = len(self.cassette.calls)
        enrich.run(live=True)
        new = [c["url"] for c in self.cassette.calls[before:]]
        self.assertEqual([u for u in new if "decision-makers" in u or "reoon" in u], [])


class TestSection9Traps(EnrichTest):
    def test_trap_1_company_name_collisions_are_excluded_not_merged(self):
        enrich.run(live=True, ids=["samename"])
        rec = self.rec("samename")
        kept = [c["name"] for c in rec["contacts"]]
        excluded = [e["name"] for e in rec["excluded"]]
        self.assertEqual(kept, ["Mirna Zorić"])
        self.assertIn("Luc Marchand", excluded)
        self.assertIn("Pablo Estrada", excluded)
        for e in rec["excluded"]:
            self.assertIn("collision", e["why"])

    def test_trap_1_a_person_with_no_evidence_of_identity_is_not_merged(self):
        rec = {"domain": "meridian.test", "company": "Meridian", "company_facts": {}}
        self.assertFalse(enrich.same_company({"name": "Nobody"}, rec))

    def test_trap_1_an_address_outranks_a_matching_company_name(self):
        """The branch that decides. A payload can claim any company string it
        likes; if it also carries an address, the address answers."""
        rec = {"domain": "meridian.test", "company": "Meridian",
               "company_facts": {}}
        self.assertFalse(enrich.same_company(
            {"company": "Meridian", "email": "a@elsewhere.test"}, rec))

    def test_trap_1_a_name_match_with_no_address_is_accepted_on_purpose(self):
        """Pinning what the second branch actually does, because the docstring
        used to claim more than it delivered.

        A person with no address rides on a lowercase company-name match. That
        is licensed by the CALLER - both search by domain, so the payload is
        already scoped - and not by the name. If this ever returns False, the
        LinkedIn lane loses every profile-only person a domain-scoped search
        returns; if a caller that does not scope by domain starts using it,
        this is the line that lets two firms with one name merge.
        """
        rec = {"domain": "meridian.test", "company": "Meridian",
               "company_facts": {}}
        self.assertTrue(enrich.same_company({"company": "meridian"}, rec))
        self.assertFalse(enrich.same_company({"company": "Meridian Labs"}, rec))

    def test_trap_2_accept_all_is_never_sendable_on_its_own(self):
        enrich.run(live=True, ids=["lumen"])
        contact = self.rec("lumen")["contacts"][0]
        self.assertEqual(contact["verdict"], "accept_all")
        self.assertFalse(contact["sendable"])

    def test_trap_3_mail_domain_is_recorded_without_overwriting_the_domain(self):
        enrich.run(live=True, ids=["parked"])
        rec = self.rec("parked")
        self.assertEqual(rec["domain"], "parked.test")
        self.assertEqual(rec["company_facts"]["email_domain"], "halcyon.test")
        self.assertTrue(any("mail domain is halcyon.test" in e["note"] for e in rec["log"]))

    def test_trap_3_an_address_on_the_mail_domain_counts_as_this_company(self):
        rec = {"domain": "parked.test", "company": "Kestrel",
               "company_facts": {"email_domain": "halcyon.test"}}
        self.assertTrue(enrich.same_company({"email": "a@halcyon.test"}, rec))
        self.assertFalse(enrich.same_company({"email": "a@elsewhere.test"}, rec))

    def test_the_free_count_stops_a_paid_search_on_a_parked_domain(self):
        """Section 5.1: the count exists to prevent exactly this spend."""
        enrich.run(live=True, ids=["parked"])
        urls = " ".join(self.cassette.urls())
        self.assertIn("people/count", urls)
        self.assertNotIn("decision-makers", urls)
        self.assertIn("domain/enrich", urls)
        self.assertTrue(any("skipping decision-makers" in e["note"]
                            for e in self.rec("parked")["log"]))

    def test_a_dry_run_prices_a_parked_domain_without_the_search_credit(self):
        enrich.run(live=True, ids=["parked"])          # learns the count
        plan = enrich.plan(self.rec("parked"))
        self.assertNotIn("decision-makers", [o["call"] for o in plan])

    def test_a_staffed_domain_still_buys_decision_makers(self):
        enrich.run(live=True, ids=["samename"])
        self.assertIn("decision-makers", " ".join(self.cassette.urls()))

    def test_trap_4_a_rebrand_is_found_when_the_domain_yields_nobody(self):
        enrich.run(live=True, ids=["parked"])
        rec = self.rec("parked")
        self.assertEqual(rec["company_facts"]["name"], "Halcyon")
        urls = " ".join(self.cassette.urls())
        self.assertIn("domain/enrich", urls)

    def test_trap_7_enrichment_never_sends_current_work_location(self):
        enrich.run(live=True)
        self.assertNotIn("current_work_location", " ".join(self.cassette.urls()))

    def test_trap_8_no_raw_payload_is_stored_on_the_record(self):
        enrich.run(live=True)
        blob = str(store.load())
        for noise in ("profile_picture", "smtp_transcript", "debug", "contact_info",
                      "skills", "followers", "raw_smtp"):
            self.assertNotIn(noise, blob, noise)

    def test_trap_8_contacts_keep_only_schema_fields(self):
        enrich.run(live=True, ids=["samename"])
        for c in self.rec("samename")["contacts"]:
            self.assertEqual(set(c), {"name", "title", "linkedin", "email",
                                      # The contact id, assigned where a
                                      # contact enters the record. SCHEMA.md
                                      # documents it as `contacts[].key`. It
                                      # used to be written two stages later by
                                      # `personas.select`, which is how events
                                      # about a contact came to be recorded
                                      # before it had one - and how two
                                      # keyless contacts at one domain
                                      # collapsed into a single stored event.
                                      "key",
                                      "email_source", "persona", "angle", "verdict",
                                      "reoon", "sendable", "primary",
                                      "verification",
                                      # The MX decision, trimmed by `mx.decide`
                                      # exactly as `mx.apply_to_record` stores
                                      # it. Screening now runs during
                                      # enrichment - before any verifier credit
                                      # is spent - so it lands here rather than
                                      # later.
                                      "mx"})


class TestOutcomes(EnrichTest):
    def test_a_domain_with_nobody_is_dropped_with_a_reason(self):
        enrich.run(live=True, ids=["parked"])
        rec = self.rec("parked")
        self.assertEqual(rec["state"], "dropped")
        self.assertTrue(rec["drop_reason"])

    def test_a_dropped_record_keeps_its_line_and_its_history(self):
        before = len(store.load())
        enrich.run(live=True)
        self.assertEqual(len(store.load()), before)
        self.assertTrue(self.rec("parked")["diagnosis"]["died_because"])

    def test_sendable_is_computed_not_trusted(self):
        recs = store.load()
        for r in recs:
            for c in r["contacts"]:
                c["sendable"] = True          # a lie planted on the record
        store.save(recs)
        enrich.run(live=True, ids=["lumen"])
        self.assertFalse(self.rec("lumen")["contacts"][0]["sendable"])

    def test_a_primary_is_only_ever_a_sendable_contact(self):
        enrich.run(live=True)
        for rec in store.load():
            for c in rec["contacts"]:
                if c.get("primary") and c.get("email"):
                    self.assertTrue(c["sendable"] or rec["state"] != "verified")

    def test_every_provider_call_is_logged_on_the_record(self):
        enrich.run(live=True, ids=["meridian"])
        steps = [e["step"] for e in self.rec("meridian")["log"]]
        self.assertIn("enrich", steps)
        self.assertIn("verify", steps)


class TestTheCap(EnrichTest):
    def test_a_dry_run_calls_nothing_and_writes_nothing(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        result = enrich.run()
        self.assertEqual(self.cassette.calls, [])
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertFalse(result["live"])

    def test_a_dry_run_reports_what_it_would_do_and_what_it_would_cost(self):
        result = enrich.run()
        self.assertEqual(len(result["records"]), 4)
        meridian = next(r for r in result["records"] if r["id"] == "meridian")
        self.assertEqual([o["call"] for o in meridian["ops"]],
                         ["people-count", "contactout-verify", "deliverable-verify",
                          "reoon-verify"])
        # The secondary is expected now, not conditional: two independent
        # confirmations are required, so it runs on every address the primary
        # clears. Only the escalation stays a maybe.
        conditional = [o["call"] for o in meridian["ops"] if o.get("conditional")]
        self.assertEqual(conditional, ["reoon-verify"])
        self.assertTrue(all(o["why"] for r in result["records"] for o in r["ops"]))
        self.assertGreater(result["spent"], 0)

    def test_the_free_call_is_costed_at_zero(self):
        result = enrich.run()
        for r in result["records"]:
            for o in r["ops"]:
                if o["call"] == "people-count":
                    self.assertEqual(o["cost"], 0)

    def test_the_cap_refuses_the_call_rather_than_going_over(self):
        result = enrich.run(live=True, cap=1)
        self.assertLessEqual(result["spent"], 1)
        self.assertTrue(result["refused"])
        self.assertNotIn("decision-makers", " ".join(self.cassette.urls()))

    def test_a_cap_of_zero_spends_nothing_but_still_runs_the_free_call(self):
        result = enrich.run(live=True, cap=0)
        self.assertEqual(result["spent"], 0)
        for url in self.cassette.urls():
            self.assertIn("people/count", url)

    def test_limit_bounds_the_fan_out(self):
        result = enrich.run(limit=2)
        self.assertEqual(len(result["records"]), 2)

    def test_every_planned_op_states_why_it_is_needed(self):
        for rec in store.load():
            for o in enrich.plan(rec):
                self.assertTrue(o["why"], o["call"])

    def test_a_terminal_record_is_never_re_enriched(self):
        store.drop("meridian", "test drop")
        self.assertEqual(enrich.plan(self.rec("meridian")), [])


class TestPlanIsPure(EnrichTest):
    def test_planning_touches_neither_the_queue_nor_a_provider(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        for rec in store.load():
            enrich.plan(rec)
        self.assertEqual(self.cassette.calls, [])
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)


class TheFreeCountIsWhatGuardsThePaidOne(EnrichTest):
    """It was gated on the dict, and it writes one key of that dict.

    `plan` and `enrich_record` both asked `not rec.get("company_facts")`,
    and the free `people-count` writes only `headcount_signal` - so any
    other writer of any other key suppressed it. `demo`, `companies` and
    `personas.apply_icp` all do exactly that. With the count skipped,
    `staffed` is None, `unstaffed` is False, and a record with no contacts
    goes straight to the paid `decision-makers` on a domain that might be
    parked, which is the one thing the free call exists to prevent.
    """

    def record(self, facts):
        rec = store.new_record("acme", "domains", "demo", "Acme", "acme.test")
        rec["company_facts"] = dict(facts)
        # The subject here is which call the free count guards, so the company
        # has to be one the paid call is allowed to run on at all. Without a
        # verdict the ICP gate answers first and `decision-makers` never
        # appears in the plan to be ordered against.
        rec["qualification"] = {"inputs_fingerprint": "pinned-for-this-test",
                                "at": store.now(),
                                "verdict": {"icp_status": "qualified"}}
        return rec

    def calls(self, rec):
        return [o["call"] for o in enrich.plan(rec)]

    def test_a_fact_written_by_somebody_else_does_not_skip_the_count(self):
        """The defect. `icp_flags` is a real writer - `personas.apply_icp`."""
        self.assertIn("people-count",
                      self.calls(self.record({"icp_flags": ["dont_drop"]})))

    def test_and_the_paid_call_is_not_reached_before_it(self):
        ops = self.calls(self.record({"icp_flags": ["dont_drop"]}))
        self.assertLess(ops.index("people-count"),
                        ops.index("decision-makers"))

    def test_the_count_is_skipped_once_it_has_actually_answered(self):
        """Otherwise it is bought again on every run."""
        self.assertNotIn("people-count",
                         self.calls(self.record({"headcount_signal": 12})))

    def test_a_zero_answer_still_counts_as_answered(self):
        """`0` is an answer - the domain is real and nobody works there -
        and re-buying it would be paying to be told the same thing."""
        self.assertNotIn("people-count",
                         self.calls(self.record({"headcount_signal": 0})))

    def test_an_empty_record_still_buys_it(self):
        self.assertIn("people-count", self.calls(self.record({})))


if __name__ == "__main__":
    unittest.main()


class TestMxScreensBeforeAnyVerifierCredit(EnrichTest):
    """Section 9: a free DNS lookup gates two paid verification calls.

    A domain behind a gateway this client blocks has its email channel closed
    whatever a verifier would say, so buying that answer buys nothing. Under
    `required_confirmations: 2` the saving doubled: a blocked contact now
    skips a primary *and* a secondary rather than one call and a maybe.

    The screening is narrow on purpose. Only a positively identified gateway
    cancels verification - a DNS failure or a domain with no MX also closes
    the channel, but neither is evidence about the address, and a resolver
    that was down for a minute must not quietly cancel the verification of an
    address that is perfectly good.
    """

    def enrich_with_mx(self, hosts):
        from src import mx
        cache = {}

        def resolver(domain):
            if domain in hosts:
                return list(hosts[domain])
            raise mx.MXError(f"no fixture for {domain}")

        real = mx.resolve
        mx.resolve = resolver
        try:
            return enrich.run(live=True)
        finally:
            mx.resolve = real

    def verifier_calls(self):
        return [u for u in self.cassette.urls()
                if "contactout.com/v1/email/verify" in u or "reoon" in u
                or "deliverable" in u]

    def test_a_blocked_domain_costs_no_verifier_call(self):
        before = len(self.verifier_calls())
        self.enrich_with_mx({"meridian.test": ["mx1.pphosted.com"],
                             "lumen.test": ["aspmx.l.google.com"]})
        for url in self.verifier_calls()[before:]:
            self.assertNotIn("meridian.test", url)
            self.assertNotIn("tomislav", url)

    def test_the_unblocked_domain_is_still_verified(self):
        """The saving must not become a silent skip of everything."""
        self.enrich_with_mx({"meridian.test": ["mx1.pphosted.com"],
                             "lumen.test": ["aspmx.l.google.com"]})
        self.assertTrue(any("luka.peric" in u for u in self.verifier_calls()))

    def test_the_skip_is_recorded_rather_than_silent(self):
        self.enrich_with_mx({"meridian.test": ["mx1.pphosted.com"],
                             "lumen.test": ["aspmx.l.google.com"]})
        rec = self.rec("meridian")
        skipped = [e for e in rec.get("events") or []
                   if e.get("type") == "provider_call_skipped"
                   and e.get("provider") == "verification"]
        self.assertTrue(skipped, "no event explains the missing verification")
        self.assertIn("MX", skipped[0].get("reason", ""))

    def test_the_contact_keeps_its_record_and_its_profile(self):
        """Blocking suppresses the channel, never the person."""
        self.enrich_with_mx({"meridian.test": ["mx1.pphosted.com"],
                             "lumen.test": ["aspmx.l.google.com"]})
        rec = self.rec("meridian")
        self.assertTrue(rec["contacts"])
        self.assertIsNone(rec.get("drop_reason"))

    def test_a_dns_failure_does_not_cancel_verification(self):
        """A resolver that was down is not evidence about an address."""
        before = len(self.verifier_calls())
        self.enrich_with_mx({})            # every lookup raises
        after = self.verifier_calls()[before:]
        self.assertTrue(any("tomislav" in u or "luka" in u for u in after),
                        "a DNS failure silently cancelled verification")
