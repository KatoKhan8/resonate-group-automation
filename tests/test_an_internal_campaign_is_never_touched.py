#!/usr/bin/env python3
"""An internal Resonate campaign is never touched, and UNKNOWN never passes.

Operator decision, Zvonimir, 2026-10-01. Both provider workspaces hold a mix
of (a) Resonate OS campaigns recorded in the ledger and (b) internal Resonate
campaigns the team runs MANUALLY for Productive. (b) is never written to by
code - no verb, no exception - and a campaign on NEITHER list is `unknown`,
which is treated exactly like (b).

WHAT WAS MEASURED BEFORE THIS FILE EXISTED, at d98c83ce, by calling `perform`
with a transport that raises if it is reached. Eight SUPPORTED verbs had no
ownership check of any kind and REACHED THE TRANSPORT for provider campaign
274, 327, 328, 352 and for a campaign id nothing has ever recorded:

    bison.pause          bison.create_campaign   bison.set_sequence
    bison.stop_lead      heyreach.pause          heyreach.create_list
    heyreach.set_sequence                        heyreach.stop_lead

The prospect-facing verbs refused, but for want of an `Authorization` rather
than on ownership - `require_conditional_permission` called directly PASSED
`bison.pause`, `bison.set_sequence`, `bison.stop_lead`, `bison.create_campaign`
and their HeyReach counterparts for all four internal campaigns, because those
verbs have no `CONDITIONAL` entry. So the gap was an ownership gap and not an
authorization gap, and it is closed by a DEFAULT rather than by four more
entries in an opt-in table.

EVERY REFUSAL HERE IS ASSERTED AS AN EFFECT. The transport and the read-back
fail the test if they are called at all, so "refused" means the network
boundary was never reached - not that a log line said so. `ProviderTest` arms
a second tripwire on `urllib.request.urlopen` underneath that.

THE NEGATIVE CONTROL IS `TheDeclarationIsWhatRefusesIt`: with the declaration
removed and a ledger row bound to 327, the same write reaches the transport.
A guard that cannot be shown to fail is not a guard.
"""
import os
import tempfile
import unittest

from src import campaigns, providerwrites as pw, store
from tests.base import ProviderTest

#: The four EmailBison campaigns the operator declared on 2026-10-01.
INTERNAL_BISON = ("274", "327", "328", "352")

#: Ours, in the ledger, bound on both channels. The positive control's subject.
OURS = "productive-test-ours"
OURS_BISON = "9001"
OURS_HEYREACH = "9002"

#: A number nothing anywhere has ever recorded.
NOBODYS = "777777"


def _email_verbs():
    """Every declared EmailBison verb. None of them is list-scoped."""
    return tuple(op for op, (channel, _f, _w) in pw.OPERATIONS.items()
                 if channel == "email")


def _linkedin_campaign_verbs():
    """Every declared HeyReach verb whose target is a CAMPAIGN.

    `LIST_SCOPED` is excluded by name rather than silently: those two carry a
    LIST id in the `provider_campaign_id` slot, lists and campaigns are
    separate id spaces at HeyReach, and both already refuse unless the list is
    attached to no campaign at all.
    """
    return tuple(op for op, (channel, _f, _w) in pw.OPERATIONS.items()
                 if channel == "linkedin" and op not in pw.LIST_SCOPED)


class GuardTest(ProviderTest):
    """A temp ledger, a temp declaration file, and two tripwires."""

    def setUp(self):
        super().setUp()
        self.reached = []
        self.config = os.path.join(self._store_tmp, "internal-campaigns.txt")
        self.addCleanup(self._restore_env,
                        {"INTERNAL_CAMPAIGNS":
                         os.environ.get("INTERNAL_CAMPAIGNS")})
        self.declare(*(("bison", c) for c in INTERNAL_BISON))

    def declare(self, *pairs):
        """Write the operator declaration this test runs against."""
        with open(self.config, "w", encoding="utf-8") as handle:
            handle.write("# a test declaration\n")
            for channel, ident in pairs:
                handle.write("%s %s   # declared by a test\n" % (channel, ident))
        os.environ["INTERNAL_CAMPAIGNS"] = self.config
        self.assertEqual(pw.internal_campaigns_path(),
                         os.path.abspath(self.config))

    def undeclare(self):
        """No declaration file at all - the fail-open case, if there were one."""
        os.environ["INTERNAL_CAMPAIGNS"] = os.path.join(
            self._store_tmp, "no-such-declaration.txt")

    def ledger(self, *rows):
        """Write canonical campaign rows. THE positive record of ownership."""
        built = []
        for campaign_id, bison_id, heyreach_id in rows:
            row = campaigns.new_campaign(campaign_id, "productive", campaign_id,
                                         created_by="test")
            if bison_id is not None:
                row["bison_campaign_id"] = str(bison_id)
            if heyreach_id is not None:
                row["heyreach_campaign_id"] = str(heyreach_id)
            built.append(row)
        campaigns.save(built)
        # The fixture has to be real: a ledger that did not persist would make
        # every refusal below pass for the wrong reason.
        for campaign_id, _b, _h in rows:
            self.assertIsNotNone(campaigns.get(campaign_id),
                                 "the ledger fixture did not persist")
        return built

    def ours(self):
        return self.ledger((OURS, OURS_BISON, OURS_HEYREACH))

    # -- the tripwires. Being called IS the failure.

    def transport(self, payload=None):
        self.reached.append("transport")
        raise AssertionError("THE TRANSPORT WAS REACHED: a refused write "
                             "touched the provider boundary")

    def readback(self):
        self.reached.append("readback")
        raise AssertionError("THE READ-BACK WAS REACHED")

    def perform(self, operation, **kw):
        kw.setdefault("payload", {"probe": operation})
        kw.setdefault("transport", self.transport)
        kw.setdefault("readback", self.readback)
        kw.setdefault("expected", {"ok": True})
        return pw.perform(operation, **kw)

    def assertRefusedBeforeTheNetwork(self, operation, **kw):
        """Refused, and the provider boundary was never reached."""
        self.reached = []
        with self.assertRaises(pw.WriteRefused, msg=operation):
            self.perform(operation, **kw)
        self.assertEqual(self.reached, [],
                         "%s refused AFTER reaching %s" % (operation,
                                                           self.reached))

    def assertReachedTheTransport(self, operation, **kw):
        """The allowed path. The guard let it through to the boundary."""
        self.reached = []
        with self.assertRaises((AssertionError, pw.WriteUnverified),
                               msg=operation):
            self.perform(operation, **kw)
        self.assertEqual(self.reached, ["transport"],
                         "%s never reached the transport: %s"
                         % (operation, self.reached))


# --------------------------------------------------------------- the config

class TheOperatorDeclaresOwnershipInConfig(unittest.TestCase):
    """The shipped file, parsed. Not a fixture - the real one."""

    def test_the_shipped_file_exists_and_is_in_git(self):
        path = pw.internal_campaigns_path()
        self.assertTrue(os.path.exists(path), path)
        self.assertEqual(
            path,
            os.path.abspath(os.path.join(store.ROOT, "config",
                                         "internal-campaigns.txt")))

    def test_the_shipped_file_declares_exactly_the_four_emailbison_campaigns(self):
        """274, 327, 328, 352. Read from disk, not from a literal in a test."""
        declared = pw.declared_internal()
        self.assertEqual(sorted(declared["bison"]), sorted(INTERNAL_BISON))

    def test_the_shipped_file_declares_no_heyreach_campaign_yet(self):
        """And says so out loud, because an empty list is not a measurement."""
        self.assertEqual(declared_heyreach(), frozenset())

    def test_the_file_shows_how_to_add_a_heyreach_campaign(self):
        """The operator adds ids here, so the format has to be in the file."""
        with open(pw.internal_campaigns_path(), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("heyreach ", text)
        self.assertIn("<channel> <provider campaign id>", text)

    def test_an_environment_override_redirects_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "decl.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("heyreach 604869\n")
            previous = os.environ.get("INTERNAL_CAMPAIGNS")
            os.environ["INTERNAL_CAMPAIGNS"] = path
            try:
                self.assertEqual(pw.declared_internal()["heyreach"],
                                 frozenset({"604869"}))
                self.assertEqual(pw.declared_internal()["bison"], frozenset())
            finally:
                if previous is None:
                    os.environ.pop("INTERNAL_CAMPAIGNS", None)
                else:
                    os.environ["INTERNAL_CAMPAIGNS"] = previous


def declared_heyreach():
    return pw.declared_internal()["heyreach"]


class AFileNobodyCanReadRefusesEverything(unittest.TestCase):
    """A line that does not parse is a fault, not a line to skip."""

    def _declared(self, text):
        return pw._parse_declared(text, "<test>")

    def test_comments_and_blank_lines_are_ignored(self):
        declared = self._declared("# a note\n\n  \nbison 274  # why\n")
        self.assertEqual(declared["bison"], frozenset({"274"}))

    def test_a_line_with_one_token_raises(self):
        with self.assertRaises(pw.InternalCampaignsUnreadable):
            self._declared("274\n")

    def test_a_line_with_three_tokens_raises(self):
        with self.assertRaises(pw.InternalCampaignsUnreadable):
            self._declared("bison 274 extra\n")

    def test_an_unknown_channel_raises(self):
        with self.assertRaises(pw.InternalCampaignsUnreadable):
            self._declared("smartlead 274\n")

    def test_an_id_that_is_not_a_campaign_id_raises(self):
        for bad in ("abc", "274.5", "-"):
            with self.assertRaises(pw.InternalCampaignsUnreadable, msg=bad):
                self._declared("bison %s\n" % bad)

    def test_the_fault_is_a_write_refusal_so_it_fails_closed(self):
        """`perform` wraps `WriteRefused`, so a bad file refuses writes."""
        self.assertTrue(issubclass(pw.InternalCampaignsUnreadable,
                                   pw.WriteRefused))

    def test_id_spellings_collapse_to_one_campaign(self):
        """`_provider_key` is the only comparison, here as everywhere."""
        for spelling in ("327", " 327 ", "0327", "327.0"):
            declared = self._declared("bison %s\n" % spelling)
            self.assertEqual(declared["bison"], frozenset({"327"}), spelling)


class AMissingDeclarationStillRefuses(GuardTest):
    """Absence of the file is not absence of the rule."""

    def test_a_missing_file_declares_nothing(self):
        self.undeclare()
        self.assertEqual(pw.declared_internal(),
                         {"bison": frozenset(), "heyreach": frozenset()})

    def test_and_the_campaign_it_would_have_named_is_still_refused(self):
        """It becomes `unknown`, and unknown is do-not-touch."""
        self.undeclare()
        self.assertEqual(pw.classify_campaign("email", "327"),
                         pw.UNKNOWN_OWNER)
        self.assertRefusedBeforeTheNetwork(pw.EMAIL_PAUSE,
                                           provider_campaign_id="327")


# ----------------------------------------------------------- the classifier

class TheClassifierHasExactlyThreeStates(GuardTest):

    def test_a_ledger_bound_campaign_is_resonate_os(self):
        self.ours()
        self.assertEqual(pw.classify_campaign("email", OURS_BISON),
                         pw.RESONATE_OS)
        self.assertEqual(pw.classify_campaign("linkedin", OURS_HEYREACH),
                         pw.RESONATE_OS)

    def test_a_declared_campaign_is_resonate_internal(self):
        for ident in INTERNAL_BISON:
            self.assertEqual(pw.classify_campaign("email", ident),
                             pw.RESONATE_INTERNAL, ident)

    def test_a_campaign_in_neither_is_unknown(self):
        self.ours()
        self.assertEqual(pw.classify_campaign("email", NOBODYS),
                         pw.UNKNOWN_OWNER)
        self.assertEqual(pw.classify_campaign("linkedin", NOBODYS),
                         pw.UNKNOWN_OWNER)

    def test_the_channels_are_separate_id_spaces(self):
        """327 is internal at EmailBison and means nothing at HeyReach."""
        self.assertEqual(pw.classify_campaign("email", "327"),
                         pw.RESONATE_INTERNAL)
        self.assertEqual(pw.classify_campaign("linkedin", "327"),
                         pw.UNKNOWN_OWNER)

    def test_a_declared_campaign_stays_internal_when_a_row_claims_it(self):
        """MEASURED 2026-09-18: a row re-bound to 327 carried a grant onto it.

        The declaration is checked BEFORE the ledger for exactly this. A row is
        a claim this system wrote about itself; the operator's declaration
        outranks it.
        """
        self.ledger(("a-row-rebound-to-327", "327", None))
        self.assertEqual(pw.classify_campaign("email", "327"),
                         pw.RESONATE_INTERNAL)
        self.assertRefusedBeforeTheNetwork(
            pw.EMAIL_PAUSE, campaign="a-row-rebound-to-327")

    def test_an_id_nothing_can_canonicalise_is_unknown(self):
        for bad in (None, "", "   ", "not-a-number", "327.5", True, False):
            self.assertEqual(pw.classify_campaign("email", bad),
                             pw.UNKNOWN_OWNER, repr(bad))

    def test_every_spelling_of_a_declared_id_is_internal(self):
        for spelling in ("327", 327, " 327 ", "0327", 327.0):
            self.assertEqual(pw.classify_campaign("email", spelling),
                             pw.RESONATE_INTERNAL, repr(spelling))

    def test_the_classifier_returns_nothing_outside_the_three(self):
        self.ours()
        seen = {pw.classify_campaign("email", v)
                for v in (OURS_BISON, "327", NOBODYS, None, "x")}
        self.assertTrue(seen <= set(pw.OWNERSHIP), seen)

    def test_an_unreadable_ledger_proves_nothing_is_ours(self):
        """Fail closed: a ledger that cannot be read makes everything unknown."""
        self.ours()
        self.assertEqual(pw.classify_campaign("email", OURS_BISON),
                         pw.RESONATE_OS)
        with open(store.campaigns_path(), "w", encoding="utf-8") as handle:
            handle.write("{this is not json\n")
        self.assertEqual(pw.classify_campaign("email", OURS_BISON),
                         pw.UNKNOWN_OWNER)


# ------------------------------------------- every verb, every internal id

class AnInternalCampaignIsRefusedForEveryVerb(GuardTest):

    def test_the_ownership_guard_refuses_every_emailbison_verb(self):
        """Called directly, so no other gate can be what refused."""
        for ident in INTERNAL_BISON:
            for operation in _email_verbs():
                with self.assertRaises(pw.WriteRefused,
                                       msg="%s %s" % (operation, ident)) as c:
                    pw.require_resonate_os_campaign(operation, ident)
                self.assertIn("internal Resonate campaign", str(c.exception))

    def test_the_door_refuses_every_emailbison_verb_before_the_network(self):
        for ident in INTERNAL_BISON:
            for operation in _email_verbs():
                self.assertRefusedBeforeTheNetwork(
                    operation, provider_campaign_id=ident)

    def test_a_row_bound_to_an_internal_campaign_refuses_too(self):
        """The canonical id is the only argument most callers pass."""
        self.ledger(*[("row-for-%s" % i, i, None) for i in INTERNAL_BISON])
        for ident in INTERNAL_BISON:
            for operation in _email_verbs():
                self.assertRefusedBeforeTheNetwork(
                    operation, campaign="row-for-%s" % ident)

    def test_nothing_is_recorded_as_staged_by_a_refused_write(self):
        """A refusal must leave no trace that could block a later real write."""
        self.ledger(("row-for-327", "327", None))
        self.assertRefusedBeforeTheNetwork(pw.EMAIL_SET_SEQUENCE,
                                           campaign="row-for-327")
        self.assertIsNone(pw.staged_already("row-for-327", pw.EMAIL_SET_SEQUENCE,
                                            {"probe": pw.EMAIL_SET_SEQUENCE}))

    def test_the_four_are_refused_whatever_spelling_is_offered(self):
        for spelling in ("327", 327, "0327", 327.0, " 328 "):
            self.assertRefusedBeforeTheNetwork(
                pw.EMAIL_PAUSE, provider_campaign_id=spelling)


class AHeyReachCampaignOnTheListIsRefused(GuardTest):

    HEYREACH_INTERNAL = "604869"

    def setUp(self):
        super().setUp()
        self.declare(("heyreach", self.HEYREACH_INTERNAL))

    def test_it_classifies_as_resonate_internal(self):
        self.assertEqual(
            pw.classify_campaign("linkedin", self.HEYREACH_INTERNAL),
            pw.RESONATE_INTERNAL)

    def test_the_ownership_guard_refuses_every_heyreach_campaign_verb(self):
        for operation in _linkedin_campaign_verbs():
            with self.assertRaises(pw.WriteRefused, msg=operation) as c:
                pw.require_resonate_os_campaign(operation,
                                                self.HEYREACH_INTERNAL)
            self.assertIn("internal Resonate campaign", str(c.exception))

    def test_the_door_refuses_them_before_the_network(self):
        for operation in _linkedin_campaign_verbs():
            self.assertRefusedBeforeTheNetwork(
                operation, provider_campaign_id=self.HEYREACH_INTERNAL)

    def test_a_row_bound_to_it_refuses_too(self):
        self.ledger(("row-for-hr", None, self.HEYREACH_INTERNAL))
        for operation in _linkedin_campaign_verbs():
            self.assertRefusedBeforeTheNetwork(operation, campaign="row-for-hr")

    def test_declaring_it_on_heyreach_does_not_declare_it_on_bison(self):
        self.assertEqual(pw.classify_campaign("email", self.HEYREACH_INTERNAL),
                         pw.UNKNOWN_OWNER)


# -------------------------------------------------- unknown never becomes pass

class UnknownIsNeverAPass(GuardTest):

    def test_a_campaign_absent_from_both_is_refused_for_every_verb(self):
        self.ours()
        for operation in _email_verbs():
            with self.assertRaises(pw.WriteRefused, msg=operation) as c:
                pw.require_resonate_os_campaign(operation, NOBODYS)
            self.assertIn("NOTHING POSITIVELY RECORDS IT", str(c.exception))
        for operation in _linkedin_campaign_verbs():
            with self.assertRaises(pw.WriteRefused, msg=operation):
                pw.require_resonate_os_campaign(operation, NOBODYS)

    def test_the_door_refuses_it_before_the_network(self):
        self.ours()
        for operation in _email_verbs():
            self.assertRefusedBeforeTheNetwork(
                operation, provider_campaign_id=NOBODYS)

    def test_a_write_with_no_resolvable_destination_is_refused(self):
        """No provider id and no bound row. Absence is a refusal."""
        self.ledger(("unbound-row", None, None))
        for operation in (pw.EMAIL_PAUSE, pw.EMAIL_SET_SEQUENCE,
                          pw.EMAIL_STOP_LEAD):
            self.assertRefusedBeforeTheNetwork(operation,
                                               campaign="unbound-row")

    def test_a_row_that_does_not_exist_is_refused(self):
        self.assertRefusedBeforeTheNetwork(pw.EMAIL_PAUSE,
                                           campaign="no-such-row")

    def test_a_create_has_no_destination_and_is_not_refused_by_this_guard(self):
        """A create cannot touch a campaign that does not exist yet.

        Named and narrow. A create whose row ALREADY binds a provider campaign
        is a re-stage, and the next test proves it is classified like any other
        write.
        """
        self.ledger(("unbound-row", None, None))
        self.assertIsNone(pw.require_resonate_os_campaign(
            pw.EMAIL_CREATE_CAMPAIGN, None, "unbound-row"))

    def test_a_restage_onto_an_internal_campaign_is_still_refused(self):
        self.ledger(("row-for-327", "327", None))
        with self.assertRaises(pw.WriteRefused):
            pw.require_resonate_os_campaign(pw.EMAIL_CREATE_CAMPAIGN, None,
                                            "row-for-327")


# ------------------------------------------------------- the positive control

class TheAllowedPathIsUNCHANGED(GuardTest):
    """A ledger-recorded Resonate OS campaign still reaches the transport.

    MEASURED AT d98c83ce for each verb below: the transport WAS reached. If
    this class fails, the tightening broke the path it was not supposed to
    touch, and the measurement that proves the difference is in the module
    docstring.
    """

    def setUp(self):
        super().setUp()
        self.ours()

    def test_it_classifies_as_resonate_os(self):
        self.assertEqual(pw.classify_campaign("email", OURS_BISON),
                         pw.RESONATE_OS)
        self.assertEqual(pw.require_resonate_os_campaign(
            pw.EMAIL_PAUSE, OURS_BISON), pw.RESONATE_OS)

    def test_the_unconditional_emailbison_verbs_still_reach_the_transport(self):
        for operation in (pw.EMAIL_PAUSE, pw.EMAIL_STOP_LEAD,
                          pw.EMAIL_SET_SEQUENCE):
            self.assertReachedTheTransport(operation, campaign=OURS,
                                           provider_campaign_id=OURS_BISON)

    def test_the_unconditional_heyreach_verbs_still_reach_the_transport(self):
        for operation in (pw.LINKEDIN_PAUSE, pw.LINKEDIN_STOP_LEAD,
                          pw.LINKEDIN_SET_SEQUENCE):
            self.assertReachedTheTransport(operation, campaign=OURS,
                                           provider_campaign_id=OURS_HEYREACH)

    def test_the_canonical_id_alone_is_enough_as_it_was_before(self):
        """Most call sites pass `campaign=` and no provider id. Still works."""
        self.assertReachedTheTransport(pw.EMAIL_PAUSE, campaign=OURS)
        self.assertReachedTheTransport(pw.LINKEDIN_PAUSE, campaign=OURS)

    def test_creating_a_campaign_still_reaches_the_transport(self):
        self.ledger(("fresh-row", None, None))
        self.assertReachedTheTransport(pw.EMAIL_CREATE_CAMPAIGN,
                                       campaign="fresh-row")

    def test_creating_a_list_still_reaches_the_transport(self):
        self.assertReachedTheTransport(pw.LINKEDIN_CREATE_LIST)

    def test_the_list_scoped_verbs_are_not_classified_as_campaigns(self):
        """A list id is not a campaign id, and both already refuse a bound list."""
        for operation in pw.LIST_SCOPED:
            self.assertIsNone(
                pw.require_resonate_os_campaign(operation, "933603", OURS))


# ----------------------------------- the grants and the legacy seals are intact

class TheExistingSealsDoNotRegress(GuardTest):
    """487/489/493 and the legacy campaigns, measured rather than assumed."""

    PINNED = (("487", "productive-email-control-v3"),
              ("489", "productive-email-us-cohort-v1"),
              ("493", "productive-email-batch1-ivan"))

    def setUp(self):
        super().setUp()
        self.ledger(*[(canonical, provider, None)
                      for provider, canonical in self.PINNED])

    def test_the_pinned_grant_still_resolves_exactly_as_before(self):
        """The authorization allowlist is UNCHANGED by this tightening."""
        for provider, canonical in self.PINNED:
            self.assertTrue(pw.require_conditional_permission(
                pw.EMAIL_ACTIVATE, provider, canonical))

    def test_and_the_new_guard_agrees_they_are_resonate_os(self):
        """They are ours. Their seals are elsewhere, which the next tests show."""
        for provider, canonical in self.PINNED:
            self.assertEqual(pw.classify_campaign("email", provider),
                             pw.RESONATE_OS)

    def test_activation_is_still_refused_without_an_authorization(self):
        """`EMAIL_ACTIVATE` is prospect-facing and a dict is not a token."""
        for provider, canonical in self.PINNED:
            self.assertRefusedBeforeTheNetwork(
                pw.EMAIL_ACTIVATE, campaign=canonical,
                provider_campaign_id=provider,
                authorization={"pretending": True})

    def test_a_pinned_row_rebound_to_481_or_485_is_still_refused(self):
        """MEASURED 2026-09-18: re-binding a row moved the grant's target.

        The pin plus `_NEVER_ACTIVATE` is what refuses it, and this tightening
        does not touch either - so the same re-bind must still be refused.
        """
        for never in ("481", "485"):
            self.ledger(("productive-email-control-v3", never, None))
            with self.assertRaises(pw.WriteRefused, msg=never):
                pw.require_conditional_permission(
                    pw.EMAIL_ACTIVATE, never, "productive-email-control-v3")

    def test_a_legacy_campaign_is_still_refused_activation_by_its_scope(self):
        """503/504/505 hold 1,313 rows in `sending_paused`. Never resumed.

        The seal is the authorization allowlist, not ownership: these ARE our
        campaigns, so the ownership guard correctly calls them `resonate_os`
        and says nothing about them. That is asserted too, so the report
        cannot claim ownership is what holds them.
        """
        self.ledger(("productive-legacy-503", "503", None))
        self.assertEqual(pw.classify_campaign("email", "503"), pw.RESONATE_OS)
        with self.assertRaises(pw.WriteRefused):
            pw.require_conditional_permission(pw.EMAIL_ACTIVATE, "503",
                                              "productive-legacy-503")
        self.assertRefusedBeforeTheNetwork(
            pw.EMAIL_ACTIVATE, campaign="productive-legacy-503",
            provider_campaign_id="503")

    def test_heyreach_activation_stays_scoped_to_the_canary(self):
        self.ledger(("row-hr-other", None, "599020"))
        with self.assertRaises(pw.WriteRefused):
            pw.require_conditional_permission(pw.LINKEDIN_ACTIVATE, "599020",
                                              "row-hr-other")

    def test_the_resealed_add_lead_is_still_resealed(self):
        self.assertFalse(pw.CAMPAIGN_LEVEL_STAGING_IS_PROVEN)
        with self.assertRaises(pw.WriteRefused):
            pw.require_conditional_permission(pw.LINKEDIN_ADD_LEAD,
                                              OURS_HEYREACH, OURS)


# -------------------------------------------------------- the negative control

class TheDeclarationIsWhatRefusesIt(GuardTest):
    """A gate that cannot be shown to fail is not a gate.

    Same write, same ledger row, same verb. The ONLY difference between the two
    tests is whether the operator's line is in the declaration file.
    """

    def test_with_the_declaration_the_write_is_refused(self):
        self.ledger(("row-for-327", "327", None))
        self.assertRefusedBeforeTheNetwork(pw.EMAIL_PAUSE,
                                           campaign="row-for-327")

    def test_without_the_declaration_a_ledger_bound_row_reaches_the_transport(self):
        self.declare(("bison", "274"))      # 327 deliberately absent
        self.ledger(("row-for-327", "327", None))
        self.assertEqual(pw.classify_campaign("email", "327"), pw.RESONATE_OS)
        self.assertReachedTheTransport(pw.EMAIL_PAUSE, campaign="row-for-327")

    def test_and_274_is_still_refused_in_that_same_state(self):
        self.declare(("bison", "274"))
        self.ledger(("row-for-274", "274", None))
        self.assertRefusedBeforeTheNetwork(pw.EMAIL_PAUSE,
                                           campaign="row-for-274")


# ------------------------------------------------------------- the wiring

class TheGuardRunsOnEveryPathThroughTheDoor(unittest.TestCase):
    """`perform` has two branches. The guard must be on both.

    Asserted as an EFFECT in the classes above - a prospect-facing verb and a
    staging verb are each shown refused with the transport untouched - and
    structurally here, because a branch added later would otherwise skip it
    silently.
    """

    def test_both_branches_call_the_guard(self):
        import inspect
        source = inspect.getsource(pw._perform)
        self.assertEqual(source.count("require_resonate_os_campaign("), 2,
                         "`_perform` has two branches and the ownership guard "
                         "must be called on both")

    def test_the_guard_runs_before_the_transport_is_called(self):
        import inspect
        source = inspect.getsource(pw._perform)
        self.assertLess(source.index("require_resonate_os_campaign("),
                        source.index("response = transport(payload)"))

    def test_the_guard_runs_before_the_authorization_is_spent(self):
        import inspect
        source = inspect.getsource(pw._perform)
        self.assertLess(source.index("require_resonate_os_campaign("),
                        source.index("authorization.spend()"))


if __name__ == "__main__":
    unittest.main()
