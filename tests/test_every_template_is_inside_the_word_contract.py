#!/usr/bin/env python3
"""Every cadence template is inside a word contract, structurally.

WHY THIS FILE EXISTS. CANARY-01's fourth exit criterion is that every
template `stage_s7_copy` can render passes both the word ceiling and the
word floor, with a RED test when a template escapes. Measured 2026-10-14
(`work/b4_measure.py`, gitignored, method below):

    angle_shift_champion            129 words   em4 45-90   OVER by 39
    angle_shift_economic_buyer    126-131 words   em4 45-90   OVER by 36-41
    rung3_economic_buyer            105 words   em3 60-90   OVER by 15
    BODY_1 (489 live copy, rendered)
                                  100-107 words   em1 60-90   OVER by 10-17

Counts are across the client's whole declared angle space (7 families);
the ranges move because the angle phrase is inside the body. BODY_1's
figure is the RENDERED count - placeholders replaced the way
`stage_s7_copy.render` replaces them - not the raw template text, whose
unrendered `{ANGLE}` placeholder undercounts by a dozen words.

and nothing failed, because no door applies a body word count to a
TEMPLATE. `lint.check` bounds the words stored ON A RECORD under a step
key; `stage_s7_copy.render` checks subjects and placeholders only; and
the six step-3/4/5 templates are bound to no cadence step at all - they
are rendered straight out of `cadence.TEMPLATES`. Six controls in this
repository have already been found unable to fail (NEXT-glm-c.md). This
file is built to be the seventh's opposite:

  - COVERAGE IS STRUCTURAL, not a hand-kept walk. The universe is
    `cadence.TEMPLATES` itself, and the binding map below must name
    every entry and nothing else, IN BOTH DIRECTIONS. A template added
    with no binding is a hard failure naming it - the way the phantom
    sinks in `tier_from_sinks.py` abort rather than silently skip - and
    a binding whose template was deleted fails too.
  - THE PROOF IS IN THE FILE, not in a one-off demonstration.
    `test_a_planted_uncovered_template_is_named` plants a probe template
    in the real universe, demands the guard name it, and restores the
    universe; `test_a_binding_for_an_absent_template_is_named` does the
    other direction. A pass here proves the guard ran, because the same
    function that returns [] also returns the probe's name when planted.
  - BOTH BOUNDS, ALWAYS. Ceiling and floor together, spelled from the
    one authority (`skills.cold_email_writing.WORD_CONTRACT`) and from
    `lint`'s own constants, never retyped here.

RED TODAY, DELIBERATELY. The four over-ceiling bodies above fail
`test_every_render_is_inside_both_bounds` and
`test_the_live_campaign_copy_is_inside_em1_and_em2` until the owner
rewrites them - per the lane brief, over-ceiling bodies are the owner's
to rewrite once he has been told exactly which and by how much. DO NOT
WIDEN A BOUND TO MAKE THESE PASS.

THE BINDING MAP, AND WHERE EACH ENTRY COMES FROM:

  - rung3_* -> em3, angle_shift_* -> em4, close_* -> em5.
    `stage_s7_copy._steps_three_four_and_five`'s own comment: "THE NAMES
    ARE STEP KEYS, NOT PROVIDER POSITIONS. `body_3` is em3's words
    because the step is called em3."
  - comparable_proof / comparable_proof_short -> em2. The proof beat is
    the second email of the five-step batch - BODY_2's slot - and the
    short one is its accepted-connection variant under balanced_v1's
    day10.
  - persona_pain, breakup -> the generic `lint.MIN_WORDS`..`MAX_WORDS`
    that `lint.check` applies at a day key today. No em slot names them;
    tightening them is the owner's call, recorded in
    docs/REVIEW-GLM-C-2026-10-14.md, not this file's guess.
  - linkedin_intro / linkedin_followup -> the note char bounds
    `lint.check_linkedin` applies, 40-300.

THE RENDER SPACE IS THE CLIENT'S OWN. Personas come from the template
names themselves and angle families from
`config/clients/productive.yaml` at import, so a new angle family is
rendered the day it is declared and a persona whose angles vanish is a
REFUSED failure, not a silent skip. An empty space fails every bounds
test with "walked no renders" - a vacuous pass is impossible. The lead
is a fixed synthetic one - Jane, Example Corp, industry "services" -
because the batch CSV is real prospect data that lives outside this
tree; only single-token stand-ins, so counts move by at most a word or
two against a real lead.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import cadence, clients, lint                           # noqa: E402
from src.skills import cold_email_writing as writer              # noqa: E402
import stage_s7_copy                                             # noqa: E402

CONFIG = clients.load("productive")

FIRST = "Jane"
COMPANY = "Example Corp"
INDUSTRY = "services"        # stand-in for the batch CSV's Industry column

# The six step-3/4/5 templates, by the slot stage_s7_copy renders them into.
S7_KINDS = ("rung3", "angle_shift", "close")
S7_SLOTS = {"3": "em3", "4": "em4", "5": "em5"}

# The declared binding: template name -> (kind, argument).
#   ("em", slot)       writer-contract slot; floor and ceiling both apply
#   ("generic", None)  lint's every-email 40..180 (what a day key gets today)
#   ("chars", "note")  the LinkedIn note bounds check_linkedin applies
TEMPLATE_BINDINGS = {
    "rung3_champion": ("em", "em3"),
    "rung3_economic_buyer": ("em", "em3"),
    "angle_shift_champion": ("em", "em4"),
    "angle_shift_economic_buyer": ("em", "em4"),
    "close_champion": ("em", "em5"),
    "close_economic_buyer": ("em", "em5"),
    "comparable_proof": ("em", "em2"),
    "comparable_proof_short": ("em", "em2"),
    "persona_pain": ("generic", None),
    "breakup": ("generic", None),
    "linkedin_intro": ("chars", "note"),
    "linkedin_followup": ("chars", "note"),
}


def declared_personas():
    """Personas named by the s7 templates themselves - so a new
    `rung3_<persona>` drags its persona into the universe automatically."""
    out = set()
    for name in cadence.TEMPLATES:
        for kind in S7_KINDS:
            if name.startswith(kind + "_"):
                out.add(name[len(kind) + 1:])
    return sorted(out)


def render_space():
    """[(persona, angle_key, angle_phrase)] - every persona an s7 template
    names crossed with every angle family the client declares for it."""
    space = []
    for persona in declared_personas():
        angles = clients.angles_for(CONFIG, persona) or {}
        if not angles:
            space.append((persona, None, None))
            continue
        for angle_key in sorted(angles):
            space.append((persona, angle_key, angles[angle_key]))
    return space


def s7_renders():
    """The six step-3/4/5 templates, through the same function batch 1
    calls, for the whole render space."""
    out = []
    for persona, angle_key, phrase in render_space():
        if angle_key is None:
            for kind in S7_KINDS:
                out.append({"template": f"{kind}_{persona}", "persona": persona,
                            "angle_key": None,
                            "refused": "the client config declares no angles "
                                       f"for persona {persona!r}"})
            continue
        fields, reason = stage_s7_copy._steps_three_four_and_five(
            persona, angle_key, phrase, FIRST, COMPANY, CONFIG)
        if reason:
            for kind in S7_KINDS:
                out.append({"template": f"{kind}_{persona}", "persona": persona,
                            "angle_key": angle_key, "refused": reason})
            continue
        for digit, slot in S7_SLOTS.items():
            out.append({"template": fields["template_" + digit],
                        "persona": persona, "angle_key": angle_key,
                        "slot": slot, "body": fields["body_" + digit]})
    return out


def hard_489_renders():
    """BODY_1/BODY_2 - campaign 489's live copy, verbatim from the module -
    rendered the way `stage_s7_copy.render` renders them: plain placeholder
    replacement, then the module's own unresolved-placeholder check."""
    out = []
    for persona, angle_key, phrase in render_space():
        if angle_key is None:
            continue
        fields = {"FIRST": FIRST, "COMPANY": COMPANY, "INDUSTRY": INDUSTRY,
                  "ANGLE": phrase}
        for slot, template in (("em1", stage_s7_copy.BODY_1),
                               ("em2", stage_s7_copy.BODY_2)):
            text = template
            for key, value in fields.items():
                text = text.replace("{" + key + "}", value)
            left = stage_s7_copy.PLACEHOLDER.search(text)
            if left:
                out.append({"slot": slot, "persona": persona,
                            "angle_key": angle_key,
                            "refused": f"did not fully render: "
                                       f"{left.group(0)}"})
                continue
            out.append({"slot": slot, "persona": persona,
                        "angle_key": angle_key, "body": text})
    return out


def template_renders():
    """Every non-s7 entry in cadence.TEMPLATES through
    cadence.template_vars + cadence.render - the path `cadence.expand_step`
    takes - for the whole render space."""
    s7_names = {f"{kind}_{p}" for kind in S7_KINDS for p in declared_personas()}
    rec = {"id": "word-contract-guard", "company": COMPANY,
           "domain": "example.com", "client": "productive",
           "state": "qualified", "contacts": []}
    out = []
    for name, template in sorted(cadence.TEMPLATES.items()):
        if name in s7_names:
            continue
        for persona, angle_key, _phrase in render_space():
            if angle_key is None:
                continue
            contact = {"key": "guard-c1", "name": FIRST + " Doe",
                       "title": "Head of Operations", "persona": persona,
                       "angle": angle_key,
                       "linkedin": "https://www.linkedin.com/in/guardc1"}
            rec["contacts"] = [contact]
            values = cadence.template_vars(rec, contact, CONFIG)
            try:
                parts = cadence.render(template, values)
            except Exception as exc:
                # a template that cannot render for a declared persona and
                # family is a failure naming it, never a skip
                out.append({"template": name, "persona": persona,
                            "angle_key": angle_key,
                            "refused": f"{type(exc).__name__}: {exc}"})
                continue
            out.append({"template": name, "persona": persona,
                        "angle_key": angle_key,
                        "body": parts.get("body"),
                        "note": parts.get("note")})
    return out


def bounds_for(name):
    """(floor, ceiling) for a bound template, spelled from the authority."""
    kind, arg = TEMPLATE_BINDINGS[name]
    if kind == "em":
        low, _target, high = writer.WORD_CONTRACT[arg]
        return low, high
    if kind == "generic":
        return lint.MIN_WORDS, lint.MAX_WORDS
    raise AssertionError(f"unknown binding kind {kind!r} for {name!r}")


def word_failures(renders, slot_bounds=None):
    """One line per render outside its bounds, naming template, count,
    contract and the over/under amount - the owner's rewrite list."""
    fails = []
    for r in renders:
        name = r.get("template") or r.get("slot")
        where = (f"persona {r['persona']!r}, angle family "
                 f"{r['angle_key']!r}")
        if r.get("refused"):
            fails.append(f"{name}: REFUSED - {r['refused']} ({where})")
            continue
        if slot_bounds:
            low, _target, high = slot_bounds[r["slot"]]
        else:
            low, high = bounds_for(name)
        words = len(lint.countable_words(r["body"]))
        if words > high:
            fails.append(f"{name}: {words} words, contract {low}-{high}, "
                         f"OVER by {words - high} ({where})")
        elif words < low:
            fails.append(f"{name}: {words} words, contract {low}-{high}, "
                         f"UNDER by {low - words} ({where})")
    return fails


def coverage_failures():
    """The structural coverage check: every template bound, every binding
    live. Empty means green; the planted-probe test proves it can be
    non-empty."""
    templates = set(cadence.TEMPLATES)
    bound = set(TEMPLATE_BINDINGS)
    fails = []
    for name in sorted(templates - bound):
        fails.append(f"template {name!r} has no word-contract binding: add it "
                     f"to TEMPLATE_BINDINGS or remove the template")
    for name in sorted(bound - templates):
        fails.append(f"TEMPLATE_BINDINGS names {name!r}, which is not in "
                     f"cadence.TEMPLATES: a deleted template must take its "
                     f"binding with it")
    return fails


class TestCoverageIsStructural(unittest.TestCase):

    def test_the_universe_and_the_binding_map_name_the_same_templates(self):
        self.assertTrue(cadence.TEMPLATES,
                        "cadence.TEMPLATES is empty: the guard walked no "
                        "universe, which is a broken guard, not a green one")
        self.assertTrue(TEMPLATE_BINDINGS,
                        "TEMPLATE_BINDINGS is empty: same broken-guard state")
        self.assertEqual(coverage_failures(), [])

    def test_a_planted_uncovered_template_is_named(self):
        probe = "zzz_planted_uncovered_probe"
        self.assertNotIn(probe, cadence.TEMPLATES)
        cadence.TEMPLATES[probe] = {"subject": "planted", "body": "planted"}
        try:
            fails = coverage_failures()
        finally:
            del cadence.TEMPLATES[probe]
        self.assertNotIn(probe, cadence.TEMPLATES)
        self.assertEqual(
            fails,
            [f"template {probe!r} has no word-contract binding: add it to "
             f"TEMPLATE_BINDINGS or remove the template"],
            "the guard must name the planted template, and only it")

    def test_a_binding_for_an_absent_template_is_named(self):
        victim = "breakup"
        self.assertIn(victim, cadence.TEMPLATES)
        removed = cadence.TEMPLATES.pop(victim)
        try:
            fails = coverage_failures()
        finally:
            cadence.TEMPLATES[victim] = removed
        self.assertIn(victim, cadence.TEMPLATES)
        self.assertTrue(any(victim in f for f in fails),
                        f"the guard must name the deleted template: {fails}")


class TestTheSixStep345Templates(unittest.TestCase):
    """RED today on three bodies - angle_shift_champion (129 words, over by
    39 in every champion family), angle_shift_economic_buyer (126-131, over
    by 36-41), rung3_economic_buyer (105, over by 15 in every family) -
    until the owner rewrites them. Do not widen em3/em4 to fix it."""

    def test_every_render_is_inside_both_bounds(self):
        renders = s7_renders()
        self.assertGreater(
            len(renders), 0,
            "the guard walked no renders: the client config declared no "
            "personas or angles, which is a broken guard, not a green one")
        self.assertEqual(word_failures(renders), [])


class TestThe489Copy(unittest.TestCase):
    """Campaign 489's live copy, verbatim, rendered. RED today on BODY_1 -
    100-107 words against em1's 90, over by 10-17 depending on angle
    family - until the owner rewrites it. BODY_2 is inside em2."""

    def test_the_live_campaign_copy_is_inside_em1_and_em2(self):
        renders = hard_489_renders()
        self.assertGreater(
            len(renders), 0,
            "the guard walked no renders: the client config declared no "
            "personas or angles, which is a broken guard, not a green one")
        self.assertEqual(word_failures(renders, slot_bounds=writer.WORD_CONTRACT),
                         [])


class TestTheDayKeyedAndProofTemplates(unittest.TestCase):

    def test_every_render_is_inside_both_bounds(self):
        renders = [r for r in template_renders()
                   if TEMPLATE_BINDINGS[r["template"]][0] in ("em", "generic")]
        self.assertGreater(
            len(renders), 0,
            "the guard walked no renders: the client config declared no "
            "personas or angles, which is a broken guard, not a green one")
        self.assertEqual(word_failures(renders), [])


class TestTheLinkedinTemplates(unittest.TestCase):

    def test_the_notes_are_inside_the_char_bounds(self):
        fails = []
        checked = 0
        for r in template_renders():
            if TEMPLATE_BINDINGS[r["template"]][0] != "chars":
                continue
            if r.get("refused"):
                fails.append(f"{r['template']}: REFUSED - {r['refused']} "
                             f"(persona {r['persona']!r}, angle family "
                             f"{r['angle_key']!r})")
                continue
            note = r["note"] or ""
            checked += 1
            if len(note) > lint.NOTE_MAX_CHARS:
                fails.append(f"{r['template']}: {len(note)} chars, over "
                             f"{lint.NOTE_MAX_CHARS} by "
                             f"{len(note) - lint.NOTE_MAX_CHARS}")
            elif len(note) < lint.NOTE_MIN_CHARS:
                fails.append(f"{r['template']}: {len(note)} chars, under "
                             f"{lint.NOTE_MIN_CHARS} by "
                             f"{lint.NOTE_MIN_CHARS - len(note)}")
        self.assertGreater(
            checked, 0,
            "the guard walked no linkedin renders: a vacuous pass is not a "
            "pass")
        self.assertEqual(fails, [])


if __name__ == "__main__":
    unittest.main()
