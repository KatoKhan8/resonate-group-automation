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

    The ladder's order is the operator's decision, 2026-10-15:

    1. no attested owner          -> "no-owner"       (never satisfiable)
    2. damaged source text        -> "export-limited" (can neither confirm
                                      nor deny - BEFORE any equality test,
                                      because a match on damaged text is
                                      luck, not identity)
    3. px equal under NFC-exact   -> "match"
    4. anything else              -> "mismatch"       (a REAL mismatch -
                                      stripped diacritics land here, by
                                      decision, not by accident)
    """
    if not row.get("owner_present"):
        return "no-owner"
    if row.get("damaged"):
        return "export-limited"
    return "match" if row["owner_px"] == expected_px else "mismatch"


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
        from src.providers import bison
        rows, meta = bison.sender_emails()
        self.assertGreater(meta.get("total", 0), 0)
        expected = config_signature_px()
        verdicts = Counter()
        for row in rows:
            sig_html = (row.get("signature") or row.get("Signature") or "")
            m = re.match(r"<p[^>]*>([^<]+)</p>", sig_html.strip())
            name = (m.group(1).strip() if m else "").strip()
            verdicts["no-owner" if not name else
                     ("match" if px_of(name) == expected else "mismatch")] += 1
        self.assertEqual(verdicts.get("mismatch", 0), 0,
                         f"live estate vs signature px {expected}: "
                         f"{dict(verdicts)}")


if __name__ == "__main__":
    unittest.main()
