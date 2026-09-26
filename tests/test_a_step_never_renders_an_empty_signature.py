"""No mailbox has a signature stored — TASK-341 / TASK-392.

THE FINDING

EmailBison's `/sender-emails` endpoint returns `email_signature` on every
inbox row.  Measured in the provider's own response shape::

    {"id": 3392, "name": "...", "email": "sender.one@...",
     "email_signature": "<p>...VP of Business Development @ExampleCo</p>",
     "daily_limit": 15}

`senderinventory.provider_state()` DROPS that field.  It preserves status,
type, warmup, daily_limit, tags, counters and bounce_rate — but not
`email_signature`.  The canonical sender model
(`senderidentity.new_email_account`) has no field for it either.

The render path — `cadence.render`, `render.py`, `bisonfactory.py` — never
references a signature at all.  `leadobserve.scheduled_rows` explicitly says
"the sender's email signature... None of that is kept."

VERDICT: PRESENT AT SOURCE, LOST IN PIPELINE at `senderinventory.provider_state()`.

154 attested mailboxes, 0 with a signature stored in canonical state.
155 email steps (31 leads x 5 steps) render empty.

WHAT THIS TEST ASSERTS

1. `provider_state()` does NOT preserve `email_signature` — documenting the
   gap.  When somebody fixes it, this test flips and must be updated.
2. The canonical email account model has no signature field — same gap.
3. A render with no signature data produces an empty/absent signature,
   which is the launch blocker OPERATING-MODE §24 names.
"""
import unittest

from src import senderidentity
from src.senderinventory import provider_state


class TestProviderStateDropsSignature(unittest.TestCase):
    """The provider has the signature; the pipeline drops it."""

    def _provider_row(self):
        """The shape EmailBison's /sender-emails actually returns."""
        return {
            "id": 3392,
            "status": "Connected",
            "type": "default",
            "warmup_enabled": True,
            "daily_limit": 15,
            "tags": [{"name": "sales"}],
            "emails_sent_count": 800,
            "bounced_count": 5,
            "unique_replied_count": 42,
            "unsubscribed_count": 1,
            "email_signature": "<p>Anna Kovač<br>VP Business Development<br>"
                               "Resonate Group</p>",
        }

    def test_provider_state_does_not_preserve_email_signature(self):
        """DOCUMENTING THE GAP.  The provider returns `email_signature`;
        `provider_state()` drops it.  When this test fails, the gap is fixed
        and the test must be updated to assert preservation instead."""
        row = self._provider_row()
        state = provider_state(row)
        self.assertNotIn(
            "email_signature", state,
            "EXPECTED FAILURE: provider_state now preserves email_signature. "
            "Update this test to assert it IS present.")

    def test_provider_row_has_signature_but_state_does_not(self):
        """The source has it, the stored state does not.  THE GAP."""
        row = self._provider_row()
        self.assertIn("email_signature", row)
        self.assertTrue(row["email_signature"])
        state = provider_state(row)
        self.assertNotIn("email_signature", state)


class TestCanonicalModelHasNoSignatureField(unittest.TestCase):
    """`senderidentity.new_email_account` has no signature field."""

    def test_new_email_account_has_no_signature_key(self):
        account = senderidentity.new_email_account(
            workspace="productive",
            account_id="eb-3392",
            sender_id="anna",
            email_address="anna01@example.test",
            provider="emailbison",
            provider_account_id="3392",
            active=True,
            daily_limit=15,
            health="ok",
        )
        self.assertNotIn(
            "email_signature", account,
            "EXPECTED FAILURE: new_email_account now accepts/stores a "
            "signature.  Update this test.")
        self.assertNotIn("signature", account)


class TestRenderProducesNoSignature(unittest.TestCase):
    """The render path has no signature handling at all."""

    def test_cadence_render_has_no_signature_variable(self):
        """`cadence.render` substitutes template variables.  No template
        carries a `{signature}` variable because no step defines one."""
        from src.cadence import render
        template = {"subject": "Hello {first_name}", "body": "Body text"}
        values = {"first_name": "John"}
        result = render(template, values)
        self.assertEqual(result["body"], "Body text")
        self.assertNotIn("signature", result)
        self.assertNotIn("Signature", result.get("body", ""))


if __name__ == "__main__":
    unittest.main()
