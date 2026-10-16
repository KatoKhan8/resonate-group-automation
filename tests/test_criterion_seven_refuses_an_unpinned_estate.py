"""Criterion 7's estate input is AUTHENTICATED, or there is no verdict.

TASK 0231 (pilotcaps), 2026-10-16.

WHAT CRITERION 7 SAYS, verbatim, from its only authority
(`resonate-ops\\CANARY-01.md:121-127`, sha256
`9e0d5f77cb8ade251dafcd52b286e6b3de99e71f5a9fe0d9f97a916d09ee1e89`):

    7. Every sender email attached to the campaign has the same owner, and
       every rendered body is signed with that owner's name. A test goes RED
       when a campaign's attached pool contains two different owners, and RED
       when a body is signed by anyone other than the pool's owner. This must
       be a test and not a habit: the pool is homogeneous today, and one
       mailbox added later by someone else would silently make every body
       wrong - the same shape as the six controls already found unable to fail.

NOTE WHAT THAT LAST SENTENCE DOES TO THE SHAPE OF THE WORK. Criterion 7 does
not ask for a measurement; it asks for *a test that goes RED*. So no report,
however carefully measured, can satisfy it - which is why this is a test module
and not another document. `ThePerCampaignVerdict` in
`tests/test_the_attached_pool_is_one_owner_per_campaign.py` already supplies
the RED-on-two-owners and RED-on-a-foreign-signature halves. This module
supplies the rung underneath them, which was missing:

**THE VERDICT IS ONLY AS GOOD AS THE ESTATE IT WAS COMPUTED FROM, AND NOTHING
CHECKED THE ESTATE.** `canary_pool_readback.load_recorded_estate` opens a path
and parses it. It verifies no digest. So an estate file that had been edited,
regenerated, truncated or swapped since it was measured would be joined onto
the membership ids and would produce a confident `MET`, and the only thing
standing between that and a wrong verdict was that nobody had edited the file.
That is a habit, which is the exact word the criterion rules out.

THE FOUR CONTROLS, AND EACH IS SHOWN ABLE TO FAIL. A control that cannot fail
is this repository's own recurring defect, named in criterion 7's own text.
The mutation that breaks each one is written in its docstring, and the lane
entry records the run where each was applied and seen to go red:

    C1  a pinned estate, every cohort mailbox signed, one owner  -> MET
    C2  the same, one signature blanked                          -> NOT MET
    C3  the same, one cohort mailbox's row deleted               -> UNKNOWN
    C4  the same, one byte flipped                       -> REFUSED, no verdict

C1 exists because an instrument that only ever says no is useless and has been
shipped here before. C4 is the new rung; C2 and C3 pin the semantics C4 would
otherwise be able to fake, since a loader that refused everything would also
"pass" C2 and C3 for the wrong reason.

NO PROVIDER CALL, AND NO DEPENDENCE ON A FILE OUTSIDE GIT. The fixtures are
built here, in a temporary directory, and digested here. The real recorded walk
lives in `resonate-ops` because it carries 181 real addresses; the one test
that looks at it skips when it is absent, so this module is runnable from a
clean clone, which a test whose authority sits outside the repository is not.
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_readback():
    """Import `scripts/canary_pool_readback.py` by path.

    By path rather than by name because `scripts/` is not a package, and this
    is the same loader the sibling pool module uses - deliberately, so that
    both test modules exercise the one implementation rather than two copies
    that can drift apart.
    """
    path = os.path.join(ROOT, "scripts", "canary_pool_readback.py")
    spec = importlib.util.spec_from_file_location("canary_pool_readback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load_readback()

#: The ten approved sender ids, taken from the implementation rather than
#: retyped, so a change there cannot leave this module testing a stale pool.
POOL = sorted(rb.APPROVED_POOL)

#: The signature the ten mailboxes really carry and the ten approved bodies
#: really sign, measured from the hash-pinned estate export at 2026-10-16
#: 01:54:03Z. Spelled here so the fixture is the real shape - a `<br>` between
#: the name and the company - because a fixture using `<p>Name</p>` would pass
#: a reader that the real data defeats, which is the defect 0180 found.
REAL_SIGNATURE = "<p>Ivan Mamic<br>Productive</p>"


def _row(sender_id, signature=REAL_SIGNATURE):
    """One estate row in the provider's own shape.

    Only the keys the join and the ladder read are set. `email_signature` is
    the provider's field name; `signature` and `Signature` are NOT it, and a
    fixture that offered those instead would be testing the bug rather than
    the code.
    """
    return {
        "id": sender_id,
        "email": "sender-%d@example.invalid" % sender_id,
        "name": "Sender %d" % sender_id,
        "email_signature": signature,
        "status": "connected",
    }


def _write_estate(directory, rows, total=None):
    """Write an estate file in `load_recorded_estate`'s shape; return (path, digest)."""
    blob = {"rows": rows,
            "meta_returned": {"total": len(rows) if total is None else total}}
    path = os.path.join(directory, "estate.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(blob, handle)
    with open(path, "rb") as handle:
        return path, hashlib.sha256(handle.read()).hexdigest()


class TheControlsCanEachFail(unittest.TestCase):
    """C1-C4. Each test names the mutation that reddens it and nothing else."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="c7pin-")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for name in os.listdir(self.dir):
            os.unlink(os.path.join(self.dir, name))
        os.rmdir(self.dir)

    def _verdict(self, rows, digest_override=None, total=None):
        """Load pinned, then judge. Returns the verdict dict.

        The load and the judge are in one helper ON PURPOSE: it is the pair
        that matters. A test that loaded separately could assert on a refusal
        while a verdict had already been computed from the rows.
        """
        path, digest = _write_estate(self.dir, rows, total=total)
        estate, estate_total = rb.load_pinned_estate(
            path, digest if digest_override is None else digest_override)
        return rb.verdict_for_campaign(
            599020, list(POOL), estate, estate_total=estate_total)

    # --- C1 ---------------------------------------------------------------
    def test_c1_a_pinned_homogeneous_estate_is_MET(self):
        """C1: the instrument CAN say yes.

        TO SEE THIS FAIL: change one fixture row's signature to another
        person, e.g. `_row(POOL[0], "<p>Someone Else<br>Productive</p>")`.
        C1 goes red with `PoolNotOneOwner` and C2 stays red-for-its-own-reason,
        which is how you know C1 is reading the owner and not the row count.
        """
        verdict = self._verdict([_row(i) for i in POOL])
        self.assertEqual(verdict["verdict"], rb.MET,
                         "a pinned estate in which every one of the ten "
                         "mailboxes carries the same non-empty signature must "
                         "read MET; findings were %r" % (verdict["findings"],))
        self.assertEqual(verdict["attached"], POOL)
        self.assertIsNotNone(verdict["owner_px"],
                             "MET with no owner recorded would be a pass with "
                             "nothing behind it")

    def test_c1_is_not_passing_because_the_pool_is_empty(self):
        """C1's own control: MET must depend on the rows, not on the shape.

        Without this, C1 could be satisfied by an instrument that returns MET
        whenever it is handed anything at all.
        """
        verdict = self._verdict([_row(i) for i in POOL[:-1]])
        self.assertNotEqual(
            verdict["verdict"], rb.MET,
            "an estate missing one of the ten still read MET, so C1 proves "
            "nothing about the join")

    # --- C2 ---------------------------------------------------------------
    def test_c2_one_blank_signature_is_NOT_MET_and_names_the_mailbox(self):
        """C2: a blanked signature refuses, and says which mailbox.

        TO SEE THIS FAIL: in `test_every_body_is_signed_by_the_pools_owner`,
        weaken the emptiness test to a null test - treat `sig is not None` as
        a signature. A blank block then reads as a named owner, C2 goes green
        for the wrong reason, and C1 stays green, which is precisely the
        "control unable to fail" shape. C2 red while C1 green is the signal.

        NOT MET rather than UNKNOWN is deliberate and is the implementation's
        own documented choice: a block with no text is a MEASURED fact about
        that mailbox, not an unreadable authority.
        """
        rows = [_row(i) for i in POOL]
        rows[3]["email_signature"] = "   "
        verdict = self._verdict(rows)
        self.assertEqual(verdict["verdict"], rb.NOT_MET,
                         "a mailbox with a whitespace-only signature must be "
                         "NOT MET, not UNKNOWN and certainly not MET")
        reasons = " ".join(f["reason"] for f in verdict["findings"])
        self.assertIn(str(POOL[3]), reasons,
                      "the refusal must NAME the offending mailbox: a verdict "
                      "that says 'something is wrong' is not actionable. "
                      "reasons were %r" % reasons)
        # AND IT MUST REFUSE FOR THE RIGHT REASON. Added on 0231's
        # re-dispatch, because the two assertions above are satisfied by a
        # verdict that calls the blank mailbox a SECOND OWNER named `None`
        # instead of an ownerless one - NOT MET either way, and the id named
        # either way. Measured: with the emptiness test nulled AND
        # `pool_owner`'s message made None-safe, all 16 tests went green on a
        # destroyed blank check. The verdict value alone cannot see that.
        self.assertIn("no attested owner", reasons,
                      "a blank signature must be refused AS AN OWNERLESS "
                      "MAILBOX. reasons were %r" % reasons)
        self.assertNotIn("distinct owners", reasons,
                         "a mailbox with no signature is not a second owner: "
                         "a phantom owner reported as a heterogeneous pool "
                         "hides the fact that the emptiness test did not run. "
                         "reasons were %r" % reasons)

    def test_c2_a_blank_signature_is_ownerless_not_a_second_owner(self):
        """C2 at the guard's own level, asserting on the EXCEPTION TYPE.

        The test above reads the verdict the whole instrument assembles, so a
        different rung answering first is invisible to it. This one calls the
        emptiness guard directly and asserts WHICH refusal it raises, which no
        rung above it can fake.

        TO SEE THIS FAIL: null the emptiness test in
        `test_every_body_is_signed_by_the_pools_owner.estate_row_from_provider`
        (`"owner_present": sig_html is not None`). `pool_owner` then raises
        `PoolNotOneOwner` instead and this test goes red on the type, with no
        dependence on a `TypeError` in the refusal's own message formatting.
        """
        from tests import test_every_body_is_signed_by_the_pools_owner as sg

        rows = [_row(i) for i in POOL]
        rows[3]["email_signature"] = "   "
        ladder = [sg.estate_row_from_provider(r) for r in rows]
        # Catch the whole refusal family rather than one member, so a WRONG
        # refusal fails on its type with that type named, instead of
        # propagating as a bare error a reader has to decode.
        try:
            sg.pool_owner(ladder)
        except (sg.OwnerlessMailbox, sg.PoolNotOneOwner, sg.PoolEmpty) as exc:
            raised = exc
        else:
            self.fail("a pool containing a blank signature must be refused; "
                      "pool_owner returned an owner instead")
        self.assertIsInstance(
            raised, sg.OwnerlessMailbox,
            "the refusal must be OwnerlessMailbox. %s says the blank mailbox "
            "was counted as a second OWNER, which means the emptiness test "
            "never ran: %s" % (type(raised).__name__, raised))
        self.assertIn(str(POOL[3]), str(raised))
        # and the nine that ARE signed must still resolve to one owner, or
        # this test would pass on an instrument that refused everything.
        self.assertEqual(
            sg.px_of("Ivan Mamic"),
            sg.pool_owner([l for l in ladder if l["id"] != POOL[3]]),
            "the control's own control: the other nine must still be one "
            "owner, or a guard that refuses every pool would 'pass' here")

    def test_c2_blank_and_absent_are_not_the_same_verdict(self):
        """The two failure modes C2 and C3 cover must stay distinguishable.

        If a future change collapsed them, C2 and C3 would both pass while the
        instrument had stopped telling a measured emptiness from an unreadable
        authority - which is the invariant-0 distinction this estate turns on.
        """
        blanked = [_row(i) for i in POOL]
        blanked[0]["email_signature"] = ""
        deleted = [_row(i) for i in POOL[1:]]
        self.assertEqual(self._verdict(blanked)["verdict"], rb.NOT_MET)
        self.assertEqual(self._verdict(deleted)["verdict"], rb.UNKNOWN)

    # --- C3 ---------------------------------------------------------------
    def test_c3_a_missing_row_is_UNKNOWN_never_an_all_clear(self):
        """C3: a cohort mailbox with no row reads UNKNOWN, not PASS.

        TO SEE THIS FAIL: make `rb.resolve` an inner join - drop ids with no
        row instead of returning them in `unresolved`. The nine rows that DO
        resolve are homogeneous, so the verdict becomes MET and C3 goes red
        while C1 stays green. That is the whole reason C3 exists: silence is
        not consent and absence is not a pass.
        """
        rows = [_row(i) for i in POOL if i != POOL[2]]
        verdict = self._verdict(rows)
        self.assertEqual(verdict["verdict"], rb.UNKNOWN,
                         "a membership id that resolves to no row must be "
                         "UNKNOWN; findings were %r" % (verdict["findings"],))
        reasons = " ".join(f["reason"] for f in verdict["findings"])
        self.assertIn(str(POOL[2]), reasons,
                      "UNKNOWN must name the unresolved id, or a reader "
                      "cannot act on it")
        self.assertNotIn(
            rb.MET, [f["verdict"] for f in verdict["findings"]],
            "no finding may read MET on a run whose overall verdict is UNKNOWN")

    def test_c3_a_partial_walk_cannot_produce_a_verdict_about_absence(self):
        """A short walk is UNKNOWN even when every row it DID return agrees.

        A walk can only undercount, so an undercount reads as "this id is not
        in the estate" - a loud failure invented out of a partial read.
        """
        verdict = self._verdict([_row(i) for i in POOL], total=181)
        self.assertEqual(verdict["verdict"], rb.UNKNOWN)
        self.assertIn("partial",
                      " ".join(f["reason"] for f in verdict["findings"]))

    # --- C4 ---------------------------------------------------------------
    def test_c4_a_flipped_byte_refuses_before_any_join(self):
        """C4: a hash mismatch refuses, and produces NO verdict at all.

        TO SEE THIS FAIL: delete the digest comparison in
        `load_pinned_estate`, or move it to after `load_recorded_estate`
        returns. C4 goes red; C1, C2 and C3 all stay green, because they never
        exercise a mismatched file. That asymmetry is the point - C4 is the
        only control that observes the authentication rung.
        """
        rows = [_row(i) for i in POOL]
        path, digest = _write_estate(self.dir, rows)
        flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
        with self.assertRaises(rb.EstateNotPinned) as caught:
            rb.load_pinned_estate(path, flipped)
        message = str(caught.exception)
        self.assertIn("does not match its pin", message)
        self.assertIn(digest, message,
                      "the refusal must print the MEASURED digest in full, or "
                      "the reader cannot tell a stale pin from a changed file")

    def test_c4_refuses_before_the_file_is_even_parsed(self):
        """C4's ORDER, which asserting the refusal alone does NOT establish.

        FOUND BY ATTACKING C4 RATHER THAN BY A FAILING TEST. The first version
        of this module asserted only that a mismatched pin raises. A mutation
        that moved the digest comparison to AFTER `load_recorded_estate`
        returned - so the file WAS parsed, and in a caller with side effects
        would have been joined - was invisible to all 15 tests. "Refuses" and
        "refuses before anything else happens" are different claims and the
        brief asked for the second.

        THE PROBE: a file whose bytes are not the pinned bytes AND whose
        contents are not valid JSON. The exception type says which rung ran
        first, with no instrumentation and no mocking:

            check first  -> EstateNotPinned      (correct)
            parse first  -> JSONDecodeError      (the rung ran out of order)

        TO SEE THIS FAIL: move the digest comparison below the
        `load_recorded_estate` call in `load_pinned_estate`.
        """
        path = os.path.join(self.dir, "estate.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{this is not json at all")
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        wrong = ("0" if digest[0] != "0" else "1") + digest[1:]

        with self.assertRaises(rb.EstateNotPinned) as caught:
            rb.load_pinned_estate(path, wrong)
        self.assertIn("does not match its pin", str(caught.exception))

        # The control for the probe itself: with the RIGHT pin the same file
        # must fail at the parse. Without this, the test above would pass
        # against a loader that refused every file for any reason, and a probe
        # that cannot distinguish its two outcomes measures nothing.
        with self.assertRaises(json.JSONDecodeError):
            rb.load_pinned_estate(path, digest)

    def test_c4_refuses_an_absent_pin_rather_than_running_unpinned(self):
        """No digest is a refusal, not silent permission.

        The dangerous shape is `expected_sha256=None` quietly meaning "skip the
        check", which is how every optional guard in this estate has failed.
        """
        rows = [_row(i) for i in POOL]
        path, _digest = _write_estate(self.dir, rows)
        for bad in (None, "", "   ", "deadbeef", "not-hex-at-all-xyz!"):
            with self.subTest(pin=bad):
                with self.assertRaises(rb.EstateNotPinned):
                    rb.load_pinned_estate(path, bad)

    def test_c4_an_unreadable_estate_is_UNKNOWN_not_empty(self):
        """A path that cannot be opened refuses; it does not read as zero rows."""
        with self.assertRaises(rb.EstateNotPinned) as caught:
            rb.load_pinned_estate(
                os.path.join(self.dir, "no-such-estate.json"), "a" * 64)
        self.assertIn("cannot be read", str(caught.exception))

    def test_c4_a_matching_pin_loads_and_a_truncated_pin_is_accepted(self):
        """The guard must still admit the real pin this estate recorded.

        The estate's own records pin artifacts to sixteen hex digits. A loader
        that only accepted sixty-four could not be handed the recorded pin, so
        it would be bypassed - and a guard nobody can call is a guard nobody
        runs.
        """
        rows = [_row(i) for i in POOL]
        path, digest = _write_estate(self.dir, rows)
        for pin in (digest, digest[:rb.MIN_PIN_HEX]):
            with self.subTest(pin_length=len(pin)):
                loaded, total = rb.load_pinned_estate(path, pin)
                self.assertEqual(len(loaded), len(POOL))
                self.assertEqual(total, len(POOL))
        with self.assertRaises(rb.EstateNotPinned):
            rb.load_pinned_estate(path, digest[:rb.MIN_PIN_HEX - 1])


class TheDenominatorIsPrintedOrNeitherNumberIs(unittest.TestCase):
    """A percentage with no denominator beside it is failure family 2 here."""

    def test_the_verdict_carries_the_approved_set_and_the_attached_set(self):
        directory = tempfile.mkdtemp(prefix="c7den-")
        self.addCleanup(lambda: (
            [os.unlink(os.path.join(directory, n))
             for n in os.listdir(directory)], os.rmdir(directory)))
        path, digest = _write_estate(directory, [_row(i) for i in POOL])
        estate, total = rb.load_pinned_estate(path, digest)
        verdict = rb.verdict_for_campaign(599020, list(POOL), estate,
                                          estate_total=total)
        self.assertEqual(verdict["approved"], POOL,
                         "the verdict must carry the denominator it judged "
                         "against, not just a pass")
        self.assertEqual(verdict["attached"], POOL)
        self.assertEqual(len(estate), total,
                         "a complete walk must report len(rows) == meta.total")

    def test_an_unread_membership_is_UNKNOWN_and_reports_no_attached_set(self):
        """Membership is the input the offline estate CANNOT supply.

        This is the finding 0231 reached and it is recorded as a test so it
        cannot quietly stop being true: the recorded estate walk answers who
        owns a mailbox, and nothing offline answers which mailboxes are
        ATTACHED. `membership=None` is UNKNOWN - never an empty pool, and
        never MET.
        """
        directory = tempfile.mkdtemp(prefix="c7mem-")
        self.addCleanup(lambda: (
            [os.unlink(os.path.join(directory, n))
             for n in os.listdir(directory)], os.rmdir(directory)))
        path, digest = _write_estate(directory, [_row(i) for i in POOL])
        estate, total = rb.load_pinned_estate(path, digest)
        verdict = rb.verdict_for_campaign(599020, None, estate,
                                          estate_total=total)
        self.assertEqual(verdict["verdict"], rb.UNKNOWN)
        self.assertIsNone(verdict["attached"],
                          "an unread membership must not be rendered as an "
                          "empty attached set")


#: The recorded walk, and the pin recorded for it in
#: `FINDING-the-one-authorised-read-2026-10-15.md:60`. Outside git by design -
#: it carries 181 real addresses - so the test below SKIPS when it is absent
#: rather than failing, and asserts only on counts and on whether a field
#: exists. No address and no signature string is ever printed from it.
RECORDED_WALK = os.path.join(
    r"C:\Users\Zvonimir\Desktop\resonate-ops", "canary",
    "sender-emails-live-2026-10-15.json")
RECORDED_WALK_PIN = "b677205570bba0bd"


class TheRealRecordedWalk(unittest.TestCase):
    """What the offline estate can and cannot establish, against the real file."""

    def setUp(self):
        if not os.path.exists(RECORDED_WALK):
            self.skipTest("the recorded walk is outside git and is not on "
                          "this machine: %s" % RECORDED_WALK)

    def test_the_recorded_walk_still_matches_the_pin_it_was_recorded_under(self):
        rows, total = rb.load_pinned_estate(RECORDED_WALK, RECORDED_WALK_PIN)
        self.assertEqual(len(rows), 181)
        self.assertEqual(total, 181,
                         "len(rows) == meta.total is what makes this walk "
                         "COMPLETE rather than a sample; a sample cannot "
                         "resolve an id's absence")

    def test_every_recorded_row_carries_the_providers_signature_field(self):
        """0180's defect 1, reproduced offline: the field is `email_signature`.

        `signature` and `Signature` are absent from every row, so a reader
        looking for either sees nothing on all 181 - and `mismatch == 0` then
        holds vacuously. This asserts the POSITIVE form, which is the repair
        0180 asked for: every row must be NAMED, so the next version cannot
        pass by seeing nothing.
        """
        rows, _total = rb.load_pinned_estate(RECORDED_WALK, RECORDED_WALK_PIN)
        named = sum(1 for r in rows
                    if str(r.get(rb.PROVIDER_SIGNATURE_FIELD) or "").strip())
        self.assertEqual(named, len(rows),
                         "every recorded row must carry a non-empty %r"
                         % rb.PROVIDER_SIGNATURE_FIELD)
        for absent in ("signature", "Signature"):
            self.assertEqual(
                [r for r in rows if absent in r], [],
                "%r is not the provider's field name; a reader using it sees "
                "nothing on every row and passes vacuously" % absent)

    def test_the_ten_approved_ids_all_resolve_in_the_recorded_walk(self):
        rows, _total = rb.load_pinned_estate(RECORDED_WALK, RECORDED_WALK_PIN)
        resolved, unresolved, duplicated = rb.resolve(list(POOL), rows)
        self.assertEqual(unresolved, [],
                         "an approved pool id with no row in the complete "
                         "walk would make criterion 7 UNKNOWN")
        self.assertEqual(duplicated, [])
        self.assertEqual(len(resolved), len(POOL))


if __name__ == "__main__":
    unittest.main(verbosity=2)
