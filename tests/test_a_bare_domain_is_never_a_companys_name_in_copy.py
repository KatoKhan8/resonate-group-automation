#!/usr/bin/env python3
"""A bare domain is never a company's name in prospect-facing copy.

DECIDED 2026-10-15, `DECISION-canary-cohort-and-pool-2026-10-15.md` section 4:
one canonical derivation for a contact's company name -

    company_facts.name   when non-empty AND not domain-shaped
    else record.company  when not domain-shaped
    else REFUSE the render

- and a copy gate that refuses any body carrying a token matching
`^[a-z0-9.\\-]+\\.[a-z]{2,}$` in a company slot. The lint leg is pinned by
`test_a_bare_domain_in_a_company_slot_is_refused_by_the_lint.py`; this file
pins the render leg. Born red in TASK 0100 (tests only, no production file);
LANDED by TASK 0110 - the commit that carries this file also carries the two
production lines in `scripts/stage_s7_copy.py` that turn it green, and the
refusal was made VISIBLE here before landing (see the last red test).

FOUND, measured at wt-glm-b-2026-10-14 HEAD 01f9b45e4 (CRLF tree):

* `record.company` is a bare domain on 16 of the 25 sanctioned contacts
  (re-measured from phase0b/backup/queue.jsonl.pre-emailbatch), so a renderer
  that trusts it addresses three prospects in ten by their own hostname.
* The STORE path already implements the derivation. `cadence.company_name`
  refuses domain-only records with `CompanyNameUnusable`, and
  `cadence.expand_step` lets that raise propagate - measured end to end, all
  three scenarios behave. Those assertions below are GREEN today and are here
  so the two chains cannot drift apart once the red leg is fixed.
* The COPY path - `scripts/stage_s7_copy.render`, the render the approval
  sheet was built from - implements NONE of it. It reads one `Company` string
  off the supplier row, holds it only when EMPTY, and renders whatever it is
  given: measured, `Company='advertisepurple.com'` renders `body_1` naming
  the domain three times ("...and I do not know how advertisepurple.com
  handles it"), and `Company='e-2.at'` does the same. That is the red.

WHY THE RED LEG IS THE REFUSAL, NOT THE PRECEDENCE: the copy render never
sees the record - facts-vs-record precedence cannot even be expressed through
its row interface, and today it is resolved by whatever builds the row (the
sheet-side builder plus the supplier CSV, `work/Productive/
productive_ICP_safe_to_send (1).csv`, which the standing rules forbid this
lane from reading). What the render itself must guarantee, and what the
decision's else-leg demands, is that a domain-shaped name FAILS CLOSED: the
render refuses rather than choosing. The assertion is on the invariant (no
bare-domain token in any rendered value), not the mechanism, so a fix that
resolves a facts name inside the render passes too.

MUTATION PROOF (the fix direction): adding two lines to `render` -

    if re.fullmatch(r"[a-z0-9.\\-]+\\.[a-z]{2,}", company):
        return None, "company name is domain-shaped; refusing to render"

- directly after the empty-company hold turns every red assertion green while
the usable-name control stays green. TASK 0110 landed exactly that shape after
the full three-state proof in one session: strengthened tests RED (the new
visibility leg fails with hold=None, because the render still ships), GREEN
with the two lines applied, RED again after a byte-exact revert of both
production files (proven by raw sha256, both files LF on disk and in blob,
no conversion active), then re-applied and committed.
"""
import re
import unittest

from scripts import stage_s7_copy                              # noqa: E402
from src import cadence, clients                               # noqa: E402

#: The decision's own token shape, verbatim.
DOMAIN = re.compile(r"^[a-z0-9.\-]+\.[a-z]{2,}$")

ROW = {
    "First Name": "Jonathan",
    "Company": None,               # set per scenario
    "Industry": "digital marketing",
    "Job Title": "Digital Project Manager",
}

EMAIL = "jonathan@advertisepurple.com"
CONTACT = {
    "key": "jonathan-moisan",
    "name": "Jonathan Moisan",
    "email": EMAIL,
    "persona": "delivery",
}


def _record(company, facts_name):
    return {
        "id": "test-domain-co",
        "client": "productive",
        "state": "ready",
        "domain": "advertisepurple.com",
        "company": company,
        "company_facts": {"name": facts_name,
                          "industry": "digital marketing"},
        "contacts": [dict(CONTACT)],
    }


def _domain_tokens(variables):
    """Every bare-domain token in every rendered string, with its field."""
    if not variables:
        return []
    out = []
    for field, value in variables.items():
        for token in re.split(r"\s+", str(value or "")):
            if DOMAIN.match(token):
                out.append(f"{field}:{token}")
    return out


class TheCopyRenderRefusesADomainShapedCompany(unittest.TestCase):
    """RED today: `stage_s7_copy.render` ships the domain, three times."""

    @classmethod
    def setUpClass(cls):
        cls.config = clients.load("productive")

    def _render(self, company):
        row = dict(ROW, Company=company)
        return stage_s7_copy.render(row, self.config)

    def test_the_control_renders_a_real_name(self):
        """The chain works, so the red below is the company slot, not the
        fixture. Green today and must stay green under the fix."""
        variables, hold = self._render("Advertise Purple")
        self.assertIsNone(hold)
        self.assertIn("Advertise Purple", variables["body_1"])
        self.assertEqual(_domain_tokens(variables), [])

    def test_a_domain_company_is_never_rendered(self):
        """Measured red: body_1 names `advertisepurple.com` three times."""
        variables, hold = self._render("advertisepurple.com")
        tokens = _domain_tokens(variables)
        self.assertTrue(variables is None or not tokens,
                        "the copy render shipped a bare domain in the "
                        f"company slot ({tokens}); hold={hold!r}. The "
                        "decision's else-leg is REFUSE, never the hostname")

    def test_a_short_cctld_company_is_never_rendered_either(self):
        """`e-2.at` also full-matches `^[a-z0-9.\\-]+\\.[a-z]{2,}$` - the
        two-character TLD is the regex's floor, and the refusal must not
        depend on the domain being long. Measured red today."""
        variables, hold = self._render("e-2.at")
        tokens = _domain_tokens(variables)
        self.assertTrue(variables is None or not tokens,
                        f"a two-character-TLD domain reached the copy "
                        f"({tokens}); hold={hold!r}")

    def test_the_refusal_is_visible_not_swallowed(self):
        """TASK 0110's strengthening - the brief's "the refusal must be
        visible to the caller, not swallowed". A domain-shaped company must
        come back as (None, hold) with the hold NAMING the domain shape:
        (None, None) would read to a caller as "nothing to do" and the lead
        would silently vanish from the sheet instead of being held. RED
        today for exactly that reason: the render ships the domain and the
        hold is None."""
        for company in ("advertisepurple.com", "e-2.at"):
            with self.subTest(company=company):
                variables, hold = self._render(company)
                self.assertTrue(
                    variables is None and hold is not None
                    and "domain" in hold.lower(),
                    f"a domain-shaped company must come back as a VISIBLE "
                    f"refusal; got variables="
                    f"{'rendered' if variables is not None else 'None'}, "
                    f"hold={hold!r}. The hold reason is the caller's only "
                    f"signal that the render refused")


class TheStorePathIsTheCanonicalDerivation(unittest.TestCase):
    """GREEN today, asserted so it STAYS that way. `cadence.expand_step`
    over the production STEPS day-5 spec (persona_pain, the template that
    names {company} twice) is the one render that already carries the
    decision. If these ever fail, the two chains have drifted and the red
    class above no longer measures the same defect."""

    @classmethod
    def setUpClass(cls):
        cls.config = clients.load("productive")
        cls.spec = next(s for s in cadence.STEPS if s["key"] == "day5")

    def _step(self, company, facts_name):
        return cadence.expand_step(_record(company, facts_name),
                                   dict(CONTACT), self.spec, self.config)

    def test_facts_empty_falls_to_record_company(self):
        step = self._step("Advertise Purple", "")
        self.assertIn("Advertise Purple", step["body"])
        self.assertEqual(_domain_tokens({"body": step["body"]}), [])

    def test_record_company_domain_falls_to_facts_name(self):
        step = self._step("advertisepurple.com", "Advertise Purple")
        self.assertIn("Advertise Purple", step["body"])
        self.assertNotIn("advertisepurple.com", step["body"])

    def test_both_unusable_refuses_rather_than_choosing(self):
        with self.assertRaises(cadence.CompanyNameUnusable):
            self._step("advertisepurple.com", "advertisepurple.com")


if __name__ == "__main__":
    unittest.main()
