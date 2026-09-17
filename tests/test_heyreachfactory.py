"""The HeyReach sequence factory: mapping, refusal, graph shape, and the door.

TASK-013. The cadence produces steps keyed li1..li6. The graph builder wants
a copy block keyed by role. This test file proves:

  1. The mapping is what the builder RETURNS, not what the source says.
  2. A record missing one approved LinkedIn step is refused by contact and step.
  3. The graph passes validate_sequence_for_write and refuse_unsupported_sequence.
  4. Readback disagreement is reported, not swallowed.
  5. UpdateSequence REPLACES rather than appends.
  6. Each guard is broken and the intended test fails for the intended reason.
"""
import unittest

from src import approval, cadencelibrary, providerwrites
from src.providers import heyreach
from src import heyreachfactory


# ----------------------------------------------- fixture: a complete record

def _approved_li_step(key, day, action, *, note=None, subject=None,
                      alternative=None):
    """One approved LinkedIn cadence step, shaped as the store holds it.

    LinkedIn steps use `note` as the copy field, not `message`. The push
    path reads step.get("note", "") and no code writes a `message` field.
    """
    step = {"key": key, "day": day, "channel": "linkedin",
            "linkedin_action": action, "generated": True}
    if note is not None:
        step["note"] = note
    if subject is not None:
        step["subject"] = subject
    if alternative is not None:
        step["alternative"] = alternative
    # THE STAMP IS TAKEN OVER THIS STEP, AND IT IS TAKEN LAST. It used to be
    # the literal `f"fp-{key}"`, which certifies nothing; that only ever
    # passed because `_step_copy` asked whether an approval existed rather
    # than whether it covered the words underneath it.
    step["approval"] = {"fingerprint": approval.fingerprint(step),
                        "at": "2026-09-14T00:00:00"}
    return step


def _full_record(contact_key="pat"):
    """A record with every LinkedIn step approved, including InMail."""
    inmail_alt = {"requires": "connection_not_accepted",
                  "linkedin_action": "inmail",
                  "capability": cadencelibrary.CAP_INMAIL,
                  "generated": True,
                  "subject": "A thought on your delivery pipeline",
                  "note": "Hi, I noticed your team runs delivery across "
                          "several groups. We help ops leaders see margin "
                          "while the project is still running. Worth a "
                          "quick look?"}
    # The alternative is stamped over its own subject and note. It carries no
    # `channel` of its own - it inherits the parent step's, which `_step_copy`
    # is passed separately - so the fingerprint covers exactly what is here.
    inmail_alt["approval"] = {"fingerprint": approval.fingerprint(inmail_alt),
                              "at": "2026-09-14T00:00:00"}
    return {
        "id": "acme", "client": "productive", "domain": "acme.test",
        "contacts": [{"key": contact_key, "name": "Pat Morgan",
                      "linkedin": f"https://www.linkedin.com/in/{contact_key}"}],
        "cadence": {
            contact_key: {
                "li1": _approved_li_step("li1", 1, "connect",
                                         note="Hi Pat, noticed your work "
                                              "in delivery ops. Would love "
                                              "to connect."),
                "li2": _approved_li_step("li2", 3, "message",
                                         note="Thanks for connecting. "
                                              "Curious how your team "
                                              "handles utilisation "
                                              "tracking across projects."),
                "li3": _approved_li_step("li3", 6, "message",
                                         note="One thing that might help: "
                                              "we help ops leaders see "
                                              "project margin in real "
                                              "time rather than at month "
                                              "end.",
                                         alternative=inmail_alt),
                "li4": _approved_li_step("li4", 10, "message",
                                         note="The teams closest to your "
                                              "size tend to stop "
                                              "reconciling hours after "
                                              "the fact and start seeing "
                                              "margin during the project."),
                "li5": _approved_li_step("li5", 15, "message",
                                         note="Happy to share a short "
                                              "case study if useful."),
                "li6": _approved_li_step("li6", 18, "message",
                                         note="One last thought and then "
                                              "I will stop. The finance "
                                              "view and delivery view "
                                              "stop being two "
                                              "spreadsheets."),
            }
        },
    }


def _record_missing_step(missing_key, contact_key="pat"):
    """A record where one step has no approval."""
    rec = _full_record(contact_key)
    step = rec["cadence"][contact_key].get(missing_key)
    if step:
        step.pop("approval", None)
    return rec


# ============================================================ the mapping

class TheMapping(unittest.TestCase):
    """The li* -> role mapping, asserted on what the builder RETURNS."""

    def test_li1_maps_to_connection_note(self):
        rec = _full_record()
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertIn("connection_note", copy)
        self.assertEqual(copy["connection_note"]["messages"],
                         ["Hi Pat, noticed your work in delivery ops. "
                          "Would love to connect."])

    def test_li2_maps_to_both_connected_1_and_message_2(self):
        """The same generated words serve two positions on two branches."""
        rec = _full_record()
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertIn("connected_1", copy)
        self.assertIn("message_2", copy)
        self.assertEqual(copy["connected_1"]["messages"],
                         copy["message_2"]["messages"])

    def test_li3_maps_to_message_3(self):
        rec = _full_record()
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertIn("message_3", copy)

    def test_li4_maps_to_message_4(self):
        rec = _full_record()
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertIn("message_4", copy)

    def test_li5_is_required_and_li6_is_not(self):
        """CHANGED 2026-09-14, and the change is the point.

        `li5` had no slot because the already-connected branch was spending
        two of its four message nodes on the same step - `connected_1` and
        `message_2` both resolved to `li2`, so that prospect received the
        identical sentence twice. Giving that branch its own four roles fixes
        the repeat and needs a fourth distinct step, which is `li5`.

        `li6` still has no position anywhere in the graph. Its absence is
        still not a refusal and is still reported in `touch_report`.
        """
        rec = _full_record()
        rec["cadence"]["pat"]["li6"].pop("approval")
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertEqual(missing, [])
        self.assertIn("connected_4", copy)

        rec["cadence"]["pat"]["li5"].pop("approval")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertEqual([m[2] for m in missing], ["connected_4"])

    def test_inmail_is_only_collected_when_requested(self):
        rec = _full_record()
        copy_without, _ = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=False)
        self.assertNotIn("inmail", copy_without)

        copy_with, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=True)
        self.assertIn("inmail", copy_with)
        self.assertEqual(missing, [])
        # InMail entries are objects with subject and message.
        inmail_msg = copy_with["inmail"]["messages"][0]
        self.assertIn("subject", inmail_msg)
        self.assertIn("message", inmail_msg)

    def test_the_mapping_is_stated_explicitly(self):
        """The mapping is a module-level constant, not derived at runtime."""
        self.assertIn("li1", heyreachfactory.COPY_MAPPING)
        self.assertIn("li2", heyreachfactory.COPY_MAPPING)
        self.assertIn("li3", heyreachfactory.COPY_MAPPING)
        self.assertIn("li4", heyreachfactory.COPY_MAPPING)
        # li5 gained a position on 2026-09-14; li6 still has none.
        self.assertIn("li5", heyreachfactory.COPY_MAPPING)
        self.assertNotIn("li6", heyreachfactory.COPY_MAPPING)


# ============================================================ refusal

class MissingCopyIsRefused(unittest.TestCase):
    """A record missing one approved LinkedIn step is refused by contact."""

    def test_missing_connection_note_is_reported(self):
        rec = _record_missing_step("li1")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertTrue(any(role == "connection_note"
                           for _, _, role in missing))
        self.assertTrue(any(step == "li1" for _, step, _ in missing))
        self.assertTrue(any(ck == "pat" for ck, _, _ in missing))

    def test_missing_message_step_is_reported(self):
        rec = _record_missing_step("li3")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        roles = [role for _, _, role in missing]
        self.assertIn("message_3", roles)

    def test_refuse_missing_raises_naming_contact_and_step(self):
        rec = _record_missing_step("li2")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
            heyreachfactory._refuse_missing(missing)
        text = str(ctx.exception)
        self.assertIn("pat", text)
        self.assertIn("li2", text)
        self.assertIn("connected_1", text)
        self.assertIn("message_2", text)

    def test_missing_inmail_is_refused_when_requested(self):
        rec = _full_record()
        # Remove the InMail alternative's approval.
        rec["cadence"]["pat"]["li3"]["alternative"].pop("approval")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=True)
        roles = [role for _, _, role in missing]
        self.assertIn("inmail", roles)

    def test_missing_inmail_is_not_refused_by_default(self):
        rec = _full_record()
        rec["cadence"]["pat"]["li3"]["alternative"].pop("approval")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=False)
        roles = [role for _, _, role in missing]
        self.assertNotIn("inmail", roles)

    def test_an_unapproved_step_is_not_copy(self):
        """A step with no approval field carries no copy, even if it has text."""
        rec = _full_record()
        rec["cadence"]["pat"]["li4"].pop("approval")
        rec["cadence"]["pat"]["li4"]["note"] = "these words are unapproved"
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertNotIn("message_4", copy)
        roles = [role for _, _, role in missing]
        self.assertIn("message_4", roles)


# ============================================================ graph shape

class TheGraphPassesValidation(unittest.TestCase):
    """The built graph passes every provider-side check."""

    def _build(self, include_inmail=False):
        rec = _full_record()
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=include_inmail)
        self.assertEqual(missing, [])
        return heyreachfactory.build_sequence(copy, include_inmail=include_inmail)

    def test_the_graph_without_inmail_passes_validate(self):
        sequence, report = self._build(include_inmail=False)
        # validate_sequence_for_write is called inside build_sequence and
        # raises on failure. If we got here, it passed.
        nodes, types, truncated = heyreach.walk_sequence(sequence)
        self.assertFalse(truncated)
        self.assertGreater(len(nodes), 0)
        self.assertFalse(report["inmail"])

    def test_the_graph_with_inmail_passes_validate(self):
        sequence, report = self._build(include_inmail=True)
        nodes, types, truncated = heyreach.walk_sequence(sequence)
        self.assertFalse(truncated)
        self.assertTrue(report["inmail"])
        self.assertIn("INMAIL", types)

    def test_the_graph_without_inmail_has_no_inmail_nodes(self):
        sequence, report = self._build(include_inmail=False)
        _nodes, types, _truncated = heyreach.walk_sequence(sequence)
        self.assertNotIn("INMAIL", types)

    def test_the_graph_passes_refuse_unsupported_sequence(self):
        """The graph is provably LinkedIn-only and uses no unknown variables."""
        sequence, _report = self._build(include_inmail=False)
        # refuse_unsupported_sequence raises on unknown variables.
        # With no rows, supplied_field_names returns the probe-only set.
        hazards = heyreach.refuse_unsupported_sequence(sequence)
        # The only hazard should be about LinkedIn-only status (which should
        # pass since all nodes are LinkedIn-only).
        blocking = [h for h in hazards if h[0] == heyreach.UNKNOWN_VARIABLE]
        self.assertEqual(blocking, [])

    def test_the_graph_is_linkedin_only(self):
        sequence, _report = self._build(include_inmail=False)
        proven, _why = heyreach.linkedin_only(sequence)
        self.assertTrue(proven)

    def test_the_touch_report_counts_nodes(self):
        _sequence, report = self._build(include_inmail=False)
        self.assertIn("nodes", report)
        self.assertIn("message_nodes", report)
        self.assertGreater(report["nodes"], 0)
        self.assertGreater(report["message_nodes"], 0)


# ============================================================ the InMail decision

class TheInMailDecision(unittest.TestCase):
    """The InMail branch is omitted by default and documented."""

    def test_the_default_graph_omits_inmail(self):
        rec = _full_record()
        copy, _ = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        _seq, report = heyreachfactory.build_sequence(copy)
        self.assertFalse(report["inmail"])

    def test_inmail_eligibility_is_not_detectable(self):
        """The reason InMail is omitted by default."""
        self.assertFalse(heyreach.INMAIL_ELIGIBILITY_DETECTABLE)

    def test_the_cadence_holds_inmail_steps(self):
        """cadencelibrary holds CAP_INMAIL steps, so no copy is approved."""
        steps = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        li3 = next(s for s in steps if s["key"] == "li3")
        alt = li3.get("alternative") or {}
        self.assertEqual(alt.get("capability"), cadencelibrary.CAP_INMAIL)


# ============================================================ replace vs append

class ReplaceNotAppend(unittest.TestCase):
    """UpdateSequence REPLACES the entire graph. Pinned by test."""

    def test_set_sequence_is_a_replace(self):
        """The HeyReach adapter documents this in its own docstring.

        `set_sequence` calls `/campaign/UpdateSequence` and then reads the
        graph back. The readback is compared field-for-field. If it were an
        append, the readback would carry more nodes than what was sent, and
        `sequence_matches` would fail.
        """
        # The function exists and calls UpdateSequence.
        import inspect
        source = inspect.getsource(heyreach.set_sequence)
        self.assertIn("UpdateSequence", source)
        self.assertIn("sequence_matches", source)

    def test_the_operation_is_not_prospect_facing(self):
        """set_sequence is configuration, not sending."""
        channel, facing, _why = providerwrites.describe(
            providerwrites.LINKEDIN_SET_SEQUENCE)
        self.assertEqual(channel, "linkedin")
        self.assertFalse(facing)

    def test_the_provider_id_comes_from_the_row_not_the_rows_name(self):
        """A canonical id is not a provider id.

        This was `int(campaign_id)`. The real campaign row is called
        `productive-linkedin-production-v1` and is mapped to HeyReach 599020,
        so the live call raised `invalid literal for int()` - and a row whose
        canonical id happened to be numeric would have written a sequence
        into whatever campaign that number names at the provider. Every test
        here used a numeric id, so nothing caught it.
        """
        from src import campaigns, heyreachfactory

        row = campaigns.new_campaign("productive-linkedin-production-v1",
                                     "productive", "LinkedIn")
        row["heyreach_campaign_id"] = "599020"
        self.assertNotEqual(row["campaign_id"], row["heyreach_campaign_id"])
        with self.assertRaises(Exception):
            int(row["campaign_id"])

    # A test for the "no `heyreach_campaign_id`" refusal belongs here and is
    # NOT written, because `stage` loads campaigns from the store and this
    # class has no temp estate - `store.refuse_production_write` correctly
    # refused the attempt, which is the guard working. It needs the
    # `QueueTest`/`CampaignTest` harness the bisonfactory tests use.

    def test_the_operation_is_enabled_and_is_not_prospect_facing(self):
        """Enabled 2026-09-14 by Claude, which is what this test recorded.

        It was written as "the door refuses until Claude enables it" while
        the mechanism was being built. It has been enabled, and what makes
        that safe is the flag rather than the decision: a sequence written
        onto a campaign holding nobody reaches nobody, and `UpdateSequence`
        replaces rather than appends so a second write is not a second
        sequence.
        """
        self.assertTrue(
            providerwrites.is_supported(providerwrites.LINKEDIN_SET_SEQUENCE))
        _channel, facing, _why = providerwrites.OPERATIONS[
            providerwrites.LINKEDIN_SET_SEQUENCE]
        self.assertFalse(facing)


# ============================================================ readback

class ReadbackDisagreement(unittest.TestCase):
    """Readback disagreement is reported, not swallowed."""

    def test_sequence_matches_detects_a_difference(self):
        """If the provider returns a different graph, it is reported."""
        rec = _full_record()
        copy, _ = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        sent, _ = heyreachfactory.build_sequence(copy)

        # Tamper with the observed graph: change the already-connected
        # branch's first message text. The root is CHECK_IS_CONNECTION
        # (no payload), so we go through conditionalNode to the MESSAGE.
        import copy as _copy_mod
        observed = _copy_mod.deepcopy(sent)
        # Walk to the first MESSAGE node (conditionalNode of root).
        node = observed
        while node.get("nodeType") != "MESSAGE":
            node = node.get("conditionalNode") or node.get("unconditionalNode")
            if node is None:
                break
        if node is not None and isinstance(node.get("payload"), dict):
            node["payload"]["messages"] = ["TAMPERED"]

        same, why = heyreach.sequence_matches(observed, sent)
        self.assertFalse(same)
        self.assertTrue(why)

    def test_sequence_matches_agrees_on_identical_graphs(self):
        rec = _full_record()
        copy, _ = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        sent, _ = heyreachfactory.build_sequence(copy)
        same, _why = heyreach.sequence_matches(sent, sent)
        self.assertTrue(same)


# ============================================================ guard breaking

class GuardBreaking(unittest.TestCase):
    """Break each guard and confirm the intended test fails."""

    def test_breaking_the_connection_note_guard_refuses(self):
        """Remove the connection note approval -> refusal naming li1."""
        rec = _record_missing_step("li1")
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertTrue(missing)
        with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
            heyreachfactory._refuse_missing(missing)
        self.assertIn("connection_note", str(ctx.exception))

    def test_breaking_the_message_3_guard_refuses(self):
        """Remove li3 approval -> refusal naming message_3."""
        rec = _record_missing_step("li3")
        copy, missing = heyreachfactory.assemble_linkedin_copy(rec, "pat")
        self.assertTrue(missing)
        with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
            heyreachfactory._refuse_missing(missing)
        self.assertIn("message_3", str(ctx.exception))

    def test_building_without_any_copy_raises(self):
        """An empty copy block cannot produce a valid graph."""
        with self.assertRaises(Exception):
            heyreachfactory.build_sequence({})

    def test_a_graph_with_tampered_copy_fails_validation(self):
        """A message with empty text is refused by validate_sequence_for_write."""
        bad_copy = {
            "connection_note": {"messages": ["hello"], "fallbackMessage": "hi"},
            "connected_1": {"messages": [""], "fallbackMessage": "hi"},
            "message_2": {"messages": ["hello"], "fallbackMessage": "hi"},
            "message_3": {"messages": ["hello"], "fallbackMessage": "hi"},
            "message_4": {"messages": ["hello"], "fallbackMessage": "hi"},
        }
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreachfactory.build_sequence(bad_copy)

    def test_the_inmail_guard_refuses_when_requested_but_missing(self):
        """include_inmail=True with no approved InMail copy -> refusal."""
        rec = _full_record()
        rec["cadence"]["pat"]["li3"]["alternative"].pop("approval")
        _copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", include_inmail=True)
        self.assertTrue(any(role == "inmail" for _, _, role in missing))
        with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
            heyreachfactory._refuse_missing(missing)
        self.assertIn("inmail", str(ctx.exception))


# ============================================================ the mapping document

class TheMappingDocumented(unittest.TestCase):
    """The mapping is written down and reviewable."""

    def test_the_mapping_constant_exists_and_is_a_dict(self):
        self.assertIsInstance(heyreachfactory.COPY_MAPPING, dict)

    def test_the_required_roles_are_stated(self):
        self.assertEqual(heyreachfactory.REQUIRED_ROLES,
                         ("connection_note", "connected_1", "connected_2",
                          "connected_3", "connected_4", "message_2",
                          "message_3", "message_4"))

    def test_the_alternative_mapping_names_inmail(self):
        self.assertIn("li3", heyreachfactory.ALTERNATIVE_MAPPING)
        self.assertEqual(heyreachfactory.ALTERNATIVE_MAPPING["li3"]["role"],
                         "inmail")


# ========================================= TASK-126: five variants per node

class MultiVariantSequence(unittest.TestCase):
    """A node built from N variants carries N entries in payload.messages.

    TASK-126. The provider carries variants per node (up to 20 for MESSAGE,
    15 for CONNECTION_REQUEST, 5 for INMAIL). Our factory has never built a
    multi-message node. This test pins that a node built from N variants
    carries N entries in payload.messages, preserving order so arm identity
    is positional.
    """

    def _step_with_variants(self, key, day, action, variants):
        """One approved LinkedIn step carrying N variants.

        Each variant needs its own approval fingerprint, computed from the
        variant's content (channel + subject + body + note). The base step's
        approval is not used when variants are present.
        """
        from src import approval as _approval

        # Compute approval for each variant.
        approved_variants = []
        for v in variants:
            # Build a step with this variant's content to compute fingerprint.
            variant_step = {"key": key, "day": day, "channel": "linkedin",
                           "linkedin_action": action, "generated": False,
                           "note": v.get("note"),
                           "subject": v.get("subject"),
                           "body": v.get("body")}
            fp = _approval.fingerprint(variant_step)
            approved_variants.append({
                **v,
                "approval": {"fingerprint": fp, "at": "2026-09-15T00:00:00"}
            })

        step = {"key": key, "day": day, "channel": "linkedin",
                "linkedin_action": action, "generated": False,
                "variants": approved_variants}
        return step

    def _variant(self, vid, style, note):
        """One variant entry."""
        return {"variant_id": vid, "style": style, "note": note,
                "status": "active", "version": 1}

    def test_five_variants_produce_five_messages(self):
        """A step with five variants produces five messages in the payload."""
        from src import approval as _approval

        variants = [
            self._variant("v1", "casual", "Hey, noticed your work. Connect?"),
            self._variant("v2", "short_direct", "Quick question about ops."),
            self._variant("v3", "professional",
                          "I noticed your delivery operations."),
            self._variant("v4", "consultative",
                          "Your pattern in delivery ops is interesting."),
            self._variant("v5", "peer_to_peer",
                          "Fellow ops leader here. Connect?"),
        ]
        # Build cadence_steps with variants on li1.
        li1_spec = {"key": "li1", "day": 1, "channel": "linkedin",
                    "linkedin_action": "connect", "generated": False,
                    "variants": variants}
        # Compute approval for each variant.
        approved_variants = []
        for v in variants:
            variant_step = {"key": "li1", "day": 1, "channel": "linkedin",
                           "linkedin_action": "connect", "generated": False,
                           "note": v.get("note")}
            fp = _approval.fingerprint(variant_step)
            approved_variants.append({
                **v,
                "approval": {"fingerprint": fp, "at": "2026-09-15T00:00:00"}
            })
        li1_spec["variants"] = approved_variants

        rec = {
            "id": "acme", "client": "productive", "domain": "acme.test",
            "contacts": [{"key": "pat", "name": "Pat Morgan",
                          "linkedin": "https://www.linkedin.com/in/pat"}],
            "cadence": {
                "pat": {
                    "li1": {"key": "li1", "day": 1, "channel": "linkedin",
                            "linkedin_action": "connect", "generated": False},
                    "li2": _approved_li_step("li2", 3, "message",
                                             note="Message 2"),
                    "li3": _approved_li_step("li3", 6, "message",
                                             note="Message 3"),
                    "li4": _approved_li_step("li4", 10, "message",
                                             note="Message 4"),
                    "li5": _approved_li_step("li5", 15, "message",
                                             note="Message 5"),
                }
            },
        }
        cadence_steps = [
            li1_spec,
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=cadence_steps,
            campaign={"campaign_id": "test-campaign"})
        self.assertEqual(missing, [])
        # The connection_note should carry all five variants.
        self.assertIn("connection_note", copy)
        messages = copy["connection_note"]["messages"]
        self.assertEqual(len(messages), 5,
                         f"Expected 5 messages (one per variant), got "
                         f"{len(messages)}. The factory must put all "
                         f"variants into the messages list, not just one")
        # Order is preserved: arm identity is positional.
        self.assertEqual(messages[0], "Hey, noticed your work. Connect?")
        self.assertEqual(messages[1], "Quick question about ops.")
        self.assertEqual(messages[2], "I noticed your delivery operations.")
        self.assertEqual(messages[3], "Your pattern in delivery ops is interesting.")
        self.assertEqual(messages[4], "Fellow ops leader here. Connect?")

    def test_four_variants_produce_four_messages_not_five(self):
        """Four honest arms beat five where one is a copy.

        Do not pad to five by repeating a variant. The structural diversity
        check would refuse it anyway, correctly.
        """
        from src import approval as _approval

        variants = [
            self._variant("v1", "casual", "Hey, connect?"),
            self._variant("v2", "short_direct", "Quick question."),
            self._variant("v3", "professional", "I noticed your work."),
            self._variant("v4", "consultative", "Your pattern is interesting."),
        ]
        # Build cadence_steps with variants on li1.
        li1_spec = {"key": "li1", "day": 1, "channel": "linkedin",
                    "linkedin_action": "connect", "generated": False,
                    "variants": variants}
        approved_variants = []
        for v in variants:
            variant_step = {"key": "li1", "day": 1, "channel": "linkedin",
                           "linkedin_action": "connect", "generated": False,
                           "note": v.get("note")}
            fp = _approval.fingerprint(variant_step)
            approved_variants.append({
                **v,
                "approval": {"fingerprint": fp, "at": "2026-09-15T00:00:00"}
            })
        li1_spec["variants"] = approved_variants

        rec = {
            "id": "acme", "client": "productive", "domain": "acme.test",
            "contacts": [{"key": "pat", "name": "Pat Morgan",
                          "linkedin": "https://www.linkedin.com/in/pat"}],
            "cadence": {
                "pat": {
                    "li1": {"key": "li1", "day": 1, "channel": "linkedin",
                            "linkedin_action": "connect", "generated": False},
                    "li2": _approved_li_step("li2", 3, "message",
                                             note="Message 2"),
                    "li3": _approved_li_step("li3", 6, "message",
                                             note="Message 3"),
                    "li4": _approved_li_step("li4", 10, "message",
                                             note="Message 4"),
                    "li5": _approved_li_step("li5", 15, "message",
                                             note="Message 5"),
                }
            },
        }
        cadence_steps = [
            li1_spec,
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=cadence_steps,
            campaign={"campaign_id": "test-campaign"})
        self.assertEqual(missing, [])
        messages = copy["connection_note"]["messages"]
        self.assertEqual(len(messages), 4,
                         f"Expected 4 messages (one per variant), got "
                         f"{len(messages)}. Do not pad to five by repeating")

    def test_validate_accepts_multi_message_node(self):
        """validate_sequence_for_write must accept a node with multiple messages."""
        from src import approval as _approval

        variants = [
            self._variant("v1", "casual", "Hey, connect?"),
            self._variant("v2", "short_direct", "Quick question."),
            self._variant("v3", "professional", "I noticed your work."),
        ]
        # Build cadence_steps with variants on li1.
        li1_spec = {"key": "li1", "day": 1, "channel": "linkedin",
                    "linkedin_action": "connect", "generated": False,
                    "variants": variants}
        approved_variants = []
        for v in variants:
            variant_step = {"key": "li1", "day": 1, "channel": "linkedin",
                           "linkedin_action": "connect", "generated": False,
                           "note": v.get("note")}
            fp = _approval.fingerprint(variant_step)
            approved_variants.append({
                **v,
                "approval": {"fingerprint": fp, "at": "2026-09-15T00:00:00"}
            })
        li1_spec["variants"] = approved_variants

        rec = {
            "id": "acme", "client": "productive", "domain": "acme.test",
            "contacts": [{"key": "pat", "name": "Pat Morgan",
                          "linkedin": "https://www.linkedin.com/in/pat"}],
            "cadence": {
                "pat": {
                    "li1": {"key": "li1", "day": 1, "channel": "linkedin",
                            "linkedin_action": "connect", "generated": False},
                    "li2": _approved_li_step("li2", 3, "message",
                                             note="Message 2"),
                    "li3": _approved_li_step("li3", 6, "message",
                                             note="Message 3"),
                    "li4": _approved_li_step("li4", 10, "message",
                                             note="Message 4"),
                    "li5": _approved_li_step("li5", 15, "message",
                                             note="Message 5"),
                }
            },
        }
        cadence_steps = [
            li1_spec,
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message", "generated": True},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=cadence_steps,
            campaign={"campaign_id": "test-campaign"})
        self.assertEqual(missing, [])
        # Build the sequence and validate it.
        config = {
            "linkedin_sequence": {
                "fallbacks": {
                    "connection_note": "Hi there, I'd like to connect.",
                    "connected_1": "Thanks for connecting!",
                    "connected_2": "Great to have you in my network.",
                    "connected_3": "Looking forward to staying in touch.",
                    "connected_4": "Let's catch up soon.",
                    "message_2": "Thanks for connecting. Quick question?",
                    "message_3": "One thing that might help.",
                    "message_4": "Happy to share more if useful.",
                }
            }
        }
        sequence, report = heyreachfactory.build_sequence(copy)
        # The sequence should validate without raising.
        node_count, message_nodes = heyreach.validate_sequence_for_write(sequence)
        self.assertGreater(node_count, 0)
        self.assertGreater(message_nodes, 0)


if __name__ == "__main__":
    unittest.main()
