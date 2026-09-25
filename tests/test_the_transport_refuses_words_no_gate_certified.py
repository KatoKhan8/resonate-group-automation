"""THE WIRING. A gate that lives in one function is a gate a script walks past.

On 2026-09-25 the push that sent 64 wrong emails called
`bison.create_lead` and `bison.attach_leads` directly. Every copy gate in
this repository lived inside `bisonfactory.stage`, so `_refuse_copylint`,
`_ensure_leads`, `_refuse_unsupported`, `_approved_copy` and the tenancy
check all ran zero times on those 690 leads.

These tests drive the REAL transport function - the one that opens the
socket - with `urlopen` booby-trapped, and prove three things:

  1. the incident's own payload is refused there, going through the
     provider module exactly as the scratch script did;
  2. the refusal lands BEFORE the socket;
  3. removing the guard lets the payload reach the socket, which is what
     makes 1 and 2 evidence rather than decoration.
"""
import unittest
import urllib.request

from src import copyprovenance as cp
from src import providers
from src.providers import bison, heyreach  # noqa: F401  (registers the hosts)


class SocketWasOpened(Exception):
    """The booby trap. Reaching this means the guards let the call through."""


CONFIG = {"cadence": "productive_li_heavy_v1", "name": "productive"}
GOOD_ID = "productive:productive_li_heavy_v1:em1"

#: The incident payload, in the shape `bison.create_lead` posts it.
SHIPPED_BODY = (
    "Hi Rhett, I was reading the Northwind site this week and the line "
    "about please allow me to introduce myself is what made me write.\n\n"
    "I work with agency founders who want a second source of new "
    "business.\n\nWorth a short call next week?\n\nZvonimir")

CLEAN_BODY = (
    "Scott, your site says margin is known at the end of the month.\n\n"
    "The pattern in teams your size is that the numbers arrive too late to "
    "act on.\n\nIs that roughly how it works at your end today?")


def lead_payload(body, extra=None):
    variables = {"subject_1": "quick question", "body_1": body}
    variables.update(extra or {})
    return {"email": "someone@example.test", "first_name": "Rhett",
            "custom_variables": [{"name": k, "value": v}
                                 for k, v in sorted(variables.items())]}


class TheTransportIsTheLastLine(unittest.TestCase):

    def setUp(self):
        # Booby-trap the socket itself, in the module the transport calls.
        # A test that reached a real provider would be a test that staged a
        # lead on a client's estate.
        self._urlopen = urllib.request.urlopen

        def trap(*_a, **_kw):
            raise SocketWasOpened("a real request was about to be made")

        urllib.request.urlopen = trap
        self.addCleanup(setattr, urllib.request, "urlopen", self._urlopen)
        # The transport must be the real one: swapping it for a cassette is
        # exactly the case this test must not accidentally measure.
        providers.reset_transport()

    def _post(self, body, url="https://send.resonategroup.co/api/leads"):
        return providers._urllib_transport(
            "POST", url, {"Authorization": "Bearer x"}, body, 5)

    def assertReachedTheSocket(self, call):
        """The trap fired. `_urllib_transport` wraps anything the socket
        raises in `HttpTransportError`, so the sentinel arrives by name
        rather than by class - which is itself worth asserting, because a
        guard that raised inside the try block would look identical if the
        name were not checked."""
        with self.assertRaises(providers.HttpTransportError) as caught:
            call()
        self.assertIn("SocketWasOpened", str(caught.exception))

    def test_the_incident_payload_is_refused_at_the_wire(self):
        with providers.allow_writes("test: the write is authorized, the "
                                    "words are not"):
            with self.assertRaises(providers.UncertifiedCopyRefused):
                self._post(lead_payload(SHIPPED_BODY))

    def test_the_refusal_lands_before_the_socket(self):
        # If the guard ran after the request was built, this would raise
        # SocketWasOpened instead.
        with providers.allow_writes("test"):
            try:
                self._post(lead_payload(SHIPPED_BODY))
            except providers.UncertifiedCopyRefused:
                pass
            except providers.HttpTransportError as e:
                self.fail("the socket was opened before the copy was "
                          "vetted: %s" % e)

    def test_removing_the_guard_lets_the_incident_payload_reach_the_socket(self):
        # THE PROOF THAT THE TWO TESTS ABOVE ARE NOT VACUOUS. With the guard
        # neutered the same payload goes all the way to `urlopen`.
        original = providers.refuse_uncertified_copy
        providers.refuse_uncertified_copy = lambda *_a, **_kw: None
        self.addCleanup(setattr, providers, "refuse_uncertified_copy", original)
        with providers.allow_writes("test"):
            self.assertReachedTheSocket(
                lambda: self._post(lead_payload(SHIPPED_BODY)))

    def test_certified_copy_is_let_through_to_the_socket(self):
        values = cp.certify([(1, GOOD_ID, "quick question", CLEAN_BODY)],
                            client="productive", owner_name="Bernarda Vrbat",
                            config=CONFIG)
        payload = lead_payload(CLEAN_BODY, extra=values)
        with providers.allow_writes("test"):
            self.assertReachedTheSocket(lambda: self._post(payload))

    def test_one_word_changed_after_certification_is_refused_again(self):
        values = cp.certify([(1, GOOD_ID, "quick question", CLEAN_BODY)],
                            client="productive", owner_name="Bernarda Vrbat",
                            config=CONFIG)
        payload = lead_payload(CLEAN_BODY + "\n\nZvonimir", extra=values)
        with providers.allow_writes("test"):
            with self.assertRaises(providers.UncertifiedCopyRefused):
                self._post(payload)

    def test_an_unauthorized_write_is_still_refused_as_unauthorized(self):
        # Order matters: the ledger row has to name the real problem.
        with self.assertRaises(providers.ProviderWriteRefused) as caught:
            self._post(lead_payload(SHIPPED_BODY))
        self.assertNotIsInstance(caught.exception,
                                 providers.UncertifiedCopyRefused)


class WhatTheGateDoesNotRefuse(unittest.TestCase):
    """A gate that refuses legitimate traffic gets switched off."""

    def test_a_sequence_of_merge_fields_carries_no_copy(self):
        body = {"title": "seq", "sequence_steps": [
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "Re: {SUBJECT_1}", "email_body": "<p>{BODY_2}</p>"}]}
        carries, _variables = providers.copy_in_payload(body)
        self.assertFalse(carries)

    def test_attaching_leads_carries_no_copy(self):
        carries, _v = providers.copy_in_payload({"lead_ids": [1, 2, 3]})
        self.assertFalse(carries)

    def test_a_read_is_never_refused(self):
        providers.refuse_uncertified_copy(
            "GET", "https://send.resonategroup.co/api/leads",
            lead_payload(SHIPPED_BODY))

    def test_an_unguarded_host_is_never_refused(self):
        providers.refuse_uncertified_copy(
            "POST", "https://api.example-enrichment.test/v1/people",
            lead_payload(SHIPPED_BODY))


class BothProspectFacingHostsAreCovered(unittest.TestCase):
    """`heyreachfactory.stage` was left uncovered by the last wiring and the
    doc said so, which is the only reason anybody knew. This asserts the
    coverage rather than documenting it."""

    def test_the_email_host_is_guarded(self):
        self.assertTrue(providers.is_prospect_facing(bison.base()))

    def test_the_linkedin_host_is_guarded(self):
        self.assertTrue(providers.is_prospect_facing(heyreach.BASE))

    def test_a_linkedin_message_with_uncertified_words_is_refused(self):
        body = {"leads": [{"firstName": "Rhett", "message": SHIPPED_BODY}]}
        with self.assertRaises(providers.UncertifiedCopyRefused):
            providers.refuse_uncertified_copy(
                "POST", heyreach.BASE + "/campaign/AddLeadsToCampaignV2", body)


if __name__ == "__main__":
    unittest.main()
