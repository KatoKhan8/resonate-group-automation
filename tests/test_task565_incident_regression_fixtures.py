#!/usr/bin/env python3
"""TASK-565 — every real incident becomes a permanent regression requirement.

THE BOUNDARY CONDITION IS THE ACCEPTANCE, not the presence of a test.

For each incident there are TWO tests:

    test_<incident>            the guard prevents the real effect
    test_<incident>_boundary   removing THAT guard, in memory, makes the
                               first one fail in the incident-producing
                               direction

The second is what makes the first evidence. A fixture that still passes
with its guard removed is testing something else - measured here 2026-09-28,
when a bypass mutation left a test green because a DIFFERENT guard produced
a HELD instead of a BLOCK.

Every mutation is a monkeypatch inside a try/finally. No production guard is
weakened and nothing is written to disk.
"""
import unittest
from unittest import mock

from src import (approval, claims, copylint, eligibility, generate,
                 heyreachfactory, lint, providers, sendersignature,
                 sequenceplan, trailingcontent)
from src import generate_campaign as gc
from src.providers import bison as _bison          # noqa: F401  (base registry)

NO_EVIDENCE = [{"gap": "customer case studies", "detail": "n"},
               {"gap": "verified benchmarks", "detail": "n"}]


def _contact(**kw):
    c = {"key": "c1", "name": "Test Person", "email": "t@example.com",
         "linkedin": "linkedin.com/in/test"}
    c.update(kw)
    return c


def _rec(contact=None, **kw):
    c = contact or _contact()
    r = {"id": "rec-565", "client": "productive", "log": [], "events": [],
         "company_facts": {}, "company": "TestCo", "domain": "test.test",
         "contacts": [c], "cadence": {}}
    r.update(kw)
    return r


def _pack(facts):
    return {"facts": [{"snippet": f} for f in facts]}


CLEAN_BODY = ("Hi there, a plain body with nothing to trace and no claim in "
              "it at all, written to clear the minimum word count without "
              "asserting anything about the company or its customers.")


def _lead(first_body=None, **kw):
    """A lead with all five steps filled.

    FIVE, because `copylint.STEPS_EXPECTED` is 5 and a short lead fires
    `empty_step`. A boundary test whose lead is refused by `empty_step`
    cannot show that the rule under test is the one doing the work - which
    is exactly what this suite exists to prove, and it caught this fixture
    first.
    """
    bodies = [first_body or CLEAN_BODY] + [
        "%s Follow-up number %d, written plainly." % (CLEAN_BODY, n)
        for n in range(2, 6)]
    lead = {"id": "c1",
            "steps": [{"subject": "a question about your projects",
                       "body": b} for b in bodies],
            "ps": {}, "linkedin": {},
            "pack": _pack(["TestCo runs retail merchandising programmes."])}
    lead.update(kw)
    return lead


def _refused(lead):
    return gc.copylint_failures(copylint.check_batch([lead]), lead["id"])


# ---------------------------------------------------------------- incident 1
class Incident1WrongCompanyCopy(unittest.TestCase):
    """64 emails carrying another agency's pitch went out from 503/504/505.

    LOWEST BOUNDARY: `copylint.untraceable_company_claim`. It refuses a claim
    about the company that no pack fact supports, at batch lint, BEFORE the
    copy can be approved - which is upstream of every provider write.
    """

    # A NUMERIC SPECIFIC, because that is what the rule keys on: it extracts
    # figures and currency from a company claim and asks the pack to support
    # them. A prose claim with no number is caught by other rules, not this
    # one, and a boundary test has to exercise the guard it names.
    BAD = ("Hi there, I saw TestCo raised $12M in Series B funding in 2024, "
           "which usually means a lot more moving parts to keep track of "
           "when budgets and delivery live in separate systems entirely.")

    def _bad_lead(self):
        return _lead(first_body=self.BAD)

    def test_a_company_claim_no_pack_fact_supports_is_refused(self):
        self.assertTrue(_refused(self._bad_lead()),
                        "an untraceable company claim reached approval")

    def test_boundary_removing_the_rule_lets_it_through(self):
        real = copylint.untraceable
        try:
            copylint.untraceable = lambda body, pack: []
            self.assertFalse(
                _refused(self._bad_lead()),
                "the fixture passes with untraceable() removed, so it is "
                "not the guard doing the work")
        finally:
            copylint.untraceable = real
        self.assertTrue(_refused(self._bad_lead()), "guard not restored")


# ---------------------------------------------------------------- incident 2
class Incident2SignatureNotTheMailboxOwner(unittest.TestCase):
    """A signature that is not the mailbox owner's.

    LOWEST BOUNDARY: `sendersignature.compose`, which derives the block from
    the sender identity and returns EMPTY for a sender with no name rather
    than inventing one, plus `refuse_if_duplicate` for a body that already
    carries a block.
    """

    def test_the_signature_is_derived_from_the_sender_identity(self):
        self.assertEqual(sendersignature.compose({"name": "Ivan"}),
                         "Ivan\nProductive")

    def test_an_unnamed_sender_signs_nothing_rather_than_guessing(self):
        self.assertEqual(sendersignature.compose({}), "")
        self.assertEqual(sendersignature.compose(None), "")

    def test_a_body_already_signed_is_refused_not_double_signed(self):
        sig = sendersignature.compose({"name": "Ivan"})
        with self.assertRaises(sendersignature.SignatureDuplicate):
            sendersignature.refuse_if_duplicate("Body.\n\n" + sig, sig)

    def test_boundary_removing_the_duplicate_check_double_signs(self):
        sig = sendersignature.compose({"name": "Ivan"})
        body = "Body.\n\n" + sig
        real = sendersignature.refuse_if_duplicate
        try:
            sendersignature.refuse_if_duplicate = lambda b, s: b
            doubled = trailingcontent.compose(
                sendersignature.refuse_if_duplicate(body, sig), signature=sig)
            self.assertEqual(doubled.count(sig.strip()), 2,
                             "without the check the block is not doubled, so "
                             "the check is not what prevents it")
        finally:
            sendersignature.refuse_if_duplicate = real


# ---------------------------------------------------------------- incident 3
class Incident3EmptyBodyFromUnresolvedVariables(unittest.TestCase):
    """77 emails with an empty subject and a `<p></p>` body, 2026-09-23.

    LOWEST BOUNDARY: `lint.check`. An unfilled merge field is `placeholder`
    and an absent body is `body_missing`; either refuses the step before it
    can be stored, which is upstream of approval and of any provider write.
    """

    def _step(self, body):
        return {"channel": "email", "generated": True,
                "subject": "a question about your projects", "body": body}

    def test_an_unresolved_variable_refuses_the_step(self):
        rec = _rec()
        failures = lint.check(rec, "c1", self._step(
            "Hi {FIRST_NAME}, this body still carries a merge field that "
            "nobody filled in before it was about to be sent to a person."))
        self.assertIn("placeholder", failures)

    def test_an_empty_body_refuses_the_step(self):
        rec = _rec()
        self.assertTrue(lint.check(rec, "c1", self._step("")),
                        "an empty body was not refused")

    def test_boundary_without_the_placeholder_rule_it_ships(self):
        rec = _rec()
        step = self._step(
            "Hi {FIRST_NAME}, this body still carries a merge field that "
            "nobody filled in before it was about to be sent to a person.")
        real = lint.PLACEHOLDER_RE
        try:
            lint.PLACEHOLDER_RE = mock.Mock(search=lambda t: None)
            self.assertNotIn("placeholder", lint.check(rec, "c1", step),
                             "the fixture passes with PLACEHOLDER_RE "
                             "neutered, so it is not the guard")
        finally:
            lint.PLACEHOLDER_RE = real
        self.assertIn("placeholder", lint.check(rec, "c1", step))


# ------------------------------------------------------------- incidents 4/5
class Incident4And5UnsupportedFigure(unittest.TestCase):
    """An unsupported figure on an email (4) and on a LinkedIn message (5).

    LOWEST BOUNDARY: `claims.check`, reached on BOTH channels through
    `generate._step_refusals`, which is the gate the campaign path runs
    before a step may be stored.
    """

    FIGURE = ("TestCo grew forty five percent last year, which is why margin "
              "visibility matters so much for a team of that size.")

    def _cited(self, channel):
        c = _contact()
        rec = _rec(c)
        if channel == "linkedin":
            pair = ("li2", {"channel": "linkedin", "generated": True,
                            "note": self.FIGURE})
        else:
            pair = ("em2", {"channel": "email", "generated": True,
                            "subject": "a question", "body": self.FIGURE})
        out = generate._step_refusals(rec, c, [pair])
        return "unsupported claim" in " ".join(out.get(pair[0]) or [])

    def test_an_unsupported_figure_is_refused_on_email(self):
        self.assertTrue(self._cited("email"))

    def test_an_unsupported_figure_is_refused_on_linkedin(self):
        self.assertTrue(self._cited("linkedin"))

    def test_boundary_removing_claims_lets_the_figure_through_both(self):
        real = claims.check
        try:
            claims.check = lambda *a, **k: []
            self.assertFalse(self._cited("email"))
            self.assertFalse(self._cited("linkedin"))
        finally:
            claims.check = real
        self.assertTrue(self._cited("email"))
        self.assertTrue(self._cited("linkedin"))


# ---------------------------------------------------------------- incident 6
class Incident6RepliedThenMessagedAgain(unittest.TestCase):
    """A prospect who replied "no thank you" received another message,
    seven minutes after the refusal, 2026-09-23.

    LOWEST BOUNDARY: `eligibility.must_not_contact`, which answers about the
    PERSON rather than about a step, so it holds whether or not anything is
    scheduled. `_replied` is the check inside it that this incident needs.
    """

    def _reasons(self, contact, rec):
        return [r for r in eligibility.must_not_contact(rec, contact) if r]

    def test_an_unsubscribed_contact_may_not_be_contacted(self):
        c = _contact(unsubscribed=True)
        self.assertTrue(self._reasons(c, _rec(c)))

    def test_a_reply_event_also_blocks_at_the_account_level(self):
        """Defence in depth, asserted but NOT the boundary under test.

        A reply event trips `_paused` (`blocked:company_paused`) as well as
        `_replied`, so it cannot isolate either. The incident's own path is
        the one below: `accountpolicy.apply_reply` honours a removal request
        by writing `unsubscribed` on the contact, and `_replied` reads that.
        """
        c = _contact()
        rec = _rec(c, events=[{"type": "reply_received", "contact": "c1"}])
        self.assertTrue(self._reasons(c, rec))

    def test_a_control_contact_is_contactable(self):
        c = _contact()
        self.assertFalse(self._reasons(c, _rec(c)))

    def test_boundary_removing_replied_makes_them_contactable_again(self):
        c = _contact(unsubscribed=True)
        rec = _rec(c)
        self.assertEqual(
            self._reasons(c, rec), [eligibility.BLOCKED_UNSUBSCRIBED],
            "the unsubscribed state must be the ONLY reason, or this cannot "
            "isolate the boundary")
        real = eligibility._replied
        try:
            eligibility._replied = lambda rec_, contact_: None
            self.assertFalse(
                self._reasons(c, rec),
                "the fixture passes with _replied removed, so a different "
                "guard is doing the work and this does not test the incident")
        finally:
            eligibility._replied = real
        self.assertTrue(self._reasons(c, rec), "guard not restored")


# ---------------------------------------------------------------- incident 7
class Incident7OldApprovalReusedAfterTheCopyChanged(unittest.TestCase):
    """An approval reused after the words it covered changed.

    LOWEST BOUNDARY: `approval.is_approved`, which compares the approval's
    fingerprint against the step's CURRENT text and so cannot be latched.
    """

    def _rec_with_approved_step(self):
        step = {"channel": "email", "subject": "s", "body": "the approved words"}
        rec = _rec()
        rec["cadence"] = {"c1": {"em1": dict(step)}}
        rec["cadence"]["c1"]["em1"]["approval"] = {
            "by": "operator", "at": "2026-09-29",
            "fingerprint": approval.fingerprint(step)}
        return rec

    def test_the_approval_holds_while_the_words_are_unchanged(self):
        rec = self._rec_with_approved_step()
        self.assertTrue(approval.is_approved(rec, "c1", "em1"))

    def test_changing_the_words_drops_the_approval(self):
        rec = self._rec_with_approved_step()
        rec["cadence"]["c1"]["em1"]["body"] = "different words entirely"
        self.assertFalse(approval.is_approved(rec, "c1", "em1"),
                         "an approval survived a change to the copy it covered")

    def test_boundary_a_fingerprint_that_ignores_the_body_latches(self):
        rec = self._rec_with_approved_step()
        rec["cadence"]["c1"]["em1"]["body"] = "different words entirely"
        real = approval.fingerprint
        try:
            approval.fingerprint = lambda step: "constant"
            rec["cadence"]["c1"]["em1"]["approval"]["fingerprint"] = "constant"
            self.assertTrue(
                approval.is_approved(rec, "c1", "em1"),
                "with a constant fingerprint the approval should latch; it "
                "did not, so the fingerprint is not what invalidates it")
        finally:
            approval.fingerprint = real


# ---------------------------------------------------------------- incident 8
class Incident8DirectProviderWriteBypass(unittest.TestCase):
    """A create/attach reaching a provider outside the factory.

    LOWEST BOUNDARY: `providers.refuse_unauthorized_write`, called on the
    FIRST line of the transport, before the socket.

    AND IT MAY NOT DEPEND ON IMPORT ORDER. Until 2026-09-29 the guarded-host
    set was filled only when a provider module was imported, so a caller that
    reached the transport without importing one found it empty and was not
    refused. The hosts are seeded at `providers` import now, and
    `test_the_seed_matches_what_the_modules_register` keeps the seed honest.
    """

    LIVE_WRITES = ("https://send.resonategroup.co/api/campaigns/487/leads",
                   "https://api.heyreach.io/api/public/campaign/"
                   "AddLeadsToCampaignV2")

    def test_an_unauthorized_prospect_facing_write_is_refused(self):
        for url in self.LIVE_WRITES:
            with self.assertRaises(providers.ProviderWriteRefused, msg=url):
                providers.refuse_unauthorized_write("POST", url)

    def test_the_guard_does_not_depend_on_provider_import_order(self):
        """The real bases are guarded by `providers` alone.

        Asserted against the seed rather than by re-importing, because a
        module already imported by this suite cannot be un-imported.
        """
        for host in providers.KNOWN_PROSPECT_FACING_HOSTS:
            self.assertIn(host, providers._prospect_facing_hosts)

    def test_the_seed_matches_what_the_modules_register(self):
        from src.providers import bison, heyreach     # noqa: F401
        for host in providers.KNOWN_PROSPECT_FACING_HOSTS:
            self.assertIn(host, providers._prospect_facing_hosts)
        self.assertIn(providers.host_of(bison.DEFAULT_BASE),
                      providers.KNOWN_PROSPECT_FACING_HOSTS)
        self.assertIn(providers.host_of(heyreach.BASE),
                      providers.KNOWN_PROSPECT_FACING_HOSTS)

    def test_a_read_is_not_refused(self):
        providers.refuse_unauthorized_write(
            "GET", "https://send.resonategroup.co/api/campaigns/487")

    def test_boundary_an_unguarded_host_is_not_protected(self):
        real = set(providers._prospect_facing_hosts)
        try:
            providers._prospect_facing_hosts.clear()
            providers.refuse_unauthorized_write("POST", self.LIVE_WRITES[0])
        finally:
            providers._prospect_facing_hosts.clear()
            providers._prospect_facing_hosts.update(real)
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write("POST", self.LIVE_WRITES[0])


# ---------------------------------------------------------------- incident 9
class Incident9PSLostBeforeTheProvider(unittest.TestCase):
    """The P.S. present in the render and absent from what was pushed.

    LOWEST BOUNDARY: `trailingcontent.compose`, the ONE composer both the
    rendered email and the EmailBison projection call, so the two cannot
    disagree about what a body is.
    """

    BODY, PS, SIG = "The body.", "A specific verified fact.", "Ivan\nProductive"

    def test_the_ps_survives_into_the_composed_body(self):
        out = trailingcontent.compose(self.BODY, ps=self.PS, signature=self.SIG)
        self.assertIn(self.PS, out)

    def test_the_ps_renders_labelled_and_never_doubled(self):
        out = trailingcontent.compose(self.BODY, ps=self.PS, signature=self.SIG)
        self.assertIn("P.S. " + self.PS, out)
        self.assertEqual(out.count("P.S."), 1)
        already = trailingcontent.compose(self.BODY, ps="P.S. " + self.PS,
                                          signature=self.SIG)
        self.assertEqual(already.count("P.S."), 1)

    def test_boundary_without_append_ps_it_is_lost(self):
        real = trailingcontent.append_ps
        try:
            trailingcontent.append_ps = lambda body, ps: body or ""
            out = trailingcontent.compose(self.BODY, ps=self.PS,
                                          signature=self.SIG)
            self.assertNotIn(self.PS, out)
        finally:
            trailingcontent.append_ps = real
        self.assertIn(self.PS, trailingcontent.compose(
            self.BODY, ps=self.PS, signature=self.SIG))


# --------------------------------------------------------------- incident 10
class Incident10LinkedInStepLostBeforeHeyReach(unittest.TestCase):
    """A LinkedIn step present in the plan and absent from the push.

    LOWEST BOUNDARY: `sequenceplan.derive_heyreach_payload`, which projects
    the keys `cadencelibrary.LINKEDIN_WRITER_KEYS` names, and
    `heyreachfactory.COPY_MAPPING`, which must carry a graph role for each.
    """

    def _plan(self):
        seq = {k: "note %s, long enough to be a real message." % k
               for k in ("li1", "li2", "li3", "li4", "li5")}
        return sequenceplan.new(
            "productive", {"company": "TestCo", "domain": "test.test"},
            [{"contact_key": "c1", "email": "t@example.com",
              "first_name": "T", "qualification": "QUALIFIED_THIN",
              "sequences": seq, "subjects": {}}])

    def test_all_five_linkedin_steps_reach_the_projection(self):
        lead = sequenceplan.derive_heyreach_payload(self._plan())["leads"][0]
        li = lead.get("linkedin") or lead.get("li") or {}
        self.assertEqual(sorted(li), ["li1", "li2", "li3", "li4", "li5"])

    def test_every_projected_step_has_a_graph_role(self):
        for k in ("li1", "li2", "li3", "li4", "li5"):
            self.assertTrue(heyreachfactory.COPY_MAPPING.get(k, {}).get("role"),
                            "%s has no HeyReach graph role" % k)

    def test_boundary_a_four_key_authority_loses_li5(self):
        from src import cadencelibrary
        real = cadencelibrary.LINKEDIN_WRITER_KEYS
        try:
            cadencelibrary.LINKEDIN_WRITER_KEYS = ("li1", "li2", "li3", "li4")
            lead = sequenceplan.derive_heyreach_payload(
                self._plan())["leads"][0]
            li = lead.get("linkedin") or lead.get("li") or {}
            self.assertNotIn("li5", li)
        finally:
            cadencelibrary.LINKEDIN_WRITER_KEYS = real
        lead = sequenceplan.derive_heyreach_payload(self._plan())["leads"][0]
        self.assertIn("li5", lead.get("linkedin") or lead.get("li") or {})


if __name__ == "__main__":
    unittest.main()
