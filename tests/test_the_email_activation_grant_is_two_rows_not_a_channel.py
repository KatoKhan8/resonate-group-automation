"""EMAIL_ACTIVATE was widened by one row on 2026-09-18. These are the refusals.

The grant is the single verb on EmailBison that makes a staged sequence start
emailing real people, and it is scoped to NAMED CANONICAL ROWS rather than to
the channel. Widening it from one row to two is the kind of change whose risk
lives entirely in what it stops refusing, so this file spends almost all of
its assertions on the refusal branches and only two on the acceptance.

Every case here drives `require_conditional_permission` - the real predicate
against real canonical state - rather than re-stating the tuple. A test that
reads the constant back passes when the constant is wrong.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, providerwrites  # noqa: E402

V3 = "productive-email-control-v3"
US = "productive-email-us-cohort-v1"


def require(provider_id, canonical):
    return providerwrites.require_conditional_permission(
        providerwrites.EMAIL_ACTIVATE, provider_id, canonical)


class TestTheGrantIsTwoNamedRows(unittest.TestCase):
    def test_both_authorized_rows_pass_against_their_own_binding(self):
        """The acceptance half. Two rows, each against the id it is bound to.

        Skipped rather than failed when a row has no provider id yet: the US
        cohort's campaign does not exist until the factory creates it, and a
        test that demanded otherwise would fail for a whole session for a
        reason that is not a defect.
        """
        for canonical in (V3, US):
            with self.subTest(canonical=canonical):
                row = campaigns.get(canonical) or {}
                bound = row.get("bison_campaign_id")
                if not bound:
                    self.skipTest(f"{canonical} is not bound to a provider "
                                  f"campaign yet")
                self.assertTrue(require(str(bound), canonical))

    def test_an_unbound_row_is_refused_rather_than_waved_through(self):
        """No `bison_campaign_id` means nothing to check against.

        The dangerous reading is that an unbound row is harmless because it
        names nothing. It is the opposite: unchecked is unbounded.
        """
        original = campaigns.get(US) or {}
        if not original.get("bison_campaign_id"):
            with self.assertRaises(providerwrites.WriteRefused) as caught:
                require("487", US)
            self.assertIn("bison_campaign_id", str(caught.exception))
        else:
            self.skipTest("the US cohort row is already bound")


class TestEverythingElseStillRefuses(unittest.TestCase):
    def test_a_row_nobody_authorized(self):
        for canonical in ("camp-1", "productive-email-control-v2",
                          "productive-email-liheavy-v1", "", None):
            with self.subTest(canonical=canonical):
                with self.assertRaises(providerwrites.WriteRefused):
                    require("487", canonical)

    def test_the_clients_own_live_campaigns(self):
        """327, 328 and 352 are the client's. They are not ours to start.

        Offered under BOTH authorized rows, because the failure that matters
        is a valid row carrying an invalid number.
        """
        for provider_id in ("327", "328", "352", "418"):
            for canonical in (V3, US):
                with self.subTest(provider=provider_id, canonical=canonical):
                    with self.assertRaises(providerwrites.WriteRefused):
                        require(provider_id, canonical)

    def test_the_historical_campaigns_under_an_authorized_row(self):
        """481 and 485 offered with a row that IS authorized.

        This is the exact dangerous pairing: the caller has a real grant in
        hand and names the wrong campaign with it. 485 holds live 487's own
        ten leads and 481 holds four of the five US-cohort contacts.
        """
        for provider_id in ("481", "485"):
            for canonical in (V3, US):
                with self.subTest(provider=provider_id, canonical=canonical):
                    with self.assertRaises(providerwrites.WriteRefused):
                        require(provider_id, canonical)

    def test_the_two_authorized_rows_cannot_borrow_each_others_campaign(self):
        """Widening to two rows creates a pairing that did not exist before.

        With one row there was nothing to cross. With two, a caller holding
        the US cohort's row could name 487 - the live campaign whose ten
        people already have openers queued - and a predicate that checked only
        "is this row authorized" would admit it.
        """
        v3_bound = (campaigns.get(V3) or {}).get("bison_campaign_id")
        us_bound = (campaigns.get(US) or {}).get("bison_campaign_id")

        # THE REFUSAL IS ASSERTED UNCONDITIONALLY. Its REASON is only asserted
        # once the row is bound, and that is not a softening: before staging,
        # the US row has no `bison_campaign_id`, so the honest refusal is
        # "nothing to check against" rather than "mismatched binding". Pinning
        # the mismatch message today would fail for the one session in which
        # the row is correct and simply young. Once bound, the stricter
        # assertion turns itself on - which is what makes it worth having.
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            require(str(v3_bound), US)
        if us_bound:
            self.assertIn("mismatched binding", str(caught.exception).lower())
            with self.assertRaises(providerwrites.WriteRefused) as other:
                require(str(us_bound), V3)
            self.assertIn("mismatched binding", str(other.exception).lower())
        else:
            self.assertIn("bison_campaign_id", str(caught.exception))

    def test_no_campaign_id_at_all(self):
        for canonical in (V3, US):
            with self.subTest(canonical=canonical):
                with self.assertRaises(providerwrites.WriteRefused):
                    require(None, canonical)
                with self.assertRaises(providerwrites.WriteRefused):
                    require("", canonical)


class TestTheNeverActivateListHoldsWhenTheBindingIsWrong(unittest.TestCase):
    """What holds when the binding check is handed a wrong number.

    REWRITTEN 2026-09-18 WHEN THE ENTRIES WERE PINNED, and the rewrite is the
    point rather than an inconvenience. With `(487, v3)` and `(489, us)` pinned
    the PIN now refuses a re-bound row BEFORE `_NEVER_ACTIVATE` is consulted -
    so the earlier version of these tests passed while exercising a different
    guard than the one they named. CLAUDE.md: when you break a guard
    deliberately, confirm the intended test failed for the intended reason and
    that a different guard did not fire first. It did.

    `_NEVER_ACTIVATE` is still live and still necessary, on the UNPINNED path:
    a new entry may be added with `None` while its campaign is being created,
    because this provider archives a campaign that sits without a sender and
    pinning a literal first would run that clock. On that path the row supplies
    the id, and this list is the only thing standing between a mis-bound new
    row and 481 or 485. So these tests drive it there.
    """

    ROW = "productive-email-being-created"

    def _unpinned(self, binding):
        """An UNPINNED allowlist entry, plus a row bound to `binding`."""
        real_get = campaigns.get
        real_grant = providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS

        def fake_get(campaign_id, rows=None, _v=binding):
            if campaign_id == self.ROW:
                return {"campaign_id": self.ROW, "bison_campaign_id": _v}
            return real_get(campaign_id, rows)

        campaigns.get = fake_get
        providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS = (
            real_grant + ((None, self.ROW),))
        return real_get, real_grant

    def _restore(self, real_get, real_grant):
        campaigns.get = real_get
        providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS = real_grant

    def test_an_unpinned_row_pointing_at_481_or_485_is_refused_by_the_list(self):
        for bad in sorted(providerwrites._NEVER_ACTIVATE):
            with self.subTest(bound=bad):
                restore = self._unpinned(int(bad))
                try:
                    with self.assertRaises(
                            providerwrites.WriteRefused) as caught:
                        require(bad, self.ROW)
                    self.assertIn("never-activate", str(caught.exception))
                finally:
                    self._restore(*restore)

    def test_the_list_is_what_refuses_and_not_something_else(self):
        """Break-proofing, in the form the rule asks for.

        With `_NEVER_ACTIVATE` emptied the same call must start PASSING. If it
        still refuses, this case is being carried by a different check and
        stops being evidence for this one - which is exactly what happened to
        the previous version of this test once the entries were pinned.
        """
        restore = self._unpinned(481)
        real_never = providerwrites._NEVER_ACTIVATE
        providerwrites._NEVER_ACTIVATE = frozenset()
        try:
            self.assertTrue(
                require("481", self.ROW),
                "with the never-activate list emptied this should pass; if it "
                "still refuses, that list is not what refuses 481 here")
        finally:
            providerwrites._NEVER_ACTIVATE = real_never
            self._restore(*restore)

    def test_a_pinned_row_pointing_at_481_is_refused_by_the_pin_instead(self):
        """The pinned path refuses earlier, and says so in different words.

        Asserted rather than left implicit, so a reader knows which guard is
        doing the work on which path.
        """
        real_get = campaigns.get

        def fake_get(campaign_id, rows=None):
            if campaign_id == US:
                return {"campaign_id": US, "bison_campaign_id": 481}
            return real_get(campaign_id, rows)
        campaigns.get = fake_get
        try:
            with self.assertRaises(providerwrites.WriteRefused) as caught:
                require("481", US)
            self.assertIn("pinned", str(caught.exception))
        finally:
            campaigns.get = real_get


class TestTheOtherEmailVerbSharesTheCondition(unittest.TestCase):
    def test_assign_sender_is_scoped_the_same_way(self):
        """`EMAIL_ASSIGN_SENDER` uses the same predicate, so widening one
        widened the other. Asserted rather than assumed."""
        self.assertIs(
            providerwrites.CONDITIONAL[providerwrites.EMAIL_ASSIGN_SENDER],
            providerwrites.CONDITIONAL[providerwrites.EMAIL_ACTIVATE])
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.require_conditional_permission(
                providerwrites.EMAIL_ASSIGN_SENDER, "481", US)

    def test_activate_is_still_conditional_and_not_plain_supported(self):
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.EMAIL_ACTIVATE),
            "EMAIL_ACTIVATE without a condition is a licence to start any "
            "campaign in the workspace")


if __name__ == "__main__":
    unittest.main()


class TestBothGrantTablesMustAgree(unittest.TestCase):
    """Activation needs TWO independent grants and that is the design.

    `providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS` decides which provider
    campaign a canonical row may reach. `executionguard.LIVE_ACTIVATION_GRANTS`
    decides whether an operator has granted the ACT of activating that row at
    all - it is gate 7, the killswitch, and it is the reason the first live
    attempt at campaign 489 was refused five times out of five with both
    tables otherwise satisfied.

    Neither is sufficient alone. These assertions are what stops a future
    widening that edits one file from being enough.
    """

    def test_the_email_rows_are_granted_in_both_tables(self):
        from src import executionguard
        for canonical in (V3, US):
            with self.subTest(canonical=canonical):
                self.assertIn(
                    canonical,
                    [c for _, c in providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS])
                self.assertTrue(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE,
                    {"campaign_id": canonical}))

    def test_a_row_in_neither_table_is_refused_by_both(self):
        from src import executionguard
        for canonical in ("productive-email-control-v2",
                          "productive-email-liheavy-v1", "camp-1"):
            with self.subTest(canonical=canonical):
                self.assertFalse(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE,
                    {"campaign_id": canonical}))
                with self.assertRaises(providerwrites.WriteRefused):
                    require("487", canonical)

    def test_the_email_grant_does_not_leak_onto_linkedin(self):
        """A grant to start an email campaign is not a grant on the other
        channel, and the frozenset per row is what enforces it."""
        from src import executionguard
        for canonical in (V3, US):
            with self.subTest(canonical=canonical):
                self.assertFalse(executionguard.activation_is_granted(
                    executionguard.LINKEDIN_ACTIVATE,
                    {"campaign_id": canonical}))

    def test_an_unnamed_campaign_fails_closed(self):
        from src import executionguard
        for campaign in ({}, {"campaign_id": ""}, {"campaign_id": None}, None):
            with self.subTest(campaign=campaign):
                self.assertFalse(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE, campaign))


class TestTheFourDefeatsGlmFound(unittest.TestCase):
    """GLM adversarial review, 2026-09-18. All four reproduced before they
    were fixed; these are the regressions.

    The first two are the ones that mattered: with the provider id unpinned,
    the binding check compared a caller's number against a number the ROW
    supplied, so a row edited to name a different campaign did not mismatch -
    it moved the target.
    """

    def _with_binding(self, value, canonical=V3):
        """Run against a canonical row bound to `value`, restoring after."""
        real = campaigns.get

        def fake(campaign_id, rows=None, _v=value, _c=canonical):
            if campaign_id == _c:
                return {"campaign_id": _c, "bison_campaign_id": _v}
            return real(campaign_id, rows)
        return real, fake

    def test_a_row_rebound_to_a_client_campaign_is_refused(self):
        """327, 328 and 352 are the CLIENT's live campaigns.

        `_NEVER_ACTIVATE` never caught this: it names 481 and 485, and the
        client's own campaigns are not on it. The pin is what catches it.
        """
        for client_campaign in (327, 328, 352):
            with self.subTest(bound=client_campaign):
                real, fake = self._with_binding(client_campaign)
                campaigns.get = fake
                try:
                    with self.assertRaises(providerwrites.WriteRefused) as e:
                        require(str(client_campaign), V3)
                    self.assertIn("pinned", str(e.exception))
                finally:
                    campaigns.get = real

    def test_one_authorized_row_rebound_to_the_others_campaign(self):
        """Re-binding a row does not move a grant."""
        real, fake = self._with_binding(489, canonical=V3)
        campaigns.get = fake
        try:
            with self.assertRaises(providerwrites.WriteRefused):
                require("489", V3)
        finally:
            campaigns.get = real

    def test_a_non_canonical_spelling_cannot_slip_past_never_activate(self):
        """`481.0` and `"0481"` are not different campaigns from `481`.

        Before `_provider_key`, `str(481.0).strip()` was `"481.0"`, which is
        not in a set holding `"481"`, so the never-activate list missed it
        entirely and the write was PERMITTED. Reproduced 2026-09-18.
        """
        for spelling in (481.0, "0481", " 481", "485.0", 485.0, "0485"):
            with self.subTest(bound=spelling):
                real, fake = self._with_binding(spelling)
                campaigns.get = fake
                try:
                    with self.assertRaises(providerwrites.WriteRefused):
                        require(str(spelling).strip(), V3)
                finally:
                    campaigns.get = real

    def test_provider_key_canonicalises_and_refuses_what_it_cannot(self):
        key = providerwrites._provider_key
        for same in (481, "481", 481.0, "481.0", " 481 ", "0481"):
            with self.subTest(value=same):
                self.assertEqual(key(same), "481")
        for unusable in (None, "", "   ", "not-a-number", 481.5, "481.5",
                         True, False, [], {}):
            with self.subTest(value=unusable):
                self.assertIsNone(key(unusable))

    def test_a_row_that_is_not_a_row_refuses_rather_than_raising(self):
        real = campaigns.get

        def fake(campaign_id, rows=None):
            return ["not", "a", "row"] if campaign_id == V3 else real(
                campaign_id, rows)
        campaigns.get = fake
        try:
            with self.assertRaises(providerwrites.WriteRefused):
                require("487", V3)
        finally:
            campaigns.get = real


class TestTheGrantTableCannotBeTalkedIntoAgreeing(unittest.TestCase):
    def test_a_truthy_non_dict_campaign_refuses_instead_of_crashing(self):
        """`(campaign or {}).get` passed a truthy non-dict through to `.get`
        and raised AttributeError. Only a refusal is safe here; an exception
        moves the decision to whatever `except` sits above the caller."""
        from src import executionguard
        for row in (["x"], "a-string", 5, 3.4, ("a",)):
            with self.subTest(row=row):
                self.assertFalse(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE, row))

    def test_falsy_campaigns_still_refuse(self):
        from src import executionguard
        for row in (None, {}, 0, "", []):
            with self.subTest(row=row):
                self.assertFalse(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE, row))

    def test_a_grant_value_that_is_not_a_set_refuses(self):
        """`in` on a string is SUBSTRING matching, so a note REFUSING a grant
        read as granting it: "bison.activate" in "bison.activate denied
        pending review" is True."""
        from src import executionguard
        saved = dict(executionguard.LIVE_ACTIVATION_GRANTS)
        try:
            for bad in ("bison.activate denied pending review",
                        ["bison.activate"], ("bison.activate",),
                        {"bison.activate": False}, 1):
                with self.subTest(value=bad):
                    executionguard.LIVE_ACTIVATION_GRANTS["camp-x"] = bad
                    self.assertFalse(executionguard.activation_is_granted(
                        providerwrites.EMAIL_ACTIVATE,
                        {"campaign_id": "camp-x"}))
        finally:
            executionguard.LIVE_ACTIVATION_GRANTS.clear()
            executionguard.LIVE_ACTIVATION_GRANTS.update(saved)

    def test_a_real_frozenset_grant_still_works(self):
        from src import executionguard
        for canonical in (V3, US):
            with self.subTest(canonical=canonical):
                self.assertTrue(executionguard.activation_is_granted(
                    providerwrites.EMAIL_ACTIVATE,
                    {"campaign_id": canonical}))
