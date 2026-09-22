"""A client can never SEE or TRIGGER anything about another client.

OPERATOR, 2026-09-21: "tests for... 'a client can never see or trigger
anything about another client'."

Two verbs, and the second one is new in Phase B. Phase A proved a client
cannot SEE another client: the tools are filtered, the pack is filtered, the
answer is checked. TRIGGER is a different question, and it has a different
hole: the target of a change request arrives in the MESSAGE, not out of the
store, so no reading filter touches it. "Remove lead mole@rival.test" typed
in Acme's channel would have produced a ticket scoped to Acme naming the
rival's person, and executing it would have reached into another client's
estate through a gate that had checked the wrong thing.

Two synthetic workspaces, `alpha` and `beta`, each with their own estate,
so every assertion here is about the mechanism rather than about whatever
Productive is configured with today.

THE REFUSAL IS THE SAME EITHER WAY. "I cannot find that in your workspace"
is what a client hears whether the target belongs to another client or to
nobody at all, because an answer that told the two apart would confirm the
other client's record exists - and that confirmation IS the disclosure.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import llm, slackconversation as conversation           # noqa: E402
from src import slackagenttools as tools                         # noqa: E402
from src import slackrequests as requests, slackscope            # noqa: E402

ALPHA_CHANNEL, ALPHA_USER = "C0ALPHAAAAA", "U0ALPHAAAAA"
BETA_CHANNEL, BETA_USER = "C0BETAAAAAA", "U0BETAAAAAA"
INTERNAL_CHANNEL, OPERATOR = "C0INTERNALX", "U0OPERATORX"


class TwoClients(unittest.TestCase):
    """A throwaway estate with two tenants in it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-two-clients-")
        self._prev = {}
        from src import store
        for key, value in (
                ("QUEUE", os.path.join(self.tmp, "queue.jsonl")),
                ("WORKSPACES", os.path.join(self.tmp, "workspaces.jsonl")),
                ("CLIENTS_DIR", os.path.join(self.tmp, "clients")),
                ("KNOWLEDGE_PACK", os.path.join(self.tmp, "pack.json")),
                (requests.REQUESTS_DIR_VAR,
                 os.path.join(self.tmp, "requests")),
                (slackscope.INTERNAL_CHANNELS_VAR, INTERNAL_CHANNEL),
                (slackscope.OPERATOR_USER_VAR, OPERATOR),
                (slackscope.STATUS_CHANNEL_VAR, ""),
                (slackscope.OPS_CHANNEL_VAR, "")):
            self._prev[key] = os.environ.get(key)
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name in store.STATE_OVERRIDES:
            self._prev[name] = os.environ.get(name)
            os.environ[name] = os.path.join(self.tmp, "%s.jsonl"
                                            % name.lower())
        os.environ["WORKSPACES"] = os.path.join(self.tmp, "workspaces.jsonl")
        self._threads = conversation.THREADS
        conversation.THREADS = os.path.join(self.tmp, "threads.jsonl")
        os.makedirs(os.environ["CLIENTS_DIR"], exist_ok=True)
        self._build()

    def tearDown(self):
        conversation.THREADS = self._threads
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self):
        from src import campaigns, store, workspaces as ws

        rows = []
        for slug, name, channel, user in (
                ("alpha", "Alpha", ALPHA_CHANNEL, ALPHA_USER),
                ("beta", "Beta", BETA_CHANNEL, BETA_USER)):
            entry = ws.new_workspace(slug, name, client=slug,
                                     created_by="test")
            entry["settings"] = {"policy": {
                slackscope.AGENT_CHANNEL_KEY: channel,
                slackscope.WORKSPACE_USERS_KEY: [user]}}
            rows.append(entry)
        ws.save(rows)

        for slug in ("alpha", "beta"):
            with open(os.path.join(os.environ["CLIENTS_DIR"],
                                   "%s.yaml" % slug), "w",
                      encoding="utf-8") as handle:
                handle.write("name: %s\ncadence: %s_cadence_v1\n"
                             % (slug.title(), slug))

        store.save([
            {"id": "alpha-1", "domain": "alpha-co.test", "client": "alpha",
             "state": "approved", "icp": {"verdict": "in"},
             "contacts": [{"email": "ada@alpha-co.test", "name": "Ada",
                           "key": "ada", "sendable": True,
                           "verdict": "valid"}]},
            {"id": "beta-1", "domain": "beta-co.test", "client": "beta",
             "state": "approved", "icp": {"verdict": "in"},
             "contacts": [{"email": "mole@beta-co.test", "name": "Mole",
                           "key": "mole", "sendable": True,
                           "verdict": "valid"}]},
            {"id": "orphan-1", "domain": "nobody.test", "state": "approved",
             "contacts": [{"email": "who@nobody.test", "key": "who"}]},
        ])
        campaigns.save([
            {"kind": "campaign", "campaign_id": "alpha-c1", "client": "alpha",
             "name": "Alpha cohort", "status": "approved",
             "bison_campaign_id": 1111, "record_ids": ["alpha-1"],
             "senders": {"email": [{"provider_account_id": "5001",
                                    "account_id": "eb-5001"}]}},
            {"kind": "campaign", "campaign_id": "beta-c1", "client": "beta",
             "name": "Beta cohort", "status": "approved",
             "bison_campaign_id": 2222, "record_ids": ["beta-1"],
             "senders": {"email": [{"provider_account_id": "6001",
                                    "account_id": "eb-6001"}]}},
        ])
        self._senders()

    def _senders(self):
        """Two sending estates, one per tenant, in the one roster file.

        Alpha's sender is named `kresimir` after the real one, because the
        operator's instruction is about exactly that person: Productive's
        channel may discuss his mailboxes and a second client's channel may
        not see him at all.
        """
        from src import senderidentity as si

        rows = [
            si.new_sender("alpha", "kresimir", "Kresimir Simicic",
                          title="Account Executive"),
            si.new_email_account("alpha", "eb-5001", "kresimir",
                                 "k1@alpha-co.test", provider_account_id="5001",
                                 daily_limit=15),
            si.new_email_account("alpha", "eb-5002", "kresimir",
                                 "k2@alpha-co.test", provider_account_id="5002",
                                 daily_limit=15),
            # Authorized on paper for nothing: no attestation below, so this
            # one must not appear however the question is asked. It stands
            # in for the excluded identities in the real register.
            si.new_sender("alpha", "excluded_person", "Casey Excluded"),
            si.new_email_account("alpha", "eb-5099", "excluded_person",
                                 "x@alpha-co.test", provider_account_id="5099",
                                 daily_limit=15),
            si.new_sender("beta", "mole", "Mole Person"),
            si.new_email_account("beta", "eb-6001", "mole",
                                 "m@beta-co.test", provider_account_id="6001",
                                 daily_limit=15),
        ]
        rows += [
            {"kind": "ownership_attestation", "workspace": "alpha",
             "channel": "email", "account_id": "eb-5001",
             "sender_id": "kresimir", "by": "operator, in a test",
             "at": "2026-09-22T00:00:00+00:00"},
            {"kind": "ownership_attestation", "workspace": "alpha",
             "channel": "email", "account_id": "eb-5002",
             "sender_id": "kresimir", "by": "operator, in a test",
             "at": "2026-09-22T00:00:00+00:00"},
            {"kind": "ownership_attestation", "workspace": "beta",
             "channel": "email", "account_id": "eb-6001",
             "sender_id": "mole", "by": "operator, in a test",
             "at": "2026-09-22T00:00:00+00:00"},
        ]
        si.save(rows)

    # ---------------------------------------------------------- helpers

    def alpha(self):
        return slackscope.resolve(channel=ALPHA_CHANNEL)

    def say_as_alpha(self, text, thread="T1"):
        return conversation.respond(text, channel=ALPHA_CHANNEL,
                                    user=ALPHA_USER, thread_ts=thread,
                                    model=llm.NoModel())


# ================================================================== SEE

class AlphaCannotSeeBeta(TwoClients):

    def test_the_record_reader_returns_only_alphas_records(self):
        self.assertEqual([r["id"] for r in tools._records("alpha")],
                         ["alpha-1"])

    def test_an_unattributed_record_belongs_to_nobody(self):
        """`orphan-1` has no client. It reaches neither tenant."""
        for slug in ("alpha", "beta"):
            self.assertNotIn("orphan-1",
                             [r["id"] for r in tools._records(slug)])

    def test_the_campaign_reader_returns_only_alphas_campaigns(self):
        self.assertEqual([r["campaign_id"] for r in
                          tools._campaign_rows("alpha")], ["alpha-c1"])

    def test_a_lead_lookup_for_betas_person_finds_nothing(self):
        result = tools.run(self.alpha(), "lead_lookup", "mole@beta-co.test")
        self.assertEqual(result.get("matches"), 0)
        self.assertNotIn("beta-co", str(result.get("leads") or ""))

    def test_an_account_lookup_for_betas_domain_finds_nothing(self):
        result = tools.run(self.alpha(), "account_lookup", "beta-co.test")
        self.assertEqual(result.get("matches"), 0)

    def test_betas_campaign_is_not_readable_from_alphas_channel(self):
        result = tools.run(self.alpha(), "campaign_detail", "2222")
        self.assertIn("_error", result)
        self.assertNotIn("beta", str(result).lower())

    def test_a_workspace_argument_naming_beta_returns_alpha(self):
        self.assertEqual(tools._workspace_for(self.alpha(), "beta"), "alpha")
        summary = tools.run(self.alpha(), "workspace_summary", "beta")
        self.assertEqual(summary.get("slug"), "alpha")

    def test_the_sender_count_is_alphas_only(self):
        result = tools.run(self.alpha(), "sender_summary")
        self.assertEqual(result.get("workspace"), "alpha")
        self.assertEqual(result.get("campaigns_they_serve"), 1)

    def test_the_cadence_is_alphas_only(self):
        result = tools.run(self.alpha(), "cadence_detail", "beta")
        self.assertEqual(result.get("workspace"), "alpha")
        self.assertNotIn("beta", str(result).lower())


class AClientsOwnSendersAreTheirOwnData(TwoClients):
    """OPERATOR, 2026-09-22.

    "A client's OWN senders are the client's own data. In
    #productive-resonate-outbound the agent may name Productive's authorized
    sender humans, say how many mailboxes and LinkedIn seats each has, their
    daily capacity, which campaigns they carry, and their health."

    The people sending for Productive are Productive's own staff and half of
    them are in that channel. What must still hold is that this is THEIR
    estate and nobody else's.
    """

    def beta(self):
        return slackscope.resolve(channel=BETA_CHANNEL)

    # ---- what alpha MAY see

    def test_alpha_can_see_its_own_sender_by_name(self):
        result = tools.run(self.alpha(), "sender_roster")
        names = [row["name"] for row in result["senders"]]
        self.assertIn("Kresimir Simicic", names)

    def test_alpha_is_told_the_mailboxes_capacity_and_campaigns(self):
        row = [r for r in tools.run(self.alpha(), "sender_roster")["senders"]
               if r["name"] == "Kresimir Simicic"][0]
        self.assertEqual(row["mailboxes"], 2)
        self.assertEqual(row["daily_email_capacity"], 30)
        self.assertEqual(row["campaigns_carried"], ["Alpha cohort"])

    def test_the_hard_stop_is_reported_beside_the_rate(self):
        """A bounce rate means nothing without the line it is measured
        against."""
        result = tools.run(self.alpha(), "sender_roster")
        self.assertEqual(result["bounce_hard_stop_percent"], 2.0)

    def test_an_unattested_person_is_not_on_the_roster(self):
        """The excluded identities are excluded by having no attestation,
        so a filter on attestation cannot list them however it is asked."""
        result = tools.run(self.alpha(), "sender_roster")
        self.assertNotIn("Casey Excluded",
                         [row["name"] for row in result["senders"]])
        self.assertNotIn("Casey", json.dumps(result))

    def test_the_attestation_prose_never_reaches_the_answer(self):
        """`by` records who signed it and how attestation works. Neither is
        a fact about the client's estate."""
        result = json.dumps(tools.run(self.alpha(), "sender_roster"))
        self.assertNotIn("operator, in a test", result)
        self.assertNotIn("attestation", result.lower())

    def test_a_client_may_say_mailbox_and_seat(self):
        """Refusing to say "mailbox" to the person whose mailbox it is was
        the module being cautious about the wrong thing."""
        text = ("Kresimir has two mailboxes and one LinkedIn seat, "
                "30 emails a day.")
        self.assertEqual(self.alpha().check_outbound(text), text)

    def test_a_client_still_may_not_say_attested(self):
        """The operator asked for "authorized senders"."""
        for text in ("Kresimir is attested on both.",
                     "That is an attestation from the operator.",
                     "The mailbox is still in warmup."):
            with self.assertRaises(slackscope.ScopeViolation):
                self.alpha().check_outbound(text)

    # ---- what beta may NOT see

    def test_beta_cannot_see_alphas_sender_at_all(self):
        result = tools.run(self.beta(), "sender_roster")
        self.assertNotIn("Kresimir Simicic",
                         [row["name"] for row in result["senders"]])
        self.assertNotIn("kresimir", json.dumps(result).lower())
        self.assertNotIn("alpha", json.dumps(result).lower())

    def test_beta_sees_only_its_own(self):
        result = tools.run(self.beta(), "sender_roster")
        self.assertEqual([row["name"] for row in result["senders"]],
                         ["Mole Person"])
        self.assertEqual(result["workspace"], "beta")

    def test_a_workspace_argument_cannot_fetch_the_other_roster(self):
        result = tools.run(self.beta(), "sender_roster", "alpha")
        self.assertEqual(result["workspace"], "beta")
        self.assertNotIn("Kresimir", json.dumps(result))

    def test_naming_alphas_sender_in_betas_channel_is_refused(self):
        """The backstop, for the one thing a word list can still catch."""
        with self.assertRaises(slackscope.ScopeViolation):
            self.beta().check_outbound(
                "Alpha's senders carry that campaign.", rows=None)

    def test_an_unresolved_authorization_is_not_reported_as_zero(self):
        """Measured on the live roster: LinkedIn authorizations carry `hr-`
        ids and the seats carry `li-`, so none of them resolves. "0 seats"
        would read as "you have no LinkedIn sending", which is false."""
        result = tools.run(self.alpha(), "sender_roster")
        self.assertEqual(result["linkedin_seats"], 0)
        self.assertNotIn("linkedin_authorizations_unresolved", result)


# ============================================================== TRIGGER

class AlphaCannotTriggerAnythingAboutBeta(TwoClients):
    """The Phase B half. A ticket's target comes from the MESSAGE."""

    def test_alpha_cannot_raise_a_removal_for_betas_lead(self):
        result = self.say_as_alpha("remove lead mole@beta-co.test")
        self.assertEqual(result["how"], "request_not_yours")
        self.assertEqual(requests.load(), [])

    def test_the_refusal_does_not_say_whose_it_is(self):
        result = self.say_as_alpha("remove lead mole@beta-co.test")
        lowered = result["reply"].lower()
        self.assertNotIn("beta", lowered.replace("beta-co.test", ""))
        self.assertNotIn("another client", lowered)
        self.assertNotIn("belongs to", lowered)

    def test_a_target_that_exists_nowhere_gets_the_same_refusal(self):
        """The two answers must be identical, or the difference is the
        disclosure."""
        theirs = self.say_as_alpha("remove lead mole@beta-co.test")["reply"]
        nobodys = self.say_as_alpha(
            "remove lead ghost@nowhere.test")["reply"]
        self.assertEqual(
            theirs.replace("mole@beta-co.test", "X"),
            nobodys.replace("ghost@nowhere.test", "X"))

    def test_alpha_cannot_raise_a_pause_for_betas_campaign(self):
        result = self.say_as_alpha("pause campaign 2222")
        self.assertEqual(result["how"], "request_not_yours")
        self.assertEqual(requests.load(), [])

    def test_alpha_can_raise_a_pause_for_its_own_campaign(self):
        """The check must not be so tight that it refuses everything."""
        result = self.say_as_alpha("pause campaign 1111")
        self.assertEqual(result["how"], "request_restated")

    def test_alpha_cannot_raise_a_copy_change_on_betas_cadence(self):
        result = self.say_as_alpha(
            "change the connection message of cadence beta_cadence_v1 to "
            "\"hello there\"")
        self.assertEqual(result["how"], "request_not_yours")

    def test_alpha_can_raise_a_copy_change_on_its_own_cadence(self):
        result = self.say_as_alpha(
            "change the connection message of cadence alpha_cadence_v1 to "
            "\"hello there\"")
        self.assertEqual(result["how"], "request_restated")

    def test_alpha_can_still_remove_its_own_lead(self):
        result = self.say_as_alpha("remove lead ada@alpha-co.test")
        self.assertEqual(result["how"], "request_restated")
        raised = self.say_as_alpha("yes")
        self.assertEqual(requests.get(raised["ticket"])["workspace"],
                         "alpha")

    def test_a_ticket_alpha_raised_is_scoped_to_alpha(self):
        self.say_as_alpha("remove lead ada@alpha-co.test")
        ticket = requests.get(self.say_as_alpha("yes")["ticket"])
        self.assertEqual(ticket["workspace"], "alpha")
        self.assertEqual(ticket["requester"], ALPHA_USER)
        self.assertNotIn("beta", str(ticket).lower())

    def test_alpha_cannot_decide_betas_ticket(self):
        """Even the id of somebody else's request is not a handle."""
        beta = conversation.respond("remove lead mole@beta-co.test",
                                    channel=BETA_CHANNEL, user=BETA_USER,
                                    thread_ts="TB", model=llm.NoModel())
        self.assertEqual(beta["how"], "request_restated")
        ticket_id = conversation.respond("yes", channel=BETA_CHANNEL,
                                         user=BETA_USER, thread_ts="TB",
                                         model=llm.NoModel())["ticket"]
        result = self.say_as_alpha("approve %s" % ticket_id)
        self.assertEqual(result["how"], "refused")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.AWAITING)

    def test_an_internal_channel_may_target_either(self):
        """The restriction is on a CLIENT channel, not on the operator."""
        for target in ("1111", "2222"):
            result = conversation.respond(
                "pause campaign %s" % target, channel=INTERNAL_CHANNEL,
                user=OPERATOR, thread_ts="TI-%s" % target,
                model=llm.NoModel())
            self.assertEqual(result["how"], "request_restated", target)


# ========================================================== THE BACKSTOP

class NothingAboutBetaSurvivesIntoAlphasChannel(TwoClients):

    def test_the_outbound_check_refuses_betas_name(self):
        with self.assertRaises(slackscope.ScopeViolation):
            self.alpha().check_outbound("Beta is running one campaign too.")

    def test_alphas_pack_holds_only_alpha(self):
        from src import slackknowledge
        visible = self.alpha().filter_pack(slackknowledge.pack(force=True))
        self.assertEqual(list(visible.get("workspaces") or {}), ["alpha"])
        self.assertNotIn("beta", repr(visible).lower())

    def test_the_action_required_post_names_only_the_raising_workspace(self):
        self.say_as_alpha("remove lead ada@alpha-co.test")
        result = self.say_as_alpha("yes")
        announcement = result["post_to_internal"]
        self.assertIn("alpha", announcement)
        self.assertNotIn("beta", announcement.lower())


if __name__ == "__main__":
    unittest.main()
