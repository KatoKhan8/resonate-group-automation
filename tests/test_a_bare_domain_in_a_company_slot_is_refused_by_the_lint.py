#!/usr/bin/env python3
"""A bare domain in a company slot is refused by the copy lint.

DECIDED 2026-10-15, `DECISION-canary-cohort-and-pool-2026-10-15.md` section 4:
alongside the company-name derivation, "have the copy gate refuse any body
carrying a token matching `^[a-z0-9.\\-]+\\.[a-z]{2,}$` in a company slot - a
bare domain in prospect-facing copy is a fail-closed refusal, not a rendering
choice." This is the gate leg; the render leg is pinned by
`test_a_bare_domain_is_never_a_companys_name_in_copy.py`. This test is the
task's deliverable (GLM-B TASK 0100): the CHANGE is the operator's to order
once certified. No production file is changed by the commit that carries
this test.

FOUND, measured at wt-glm-b-2026-10-14 HEAD 01f9b45e4 (CRLF tree): a body
naming `advertisepurple.com` three times - the exact body
`scripts/stage_s7_copy.render` produces when the Company column holds the
record's domain, which is the shape of `record.company` on 16 of the 25
sanctioned contacts - passes `lint.check` with ZERO codes. The usable-name
control also passes, so the clean verdict is not a word-count artifact: the
lint simply has no rule for the class. `check` was read end to end; nothing
between `recipient_*` and the lane codes looks at what the company slot
carries.

THE SLOT, OPERATIONALISED. The decision says "in a company slot". The tightest
reading both sides agree on, and the one asserted here, is the defect itself:
a token that IS one of the record's own company candidates (its `company`,
its `company_facts.name`, its `domain`) - the body addressing the prospect by
their own hostname. A fix may be stricter (any bare-domain token anywhere);
it may not be looser than this. The URL control below guards the other edge:
the CTA link the send chain appends is `https://...` and must not be refused
by this class of rule.

MUTATION PROOF (the fix direction): adding to `lint.check`, after the
placeholder rule -

    slots = {str(rec.get("company") or "").strip().lower(),
             str((rec.get("company_facts") or {}).get("name")
                 or "").strip().lower(),
             str(rec.get("domain") or "").strip().lower()}
    for field in (body, subject):
        for token in field.split():
            if (re.fullmatch(r"[a-z0-9.\\-]+\\.[a-z]{2,}", token)
                    and token.lower() in slots):
                fails.add("company_slot_domain")

- turns the red assertions green while both controls stay green. The
mutation was reverted byte-exact; no production file is changed here.
"""
import unittest

from src import lint                                               # noqa: E402

EMAIL = "jonathan@advertisepurple.com"


def _contact():
    return {
        "key": "jonathan-moisan",
        "name": "Jonathan Moisan",
        "email": EMAIL,
        "primary": True,
        # The fixture pattern from
        # tests/test_the_angle_gate_is_scoped_to_the_send_scope.py: valid
        # evidence from the client's own providers, so `sendable` recomputes
        # True under the productive policy (primary deliverable) and nothing
        # about the record refuses except the rule under test.
        "verification": {
            "state": "verified", "sendable": True,
            "evidence": [{"provider": p, "status": "valid", "email": EMAIL,
                          "at": "2026-09-30T12:00:00+00:00"}
                         for p in ("deliverable", "reoon")]},
    }


def _record():
    # record.company IS the bare domain - the measured shape of 16 of the 25
    # sanctioned contacts - and the facts carry the trading name.
    return {
        "id": "test-domain-co",
        "client": "productive",
        "state": "ready",
        "domain": "advertisepurple.com",
        "company": "advertisepurple.com",
        "company_facts": {"name": "Advertise Purple"},
        "contacts": [_contact()],
    }


def _step(company):
    """The opener the production render emits, {COMPANY} resolved by hand.

    Literal rather than rendered, deliberately: under the render-side fix the
    domain render begins to refuse (that is the point of the sibling test),
    and this gate must stay testable whatever the render does.
    """
    return {
        "channel": "email",
        "subject": "profitability visible on Monday",
        "body": (
            f"Jonathan, I work with digital marketing teams on profitability "
            f"visible on Monday, and I do not know how {company} handles it\n\n"
            f"The pattern I see in teams the size of {company} is that the "
            f"numbers arrive too late to act on. Utilisation and margin are "
            f"known at the end of the month, which is after the month when "
            f"something could have been done about them.\n\n"
            f"Is that roughly how it works at {company} today, or have you "
            f"already put something in place for it?"),
    }


class TheLintRefusesADomainInTheCompanySlot(unittest.TestCase):

    def _codes(self, company):
        return lint.check(_record(), _contact()["key"], _step(company))

    def test_the_control_body_passes_clean(self):
        """The trading name in the same slot lints clean - measured, and it
        must stay clean, so the refusal below can only be the domain."""
        self.assertEqual(self._codes("Advertise Purple"), [])

    def test_a_body_addressing_the_prospect_by_their_domain_is_refused(self):
        """RED today: this exact shape (three tokens, the record's own
        domain) is what the copy render ships for 16 of 25 contacts, and
        `lint.check` returns [] for it."""
        self.assertTrue(self._codes("advertisepurple.com"),
                        "the copy gate passed a body that addresses the "
                        "prospect by their own domain three times")

    def test_the_short_cctld_shape_is_refused_too(self):
        """`e-2.at` full-matches the decision's regex - two-character TLDs
        are the floor, and the rule must not depend on domain length."""
        record = _record()
        record["domain"] = "e-2.at"
        record["company"] = "e-2.at"
        record["contacts"][0]["email"] = "someone@e-2.at"
        for ev in record["contacts"][0]["verification"]["evidence"]:
            ev["email"] = "someone@e-2.at"
        step = _step("e-2.at")
        self.assertTrue(
            lint.check(record, record["contacts"][0]["key"], step),
            "the copy gate passed a two-character-TLD domain in the company "
            "slot")

    def test_a_url_is_not_a_bare_domain(self):
        """The CTA control. The send chain appends `https://...` links, and
        a token with a scheme or path does not full-match the decision's
        regex - so the refusal, when it arrives, must not catch it. Today
        this passes; it is here so a future over-broad rule cannot land
        silently."""
        step = _step("Advertise Purple")
        step["body"] += ("\n\nIf useful: https://theproductiveai.com/x/what-"
                         "we-do (no pitch on that page)")
        self.assertEqual(self._codes("Advertise Purple"), [])


if __name__ == "__main__":
    unittest.main()
