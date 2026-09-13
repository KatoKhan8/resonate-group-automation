#!/usr/bin/env python3
"""A filter key HeyReach does not recognise is discarded in silence and the
whole inbox comes back - so a typo reads as an answer.

MEASURED, NOT FEARED. On 2026-09-13, against the client's live inbox of 26,039
conversations, through `heyreach.conversations`:

    {"nonsenseKeyNobodyDocuments": "x"}   -> 26039   dropped
    {"companyName": "Nineyards"}          -> 26039   dropped: not a filter
    {"searchString": "Brooke"}            ->    13   honoured
    {"leadProfileUrl": <a real profile>}  ->     1   honoured
    {"leadProfileUrl": <a candidate>}     ->     0   honoured, and empty
    {"linkedInAccountIds": [116968]}      ->  1261   honoured
    {"linkedInAccountIds": [999999999]}   ->     0   honoured, and empty
    {"campaignIds": [594061]}             ->     0   honoured, and empty

The unfiltered total is the control: a key that changes nothing returns it, and
a key that is honoured does not. The `999999999` rows are the second control -
without them "0" could mean the filter was rejected rather than applied.

WHY THAT IS A SAFETY PROBLEM AND NOT A CONVENIENCE ONE. `collision` reads this
route to decide whether one of the client's own seats has already written to
somebody. A misspelled key does not raise, does not warn and does not return
nothing - it returns the entire estate, which the local slug match then walks
without finding the person, and the verdict is CLEAR. That is the exact shape
of the false clear this repository has already had once on the email side.

So the transport allowlists the keys it has measured and raises on any other.
The prose describing this hazard was already in
`test_the_linkedin_lane_could_collide`; nothing enforced it.
"""
import json
import os
import unittest

from src import providers
from src.providers import heyreach


PAGE = {"items": [], "totalCount": 0}


class StubbedWire(unittest.TestCase):
    """A synthetic credential, so a refusal is about the filter and not the key.

    `headers()` reads the key at call time, which is what makes the guard's
    ordering testable: a key that never reaches the wire cannot have been
    checked against a credential either.
    """

    def setUp(self):
        previous = os.environ.get("HEYREACH_KEY")
        os.environ["HEYREACH_KEY"] = "synthetic-filter-test-key-000111"

        def restore():
            if previous is None:
                os.environ.pop("HEYREACH_KEY", None)
            else:
                os.environ["HEYREACH_KEY"] = previous

        self.addCleanup(restore)


class TheTransportRefusesAKeyItCannotVouchFor(StubbedWire):

    def wire(self):
        """Record what reaches the wire. Returns the list of request bodies."""
        sent = []

        def transport(method, url, headers, body, timeout):
            sent.append({"url": url, "body": body})
            return 200, json.dumps(PAGE)

        providers.set_transport(transport)
        self.addCleanup(providers.reset_transport)
        return sent

    def test_a_measured_key_reaches_the_provider(self):
        sent = self.wire()
        heyreach.conversations(0, 10, filters={"searchString": "Brooke"})
        self.assertEqual(sent[0]["body"]["filters"], {"searchString": "Brooke"})

    def test_every_allowlisted_key_is_accepted(self):
        sent = self.wire()
        for key in heyreach.INBOX_FILTER_KEYS:
            heyreach.conversations(0, 10, filters={key: "x"})
        self.assertEqual(len(sent), len(heyreach.INBOX_FILTER_KEYS))

    def test_an_unmeasured_key_never_reaches_the_wire(self):
        """The refusal has to happen BEFORE the request, or the 26,039 arrive
        and something downstream has already been handed them."""
        sent = self.wire()
        with self.assertRaises(providers.ProviderError):
            heyreach.conversations(0, 10, filters={"companyName": "Nineyards"})
        self.assertEqual(sent, [])

    def test_a_typo_in_a_real_key_is_refused_rather_than_ignored(self):
        sent = self.wire()
        with self.assertRaises(providers.ProviderError):
            heyreach.conversations(0, 10, filters={"searchStrings": "Brooke"})
        self.assertEqual(sent, [])

    def test_the_refusal_names_the_key_and_what_would_have_happened(self):
        # The wire is stubbed even though the guard should refuse before it.
        # Without this, breaking the guard makes this test reach the real
        # provider - which is how a red test stops being a question about the
        # system and becomes a live call nobody authorised.
        self.wire()
        with self.assertRaises(providers.ProviderError) as caught:
            heyreach.conversations(0, 10, filters={"companyName": "x"})
        message = str(caught.exception)
        self.assertIn("companyName", message)
        self.assertIn("whole inbox", message)

    def test_one_good_key_does_not_smuggle_a_bad_one(self):
        sent = self.wire()
        with self.assertRaises(providers.ProviderError):
            heyreach.conversations(
                0, 10, filters={"searchString": "Brooke", "companyName": "x"})
        self.assertEqual(sent, [])

    def test_no_filter_at_all_is_still_the_whole_inbox_and_is_allowed(self):
        """The poller reads unfiltered on purpose. This must not break it."""
        sent = self.wire()
        heyreach.conversations()
        self.assertEqual(sent[0]["body"]["filters"], {})


class TheCompanyQuestionStillCannotBeAsked(unittest.TestCase):
    """`companyName` is absent from the allowlist because it is not a filter,
    not because nobody got round to it.

    `collision.account_is_unanswerable` rests on this. If somebody ever adds
    `companyName` here on the strength of it appearing in a conversation
    payload, the company-level check becomes answerable-looking and answers 0
    for every company - which is the reading that module exists to refuse.
    """

    def test_company_name_is_not_an_allowlisted_filter(self):
        self.assertNotIn("companyName", heyreach.INBOX_FILTER_KEYS)

    def test_the_allowlist_is_exactly_what_was_measured(self):
        self.assertEqual(
            set(heyreach.INBOX_FILTER_KEYS),
            {"searchString", "leadProfileUrl", "linkedInAccountIds",
             "campaignIds"})


class AProfileTheProviderCannotResolveIsNotAnAbsence(StubbedWire):
    """A well-formed but unknown `leadProfileUrl` answers 400, not 0.

    Measured: `.../in/zzqq9notarealperson` returned 400 while
    `.../in/brookebaron` - a real profile with no conversation - returned 0.
    Those are different facts and `_read` keeps them apart by raising, so a
    caller cannot read "the provider refused" as "nobody has spoken to them".
    """

    def test_a_refusal_raises_rather_than_returning_an_empty_page(self):
        def transport(method, url, headers, body, timeout):
            return 400, json.dumps({"message": "invalid profile url"})

        providers.set_transport(transport)
        self.addCleanup(providers.reset_transport)
        with self.assertRaises(providers.ProviderError):
            heyreach.conversations(
                0, 10,
                filters={"leadProfileUrl": "https://www.linkedin.com/in/zzqq9"})


if __name__ == "__main__":
    unittest.main()
