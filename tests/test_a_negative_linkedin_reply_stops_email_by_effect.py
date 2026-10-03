"""Deliverable 6: a NEGATIVE LinkedIn reply stops EMAIL, proven BY EFFECT.

WHAT ALREADY EXISTED AND WHY IT IS NOT ENOUGH.
`tests/test_a_linkedin_reply_stops_email_inside_fifteen_minutes.py` proves
the CLOCK: poll interval 300s + measured stop write 1.694s + a 30s local
budget = ~332s, comfortably inside the 900s gate. That is arithmetic over
named terms, and it is good arithmetic. What it does not do is take a
record that email could go to, deliver a negative LinkedIn reply, and then
ask the email gate again.

So this file asserts the EFFECT, in the only way that means anything:

    1. BEFORE  - ask `eligibility.decide` for the EMAIL step. It must be
                 something other than blocked-by-reply, or the test proves
                 nothing (a record that was already blocked would pass this
                 file with the machinery disconnected).
    2. DELIVER - one negative reply, arriving on LINKEDIN, matched to the
                 person by their profile URL and not by their email.
    3. AFTER   - ask the EMAIL gate again. It must now refuse, and refuse
                 for a reply-shaped reason.

Step 1 is the control and it is the half that is usually missing.

AND THE CLOCK IS STILL ASSERTED, against the same named terms, because an
effect that takes an hour does not satisfy "within 15 minutes".
"""
import time
import unittest

from src import accountpolicy, eligibility, events, linkedin, replies


PROFILE = "https://www.linkedin.com/in/ann-example"

#: The three terms, from the module that owns each. Not retyped as
#: literals: `replywatch.DEFAULT_INTERVAL` is what the running loop uses.
GATE_SECONDS = 15 * 60


def _record():
    """One account, one contact, reachable on BOTH channels.

    The cross-channel join in this system is structural: ONE contact dict
    carries `email` and `linkedin` together, so a reply matched by profile
    URL lands on the same object the email gate reads. That is the thing
    being tested, so the fixture must not fake it with two records.
    """
    return {
        "id": "acme-com", "domain": "acme.com", "company": "Acme",
        "state": "approved", "client": "demo", "lane": "cold",
        "company_facts": {"name": "Acme", "employees": 40},
        "contacts": [{
            "key": "ann", "name": "Ann Example", "title": "COO",
            "persona": "founder", "angle": "operations efficiency",
            "email": "ann@acme.com", "linkedin": PROFILE,
            "bison_lead_id": "bison-1", "heyreach_lead_id": "hr-1",
        }],
        "events": [], "research": [], "cadence": {},
    }


class TheJoinIsRealBeforeAnythingElse(unittest.TestCase):
    """CONTROL. If the profile does not match the contact, nothing below
    is about cross-channel anything."""

    def test_a_linkedin_event_matches_the_contact_that_holds_the_email(self):
        rec = _record()
        event = {"type": "reply_received", "linkedin": PROFILE,
                 "text": "not interested"}
        matched = events.match_record([rec], event)
        self.assertIs(matched, rec)
        key = events.match_contact(rec, event)
        self.assertEqual(key, "ann")
        contact = rec["contacts"][0]
        self.assertEqual(contact["email"], "ann@acme.com",
                         "the matched contact must be the one email goes to")

    def test_the_profile_url_is_canonicalised_not_compared_raw(self):
        self.assertEqual(linkedin.canonical(PROFILE),
                         linkedin.canonical(PROFILE.upper().replace(
                             "HTTPS://WWW.LINKEDIN.COM",
                             "https://www.linkedin.com")))


class ANegativeReplyIsClassifiedNegative(unittest.TestCase):
    """CONTROL for the verdict itself."""

    def test_not_interested_is_negative(self):
        """The key is `classification`, and the phrase matters.

        "not interested, please remove me" classifies as UNSUBSCRIBE, not
        NEGATIVE - `RULES` puts the unsubscribe patterns ahead of the
        negative ones on purpose, and "remove me" is an unsubscribe. That
        is a STRONGER stop, not a miss, but this test is about the negative
        verdict specifically, so it uses a phrase that is only negative.
        """
        verdict = replies.classify("not interested, thanks")
        self.assertEqual(verdict["classification"], replies.NEGATIVE)

    def test_a_removal_request_is_the_stronger_unsubscribe_verdict(self):
        verdict = replies.classify("not interested, please remove me")
        self.assertEqual(verdict["classification"], replies.UNSUBSCRIBE)

    def test_a_neutral_sentence_is_not_negative(self):
        """So the test above is about the words and not about everything."""
        verdict = replies.classify("thanks, can you send more detail?")
        self.assertNotEqual(verdict["classification"], replies.NEGATIVE)


class TheEmailGateChangesItsAnswer(unittest.TestCase):
    """THE DELIVERABLE. Before, deliver, after."""

    def _email_decision(self, rec):
        contact = rec["contacts"][0]
        step = {"channel": "email", "subject": "a question about Acme",
                "body": " ".join(["word"] * 80)}
        return eligibility.decide(
            rec, contact, "day1", channel="email", step=step,
            timeline={"ann": {"day1": step}})

    def test_before_the_reply_the_email_gate_is_not_blocking_for_a_reply(self):
        """THE CONTROL. Without it this file passes on a dead record."""
        decision = self._email_decision(_record())
        self.assertNotIn(eligibility.BLOCKED_REPLIED, decision["reasons"])
        self.assertNotIn(eligibility.BLOCKED_CONTACT_STOPPED,
                         decision["reasons"])
        self.assertNotIn(eligibility.BLOCKED_UNSUBSCRIBED,
                         decision["reasons"])

    def test_a_negative_linkedin_reply_blocks_the_email_step(self):
        rec = _record()
        before = self._email_decision(rec)
        self.assertNotIn(eligibility.BLOCKED_CONTACT_STOPPED,
                         before["reasons"])

        # DELIVER. `accountpolicy.apply_reply` is the only thing that moves
        # a record into a stopped state, and `inbound.handle` reaches it
        # for every reply. Called directly here so the assertion is about
        # the STATE TRANSITION and not about the poller's plumbing - the
        # poller is the clock, asserted separately below.
        accountpolicy.apply_reply(rec, "ann", outcome=replies.NEGATIVE,
                                  channel="linkedin")

        after = self._email_decision(rec)
        self.assertNotEqual(after["verdict"], eligibility.ELIGIBLE,
                            "email is still eligible after a negative "
                            "LinkedIn reply from the same person")
        reply_shaped = {eligibility.BLOCKED_CONTACT_STOPPED,
                        eligibility.BLOCKED_REPLIED,
                        eligibility.BLOCKED_UNSUBSCRIBED,
                        eligibility.BLOCKED_CONTACT_PAUSED,
                        eligibility.BLOCKED_COMPANY_PAUSED}
        self.assertTrue(
            reply_shaped & set(after["reasons"]),
            f"email was refused, but not for a reply-shaped reason: "
            f"{after['reasons']}")

    def test_the_contact_is_marked_stopped_on_the_record(self):
        """The mechanism, so a future refactor cannot pass by accident."""
        rec = _record()
        accountpolicy.apply_reply(rec, "ann", outcome=replies.NEGATIVE,
                                  channel="linkedin")
        contact = rec["contacts"][0]
        self.assertTrue(contact.get("stopped") or contact.get("unsubscribed")
                        or rec.get("paused"),
                        "nothing on the record records the stop")

    def test_a_colleague_at_the_same_company_is_a_separate_question(self):
        """Scope check: this must not silently stop the whole estate."""
        rec = _record()
        rec["contacts"].append({
            "key": "bob", "name": "Bob Other", "title": "CFO",
            "persona": "founder", "angle": "operations efficiency",
            "email": "bob@acme.com",
            "linkedin": "https://www.linkedin.com/in/bob-other"})
        accountpolicy.apply_reply(rec, "ann", outcome=replies.NEGATIVE,
                                  channel="linkedin")
        self.assertTrue(rec["contacts"][0].get("stopped")
                        or rec["contacts"][0].get("unsubscribed")
                        or rec.get("paused"))
        # Bob's own contact-level stop flag must not have been set by Ann's
        # reply. The ACCOUNT may be held, which is a different control.
        self.assertFalse(rec["contacts"][1].get("stopped"))


class TheClockStillClears(unittest.TestCase):
    """The effect above has to happen inside the operator's 15 minutes."""

    def test_the_poll_interval_is_the_one_the_running_loop_uses(self):
        from src import replywatch
        self.assertEqual(replywatch.DEFAULT_INTERVAL, 300)
        self.assertIn("heyreach", replywatch.PROVIDERS)
        self.assertIn("emailbison", replywatch.PROVIDERS)

    def test_the_local_work_is_far_inside_its_budget(self):
        """MEASURED here rather than asserted: classify, apply, re-decide."""
        rec = _record()
        started = time.monotonic()
        replies.classify("not interested, thanks")
        accountpolicy.apply_reply(rec, "ann", outcome=replies.NEGATIVE,
                                  channel="linkedin")
        contact = rec["contacts"][0]
        step = {"channel": "email", "subject": "s",
                "body": " ".join(["word"] * 80)}
        eligibility.decide(rec, contact, "day1", channel="email", step=step,
                           timeline={"ann": {"day1": step}})
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 30.0, f"local work took {elapsed:.2f}s")

    def test_the_worst_case_clears_the_gate_with_headroom(self):
        from src import replywatch
        # poll + the measured EmailBison stop write + the 30s local budget
        worst = replywatch.DEFAULT_INTERVAL + 1.694 + 30.0
        self.assertLess(worst, GATE_SECONDS)
        # The unmeasured term is provider VISIBILITY: how long after a
        # person hits send the row is readable in the HeyReach inbox. It
        # has never been measured live. Named here so the headroom is a
        # budget for a known unknown rather than a comfort.
        self.assertGreater(GATE_SECONDS - worst, 8 * 60)


if __name__ == "__main__":
    unittest.main()
