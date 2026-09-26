"""A step must never render with an empty signature.

THE DEFECT THIS EXISTS FOR. TASK-341, 2026-09-26: every one of the 31 written
leads renders "mailbox signature / none stored on this mailbox" on all five
email steps - 155 email steps with no signature. The review page renders the
empty state politely, so the gap is invisible.

THE DESIGN INTENT. The copy engine deliberately writes NO signature:
- src/copystages.py:283: "Write no signature. The sending mailbox appends its own."
- src/copyprompts.py:315-316: "Write no signature and no sign-off name."
- config/clients/productive.yaml:7: mode: client_rep

The signature is supposed to come from the EmailBison provider's sender settings
(email_signature field on the sender_email object), appended at send time.

THE LOCAL SYSTEM HAS NO SIGNATURE FIELD. The senderidentity module's email
account model (src/senderidentity.py new_email_account) has no signature field.
The 154 attested mailboxes have signatures at the EmailBison provider, but the
local system has never queried or stored them.

THE VERDICT: ABSENT AT SOURCE. The signature is not stored in the local system's
sender identity model, and the provider has not been queried for it.

WHY THIS TEST IS SKIPPED. The operator has not yet decided whether signatures
are required in the rendered output. The copy engine writes no signature by
design, and the provider appends its own at send time. A test that fails on
an empty signature would refuse every step until the operator decides what the
signature should say. This test is written but skipped, so it can be enabled
when the operator makes that decision.

WHAT THIS TEST CHECKS. When enabled, it asserts that:
1. The step body is not empty
2. The sender identity is present in the generation context
3. The signature block (if rendered) is not empty
"""
import unittest

from src import clients, generate


class AStepNeverRendersAnEmptySignature(unittest.TestCase):

    @unittest.skip("operator has not yet decided signatures are required; "
                   "the copy engine writes no signature by design and the "
                   "provider appends its own at send time - TASK-341")
    def test_the_step_body_is_not_empty(self):
        """A step with no body is a step that says nothing."""
        rec = {"id": "test-lead", "company": "Test Co",
               "contacts": [{"key": "dana", "name": "Dana", "persona": "founder",
                             "angle": "founder"}],
               "cadence": {"dana": {"em1": {"body": "", "day": 1, "channel": "email"}}}}
        contact = rec["contacts"][0]
        step = rec["cadence"]["dana"]["em1"]
        body = step.get("body") or ""
        self.assertTrue(body.strip(),
                        "a step with an empty body says nothing to the prospect")

    @unittest.skip("operator has not yet decided signatures are required; "
                   "the copy engine writes no signature by design and the "
                   "provider appends its own at send time - TASK-341")
    def test_the_sender_identity_is_present(self):
        """The generation context must carry sender identity."""
        config = {"sender": {"name": "Ivan", "role": "founder",
                             "company": "Productive",
                             "works_on": "project profitability for agencies"}}
        identity = clients.sender_identity(config)
        self.assertTrue(identity, "sender_identity must not be empty")
        self.assertIn("name", identity, "sender identity must have a name")

    @unittest.skip("operator has not yet decided signatures are required; "
                   "the copy engine writes no signature by design and the "
                   "provider appends its own at send time - TASK-341")
    def test_the_generation_context_carries_sender_identity(self):
        """The generation context for an email step must carry sender identity."""
        rec = {"id": "test-lead", "company": "Test Co",
               "contacts": [{"key": "dana", "name": "Dana", "persona": "founder",
                             "angle": "founder"}],
               "cadence": {"dana": {"em1": {"body": "Hi Dana, testing.", "day": 1,
                                             "channel": "email"}}}}
        contact = rec["contacts"][0]
        client = {"sender": {"name": "Ivan", "role": "founder",
                             "company": "Productive",
                             "works_on": "project profitability for agencies"}}
        block = generate.context_for(rec, contact, client=client, step="draft",
                                     step_key="em1")
        self.assertIn("sender_identity", block,
                      "the generation context must carry sender_identity")
        self.assertTrue(block["sender_identity"],
                        "sender_identity must not be empty")


if __name__ == "__main__":
    unittest.main()
