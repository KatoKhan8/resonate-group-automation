"""Control (c) of the incident gate: the 76 blank emails, as a fixture.

OPERATOR DECISION 2026-09-23. `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.

EVERY FIXTURE HERE IS A REAL SHAPE READ OFF THE PROVIDER, not an invented
one. That distinction is why this file exists at all: this repository has
already shipped a guard whose tests mocked the very function that was broken,
and a suite that is green against imagined data proves only that the
imagination is consistent.

The shapes, verbatim from EmailBison on 2026-09-23:

    campaign 497 step 4769  order 1  thread_reply False
        subject template  '{SUBJECT_1}'
        body template     '<p>{BODY_1}</p>'
    campaign 497 step 4770  order 2  thread_reply True
        subject template  'Re: {SUBJECT_1}'
        body template     '<p>{BODY_2}</p>'

    the row that sent, step 4769:   email_subject ''      email_body '<p></p>'
    the row that stopped, step 4770: email_subject 'Re: '  email_body '<p></p>'
    the lead behind them (167865):  custom variables `headline`, `location`
                                    and NOTHING ELSE - no subject_1, no body_1

    a lead that rendered correctly (167609): subject_1 and body_1 present,
                                    AND body_4/5/6 holding the string 'None'

THE PRE-FIX ASSERTION IS PART OF THE TEST. `test_the_old_predicate_passes_it`
reproduces what the code did before this gate - a truthiness check on the
lead's own material - and asserts it finds the blank row acceptable. If
somebody later weakens `emptyrender` back toward that, this file says so in
the plainest terms available: the old way called this email fine, and a real
person received it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import emptyrender                                    # noqa: E402


# --- the rows, as the provider recorded them -------------------------------

OPENER_BLANK = {"id": 22352262, "sequence_step_id": 4769, "status": "sent",
                "thread_reply": False, "email_subject": "",
                "email_body": "<p></p>", "lead": {"id": 167865}}

FOLLOWUP_BLANK = {"id": 22356508, "sequence_step_id": 4770, "status": "stopped",
                  "thread_reply": True, "email_subject": "Re: ",
                  "email_body": "<p></p>", "lead": {"id": 167865}}

#: The row that proved `already` did not mean contained. Campaign 491 was
#: paused on 2026-09-23, so every one of its 275 undelivered rows read
#: `sending_paused` - including this blank, which the allowlist filed under
#: `already` next to the sent and the stopped. Nothing had stopped it. The
#: campaign's pause had. Read back from the provider 2026-09-24T07:5xZ.
PAUSED_BLANK = {"id": 22356723, "sequence_step_id": 4752,
                "status": "sending_paused", "thread_reply": True,
                "email_subject": "Re: ", "email_body": "<p></p>",
                "lead": {"id": 204724}}

#: The same campaign, the same paused status, copy that rendered correctly.
#: 274 of the 275 looked like this, and none of them may halt anything.
PAUSED_GOOD = {"id": 22356784, "sequence_step_id": 4752,
               "status": "sending_paused", "thread_reply": True,
               # SHAPE, NOT THE ROW'S REAL COPY. The live row renders a
               # real prospect's first name and their employer, and a
               # tracked file may not carry either. What this fixture has to
               # preserve is that the merge fields RESOLVED - the fault
               # classes all turn on emptiness, not on who is named.
               "email_subject": "Re: the ops stack",
               "email_body": "<p>Firstname, the teams I work with that look "
                             "most like Example Agency Ltd tend to arrive at "
                             "the same place.</p>",
               "lead": {"id": 204700}}

OPENER_GOOD = {"id": 22352260, "sequence_step_id": 4769, "status": "sent",
               "thread_reply": False,
               "email_subject": "profitability visible on Monday not two "
                                "weeks late",
               "email_body": "<p>Julian, I work with Marketing &amp; "
                             "Advertising teams on profitability.</p>",
               "lead": {"id": 167609}}

FOLLOWUP_GOOD = {"id": 22352261, "sequence_step_id": 4770, "status": "scheduled",
                 "thread_reply": True,
                 "email_subject": "Re: profitability visible on Monday",
                 "email_body": "<p>Julian, the teams I work with.</p>",
                 "lead": {"id": 167609}}


class TheRowThatReachedAProspect(unittest.TestCase):
    """Step 4769's actual sent row is refused, in every field it was wrong."""

    def test_the_empty_opener_is_refused(self):
        faults = dict(emptyrender.classify_row(OPENER_BLANK))
        self.assertEqual(faults.get("body"), emptyrender.EMPTY)
        self.assertEqual(faults.get("subject"), emptyrender.EMPTY)

    def test_the_threaded_followup_is_refused_on_a_bare_Re(self):
        """`Re: ` alone is `{SUBJECT_1}` resolving to nothing, not a thread."""
        faults = dict(emptyrender.classify_row(FOLLOWUP_BLANK))
        self.assertEqual(faults.get("subject"), emptyrender.SUBJECT_RE)
        self.assertEqual(faults.get("body"), emptyrender.EMPTY)

    def test_a_real_email_is_not_refused(self):
        self.assertEqual(emptyrender.classify_row(OPENER_GOOD), [])
        self.assertEqual(emptyrender.classify_row(FOLLOWUP_GOOD), [])


class TheThreadedExemptionIsExactlyAsWideAsItWasArgued(unittest.TestCase):
    """A threaded follow-up may have NO subject. It may not have an empty body."""

    def test_an_empty_subject_on_a_threaded_row_is_allowed(self):
        row = dict(FOLLOWUP_GOOD, email_subject="")
        self.assertEqual(dict(emptyrender.classify_row(row)).get("subject"),
                         None)

    def test_an_empty_subject_on_an_OPENER_is_never_allowed(self):
        row = dict(OPENER_GOOD, email_subject="")
        self.assertEqual(dict(emptyrender.classify_row(row))["subject"],
                         emptyrender.EMPTY)

    def test_a_threaded_row_gets_no_exemption_on_its_body(self):
        row = dict(FOLLOWUP_GOOD, email_body="<p></p>")
        self.assertEqual(dict(emptyrender.classify_row(row))["body"],
                         emptyrender.EMPTY)


class TheOtherThreeShapes(unittest.TestCase):
    """`None`, placeholders, and HTML that renders to nothing."""

    def test_the_literal_None_is_refused(self):
        """`body_4` on the leads that rendered fine holds exactly this."""
        for value in ("None", "none", " NONE ", "null", "<p>None</p>"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.LITERAL_NONE)

    def test_an_unresolved_placeholder_is_refused(self):
        for value in ("<p>{BODY_1}</p>", "{{FIRST_NAME}}, hello"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.PLACEHOLDER)
        self.assertEqual(emptyrender.classify_subject("{SUBJECT_1}"),
                         emptyrender.PLACEHOLDER)

    def test_html_that_renders_to_nothing_is_refused(self):
        for value in ("<p></p>", "<br>", "<br/>", "&nbsp;", "  ",
                      "<p><br></p>", "<div>&nbsp;</div>"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.EMPTY)

    def test_a_body_merely_CONTAINING_a_break_is_a_real_body(self):
        """The nothing-match is anchored. A real body with `<br>` is real."""
        self.assertIsNone(
            emptyrender.classify_body("<p>Hello.<br>Second line.</p>"))


class TheScanSplitsWhatCanStillSendFromWhatCannot(unittest.TestCase):
    """The watcher halts on `pending`; `already` is the incident's record."""

    def test_a_scheduled_blank_is_pending(self):
        row = dict(OPENER_BLANK, status="scheduled")
        found = emptyrender.scan([row])
        self.assertEqual(len(found["pending"]), 1)
        self.assertEqual(found["already"], [])

    def test_a_sent_blank_is_already_and_does_not_halt(self):
        found = emptyrender.scan([OPENER_BLANK])
        self.assertEqual(found["pending"], [])
        self.assertEqual(len(found["already"]), 1)

    def test_a_stopped_blank_is_already(self):
        found = emptyrender.scan([FOLLOWUP_BLANK])
        self.assertEqual(found["pending"], [])
        self.assertEqual(len(found["already"]), 1)

    def test_the_scan_carries_no_prospect_identifier(self):
        """So a caller may log a finding into any channel."""
        entry = emptyrender.scan([OPENER_BLANK])["already"][0]
        self.assertEqual(set(entry), {"row", "lead", "step", "status",
                                      "faults"})
        self.assertNotIn("email", str(entry))

    def test_the_whole_497_queue_as_it_was(self):
        """All four rows together: two refused, two clean."""
        found = emptyrender.scan([OPENER_BLANK, FOLLOWUP_BLANK,
                                  OPENER_GOOD, FOLLOWUP_GOOD])
        self.assertEqual(len(found["already"]), 2)
        self.assertEqual(found["pending"], [])


class APausedCampaignIsDormantNotContained(unittest.TestCase):
    """491 row 22356723, and the day `already` stopped meaning "settled".

    The allowlist that shipped with the gate called four statuses sendable
    and everything else `already`. A paused campaign's rows are none of the
    four, so a blank sat in the bucket labelled "already sent or stopped"
    while being neither - one operator click from going out. Both witnesses
    reported `pending: 0` and both were reading this predicate.
    """

    def test_the_paused_blank_is_pending_not_already(self):
        found = emptyrender.scan([PAUSED_BLANK])
        self.assertEqual(len(found["pending"]), 1, "a paused blank can send")
        self.assertEqual(found["already"], [])
        self.assertEqual(found["pending"][0]["row"], 22356723)
        self.assertEqual(found["pending"][0]["lead"], 204724)

    def test_sending_paused_is_not_a_settled_status(self):
        self.assertNotIn("sending_paused", emptyrender.SETTLED_STATUSES)
        self.assertEqual(emptyrender.SETTLED_STATUSES,
                         frozenset({"sent", "stopped", "bounced"}))

    def test_a_status_nobody_has_seen_counts_as_able_to_send(self):
        """The denylist's whole point: fail toward halting, not toward calm."""
        for unknown in ("sending_resumed", "deferred", "held", "retrying", "?"):
            found = emptyrender.scan([dict(PAUSED_BLANK, status=unknown)])
            self.assertEqual(len(found["pending"]), 1, unknown)

    def test_well_rendered_paused_copy_still_halts_nothing(self):
        """274 of 491's 275 were fine. An unsettled status is not a fault."""
        found = emptyrender.scan([PAUSED_GOOD])
        self.assertEqual(found["pending"], [])
        self.assertEqual(found["already"], [])

    def test_the_sent_and_the_stopped_are_still_already(self):
        found = emptyrender.scan([OPENER_BLANK, FOLLOWUP_BLANK])
        self.assertEqual(found["pending"], [])
        self.assertEqual(len(found["already"]), 2)

    def test_the_491_queue_shape_splits_one_from_the_other(self):
        """The real read: one blank, one settled blank, one good, all paused."""
        found = emptyrender.scan([PAUSED_BLANK, PAUSED_GOOD, FOLLOWUP_BLANK])
        self.assertEqual([e["row"] for e in found["pending"]], [22356723])
        self.assertEqual([e["row"] for e in found["already"]], [22356508])


class TheWatcherHaltsAndTheGuardRefuses(unittest.TestCase):
    """Both controls are wired to the same predicate, and both are reachable."""

    def test_the_watcher_carries_the_check(self):
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "scripts", "bison_watch_loop.py")
        spec = importlib.util.spec_from_file_location("blw_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module._halt_on_blank_content))
        # A campaign with nothing pending does not halt.
        self.assertFalse(module._halt_on_blank_content(
            497, {"blanks": emptyrender.scan([OPENER_BLANK])}, lambda _l: None))

    def test_the_halt_actually_pauses_and_carries_a_write_scope(self):
        """The first live exercise of this halt paused NOTHING.

        2026-09-23T20:18:58Z, `work/provider-write-refusals.jsonl`: "no
        RESONATE_PROVIDER_WRITES and no allow_writes() scope". The watcher is
        a reader and holds no scope, so the guard refused the pause before it
        reached the provider - correctly - and the control was an alert that
        halted nothing. This pins the fix: the scope is open, it is scoped to
        the pause route alone, and the verb is actually called.
        """
        import importlib.util
        from src import providers as _providers
        from src.providers import bison as _bison
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "scripts", "bison_watch_loop.py")
        spec = importlib.util.spec_from_file_location("blw_pause", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        seen = {}
        real_pause, real_campaign = _bison.pause_campaign, _bison.campaign

        def _pause(campaign_id):
            allowed, why = _providers.writes_allowed(
                "https://send.example.test/api/campaigns/"
                f"{campaign_id}/pause")
            seen["allowed"], seen["why"] = allowed, why
            # And the scope must NOT reach a route it was not given.
            seen["attach_allowed"], _ = _providers.writes_allowed(
                "https://send.example.test/api/campaigns/"
                f"{campaign_id}/leads/attach-leads")
            seen["paused"] = campaign_id
            return {"campaign_id": campaign_id, "status": "paused"}

        _bison.pause_campaign = _pause
        _bison.campaign = lambda _cid: {"status": "paused"}
        try:
            blanks = emptyrender.scan([dict(OPENER_BLANK, status="scheduled")])
            lines = []
            halted = module._halt_on_blank_content(497, {"blanks": blanks},
                                                   lines.append)
        finally:
            _bison.pause_campaign, _bison.campaign = real_pause, real_campaign

        self.assertTrue(halted)
        self.assertEqual(seen.get("paused"), 497)
        self.assertTrue(seen.get("allowed"),
                        f"the pause was not authorised: {seen.get('why')}")
        self.assertFalse(seen.get("attach_allowed"),
                         "the halt's scope reached a route it was not given")
        self.assertTrue(any("BLANK-CONTENT" in l for l in lines))

    def test_the_push_guard_exists_and_refuses_on_a_blank_row(self):
        from src import bisonfactory
        from src.providers import bison as _bison
        report = {"provider": {}, "did": []}
        original = _bison.scheduled_emails
        _bison.scheduled_emails = lambda *_a, **_k: [dict(OPENER_BLANK,
                                                          status="scheduled")]
        try:
            with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                bisonfactory._refuse_blank_render(497, report)
            self.assertIn("would send nothing a person can read",
                          str(caught.exception))
        finally:
            _bison.scheduled_emails = original

    def test_an_empty_queue_is_reported_as_verified_NOTHING(self):
        """Zero rows checked must never read as a clean bill of health."""
        from src import bisonfactory
        from src.providers import bison as _bison
        report = {"provider": {}, "did": []}
        original = _bison.scheduled_emails
        _bison.scheduled_emails = lambda *_a, **_k: []
        try:
            bisonfactory._refuse_blank_render(497, report)
        finally:
            _bison.scheduled_emails = original
        self.assertEqual(report["provider"]["blank_render_checked"], 0)
        self.assertFalse(report["provider"]["blank_render_verified"])

    def test_an_unreadable_queue_refuses_rather_than_passing(self):
        from src import bisonfactory
        from src.providers import bison as _bison
        report = {"provider": {}, "did": []}
        original = _bison.scheduled_emails

        def _boom(*_a, **_k):
            raise RuntimeError("provider 500")

        _bison.scheduled_emails = _boom
        try:
            with self.assertRaises(bisonfactory.FactoryRefused):
                bisonfactory._refuse_blank_render(497, report)
        finally:
            _bison.scheduled_emails = original


class TheOldWayCalledThisEmailFine(unittest.TestCase):
    """The pre-fix predicate, reproduced, asserted to MISS the real row.

    `bisonfactory._approved_copy` refused a step only when the lead's own
    material was falsy - `not found.get("subject") or not found.get("body")`.
    Two things follow, and both are why 76 emails went out:

      1. it inspects OUR material, and the lead behind the sent blank row had
         no material here at all because we never staged it;
      2. `'None'` is a non-empty string, so a step whose body is the four
         characters `None` passes it.

    If this test ever fails, the old predicate has started catching the case -
    which would mean somebody changed what it is modelling, and this file is
    then lying about history rather than recording it.
    """

    @staticmethod
    def _old_predicate(found):
        return not found or not found.get("subject") or not found.get("body")

    def test_it_never_saw_the_lead_at_all(self):
        """Lead 167865 carried only `headline` and `location`."""
        material = {"headline": "Digital Project Manager", "location": "UK"}
        self.assertTrue(self._old_predicate(material))
        # It would have been reported missing - IF it had ever been in
        # `wanted`. It was not, and that is the whole 73.

    def test_it_passes_the_literal_None(self):
        old = self._old_predicate({"subject": "None", "body": "None"})
        self.assertFalse(old, "the old predicate accepted 'None'")
        self.assertEqual(emptyrender.classify_body("None"),
                         emptyrender.LITERAL_NONE)

    def test_it_passes_an_unresolved_placeholder(self):
        old = self._old_predicate({"subject": "{SUBJECT_1}",
                                   "body": "<p>{BODY_1}</p>"})
        self.assertFalse(old, "the old predicate accepted a raw placeholder")
        self.assertEqual(emptyrender.classify_body("<p>{BODY_1}</p>"),
                         emptyrender.PLACEHOLDER)

    def test_it_passes_html_that_renders_to_nothing(self):
        old = self._old_predicate({"subject": "Re: ", "body": "<p></p>"})
        self.assertFalse(old, "the old predicate accepted '<p></p>'")
        self.assertEqual(emptyrender.classify_body("<p></p>"),
                         emptyrender.EMPTY)


if __name__ == "__main__":
    unittest.main()
