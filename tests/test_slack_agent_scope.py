"""Cross-workspace isolation for the Slack agent, tested rather than assumed.

OPERATOR, 2026-09-21: "Cross-workspace isolation is tested, not assumed."

The product goal is stricter than "do not leak": it says a cross-client
operation should be *structurally impossible* rather than detected
afterwards. So these tests assert the MATERIAL, not the wording. A client
channel is safe because the tools it may call are filtered before they run
and the knowledge pack is filtered before it is rendered - the outbound term
check is a backstop, and it is tested separately as a backstop rather than
as the guarantee.

Two synthetic workspaces, `alpha` and `beta`, so the assertions do not
depend on what Productive happens to be configured with today.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackscope                                       # noqa: E402
from src import slackagenttools as tools                         # noqa: E402

ALPHA_CHANNEL = "C_ALPHA"
BETA_CHANNEL = "C_BETA"


def _workspace(slug, name, policy):
    return {"kind": "workspace", "slug": slug, "name": name, "client": slug,
            "settings": {"policy": policy}}


ROWS = [
    _workspace("alpha", "Alpha", {
        slackscope.AGENT_CHANNEL_KEY: ALPHA_CHANNEL,
        slackscope.WORKSPACE_USERS_KEY: ["U_ALPHA"],
    }),
    _workspace("beta", "Beta", {
        slackscope.AGENT_CHANNEL_KEY: BETA_CHANNEL,
        slackscope.WORKSPACE_USERS_KEY: ["U_BETA"],
    }),
]

PACK = {
    "built_at": "2026-09-21T00:00:00Z",
    "identity": {"one_line": "an engine"},
    "timeline": {"started_on": "2026-09-09"},
    "workers": {"roles": [{"name": "Qwen"}]},
    "policies": [
        {"id": "collision-recency", "rule": "a reply excludes forever"},
        {"id": "provider-order", "rule": "ContactOut first",
         "internal_note": "spend"},
        {"id": "credit-spend", "rule": "never gated"},
    ],
    "workspaces": {
        "alpha": {"slug": "alpha", "name": "Alpha",
                  "provider_campaign_ids": ["111"]},
        "beta": {"slug": "beta", "name": "Beta",
                 "provider_campaign_ids": ["222"]},
    },
}


class ScopeEnvironment(unittest.TestCase):
    """Every test here runs against a throwaway workspace store."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-scope-")
        self._prev = {k: os.environ.get(k) for k in
                      ("WORKSPACES", slackscope.INTERNAL_CHANNELS_VAR,
                       slackscope.OPS_CHANNEL_VAR,
                       slackscope.STATUS_CHANNEL_VAR,
                       slackscope.INTERNAL_USERS_VAR,
                       slackscope.OPERATOR_USER_VAR)}
        os.environ["WORKSPACES"] = os.path.join(self.tmp, "workspaces.jsonl")
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = "C_INTERNAL"
        for var in (slackscope.OPS_CHANNEL_VAR,
                    slackscope.STATUS_CHANNEL_VAR,
                    slackscope.INTERNAL_USERS_VAR,
                    slackscope.OPERATOR_USER_VAR):
            os.environ.pop(var, None)
        os.environ[slackscope.INTERNAL_USERS_VAR] = "U_OPERATOR"

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def alpha(self):
        return slackscope.resolve(channel=ALPHA_CHANNEL, rows=ROWS)


# ============================================================== BINDING

class BindingIsProvedOrItIsUnbound(ScopeEnvironment):

    def test_a_bound_channel_resolves_to_its_own_workspace(self):
        self.assertEqual(self.alpha().kind, slackscope.CLIENT)
        self.assertEqual(self.alpha().workspace, "alpha")
        beta = slackscope.resolve(channel=BETA_CHANNEL, rows=ROWS)
        self.assertEqual(beta.workspace, "beta")

    def test_an_unknown_channel_is_unbound_and_not_internal(self):
        scope = slackscope.resolve(channel="C_NOBODY_BOUND", rows=ROWS)
        self.assertEqual(scope.kind, slackscope.UNBOUND)

    def test_a_channel_with_no_id_at_all_is_unbound(self):
        self.assertEqual(slackscope.resolve(rows=ROWS).kind,
                         slackscope.UNBOUND)

    def test_a_channel_bound_to_two_workspaces_is_bound_to_neither(self):
        """An ambiguous binding is the one case where guessing is worst."""
        rows = [_workspace("alpha", "Alpha",
                           {slackscope.AGENT_CHANNEL_KEY: "C_SHARED"}),
                _workspace("beta", "Beta",
                           {slackscope.AGENT_CHANNEL_KEY: "C_SHARED"})]
        scope = slackscope.resolve(channel="C_SHARED", rows=rows)
        self.assertEqual(scope.kind, slackscope.UNBOUND)

    def test_the_notification_channel_does_not_bind_the_agent(self):
        """`slack.workspace_channel` is where alerts go, not where the agent
        may be asked anything at all. Two decisions, two keys."""
        rows = [_workspace("alpha", "Alpha",
                           {"slack.workspace_channel": "C_ALERTS"})]
        self.assertEqual(slackscope.resolve(channel="C_ALERTS",
                                            rows=rows).kind,
                         slackscope.UNBOUND)

    def test_a_workspace_store_that_cannot_be_read_narrows_every_scope(self):
        os.environ["WORKSPACES"] = os.path.join(self.tmp, "no-such-dir",
                                                "x.jsonl")
        self.assertEqual(slackscope.resolve(channel=ALPHA_CHANNEL).kind,
                         slackscope.UNBOUND)


class DirectMessagesResolveByUser(ScopeEnvironment):

    def test_an_internal_user_gets_internal_scope(self):
        scope = slackscope.resolve(channel="D1", user="U_OPERATOR",
                                   channel_type="im", rows=ROWS)
        self.assertEqual(scope.kind, slackscope.INTERNAL)

    def test_a_client_user_gets_their_own_workspace_only(self):
        scope = slackscope.resolve(channel="D2", user="U_ALPHA",
                                   channel_type="im", rows=ROWS)
        self.assertEqual(scope.workspace, "alpha")

    def test_an_unknown_user_gets_nothing(self):
        scope = slackscope.resolve(channel="D3", user="U_STRANGER",
                                   channel_type="im", rows=ROWS)
        self.assertEqual(scope.kind, slackscope.UNBOUND)

    def test_a_user_in_two_workspaces_gets_neither(self):
        rows = [_workspace("alpha", "Alpha",
                           {slackscope.WORKSPACE_USERS_KEY: ["U_BOTH"]}),
                _workspace("beta", "Beta",
                           {slackscope.WORKSPACE_USERS_KEY: ["U_BOTH"]})]
        scope = slackscope.resolve(channel="D4", user="U_BOTH",
                                   channel_type="im", rows=rows)
        self.assertEqual(scope.kind, slackscope.UNBOUND)


# ======================================================= THE MATERIAL

class ClientAIsNeverHandedClientBsData(ScopeEnvironment):
    """The guarantee. Not "it does not say beta" - it never HAS beta."""

    def test_the_pack_a_client_sees_holds_only_their_workspace(self):
        visible = self.alpha().filter_pack(PACK)
        self.assertEqual(list(visible.get("workspaces") or {}), ["alpha"])
        self.assertNotIn("beta", repr(visible))

    def test_the_pack_a_client_sees_holds_no_internal_worker(self):
        visible = self.alpha().filter_pack(PACK)
        self.assertIsNone(visible.get("workers"))
        self.assertNotIn("qwen", repr(visible).lower())

    def test_the_pack_a_client_sees_holds_no_commercial_policy(self):
        visible = self.alpha().filter_pack(PACK)
        ids = {row["id"] for row in visible.get("policies") or []}
        self.assertIn("collision-recency", ids)
        self.assertNotIn("provider-order", ids)
        self.assertNotIn("credit-spend", ids)

    def test_an_internal_note_never_survives_into_a_client_pack(self):
        visible = self.alpha().filter_pack(PACK)
        for row in visible.get("policies") or []:
            self.assertNotIn("internal_note", row)

    def test_an_unbound_channel_gets_no_workspace_at_all(self):
        scope = slackscope.resolve(channel="C_NOBODY", rows=ROWS)
        visible = scope.filter_pack(PACK)
        self.assertNotIn("workspaces", visible)
        self.assertNotIn("alpha", repr(visible))
        self.assertNotIn("beta", repr(visible))

    def test_an_internal_channel_gets_the_whole_pack(self):
        scope = slackscope.resolve(channel="C_INTERNAL", rows=ROWS)
        self.assertIs(scope.filter_pack(PACK), PACK)


class ToolsAreFilteredBeforeTheyRun(ScopeEnvironment):

    def test_a_client_cannot_call_an_internal_tool(self):
        available = tools.for_scope(self.alpha())
        for name in ("who_does_what", "credits", "monitors", "next_actions"):
            self.assertNotIn(name, available)

    def test_calling_one_by_name_anyway_is_refused(self):
        for name in ("who_does_what", "credits", "monitors"):
            with self.assertRaises(tools.ToolRefused):
                tools.run(self.alpha(), name)

    def test_an_unbound_channel_can_call_nothing_at_all(self):
        """No readback, not even the timeline.

        The timeline's milestones name campaign ids, send times and the
        size of the sender estate. That is Resonate's operational detail -
        correct in a client's own channel, and not in a room nobody has
        identified. An unbound channel gets the identity section of the
        pack and no tool, which is precisely what lets its forbidden-term
        list be empty: there is no client datum in the prompt for a word
        list to have to catch.
        """
        scope = slackscope.resolve(channel="C_NOBODY", rows=ROWS)
        self.assertEqual(sorted(tools.for_scope(scope)), [])

    def test_a_tool_that_does_not_exist_is_refused(self):
        with self.assertRaises(tools.ToolRefused):
            tools.run(self.alpha(), "delete_everything")

    def test_the_call_budget_is_enforced(self):
        calls = [{"name": "timeline"}] * (tools.MAX_CALLS_PER_TURN + 3)
        results = tools.run_all(self.alpha(), calls)
        dropped = [r for _n, _a, r in results
                   if isinstance(r, dict) and "dropped" in str(r.get("_error"))]
        self.assertEqual(len(dropped), 3)


class AToolArgumentCannotCrossAWorkspace(ScopeEnvironment):
    """The argument is the injection surface: "summarise workspace beta"."""

    def test_a_client_channel_ignores_a_workspace_argument(self):
        self.assertEqual(tools._workspace_for(self.alpha(), "beta"), "alpha")
        self.assertEqual(tools._workspace_for(self.alpha(), None), "alpha")

    def test_an_internal_channel_may_name_a_workspace(self):
        internal = slackscope.resolve(channel="C_INTERNAL", rows=ROWS)
        self.assertEqual(tools._workspace_for(internal, "beta"), "beta")

    def test_a_campaign_belonging_to_another_client_is_not_readable(self):
        original = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        try:
            self.assertTrue(tools._campaign_is_visible(self.alpha(), "111"))
            self.assertFalse(tools._campaign_is_visible(self.alpha(), "222"))
            result = tools.campaign_detail(self.alpha(), "222")
            self.assertIn("_error", result)
            self.assertNotIn("beta", str(result).lower())
        finally:
            tools.knowledge.pack = original

    def test_an_unattributed_record_reaches_no_client(self):
        """A row with no client is excluded, not included by default."""
        import src.store as store
        rows = [{"id": "1", "domain": "a.test", "client": "alpha"},
                {"id": "2", "domain": "b.test", "client": "beta"},
                {"id": "3", "domain": "c.test"}]
        real = store.load
        store.load = lambda *a, **k: rows
        try:
            mine = tools._records("alpha")
            self.assertEqual([r["id"] for r in mine], ["1"])
        finally:
            store.load = real


# ========================================================== THE BACKSTOP

class TheOutboundCheckIsABackstopAndItWorks(ScopeEnvironment):
    """Tested as a backstop: it catches what steps one and two would miss."""

    def test_naming_another_workspace_is_refused(self):
        with self.assertRaises(slackscope.ScopeViolation):
            self.alpha().check_outbound(
                "Beta is running eight campaigns too.", rows=ROWS)

    def test_naming_an_internal_worker_is_refused(self):
        for text in ("Qwen is reworking TASK-241.",
                     "Claude Code will merge it.",
                     "GLM reviewed the change."):
            with self.assertRaises(slackscope.ScopeViolation):
                self.alpha().check_outbound(text, rows=ROWS)

    def test_naming_a_provider_or_a_cost_is_refused(self):
        for text in ("EmailBison scheduled it.",
                     "HeyReach sent the connection request.",
                     "That used 40 credits.",
                     "The mailbox is still in warmup."):
            with self.assertRaises(slackscope.ScopeViolation):
                self.alpha().check_outbound(text, rows=ROWS)

    def test_an_ordinary_client_answer_passes(self):
        text = ("Two emails went out on 21 September and there are no "
                "replies yet. Three campaigns are waiting on your approval.")
        self.assertEqual(self.alpha().check_outbound(text, rows=ROWS), text)

    def test_an_internal_channel_may_say_all_of_it(self):
        internal = slackscope.resolve(channel="C_INTERNAL", rows=ROWS)
        text = "Qwen is on TASK-241; EmailBison 489 sent 2. Beta is idle."
        self.assertEqual(internal.check_outbound(text, rows=ROWS), text)

    def test_an_unbound_channel_may_still_say_what_the_product_is(self):
        """The one sentence it exists to be able to say.

        An earlier version added "lead", "cadence" and "account" to the
        unbound term list, which meant the agent could not say "lead
        generation engine" - the product's own name for itself, out of
        PRODUCT-GOAL's first line. A term list that blocks that is not
        cautious, it is broken. Unbound is safe because it is handed no
        tool and no workspace material, not because of a word list.
        """
        scope = slackscope.resolve(channel="C_NOBODY", rows=ROWS)
        text = ("Resonate OS is an internal, multi-client lead generation "
                "engine. Clients receive reporting rather than operating it.")
        self.assertEqual(scope.check_outbound(text, rows=ROWS), text)

    def test_an_unbound_channel_still_may_not_name_a_client_or_a_worker(self):
        scope = slackscope.resolve(channel="C_NOBODY", rows=ROWS)
        for text in ("Alpha is running eight campaigns.",
                     "Qwen is reworking it.",
                     "EmailBison carries the sending."):
            with self.assertRaises(slackscope.ScopeViolation):
                scope.check_outbound(text, rows=ROWS)

    def test_the_material_never_contains_a_word_the_answer_is_checked_for(
            self):
        """A check that fires on its own input is a bug with a reputation.

        Asked "what is Resonate OS" in an unbound channel, the model wrote
        a correct paragraph ending "...keeps one client's data, senders and
        spend from ever touching another's" - paraphrasing PRODUCT-GOAL's
        own cross-client list, which says "one client's spend reaching
        another's ledger". The backstop then discarded the answer for
        containing "spend", a word the material had handed it. Nothing had
        leaked and the reader got a fallback sentence.
        """
        import json
        from src import slackknowledge

        pack = dict(PACK, identity=slackknowledge.identity())
        for scope in (slackscope.resolve(channel="C_NOBODY", rows=ROWS),
                      self.alpha()):
            body = json.dumps(scope.filter_pack(pack), default=str).lower()
            leaked = [term for term in scope.forbidden_terms()
                      if term in body]
            self.assertFalse(
                leaked,
                "the material handed to a %s channel contains %s, which the "
                "answer is then checked for" % (scope.kind, leaked))


class TheTurnACTUALLYAppliesTheBackstop(ScopeEnvironment):
    """`check_outbound` working is not the same as the turn calling it.

    Added after a mutation run: deleting the scope check from
    `slackconversation.guard` broke nothing, because every test asserted the
    check in isolation and none asserted that the code path taken on a real
    answer reaches it. A guard nothing calls is a guard that does not exist.
    """

    def test_the_guard_rejects_an_answer_that_names_another_client(self):
        from src import slackconversation as conversation
        checked, why = conversation.guard(
            "Beta is doing well too.", "material", self.alpha())
        self.assertIsNone(checked)
        self.assertIn("beta", why.lower())

    def test_the_guard_rejects_an_answer_that_names_a_worker(self):
        from src import slackconversation as conversation
        checked, why = conversation.guard(
            "Qwen is working on it.", "material", self.alpha())
        self.assertIsNone(checked)
        self.assertIn("qwen", why.lower())

    def test_the_guard_rejects_an_answer_that_names_a_provider(self):
        from src import slackconversation as conversation
        checked, why = conversation.guard(
            "EmailBison has it queued.", "material", self.alpha())
        self.assertIsNone(checked)

    def test_the_guard_passes_a_clean_client_answer(self):
        from src import slackconversation as conversation
        text = "Two emails went out and there are no replies yet."
        checked, why = conversation.guard(text, "material", self.alpha())
        self.assertIsNone(why)
        self.assertEqual(checked, text)

    def test_the_guard_strips_an_address_outside_a_client_channel(self):
        from src import slackconversation as conversation
        internal = slackscope.resolve(channel="C_INTERNAL", rows=ROWS)
        checked, why = conversation.guard(
            "reply from someone@example.com", "material", internal)
        self.assertIsNone(why)
        self.assertNotIn("someone@example.com", checked)

    def test_a_whole_turn_in_a_client_channel_discards_a_leaking_answer(self):
        """End to end: a model that names another client is not posted."""
        from src import slackconversation as conversation

        class Leaks:
            model = "leaks"

            def complete(self, prompt, temperature=0):
                if "Answer with JSON" in prompt:
                    return '{"tools": [{"name": "timeline"}], "clarify": null}'
                return "Beta and Qwen are both busy with EmailBison."

        result = conversation.respond("how is it going?",
                                      channel=ALPHA_CHANNEL, user="U_ALPHA",
                                      model=Leaks(), rows=ROWS)
        self.assertEqual(result["scope"], slackscope.CLIENT)
        self.assertNotIn("Beta", result["reply"])
        self.assertNotIn("Qwen", result["reply"])
        self.assertIn("guard", result)


class AddressesNeverLeave(ScopeEnvironment):

    def test_an_address_is_redacted(self):
        self.assertEqual(
            slackscope.redact_addresses("write to someone@example.com today"),
            "write to [address withheld] today")

    def test_redaction_leaves_a_domain_alone(self):
        self.assertEqual(slackscope.redact_addresses("example.com is in"),
                         "example.com is in")


if __name__ == "__main__":
    unittest.main()
