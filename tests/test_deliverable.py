"""Deliverable: a documented request, an undocumented answer.

The provider's API page gives the endpoints, the method and the auth header, so
those are no longer guesses and the adapter carries them. It gives nothing about
the response, so the tests that matter here are the refusal that stops a credit
being spent on an answer this code may not be able to read, the asynchronous
submit-then-collect flow, and the normaliser that makes the eventual answer a
configuration detail rather than a rewrite.
"""
import json
import unittest

from src import verification
from src.providers import deliverable
from tests.base import ProviderTest


class Wire:
    """A transport that answers from a script and remembers what it was asked."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "body": body})
        status, payload = self.replies[min(len(self.calls) - 1,
                                           len(self.replies) - 1)]
        return status, json.dumps(payload)

    def urls(self):
        return [c["url"] for c in self.calls]


class TestWhatIsDocumentedIsUsed(ProviderTest):
    def test_the_endpoints_and_auth_come_from_the_documentation(self):
        current = deliverable.settings()
        self.assertEqual(current["base"], "https://api.deliverable.co/gateway")
        self.assertEqual(current["path"], "/verify/single")
        self.assertEqual(current["status_path"], "/verify/single/status")
        self.assertEqual(current["method"], "POST")
        self.assertEqual(current["auth"], "header")
        self.assertEqual(deliverable.HEADER_NAME, "x-api-key")

    def test_the_request_half_needs_nothing_further(self):
        self.assertEqual(deliverable.transport_gaps(), [])

    def test_a_request_can_therefore_be_built_without_being_sent(self):
        plan = deliverable.build_request("someone@example.test")
        self.assertEqual(plan["method"], "POST")
        self.assertEqual(plan["url"],
                         "https://api.deliverable.co/gateway/verify/single")
        self.assertEqual(plan["body"], {"email": "someone@example.test"})
        self.assertEqual(plan["headers"]["x-api-key"], "test-key-not-real")
        self.assertEqual(self.cassette.calls, [])

    def test_the_collecting_call_is_built_too(self):
        plan = deliverable.build_status_request("t-1")
        self.assertEqual(plan["method"], "POST")
        self.assertTrue(plan["url"].endswith("/verify/single/status"))
        self.assertEqual(plan["body"], {"task_id": "t-1"})

    def test_an_override_still_wins_over_the_default(self):
        deliverable.configure(base="https://elsewhere.test/v9")
        self.assertIn("https://elsewhere.test/v9/verify/single",
                      deliverable.build_request("a@b.test")["url"])

    def test_each_auth_style_puts_the_key_where_it_belongs(self):
        deliverable.configure(auth="header")
        self.assertIn("x-api-key", deliverable.build_request("a@b.test")["headers"])

        deliverable.configure(auth="bearer")
        plan = deliverable.build_request("a@b.test")
        self.assertTrue(plan["headers"]["Authorization"].startswith("Bearer "))

        deliverable.configure(auth="query")
        plan = deliverable.build_request("a@b.test")
        self.assertIn("api_key=", plan["url"])
        self.assertEqual(plan["headers"], {})

    def test_a_get_contract_would_carry_the_address_in_the_query(self):
        deliverable.configure(method="GET")
        plan = deliverable.build_request("someone@example.test")
        self.assertEqual(plan["method"], "GET")
        self.assertIn("email=someone%40example.test", plan["url"])
        self.assertIsNone(plan["body"])

    def test_the_key_is_redacted_when_a_url_is_shown(self):
        deliverable.configure(auth="query")
        plan = deliverable.build_request("a@b.test")
        self.assertNotIn("test-key-not-real", self.providers.redact(plan["url"]))


class TestTheAnswerIsNotGuessed(ProviderTest):
    def test_the_response_shape_is_the_one_remaining_gap(self):
        self.assertFalse(deliverable.contract_verified())
        gaps = deliverable.contract_gaps()
        self.assertEqual(len(gaps), 1)
        self.assertIn("DELIVERABLE_RESULT_SHAPE", gaps[0])

    def test_it_refuses_to_verify_until_a_real_answer_has_been_read(self):
        with self.assertRaises(deliverable.ContractNotVerified):
            deliverable.verify("someone@example.test")
        self.assertEqual(self.cassette.calls, [])

    def test_the_refusal_happens_before_anything_is_submitted(self):
        wire = Wire((200, {"task_id": "t-1"}))
        self.providers.set_transport(wire)
        with self.assertRaises(deliverable.ContractNotVerified):
            deliverable.verify("someone@example.test")
        self.assertEqual(wire.calls, [])

    def test_the_refusal_names_the_command_that_would_lift_it(self):
        with self.assertRaises(deliverable.ContractNotVerified) as e:
            deliverable.verify("someone@example.test")
        self.assertIn("src.validate", str(e.exception))
        self.assertIn("DELIVERABLE_RESULT_SHAPE", str(e.exception))

    def test_a_broken_request_contract_refuses_even_harder(self):
        deliverable.configure(auth="telepathy")
        self.assertTrue(deliverable.transport_gaps())
        with self.assertRaises(deliverable.ContractNotVerified):
            deliverable.build_request("someone@example.test")

    def test_the_health_check_skips_rather_than_calling(self):
        result = deliverable.check()
        self.assertTrue(result["skipped"])
        self.assertIn("no account or quota endpoint", result["note"])
        self.assertEqual(self.cassette.calls, [])

    def test_the_health_check_never_verifies_an_address_to_look_green(self):
        wire = Wire((200, {"status": "valid"}))
        self.providers.set_transport(wire)
        deliverable.check()
        self.assertEqual(wire.calls, [])

    def test_a_missing_key_is_reported_before_the_contract(self):
        self.clear_keys()
        result = deliverable.check()
        self.assertFalse(result["ok"])
        self.assertIn("DELIVERABLE_KEY", result["note"])


class TestTheAsynchronousFlow(ProviderTest):
    """Submit, then collect. The documentation is explicit that it is two calls."""

    def setUp(self):
        super().setUp()
        self.confirm_deliverable_contract()

    def wire(self, *replies):
        w = Wire(*replies)
        self.providers.set_transport(w)
        return w

    def test_it_submits_then_collects(self):
        wire = self.wire((200, {"task_id": "t-7"}), (200, {"status": "valid"}))
        entry = deliverable.verify("someone@example.test", sleep=lambda s: None)
        self.assertEqual(entry["status"], "valid")
        self.assertEqual(len(wire.calls), 2)
        self.assertTrue(wire.urls()[0].endswith("/verify/single"))
        self.assertTrue(wire.urls()[1].endswith("/verify/single/status"))

    def test_the_task_id_is_carried_into_the_poll(self):
        wire = self.wire((200, {"task_id": "t-7"}), (200, {"status": "valid"}))
        deliverable.verify("a@b.test", sleep=lambda s: None)
        self.assertEqual(wire.calls[1]["body"], {"task_id": "t-7"})

    def test_the_key_travels_on_both_calls(self):
        wire = self.wire((200, {"task_id": "t-7"}), (200, {"status": "valid"}))
        deliverable.verify("a@b.test", sleep=lambda s: None)
        for call in wire.calls:
            self.assertEqual(call["headers"]["x-api-key"], "test-key-not-real")

    def test_a_pending_answer_is_polled_again(self):
        wire = self.wire((200, {"task_id": "t-7"}),
                         (200, {"status": "processing"}),
                         (200, {"status": "processing"}),
                         (200, {"status": "valid"}))
        slept = []
        entry = deliverable.verify("a@b.test", sleep=slept.append)
        self.assertEqual(entry["status"], "valid")
        self.assertEqual(len(wire.calls), 4)
        self.assertEqual(len(slept), 2)

    def test_a_provider_that_never_settles_is_unknown_not_valid(self):
        wire = self.wire((200, {"task_id": "t-7"}), (200, {"status": "pending"}))
        entry = deliverable.verify("a@b.test", attempts=3, sleep=lambda s: None)
        self.assertEqual(entry["status"], "unknown")
        self.assertEqual(len(wire.calls), 4)          # one submit, three polls

    def test_the_task_id_is_read_under_any_spelling(self):
        for payload in ({"task_id": "a"}, {"taskId": "a"}, {"id": "a"},
                        {"data": {"task_id": "a"}}):
            self.assertEqual(deliverable.task_id(payload), "a", payload)

    def test_an_inline_answer_is_accepted_without_a_poll(self):
        wire = self.wire((200, {"status": "valid", "email": "a@b.test"}))
        entry = deliverable.verify("a@b.test", sleep=lambda s: None)
        self.assertEqual(entry["status"], "valid")
        self.assertEqual(len(wire.calls), 1)

    def test_a_response_with_neither_a_handle_nor_an_answer_is_an_error(self):
        self.wire((200, {"message": "thanks"}))
        with self.assertRaises(deliverable.ProviderError):
            deliverable.verify("a@b.test", sleep=lambda s: None)

    def test_a_rejected_submit_raises_rather_than_returning_valid(self):
        self.wire((401, {"error": "unauthorised"}))
        with self.assertRaises(deliverable.ProviderError):
            deliverable.verify("a@b.test", sleep=lambda s: None)

    def test_a_rejected_poll_raises_too(self):
        self.wire((200, {"task_id": "t-7"}), (500, {"error": "boom"}))
        with self.assertRaises(deliverable.ProviderError):
            deliverable.verify("a@b.test", sleep=lambda s: None)

    def test_pending_is_only_pending_never_an_answer(self):
        for label in ("pending", "processing", "queued", "in progress", "running"):
            self.assertTrue(deliverable.pending({"status": label}), label)
        for label in ("valid", "invalid", "catch_all", "unknown"):
            self.assertFalse(deliverable.pending({"status": label}), label)


class TestTheValidationHarnessIsTheOnlyExemption(ProviderTest):
    def test_it_may_read_one_answer_with_the_shape_still_unread(self):
        wire = Wire((200, {"task_id": "t-7"}), (200, {"status": "valid"}))
        self.providers.set_transport(wire)
        entry = deliverable.verify("a@b.test", sleep=lambda s: None,
                                   unread_contract=True)
        self.assertEqual(entry["status"], "valid")

    def test_the_exemption_still_needs_a_complete_request_contract(self):
        deliverable.configure(auth="telepathy")
        with self.assertRaises(deliverable.ContractNotVerified):
            deliverable.verify("a@b.test", unread_contract=True)

    def test_the_waterfall_itself_does_not_take_the_exemption(self):
        import inspect
        source = inspect.getsource(verification)
        self.assertNotIn("unread_contract", source)


class TestNormalisation(unittest.TestCase):
    """The real payload is unknown, so the normaliser reads what verifiers use."""

    def norm(self, payload):
        return deliverable.normalise(payload, "someone@example.test")

    def test_the_output_is_the_projects_own_model(self):
        entry = self.norm({"status": "valid"})
        self.assertEqual(entry["provider"], "deliverable")
        for field in ("status", "email", "deliverable", "safe_to_send",
                      "catch_all", "disposable", "role_account", "score",
                      "reason", "at"):
            self.assertIn(field, entry)

    def test_a_valid_answer_in_any_of_its_spellings(self):
        # `{"state": "ok"}` was here and is deliberately gone; see
        # `AnAcknowledgementIsNotAVerdict`. A boolean field is a different
        # matter and stays: `deliverable: true` and `is_valid: true` are
        # statements about the mailbox whatever the envelope says.
        for payload in ({"status": "valid"}, {"result": "deliverable"},
                        {"deliverable": True}, {"is_valid": True},
                        {"state": "verified"}):
            self.assertEqual(self.norm(payload)["status"], "valid", payload)

    def test_a_transport_ok_is_not_a_valid_answer(self):
        """The other half of the line above."""
        self.assertEqual(self.norm({"state": "ok"})["status"], "unknown")
        self.assertEqual(self.norm({"status": "ok"})["status"], "unknown")

    def test_an_invalid_answer_in_any_of_its_spellings(self):
        for payload in ({"status": "invalid"}, {"result": "undeliverable"},
                        {"deliverable": False}, {"state": "bounced"}):
            self.assertEqual(self.norm(payload)["status"], "invalid", payload)

    def test_a_catch_all_answer(self):
        for payload in ({"status": "catch_all"}, {"catch_all": True},
                        {"is_catch_all": True}, {"result": "accept_all"}):
            self.assertEqual(self.norm(payload)["status"], "accept_all", payload)

    def test_disposable_beats_everything_else(self):
        entry = self.norm({"status": "valid", "disposable": True})
        self.assertEqual(entry["status"], "disposable")

    def test_an_unrecognised_answer_is_unknown_never_valid(self):
        for payload in ({}, {"status": "who knows"}, {"result": "risky"},
                        {"status": None}):
            self.assertEqual(self.norm(payload)["status"], "unknown", payload)

    def test_an_envelope_is_unwrapped(self):
        self.assertEqual(self.norm({"data": {"status": "valid"}})["status"], "valid")
        self.assertEqual(self.norm({"result": {"status": "valid"}})["status"],
                         "valid")

    def test_a_string_boolean_is_read_as_a_boolean(self):
        self.assertIs(self.norm({"catch_all": "true"})["catch_all"], True)
        self.assertIs(self.norm({"disposable": "no"})["disposable"], False)

    def test_a_score_is_kept_only_when_numeric(self):
        self.assertEqual(self.norm({"score": 87})["score"], 87)
        self.assertIsNone(self.norm({"score": "high"})["score"])

    def test_nothing_raw_survives_normalisation(self):
        entry = self.norm({"status": "valid", "raw_smtp": "250 OK transcript",
                           "debug": {"trace": "x" * 500}})
        self.assertNotIn("raw_smtp", entry)
        self.assertNotIn("debug", entry)

    def test_fields_the_normaliser_ignores_are_reported_for_review(self):
        unmapped = deliverable.unmapped_fields({"status": "valid",
                                                "mystery_field": 1,
                                                "another": 2})
        self.assertEqual(unmapped, ["another", "mystery_field"])

    def test_the_asynchronous_plumbing_is_not_reported_as_unmapped(self):
        self.assertEqual(deliverable.unmapped_fields({"task_id": "t-1",
                                                      "status": "valid"}), [])

    def test_a_normalised_result_feeds_the_resolver_directly(self):
        entry = self.norm({"status": "valid"})
        decision = verification.decide([entry])
        self.assertEqual(decision["state"], verification.HELD)  # no primary yet

        with_primary = verification.decide(
            [verification.result("contactout", "valid"), entry])
        self.assertTrue(with_primary["sendable"])


class TestItCannotBypassTheResolver(ProviderTest):
    def test_the_module_never_writes_sendable(self):
        import inspect
        import re
        source = inspect.getsource(deliverable)
        self.assertIsNone(re.search(r"\[[\"']sendable[\"']\]\s*=", source))

    def test_a_deliverable_valid_alone_does_not_clear_a_catch_all(self):
        evidence = [verification.result("contactout", "accept_all", catch_all=True),
                    deliverable.normalise({"status": "valid"}, "a@b.test")]
        self.assertFalse(verification.decide(evidence)["sendable"])

    def test_it_is_the_secondary_not_the_primary(self):
        self.assertEqual(verification.DEFAULT_POLICY["secondary"], "deliverable")
        self.assertEqual(verification.DEFAULT_POLICY["primary"], "contactout")


class AVerdictIsMatchedOnWholeWords(unittest.TestCase):
    """The defect this file did not have a test for.

    `classify` matched its vocabulary with `word in label`, so any answer
    whose text merely *contained* a positive word was read as one:

        not_deliverable  contains  deliverable
        token_expired    contains  ok
        revoked          contains  ok
        broken           contains  ok
        not ok           contains  ok

    Every one of those is an error, and a `valid` from this provider is one
    of the two independent vendor confirmations that make an address
    sendable. Nothing reached it - `require_contract` refuses every call
    until `DELIVERABLE_RESULT_SHAPE` is set, and nobody has set it - but
    `HUMAN-ACTIONS-REQUIRED.md` asks a person to set exactly that, so it
    was one authorised action from arming.
    """

    def kind(self, status):
        return deliverable.classify({"status": status})

    def test_a_word_that_merely_contains_a_positive_word_is_not_positive(self):
        for status in ("not_deliverable", "token_expired", "revoked",
                       "broken", "not ok", "non-deliverable", "not valid"):
            with self.subTest(status=status):
                self.assertNotEqual(self.kind(status), "valid")

    def test_the_words_that_really_are_positive_still_are(self):
        """"ok" and "good" used to be on this list and are not any more.

        They were a guess. Nobody has read a real Deliverable response -
        `require_contract` refuses every call until somebody sets
        `DELIVERABLE_RESULT_SHAPE`, and `HUMAN-ACTIONS-REQUIRED.md` asks a
        person to do exactly that - so this vocabulary was written from
        what a verifier might plausibly say. "ok" is what an API says
        about a request, and `classify` reads the *unwrapped* body, so a
        transport status sitting at the top level of an unrecognised
        envelope was being read as a verdict about a mailbox.

        Removing them makes classification stricter: those bodies now
        answer `unknown`, which holds the address. Dropping a real vendor
        whose positive word is "ok" costs a hold; keeping it cost one of
        the two confirmations that make an address sendable.
        """
        for status in ("valid", "deliverable", "safe", "verified"):
            with self.subTest(status=status):
                self.assertEqual(self.kind(status), "valid")

    def test_a_negated_label_is_never_valid(self):
        """"not deliverable" is two words and passes the whole-word test on
        its second one. The negation is what settles it."""
        for status in ("not deliverable", "not_valid", "no ok", "never valid"):
            with self.subTest(status=status):
                self.assertEqual(self.kind(status), "unknown")

    def test_a_negated_label_is_not_promoted_to_invalid_either(self):
        """Unknown holds the address and asks. Reading "not deliverable" as
        a definite invalid would be a different guess about a sentence
        this provider has never been seen to send."""
        self.assertEqual(self.kind("not deliverable"), "unknown")

    def test_the_refusals_still_refuse(self):
        self.assertEqual(self.kind("invalid"), "invalid")
        self.assertEqual(self.kind("undeliverable"), "invalid")
        self.assertEqual(self.kind("disposable"), "disposable")
        self.assertEqual(self.kind("catch_all"), "accept_all")

    def test_pending_is_matched_the_same_way(self):
        """It shares the vocabulary and shared the bug."""
        self.assertTrue(deliverable.pending({"status": "pending"}))
        self.assertFalse(deliverable.pending({"status": "not_pending"}))


class AnAcknowledgementIsNotAVerdict(unittest.TestCase):
    """"ok" is what an API says about the request, not about the mailbox.

    `classify` reads its vocabulary off the *unwrapped* body, and `unwrap`
    descends only into `data` or `result`. Any other envelope therefore
    leaves the transport status at the top level - and "ok" was a positive
    word, so `{"status": "ok"}` classified as `valid`.

    That is not a near miss. A `valid` here is one of the two independent
    vendor confirmations that make an address sendable, so a poll that
    caught a task before it settled, or a submit acknowledgement with no
    task id, could supply the second one. `words_of` already records that
    "ok" carried the previous instance of this bug: the substring matching
    was fixed and the word was left in the list.

    Losing a real vendor whose positive word is "ok" costs an `unknown`,
    which holds the address and asks a person. Keeping it cost a false
    confirmation. That asymmetry is the whole argument.
    """

    def kind(self, body):
        return deliverable.classify(body)

    def test_a_transport_acknowledgement_is_not_valid(self):
        for body in ({"status": "ok"}, {"status": "OK"}, {"state": "ok"},
                     {"status": "good"},
                     {"status": "ok", "message": "accepted"}):
            with self.subTest(body=body):
                self.assertNotEqual(self.kind(body), "valid")

    def test_a_deliverability_verdict_still_is(self):
        for word in ("valid", "deliverable", "safe", "verified"):
            with self.subTest(word=word):
                self.assertEqual(self.kind({"status": word}), "valid")

    def test_an_unsettled_task_under_an_ok_envelope_is_not_a_verdict(self):
        """The reachable shape. `collect` returns the body as soon as
        `pending` is false, and `pending` never looked inside the
        envelope."""
        body = {"status": "ok", "task": {"state": "processing"}}
        self.assertNotEqual(self.kind(body), "valid")

    def test_the_words_that_refuse_are_untouched(self):
        self.assertEqual(self.kind({"status": "invalid"}), "invalid")
        self.assertEqual(self.kind({"status": "undeliverable"}), "invalid")


if __name__ == "__main__":
    unittest.main()
