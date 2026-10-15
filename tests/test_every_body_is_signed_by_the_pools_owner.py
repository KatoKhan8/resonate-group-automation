"""Every body is signed by its pool's owner - CANARY-01 blocker B7.

WHAT WAS MEASURED, 2026-10-14/15. The signature is composed at COPY TIME
from the client config's ``sender.name`` and rendered into every body
variable pushed to EmailBison. The attach path reads back pool membership
IDS ONLY, and nothing anywhere reconciles the pool's owners with the
composed name - the reconciliation the config's own comment demands before
any send does not exist in code. Measured against the operator's
2026-09-21 estate export (hash-joined to provider sender ids): the config
signs as a person who owns ZERO of the 225 mailboxes; 223 named-owner
mailboxes belong to nine other people; 2 mailboxes carry no attested
owner at all. Precedent: the 09-13 canary sent from another person's
mailbox while the engine signed the config's name.

THE NORMALISATION DECISION, operator, 2026-10-15, binding: EXACT match
after Unicode NFC normalisation and nothing else. No fuzzy matching, no
diacritic stripping, no case folding beyond what NFC gives. A loose
matcher would pass spellings it must not, which is a control that cannot
fail, and the catalogue is at ten owners already. So ``px`` equality is
exactly NFC-string equality, and a spelling with a stripped diacritic is
a DIFFERENT owner - which is the finding, not a tolerance to build in.

TWO CONSEQUENCES OF THAT DECISION, both intended. Comparison runs against
the live source rather than an export wherever possible; where only an
export exists and its text is damaged (U+FFFD), the row is classified
EXPORT-LIMITED - never a match, never a pronounced mismatch - rather than
reported as a mismatch that is an encoding artifact. And the five
misspelled mailboxes are a DATA DEFECT to be corrected in EmailBison, not
a case for the test to accept: their display names misspell an owner whose
Signature column spells correctly. That test stays RED and names the five.

CORRECTION, 2026-10-15. An earlier reading of the same export said it had
destroyed a diacritic (a literal U+FFFD). It had not: the file decodes as
strict utf-8 with U+0107/U+017E/U+010C intact, and the U+FFFD was a
cp1250 console-rendering artifact. The real diacritic-dropper is the
config's own ``sender.name`` (pure ASCII), so config-vs-estate is a REAL
mismatch under NFC-exact. The export-limited classification remains in the
ladder for a future genuinely mangled export; zero rows fire it today.

THE DOUBLE-SIGN GUARD EXISTS AND IS UNWIRED. ``sendersignature.
refuse_if_duplicate`` raises ``SignatureDuplicate`` on a body that already
carries the signature block - and has ZERO production callers (measured
2026-10-15: only tests import it). ``trailingcontent.compose`` appends the
signature unconditionally, so a pre-signed body in is a double-signed body
out. The wiring test below is RED for exactly that reason.

HYGIENE. The fixture ``tests/fixtures/sender-estate-2026-09-21.json``
carries no name in clear: owners and display names are px-<12 hex> under
the task189 salt, so this file can name ids and px values without ever
carrying the client's roster (tests/test_fixture_hygiene.py forbids those
surnames as substrings in any tracked file). px ids resolve to names only
through scripts/email_sender_estate.py, which is where the roster belongs.

THE FOUR RED TESTS self-destruct when their defect is fixed, per the
pattern this review established in B4: an ``expectedFailure`` whose test
starts passing becomes an UNEXPECTED SUCCESS that fails the suite until
the marker is removed. The ledger cannot outlive the defect it names.
"""
import hashlib
import inspect
import json
import os
import re
import unittest
import unicodedata
from collections import Counter

from src import clients, sendersignature, trailingcontent

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "sender-estate-2026-09-21.json")

#: As scripts/task189_scrub_pii.py and history_pii_scan.py, so px ids read
#: identically across every artifact this estate has ever produced.
SALT = "resonate-pii-salt-2026-09-16"

#: The px of the live config's sender.name as measured 2026-10-15. The
#: config drops its owner's diacritic (pure ASCII), which is why this px
#: matches NO mailbox's owner_px and only thirteen display names.
CONFIG_PX_TODAY = "px-fc7d1255b8a3"

#: The five mailboxes whose EmailBison DISPLAY NAME misspells an owner
#: whose Signature column spells correctly (operator decision 2026-10-15:
#: a data defect to correct in EmailBison, never a case for the test to
#: accept). name_px px-2f1dd920a186 vs owner_px px-387dd1f77205.
THE_FIVE = (2910, 3425, 3426, 3430, 3435)
MISSPELLED_PX = "px-2f1dd920a186"
CORRECT_PX = "px-387dd1f77205"

#: The two mailboxes with an EMPTY signature in the export: no attested
#: owner, so they can never satisfy the one-owner rule at all.
EMPTY_IDS = (2742, 2782)

#: The owner histogram of the 09-21 snapshot. Regenerating the fixture
#: from a newer export must be a conscious act: this pin fails and forces
#: a human to re-derive every estate relation in this file.
OWNER_SNAPSHOT = {
    "px-387dd1f77205": 71,
    "px-19834114d0e7": 58,
    "px-7513d195dfb1": 17,
    "px-c82dcaabaec1": 17,
    "px-494dc227d91e": 17,
    "px-75ee916b9999": 13,
    "px-898fe4fd21fe": 12,
    "px-a0e6d43e8d90": 11,
    "px-894888e9f1c3": 6,
    "px-523053400694": 1,
}
ROWS_TODAY = 225


def px_of(name):
    """NFC then the task189 salt: px equality is NFC-string equality."""
    return "px-" + hashlib.sha256(
        (SALT + unicodedata.normalize("NFC", name or "")).encode()
    ).hexdigest()[:12]


# --- the comparison ladder -------------------------------------------------

def classify(expected_px, row):
    """Classify one mailbox row against the px the config signs as.

    The ladder's order is the operator's decision, 2026-10-15, with rung 0
    added 2026-10-16 by TASK 0190:

    0. an owner is attested but        -> "unreadable"     (UNKNOWN. Not
       this code cannot read it                             ownerless, not
                                                            a mismatch, and
                                                            never a pass)
    1. no attested owner          -> "no-owner"       (never satisfiable)
    2. damaged source text        -> "export-limited" (can neither confirm
                                      nor deny - BEFORE any equality test,
                                      because a match on damaged text is
                                      luck, not identity)
    3. px equal under NFC-exact   -> "match"
    4. anything else              -> "mismatch"       (a REAL mismatch -
                                      stripped diacritics land here, by
                                      decision, not by accident)

    RUNG 0 IS THE WHOLE OF TASK 0190's LESSON. The first version of the
    live leg below read a field the provider does not have, got None,
    called 181 of 181 mailboxes ownerless, and reported mismatch == 0.
    "Ownerless" is a FACT about a mailbox - two real ones carry no
    signature at all. "I could not read the signature this mailbox
    carries" is not that fact; it is the absence of a reading. Collapsing
    the second into the first is how an instrument passes while seeing
    nothing, so they are now different rungs and the caller must refuse
    on rung 0. Invariant 0: an unreadable authority means UNKNOWN, and
    UNKNOWN never becomes PASS.
    """
    if row.get("unreadable"):
        return "unreadable"
    if not row.get("owner_present"):
        return "no-owner"
    if row.get("damaged"):
        return "export-limited"
    return "match" if row["owner_px"] == expected_px else "mismatch"


# --- the provider row ------------------------------------------------------
#
# TASK 0190, 2026-10-16. Everything in this section exists because the live
# leg at the bottom of this file used to read `row["signature"]`.
#
# MEASURED, not inferred, from the 181 captured page bodies of the one
# authorised /sender-emails walk (operator, 2026-10-15 23:00; the capture is
# in resonate-ops, outside git, and no further provider call was made to
# establish any of this). Key-set over all 181 rows: 24 distinct keys, the
# same 24 on every row ->
#
#   bounced_count created_at daily_limit email email_signature
#   emails_sent_count id imap_port imap_server interested_leads_count name
#   smtp_port smtp_server status tags total_leads_contacted_count
#   total_opened_count total_replied_count type unique_opened_count
#   unique_replied_count unsubscribed_count updated_at warmup_enabled
#
# `signature` and `Signature` are not among them, on any row. Both keys the
# old instrument read are absent from the entire estate.

#: The provider's field. One name, in one place, so a second reader cannot
#: guess a different one.
PROVIDER_SIGNATURE_FIELD = "email_signature"

#: What the old instrument read, kept so the control below can prove the
#: defect is gone rather than assert it.
FIELDS_THE_OLD_INSTRUMENT_READ = ("signature", "Signature")

#: The old pattern, same purpose. `[^<]+` stops at the `<br>` and `</p>`
#: never follows, so it matches ZERO of 181 rows even given the right field.
PATTERN_THE_OLD_INSTRUMENT_USED = r"<p[^>]*>([^<]+)</p>"

#: THE ONE SHAPE THIS ESTATE HAS. All 181 captured signatures reduce to
#: `<p>TEXT<br>TEXT</p>` - one shape, 181 of 181, no second form - the owner
#: first and the company second. So the owner is the first text node inside
#: the `<p>`, terminated by ANY tag rather than by `</p>`.
#:
#: Deliberately not a general HTML parser and deliberately not looser than
#: this: the operator's 2026-10-15 decision is that a loose matcher passes
#: spellings it must not. Anything that is not this shape is UNREADABLE
#: (rung 0), which refuses - it is not quietly re-read by a fallback.
_OWNER_IN_SIGNATURE = re.compile(r"\A<p[^>]*>\s*([^<]+?)\s*<", re.IGNORECASE)

#: Tags out, so "this block carries no text at all" can be told apart from
#: "this block carries text I could not read an owner out of". The first is
#: a fact about the mailbox (ownerless); the second is UNKNOWN.
_A_TAG = re.compile(r"<[^>]*>")


def signature_carries_text(sig_html):
    """True when the block has any text content outside its tags."""
    return bool(_A_TAG.sub("", sig_html or "").strip())


def owner_of_signature(sig_html):
    """The owner name a signature block attests, or "" when it reads none.

    "" means only "no name was read here". Whether that is an ownerless
    mailbox or an unreadable block is decided by
    `signature_carries_text`, because collapsing those two is the defect
    this section exists to kill.
    """
    m = _OWNER_IN_SIGNATURE.match((sig_html or "").strip())
    return (m.group(1).strip() if m else "")


class SignatureFieldMissing(ValueError):
    """The provider row carries no signature field at all.

    A hard failure, never a row classification: if this endpoint stops
    returning `email_signature` the instrument has lost its authority and
    must say so, not classify 181 rows as ownerless and pass.
    """


def estate_row_from_provider(row):
    """One /sender-emails row as a row the ladder can classify.

    Raises `SignatureFieldMissing` when the field is absent. That is the
    whole point: reading a key the provider does not have returns None
    silently, and None reads as "no attested owner".
    """
    if PROVIDER_SIGNATURE_FIELD not in row:
        raise SignatureFieldMissing(
            f"sender-email row id={row.get('id')!r} carries no "
            f"{PROVIDER_SIGNATURE_FIELD!r}; its keys are {sorted(row)}. "
            f"Refusing to classify: an absent authority is UNKNOWN, never "
            f"an ownerless mailbox")
    sig_html = row[PROVIDER_SIGNATURE_FIELD] or ""
    name = owner_of_signature(sig_html)
    return {
        "id": row.get("id"),
        "owner_present": bool(name),
        "owner_px": px_of(name) if name else None,
        # Text in the block but no name read out of it: UNKNOWN, rung 0.
        # A block with NO text (""/"<p></p>") is genuinely ownerless.
        "unreadable": signature_carries_text(sig_html) and not name,
        # The provider is the live source; export damage cannot apply.
        "damaged": False,
    }


def classify_provider_rows(rows, expected_px):
    """Classify a whole /sender-emails walk. Returns (verdicts, ids).

    Factored out of the live leg so the control below drives THE SAME CODE
    the live read drives. A control that exercises a re-implementation of
    the instrument is not a control.
    """
    verdicts, ids = Counter(), {}
    for row in rows:
        estate_row = estate_row_from_provider(row)
        verdict = classify(expected_px, estate_row)
        verdicts[verdict] += 1
        ids.setdefault(verdict, []).append(estate_row["id"])
    return verdicts, ids


class EstateNotOneOwner(ValueError):
    """The read estate does not prove one owner. Carries the reason."""


class EstateNotObserved(ValueError):
    """The read produced no owner reading at all, so it proves nothing."""


def refuse_unless_one_owner(verdicts, ids, expected_px):
    """Refuse unless the walk POSITIVELY shows one owner, and saw names.

    Four refusals, in this order, and the first three are what the old
    instrument had none of:

    1. `unreadable` > 0   - a signature exists and was not read. UNKNOWN.
    2. nothing observed   - zero rows reached an equality test at all, so
                            "no mismatch" is a statement about this code
                            and not about the estate. THIS IS THE SEAL:
                            the old instrument's 181 no-owners would stop
                            here even if rung 0 somehow did not fire.
    3. `no-owner` > 0     - a mailbox with no attested owner can never
                            satisfy the one-owner rule (same reasoning as
                            `OwnerlessMailbox` above), so it refuses
                            rather than being outvoted.
    4. `mismatch` > 0     - the real answer this instrument exists for.

    Returns the verdict Counter on success, so a caller reports what was
    seen rather than only that nothing was wrong.
    """
    if verdicts.get("unreadable"):
        raise EstateNotOneOwner(
            f"{verdicts['unreadable']} row(s) carry a signature this code "
            f"cannot read: ids {ids.get('unreadable')}. UNKNOWN is not a "
            f"pass; fix the reader or the shape changed")
    observed = verdicts.get("match", 0) + verdicts.get("mismatch", 0)
    if not observed:
        raise EstateNotObserved(
            f"no row reached the equality test, so this proves nothing "
            f"about the estate: {dict(verdicts)}. An instrument that sees "
            f"no owner name cannot report one owner")
    if verdicts.get("no-owner"):
        raise EstateNotOneOwner(
            f"{verdicts['no-owner']} mailbox(es) attest no owner at all: "
            f"ids {ids.get('no-owner')}; a mailbox with no owner can never "
            f"satisfy the one-owner rule")
    if verdicts.get("mismatch"):
        raise EstateNotOneOwner(
            f"{verdicts['mismatch']} of {observed} mailboxes attest an "
            f"owner other than {expected_px}: ids {ids.get('mismatch')}")
    return verdicts


# --- the pool rule ---------------------------------------------------------

class PoolEmpty(ValueError):
    """An empty pool is not a decision; nothing may be attached to one."""


class OwnerlessMailbox(ValueError):
    """A mailbox with no attested owner can never satisfy the one-owner
    rule, so its presence refuses the pool rather than being outvoted."""


class PoolNotOneOwner(ValueError):
    """The pool's mailboxes attest more than one distinct owner."""


def pool_owner(rows):
    """The single owner every mailbox in the pool attests, or a refusal.

    This is the offline primitive for the check the attach path never
    runs: production reads back pool membership ids only
    (providers/bison.py campaign_senders drops every other row field) and
    never asks who owns the mailboxes it just attached.
    """
    if not rows:
        raise PoolEmpty("the pool has no mailboxes; an empty pool is not "
                        "a decision")
    ownerless = [r["id"] for r in rows if not r.get("owner_present")]
    if ownerless:
        raise OwnerlessMailbox(
            f"mailbox(es) {ownerless} carry no attested owner; a mailbox "
            f"with no owner can never satisfy the one-owner rule")
    counts = Counter(r["owner_px"] for r in rows)
    if len(counts) > 1:
        detail = "; ".join(
            f"{o} x{counts[o]} ({' '.join(str(r['id']) for r in rows if r['owner_px'] == o)})"
            for o in sorted(counts))
        raise PoolNotOneOwner(
            f"the pool has {len(counts)} distinct owners: {detail}")
    return next(iter(counts))


# --- the once rule ---------------------------------------------------------

class SignatureMissing(ValueError):
    """The body does not carry the signature block it must carry."""


class SignatureDoubled(ValueError):
    """The body carries the signature block more than once."""


def carries_exactly_once(body, signature):
    """True when the body carries the signature block exactly once.

    The count is asserted, not boolean-tested: a doubled body is a
    different failure from an unsigned one, and the message says which.
    """
    if not (signature or "").strip():
        raise SignatureMissing("there is no signature block to carry; a "
                               "config with no sender name composes no "
                               "signature and can sign nothing")
    n = (body or "").count(signature)
    if n == 0:
        raise SignatureMissing("body does not carry the signature block")
    if n > 1:
        raise SignatureDoubled(f"body carries the signature block {n} "
                               f"times; refusing to double-sign")
    return True


# --- the real production chain --------------------------------------------

def the_real_chain(config=None):
    """Run the chain a prospect's email actually runs, return (body, sig)."""
    config = config if config is not None else clients.load("productive")
    signature = sendersignature.compose(clients.sender_identity(config))
    body = trailingcontent.compose(
        "sample body line.", ps="P.S. sample.",
        signature=signature, cta_link=None)
    return body, signature


def config_signature_px():
    """The px of the name the live config signs every body with."""
    config = clients.load("productive")
    name = (clients.sender_identity(config).get("name") or "")
    return px_of(name)


#: Abstract names only. The client's roster may not appear here (hygiene),
#: and self-proofs must not depend on which real person is measured.
NFC_COMPOSED = "Ada Lovelacé"        # precomposed e-acute
NFC_DECOMPOSED = "Ada Lovelacé"     # e + combining acute
DIACRITIC_STRIPPED = "Ada Lovelace"       # the config's own habit
CASE_FOLDED = "ada lovelacé"


def synthetic_row(id_, name, **over):
    row = {"id": id_, "owner_px": px_of(name), "owner_present": True,
           "name_px": px_of(name), "damaged": False}
    row.update(over)
    return row


class EstateTestCase(unittest.TestCase):
    """Loads the snapshot once, loudly: a missing fixture is an error,
    never a skip (the vacuous-pass lesson of this review, S19/S20)."""

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as f:
            doc = json.load(f)
        cls.rows = doc["rows"]
        cls.by_id = {r["id"]: r for r in cls.rows}


class ComparisonIsNfcExact(EstateTestCase):
    """Self-proofs that the classifier implements the operator's decision:
    NFC-exact, nothing else. Each proves the check can both fire and
    discriminate, so the RED legs below cannot be failing vacuously."""

    def test_canonically_equivalent_spellings_are_the_same_owner(self):
        composed = synthetic_row(1, NFC_COMPOSED)
        self.assertEqual(classify(px_of(NFC_COMPOSED), composed), "match")
        self.assertEqual(classify(px_of(NFC_DECOMPOSED), composed), "match",
                         "NFC equates composed and decomposed accents at "
                         "px time; this is the ONLY equivalence granted")

    def test_a_diacritic_stripped_spelling_is_a_different_owner(self):
        row = synthetic_row(2, NFC_COMPOSED)
        self.assertEqual(classify(px_of(DIACRITIC_STRIPPED), row),
                         "mismatch",
                         "operator decision 2026-10-15: stripping a "
                         "diacritic makes a DIFFERENT owner. The config's "
                         "ASCII spelling of its sender is not the same "
                         "person as the estate's owner - that is the "
                         "finding, not a tolerance to build in")

    def test_a_case_folded_spelling_is_a_different_owner(self):
        row = synthetic_row(3, NFC_COMPOSED)
        self.assertEqual(classify(px_of(CASE_FOLDED), row), "mismatch",
                         "no case folding beyond what NFC gives")

    def test_a_damaged_row_is_export_limited_even_when_it_would_match(self):
        row = synthetic_row(4, NFC_COMPOSED, damaged=True)
        self.assertEqual(classify(px_of(NFC_COMPOSED), row),
                         "export-limited",
                         "damaged is classified BEFORE equality: a match "
                         "on damaged text is luck, not identity")

    def test_a_damaged_row_is_export_limited_even_when_it_would_differ(self):
        row = synthetic_row(5, NFC_COMPOSED, damaged=True)
        self.assertEqual(classify(px_of(DIACRITIC_STRIPPED), row),
                         "export-limited",
                         "an encoding artifact is never pronounced a "
                         "mismatch; a live read settles it")

    def test_an_ownerless_row_is_no_owner(self):
        row = synthetic_row(6, NFC_COMPOSED, owner_present=False,
                            owner_px=None)
        self.assertEqual(classify(px_of(NFC_COMPOSED), row), "no-owner")


class ThePoolRule(EstateTestCase):
    """Self-proofs for pool_owner: each refusal names what a human needs
    to act on, and the real thirteen-mailbox pool resolves green."""

    def test_a_homogeneous_pool_yields_its_owner(self):
        pool = [synthetic_row(1, "Grace Hopper"),
                synthetic_row(2, "Grace Hopper")]
        self.assertEqual(pool_owner(pool), px_of("Grace Hopper"))

    def test_a_two_owner_pool_is_refused_naming_both_owners_and_the_row(self):
        """Assert the check was REACHED: the refusal names both px values
        and the id of the foreign mailbox, in one message. Substring
        checks rather than one regex, because the owners are listed in px
        order and the order of two hashes is nobody's contract."""
        pool = [synthetic_row(1, "Grace Hopper"),
                synthetic_row(2, "Grace Hopper"),
                synthetic_row(3, "Edsger Dijkstra")]
        with self.assertRaises(PoolNotOneOwner) as caught:
            pool_owner(pool)
        message = str(caught.exception)
        for needle in (px_of("Grace Hopper"), px_of("Edsger Dijkstra"),
                       "(3)"):
            self.assertIn(needle, message)

    def test_an_empty_pool_is_refused(self):
        with self.assertRaisesRegex(PoolEmpty, "no mailboxes"):
            pool_owner([])

    def test_an_ownerless_mailbox_refuses_the_pool_by_id(self):
        pool = [synthetic_row(1, "Grace Hopper"),
                synthetic_row(99, "anyone", owner_present=False,
                              owner_px=None)]
        with self.assertRaisesRegex(OwnerlessMailbox, "\\b99\\b"):
            pool_owner(pool)

    def test_the_real_thirteen_mailbox_pool_yields_its_single_owner(self):
        """Positive control on real data: the one pool in the snapshot
        that is genuinely homogeneous resolves to its owner."""
        pool = [r for r in self.rows if r["owner_px"] == "px-75ee916b9999"]
        self.assertEqual(len(pool), 13)
        self.assertEqual(pool_owner(pool), "px-75ee916b9999")


class EstateSnapshotPins(EstateTestCase):
    """Anti-vacuity pins (S19/S20): the fixture must BE the measured
    estate, or every test above is proving something about nothing."""

    def test_the_snapshot_holds_the_measured_rows(self):
        self.assertEqual(len(self.rows), ROWS_TODAY)
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(set(ids)), len(ids), "ids must be unique")
        self.assertEqual(ids, sorted(ids))

    def test_the_owner_histogram_is_the_measured_one(self):
        counts = Counter(r["owner_px"] for r in self.rows if r["owner_px"])
        self.assertEqual(dict(counts), OWNER_SNAPSHOT,
                         "the estate changed; re-derive every relation in "
                         "this file consciously, then re-pin")

    def test_the_five_named_defect_rows_are_present_as_measured(self):
        for i in THE_FIVE:
            r = self.by_id[i]
            self.assertEqual((r["name_px"], r["owner_px"]),
                             (MISSPELLED_PX, CORRECT_PX),
                             f"row {i} moved; the five are {THE_FIVE}")

    def test_the_two_ownerless_rows_are_the_measured_ones(self):
        self.assertEqual(
            sorted(r["id"] for r in self.rows if not r["owner_present"]),
            list(EMPTY_IDS))


class TheConfigToday(EstateTestCase):

    def test_the_live_config_still_signs_as_the_name_we_measured(self):
        """Change-detector, not an invariant: if sender.name moves, this
        fails loudly so the estate relations are re-derived instead of
        silently misclassifying against a name nobody re-measured."""
        self.assertEqual(config_signature_px(), CONFIG_PX_TODAY,
                         "config sender.name changed since 2026-10-15; "
                         "re-derive the estate relation and re-pin "
                         "CONFIG_PX_TODAY")


class TheFourRedTests(EstateTestCase):
    """One RED per named defect. Each carries ``expectedFailure`` so the
    suite stays green while the defect is unfixed, and self-destructs
    (unexpected success fails the suite) the moment it is - the marker
    is then removed, by hand, with the fix that removed it."""

    @unittest.expectedFailure
    def test_the_estate_backing_the_signature_is_one_pool_with_one_owner(self):
        """RED: pool-one-owner. The 225 mailboxes any campaign draws its
        pool from attest TEN distinct owners (and two attest none), while
        every body is signed by one name chosen at copy time.

        Today pool_owner raises OwnerlessMailbox for the two empty
        mailboxes; were those owned, it would raise PoolNotOneOwner
        naming all ten owners. This is the offline stand-in for the
        per-campaign pool check; the per-campaign form needs the live
        sender read (not approved as of 2026-10-15).
        """
        owner = pool_owner(self.rows)
        self.assertEqual(owner, config_signature_px())

    @unittest.expectedFailure
    def test_every_mailbox_owns_the_signature_it_is_made_to_send(self):
        """RED: signature equals owner. Under NFC-exact against the live
        config's px: today 0 match, 223 mismatch, 2 no-owner, 0
        export-limited - the person the config signs as owns no mailbox
        in the estate, and thirteen mailboxes carry that person's name as
        a DISPLAY name while attesting a different owner in their
        signature.

        The five misspelled display names are a DATA DEFECT to correct
        in EmailBison (operator, 2026-10-15), not a case for the test to
        accept: they fail here like every other row, and they are named.
        """
        expected = config_signature_px()
        verdicts = Counter(classify(expected, r) for r in self.rows)
        mismatches = sorted(r["id"] for r in self.rows
                            if classify(expected, r) == "mismatch")
        self.assertEqual(
            mismatches, [],
            f"signature px {expected} vs estate owners: "
            f"{verdicts.get('match', 0)} match, "
            f"{verdicts.get('mismatch', 0)} mismatch, "
            f"{verdicts.get('no-owner', 0)} no-owner, "
            f"{verdicts.get('export-limited', 0)} export-limited. "
            f"Mailboxes with no attested owner: {list(EMPTY_IDS)}. "
            f"The five EmailBison display-name defects (fix THERE, then "
            f"regenerate the fixture): {list(THE_FIVE)} "
            f"(name_px {MISSPELLED_PX} != owner_px {CORRECT_PX}). "
            f"The other mismatches are owner-by-owner facts of the "
            f"estate, each nameable via scripts/email_sender_estate.py.")
        self.assertGreater(verdicts.get("match", 0), 0,
                           "zero matches would make the no-mismatch "
                           "assertion vacuous; at least one mailbox must "
                           "be owned by the signer")

    @unittest.expectedFailure
    def test_the_five_misspelled_display_names_are_corrected_in_emailbison(self):
        """RED: the five, by name. Their Signature column spells the
        owner correctly; their Name (display) column drops a letter.
        The fix belongs in EmailBison's display-name field; once made and
        the fixture regenerated, this passes and the marker self-destructs.
        """
        for i in THE_FIVE:
            r = self.by_id[i]
            self.assertEqual(
                r["name_px"], r["owner_px"],
                f"EmailBison display-name defect (operator decision "
                f"2026-10-15): mailbox {i} displays {r['name_px']} while "
                f"its signature attests owner {r['owner_px']}. The five "
                f"are {list(THE_FIVE)}. Correct the display names in "
                f"EmailBison - this test accepts no substitute spelling.")

    @unittest.expectedFailure
    def test_the_compose_path_refuses_a_body_that_already_carries_the_signature(self):
        """RED: the double-sign guard is unwired.
        ``sendersignature.refuse_if_duplicate`` exists and works (its
        self-proof is green below) but has ZERO production callers -
        ``trailingcontent.compose`` appends the signature unconditionally,
        so a pre-signed body in is a double-signed body out. Wiring the
        existing guard into the composer makes this pass; the marker is
        then removed with the wiring commit.
        """
        body, sig = the_real_chain()
        with self.assertRaises(sendersignature.SignatureDuplicate):
            trailingcontent.compose(body, signature=sig)


class TheBodyCarriesTheSignatureExactlyOnce(EstateTestCase):
    """The once-check on the real production chain: it accepts the truth,
    refuses absence, refuses doubling with the count, and enforces the
    empty-name contract."""

    def test_the_real_chain_carries_the_signature_exactly_once(self):
        body, sig = the_real_chain()
        self.assertTrue(carries_exactly_once(body, sig))

    def test_an_unsigned_body_is_refused(self):
        body, sig = the_real_chain()
        unsigned = body.replace("\n\n" + sig, "")
        with self.assertRaisesRegex(SignatureMissing, "does not carry"):
            carries_exactly_once(unsigned, sig)

    def test_a_doubled_body_is_refused_with_the_count(self):
        body, sig = the_real_chain()
        with self.assertRaisesRegex(SignatureDoubled, "2 times"):
            carries_exactly_once(body + "\n\n" + sig, sig)

    def test_a_config_with_no_name_signs_nothing_and_the_once_check_refuses(self):
        """The existing contract: ``compose`` with no name returns the
        empty string, so there is no signature to carry - and counting an
        empty string must not be mistaken for carrying one."""
        sig = sendersignature.compose(
            clients.sender_identity({"sender": {"mode": "client_rep"}}))
        self.assertEqual(sig, "")
        with self.assertRaisesRegex(SignatureMissing,
                                    "no signature block"):
            carries_exactly_once("some body", sig)

    def test_the_production_double_sign_guard_works_where_it_is_called(self):
        """Positive control for the unwired finding: the guard itself is
        correct - it refuses a pre-signed body and passes a clean one."""
        body, sig = the_real_chain()
        with self.assertRaisesRegex(sendersignature.SignatureDuplicate,
                                    "refusing to double-sign"):
            sendersignature.refuse_if_duplicate(body, sig)
        clean = body.replace("\n\n" + sig, "")
        self.assertEqual(sendersignature.refuse_if_duplicate(clean, sig),
                         clean)


class ThePositiveControlForTheLiveLeg(EstateTestCase):
    """THE POSITIVE CONTROL. TASK 0190, 2026-10-16.

    The defect this replaces: the live leg read a field the provider does
    not have, could not have parsed the real shape even with the right
    field, classified 181 of 181 rows as ownerless, computed mismatch == 0
    and reported ok. Had the one authorised /sender-emails read been spent
    by simply setting `B7_LIVE_ESTATE=1`, criterion 7 would have been
    recorded MET by an instrument that never looked at an owner name.

    So the fix is not only the field and the pattern. It is this class.
    Every test here CALLS THE GATED METHOD ITSELF, through
    `drive_the_live_leg`, with the walk injected - so what is proven is
    the behaviour of the live leg and not of a re-implementation of it.
    A control that cannot go red is the defect rebuilt.

    No provider call is possible from here: `bison.sender_emails` is
    replaced for the duration, so no transport, no URL and no credential
    is reached. `calls` is asserted, because a stub that is never called
    is itself a control that sees nothing.

    Names here are abstract (hygiene); the SHAPE is the measured one.
    """

    SHAPE = "<p>%s<br>Productive</p>"

    def config_name(self):
        """The name the live config signs as - never written in clear."""
        return (clients.sender_identity(
            clients.load("productive")).get("name") or "")

    def row(self, id_, name, field=PROVIDER_SIGNATURE_FIELD):
        return {"id": id_, "name": name, "email": f"m{id_}@example.invalid",
                field: self.SHAPE % name}

    LEG = "test_the_live_estate_classifies_under_the_same_ladder"

    def the_real_leg(self):
        """The gated method's REAL body, unwrapped from its skip.

        ``unittest.skipUnless`` replaces the method with a wrapper that
        raises ``SkipTest`` when called, and ``functools.wraps`` records
        the original on ``__wrapped__``, which ``inspect.unwrap`` is the
        documented way to follow. THIS IS NOT COSMETIC: the first version
        of this control called the method directly, every one of its
        seven cases raised ``SkipTest``, and the run reported
        ``skipped=8`` and OK. A control that skips is a control that
        cannot go red - the very defect being fixed, in the fix.
        """
        gated = getattr(TheLiveRead, self.LEG)
        if not getattr(gated, "__unittest_skip__", False):
            # The gate has been lifted; the method is already the body.
            return gated
        body = inspect.unwrap(gated)
        self.assertIsNot(
            body, gated,
            "the skipped method exposes no __wrapped__, so this control "
            "would raise SkipTest and report as skipped rather than run")
        return body

    def test_the_live_leg_is_still_gated_and_its_body_is_reachable(self):
        """Pins both halves of the arrangement above: the live read stays
        behind the env var, AND the control can still reach the body. If
        either changes, this fails loudly instead of the seven cases
        below going quiet."""
        gated = getattr(TheLiveRead, self.LEG)
        self.assertTrue(getattr(gated, "__unittest_skip__", False),
                        "the /sender-emails read must stay gated")
        self.assertIsNot(self.the_real_leg(), gated)

    def drive_the_live_leg(self, rows, total=None):
        """Run the live leg's real body against injected rows.

        Returns the failure it raised, or None when it passed. No
        provider call is reachable: `bison.sender_emails` is replaced for
        the duration and `calls` is asserted, because a stub that is
        never called is a control that sees nothing.
        """
        from src.providers import bison
        calls = []

        def stub(*a, **k):
            calls.append((a, k))
            return list(rows), {"total": len(rows) if total is None else total,
                                "per_page": 15}

        case = TheLiveRead(self.LEG)
        body = self.the_real_leg()
        original = bison.sender_emails
        bison.sender_emails = stub
        try:
            try:
                body(case)
                failure = None
            except case.failureException as exc:
                failure = exc
        finally:
            bison.sender_emails = original
        self.assertEqual(len(calls), 1,
                         "the live leg did not read the walk at all; a "
                         "control whose stub is never called proves nothing")
        self.assertIs(bison.sender_emails, original, "left the module patched")
        return failure

    # --- the shape and the field, by measurement ---------------------------

    def test_the_measured_shape_yields_the_owner_name(self):
        """181 of 181 captured signatures are `<p>NAME<br>COMPANY</p>`."""
        self.assertEqual(
            owner_of_signature(self.SHAPE % NFC_COMPOSED), NFC_COMPOSED)

    def test_the_pattern_the_old_instrument_used_reads_nothing_here(self):
        """The regex defect, measured rather than asserted: `[^<]+` stops
        at the `<br>`, so `</p>` never follows and the old pattern matches
        the only shape this estate has ZERO times - even given the right
        field."""
        html = self.SHAPE % NFC_COMPOSED
        self.assertIsNone(re.match(PATTERN_THE_OLD_INSTRUMENT_USED, html),
                          "if this ever matches, the shape changed and the "
                          "history in this file needs re-measuring")
        self.assertEqual(owner_of_signature(html), NFC_COMPOSED,
                         "and the replacement reads it")

    def test_a_row_carrying_only_the_old_field_is_a_loud_refusal(self):
        """`signature` and `Signature` are absent from all 181 live rows.
        A row that carries one of them and not `email_signature` is an
        authority this code cannot read, so it raises - it is never
        classified ownerless."""
        for old in FIELDS_THE_OLD_INSTRUMENT_READ:
            row = {"id": 2763, old: self.SHAPE % NFC_COMPOSED}
            with self.assertRaisesRegex(SignatureFieldMissing,
                                        "carries no 'email_signature'"):
                estate_row_from_provider(row)

    # --- the live leg, driven -----------------------------------------------

    def test_an_estate_of_one_owner_passes(self):
        """Negative control FOR the control: the red below is conditional
        on the estate being wrong, not unconditional."""
        name = self.config_name()
        rows = [self.row(i, name) for i in (2763, 2760, 2751)]
        self.assertIsNone(self.drive_the_live_leg(rows))

    def test_one_differing_owner_turns_the_live_leg_RED_and_names_it(self):
        """THE POSITIVE CONTROL the task asks for: a row whose signature
        names someone other than the config's sender must FAIL, and the
        failure must say which mailbox."""
        name = self.config_name()
        rows = [self.row(2763, name), self.row(2760, name),
                self.row(2751, DIACRITIC_STRIPPED + " Nobody")]
        failure = self.drive_the_live_leg(rows)
        self.assertIsNotNone(
            failure, "a pool whose third mailbox attests a different owner "
                     "was reported ok; this instrument is blind again")
        self.assertIn("2751", str(failure))
        self.assertIn("attest an owner other than", str(failure))
        self.assertIn("1 of 3", str(failure),
                      "the refusal states how many of how many, because "
                      "one wrong mailbox in three is a different estate "
                      "from three wrong in three")
        self.assertNotIn("2763", str(failure),
                         "the two matching mailboxes must not be named as "
                         "mismatches")

    def test_the_whole_old_defect_cannot_report_ok(self):
        """The exact historical scenario, at estate scale: every row
        carries its signature under the field the old instrument read.
        The old code called this 181 ownerless rows and passed. It must
        now fail, and the message must name the field."""
        name = self.config_name()
        rows = [{"id": i, "signature": self.SHAPE % name}
                for i in range(2700, 2881)]
        self.assertEqual(len(rows), 181)
        from src.providers import bison
        original = bison.sender_emails
        bison.sender_emails = lambda *a, **k: (rows, {"total": len(rows)})
        try:
            with self.assertRaisesRegex(SignatureFieldMissing,
                                        "email_signature"):
                self.the_real_leg()(TheLiveRead(self.LEG))
        finally:
            bison.sender_emails = original

    def test_an_unreadable_signature_is_refused_not_counted_ownerless(self):
        """A non-empty signature in a shape this code does not read is
        UNKNOWN (rung 0) and refuses. The old collapse of UNKNOWN into
        "ownerless" is what made 181 blind rows look like a clean estate."""
        name = self.config_name()
        odd = {"id": 2751, PROVIDER_SIGNATURE_FIELD:
               f"{name}<br>Productive"}          # no <p> wrapper
        estate_row = estate_row_from_provider(odd)
        self.assertTrue(estate_row["unreadable"])
        self.assertFalse(estate_row["owner_present"])
        self.assertEqual(classify(px_of(name), estate_row), "unreadable")
        failure = self.drive_the_live_leg([self.row(2763, name), odd])
        self.assertIsNotNone(failure, "an unreadable signature passed")
        self.assertIn("cannot read", str(failure))
        self.assertIn("2751", str(failure))

    def test_an_estate_that_reads_nothing_at_all_is_refused(self):
        """THE SEAL. Every row unreadable: nothing reached the equality
        test, so mismatch is 0 and means nothing. This is the shape of
        the defect itself and it must not pass."""
        rows = [{"id": i, PROVIDER_SIGNATURE_FIELD: "Ada<br>Productive"}
                for i in (2763, 2760, 2751)]
        failure = self.drive_the_live_leg(rows)
        self.assertIsNotNone(failure, "a walk that read no owner name "
                                      "reported one owner")

    def test_an_empty_signature_is_ownerless_and_still_refuses(self):
        """The two real mailboxes with an empty signature are genuinely
        ownerless - a different fact from unreadable, and also not a pass:
        a mailbox with no attested owner can never satisfy the one-owner
        rule, so it refuses rather than being outvoted."""
        name = self.config_name()
        for empty in ("", "   ", "<p></p>", "<p> </p>"):
            with self.subTest(empty=empty):
                blank = {"id": 2742, PROVIDER_SIGNATURE_FIELD: empty}
                estate_row = estate_row_from_provider(blank)
                self.assertFalse(estate_row["unreadable"],
                                 "a block with no text at all attests no "
                                 "owner; that is a fact, not an UNKNOWN")
                self.assertEqual(classify(px_of(name), estate_row),
                                 "no-owner")
                failure = self.drive_the_live_leg(
                    [self.row(2763, name), blank])
                self.assertIsNotNone(failure, "an ownerless mailbox passed")
                self.assertIn("2742", str(failure))
                self.assertIn("no owner", str(failure))

    def test_a_block_with_text_but_no_name_slot_is_unreadable(self):
        """`<p><br>Productive</p>` carries text but nothing in the owner
        slot. That is not "this mailbox has no owner" - it is a shape
        this code does not understand, so it fails closed to UNKNOWN."""
        name = self.config_name()
        odd = {"id": 2782,
               PROVIDER_SIGNATURE_FIELD: "<p><br>Productive</p>"}
        estate_row = estate_row_from_provider(odd)
        self.assertTrue(estate_row["unreadable"])
        self.assertEqual(classify(px_of(name), estate_row), "unreadable")
        failure = self.drive_the_live_leg([self.row(2763, name), odd])
        self.assertIsNotNone(failure)
        self.assertIn("cannot read", str(failure))

    def test_the_nothing_observed_seal_refuses_on_its_own(self):
        """FOUND BY ATTACKING THIS CONTROL, 2026-10-16. Deleting the
        `if not observed` seal from `refuse_unless_one_owner` broke NO
        test: every walk that observes nothing also trips rung 0 or the
        no-owner rung first, so the seal was shadowed and untested - a
        guard nothing proves is a guard that can be removed by accident.

        It is kept, and tested here at its own level, because it is the
        only POSITIVE member of the refusal: the other three ask "did I
        find something wrong", and this one asks "did I see an owner name
        at all". That is precisely the question the old instrument never
        asked. It also catches the next version of the defect - a verdict
        label added to the ladder and forgotten in the refusal list -
        which is why `export-limited` is exercised below.
        """
        px = px_of(NFC_COMPOSED)
        for verdicts in (Counter(),
                         Counter({"export-limited": 181}),
                         Counter({"export-limited": 1, "no-owner": 0})):
            with self.subTest(verdicts=dict(verdicts)):
                with self.assertRaisesRegex(EstateNotObserved,
                                            "no row reached the equality"):
                    refuse_unless_one_owner(verdicts, {}, px)
        # And it does NOT fire once even one name was read.
        self.assertEqual(
            refuse_unless_one_owner(Counter({"match": 1}), {}, px),
            Counter({"match": 1}))

    def test_a_partial_walk_is_refused_even_when_every_row_matches(self):
        """Completeness is not implied by agreement. 181 of 225 rows all
        attesting one owner says nothing about the other 44."""
        name = self.config_name()
        rows = [self.row(i, name) for i in (2763, 2760, 2751)]
        self.assertIsNotNone(self.drive_the_live_leg(rows, total=225),
                             "a short walk was accepted")


class TheLiveRead(EstateTestCase):
    """The live legs, gated behind an explicit env var. NOT APPROVED as
    of 2026-10-15: the /sender-emails read waits for daylight. Note the
    scope: ``bison.sender_emails`` walks every page and refuses short
    lists by design (a page-1 read cannot support classification - it is
    the fifteen-inboxes trap that function was built to prevent), so
    enabling this leg is the full sanctioned walk, not the page-1 eyeball.
    """

    @unittest.skipUnless(
        os.environ.get("B7_LIVE_ESTATE"),
        "set B7_LIVE_ESTATE=1 only after the operator approves the "
        "/sender-emails read (full walk; page-1 is not classifiable). "
        "NOT APPROVED as of 2026-10-15.")
    def test_the_live_estate_classifies_under_the_same_ladder(self):
        """TASK 0190: this now uses the ladder it always claimed to.

        It reads `email_signature`, the field that exists; it refuses an
        unreadable signature instead of counting it ownerless; it refuses
        a walk that observed no owner name at all; and every line of that
        judgement is `classify_provider_rows` +
        `refuse_unless_one_owner`, which `ThePositiveControlForTheLiveLeg`
        below drives offline and proves can go RED.
        """
        from src.providers import bison
        rows, meta = bison.sender_emails()
        self.assertGreater(meta.get("total", 0), 0)
        # Completeness before classification. `sender_emails` raises
        # PartialInventory itself, so this is belt and braces on the one
        # number that makes a walk evidence rather than a sample.
        self.assertEqual(len(rows), meta["total"],
                         "a partial walk cannot settle an estate-wide "
                         "question")
        expected = config_signature_px()
        verdicts, ids = classify_provider_rows(rows, expected)
        # Not assertEqual(mismatch, 0): see refuse_unless_one_owner for
        # why three other outcomes must also refuse.
        try:
            refuse_unless_one_owner(verdicts, ids, expected)
        except (EstateNotOneOwner, EstateNotObserved) as exc:
            self.fail(f"live estate vs signature px {expected}: {exc}")


if __name__ == "__main__":
    unittest.main()
