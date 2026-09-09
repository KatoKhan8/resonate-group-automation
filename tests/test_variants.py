"""Five ways to say the same true thing, and how we decide which works.

The three properties every test here is really about:

**Determinism.** The same planned touch resolves to the same variant on
every read. A random draw would move somebody from A to D on a page
refresh, and the assignment would then be a property of when it was looked
at rather than of who they are.

**History is immutable.** Optimisation moves *future* traffic. A recorded
assignment outranks the deterministic function, so shifting the allocation
tomorrow cannot rewrite who was in which cell yesterday - which is the only
thing that keeps the rates honest.

**No rosette on noise.** Four replies against three is not a winner. The
evaluator has to say `no_clear_winner` there, and has to keep saying
`insufficient_data` until it has enough of both exposures and outcomes.
"""
import unittest

from src import account, accountpolicy as ap, events, store, variants as V
from tests.campaignbase import CampaignTest

WS = "productive"
CAMPAIGN = "camp-1"
JOHN, SARAH = "john", "sarah"

STYLES = ("short_direct", "casual", "professional", "consultative",
          "problem_led")


def five(prefix="v", node_type="email"):
    """A full experiment: five complete variants in this channel's styles."""
    styles = (STYLES if node_type == "email"
              else ("casual", "short_direct", "professional", "consultative",
                    "peer_to_peer"))
    return [V.variant(f"{prefix}{i}", style,
                      subject=f"subject {i}", body=f"body {i}")
            for i, style in enumerate(styles, start=1)]


def node(key="d1", node_type="email", entries=None, **extra):
    return {"key": key, "type": node_type, "label": key,
            "variants": entries if entries is not None else five(),
            **extra}


class TheExperimentShape(unittest.TestCase):

    def test_five_variants_are_supported_on_every_message_step(self):
        for kind in V.MESSAGE_NODES:
            entries = five(node_type=kind)
            self.assertEqual(len(entries), V.MINIMUM_VARIANTS, kind)
            self.assertEqual(V.validate(node(node_type=kind,
                                             entries=entries)), [], kind)

    def test_the_model_does_not_cap_at_five(self):
        entries = five() + [V.variant("v6", "casual", subject="s", body="b")]
        self.assertEqual([f for f in V.validate(node(entries=entries))
                          if f["level"] == "block"], [])

    def test_fewer_than_five_warns_rather_than_blocks(self):
        entries = five()[:3]
        levels = [f["level"] for f in V.validate(node(entries=entries))]
        self.assertIn("warn", levels)
        self.assertNotIn("block", levels)

    def test_a_wait_cannot_carry_variants(self):
        found = V.validate(node(node_type="wait"))
        self.assertTrue(any(f["level"] == "block" for f in found))

    def test_control_flow_nodes_are_not_message_nodes(self):
        for kind in ("wait", "branch", "reply_check", "connection_check",
                     "stop", "handoff", "dm_handoff"):
            self.assertNotIn(kind, V.MESSAGE_NODES, kind)

    def test_a_variant_with_no_copy_is_refused(self):
        entries = five()
        entries[2] = V.variant("v3", "professional")
        found = V.validate(node(entries=entries))
        self.assertTrue(any("no copy" in f["why"] for f in found))

    def test_duplicate_ids_are_refused(self):
        entries = five()
        entries[1] = V.variant("v1", "casual", subject="s", body="b")
        found = V.validate(node(entries=entries))
        self.assertTrue(any("share the id" in f["why"] for f in found))

    def test_style_is_stored_not_only_a_letter(self):
        """The letter is not the finding; the approach is."""
        for entry in five():
            self.assertIn(entry["style"], V.EMAIL_STYLES)


class AssignmentIsDeterministic(unittest.TestCase):

    def test_the_same_contact_always_gets_the_same_variant(self):
        step = node()
        first = V.assign(step, CAMPAIGN, "contact-7")
        for _ in range(50):
            self.assertEqual(V.assign(step, CAMPAIGN, "contact-7"), first)

    def test_traffic_is_spread_evenly_by_default(self):
        step = node()
        counts = {}
        for i in range(5000):
            chosen = V.assign(step, CAMPAIGN, f"contact-{i}")
            counts[chosen] = counts.get(chosen, 0) + 1
        self.assertEqual(len(counts), 5)
        for variant_id, count in counts.items():
            self.assertGreater(count, 800, variant_id)
            self.assertLess(count, 1200, variant_id)

    def test_each_step_assigns_independently(self):
        """One contact must not sit in the same cell of every experiment."""
        pairs = [(V.assign(node("d1"), CAMPAIGN, f"c{i}"),
                  V.assign(node("d6"), CAMPAIGN, f"c{i}"))
                 for i in range(200)]
        self.assertTrue(any(a != b for a, b in pairs))

    def test_a_custom_allocation_is_honoured(self):
        entries = five()
        entries[0]["allocation"] = 0.6
        for entry in entries[1:]:
            entry["allocation"] = 0.1
        step = node(entries=entries)
        counts = {}
        for i in range(4000):
            chosen = V.assign(step, CAMPAIGN, f"contact-{i}")
            counts[chosen] = counts.get(chosen, 0) + 1
        self.assertGreater(counts["v1"], 2100)
        self.assertLess(counts["v1"], 2700)

    def test_an_allocation_that_does_not_sum_to_one_still_assigns_everybody(self):
        entries = five()
        for entry in entries:
            entry["allocation"] = 0.1          # sums to 0.5
        step = node(entries=entries)
        chosen = {V.assign(step, CAMPAIGN, f"c{i}") for i in range(500)}
        self.assertEqual(len(chosen), 5)

    def test_a_paused_variant_receives_no_traffic(self):
        entries = five()
        entries[0]["status"] = V.VARIANT_PAUSED
        step = node(entries=entries)
        chosen = {V.assign(step, CAMPAIGN, f"c{i}") for i in range(1000)}
        self.assertNotIn("v1", chosen)
        self.assertEqual(len(chosen), 4)


class HistoryIsNeverRewritten(unittest.TestCase):

    def test_a_recorded_assignment_outranks_the_function(self):
        step = node()
        computed = V.assign(step, CAMPAIGN, "contact-7")
        other = next(v for v in step["variants"]
                     if v["variant_id"] != computed)["variant_id"]
        resolved = V.resolve(step, CAMPAIGN, "contact-7", recorded=other)
        self.assertEqual(resolved["variant_id"], other)

    def test_shifting_traffic_does_not_move_an_assigned_contact(self):
        step = node()
        before = V.assign(step, CAMPAIGN, "contact-7")

        verdict = {"state": V.WINNER, "leader": "v1"}
        shifted = V.shifted_allocation(step, verdict)
        for entry in step["variants"]:
            entry["allocation"] = shifted[entry["variant_id"]]
        step["allocation_version"] = 2

        self.assertEqual(
            V.resolve(step, CAMPAIGN, "contact-7", recorded=before)
            ["variant_id"], before)

    def test_the_allocation_version_is_part_of_the_assignment(self):
        step = node()
        first = V.assign(step, CAMPAIGN, "contact-7")
        step["allocation_version"] = 2
        # Not required to differ for every contact, but the version must
        # reach the hash, or a re-allocation could never rebalance anybody.
        moved = [V.assign(step, CAMPAIGN, f"c{i}") != first
                 for i in range(50)]
        self.assertTrue(any(moved))


class TheEvaluatorRefusesToGuess(unittest.TestCase):

    def results(self, **counts):
        return {k: {"exposures": e, V.POSITIVE_REPLIES: o}
                for k, (e, o) in counts.items()}

    def test_before_the_first_checkpoint_it_is_exploring(self):
        out = V.evaluate(node(), self.results(v1=(10, 2)), progress=0.04)
        self.assertEqual(out["state"], V.EXPLORING)
        self.assertIsNone(out["leader"])
        self.assertIn("10%", out["why"])

    def test_the_checkpoint_alone_does_not_declare_a_winner(self):
        """10% is when we start looking, not when we decide."""
        out = V.evaluate(node(), self.results(
            v1=(4, 4), v2=(4, 3), v3=(4, 1), v4=(4, 0), v5=(4, 0)),
            progress=0.10)
        self.assertEqual(out["state"], V.INSUFFICIENT_DATA)

    def test_four_replies_against_three_is_not_a_winner(self):
        """The exact case the brief names."""
        out = V.evaluate(node(), self.results(
            v1=(40, 4), v2=(40, 3), v3=(40, 3), v4=(40, 2), v5=(40, 2)),
            progress=0.9)
        self.assertIn(out["state"], (V.LEADING, V.NO_CLEAR_WINNER))
        self.assertNotEqual(out["state"], V.WINNER)

    def test_a_small_sample_per_variant_blocks_a_winner(self):
        out = V.evaluate(node(), self.results(
            v1=(5, 5), v2=(5, 0), v3=(5, 0), v4=(5, 0), v5=(5, 0)),
            progress=0.9)
        self.assertEqual(out["state"], V.INSUFFICIENT_DATA)

    def test_a_clear_separation_is_a_winner(self):
        out = V.evaluate(node(), self.results(
            v1=(200, 40), v2=(200, 10), v3=(200, 9), v4=(200, 8),
            v5=(200, 10)), progress=0.9)
        self.assertEqual(out["state"], V.WINNER)
        self.assertEqual(out["leader"], "v1")

    def test_an_even_result_is_no_clear_winner(self):
        out = V.evaluate(node(), self.results(
            v1=(200, 10), v2=(200, 10), v3=(200, 10), v4=(200, 10),
            v5=(200, 10)), progress=0.9)
        self.assertEqual(out["state"], V.NO_CLEAR_WINNER)
        self.assertIsNone(out["leader"])

    def test_every_row_carries_its_denominator(self):
        out = V.evaluate(node(), self.results(
            v1=(200, 40), v2=(200, 10), v3=(200, 9), v4=(200, 8),
            v5=(200, 10)), progress=0.9)
        for row in out["rows"]:
            self.assertIn("exposures", row)
            self.assertIn("outcomes", row)
            self.assertIsNotNone(row["rate"])

    def test_the_thresholds_are_configurable(self):
        config = {"experiments": {"minimum_per_variant": 4,
                                  "minimum_outcomes": 4}}
        out = V.evaluate(node(), self.results(
            v1=(5, 5), v2=(5, 0), v3=(5, 0), v4=(5, 0), v5=(5, 0)),
            progress=0.9, config=config)
        self.assertNotEqual(out["state"], V.INSUFFICIENT_DATA)

    def test_the_default_objective_is_a_business_outcome(self):
        self.assertEqual(V.DEFAULT_OBJECTIVE, V.POSITIVE_REPLIES)
        for name in ("opens", "clicks"):
            self.assertNotIn(name, V.OBJECTIVES)

    def test_an_experiment_with_no_active_variants_is_paused(self):
        entries = five()
        for entry in entries:
            entry["status"] = V.VARIANT_PAUSED
        out = V.evaluate(node(entries=entries), {}, progress=0.9)
        self.assertEqual(out["state"], V.PAUSED)


class TrafficShiftsForwardOnly(unittest.TestCase):

    def test_a_winner_does_not_take_everything_by_default(self):
        """A variant that stops being served stops being measured."""
        verdict = {"state": V.WINNER, "leader": "v1"}
        shifted = V.shifted_allocation(node(), verdict)
        self.assertAlmostEqual(shifted["v1"], 0.75)
        self.assertAlmostEqual(sum(shifted.values()), 1.0, places=6)
        for key in ("v2", "v3", "v4", "v5"):
            self.assertGreater(shifted[key], 0.0, key)

    def test_hard_winner_mode_is_available_but_not_the_default(self):
        verdict = {"state": V.WINNER, "leader": "v1"}
        shifted = V.shifted_allocation(node(winner_takes_all=True), verdict)
        self.assertEqual(shifted["v1"], 1.0)
        self.assertEqual(shifted["v2"], 0.0)

    def test_nothing_shifts_without_a_winner(self):
        for state in (V.EXPLORING, V.INSUFFICIENT_DATA, V.LEADING,
                      V.NO_CLEAR_WINNER):
            shifted = V.shifted_allocation(node(), {"state": state,
                                                    "leader": "v1"})
            self.assertAlmostEqual(shifted["v1"], 0.2, msg=state)

    def test_the_winner_share_is_configurable(self):
        verdict = {"state": V.WINNER, "leader": "v1"}
        shifted = V.shifted_allocation(
            node(), verdict, config={"experiments": {"winner_share": 0.9}})
        self.assertAlmostEqual(shifted["v1"], 0.9)


class EditingAVariantInvalidatesItsApproval(unittest.TestCase):

    def test_the_fingerprint_moves_when_the_copy_moves(self):
        entry = V.variant("v1", "casual", subject="s", body="b")
        before = V.fingerprint(entry)
        entry["body"] = "b changed"
        self.assertNotEqual(V.fingerprint(entry), before)

    def test_the_fingerprint_moves_when_the_style_moves(self):
        entry = V.variant("v1", "casual", subject="s", body="b")
        before = V.fingerprint(entry)
        entry["style"] = "professional"
        self.assertNotEqual(V.fingerprint(entry), before)

    def test_applying_a_variant_replaces_only_the_copy(self):
        step = {"channel": "email", "day": 1, "subject": "old", "body": "old"}
        out = V.apply_to_step(step, V.variant("v2", "casual", subject="new",
                                              body="fresh"))
        self.assertEqual(out["subject"], "new")
        self.assertEqual(out["body"], "fresh")
        self.assertEqual(out["day"], 1)
        self.assertEqual(out["variant_id"], "v2")
        self.assertEqual(out["variant_style"], "casual")


class AttributionDoesNotOverclaim(CampaignTest):

    def record(self, rid="var-acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "email": "john@acme.test",
             "selected": True},
            {"key": SARAH, "name": "Sarah Jones", "email": "sarah@acme.test",
             "selected": True},
        ]
        store.save([rec])
        return rec

    def touch(self, rec, key, step, variant_id, at, style="casual"):
        events.record(rec, events.PUSH_MARKED, contact_key=key,
                      channel="email", step=step, at=at, sender_id="anna",
                      variant_id=variant_id, variant_style=style)

    def positive(self, rec, key, at):
        events.record(rec, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{key}")
        events.record(rec, events.POSITIVE_REPLY_DETECTED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{key}:p")

    def test_a_confirmed_touch_carries_its_variant(self):
        rec = self.record()
        self.touch(rec, JOHN, "d1", "v3", "2026-08-01T09:00:00+00:00")
        journey = V.journey_of(rec, JOHN)
        self.assertEqual(journey[0]["variant_id"], "v3")

    def test_a_planned_touch_is_not_an_exposure(self):
        """The rule the whole product rests on, here too."""
        rec = self.record()
        events.record(rec, events.PUSH_PREPARED, contact_key=JOHN,
                      channel="email", step="d1", variant_id="v3",
                      at="2026-08-01T09:00:00+00:00", sender_id="anna")
        self.assertEqual(V.journey_of(rec, JOHN), [])
        self.assertEqual(V.results_from([rec], "d1"), {})

    def test_the_whole_journey_is_preserved(self):
        rec = self.record()
        self.touch(rec, JOHN, "d1", "c", "2026-08-01T09:00:00+00:00")
        self.touch(rec, JOHN, "d3", "a", "2026-08-03T09:00:00+00:00")
        self.touch(rec, JOHN, "d6", "e", "2026-08-06T09:00:00+00:00")
        self.assertEqual([t["variant_id"] for t in V.journey_of(rec, JOHN)],
                         ["c", "a", "e"])

    def test_the_outcome_is_credited_to_the_last_touch_before_it(self):
        rec = self.record()
        self.touch(rec, JOHN, "d1", "c", "2026-08-01T09:00:00+00:00")
        self.touch(rec, JOHN, "d6", "e", "2026-08-06T09:00:00+00:00")
        self.positive(rec, JOHN, "2026-08-07T09:00:00+00:00")

        last = V.results_from([rec], "d6")
        self.assertEqual(last["e"][V.POSITIVE_REPLIES], 1)

        earlier = V.results_from([rec], "d1")
        self.assertEqual(earlier["c"]["exposures"], 1)
        self.assertEqual(earlier["c"][V.POSITIVE_REPLIES], 0,
                         "an earlier step was credited with a later reply")

    def test_an_exposure_with_no_reply_still_counts_as_a_denominator(self):
        rec = self.record()
        self.touch(rec, SARAH, "d1", "a", "2026-08-01T09:00:00+00:00")
        results = V.results_from([rec], "d1")
        self.assertEqual(results["a"]["exposures"], 1)
        self.assertEqual(results["a"][V.POSITIVE_REPLIES], 0)

    def test_a_reply_before_a_touch_is_not_credited_to_it(self):
        rec = self.record()
        self.positive(rec, JOHN, "2026-08-01T09:00:00+00:00")
        self.touch(rec, JOHN, "d6", "e", "2026-08-06T09:00:00+00:00")
        results = V.results_from([rec], "d6")
        self.assertEqual(results["e"][V.POSITIVE_REPLIES], 0)



class TheScreenWillNotRateWhatTheEvaluatorWouldNotJudge(CampaignTest):
    """Two screens in one product answering the same question differently
    is how a reader learns to trust whichever one flatters the result.

    The evaluator refuses to call a winner below `minimum_per_variant`.
    The screen printed "0.0%" from three sends anyway - a number two
    variants can be compared on when the difference between them is noise.

    Built from the real API rather than a hand-made dict, because a
    fixture I invent is a fixture that can disagree with the page.
    """

    def rendered(self, exposures, floor=None):
        import os
        import shutil
        import tempfile

        from src import repo as repo_module, store as store_module
        from src.web import api, demodata, pages

        tmp = tempfile.mkdtemp(prefix="rga-variant-screen-")
        previous = {k: os.environ.get(k) for k in ("CLIENTS_DIR", "OUT")}
        try:
            store_module.use_directory(os.path.join(tmp, "work"))
            os.environ["CLIENTS_DIR"] = os.path.join(tmp, "clients")
            os.environ["OUT"] = os.path.join(tmp, "out")
            demodata.install()
            repo = repo_module.Repo.for_user("ops@productive.test",
                                             "productive")
            data = api.campaign_experiments(repo, demo=True)
            if floor is not None:
                data["minimum_per_variant"] = floor
            for step in data["steps"]:
                for entry in step["variants"]:
                    result = entry.get("result")
                    if result is not None:
                        result["exposures"] = exposures
                        result["outcomes"] = 0
                        result["rate"] = 0.0
            return pages.campaign_experiments(data)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_rate_from_three_sends_is_not_shown(self):
        html = self.rendered(3)
        self.assertNotIn("0.0%", html)
        self.assertIn("too few to rate", html)

    def test_the_counts_are_still_shown(self):
        """Suppressing the rate must not suppress the evidence."""
        self.assertIn("0/3", self.rendered(3))

    def test_a_rate_above_the_floor_is_shown_with_its_denominator(self):
        html = self.rendered(40)
        self.assertIn("0.0%", html)
        self.assertIn("0/40", html)

    def test_the_floor_comes_from_configuration(self):
        """A workspace that raised the floor raised it for the screen."""
        self.assertIn("too few to rate", self.rendered(40, floor=100))

    def test_the_api_reports_the_floor_it_evaluates_against(self):
        import os
        import shutil
        import tempfile

        from src import repo as repo_module, store as store_module
        from src.web import api, demodata

        tmp = tempfile.mkdtemp(prefix="rga-variant-floor-")
        previous = {k: os.environ.get(k) for k in ("CLIENTS_DIR", "OUT")}
        try:
            store_module.use_directory(os.path.join(tmp, "work"))
            os.environ["CLIENTS_DIR"] = os.path.join(tmp, "clients")
            os.environ["OUT"] = os.path.join(tmp, "out")
            demodata.install()
            repo = repo_module.Repo.for_user("ops@productive.test",
                                             "productive")
            data = api.campaign_experiments(repo, demo=True)
            self.assertEqual(data["minimum_per_variant"],
                             V.settings(repo.config())["minimum_per_variant"])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
