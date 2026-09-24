"""Checking a new list against what we already know.

The failure this prevents: a CSV arrives carrying somebody who replied in
March, a company that asked to be removed in June, and a colleague of
somebody we are mid-conversation with. Every row looks fresh, because a CSV
carries no history.

The two properties worth stating before the tests:

**Previously engaged is not permanently excluded.** "Remove us" suppresses.
"Not right now" is a follow-up. "My colleague is talking to you" is a hold.
Collapsing those into one verdict throws away the best rows in the list; the
tests below pin each one separately.

**Identity is proved, never guessed.** Matching is `dedupe`'s: normalised
email, canonical LinkedIn, provider lead id, our own record+contact key. A
name and a company are never identity, and there is a test that says so.
"""
import os
import tempfile
import unittest

from src import (account, accountpolicy as ap, agencydnc, events, hygiene,
                 store)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


class HygieneTest(CampaignTest):

    def record(self, rid="acme", domain="acme.test", company="Acme Ltd"):
        rec = store.new_record(rid, "domains", WS, company, domain)
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "john@acme.test", "selected": True,
             "linkedin": "https://www.linkedin.com/in/john-smith/",
             "priority": account.PRIMARY},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "sarah@acme.test", "selected": True,
             "priority": account.SECONDARY},
        ]
        store.save([rec])
        return rec

    def touched(self, rec, key=JOHN, at="2026-08-01T09:00:00+00:00"):
        events.record(rec, events.PUSH_MARKED, contact_key=key,
                      channel="email", day=1, at=at, sender_id="anna")
        return rec

    def replied(self, rec, key=JOHN, outcome=ap.POSITIVE,
                at="2026-08-05T09:00:00+00:00"):
        """A reply, classified, exactly as `replies.apply` records one.

        The receipt, the classifier's verdict, and - when positive - the
        positive signal. Recording only the receipt would leave
        `classify_outcome` reading `unknown`, which is correct and is not
        what this fixture is trying to describe.
        """
        events.record(rec, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{rec['id']}-{key}")
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=key,
                      channel="email", at=at, classification=outcome,
                      provider_event_id=f"r-{rec['id']}-{key}:classified")
        if outcome == ap.POSITIVE:
            events.record(rec, events.POSITIVE_REPLY_DETECTED,
                          contact_key=key, channel="email", at=at,
                          provider_event_id=f"r-{rec['id']}-{key}:positive")
        ap.apply_reply(rec, key, outcome, at=at, channel="email")
        return rec

    def index(self, *recs):
        return hygiene.index(list(recs) or [self.record()], workspace=WS)

    def check(self, candidate, *recs, **kw):
        return hygiene.check(candidate, self.index(*recs), **kw)


# ------------------------------------------------------------- the basics

class AFreshRowIsFresh(HygieneTest):

    def test_a_person_and_a_company_we_have_never_seen(self):
        out = self.check({"email": "new@elsewhere.test",
                          "domain": "elsewhere.test"}, self.record())
        self.assertEqual(out["verdict"], hygiene.FRESH)
        self.assertEqual(out["action"], hygiene.ELIGIBLE)

    def test_a_row_with_no_identifier_at_all_is_matched_on_the_account(self):
        rec = self.touched(self.record())
        out = self.check({"domain": "acme.test", "name": "Anonymous"}, rec)
        self.assertFalse(out["identified"])
        self.assertEqual(out["matched_on"], "account")
        self.assertEqual(out["verdict"], hygiene.PREVIOUSLY_CONTACTED)

    def test_a_name_and_a_company_are_never_identity(self):
        """The rule the whole module rests on."""
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.check({"name": "John Smith", "company": "Acme Ltd"}, rec)
        self.assertFalse(out["identified"])
        self.assertEqual(out["matched"], [],
                         "a name matched a contact history")


# ------------------------------------------------------- matching on identity

class ItMatchesOnProvenIdentity(HygieneTest):

    def test_the_same_email_in_an_old_campaign(self):
        rec = self.touched(self.record())
        out = self.check({"email": "John@Acme.TEST"}, rec)
        self.assertEqual(out["verdict"], hygiene.PREVIOUSLY_CONTACTED)
        self.assertEqual(out["matched"][0]["how"], "email")
        self.assertEqual(out["matched"][0]["contact_key"], JOHN)

    def test_the_same_linkedin_profile_in_an_old_campaign(self):
        rec = self.replied(self.record(), JOHN, ap.POSITIVE)
        out = self.check(
            {"linkedin": "http://linkedin.com/in/john-smith?trk=x"}, rec)
        self.assertEqual(out["matched"][0]["how"], "linkedin")
        self.assertEqual(out["verdict"], hygiene.ACTIVE_CONVERSATION)

    def test_a_different_person_at_a_known_company_is_not_the_same_person(self):
        rec = self.touched(self.record())
        out = self.check({"email": "brand-new@acme.test",
                          "domain": "acme.test"}, rec)
        self.assertEqual(out["matched"], [])
        self.assertEqual(out["matched_on"], "account")


# ------------------------------------------------- one verdict per history

class EveryHistoryHasItsOwnVerdict(HygieneTest):
    """`previously engaged` is not one bucket, and this is why it matters."""

    CASES = (
        (ap.UNSUBSCRIBE, hygiene.SUPPRESSED_CONTACT, hygiene.SUPPRESS),
        (ap.ACCOUNT_DNC, hygiene.SUPPRESSED_ACCOUNT, hygiene.SUPPRESS),
        (ap.LEFT_COMPANY, hygiene.INVALID_CONTACT, hygiene.EXCLUDE),
        (ap.WRONG_PERSON, hygiene.WRONG_PERSON, hygiene.SUPPRESS),
        (ap.POSITIVE, hygiene.ACTIVE_CONVERSATION, hygiene.HOLD),
        (ap.EXISTING_CLIENT, hygiene.ACTIVE_CONVERSATION, hygiene.HOLD),
        (ap.NOT_NOW, hygiene.FUTURE_FOLLOW_UP, hygiene.ROUTE),
        (ap.REFERRAL, hygiene.REFERRAL, hygiene.ROUTE),
        (ap.NEGATIVE, hygiene.PREVIOUSLY_ENGAGED, hygiene.HOLD),
    )

    def test_each_outcome_produces_its_own_verdict(self):
        for outcome, verdict, action in self.CASES:
            rec = self.replied(self.record(f"acme-{outcome}"), JOHN, outcome)
            out = self.check({"email": "john@acme.test"}, rec)
            self.assertEqual(out["verdict"], verdict, outcome)
            self.assertEqual(out["action"], action, outcome)

    def test_not_interested_is_not_treated_as_suppression(self):
        """The distinction the brief calls out: engaged is not excluded."""
        rec = self.replied(self.record(), JOHN, ap.NEGATIVE)
        out = self.check({"email": "john@acme.test"}, rec)
        self.assertNotEqual(out["action"], hygiene.SUPPRESS)

    def test_a_meeting_outranks_a_reply(self):
        rec = self.replied(self.record(), JOHN, ap.POSITIVE)
        events.record(rec, events.MEETING_MARKED, contact_key=JOHN,
                      at="2026-08-07T09:00:00+00:00")
        out = self.check({"email": "john@acme.test"}, rec)
        self.assertEqual(out["verdict"], hygiene.MEETING_BOOKED)
        self.assertEqual(out["action"], hygiene.EXCLUDE)

    def test_contacted_but_never_replied_is_review_not_hold(self):
        rec = self.touched(self.record())
        out = self.check({"email": "john@acme.test"}, rec)
        self.assertEqual(out["verdict"], hygiene.PREVIOUSLY_CONTACTED)
        self.assertEqual(out["action"], hygiene.REVIEW)


# ------------------------------------------------------- account history

class TheAccountsHistoryReachesANewPerson(HygieneTest):
    """The case the brief singles out: Sarah has never appeared before."""

    def test_an_account_dnc_reaches_somebody_who_has_never_appeared(self):
        rec = self.replied(self.record(), JOHN, ap.ACCOUNT_DNC)
        out = self.check({"email": "brand-new@acme.test",
                          "domain": "acme.test"}, rec)
        self.assertEqual(out["verdict"], hygiene.SUPPRESSED_ACCOUNT)
        self.assertEqual(out["action"], hygiene.SUPPRESS)

    def test_a_positive_reply_holds_a_new_colleague_rather_than_deleting_them(self):
        rec = self.replied(self.record(), JOHN, ap.POSITIVE)
        out = self.check({"email": "michael@acme.test",
                          "domain": "acme.test"}, rec)
        self.assertEqual(out["verdict"], hygiene.ACTIVE_CONVERSATION)
        self.assertEqual(out["action"], hygiene.HOLD)
        self.assertIn("John Smith", out["why"])

    def test_the_account_verdict_follows_the_configured_reply_policy(self):
        """Reconfigure the policy and import agrees with the engine."""
        rec = self.replied(self.record(), JOHN, ap.POSITIVE)
        out = hygiene.check({"email": "michael@acme.test",
                             "domain": "acme.test"},
                            self.index(rec),
                            config={"reply": {"on_positive": "continue"}})
        self.assertEqual(out["action"], hygiene.REVIEW)

    def test_a_quiet_account_leaves_a_new_person_fresh(self):
        rec = self.record()
        out = self.check({"email": "new@acme.test", "domain": "acme.test"},
                         rec)
        self.assertEqual(out["verdict"], hygiene.FRESH)


# --------------------------------------------------------- the worst wins

class TheMostConservativeVerdictWins(HygieneTest):

    def test_a_suppression_outranks_a_contact_level_hold(self):
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        self.replied(rec, SARAH, ap.ACCOUNT_DNC)
        out = self.check({"email": "john@acme.test", "domain": "acme.test"},
                         rec)
        self.assertEqual(out["verdict"], hygiene.SUPPRESSED_ACCOUNT)

    def test_the_order_is_the_verdict_tuple(self):
        self.assertEqual(hygiene.worst([hygiene.FRESH,
                                        hygiene.PREVIOUSLY_CONTACTED]),
                         hygiene.PREVIOUSLY_CONTACTED)
        self.assertEqual(hygiene.worst([]), hygiene.FRESH)

    def test_every_verdict_has_an_action_and_a_label(self):
        for verdict in hygiene.VERDICTS:
            self.assertIn(verdict, hygiene.ACTION_OF)
            self.assertIn(verdict, hygiene.LABEL)
            self.assertIn(hygiene.ACTION_OF[verdict], hygiene.ACTIONS)


# ------------------------------------------------------ agency suppression

class AgencySuppressionSaysNothingAboutWhy(HygieneTest):

    def setUp(self):
        super().setUp()
        self.dnc = os.path.join(tempfile.mkdtemp(prefix="dnc-"), "dnc.jsonl")
        os.environ["AGENCY_DNC"] = self.dnc

    def tearDown(self):
        os.environ.pop("AGENCY_DNC", None)
        super().tearDown()

    def test_it_suppresses_a_row_no_workspace_has_ever_seen(self):
        agencydnc.add("email", "stranger@nowhere.test")
        out = self.check({"email": "stranger@nowhere.test"},
                         self.record(), agency=agencydnc.Index())
        self.assertEqual(out["verdict"], hygiene.AGENCY_SUPPRESSED)
        self.assertEqual(out["action"], hygiene.SUPPRESS)

    def test_the_reason_names_no_workspace_person_or_campaign(self):
        agencydnc.add("email", "stranger@nowhere.test",
                      agencydnc.COMPLAINT)
        out = self.check({"email": "stranger@nowhere.test"},
                         self.record(), agency=agencydnc.Index())
        why = " ".join(out["reasons"]).lower()
        self.assertIn("agency safety policy", why)
        for leak in ("productive", "acme", "campaign", "replied", "august"):
            self.assertNotIn(leak, why, leak)

    def test_the_file_holds_no_plaintext_identifier(self):
        agencydnc.add("email", "stranger@nowhere.test")
        with open(self.dnc, encoding="utf-8") as handle:
            body = handle.read()
        self.assertNotIn("stranger", body)
        self.assertNotIn("nowhere.test", body)

    def test_a_name_can_never_put_anybody_on_the_list(self):
        with self.assertRaises(ValueError):
            agencydnc.add("name", "Sarah Jones")

    def test_an_unknown_reason_is_refused(self):
        with self.assertRaises(ValueError):
            agencydnc.add("email", "x@y.test", "because-i-said-so")

    def test_an_ordinary_reply_does_not_put_anybody_on_the_agency_list(self):
        """Client history stays inside the client's tenancy.

        REWRITTEN 2026-09-24. This asserted it of EVERY reply including an
        unsubscribe, which was right until the operator removed the
        unsubscribe link from every campaign and made the reply the whole
        opt-out mechanism. An opt-out that stops at a tenancy boundary is not
        an opt-out: the next workspace to import this person writes to them
        again.

        So the guarantee is narrowed to what it still is, and the narrowing
        is the exception rather than the rule - every outcome below is an
        answer about this quarter's OFFER and stays where it was heard.
        """
        for outcome in (ap.POSITIVE, ap.NEUTRAL, ap.NEGATIVE, ap.NOT_NOW,
                        ap.NOT_ICP, ap.WRONG_PERSON, ap.LEFT_COMPANY,
                        ap.EXISTING_CLIENT, ap.REFERRAL, ap.UNKNOWN):
            with self.subTest(outcome=outcome):
                self.setUp()
                self.replied(self.record(), JOHN, outcome)
                self.assertEqual(len(agencydnc.Index()), 0)

    def test_only_a_removal_request_crosses_the_tenancy_boundary(self):
        """OPERATOR, 2026-09-24. The one shape of reply that crosses.

        Asked through `keys_for`, which is `agencydnc`'s own definition of a
        strong identifier - the profile URL is canonicalised on the way in, so
        hashing the raw string here would test a different question.
        """
        for outcome in ap.AGENCY_SUPPRESSION_OUTCOMES:
            with self.subTest(outcome=outcome):
                self.setUp()
                rec = self.replied(self.record(), JOHN, outcome)
                john = rec["contacts"][0]
                index = agencydnc.load()
                keys = agencydnc.keys_for(john)
                self.assertEqual(sorted(k.split(":")[0] for k in keys),
                                 ["email", "linkedin"])
                for plain, digest in keys.items():
                    self.assertIn(digest, index, plain.split(":")[0])

    def test_a_company_wide_stop_carries_every_colleague_across(self):
        """`account_do_not_contact` means the COMPANY asked, so all of them.

        `_suppress_account` suppresses every contact individually, and each
        one's identifiers cross with it. Sarah never replied; the company
        spoke for her, which is the whole difference between this class and
        `unsubscribe`.
        """
        rec = self.replied(self.record(), JOHN, ap.ACCOUNT_DNC)
        index = agencydnc.load()
        for contact in rec["contacts"]:
            for plain, digest in agencydnc.keys_for(contact).items():
                self.assertIn(digest, index, f"{contact['key']}: {plain}")

    def test_what_crosses_still_leaks_nothing(self):
        """The privacy model is unchanged, and that is load-bearing.

        A one-way hash and a closed reason category. No name, no company, no
        workspace, no record id, no campaign - so the file cannot be read as
        a directory of another client's prospects.
        """
        self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        with open(self.dnc, encoding="utf-8") as handle:
            body = handle.read()
        for leak in ("john", "acme", "productive", "linkedin", "smith",
                     "unsubscribe"):
            self.assertNotIn(leak, body.lower(), leak)
        entry = agencydnc.load()[
            agencydnc.fingerprint("email", "john@acme.test")]
        self.assertEqual(entry["reason"], agencydnc.REQUESTED)


# ------------------------------------------------------------- tenancy

class HistoryStaysInsideItsWorkspace(HygieneTest):

    def test_an_index_built_from_one_workspace_holds_only_that_workspace(self):
        mine = self.replied(self.record("acme"), JOHN, ap.ACCOUNT_DNC)
        theirs = store.new_record("other", "domains", "contactout",
                                  "Other Ltd", "other.test")
        theirs["contacts"] = [{"key": "x", "name": "X", "email": "x@other.test",
                               "selected": True}]
        store.save([theirs])

        index = hygiene.index([mine], workspace=WS)
        out = hygiene.check({"email": "x@other.test", "domain": "other.test"},
                            index)
        self.assertEqual(out["verdict"], hygiene.FRESH,
                         "another workspace's record reached this check")

    def test_the_index_never_widens_what_it_was_given(self):
        """`Repo.records()` has already scoped; this must not re-read."""
        index = hygiene.index([], workspace=WS)
        self.assertEqual(index["records"], 0)
        self.assertEqual(index["by_identity"], {})


# ------------------------------------------------------ the import path

class TheImportPreviewClassifiesRatherThanDeletes(HygieneTest):
    """Requirements O, P and Q, at the parser rather than at the screen."""

    def parse(self, csv_text, rec=None):
        from src.web import upload

        recs = [rec] if rec is not None else []
        return upload.parse(csv_text.encode("utf-8"), batch="b", client=WS,
                            history=hygiene.index(recs, workspace=WS))

    def test_a_duplicate_row_inside_one_file_is_still_caught(self):
        out = self.parse("domain\nacme.test\nacme.test\n")
        self.assertEqual(out["duplicates"], 1)

    def test_a_previously_engaged_row_is_kept_with_its_reason(self):
        """Cleaning a list never means losing the row that matters most."""
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse("domain,email\nacme.test,john@acme.test\n", rec)
        self.assertEqual(len(out["rows"]), 1, "an engaged row was dropped")
        verdict = out["rows"][0]["hygiene"]
        self.assertEqual(verdict["verdict"], hygiene.SUPPRESSED_CONTACT)
        self.assertTrue(verdict["why"])

    def test_the_preview_summarises_by_verdict(self):
        rec = self.replied(self.record(), JOHN, ap.ACCOUNT_DNC)
        out = self.parse("domain,email\nacme.test,new@acme.test\n"
                         "elsewhere.test,other@elsewhere.test\n", rec)
        summary = out["hygiene"]
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["eligible"], 1)
        self.assertEqual(summary["by_verdict"][hygiene.SUPPRESSED_ACCOUNT], 1)

    def test_the_summary_rows_are_ordered_most_final_first(self):
        rec = self.replied(self.record(), JOHN, ap.ACCOUNT_DNC)
        out = self.parse("domain,email\nacme.test,new@acme.test\n"
                         "elsewhere.test,other@elsewhere.test\n", rec)
        order = [r["verdict"] for r in out["hygiene"]["rows"]]
        self.assertEqual(order[0], hygiene.SUPPRESSED_ACCOUNT)

    def test_a_formula_in_an_email_column_is_refused(self):
        """The guard the domain column has. CSV injection travels by column."""
        out = self.parse("domain,email\nacme.test,=cmd|'/c calc'!A1\n")
        self.assertEqual(len(out["rows"]), 1)
        self.assertNotIn("email", out["rows"][0])

    def test_a_linkedin_column_matches_a_known_profile(self):
        rec = self.replied(self.record(), JOHN, ap.NOT_NOW)
        out = self.parse("domain,linkedin\n"
                         "acme.test,https://linkedin.com/in/john-smith\n", rec)
        self.assertEqual(out["rows"][0]["hygiene"]["verdict"],
                         hygiene.FUTURE_FOLLOW_UP)

    def test_without_history_no_verdict_is_claimed(self):
        """None means the pass did not run, not that it found nothing."""
        from src.web import upload

        out = upload.parse(("domain\nacme.test\n").replace("\n", chr(10))
                           .encode("utf-8"), batch="b", client=WS)
        self.assertIsNone(out["hygiene"])


# --------------------------------------------------------------- summary

class TheSummaryIsWhatThePreviewShows(HygieneTest):

    def test_it_counts_by_verdict_and_by_action(self):
        rec = self.replied(self.touched(self.record()), JOHN, ap.UNSUBSCRIBE)
        index = self.index(rec)
        rows = [hygiene.check(c, index) for c in (
            {"email": "john@acme.test"},
            {"email": "new@elsewhere.test", "domain": "elsewhere.test"},
            {"email": "other@elsewhere.test", "domain": "elsewhere.test"},
        )]
        summary = hygiene.summarise(rows)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["eligible"], 2)
        self.assertEqual(summary["not_eligible"], 1)
        self.assertEqual(summary["by_verdict"][hygiene.SUPPRESSED_CONTACT], 1)

    def test_nothing_is_dropped_from_the_result(self):
        """Cleaning a list never means losing a row."""
        rec = self.replied(self.record(), JOHN, ap.ACCOUNT_DNC)
        index = self.index(rec)
        rows = [hygiene.check({"email": f"p{i}@acme.test",
                               "domain": "acme.test"}, index)
                for i in range(5)]
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertTrue(row["why"], "a verdict with no reason")


if __name__ == "__main__":
    unittest.main()
