"""The template register cannot escape the word contract.

CANARY-01 blocker B4, 2026-10-14: eight-plus templates were invisible to
every body check because coverage was a hand-kept walk - the checks visited
the templates somebody remembered, and `cadence.TEMPLATES` grew six
step-4/5 personas templates plus a retired variant that nothing visited at
all. Three of them render over the 90-word ceiling today and nothing on
master goes red, because no check anywhere renders the REGISTER and counts
its words. `lint`'s contract gate applies to stored record steps after a
writer writes them; `stage_s7_copy` lints SUBJECTS only; the product-name
walk checks content, never length.

THE GUARD HERE IS THE WALK, NOT A LIST. Coverage is computed structurally
from the consumers that actually render templates:

  - every step spec in `cadence.STEPS` and every UPPER list/tuple attribute
    of `cadencelibrary` (template, alternative.template,
    variant_if_accepted), and
  - `scripts/stage_s7_copy.py` itself, driven for every persona and every
    angle the productive config declares, which is the only renderer of the
    `rung3_`/`angle_shift_`/`close_` per-persona six.

A template in the register that NONE of those can name is a hard failure
naming it - the same shape as the phantom-sink fix, which aborts rather
than silently skips. Plant a template nobody covers and this file goes red
saying so; delete it and the file is green again. That mutation was run as
the proof and is documented in
`docs/REVIEW-GLM-2026-10-14-QUEUE.md` §B4.

BOUNDS COME FROM THE AUTHORITIES THAT DECLARE THEM, never retyped here:
em3/em4/em5 slots read `writercontract.WORD_CONTRACT` (the only authority
for a body's word count, operator 2026-10-02); day-keyed cadence steps have
no writer-contract entry, so they take `lint`'s single-email shape bounds
(40-180); LinkedIn notes take `lint.NOTE_MAX_CHARS` in characters. Word
counts use `lint.countable_words` - the one definition of a word - and are
measured per angle, because the interpolated angle phrase changes the count.

THREE TEMPLATES WERE OVER CEILING WHEN THIS FILE WAS WRITTEN, AND THE
REWRITE HAS SINCE LANDED. `rung3_economic_buyer` (104 words, em3 ceiling
90), `angle_shift_champion` (127, em4 ceiling 90) and
`angle_shift_economic_buyer` (124-129 across angles, em4 ceiling 90) each
carried `expectedFailure` with their numbers while the rewrite was the
OPERATOR's to make (CANARY-01 B4). glm-c's approved trims make all three
pass, and the markers were removed in the step that merged those trims
(integ/nine M5a) - the ledger does not outlive the defect it names. The
three tests are now ordinary assertions and go RED if any of the three
bodies grows back over its writercontract ceiling.

One number corrected here: `comparable_proof_short` was reported at 42
words. Through the real renderer, over every persona and angle the
productive config declares, it renders 58 words flat. It sits inside every
bound any authority declares for its day10 slot. The FLOOR GAP is still
real - before this file, nothing checked any floor on the register - but
this template is not a floor violation.
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts import stage_s7_copy  # noqa: E402
from src import cadence, cadencelibrary, clients, lint  # noqa: E402
from src.skills import cold_email_writing as writercontract  # noqa: E402

CLIENT = "productive"


def _config():
    return clients.load(CLIENT)


def _fixture_record():
    contact = {
        "name": "Ada Lovelace",
        "title": "Head of Operations",
        "linkedin": "https://www.linkedin.com/in/ada-b4-guard",
        "email": "ada@example.test",
    }
    contact["key"] = lint.contact_key(contact)
    return {"id": "b4-guard", "client": CLIENT, "domain": "example.test",
            "company": "Example", "contacts": [contact]}


def _angle_table(config):
    """[(persona, angle_key, angle_label)] for every configured angle."""
    out = []
    for persona, block in clients.personas(config).items():
        for angle_key in sorted((block or {}).get("angles") or {}):
            out.append((persona, angle_key,
                        block["angles"][angle_key]))
    return out


def _step_bindings():
    """template name -> [(where, step_key)] across every declared cadence.

    `cadence.STEPS` plus every UPPER list/tuple in `cadencelibrary`, so a
    cadence added later is walked the day it lands rather than the day
    somebody remembers to add it to a list.
    """
    out = {}
    sources = [("cadence.STEPS", cadence.STEPS)]
    for name in dir(cadencelibrary):
        if name.isupper():
            specs = getattr(cadencelibrary, name)
            if isinstance(specs, (list, tuple)):
                sources.append((f"cadencelibrary.{name}", specs))
    for label, specs in sources:
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            alt = spec.get("alternative")
            names = [spec.get("template"),
                     alt.get("template") if isinstance(alt, dict) else None,
                     spec.get("variant_if_accepted")]
            for template in names:
                if template:
                    out.setdefault(template, []).append((label, spec["key"]))
    return out


def _s7_renders(config):
    """template name -> [render dicts], by driving stage_s7 itself.

    `_steps_three_four_and_five` is the only renderer of the per-persona
    six, so coverage of those templates is proven by running the consumer,
    not by re-deriving its name construction here.
    """
    out = {}
    for persona, angle_key, angle in _angle_table(config):
        fields, reason = stage_s7_copy._steps_three_four_and_five(
            persona, angle_key, angle, "Ada", "Example", config)
        if reason:
            continue
        for field in ("3", "4", "5"):
            entry = {"persona": persona, "angle_key": angle_key,
                     "slot": f"em{field}",
                     "body": fields[f"body_{field}"],
                     "subject": fields.get("subject")}
            out.setdefault(fields[f"template_{field}"], []).append(entry)
    return out


def _words(body):
    return len(lint.countable_words(body))


def _engine_renders(config, skip=()):
    """template name -> rendered dict, through the engine's own vars.

    `skip` names the per-persona six: their values are persona-shaped and
    the stage_s7 consumer renders them, so the engine render never sees
    them and cannot speak for them.
    """
    record = _fixture_record()
    contact = record["contacts"][0]
    base = cadence.template_vars(record, contact, config)
    out = {}
    for name, template in cadence.TEMPLATES.items():
        if name in skip:
            continue
        if "note" in template or "body" in template:
            out[name] = cadence.render(template, base)
    return out


class ATemplateNothingRendersIsAHardFailure(unittest.TestCase):
    """The structural coverage guard. Green on master; red on an orphan."""

    @classmethod
    def setUpClass(cls):
        cls.config = _config()
        cls.step_bindings = _step_bindings()
        cls.s7 = _s7_renders(cls.config)
        cls.engine = _engine_renders(cls.config, skip=set(cls.s7))

    def test_every_template_in_the_register_is_covered_by_a_renderer(self):
        covered = set(self.step_bindings) | set(self.s7)
        for name in cadence.TEMPLATES:
            with self.subTest(template=name):
                where = self.step_bindings.get(name) or [
                    f"stage_s7 em slot {e['slot']} ({e['persona']})"
                    for e in self.s7.get(name, [])]
                self.assertIn(
                    name, covered,
                    f"{name!r} sits in cadence.TEMPLATES and NOTHING covers "
                    f"it: no cadence step names it, no alternative or "
                    f"variant names it, and stage_s7 cannot construct its "
                    f"name from any persona. A template without a renderer "
                    f"cannot reach a body check at all - bind it or delete "
                    f"it. Covered by: {where}")

    def test_every_covered_template_renders_non_empty_and_complete(self):
        for name in cadence.TEMPLATES:
            with self.subTest(template=name):
                if name in self.s7:
                    bodies = [e["body"] for e in self.s7[name]]
                else:
                    rendered = self.engine[name]
                    bodies = ([rendered["note"]] if "note" in rendered
                              else [rendered.get("body") or ""])
                for body in bodies:
                    self.assertTrue(
                        (body or "").strip(),
                        f"{name!r} renders an empty body - the blank-render "
                        f"incident shape, caught here on the register")
                    self.assertNotIn(
                        "{", body or "",
                        f"{name!r} left an unrendered placeholder")
                    self.assertNotIn("}", body or "")

    def test_linkedin_notes_fit_the_connection_request_cap(self):
        for name, template in cadence.TEMPLATES.items():
            if "note" not in template:
                continue
            with self.subTest(template=name):
                note = self.engine[name]["note"]
                self.assertLessEqual(
                    len(note), lint.NOTE_MAX_CHARS,
                    f"{name!r} renders {len(note)} characters; LinkedIn "
                    f"refuses a connection request over "
                    f"{lint.NOTE_MAX_CHARS}")


class EveryEmailTemplateSitsInsideItsContract(unittest.TestCase):
    """The word check the register never had, bounds from their authorities.

    em3/em4/em5 read the writer contract; day-keyed steps have no contract
    entry and take lint's single-email shape bounds (40-180). Floors are
    asserted here for the first time on the register.
    """

    @classmethod
    def setUpClass(cls):
        cls.config = _config()
        cls.s7 = _s7_renders(cls.config)
        cls.engine = _engine_renders(cls.config, skip=set(cls.s7))
        record = _fixture_record()
        cls.base_vars = cadence.template_vars(
            record, record["contacts"][0], cls.config)

    def _day_keyed_counts(self, name):
        """The template's body word count for every configured angle."""
        counts = []
        for persona, angle_key, angle in _angle_table(self.config):
            clause = angle.split(",")[0].strip()
            values = dict(self.base_vars, angle_phrase=clause,
                          angle_word=cadence.angle_word(angle_key, clause,
                                                        self.config))
            counts.append(_words(cadence.render(cadence.TEMPLATES[name],
                                                values)["body"]))
        return counts

    def test_em_slot_templates_are_within_the_writer_contract(self):
        for name, entries in self.s7.items():
            if name in ("rung3_economic_buyer", "angle_shift_champion",
                        "angle_shift_economic_buyer"):
                continue  # the three known over-ceiling bodies, below
            with self.subTest(template=name):
                floor, ceiling = writercontract.word_range(entries[0]["slot"])
                counts = [_words(e["body"]) for e in entries]
                self.assertTrue(counts, f"{name!r} rendered nothing")
                self.assertGreaterEqual(
                    min(counts), floor,
                    f"{name!r} renders {min(counts)} words at some angle, "
                    f"under the {entries[0]['slot']} floor of {floor}")
                self.assertLessEqual(
                    max(counts), ceiling,
                    f"{name!r} renders {max(counts)} words at some angle, "
                    f"over the {entries[0]['slot']} ceiling of {ceiling}")

    def test_day_keyed_templates_are_within_the_standing_shape(self):
        for name, template in cadence.TEMPLATES.items():
            if "note" in template or name in self.s7:
                continue
            with self.subTest(template=name):
                counts = self._day_keyed_counts(name)
                self.assertGreaterEqual(
                    min(counts), lint.MIN_WORDS,
                    f"{name!r} renders {min(counts)} words, under the "
                    f"{lint.MIN_WORDS}-word floor every email shape carries")
                self.assertLessEqual(
                    max(counts), lint.MAX_WORDS,
                    f"{name!r} renders {max(counts)} words, over the "
                    f"{lint.MAX_WORDS}-word standing ceiling")

    # The three bodies that were over ceiling when this file was written.
    # The rewrite LANDED - glm-c's trims, merged here as M5 - so all three
    # now pass and the `expectedFailure` markers were removed in the same
    # step that merged the trims. The ledger does not outlive the defect it
    # names. Numbers are min-max over every configured angle, counted with
    # lint.countable_words through the stage_s7 renderer; the bounds still
    # come from writercontract.

    def test_rung3_economic_buyer_is_over_the_em3_ceiling(self):
        entries = self.s7["rung3_economic_buyer"]
        _, ceiling = writercontract.word_range("em3")
        for entry in entries:
            self.assertLessEqual(
                _words(entry["body"]), ceiling,
                f"rung3_economic_buyer renders {_words(entry['body'])} "
                f"words for {entry['persona']}/{entry['angle_key']}, over "
                f"the em3 ceiling of {ceiling} - CANARY-01 B4, rewrite "
                f"owned by the operator")

    def test_angle_shift_champion_is_over_the_em4_ceiling(self):
        entries = self.s7["angle_shift_champion"]
        _, ceiling = writercontract.word_range("em4")
        for entry in entries:
            self.assertLessEqual(
                _words(entry["body"]), ceiling,
                f"angle_shift_champion renders {_words(entry['body'])} "
                f"words, over the em4 ceiling of {ceiling} - CANARY-01 B4, "
                f"rewrite owned by the operator")

    def test_angle_shift_economic_buyer_is_over_the_em4_ceiling(self):
        entries = self.s7["angle_shift_economic_buyer"]
        _, ceiling = writercontract.word_range("em4")
        for entry in entries:
            self.assertLessEqual(
                _words(entry["body"]), ceiling,
                f"angle_shift_economic_buyer renders "
                f"{_words(entry['body'])} words for "
                f"{entry['persona']}/{entry['angle_key']}, over the em4 "
                f"ceiling of {ceiling} - CANARY-01 B4, rewrite owned by "
                f"the operator")


if __name__ == "__main__":
    unittest.main()
