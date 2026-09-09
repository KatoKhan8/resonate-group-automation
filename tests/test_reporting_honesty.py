"""Numbers that were being computed correctly and meaning something else.

Five defects, found by walking every rate on every reporting surface back to
the code that writes the field it counts. Four of them are the same shape as
this codebase's own worst precedent - an evaluator that reported
INSUFFICIENT_DATA forever because nothing wrote the field it read.

**A tile that could only ever be zero.** The internal report counted
`invalid` from `contact["verification"]["status"]`. `verification.apply`
writes `state`. Nothing has ever written `status`, so "Invalid - not used"
read 0 for every workspace, which is indistinguishable from having checked.

**Two definitions of "double verified".** The same two words meant
"confirmations obtained" on the operator dashboard and "providers asked" in
the client report. Two providers both answering `unknown` were reported to
a client as double verified. Those words describe the safety property the
whole build rests on.

**One reply counted twice.** `replies.apply` writes a `reply_classified`
beside every `reply_received`, and a `positive_reply_detected` beside every
positive one. The sender report added the types together, so its reply and
positive rates were about double the same client's PDF. A test elsewhere
says this exact bug was found and fixed in the workspace card; nobody
checked here.

**A stored flag read where everything else recomputes.** `report.funnel`
counted `verified` from `contact["sendable"]`. `verification.is_sendable`
documents at length why that is the wrong thing to read, and `funnel` is
the default output of `python -m src.report`.

**A rate with no denominator.** The operator screen printed a bare rounded
float, and an empty cell when no contact had an address.
"""
import unittest

from tests.campaignbase import CampaignTest, contact as make_contact

from src import events, report, store, verification as v


def evidence_for(email, statuses):
    return [v.result(provider, status, email)
            for provider, status in statuses]


def contact_with(email, statuses, key="a"):
    contact = {"key": key, "name": "A Person", "email": email,
               "selected": True}
    evidence = evidence_for(email, statuses)
    v.apply(contact, v.decide(evidence), evidence)
    return contact


class TheVerificationTiles(CampaignTest):
    """Recomputed from the evidence, like everything else that asks."""

    def counts(self, contacts):
        from src.web import api

        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = contacts
        return api._verification_counts(
            [rec], v.policy_for(self.config))

    def test_two_providers_both_unsure_is_not_double_verified(self):
        """The words on that tile describe the safety property. Two
        providers having been *asked* is not two confirmations."""
        found = self.counts([contact_with("a@x.test",
                                          [("contactout", v.S_UNKNOWN),
                                           ("deliverable", v.S_UNKNOWN)])])
        self.assertEqual(found["double"], 0)

    def test_two_confirmations_is(self):
        found = self.counts([contact_with("a@x.test",
                                          [("contactout", v.S_VALID),
                                           ("deliverable", v.S_VALID)])])
        self.assertEqual(found["double"], 1)
        self.assertEqual(found["single"], 0)

    def test_one_confirmation_is_held_for_a_second(self):
        found = self.counts([contact_with("a@x.test",
                                          [("contactout", v.S_VALID)])])
        self.assertEqual(found["single"], 1)
        self.assertEqual(found["double"], 0)

    def test_an_invalid_address_is_counted(self):
        """It read a key nothing writes, so this was zero forever."""
        found = self.counts([contact_with("a@x.test",
                                          [("contactout", v.S_INVALID)])])
        self.assertEqual(found["invalid"], 1)

    def test_a_disagreement_is_counted(self):
        found = self.counts([contact_with("a@x.test",
                                          [("contactout", v.S_VALID),
                                           ("deliverable", v.S_INVALID)])])
        self.assertEqual(found["disagreement"], 1)

    def test_a_contact_with_no_address_is_in_no_bucket(self):
        found = self.counts([{"key": "b", "name": "B"}])
        self.assertEqual(found["addresses"], 0)
        self.assertEqual(found["double"] + found["single"], 0)

    def test_the_denominator_travels_with_them(self):
        """Four counts and nothing to read them against was the other half
        of the same problem."""
        found = self.counts([
            contact_with("a@x.test", [("contactout", v.S_VALID),
                                      ("deliverable", v.S_VALID)], key="a"),
            contact_with("b@x.test", [("contactout", v.S_VALID)], key="b")])
        self.assertEqual(found["addresses"], 2)

    def test_a_stored_verdict_with_no_evidence_is_not_double_verified(self):
        """The drift every other reader of this recomputes to avoid."""
        found = self.counts([{"key": "a", "email": "a@x.test",
                              "verification": {"state": "verified",
                                               "providers": ["a", "b"],
                                               "confirmation_count": 2}}])
        self.assertEqual(found["double"], 0)


class TheFunnelRecomputes(CampaignTest):

    def test_a_hand_written_sendable_flag_does_not_count_as_verified(self):
        """`verification.is_sendable` says why reading the stored value is
        the mistake. `funnel` was the last caller still doing it, and it is
        what `python -m src.report` prints by default."""
        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = [{"key": "a", "email": "a@x.test",
                            "sendable": True}]
        self.assertEqual(report.funnel([rec])["verified"], 0)

    def test_real_evidence_does(self):
        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = [contact_with("a@x.test",
                                        [("contactout", v.S_VALID),
                                         ("deliverable", v.S_VALID)])]
        self.assertEqual(report.funnel([rec])["verified"], 1)


class OneReplyIsOneReply(CampaignTest):
    """The sender report added the event types together."""

    def sender_rows(self):
        from src import repo as repo_module
        from src.web import api

        return api.sender_report(repo_module.Repo.for_client("demo"))["rows"]

    def seeded(self, positive=False):
        from src import replies

        recs = self.seed_records()
        rec = recs[0]
        contact = rec["contacts"][0]
        contact["selected"] = True
        # The stored assignment, written the way `assignment.stored` reads
        # it. What the sender report groups by is not what this test is
        # about; that one reply is one reply is.
        contact["sender_assignment"] = {
            "email": {"sender_id": "anna", "account_id": "anna07"}}
        at = "2026-09-01T09:00:00+00:00"
        events.record(rec, events.REPLY_RECEIVED, contact_key=contact["key"],
                      channel="email", at=at)
        replies.apply(rec, contact["key"],
                      "Sounds good, happy to chat." if positive
                      else "Thanks, I will take a look.",
                      at=at, channel="email")
        store.save(recs)
        return recs

    def test_one_message_is_one_reply(self):
        self.seeded()
        total = sum(row["replies"] for row in self.sender_rows())
        self.assertEqual(total, 1)

    def test_one_positive_is_one_positive(self):
        self.seeded(positive=True)
        rows = self.sender_rows()
        self.assertEqual(sum(row["replies"] for row in rows), 1)
        self.assertEqual(sum(row["positive"] for row in rows), 1)


class ADeliveredCountOfZero(CampaignTest):
    """Three states, and the middle one was invisible.

    `or None` made a period with sends and no delivery confirmation render
    exactly like a period with no delivery instrumentation at all - both
    "n/a", under a note in the client report promising this reads n/a
    rather than 0.
    """

    def counts(self, pushed=0, delivered=0):
        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = [{"key": "a", "email": "a@x.test"}]
        for _ in range(pushed):
            events.record(rec, events.PUSH_MARKED, contact_key="a",
                          channel="email", at=_stamp(_),
                          step="day1", sender_id="anna")
        for _ in range(delivered):
            events.record(rec, events.EMAIL_DELIVERED, contact_key="a",
                          channel="email", at=_stamp(_ + 50))
        store.save([rec])
        return report.for_client("demo", [rec], config=self.config)

    def test_nothing_sent_is_not_a_fact_about_deliverability(self):
        """0 delivered of nothing sent is not a number worth printing."""
        self.assertIsNone(self.counts()["emails_delivered"])

    def test_sent_and_nothing_confirmed_is_a_real_zero(self):
        """The state that was invisible, and the alarming one."""
        self.assertEqual(self.counts(pushed=3)["emails_delivered"], 0)

    def test_confirmed_deliveries_are_counted(self):
        self.assertEqual(
            self.counts(pushed=3, delivered=2)["emails_delivered"], 2)


def _stamp(n):
    return "2026-08-%02dT09:00:00+00:00" % (1 + (n % 27))


class EveryRateShowsItsDenominator(CampaignTest):

    def html(self):
        from src import repo as repo_module
        from src.web import api, pages

        repo = repo_module.Repo.for_client("demo")
        return pages.reporting(api.reporting(repo))

    def test_the_pass_rate_is_a_pair(self):
        """It was the only bare rate on any surface, and an empty cell when
        nothing had an address."""
        store.save(self.seed_records())
        html = self.html()
        self.assertIn("Pass rate", html)
        self.assertIn(" of ", html.split("Pass rate", 1)[1][:400])

    def test_it_says_nothing_rather_than_nothing_at_all(self):
        """No addresses at all used to render a blank cell."""
        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = [{"key": "a", "name": "A"}]
        store.save([rec])
        after = self.html().split("Pass rate", 1)[1][:400]
        self.assertIn("0 of 0", after)


class NothingObservesAMeeting(CampaignTest):

    def test_a_global_tile_says_so_rather_than_printing_zero(self):
        """A zero here is an absence of instrumentation, and the source
        table three lines below already said so while the tile said 0."""
        from src.web import pages

        self.assertIn("not tracked", pages._meetings(0))
        self.assertIn("not tracked", pages._meetings(None))

    def test_a_real_count_is_printed(self):
        from src.web import pages

        self.assertEqual(pages._meetings(3), "3")


if __name__ == "__main__":
    unittest.main()
