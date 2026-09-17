"""A `stopped` membership on a campaign of ours that never sent anything.

MEASURED 2026-09-16 ON THE LIVE PRODUCTIVE WORKSPACE (id 10), and this is the
whole defect in four numbers:

    campaign 485   status draft   emails_sent 0   total_leads_contacted 0
                   opened 0  unique_opens 0  replied 0  unique_replies 0
                   bounced 0  unsubscribed 0  interested 0
    membership(485)  ->  `stopped` for 10 of 10 leads

The provider stops a campaign's memberships when it archives a campaign with
no sending account attached. `stopped` is in `collision.SUSPECT_STATUSES`, so
`account_policy` answered HOLD for every one of those ten accounts - "a
campaign at this account ended early and the status does not say whether we
stopped it, they unsubscribed, or the provider stopped it on a reply" - and
`bisonfactory._refuse_colliding_leads` refused the entire READY cohort with
`FactoryRefused: 10 contact(s) collided with the client's own estate`.

It was not the client's estate. It was ours, and it had sent nobody anything.

WHAT THESE TESTS ARE ACTUALLY DEFENDING, because the fix is one step away from
being much worse than the defect. "This campaign is ours" must never be enough
to clear a row - a campaign of ours that HAS sent is exactly as much of a
collision as one of the client's. So every test below that allows an exclusion
has a twin that forbids it, and the twins are the point:

    the campaign sent one email          -> not an artifact
    the counter is missing               -> not an artifact
    the campaign is running              -> not an artifact
    the queue holds a sent row           -> not an artifact
    our own action ledger has a row      -> not an artifact
    nothing local claims the campaign    -> not an artifact
    the provider's name disowns it       -> not an artifact
    the membership contradicts the
      campaign it belongs to             -> not an artifact

And the four verdicts that must not move at all: an unknown stop reason, an
unsubscribe, a reply, and thirteen real emails to a colleague.
"""
import json
import os
import tempfile
import unittest

from src import collision, providers
from src.providers import bison

WS = 10          # the workspace every read in this file is pinned to

# The same placeholder the sibling collision suite installs, and for the same
# reason: `tests/__init__.py` clears every credential at package import, so a
# read that builds provider headers raises `MissingKey` before it reaches the
# behaviour under test.
PLACEHOLDER = "test-key-not-real"
_saved = {}


def setUpModule():
    for name in ("BISON_KEY", "BISON_BASE"):
        _saved[name] = os.environ.get(name)
    os.environ["BISON_KEY"] = PLACEHOLDER
    os.environ.setdefault("BISON_BASE", "https://bison.invalid")


def tearDownModule():
    for name, value in _saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


# --------------------------------------------------------------- fixtures

OURS = 485                  # a campaign this system built
THEIRS = 352                # one of the client's own, from before we existed
CLIENT = "productive"
CANONICAL = "productive-email-control-v2"

#: What a campaign of ours that has never sent anything reads like. Copied
#: field for field off campaign 485 on 2026-09-16.
SILENT = {
    "id": OURS,
    "name": f"RESONATE - PRODUCTIVE - EMAIL - CONTROL [{CLIENT}/{CANONICAL}]",
    "status": "draft",
    "emails_sent": 0, "total_leads_contacted": 0,
    "opened": 0, "unique_opens": 0,
    "replied": 0, "unique_replies": 0,
    "bounced": 0, "unsubscribed": 0, "interested": 0,
    "total_leads": 10,
}


def campaign_row(**overrides):
    return dict(SILENT, **overrides)


def membership(campaign_id, status, sent=0, replies=0, opens=0,
               interested=False):
    return {"campaign_id": campaign_id, "status": status, "emails_sent": sent,
            "replies": replies, "opens": opens, "interested": interested}


def lead(email, sent=0, memberships=(), lead_status="unverified"):
    return {
        "id": abs(hash(email)) % 100000,
        "email": email,
        "status": lead_status,
        "overall_stats": {"emails_sent": sent, "replies": 0, "opens": 0},
        "lead_campaign_data": list(memberships),
        "created_at": "2026-04-08T18:33:00.000000Z",
    }


class Wire:
    """One estate, one campaign table, one scheduled-email queue.

    Deliberately routes on the real URL shapes rather than on a flag, so a
    test cannot pass by never reaching the route it is about. `reads` records
    which campaign rows were fetched, which is how the "an estate that is not
    ours costs no provider read" test is written.
    """

    def __init__(self, rows, campaigns=None, queues=None):
        self.rows = rows
        self.campaigns = dict(campaigns or {})
        self.queues = dict(queues or {})
        self.reads = []

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        if bison.USERS_PATH in url:
            return 200, {"data": {"workspace": {"id": WS, "name": "TESTWS"}}}
        if "/scheduled-emails" in url:
            which = int(url.split("/campaigns/")[1].split("/")[0])
            return 200, {"data": self.queues.get(which, []),
                         "meta": {"current_page": 1, "last_page": 1,
                                  "per_page": 15,
                                  "total": len(self.queues.get(which, []))}}
        if "/campaigns/" in url:
            which = int(url.split("/campaigns/")[1].split("?")[0].split("/")[0])
            self.reads.append(which)
            if which not in self.campaigns:
                return 404, {"message": "no such campaign"}
            return 200, {"data": self.campaigns[which]}
        return 200, {"data": self.rows,
                     "meta": {"current_page": 1, "last_page": 1,
                              "per_page": 15, "total": len(self.rows)}}


class StagingTest(unittest.TestCase):
    """Local state pointed at temp files, and the per-process evidence memo
    cleared before AND after every test.

    The memo is what makes the exclusion cost one provider read per campaign
    per run instead of one per account. A test that inherited another test's
    memo would prove the memo rather than the rule, so it is cleared on both
    sides of every case.
    """

    bindings = ((OURS, CLIENT, CANONICAL),)
    ledger = ()

    def setUp(self):
        collision.forget_staging_evidence()
        self.addCleanup(collision.forget_staging_evidence)
        tmp = tempfile.mkdtemp()
        self.campaigns_path = os.path.join(tmp, "campaigns.jsonl")
        self.ledger_path = os.path.join(tmp, "action-ledger.jsonl")
        self.write(self.campaigns_path, [
            {"campaign_id": canonical, "client": client,
             "bison_campaign_id": provider_id, "name": "x"}
            for provider_id, client, canonical in self.bindings])
        self.write(self.ledger_path, list(self.ledger))
        for name, value in (("CAMPAIGNS", self.campaigns_path),
                            ("ACTION_LEDGER", self.ledger_path)):
            before = os.environ.get(name)
            os.environ[name] = value
            self.addCleanup(self.restore, name, before)

    @staticmethod
    def restore(name, before):
        if before is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = before

    @staticmethod
    def write(path, rows):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def wire(self, rows, campaigns=None, queues=None):
        w = Wire(rows, campaigns if campaigns is not None
                 else {OURS: campaign_row()}, queues)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        return w

    def account(self, rows, campaigns=None, queues=None):
        self.wire(rows, campaigns, queues)
        return collision.check_account("example.test", expect_workspace=WS)

    def policy(self, rows, campaigns=None, queues=None):
        return collision.account_policy(self.account(rows, campaigns, queues))


# ------------------------------------------------ the verdicts that must hold

class TheVerdictsThatMustNotMove(StagingTest):
    """Four HOLDs and a STOP that this change is not allowed to touch. Each
    one is the reason the account gate exists at all."""

    def test_a_stopped_campaign_with_an_unknown_reason_still_holds(self):
        """The defect's own shape, on a campaign that is NOT ours. The
        provider does not record who ended it, so nobody may infer that we
        did."""
        found = self.policy([lead("a@example.test", sent=8,
                                  memberships=[membership(THEIRS, "stopped",
                                                          sent=8)])])
        self.assertEqual(found[0], collision.HOLD)
        self.assertIn("ended early", found[1])
        self.assertIn("stopped", found[1])

    def test_an_unsubscribe_still_holds(self):
        """An unsubscribe reaches this module as a `stopped` membership on a
        campaign that HAS sent. The campaign counter says so - `unsubscribed`
        is 1 - and a campaign with an unsubscribe can never be an artifact."""
        found = self.policy(
            [lead("a@example.test", sent=4,
                  memberships=[membership(OURS, "stopped", sent=4)])],
            campaigns={OURS: campaign_row(emails_sent=4,
                                          total_leads_contacted=1,
                                          unsubscribed=1)})
        self.assertEqual(found[0], collision.HOLD)
        self.assertIn("unsubscribed", found[1])

    def test_a_reply_still_stops_the_account(self):
        """Even on a campaign of ours, and even when the reply COUNTER is
        zero: `status: replied` is the membership's own verdict and it wins."""
        found = self.policy(
            [lead("a@example.test", sent=3,
                  memberships=[membership(OURS, "replied", sent=3)])],
            campaigns={OURS: campaign_row(emails_sent=3,
                                          total_leads_contacted=1, replied=1)})
        self.assertEqual(found[0], collision.STOP)
        self.assertIn("answered", found[1])

    def test_a_colleague_mid_sequence_still_stops_the_account(self):
        found = self.policy([lead("a@example.test", sent=5,
                                  memberships=[membership(THEIRS,
                                                          "in_sequence",
                                                          sent=5)])])
        self.assertEqual(found[0], collision.STOP)

    def test_an_unread_status_still_holds(self):
        found = self.policy([lead("a@example.test", sent=4,
                                  memberships=[membership(THEIRS, "active",
                                                          sent=4)])])
        self.assertEqual(found[0], collision.HOLD)
        self.assertIn("active", found[1])

    def test_a_bounce_still_holds_even_on_a_campaign_of_ours(self):
        """A bounce is a fact about the ADDRESS. Whoever staged the lead that
        discovered it does not get to retire it."""
        found = self.policy(
            [lead("a@example.test", memberships=[membership(OURS, "bounced")],
                  lead_status="bounced")])
        self.assertEqual(found[0], collision.HOLD)
        self.assertIn("bounced", found[1])


# --------------------------------------------- the thirteen-email colleague

class TheThirteenEmailAccountIsNeverCleared(StagingTest):
    """`ogpartner.dk` on the live estate: the contact we picked had nothing,
    and a COLLEAGUE (lead 169009, created 2026-04-23) had thirteen emails - 8
    in campaign 328 and 5 in 352, both `sequence_finished`. TASK-177 passed
    the record with "0 prior email(s)" because it asked `check_address`, a
    person-level question, and never `check_account`.

    That history has to survive this change untouched. These tests are written
    against the account-level answer for that exact shape.
    """

    #: The colleague's two finished campaigns, and the row for the contact we
    #: picked, who is in our silent staging campaign and nothing else.
    def estate(self):
        return [
            lead("colleague@example.test", sent=13, memberships=[
                membership(328, "sequence_finished", sent=8),
                membership(THEIRS, "sequence_finished", sent=5)]),
            lead("picked@example.test", sent=0, memberships=[
                membership(OURS, "stopped")]),
        ]

    def test_the_thirteen_emails_survive_the_exclusion(self):
        found = self.account(self.estate())
        self.assertEqual(found["emails_sent_total"], 13)
        self.assertEqual(found["verdict"], collision.TOUCHED)

    def test_the_account_is_never_reported_as_having_no_prior_contact(self):
        """The sentence TASK-177 produced, and the one that must not come
        back."""
        _decision, why = collision.account_policy(self.account(self.estate()))
        self.assertNotIn("no prior contact", why)
        self.assertIn("13 email(s)", why)

    def test_the_colleagues_campaigns_are_still_on_the_answer(self):
        found = self.account(self.estate())
        colleague = [p for p in found["people"]
                     if p["email"].startswith("colleague")][0]
        self.assertEqual(sorted(c["campaign_id"] for c in colleague["campaigns"]),
                         [328, THEIRS])
        self.assertEqual(colleague.get("our_staging_excluded"), None)

    def test_a_campaign_with_any_send_is_never_an_artifact_even_when_ours(self):
        """Ownership is not evidence, and this is the case that proves it: the
        same thirteen emails, on a campaign carrying OUR binding on both
        sides. Thirteen sends is thirteen sends."""
        self.wire([], campaigns={OURS: campaign_row(emails_sent=13,
                                                    total_leads_contacted=2)})
        evidence = collision.staging_artifact_evidence(OURS)
        self.assertFalse(evidence["proven"])
        self.assertTrue(evidence["arms"]["ours"][0], "ownership did hold")
        self.assertIn("has touched somebody", evidence["why"])

    def test_the_same_account_holds_when_its_own_history_ended_early(self):
        """The colleague's history read `stopped` instead of finished. Not
        ours, so nothing is excluded, so it is still a HOLD."""
        estate = [lead("colleague@example.test", sent=13, memberships=[
            membership(328, "sequence_finished", sent=8),
            membership(THEIRS, "stopped", sent=5)])]
        self.assertEqual(self.policy(estate)[0], collision.HOLD)


# -------------------------------------------------- the exclusion itself

class OurOwnSilentStagingIsExcluded(StagingTest):
    """The other half. A guard that held on everything would be deleted."""

    def cohort(self):
        return [lead("picked@example.test", memberships=[
            membership(OURS, "stopped")])]

    def test_the_account_allows(self):
        decision, _why = self.policy(self.cohort())
        self.assertEqual(decision, collision.ALLOW)

    def test_the_account_reads_clear(self):
        self.assertEqual(self.account(self.cohort())["verdict"],
                         collision.CLEAR)

    def test_the_exclusion_is_reported_rather_than_silent(self):
        found = self.account(self.cohort())
        self.assertEqual([e["campaign_id"]
                          for e in found["our_staging_excluded"]], [OURS])
        self.assertEqual(found["our_staging_excluded"][0]["status"], "stopped")

    def test_the_operator_sentence_names_what_was_taken_out(self):
        _decision, why = collision.account_policy(self.account(self.cohort()))
        self.assertIn(str(OURS), why)
        self.assertIn("sent nothing", why)

    def test_a_sending_paused_row_of_ours_is_excluded_too(self):
        """The other status our staging leaves - campaign 481 on the live
        estate reads `sending_paused` for the same people 485 reads
        `stopped`."""
        found = self.account([lead("picked@example.test", memberships=[
            membership(OURS, "sending_paused")])])
        self.assertEqual(len(found["our_staging_excluded"]), 1)

    def test_the_evidence_names_all_four_arms(self):
        self.wire([])
        evidence = collision.staging_artifact_evidence(OURS)
        self.assertTrue(evidence["proven"])
        self.assertEqual(sorted(evidence["arms"]),
                         ["ledger", "ours", "queue", "zero_send"])


# ------------------------------------------------ every way it must refuse

class OwnershipAloneProvesNothing(StagingTest):
    """Eight refusals. Each one is a way the exclusion could have fired on
    something it had no right to."""

    def refuses(self, campaigns=None, queues=None, rows=None):
        self.wire(rows if rows is not None else [], campaigns, queues)
        return collision.staging_artifact_evidence(OURS)

    def test_a_campaign_that_sent_one_email_is_not_an_artifact(self):
        found = self.refuses({OURS: campaign_row(emails_sent=1,
                                                 total_leads_contacted=1)})
        self.assertFalse(found["proven"])
        self.assertIn("emails_sent=1", found["why"])

    def test_a_missing_counter_is_not_a_zero_one(self):
        """The fail-closed rule. A provider that stops returning a counter -
        or a proxy that trims one - must not read as silence."""
        row = campaign_row()
        row.pop("unsubscribed")
        found = self.refuses({OURS: row})
        self.assertFalse(found["proven"])
        self.assertIn("unsubscribed", found["why"])
        self.assertIn("unread counter is not a zero one", found["why"])

    def test_a_counter_that_is_not_an_integer_is_not_a_zero_one(self):
        found = self.refuses({OURS: campaign_row(emails_sent="0")})
        self.assertFalse(found["proven"])
        self.assertIn("emails_sent", found["why"])

    def test_a_running_campaign_at_zero_sent_is_not_an_artifact(self):
        """It started thirty seconds ago and every counter is still zero.
        This is the arm that makes the counters safe to trust."""
        found = self.refuses({OURS: campaign_row(status="active")})
        self.assertFalse(found["proven"])
        self.assertIn("not a state this system has verified", found["why"])

    def test_a_status_word_nobody_here_has_read_is_not_an_artifact(self):
        found = self.refuses({OURS: campaign_row(status="warming")})
        self.assertFalse(found["proven"])
        self.assertIn("warming", found["why"])

    def test_a_queue_row_that_was_sent_is_not_an_artifact(self):
        """Independent of the counters. Campaign 451 on the live estate sent
        exactly one email and carries exactly one queue row reading `sent`."""
        found = self.refuses(queues={OURS: [{"status": "sent",
                                             "sent_at": "2026-09-14T00:00:00Z"}]})
        self.assertFalse(found["proven"])
        self.assertIn("already sent", found["why"])

    def test_a_queue_word_nobody_here_has_read_is_not_an_artifact(self):
        found = self.refuses(queues={OURS: [{"status": "delivering"}]})
        self.assertFalse(found["proven"])
        self.assertIn("delivering", found["why"])

    def test_our_own_action_ledger_disqualifies_it(self):
        """The second witness, and the one a counter-only check would miss: a
        send that timed out mid-flight leaves a reservation here even when
        nothing at the provider ever moved."""
        self.ledger = ({"key": "k", "state": "attempted",
                        "campaign_id": CANONICAL},)
        self.setUp()
        found = self.refuses()
        self.assertFalse(found["proven"])
        self.assertIn("action ledger", found["why"])

    def test_an_unresolved_ledger_row_disqualifies_it(self):
        """`unresolved` exists precisely to say nobody knows. Nobody-knows is
        not nobody-was-contacted."""
        self.ledger = ({"key": "k", "state": "unresolved",
                        "campaign_id": CANONICAL},)
        self.setUp()
        self.assertFalse(self.refuses()["proven"])

    def test_a_refused_ledger_row_does_not_disqualify_it(self):
        """The twin. `failed` means the provider refused before acting, which
        is positive evidence that nobody was reached."""
        self.ledger = ({"key": "k", "state": "failed",
                        "campaign_id": CANONICAL},)
        self.setUp()
        self.assertTrue(self.refuses()["proven"])

    def test_a_campaign_nothing_local_claims_is_not_an_artifact(self):
        self.bindings = ()
        self.setUp()
        found = self.refuses()
        self.assertFalse(found["proven"])
        self.assertIn("no canonical campaign row claims", found["why"])

    def test_a_campaign_two_local_rows_claim_is_not_an_artifact(self):
        """An ambiguous claim of ownership is not a claim."""
        self.bindings = ((OURS, CLIENT, CANONICAL),
                         (OURS, CLIENT, "some-other-campaign"))
        self.setUp()
        self.assertFalse(self.refuses()["proven"])

    def test_a_provider_name_without_our_binding_is_not_an_artifact(self):
        """Campaign 451 on the live estate is bound in `campaigns.jsonl` and
        its provider name carries no binding suffix at all - built before the
        name became the anchor. Local state alone does not settle ownership."""
        found = self.refuses({OURS: campaign_row(
            name="RESONATE - PRODUCTIVE CANARY - Hot Soup Group")})
        self.assertFalse(found["proven"])
        self.assertIn("does not carry this system's binding", found["why"])

    def test_a_provider_name_claiming_another_client_is_not_an_artifact(self):
        found = self.refuses({OURS: campaign_row(
            name=f"x [someone-else/{CANONICAL}]")})
        self.assertFalse(found["proven"])

    def test_a_campaign_the_provider_cannot_answer_for_is_not_an_artifact(self):
        found = self.refuses({})            # 404 from the campaign route
        self.assertFalse(found["proven"])
        self.assertIn("could not be read", found["why"])


class TheMembershipRowHasToAgreeWithItsCampaign(StagingTest):
    """The campaign-level proof is necessary and not sufficient. A row that
    contradicts the campaign it belongs to is a row this system has misread,
    and a misreading is never resolved in favour of sending."""

    def test_a_membership_claiming_a_send_is_kept(self):
        found = self.account([lead("a@example.test", sent=2, memberships=[
            membership(OURS, "stopped", sent=2)])])
        self.assertEqual(found["our_staging_excluded"], [])
        self.assertEqual(collision.account_policy(found)[0], collision.HOLD)

    def test_a_membership_claiming_a_reply_is_kept(self):
        found = self.account([lead("a@example.test", memberships=[
            membership(OURS, "stopped", replies=1)])])
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_membership_claiming_an_open_is_kept(self):
        found = self.account([lead("a@example.test", memberships=[
            membership(OURS, "stopped", opens=1)])])
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_membership_marked_interested_is_kept(self):
        found = self.account([lead("a@example.test", memberships=[
            membership(OURS, "stopped", interested=True)])])
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_membership_with_an_unreadable_counter_is_kept(self):
        found = self.account([lead("a@example.test", memberships=[
            {"campaign_id": OURS, "status": "stopped", "emails_sent": None,
             "replies": 0, "opens": 0, "interested": False}])])
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_bounced_membership_of_ours_is_kept_in_the_answer(self):
        """The twin of `test_a_bounce_still_holds_even_on_a_campaign_of_ours`,
        and it exists because that one is guarded by something else.

        `account_policy` reaches its bounce HOLD through `any_bounce`, which
        reads the LEAD's status and not the membership - so deleting `bounced`
        from `EXCLUDABLE_MEMBERSHIP`'s exclusion left that test green while the
        row itself vanished from the answer. Measured, deliberately, by
        breaking it. This one asserts on the row.
        """
        found = self.account([lead("a@example.test", memberships=[
            membership(OURS, "bounced")], lead_status="bounced")])
        self.assertEqual(found["our_staging_excluded"], [])
        self.assertEqual(
            [c["campaign_id"] for c in found["people"][0]["campaigns"]],
            [OURS])

    def test_a_sequence_finished_membership_of_ours_is_kept(self):
        """A campaign that sent nothing cannot have finished a sequence, so
        seeing one means the evidence is wrong somewhere."""
        found = self.account([lead("a@example.test", memberships=[
            membership(OURS, "sequence_finished")])])
        self.assertEqual(found["our_staging_excluded"], [])


class ItIsDerivedNotRemembered(StagingTest):
    """The exclusion must not outlive the evidence for it."""

    def test_no_campaign_number_is_written_down_anywhere(self):
        """A hardcoded allowlist would keep clearing 485 after 485 starts
        sending. The only campaign ids this module knows are the ones it reads
        out of the binding file and the provider at call time.

        Read off the AST rather than the text, so the measurements recorded in
        the prose - which are the evidence for the rule and belong there -
        cannot satisfy it and cannot break it either.
        """
        import ast

        with open(collision.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        docstrings = {id(ast.get_docstring(node, clean=False))
                      for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef,
                                           ast.FunctionDef))}
        forbidden = {485, 481, 484, 451}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if isinstance(node.value, int) and node.value in forbidden:
                self.fail(f"campaign {node.value} is a literal at line "
                          f"{node.lineno}")
            if isinstance(node.value, str) and id(node.value) not in docstrings:
                for number in forbidden:
                    self.assertNotIn(str(number), node.value,
                                     f"line {node.lineno}")

    def test_forgetting_makes_the_provider_answer_again(self):
        wire = self.wire([lead("a@example.test",
                               memberships=[membership(OURS, "stopped")])])
        collision.check_account("example.test", expect_workspace=WS)
        first = list(wire.reads)
        collision.check_account("example.test", expect_workspace=WS)
        self.assertEqual(wire.reads, first, "the memo did not hold in-run")
        collision.forget_staging_evidence()
        collision.check_account("example.test", expect_workspace=WS)
        self.assertGreater(len(wire.reads), len(first))

    def test_a_campaign_that_starts_sending_stops_being_an_artifact(self):
        """Same campaign, same binding, one send later. The next run's answer
        has to change, which is the whole reason nothing is persisted."""
        wire = self.wire([lead("a@example.test",
                               memberships=[membership(OURS, "stopped")])])
        self.assertEqual(
            len(collision.check_account(
                "example.test", expect_workspace=WS)["our_staging_excluded"]),
            1)
        wire.campaigns[OURS] = campaign_row(emails_sent=1,
                                            total_leads_contacted=1)
        collision.forget_staging_evidence()
        self.assertEqual(
            collision.check_account(
                "example.test", expect_workspace=WS)["our_staging_excluded"],
            [])

    def test_an_estate_of_campaigns_that_are_not_ours_costs_no_read(self):
        """The binding file is the cheap filter. A worked account whose leads
        sit in a dozen of the client's campaigns must not cost a dozen
        provider reads to answer."""
        wire = self.wire([lead("a@example.test", sent=40, memberships=[
            membership(300 + i, "sequence_finished", sent=8)
            for i in range(5)])])
        collision.check_account("example.test", expect_workspace=WS)
        self.assertEqual(wire.reads, [])


class TheTwoDerivationsOfOurNameAgree(unittest.TestCase):
    """`_ours` recomputes the binding suffix rather than importing
    `bisonfactory.provider_campaign_name`, because the factory imports this
    module. Duplication that nothing pins is duplication that drifts, so this
    pins it."""

    def test_the_suffix_this_module_looks_for_is_the_one_the_factory_writes(self):
        from src import bisonfactory

        written = bisonfactory.provider_campaign_name(
            {"name": "RESONATE - X", "client": CLIENT,
             "campaign_id": CANONICAL})
        self.assertTrue(written.endswith(f" [{CLIENT}/{CANONICAL}]"),
                        f"the factory now writes {written!r}")


class TheAccountLevelQuestionIsStillTheOneBeingAsked(StagingTest):
    """Person-level history is not the fallback, and this change does not make
    it one: the exclusion happens inside `check_account`, over every lead at
    the domain, and a colleague's history is what survives it."""

    def test_the_picked_contact_being_clear_does_not_clear_the_account(self):
        found = self.account([
            lead("picked@example.test", memberships=[
                membership(OURS, "stopped")]),
            lead("colleague@example.test", sent=9, memberships=[
                membership(THEIRS, "stopped", sent=9)])])
        self.assertEqual(collision.account_policy(found)[0], collision.HOLD)

    def test_every_lead_at_the_domain_is_still_read(self):
        found = self.account([
            lead("picked@example.test", memberships=[
                membership(OURS, "stopped")]),
            lead("colleague@example.test", sent=9, memberships=[
                membership(THEIRS, "sequence_finished", sent=9)])])
        self.assertEqual(found["leads"], 2)
        self.assertEqual(found["emails_sent_total"], 9)


if __name__ == "__main__":
    unittest.main()
