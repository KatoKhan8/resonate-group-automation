#!/usr/bin/env python3
"""Five provider steps, five sets of approved words, and no empty one.

A one-step campaign can carry the generated copy in a single pair of custom
variables, because a variable holds one value per lead. Five steps cannot,
and the failure when they try is the quiet kind this repository keeps
finding: the campaign is created, the sequence reads back with five steps,
the schedule is right, the sender is bound, the membership is right - and on
day eight a real person receives an email with no subject and no body.

So there are two claims here and the second is the one that matters.

  1. The sequence written to EmailBison reproduces the cadence. Five steps
     in cadence order, each carrying the gap to the next as `wait_in_days`.

  2. A contact who cannot fill every one of those steps is never staged, and
     a dry run says which contact and which step without refusing, so the
     answer to "what is missing" is one command rather than five.

WHAT `wait_in_days` MEANS was measured, not assumed - see the note above
`_sequence_steps`. It is the wait AFTER the step that declares it, read off
381 discriminating scheduled-email pairs on the client's own live campaign
352 on 2026-09-13.

THE SHAPE OF THE FIVE STEPS CHANGED ON 2026-09-16 AND THIS MODULE HAD NOT
FOLLOWED. It declared five steps each owning its own `{SUBJECT_n}` and none
of them a thread reply - the pre-2026-09-16 shape - so every test in it hit
the threading guard in `_sequence_steps` instead of the property it was
written to assert. The guard was right and the fixture was wrong.

THE INVARIANT THE FIXTURE NOW ENCODES: only the opener owns a subject.

    em1   NEW EMAIL   thread_reply false, subject `{SUBJECT_1}`, body_1
    em2   FOLLOW-UP   thread_reply TRUE,  subject `{SUBJECT_1}`, body_2
    em3   FOLLOW-UP   thread_reply TRUE,  subject `{SUBJECT_1}`, body_3
    em4   FOLLOW-UP   thread_reply TRUE,  subject `{SUBJECT_1}`, body_4
    em5   FOLLOW-UP   thread_reply TRUE,  subject `{SUBJECT_1}`, body_5

There is exactly ONE subject variable per lead. No `subject_2`..`subject_5`
is generated, approved, or sent - the provider's own thread-reply mechanism
continues the thread and prepends "Re:" itself, measured by TASK-159 across
153 follow-ups, so nothing here writes a "Re:" of its own. Five DISTINCT
BODIES is still the claim; five distinct subjects never was.

FIVE IS NOT SPECIAL AND NEITHER IS THREE. Three steps is the production-safe
CONTROL, not evidence that three touches is optimal; the number of touches is
a parameter this engine has to hold at whatever value a future campaign picks.
`tests/test_a_threaded_sequence_is_threaded_at_every_length.py` is the proof
that the invariant does not depend on the length, and names the two lengths
at which the engine does not yet hold it.
"""
import unittest

from src import (bisonfactory, cadence, cadencelibrary, campaigns, store,
                 workspaces)
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

CID = "camp-five-step"

# The email half of `productive_li_heavy_v1`: days 1, 4, 8, 12 and 21, so the
# gaps are 3, 4, 4 and 9. Written out here rather than computed, because a
# test that derives its expectation the same way the code does agrees with
# the code unconditionally.
WAITS = (3, 4, 4, 9)

# THE OPENER'S SUBJECT, AND THERE IS NO OTHER ONE. Every step references
# `{SUBJECT_1}`; the opener sends it, and the follow-ups are thread replies
# so the provider continues the original thread. Written out five times
# rather than looped, because the thing being asserted is that all five
# strings are the SAME string.
OPENER_SUBJECT = "{SUBJECT_1}"

# The last wait is 1, NOT 0. `wait_in_days` is the gap until the next step,
# so on the final step nothing reads it - but 0 is not inert at the provider:
# campaign 485 was created and `set_sequence` raised, leaving it at 0 steps.
# Both shipped client files carry 1 on their last step for this reason.
FINAL_WAIT = 1

SEQUENCE_CONFIG = {
    "title": "Resonate generated cadence",
    # One opener and four follow-ups. The pattern is per-position in cadence
    # order and it is what makes steps 2-5 thread replies rather than five
    # cold opens - the ladder's own default for this cadence is
    # (False, True, False, True, False), which would put steps 3 and 5 back
    # in the shape the invariant forbids.
    "thread_reply_pattern": [False, True, True, True, True],
    "steps": {
        "em1": {"order": 1, "subject": OPENER_SUBJECT,
                "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
        "em2": {"order": 2, "subject": OPENER_SUBJECT,
                "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
        "em3": {"order": 3, "subject": OPENER_SUBJECT,
                "body": "<p>{BODY_3}</p>", "wait_in_days": 4},
        "em4": {"order": 4, "subject": OPENER_SUBJECT,
                "body": "<p>{BODY_4}</p>", "wait_in_days": 9},
        "em5": {"order": 5, "subject": OPENER_SUBJECT,
                "body": "<p>{BODY_5}</p>", "wait_in_days": FINAL_WAIT},
    },
}

CONFIG = {
    "cadence": "productive_li_heavy_v1",
    "email_sequence": SEQUENCE_CONFIG,
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}


def approved(step_key, n):
    """One approved step, stamped over the words it is about to ship.

    THE STAMP COVERS THE WORDS. A literal `fp-{n}` was enough while staging
    checked only that an approval EXISTED; `bisonfactory._certified_copy`
    hashes the words it is about to stage and compares, so a stamp that
    covers nothing is refused - which is the point of the stamp.
    """
    from src import approval as _approval

    step = {"channel": "email",
            "subject": f"subject for {step_key}",
            "body": f"<p>body for {step_key}</p>"}
    step["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                        "fingerprint": _approval.fingerprint(step)}
    return step


def record(rid, email, first, keys=("em1", "em2", "em3", "em4", "em5")):
    key = f"{rid}-c1"
    steps = {k: approved(k, i) for i, k in enumerate(keys, start=1)}
    return {"id": rid, "client": "productive", "domain": "example.com",
            "company": "Example", "state": "ready",
            "cadence": {key: steps},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True}]}


class TheSequenceReproducesTheCadence(unittest.TestCase):
    """`_sequence_steps` alone, with no estate and no provider."""

    def steps(self, configured=None):
        return bisonfactory._sequence_steps(
            configured or SEQUENCE_CONFIG,
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)

    def test_five_steps_in_cadence_order(self):
        steps = self.steps()
        self.assertEqual([s["order"] for s in steps], [1, 2, 3, 4, 5])
        self.assertEqual([s["step_key"] for s in steps],
                         ["em1", "em2", "em3", "em4", "em5"])

    def test_each_step_waits_the_gap_to_the_next_one(self):
        """Four gaps for five steps. The fifth wait has no successor."""
        steps = self.steps()
        self.assertEqual(tuple(s["wait_in_days"] for s in steps[:-1]), WAITS)

    def test_the_last_wait_is_not_zero(self):
        """Inert is not the same as accepted. 485 was created with 0 steps."""
        steps = self.steps()
        self.assertNotEqual(steps[-1]["wait_in_days"], 0)
        self.assertEqual(steps[-1]["wait_in_days"], FINAL_WAIT)

    def test_only_the_opener_owns_a_subject(self):
        """Five steps, one subject. `{SUBJECT_2}`..`{SUBJECT_5}` never exist.

        Not "the follow-ups carry no subject" - they carry one, because the
        flag is the mechanism and the provider stores the field either way.
        They carry the OPENER'S subject, so there is exactly one subject
        variable per lead and nothing numbered past the first to generate,
        approve or accidentally send.
        """
        steps = self.steps()
        self.assertEqual([s["email_subject"] for s in steps],
                         [OPENER_SUBJECT] * 5)
        self.assertEqual({s["email_subject"] for s in steps},
                         {OPENER_SUBJECT})
        for n in range(2, 6):
            for step in steps:
                self.assertNotIn(f"{{SUBJECT_{n}}}", step["email_subject"])

    def test_every_step_after_the_opener_is_a_thread_reply(self):
        """The opener opens; the other four continue what it opened."""
        steps = self.steps()
        self.assertFalse(steps[0]["thread_reply"])
        self.assertEqual([s["thread_reply"] for s in steps[1:]], [True] * 4)

    def test_nothing_here_writes_its_own_re_prefix(self):
        """EmailBison prepends "Re:" itself - TASK-159, 153 follow-ups.

        A hand-built "Re:" chain is simulated threading, and the read-back
        comparator would call the provider's own prefix drift forever.
        """
        for step in self.steps():
            self.assertFalse(step["email_subject"].lower().startswith("re:"),
                             f"step {step['order']} writes its own Re:")

    def test_each_step_carries_its_own_numbered_body(self):
        """Five distinct bodies is the claim. Five subjects never was."""
        steps = self.steps()
        for n, step in enumerate(steps, start=1):
            self.assertIn(f"{{BODY_{n}}}", step["email_body"])
        self.assertEqual(len({s["email_body"] for s in steps}), 5)

    def test_a_declared_delay_that_contradicts_the_cadence_is_refused(self):
        """The delay is declared, so the check is what makes it true."""
        for key, wrong in (("em1", 2), ("em2", 5), ("em4", 8)):
            with self.subTest(step=key):
                broken = dict(SEQUENCE_CONFIG)
                broken["steps"] = {k: dict(v)
                                   for k, v in SEQUENCE_CONFIG["steps"].items()}
                broken["steps"][key]["wait_in_days"] = wrong
                with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                    self.steps(broken)
                self.assertIn(key, str(caught.exception))

    def test_a_step_the_cadence_does_not_have_is_refused(self):
        """The key is how a delay is matched to the gap it claims to be."""
        broken = dict(SEQUENCE_CONFIG)
        broken["steps"] = {k: dict(v)
                           for k, v in SEQUENCE_CONFIG["steps"].items()}
        broken["steps"]["em6"] = broken["steps"].pop("em5")
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.steps(broken)
        self.assertIn("em6", str(caught.exception))

    def test_a_missing_cadence_step_is_refused(self):
        """Four declared steps against five email days is not a subset."""
        broken = dict(SEQUENCE_CONFIG)
        broken["steps"] = {k: dict(v)
                           for k, v in SEQUENCE_CONFIG["steps"].items()
                           if k != "em3"}
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.steps(broken)

    def test_a_step_with_no_declared_wait_is_refused(self):
        """"Nobody chose" must not look the same as a chosen delay."""
        broken = dict(SEQUENCE_CONFIG)
        broken["steps"] = {k: dict(v)
                           for k, v in SEQUENCE_CONFIG["steps"].items()}
        del broken["steps"]["em3"]["wait_in_days"]
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.steps(broken)
        self.assertIn("wait_in_days", str(caught.exception))

    def test_the_single_step_shape_still_works(self):
        """Campaign 451 is staged against it and has a scheduled send."""
        steps = self.steps({"subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                            "wait_in_days": 3})
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["email_subject"], "{SUBJECT}")
        self.assertNotIn("step_key", steps[0])

    def test_a_cadence_longer_than_the_declared_variables_is_refused(self):
        """Step seven would send with nothing in it, and read back correct."""
        from src.providers import bison as real

        long_cadence = tuple(
            {"key": f"em{n}", "day": n * 2, "channel": "email"}
            for n in range(1, real.MAX_SEQUENCE_STEPS + 2))
        block = {f"em{n}": {"order": n, "subject": f"{{SUBJECT_{n}}}",
                            "body": f"<p>{{BODY_{n}}}</p>", "wait_in_days": 2}
                 for n in range(1, real.MAX_SEQUENCE_STEPS + 2)}
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._sequence_steps({"steps": block}, long_cadence)
        self.assertIn("MAX_SEQUENCE_STEPS", str(caught.exception))


# The CONTROL cadence the live campaign runs: FIVE email touches on days
# 1, 4, 8, 12 and 21 - the CLIENT'S OWN LADDER, the same one
# `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1` declares - so the gaps are 3, 4, 4
# and 9. Written out
# here rather than read off the campaign row, for two reasons. A test must not
# read live client state, and a test that derives its expectation the same way
# the code does agrees with the code unconditionally - the point of writing
# the days down is that `productive.yaml`'s declared waits are checked
# AGAINST them.
#
# THE KEYS ARE NOT em1..em4. `breakup` (em3) was retired and em4/em5 kept the
# names their approved copy was written under, because a step key is identity
# - approvals are fingerprinted per key. So the keys and the days are listed
# as PAIRS rather than generated from a counter, which is what the previous
# `f"em{n}"` did and what would quietly rename two steps here.
CONTROL_STEPS = (("em1", 1), ("em2", 4), ("em3", 8), ("em4", 12),
                 ("em5", 21))
CONTROL_KEYS = [key for key, _day in CONTROL_STEPS]
CONTROL_DAYS = tuple(day for _key, day in CONTROL_STEPS)
CONTROL_CADENCE = tuple(
    {"key": key, "day": day, "channel": "email", "generated": True}
    for key, day in CONTROL_STEPS)
CONTROL_WAITS = (3, 4, 4, 9)


class TheShippedConfigurationAgreesWithTheShippedCadence(unittest.TestCase):
    """The config Productive actually runs, against the cadence it runs it on.

    Everything above tests the checker with fixtures. This tests the real
    file, which is the half that drifts: `email_sequence` lives in
    `config/clients/productive.yaml` and the cadence lives either in
    `src/cadencelibrary.py` or on the campaign row, and editing one without
    the other is how a campaign ends up sending on a schedule nobody
    described.

    WHAT CHANGED ON 2026-09-16 AND WHY THIS CLASS LOOKS DIFFERENT. This class
    used to assert that `productive.yaml` builds FIVE steps against the
    library cadence its `cadence:` line names. It does not any more, and that
    is deliberate rather than drift: the operator approved a three-step
    CONTROL, `email_sequence` was cut to em1-em3, and the three-step cadence
    travels on the campaign row as `cadence_steps` - which is how
    `cadence.steps_for` resolves it in production. The client-level pair no
    longer agrees, and the last test in this class is the one that says so:
    the factory REFUSES that pair rather than staging five provider steps
    against three approved ones. It is refused for the same reason campaign
    484 was created wrong - five steps, three approvals - and refusing is the
    fix that episode earned.

    AND AGAIN, TWICE. On 2026-09-24 the CONTROL became FOUR steps - em1,
    em2, em4, em5, `breakup` retired and em3's position left EMPTY because
    rung 3 was unwritten. On 2026-09-25 rung 3 was approved and took that
    position as `em3`, making it FIVE. The other keys never moved across
    either change, which is why `CONTROL_STEPS` lists key/day pairs instead
    of generating `em{n}` from a counter: generating them would have renamed
    two steps while the gap existed and handed em4's approvals to rung 3 the
    moment it landed.

    Five steps is the production-safe CONTROL, not a claim that five is the
    right number. Nothing in this class asserts the number; it asserts that
    whatever number is declared reproduces the cadence it is checked against.
    """

    def shipped(self):
        from src import clients

        return clients.load("productive").get("email_sequence")

    def test_productive_builds_its_control_against_the_control_cadence(self):
        steps = bisonfactory._sequence_steps(self.shipped(), CONTROL_CADENCE)
        self.assertEqual([s["step_key"] for s in steps], CONTROL_KEYS)
        self.assertEqual(tuple(s["wait_in_days"] for s in steps[:-1]),
                         CONTROL_WAITS)
        self.assertNotEqual(steps[-1]["wait_in_days"], 0)

    def test_the_shipped_control_owns_exactly_one_subject(self):
        """The live sequence, read off the file the live campaign was built
        from. A template asking for `{SUBJECT_3}` while the lead carries no
        `subject_3` renders nothing, and every readback still agrees.
        """
        steps = bisonfactory._sequence_steps(self.shipped(), CONTROL_CADENCE)
        self.assertEqual({s["email_subject"] for s in steps},
                         {OPENER_SUBJECT})
        self.assertFalse(steps[0]["thread_reply"])
        self.assertTrue(all(s["thread_reply"] for s in steps[1:]))
        for step in steps:
            self.assertFalse(
                step["email_subject"].lower().startswith("re:"),
                "the provider prepends Re: itself; a hand-built one is "
                "simulated threading")
        for n, step in enumerate(steps, start=1):
            self.assertIn(f"{{BODY_{n}}}", step["email_body"])

    def test_every_merge_field_the_sequence_uses_is_declared_at_the_provider(self):
        """A variable the workspace does not hold is a 422 mid-batch."""
        from src.providers.bison import LEAD_VARIABLES

        steps = bisonfactory._sequence_steps(self.shipped(), CONTROL_CADENCE)
        # ONE subject variable, however many steps there are.
        self.assertIn("subject_1", LEAD_VARIABLES)
        for n in range(1, len(steps) + 1):
            self.assertIn(f"body_{n}", LEAD_VARIABLES)

    def test_a_campaign_with_no_cadence_of_its_own_is_refused(self):
        """The scenario this test has always been about, on its real guard.

        THE OLD MECHANISM IS GONE AND IT WAS AN ACCIDENT. Until 2026-09-25
        this asserted that `_sequence_steps(shipped, library)` RAISES,
        because the control's declared keys differed from the library's -
        four against five. Rung 3 gave the control an `em3`, and the operator
        then aligned the days to the client's own ladder so that email and
        LinkedIn run the same clock for the same prospect. Both sides are now
        `em1..em5` on 1/4/8/12/21, the refusal stopped firing, and this test
        went red with "FactoryRefused not raised". Measured, not predicted.

        That protection was never about the campaign. It fired because two
        unrelated files happened to disagree, and it evaporated the moment
        somebody made them agree for a good reason.

        SO THE SCENARIO IS UNCHANGED AND THE GUARD IS NEW. What must not
        happen is a campaign being staged against a cadence it never chose -
        campaign 484 shipped five provider steps with copy for three, and 481
        is live with its sequence already written, where `set_sequence`
        APPENDS and would have left it holding duplicates. That is now
        refused by `_plan`, on the campaign, before any cadence is resolved.

        Asserted through `_plan` - the real entry point, reached by every
        stage, dry run included - rather than by reaching into
        `_sequence_steps`.
        """
        from src import clients

        config = clients.load("productive")
        row = campaigns.new_campaign("camp-no-cadence", "productive", "No cadence")
        row["record_ids"] = []
        self.assertNotIn("cadence_steps", row)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._plan(row, [], config)
        self.assertIn("camp-no-cadence", str(caught.exception))

    def test_the_library_and_the_control_now_agree(self):
        """Recorded as a FACT, because a reader will assume otherwise.

        Every earlier version of this class rested on these two disagreeing.
        They no longer do, and that is deliberate: the client's own ladder is
        what both now describe. Stated here so the next person to read the
        class does not reintroduce a guard that cannot fire.
        """
        from src import cadence, clients

        config = clients.load("productive")
        library = cadence.steps_for({"client": "productive"}, config=config)
        email = [(s.get("key"), s.get("day")) for s in library
                 if s.get("channel") == "email"]
        self.assertEqual([k for k, _d in email],
                         ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual([d for _k, d in email], list(CONTROL_DAYS))


class TheWordsTravelWithThePerson(QueueTest):
    """The whole path, against a provider that behaves like the real one."""

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        # The workspace killswitch must be on for lead writes.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        store.save([record("rec-1", "one@example.com", "Ada"),
                    record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Five step")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=CONFIG)]
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def stage(self, **kw):
        return bisonfactory.stage(CID, config=CONFIG, live=True, **kw)

    def test_the_provider_holds_five_steps_with_the_cadence_delays(self):
        report = self.stage()
        held = self.bison.sequence_steps(report["provider"]["campaign_id"])
        self.assertEqual(len(held), 5)
        self.assertEqual([s["order"] for s in held], [1, 2, 3, 4, 5])
        self.assertEqual([s["email_subject"] for s in held],
                         [OPENER_SUBJECT] * 5)
        self.assertEqual(tuple(s["wait_in_days"] for s in held[:-1]), WAITS)
        self.assertNotEqual(held[-1]["wait_in_days"], 0)

    def test_the_provider_holds_one_opener_and_four_thread_replies(self):
        """The flag reaches the wire, not just the plan.

        The threading is the provider's mechanism, so a sequence that was
        threaded in `_sequence_steps` and arrived flat is five cold opens to
        a real person - and the read-back would agree it was correct.
        """
        report = self.stage()
        held = self.bison.sequence_steps(report["provider"]["campaign_id"])
        self.assertEqual([bool(s.get("thread_reply")) for s in held],
                         [False, True, True, True, True])

    def test_every_step_gets_its_own_words(self):
        """`{BODY_3}` resolves to the third step's approved body.

        Not to the first one's. Matching by position instead of by cadence
        key is the mistake that would put a day-twelve approval in the
        day-one slot the first time somebody approved out of order.

        The subject is not in this list because there is only one of them:
        see the test below.
        """
        self.stage()
        lead = next(iter(self.bison.leads.values()))
        held = self.bison.variables_of(lead)
        for n, key in enumerate(("em1", "em2", "em3", "em4", "em5"), start=1):
            self.assertEqual(held[f"body_{n}"], f"<p>body for {key}</p>")
        self.assertEqual(len({held[f"body_{n}"] for n in range(1, 6)}), 5)

    def test_the_lead_carries_one_subject_and_no_numbered_follow_up_one(self):
        """`subject_2`..`subject_5` are never generated for a threaded lead.

        `bison._variables` drops empty values, so they are absent rather
        than blank. The absence is the point: there is no second subject to
        approve, to send, or to leave behind on the lead when the sequence
        changes length.
        """
        self.stage()
        held = self.bison.variables_of(next(iter(self.bison.leads.values())))
        self.assertEqual(held["subject_1"], "subject for em1")
        for n in range(2, 6):
            self.assertFalse(held.get(f"subject_{n}"),
                             f"subject_{n} reached the provider with "
                             f"{held.get(f'subject_{n}')!r}")

    def test_a_multi_step_lead_carries_no_unnumbered_copy(self):
        """One shape per campaign. A variable no template reads is noise."""
        self.stage()
        held = self.bison.variables_of(next(iter(self.bison.leads.values())))
        self.assertNotIn("subject", held)
        self.assertNotIn("body", held)
        self.assertEqual(held["client"], "productive")
        self.assertTrue(held["record_id"])

    def test_a_contact_missing_one_step_stops_the_whole_run(self):
        """Four of five staged is a cohort nobody can reason about."""
        store.save([record("rec-1", "one@example.com", "Ada"),
                    record("rec-2", "two@example.com", "Grace",
                           keys=("em1", "em2", "em4", "em5"))])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        message = str(caught.exception)
        self.assertIn("em3", message)
        self.assertIn("rec-2", message)
        self.assertEqual(self.bison.created_leads, 0,
                         "a lead was created before the run was refused")

    def test_an_unapproved_step_is_missing_even_though_it_has_words(self):
        """A draft is not copy anybody blessed.

        The approval fingerprint is what `executionguard` checks a payload
        against, so shipping unapproved words would put the gate and the
        wire out of step.
        """
        drafted = record("rec-2", "two@example.com", "Grace")
        del drafted["cadence"]["rec-2-c1"]["em3"]["approval"]
        store.save([record("rec-1", "one@example.com", "Ada"), drafted])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        self.assertIn("em3", str(caught.exception))

    def test_a_dry_run_reports_what_is_missing_without_refusing(self):
        """"What is missing" is one command, not one answer at a time."""
        store.save([record("rec-1", "one@example.com", "Ada",
                           keys=("em1", "em2")),
                    record("rec-2", "two@example.com", "Grace",
                           keys=("em1", "em2", "em3", "em4", "em5"))])
        report = bisonfactory.stage(CID, config=CONFIG, live=False)
        missing = {lead["contact_key"]: lead["missing_copy"]
                   for lead in report["plan"]["leads"]}
        self.assertEqual(missing["rec-1-c1"], ["em3", "em4", "em5"])
        self.assertEqual(missing["rec-2-c1"], [])
        self.assertEqual(self.bison.created_campaigns, 0,
                         "a dry run reached the provider")

    def test_a_tenancy_mismatch_is_still_the_first_refusal(self):
        """A copy complaint must not mask a wrong-estate refusal.

        The copy check used to run inside `_plan`, which happens before the
        workspace is read - so staging one client's campaign into another
        client's estate was reported as a missing draft.
        """
        store.save([record("rec-1", "one@example.com", "Ada",
                           keys=("em1",))])
        foreign = dict(CONFIG, providers={"emailbison": {"workspace": 25}})
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=foreign, live=True)
        self.assertIn("25", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
