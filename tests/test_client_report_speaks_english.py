"""A client's document does not print this system's identifiers.

`_replies` built its table with `str(k).title()`. Python's `str.title`
capitalises after an underscore and keeps the underscore, so the reply
classification keys came out as `Out_Of_Office`, `Not_Now` and
`Account_Do_Not_Contact` under a column headed "Classification" - in every
client PDF, on the Reply Analysis page.

`_humanise` sits four lines above it and exists for exactly this: its
docstring says "a client's document is not the place a reader meets this
system's identifiers". The appendix already routes through it. This table did
not.

The vendor canary is also widened here. It looped `("executive", "detailed")`
and skipped `monthly` - the canonical monthly deliverable, and the one a
client actually receives on a schedule.
"""
import unittest

from src import clientreport
from tests.test_client_reports import text_of, OPERATOR
from tests.webbase import WebTest

# Derived, so a template added later is covered without editing a test.
CLIENT_TEMPLATES = clientreport.CLIENT_FACING


class AClientReportSpeaksEnglish(WebTest):

    def generate(self, who=OPERATOR, **fields):
        session = self.signin(who)
        payload = {"csrf": session.csrf("/reporting/client"),
                   "template": "executive"}
        payload.update(fields)
        status, body, _ = session.post_bytes(
            "/reporting/client/generate", payload)
        self.assertEqual(status, 200, body[:200])
        return body

    # ------------------------------------------------------- the identifier
    #
    # Planted, not hoped for. The demo estate's only reply classification is
    # `positive`, which has no underscore - so a test that merely rendered the
    # demo report would have passed against the broken code and proved
    # nothing. These keys are the ones `accountpolicy` actually defines.

    PLANTED = {"out_of_office": 3, "not_now": 2, "account_do_not_contact": 1,
               "positive": 4}

    def planted_report(self, template="monthly"):
        meta = {"workspace_name": "W", "workspace_slug": "w",
                "template": template, "period": "All time",
                "campaign_label": "All campaigns", "generated_by": "t",
                "report_id": "r1", "generated_at": "2026-09-08",
                "demo": False}
        data = {"reply_breakdown": dict(self.PLANTED),
                "replies": sum(self.PLANTED.values())}
        return text_of(clientreport.build(data, meta, ["replies"]))

    def test_no_underscored_identifier_reaches_the_reply_table(self):
        drawn = self.planted_report()
        for key in self.PLANTED:
            self.assertNotIn(key, drawn)
            if "_" in key:
                # `str.title` keeps the underscore, which is the defect.
                # For a single word it is already the right answer.
                self.assertNotIn(key.title(), drawn)

    def test_each_classification_is_printed_as_a_sentence(self):
        drawn = self.planted_report()
        for label in ("Out of office", "Not now", "Account do not contact"):
            self.assertIn(label, drawn)

    def test_a_single_word_classification_keeps_its_capital(self):
        """`_humanise` passes a word with no underscore straight through, so
        fixing the underscored keys is what broke this one."""
        self.assertIn("Positive", self.planted_report())
        self.assertNotIn(chr(10) + "positive" + chr(10),
                         self.planted_report())

    # ------------------------------------------------ the widened canary

    def test_no_provider_name_reaches_any_client_template(self):
        """`monthly` was outside the loop, and it is the one sent monthly."""
        for template in CLIENT_TEMPLATES:
            drawn = text_of(self.generate(template=template)).lower()
            for vendor in ("reoon", "contactout", "emailbison", "heyreach",
                           "apify", "aiark", "deliverable"):
                self.assertNotIn(vendor, drawn, f"{vendor} in {template}")

    def test_every_client_template_still_renders(self):
        """Otherwise the two tests above pass on empty documents."""
        for template in CLIENT_TEMPLATES:
            raw = self.generate(template=template)
            self.assertTrue(raw.startswith(b"%PDF"))
            self.assertTrue(text_of(raw).strip(), f"{template} drew nothing")


if __name__ == "__main__":
    unittest.main()
