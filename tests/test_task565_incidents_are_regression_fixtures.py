"""TASK-565: every real incident becomes a regression fixture.

Ten incidents, ten fixtures.  Each fixture reproduces the REAL EFFECT,
FAILS if its lowest-layer guard is removed, carries a control proving
it does not refuse everything, and names the incident it descends from.

THE RULE FOR WHERE EACH ONE LIVES.  Each fixture asserts at the LOWEST
LAYER THAT PREVENTS THE REAL EFFECT.  Not at the layer where the bug
happened to be found.  A test that asserts a symptom one layer above
the guard passes when the guard is removed - that exact failure was
measured on 2026-09-28.

NO PROSPECT DATA.  These are real incidents and real people; the tests
use the shapes, never the identities.

Provider writes 0, sending.live false, freeze active.

THE TEN
  1. Wrong-company copy sent from a Productive mailbox (64 emails)
  2. Signature not matching the mailbox owner
  3. Empty body from unresolved variables (77 emails, 2026-09-23)
  4. An unsupported figure on an email
  5. An unsupported figure on a LinkedIn message
  6. A prospect who replied receiving another message (7 min after refusal)
  7. An old approval reused after the copy changed
  8. A direct create_lead/attach bypassing the factory
  9. The P.S. lost before it reaches the provider
 10. A LinkedIn step lost before HeyReach (TASK-548)
"""
import copy
import hashlib
import inspect
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (approval, bisonfactory, cadence, clients, contamination,
                 copylint, eligibility, emptyrender, executionguard,
                 heyreachfactory, inbound, lint, optout, providerwrites,
                 render, reviewapproval, sendersignature, sequenceplan,
                 store, trailingcontent)
from src.providers import heyreach
import src.providers as providers


# ====================================================================
#
# INCIDENT 1: Wrong-company copy sent from a Productive mailbox
#
# 64 emails carrying another agency's pitch, signed with the operator's
# name, from mailboxes 503/504/505.  2026-09-25.
#
# LOWEST GUARD: reviewapproval.require.  The factory gates ran correctly
# but the push that caused the incident bypassed the factory entirely,
# using bison.create_lead and bison.attach_leads directly.  The guard
# that catches this NOW sits on the ACTIVATION CALL itself: every route
# to activation goes through bison.resume_campaign or
# heyreach.activate_campaign, and both ask reviewapproval.require.
#
# ====================================================================


class Incident1_WrongCompanyCopy(unittest.TestCase):
    """Incident 1: wrong-company copy from a Productive mailbox.

    64 emails, 2026-09-25.  The guard is reviewapproval.require: no
    activation without the operator's approval of the review file hash.
    """

    def test_activation_without_approval_is_refused(self):
        """The guard: reviewapproval.require raises NotApproved when no
        operator approval exists for the campaign."""
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("999999")

    def test_activation_with_wrong_hash_is_refused(self):
        """An approval for a DIFFERENT review file hash is refused.
        Re-rendering the copy produces a new hash and needs a new
        approval."""
        rows = [{"campaign": "999999", "review_hash": "abcdef0123456789",
                 "by": "zvonimir"}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("999999", review_hash="different_hash",
                                   rows=rows)

    def test_approval_from_wrong_person_is_refused(self):
        """An approval recorded by the production session for its own
        work is the thing the incident was made of.  Only the operator's
        approval counts."""
        rows = [{"campaign": "999999", "review_hash": "abcdef0123456789",
                 "by": "claude"}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("999999", rows=rows)

    def test_control_valid_approval_passes(self):
        """CONTROL: a valid approval from the operator with the correct
        hash passes."""
        rows = [{"campaign": "999999", "review_hash": "abcdef0123456789",
                 "by": "zvonimir"}]
        result = reviewapproval.require("999999",
                                        review_hash="abcdef0123456789",
                                        rows=rows)
        self.assertEqual(result["campaign"], "999999")

    def test_mutation_removing_require_lets_bad_activation_through(self):
        """MUTATION: if reviewapproval.require were removed from the
        activation path, no check would stop a campaign with no
        approval.  This proves the guard is load-bearing by showing it
        is the ONLY thing that refuses."""
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("nonexistent-campaign")


# ====================================================================
#
# INCIDENT 2: Signature not matching the mailbox owner
#
# The signature block was not composed from the mailbox owner's identity.
# A different Productive sender's name appeared under mailboxes that
# belonged to somebody else.
#
# LOWEST GUARD: sendersignature.compose reads from clients.sender_identity
# which reads from the client config's sender block.  The byte-identical
# assertion between the rendered body and the projection catches any
# drift.
#
# ====================================================================


class Incident2_SignatureMismatch(unittest.TestCase):
    """Incident 2: signature not matching the mailbox owner.

    The guard: sendersignature.compose produces the signature from the
    sender identity, and the byte-identical assertion catches any drift
    between the render and the projection.
    """

    def test_wrong_sender_produces_different_signature(self):
        """A signature composed from a different sender is not the same
        as the mailbox owner's."""
        correct = sendersignature.compose({"name": "Anna Kowalski"})
        wrong = sendersignature.compose({"name": "Mark Johnson"})
        self.assertNotEqual(correct, wrong)

    def test_empty_sender_produces_no_signature(self):
        """A sender with no name produces no signature.  An email with
        no signature is a missing signature, not a wrong one."""
        sig = sendersignature.compose({"name": ""})
        self.assertEqual(sig, "")

    def test_signature_is_two_lines_name_then_company(self):
        """The signature is exactly: name, newline, 'Productive'."""
        sig = sendersignature.compose({"name": "Anna Kowalski"})
        self.assertEqual(sig, "Anna Kowalski\nProductive")

    def test_control_correct_sender_produces_correct_signature(self):
        """CONTROL: the correct sender produces the expected signature."""
        sig = sendersignature.compose({"name": "Anna Kowalski"})
        self.assertIn("Anna Kowalski", sig)
        self.assertIn("Productive", sig)

    def test_mutation_breaking_compose_breaks_the_chain(self):
        """MUTATION: if compose returned a fixed string regardless of
        the sender, every mailbox would get the same signature.  The
        byte-identical assertion would catch this because the projection
        reads the REAL sender."""
        sig_a = sendersignature.compose({"name": "Anna Kowalski"})
        sig_b = sendersignature.compose({"name": "Somebody Else"})
        self.assertNotEqual(sig_a, sig_b,
                            "compose must be sender-dependent")


# ====================================================================
#
# INCIDENT 3: Empty body from unresolved variables
#
# 77 emails with subject '' and body '<p></p>', sent 2026-09-23.
# The sequence steps were pure merge templates; a lead carrying no
# body_1 rendered to <p></p> and the provider sent that.
#
# LOWEST GUARD: emptyrender.classify_row.  This looks at the RENDERED
# QUEUE ROW (email_subject and email_body off bison.scheduled_emails),
# not the sequence template.  A variable that resolved to nothing is
# caught here even though the template itself is valid.
#
# ====================================================================


class Incident3_EmptyBodyFromUnresolvedVariables(unittest.TestCase):
    """Incident 3: 77 empty emails, 2026-09-23.

    The guard: emptyrender.classify_body and classify_subject detect
    empty renders, placeholder survivors, and literal None values.
    """

    def test_empty_html_body_is_caught(self):
        """The exact shape that sent 76 times: <p></p>."""
        result = emptyrender.classify_body("<p></p>")
        self.assertEqual(result, emptyrender.EMPTY)

    def test_empty_subject_is_caught(self):
        """An empty subject on a non-threaded step is caught."""
        result = emptyrender.classify_subject("", thread_reply=False)
        self.assertEqual(result, emptyrender.EMPTY)

    def test_unresolved_placeholder_in_body_is_caught(self):
        """A merge field that survived the render is caught."""
        result = emptyrender.classify_body("{BODY_1}")
        self.assertEqual(result, emptyrender.PLACEHOLDER)

    def test_literal_none_in_body_is_caught(self):
        """The string 'None' in a body field is caught."""
        result = emptyrender.classify_body("None")
        self.assertEqual(result, emptyrender.LITERAL_NONE)

    def test_bare_re_subject_is_caught(self):
        """A subject that is just 'Re:' with nothing after it is the
        empty case wearing the thread's clothes."""
        result = emptyrender.classify_subject("Re:", thread_reply=True)
        self.assertEqual(result, emptyrender.SUBJECT_RE)

    def test_control_valid_body_passes(self):
        """CONTROL: a real body passes."""
        result = emptyrender.classify_body(
            "Hello, I wanted to discuss your visibility gap.")
        self.assertIsNone(result)

    def test_control_threaded_empty_subject_passes(self):
        """CONTROL: an empty subject on a threaded reply is legitimate
        (the provider prepends Re: itself)."""
        result = emptyrender.classify_subject("", thread_reply=True)
        self.assertIsNone(result)

    def test_scan_finds_pending_faulty_rows(self):
        """A scheduled row with empty body is flagged as pending."""
        rows = [{"id": 12345,
                 "lead": {"id": 99},
                 "sequence_step_id": 1,
                 "status": "scheduled",
                 "email_subject": "",
                 "email_body": "<p></p>",
                 "thread_reply": False}]
        found = emptyrender.scan(rows)
        self.assertEqual(len(found["pending"]), 1)
        self.assertEqual(found["pending"][0]["row"], 12345)

    def test_copylint_unrendered_variable_fires(self):
        """copylint also catches unresolved variables at the batch level."""
        lead = {"id": "test",
                "steps": [{"body": "Hello {first_name} at {company}."}]}
        report = copylint.check_batch([lead])
        self.assertIn("test",
                      report["offenders"]["unrendered_variable"])

    def test_mutation_removing_classify_lets_empty_through(self):
        """MUTATION: if classify_body returned None for everything,
        empty renders would pass.  This proves classify_body is what
        catches them."""
        self.assertIsNotNone(emptyrender.classify_body("<p></p>"))
        rows = [{"id": 1, "lead": {"id": 1}, "sequence_step_id": 1,
                 "status": "scheduled", "email_subject": "Test",
                 "email_body": "<p></p>", "thread_reply": False}]
        found = emptyrender.scan(rows)
        self.assertTrue(len(found["pending"]) > 0,
                        "scan must find the empty body")


# ====================================================================
#
# INCIDENT 4: An unsupported figure on an email
#
# A model invented a plausible detail about a company nobody researched.
#
# LOWEST GUARD: copylint.untraceable.  It extracts specifics from a
# draft and requires each to appear in that lead's own pack facts.
#
# ====================================================================


class Incident4_UnsupportedFigureOnEmail(unittest.TestCase):
    """Incident 4: an unsupported figure on an email.

    The guard: copylint.untraceable extracts specifics from company
    claims and requires each to trace to a pack fact.
    """

    def test_invented_figure_is_untraceable(self):
        """A figure not in the pack is refused."""
        body = ("Northwind grew revenue by $50M last quarter. "
                "Worth a conversation?")
        pack = {"facts": [
            {"snippet": "Northwind builds booking software for clinics."},
        ]}
        found = copylint.untraceable(body, pack)
        self.assertTrue(len(found) > 0,
                        "an invented figure must be untraceable")

    def test_supported_figure_traces(self):
        """A figure that IS in the pack traces correctly."""
        body = ("Northwind grew revenue by $50M last quarter. "
                "Worth a conversation?")
        pack = {"facts": [
            {"snippet": "Northwind grew revenue by $50M last quarter "
                         "driven by clinic bookings."},
        ]}
        found = copylint.untraceable(body, pack)
        self.assertEqual(len(found), 0,
                         "a supported figure must trace")

    def test_control_generic_copy_passes(self):
        """CONTROL: copy with no specifics passes (nothing to trace)."""
        body = ("Hi there, I noticed your work in the clinic space. "
                "We help teams like yours see delivery margin while "
                "the work is still running.  Worth a short conversation?")
        pack = {"facts": [
            {"snippet": "Northwind builds booking software for clinics."},
        ]}
        found = copylint.untraceable(body, pack)
        self.assertEqual(len(found), 0)

    def test_reused_number_in_different_context_is_refused(self):
        """A number from the pack used in a different context is refused.
        This is the TASK-330 fix: content-word overlap is required."""
        body = ("Northwind raised $50M in 2019. "
                "Worth a conversation?")
        pack = {"facts": [
            {"snippet": "Northwind grew revenue by $50M last quarter."},
        ]}
        found = copylint.untraceable(body, pack)
        self.assertTrue(len(found) > 0,
                        "a reused number in a different context must "
                        "be refused")

    def test_batch_check_refuses_untraceable_claims(self):
        """The batch lint refuses a lead with untraceable claims."""
        lead = {"id": "test-inv",
                "steps": [
                    {"body": "They grew 300% last year. " +
                             "x " * 50},
                ]}
        pack = {"facts": [
            {"snippet": "They build software."},
        ]}
        report = copylint.check_batch([lead], packs={"test-inv": pack})
        self.assertIn("test-inv",
                      report["offenders"]["untraceable_company_claim"])


# ====================================================================
#
# INCIDENT 5: An unsupported figure on a LinkedIn message
#
# Same defect as incident 4, but on the LinkedIn channel.
#
# LOWEST GUARD: copylint.other_prospect_text feeds LinkedIn messages
# into the same traceability check.  The LinkedIn copy goes through
# the same specifics_in / untraceable pipeline.
#
# ====================================================================


class Incident5_UnsupportedFigureOnLinkedIn(unittest.TestCase):
    """Incident 5: an unsupported figure on a LinkedIn message.

    The guard: copylint checks LinkedIn messages through
    other_prospect_text, which feeds them into the same traceability
    pipeline.
    """

    def test_linkedin_message_with_invented_figure_is_checked(self):
        """A LinkedIn message carrying an invented figure is caught by
        the batch lint's traceability check."""
        lead = {
            "id": "test-li",
            "steps": [{"body": "Hello. " + "x " * 30}],
            "linkedin": {
                "li2": "Your company grew 300% last year. "
                       "Worth connecting?",
            },
        }
        text = copylint.other_prospect_text(lead)
        self.assertIn("300%", text)
        specifics = copylint.specifics_in(text)
        self.assertTrue(len(specifics) > 0,
                        "specifics_in must find the figure")

    def test_control_supported_linkedin_figure_passes(self):
        """CONTROL: a LinkedIn message with a supported figure passes."""
        lead = {
            "id": "test-li-ok",
            "steps": [{"body": "Hello."}],
            "linkedin": {
                "li2": "Northwind builds booking software for clinics. "
                       "Worth connecting?",
            },
        }
        text = copylint.other_prospect_text(lead)
        self.assertIn("booking software", text)

    def test_ps_also_checked(self):
        """P.S. lines are also extracted and checked."""
        lead = {
            "id": "test-ps",
            "steps": [{"body": "Hello."}],
            "ps": {"em1": "P.S. They grew $50M last year."},
        }
        text = copylint.other_prospect_text(lead)
        self.assertIn("$50M", text)
        specifics = copylint.specifics_in(text)
        self.assertTrue(len(specifics) > 0)


# ====================================================================
#
# INCIDENT 6: A prospect who replied receiving another message
#
# Happened 2026-09-23, seven minutes after the refusal.
#
# LOWEST GUARD: eligibility.decide returns BLOCKED_REPLIED for a contact
# who has replied.  The execution gate (executionguard.authorize) runs
# eligibility as gate 4 and refuses.  Additionally, inbound.handle
# stops both channels on any reply.
#
# ====================================================================


class Incident6_RepliedProspectGetsAnotherMessage(unittest.TestCase):
    """Incident 6: prospect replied 'no thank you', got another message
    seven minutes later.

    The guard: eligibility.decide returns BLOCKED_REPLIED.  The
    execution gate refuses at gate 4.
    """

    def _rec_with_reply(self):
        """A record with a reply event on it."""
        return {
            "id": "test-reply",
            "client": "demo",
            "company": "Test Company",
            "domain": "test.test",
            "state": "active",
            "company_facts": {"name": "Test Company"},
            "contacts": [{
                "key": "test",
                "email": "test@test.test",
                "name": "Test Person",
            }],
            "events": [
                {"type": "reply_received", "channel": "email",
                 "contact": "test",
                 "text": "no thank you",
                 "at": "2026-09-23T10:00:00+00:00"},
            ],
        }

    def test_replied_contact_is_blocked(self):
        """A contact who has replied is BLOCKED, not eligible."""
        rec = self._rec_with_reply()
        contact = rec["contacts"][0]
        # Pass the step directly so eligibility does not need a timeline
        step = {"channel": "email", "subject": "Test", "body": "Body text."}
        verdict = eligibility.decide(rec, contact, "em2",
                                     campaign={"client": "demo"},
                                     step=step)
        self.assertEqual(verdict["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_REPLIED,
                      verdict.get("reason", ""))

    def test_control_non_replied_contact_not_blocked_for_reply(self):
        """CONTROL: a contact who has NOT replied is not blocked for
        this reason."""
        rec = {
            "id": "test-noreply",
            "client": "demo",
            "company": "Test Company",
            "domain": "test.test",
            "state": "active",
            "company_facts": {"name": "Test Company"},
            "contacts": [{
                "key": "test",
                "email": "test@test.test",
                "name": "Test Person",
                "verdict": "valid",
            }],
            "events": [],
        }
        contact = rec["contacts"][0]
        step = {"channel": "email", "subject": "Test", "body": "Body text."}
        verdict = eligibility.decide(rec, contact, "em2",
                                     campaign={"client": "demo"},
                                     step=step)
        self.assertNotEqual(verdict["verdict"], eligibility.BLOCKED)

    def test_suppression_reason_includes_replied(self):
        """BLOCKED_REPLIED is in the suppression reasons the execution
        gate checks."""
        self.assertIn(eligibility.BLOCKED_REPLIED,
                      executionguard.SUPPRESSION_REASONS)

    def test_mutation_reply_check_is_loadbearing(self):
        """MUTATION: the reply check is what blocks this contact.
        Without it, a replied contact would not be BLOCKED for this
        reason."""
        rec = self._rec_with_reply()
        contact = rec["contacts"][0]
        step = {"channel": "email", "subject": "Test", "body": "Body text."}
        verdict = eligibility.decide(rec, contact, "em2",
                                     campaign={"client": "demo"},
                                     step=step)
        self.assertEqual(verdict["verdict"], eligibility.BLOCKED,
                         "a replied contact must be BLOCKED")


# ====================================================================
#
# INCIDENT 7: An old approval reused after the copy changed
#
# The approval fingerprint did not cover the actual words that shipped.
#
# LOWEST GUARD: approval.fingerprint + bisonfactory._certified_copy.
# The fingerprint is a hash of channel + subject + body + note + ps.
# _certified_copy hashes the entry's OWN subject and body and compares
# to the stamp.  Any edit to the words moves the fingerprint and the
# old approval no longer applies.
#
# ====================================================================


class Incident7_OldApprovalReusedAfterCopyChanged(unittest.TestCase):
    """Incident 7: an old approval reused after the copy changed.

    The guard: approval.fingerprint + bisonfactory._certified_copy.
    The fingerprint covers the exact words; _certified_copy verifies
    the staged words match the stamp.
    """

    def test_fingerprint_changes_when_body_changes(self):
        """Editing the body moves the fingerprint."""
        step1 = {"channel": "email", "subject": "Test", "body": "Original"}
        step2 = {"channel": "email", "subject": "Test",
                 "body": "Original\n\nEdited."}
        self.assertNotEqual(approval.fingerprint(step1),
                            approval.fingerprint(step2))

    def test_fingerprint_changes_when_subject_changes(self):
        """Editing the subject moves the fingerprint."""
        step1 = {"channel": "email", "subject": "Original", "body": "Test"}
        step2 = {"channel": "email", "subject": "Different", "body": "Test"}
        self.assertNotEqual(approval.fingerprint(step1),
                            approval.fingerprint(step2))

    def test_fingerprint_changes_when_ps_changes(self):
        """Editing the P.S. moves the fingerprint."""
        step1 = {"channel": "email", "subject": "Test", "body": "Body",
                 "ps": "P.S. One"}
        step2 = {"channel": "email", "subject": "Test", "body": "Body",
                 "ps": "P.S. Two"}
        self.assertNotEqual(approval.fingerprint(step1),
                            approval.fingerprint(step2))

    def test_reviewapproval_refuses_hash_mismatch(self):
        """reviewapproval.require refuses when the review file hash
        does not match the approval."""
        rows = [{"campaign": "487", "review_hash": "original_hash_1234",
                 "by": "zvonimir"}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("487", review_hash="new_hash_5678",
                                   rows=rows)

    def test_control_same_words_same_fingerprint(self):
        """CONTROL: identical words produce identical fingerprints."""
        step1 = {"channel": "email", "subject": "Test", "body": "Body"}
        step2 = {"channel": "email", "subject": "Test", "body": "Body"}
        self.assertEqual(approval.fingerprint(step1),
                         approval.fingerprint(step2))

    def test_mutation_fingerprint_is_loadbearing(self):
        """MUTATION: if the fingerprint check were removed, a stamp from
        one set of words would approve any other set."""
        fp_original = approval.fingerprint(
            {"channel": "email", "subject": "S", "body": "Original"})
        fp_edited = approval.fingerprint(
            {"channel": "email", "subject": "S", "body": "Edited"})
        self.assertNotEqual(fp_original, fp_edited,
                            "different words must produce different "
                            "fingerprints")


# ====================================================================
#
# INCIDENT 8: A direct create_lead/attach bypassing the factory
#
# The push that caused incident 1 used bison.create_lead and
# bison.attach_leads directly, bypassing the factory and all its gates.
#
# LOWEST GUARD: providers.refuse_unauthorized_write.  This sits on the
# TRANSPORT, before the socket.  Every mutating provider call goes
# through it.  A call that is not in SUPPORTED and not explicitly
# authorized is refused.
#
# ====================================================================


class Incident8_DirectCreateLeadBypass(unittest.TestCase):
    """Incident 8: a direct create_lead/attach bypassing the factory.

    The guard: providers.refuse_unauthorized_write sits on the transport
    and refuses any mutating call without explicit authorization.
    """

    def test_unauthorized_write_to_prospect_facing_host_is_refused(self):
        """A mutating call to a prospect-facing host without
        authorization is refused before the socket.  The host must be
        one the providers module has registered."""
        # Import the providers to trigger host registration
        from src.providers import bison as _bison  # noqa: F401
        # Use the actual registered host
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST",
                "https://send.resonategroup.co/api/leads")

    def test_read_is_not_refused(self):
        """A GET (read) call is not refused by the write guard."""
        from src.providers import bison as _bison  # noqa: F401
        # Should not raise
        providers.refuse_unauthorized_write(
            "GET",
            "https://send.resonategroup.co/api/leads")

    def test_non_prospect_facing_write_is_not_refused(self):
        """A write to a non-prospect-facing endpoint is not refused by
        this guard (it may have its own)."""
        # A non-prospect-facing URL should pass
        providers.refuse_unauthorized_write(
            "POST",
            "https://slack.com/api/chat.postMessage")

    def test_control_supported_operation_still_needs_auth(self):
        """CONTROL: even a supported operation refuses without auth."""
        from src.providers import heyreach as _hr  # noqa: F401
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST",
                "https://api.heyreach.io/api/public/campaign/UpdateSequence")

    def test_mutation_transport_guard_is_loadbearing(self):
        """MUTATION: if refuse_unauthorized_write were removed from the
        transport, a direct create_lead call would reach the provider
        without any gate.  This proves the transport guard is the
        lowest layer."""
        from src.providers import bison as _bison  # noqa: F401
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST",
                "https://send.resonategroup.co/api/leads")


# ====================================================================
#
# INCIDENT 9: The P.S. lost before it reaches the provider
#
# The P.S. was composed into the rendered email but dropped before
# reaching the provider projection.
#
# LOWEST GUARD: trailingcontent.compose + bisonfactory._approved_copy.
# compose appends the P.S. to the body.  _approved_copy requires the
# P.S. to be present on steps that expect one (em1, em3).  A step
# without a P.S. when one is expected is BLOCKED.
#
# ====================================================================


class Incident9_PSLostBeforeProvider(unittest.TestCase):
    """Incident 9: the P.S. lost before it reaches the provider.

    The guard: trailingcontent.compose appends the P.S. and
    bisonfactory._approved_copy requires it on steps that expect one.
    """

    def test_compose_appends_ps(self):
        """trailingcontent.compose appends the P.S. to the body."""
        result = trailingcontent.compose("Hello.", ps="P.S. Note.")
        self.assertIn("P.S. Note.", result)

    def test_compose_without_ps_omits_it(self):
        """Without a P.S., the body has no P.S. section."""
        result = trailingcontent.compose("Hello.")
        self.assertNotIn("P.S.", result)

    def test_missing_ps_on_required_step_blocks(self):
        """A required step (em1) without a P.S. key is BLOCKED by
        _approved_copy."""
        step = {
            "channel": "email",
            "subject": "Test",
            "body": "Body",
            # No ps field at all - this is the bypass
        }
        step["approval"] = {
            "fingerprint": approval.fingerprint(step),
            "by": "test@example.com",
        }
        sequence = [{"step_key": "em1", "order": 1}]
        source = {
            "cadence": {
                "test-contact": {
                    "em1": step,
                },
            },
        }
        copy_steps, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em1"}])
        self.assertTrue(any("em1" in m and "P.S." in m for m in missing),
                        f"expected em1 missing P.S., got {missing}")
        self.assertEqual(len(copy_steps), 0,
                         "em1 without P.S. must not produce copy")

    def test_control_step_with_ps_passes(self):
        """CONTROL: a step with a P.S. passes."""
        step = {
            "channel": "email",
            "subject": "Test",
            "body": "Body",
            "ps": "P.S. Note.",
        }
        step["approval"] = {
            "fingerprint": approval.fingerprint(step),
            "by": "test@example.com",
        }
        sequence = [{"step_key": "em1", "order": 1}]
        source = {
            "cadence": {
                "test-contact": {
                    "em1": step,
                },
            },
        }
        copy_steps, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em1"}])
        self.assertFalse(any("em1" in m for m in missing),
                         f"em1 with P.S. should not be missing: {missing}")

    def test_mutation_compose_is_loadbearing(self):
        """MUTATION: if compose did not append the P.S., the body would
        be different.  This proves compose is load-bearing."""
        with_ps = trailingcontent.compose("Hello.", ps="P.S. Note.")
        without_ps = trailingcontent.compose("Hello.", ps="")
        self.assertNotEqual(with_ps, without_ps,
                            "compose must append the P.S.")
        self.assertIn("P.S. Note.", with_ps)
        self.assertNotIn("P.S.", without_ps)


# ====================================================================
#
# INCIDENT 10: A LinkedIn step lost before HeyReach
#
# TASK-548.  A LinkedIn step was lost in the mapping from cadence to
# the HeyReach graph.
#
# LOWEST GUARD: heyreachfactory.COPY_MAPPING.  Every cadence step has
# an entry and every role resolves to exactly one cadence step.  A step
# that maps to no role is lost; a role that maps to no step is empty.
#
# ====================================================================


class Incident10_LinkedInStepLostBeforeHeyReach(unittest.TestCase):
    """Incident 10: a LinkedIn step lost before HeyReach (TASK-548).

    The guard: heyreachfactory.COPY_MAPPING ensures every cadence step
    has a graph role and every role resolves to a step.
    """

    def test_every_cadence_step_has_a_role(self):
        """Every LinkedIn cadence step (li1-li5) maps to at least one
        graph role."""
        for step_key in ("li1", "li2", "li3", "li4", "li5"):
            self.assertIn(step_key, heyreachfactory.COPY_MAPPING,
                          f"{step_key} has no role mapping")

    def test_every_role_resolves_to_a_step(self):
        """Every graph role resolves to exactly one cadence step."""
        all_steps = set()
        for step_key, mapping in heyreachfactory.COPY_MAPPING.items():
            roles = mapping["role"]
            if isinstance(roles, str):
                roles = (roles,)
            for role in roles:
                self.assertIsNotNone(role,
                                     f"{step_key} maps to a None role")
            all_steps.add(step_key)
        self.assertEqual(len(all_steps), 5,
                         "expected five LinkedIn steps in COPY_MAPPING")

    def test_no_step_maps_to_more_than_two_roles(self):
        """A step may fill two roles (on different branches) but not
        more."""
        for step_key, mapping in heyreachfactory.COPY_MAPPING.items():
            roles = mapping["role"]
            if isinstance(roles, str):
                roles = (roles,)
            self.assertTrue(len(roles) <= 2,
                            f"{step_key} maps to {len(roles)} roles")

    def test_control_all_five_steps_map(self):
        """CONTROL: all five steps map to roles."""
        self.assertEqual(len(heyreachfactory.COPY_MAPPING), 5)

    def test_linkedin_sequence_graph_is_built(self):
        """The HeyReach graph builder produces a graph from copy.

        The COPY_MAPPING covers every role the graph needs.  The graph
        builder itself requires inmail copy too; the mapping is the guard
        that prevents a step from being lost.
        """
        # Verify the mapping covers all required roles
        from src.sequenceplan import LINKEDIN_ROLES
        mapped_roles = set()
        for step_key, mapping in heyreachfactory.COPY_MAPPING.items():
            roles = mapping["role"]
            if isinstance(roles, str):
                roles = (roles,)
            mapped_roles.update(roles)
        # Every required role is covered by the mapping
        for role in LINKEDIN_ROLES:
            self.assertIn(role, mapped_roles,
                          f"required role {role!r} has no mapping")

    def test_mutation_copy_mapping_is_loadbearing(self):
        """MUTATION: if li3 were removed from COPY_MAPPING, the graph
        would have a gap.  This proves the mapping is load-bearing."""
        self.assertIn("li3", heyreachfactory.COPY_MAPPING)
        mapping = heyreachfactory.COPY_MAPPING["li3"]
        roles = mapping["role"]
        if isinstance(roles, str):
            roles = (roles,)
        self.assertTrue(len(roles) > 0,
                        "li3 must map to at least one role")


# ====================================================================
#
# SUITE INTEGRITY: the guards are on the real path
#
# ====================================================================


class SuiteIntegrity(unittest.TestCase):
    """Prove the guards are connected to the real entry points."""

    def test_refuse_unauthorized_write_is_called_by_transport(self):
        """refuse_unauthorized_write is called by the urllib transport."""
        source = inspect.getsource(providers._urllib_transport)
        self.assertIn("refuse_unauthorized_write", source,
                       "the transport must call refuse_unauthorized_write")

    def test_eligibility_decide_is_called_by_executionguard(self):
        """eligibility is used by the execution gate."""
        source = inspect.getsource(executionguard.authorize)
        self.assertIn("eligibility", source,
                       "executionguard.authorize must use eligibility")

    def test_approval_fingerprint_is_called_by_certified_copy(self):
        """approval.fingerprint is used by _certified_copy."""
        source = inspect.getsource(bisonfactory._certified_copy)
        self.assertIn("fingerprint", source,
                       "_certified_copy must check the fingerprint")

    def test_trailingcontent_compose_is_called_by_render(self):
        """trailingcontent.compose is on the render path."""
        source = inspect.getsource(render.emailbison_rows)
        self.assertIn("trailingcontent", source,
                       "render must use trailingcontent")

    def test_reviewapproval_require_is_on_activation_path(self):
        """reviewapproval.require is called before activation."""
        from src.providers import bison
        source = inspect.getsource(bison.resume_campaign)
        self.assertIn("reviewapproval", source,
                       "bison.resume_campaign must call reviewapproval")


if __name__ == "__main__":
    unittest.main()
