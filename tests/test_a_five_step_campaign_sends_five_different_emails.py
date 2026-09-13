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
"""
import unittest

from src import bisonfactory, cadencelibrary, campaigns, store, workspaces
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison

CID = "camp-five-step"

# The email half of `productive_li_heavy_v1`: days 1, 4, 8, 12 and 21, so the
# gaps are 3, 4, 4 and 9. Written out here rather than computed, because a
# test that derives its expectation the same way the code does agrees with
# the code unconditionally.
WAITS = (3, 4, 4, 9)

SEQUENCE_CONFIG = {
    "title": "Resonate generated cadence",
    "steps": {
        "em1": {"order": 1, "subject": "{SUBJECT_1}",
                "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
        "em2": {"order": 2, "subject": "{SUBJECT_2}",
                "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
        "em3": {"order": 3, "subject": "{SUBJECT_3}",
                "body": "<p>{BODY_3}</p>", "wait_in_days": 4},
        "em4": {"order": 4, "subject": "{SUBJECT_4}",
                "body": "<p>{BODY_4}</p>", "wait_in_days": 9},
        "em5": {"order": 5, "subject": "{SUBJECT_5}",
                "body": "<p>{BODY_5}</p>", "wait_in_days": 0},
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
    return {"channel": "email",
            "subject": f"subject for {step_key}",
            "body": f"<p>body for {step_key}</p>",
            "approval": {"by": "operator", "at": "2026-09-13T00:00:00Z",
                         "fingerprint": f"fp-{n}"}}


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


class TheShippedConfigurationAgreesWithTheShippedCadence(unittest.TestCase):
    """The config Productive actually runs, against the cadence it names.

    Everything above tests the checker with fixtures. This tests the two real
    files, which is the pair that drifts: `email_sequence` lives in
    `config/clients/productive.yaml` and the cadence lives in
    `src/cadencelibrary.py`, and editing either one without the other is how
    a campaign ends up sending on a schedule nobody described.
    """

    def test_productive_builds_five_steps_against_its_own_cadence(self):
        from src import cadence, clients

        config = clients.load("productive")
        steps = bisonfactory._sequence_steps(
            config.get("email_sequence"),
            cadence.steps_for({"client": "productive"}, config=config))
        self.assertEqual([s["step_key"] for s in steps],
                         ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual(tuple(s["wait_in_days"] for s in steps[:-1]), WAITS)
        # The merge field and the variable it resolves to are the same
        # number. A template asking for `{SUBJECT_3}` while the lead carries
        # `subject_2` renders nothing, and every readback still agrees.
        for n, step in enumerate(steps, start=1):
            self.assertIn(f"{{SUBJECT_{n}}}", step["email_subject"])
            self.assertIn(f"{{BODY_{n}}}", step["email_body"])

    def test_every_merge_field_the_sequence_uses_is_declared_at_the_provider(self):
        """A variable the workspace does not hold is a 422 mid-batch."""
        from src import cadence, clients
        from src.providers.bison import LEAD_VARIABLES

        config = clients.load("productive")
        steps = bisonfactory._sequence_steps(
            config.get("email_sequence"),
            cadence.steps_for({"client": "productive"}, config=config))
        for n in range(1, len(steps) + 1):
            self.assertIn(f"subject_{n}", LEAD_VARIABLES)
            self.assertIn(f"body_{n}", LEAD_VARIABLES)


class TheWordsTravelWithThePerson(QueueTest):
    """The whole path, against a provider that behaves like the real one."""

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)

        # The workspace killswitch must be on for lead writes.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        store.save([record("rec-1", "one@example.com", "Ada"),
                    record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Five step")
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
                         [f"{{SUBJECT_{n}}}" for n in range(1, 6)])
        self.assertEqual(tuple(s["wait_in_days"] for s in held[:-1]), WAITS)

    def test_every_step_gets_its_own_words(self):
        """`{SUBJECT_3}` resolves to the third step's approved subject.

        Not to the first one's. Matching by position instead of by cadence
        key is the mistake that would put a day-twelve approval in the
        day-one slot the first time somebody approved out of order.
        """
        self.stage()
        lead = next(iter(self.bison.leads.values()))
        held = self.bison.variables_of(lead)
        for n, key in enumerate(("em1", "em2", "em3", "em4", "em5"), start=1):
            self.assertEqual(held[f"subject_{n}"], f"subject for {key}")
            self.assertEqual(held[f"body_{n}"], f"<p>body for {key}</p>")

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
