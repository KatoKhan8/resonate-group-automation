#!/usr/bin/env python3
"""All three prospect-facing provider writes carry BOTH guards - TASK 0395.

`suppression/0370` measured, by AST, that no tree in this estate had all
three sites carrying both the door (`providerwrites.perform`) and the brake
(`haltfile.require_released`):

    origin/master          3 BYPASS
    glm-review  (I1)       2 THROUGH_DOOR, 1 BYPASS   - door, never brake
    glm-c       (I2/3/4)   1 both, 2 BRAKE_ONLY       - brake, never door
    brake-identity         3 BRAKE_ONLY
    integ-at-once          3 BRAKE_ONLY

The three sites, and they are the whole population of direct prospect-facing
EmailBison verbs:

    scripts/batch_activate.py  gated_resume   bison.resume_campaign
    scripts/resume_487.py      main           bison.resume_campaign
    src/bisonfactory.py        _attach        bison.attach_senders

THE INVARIANT UNDER TEST IS NOT A SENTENCE IN THE SOURCE. Three questions
per site, and the third is what makes the other two mean anything:

    1. brake pulled          -> the provider verb is NOT reached
    2. write unauthorised    -> the provider verb is NOT reached
    3. both released, and
       the campaign is ours  -> the provider verb IS reached

and a fourth that is the actual safety property the ordering was chosen for:

    4. brake pulled AFTER the site's own consult, while the write is in
       flight -> the provider verb is still NOT reached, because `perform`
       pulls the brake again at its step 2c, one statement before the
       transport.

WHAT "UNAUTHORISED" MEANS HERE, AND WHY THIS LEVER. The door's ownership
default-refuse: a campaign the operator has DECLARED internal is never
written to from code. It is the right lever because it is reachable from
NOWHERE ELSE - no caller-side gate in any of the three sites reads the
declaration - so a refusal carrying its words is proof the write passed
through the door and not past it. Each test asserts on those words, not
merely on a refusal: this estate has already recorded a control that passed
because a different guard answered first.

NO PROVIDER CALL, NO NETWORK, NO --live ANYTHING. Every test patches at the
bison module seam (`resume_campaign`, `attach_senders`, `campaign`,
`campaign_senders`), points the campaign store and the write ledger at temp
files, and patches `haltfile.STOP_SENDING_PATH` to a throwaway. NO TEST
CREATES THE REAL STOP-SENDING FILE.

WHY `killswitch.require` IS PATCHED PERMISSIVE. Same reason the TASK 0210
module gives: the freeze refuses everything in this build, so without the
patch every test here would be refused by the freeze before either guard
was consulted - green for the wrong reason. The premise is measured, not
assumed, by `TheFreezeIsMeasuredNotAssumed` in that module.

Born-red on the composed base (integ/canary-nine-at-once + task-glm-c, no
-X): sites 1 and 2 reach the verb with the write unauthorised, because they
call `bison.resume_campaign` directly; site 3 cannot even reach its control.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import (bisonfactory, campaigns, haltfile,          # noqa: E402
                 killswitch, providerwrites)
from src.providers import bison                              # noqa: E402
from tests.campaignbase import CampaignTest                  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_activate as activate                            # noqa: E402
import resume_487 as recover                                 # noqa: E402

PREFIX = "productive-email-batch1-"
CANONICAL_ID = "productive-email-control-v3"
BATCH_PROVIDER_ID = "9001"

INTERNAL_WORDS = "DECLARED an internal Resonate campaign"
BRAKE_WORDS = "STOP-SENDING"


class _BothGuards(CampaignTest):
    """A campaign fixture, a throwaway write ledger, a throwaway brake path
    and a throwaway internal-campaign declaration. Nothing real."""

    def setUp(self):
        super().setUp()
        self.scratch = tempfile.mkdtemp(prefix="rga-0395-")
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)

        self.ledger_path = os.path.join(self.scratch, "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)

        self.brake_path = os.path.join(self.scratch, "STOP-SENDING")
        self.declared_path = os.path.join(self.scratch,
                                          "internal-campaigns.txt")

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = \
                self._old_ledger

    # ---------------------------------------------------------- the levers

    def pull_brake(self):
        with open(self.brake_path, "wb") as handle:
            handle.write(b"")

    def declare_internal(self, provider_id):
        # The declaration's channel token is the PROVIDER's name, not the
        # medium: "bison", never "email". The wrong token raises
        # `InternalCampaignsUnreadable`, which ALSO fails closed - so the
        # verb-not-reached half of these tests passed on the wrong refusal
        # until the assertion on the door's own words caught it.
        with open(self.declared_path, "w", encoding="utf-8") as handle:
            handle.write("bison %s\n" % provider_id)

    def bind(self, canonical, provider_id):
        row = campaigns.get(canonical)
        row["bison_campaign_id"] = str(provider_id)
        campaigns.save([row])
        return row

    @contextlib.contextmanager
    def guards(self, brake_on_grant=False):
        """Every patch common to all three sites.

        `brake_on_grant=True` creates the brake file at the moment the site
        mints its GateToken - which is AFTER the site's own
        `haltfile.require_released()` and BEFORE the transport. That is the
        in-flight case, and the only thing that can refuse it is the door's
        own consult at step 2c.
        """
        real_grant = providerwrites.grant

        def grant(*args, **kwargs):
            if brake_on_grant:
                self.pull_brake()
            return real_grant(*args, **kwargs)

        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                mock.patch.object(providerwrites, "internal_campaigns_path",
                                  lambda: self.declared_path), \
                mock.patch("src.killswitch.require",
                           lambda **kwargs: None), \
                mock.patch.object(providerwrites, "grant", grant):
            yield


# --------------------------------------------------------------- site one


class BatchActivateResume(_BothGuards):
    """scripts/batch_activate.py, driven through its own main(["--live"])."""

    def drive(self, brake_on_grant=False):
        reached = []

        def record(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=PREFIX + "alpha")
        # TASK 0398: named, healthy seats so the bounce hard stop PASSES.
        # Every assertion in this class is about WHICH guard answered, and
        # a stop that halts on an unjudgeable mailbox answers before both
        # of them - green, and watching neither.
        seats = self.make_senders_nameable(PREFIX + "alpha")
        healthy = {seat: activate.classify(1877, 8, seat=seat)
                   for seat in seats}
        provider_row = {"status": "paused", "total_leads": 2,
                        "emails_sent": 0, "bounced": 0, "unsubscribed": 0}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                self.guards(brake_on_grant=brake_on_grant), \
                mock.patch.object(activate, "load_env", lambda: None), \
                mock.patch.object(activate, "mailbox_health",
                                  lambda: healthy), \
                mock.patch.object(activate, "ROOT", self.tmp), \
                mock.patch.object(activate.time, "sleep", lambda s: None), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(provider_row)), \
                mock.patch.object(bison, "scheduled_emails", lambda pid: []), \
                mock.patch.object(bison, "resume_campaign", record):
            activate.main(["--live"])
        return out.getvalue(), reached

    def test_the_brake_stops_it(self):
        self.pull_brake()
        out, reached = self.drive()
        self.assertEqual(reached, [], "the brake was pulled and "
                                      "bison.resume_campaign was still called")
        self.assertIn(BRAKE_WORDS, out)

    def test_an_unauthorised_write_never_reaches_the_verb(self):
        self.declare_internal(BATCH_PROVIDER_ID)
        out, reached = self.drive()
        self.assertEqual(reached, [], "the operator declared this campaign "
                                      "internal and the resume still reached "
                                      "bison.resume_campaign")
        self.assertIn(INTERNAL_WORDS, out,
                      "the refusal must be the DOOR's ownership guard. Any "
                      "other wording means a different guard answered first "
                      "and this test is not watching what it claims to")

    def test_the_brake_pulled_in_flight_still_stops_it(self):
        out, reached = self.drive(brake_on_grant=True)
        self.assertEqual(reached, [],
                         "the brake was pulled after the site's own consult "
                         "and before the transport; the door's step-2c "
                         "consult is what has to catch that, and it did not")
        self.assertIn(BRAKE_WORDS, out)

    def test_the_control_reaches_the_verb(self):
        out, reached = self.drive()
        self.assertEqual(reached, [(BATCH_PROVIDER_ID, 2)],
                         "with no brake and nothing declared internal the "
                         "verb must be reached exactly once. If it is not, "
                         "the three refusals above prove nothing: %s" % out)


# --------------------------------------------------------------- site two


class Resume487(_BothGuards):
    """scripts/resume_487.py, driven through its own main(["--live"])."""

    def drive(self, brake_on_grant=False):
        reached = []

        def record(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CANONICAL_ID)
        self.bind(CANONICAL_ID, recover.CAMPAIGN)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                self.guards(brake_on_grant=brake_on_grant), \
                mock.patch.object(recover, "_setup_data_access",
                                  lambda: None), \
                mock.patch.object(recover, "window_gate", lambda: True), \
                mock.patch.object(recover, "truth_gate",
                                  lambda b: ({"status": "paused"},
                                             {"sending_paused": 10},
                                             {"timezone": "Europe/Zagreb"})), \
                mock.patch.object(recover, "copy_gate", lambda: True), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "in_sequence"}), \
                mock.patch.object(bison, "membership", lambda cid: {}), \
                mock.patch.object(bison, "resume_campaign", record):
            code = recover.main(["--live"])
        return code, out.getvalue(), reached

    def test_the_brake_stops_it(self):
        self.pull_brake()
        code, out, reached = self.drive()
        self.assertEqual(reached, [])
        self.assertEqual(code, 1)
        self.assertIn("BRAKE REFUSED", out)

    def test_an_unauthorised_write_never_reaches_the_verb(self):
        self.declare_internal(recover.CAMPAIGN)
        code, out, reached = self.drive()
        self.assertEqual(reached, [], "487 was declared internal and the "
                                      "resume still reached the verb")
        self.assertEqual(code, 1)
        self.assertIn(INTERNAL_WORDS, out,
                      "the refusal must be the DOOR's ownership guard")

    def test_the_brake_pulled_in_flight_still_stops_it(self):
        code, out, reached = self.drive(brake_on_grant=True)
        self.assertEqual(reached, [],
                         "the brake was pulled after this script's own "
                         "consult inside the write window and before the "
                         "transport; the door has to catch that")
        self.assertEqual(code, 1)

    def test_the_control_reaches_the_verb(self):
        _code, out, reached = self.drive()
        self.assertEqual(reached, [(recover.CAMPAIGN, recover.EXPECT_LEADS)],
                         "with no brake and nothing declared internal the "
                         "verb must be reached exactly once: %s" % out)


# ------------------------------------------------------------- site three


class AttachSenders(_BothGuards):
    """src/bisonfactory.py `_ensure_senders`, called directly.

    This site has no CLI: the canary's shape is a campaign that already
    exists, so `stage()` never runs and nothing upstream refuses.
    """

    SENDER = 2736

    def drive(self, brake_on_grant=False):
        attached = []

        def record(provider_id, wanted):
            attached.append((provider_id, list(wanted)))
            return {"senders": list(wanted)}

        reads = []

        def senders(_provider_id):
            # First call is the site's own pre-check (nothing bound yet);
            # any later call is the door's read-back, after the attach.
            reads.append(True)
            return [] if len(reads) == 1 else [self.SENDER]

        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CANONICAL_ID)
        row = self.bind(CANONICAL_ID, recover.CAMPAIGN)
        row["senders"] = {"email": [{"provider_account_id": self.SENDER}]}
        report = {"did": [], "provider": {}}
        raised = None
        with self.guards(brake_on_grant=brake_on_grant), \
                mock.patch.object(bisonfactory.bison, "attach_senders",
                                  side_effect=record), \
                mock.patch.object(bisonfactory.bison, "campaign_senders",
                                  side_effect=senders):
            try:
                bisonfactory._ensure_senders(str(recover.CAMPAIGN), row,
                                             report, by="tests/0395")
            except Exception as exc:               # noqa: BLE001
                raised = exc
        return raised, report, attached

    def test_the_brake_stops_it(self):
        self.pull_brake()
        raised, _report, attached = self.drive()
        self.assertEqual(attached, [])
        self.assertIsInstance(raised, haltfile.OperatorStop)

    def test_an_unauthorised_write_never_reaches_the_verb(self):
        self.declare_internal(recover.CAMPAIGN)
        raised, _report, attached = self.drive()
        self.assertEqual(attached, [], "the campaign was declared internal "
                                       "and the attach still reached "
                                       "bison.attach_senders")
        self.assertIsInstance(raised, providerwrites.WriteRefused)
        self.assertIn(INTERNAL_WORDS, str(raised),
                      "the refusal must be the DOOR's ownership guard")

    def test_the_brake_pulled_in_flight_still_stops_it(self):
        raised, _report, attached = self.drive(brake_on_grant=True)
        self.assertEqual(attached, [],
                         "the brake was pulled after _ensure_senders' own "
                         "consult and before the transport")
        self.assertIsInstance(raised, haltfile.OperatorStop)

    def test_the_control_reaches_the_verb(self):
        raised, _report, attached = self.drive()
        self.assertIsNone(raised, "the control must not refuse: %r" % raised)
        self.assertEqual(attached, [(str(recover.CAMPAIGN), [self.SENDER])],
                         "with both guards released the attach must reach "
                         "the verb exactly once")


class TheDoorItselfPullsTheBrake(unittest.TestCase):
    """The structural half of the in-flight tests above, stated once.

    The three sites are safe in flight because `_perform` consults the
    brake itself, immediately before the transport - not because each
    caller remembered to. If that consult is ever moved or removed, the
    three in-flight tests go red and so does this, and this one says why
    in one line.
    """

    def test_perform_consults_the_brake_before_the_transport(self):
        import ast
        import inspect

        source = inspect.getsource(providerwrites._perform)
        tree = ast.parse(source.lstrip())
        brake_line = transport_line = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and \
                    func.attr == "require_released":
                brake_line = node.lineno
            if isinstance(func, ast.Name) and func.id == "transport":
                if transport_line is None:
                    transport_line = node.lineno
        self.assertIsNotNone(brake_line,
                             "_perform does not consult haltfile at all: the "
                             "door is not a brake and every in-flight case "
                             "above is unprotected")
        self.assertIsNotNone(transport_line, "_perform calls no transport")
        self.assertLess(brake_line, transport_line,
                        "the brake consult must come BEFORE the transport "
                        "call; after it is not a brake, it is a report")


if __name__ == "__main__":
    unittest.main()
