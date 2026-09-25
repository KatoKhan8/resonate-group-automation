#!/usr/bin/env python3
"""CheapVerifier: the free rung, the credit rule, and the order it sits in.

EVERY CASSETTE HERE IS A REAL RESPONSE. `tests/cassettes/cheapverifier/*.json`
were produced on 2026-09-25 by `work/cv/record_cassettes.py`, which makes the
call and saves what came back; each carries a `_provenance` block saying so.
None was hand-written. ~30 tests were green against invented Apify actor ids
this week because the cassettes matched the invention, and a cassette written
by the same person as the parser tests nothing but their consistency.

WHAT IS *NOT* CASSETTED, AND IS NOT FAKED TO LOOK CASSETTED: a 200 from
`/email-validation`, a 200 from `/file/upload`, and `/task/details` for a real
completed file. Recording those costs credits, and Productive's declared
`per_day` ceiling of 5,000 already stands at 14,365 committed, so
`spendledger.check` refuses a single credit. Those paths are exercised below
through CONSTRUCTED responses that are labelled as such: they test OUR guard
logic, and they make no claim about what the provider sends.

THE FOUR THINGS THIS PINS:

1. A 404 from the stored lookup is `None`, not an exception and not a verdict.
2. `catch_all` and `unknown` cost 0; only `valid` and `invalid` cost 1; a
   reservation is never spend; `billingStatus: pending` is never free.
3. `invalid` at CheapVerifier ends the waterfall - nothing more is bought.
4. `/task/details` proves it read every row, or refuses.
"""
import json
import os
import unittest

from src import verification
from src.providers import cheapverifier as cv

CASSETTES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "cassettes", "cheapverifier")


def cassette(name):
    """A recorded response. Fails loudly if it was not actually recorded."""
    path = os.path.join(CASSETTES, name + ".json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not (data.get("_provenance") or {}).get("real"):
        raise AssertionError(
            f"{name} is not marked as a recorded response. A cassette that "
            f"was written rather than recorded proves only that its author "
            f"was consistent with themselves")
    return data


def replay(*names):
    """A transport that answers each call from the next recorded response."""
    queue = [cassette(n) for n in names]

    def transport(method, url, headers, body, timeout):
        if not queue:
            raise AssertionError("more calls were made than cassettes given")
        item = queue.pop(0)
        return item["status"], json.dumps(item["body"])
    return transport


class StoredLookupReadsA404AsNothingStored(unittest.TestCase):
    """The free rung, and the mistake that would break the whole run."""

    def setUp(self):
        os.environ["CHEAPVERIFIER_API_KEY"] = "test-key-not-real"
        self.previous = None

    def tearDown(self):
        from src import providers
        providers.reset_transport()
        os.environ.pop("CHEAPVERIFIER_API_KEY", None)

    def test_a_404_is_none_and_never_raises(self):
        """THE CENTRAL ONE. A cache miss is an answer, not a failure.

        On a cold cohort nearly every address is a miss. If this raised, the
        free rung - the one that exists so we never pay twice for the same
        answer - would be the thing that breaks the run on the first address.
        """
        from src import providers
        providers.set_transport(replay("stored_miss_404"))
        self.assertIsNone(cv.stored("anyone@example.invalid"))

    def test_the_recorded_404_really_is_a_404_saying_nothing_is_stored(self):
        """The cassette is checked, not assumed. It is the premise of the test above."""
        recorded = cassette("stored_miss_404")
        self.assertEqual(404, recorded["status"])
        self.assertIn("No validation result found",
                      json.dumps(recorded["body"]))

    def test_a_miss_is_not_a_verdict(self):
        """None must not normalise into something the waterfall can act on."""
        from src import providers
        providers.set_transport(replay("stored_miss_404"))
        answer = cv.stored("anyone@example.invalid")
        self.assertIsNone(answer)
        # And the normaliser, handed nothing, holds the address rather than
        # clearing it.
        entry = cv.normalise(None, "anyone@example.invalid")
        self.assertEqual("unknown", entry["status"])
        self.assertIsNot(True, entry.get("deliverable"))

    def test_an_unusable_address_is_raised_not_silently_unknown(self):
        from src import providers
        providers.set_transport(replay("stored_invalid_syntax_422"))
        with self.assertRaises(Exception):
            cv.stored("not-an-address")


class AWrongKeyIs403AndTheSpecSaysOtherwise(unittest.TestCase):
    """The live API deviates from its own document, and the adapter reads both."""

    def tearDown(self):
        from src import providers
        providers.reset_transport()
        os.environ.pop("CHEAPVERIFIER_API_KEY", None)

    def test_both_401_and_403_are_credential_failures(self):
        self.assertTrue(cv.auth_failure(401))
        self.assertTrue(cv.auth_failure(403))
        self.assertFalse(cv.auth_failure(404))
        self.assertFalse(cv.auth_failure(500))

    def test_the_recorded_responses_show_403_for_a_wrong_key(self):
        """Recorded, not asserted from the spec - which documents 401 here."""
        self.assertEqual(403, cassette("auth_wrong_key_403")["status"])
        self.assertEqual(401, cassette("auth_missing_key_401")["status"])

    def test_no_real_error_body_carries_the_documented_success_field(self):
        """The spec's Error schema promises `success: false`. Nothing sends it.

        An adapter that branched on `success` would be reading a field the
        provider does not send, and the branch would never fire.
        """
        errors = ("stored_miss_404", "stored_invalid_syntax_422",
                  "auth_missing_key_401", "auth_wrong_key_403",
                  "task_status_missing_404", "task_details_missing_404",
                  "uploads_results_missing_404",
                  "uploads_results_bad_status_422",
                  "single_missing_param_400")
        for name in errors:
            body = cassette(name)["body"]
            self.assertNotIn(
                "success", body if isinstance(body, dict) else {},
                f"{name} carries `success`, so the spec's envelope may be "
                f"real after all - re-check message_of()")

    def test_message_of_reads_every_shape_that_was_actually_sent(self):
        """Four different envelopes across five endpoints, all real."""
        self.assertIn("No validation result",
                      cv.message_of(cassette("stored_miss_404")["body"]))
        # {"error": "Task not found"} - no `message` key at all.
        self.assertEqual("Task not found",
                         cv.message_of(cassette("task_details_missing_404")["body"]))
        # {"status":"error","message":"Task not found"} - a different shape.
        self.assertEqual("Task not found",
                         cv.message_of(cassette("task_status_missing_404")["body"]))
        # 422 carries its reason in `details`, not in `message`.
        self.assertIn("must be a valid email address",
                      cv.message_of(cassette("stored_invalid_syntax_422")["body"]))


class TheCreditRuleIsKeyedOnTheOutcome(unittest.TestCase):
    """The money. One credit per address that reached a verdict, and no other."""

    def test_only_valid_and_invalid_cost_a_credit(self):
        self.assertEqual(1, cv.credits_for("valid"))
        self.assertEqual(1, cv.credits_for("invalid"))
        self.assertEqual(0, cv.credits_for("catch_all"))
        self.assertEqual(0, cv.credits_for("unknown"))

    def test_an_unrecognised_outcome_costs_a_credit_not_zero(self):
        """The conservative direction. Under-reporting a bill is how a ledger
        stops being able to refuse."""
        self.assertEqual(1, cv.credits_for("something_new"))
        self.assertEqual(1, cv.credits_for(None))

    def test_a_reservation_is_held_and_never_ledgered_as_spend(self):
        """`creditsReserved` is one credit per deduplicated row, HELD.

        Ledgering it would over-report the bill by every catch_all and
        unknown in the file - and this ledger is what refuses the NEXT call,
        so an over-report becomes a refusal of work that was affordable.
        """
        receipt = cv.trim_upload({"fileId": "1", "creditsReserved": 500,
                                  "emailCount": 500}, submitted=500)
        self.assertEqual(500, receipt["credits_reserved"])
        self.assertNotIn("credits", receipt)
        held = cv.reserved_is_not_spent(receipt)
        self.assertEqual(500, held["held"])
        self.assertEqual(0, held["spent"])

    def test_a_file_settles_to_the_rows_that_reached_a_verdict(self):
        rows = [{"outcome": "valid"}, {"outcome": "valid"},
                {"outcome": "invalid"},
                {"outcome": "catch_all"}, {"outcome": "catch_all"},
                {"outcome": "unknown"}]
        account = cv.settlement(rows)
        self.assertEqual(6, account["rows"])
        self.assertEqual(3, account["credits"])       # not 6
        self.assertEqual(3, account["chargeable_rows"])
        self.assertEqual(3, account["free_rows"])

    def test_billing_status_pending_is_chargeable_not_free(self):
        """`pending` means not settled yet and STILL CHARGEABLE.

        A settlement that read pending as free would under-report by every
        row still in flight.
        """
        body = {"status": "success",
                "data": {"email": "x@example.invalid", "outcome": "valid"},
                "creditsUsed": 0,                 # not settled yet
                "billingStatus": "pending"}
        trimmed = cv.trim_single(body, "x@example.invalid")
        self.assertEqual("pending", trimmed["billing_status"])
        self.assertFalse(trimmed["settled"])
        # OURS is 1, keyed on the outcome, despite creditsUsed saying 0.
        self.assertEqual(1, trimmed["credits"])

    def test_a_catch_all_costs_nothing_and_is_not_a_confirmation(self):
        body = {"status": "success",
                "data": {"email": "x@example.invalid", "outcome": "catch_all"},
                "creditsUsed": 0, "billingStatus": "completed"}
        trimmed = cv.trim_single(body, "x@example.invalid")
        self.assertEqual(0, trimmed["credits"])
        entry = cv.normalise(trimmed, "x@example.invalid")
        self.assertEqual("accept_all", entry["status"])
        self.assertFalse(entry["charged"])
        # accept_all is not in CONFIRMING_STATUSES, so it confirms nothing.
        self.assertEqual(set(), verification.confirmations([entry]))


class TheDetailsReadProvesItReadEveryRow(unittest.TestCase):
    """CONSTRUCTED responses. These test OUR guard, not the provider's shape.

    The operator states, and the spec's text agrees, that omitting `page`
    returns every row. That could not be verified live: it needs a completed
    file, which needs a paid upload, which the ceiling refuses. So the guard
    below exists precisely because the claim is unverified - and `/leads`
    already failed in this exact shape, an offset that died at page 1,000
    while `meta.last_page` promised more.
    """

    def setUp(self):
        os.environ["CHEAPVERIFIER_API_KEY"] = "test-key-not-real"

    def tearDown(self):
        from src import providers
        providers.reset_transport()
        os.environ.pop("CHEAPVERIFIER_API_KEY", None)

    def _transport(self, pages):
        """Answers each call with the next constructed page."""
        queue = list(pages)

        def transport(method, url, headers, body, timeout):
            return 200, json.dumps(queue.pop(0))
        return transport

    def test_a_complete_unpaged_read_is_accepted(self):
        from src import providers
        rows = [{"email": f"a{i}@example.invalid", "outcome": "valid"}
                for i in range(25)]
        providers.set_transport(self._transport([
            {"status": "success", "fileId": "f1", "data": rows,
             "total": 25, "page": 1, "totalPages": 1}]))
        read = cv.details("f1")
        self.assertEqual(25, len(read["rows"]))
        self.assertTrue(read["read_complete"])
        self.assertFalse(read["paged"])

    def test_a_half_read_is_refused_rather_than_returned(self):
        """THE REGRESSION THIS CATCHES. Delete the length check in `details`
        and this returns 10 rows for a 25-row file, silently."""
        from src import providers
        rows = [{"email": f"a{i}@example.invalid", "outcome": "valid"}
                for i in range(10)]
        # Says 25 rows, hands back 10, and claims a single page - so paging
        # cannot rescue it either.
        providers.set_transport(self._transport([
            {"status": "success", "fileId": "f1", "data": rows,
             "total": 25, "page": 1, "totalPages": 1},
            {"status": "success", "fileId": "f1", "data": rows,
             "total": 25, "page": 1, "totalPages": 1},
        ]))
        with self.assertRaises(cv.IncompleteRead):
            cv.details("f1")

    def test_a_short_unpaged_read_falls_back_to_paging(self):
        from src import providers
        page1 = [{"email": f"a{i}@example.invalid", "outcome": "valid"}
                 for i in range(10)]
        page2 = [{"email": f"b{i}@example.invalid", "outcome": "catch_all"}
                 for i in range(5)]
        providers.set_transport(self._transport([
            # The unpaged read returns only the first page's worth.
            {"status": "success", "fileId": "f1", "data": page1,
             "total": 15, "page": 1, "totalPages": 2},
            {"status": "success", "fileId": "f1", "data": page1,
             "total": 15, "page": 1, "totalPages": 2},
            {"status": "success", "fileId": "f1", "data": page2,
             "total": 15, "page": 2, "totalPages": 2},
        ]))
        read = cv.details("f1")
        self.assertEqual(15, len(read["rows"]))
        self.assertTrue(read["paged"])
        # And the settlement over the complete read is the real bill.
        self.assertEqual(10, cv.settlement(read["rows"])["credits"])


class InvalidAtCheapVerifierIsDropped(unittest.TestCase):
    """Rule 3 of the new order: no further spend on an invalid."""

    def test_an_invalid_primary_settles_and_buys_nothing_more(self):
        policy = dict(verification.DEFAULT_POLICY)
        policy.update({"primary": "cheapverifier", "secondary": "deliverable",
                       "catch_all": "reoon"})
        evidence = [verification.result("cheapverifier", "invalid",
                                        "x@example.invalid")]
        decision = verification.decide(evidence, policy)
        self.assertEqual(verification.INVALID, decision["state"])
        self.assertFalse(decision["sendable"])
        # Neither of the later rungs has anything to add.
        self.assertFalse(verification.needs("deliverable", evidence, policy))
        self.assertFalse(verification.needs("reoon", evidence, policy))

    def test_a_valid_primary_still_needs_the_second_opinion(self):
        """Rule 4: Deliverable runs on valid, catch_all and unknown."""
        policy = dict(verification.DEFAULT_POLICY)
        policy.update({"primary": "cheapverifier", "secondary": "deliverable",
                       "catch_all": "reoon"})
        for outcome in ("valid", "accept_all", "unknown"):
            evidence = [verification.result("cheapverifier", outcome,
                                            "x@example.invalid")]
            self.assertTrue(
                verification.needs("deliverable", evidence, policy),
                f"deliverable must be asked after a {outcome} primary")

    def test_one_confirmation_is_never_sendable(self):
        policy = dict(verification.DEFAULT_POLICY)
        policy.update({"primary": "cheapverifier", "secondary": "deliverable",
                       "catch_all": "reoon"})
        evidence = [verification.result("cheapverifier", "valid",
                                        "x@example.invalid")]
        decision = verification.decide(evidence, policy)
        self.assertFalse(decision["sendable"])
        self.assertEqual(1, decision["confirmation_count"])
        self.assertEqual(2, decision["required_confirmations"])


class TheFreeRungRunsBeforeThePaidOne(unittest.TestCase):
    """Rule 0 of the new order, proved by counting the calls that happen.

    "The stored lookup is checked first" is the kind of claim that is easy to
    write in a docstring and never actually do. These count requests.
    """

    def setUp(self):
        os.environ["CHEAPVERIFIER_API_KEY"] = "test-key-not-real"

    def tearDown(self):
        from src import providers
        providers.reset_transport()
        os.environ.pop("CHEAPVERIFIER_API_KEY", None)

    def _recording_transport(self, answers):
        """Records every URL asked for, answering from `answers` in order."""
        seen = []
        queue = list(answers)

        def transport(method, url, headers, body, timeout):
            seen.append(url)
            status, payload = queue.pop(0)
            return status, json.dumps(payload)
        return seen, transport

    def test_a_stored_hit_costs_nothing_and_no_paid_call_is_made(self):
        """THE POINT OF THE FREE RUNG. One request, zero credits."""
        from src import providers
        seen, transport = self._recording_transport([
            (200, {"email": "x@example.invalid", "outcome": "valid",
                   "reason_code": "smtp_ok", "confidence": "high",
                   "algorithm_version": "v1", "upload_id": "u1"}),
        ])
        providers.set_transport(transport)

        entry = verification.call("cheapverifier", "x@example.invalid")

        self.assertEqual(1, len(seen), "exactly one request: the free lookup")
        self.assertIn("/verify/", seen[0])
        self.assertNotIn("/email-validation", seen[0])
        self.assertEqual("valid", entry["status"])
        # And it must be marked free, because `verify()` writes a ledger row
        # for anything not explicitly free.
        self.assertFalse(entry["charged"])

    def test_a_stored_miss_falls_through_to_the_paid_call(self):
        from src import providers
        seen, transport = self._recording_transport([
            (404, {"error": "Not found",
                   "message": "No validation result found for ..."}),
            (200, {"status": "success",
                   "data": {"email": "x@example.invalid", "outcome": "valid"},
                   "creditsUsed": 1, "billingStatus": "completed"}),
        ])
        providers.set_transport(transport)

        entry = verification.call("cheapverifier", "x@example.invalid")

        self.assertEqual(2, len(seen), "the free lookup, then the paid call")
        self.assertIn("/verify/", seen[0])
        self.assertIn("/email-validation", seen[1])
        self.assertEqual("valid", entry["status"])
        self.assertTrue(entry["charged"])

    def test_a_free_outcome_from_the_paid_call_is_still_not_charged(self):
        """A catch_all costs nothing even though a paid endpoint was used."""
        from src import providers
        seen, transport = self._recording_transport([
            (404, {"error": "Not found", "message": "nothing stored"}),
            (200, {"status": "success",
                   "data": {"email": "x@example.invalid",
                            "outcome": "catch_all"},
                   "creditsUsed": 0, "billingStatus": "completed"}),
        ])
        providers.set_transport(transport)

        entry = verification.call("cheapverifier", "x@example.invalid")
        self.assertEqual("accept_all", entry["status"])
        self.assertFalse(entry["charged"])

    def test_the_stored_rung_is_wired_into_the_waterfall_at_all(self):
        """`cheapverifier` must actually be a verifier the runner can reach.

        Existence is not function: a provider module nothing dispatches to is
        a module that never runs.
        """
        self.assertIn("cheapverifier", verification.verifiers())
        self.assertEqual(1, verification.COSTS["cheapverifier"])
        self.assertIn("cheapverifier", verification.CALL_NAMES)


class TheProviderIsWiredIntoTheWaterfallLedger(unittest.TestCase):
    """EXISTENCE IS NOT FUNCTION, and this one nearly shipped broken.

    `verification.verify` calls `waterfall.record_step` for every rung, and
    `record_step` enforces `waterfall.require`, which refuses any provider the
    `EMAIL_VERIFICATION` stage does not declare. Before the stage was updated
    this raised

        WaterfallViolation: cheapverifier is not part of the
        email_verification waterfall

    on the FIRST paid call of any run that passes a record. The module
    imported, the policy resolved, and 36 unit tests passed - and production
    would have broken on address one. Caught by asking the consumer rather
    than by reading the module.
    """

    def test_the_ledger_accepts_a_cheapverifier_step(self):
        from src import waterfall
        row = waterfall.record_step(
            {"id": "r"}, waterfall.EMAIL_VERIFICATION, "cheapverifier",
            "cheapverifier-verify", reason=None, result="valid",
            expected_cost=1)
        self.assertEqual("cheapverifier", row["provider"])
        self.assertNotEqual("unknown", row["cost_unit"],
                            "a provider with no COST_UNITS entry ledgers its "
                            "cost as 'unknown', which is how a bill stops "
                            "being attributable")

    def test_it_is_a_primary_rung_and_needs_no_fallback_reason(self):
        from src import waterfall
        self.assertFalse(
            waterfall.is_fallback(waterfall.EMAIL_VERIFICATION,
                                  "cheapverifier"))

    def test_the_call_name_the_runner_uses_is_the_one_declared(self):
        """A step is matched on (provider, call). A mismatch refuses.

        `verification.CALL_NAMES` is what `verify()` passes; the stage is
        what `require()` checks against. If they drift, every call raises.
        """
        from src import waterfall
        self.assertIsNotNone(
            waterfall.step_for(waterfall.EMAIL_VERIFICATION, "cheapverifier",
                               verification.CALL_NAMES["cheapverifier"]))

    def test_the_existing_fallback_guard_still_refuses_a_reasonless_step(self):
        """Registering a new primary must not have opened the stage up."""
        from src import waterfall
        with self.assertRaises(waterfall.WaterfallViolation):
            waterfall.record_step({"id": "r"}, waterfall.EMAIL_VERIFICATION,
                                  "deliverable", "deliverable-verify",
                                  reason=None)

    def test_contactout_is_still_the_primary_for_other_workspaces(self):
        from src import waterfall
        self.assertFalse(
            waterfall.is_fallback(waterfall.EMAIL_VERIFICATION, "contactout"))


class TheVerificationPairPolicy(unittest.TestCase):
    """Both pairs are accepted, and a pair is unordered."""

    def policy(self):
        from src import clients
        return verification.policy_for(clients.load("productive"))

    def test_the_client_policy_carries_the_new_order(self):
        policy = self.policy()
        self.assertEqual("cheapverifier", policy["primary"])
        self.assertEqual("deliverable", policy["secondary"])
        self.assertEqual("reoon", policy["catch_all"])
        self.assertEqual(2, policy["required_confirmations"])
        self.assertEqual(["reoon"], policy["accept_all_clears_on"])

    def test_both_pairs_are_accepted(self):
        policy = self.policy()
        self.assertTrue(
            verification.pair_accepted(["cheapverifier", "deliverable"], policy))
        self.assertTrue(
            verification.pair_accepted(["cheapverifier", "reoon"], policy))

    def test_a_pair_is_unordered(self):
        """Which of the two answered first is scheduling, not evidence."""
        policy = self.policy()
        self.assertTrue(
            verification.pair_accepted(["deliverable", "cheapverifier"], policy))

    def test_a_pair_the_policy_does_not_declare_is_not_accepted(self):
        policy = self.policy()
        self.assertFalse(
            verification.pair_accepted(["deliverable", "reoon"], policy))
        self.assertFalse(
            verification.pair_accepted(["cheapverifier"], policy))

    def test_no_declared_policy_is_none_rather_than_true_or_false(self):
        """Undeclared is reported as undeclared, never defaulted into a policy."""
        self.assertIsNone(verification.pair_accepted(
            ["a", "b"], verification.DEFAULT_POLICY))

    def test_other_workspaces_are_untouched(self):
        self.assertEqual("contactout", verification.DEFAULT_POLICY["primary"])
        self.assertIsNone(verification.DEFAULT_POLICY["accepted_pairs"])


class TheModuleRefusesWhenUnconfigured(unittest.TestCase):
    """It refuses clearly and before the wire, rather than erroring obscurely."""

    def setUp(self):
        self.saved = os.environ.pop("CHEAPVERIFIER_API_KEY", None)
        # `key()` reads config/.env too, so point the loader at nothing.
        self.env = os.environ.get("RESONATE_ENV_FILE")

    def tearDown(self):
        if self.saved is not None:
            os.environ["CHEAPVERIFIER_API_KEY"] = self.saved

    def test_require_configured_raises_a_local_refusal(self):
        from src import providers
        if providers.load_env().get("CHEAPVERIFIER_API_KEY"):
            self.skipTest("a real key is present in config/.env")
        with self.assertRaises(cv.NotConfigured):
            cv.require_configured()

    def test_a_local_refusal_is_never_billed(self):
        """`NotConfigured` is raised before the network, so it costs nothing.

        `verification.call` marks only local refusals free. 41 credits were
        once ledgered for Deliverable calls that provably never happened.
        """
        self.assertIn(cv.NotConfigured, verification._local_refusals())

    def test_the_credential_is_registered_where_the_health_check_looks(self):
        """`credential_health` reads `config.VARIABLES`. An unregistered name
        is invisible to it."""
        from src import config
        names = [name for name, _c, group, _w in config.VARIABLES
                 if group == "providers"]
        self.assertIn("CHEAPVERIFIER_API_KEY", names)


class TheRateLimitIsMeasuredOrAbsent(unittest.TestCase):
    """An unknown limit is not permission to guess one."""

    def test_the_paid_rate_limit_is_none_and_means_unknown(self):
        self.assertIsNone(cv.RATE_LIMIT_PAID)
        self.assertIsNone(cv.recommended_workers("paid"))

    def test_the_free_rate_limit_carries_the_date_it_was_measured(self):
        self.assertEqual("2026-09-25", cv.RATE_LIMIT_FREE_MEASURED_AT)
        self.assertGreater(cv.RATE_LIMIT_FREE_REQ_S, 0)

    def test_the_recommended_free_concurrency_is_below_the_measured_edge(self):
        """A clean arm at K is evidence for K, not for 2K."""
        self.assertLessEqual(cv.recommended_workers("free"), 32)


if __name__ == "__main__":
    unittest.main()
