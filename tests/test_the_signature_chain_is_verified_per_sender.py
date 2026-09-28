r"""The signature-chain verifier, proved able to FAIL five different ways.

TASK-425 criterion 2, P0-A. The verdict about the estate is NOT made here: it
is made by `scripts/verify_signature_chain.py`, which reads the real source of
truth (EmailBison `GET /sender-emails`, fully paginated) and the real canonical
roster. **These tests do not stand in for that read and are not evidence about
any mailbox.** They exist for the opposite reason.

## WHY A VERIFIER NEEDS ITS OWN NEGATIVE CONTROLS

A checker that cannot fail proves nothing, and this repository has shipped that
shape more than once: `tests/test_a_step_never_renders_an_empty_signature.py`
is three tests, all SKIPPED, written for this exact blocker in TASK-341 - so
the guard against an empty signature has never once executed. A verifier that
reports BLOCKED is equally worthless if BLOCKED is all it can say, which is why
the positive control below is not a courtesy: it is what makes the BLOCKED
verdict mean something.

## THE FIVE THAT MUST FAIL

    1. wrong pairing    sender X's signature under sender Y
    2. missing          no signature field for that sender at all
    3. empty            the field present and empty
    4. substituted      another productive sender's signature in its place
    5. projection gap   the rendered copy HAS it, the projection does not

1 and 4 are caught by the same mechanism and are kept separate on purpose: a
signature is only evidence about identity while it DISCRIMINATES, so a block
resolving to two owners attributes nothing and fails closed. That is the
same-value-different-authority rule, one level down from TASK-462.

## NO REAL VALUES

The signature strings here are obvious placeholders. No real signature, real
name or real address appears in this file, and none is hardcoded in
`src/sendersignature.py` either - control 2 is what proves there is no
fallback: with nothing at the source, resolution refuses rather than
substituting anything.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import sendersignature as ss  # noqa: E402

WS = "productive"

SIG_X = "<p>-- Placeholder X, Role X @PlaceholderCo</p>"
SIG_Y = "<p>-- Placeholder Y, Role Y @PlaceholderCo</p>"

#: The projection's real shape, from `sequenceplan.derive_bison_sequence`:
#: a template of merge fields, one step per cadence email.
STEP_FIELDS = ("email_subject", "email_body", "order", "step_key",
               "thread_reply", "wait_in_days")


def human(sender_id):
    return {"kind": ss.si.SENDER, "workspace": WS, "sender_id": sender_id,
            "display_name": sender_id.title(), "active": True}


def mailbox(account_id, provider_id, sender_id=None):
    return {"kind": ss.si.EMAIL_ACCOUNT, "workspace": WS,
            "account_id": account_id, "provider_account_id": str(provider_id),
            "sender_id": sender_id, "email_address": "%s@example.test" % account_id,
            "domain": "example.test", "active": True, "provider": "emailbison"}


def attestation(account_id, sender_id):
    return {"kind": ss.so.ATTESTATION, "workspace": WS, "channel": "email",
            "account_id": account_id, "sender_id": sender_id,
            "by": "test", "at": "2026-09-28T00:00:00Z"}


def provider(provider_id, signature=..., name="Placeholder"):
    row = {"id": provider_id, "name": name,
           "email": "mbox%s@example.test" % provider_id, "status": "Connected"}
    if signature is not ...:
        row[ss.PROVIDER_FIELD] = signature
    return row


def projection(signature=None):
    """A five-step projection, optionally with the signature appended."""
    steps = []
    for i in range(1, 6):
        body = "<p>{BODY_%d}</p>" % i
        if signature:
            body += signature
        steps.append({"email_subject": "{SUBJECT_1}", "email_body": body,
                      "order": i, "step_key": "em%d" % i,
                      "thread_reply": i > 1, "wait_in_days": 3})
    return steps


def rendered(signature=None):
    text = "subject\n<p>the approved words</p>"
    return text + (signature or "")


class TheVerifierCanPass(unittest.TestCase):
    """THE POSITIVE CONTROL. Without this, BLOCKED is meaningless."""

    def test_all_five_links_pass_when_the_chain_is_whole(self):
        rows = [human("x"), mailbox("a1", 1, "x")]
        account = rows[1]
        index = ss.index_provider([provider(1, SIG_X)])
        owners = ss.owners_of_signature([account], rows, index)
        chain = ss.chain_for(account, rows, index, signature_owners=owners,
                             rendered=rendered(SIG_X),
                             projection_steps=projection(SIG_X))
        self.assertEqual(chain["status"], ss.OK, chain["note"])
        self.assertIsNone(chain["failed_link"])
        self.assertTrue(chain["pass"])
        self.assertEqual(chain["links"],
                         {"owner": True, "identity": True, "signature": True,
                          "rendered": True, "projection": True})

    def test_the_owner_comes_from_an_attestation_too(self):
        """The second of `resolve_owner`'s two paths, so link 1 is not
        passing only for rows that happened to be created with an owner."""
        rows = [human("x"), mailbox("a1", 1, None), attestation("a1", "x")]
        account = rows[1]
        index = ss.index_provider([provider(1, SIG_X)])
        chain = ss.chain_for(
            account, rows, index,
            signature_owners=ss.owners_of_signature([account], rows, index),
            rendered=rendered(SIG_X), projection_steps=projection(SIG_X))
        self.assertEqual(chain["owner"], "x")
        self.assertTrue(chain["pass"], chain["note"])


class TheFiveNegativeControls(unittest.TestCase):
    """Every one of these MUST fail. A pass here is a broken verifier."""

    def chain(self, account, rows, provider_rows, rendered_text,
              projection_steps):
        index = ss.index_provider(provider_rows)
        owners = ss.owners_of_signature(
            [r for r in rows if r.get("kind") == ss.si.EMAIL_ACCOUNT],
            rows, index)
        return ss.chain_for(account, rows, index, signature_owners=owners,
                            rendered=rendered_text,
                            projection_steps=projection_steps)

    # ---------------------------------------------------- 1. wrong pairing
    def test_control_1_wrong_pairing_fails(self):
        """X's mailbox holds Y's block while Y's mailbox holds it too.

        The value is non-empty and looks perfectly healthy. It is refused
        because it now resolves to two owners, so it identifies neither.
        """
        rows = [human("x"), human("y"),
                mailbox("a1", 1, "x"), mailbox("a2", 2, "y")]
        account = rows[2]
        chain = self.chain(account, rows,
                           [provider(1, SIG_Y), provider(2, SIG_Y)],
                           rendered(SIG_Y), projection(SIG_Y))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.SIGNATURE_AMBIGUOUS)
        self.assertEqual(chain["failed_link"], "signature")
        self.assertIn("shared by 2 owners", chain["note"])
        self.assertFalse(chain["signature_present_at_source"])

    # --------------------------------------------------------- 2. missing
    def test_control_2_missing_fails_and_nothing_is_defaulted(self):
        rows = [human("x"), mailbox("a1", 1, "x")]
        chain = self.chain(rows[1], rows, [provider(1)],
                           rendered(SIG_X), projection(SIG_X))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.SIGNATURE_ABSENT)
        self.assertEqual(chain["failed_link"], "signature")
        self.assertIn("no %r field" % ss.PROVIDER_FIELD, chain["note"])

    def test_control_2b_a_mailbox_the_source_does_not_carry_fails(self):
        """Our row names a provider mailbox the inventory does not have.

        UNKNOWN, never "absent": a canonical row pointing at a mailbox that
        no longer exists must not read as a mailbox with no signature.
        """
        rows = [human("x"), mailbox("a1", 999, "x")]
        chain = self.chain(rows[1], rows, [provider(1, SIG_X)],
                           rendered(SIG_X), projection(SIG_X))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.NO_PROVIDER_ROW)
        self.assertEqual(chain["failed_link"], "identity")
        self.assertIn("UNKNOWN", chain["note"])

    # ----------------------------------------------------------- 3. empty
    def test_control_3_empty_fails(self):
        for blank in ("", "   ", "\n\t "):
            with self.subTest(blank=repr(blank)):
                rows = [human("x"), mailbox("a1", 1, "x")]
                chain = self.chain(rows[1], rows, [provider(1, blank)],
                                   rendered(SIG_X), projection(SIG_X))
                self.assertFalse(chain["pass"])
                self.assertEqual(chain["status"], ss.SIGNATURE_EMPTY)
                self.assertEqual(chain["failed_link"], "signature")

    def test_control_3b_an_empty_signature_is_never_found_in_anything(self):
        """`"" in anything` is True, and reading that as "present" is the
        guard-that-cannot-fail shape this whole blocker hid behind."""
        self.assertFalse(ss.carries("any body at all", ""))
        self.assertFalse(ss.carries("any body at all", None))
        self.assertFalse(ss.signature_in_projection(projection(), ""))

    # ----------------------------------------------------- 4. substituted
    def test_control_4_another_senders_signature_substituted_fails(self):
        """Y keeps their own block; X's mailbox is given a copy of it.

        Distinct from control 1 in intent - a substitution rather than a
        swap - and it must fail for X even though X's stored value is a
        real, non-empty signature belonging to a real productive sender.
        """
        rows = [human("x"), human("y"),
                mailbox("a1", 1, "x"), mailbox("a2", 2, "y")]
        x_account, y_account = rows[2], rows[3]
        provider_rows = [provider(1, SIG_Y), provider(2, SIG_Y)]

        x_chain = self.chain(x_account, rows, provider_rows,
                             rendered(SIG_Y), projection(SIG_Y))
        self.assertFalse(x_chain["pass"])
        self.assertEqual(x_chain["status"], ss.SIGNATURE_AMBIGUOUS)

        # And the rightful owner is refused too, which is correct: once the
        # block is shared it attributes nobody, so passing Y would be
        # asserting an identity the data no longer supports.
        y_chain = self.chain(y_account, rows, provider_rows,
                             rendered(SIG_Y), projection(SIG_Y))
        self.assertFalse(y_chain["pass"])
        self.assertEqual(y_chain["status"], ss.SIGNATURE_AMBIGUOUS)

    def test_control_4b_a_different_signature_in_the_rendered_mail_fails(self):
        """X resolves to X's block and the rendered mail carries Y's."""
        rows = [human("x"), human("y"),
                mailbox("a1", 1, "x"), mailbox("a2", 2, "y")]
        chain = self.chain(rows[2], rows,
                           [provider(1, SIG_X), provider(2, SIG_Y)],
                           rendered(SIG_Y), projection(SIG_Y))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.OK)
        self.assertEqual(chain["failed_link"], "rendered")

    # -------------------------------------------------- 5. projection gap
    def test_control_5_projection_missing_it_while_rendered_has_it_fails(self):
        rows = [human("x"), mailbox("a1", 1, "x")]
        chain = self.chain(rows[1], rows, [provider(1, SIG_X)],
                           rendered(SIG_X), projection(None))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.OK)
        self.assertEqual(chain["failed_link"], "projection")
        self.assertTrue(chain["links"]["rendered"])
        self.assertFalse(chain["links"]["projection"])

    # ------------------------------------------------- link 1, for its own sake
    def test_an_unowned_mailbox_fails_at_link_one(self):
        rows = [human("x"), mailbox("a1", 1, None)]
        chain = self.chain(rows[1], rows, [provider(1, SIG_X)],
                           rendered(SIG_X), projection(SIG_X))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.NO_OWNER)
        self.assertEqual(chain["failed_link"], "owner")

    def test_an_attestation_to_a_stranger_fails_at_link_two(self):
        rows = [mailbox("a1", 1, None), attestation("a1", "nobody")]
        chain = self.chain(rows[0], rows, [provider(1, SIG_X)],
                           rendered(SIG_X), projection(SIG_X))
        self.assertFalse(chain["pass"])
        self.assertEqual(chain["status"], ss.NO_CANONICAL_HUMAN)
        self.assertEqual(chain["failed_link"], "identity")


class TheProjectionShapeIsTheRealOne(unittest.TestCase):
    """Link 5 is structural: there is no field a signature could travel in.

    Asserted against the shape `sequenceplan.derive_bison_sequence` actually
    emits, so this fails the day a signature field is added - which is the
    day the assertion should be revisited rather than silently outlived.
    """

    def test_the_projection_has_no_signature_field(self):
        from src import bisonfactory, cadence, clients
        config = clients.load("productive")
        steps = cadence.steps_for(None, config)
        sequence = bisonfactory._sequence_steps(
            config.get("email_sequence") or {}, steps)
        self.assertTrue(sequence)
        fields = sorted({k for s in sequence for k in s.keys()})
        self.assertEqual(fields, sorted(STEP_FIELDS))
        self.assertEqual([f for f in fields if "sign" in f.lower()], [])

    def test_a_lead_carries_no_signature_variable(self):
        from src import bisonfactory
        lead = {"record_id": "r", "contact_key": "c",
                "copy": [{"step_key": "em%d" % i, "subject": "s",
                          "body": "b"} for i in range(1, 6)]}
        variables = bisonfactory._variables_for(lead, {"client": "productive"})
        names = sorted(str(v.get("name")) for v in variables)
        self.assertEqual([n for n in names if "sign" in n.lower()], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
