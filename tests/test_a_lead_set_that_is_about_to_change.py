#!/usr/bin/env python3
"""The gate that could never admit a first lead, and the two shapes of campaign.

THE DEFECT THIS MODULE IS ABOUT.

`executionguard.authorize` refuses to mint an authorization unless
`configdiff.compare_heyreach` returns PASS. `heyreachfactory.ensure_leads`
asks for that authorization in order to ADD A LEAD. `lead_set` is in
`REQUIRED_HEYREACH` and was compared by equality.

So the gate demanded that the provider already hold the people it was being
asked for permission to put there. It could not admit a first lead into any
campaign, ever. Nobody had noticed because no lead had ever been added - the
path had never run end to end, and a gate that has never passed looks exactly
like a gate that is working.

Found on 2026-09-15 by running it against a real DRAFT campaign with a real
three-contact cohort, which is the only way it was ever going to surface.

WHAT THE FIX DOES NOT GIVE UP, and this is the whole argument:

The safety property is not "the provider holds exactly who we approved". It is
"the provider holds NOBODY WE DID NOT APPROVE". Equality asserted both at
once, and only the second one survives a write that is adding people. A
campaign whose lead set is a SUBSET of the approved set contains no stranger,
whether it is empty, half full or complete - and a stranger still fails,
because a stranger is not in the approved set and containment refuses it.

That is proven below in both directions, because a subset check that admits
everything would pass the first half of that sentence and betray the second.

THE SECOND SHAPE OF CAMPAIGN.

`approved_heyreach` could only describe a single-step canary: CONNECTION_REQUEST
then END, one literal note rendered from one contact's `day3` step. Campaign
599020 is a 24-node graph carrying MERGE VARIABLES - its connection request
reads `{connection_note}` and each lead brings its own approved words in
`customUserFields`. Every field derived from a rendered note described a
campaign that does not exist.

The row declares its shape now, and a row that does not is refused rather than
guessed - the rule this module already set for itself over `provider_delays`.
"""
import unittest
from unittest import mock

from src import configdiff, providerwrites

from tests.base import QueueTest


APPROVED_TWO = frozenset({"ada-lovelace", "grace-hopper"})


def _approved(**over):
    """An approved-side config with a two-person lead set."""
    row = {"campaign_id": "599020", "lead_set": APPROVED_TWO, "lead_count": 2,
           "status": "DRAFT", "note": "{connection_note}"}
    row.update(over)
    return row


def _provider(**over):
    row = {"campaign_id": "599020", "lead_set": frozenset(), "lead_count": 0,
           "status": "DRAFT", "note": "{connection_note}"}
    row.update(over)
    return row


REQUIRED = ("campaign_id", "lead_set", "lead_count", "status", "note")


class AnEmptyCampaignCanBeFilled(unittest.TestCase):
    """The case the old comparison made impossible."""

    def test_equality_refuses_the_first_lead(self):
        """The defect itself, pinned so it cannot come back quietly.

        This is what every add-lead attempt met: the approved side names the
        cohort, the provider holds nobody yet, and the diff calls that a
        mismatch on a REQUIRED field.
        """
        found = configdiff.diff(_approved(), _provider(), REQUIRED)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("lead_set: mismatch", found["failures"])

    def test_containment_admits_it(self):
        found = configdiff.diff(_approved(), _provider(), REQUIRED,
                                subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.PASS, found["failures"])

    def test_a_half_filled_campaign_is_admitted_too(self):
        """A retry after a partial write must not be refused for being partial.

        One of the two landed. The next attempt is for the other, and the
        provider's set is still a subset of the approved one.
        """
        found = configdiff.diff(
            _approved(),
            _provider(lead_set=frozenset({"ada-lovelace"}), lead_count=1),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.PASS, found["failures"])

    def test_a_complete_campaign_still_matches(self):
        found = configdiff.diff(
            _approved(),
            _provider(lead_set=APPROVED_TWO, lead_count=2),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.PASS, found["failures"])


class AStrangerStillFails(unittest.TestCase):
    """The half of the property that has to survive the fix.

    A containment check that admitted anything would pass every test above and
    be worthless. These are the tests that make the fix mean something.
    """

    def test_a_lead_nobody_approved_fails(self):
        found = configdiff.diff(
            _approved(),
            _provider(lead_set=frozenset({"ada-lovelace", "stranger"}),
                      lead_count=2),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("lead_set: mismatch", found["failures"])

    def test_a_campaign_holding_only_strangers_fails(self):
        found = configdiff.diff(
            _approved(),
            _provider(lead_set=frozenset({"someone-else"}), lead_count=1),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)

    def test_more_leads_than_were_approved_fails(self):
        """The count is checked as well as the identities, because a provider
        that returns an unreadable profile leaves `lead_set` UNVERIFIABLE and
        the count is then the only thing left."""
        found = configdiff.diff(
            _approved(),
            _provider(lead_set=APPROVED_TWO, lead_count=5),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("lead_count: mismatch", found["failures"])

    def test_no_other_field_is_loosened_by_asking(self):
        """`subset_fields` names two fields. Everything else is still equality,
        so a campaign in the wrong STATE cannot be staged into."""
        found = configdiff.diff(
            _approved(), _provider(status="IN_PROGRESS"),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("status: mismatch", found["failures"])

    def test_the_note_is_still_equality(self):
        found = configdiff.diff(
            _approved(), _provider(note="something nobody approved"),
            REQUIRED, subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("note: mismatch", found["failures"])

    def test_an_unapproved_field_still_fails_unconditionally(self):
        """UNEXPECTED is not softened by containment: nobody approved it."""
        provider = _provider(lead_set=APPROVED_TWO, lead_count=2)
        provider["a_field_nobody_approved"] = "surprise"
        found = configdiff.diff(_approved(), provider, REQUIRED,
                                subset_fields=configdiff.SUBSET_FIELDS)
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn("a_field_nobody_approved: unexpected", found["failures"])


class ContainmentIsOptIn(unittest.TestCase):
    """It is only ever applied when the caller names the fields."""

    def test_the_default_is_equality(self):
        found = configdiff.diff(_approved(), _provider(), REQUIRED)
        self.assertEqual(found["verdict"], configdiff.FAIL)

    def test_compare_heyreach_defaults_to_equality(self):
        """`staging` is False unless asked for, so every caller that is not
        adding leads compares exactly as it did before."""
        import inspect
        sig = inspect.signature(configdiff.compare_heyreach)
        self.assertIs(sig.parameters["staging"].default, False)

    # The assertion that `ensure_leads` actually PASSES the flag lives in
    # `test_heyreachfactory_ensure_leads.WhatTheFactoryHandsTheDoor`, which
    # already drives a real live push with the whole gate chain mocked around
    # it. Asserting it here would mean rebuilding that harness, and a test
    # that constructs its own input is testing the seam rather than the path.

    def test_a_boolean_is_never_treated_as_a_number(self):
        """`isinstance(True, int)` is True in Python, so a bool would sneak
        through the integer branch and `False <= True` would read as MATCH."""
        self.assertFalse(configdiff._within(False, True))
        self.assertTrue(configdiff._within(True, True))


class TheStoppabilityCeilingFollowsThePause(unittest.TestCase):
    """The one-lead bound reads the predicate rather than a copied number.

    `approved_heyreach` refused any campaign with more than one approved lead,
    because `executionguard`'s stoppability gate caps an unstoppable channel
    at one contact - and its own comment said the bound "should be raised
    deliberately" when a pause was established. It was established on
    2026-09-12 against campaign 594061 and the bound had not moved.

    It now reads `providerwrites.is_supported("heyreach.pause")`, the same
    predicate the gate itself reads, so the two cannot drift apart and a
    withdrawn pause tightens both without anybody remembering to.

    DOES THE PREMISE STILL HOLD AFTER THE 2026-09-16 GRANTS? Asked because
    those grants moved `is_supported` for eight verbs, this ceiling reads
    `is_supported`, and a ceiling that moves as a side effect of something
    else is exactly what this class was written to prevent. Worked through
    rather than assumed, and the answer is yes - with one thing that had to
    be checked and is now asserted below rather than believed.

    `executionguard.UNSTOPPABLE_CHANNEL_CAP` limits how many distinct people
    a channel may reach WHILE NOTHING CAN STOP IT. Its premise is a statement
    about the STOP verb and about nothing else:

      1. The gate fires only when `is_supported(PAUSE_OPERATION[channel])` is
         False. Neither ACTIVATE verb, and none of the five campaign-building
         verbs, is a pause operation, so not one of the grants is an input to
         it. The ceiling did not move; nothing that reads it changed.

      2. What the grants DID change is that the question is now real. Until
         2026-09-16 no wired verb could start a campaign holding people, so
         "exposure this system cannot recall" was hypothetical. It is not any
         more, and this is precisely the situation the cap was written for.
         The premise survives because the stop was established FIRST and on
         evidence: `heyreach.pause` on 2026-09-12 against 594061 (200, read
         back PAUSED, connectionsSent 0), `bison.pause` and
         `bison.stop_lead` on 2026-09-13, each measured with a readback.

      3. The half that had to be CHECKED rather than assumed: a stop that is
         narrower than the start would satisfy `is_supported` and leave real
         exposure unrecallable. It is not. Both pause verbs are in SUPPORTED
         and carry NO `CONDITIONAL`, so a stop may be aimed at any campaign
         on the channel, while each ACTIVATE verb is scoped by name to ONE.
         The stop is strictly broader than the start, and on email
         `bison.stop_lead` is finer still - it halts one person while the
         rest of the campaign continues. That asymmetry is the premise, and
         `test_the_stop_is_broader_than_the_start` now asserts it, because
         nothing else in this repository did.

    So the number stays 1 and it stays where it is: it is not a cohort size
    somebody chose, it is the exposure that is survivable in the world where
    the pause predicate answers False. In the world where it answers True the
    cap is dormant, and the cap becoming dormant for the wrong reason - a
    pause narrowed to a condition, or withdrawn - is what the tests below
    are for.
    """

    def test_the_pause_is_what_lifts_it(self):
        self.assertIn("heyreach.pause", providerwrites.SUPPORTED)

    def test_the_stop_is_broader_than_the_start(self):
        """THE CEILING'S PREMISE, ASSERTED RATHER THAN ASSUMED.

        `UNSTOPPABLE_CHANNEL_CAP` lifts on "a stop exists", and `is_supported`
        is the whole of what it asks. That was a complete question while
        nothing could start a campaign holding people. Now that both ACTIVATE
        verbs are granted it is not, because `is_supported` cannot tell a stop
        that covers the channel from a stop that covers one campaign - and a
        stop narrower than the start would lift the ceiling while leaving
        people this system could not recall.

        For each channel: the pause verb is supported and UNCONDITIONAL, so
        every campaign on it can be stopped; the activate verb is supported
        and conditional on exactly one campaign, so one campaign on it can be
        started. There is therefore no campaign this build can start and
        cannot stop, which is the sentence the ceiling stands on.

        A pause acquiring a condition would fail here and should: it would
        not be caught by `is_supported`, and it is the one change that could
        make the cap dormant while the exposure it bounds was real.
        """
        from src import executionguard

        for channel, activate in (("linkedin", "heyreach.activate"),
                                  ("email", "bison.activate")):
            pause = executionguard.PAUSE_OPERATION[channel]
            self.assertTrue(providerwrites.is_supported(pause), pause)
            self.assertFalse(
                providerwrites.is_conditional(pause),
                f"{pause} carries a condition, so the stop on {channel} no "
                f"longer covers every campaign {activate} could start and "
                f"the stoppability ceiling is lifting on a false premise")
            # And the start is the narrow one, not the broad one.
            self.assertTrue(providerwrites.is_supported(activate), activate)
            self.assertTrue(
                providerwrites.is_conditional(activate),
                f"{activate} can start any campaign on {channel} while the "
                f"ceiling assumes the stop is the broader of the two")

        # Email's stop is finer than campaign granularity, which is the
        # granularity the safety argument actually wants: one person is
        # halted while the rest of the campaign continues.
        self.assertTrue(providerwrites.is_supported(
            providerwrites.EMAIL_STOP_LEAD))
        self.assertFalse(providerwrites.is_conditional(
            providerwrites.EMAIL_STOP_LEAD))

    def test_the_ceiling_does_not_read_the_activation_grants(self):
        """The grants are not an input to it, and the number did not move.

        Eight verbs entered `SUPPORTED` on 2026-09-16 and this ceiling reads
        `SUPPORTED`. It reads ONE ENTRY of it - the channel's pause - so the
        grants are irrelevant to it by construction, and the cap is still the
        one-person canary it always was. Asserted because "the ceiling moved
        when the grants landed" is the plausible-sounding conclusion, and it
        is wrong: the ceiling moved on 2026-09-12, when the pause did.
        """
        from src import executionguard

        self.assertEqual(executionguard.UNSTOPPABLE_CHANNEL_CAP, 1)
        self.assertEqual(set(executionguard.PAUSE_OPERATION.values()),
                         {"heyreach.pause", "bison.pause"})
        # Withdraw every 2026-09-16 grant and the ceiling is unchanged,
        # because none of them is a pause.
        granted = ("heyreach.activate", "bison.activate",
                   "heyreach.create_campaign", "heyreach.create_list",
                   "heyreach.set_sequence", "bison.create_campaign",
                   "bison.set_sequence", "bison.assign_sender")
        without = tuple(op for op in providerwrites.SUPPORTED
                        if op not in granted)
        with mock.patch.object(providerwrites, "SUPPORTED", without):
            approved = configdiff.approved_heyreach(*_campaign_with(leads=2))
        self.assertEqual(approved["lead_count"], 2)

    def test_without_a_pause_the_ceiling_is_one(self):
        """Withdraw the pause and the ceiling tightens, with no edit here.

        This is the direction that proves the two are one truth rather than
        two copies of it, and it is why the number was never written down in
        `configdiff`.
        """
        source = _campaign_with(leads=2)
        without = tuple(op for op in providerwrites.SUPPORTED
                        if op != "heyreach.pause")
        with mock.patch.object(providerwrites, "SUPPORTED", without):
            with self.assertRaises(configdiff.DiffRefused) as caught:
                configdiff.approved_heyreach(*source)
        self.assertIn("stoppability ceiling", str(caught.exception))

    def test_with_a_pause_a_cohort_is_allowed(self):
        approved = configdiff.approved_heyreach(*_campaign_with(leads=2))
        self.assertEqual(approved["lead_count"], 2)

    def test_an_empty_approved_set_is_still_refused(self):
        """Lifting the ceiling must not make "nobody approved" acceptable: a
        campaign with no approved leads has nobody it may legitimately hold,
        and with containment in play an empty approved set would otherwise
        match an empty provider set and PASS."""
        with self.assertRaises(configdiff.DiffRefused) as caught:
            configdiff.approved_heyreach(*_campaign_with(leads=0))
        self.assertIn("approved lead set is empty", str(caught.exception))

    def test_a_contact_without_approved_copy_is_not_in_the_lead_set(self):
        """The identity half and the copy half are one question here: a
        contact the factory would refuse to push is a contact this campaign
        may not hold, so removing their approval removes them from the set."""
        campaign, recs, config = _campaign_with(leads=2)
        recs[1]["cadence"]["c1"]["li3"].pop("approval")
        approved = configdiff.approved_heyreach(campaign, recs, config)
        self.assertEqual(approved["lead_count"], 1)
        self.assertEqual(approved["lead_set"], frozenset({"ada-lovelace"}))


def _approved_cadence(contact_key):
    """Approved LinkedIn copy for every role the graph requires.

    The same state `scripts/build_control_cohort.py` writes: each of li1..li5
    carries the client's own fallback text and an approval stamp. Built here
    rather than mocked, because `_approved_for_campaign` asks
    `heyreachfactory.custom_fields_for` - the function production uses - and a
    mock would test the mock.

    THE STAMP NAMES AN ADDRESS, AND IT USED TO SAY `"test"`. That is not a
    cosmetic change and it is why every test in this file that reached
    `approved_heyreach` had started erroring. `heyreachfactory._step_copy`
    asks `approval.is_accountable_approver(stamp["by"])` and returns None for
    a bare token - a rule added because 84 approvals in this estate are
    stamped `by: "claude"`, 83 of them on `generated: true` steps whose
    fingerprint never moves, so a self-recorded stamp on generated words
    would be permanent. A bare token is exactly what that rule refuses, and
    this fixture was writing one.

    So the fixture was asserting a state production may not reach. Making the
    approver an address is not a loosening: it is the fixture finally
    describing an approval a human could be held to, which is the only kind
    that puts a contact in an approved lead set.
    """
    from src import approval as _approval
    from src import heyreachfactory as _hf

    steps = {}
    for i, step_key in enumerate(_hf.COPY_MAPPING):
        step = {"channel": "linkedin", "note": f"approved sentence {i}"}
        steps[step_key] = dict(
            step, approval={"by": "operator@example.com",
                            "at": "2026-09-15T00:00:00+00:00",
                            "fingerprint": _approval.fingerprint(step)})
    return {contact_key: steps}


def _campaign_with(leads):
    """A declared-shape campaign row and the records behind it."""
    recs = []
    slugs = ["ada-lovelace", "grace-hopper", "alan-turing"][:leads]
    for i, slug in enumerate(slugs):
        recs.append({
            "id": f"rec-{i}", "client": "productive", "domain": "example.com",
            # A real company name, because the LEGACY path renders a template
            # and `cadence.company_name` refuses to address somebody by their
            # own hostname. The declared-shape path never renders anything,
            # which is the difference the last test in this file turns on.
            "company": f"Kestrel Wharf {i}",
            "company_facts": {"name": f"Kestrel Wharf {i}"},
            "contacts": [{"key": f"c{i}", "name": "Pat Okafor",
                          "linkedin": f"https://www.linkedin.com/in/{slug}"}],
            "cadence": _approved_cadence(f"c{i}"),
        })
    campaign = {
        "campaign_id": "c1", "client": "productive", "name": "N",
        "heyreach_campaign_id": "599020",
        "record_ids": [r["id"] for r in recs],
        "org_unit": "118832", "heyreach_list_id": "933603",
        "provider_status_expected": "DRAFT",
        "provider_delays": [["DAY", 1]],
        "provider_note": "{connection_note}",
        "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"],
        "senders": {"linkedin": [{"provider_account_id": 174892}]},
        "daily_volume": {"linkedin": 0},
    }
    return campaign, recs, {}


class TheApprovedSenderSetWasAlwaysEmpty(unittest.TestCase):
    """`_ids` read `id` off a sender row that stores `provider_account_id`.

    Found on the first real staging diff: campaign 599020 failed on
    `sender_ids` alone, approved `frozenset()` against provider `{'174892'}`,
    on a campaign whose seat was correct and had been for days.

    The mismatch is the lucky case. Against a provider reporting NO seats,
    empty would have matched empty and the field would have PASSED while
    asserting nothing at all - a campaign with no sender assigned reading as a
    campaign whose senders are exactly as approved. That is the direction
    these tests are really about.
    """

    def test_a_canonical_sender_row_is_read(self):
        self.assertEqual(
            configdiff._ids([{"provider_account_id": 174892}]),
            frozenset({"174892"}))

    def test_a_provider_row_using_id_still_works(self):
        """`approved_bison` passes rows the provider returns, which use `id`."""
        self.assertEqual(configdiff._ids([{"id": 42}]), frozenset({"42"}))

    def test_a_bare_value_still_works(self):
        self.assertEqual(configdiff._ids([174892, "9"]),
                         frozenset({"174892", "9"}))

    def test_an_unassigned_campaign_does_not_read_as_approved(self):
        """The silent direction. Two empty sets compare equal, so the bug
        could only ever be caught where the provider HAD a seat."""
        approved = configdiff._ids([{"provider_account_id": 174892}])
        self.assertNotEqual(approved, configdiff._ids([]))

    def test_a_row_carrying_neither_key_is_skipped(self):
        self.assertEqual(configdiff._ids([{"name": "no id here"}]),
                         frozenset())


class TheDeclaredShapeIsRequiredTogether(QueueTest):
    """A row that says what its graph SAYS must say what its graph DOES."""

    def test_a_note_without_actions_refuses(self):
        campaign, recs, config = _campaign_with(leads=1)
        campaign.pop("provider_actions")
        with self.assertRaises(configdiff.DiffRefused) as caught:
            configdiff.approved_heyreach(campaign, recs, config)
        self.assertIn("provider_actions", str(caught.exception))

    def test_the_declared_note_is_what_is_compared(self):
        """Not a rendered sentence. The provider holds the merge variable and
        the approved side has to say the same string or the diff is checking
        words against a placeholder forever."""
        approved = configdiff.approved_heyreach(*_campaign_with(leads=1))
        self.assertEqual(approved["note"], "{connection_note}")
        # A TUPLE, because `provider_heyreach` returns one and `diff` compares
        # by equality - a list here would mismatch a tuple there on every
        # field and the campaign would fail its own `actions` check forever.
        self.assertEqual(approved["actions"],
                         ("CHECK_IS_CONNECTION", "MESSAGE"))

    def test_a_row_declaring_nothing_keeps_the_old_behaviour(self):
        """The canary path is untouched: with no `provider_note`, the copy
        still comes from the contact's own approved `day3` step, and a
        campaign with none is refused exactly as before."""
        campaign, recs, config = _campaign_with(leads=1)
        campaign.pop("provider_note")
        campaign.pop("provider_actions")
        with self.assertRaises(configdiff.DiffRefused) as caught:
            configdiff.approved_heyreach(campaign, recs, config)
        self.assertIn("no APPROVED and renderable LinkedIn step",
                      str(caught.exception))


if __name__ == "__main__":
    unittest.main()
