"""The provider does the signing - B7 narrowed, operator decision 2026-10-15.

THE DIAGNOSIS, NARROWED. EmailBison's per-account signatures are already
correct: every named row in the operator's 09-21 estate export carries a
Signature attesting that row's own owner (measured: Signature matches the
row's Name on 194 of 225 rows; the 31 disagreements are display-name
spellings, chiefly diacritic-strippings, and the five-letter misspelling
on five rows recorded in the sibling test file). The provider side is
right. THE DEFECT IS THAT WE SIGN THE BODY AS WELL:
``sendersignature.compose`` reads ``sender.name`` from the client config
and renders it into every body variable pushed to EmailBison, and the
provider then appends its own per-account signature. A recipient can
receive a body signed by one name followed immediately by a signature
block reading another. Two signatures, two different people, one email.

MEASURED BEFORE THESE TESTS WERE WRITTEN (NEXT-glm.md, 2026-10-14):

1. The double signature end to end. BOTH HALVES are measured offline:
   our pushed bodies carry the composed signature (the chain below),
   and all 223 named accounts carry their own Signature in the provider
   (the export). Whether EmailBison appends its signature to a body that
   already contains one is NOT settleable from stored state - no
   artifact records a delivered post-TASK-906 body (the 09-13 canary's
   expected_body predates TASK-906 and carries no sign-off; the
   incident sent-rows carry subject but no body; the reply ledger is
   classified metadata only). If the provider SUPPRESSES its signature
   when the body already carries one, the defect shrinks to "the wrong
   name in the body" - still a defect, different severity. The operator
   said he would rather know than assume; this file names the link as
   UNKNOWN rather than assuming either way.

2. Every place ``sender.name`` reaches a body, file:line:
   ``src/bisonfactory.py:2120`` composes it and ``:2131``/``:2148``
   render it into every body variable (projection and rendered email
   share ``trailingcontent.compose``); ``src/render.py:49-61`` the same
   for the rendered-email surface; ``src/render.py:112-123`` the human
   review card (internal surface); ``src/configdiff.py:729-744`` config-
   diff sample bodies (internal surface); ``src/sequenceplan.py:367``
   carries the identity on the plan; ``src/generate.py:666,719`` put
   ``sender_identity`` into the WRITER PROMPT (the model is told who is
   writing - a leak path into generated prose, not a render).

3. What breaks if the name leaves the body: ``approval.
   sender_fingerprint`` (``src/approval.py:241-265``) hashes the CONFIG'S
   sender block plus ``sendersignature.compose`` of it - NOT the body -
   so removing the signature from bodies does not stale any stamp
   (3005 stamps are already stale for other reasons, measured
   2026-09-28). ``sequencegate`` and ``copylint`` gate on links and
   words, not on the signature's presence. The projection and the
   rendered email stay byte-identical because both call the same
   composer. The consumers that DO assert presence are TESTS:
   ``tests/test_task906_signature_composed_into_copy.py`` and
   ``tests/test_the_signoff_name_is_the_mailbox_owners_full_name.py``
   - both need rewriting alongside the production change, which is the
   operator's to order (it touches prospect-facing output and waits).

THE BODY CHANGE IS NOT MADE HERE. These tests are the RED ledger for
the decision the operator has already recorded: the body ends at its
last sentence; the provider does the signing. Each marker
self-destructs (unexpected success fails the suite) the moment the
production change lands, per the pattern this review established.

HYGIENE: no roster name appears here. The config's sender name is read
at RUNTIME from the loaded config and compared as a substring; the
self-proofs use abstract names only.
"""
import unittest

from src import bisonfactory, clients, sendersignature, trailingcontent

#: The fixed second line of every sign-off block this system composes.
COMPANY_LINE = sendersignature.COMPANY_LINE


def signoff_pairs(body):
    """Every (name_line, company_line) pair in a body.

    Structural, so it fires for ANY name above the company line - the
    config's person today, any of the estate's ten owners tomorrow. The
    owner set itself cannot be named in a tracked file (roster hygiene),
    and does not need to be: a sign-off block is a sign-off block
    whoever it names.
    """
    lines = (body or "").splitlines()
    return [i for i in range(len(lines) - 1)
            if lines[i + 1].strip() == COMPANY_LINE and lines[i].strip()]


def the_real_chain():
    """The production body composition, exactly as a prospect receives it
    from our side (body, P.S., signature, opt-out - in the fixed order)."""
    config = clients.load("productive")
    signature = sendersignature.compose(clients.sender_identity(config))
    body = trailingcontent.compose(
        "sample body line.", ps="P.S. sample.",
        signature=signature, cta_link=None)
    return body, signature


def the_real_variables():
    """The body variables actually pushed to the provider for one lead,
    through ``bisonfactory._variables_for`` - the production staging path.
    """
    lead = {"record_id": "r-b7", "contact_key": "c-b7",
            "persona": None,
            "subject": "sample subject", "body": "sample body line.",
            "ps": "sample ps",
            "copy": [{"step_key": "em1", "subject": "sample subject",
                      "body": "sample body line.", "ps": "sample ps"}]}
    campaign = {"client": "productive"}
    sender = clients.sender_identity(clients.load("productive"))
    return bisonfactory._variables_for(lead, campaign, sequence=(),
                                       sender=sender)


class TheSelfProofs(unittest.TestCase):
    """The detector must fire and discriminate before any RED leg can
    mean anything."""

    def test_a_signoff_pair_is_detected_whosever_name_it_carries(self):
        body = "some sentence.\n\nAda Lovelace\nProductive\n\nP.S. x"
        pairs = signoff_pairs(body)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(body.splitlines()[pairs[0]], "Ada Lovelace")

    def test_a_body_that_ends_at_its_last_sentence_has_no_pairs(self):
        body = ("some sentence.\n\nP.S. sample.\n"
                "Don't want these? Reply stop.")
        self.assertEqual(signoff_pairs(body), [])
        self.assertEqual(signoff_pairs(""), [])

    def test_the_company_word_in_prose_is_not_a_signoff(self):
        """Only a line that IS the company line, with a name above it,
        counts - the word appearing inside prose must not fire."""
        body = "We work with Productive teams every day.\n\nP.S. x"
        self.assertEqual(signoff_pairs(body), [])


class TheThreeRedTests(unittest.TestCase):

    @unittest.expectedFailure
    def test_no_composed_body_carries_a_sign_off_block(self):
        """RED: no sender name in the body, any name from the owner set.
        The body ends at its last sentence; the provider does the
        signing. Today the real chain renders exactly one sign-off block
        - the config's claim - into every body it composes."""
        body, _ = the_real_chain()
        pairs = signoff_pairs(body)
        self.assertEqual(
            pairs, [],
            f"composed body carries {len(pairs)} sign-off block(s) at "
            f"line(s) {pairs}; the body must end at its last sentence - "
            f"the provider's per-account signature does the signing")

    @unittest.expectedFailure
    def test_exactly_one_signature_reaches_the_recipient(self):
        """RED: exactly one signature reaches the recipient, and OUR
        contribution is ZERO - every named account already carries its
        own correct signature in the provider (measured, 09-21 export),
        so the one signature the recipient sees must be the provider's.
        Today our layer contributes one, which makes two.

        The premise depends on the provider appending its signature to
        a body that already carries one - UNKNOWN from stored state
        (see the module docstring, measurement 1). If the provider
        suppresses instead, the invariant this test should hold changes
        and the operator decides again; it is named, not assumed.
        """
        body, _ = the_real_chain()
        self.assertEqual(
            signoff_pairs(body), [],
            "our layer must contribute zero signatures; the provider's "
            "per-account signature is the one the recipient sees")

    @unittest.expectedFailure
    def test_the_configs_claim_is_not_rendered_into_any_body_variable(self):
        """RED: the config's claim is not rendered at all.
        ``bisonfactory._variables_for`` is the production staging path:
        today its body variables carry the composed signature block and
        the config's sender name inside it. No variable VALUE may
        contain either - the claim may live in the config and in the
        approval fingerprint, never in a prospect-facing variable."""
        name_line = sendersignature.compose(
            clients.sender_identity(clients.load("productive")))
        first_line = name_line.splitlines()[0]
        offenders = [v["name"] for v in the_real_variables()
                     if first_line in str(v.get("value", ""))
                     or name_line in str(v.get("value", ""))]
        self.assertEqual(
            offenders, [],
            f"body variable(s) {offenders} render the config's sender "
            f"claim; the provider signs, the body does not")


if __name__ == "__main__":
    unittest.main()
