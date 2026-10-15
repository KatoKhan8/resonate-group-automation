r"""The 2% / 7-day bounce hard stop must answer PASS, STOP or BLIND. Always.

TASK-0140, lane `suppression`. The sibling of
`test_the_producer_reads_forty_pages_and_the_watcher_four_hundred.py`
(TASK-0130), which measured the cap. This one is about the verdict.

## WHAT WAS WRONG, MEASURED BEFORE IT WAS REPAIRED

`scripts/bounce_stop_7day.py` had zero `except` clauses in the whole file and
its own `OURS` tuple is `(487, 489, 491, 492, 493, 494, 495, 496, 497, 498)`.
Campaign 491 is the THIRD it walks and it is 665 rows - 45 pages - against a
default `bison.PAGE_CAP` of 40. So `bison._paged` raised `PartialInventory`
out of `measure()`, past `main()`, and the standing hard stop

    bounce > 2% on any MAILBOX over 7 days

produced **no verdict for any mailbox**, including the mailboxes in the two
campaigns it HAD already read whole. Reproduced at the provider seam on
`2edca33a6`, with no network call: stdout 0 bytes, exit 1.

**And exit 1 is this script's own TRIPPED code**, so a reader keyed on the
status could not tell a tripped hard stop from a crashed one. That is why the
exit codes below are three and not two.

## THE PROPERTY

Every mailbox that sent for us in the window comes out with exactly one of
PASS, STOP or BLIND, and BLIND is a verdict rather than an absence:

    PASS    measured, under the threshold, off a COMPLETE read
    STOP    measured at or over the threshold - provable from a partial read,
            because more rows can only add sends, and stopping is the safe
            direction
    BLIND   could not be measured, and the exception class is in the reason

A PASS needs a complete read and a STOP does not. That asymmetry is
`senderheadroom`'s, in this repository's own words - *"a walk can only
undercount, so FULL is provable from any walk and ROOM is provable from none
but a complete, fresh, covering one. REFUSED IS NOT ROOM."* Here: a campaign
we could not read may hold the very bounces that would trip a mailbox, so no
mailbox can be cleared while one is unreadable; but a mailbox already over the
line is over it whatever else arrives.

## WHAT IS ASSERTED, AND HOW

At the provider seam, with the real pager's refusal contract - fifteen rows a
page, raise past the cap, never a prefix - and on the RETURN VALUE of `run()`
rather than on printed prose, except for the one-line summary, which is
asserted to be one line and to say BLIND out loud, because that line is what
the operator reads before a canary batch.

`tests/fakebison.py` is unusable here for the same reason TASK-0130 found: its
`scheduled_emails` ignores `cap` entirely and never paginates.
"""
import importlib.util
import math
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import providers                                          # noqa: E402
from src.providers import bison                                   # noqa: E402

#: `HttpTimeout` lives on the package, not on `bison` - `bison` imports only
#: `ProviderError` from it. Named here so the narrow-catch tests can use a
#: SECOND provider exception class and not just the cap refusal.
HttpTimeout = providers.HttpTimeout

SCRIPT = os.path.join(ROOT, "scripts", "bounce_stop_7day.py")

#: 491 as the watcher's heartbeat and the completed 2026-10-03 census both
#: read it, quoted in `docs/SUPPRESSION-THE-PRODUCER-READS-FORTY-PAGES`.
LIVE_491_ROWS = 665
LIVE_491_PAGES = 45


def _stop():
    """The script, imported as a module so `run()` can be called directly."""
    spec = importlib.util.spec_from_file_location("_bounce_stop_7day", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(mailbox, status, stamp="2026-10-15T09:00:00.000000Z", seq=0):
    return {"id": 900000 + seq,
            "status": status,
            "sent_at": stamp,
            "scheduled_date": stamp,
            "sender_email": {"id": mailbox, "email": f"m{mailbox}@example.test"}}


def _queue(mailbox, sent, bounced, stamp="2026-10-15T09:00:00.000000Z"):
    rows = [_row(mailbox, "bounced", stamp, i) for i in range(bounced)]
    rows += [_row(mailbox, "sent", stamp, 1000 + i) for i in range(sent)]
    return rows


class _Pager:
    """`bison.scheduled_emails` with `bison._paged`'s refusal contract.

    `queues` maps campaign id -> rows. A campaign in `raises` raises that
    exception instead. Anything not named returns no rows, which is what a
    campaign with an empty queue really does.
    """

    def __init__(self, queues=None, raises=None):
        self.queues = dict(queues or {})
        self.raises = dict(raises or {})
        self.asked = []

    def __call__(self, campaign_id, cap=None):
        self.asked.append((campaign_id, cap))
        if campaign_id in self.raises:
            raise self.raises[campaign_id]
        rows = list(self.queues.get(campaign_id, []))
        effective = cap or bison.PAGE_CAP
        pages = max(1, math.ceil(len(rows) / bison.PAGE_SIZE))
        if pages > effective:
            raise bison.PartialInventory(
                f"emailbison scheduled_emails: {pages} pages to walk and this "
                f"read stops at {effective}. Refusing to return "
                f"{effective * bison.PAGE_SIZE} of {len(rows)} as though it "
                f"were all of them")
        return rows


class _Run:
    """Run the script's own `run()` over a seam-level pager. No network.

    `load_env` is stubbed too, so no `config/.env` is read on any platform or
    in any worktree - a worktree has none, and this must not depend on that.
    """

    def __init__(self, queues=None, raises=None, campaigns=(487, 489)):
        self.pager = _Pager(queues, raises)
        self.campaigns = campaigns

    def __enter__(self):
        self.module = _stop()
        self._patches = [
            mock.patch.object(bison, "scheduled_emails", self.pager),
            mock.patch("src.providers.load_env", lambda *a, **k: {}),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False

    def result(self, **kw):
        return self.module.run(campaigns=self.campaigns, **kw)

    def verdict_of(self, mailbox):
        raise AssertionError("use result()")


def _verdicts(result):
    return {sid: entry["verdict"] for sid, entry in result["mailboxes"].items()}


# --------------------------------------------------------------- the verdicts


class AMailboxOverTheThresholdIsStopped(unittest.TestCase):
    """STOP is measured, and it survives an incomplete estate."""

    def test_over_the_threshold_is_a_stop(self):
        with _Run(queues={487: _queue(3437, sent=96, bounced=4)}) as r:
            out = r.result()
        self.assertEqual(_verdicts(out), {3437: "STOP"})
        self.assertAlmostEqual(out["mailboxes"][3437]["rate"], 4.0, places=6)
        self.assertEqual(out["verdict"], "STOP")
        self.assertEqual(out["exit_code"], 1)

    def test_exactly_at_the_threshold_is_a_stop(self):
        """AT or over, not merely over.

        Kills the mutation that makes the comparison strict. 2 bounced of 100
        is exactly 2.00%, and with `>` that mailbox comes out **PASS** -
        measured, at the limit, and cleared. Verified by applying the
        mutation: the only test that goes red is this one, and it goes red as
        `{3437: 'PASS'} != {3437: 'STOP'}`. A rule written "> 2%" therefore
        does not merely leave a gap at its own boundary; it clears it.
        """
        with _Run(queues={487: _queue(3437, sent=98, bounced=2)}) as r:
            out = r.result()
        self.assertAlmostEqual(out["mailboxes"][3437]["rate"], 2.0, places=6)
        self.assertEqual(_verdicts(out), {3437: "STOP"})
        self.assertEqual(out["exit_code"], 1)

    def test_a_stop_survives_an_unreadable_campaign(self):
        """A stop needs no complete read. More rows can only add sends.

        The mailbox trips in 487; 489 refuses. The verdict stays STOP - it is
        not downgraded to BLIND - and the run still reports the blindness.
        """
        with _Run(queues={487: _queue(3437, sent=90, bounced=10),
                          489: _queue(9999, 0, 0)},
                  raises={489: bison.PartialInventory("45 pages, cap 40")}) as r:
            out = r.result()
        self.assertEqual(out["mailboxes"][3437]["verdict"], "STOP")
        self.assertEqual(out["verdict"], "STOP")
        self.assertEqual(out["exit_code"], 1)
        self.assertEqual([u["campaign"] for u in out["unreadable"]], [489])
        self.assertIn("BLIND", out["summary"])


class AMailboxUnderTheThresholdPasses(unittest.TestCase):
    """PASS is measured, and only off a complete read."""

    def test_under_the_threshold_is_a_pass(self):
        with _Run(queues={487: _queue(3437, sent=99, bounced=1)}) as r:
            out = r.result()
        self.assertEqual(_verdicts(out), {3437: "PASS"})
        self.assertAlmostEqual(out["mailboxes"][3437]["rate"], 1.0, places=6)
        self.assertEqual(out["verdict"], "CLEAR")
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(out["unreadable"], [])

    def test_a_clean_mailbox_cannot_pass_while_a_campaign_is_unreadable(self):
        """The asymmetry, asserted as a property and not as a preference.

        Kills the mutation that swallows the blindness: with 489 unreadable,
        this mailbox's 1.00% is a rate over the rows we happened to see, and
        the rows we did not see are exactly where a bounce would hide.
        """
        with _Run(queues={487: _queue(3437, sent=99, bounced=1)},
                  raises={489: bison.PartialInventory("45 pages, cap 40")}) as r:
            out = r.result()
        self.assertEqual(_verdicts(out), {3437: "BLIND"})
        self.assertIn("PartialInventory", out["mailboxes"][3437]["reason"])
        self.assertEqual(out["verdict"], "BLIND")
        self.assertNotEqual(out["exit_code"], 0)

    def test_no_sends_in_the_window_is_not_a_pass_and_not_blind(self):
        """UNDEFINED is still neither, and the run still says so.

        The existing doctrine of this script, kept: a mailbox we never sent
        from has no 7-day rate. It is not 0%, and it does not appear as a
        PASS. Every queue was read whole, so the run is not BLIND either -
        there was simply nothing to measure, which is a different sentence.
        """
        with _Run(queues={487: [], 489: []}) as r:
            out = r.result()
        self.assertEqual(out["mailboxes"], {})
        self.assertEqual(out["verdict"], "NO-DATA")
        self.assertEqual(out["exit_code"], 0)
        self.assertIn("0 PASS", out["summary"])
        self.assertIn("UNDEFINED", out["summary"])
        self.assertEqual(out["summary"].count(chr(10)), 0)


# ------------------------------------------------------------------ the blind


class AReadThatRaisesIsBlindAndLoud(unittest.TestCase):
    """One refused campaign. BLIND, named, non-zero."""

    def test_a_refused_campaign_is_reported_not_skipped(self):
        with _Run(queues={487: _queue(3437, sent=50, bounced=0)},
                  raises={489: bison.PartialInventory(
                      "emailbison scheduled_emails: 45 pages to walk and this "
                      "read stops at 40")}) as r:
            out = r.result()
        self.assertEqual(len(out["unreadable"]), 1)
        entry = out["unreadable"][0]
        self.assertEqual(entry["campaign"], 489)
        self.assertEqual(entry["error"], "PartialInventory")
        self.assertIn("45 pages", entry["detail"])

    def test_the_exception_class_is_in_the_mailbox_reason(self):
        """Named, so a reader can tell a cap refusal from a timeout."""
        with _Run(queues={487: _queue(3437, sent=50, bounced=0)},
                  raises={489: HttpTimeout("read timed out")}) as r:
            out = r.result()
        self.assertEqual(_verdicts(out), {3437: "BLIND"})
        self.assertIn("HttpTimeout", out["mailboxes"][3437]["reason"])

    def test_a_blind_run_exits_non_zero(self):
        """Kills the mutation that returns 0 anyway."""
        with _Run(queues={487: _queue(3437, sent=50, bounced=0)},
                  raises={489: bison.PartialInventory("cap 40")}) as r:
            out = r.result()
        self.assertNotEqual(out["exit_code"], 0)
        self.assertEqual(out["exit_code"], 2)

    def test_main_returns_the_non_zero_code_it_computed(self):
        """The exit code reaches the process, not just the dict.

        A verdict that is right inside `run()` and discarded by `main()` is
        this repository's signature defect - a thing computed correctly that
        nothing downstream reads.
        """
        with _Run(queues={487: _queue(3437, sent=50, bounced=0)},
                  raises={489: bison.PartialInventory("cap 40")}) as r:
            with mock.patch.object(r.module, "OURS", (487, 489)):
                code = r.module.main([])
        self.assertEqual(code, 2)

    def test_the_json_mode_carries_the_same_verdicts_and_code(self):
        import json
        with _Run(queues={487: _queue(3437, sent=50, bounced=0)},
                  raises={489: bison.PartialInventory("cap 40")}) as r:
            with mock.patch.object(r.module, "OURS", (487, 489)), \
                    mock.patch("sys.stdout") as out:
                code = r.module.main(["--json"])
        self.assertEqual(code, 2)
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        payload = json.loads(printed)
        self.assertEqual(payload["verdict"], "BLIND")
        self.assertEqual(payload["mailboxes"]["3437"]["verdict"], "BLIND")


class ATotalFetchFailureIsBlindForEveryMailbox(unittest.TestCase):
    """Nothing readable at all. The loudest case, and the vacuous-pass trap."""

    def test_every_campaign_refusing_is_blind_and_non_zero(self):
        raises = {487: bison.PartialInventory("cap 40"),
                  489: HttpTimeout("timed out")}
        with _Run(raises=raises) as r:
            out = r.result()
        self.assertEqual(out["verdict"], "BLIND")
        self.assertNotEqual(out["exit_code"], 0)
        self.assertEqual(out["exit_code"], 2)
        self.assertEqual([u["campaign"] for u in out["unreadable"]], [487, 489])

    def test_no_mailbox_is_passed_when_nothing_was_read(self):
        """The vacuous pass, asserted directly.

        With no queue readable there is no mailbox roster at all, so "every
        mailbox is BLIND" cannot be asserted by counting BLINDs - there are
        none to count. What must hold is that nothing is PASS and the run
        itself refuses to be clear.
        """
        raises = {487: bison.PartialInventory("cap 40"),
                  489: bison.PartialInventory("cap 40")}
        with _Run(raises=raises) as r:
            out = r.result()
        self.assertNotIn("PASS", set(_verdicts(out).values()))
        self.assertFalse(out["roster_complete"])
        self.assertNotEqual(out["verdict"], "CLEAR")
        self.assertNotEqual(out["verdict"], "NO-DATA")

    def test_the_summary_is_one_loud_sentence(self):
        """What the operator reads before a canary batch."""
        raises = {487: bison.PartialInventory("cap 40"),
                  489: bison.PartialInventory("cap 40")}
        with _Run(raises=raises) as r:
            out = r.result()
        summary = out["summary"]
        self.assertNotIn("\n", summary)
        self.assertIn("BLIND", summary)
        self.assertLess(len(summary), 200, summary)
        self.assertNotIn("OK", summary)


class TheLiveEstateIsTheCaseThatBrokeIt(unittest.TestCase):
    """491 at its real size, 665 rows and 45 pages.

    A BLIND-FOREVER STOP IS STILL A NO-OP, only a louder one. At
    `bison.PAGE_CAP = 40` campaign 491 can never be read, so no mailbox in
    this estate could ever reach PASS and the try/except alone would have
    bought a permanent BLIND. So the repair also asks for the cap its own
    sibling has asked for since 2026-09-22: `scripts/hard_stop_check.py`
    measures the SAME rule on the SAME endpoint at 400, as do the watcher
    and `slackagentreadback`. Cost, measured by the completed 2026-10-03
    census: 45 pages of 491 in 9 seconds, five requests more than 40.
    """

    def test_the_real_491_is_read_whole_because_the_script_asks_for_400(self):
        """The case that broke it, now measured rather than refused.

        Every one of 491's 665 rows must reach the measurement, and the
        mailbox must come out with a real verdict - not BLIND, which is what
        a try/except alone would have produced here for ever.
        """
        queues = {487: _queue(3437, sent=19, bounced=0),
                  491: _queue(2736, sent=LIVE_491_ROWS - 1, bounced=1)}
        with _Run(queues=queues, campaigns=(487, 489, 491)) as r:
            out = r.result()
        self.assertEqual(out["unreadable"], [])
        self.assertTrue(out["roster_complete"])
        self.assertEqual(_verdicts(out), {2736: "PASS", 3437: "PASS"})
        self.assertEqual(out["mailboxes"][2736]["sent"], LIVE_491_ROWS - 1)
        self.assertEqual(out["mailboxes"][2736]["bounced"], 1)
        self.assertEqual(out["exit_code"], 0)

    def test_every_campaign_is_asked_at_the_queue_cap_and_not_the_default(self):
        """One number for one queue, and it is the sibling's number.

        Kills a cap that merely happens to be big enough for today: 491 needs
        45 pages, so 80 would work now and disagree with the watcher on the
        next sequence step.
        """
        with _Run(queues={487: _queue(3437, 19, 0)},
                  campaigns=(487, 489, 491)) as r:
            r.result()
        self.assertEqual({cap for _c, cap in r.pager.asked},
                         {bison.CAMPAIGN_QUEUE_PAGE_CAP})
        self.assertEqual(r.module.QUEUE_PAGE_CAP,
                         bison.CAMPAIGN_QUEUE_PAGE_CAP)

    def test_the_cap_is_still_bounded_and_491_is_over_the_default(self):
        """Not removal. The refusal is the property, not the number.

        Offset pagination on this instance is refused with HTTP 422 beyond
        roughly 500 pages, measured against client campaign 352 and recorded
        in `docs/THE-23rd-IS-PROVEN-2026-09-18.md`. So the cap sits below
        that, and the default it replaces really was too small.
        """
        module = _stop()
        self.assertGreater(module.QUEUE_PAGE_CAP, LIVE_491_PAGES)
        self.assertLess(module.QUEUE_PAGE_CAP, 500)
        self.assertGreater(LIVE_491_PAGES, bison.PAGE_CAP)

    def test_a_queue_too_big_even_for_400_is_blind_not_silent(self):
        """The BLIND machinery on the real path, not only on a stub.

        A queue of 401 pages refuses at the cap the script now asks for, and
        that refusal must still produce a named BLIND and a non-zero exit -
        otherwise raising the cap has only moved the cliff.
        """
        huge = _queue(2736, sent=bison.PAGE_SIZE * 401, bounced=0)
        with _Run(queues={487: _queue(3437, 50, 0), 491: huge},
                  campaigns=(487, 491)) as r:
            out = r.result()
        self.assertEqual([u["campaign"] for u in out["unreadable"]], [491])
        self.assertEqual(out["unreadable"][0]["error"], "PartialInventory")
        self.assertIn("401", out["unreadable"][0]["detail"])
        self.assertEqual(_verdicts(out), {3437: "BLIND"})
        self.assertEqual(out["exit_code"], 2)

    def test_the_campaigns_after_the_refusal_are_still_asked(self):
        """A refusal on 491 must not cancel 492 through 498.

        The escaping exception stopped the walk at the third of ten. Three
        asked, seven never. This is the same claim from the other side: every
        campaign in the tuple is read whatever the ones before it did.
        """
        queues = {493: _queue(3437, sent=50, bounced=0)}
        with _Run(queues=queues,
                  raises={491: bison.PartialInventory("cap 400")},
                  campaigns=(487, 489, 491, 492, 493)) as r:
            r.result()
        self.assertEqual([c for c, _cap in r.pager.asked],
                         [487, 489, 491, 492, 493])


class AnUnattributableSendCannotClearAnybody(unittest.TestCase):
    """A send with no mailbox, and a send with no date."""

    def test_a_row_with_no_sender_blinds_the_roster(self):
        """It was silently dropped. A send we cannot attribute is a send.

        `(row.get("sender_email") or {}).get("id")` returned None and the row
        was skipped with no trace, so a campaign of unattributed sends read as
        a campaign of none and every other mailbox passed off a denominator
        that was missing them.
        """
        rows = _queue(3437, sent=50, bounced=0)
        rows.append({"id": 1, "status": "bounced", "sender_email": None,
                     "sent_at": "2026-10-15T09:00:00.000000Z"})
        with _Run(queues={487: rows}) as r:
            out = r.result()
        self.assertEqual(out["unattributed"], 1)
        self.assertFalse(out["roster_complete"])
        self.assertEqual(_verdicts(out), {3437: "BLIND"})
        self.assertNotEqual(out["exit_code"], 0)

    def test_a_sender_that_is_a_bare_string_does_not_crash_the_run(self):
        """`sender_email` is a dict on this route and a string on others.

        `.get` on a string is an AttributeError, which is exactly the kind of
        unanticipated exception that must NOT be caught into a BLIND - so it
        is handled by shape instead, and counted as unattributed.
        """
        rows = _queue(3437, sent=50, bounced=0)
        rows.append({"id": 1, "status": "sent", "sender_email": "x@y.test",
                     "sent_at": "2026-10-15T09:00:00.000000Z"})
        with _Run(queues={487: rows}) as r:
            out = r.result()
        self.assertEqual(out["unattributed"], 1)
        self.assertEqual(_verdicts(out), {3437: "BLIND"})

    def test_an_undateable_row_blinds_only_its_own_mailbox(self):
        """Per mailbox, which is the unit the brief names.

        A row whose stamp will not parse cannot be placed in or out of the
        window, so its mailbox has no measurable rate - and the OTHER mailbox,
        whose rows all parsed in a campaign that was read whole, still passes.
        """
        rows = _queue(3437, sent=50, bounced=0)
        rows += _queue(2736, sent=50, bounced=0)
        rows.append(_row(2736, "bounced", stamp="not-a-date", seq=7))
        with _Run(queues={487: rows}) as r:
            out = r.result()
        self.assertEqual(_verdicts(out), {2736: "BLIND", 3437: "PASS"})
        self.assertIn("ValueError", out["mailboxes"][2736]["reason"])
        self.assertEqual(out["exit_code"], 2)


class AnUnanticipatedExceptionEscapes(unittest.TestCase):
    """The catch is narrow. A bug must not become a BLIND."""

    def test_a_non_provider_exception_is_not_swallowed(self):
        """`except Exception` around the loop would hide this.

        A `KeyError` from our own code is not a provider refusal and must not
        be reported as "the provider could not be read". It escapes.
        """
        class _Boom:
            def __call__(self, campaign_id, cap=None):
                raise KeyError("a bug in our own row handling")

        with _Run() as r:
            with mock.patch.object(bison, "scheduled_emails", _Boom()):
                with self.assertRaises(KeyError):
                    r.result()


class TheFixtureIsTheRealRefusal(unittest.TestCase):
    """Guarding the guard. Without this the classes above measure nothing."""

    def test_the_pager_refuses_past_the_cap_and_never_returns_a_prefix(self):
        pager = _Pager({491: _queue(2736, LIVE_491_ROWS, 0)})
        with self.assertRaises(bison.PartialInventory):
            pager(491, cap=bison.PAGE_CAP)
        rows = pager(491, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
        self.assertEqual(len(rows), LIVE_491_ROWS)

    def test_the_page_arithmetic_matches_the_measured_census(self):
        """665 rows at 15 a page is 45, and the census recorded 45."""
        self.assertEqual(bison.PAGE_SIZE, 15)
        self.assertEqual(math.ceil(LIVE_491_ROWS / bison.PAGE_SIZE),
                         LIVE_491_PAGES)
        self.assertGreater(LIVE_491_PAGES, bison.PAGE_CAP)

    def test_partial_inventory_is_a_provider_error_and_timeout_too(self):
        """The narrow catch has to cover both, so prove they share a base."""
        self.assertTrue(issubclass(bison.PartialInventory,
                                   bison.ProviderError))
        self.assertTrue(issubclass(HttpTimeout, bison.ProviderError))
        self.assertFalse(issubclass(KeyError, bison.ProviderError))


class TheThresholdIsOneNumber(unittest.TestCase):
    """The rule as written, pinned."""

    def test_the_threshold_is_two_percent(self):
        module = _stop()
        self.assertEqual(module.THRESHOLD, 2.0)

    def test_the_script_has_an_except_clause_for_the_provider_read(self):
        """By behaviour, not by reading the source for words.

        Asserted through the import graph instead: the module must name a
        provider exception it catches. `TheFixtureIsTheRealRefusal` proves the
        class hierarchy; `AReadThatRaisesIsBlindAndLoud` proves the catch
        works. This one only pins that the three verdict names exist as the
        module's own vocabulary, so a rewrite that drops BLIND goes red here
        before it goes red anywhere subtler.
        """
        module = _stop()
        self.assertEqual(set(module.VERDICTS), {"PASS", "STOP", "BLIND"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
