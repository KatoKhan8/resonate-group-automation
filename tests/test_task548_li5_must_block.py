"""TASK-548: li5 must BLOCK, never vanish.

The fifth LinkedIn step was generated, gated, stored, and then silently
dropped before the provider ever saw it. The projection must refuse when
the cadence declares a step the payload cannot carry, naming the step.

Two assertions per channel:
1. The refusal fires when a declared step is missing.
2. A control proving a complete five-step payload still passes.

A guard that refuses everything is not a guard.
"""
import unittest

from src import sequenceplan


class TestLinkedInMustBlockNotVanish(unittest.TestCase):
    """derive_heyreach_payload refuses when a declared LinkedIn step is missing."""

    def _make_plan(self, sequences, *, cadence_steps=None):
        """Build a minimal plan with one contact carrying `sequences`."""
        plan = {
            "version": "1",
            "client": "test-client",
            "account": {"company": "Acme", "domain": "acme.com"},
            "contacts": [{
                "contact_key": "test-contact",
                "qualification": "QUALIFIED_THIN",
                "sequences": dict(sequences),
                "subjects": {"A": "Sub A", "B": "Sub B", "C": "Sub C"},
            }],
        }
        if cadence_steps is not None:
            plan["cadence_steps"] = cadence_steps
        return plan

    # 1. CONTROL: a complete five-step payload passes.
    def test_complete_five_step_payload_passes(self):
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(len(payload["leads"]), 1)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 5)
        for key in ("li1", "li2", "li3", "li4", "li5"):
            self.assertIn(key, li)

    # 2. REFUSAL: missing li5 fires PlanRefused when cadence declares it.
    def test_missing_li5_refuses(self):
        cadence_steps = [
            {"key": "li1", "channel": "linkedin", "day": 1},
            {"key": "li2", "channel": "linkedin", "day": 3},
            {"key": "li3", "channel": "linkedin", "day": 6},
            {"key": "li4", "channel": "linkedin", "day": 10},
            {"key": "li5", "channel": "linkedin", "day": 15},
        ]
        seqs = {"li1": "Note 1", "li2": "Note 2", "li3": "Note 3",
                "li4": "Note 4"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        self.assertIn("li5", str(ctx.exception))
        self.assertIn("test-contact", str(ctx.exception))

    # 3. REFUSAL: missing li3 fires PlanRefused when cadence declares it.
    def test_missing_li3_refuses(self):
        cadence_steps = [
            {"key": "li1", "channel": "linkedin", "day": 1},
            {"key": "li2", "channel": "linkedin", "day": 3},
            {"key": "li3", "channel": "linkedin", "day": 6},
            {"key": "li4", "channel": "linkedin", "day": 10},
            {"key": "li5", "channel": "linkedin", "day": 15},
        ]
        seqs = {"li1": "Note 1", "li2": "Note 2", "li4": "Note 4",
                "li5": "Note 5"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        self.assertIn("li3", str(ctx.exception))

    # 4. REFUSAL: missing multiple steps names all of them.
    def test_missing_multiple_steps_names_all(self):
        cadence_steps = [
            {"key": "li1", "channel": "linkedin", "day": 1},
            {"key": "li2", "channel": "linkedin", "day": 3},
            {"key": "li3", "channel": "linkedin", "day": 6},
            {"key": "li4", "channel": "linkedin", "day": 10},
            {"key": "li5", "channel": "linkedin", "day": 15},
        ]
        seqs = {"li1": "Note 1", "li3": "Note 3"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        msg = str(ctx.exception)
        self.assertIn("li2", msg)
        self.assertIn("li4", msg)
        self.assertIn("li5", msg)

    # 5. CADENCE-DRIVEN: when cadence_steps declares three LinkedIn steps,
    #    only those three are expected.
    def test_cadence_declares_three_steps_only_three_expected(self):
        cadence_steps = [
            {"key": "li1", "channel": "linkedin", "day": 1},
            {"key": "li2", "channel": "linkedin", "day": 3},
            {"key": "li3", "channel": "linkedin", "day": 6},
        ]
        seqs = {"li1": "Note 1", "li2": "Note 2", "li3": "Note 3"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(len(payload["leads"]), 1)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 3)

    # 6. CADENCE-DRIVEN REFUSAL: cadence declares five, contact has four.
    def test_cadence_declares_five_contact_has_four_refuses(self):
        cadence_steps = [
            {"key": "li1", "channel": "linkedin", "day": 1},
            {"key": "li2", "channel": "linkedin", "day": 3},
            {"key": "li3", "channel": "linkedin", "day": 6},
            {"key": "li4", "channel": "linkedin", "day": 10},
            {"key": "li5", "channel": "linkedin", "day": 15},
        ]
        seqs = {"li1": "Note 1", "li2": "Note 2", "li3": "Note 3",
                "li4": "Note 4"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        self.assertIn("li5", str(ctx.exception))


class TestEmailMustBlockNotVanish(unittest.TestCase):
    """derive_bison_payload refuses when a declared email step is missing."""

    def _make_plan(self, sequences, *, cadence_steps=None):
        """Build a minimal plan with one contact carrying `sequences`."""
        plan = {
            "version": "1",
            "client": "test-client",
            "account": {"company": "Acme", "domain": "acme.com"},
            "contacts": [{
                "contact_key": "test-contact",
                "email": "test@acme.com",
                "first_name": "Test",
                "qualification": "QUALIFIED_THIN",
                "sequences": dict(sequences),
                "subjects": {"A": "Sub A", "B": "Sub B", "C": "Sub C"},
            }],
        }
        if cadence_steps is not None:
            plan["cadence_steps"] = cadence_steps
        return plan

    # 1. CONTROL: a complete five-step email payload passes.
    def test_complete_five_step_email_payload_passes(self):
        seqs = {f"em{i}": f"Body {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_bison_payload(plan)
        self.assertEqual(len(payload["leads"]), 1)
        steps = payload["leads"][0]["steps"]
        self.assertEqual(len(steps), 5)
        email_keys = [s["step_key"] for s in steps]
        self.assertEqual(email_keys, ["em1", "em2", "em3", "em4", "em5"])

    # 2. REFUSAL: missing em5 fires PlanRefused when cadence declares it.
    def test_missing_em5_refuses(self):
        cadence_steps = [
            {"key": "em1", "channel": "email", "day": 1},
            {"key": "em2", "channel": "email", "day": 3},
            {"key": "em3", "channel": "email", "day": 6},
            {"key": "em4", "channel": "email", "day": 10},
            {"key": "em5", "channel": "email", "day": 15},
        ]
        seqs = {"em1": "Body 1", "em2": "Body 2", "em3": "Body 3",
                "em4": "Body 4"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_bison_payload(plan)
        self.assertIn("em5", str(ctx.exception))
        self.assertIn("test-contact", str(ctx.exception))

    # 3. CADENCE-DRIVEN: when cadence_steps declares three email steps,
    #    only those three are expected.
    def test_cadence_declares_three_email_steps_only_three_expected(self):
        cadence_steps = [
            {"key": "em1", "channel": "email", "day": 1},
            {"key": "em3", "channel": "email", "day": 3},
            {"key": "em5", "channel": "email", "day": 6},
        ]
        seqs = {"em1": "Body 1", "em3": "Body 3", "em5": "Body 5"}
        plan = self._make_plan(seqs, cadence_steps=cadence_steps)
        payload = sequenceplan.derive_bison_payload(plan)
        self.assertEqual(len(payload["leads"]), 1)
        steps = payload["leads"][0]["steps"]
        self.assertEqual(len(steps), 3)


if __name__ == "__main__":
    unittest.main()
