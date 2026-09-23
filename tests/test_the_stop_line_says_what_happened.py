"""The reply watcher may not claim a stop it did not make.

OPERATOR DECISION 2026-09-23. `scripts/reply_watch_loop.py` printed

    REPLY heyreach ingested=3 - the lead is stopped on both channels

as a CONSTANT inside an f-string, on any non-zero ingest count, consulting
nothing. It said that about lead 204966 at 15:57:01Z while the stop had
raised `StopRefused: record is in no campaign` and the lead read
`in_sequence` at the provider for another half hour. It had said the same
thing once before, about Megan Ward.

A stop that never ran reporting as a stop is the worst available failure on
this path, because it is indistinguishable from the success.

What these pin:

    the line is DERIVED       `summarise_stops` builds it from the outcome
    three outcomes, not two   stopped / refused / no lead on that channel,
                              because "no lead" is the ordinary state of a
                              single-channel contact and must not read as a
                              failure
    a refusal ALERTS          and "no lead" does not, or the alert is buried
    both channels attempted   the email half was the only one ever called
                              from the reply path
"""
import unittest

from src import inbound, leadstop


def _outcome(email=None, linkedin=None, record="rec-1"):
    stops = {}
    if email is not None:
        stops["email"] = email
    if linkedin is not None:
        stops["linkedin"] = linkedin
    return {"applied": {"record_id": record}, "provider_stop": stops}


STOPPED = {"attempted": True, "stopped": True, "already": False,
           "status_after": "stopped"}
ALREADY = {"attempted": True, "stopped": True, "already": True,
           "status_after": "replied"}
NO_LEAD = {"attempted": False, "stopped": False,
           "why": "this contact carries no heyreach_lead_id"}
REFUSED = {"attempted": True, "stopped": False, "error": "StopRefused",
           "why": "record 'crosschannel-stop-test-2026-09-23' is in no "
                  "campaign, so there is no provider campaign to stop them in"}


class TestTheLineIsDerived(unittest.TestCase):

    def test_a_confirmed_stop_says_stopped(self):
        line, refusals = inbound.summarise_stops([_outcome(email=STOPPED)])
        self.assertIn("email: stopped", line)
        self.assertEqual(refusals, [])

    def test_an_already_stopped_lead_is_distinguished(self):
        """Already stopped is a success but not a write, and a reader who
        cannot tell them apart cannot tell a working stop from a no-op."""
        line, _ = inbound.summarise_stops([_outcome(email=ALREADY)])
        self.assertIn("email: already stopped", line)

    def test_no_lead_on_a_channel_says_so_and_is_not_a_failure(self):
        line, refusals = inbound.summarise_stops(
            [_outcome(email=STOPPED, linkedin=NO_LEAD)])
        self.assertIn("linkedin: no lead", line)
        self.assertEqual(refusals, [],
                         "a single-channel contact must not raise an alert")

    def test_the_2026_09_23_refusal_reads_as_a_refusal(self):
        """THE DEFECT, in one assertion. This exact outcome printed 'the lead
        is stopped on both channels'."""
        line, refusals = inbound.summarise_stops(
            [_outcome(email=REFUSED, linkedin=NO_LEAD)])
        self.assertIn("email: REFUSED", line)
        self.assertIn("is in no campaign", line)
        self.assertNotIn("stopped on both channels", line)
        self.assertEqual(len(refusals), 1)
        self.assertEqual(refusals[0]["channel"], "email")

    def test_a_refusal_carries_the_record_so_somebody_can_go_and_look(self):
        _, refusals = inbound.summarise_stops(
            [_outcome(email=REFUSED, record="productive-acme")])
        self.assertEqual(refusals[0]["record"], "productive-acme")
        self.assertIn("no campaign", refusals[0]["why"])

    def test_both_channels_refusing_raises_two(self):
        _, refusals = inbound.summarise_stops(
            [_outcome(email=REFUSED, linkedin=REFUSED)])
        self.assertEqual(len(refusals), 2)
        self.assertEqual({r["channel"] for r in refusals},
                         {"email", "linkedin"})

    def test_nothing_to_stop_is_stated_rather_than_implied(self):
        line, refusals = inbound.summarise_stops([_outcome()])
        self.assertEqual(line, "no provider binding to stop")
        self.assertEqual(refusals, [])

    def test_it_survives_the_shapes_a_watcher_actually_holds(self):
        for outcomes in ([], None, [{}], [{"provider_stop": None}],
                         [{"provider_stop": "not-a-dict"}]):
            with self.subTest(outcomes=outcomes):
                line, refusals = inbound.summarise_stops(outcomes)
                self.assertIsInstance(line, str)
                self.assertEqual(refusals, [])

    def test_channel_order_is_stable(self):
        """Two reads of the same event must be comparable by eye."""
        line, _ = inbound.summarise_stops(
            [_outcome(email=STOPPED, linkedin=NO_LEAD)])
        self.assertLess(line.index("email"), line.index("linkedin"))


class TestBothChannelsAreAttempted(unittest.TestCase):
    """The email half was the only one ever called from the reply path, while
    STOP_ROUTES has authorised the HeyReach route the whole time."""

    def test_the_stop_routes_cover_both_providers(self):
        self.assertIn("stop-future-emails", inbound.STOP_ROUTES)
        self.assertIn("stopleadincampaign", inbound.STOP_ROUTES)

    def test_a_contact_with_no_bindings_reports_both_channels(self):
        """Not one verdict for the contact - one per channel, so a reader can
        see which side was never staged."""
        result = inbound._stop_at_provider({"id": "r"}, {"key": "c"}, [])
        self.assertEqual(set(result), {"email", "linkedin"})
        for channel, entry in result.items():
            with self.subTest(channel=channel):
                self.assertFalse(entry["attempted"])
                self.assertFalse(entry["stopped"])
                self.assertIn("carries no", entry["why"])

    def test_a_missing_binding_names_the_field_that_is_missing(self):
        result = inbound._stop_at_provider({"id": "r"}, {"key": "c"}, [])
        self.assertIn("bison_lead_id", result["email"]["why"])
        self.assertIn("heyreach_lead_id", result["linkedin"]["why"])


class TestAnUnknownClassificationStillStops(unittest.TestCase):
    """OPERATOR REQUIREMENT 2026-09-23: "A reply of class unknown must still
    stop the other channel."

    The 17:54 test reply classified `unknown` - rules-3, confidence 0.0, "no
    rule matched and no classifier was available". If the stop were gated
    behind a positive or negative verdict, the whole cross-channel guarantee
    would rest on a classifier whose DEFAULT answer is `unknown`.

    Driven through `inbound.handle` rather than asserted against the source:
    a test that greps for the ordering passes the day somebody keeps the
    comment and moves the call.
    """

    def setUp(self):
        self.calls = []
        real = leadstop.stop_contact

        def recording(rec, contact, why, **kw):
            self.calls.append({"record": rec.get("id"),
                               "contact": contact.get("key"), "why": why})
            return {"stopped": True, "already": False,
                    "status_after": "stopped", "lead_id": 1,
                    "campaign": "c-1"}

        leadstop.stop_contact = recording
        self.addCleanup(setattr, leadstop, "stop_contact", real)

    def _record(self):
        return {"id": "rec-unknown", "client": "productive", "state": "queued",
                "domain": "example.test", "company": "Example",
                "contacts": [{"key": "ck-1", "email": "a@example.test",
                              "bison_lead_id": 1, "sendable": True}]}

    def test_a_reply_that_classifies_unknown_still_reaches_the_stop(self):
        rec = self._record()
        event = {"type": "reply_received", "provider": "emailbison",
                 "channel": "email", "email": "a@example.test",
                 "record_id": "rec-unknown", "at": "2026-09-23T15:54:54Z",
                 "provider_event_id": "test:unknown:1",
                 "text": "\u4f60\u597d"}
        outcome = inbound.handle(event, [rec])
        verdict = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(
            len(self.calls), 1,
            f"a reply classified {verdict!r} did not reach the stop at all")
        self.assertEqual(self.calls[0]["record"], "rec-unknown")
        stops = outcome.get("provider_stop") or {}
        self.assertTrue((stops.get("email") or {}).get("stopped"))


if __name__ == "__main__":
    unittest.main()
