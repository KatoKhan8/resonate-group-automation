#!/usr/bin/env python3
"""One canonical plan, two providers, and a mutation that reaches both.

TASK-364 REWORK 2. The plan is built FIRST, from STRATEGY (the cadence this
campaign declared) and COPY (the client's declared templates). Both provider
payloads are projections OF it.

WHY THIS FILE EXISTS AND WHAT IT REFUSES TO REPEAT. The second attempt at this
task built the derivation BACKWARDS: each factory built its provider sequence
first and then generated a "canonical plan" from the result. Its consistency
test called `sequenceplan.derive_*` on a plan it had built itself, which proves
only that the derive functions agree with each other - a question nobody asked.
Because the plan was generated FROM the sequence, the two could not disagree, a
mutation of the plan could not change either payload, and the test was green by
construction.

So every assertion here goes through a REAL factory entry point -
`bisonfactory.stage` and `heyreachfactory.stage` - and the three questions are:

  1. Is the payload the factory produces exactly the projection of the plan
     that this test built, independently, from the campaign row and the client
     config? (`derive_bison_sequence`, `derive_heyreach_sequence`.)

  2. Does a change to the canonical plan change BOTH payloads?

  3. Would this still pass if a factory built its own sequence? The LinkedIn
     half answers that one directly. Until this task, the HeyReach message
     delays came from the module constant `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`
     whatever the campaign declared, so the cadence below - which no library
     declares, and whose LinkedIn gaps are 6/7/8 rather than the ladder's
     3/4/5 - produces a graph that a factory building its own sequence CANNOT
     produce. That test fails against a factory that builds, and passes only
     against one that projects.

THE CADENCE IS DELIBERATELY UNLIKE EVERY DECLARED ONE. Days, gaps and waits
are chosen so that nothing in the repository - no ladder, no client file, no
default - carries them. A projection can only get them from the plan.

NO PROVIDER IS TOUCHED. The EmailBison transport is `FakeBison`, the HeyReach
transport is a fake that records what would have been written and delegates
every pure function to the real module, so the graph is validated by the real
`validate_sequence_for_write` and only the wire is fake.
"""
import copy as copy_mod
import unittest

from src import (approval, bisonfactory, campaigns, heyreachfactory, icp,
                 sequenceplan, store, workspaces)
from src.providers import heyreach as real_heyreach
from src.providers.bison import MAX_SEQUENCE_STEPS
from tests import packfixture
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

COMPANY = "Northwind"
DOMAIN = "northwind.test"

# THE STRATEGY HALF. Five email steps and five LinkedIn steps, on days no
# declared cadence uses. The email gaps are 5, 7, 6, 11; the LinkedIn
# inter-message gaps are 6, 7, 8 - the canonical ladder's are 3, 4, 5.
EMAIL_DAYS = (1, 6, 13, 19, 30)
EMAIL_WAITS = (5, 7, 6, 11)
LINKEDIN_DAYS = (1, 5, 11, 18, 26)
LINKEDIN_GAPS = (6, 7, 8)

# The last wait has no successor and is inert, but 0 is not accepted by the
# provider: campaign 485 was created and `set_sequence` raised, leaving it at
# 0 steps.
FINAL_WAIT = 1

# THE SECOND CADENCE, for the mutation. One edit to the strategy moves the
# fourth email step and the fourth LinkedIn step, so both channels' payloads
# have to move with it.
MUTATED_EMAIL_DAYS = (1, 6, 13, 24, 30)
MUTATED_EMAIL_WAITS = (5, 7, 11, 6)
MUTATED_LINKEDIN_DAYS = (1, 5, 11, 22, 26)
MUTATED_LINKEDIN_GAPS = (6, 11, 4)

OPENER_SUBJECT = "{SUBJECT_1}"

LINKEDIN_ACTIONS = ("connect", "message", "message", "message", "message")

# One fallback per role. The client's own words, never invented here, and
# never anything true of one person: HeyReach sends the fallback when a
# per-lead variable cannot be filled, and the graph is campaign-level.
FALLBACKS = {
    "connection_note": "Would like to connect about delivery planning.",
    "connected_1": "Thanks for connecting - how is delivery planned today?",
    "connected_2": "Most teams see margin at month end rather than during.",
    "connected_3": "Happy to share what similar teams changed first.",
    "connected_4": "Last note from me, and thank you for the time.",
    "message_2": "Thanks for connecting - how is delivery planned today?",
    "message_3": "Most teams see margin at month end rather than during.",
    "message_4": "Happy to share what similar teams changed first.",
}


def cadence_steps(email_days=EMAIL_DAYS, linkedin_days=LINKEDIN_DAYS):
    """The campaign's declared cadence: both channels, in day order.

    `cadence.validate_steps` requires ascending days across the whole
    sequence, so the two channels are interleaved rather than concatenated.
    """
    steps = []
    for position, day in enumerate(email_days, start=1):
        steps.append({"key": f"em{position}", "day": day, "channel": "email",
                      "generated": True})
    for position, day in enumerate(linkedin_days, start=1):
        steps.append({"key": f"li{position}", "day": day,
                      "channel": "linkedin",
                      "linkedin_action": LINKEDIN_ACTIONS[position - 1],
                      "generated": True})
    steps.sort(key=lambda s: (s["day"], s["channel"]))
    return steps


def client_config(waits=EMAIL_WAITS, final_wait=FINAL_WAIT):
    """THE COPY HALF: per-step email templates and per-role LinkedIn fallbacks.

    Every body is a merge field. The words travel per lead; the campaign-level
    artifact says nothing about one person.
    """
    all_waits = list(waits) + [final_wait]
    steps = {}
    for position, wait in enumerate(all_waits, start=1):
        steps[f"em{position}"] = {"order": position,
                                  "subject": OPENER_SUBJECT,
                                  "body": f"<p>{{BODY_{position}}}</p>",
                                  "wait_in_days": wait}
    return {
        "name": "Northwind test",
        "email_sequence": {
            "title": "One plan, two providers",
            "thread_reply_pattern": [False, True, True, True, True],
            "steps": steps,
        },
        "linkedin_sequence": {"fallbacks": dict(FALLBACKS)},
        "sending_window": {"days": ["monday", "tuesday", "wednesday",
                                    "thursday", "friday"],
                           "start": "09:00", "end": "17:00",
                           "timezone": "Europe/Zagreb"},
        "providers": {"emailbison": {"workspace": 10}},
    }


def _stamp(step):
    """An accountable approval taken over this step's own words."""
    step["approval"] = {"by": "operator", "at": "2026-09-27T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return step


def _email_step(key, first):
    """One approved email step.

    The opener is held to the copy lint's bar, and the four follow-ups come
    from `packfixture` - one argument each, none repeating another - because
    `sequencegate`'s `followup_adds_value` check is on this path and is right
    to refuse a sequence of paraphrases. Shared rather than retyped so this
    module cannot drift from the others that stage a five-step campaign.
    """
    body = (packfixture.html_opener(first, COMPANY) if key == "em1"
            else packfixture.html_followup(key))
    return _stamp({"channel": "email", "subject": f"subject for {key}",
                   "body": body})


LINKEDIN_NOTES = {
    "li1": "Noticed your delivery work - would like to connect.",
    "li2": "Thanks for connecting. How is project planning handled now?",
    "li3": "One thought: margin is usually visible only at month end.",
    "li4": "Teams close to your size stop reconciling hours after the fact.",
    "li5": "Happy to share a short case study if that is useful.",
}


def _linkedin_step(key, day, action):
    """One approved LinkedIn step, shaped as the store holds it."""
    return _stamp({"key": key, "day": day, "channel": "linkedin",
                   "linkedin_action": action, "generated": True,
                   "note": LINKEDIN_NOTES[key]})


def record(rid, email, first, linkedin_days=LINKEDIN_DAYS):
    """One record with approved copy for every step of both channels."""
    key = f"{rid}-c1"
    steps = {f"em{n}": _email_step(f"em{n}", first) for n in range(1, 6)}
    for position, day in enumerate(linkedin_days, start=1):
        steps[f"li{position}"] = _linkedin_step(
            f"li{position}", day, LINKEDIN_ACTIONS[position - 1])
    return {"id": rid, "client": "productive", "domain": DOMAIN,
            "company": COMPANY, "state": "ready",
            # AND THE ICP VERDICT. `bisonfactory._plan` reads
            # `qualify.state_of` per lead and the sequence gate refuses an
            # absent one by design - a record this system never qualified is
            # not a qualified record. A record that reached approved copy in
            # production carries a verdict, so a fixture without one is the
            # fixture being unrealistic rather than the gate being wrong.
            "qualification": {"verdict": {"icp_status": icp.QUALIFIED}},
            "research": [packfixture.own_fact(rid, DOMAIN, COMPANY)],
            "cadence": {key: steps},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True,
                          "linkedin": f"https://www.linkedin.com/in/{key}"}]}


class FakeHeyReach:
    """The HeyReach wire, recorded. Every pure function is the real one.

    `set_sequence` and `campaign_sequence` are the only transports the staging
    path touches, so they are the only two faked. Everything else - `_node`,
    `_copy`, `validate_sequence_for_write`, `sequence_matches`, the node type
    constants - delegates to the real module, so the graph this records was
    validated by the code that validates a real one.
    """

    def __init__(self):
        self.written = []
        self.held = {}

    def set_sequence(self, campaign_id, sequence):
        self.written.append((int(campaign_id), copy_mod.deepcopy(sequence)))
        self.held[int(campaign_id)] = copy_mod.deepcopy(sequence)
        return {"status": "ok"}

    def campaign_sequence(self, campaign_id):
        return copy_mod.deepcopy(self.held.get(int(campaign_id)) or {})

    def __getattr__(self, name):
        return getattr(real_heyreach, name)


class ThePlanIsBuiltFromStrategyAndCopy(unittest.TestCase):
    """The plan carries the cadence's shape and the client's words. No leads.

    Nothing in this class touches a provider or a lead. That is the point: the
    plan exists before either, and it is what the payloads are made from.
    """

    def plan(self, **kw):
        row = {"campaign_id": "c1", "client": "productive",
               "cadence_steps": cadence_steps(**kw)}
        return sequenceplan.for_campaign(row, client_config())

    def test_the_email_steps_carry_the_cadences_days_and_the_configs_waits(self):
        steps = [s for s in self.plan()["steps"] if s["channel"] == "email"]
        self.assertEqual([s["step_key"] for s in steps],
                         ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual([s["day"] for s in steps], list(EMAIL_DAYS))
        self.assertEqual(tuple(s["wait_in_days"] for s in steps[:-1]),
                         EMAIL_WAITS)

    def test_the_linkedin_message_gaps_come_from_this_campaigns_cadence(self):
        plan = self.plan()
        self.assertEqual(plan["linkedin"]["message_delays"],
                         list(LINKEDIN_GAPS))
        self.assertEqual(plan["linkedin"]["delays_from"], "campaign_cadence")

    def test_a_declared_wait_that_does_not_reproduce_the_cadence_is_refused(self):
        """The plan is checked against the strategy, not trusted."""
        row = {"campaign_id": "c1", "client": "productive",
               "cadence_steps": cadence_steps()}
        config = client_config()
        config["email_sequence"]["steps"]["em2"]["wait_in_days"] = 99
        plan = sequenceplan.for_campaign(row, config)
        with self.assertRaises(sequenceplan.PlanRefused) as caught:
            sequenceplan.derive_bison_sequence(plan,
                                               max_steps=MAX_SEQUENCE_STEPS)
        self.assertIn("em2", str(caught.exception))

    def test_a_cadence_with_no_room_between_messages_is_refused(self):
        """Two message nodes a day apart or less send twice at once."""
        with self.assertRaises(sequenceplan.PlanRefused):
            self.plan(linkedin_days=(1, 5, 11, 11, 26))


class BothProviderPayloadsAreProjectionsOfOnePlan(QueueTest):
    """The whole path, through both factory entry points, against fakes."""

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        real_bison = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", real_bison)
        self.heyreach = FakeHeyReach()
        real_module = heyreachfactory.heyreach
        heyreachfactory.heyreach = self.heyreach
        self.addCleanup(setattr, heyreachfactory, "heyreach", real_module)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    # ------------------------------------------------------------ fixtures

    def estate(self, campaign_id, *, email_days=EMAIL_DAYS,
               linkedin_days=LINKEDIN_DAYS, provider_campaign=900001):
        """One campaign row and its records, declared not inherited."""
        store.save([record("rec-1", "one@northwind.test", "Ada",
                           linkedin_days=linkedin_days),
                    record("rec-2", "two@northwind.test", "Grace",
                           linkedin_days=linkedin_days)])
        row = campaigns.new_campaign(campaign_id, "productive", "One plan")
        row["cadence_steps"] = cadence_steps(email_days=email_days,
                                             linkedin_days=linkedin_days)
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        row["heyreach_campaign_id"] = str(provider_campaign)
        campaigns.save([row])
        return row

    def canonical_plan(self, row, config):
        """The plan this test builds, from the same two inputs the factories
        read, without going through either of them."""
        return sequenceplan.for_campaign(row, config)

    # ---------------------------------------------------- the two payloads

    def test_the_email_payload_is_the_plans_projection(self):
        """Dry run: the sequence the write path will send is the projection.

        The dry run is a real entry point - it is the one an operator runs -
        and its report carries what the live write would send.
        """
        row = self.estate("camp-one-plan-email")
        config = client_config()
        report = bisonfactory.stage("camp-one-plan-email", config=config,
                                    live=False)
        plan = self.canonical_plan(row, config)
        self.assertEqual(
            report["plan"]["provider_sequence"],
            sequenceplan.derive_bison_sequence(plan,
                                               max_steps=MAX_SEQUENCE_STEPS))
        self.assertEqual(report["plan"]["sequence_plan"], plan)

    def test_the_linkedin_payload_is_the_plans_projection(self):
        row = self.estate("camp-one-plan-li")
        config = client_config()
        report = heyreachfactory.stage("camp-one-plan-li", config=config,
                                       live=False)
        plan = self.canonical_plan(row, config)
        graph, _report = sequenceplan.derive_heyreach_sequence(plan)
        self.assertEqual(report["plan"]["provider_sequence"], graph)
        self.assertEqual(report["plan"]["sequence_plan"], plan)

    def test_neither_plan_still_carries_the_retired_sequence_key(self):
        """`plan["sequence"]` was the artifact the write paths used to read.

        It is retired rather than renamed: while it exists, a write path can
        read a sequence that nothing derived from the plan, which is the
        defect this task is about. Asserted on what the factories RETURN.
        """
        self.estate("camp-one-plan-retired")
        config = client_config()
        email = bisonfactory.stage("camp-one-plan-retired", config=config,
                                   live=False)
        linkedin = heyreachfactory.stage("camp-one-plan-retired",
                                         config=config, live=False)
        self.assertNotIn("sequence", email["plan"])
        self.assertNotIn("sequence", linkedin["plan"])

    def test_the_graph_carries_this_campaigns_own_message_gaps(self):
        """THE FALSIFIER. A factory building its own graph cannot pass this.

        The delays used to come from `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`
        - 3, 4 and 5 days - whatever the campaign declared. This campaign
        declares 6, 7 and 8, and no library, client file or default carries
        them, so a graph holding them can only have been projected from this
        campaign's plan.
        """
        self.estate("camp-one-plan-gaps")
        report = heyreachfactory.stage("camp-one-plan-gaps",
                                       config=client_config(), live=False)
        delays = self.message_delays(report["plan"]["provider_sequence"])
        self.assertEqual(delays, list(LINKEDIN_GAPS))
        self.assertNotEqual(delays, list(sequenceplan.canonical_message_delays()))

    def message_delays(self, graph):
        """The already-connected branch's inter-message delays, in days.

        Read off the graph the provider is handed, not off the plan: the
        question is what the payload says. The branch is
        MESSAGE -> MESSAGE(d1) -> VIEW_PROFILE(2) -> MESSAGE(d2-2) ->
        MESSAGE(d3), so the second gap is the view plus the message.
        """
        node = (graph or {}).get("conditionalNode")
        delays, pending = [], 0
        while isinstance(node, dict):
            kind = node.get("nodeType")
            delay = int(node.get("actionDelay") or 0)
            unit = str(node.get("actionDelayUnit") or "").upper()
            days = delay if unit == "DAY" else 0
            if kind == "MESSAGE":
                if delays or days or pending:
                    if days or pending:
                        delays.append(days + pending)
                pending = 0
            else:
                pending += days
            node = node.get("unconditionalNode")
        return delays

    # ------------------------------------------------------- the mutation

    def test_mutating_the_plan_changes_both_provider_payloads(self):
        """One edit to the canonical plan, and both payloads move with it.

        The mutation is applied where the plan is made - the campaign's own
        cadence and the client's declared waits - and it is the SAME edit for
        both channels: the fourth step of each moves. Both projections change,
        and each factory emits its channel's new projection.

        This is the assertion attempt 2 could not make. Its plan was generated
        from the built sequence, so a mutation of the plan changed nothing.
        """
        first_row = self.estate("camp-one-plan-before")
        first_config = client_config()
        first_plan = self.canonical_plan(first_row, first_config)
        before_email = bisonfactory.stage("camp-one-plan-before",
                                          config=first_config, live=False)
        before_li = heyreachfactory.stage("camp-one-plan-before",
                                          config=first_config, live=False)

        second_row = self.estate("camp-one-plan-after",
                                 email_days=MUTATED_EMAIL_DAYS,
                                 linkedin_days=MUTATED_LINKEDIN_DAYS,
                                 provider_campaign=900002)
        second_config = client_config(waits=MUTATED_EMAIL_WAITS)
        second_plan = self.canonical_plan(second_row, second_config)
        after_email = bisonfactory.stage("camp-one-plan-after",
                                         config=second_config, live=False)
        after_li = heyreachfactory.stage("camp-one-plan-after",
                                         config=second_config, live=False)

        # The plan changed in both channels.
        self.assertNotEqual(first_plan["steps"], second_plan["steps"])
        self.assertEqual(second_plan["linkedin"]["message_delays"],
                         list(MUTATED_LINKEDIN_GAPS))

        # Both projections changed.
        self.assertNotEqual(
            sequenceplan.derive_bison_sequence(first_plan,
                                               max_steps=MAX_SEQUENCE_STEPS),
            sequenceplan.derive_bison_sequence(second_plan,
                                               max_steps=MAX_SEQUENCE_STEPS))
        self.assertNotEqual(
            sequenceplan.derive_heyreach_sequence(first_plan)[0],
            sequenceplan.derive_heyreach_sequence(second_plan)[0])

        # And both factories emit the new one, each equal to its projection.
        self.assertNotEqual(before_email["plan"]["provider_sequence"],
                            after_email["plan"]["provider_sequence"])
        self.assertNotEqual(before_li["plan"]["provider_sequence"],
                            after_li["plan"]["provider_sequence"])
        self.assertEqual(
            after_email["plan"]["provider_sequence"],
            sequenceplan.derive_bison_sequence(second_plan,
                                               max_steps=MAX_SEQUENCE_STEPS))
        self.assertEqual(after_li["plan"]["provider_sequence"],
                         sequenceplan.derive_heyreach_sequence(second_plan)[0])
        self.assertEqual(
            self.message_delays(after_li["plan"]["provider_sequence"]),
            list(MUTATED_LINKEDIN_GAPS))

    # --------------------------------------------------------- to the wire

    def test_the_graph_that_reaches_the_heyreach_transport_is_the_projection(self):
        """Live, through `providerwrites.perform`, against a recorded wire."""
        row = self.estate("camp-one-plan-wire")
        config = client_config()
        heyreachfactory.stage("camp-one-plan-wire", config=config, live=True)
        plan = self.canonical_plan(row, config)
        graph, _report = sequenceplan.derive_heyreach_sequence(plan)
        self.assertEqual([written for _cid, written in self.heyreach.written],
                         [graph])

    def test_the_sequence_that_reaches_emailbison_is_the_projection(self):
        """Live, through the real staging order, against `FakeBison`.

        TWO COMPARISONS, AND THE SECOND ONE IS THE HONEST ONE. Comparing the
        payload to `derive_bison_sequence` proves the factory reads the
        projection and nothing else - but a bug INSIDE the projection would
        appear on both sides of that equality and pass. So the numbers are
        also compared against this cadence's own gaps, written out at the top
        of this module rather than derived: strategy says 5, 7, 6, 11, and
        that is what the provider must hold.
        """
        row = self.estate("camp-one-plan-email-wire")
        config = client_config()
        report = bisonfactory.stage("camp-one-plan-email-wire", config=config,
                                    live=True)
        plan = self.canonical_plan(row, config)
        wanted = sequenceplan.derive_bison_sequence(
            plan, max_steps=MAX_SEQUENCE_STEPS)
        held = self.bison.sequence_steps(report["provider"]["campaign_id"])
        self.assertEqual(
            [(s["email_subject"], s["email_body"], s["wait_in_days"],
              bool(s.get("thread_reply"))) for s in held],
            [(s["email_subject"], s["email_body"], s["wait_in_days"],
              bool(s.get("thread_reply"))) for s in wanted])
        self.assertEqual(tuple(s["wait_in_days"] for s in held[:-1]),
                         EMAIL_WAITS)
        self.assertEqual(held[-1]["wait_in_days"], FINAL_WAIT)
        self.assertEqual([bool(s.get("thread_reply")) for s in held],
                         [False, True, True, True, True])
        self.assertEqual({s["email_subject"] for s in held},
                         {OPENER_SUBJECT})


if __name__ == "__main__":
    unittest.main()
