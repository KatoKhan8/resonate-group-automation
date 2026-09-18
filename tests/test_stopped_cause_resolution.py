"""Why did these 33 accounts stop? Evidence, not assumption.

TASK-232. 33 accounts are on HOLD because a campaign at each ended with
status `stopped` and nobody asked WHY. `collision.account_policy` sees
`stopped` in `SUSPECT_STATUSES`, cannot tell the cause, and holds. That is
the right default and it is not an answer.

This suite tests `stoppedcause.resolve`, which classifies the cause from
evidence that already exists: the events feed, the reply feed, the lead's
own counters, the campaign state, and our own action ledger.

THE REQUIREMENT THAT OUTRANKS THE FEATURE:

    STILL_UNKNOWN keeps the HOLD.

A HOLD that becomes CLEAR because nobody could find evidence of a refusal
is precisely the failure the gate exists to prevent: missing evidence is
never positive evidence. The task is only worth doing if the UNKNOWN branch
is honest.

So the most important test in this file is not one of the six positive
classifications - it is the one that asserts STILL_UNKNOWN explicitly when
no evidence exists, and the break-proof test that makes the evidence lookup
return nothing for every account and confirms ALL of them report
STILL_UNKNOWN rather than CLEAR.
"""
import unittest

from src import stoppedcause


# --------------------------------------------------------------- fixtures

def _person(lead_id=101, campaign_id=200, status="stopped", replies=0,
            lead_status="active", interested=False, campaign_status="stopped"):
    """A `collision.touches_of` dict for one person with one campaign."""
    return {
        "email": "test@example.com",
        "lead_id": lead_id,
        "lead_status": lead_status,
        "emails_sent": 3,
        "replies": replies,
        "opens": 1,
        "campaigns": [{
            "campaign_id": campaign_id,
            "status": campaign_status,
            "emails_sent": 3,
            "replies": replies,
            "opens": 1,
            "interested": interested,
        }],
        "in_sequence": False,
        "unknown_statuses": [],
        "created_at": "2026-01-01T00:00:00Z",
    }


def _event(kind, lead_id=101, campaign_id=200, occurred_at="2026-06-15T10:00:00Z",
           provider_event_type=None):
    """A normalised event dict, as `bisonevents.normalise` would produce."""
    return {
        "kind": kind,
        "lead_id": lead_id,
        "campaign_id": campaign_id,
        "occurred_at": occurred_at,
        "provider_event_type": provider_event_type or kind.upper(),
        "provider_event_id": f"evt-{kind}-{lead_id}",
        "workspace_id": 10,
        "email": "test@example.com",
    }


def _ledger_row(key="email:rec1:contact1:step1", campaign_id=200,
                lead_id=101, operation="bison.stop_lead", state="sent"):
    """An action ledger row for a stop_lead operation."""
    return {
        "key": key,
        "campaign_id": campaign_id,
        "contact_key": str(lead_id),
        "lead_id": lead_id,
        "operation": operation,
        "state": state,
        "at": "2026-06-10T10:00:00Z",
        "channel": "email",
        "workspace": "productive",
    }


# --------------------------------------------------------- positive cases

class UnsubscribedTest(unittest.TestCase):
    """An unsubscribe event resolves to UNSUBSCRIBED."""

    def test_unsubscribe_event_classifies_as_unsubscribed(self):
        person = _person()
        events = [_event("unsubscribed")]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events)
        self.assertEqual(result["outcome"], stoppedcause.UNSUBSCRIBED)
        self.assertIn("UNSUBSCRIBED", result["evidence"])


class RepliedInterestedTest(unittest.TestCase):
    """A reply event or membership signal resolves to REPLIED_INTERESTED."""

    def test_reply_event_classifies_as_replied(self):
        person = _person()
        events = [_event("replied")]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events)
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)
        self.assertIn("REPLIED", result["evidence"])

    def test_membership_replies_counter_classifies_as_replied(self):
        person = _person(replies=2)
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)
        self.assertIn("replies > 0", result["evidence"])

    def test_membership_status_replied_classifies_as_replied(self):
        person = _person(campaign_status="replied")
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)

    def test_interested_flag_classifies_as_replied(self):
        person = _person(interested=True)
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)


class BouncedTest(unittest.TestCase):
    """A bounce event or lead status resolves to BOUNCED."""

    def test_bounce_event_classifies_as_bounced(self):
        person = _person()
        events = [_event("bounced")]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events)
        self.assertEqual(result["outcome"], stoppedcause.BOUNCED)
        self.assertIn("BOUNCED", result["evidence"])

    def test_lead_status_bounced_classifies_as_bounced(self):
        person = _person(lead_status="bounced")
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.BOUNCED)
        self.assertIn("bounced", result["evidence"])


class WeStoppedItTest(unittest.TestCase):
    """Our own action ledger records a stop_lead -> WE_STOPPED_IT."""

    def test_ledger_stop_classifies_as_we_stopped_it(self):
        person = _person()
        ledger = [_ledger_row(campaign_id=200, lead_id=101)]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=ledger)
        self.assertEqual(result["outcome"], stoppedcause.WE_STOPPED_IT)
        self.assertIn("action ledger", result["evidence"])

    def test_ledger_stop_must_be_settled_sent_or_attempted(self):
        """A failed or abandoned stop is not evidence we stopped them."""
        person = _person()
        for state in ("failed", "abandoned", "unresolved"):
            ledger = [_ledger_row(campaign_id=200, lead_id=101, state=state)]
            result = stoppedcause.resolve(person, campaign_id=200,
                                          events_fetch=lambda **kw: [],
                                          ledger_rows=ledger)
            # Not WE_STOPPED_IT - should fall through to STILL_UNKNOWN
            self.assertNotEqual(result["outcome"], stoppedcause.WE_STOPPED_IT,
                                f"state={state} should not classify as WE_STOPPED_IT")


class SequenceFinishedTest(unittest.TestCase):
    """Campaign finished, no adverse signal -> SEQUENCE_FINISHED."""

    def test_sequence_finished_classifies_correctly(self):
        person = _person(campaign_status="sequence_finished")
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.SEQUENCE_FINISHED)
        self.assertIn("sequence_finished", result["evidence"])


# --------------------------------------------------------- the critical case

class StillUnknownTest(unittest.TestCase):
    """STILL_UNKNOWN keeps the HOLD. This is the requirement that outranks
    the feature.

    A `stopped` membership with NO corroborating evidence must come back
    STILL_UNKNOWN, not CLEAR. Missing evidence is never positive evidence.
    """

    def test_stopped_with_no_evidence_is_still_unknown(self):
        """The whole point: a stopped membership, no events, no ledger, no
        reply, no bounce, no finished sequence -> STILL_UNKNOWN."""
        person = _person()
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)
        self.assertIn("missing evidence", result["evidence"])

    def test_still_unknown_is_explicit_not_default(self):
        """The UNKNOWN branch must be an explicit arm, not a fall-through.
        If the code were restructured so that the default outcome were
        something else, this test would catch it."""
        person = _person()
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        # Assert the outcome is STILL_UNKNOWN specifically, not just "not CLEAR"
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)
        # And the evidence must say WHY it is unknown
        self.assertIsNotNone(result["evidence"])
        self.assertIn("missing evidence", result["evidence"])

    def test_no_lead_id_is_still_unknown(self):
        """A person with no lead_id cannot be resolved."""
        person = _person(lead_id=None)
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)

    def test_no_campaign_id_is_still_unknown(self):
        """A membership with no campaign_id cannot be resolved."""
        person = _person()
        result = stoppedcause.resolve(person, campaign_id=None,
                                      events_fetch=lambda **kw: [])
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)


# --------------------------------------------------------- break-proof test

class BreakProofTest(unittest.TestCase):
    """Make the evidence lookup return nothing for every account and confirm
    ALL of them report STILL_UNKNOWN rather than CLEAR.

    This is the test that prevents the failure mode the gate exists to
    prevent: a HOLD that becomes CLEAR because nobody could find evidence
    of a refusal.
    """

    def test_thirty_three_accounts_with_no_evidence_all_still_unknown(self):
        """Simulate 33 accounts, each with a stopped membership, each with
        NO evidence from any source. Every single one must report
        STILL_UNKNOWN, not CLEAR."""
        # 33 accounts, each with one person with one stopped membership
        accounts = []
        for i in range(33):
            person = _person(lead_id=1000 + i, campaign_id=2000 + i)
            accounts.append(person)

        # Evidence fetch returns nothing for every account
        def empty_fetch(**kw):
            return []

        results = []
        for person in accounts:
            result = stoppedcause.resolve(person, campaign_id=person["campaigns"][0]["campaign_id"],
                                          events_fetch=empty_fetch,
                                          ledger_rows=[])
            results.append(result)

        # EVERY ONE must be STILL_UNKNOWN
        for i, result in enumerate(results):
            self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN,
                             f"account {i} (lead={result['lead_id']}) "
                             f"should be STILL_UNKNOWN, got {result['outcome']}")

        # And the split must show 33 STILL_UNKNOWN, 0 everything else
        split = stoppedcause.report_split(results)
        self.assertEqual(split[stoppedcause.STILL_UNKNOWN], 33)
        self.assertEqual(split[stoppedcause.UNSUBSCRIBED], 0)
        self.assertEqual(split[stoppedcause.REPLIED_INTERESTED], 0)
        self.assertEqual(split[stoppedcause.BOUNCED], 0)
        self.assertEqual(split[stoppedcause.WE_STOPPED_IT], 0)
        self.assertEqual(split[stoppedcause.SEQUENCE_FINISHED], 0)

    def test_fetch_exception_is_still_unknown_not_crash(self):
        """A fetch that raises is not evidence of absence."""
        person = _person()
        def failing_fetch(**kw):
            raise RuntimeError("provider unreachable")
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=failing_fetch,
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)


# --------------------------------------------------------- priority order

class PriorityOrderTest(unittest.TestCase):
    """When multiple signals exist, the most severe wins.

    Unsubscribe > Reply > Bounce > We stopped it > Sequence finished.
    """

    def test_unsubscribe_wins_over_reply(self):
        person = _person(replies=1)
        events = [_event("unsubscribed"), _event("replied")]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events)
        self.assertEqual(result["outcome"], stoppedcause.UNSUBSCRIBED)

    def test_reply_wins_over_bounce(self):
        person = _person(lead_status="bounced")
        events = [_event("replied"), _event("bounced")]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events)
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)

    def test_bounce_wins_over_ledger_stop(self):
        person = _person(lead_status="bounced")
        ledger = [_ledger_row(campaign_id=200, lead_id=101)]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=ledger)
        self.assertEqual(result["outcome"], stoppedcause.BOUNCED)


# --------------------------------------------------------- batch resolution

class BatchResolutionTest(unittest.TestCase):
    """resolve_account_holds processes every stopped membership in an account."""

    def test_resolves_all_stopped_memberships(self):
        """Only memberships with status `stopped` are resolved."""
        account = {
            "people": [
                _person(lead_id=101, campaign_id=200, campaign_status="stopped"),
                _person(lead_id=102, campaign_id=201, campaign_status="stopped"),
                _person(lead_id=103, campaign_id=202, campaign_status="sequence_finished"),
            ]
        }
        results = stoppedcause.resolve_account_holds(
            account, events_fetch=lambda **kw: [], ledger_rows=[])
        # Only the two `stopped` memberships are resolved
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["outcome"], stoppedcause.STILL_UNKNOWN)
        self.assertEqual(results[1]["outcome"], stoppedcause.STILL_UNKNOWN)

    def test_skips_non_stopped_memberships(self):
        account = {
            "people": [
                _person(lead_id=101, campaign_id=200, campaign_status="in_sequence"),
                _person(lead_id=102, campaign_id=201, campaign_status="sequence_finished"),
            ]
        }
        results = stoppedcause.resolve_account_holds(
            account, events_fetch=lambda **kw: [], ledger_rows=[])
        # Only the sequence_finished one is not `stopped`, but it is still
        # a membership. However, only `stopped` memberships are resolved.
        # Actually, the function resolves ALL memberships with status `stopped`.
        # Let me check: the person has campaign_status="in_sequence", so it
        # should be skipped.
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()


class TestNeverContactedIsAFactNotAClearance(unittest.TestCase):
    """A stopped membership that sent NOTHING cannot carry a prospect's
    refusal - nobody at that address was written to on that campaign.

    It is the only cause answerable without the events feed, and that matters
    more than it sounds: `/api/events` replays TEN DAYS while these
    memberships are months old, so a resolver that depended on it would return
    STILL_UNKNOWN for nearly all of them and the 33 would stay a question
    forever.
    """

    def _zero_send(self, **kw):
        person = _person(**kw)
        person["emails_sent"] = 0
        person["campaigns"][0]["emails_sent"] = 0
        return person

    def test_a_stopped_membership_that_sent_nothing(self):
        person = self._zero_send()
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.NEVER_CONTACTED)
        self.assertIn("emails_sent is 0", result["evidence"])

    def test_it_does_not_outrank_a_real_refusal(self):
        """Every branch above it names something that HAPPENED, and a lead can
        carry a real refusal from a prior campaign while THIS membership sent
        nothing. A reply must still win."""
        person = self._zero_send(replies=2)
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.REPLIED_INTERESTED)

    def test_an_unsubscribe_event_still_wins(self):
        person = self._zero_send()
        events = [{"kind": "unsubscribed",
                   "provider_event_type": "LEAD_UNSUBSCRIBED",
                   "occurred_at": "2026-01-02T00:00:00Z"}]
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: events,
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.UNSUBSCRIBED)

    def test_an_absent_membership_row_is_not_a_zero(self):
        """Missing evidence is never positive evidence. A campaign the person
        has no membership row for must NOT read as 'sent nothing'."""
        person = _person(campaign_id=200)
        result = stoppedcause.resolve(person, campaign_id=999,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        self.assertEqual(result["outcome"], stoppedcause.STILL_UNKNOWN)

    def test_a_non_numeric_emails_sent_does_not_read_as_zero(self):
        """`None` or a string must not be coerced into 'nobody was emailed'."""
        for bad in (None, "", "three", {}):
            with self.subTest(emails_sent=bad):
                person = _person()
                person["campaigns"][0]["emails_sent"] = bad
                result = stoppedcause.resolve(person, campaign_id=200,
                                              events_fetch=lambda **kw: [],
                                              ledger_rows=[])
                self.assertNotEqual(result["outcome"],
                                    stoppedcause.NEVER_CONTACTED,
                                    "an unreadable counter is not a zero one")

    def test_never_contacted_is_in_the_split(self):
        person = self._zero_send()
        result = stoppedcause.resolve(person, campaign_id=200,
                                      events_fetch=lambda **kw: [],
                                      ledger_rows=[])
        split = stoppedcause.report_split([result])
        self.assertEqual(split[stoppedcause.NEVER_CONTACTED], 1)
        self.assertEqual(split[stoppedcause.STILL_UNKNOWN], 0)
