#!/usr/bin/env python3
"""TASK-936. 487, 489 and 493 are refused BY THE WRITE GATE, on EFFECT.

WHAT THIS FILE IS EVIDENCE OF, AND WHY IT IS NOT A LOG TEST.

Until TASK-936 the rule "do not touch 487/489/493" rested on three conditions
and the write gate was none of them: the killswitch, `sending.live=false`, and
3,005 stored approvals of which zero were still valid. Each of those can be
changed independently of the write path, by somebody who is not thinking about
these three campaigns at all. Measured on d98c83ce, `bison.resume` and
`bison.assign_sender` passed ownership for all three and REACHED TRANSPORT.

So every assertion here is about EFFECT. The transport and the read-back raise
`TransportTouched` if they are called at all, and reaching them is the defect.
A refusal written to a ledger while the call still reaches the provider is the
exact defect class this task closes, so no test here asserts on a log row.

THE THREE CONDITIONS ARE LIFTED ON PURPOSE in `_conditions_lifted`: the global
killswitch is cleared, `sending.live` is set to `on` for the tenant, and
`executionguard` is made to mint a passing Authorization and to revalidate
without complaint - which is what a fresh approval buys. The table still
refuses. That is the acceptance: the protection is a property of the gate.

THE NEGATIVE CONTROL IS NOT OPTIONAL and lives in
`TheNegativeControl.test_removing_the_guard_puts_every_verb_back_on_transport`.
Neutralising `providerwrites.require_not_sealed` - which is what deleting the
one call from `_perform` does - puts six verbs back on transport against all
three campaigns. Without that case this file would pass against a gate that
refuses everything for some unrelated reason, and
`TheSealIsNarrow.test_an_unsealed_campaign_still_reaches_transport` is the
other half of the same argument.

NO PROVIDER IS CONTACTED. There is no network call in this file by
construction: the transport raises instead of sending.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import providerwrites, store  # noqa: E402

#: The three sealed campaigns and the canonical rows they are bound to. Stated
#: here rather than read from `providerwrites._SEALED_CAMPAIGNS`, deliberately:
#: a test that reads the constant back passes when the constant is wrong.
SEALED = ((487, "productive-email-control-v3"),
          (489, "productive-email-us-cohort-v1"),
          (493, "productive-email-batch1-ivan"))

#: An ordinary Resonate OS campaign that is NOT sealed, used to prove the gate
#: discriminates. Synthetic: no such row exists in production.
UNSEALED_ID = 90487
UNSEALED_ROW = "synthetic-unsealed-cohort-zz"

#: Every EmailBison verb `providerwrites` declares. The table is built from
#: this rather than from a hand-written list so a verb added later is covered
#: without anybody remembering to add it here.
EMAIL_VERBS = tuple(sorted(op for op in providerwrites.OPERATIONS
                           if op.startswith("bison.")))


class TransportTouched(RuntimeError):
    """Raised by the transport and by the read-back. Reaching it IS the bug."""


class GateTest(unittest.TestCase):
    """Isolated store, three sealed rows, and a transport that cannot be used."""

    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-936-")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work, exist_ok=True)
        self._prev = {k: os.environ.get(k) for k in ("QUEUE", "OUT")}
        os.environ["QUEUE"] = os.path.join(self.work, "queue.jsonl")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self.addCleanup(self._restore_env)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(store.use_directory(self.work))

        # THE STORE ACTUALLY MOVED. Asserted rather than assumed: a worktree
        # resolving `work/` relatively has written into production before.
        self.assertTrue(
            store.queue_path().startswith(os.path.abspath(self.tmp)),
            "the queue did not move: %s" % store.queue_path())
        self.assertTrue(
            store.campaigns_path().startswith(os.path.abspath(self.tmp)),
            "campaigns did not move: %s" % store.campaigns_path())

        self.write_rows([
            {"campaign_id": row, "client": "productive", "status": "paused",
             "bison_campaign_id": provider, "record_ids": ["rec-zz-1"]}
            for provider, row in SEALED
        ] + [
            {"campaign_id": UNSEALED_ROW, "client": "productive",
             "status": "paused", "bison_campaign_id": UNSEALED_ID,
             "record_ids": ["rec-zz-1"]},
        ])
        self.touches = []

    def _restore_env(self):
        for name, value in self._prev.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def write_rows(self, rows):
        with open(store.campaigns_path(), "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    # ------------------------------------------------------------- effect

    def transport(self, _payload=None):
        self.touches.append("transport")
        raise TransportTouched("the transport was reached")

    def readback(self):
        self.touches.append("readback")
        raise TransportTouched("the read-back was reached")

    def write(self, operation, **kw):
        """One `perform` call whose transport and read-back cannot be used."""
        kw.setdefault("tenant", "productive")
        kw.setdefault("expected", {"status": "running"})
        return providerwrites.perform(
            operation, transport=self.transport, readback=self.readback,
            by="test-936", **kw)

    def refusal_for(self, operation, **kw):
        """The WriteRefused this write produced, with nothing touched.

        Asserts on EFFECT first: if the transport or the read-back was called,
        the write happened and the refusal is a log row rather than a gate.
        """
        before = len(self.touches)
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            self.write(operation, **kw)
        self.assertEqual(
            self.touches[before:], [],
            "%s was refused and STILL reached %s - a refusal that does not "
            "prevent the write is the defect TASK-936 closes"
            % (operation, self.touches[before:]))
        return str(caught.exception)

    # --------------------------------------------- the three conditions

    def _conditions_lifted(self):
        """Clear the killswitch, switch sending on, and make approval pass.

        This is the state acceptance point 1 names. Each of the three is lifted
        by its own canonical mechanism and then MEASURED, so a case that passes
        cannot be passing because the lift silently failed.
        """
        from src import executionguard, killswitch, push, workspaces

        # 1. The global killswitch is derived from `push.LiveSendNotEnabled`
        #    existing, so clearing it means removing that attribute.
        sentinel = getattr(push, "LiveSendNotEnabled")
        delattr(push, "LiveSendNotEnabled")
        self.addCleanup(setattr, push, "LiveSendNotEnabled", sentinel)
        self.assertTrue(killswitch.global_state()["sending"],
                        "the global killswitch was not actually cleared")

        # 2. `sending.live=on` for the tenant. The workspace is created first:
        #    `workspace_state` answers "no such workspace" otherwise, and a
        #    SKIP here would silently hollow out the whole effect table - a
        #    green test that cannot fail is the failure mode this repository
        #    has already shipped once.
        workspaces.ensure("productive", "Productive", created_by="test-936")
        workspaces.set_policy("productive", {"sending.live": "on"},
                              actor="test-936")
        self.assertTrue(
            killswitch.workspace_state("productive")["sending"],
            "sending.live was not actually switched on for productive")

        # 3. A fresh approval, expressed the only way the write layer can see
        #    one: `executionguard` mints a passing Authorization and
        #    revalidates without complaint. That is exactly what refreshing an
        #    approval buys a caller, and nothing more.
        real_revalidate = executionguard.revalidate
        executionguard.revalidate = lambda *a, **k: True
        self.addCleanup(setattr, executionguard, "revalidate", real_revalidate)

    def fresh_authorization(self, operation, channel, campaign_row):
        """A token that looks exactly like one every gate just minted."""
        from src import executionguard
        return executionguard.Authorization(
            key="test-936|%s|%s" % (operation, campaign_row),
            operation=operation, channel=channel, workspace="productive",
            campaign_id=campaign_row, sender_id="2736", rec_id="rec-zz-1",
            contact_key="contact-zz-1", step_key="step-1",
            fingerprint="fp-zz", gates=("all",), at=store.now())


class TheEffectTable(GateTest):
    """Acceptance 1. Every verb, every campaign, refused before transport."""

    def test_every_email_verb_against_every_sealed_campaign_is_refused(self):
        """The table of effect, with all three external conditions lifted.

        Each cell drives the real `perform` against the real canonical rows.
        A cell passes only if the verb was refused AND neither the transport
        nor the read-back was called.
        """
        self._conditions_lifted()
        table = {}
        for provider, row in SEALED:
            for verb in EMAIL_VERBS:
                with self.subTest(campaign=provider, verb=verb):
                    why = self.refusal_for(
                        verb, campaign=row,
                        provider_campaign_id=str(provider),
                        payload={"campaign_id": provider},
                        authorization=self.fresh_authorization(
                            verb, "email", row))
                    self.assertIn("SEALED at the write gate", why)
                    table[(provider, verb)] = "REFUSED"
        self.assertEqual(len(table), len(SEALED) * len(EMAIL_VERBS))
        self.assertEqual(sorted(set(table.values())), ["REFUSED"])

    def test_the_two_verbs_measured_reaching_transport_are_refused(self):
        """The named regression. `bison.resume` and `bison.assign_sender`
        reached transport on d98c83ce for all three campaigns."""
        self._conditions_lifted()
        for provider, row in SEALED:
            for verb in ("bison.resume", "bison.assign_sender"):
                with self.subTest(campaign=provider, verb=verb):
                    self.refusal_for(verb, campaign=row,
                                     provider_campaign_id=str(provider),
                                     payload={"campaign_id": provider})
        self.assertEqual(self.touches, [])

    def test_a_linkedin_verb_cannot_reach_them_either(self):
        """The seal is keyed on the destination, not on the channel.

        These three are EmailBison campaigns, so a HeyReach verb naming one is
        a binding fault - and a binding fault must refuse rather than be
        waved through because the channel looks wrong.
        """
        self._conditions_lifted()
        why = self.refusal_for("heyreach.pause",
                               campaign="productive-email-control-v3",
                               payload={"campaign_id": 487})
        self.assertIn("487", why)


class TheRefusalNamesIt(GateTest):
    """Acceptance 2. A refusal that cannot name its destination is the hole."""

    def test_the_refusal_names_the_provider_id_the_row_and_the_reason(self):
        for provider, row in SEALED:
            with self.subTest(campaign=provider):
                why = self.refusal_for("bison.resume", campaign=row,
                                       provider_campaign_id=str(provider),
                                       payload={"campaign_id": provider})
                self.assertIn(str(provider), why)
                self.assertIn(row, why)
                self.assertIn("2026-09-28", why)
                self.assertIn("operator", why)

    def test_the_refusal_says_the_three_conditions_do_not_lift_it(self):
        """The message has to tell the next reader where the protection lives,
        because the previous answer - three conditions elsewhere - is what a
        reader would otherwise assume."""
        why = self.refusal_for("bison.resume", campaign=None,
                               provider_campaign_id="493", payload={})
        self.assertIn("killswitch", why)
        self.assertIn("sending.live", why)
        self.assertIn("approval", why)
        self.assertIn("APPROVED", why)

    def test_the_refusal_says_the_transport_was_not_reached(self):
        why = self.refusal_for("bison.pause", campaign=None,
                               provider_campaign_id="489", payload={})
        self.assertIn("transport was not reached", why)


class TheSealIsFirst(GateTest):
    """The placement is the mechanism. Nothing may mask it."""

    def test_an_unsupported_verb_against_a_sealed_campaign_names_the_seal(self):
        """`bison.set_limits` is NOT in SUPPORTED, and `require_supported` is
        described in `_perform` as the cheapest and most decisive refusal. If
        the seal ran after it, the ledger row for a write aimed at 487 would
        say "unsupported" and name no campaign at all."""
        self.assertFalse(providerwrites.is_supported("bison.set_limits"))
        why = self.refusal_for("bison.set_limits",
                               campaign="productive-email-control-v3",
                               provider_campaign_id="487",
                               payload={"campaign_id": 487})
        self.assertIn("SEALED at the write gate", why)
        self.assertIn("487", why)

    def test_an_unknown_operation_against_a_sealed_campaign_names_the_seal(self):
        """Even a verb this module has never heard of. `describe` would raise
        for it, so this also proves the seal runs ahead of `describe`."""
        why = self.refusal_for("bison.invent_a_verb",
                               campaign="productive-email-control-v3",
                               payload={"campaign_id": 487})
        self.assertIn("SEALED at the write gate", why)

    def test_a_facing_verb_with_a_fresh_token_names_the_seal(self):
        """A prospect-facing verb refuses for want of an Authorization. With
        one in hand it would refuse at the conditional. The seal is ahead of
        both, so the refusal names the campaign either way."""
        self._conditions_lifted()
        why = self.refusal_for(
            "bison.activate", campaign="productive-email-control-v3",
            provider_campaign_id="487", payload={"campaign_id": 487},
            authorization=self.fresh_authorization(
                "bison.activate", "email", "productive-email-control-v3"))
        self.assertIn("SEALED at the write gate", why)
        self.assertNotIn("requires an Authorization", why)


class TheSealHasTwoHalves(GateTest):
    """What the caller SAID, and what canonical state SAYS. Different attacks."""

    def test_a_sealed_row_rebound_to_another_campaign_is_still_sealed(self):
        """The 2026-09-18 defeat, reproduced against the seal.

        The unpinned allowlist let the v3 row be re-bound 487 -> 327 and
        carried its grant onto a client campaign. A seal that trusted the
        row's binding would have the same hole, so the ROW NAME is sealed
        independently of what it is bound to.
        """
        self.write_rows([{"campaign_id": "productive-email-control-v3",
                          "client": "productive", "status": "paused",
                          "bison_campaign_id": 327}])
        why = self.refusal_for("bison.resume",
                               campaign="productive-email-control-v3",
                               payload={})
        self.assertIn("productive-email-control-v3", why)
        self.assertIn("487", why)

    def test_another_row_bound_to_a_sealed_campaign_is_refused(self):
        """And the mirror image: a row with an innocent name that resolves to
        487. The write names neither 487 nor a sealed row; canonical state is
        what refuses it."""
        self.write_rows([{"campaign_id": "synthetic-rebound-zz",
                          "client": "productive", "status": "paused",
                          "bison_campaign_id": 487}])
        why = self.refusal_for("bison.resume", campaign="synthetic-rebound-zz",
                               payload={})
        self.assertIn("synthetic-rebound-zz", why)
        self.assertIn("487", why)
        self.assertIn("bison_campaign_id", why)

    def test_a_sealed_id_is_found_wherever_the_payload_hides_it(self):
        for payload in ({"campaign_id": 487},
                        {"campaign_ids": [1, 487]},
                        {"campaign": {"id": 487}},
                        {"body": {"campaign_id": "487"}},
                        {"bison_campaign_id": 487}):
            with self.subTest(payload=payload):
                why = self.refusal_for("bison.resume", campaign=None,
                                       payload=payload)
                self.assertIn("487", why)

    def test_every_spelling_of_a_sealed_id_collapses_to_it(self):
        """`487`, `"487"`, `487.0`, `"0487"` and `" 487 "` are one campaign.
        A row bound to `481.0` slipped past `_NEVER_ACTIVATE` entirely on
        2026-09-18 for exactly this reason."""
        for spelling in (487, "487", 487.0, "0487", " 487 "):
            with self.subTest(spelling=spelling):
                why = self.refusal_for("bison.resume", campaign=None,
                                       provider_campaign_id=spelling,
                                       payload={})
                self.assertIn("487", why)

    def test_the_authorizations_own_campaign_is_checked(self):
        """A token minted for a sealed row is not a route into it either."""
        why = self.refusal_for(
            "bison.activate", campaign=None, payload={},
            authorization=self.fresh_authorization(
                "bison.activate", "email", "productive-email-batch1-ivan"))
        self.assertIn("productive-email-batch1-ivan", why)


class TheSealIsNarrow(GateTest):
    """Proof this file can fail: the gate still lets an unsealed write out."""

    def test_an_unsealed_campaign_still_reaches_transport(self):
        """THE OTHER HALF OF THE NEGATIVE CONTROL.

        Without this case, a `require_not_sealed` that refused unconditionally
        would pass every other test in this file. `bison.pause` against an
        ordinary campaign must still reach the transport - and it does, which
        is how we know the refusals above are about these three campaigns and
        not about the gate having been welded shut.
        """
        with self.assertRaises(providerwrites.WriteUnverified) as caught:
            self.write("bison.pause", campaign=UNSEALED_ROW,
                       provider_campaign_id=str(UNSEALED_ID),
                       payload={"campaign_id": UNSEALED_ID},
                       expected={"status": "paused"})
        self.assertIn("TransportTouched", str(caught.exception))
        self.assertEqual(self.touches, ["transport"])

    def test_a_lead_id_that_happens_to_be_487_does_not_refuse(self):
        """The guard must name campaigns, not numbers. A payload whose LEAD id
        is 487 is not a write to campaign 487, and a guard that cried wolf
        here is a guard somebody deletes."""
        with self.assertRaises(providerwrites.WriteUnverified):
            self.write("bison.stop_lead", campaign=UNSEALED_ROW,
                       provider_campaign_id=str(UNSEALED_ID),
                       payload={"campaign_id": UNSEALED_ID,
                                "lead_ids": [487, 489, 493]},
                       expected={"status": "stopped"})
        self.assertEqual(self.touches, ["transport"])


class TheNegativeControl(GateTest):
    """Acceptance 3 and 4. Remove the line and the writes come back."""

    def _without_the_guard(self):
        """Exactly what deleting the call from `_perform` does.

        Patching the function rather than editing the file is deliberate: the
        edit-and-revert cycle in this repository has twice served a stale
        `.pyc` and kept running the mutant after the source was restored.
        """
        real = providerwrites.require_not_sealed
        providerwrites.require_not_sealed = lambda *a, **k: True
        self.addCleanup(setattr, providerwrites, "require_not_sealed", real)

    def test_removing_the_guard_puts_every_verb_back_on_transport(self):
        """THE MANDATORY NEGATIVE CONTROL, ON EFFECT.

        Six EmailBison verbs reach the transport against all three campaigns
        with the guard gone: assign_sender, create_campaign, pause, resume,
        set_sequence and stop_lead. Measured, not asserted from a list - the
        test collects what actually arrived and requires those six.
        """
        self._without_the_guard()
        self._conditions_lifted()
        reached = {}
        for provider, row in SEALED:
            arrived = set()
            for verb in EMAIL_VERBS:
                before = len(self.touches)
                try:
                    self.write(verb, campaign=row,
                               provider_campaign_id=str(provider),
                               payload={"campaign_id": provider})
                except Exception:
                    pass
                if self.touches[before:]:
                    arrived.add(verb)
            reached[provider] = arrived

        expected = {"bison.assign_sender", "bison.create_campaign",
                    "bison.pause", "bison.resume", "bison.set_sequence",
                    "bison.stop_lead"}
        for provider, _row in SEALED:
            self.assertEqual(
                reached[provider], expected,
                "with the guard removed, campaign %s should be reachable by "
                "exactly %s; got %s. If this set SHRANK, something other than "
                "the seal is now refusing and the positive cases above are "
                "proving nothing." % (provider, sorted(expected),
                                      sorted(reached[provider])))

    def test_with_the_guard_in_place_the_same_calls_touch_nothing(self):
        """The same loop, same fixtures, guard restored. Zero contacts."""
        self._conditions_lifted()
        for provider, row in SEALED:
            for verb in EMAIL_VERBS:
                try:
                    self.write(verb, campaign=row,
                               provider_campaign_id=str(provider),
                               payload={"campaign_id": provider})
                except Exception:
                    pass
        self.assertEqual(
            self.touches, [],
            "a sealed campaign was contacted %s times" % len(self.touches))


class TheConditionsAreReallyLifted(GateTest):
    """The premise of the effect table, measured rather than assumed."""

    def test_the_killswitch_and_sending_live_are_permissive_in_the_fixture(self):
        from src import killswitch
        self._conditions_lifted()
        self.assertTrue(killswitch.global_state()["sending"])
        self.assertTrue(killswitch.workspace_state("productive")["sending"])

    def test_and_the_seal_reads_none_of_them(self):
        """The strongest form of the claim: `require_not_sealed` refuses with
        the whole killswitch module removed from `sys.modules` and no
        workspace, approval or ledger state at all."""
        for provider, row in SEALED:
            with self.subTest(campaign=provider):
                with self.assertRaises(providerwrites.WriteRefused):
                    providerwrites.require_not_sealed(
                        "bison.resume", campaign=row,
                        provider_campaign_id=str(provider), payload={})


class TheSealIsOneTable(GateTest):
    """Acceptance 5. One list, and the two halves cannot drift."""

    def test_the_row_index_is_derived_and_not_a_second_list(self):
        """`_SEALED_ROWS` is built from `_SEALED_CAMPAIGNS`, so there is no
        second table that could disagree about which row is which campaign."""
        self.assertEqual(
            providerwrites._SEALED_ROWS,
            {row: provider for provider, (row, _why)
             in providerwrites._SEALED_CAMPAIGNS.items()})

    def test_the_table_is_exactly_the_three_campaigns(self):
        self.assertEqual(sorted(providerwrites.sealed_campaigns()),
                         ["487", "489", "493"])
        for provider, row in SEALED:
            named_row, why = providerwrites.sealed_campaigns()[str(provider)]
            self.assertEqual(named_row, row)
            self.assertIn("2026-09-28", why)

    def test_the_public_reader_is_a_copy_rather_than_the_table(self):
        """`sealed_campaigns()` is how other modules are meant to read the
        seal. Handing out the dict itself would let a caller empty it."""
        got = providerwrites.sealed_campaigns()
        got.pop("487", None)
        self.assertIn("487", providerwrites.sealed_campaigns())

    def test_the_seal_does_not_depend_on_the_internal_campaign_list(self):
        """The seal and `config/internal-campaigns.txt` answer different
        questions and must not be collapsed. That file classifies TENANCY -
        is this a campaign the Productive team runs by hand, or one Resonate
        OS created - and its answer for all three of these is `resonate_os`,
        which is a PASS there. An operator's pause is not a tenancy fact.

        So the seal must hold with that file absent, which on master it is.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        listing = os.path.join(root, "config", "internal-campaigns.txt")
        if os.path.exists(listing):
            with open(listing, encoding="utf-8") as handle:
                body = handle.read()
            for provider, _row in SEALED:
                self.assertNotIn(
                    str(provider), body,
                    "the tenancy list has started naming %s; one of the two "
                    "mechanisms is now a copy of the other" % provider)
        for provider, row in SEALED:
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.require_not_sealed(
                    "bison.resume", campaign=row,
                    provider_campaign_id=str(provider), payload={})


class TheWireIsSealedToo(GateTest):
    """The same one table, enforced a second time where the socket opens.

    `providerwrites.perform` is the door, and the door is not the only way out:
    `bisonfactory` reaches the bare provider in nine places, and
    `scripts/resume_487.py` and `scripts/batch_activate.py` deliberately do not
    call `perform` at all. Each of those opens a `providers.allow_writes(...)`
    scope, which before TASK-936 was the whole authorization they needed.

    Every case here runs INSIDE an open write scope, because a seal that an
    open scope lifts is not a seal.
    """

    def scope(self):
        from src import providers
        return providers.allow_writes("TASK-936 test: an open scope must not "
                                      "lift the seal")

    def url(self, path):
        from src.providers import bison
        return bison.DEFAULT_BASE + path

    def test_every_campaign_scoped_bison_write_route_is_refused(self):
        from src import providers
        routes = (("PATCH", "/api/campaigns/%s/pause"),
                  ("PATCH", "/api/campaigns/%s/resume"),
                  ("PATCH", "/api/campaigns/%s/update"),
                  ("PUT", "/api/campaigns/%s/schedule"),
                  ("POST", "/api/campaigns/%s/attach-sender-emails"),
                  ("POST", "/api/campaigns/%s/leads/attach-leads"),
                  ("POST", "/api/campaigns/%s/leads/stop-future-emails"),
                  ("POST", "/api/campaigns/%s/sequence-steps"))
        for provider, _row in SEALED:
            for method, template in routes:
                with self.subTest(campaign=provider, route=template):
                    with self.scope():
                        with self.assertRaises(
                                providers.ProviderWriteRefused) as caught:
                            providers.refuse_unauthorized_write(
                                method, self.url(template % provider))
                    why = str(caught.exception)
                    self.assertIn("SEALED", why)
                    self.assertIn(str(provider), why)

    def test_an_open_write_scope_does_not_lift_it(self):
        """`scripts/resume_487.py` wraps its one bare call in exactly this."""
        from src import providers
        with providers.allow_writes("resume 487 per the 2026-09-21 grant"):
            self.assertTrue(providers.writes_allowed(
                self.url("/api/campaigns/487/resume"))[0],
                "the scope did not actually open; this case would pass for "
                "the wrong reason")
            with self.assertRaises(providers.ProviderWriteRefused) as caught:
                providers.refuse_unauthorized_write(
                    "PATCH", self.url("/api/campaigns/487/resume"))
        self.assertIn("SEALED", str(caught.exception))

    def test_an_unsealed_campaign_passes_the_wire_check(self):
        """Proof this class can fail. 327 is somebody else's live campaign and
        the seal has nothing to say about it."""
        from src import providers
        with self.scope():
            providers.refuse_unauthorized_write(
                "POST", self.url("/api/campaigns/327/leads/attach-leads"))

    def test_a_read_of_a_sealed_campaign_is_not_refused(self):
        """Acceptance 6. These three stay fully READABLE: provider truth about
        a sealed campaign is exactly what anybody reasoning about it needs."""
        from src import providers
        for provider, _row in SEALED:
            with self.subTest(campaign=provider):
                providers.refuse_unauthorized_write(
                    "GET", self.url("/api/campaigns/%s" % provider))

    def test_a_lead_whose_id_reads_like_a_sealed_campaign_is_not_refused(self):
        from src import providers
        with self.scope():
            providers.refuse_unauthorized_write(
                "PATCH", self.url("/api/leads/487"))

    def test_the_url_parser_only_reads_a_campaign_segment(self):
        from src import providers
        self.assertEqual(
            providers.campaign_in_url(self.url("/api/campaigns/487/pause")),
            "487")
        self.assertEqual(
            providers.campaign_in_url(self.url("/api/campaigns/0487/pause")),
            "487")
        self.assertIsNone(providers.campaign_in_url(
            self.url("/api/leads/487")))
        self.assertIsNone(providers.campaign_in_url(
            self.url("/api/campaigns")))
        self.assertIsNone(providers.campaign_in_url(
            self.url("/api/senders/487/campaigns")))

    def test_the_wire_check_reads_the_same_one_table(self):
        """One list, two enforcement points. Emptying the table unseals both,
        which is what makes it one list rather than two."""
        from src import providers
        real = providerwrites.sealed_campaigns
        providerwrites.sealed_campaigns = lambda: {}
        self.addCleanup(setattr, providerwrites, "sealed_campaigns", real)
        with self.scope():
            providers.refuse_unauthorized_write(
                "PATCH", self.url("/api/campaigns/487/pause"))

    def test_an_unreadable_table_refuses_rather_than_admits(self):
        """Fail closed. "The import failed" is not evidence of safety."""
        from src import providers

        def explode():
            raise RuntimeError("the seal cannot be read")

        real = providerwrites.sealed_campaigns
        providerwrites.sealed_campaigns = explode
        self.addCleanup(setattr, providerwrites, "sealed_campaigns", real)
        with self.scope():
            with self.assertRaises(providers.ProviderWriteRefused) as caught:
                providers.refuse_unauthorized_write(
                    "PATCH", self.url("/api/campaigns/327/pause"))
        self.assertIn("could not be read", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
