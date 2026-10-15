"""What went out, and the one number that is allowed to be an alarm.

WHAT THIS FILE IS FOR. This is the page the operator reads at 09:00 on the
morning CANARY-01 sends. The question is per PROSPECT - what went out, to
whom, from which sender, did anything refuse - and TASK 0030's provider write
log cannot answer it: that ledger's row carries no address, no sender, no step
and no channel. So two authorities are crossed here, and the test that matters
most is that neither is allowed to cover for the other.

THE INVARIANT UNDER TEST IS `unaccounted`, and it is built to be able to fire.
`attempted` is defined by a NAMED SET of touch states that mean "we acted",
independently of sent and refused. Defining it as sent + refused + leftovers
would make `unaccounted` zero by construction, and the page would be reporting
its own arithmetic back as a safety property. So:

    a touch state this page cannot classify is counted as attempted AND as
    unaccounted, and raises the warning - it is never filed into whichever of
    the two buckets is checked first;

    an unreadable refusal ledger makes the refusal figure UNKNOWN, never 0;

    a failed self-control makes every COUNT UNKNOWN - None and not 0, because
    a zero on this page reads as "nothing went out";

    the approved-cohort denominator is UNKNOWN when nobody supplied it, and is
    never defaulted to the number of rows found, which would make the figure
    agree with itself whatever happened.

EVERY ADDRESS IN THIS FILE IS SYNTHETIC. The real rows name real prospects, so
the brief forbids putting one in a fixture, and nothing here reads the real
store: every record is a dict this test builds and hands to the reader.
NOTHING REACHES A PROVIDER OR A NETWORK. One test patches `socket.socket` to
raise and then calls the reader.
"""
import datetime
import json
import os
import shutil
import socket
import tempfile
import unittest

from src import canarysend, events, touch
from src.web import pages
from src.web.app import permission_for
from tests.webbase import WebTest

PATH = "/canary"
ADMIN = "admin@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"

NOW = datetime.datetime(2026, 10, 16, 9, 0, 0)

#: Synthetic throughout. `.invalid` is reserved by RFC 2606 and can never be
#: a real prospect, which is a stronger guarantee than choosing a name that
#: merely looks fictional.
ALICE = "alice@example.invalid"
BRUNO = "bruno@example.invalid"

#: `record_id -> contact_key -> timeline`. Supplied explicitly so that no
#: test here needs a client config on disk, reaches `cadence.build`, or can
#: touch the real store. An EMPTY per-contact timeline is the honest fixture
#: for a send: the step is established by the confirming event, not by the
#: plan. Refusals need a status, so those tests use `timeline_with`.
TIMELINE = {"rec-1": {"k1": {}}}


def timeline_with(status, step="em1", channel="email", day=1,
                  record_id="rec-1", contact_key="k1"):
    """A timeline carrying a cadence status, which is the ONLY thing that
    produces BLOCKED, HELD or PAUSED - see `canarysend._timelines_for`."""
    return {record_id: {contact_key: {
        step: {"status": status, "channel": channel, "day": day}}}}


def record(record_id="rec-1", campaign="c-901", address=ALICE,
           contact_key="k1", selected=True, event_list=None):
    """One queue record with one contact. Nothing is loaded from a store."""
    return {
        "id": record_id,
        "campaign": campaign,
        "contacts": [{"key": contact_key, "selected": selected,
                      "email": address}],
        "events": list(event_list or []),
    }


def sent_event(contact_key="k1", step="em1", channel="email",
               sender="sender-7", at="2026-10-16T08:30:00Z"):
    """A confirming touch event - `push_marked` is what establishes SENT.

    Built by hand rather than through `events.record` so that a change to
    that function's defaults shows up here as a failure rather than as a
    page that reads every row UNKNOWN and looks merely cautious.
    """
    return {"type": events.PUSH_MARKED, "contact": contact_key, "step": step,
            "channel": channel, "sender_id": sender, "at": at,
            "id": "ev-%s-%s" % (contact_key, step)}


class TheReaderIsNotBlind(unittest.TestCase):
    """Without this class every refusal below is satisfied by a reader that
    classifies nothing, which is this lane's own B7 defect."""

    def test_the_three_controls_all_pass(self):
        results = canarysend.controls(now=NOW)
        self.assertEqual(len(results), 3)
        for check in results:
            self.assertTrue(check["ok"], "%s FAILED: %s"
                            % (check["name"], check["detail"]))

    def test_the_controls_are_the_three_the_brief_names(self):
        names = {check["name"] for check in canarysend.controls(now=NOW)}
        self.assertEqual(names, {
            "an_unreadable_ledger_is_unknown_not_zero",
            "a_planted_refusal_is_refused_with_its_reason",
            "an_unclassifiable_row_lands_in_unaccounted"})

    def test_a_confirmed_touch_reads_as_sent(self):
        """The positive direction. A reader that never says SENT passes
        every other test in this file and is useless."""
        rows, _, _ = canarysend.rows_for([record(event_list=[sent_event()])],
                                      now=NOW, timelines=TIMELINE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], canarysend.SENT)

    def test_the_row_carries_all_seven_columns(self):
        rows, _, _ = canarysend.rows_for([record(event_list=[sent_event()])],
                                      now=NOW, timelines=TIMELINE)
        row = rows[0]
        self.assertEqual(row["at"], "2026-10-16T08:30:00Z")
        self.assertEqual(row["address"], ALICE)
        self.assertEqual(row["channel"], "email")
        self.assertEqual(row["campaign"], "c-901")
        self.assertEqual(row["step"], "em1")
        self.assertEqual(row["sender_id"], "sender-7")
        self.assertEqual(row["outcome_label"], "SENT")

    def test_the_absent_ledger_control_uses_a_really_absent_path(self):
        path = os.path.join(tempfile.gettempdir(), canarysend.ABSENT_LEDGER)
        self.assertFalse(os.path.exists(path),
                         "%s exists, so that control is vacuous"
                         % canarysend.ABSENT_LEDGER)


class UnaccountedCanActuallyFire(unittest.TestCase):
    """The counter the brief calls the one that matters."""

    def test_a_state_this_page_cannot_classify_is_unknown(self):
        outcome, why = canarysend.classify(canarysend.PLANTED_UNCLASSIFIABLE)
        self.assertEqual(outcome, canarysend.UNKNOWN)
        self.assertTrue(why)

    def test_it_is_counted_as_attempted_and_as_unaccounted(self):
        """Both, and that is the point: a row the page cannot classify must
        stay in the denominator. Dropping it is how a dashboard reports
        100% sent."""
        tally = canarysend.counters(
            [{"outcome": canarysend.UNKNOWN, "why": "x"}])
        self.assertEqual(tally["attempted"], 1)
        self.assertEqual(tally["sent"], 0)
        self.assertEqual(tally["refused"], 0)
        self.assertEqual(tally["unaccounted"], 1)
        self.assertTrue(tally["has_unaccounted"])

    def test_attempted_is_not_sent_plus_refused_by_construction(self):
        """If it were, `unaccounted` could never be non-zero and this whole
        counter would be the page reporting its own arithmetic."""
        tally = canarysend.counters([
            {"outcome": canarysend.SENT, "why": "a"},
            {"outcome": canarysend.REFUSED, "why": "b"},
            {"outcome": canarysend.UNKNOWN, "why": "c"}])
        self.assertEqual(tally["attempted"], 3)
        self.assertNotEqual(tally["attempted"],
                            tally["sent"] + tally["refused"])
        self.assertEqual(tally["unaccounted"], 1)

    def test_no_unaccounted_rows_means_the_warning_is_down(self):
        """A warning that is always on is a warning nobody reads."""
        tally = canarysend.counters([{"outcome": canarysend.SENT, "why": "a"}])
        self.assertEqual(tally["unaccounted"], 0)
        self.assertFalse(tally["has_unaccounted"])

    def test_a_new_touch_state_added_upstream_surfaces_as_unaccounted(self):
        """The realistic version: `touch` grows a state and nobody tells
        this page. It must alarm, not absorb it."""
        self.assertNotIn("quarantined", touch.STATES)
        outcome, why = canarysend.classify("quarantined")
        self.assertEqual(outcome, canarysend.UNKNOWN)
        self.assertIn("quarantined", why)

    def test_the_three_sets_partition_every_state_touch_defines(self):
        """Why this is the most useful test in the file.

        A mutation that made an in-vocabulary-but-unclassified state return
        "not attempted" instead of UNKNOWN SURVIVED, and the reason was not
        a weak assertion: `NOT_YET`, `SENT_STATES` and `REFUSED_STATES`
        exactly cover `touch.STATES`, so that branch is unreachable today
        and no input could kill the mutant.

        It is still the right forward guard - it fires the day somebody adds
        a state upstream. This test is the early warning that goes with it:
        the moment `touch.STATES` grows a thirteenth entry, this fails and
        names it, which is more useful than discovering it on the page.
        """
        covered = (set(canarysend.NOT_YET) | set(canarysend.SENT_STATES)
                   | set(canarysend.REFUSED_STATES))
        self.assertEqual(
            set(touch.STATES) - covered, set(),
            "a touch state this page does not classify. Put it in one of "
            "the three sets - it will otherwise render UNKNOWN and land in "
            "`unaccounted`, which is safe but is an alarm nobody can clear")
        self.assertEqual(
            covered - set(touch.STATES), set(),
            "this page classifies a state `src.touch` no longer defines")

    def test_a_state_added_to_touch_without_telling_this_page_is_unknown(self):
        """The branch the partition above makes unreachable, reached.

        Patching `touch.STATES` is the honest way to exercise it: it is
        exactly the scenario the branch exists for - a state added upstream
        that this page has not been taught - and without this the guard is
        code nothing can execute.
        """
        added = "quarantined_upstream"
        self.assertNotIn(added, touch.STATES)
        real = touch.STATES
        touch.STATES = tuple(real) + (added,)
        self.addCleanup(setattr, touch, "STATES", real)
        outcome, why = canarysend.classify(added)
        self.assertEqual(outcome, canarysend.UNKNOWN,
                         "a state in the vocabulary that this page cannot "
                         "classify must be UNKNOWN, never dropped as "
                         "'not attempted'")
        self.assertIn(added, why)
        self.assertIn("UNACCOUNTED", why)

    def test_every_state_touch_defines_is_classified_or_alarms(self):
        """A total function over the canonical vocabulary. No state falls
        through to an implicit None."""
        for state in touch.STATES:
            outcome, why = canarysend.classify(state)
            self.assertIn(outcome, (None, canarysend.SENT,
                                    canarysend.REFUSED, canarysend.UNKNOWN),
                          state)
            self.assertTrue(why, state)


class NotYetIsNotAnAttempt(unittest.TestCase):
    """`planned` and `sent` being the same word is how a system starts
    claiming things it did not do - `src.touch`'s own words."""

    def test_a_planned_step_is_not_attempted(self):
        self.assertIsNone(canarysend.classify(touch.PLANNED)[0])

    def test_a_built_payload_is_not_attempted(self):
        """`push_prepared` is the important omission, per `touch`."""
        self.assertIsNone(canarysend.classify(touch.PAYLOAD_READY)[0])

    def test_an_approved_step_is_not_attempted(self):
        self.assertIsNone(canarysend.classify(touch.APPROVED)[0])

    def test_a_planned_step_produces_no_row(self):
        rows, cohort, _ = canarysend.rows_for([record()], now=NOW, timelines=TIMELINE)
        self.assertEqual(rows, [])
        self.assertEqual(cohort, 1,
                         "the contact is still in the cohort - only the "
                         "step is not an attempt")

    def test_the_three_not_yet_states_are_named_not_inferred(self):
        self.assertEqual(canarysend.NOT_YET,
                         frozenset({touch.PLANNED, touch.APPROVED,
                                    touch.PAYLOAD_READY}))


class ARefusalIsAnEventWhoseAnswerWasNo(unittest.TestCase):

    def test_each_refusing_state_classifies_as_refused(self):
        for state in canarysend.REFUSED_STATES:
            outcome, why = canarysend.classify(state)
            self.assertEqual(outcome, canarysend.REFUSED, state)
            self.assertTrue(why, state)

    def test_the_five_refusals_are_not_flattened_to_one_word(self):
        """`held pending review` and `the transport raised` are not the
        same row, and an operator acts differently on each."""
        reasons = {canarysend.classify(state)[1]
                   for state in canarysend.REFUSED_STATES}
        self.assertEqual(len(reasons), len(canarysend.REFUSED_STATES))

    def test_refusals_are_grouped_by_reason_with_counts(self):
        tally = canarysend.counters([
            {"outcome": canarysend.REFUSED, "why": "a gate refused"},
            {"outcome": canarysend.REFUSED, "why": "a gate refused"},
            {"outcome": canarysend.REFUSED, "why": "held"}])
        self.assertEqual(tally["refused_by_reason"],
                         {"a gate refused": 2, "held": 1})

    def test_sent_states_come_from_touch_rather_than_being_relisted(self):
        """A second list of what "reached them" means is how the two
        definitions come to disagree."""
        self.assertEqual(canarysend.SENT_STATES,
                         frozenset(touch.CONFIRMED_STATES))


class ARefusalBlindReadIsNotPresentedAsCompleteOne(unittest.TestCase):
    """The measurement that reshaped this module, and it is not theoretical.

    `BLOCKED`, `HELD` and `PAUSED` are produced by `touch._planned_state`
    from the TIMELINE's `status`. An event-derived step is given
    `status: "historical"`, which maps to PLANNED. So a history built with no
    timeline can show confirmed sends and NOT ONE REFUSAL - the page would
    read `1 sent, 0 refused` and look perfect while every refusal was
    structurally invisible. That is the instrument-sees-nothing defect this
    page exists to avoid, reappearing inside the page itself.
    """

    def test_a_refusal_is_only_visible_through_the_timeline(self):
        """The premise, measured rather than asserted. Same record, same
        events, two timelines - and only one of them can see the refusal."""
        rec = record()
        with_plan, _, _ = canarysend.rows_for(
            [rec], now=NOW, timelines=timeline_with("blocked"))
        self.assertEqual([r["outcome"] for r in with_plan],
                         [canarysend.REFUSED])
        without, _, _ = canarysend.rows_for([rec], now=NOW,
                                            timelines={"rec-1": {"k1": {}}})
        self.assertEqual(without, [],
                         "with no timeline the refusal does not appear at "
                         "all - which is why it may not be counted as zero")

    def test_a_record_whose_timeline_cannot_be_built_is_named(self):
        """No client on the record, so `cadence.build` raises. The failure
        is carried out by type and message, never swallowed."""
        rows, _cohort, blind = canarysend.rows_for([record()], now=NOW)
        self.assertEqual(len(blind), 1)
        self.assertEqual(blind[0]["record_id"], "rec-1")
        self.assertTrue(blind[0]["why"])
        self.assertIn("ConfigError", blind[0]["why"])
        self.assertEqual(rows, [])

    def test_a_blind_record_makes_the_refusal_count_unknown(self):
        """An undercount presented as a count is the defect. UNKNOWN, and
        never 0 - a zero here reads as "nothing refused"."""
        data = canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW)
        self.assertTrue(data["blind"])
        self.assertIsNone(data["counters"]["refused"])
        self.assertIsNone(data["counters"]["unaccounted"])
        self.assertFalse(data["counters"]["refusals_visible"])

    def test_a_confirmed_send_is_still_sound_when_refusals_are_blind(self):
        """A send is established by an event and does not depend on the
        plan, so it is NOT thrown away - only the refusal count is."""
        data = canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW)
        self.assertEqual(data["counters"]["sent"], 1)
        self.assertEqual(data["counters"]["attempted"], 1)

    def test_the_floor_is_still_reported_beside_the_unknown(self):
        """What was actually seen is shown as `refused_at_least`, so the
        UNKNOWN does not destroy the information it qualifies."""
        data = canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW)
        self.assertEqual(data["counters"]["refused_at_least"], 0)

    def test_the_alarm_is_raised_while_any_record_is_blind(self):
        data = canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW)
        self.assertTrue(data["counters"]["has_unaccounted"])

    def test_nothing_is_blind_when_every_timeline_is_supplied(self):
        data = canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW, timelines=TIMELINE)
        self.assertEqual(data["blind"], [])
        self.assertTrue(data["counters"]["refusals_visible"])
        self.assertEqual(data["counters"]["refused"], 0)

    def test_each_refusing_cadence_status_renders_as_refused(self):
        for status in ("blocked", "waiting", "paused"):
            rows, _, _ = canarysend.rows_for(
                [record()], now=NOW, timelines=timeline_with(status))
            self.assertEqual([r["outcome"] for r in rows],
                             [canarysend.REFUSED], status)


class TheRefusalLedgerIsVerbLevel(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rga-canary-ledger-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, "provider-writes.jsonl")

    def write(self, *rows):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def test_an_absent_ledger_is_absent_and_not_empty(self):
        """Four kinds of nothing, kept apart. An unreadable ledger must not
        read as "nothing was refused"."""
        found = canarysend.campaign_refusals(path=self.path)
        self.assertEqual(found["state"], canarysend.LEDGER_ABSENT)
        self.assertEqual(found["total"], 0)

    def test_a_directory_where_the_ledger_belongs_is_unreadable(self):
        os.makedirs(self.path)
        found = canarysend.campaign_refusals(path=self.path)
        self.assertEqual(found["state"], canarysend.LEDGER_UNREADABLE)

    def test_an_empty_ledger_is_empty_and_not_absent(self):
        self.write()
        self.assertEqual(canarysend.campaign_refusals(path=self.path)["state"],
                         canarysend.LEDGER_EMPTY)

    def test_a_refusal_is_found_and_grouped_by_campaign(self):
        self.write({"at": "2026-10-16T08:00:00Z", "outcome": "refused",
                    "operation": "bison.resume_campaign", "campaign": "487",
                    "tenant": "productive", "detail": "killswitch"})
        found = canarysend.campaign_refusals(path=self.path,
                                             tenant="productive")
        self.assertEqual(found["total"], 1)
        self.assertEqual(found["by_campaign"]["487"][0]["operation"],
                         "bison.resume_campaign")

    def test_a_non_refusal_outcome_is_not_counted_as_a_refusal(self):
        self.write({"at": "2026-10-16T08:00:00Z", "outcome": "accepted",
                    "operation": "bison.pause", "campaign": "487",
                    "tenant": "productive"})
        self.assertEqual(
            canarysend.campaign_refusals(path=self.path,
                                         tenant="productive")["total"], 0)

    def test_another_tenants_refusal_is_not_shown(self):
        self.write({"at": "2026-10-16T08:00:00Z", "outcome": "refused",
                    "operation": "bison.pause", "campaign": "327",
                    "tenant": "someone-else"})
        self.assertEqual(
            canarysend.campaign_refusals(path=self.path,
                                         tenant="productive")["total"], 0)

    def test_a_truncated_final_line_is_counted_not_skipped_silently(self):
        """Normal for an append-only file mid-write. Counted, and shown."""
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"outcome": "refused", "campaign": "1",
                                     "tenant": "productive"}) + "\n")
            handle.write('{"outcome": "refu')
        found = canarysend.campaign_refusals(path=self.path,
                                             tenant="productive")
        self.assertEqual(found["damaged"], 1)
        self.assertEqual(found["total"], 1)


class AFailedControlMakesEveryCountUnknown(unittest.TestCase):

    def _break_a_control(self, name):
        real = canarysend.controls

        def broken(now=None):
            results = real(now=now)
            for check in results:
                if check["name"] == name:
                    check["ok"] = False
                    check["detail"] = "forced by a test"
            return results

        canarysend.controls = broken
        self.addCleanup(setattr, canarysend, "controls", real)

    def report(self):
        return canarysend.report([record(event_list=[sent_event()])],
                                 now=NOW, timelines=TIMELINE,
                                 ledger_path=os.path.join(
                                     tempfile.gettempdir(),
                                     canarysend.ABSENT_LEDGER))

    def test_the_counts_are_unknown_and_not_zero(self):
        """None, never 0. A zero on this page reads as "nothing went out",
        which is the most dangerous wrong answer it could give."""
        self.assertEqual(self.report()["counters"]["sent"], 1)
        self._break_a_control("an_unclassifiable_row_lands_in_unaccounted")
        tally = self.report()["counters"]
        for key in ("attempted", "sent", "refused", "unaccounted"):
            self.assertIsNone(tally[key], key)

    def test_every_rows_outcome_becomes_unknown(self):
        self._break_a_control("a_planted_refusal_is_refused_with_its_reason")
        for row in self.report()["rows"]:
            self.assertEqual(row["outcome"], canarysend.UNKNOWN)

    def test_the_recorded_state_is_still_shown_verbatim(self):
        """What is untrusted is the reader, not the event log."""
        self._break_a_control("an_unreadable_ledger_is_unknown_not_zero")
        self.assertEqual(self.report()["rows"][0]["state"], touch.SENT)

    def test_the_alarm_stays_raised_rather_than_going_quiet(self):
        """`unaccounted` has just been set to UNKNOWN, so the flag it drove
        must not fall back to False and silence the banner."""
        self._break_a_control("an_unreadable_ledger_is_unknown_not_zero")
        self.assertTrue(self.report()["counters"]["has_unaccounted"])

    def test_the_report_names_the_control_that_failed(self):
        self._break_a_control("an_unreadable_ledger_is_unknown_not_zero")
        data = self.report()
        self.assertFalse(data["controls_ok"])
        self.assertIn("an_unreadable_ledger_is_unknown_not_zero",
                      data["poison"])


class TheDenominatorsAreVisibleAndNeverInvented(unittest.TestCase):

    def test_the_approved_cohort_is_unknown_when_nobody_supplied_it(self):
        """Its authority is the approval sheet, outside this repository."""
        tally = canarysend.counters([{"outcome": canarysend.SENT, "why": "a"}])
        self.assertIsNone(tally["approved_cohort"])

    def test_it_is_never_defaulted_to_the_number_of_rows_found(self):
        """Which would make the figure agree with itself whatever happened -
        a hand-kept denominator, the pattern this lane has refused once."""
        rows = [{"outcome": canarysend.SENT, "why": "a"} for _ in range(4)]
        self.assertIsNone(canarysend.counters(rows)["approved_cohort"])

    def test_a_supplied_cohort_size_is_used(self):
        tally = canarysend.counters([{"outcome": canarysend.SENT, "why": "a"}],
                                    approved_cohort=23)
        self.assertEqual(tally["approved_cohort"], 23)

    def test_the_cohort_touched_counts_contacts_not_steps(self):
        rec = record(event_list=[sent_event(step="em1"),
                                 sent_event(step="em2")])
        rows, cohort, _ = canarysend.rows_for([rec], now=NOW, timelines=TIMELINE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(cohort, 1)

    def test_an_unselected_contact_is_not_in_the_cohort(self):
        rec = record(selected=False, event_list=[sent_event()])
        rows, cohort, _ = canarysend.rows_for([rec], now=NOW, timelines=TIMELINE)
        self.assertEqual(rows, [])
        self.assertEqual(cohort, 0)

    def test_every_figure_names_where_it_came_from(self):
        data = canarysend.report([record(event_list=[sent_event()])], now=NOW,
                              timelines=TIMELINE)
        self.assertTrue(data["authorities"])
        for entry in data["authorities"]:
            self.assertTrue(entry["figure"])
            self.assertTrue(entry["source"])
            self.assertTrue(entry["why"])


class TheAgeIsTheEventsAndNotTheRenders(unittest.TestCase):

    def test_the_age_comes_from_the_event_stamp(self):
        rows, _, _ = canarysend.rows_for([record(event_list=[sent_event()])],
                                      now=NOW, timelines=TIMELINE)
        self.assertEqual(rows[0]["age_seconds"], 1800)

    def test_a_stamp_that_cannot_be_parsed_is_none_and_never_zero(self):
        """A zero here reads as "just now", the most misleading possible
        answer about something that may have reached a person."""
        rows, _, _ = canarysend.rows_for(
            [record(event_list=[sent_event(at="whenever")])], now=NOW,
            timelines=TIMELINE)
        self.assertIsNone(rows[0]["age_seconds"])

    def test_a_stamp_in_the_future_is_none_rather_than_negative(self):
        rows, _, _ = canarysend.rows_for(
            [record(event_list=[sent_event(at="2026-12-01T00:00:00Z")])],
            now=NOW, timelines=TIMELINE)
        self.assertIsNone(rows[0]["age_seconds"])

    def test_rows_are_newest_first(self):
        rec = record(event_list=[
            sent_event(step="em1", at="2026-10-16T07:00:00Z"),
            sent_event(step="em2", at="2026-10-16T08:00:00Z")])
        rows, _, _ = canarysend.rows_for([rec], now=NOW, timelines=TIMELINE)
        self.assertEqual([r["step"] for r in rows], ["em2", "em1"])


class ItReadsAndWritesNothingElse(unittest.TestCase):

    def test_it_writes_no_file(self):
        place = tempfile.mkdtemp(prefix="rga-canary-write-")
        self.addCleanup(shutil.rmtree, place, ignore_errors=True)
        canarysend.report([record(event_list=[sent_event()])], now=NOW,
                          timelines=TIMELINE,
                          ledger_path=os.path.join(place, "ledger.jsonl"))
        self.assertEqual(os.listdir(place), [])

    def test_it_opens_no_socket(self):
        real = socket.socket

        def refuse(*a, **k):
            raise AssertionError("the canary send reader opened a socket")

        socket.socket = refuse
        self.addCleanup(setattr, socket, "socket", real)
        rows, _, _ = canarysend.rows_for([record(event_list=[sent_event()])],
                                      now=NOW, timelines=TIMELINE)
        self.assertEqual(rows[0]["outcome"], canarysend.SENT)

    def test_the_page_says_what_it_cannot_see(self):
        """One sentence, in the data rather than in a docstring, so nobody
        mistakes a clean screen for a clean send."""
        data = canarysend.report([], now=NOW, timelines=TIMELINE)
        self.assertIn("bounced", data["cannot_see"])
        self.assertIn("not a clean send", data["cannot_see"])

    def test_describe_runs_and_names_the_controls(self):
        text = canarysend.describe(
            canarysend.report([record(event_list=[sent_event()])], now=NOW,
                              timelines=TIMELINE))
        for check in canarysend.controls(now=NOW):
            self.assertIn(check["name"], text)
        self.assertIn("PASS", text)

    def test_describe_prints_unknown_rather_than_none(self):
        data = canarysend.report([record(event_list=[sent_event()])], now=NOW,
                              timelines=TIMELINE)
        data["counters"]["attempted"] = None
        self.assertIn("UNKNOWN", canarysend.describe(data))
        self.assertNotIn("None", canarysend.describe(data))


class ThePage(WebTest):
    """Served over real HTTP, by the real handler, through the real gate.

    The demo estate supplies the records, so nothing here writes a prospect
    address anywhere - the addresses on screen are the demo engine's own
    fictional ones.
    """

    def test_a_contact_viewer_gets_the_page(self):
        status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("Canary send log", body)

    def test_the_client_facing_viewer_is_refused(self):
        """The one role this gate actually excludes, measured rather than
        assumed. `_REVIEWER` grants `contacts.view` and `operations.view`
        together, so choosing between those two excludes nobody; VIEWER
        holds neither, and a client-facing role must not read a list of who
        was mailed from which mailbox."""
        status, body, _ = self.signin(VIEWER).get(PATH)
        self.assertNotEqual(status, 200)
        self.assertNotIn("Sender used", body)

    def test_a_reviewer_does_get_it_and_that_is_not_an_accident(self):
        """Recorded so nobody later reads the gate as narrower than it is."""
        status, _body, _ = self.signin(REVIEWER).get(PATH)
        self.assertEqual(status, 200)

    def test_the_two_candidate_permissions_reach_the_same_roles(self):
        """The measurement behind the comment on the route."""
        from src import workspaces as ws
        for role in (ws.REVIEWER, ws.OPERATOR, ws.WORKSPACE_ADMIN):
            self.assertEqual(ws.may(role, ws.CONTACTS_VIEW),
                             ws.may(role, ws.OPERATIONS_VIEW), role)
        self.assertFalse(ws.may(ws.VIEWER, ws.CONTACTS_VIEW))

    def test_an_anonymous_caller_is_never_served_the_page(self):
        status, body, _ = self.anonymous().get(PATH)
        self.assertIn(status, (200, 303))
        self.assertNotIn("Sender used", body)
        self.assertIn("Sign in", body)

    def test_the_route_is_gated_by_contacts_view(self):
        """Asserted on the table rather than on the handler, because the
        table runs BEFORE the handler and cannot be forgotten."""
        self.assertEqual(permission_for(PATH), "contacts.view")

    def test_the_navigation_entry_matches_that_permission(self):
        found = [entry for _k, _t, _h, items in pages.SECTIONS
                 for entry in items if entry[0] == PATH]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], "contacts.view")

    def test_a_POST_is_not_accepted(self):
        session = self.signin(ADMIN)
        status, _body, _ = session.post(PATH, {"csrf": session.csrf()})
        self.assertNotEqual(status, 200)

    def test_the_seven_columns_are_on_the_page(self):
        _status, body, _ = self.signin(ADMIN).get(PATH)
        for column in ("When", "Address", "Channel", "Campaign", "Step",
                       "Sender used", "Outcome"):
            self.assertIn("<th>" + column + "</th>", body)

    def test_the_four_counters_are_on_the_page(self):
        _status, body, _ = self.signin(ADMIN).get(PATH)
        for counter in ("attempted", "sent", "refused", "unaccounted"):
            self.assertIn(">" + counter + "<", body)

    def test_the_three_controls_are_on_the_page_with_pass_or_fail(self):
        _status, body, _ = self.signin(ADMIN).get(PATH)
        for check in canarysend.controls():
            self.assertIn(check["name"], body)
        self.assertIn("PASS", body)

    def test_the_page_says_what_it_cannot_see(self):
        """One sentence, on the page, so nobody mistakes a clean screen for
        a clean send."""
        _status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertIn(pages.esc("not a clean send"), body)

    def test_every_verdict_label_the_reader_can_produce_is_rendered(self):
        _status, body, _ = self.signin(ADMIN).get(PATH)
        for label, _why in canarysend.OUTCOME_TEXT.values():
            self.assertIn(label, body)

    def test_the_approved_cohort_denominator_renders_as_unknown(self):
        """Its authority is the approval sheet, outside this repository. It
        is shown as UNKNOWN rather than quietly omitted."""
        _status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertIn(pages.esc("of UNKNOWN approved cohort"), body)


if __name__ == "__main__":
    unittest.main()
