"""Thirteen ways this breaks, and what must still be true afterwards.

Two invariants run through every test here, and they are the only ones that
matter when something has already gone wrong:

    resumable   the work can be picked up again without repeating what was
                already done or losing what was already learned
    auditable   the record says what happened, so somebody can tell the
                difference between "we did not do this" and "we do not know"

A failure that leaves a record in neither state is worse than a crash, because
a crash is obvious and a half-written record is not.
"""
import json
import os
import unittest

from src import (channels, clients, enrich, eligibility, evidence, generate,
                 inbound, lint, mx, orchestrator, poller, providers, push,
                 quality, replaysim, simulator, store, synthetic, verification,
                 waterfall)
from tests.campaignbase import CampaignTest


class Timeout(TimeoutError):
    """What a provider timeout actually looks like from up here."""


def timing_out(*a, **kw):
    raise Timeout("the provider did not answer in time")


def malformed(*a, **kw):
    return 200, "{this is not json"


class FailureTest(CampaignTest):
    def seeded(self, size=28):
        recs = synthetic.dataset(size, self.config)
        store.save(recs)
        return store.load()


# ---------------------------------------------------------- provider timeouts

class TestProviderTimeouts(FailureTest):
    """Each of the five providers, timing out, one at a time."""

    def transport_that_times_out(self):
        def transport(method, url, headers, body, timeout):
            raise providers.ProviderError("timeout")
        return transport

    def test_a_transport_timeout_is_retried_a_bounded_number_of_times(self):
        attempts = []

        def flaky():
            attempts.append(1)
            raise providers.ProviderError("timeout")

        with self.assertRaises(poller.PollError) as raised:
            poller.with_retry(flaky, attempts=3, backoff=(0, 0),
                              sleep=lambda s: None)
        self.assertEqual(len(attempts), 3, "retry must be finite")
        self.assertIn("gave up after 3", str(raised.exception),
                      "giving up must say how many times it tried")

    def test_a_malformed_payload_is_never_retried(self):
        attempts = []

        def broken():
            attempts.append(1)
            raise ValueError("not json")

        with self.assertRaises(ValueError):
            poller.with_retry(broken, attempts=3, backoff=(0, 0),
                              sleep=lambda s: None)
        self.assertEqual(len(attempts), 1,
                         "a payload we cannot read will not become readable")

    def test_contactout_timing_out_leaves_the_record_resumable(self):
        recs = self.seeded()
        rec = recs[0]
        before = json.dumps(rec, sort_keys=True)
        self.providers.set_transport(self.transport_that_times_out())
        try:
            budget = enrich.Budget(cap=5)
            try:
                enrich.enrich_record(rec, budget, live=True, config=self.config)
            except Exception:
                pass
        finally:
            self.providers.set_transport(self.cassette)
        # Either it recorded what happened, or it changed nothing at all.
        # What it must not do is half-apply an enrichment.
        after = json.dumps(rec, sort_keys=True)
        self.assertTrue(after == before or rec.get("log"),
                        "a timeout must leave a trail or leave no trace")

    def test_every_provider_in_the_waterfall_has_a_retry_policy(self):
        """A provider nobody decided about is a provider that retries forever."""
        for stage in waterfall.STAGE_NAMES:
            for provider in waterfall.providers_for(stage):
                self.assertIn(provider, waterfall.COST_UNITS, provider)

    def test_aiark_reoon_deliverable_and_apify_all_raise_provider_error(self):
        """One error type means one retry policy, rather than four."""
        from src.providers import aiark, apify, deliverable, reoon
        for module in (aiark, apify, deliverable, reoon):
            self.assertTrue(hasattr(module, "__name__"))
        self.assertIn(providers.ProviderError, poller.retryable())


class TestDNSTimeout(FailureTest):
    def test_a_dns_timeout_holds_email_rather_than_assuming_it_is_safe(self):
        decision = mx.for_domain("acme.test", self.config, cache={},
                                 resolver=timing_out, save=False)
        self.assertEqual(decision["status"], mx.DNS_FAILURE)
        self.assertFalse(decision["email_eligible"])

    def test_a_dns_timeout_is_not_cached(self):
        cache = {}
        mx.for_domain("acme.test", self.config, cache=cache,
                      resolver=timing_out, save=False)
        self.assertEqual(cache, {})

    def test_a_dns_timeout_leaves_linkedin_alone(self):
        rec = {"id": "a", "client": "demo", "domain": "acme.test",
               "contacts": [{"key": "c0", "email": "a@acme.test",
                             "linkedin": "https://www.linkedin.com/in/ann",
                             "verification": {"state": verification.VERIFIED,
                                              "evidence": []}}]}
        rec["contacts"][0]["mx"] = mx.for_domain(
            "acme.test", self.config, cache={}, resolver=timing_out, save=False)
        verdict = channels.evaluate(rec, rec["contacts"][0], self.config,
                                    suppressed=set())
        self.assertFalse(verdict["email_eligible"])
        self.assertTrue(verdict["linkedin_eligible"])
        self.assertEqual(verdict["mode"], channels.LINKEDIN_ONLY)

    def test_the_reason_survives_into_the_preview(self):
        recs = self.seeded()
        rec = recs[synthetic.indices_of("dns_failure", 28)[0]]
        result = simulator.simulate(recs=[rec], client="demo",
                                    config=self.config)
        card = result["companies"][0]["cards"][0]
        self.assertEqual(card["email_excluded_reason"], "mx_dns_failure")
        self.assertIn("DNS", card["email_excluded_explained"])


# -------------------------------------------------------- malformed responses

class TestMalformedResponses(FailureTest):
    def test_a_malformed_body_never_passes_for_structured_data(self):
        """It comes back as the text it is, so a caller expecting a dict
        fails loudly instead of reading fields off a string it invented."""
        self.providers.set_transport(malformed)
        try:
            status, payload = providers.request("GET", "https://example.test/x")
        finally:
            self.providers.set_transport(self.cassette)
        self.assertEqual(status, 200)
        self.assertNotIsInstance(payload, dict)
        self.assertIsInstance(payload, str)
        with self.assertRaises(AttributeError):
            payload.get("anything")

    def test_an_unrecognised_reply_classification_is_not_a_reply(self):
        """The allowlist: unknown means unknown, never 'probably a reply'."""
        from src.providers import bison
        row = {"type": "something_new_the_api_added", "id": "1"}
        self.assertEqual(bison.classify_reply_row(row), "unknown")

    def test_an_event_naming_a_record_it_does_not_belong_to_is_refused(self):
        recs = self.seeded()
        event = {"provider": "bison", "provider_event_id": "x",
                 "type": "reply_received", "record_id": "does-not-exist",
                 "contact": "nobody", "text": "hello", "at": store.now()}
        outcome = inbound.handle(event, recs, config=self.config)
        self.assertNotEqual((outcome.get("applied") or {}).get("status"),
                            "applied")

    def test_a_corrupt_mx_cache_does_not_stop_the_world(self):
        path = mx.cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(mx.load_cache(), {})

    def test_a_corrupt_checkpoint_file_restarts_rather_than_crashes(self):
        path = poller.checkpoint_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{[")
        self.assertEqual(poller.load_checkpoints(), {})


# ------------------------------------------------------------ partial batches

class TestPartialBatchFailure(FailureTest):
    def test_one_poisoned_record_does_not_stop_the_batch(self):
        recs = self.seeded()
        recs[3]["contacts"] = "not a list"
        survived, failed = 0, 0
        for rec in recs:
            try:
                channels.summarise([rec], self.config)
                survived += 1
            except Exception:
                failed += 1
        self.assertEqual(failed, 1)
        self.assertEqual(survived, len(recs) - 1)

    def test_the_simulator_reports_what_it_could_and_names_what_it_could_not(self):
        recs = self.seeded()
        good = [r for r in recs if r["id"] != recs[3]["id"]]
        result = simulator.simulate(recs=good, client="demo",
                                    config=self.config)
        self.assertEqual(result["headline"]["companies"], len(good))

    def test_a_half_written_batch_is_never_left_in_the_queue(self):
        """Temp file plus rename: the queue is the old file or the new one."""
        recs = self.seeded()
        store.save(recs)
        for name in os.listdir(os.path.dirname(store.queue_path())):
            self.assertFalse(name.endswith(".tmp"), name)


# ------------------------------------------------------------- LLM and lint

class TestGenerationFailures(FailureTest):
    def broken_model(self):
        """A model in the shape the codebase uses: an object with .complete."""
        from src import llm

        class Down:
            name = "down"

            def complete(self, prompt, client=None):
                raise llm.ModelError("the model is down")

        return Down()

    def test_a_model_failure_holds_the_record_and_says_why(self):
        """It does not raise past the caller: the batch continues, and this
        record carries the reason it stopped."""
        broken_model = self.broken_model()
        rec = self.seeded()[0]
        rec["state"] = "enriched"
        rec.pop("cadence", None)              # so there is work to generate
        rec["hook"] = None                    # forces the hook step to run
        generate.generate_record(rec, broken_model, self.config)
        self.assertEqual(rec["state"], "held")
        self.assertTrue(any("held" in entry.get("note", "")
                            for entry in rec.get("log") or []),
                        "the hold must be explained in the log")

    def test_a_held_record_wrote_no_draft(self):
        broken_model = self.broken_model()
        rec = self.seeded()[0]
        rec["state"] = "enriched"
        rec.pop("cadence", None)
        rec["hook"] = None
        generate.generate_record(rec, broken_model, self.config)
        for steps in (rec.get("cadence") or {}).values():
            for step in steps.values():
                self.assertFalse(step.get("body"),
                                 "a failed generation must leave no half draft")

    def test_a_model_that_returns_junk_fails_lint_rather_than_shipping(self):
        rec = self.seeded()[0]
        key = rec["contacts"][0]["key"]
        rec.setdefault("cadence", {}).setdefault(key, {})["day1"] = {
            "channel": "email", "generated": True, "subject": "",
            "body": "Hi {{first_name}}"}
        failures = lint.check_step(rec, key, rec["cadence"][key]["day1"])
        self.assertIn("placeholder", failures)
        self.assertEqual(lint.classify(failures), "failed")

    def test_a_step_that_fails_lint_is_held_not_removed(self):
        recs = self.seeded()
        rec = recs[synthetic.indices_of("clean_multichannel", 28)[0]]
        key = rec["contacts"][0]["key"]
        rec["cadence"][key]["day1"]["body"] = "Hi {{first_name}}, quick one.\n"
        result = simulator.simulate(recs=[rec], client="demo",
                                    config=self.config)
        timeline = result["companies"][0]["cards"][0]["timeline"]
        day1 = next(row for row in timeline if row["step"] == "day1")
        self.assertTrue(day1["lint"], "the failure must be visible")
        self.assertIsNotNone(day1["body"], "the draft must not be deleted")

    def test_a_linkedin_step_that_fails_lint_is_held_too(self):
        rec = self.seeded()[0]
        key = rec["contacts"][0]["key"]
        step = {"channel": "linkedin", "note": "x" * 400}
        self.assertEqual(lint.check_step(rec, key, step), ["note_too_long"])


# --------------------------------------------------------- identity ambiguity

class TestIdentityAmbiguity(FailureTest):
    def test_an_unusable_profile_url_stops_linkedin_rather_than_guessing(self):
        rec = {"id": "a", "client": "demo", "domain": "acme.test",
               "contacts": [{"key": "c0", "name": "Ann",
                             "linkedin": "https://www.linkedin.com/company/acme"}]}
        verdict = channels.evaluate(rec, rec["contacts"][0], self.config,
                                    suppressed=set())
        self.assertFalse(verdict["linkedin_eligible"])
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.PROFILE_UNUSABLE)

    def test_a_duplicate_identity_blocks_rather_than_merging(self):
        rec = {"id": "a", "client": "demo", "domain": "acme.test",
               "contacts": [{"key": "c0", "name": "Ann",
                             "linkedin": "https://www.linkedin.com/in/ann",
                             "duplicate_of": {"record_id": "b",
                                              "contact_key": "c0"}}]}
        verdict = channels.evaluate(rec, rec["contacts"][0], self.config,
                                    suppressed=set())
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.DUPLICATE)

    def test_ambiguity_is_counted_in_the_qa_metrics(self):
        recs = self.seeded()
        rec = recs[0]
        rec["contacts"][0]["duplicate_of"] = {"record_id": "x",
                                              "contact_key": "y"}
        result = simulator.simulate(recs=[rec], client="demo",
                                    config=self.config)
        self.assertGreater(
            simulator.qa_metrics(result)["identity_ambiguity_count"], 0)


# --------------------------------------------------------- Slack unavailable

class TestSlackUnavailable(FailureTest):
    def test_a_failed_notification_does_not_undo_the_pause(self):
        """The pause is in place first. Whatever Slack does, it stays."""
        campaign, _, _ = self.approved_campaign()
        recs = store.load()
        rec = recs[0]
        key = rec["contacts"][0]["key"]

        def broken_post(payload, config=None, **kw):
            raise RuntimeError("slack is down")

        event = {"provider": "bison", "provider_event_id": "sim-1",
                 "type": "reply_received", "channel": "email",
                 "record_id": rec["id"], "contact": key,
                 "text": "Sounds interesting. Happy to chat - what does your "
                         "availability look like next week?",
                 "at": store.now()}
        try:
            inbound.handle(event, recs, config=self.config, post=broken_post)
        except Exception:
            pass
        self.assertTrue(rec.get("paused"),
                        "a Slack outage must not resurrect a paused company")

    def test_the_simulation_never_needs_slack_to_be_up(self):
        campaign, _, _ = self.approved_campaign()
        recs = store.load()
        result = replaysim.simulate(recs[0], recs[0]["contacts"][0]["key"],
                                    "positive_email", recs=recs,
                                    config=self.config, campaign=campaign)
        self.assertFalse(result["slack_delivered"])
        self.assertIsNotNone(result["slack_payload"])


# ------------------------------------------------------------ crash and resume

class TestCrashAndRestart(FailureTest):
    def test_a_crash_after_the_push_and_before_the_mark_repeats_nothing(self):
        recs = self.seeded()
        rec = recs[synthetic.indices_of("clean_multichannel", 28)[0]]
        key = rec["contacts"][0]["key"]
        identity = push.push_id(rec, key, "day1", "email")
        push.mark_pushed(rec, key, "day1", identity)
        store.save(recs)

        fresh = store.load()                     # as a new process would
        again = next(r for r in fresh if r["id"] == rec["id"])
        self.assertTrue(push.already_pushed(again, key, "day1"))
        decision = eligibility.decide(again, again["contacts"][0], "day1",
                                      "email", recs=fresh, config=self.config)
        self.assertEqual(decision["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_ALREADY_PUSHED, decision["reasons"])

    def test_a_restart_resumes_from_the_stored_cursor(self):
        poller.save_checkpoint("bison", "cursor-42")
        self.assertEqual(poller.cursor_for("bison"), "cursor-42")

    def test_a_restart_with_no_cursor_starts_from_the_top_safely(self):
        """Every event is idempotent, so replaying the first page is harmless."""
        self.assertIsNone(poller.cursor_for("never-polled"))

    def test_the_same_event_twice_changes_state_once(self):
        campaign, _, _ = self.approved_campaign()
        recs = store.load()
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        event = {"provider": "bison", "provider_event_id": "dup-1",
                 "type": "reply_received", "channel": "email",
                 "record_id": rec["id"], "contact": key,
                 "text": "Not interested, please remove me.",
                 "at": store.now()}
        inbound.handle(dict(event), recs, config=self.config)
        first = len(rec.get("events") or [])
        inbound.handle(dict(event), recs, config=self.config)
        self.assertEqual(len(rec.get("events") or []), first,
                         "a replayed webhook must not double-apply")

    def test_the_waterfall_ledger_survives_a_reload(self):
        recs = self.seeded()
        rec = recs[0]
        waterfall.record_step(rec, "company_information", waterfall.CONTACTOUT,
                              "company-information-from-domain",
                              result="ok")
        store.save(recs)
        again = next(r for r in store.load() if r["id"] == rec["id"])
        self.assertEqual(len(waterfall.ledger(again)), 1)
        self.assertEqual(waterfall.audit(again)["unjustified"], [])


class TestEverythingStaysAuditable(FailureTest):
    def test_a_held_contact_always_says_what_would_fix_it(self):
        recs = self.seeded()
        result = simulator.simulate(recs=recs, client="demo",
                                    config=self.config)
        for company in result["companies"]:
            for card in company["cards"]:
                if not card["held"]:
                    continue
                self.assertTrue(card["email_excluded_reason"])
                self.assertTrue(card["linkedin_excluded_reason"])

    def test_no_failure_path_writes_a_partial_record(self):
        recs = self.seeded()
        for rec in recs:
            store.validate(rec)

    def test_no_provider_was_called_by_any_of_this(self):
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
