"""TASK-548: li5 must BLOCK, never vanish.

The fifth LinkedIn step is generated, gated, stored, and then silently dropped
before the provider ever sees it. The cost is not the missing message - it is
that nothing reports it. A campaign meant to run five LinkedIn touches runs
four, and every gate upstream says PASS.

The projection must refuse when the cadence declares a step the payload cannot
carry, naming the step. It must never return a short payload as if complete.

CLAIM        derive_heyreach_payload and derive_bison_payload silently drop
             declared steps when the contact's sequences lack them
AUTHORITY    sequenceplan.derive_heyreach_payload iterated LINKEDIN_WRITER_KEYS
             but skipped missing keys without refusal
MEASURED AT  2026-10-04, reproduced: li5 absent from sequences -> 4-key payload
             returned successfully
STATE        PROVEN and FIXED. Both projections now raise PlanRefused when the
             cadence declares a step the contact's sequences do not carry.
"""
import unittest

from src import cadencelibrary, sequenceplan


class TestLi5MustBlockNotVanish(unittest.TestCase):
    """The LinkedIn projection refuses a short payload, never returns one."""

    def _plan(self, sequences, *, cadence_steps=None):
        plan = {
            "version": "1",
            "client": "test-client",
            "account": {"company": "Acme", "domain": "acme.com"},
            "contacts": [{
                "contact_key": "c1",
                "email": "test@acme.com",
                "first_name": "Test",
                "qualification": "VERIFIED",
                "sequences": dict(sequences),
            }],
        }
        if cadence_steps is not None:
            plan["cadence_steps"] = cadence_steps
        return plan

    # --- REPRODUCTION: the original defect ---

    def test_li5_present_when_all_five_provided(self):
        """Control: all five keys present -> li5 in payload."""
        plan = self._plan(
            {f"li{i}": f"Message {i}" for i in range(1, 6)},
            cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertIn("li5", li)
        self.assertEqual(len(li), 5)

    def test_li5_missing_with_cadence_declaring_it_refuses(self):
        """THE DEFECT: li5 missing, cadence declares it -> PlanRefused."""
        plan = self._plan(
            {f"li{i}": f"Message {i}" for i in range(1, 5)},
            cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        self.assertIn("li5", str(ctx.exception))
        self.assertIn("c1", str(ctx.exception))

    def test_li2_missing_with_cadence_declaring_it_refuses(self):
        """Not just li5: any declared key missing refuses."""
        seqs = {f"li{i}": f"Message {i}" for i in range(1, 6)}
        del seqs["li2"]
        plan = self._plan(seqs,
                          cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        self.assertIn("li2", str(ctx.exception))

    def test_two_missing_keys_both_named_in_refusal(self):
        """The refusal names every missing key, not just the first."""
        seqs = {"li1": "Message 1", "li3": "Message 3"}
        plan = self._plan(seqs,
                          cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_heyreach_payload(plan)
        msg = str(ctx.exception)
        self.assertIn("li2", msg)
        self.assertIn("li4", msg)
        self.assertIn("li5", msg)

    # --- CONTROL: the guard does not refuse everything ---

    def test_no_cadence_steps_no_refusal(self):
        """Backward compat: no cadence_steps -> no check, partial payload OK."""
        plan = self._plan({"li1": "Note 1", "li3": "Note 3"})
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 2)

    def test_no_linkedin_copy_at_all_skips_contact(self):
        """A contact with zero LinkedIn keys is not in the payload."""
        plan = self._plan({"em1": "Body 1"},
                          cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(len(payload["leads"]), 0)

    def test_email_only_cadence_no_linkedin_check(self):
        """An email-only cadence declares no LinkedIn keys -> no LI check."""
        email_only = [s for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
                      if s["channel"] == "email"]
        plan = self._plan({"li1": "Note 1", "li2": "Note 2"},
                          cadence_steps=email_only)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 2)

    # --- THE SAME PATHOLOGY ON EMAIL ---

    def test_email_em5_missing_with_cadence_declaring_it_refuses(self):
        """derive_bison_payload: same vanish pathology, same fix."""
        plan = self._plan(
            {f"em{i}": f"Body {i}" for i in range(1, 5)},
            cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        plan["contacts"][0]["subjects"] = {"A": "S", "B": "S", "C": "S"}
        with self.assertRaises(sequenceplan.PlanRefused) as ctx:
            sequenceplan.derive_bison_payload(plan)
        self.assertIn("em5", str(ctx.exception))

    def test_email_complete_five_passes(self):
        """Control: all five email keys present -> passes."""
        seqs = {f"em{i}": f"Body {i}" for i in range(1, 6)}
        seqs.update({f"li{i}": f"Msg {i}" for i in range(1, 6)})
        plan = self._plan(seqs,
                          cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        plan["contacts"][0]["subjects"] = {"A": "S", "B": "S", "C": "S"}
        payload = sequenceplan.derive_bison_payload(plan)
        steps = payload["leads"][0]["steps"]
        self.assertEqual(len(steps), 5)

    # --- MUTATION: break the wiring, prove the test fires ---

    def test_mutation_remove_li5_from_sequences_still_refuses(self):
        """If li5 is removed from sequences, the refusal must fire.

        This is the wiring check: if the guard were disconnected from the
        cadence declaration, this test would go red.
        """
        seqs = {f"li{i}": f"Message {i}" for i in range(1, 6)}
        plan = self._plan(seqs,
                          cadence_steps=cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        # First prove it passes with all five
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(len(payload["leads"][0]["linkedin"]), 5)

        # Now remove li5 - must refuse
        del plan["contacts"][0]["sequences"]["li5"]
        with self.assertRaises(sequenceplan.PlanRefused):
            sequenceplan.derive_heyreach_payload(plan)


class TestNoHardcodedFourElsewhere(unittest.TestCase):
    """TASK-548 step 4: check the count is not hardcoded anywhere else."""

    def test_derive_preview_data_carries_sequences_as_is(self):
        """derive_preview_data passes sequences through; it does not drop."""
        plan = {
            "version": "1",
            "client": "test",
            "account": {"company": "A", "domain": "a.com"},
            "contacts": [{
                "contact_key": "c1",
                "sequences": {f"li{i}": f"Msg {i}" for i in range(1, 6)},
            }],
        }
        data = sequenceplan.derive_preview_data(plan)
        row = data["rows"][0]
        for key in ("li1", "li2", "li3", "li4", "li5"):
            self.assertIn(key, row["sequences"])

    def test_linkedin_writer_keys_has_five(self):
        """The single authority has five keys, not four."""
        self.assertEqual(len(cadencelibrary.LINKEDIN_WRITER_KEYS), 5)
        self.assertEqual(cadencelibrary.LINKEDIN_WRITER_KEYS,
                         ("li1", "li2", "li3", "li4", "li5"))

    def test_heyreach_copy_mapping_covers_li5(self):
        """heyreachfactory.COPY_MAPPING maps li5 to connected_4."""
        from src import heyreachfactory
        self.assertIn("li5", heyreachfactory.COPY_MAPPING)
        roles = heyreachfactory.COPY_MAPPING["li5"]["role"]
        if isinstance(roles, str):
            roles = (roles,)
        self.assertIn("connected_4", roles)


if __name__ == "__main__":
    unittest.main()
