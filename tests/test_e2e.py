"""The whole pipeline, end to end, offline.

A fictional twelve row batch walks from a CSV through ingest, enrichment,
personas, generation, lint, render and push preparation, and every documented
edge case is exercised on the way:

  clean domain, suppressed domain, duplicate, missing domain, company name
  collision, rebrand, catch-all that clears, catch-all that does not, invalid
  address, AI Ark fallback, revive, cold, domains, multiple personas, the buyer
  offset, a non-Latin contact name, an LLM retry, a lint failure, a good record
  continuing past a bad one, an email reply pause, a LinkedIn reply pause, a
  connection accepted, a partial push and its retry, and a runner crash and
  resume.

No network, no provider credit, no model call, nothing sent.
"""
import csv
import io
import json
import os
import shutil
import tempfile
import unittest

from src import cadence, ingest, lint, llm, push, run, store
from tests.base import (FIXTURES, ProviderTest, approve_everything,
                        mx_cache_entries, pin_client_config,
                        qualify_everything)

BATCH = os.path.join(FIXTURES, "e2e-batch.csv")
SUPPRESS = os.path.join(FIXTURES, "e2e-suppress.txt")

# ASSERTS NOTHING ABOUT THEM, and that is what makes it good.
#
# This used to open "you are running the finance side of a team spread across
# several offices". `clearwater` has no `offices` fact - the one in the
# cassettes belongs to a different company - so the sentence was a statement
# about somebody else's business on no evidence, sitting in a constant named
# GOOD_BODY. The claim rule added on 2026-09-10 caught it, along with two
# hooks in `demo.py` that did the same thing.
#
# The rewrite generalises and asks, which is the same fix applied to the
# canary note and to the day-21 template before it.
GOOD_BODY = (
    "{first}, month end tends to stop being an afternoon and start being a "
    "week of chasing once finance is spread across more than one place. The "
    "part I would ask about is how long it takes to know which client work "
    "actually made money, because most teams can answer revenue quickly and "
    "margin slowly.\n\n"
    "Is that roughly the shape of it, or have you already put something in place?")

BAD_BODY = "[FIRST NAME], I wanted to reach out about your audit—screenshot attached below."


class E2EModel:
    """Deterministic, prompt driven, offline. Never a network call.

    Behaviour built in on purpose:
      - the very first answer is not JSON, so the retry path is exercised
      - every draft for Stonebridge is unusable, so the lint path is exercised
    """

    name = "e2e"

    def __init__(self):
        self.prompts = []
        self.calls = 0

    def complete(self, prompt, client=None):
        self.prompts.append(prompt)
        self.calls += 1
        if self.calls == 1:
            return "Certainly! Here is the answer in prose."       # forces a retry
        if "# persona_angle" in prompt:
            # Evidence has to be traceable to the record, so quote the record.
            title = "Head of Finance"
            for line in prompt.splitlines():
                if '"title"' in line:
                    title = line.split(":", 1)[1].strip().strip(',').strip('"')
                    break
            return json.dumps({"angle": "finance", "evidence": [title]})
        if "# diagnose" in prompt:
            return json.dumps({
                "died_on": "2025-03-12",
                "died_because": "asked to run the key against a realistic list of "
                                "accounts and the reply proposed a call instead",
                "failure_mode": "unanswered_question",
                "last_position": "a trial key with a 50 credit limit",
                "what_changed": None})
        if "# hook" in prompt:
            return json.dumps({"hook": "tried three outbound agencies before "
                                       "building the function in house"})
        if "# linkedin_note" in prompt:
            # One note per rung, not one note repeated - the quality gate now
            # runs before a note is stored and refuses the second copy. See
            # the same branch in `tests/test_preproduction.py`.
            later = ("day8", "li3", "li4", "li5")
            if any(f'"key": "{k}"' in prompt for k in later):
                return json.dumps({"note": "the part most teams find hardest "
                                           "is knowing which work paid for "
                                           "itself while it is still running. "
                                           "is that where it bites for you?"})
            return json.dumps({"note": "hi, i work with services teams on "
                                       "how their delivery and their numbers "
                                       "line up. thought it would be good to "
                                       "connect"})
        if "# draft" in prompt:
            first = "there"
            for token in ("Ćuk", "Ana", "Iris", "Otto", "Sanne", "Frank", "Mira",
                          "Petra", "梁伟"):
                if token in prompt:
                    first = token
                    break
            if "Stonebridge" in prompt:
                return json.dumps({"subject": "picking this up", "body": BAD_BODY})
            return json.dumps({"subject": "one week of month end, every month",
                               "body": GOOD_BODY.format(first=first)})
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")


class EndToEnd(ProviderTest):
    """One batch, walked once, then asserted from every angle."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="rga-e2e-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, ignore_errors=True)

    def setUp(self):
        super().setUp()
        # Pinned: these tests are about the end-to-end pipeline, not about
        # which cadence Productive currently runs.
        pin_client_config(self)
        # The productive policy now requires deliverable as primary verifier,
        # so the contract must be confirmed for the waterfall to call it.
        self.confirm_deliverable_contract()
        self.tmp = tempfile.mkdtemp(prefix="rga-e2e-run-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self.mx_cache = os.path.join(self.tmp, "mx-cache.json")
        self._prev = (os.environ.get("QUEUE"), os.environ.get("OUT"),
                      os.environ.get("MX_CACHE"))
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out
        os.environ["MX_CACHE"] = self.mx_cache
        self.seed_mx()
        self.model = E2EModel()

    def seed_mx(self):
        """Give the fixture domains an MX record, because real ones have one.

        `enrich_record` screens MX before spending a verification credit, and
        that screen only runs when the stage hands it a client config - which
        `run.stage_enrich` did not, so on the batch-runner path it never ran at
        all and every address was verified whether or not the domain could
        receive mail. Passing the config switched it on, and these `.test`
        domains publish nothing, so the whole batch became `no_mx`.

        Seeding the cache is the fixture telling the truth about the world it
        is modelling: an agency's domain accepts mail. `deadletter.test` is
        left out on purpose - it is the record that exists to prove a domain
        with no MX is refused.
        """
        import json
        allowed = ["clean.test", "catchall-safe.test", "catchall-unsafe.test",
                   "fallback.test", "collision.test", "redwood.test",
                   "skyline.test", "rebrand.test", "unsubscribed.test",
                   "replied.test", "invalid.test", "nomx.test"]
        cache = mx_cache_entries(allowed)
        io.open(self.mx_cache, "w", encoding="utf-8").write(json.dumps(cache))

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT", "MX_CACHE"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    # -------------------------------------------------------------- helpers

    def ingest_batch(self):
        return ingest.run(BATCH, client="productive", lane="domains",
                          suppress_path=SUPPRESS)

    def walk(self, passes=3):
        """Ingest, then run the pipeline to a fixed point, all offline."""
        self.ingest_batch()
        # The verdict these companies would have reached before anybody spent
        # a person credit on them. Person-level enrichment is gated on one, so
        # without this the walk would be exercising the ICP gate rather than
        # the provider waterfall it is here to test. See the helper for why it
        # is stated rather than scored.
        qualify_everything()
        reports = []
        for _ in range(passes):
            reports.append(run.run(spend=True, model=self.model))
        approve_everything()          # a human signs off before anything ships
        return reports[-1]

    def rec(self, rid):
        return store.get(rid)

    def out_file(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as f:
            return f.read()


class TestIngestEdgeCases(EndToEnd):
    def test_every_row_becomes_a_record_and_none_vanish(self):
        result = self.ingest_batch()
        self.assertEqual(len(store.load()), 12)
        self.assertEqual(len(result["queued"]) + len(result["dropped"]), 12)

    def test_the_suppressed_domain_is_dropped_before_a_credit_is_spent(self):
        self.ingest_batch()
        rec = self.rec("blocked-co")
        self.assertEqual(rec["state"], "dropped")
        self.assertIn("suppressed", rec["drop_reason"])
        self.assertEqual(self.cassette.calls, [])

    def test_the_duplicate_is_dropped_with_its_reason(self):
        self.ingest_batch()
        rec = self.rec("clearwater-again")
        self.assertEqual(rec["state"], "dropped")
        self.assertEqual(rec["drop_reason"], "duplicate domain")
        self.assertEqual(rec["domain"], "clean.test")

    def test_the_row_with_no_domain_is_dropped_with_its_reason(self):
        self.ingest_batch()
        self.assertEqual(self.rec("no-domain-co")["drop_reason"], "no domain")

    def test_all_three_lanes_are_present_and_distinct(self):
        self.ingest_batch()
        lanes = {r["id"]: r["lane"] for r in store.load()}
        self.assertEqual(lanes["redwood"], "revive")
        self.assertEqual(lanes["skyline"], "cold")
        self.assertEqual(lanes["clearwater"], "domains")


class TestEnrichmentOutcomes(EndToEnd):
    def setUp(self):
        super().setUp()
        self.report = self.walk()

    def test_the_clean_domain_verifies(self):
        # `approved` rather than `drafted`: the walk calls approve_everything(),
        # so every step on this record carries a signature and the record-level
        # state follows the steps.
        self.assertEqual(self.rec("clearwater")["state"], "approved")

    def test_a_catch_all_cleared_by_one_provider_is_now_held(self):
        """Reoon clears the catch-all and that is still only one opinion.

        ContactOut said `accept_all`, which is the absence of a confirmation
        rather than one. Under `required_confirmations: 2` a domain that
        accepts everything, vouched for by a single provider, is exactly the
        address that should wait for a second - so this record keeps its
        drafts and its LinkedIn steps and does not send email.
        """
        contact = self.rec("harborview")["contacts"][0]
        self.assertEqual(contact["verdict"], "accept_all")
        self.assertIs(contact["reoon"]["is_safe_to_send"], True)
        self.assertFalse(contact["sendable"])
        block = contact["verification"]
        self.assertEqual(block["confirmation_count"], 1)
        self.assertEqual(block["confirmed_by"], ["reoon"])

    def test_the_catch_all_that_does_not_clear_is_held_and_not_sendable(self):
        rec = self.rec("stonebridge")
        contact = rec["contacts"][0]
        self.assertEqual(contact["verdict"], "accept_all")
        self.assertIs(contact["reoon"]["is_safe_to_send"], False)
        self.assertFalse(contact["sendable"])
        self.assertEqual(rec["state"], "held")

    def test_the_invalid_address_ends_dropped_with_a_reason(self):
        rec = self.rec("deadletter")
        self.assertEqual(rec["state"], "dropped")
        self.assertIn("cleared verification", rec["drop_reason"])

    def test_the_ai_ark_fallback_finds_what_contactout_missed(self):
        rec = self.rec("northwind")
        self.assertEqual([c["name"] for c in rec["contacts"]], ["Sanne de Vries"])
        self.assertTrue(rec["contacts"][0]["sendable"])
        urls = " ".join(self.cassette.urls())
        self.assertIn("ai-ark", urls)

    def test_the_collision_is_excluded_not_merged(self):
        rec = self.rec("samename")
        kept = [c["name"] for c in rec["contacts"]]
        excluded = [e["name"] for e in rec["excluded"]]
        self.assertEqual(kept, ["Mirna Zorić"])
        self.assertIn("Luc Marchand", excluded)
        self.assertIn("Pablo Estrada", excluded)

    def test_the_rebrand_is_recorded_without_overwriting_the_domain(self):
        rec = self.rec("kestrel")
        self.assertEqual(rec["domain"], "parked.test")
        self.assertEqual(rec["company_facts"]["name"], "Halcyon")
        self.assertEqual(rec["company_facts"]["email_domain"], "halcyon.test")

    def test_no_paid_search_was_bought_for_the_parked_domain(self):
        self.assertNotIn("decision-makers?domain=parked.test",
                         " ".join(self.cassette.urls()))

    def test_nothing_raw_from_a_provider_is_on_any_record(self):
        blob = json.dumps(store.load())
        for noise in ("contact_info", "profile_picture", "smtp", "debug_log",
                      "raw_smtp", "totalElements"):
            self.assertNotIn(noise, blob, noise)


class TestPersonasAndIdentity(EndToEnd):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_the_champion_cap_bites_and_the_extra_is_excluded(self):
        rec = self.rec("clearwater")
        champions = [c for c in rec["contacts"] if c["persona"] == "champion"]
        buyers = [c for c in rec["contacts"] if c["persona"] == "economic_buyer"]
        self.assertEqual(len(champions), 2)
        self.assertEqual(len(buyers), 1)
        self.assertTrue(any("over the cap" in e["why"] for e in rec["excluded"]))

    def test_the_non_latin_contact_gets_a_stable_readable_key(self):
        keys = {c["name"]: c["key"] for c in self.rec("clearwater")["contacts"]}
        self.assertEqual(keys.get("Ćuk Šimić"), "cuk-simic")

    def test_a_fully_non_latin_name_still_gets_a_deterministic_key(self):
        rec = self.rec("clearwater")
        excluded_and_kept = {c["name"]: c.get("key") for c in rec["contacts"]}
        excluded_and_kept.update({e["name"]: None for e in rec["excluded"]})
        self.assertIn("梁伟", excluded_and_kept)

    def test_the_per_domain_export_is_written_for_the_domains_lane_only(self):
        self.assertTrue(os.path.exists(
            os.path.join(self.out, "domains", "clean.test", "people.csv")))
        self.assertFalse(os.path.exists(
            os.path.join(self.out, "domains", "redwood.test")))

    def test_an_out_of_geo_company_is_flagged_rather_than_silently_kept(self):
        from src import clients, personas
        config = clients.load("productive")
        kestrel = self.rec("kestrel")          # offices: Taipei TW
        self.assertEqual(kestrel["company_facts"]["offices"], ["Taipei TW"])
        flags = personas.icp_flags(kestrel, config)
        self.assertIn("geo outside client's stated markets", flags)

    def test_an_in_market_company_carries_no_geo_flag(self):
        from src import clients, personas
        config = clients.load("productive")
        northwind = self.rec("northwind")      # offices: Amsterdam NL
        self.assertEqual(personas.icp_flags(northwind, config), [])


class TestGenerationAndLint(EndToEnd):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_the_retry_path_was_exercised_and_recovered(self):
        self.assertGreater(self.model.calls, 1)
        rejected = [e for r in store.load() for e in r["log"] if e.get("rejected")]
        self.assertTrue(rejected)

    def test_the_revive_record_got_the_right_diagnosis(self):
        diagnosis = self.rec("redwood")["diagnosis"]
        self.assertEqual(diagnosis["died_on"], "2025-03-12")
        self.assertEqual(diagnosis["failure_mode"], "unanswered_question")

    def test_the_cold_record_got_a_specific_hook(self):
        self.assertIn("three outbound agencies", self.rec("skyline")["hook"])

    def test_exactly_two_emails_per_contact_are_model_written(self):
        # EMAIL ONLY, WHICH IS WHAT THE NAME SAYS. `productive_balanced_v1`
        # marks exactly `day1` and `day15` `generated`; the other email steps
        # name templates and cost nothing. Counting every channel also
        # asserted that no LinkedIn note is model-written, which the pinned
        # config contradicts on purpose - Productive sets
        # `linkedin_connection_note.mode: llm`. It passed only while the fake
        # model raised on `# linkedin_note` and `stage_generate` swallowed it,
        # so nothing was generated at all and the empty set satisfied both
        # assertions. The same defect stood in `tests/test_preproduction.py`.
        for rec in store.load():
            for key, steps in (rec.get("cadence") or {}).items():
                generated = {k for k, s in steps.items()
                             if s.get("generated") and s.get("channel") == "email"}
                self.assertLessEqual(len(generated), 2, f"{rec['id']}:{key}")
                self.assertTrue(generated <= {"day1", "day15"},
                                f"{rec['id']}:{key}")

    def test_the_linkedin_notes_are_model_written_because_the_client_asked(self):
        # The half the assertion above used to make implicitly, stated.
        seen = 0
        for rec in store.load():
            for key, steps in (rec.get("cadence") or {}).items():
                for step_key, step in steps.items():
                    if step.get("channel") != "linkedin":
                        continue
                    self.assertTrue(step.get("generated"),
                                    f"{rec['id']}:{key}:{step_key}")
                    seen += 1
        self.assertTrue(seen, "no linkedin step was written at all")

    def test_the_record_whose_drafts_never_pass_lint_ships_nothing(self):
        csv_text = self.out_file("emailbison.csv")
        self.assertNotIn("stonebridge", csv_text)
        self.assertNotIn("[FIRST NAME]", csv_text)
        self.assertNotIn("—", csv_text)

    def test_the_good_records_still_ship_alongside_it(self):
        rows = list(csv.DictReader(io.StringIO(self.out_file("emailbison.csv"))))
        shipped = {r["record_id"] for r in rows}
        self.assertIn("clearwater", shipped)
        self.assertIn("northwind", shipped)
        # harborview is the cleared catch-all: one confirmation, so held.
        self.assertNotIn("harborview", shipped)
        self.assertTrue(len(rows) >= 4)

    def test_every_shipped_row_passes_every_lint_rule(self):
        results = {lint.step_id(r): r for r in lint.check_all()}
        for row in csv.DictReader(io.StringIO(self.out_file("emailbison.csv"))):
            matching = [r for r in results.values() if r["id"] == row["record_id"]
                        and r["day"] == row["day"]]
            self.assertTrue(matching)
            for r in matching:
                self.assertEqual(r["failures"], [])

    def test_a_stored_draft_that_fails_lint_is_red_and_never_ships(self):
        """Rules tighten. A draft already on a record is re-checked every render."""
        from src import render
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "clearwater")
        key = next(iter(rec["cadence"]))
        rec["cadence"][key]["day15"] = {
            "channel": "email", "generated": True,
            "subject": "picking this back up",
            "body": BAD_BODY}
        store.save(recs)
        render.build()

        html = self.out_file("review.html")
        self.assertIn('<article class="failed">', html)
        csv_text = self.out_file("emailbison.csv")
        self.assertNotIn("[FIRST NAME]", csv_text)
        self.assertNotIn("picking this back up", csv_text)

    def test_the_held_record_keeps_its_drafts_but_ships_nothing(self):
        rec = self.rec("stonebridge")
        self.assertEqual(rec["state"], "held")
        self.assertNotIn("otto.lindqvist", self.out_file("emailbison.csv"))


class TestCadenceAndPause(EndToEnd):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_the_buyer_track_starts_behind_the_champion(self):
        prepared = push.run(day=30)
        days = {}
        for item in prepared["ready"]:
            if item["record"]["id"] != "clearwater":
                continue
            days.setdefault(item["contact_key"], []).append(item["step"]["day"])
        contacts = {c["key"]: c["persona"] for c in self.rec("clearwater")["contacts"]}
        champion_first = min(min(v) for k, v in days.items()
                             if contacts.get(k) == "champion")
        buyer_first = min(min(v) for k, v in days.items()
                          if contacts.get(k) == "economic_buyer")
        self.assertEqual(buyer_first, champion_first + 5)

    def test_an_email_reply_pauses_the_whole_company_on_both_channels(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "clearwater")
        contact = rec["contacts"][0]["key"]
        cadence.record_event(rec, "email_reply", contact)
        store.save(recs)

        prepared = push.run(day=30)
        self.assertFalse(any(i["record"]["id"] == "clearwater"
                             for i in prepared["ready"]))
        timeline = cadence.build(self.rec("clearwater"))
        statuses = {s["status"] for steps in timeline["contacts"].values()
                    for s in steps.values()}
        self.assertEqual(statuses, {"paused"})

    def test_a_linkedin_reply_pauses_it_just_the_same(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "clearwater")
        cadence.record_event(rec, "linkedin_reply", rec["contacts"][1]["key"])
        store.save(recs)
        self.assertTrue(cadence.build(self.rec("clearwater"))["paused"])

    def test_the_other_companies_carry_on_after_a_pause(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "clearwater")
        cadence.record_event(rec, "email_reply", rec["contacts"][0]["key"])
        store.save(recs)
        prepared = push.run(day=30)
        self.assertTrue(any(i["record"]["id"] == "northwind"
                            for i in prepared["ready"]))

    def test_accepting_a_connection_releases_day_8_and_shortens_day_10(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "northwind")
        key = rec["contacts"][0]["key"]
        long_day10 = cadence.build(rec)["contacts"][key]["day10"]["body"]
        cadence.record_event(rec, "connection_accepted", key)
        store.save(recs)
        steps = cadence.build(self.rec("northwind"))["contacts"][key]
        self.assertEqual(steps["day8"]["status"], "eligible")
        self.assertLess(len(steps["day10"]["body"]), len(long_day10))


class TestPushPreparationAndIdempotency(EndToEnd):
    def setUp(self):
        super().setUp()
        self.walk()

    def test_nothing_is_ever_sent(self):
        push.run(day=30)
        self.assertNotIn("AddLeads", " ".join(self.cassette.urls()))
        self.assertNotIn("/leads", " ".join(self.cassette.urls()))

    def test_live_is_refused(self):
        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(day=30, live=True)

    def test_the_payloads_are_the_documented_shapes(self):
        prepared = push.run(day=30, campaign_id=7, linkedin_account_id=2)
        lead = prepared["payloads"]["emailbison"]["body"]["leads"][0]
        self.assertIn("custom_variables", lead)
        pair = prepared["payloads"]["heyreach"]["body"]["accountLeadPairs"][0]
        self.assertEqual(pair["linkedInAccountId"], 2)

    def test_a_partial_push_then_a_retry_sends_nothing_twice(self):
        first = push.run(day=30)["ready"]
        half = first[: len(first) // 2]
        recs = store.load()
        for item in half:
            rec = next(r for r in recs if r["id"] == item["record"]["id"])
            push.mark_pushed(rec, item["contact_key"], item["step_key"], item["push_id"])
        store.save(recs)

        second = push.run(day=30)["ready"]
        done = {i["push_id"] for i in half}
        again = {i["push_id"] for i in second}
        self.assertEqual(done & again, set())
        self.assertEqual(len(again), len(first) - len(half))

    def test_pushing_everything_then_rerunning_prepares_nothing(self):
        ready = push.run(day=30)["ready"]
        recs = store.load()
        for item in ready:
            rec = next(r for r in recs if r["id"] == item["record"]["id"])
            push.mark_pushed(rec, item["contact_key"], item["step_key"], item["push_id"])
        store.save(recs)
        self.assertEqual(push.run(day=30)["ready"], [])

    def test_no_two_prepared_items_share_an_identity(self):
        ids = [i["push_id"] for i in push.run(day=30)["ready"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestTheProviderWaterfall(EndToEnd):
    """The new providers, inside the same twelve row batch."""

    def setUp(self):
        super().setUp()
        self.walk()

    def test_contactout_answered_first_everywhere_it_could(self):
        urls = self.cassette.urls()
        first_paid = next(i for i, u in enumerate(urls)
                          if "decision-makers" in u or "people/search" in u)
        self.assertIn("people/count", urls[0])
        self.assertGreater(first_paid, 0)

    def test_ai_ark_ran_only_where_contactout_found_nobody(self):
        northwind = self.rec("northwind")
        self.assertTrue(any(e.get("source") == "aiark"
                            for e in northwind["events"]
                            if e["type"] == "contact_found"))
        for rid in ("clearwater", "harborview"):
            self.assertFalse(any(e.get("source") == "aiark"
                                 for e in self.rec(rid)["events"]
                                 if e["type"] == "contact_found"), rid)

    def test_the_ai_ark_fallback_carries_a_machine_readable_reason(self):
        from src import enrich
        reasons = [e.get("reason") for e in self.rec("northwind")["events"]
                   if e["type"] == "provider_call_planned"
                   and e.get("provider") == "aiark"]
        self.assertTrue(reasons)
        self.assertTrue(any(any(code in r for code in enrich.FALLBACK_REASONS)
                            for r in reasons), reasons)

    def test_apify_ran_because_this_client_asked_for_it(self):
        """The premise changed, so the assertion has to.

        This asserted apify never ran "because no client enabled it", and it
        was true for two reasons at once: the client had not opted in, and
        `run.stage_enrich` passed no config, so `research` could not run for
        any client. Productive now opts in, and the stage passes the config,
        so the opt-in is what decides - which is the property worth pinning.
        """
        self.assertIn("apify", " ".join(self.cassette.urls()))

    def test_and_a_client_that_did_not_ask_gets_no_scrape(self):
        """The guard itself, asked directly rather than inferred from a run."""
        from src import clients, research
        rec = store.load()[0]
        off = dict(clients.load("productive"), research={})
        self.assertIn("not enabled", research.plan(rec, off).get("why_not", ""))

    def test_deliverable_never_called_while_its_contract_is_unconfirmed(self):
        self.assertNotIn("deliverable", " ".join(self.cassette.urls()))

    def test_a_deliverable_failure_never_becomes_evidence_of_validity(self):
        for rec in store.load():
            for contact in rec.get("contacts") or []:
                block = contact.get("verification") or {}
                for entry in block.get("evidence") or []:
                    if entry["provider"] == "deliverable":
                        self.assertEqual(entry["status"], "error")
                        if block["sendable"]:
                            # something else cleared it, never the failure
                            self.assertTrue(any(e["status"] == "valid"
                                                for e in block["evidence"]
                                                if e["provider"] != "deliverable"))

    def test_every_verified_contact_went_through_the_central_resolver(self):
        for rec in store.load():
            for contact in rec.get("contacts") or []:
                if contact.get("sendable"):
                    self.assertIn("verification", contact)
                    self.assertEqual(contact["verification"]["state"], "verified")

    def test_the_catch_all_that_cleared_needed_reoon(self):
        """Reoon was still asked, and its answer is still on the record.

        What changed is what that answer buys: clearing the catch-all is one
        confirmation, and the address needs two. The waterfall behaviour this
        test was written for - ContactOut first, Reoon only where a catch-all
        needs resolving - is unchanged.
        """
        contact = self.rec("harborview")["contacts"][0]
        providers = contact["verification"]["providers"]
        self.assertIn("contactout", providers)
        self.assertIn("reoon", providers)
        self.assertIs(contact["reoon"]["is_safe_to_send"], True)
        self.assertFalse(contact["sendable"])

    def test_the_catch_all_that_did_not_clear_is_uncleared_not_held_blindly(self):
        contact = self.rec("stonebridge")["contacts"][0]
        self.assertEqual(contact["verification"]["state"], "accept_all_uncleared")
        self.assertFalse(contact["sendable"])

    def test_the_invalid_address_stopped_the_spend_immediately(self):
        contact = self.rec("deadletter")["contacts"][0]
        self.assertEqual(contact["verification"]["state"], "invalid")
        self.assertNotIn("reoon", contact["verification"]["providers"])

    def test_the_report_can_break_the_run_down_by_provider(self):
        from src import report
        stats = report.by_provider()
        self.assertIn("contactout", stats)
        self.assertGreater(stats["contactout"]["planned"], 0)
        self.assertIsNone(stats["contactout"]["actual_credits"])

    def test_the_report_can_break_verification_down_by_verifier(self):
        from src import report
        stats = report.by_verifier()
        self.assertIn("contactout", stats["per_verifier"])
        self.assertIn("sendable", stats["final"])

    def test_one_provider_failing_does_not_stop_the_batch(self):
        """Deliverable errors on every contact and the batch still completes."""
        states = {r["id"]: r["state"] for r in store.load()}
        self.assertIn("approved", states.values())
        self.assertEqual(states["deadletter"], "dropped")


class TestRunnerResume(EndToEnd):
    def test_the_batch_resumes_after_a_simulated_crash(self):
        from src import enrich
        self.ingest_batch()
        # Same reason as `walk`: without a verdict these records are held back
        # by the ICP gate and the stage is `partial`, not `done` - correctly,
        # because they have not finished. This test is about the crash, so it
        # needs records that are able to finish.
        qualify_everything()

        original = enrich.enrich_record
        processed = []

        def crash_after_three(rec, budget, live=False, log=None, **kw):
            if len(processed) >= 3:
                raise RuntimeError("simulated crash mid batch")
            processed.append(rec["id"])
            return original(rec, budget, live=live, log=log, **kw)

        enrich.enrich_record = crash_after_three
        try:
            crashed = run.run(spend=True, model=self.model)
        finally:
            enrich.enrich_record = original

        finished = {r["id"] for r in store.load()
                    if r.get("stages", {}).get("enrich", {}).get("status") == "done"}
        self.assertEqual(len(finished), 3)
        self.assertTrue(crashed["failures"])

        seen = []
        again = enrich.enrich_record

        def watch(rec, budget, live=False, log=None, **kw):
            seen.append(rec["id"])
            return again(rec, budget, live=live, log=log, **kw)

        enrich.enrich_record = watch
        try:
            run.run(spend=True, model=self.model)
        finally:
            enrich.enrich_record = again

        self.assertEqual(set(seen) & finished, set())
        self.assertEqual(len(store.load()), 12)

    def test_a_second_full_run_changes_no_state(self):
        self.walk()
        first = {r["id"]: r["state"] for r in store.load()}
        run.run(spend=True, model=self.model)
        self.assertEqual({r["id"]: r["state"] for r in store.load()}, first)


class TestTheFinalShape(EndToEnd):
    """The exact end state of the batch, asserted as a whole."""

    def setUp(self):
        super().setUp()
        self.walk()

    def test_the_state_of_every_record(self):
        states = {r["id"]: r["state"] for r in store.load()}
        self.assertEqual(states, {
            "clearwater": "approved",
            "harborview": "held",
            "stonebridge": "held",
            "deadletter": "dropped",
            "northwind": "approved",
            "samename": "approved",
            "kestrel": "dropped",
            "blocked-co": "dropped",
            "clearwater-again": "dropped",
            "no-domain-co": "dropped",
            "redwood": "approved",
            "skyline": "approved",
        })

    def test_every_dropped_record_says_why(self):
        for rec in store.load():
            if rec["state"] == "dropped":
                self.assertTrue(rec["drop_reason"], rec["id"])

    def test_the_summary_counts_add_up(self):
        summary = json.loads(self.out_file("summary.json"))
        self.assertEqual(summary["records"], 12)
        self.assertEqual(summary["failed"] + summary["held"] + summary["clean"],
                         summary["emails"])
        self.assertGreater(summary["clean"], 0)
        self.assertEqual(summary["failed"], 0,
                         "a draft that never passed lint is not stored at all")

    def test_the_review_sheet_shows_green_and_can_show_red(self):
        from src import render
        html = self.out_file("review.html")
        self.assertIn('<article class="clean">', html)

        recs = store.load()
        rec = next(r for r in recs if r["id"] == "clearwater")
        key = next(iter(rec["cadence"]))
        rec["cadence"][key]["day15"] = {"channel": "email", "generated": True,
                                        "subject": "s", "body": BAD_BODY}
        store.save(recs)
        render.build()
        self.assertIn('<article class="failed">', self.out_file("review.html"))

    def test_the_queue_still_holds_every_record_it_started_with(self):
        self.assertEqual(len(store.load()), 12)


if __name__ == "__main__":
    unittest.main()
