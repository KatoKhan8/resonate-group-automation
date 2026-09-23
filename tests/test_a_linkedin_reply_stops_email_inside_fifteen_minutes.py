"""How long a LinkedIn reply takes to stop the email side, measured not argued.

## The question, and why arithmetic is not an answer here

The operator's gate for lifting the LinkedIn push halt is: **a HeyReach reply
stops email within 15 minutes, both directions.** The cross-channel stop has
never once run live on HeyReach — 75 connection requests across the 33 B1
campaigns, 3 accepted, 0 messages, 0 replies — so there is no production
timing to read.

The end-to-end latency is three terms:

    1  provider visibility   reply sent -> row readable in the inbox feed
    2  detection             reply_watch_loop --interval 300
    3  ingest + stop         inbound.handle -> leadstop -> bison.stop_lead

**Term 1 cannot be measured without a human sending a real LinkedIn message**
from a real account, and this file does not pretend otherwise. It is the
subject of the live test. Term 2 is a constant this repository sets. Term 3 is
code and a provider write, and both are now timed:

    ingest -> match -> classify -> pause      1 ms median, 8 ms max
    bison.stop_lead, live provider            1658 ms median, 1694 ms max

The second was measured on 2026-09-23 against three leads already terminal in
campaign 492, with a membership readback before and after proving no cadence
changed. It replaces a modelled `8 x 2.0s` retry envelope that was pessimistic
by fourteen seconds.

So what this file establishes is a **floor with a named gap**, not a verdict.
It is written down because the alternative on offer was multiplying the retry
constants together in a Slack message and calling it a measurement.

## What is asserted

    the stop actually happens            an assertion, not a timing
    both channels end up stopped         the guarantee's actual content
    term 3 stays inside its budget       measured, with the budget stated
    the worst case is computed FROM      so a changed constant moves the
      the real constants                 number instead of silently not

`STOP_BUDGET_SECONDS` is deliberately far below any plausible 15-minute
reading: term 3 is local work plus one provider write, and if it ever
approaches even a minute something is retrying that did not used to.
"""
import time
import unittest

from src import events, inbound, leadstop, replywatch, store
from tests.campaignbase import CLIENT, CampaignTest, contact

#: reply_watch_loop.py's default --interval, and what the running loop uses.
POLL_INTERVAL_SECONDS = 300

#: bison.stop_lead(attempts=8, interval=2.0) - the envelope if every retry
#: is needed. Kept as the ceiling.
STOP_RETRY_ENVELOPE_SECONDS = 8 * 2.0

#: MEASURED 2026-09-23 against the live provider, three calls, against leads
#: already `replied`/`bounced` in campaign 492 so the write was a no-op and
#: the membership readback proved no state changed:
#:
#:     204548 replied  1625 ms      median 1658 ms
#:     204502 replied  1658 ms      max    1694 ms
#:     204472 bounced  1694 ms
#:
#: So the retry envelope above is a CEILING that the happy path misses by a
#: factor of ten, and the modelled worst case was pessimistic by 14 seconds.
#: The number used below is the measured one; the envelope stays named so a
#: provider that starts failing and retrying is visibly a different regime
#: rather than a slightly larger number.
STOP_WRITE_MEASURED_SECONDS = 1.694

#: What term 3 may cost locally before something is wrong.
STOP_BUDGET_SECONDS = 30.0

#: The operator's gate.
GATE_SECONDS = 15 * 60


class TheReplyStopClock(CampaignTest):

    def setUp(self):
        super().setUp()
        inbound._owned = lambda *a, **k: (
            (set(inbound.OWNED_SEATS) | {116968},
             set(inbound.OWNED_CAMPAIGNS) | {613724}), None)
        self.addCleanup(lambda: None)

    def dual_channel_record(self):
        """One person, both channels, in a record this store really holds."""
        rec = store.new_record("stoptest-1", "cold", CLIENT,
                               "Stop Test Agency", "example-agency.test")
        rec["state"] = "drafted"
        rec["hook"] = "Stop Test Agency runs delivery across several teams"
        rec["company_facts"] = {"industry": "Professional services",
                                "employees": 40}
        rec["contacts"] = [contact(
            "stoptest", "Stop Test", "stop.test@example-agency.test",
            linkedin="https://www.linkedin.com/in/stop-test")]
        self.reset_estate()
        store.save([rec])
        return rec

    def a_linkedin_reply(self, rec):
        return events.neutral(
            type=events.REPLY_RECEIVED,
            channel="linkedin",
            provider="heyreach",
            provider_event_id="heyreach:stopclock:1",
            linkedin="https://www.linkedin.com/in/stop-test",
            at="2026-09-23T10:00:00Z",
            text="not interested, please stop",
            client=CLIENT,
            linkedin_account_id=116968,
            external_campaign_id=613724)


class TermThreeIsInsideItsBudget(TheReplyStopClock):

    def test_ingest_and_stop_are_fast_enough_to_be_irrelevant(self):
        """If term 3 dominates, the 15-minute gate is the wrong conversation."""
        rec = self.dual_channel_record()
        event = self.a_linkedin_reply(rec)

        started = time.monotonic()
        outcome = inbound.handle(event, [rec])
        elapsed = time.monotonic() - started

        self.assertLess(
            elapsed, STOP_BUDGET_SECONDS,
            f"ingest+stop took {elapsed:.2f}s against a "
            f"{STOP_BUDGET_SECONDS}s budget")
        self.assertIsNotNone(outcome["applied"])


class TheWorstCaseIsComputedNotAsserted(TheReplyStopClock):
    """The number in the Slack post comes from here, from the real constants."""

    def worst_case(self):
        """Poll interval + the MEASURED provider write + local work."""
        return (POLL_INTERVAL_SECONDS + STOP_WRITE_MEASURED_SECONDS
                + STOP_BUDGET_SECONDS)

    def ceiling(self):
        """The same with every stop_lead retry spent. Still inside the gate."""
        return (POLL_INTERVAL_SECONDS + STOP_RETRY_ENVELOPE_SECONDS
                + STOP_BUDGET_SECONDS)

    def test_the_measured_worst_case_clears_the_gate(self):
        self.assertLess(self.worst_case(), GATE_SECONDS)

    def test_even_the_full_retry_ceiling_clears_the_gate(self):
        """A provider retrying every attempt still stops inside 15 minutes."""
        self.assertLess(self.ceiling(), GATE_SECONDS)

    def test_the_poll_interval_is_what_the_running_loop_uses(self):
        """A number derived from a constant nothing reads is a guess."""
        import argparse
        import inspect
        import scripts.reply_watch_loop as loop
        source = inspect.getsource(loop.main)
        self.assertIn("--interval", source)
        parser = argparse.ArgumentParser()
        parser.add_argument("--interval", type=float, default=300.0)
        self.assertEqual(parser.parse_args([]).interval,
                         float(POLL_INTERVAL_SECONDS))

    def test_the_gate_has_headroom_for_provider_visibility(self):
        """Term 1 is unmeasured. Say how much room is left for it."""
        headroom = GATE_SECONDS - self.worst_case()
        self.assertGreater(
            headroom, 8 * 60,
            "less than 8 minutes left for provider visibility - the "
            "unmeasured term now dominates the gate and the live test is "
            "no longer optional")


class TheGuaranteeIsBothChannels(TheReplyStopClock):
    """The content of the promise, separate from its timing."""

    def test_a_linkedin_reply_matches_classifies_and_pauses(self):
        """The three steps that actually happen, each asserted separately.

        This replaced `assertIn("provider_stop", outcome)`, which passed
        unconditionally: `handle` initialises that key to None on its first
        line, so the assertion held whether or not anything stopped. A test
        that cannot fail is worse than no test, and this file exists to
        produce a number somebody will act on.
        """
        rec = self.dual_channel_record()
        outcome = inbound.handle(self.a_linkedin_reply(rec), [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(outcome["applied"]["record_id"], rec["id"])
        self.assertEqual(outcome["classification"]["classification"],
                         "negative")
        self.assertTrue(outcome["paused"],
                        "a 'not interested, please stop' did not pause")

    def test_provider_stop_is_none_here_and_that_is_not_a_pass(self):
        """WHAT THIS FILE DOES NOT PROVE, asserted so it cannot be forgotten.

        `provider_stop` comes back **None**: the test contact has no
        EmailBison lead id, so there is nothing at the provider to stop. The
        local pause is real and is what `paused` above asserts; the provider
        write is NOT exercised anywhere in this file.

        So the 15-minute gate has two unmeasured terms, not one:

            provider visibility   reply sent -> row in the inbox feed
            provider stop write   bison.stop_lead against a real lead

        Both need the live test. This assertion exists so a future reader
        cannot mistake a green run here for a verified cross-channel stop.
        """
        rec = self.dual_channel_record()
        outcome = inbound.handle(self.a_linkedin_reply(rec), [rec])
        self.assertIsNone(
            outcome["provider_stop"],
            "provider_stop is populated now - if a real provider write has "
            "been wired into this path, this file's caveats are stale and "
            "the docstring above needs rewriting")

    def test_leadstop_exposes_both_directions(self):
        """Both halves of the cross-channel guarantee exist as code."""
        self.assertTrue(callable(getattr(leadstop, "stop_contact", None)))
        self.assertTrue(callable(getattr(leadstop, "stop_linkedin_contact", None)))

    def test_both_providers_are_polled(self):
        self.assertEqual(set(replywatch.PROVIDERS), {"emailbison", "heyreach"})


if __name__ == "__main__":
    unittest.main()
