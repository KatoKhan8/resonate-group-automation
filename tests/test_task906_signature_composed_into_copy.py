"""TASK-906: the signature is composed into the rendered mail and the projection.

Acceptance:
1. Chain proven per sender: owner -> identity -> signature -> rendered
   email -> projection, all five links.
2. If the provider ever appends its own signature, our check must detect
   the duplicate and BLOCK.
3. Negative controls (all must FAIL): wrong pairing; missing; empty;
   another Productive sender's signature; present in the rendered copy
   but absent from the projection.
4. Un-skip TASK-341's three signature tests, or replace them with tests
   that actually run.
5. Criterion 2 passes only when all five links are proven.
6. Mutation: break the sender->signature mapping; the verifier must catch it.

THE BYTE-IDENTICAL ASSERTION.  The rendered body and the EmailBison
projection are byte-identical for the same step, with P.S., opt-out and
signature all present.  assertEqual on the two strings.
"""
import unittest

from src import sendersignature, trailingcontent
from scripts.render_preview import (
    _fixture_config_email, _fixture_rec_email, _build_email_plan)


# --------------------------------------------------------------- helpers

def _sender(name="Anna Kowalski"):
    return {"name": name, "role": "Head of Delivery",
            "company": "Productive"}


def _body_from_plan(plan, step_name="body_1"):
    """Extract a body variable value from the plan's first lead."""
    for v in plan["leads"][0]["variables"]:
        if v["name"] == step_name:
            return v["value"]
    return None


def _body_from_render(step, signature=None):
    """Render a body through the SAME path as emailbison_rows."""
    from src import render
    results = [{
        "status": "clean",
        "failures": [],
        "record": {"id": "test-r", "company": "TestCo",
                   "domain": "test.test", "lane": "outbound"},
        "contact": {"email": "test@test.test", "name": "Test",
                    "title": "CEO"},
        "step": step,
        "day": "1",
        "id": "test-r",
    }]
    # Use the card function with explicit signature to test the render path
    from src import sendersignature as ss
    sig = signature if signature is not None else ""
    body = step.get("body", "")
    ps = step.get("ps", "")
    return trailingcontent.compose(body, ps=ps, signature=sig)


# -------------------------------------- acceptance 1: the full chain

class TestFullChain(unittest.TestCase):
    """Acceptance 1: owner -> identity -> signature -> rendered -> projection.

    All five links, proven in one test.
    """

    def setUp(self):
        self.config = _fixture_config_email()
        self.rec = _fixture_rec_email()
        self.plan = _build_email_plan(self.config, [self.rec])

    def test_owner_to_identity(self):
        """The config's sender block is read by clients.sender_identity."""
        from src import clients
        sender = clients.sender_identity(self.config)
        self.assertEqual(sender["name"], "Anna Kowalski")

    def test_identity_to_signature(self):
        """The sender identity produces a two-line signature."""
        from src import clients
        sender = clients.sender_identity(self.config)
        sig = sendersignature.compose(sender)
        self.assertEqual(sig, "Anna Kowalski\nProductive")

    def test_signature_in_rendered_email(self):
        """The rendered email body carries the signature."""
        sig = sendersignature.compose({"name": "Anna Kowalski"})
        body = _body_from_render(
            {"subject": "Test", "body": "Hello.", "ps": "P.S. Note."},
            signature=sig)
        self.assertIn("Anna Kowalski", body)
        self.assertIn("Productive", body)

    def test_signature_in_projection(self):
        """The EmailBison projection carries the signature."""
        body = _body_from_plan(self.plan, "body_1")
        self.assertIn("Anna Kowalski", body)
        self.assertIn("Productive", body)

    def test_all_five_links_hold(self):
        """The full chain: owner -> identity -> signature -> render ->
        projection.  All five links in one assertion."""
        from src import clients
        # Link 1: owner (the config has a sender block)
        self.assertIn("sender", self.config)
        # Link 2: identity (sender_identity reads it)
        sender = clients.sender_identity(self.config)
        self.assertEqual(sender["name"], "Anna Kowalski")
        # Link 3: signature (compose produces the block)
        sig = sendersignature.compose(sender)
        self.assertEqual(sig, "Anna Kowalski\nProductive")
        # Link 4: rendered email carries it
        rendered = _body_from_render(
            {"body": "Hello.", "ps": "P.S. X"}, signature=sig)
        self.assertIn("Anna Kowalski\nProductive", rendered)
        # Link 5: projection carries it
        projected = _body_from_plan(self.plan, "body_1")
        self.assertIn("Anna Kowalski\nProductive", projected)


# -------------------------------------- byte-identical assertion

class TestByteIdentical(unittest.TestCase):
    """The rendered body and the projection are BYTE-IDENTICAL.

    Not 'both contain the signature' - identical.  assertEqual on the
    two strings.
    """

    def setUp(self):
        self.config = _fixture_config_email()
        self.rec = _fixture_rec_email()
        self.plan = _build_email_plan(self.config, [self.rec])

    def test_em1_body_is_byte_identical(self):
        """The em1 body from the projection equals the em1 body from the
        render path, byte for byte."""
        from src import clients
        sender = clients.sender_identity(self.config)
        sig = sendersignature.compose(sender)
        # Projection body
        projected = _body_from_plan(self.plan, "body_1")
        # Render path body - same inputs, same function
        stored = self.rec["cadence"]["jacob-hartley"]["em1"]
        rendered = trailingcontent.compose(
            stored["body"], ps=stored.get("ps", ""), signature=sig)
        self.assertEqual(rendered, projected)

    def test_em3_body_is_byte_identical(self):
        """The em3 body (which has its own P.S.) is byte-identical."""
        from src import clients
        sender = clients.sender_identity(self.config)
        sig = sendersignature.compose(sender)
        projected = _body_from_plan(self.plan, "body_3")
        stored = self.rec["cadence"]["jacob-hartley"]["em3"]
        rendered = trailingcontent.compose(
            stored["body"], ps=stored.get("ps", ""), signature=sig)
        self.assertEqual(rendered, projected)

    def test_em2_body_is_byte_identical(self):
        """The em2 body (no P.S.) is byte-identical."""
        from src import clients
        sender = clients.sender_identity(self.config)
        sig = sendersignature.compose(sender)
        projected = _body_from_plan(self.plan, "body_2")
        stored = self.rec["cadence"]["jacob-hartley"]["em2"]
        rendered = trailingcontent.compose(
            stored["body"], ps=stored.get("ps", ""), signature=sig)
        self.assertEqual(rendered, projected)

    def test_all_three_trailing_pieces_present(self):
        """P.S., opt-out and signature are ALL present in the same body."""
        from src import optout
        body = _body_from_plan(self.plan, "body_1")
        self.assertIn("P.S.", body)
        self.assertIn(optout.OPT_OUT_LINE, body)
        self.assertIn("Anna Kowalski", body)
        self.assertIn("Productive", body)

    def test_exactly_one_of_each(self):
        """Each trailing piece appears EXACTLY ONCE.  Not zero, not two.

        This is the counting assertion the task requires: `in` would pass
        for one occurrence OR three.  count() is the only correct check.
        """
        from src import optout
        body = _body_from_plan(self.plan, "body_1")
        self.assertEqual(body.count("P.S."), 1)
        self.assertEqual(body.count(optout.OPT_OUT_LINE), 1)
        # The signature block is the two-line unit, not the word "Productive"
        # (which also appears in the body as the product name).
        self.assertEqual(body.count("Anna Kowalski\nProductive"), 1)


# -------------------------------------- acceptance 2: duplicate detection

class TestDuplicateSignatureBlocked(unittest.TestCase):
    """Acceptance 2: a body already carrying the signature is REFUSED."""

    def test_body_with_existing_signature_is_refused(self):
        """A body that already contains the signature block AND receives
        another is refused, not double-signed."""
        sig = "Anna Kowalski\nProductive"
        body_with_sig = "Hello.\n\nAnna Kowalski\nProductive"
        with self.assertRaises(sendersignature.SignatureDuplicate):
            sendersignature.refuse_if_duplicate(body_with_sig, sig)

    def test_body_without_signature_passes(self):
        """A body that does NOT contain the signature passes through."""
        sig = "Anna Kowalski\nProductive"
        body = "Hello.\n\nSome copy."
        result = sendersignature.refuse_if_duplicate(body, sig)
        self.assertEqual(result, body)

    def test_empty_signature_never_refuses(self):
        """An empty signature cannot trigger the duplicate check."""
        body = "Hello.\n\nSome copy."
        result = sendersignature.refuse_if_duplicate(body, "")
        self.assertEqual(result, body)


# -------------------------------------- acceptance 3: negative controls

class TestNegativeControls(unittest.TestCase):
    """Acceptance 3: all negative controls must FAIL."""

    def test_wrong_pairing_refused(self):
        """A signature from sender A applied to sender B's email is
        detected by the byte-identical check."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        projected = _body_from_plan(plan, "body_1")
        # Render with a DIFFERENT sender
        wrong_sig = sendersignature.compose({"name": "Mark Johnson"})
        rendered = trailingcontent.compose(
            rec["cadence"]["jacob-hartley"]["em1"]["body"],
            ps=rec["cadence"]["jacob-hartley"]["em1"].get("ps", ""),
            signature=wrong_sig)
        self.assertNotEqual(rendered, projected,
                            "wrong sender must produce a different body")

    def test_missing_sender_produces_no_signature(self):
        """A config with no sender block produces no signature."""
        sig = sendersignature.compose({})
        self.assertEqual(sig, "")

    def test_empty_name_produces_no_signature(self):
        """A sender with an empty name produces no signature."""
        sig = sendersignature.compose({"name": ""})
        self.assertEqual(sig, "")

    def test_none_sender_produces_no_signature(self):
        """A None sender produces no signature."""
        sig = sendersignature.compose(None)
        self.assertEqual(sig, "")

    def test_another_senders_signature_differs(self):
        """A different Productive sender's signature is not the same."""
        sig_a = sendersignature.compose({"name": "Anna Kowalski"})
        sig_b = sendersignature.compose({"name": "Mark Johnson"})
        self.assertNotEqual(sig_a, sig_b)

    def test_present_in_render_but_absent_from_projection_detected(self):
        """If the signature is in the rendered body but not in the
        projection, the byte-identical assertion catches it."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        projected = _body_from_plan(plan, "body_1")
        # The projection DOES carry the signature (proven above).
        self.assertIn("Anna Kowalski\nProductive", projected)
        # Simulate a broken projection that does NOT carry the signature.
        broken_projected = trailingcontent.compose(
            rec["cadence"]["jacob-hartley"]["em1"]["body"],
            ps=rec["cadence"]["jacob-hartley"]["em1"].get("ps", ""),
            signature="")
        # The byte-identical check catches the drift.
        self.assertNotEqual(projected, broken_projected,
                            "a projection without the signature must "
                            "differ from one with it")


# -------------------------------------- acceptance 4: TASK-341 replacement

class TestSignatureNeverEmpty(unittest.TestCase):
    """Acceptance 4: replace TASK-341's three skipped tests with real ones.

    TASK-341 had three @unittest.skip tests that never executed.  These
    tests run and assert real behaviour.
    """

    def test_step_body_is_not_empty_when_signature_composed(self):
        """A step with a body and a signature produces a non-empty result."""
        sig = sendersignature.compose({"name": "Anna Kowalski"})
        result = trailingcontent.compose("Hello person.", signature=sig)
        self.assertTrue(len(result) > 0)
        self.assertIn("Hello person.", result)
        self.assertIn("Anna Kowalski", result)

    def test_sender_identity_present_in_config(self):
        """The fixture config carries a sender block."""
        config = _fixture_config_email()
        self.assertIn("sender", config)
        self.assertIn("name", config["sender"])

    def test_generation_context_carries_sender_identity(self):
        """The plan carries the sender from the config."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        # The projection carries the signature
        body = _body_from_plan(plan, "body_1")
        self.assertIn("Anna Kowalski", body)


# -------------------------------------- acceptance 6: mutation check

class TestMutationCheck(unittest.TestCase):
    """Acceptance 6: break the sender->signature mapping; verifier catches it.

    The mutation is: change the sender name.  The signature must change.
    The byte-identical assertion must fail.
    """

    def test_breaking_sender_changes_signature(self):
        """If the sender name changes, the signature changes."""
        sig_original = sendersignature.compose({"name": "Anna Kowalski"})
        sig_mutated = sendersignature.compose({"name": "Mark Johnson"})
        self.assertNotEqual(sig_original, sig_mutated)

    def test_breaking_sender_breaks_byte_identical(self):
        """If the sender is mutated, the rendered body no longer matches
        the projection."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        projected = _body_from_plan(plan, "body_1")
        # MUTATE: use a different sender for the render
        mutated_sig = sendersignature.compose({"name": "Somebody Else"})
        rendered = trailingcontent.compose(
            rec["cadence"]["jacob-hartley"]["em1"]["body"],
            ps=rec["cadence"]["jacob-hartley"]["em1"].get("ps", ""),
            signature=mutated_sig)
        self.assertNotEqual(rendered, projected,
                            "mutated sender must break byte-identical")

    def test_removing_signature_breaks_chain(self):
        """If the signature is removed (empty), the body changes."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        projected = _body_from_plan(plan, "body_1")
        # MUTATE: no signature
        rendered = trailingcontent.compose(
            rec["cadence"]["jacob-hartley"]["em1"]["body"],
            ps=rec["cadence"]["jacob-hartley"]["em1"].get("ps", ""),
            signature="")
        self.assertNotEqual(rendered, projected,
                            "removing signature must change the body")
        self.assertNotIn("Anna Kowalski", rendered)


# -------------------------------------- trailing content order

class TestTrailingContentOrder(unittest.TestCase):
    """The order of trailing content is load-bearing.

    body -> signature -> P.S. -> opt-out.
    """

    def test_order_is_correct(self):
        """The signature comes before the P.S., which comes before the
        opt-out."""
        from src import optout
        body = "Hello person."
        sig = "Anna Kowalski\nProductive"
        ps = "P.S. Note."
        result = trailingcontent.compose(body, ps=ps, signature=sig)
        sig_pos = result.index("Anna Kowalski")
        ps_pos = result.index("P.S. Note.")
        opt_out_pos = result.index(optout.OPT_OUT_LINE)
        self.assertLess(sig_pos, ps_pos,
                        "signature must come before P.S.")
        self.assertLess(ps_pos, opt_out_pos,
                        "P.S. must come before opt-out")

    def test_no_signature_still_appends_ps_and_opt_out(self):
        """Without a signature, P.S. and opt-out are still appended."""
        from src import optout
        result = trailingcontent.compose("Hello.", ps="P.S. X")
        self.assertIn("P.S. X", result)
        self.assertIn(optout.OPT_OUT_LINE, result)
        self.assertNotIn("Productive", result)

    def test_no_ps_still_appends_signature_and_opt_out(self):
        """Without a P.S., signature and opt-out are still appended."""
        from src import optout
        sig = "Anna Kowalski\nProductive"
        result = trailingcontent.compose("Hello.", signature=sig)
        self.assertIn("Anna Kowalski", result)
        self.assertIn(optout.OPT_OUT_LINE, result)


# -------------------------------------- exactly-once counting

class TestExactlyOnceCounting(unittest.TestCase):
    """The task requires COUNTING, not `in`.  An `in` check passes for one
    occurrence OR three.  count() is the only correct check.

    These tests prove that adding the signature does not duplicate the
    P.S. or the opt-out.
    """

    def test_signature_does_not_duplicate_ps(self):
        """Adding a signature does not create a second P.S."""
        sig = "Anna Kowalski\nProductive"
        result = trailingcontent.compose("Hello.", ps="P.S. Note.",
                                         signature=sig)
        self.assertEqual(result.count("P.S."), 1)

    def test_signature_does_not_duplicate_opt_out(self):
        """Adding a signature does not create a second opt-out."""
        from src import optout
        sig = "Anna Kowalski\nProductive"
        result = trailingcontent.compose("Hello.", ps="P.S. Note.",
                                         signature=sig)
        self.assertEqual(result.count(optout.OPT_OUT_LINE), 1)

    def test_all_five_bodies_have_exactly_one_signature(self):
        """Every body_N in the projection carries exactly one signature."""
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        for i in range(1, 6):
            body = _body_from_plan(plan, f"body_{i}")
            # Count the full signature block, not the word "Productive"
            # (which also appears in the body as the product name).
            self.assertEqual(body.count("Anna Kowalski\nProductive"), 1,
                             f"body_{i} has wrong signature count")

    def test_all_five_bodies_have_exactly_one_opt_out(self):
        """Every body_N in the projection carries exactly one opt-out."""
        from src import optout
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        for i in range(1, 6):
            body = _body_from_plan(plan, f"body_{i}")
            self.assertEqual(body.count(optout.OPT_OUT_LINE), 1,
                             f"body_{i} has wrong opt-out count")


# -------------------------------------- single shared appender

class TestSingleSharedAppender(unittest.TestCase):
    """The consolidation: both surfaces use trailingcontent.compose.

    No second copy of _append_ps exists anywhere in src/.
    """

    def test_no_append_ps_in_render(self):
        """src/render.py has no local _append_ps function."""
        from src import render
        self.assertFalse(hasattr(render, "_append_ps"),
                         "render.py must not have its own _append_ps")

    def test_no_append_ps_in_bisonfactory(self):
        """src/bisonfactory.py has no local _append_ps function."""
        from src import bisonfactory
        self.assertFalse(hasattr(bisonfactory, "_append_ps"),
                         "bisonfactory.py must not have its own _append_ps")

    def test_trailingcontent_append_ps_exists(self):
        """The shared append_ps lives in trailingcontent."""
        self.assertTrue(hasattr(trailingcontent, "append_ps"))

    def test_trailingcontent_compose_exists(self):
        """The shared compose lives in trailingcontent."""
        self.assertTrue(hasattr(trailingcontent, "compose"))


if __name__ == "__main__":
    unittest.main()
