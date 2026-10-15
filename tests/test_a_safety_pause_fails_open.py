"""The blank-content halt's pause is a SAFETY write and fails OPEN.

TASK 0020 (GLM-A), 2026-10-15. MEASURED on `task-pilotcaps-enforcer-2026-10-14`
(4d2d19b9b), the branch that added `providerwrites.GateToken`: the halt still
alerts and pauses NOTHING. `scripts/bison_watch_loop.py:421` calls
`providerwrites.perform(EMAIL_PAUSE, ...)` with no `gate=`, and `_perform`'s
NON-FACING branch refuses at `src/providerwrites.py:2579` ("bison.pause is a
non-facing provider write and requires a GateToken ... It was called with
NoneType") - BEFORE the conditional-permission check (:2601), BEFORE the
ownership check (:2612) and BEFORE the transport (:2656). All three proven
unreached by an offline probe on 2026-10-15 (ownership of 497 was bound
`resonate_os`, so this is not the historical bare-worktree ownership refusal
that presented as the same `None != 497`). The control experiment: the
identical call carrying `gate=providerwrites.grant(...)` is ACCEPTED and the
transport is reached. The only difference between "the emergency stop works"
and "the emergency stop alerts and stops nothing" is a token nobody granted -
which is the 2026-09-23 failure mode (`work/provider-write-refusals.jsonl`,
20:18:58Z) this control already survived once, re-entering through our own
gate.

THE INVARIANT THIS FILE PINS: the halt's pause is performed EVEN WHEN NO
GATETOKEN IS PRESENT. An emergency stop that an accountability check can
refuse is not an emergency stop; who ordered the stop is recorded after the
stop, never made a precondition of it. A refusal is the fail-safe answer for
a write that reaches a person; this is the write that stops one reaching
anybody, and it fails OPEN.

WHY THIS FILE IS GREEN ON MASTER AND BORN RED ON THE GATE BRANCH: master's
`_perform` has no `gate` parameter at all, so the pause is ungated there and
this passes. On any lineage carrying the GateToken sink demand the test is
red until the halt's pause fails open - which is the point: it holds the
MERGE of that branch to the invariant, and fails at the merge rather than in
production.

NO FIX IS WIRED HERE and no gate's behaviour is changed by this file. This
is the failing test the fix must satisfy. If the fix chosen is "the halt
mints a grant before pausing", the `gate is None` assertion below stays red
DELIBERATELY: a pause that works only because a token was minted is one
refused mint away from alerting and stopping nothing again.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, providerwrites, store          # noqa: E402
from src import emptyrender                              # noqa: E402
from src.providers import bison as _bison                # noqa: E402

#: The real shape, verbatim from EmailBison 2026-09-23: the opener row of the
#: campaign that sent blanks (docs/INCIDENT-2026-09-23-BLANK-EMAILS.md). The
#: fixture is shared with `test_a_blank_email_can_never_be_sent_again.py`,
#: which records why a tracked file may not carry the real copy.
OPENER_BLANK = {"id": 22352262, "sequence_step_id": 4769, "status": "sent",
                "thread_reply": False, "email_subject": "",
                "email_body": "<p></p>", "lead": {"id": 167865}}

#: A SYNTHETIC canonical id binding EmailBison 497, so ownership resolves
#: `resonate_os` in this test's throwaway ledger rather than against whatever
#: `work/campaigns.jsonl` the checkout happens to carry - the trap the halt
#: test's own `bind_497` docstring records, where an UNBOUND 497 was refused
#: on ownership and presented as the same `None != 497`.
CANONICAL_497 = "synthetic-test-campaign-binding-bison-497"


class TheHaltPausesWithoutAGateToken(unittest.TestCase):
    """No GateToken, no grant, no scope token of any kind - and it still stops.

    Runs the REAL `_halt_on_blank_content` from `scripts/bison_watch_loop.py`
    with every provider leg monkeypatched, and watches the `gate` argument
    `_perform` actually receives, so the assertion is about what was
    presented, not about what the source happens to say today.
    """

    def bind_497(self):
        """Record 497 in a THROWAWAY ledger before the halt pauses it."""
        tmp = tempfile.mkdtemp(prefix="rga-halt-open-")
        self.addCleanup(store.use_directory(tmp))
        self.assertTrue(store.queue_path().startswith(os.path.abspath(tmp)),
                        "the store was not redirected, so this test would "
                        "write the operator's real state")
        row = campaigns.new_campaign(CANONICAL_497, "productive",
                                     CANONICAL_497, created_by="test")
        row["bison_campaign_id"] = "497"
        campaigns.save([row])
        self.assertEqual(
            providerwrites.classify_campaign("email", 497),
            providerwrites.RESONATE_OS,
            "497 did not bind, so a refusal below could be ownership rather "
            "than the gate, and this test would measure the wrong thing")

    def test_the_pause_is_performed_with_no_gatetoken_presented(self):
        self.bind_497()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "blw_fail_open", os.path.join(root, "scripts",
                                          "bison_watch_loop.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        seen = {}
        real_pause, real_campaign = _bison.pause_campaign, _bison.campaign

        def _pause(campaign_id):
            seen["paused"] = campaign_id
            return {"campaign_id": campaign_id, "status": "paused"}

        _bison.pause_campaign = _pause
        _bison.campaign = lambda _cid: {"status": "paused"}

        # Watch what `_perform` is actually handed, without changing it: the
        # wrapper forwards everything untouched and records the kwargs. On a
        # lineage with no `gate` parameter the key is simply absent and
        # `.get("gate") is None` still holds, so the assertion means the same
        # thing on both sides of the merge.
        presented = {}
        real_perform = providerwrites._perform

        def _spy(operation, **kw):
            presented.update(kw)
            return real_perform(operation, **kw)

        providerwrites._perform = _spy
        try:
            blanks = emptyrender.scan([dict(OPENER_BLANK,
                                            status="scheduled")])
            lines = []
            halted = module._halt_on_blank_content(497, {"blanks": blanks},
                                                   lines.append)
        finally:
            providerwrites._perform = real_perform
            _bison.pause_campaign, _bison.campaign = real_pause, real_campaign

        self.assertTrue(halted)
        self.assertIsNone(presented.get("gate"),
                          "the halt presented a gate token, so this test no "
                          "longer measures the absent-token case")
        self.assertEqual(
            seen.get("paused"), 497,
            "the halt's pause was refused before the transport: a safety "
            "write must fail OPEN, and an emergency stop that an "
            "accountability gate can turn into a no-op is the 2026-09-23 "
            "failure mode again. Refused with: "
            + next((l for l in lines if "HALT-REFUSED" in l),
                   "no BLANK-CONTENT-HALT-REFUSED line emitted"))
        self.assertFalse(any("HALT-REFUSED" in l for l in lines),
                         "the halt reported its own pause refused: "
                         + "\n".join(lines))


if __name__ == "__main__":                               # pragma: no cover
    unittest.main()
