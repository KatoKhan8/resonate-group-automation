#!/usr/bin/env python3
"""The scope of `sending.live = off`: it blocks OUR new writes and nothing else.

Written for the operator's decision of 2026-09-27 (Zvonimir), which authorised
turning `sending.live` off for `productive` only after its scope was proved.
Two claims had to be separated, because conflating them is how an operator
believes a switch does something it cannot:

  WHAT IT DOES.   Every new provider write this system performs asks
                  `killswitch.workspace_state(client)` first and refuses when
                  the answer is off. Proved here through the real
                  `heyreachfactory.ensure_leads` entrypoint, with the provider
                  transport booby-trapped so that a refusal arriving AFTER a
                  network call fails the test rather than passing quietly.

  WHAT IT CANNOT DO. It does not and cannot touch a campaign already sending
                  at the provider - 487, 489 and 493. The switch is read at the
                  moment this system tries to START an action; EmailBison's own
                  scheduler is not reading it. `executionguard` says the same in
                  its own words at the stoppability gate: "The killswitch
                  refuses to START an action. It cannot END a campaign that is
                  already running." So flipping it is not a pause, must never be
                  reported as one, and - proved here - performs zero provider
                  requests of its own.

WHY THE EMAILBISON PATH IS NOT THE ONE UNDER TEST. On master at `1f4d464c`,
`bisonfactory.stage` is refused by the sequence gate before the killswitch is
ever consulted (the `6fa49014` defect, TASK-426). That refusal is also
fail-closed, so nothing reaches a provider either way - but it means the
EmailBison path cannot currently demonstrate the killswitch as the refusing
gate, and a test claiming otherwise would be passing for the wrong reason.
`tests/test_lead_writes_respect_the_killswitch.py` is that path's proof and it
is red for exactly this reason; TASK-426's acceptance check is that it goes
green. HeyReach's gate 1 IS the killswitch, before `_plan` and before any
transport, so the proof is taken there.
"""
import unittest
from unittest import mock

from src import campaigns, heyreachfactory, killswitch, providers, workspaces
from tests.base import QueueTest

# The provider ids that are ACTIVE at EmailBison and must not be touched by
# anything in this module. Per docs/state/PROVIDER-CAMPAIGNS.json and the
# standing freeze: 493 is sending, 489 has sent, 487 is active with 0 sent.
ALREADY_SENDING_AT_THE_PROVIDER = (487, 489, 493)


class NoProviderRequestWasMade(AssertionError):
    """The transport was reached. For this module that is always a failure."""


class SendingLiveOffScope(QueueTest):

    def setUp(self):
        super().setUp()
        # THE BOOBY TRAP. `providers.request` is the single chokepoint every
        # provider module goes through, and `set_transport` is its seam. Any
        # call at all raises, so "the refusal preceded the network" is proved
        # by the absence of an exception from here rather than asserted.
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise NoProviderRequestWasMade(
                f"a provider request was made: {method} {url}. Nothing in "
                f"this module may reach a provider")

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # A canonical campaign for the tenant under test. `ensure_leads`
        # requires a client, because every provider write is tenant-bound.
        row = campaigns.new_campaign("cmp-scope-1", "productive", "Scope test")
        campaigns.save([row])

    def _set_sending_live(self, value):
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": value}}
        workspaces.save([ws])

    # ------------------------------------------------------- what it DOES

    def test_off_refuses_a_new_linkedin_write_before_the_transport(self):
        """A new write is refused, and the refusal names the killswitch.

        The booby-trapped transport is what makes this more than an exception
        check: if the refusal arrived after a provider call, the call would
        raise `NoProviderRequestWasMade` and this test would fail.
        """
        self._set_sending_live("off")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory.ensure_leads("cmp-scope-1", live=True)
        self.assertIn("killswitch", str(caught.exception).lower())
        self.assertIn("off", str(caught.exception).lower())
        self.assertEqual([], self.requests,
                         "the killswitch refused only AFTER reaching the "
                         "provider transport")

    def test_absence_refuses_too_because_absence_is_not_permission(self):
        """No workspace row at all is the same as off.

        The failure this prevents is a tenant created for a demo where nobody
        remembers whether the switch was set.
        """
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory.ensure_leads("cmp-scope-1", live=True)
        self.assertIn("killswitch", str(caught.exception).lower())
        self.assertEqual([], self.requests)

    def test_the_killswitch_is_what_refuses_and_not_a_later_gate(self):
        """Bypass the killswitch and THIS refusal disappears.

        Without this, the two tests above would pass just as happily if some
        later gate were doing the work and the killswitch were inert - which is
        the exact defect TASK-426 exposed on the EmailBison path, where the
        sequence gate refuses first and the killswitch is never consulted.

        Asserting only "no killswitch in the message" would not be enough: with
        no pushable contacts `ensure_leads` can return a report having done
        nothing, and a test that accepts that passes without the bypass having
        changed anything. So what is measured is how FAR execution got.
        `_plan` is the first thing after gate 1, so whether it was called is
        exactly the question "did gate 1 stop this".
        """
        self._set_sending_live("off")
        reached = []
        real_plan = heyreachfactory._plan

        def spy(*a, **kw):
            reached.append(True)
            return real_plan(*a, **kw)

        # Gate 1 off: execution must not reach `_plan` at all.
        with mock.patch.object(heyreachfactory, "_plan", spy):
            with self.assertRaises(heyreachfactory.FactoryRefused):
                heyreachfactory.ensure_leads("cmp-scope-1", live=True)
        self.assertEqual([], reached,
                         "execution passed gate 1 while the killswitch was off")

        # Gate 1 bypassed: execution must get past it. If it does not, the two
        # tests above are not proving the killswitch is what refuses.
        permissive = lambda slug, rows=None: {
            "layer": killswitch.WORKSPACE, "label": "This workspace",
            "sending": True, "why": "bypassed for this test only"}
        with mock.patch("src.killswitch.workspace_state", permissive), \
                mock.patch.object(heyreachfactory, "_plan", spy):
            try:
                heyreachfactory.ensure_leads("cmp-scope-1", live=True)
            except heyreachfactory.FactoryRefused as e:
                self.assertNotIn(
                    "killswitch", str(e).lower(),
                    "the killswitch still refused while bypassed, so these "
                    "tests do not prove the killswitch is load-bearing")
        self.assertEqual([True], reached,
                         "with the killswitch bypassed execution still did not "
                         "reach `_plan`, so gate 1 is not what stops it and "
                         "these tests prove nothing about the killswitch")
        self.assertEqual([], self.requests,
                         "bypassing the killswitch reached a provider")

    # ----------------------------------------------------- what it CANNOT do

    def test_turning_it_off_makes_no_provider_request_at_all(self):
        """The flip is a local policy write. It is not a pause.

        This is the half an operator most needs to be true: turning the switch
        off must not itself touch the estate. If `set_policy` ever grew a
        provider call, the booby-trapped transport fails this test.
        """
        self._set_sending_live("on")
        before, after = workspaces.set_policy(
            "productive", {"sending.live": "off"},
            actor="Zvonimir 2026-09-27")
        self.assertEqual("on", before.get("sending.live"))
        self.assertEqual("off", after.get("sending.live"))
        self.assertEqual([], self.requests,
                         "turning the killswitch off made a provider request")

    def test_it_does_not_change_the_state_of_campaigns_already_sending(self):
        """487, 489 and 493 are untouched, and that is a property not a hope.

        The canonical rows for the three provider campaigns that are ACTIVE at
        EmailBison are snapshotted, the switch is turned off, and a new write is
        attempted and refused. Nothing about those three rows may differ, and no
        provider request may have been made - because the killswitch cannot
        reach a campaign that is already running, and reporting the flip as a
        pause would be claiming a control this system does not have.
        """
        rows = campaigns.load()
        for provider_id in ALREADY_SENDING_AT_THE_PROVIDER:
            rows.append(campaigns.new_campaign(
                f"cmp-live-{provider_id}", "productive",
                f"RESONATE live {provider_id}"))
            rows[-1]["provider_campaign_id"] = provider_id
            rows[-1]["status"] = campaigns.RUNNING
        campaigns.save(rows)

        def snapshot():
            loaded = campaigns.load()
            return {c.get("provider_campaign_id"): dict(c) for c in loaded
                    if c.get("provider_campaign_id")
                    in ALREADY_SENDING_AT_THE_PROVIDER}

        before = snapshot()
        self.assertEqual(len(ALREADY_SENDING_AT_THE_PROVIDER), len(before),
                         "the three live campaigns were not set up")

        self._set_sending_live("off")
        with self.assertRaises(heyreachfactory.FactoryRefused):
            heyreachfactory.ensure_leads("cmp-scope-1", live=True)

        self.assertEqual(before, snapshot(),
                         "turning the killswitch off changed a campaign that "
                         "is already sending at the provider")
        self.assertEqual([], self.requests)

    def test_it_is_a_start_control_and_reports_itself_as_one(self):
        """The workspace verdict describes a permission, not a stop action.

        `workspace_state` answers "may this tenant start something", and the
        distinction is load-bearing for what an operator is told: off means no
        NEW write, it does not mean the estate went quiet.
        """
        self._set_sending_live("off")
        verdict = killswitch.workspace_state("productive")
        self.assertFalse(verdict["sending"])
        self.assertEqual(killswitch.WORKSPACE, verdict["layer"])
        # The full report still evaluates every layer, so an operator can see
        # that the global refusal is what stops an actual send.
        full = killswitch.state(workspace="productive")
        self.assertFalse(full["sending"])
        self.assertIn(killswitch.WORKSPACE,
                      [r["layer"] for r in full["layers"] if not r["sending"]])
        self.assertEqual([], self.requests)


if __name__ == "__main__":
    unittest.main()
