"""A refusal that names the reason is an oracle.

The handler already knew this. Its comment reads "404, not 403. Telling a
caller that an object exists but belongs to somebody else is itself a
disclosure" - and the next line rendered `str(e)`, which is "record 'x'
belongs to another client and is not readable here". So the status code was
careful and the page said it out loud.

Why it matters more than "an id exists". Record ids created through the
product are a deterministic function of the domain: `upload.commit` uses
`ingest.slug(row["domain"])`. So the question anybody in any workspace
could ask, for any domain they can think of, is "is this company on another
Resonate client's target list?" - and get a definitive answer. For an
agency running competing clients in one estate, that is the disclosure the
tenancy boundary exists to prevent.

The reason still reaches `_refusal`, which is the audit path. Somebody
investigating needs to know a refusal was tenancy rather than a typo. The
person who asked does not.

Existing coverage compared status codes only - `session.get(real)[0] ==
session.get(fake)[0]` - which is why a body that differed went unnoticed.
"""
import re
import unittest

from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
MINE = "productive"
THEIRS = "contactout"


def visible(body):
    """The page's words, with markup and whitespace removed."""
    text = re.sub(r"<[^>]+>", " ", body or "")
    return re.sub(r"\s+", " ", text).strip().lower()


class ARefusalLooksLikeAnAbsence(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self.switch(self.session, MINE)
        theirs = self.records_of(THEIRS)
        self.assertTrue(theirs, "the estate has no other-client records")
        self.theirs = theirs[0]

    def pair(self, template, invented="zzz-invented-000"):
        """The same route asked about a real other-tenant id and a made-up
        one. Both must answer identically."""
        real = self.session.get(template.format(id=self.theirs["id"]))
        fake = self.session.get(template.format(id=invented))
        return real, fake

    def test_a_company_from_another_workspace_reads_as_absent(self):
        """The defect."""
        real, fake = self.pair("/companies/{id}")
        self.assertEqual(real[0], fake[0])
        self.assertNotIn("another client", visible(real[1]),
                         "the page names the reason for the refusal")

    def test_the_id_is_not_echoed_back_as_confirmation(self):
        real, _ = self.pair("/companies/{id}")
        self.assertNotIn(self.theirs["id"].lower(), visible(real[1]))

    def test_an_account_page_answers_the_same_way(self):
        real, fake = self.pair("/outreach/account/{id}")
        self.assertEqual(real[0], fake[0])
        self.assertNotIn("another client", visible(real[1]))

    def test_a_guessable_domain_cannot_be_probed(self):
        """The end-to-end shape. An operator who knows only a domain can
        derive the id, so this is the question the oracle answered."""
        from src import ingest

        derived = ingest.slug(self.theirs["domain"])
        real = self.session.get("/companies/" + derived)
        fake = self.session.get("/companies/" + ingest.slug("nobody.example"))
        self.assertEqual(real[0], fake[0])
        self.assertNotIn("another client", visible(real[1]))

    def test_the_refusal_is_still_recorded_for_an_auditor(self):
        """Silence towards the caller is not silence in the log. Removing
        the disclosure must not have removed the evidence."""
        from src import workspaces

        self.session.get("/companies/" + self.theirs["id"])
        refusals = [e for e in workspaces.audit(limit=500)
                    if e.get("action") == "security.refused"
                    and (e.get("metadata") or {}).get("kind")
                    == "cross_workspace"]
        self.assertTrue(refusals,
                        "a tenancy refusal left no trace for an auditor")

    def test_and_the_auditor_is_still_told_which_refusal_it_was(self):
        """The reason moved out of the page and stayed in the log. If it
        had been dropped from both, the fix would have traded a
        disclosure for a blind spot."""
        from src import workspaces

        self.session.get("/companies/" + self.theirs["id"])
        latest = [e for e in workspaces.audit(limit=500)
                  if e.get("action") == "security.refused"][0]
        self.assertIn("another client", str(latest.get("reason")))

    def test_a_record_in_my_own_workspace_still_opens(self):
        """So the tests above are about a refusal, not about the route
        having stopped working."""
        mine = self.records_of(MINE)[0]
        status, body, _ = self.session.get("/companies/" + mine["id"])
        self.assertEqual(status, 200)
        self.assertIn(mine["domain"].lower(), visible(body))


if __name__ == "__main__":
    unittest.main()
