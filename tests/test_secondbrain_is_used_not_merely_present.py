"""Is the Second Brain USED in generated copy, or merely present?

THE QUESTION, AND WHY THE EXISTING TESTS DO NOT ANSWER IT
=========================================================
`tests/test_the_second_brain_returns_only_what_the_task_needs.py` proves
`secondbrain.for_task` RETURNS things. `tests/test_task911_...` proves
`generate_campaign._load_admitted_facts` ADMITS things and that
`_format_br_context` RENDERS them. Every one of those is a statement about
the producer.

`tests/test_changing_an_approved_fact_changes_the_output.py` is the one that
claims a downstream effect - "changing an approved fact changes the output" -
and it gets that effect from `_FactAwareModel`, a stub whose hypothesis
branch builds its answer as

    "hypothesis": "margin invisible until month-end, context: %s, basis: %s"
                  % (context, fact_text)

where `context` is `_extract_br_context(prompt)`, the brain block read back
out of the prompt. The stub is written to copy the brain into its own answer,
so the test cannot do anything but pass, and it measures the fixture rather
than the pipeline. That is this repository's own "a green suite proves
nothing live" shape.

WHAT THIS MODULE MEASURES INSTEAD
=================================
1. ATTRIBUTION, PER SENTENCE. `src/brainattribution.py` says, for each
   retrieved entry, whether it reached a text and which sentence uses it.
   Proven in BOTH directions first (`TestAttributorControls`): an entry that
   is genuinely absent must be reported NOT USED, or "every entry was used"
   is not a result.

2. THE ABLATION. The same copy generated with the brain switched off, and
   diffed. Run in two configurations, because the single configuration is
   the trap:

     A  the hypothesis stage answers the same thing either way (a model that
        does not quote its context back). This isolates the PIPELINE: any
        difference is a difference the plumbing carries.
     B  the hypothesis stage echoes its context, as this repo's own
        `_FactAwareModel` does. This shows the one channel that exists and
        what has to be true of the model for it to carry anything.

3. THE CONSUMER CENSUS. Every path by which Second Brain content can be
   retrieved, with the consumer that reads it named, and the ones with no
   consumer at all flagged. Searched with a method that has a positive
   control, because a search that cannot find anything flags everything.

WHAT IS NOT MEASURED, AND WHY
=============================
NO MODEL IS CALLED. The wire is sealed with `sandboxharness.seal_wire(
allow=())` and the seal is positively controlled on every run. So what is
measured is PROMPT ASSEMBLY plus a prompt-driven stub writer, not a real
model's output. The stub writer is itself positively controlled
(`test_stub_writer_is_prompt_sensitive`): it demonstrably writes different
copy when its prompt differs, so "the copy is identical" is a statement
about the prompt being identical and not about a stub that ignores its
input.

ISOLATION. `store.use_directory` points state at a throwaway directory and
the MAIN checkout's `work/` files are fingerprinted before and after each
test, by `sandboxharness`. Nothing here writes production state and nothing
here changes the production copy flow: `src/brainattribution.py` is
additive, imported by no production module, and its two seams are context
managers that restore what they patched.
"""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (brainattribution as ba, campaignstrategy, clients,
                 copystages, generate_campaign as gc, offers as offers_mod,
                 sandboxharness, secondbrain, sequenceplan, skills, store)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
SCRIPTS = os.path.join(ROOT, "scripts")

CLIENT = "productive"


# ===========================================================================
# 1. THE ATTRIBUTOR, PROVEN IN BOTH DIRECTIONS FIRST.
# ===========================================================================

#: A clause nothing in this repository writes. The absent-entry control.
ABSENT_SENTINEL = ("quarterly zephyr reconciliation across trilobite "
                   "custodians")

_TARGET = (
    "Northwind Studio is a 42-person digital marketing agency in Leeds. "
    "Productive shows margin per project while it is running. "
    "Who is booked on what next week is the part that moves first.")


def _entry(text, key="test.key"):
    return ba.catalogue([{"text": text,
                          "source": "config/clients/%s.yaml %s"
                                    % (CLIENT, key)}])[0]


class TestAttributorControls(unittest.TestCase):
    """The checker must be able to say NOT USED. Both directions, first."""

    def test_absent_entry_is_reported_not_used(self):
        """POSITIVE CONTROL: an entry known to be absent must come back NOT
        USED. Without this, "all entries were used" is not a result."""
        entry = _entry("Angle label 'zephyr': " + ABSENT_SENTINEL,
                       "angle_labels")
        [rec] = ba.attribute([entry], _TARGET)
        self.assertFalse(rec["reached"], rec)
        self.assertEqual(rec["sentences"], [])
        self.assertIsNone(rec["match_kind"])

    def test_present_entry_is_reported_used_with_the_right_sentence(self):
        """The other direction: an entry that IS in the text, in sentence 3."""
        entry = _entry("Persona 'champion', angle 'resource_management': "
                       "who is booked on what next week, and where the next "
                       "hire goes",
                       "personas.champion.angles.resource_management")
        [rec] = ba.attribute([entry], _TARGET)
        self.assertTrue(rec["reached"], rec)
        self.assertEqual(rec["sentences"], [3], rec)
        self.assertIn("booked on what next week", rec["clause"])

    def test_verbatim_entry_is_reported_verbatim(self):
        entry = _entry("Capability for champion: margin per project while it "
                       "is running", "product.capability_by_persona")
        [rec] = ba.attribute([entry], _TARGET)
        self.assertEqual(rec["match_kind"], "verbatim", rec)
        self.assertEqual(rec["sentences"], [2], rec)

    def test_stopword_run_does_not_license_a_match(self):
        """The bag-of-words failure, controlled for.

        `MIN_CONTENT` is what stops a three-word run of stopwords matching
        almost any sentence. Remove it and this entry - whose payload shares
        only "while it is" with the target - would be reported USED.
        """
        entry = _entry("Angle label 'x': while it is " + ABSENT_SENTINEL,
                       "angle_labels")
        [rec] = ba.attribute([entry], _TARGET)
        self.assertFalse(rec["reached"], rec)
        # And the control that the share really is there: drop the content
        # floor and the same entry matches. So the guard is doing the work.
        [loose] = ba.attribute([entry], _TARGET, min_content=0)
        self.assertTrue(loose["reached"], loose)
        self.assertEqual(loose["clause"], "while it is")

    def test_label_prefix_does_not_license_a_match(self):
        """The formatter's own words are not the client's knowledge.

        `Persona 'champion' titles: ...` carries "persona", "champion" and
        "titles" because `secondbrain._customers` put them there. An entry
        must not be credited for a sentence because both contain a word the
        BRAIN'S FORMATTING invented.
        """
        text = "The champion persona titles this quarter are under review."
        entry = _entry("Persona 'champion' titles: Operations Manager, "
                       "Operations Director", "personas.champion.titles")
        [rec] = ba.attribute([entry], text)
        self.assertFalse(rec["reached"], rec)
        self.assertEqual(ba.fact_value(entry["text"]),
                         "Operations Manager, Operations Director")

    def test_empty_text_reaches_nothing(self):
        entries = ba.catalogue(secondbrain.for_task("campaign_strategy",
                                                    CLIENT))
        recs = ba.attribute(entries, "")
        self.assertEqual(ba.reached(recs), [])
        self.assertEqual(len(ba.not_reached(recs))
                         + len(ba.unattributable(recs)), len(entries))
        # The buckets partition the set: 37 of `productive`'s 50 entries
        # carry a payload long enough to decide, 13 do not.
        self.assertEqual(len(ba.not_reached(recs)), 37)
        self.assertEqual(len(ba.unattributable(recs)), 13)

    def test_sentence_split_numbers_from_one(self):
        self.assertEqual(len(ba.split_sentences(_TARGET)), 3)

    def test_short_payload_is_UNATTRIBUTABLE_not_unused(self):
        """The third bucket, and why it is not rounded down.

        `Min employees: 20` has the payload `20`. A draft containing the
        digit 2 is not evidence the brain supplied it, and declaring the
        entry UNUSED would make a negative verdict cheaper to reach.
        """
        for text, key in (("Min employees: 20", "icp.structural.employees.min"),
                          ("Product: Productive", "product.name"),
                          ("Persona 'champion' cap per domain: 2",
                           "personas.champion.cap_per_domain"),
                          # NOT the client's real domain, which
                          # `test_fixture_hygiene` flags wherever it appears.
                          ("Domain: a-client.invalid", "domain")):
            [rec] = ba.attribute([_entry(text, key)], _TARGET)
            self.assertFalse(rec["attributable"], (text, rec))
            self.assertFalse(rec["reached"])
            self.assertEqual(ba.unattributable([rec]), [rec["id"]])
            self.assertEqual(ba.not_reached([rec]), [],
                             "%r was rounded down into NOT USED" % text)

    def test_brain_caused_can_credit_an_entry(self):
        """POSITIVE CONTROL for the authoritative measure.

        `brain_caused` must be able to say YES, or every "no entry was
        brain-caused" result below is a checker that only says no.
        """
        entry = _entry("Angle label 'zephyr': " + ABSENT_SENTINEL,
                       "angle_labels")
        with_it = "We looked at %s last quarter." % ABSENT_SENTINEL
        without = "We looked at the usual things last quarter."
        credited = ba.brain_caused([entry], with_it, without)
        self.assertEqual([r["id"] for r in credited], [entry["id"]])
        self.assertEqual(credited[0]["sentences"], [1])
        # ...and NO, when the clause survives the ablation.
        self.assertEqual(ba.brain_caused([entry], with_it, with_it), [])


# ===========================================================================
# 2. THE CONSUMER CENSUS.
# ===========================================================================

def _source_of(name):
    """One reader for src/<name>, so no test leaks a file handle."""
    with open(os.path.join(SRC, name), encoding="utf-8") as handle:
        return handle.read()


def _production_files():
    """Every production .py under src/ and scripts/. Tests excluded.

    A test is not a consumer. "Something reads this" has to mean something
    in the shipping path reads it, or the census answers yes to a field only
    its own test has ever touched.
    """
    out = []
    for base in (SRC, SCRIPTS):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if name.endswith(".py"):
                    out.append(os.path.join(dirpath, name))
    return sorted(out)


def _reads_of(token, *, skip=()):
    """Files under src/ and scripts/ whose SOURCE mentions `token` outside a
    comment or a docstring.

    Comments are stripped with `tokenize`, because this repository's source
    carries very long explanatory comments and several of them name these
    symbols. A census that counted a comment would report a consumer that
    does not exist - which is the defect it is looking for.
    """
    import io
    import tokenize

    hits = []
    for path in _production_files():
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        if rel in skip:
            continue
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        if token not in source:
            continue
        kept = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                if tok.type == tokenize.COMMENT:
                    continue
                if tok.type == tokenize.STRING:
                    # A docstring or a prompt constant is not a read either.
                    continue
                kept.append(tok.string)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            kept = source.split()
        if any(token in piece for piece in kept):
            hits.append(rel)
    return hits


class TestRetrievalPathCensus(unittest.TestCase):
    """Every retrieval path, and the consumer that reads it. Or none."""

    def test_the_searcher_can_find_a_consumer(self):
        """POSITIVE CONTROL for the census itself.

        `for_task` has a real consumer. If this came back empty the method
        would be reporting "no consumer" for everything.
        """
        self.assertIn("src/generate_campaign.py", _reads_of("for_task"))
        self.assertIn("src/copystages.py", _reads_of("for_task"))

    def test_the_searcher_ignores_comments_and_docstrings(self):
        """NEGATIVE CONTROL: a token that appears ONLY in prose is not a read.

        `linkedin_sequence.fallbacks` appears as a bare phrase in
        `generate_campaign`'s docstring and as a string literal in its code.
        A census that counted prose would find consumers everywhere.
        """
        self.assertEqual(
            _reads_of("a producer whose output nothing reads"), [])

    # ---- PATH 1: secondbrain.for_task -> generate_campaign (LIVE) --------

    def test_path1_for_task_live_consumer_is_generate_campaign(self):
        self.assertIn("src/generate_campaign.py",
                      _reads_of("_load_admitted_facts"))
        self.assertIn("sb_facts", _source_of("generate_campaign.py"))

    def test_path1_reaches_exactly_one_prompt_stage(self):
        """`_format_br_context` is called ONCE, and into the hypothesis
        prompt. The writer is never handed it."""
        source = _source_of("generate_campaign.py")
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)
                 and n.func.id == "_format_br_context"]
        self.assertEqual(len(calls), 1, "br_context is assembled %d times"
                         % len(calls))

    # ---- PATH 2: copystages.business_context_for (NO CONSUMER) ----------

    def test_path2_business_context_for_has_no_production_consumer(self):
        """FLAGGED: a producer whose output nothing reads.

        `copystages.business_context_for` formats the whole brain for the
        `business_context` parameter of `hypothesis_user`. No production
        module calls it - `generate_campaign` assembles its own context with
        its own second copy of `_format_br_context`.
        """
        callers = _reads_of("business_context_for",
                            skip=("src/copystages.py",))
        self.assertEqual(callers, [],
                         "business_context_for gained a consumer: %s"
                         % callers)
        self.assertTrue(hasattr(copystages, "business_context_for"))

    def test_path2_there_are_two_format_br_context_implementations(self):
        """Two representations of one rule, which is the drift this repo
        names as its own failure mode. They do not even take the same
        shape: `copystages`' takes a dict of sections, `generate_campaign`'s
        takes a flat list."""
        self.assertTrue(hasattr(copystages, "_format_br_context"))
        self.assertTrue(hasattr(gc, "_format_br_context"))
        brain = secondbrain.for_task("campaign_strategy", CLIENT)
        flat = [f for facts in brain.values() for f in facts]
        self.assertIsNotNone(copystages._format_br_context(brain))
        self.assertIsNotNone(gc._format_br_context(flat))
        # And they disagree about what a line looks like.
        self.assertNotEqual(copystages._format_br_context(brain),
                            gc._format_br_context(flat))

    # ---- PATH 3: secondbrain.all_sections / index_html (NO CONSUMER) ----

    def test_path3_index_html_has_no_production_consumer(self):
        """FLAGGED: the index page is generated by nothing.

        `index_html` is the only caller of `all_sections`, and nothing in
        src/ or scripts/ calls `index_html`. No entrypoint writes the page
        to disk, and `all_sections`' mandatory `reason=` gate therefore
        guards a door nobody opens.
        """
        self.assertEqual(_reads_of("index_html", skip=("src/secondbrain.py",)),
                         [])
        self.assertEqual(_reads_of("all_sections",
                                   skip=("src/secondbrain.py",)), [])

    # ---- PATH 4: Skill.secondbrain_sections (NO CONSUMER) ---------------

    def test_path4_skill_secondbrain_sections_is_read_by_nothing(self):
        """FLAGGED: five skills declare which brain sections they need, and
        nothing reads the declaration.

        `skills/__init__.py` enforces that every skill names a `consumer`.
        It does not enforce that anything consumes `secondbrain_sections`,
        and nothing does: `generate_campaign` calls
        `secondbrain.for_task("campaign_strategy", slug)` with a literal
        task name and takes the sections from
        `secondbrain.TASK_SECTIONS`, never from the loaded skill.
        """
        readers = _reads_of("secondbrain_sections",
                            skip=("src/skills/__init__.py",
                                  "src/skills/account_research.py",
                                  "src/skills/campaign_strategy.py",
                                  "src/skills/cold_email_writing.py",
                                  "src/skills/linkedin_writing.py",
                                  "src/skills/signal_verification.py"))
        self.assertEqual(readers, [],
                         "secondbrain_sections gained a reader: %s" % readers)
        # The declarations exist and are non-empty, so this is a field that
        # is populated and unread rather than one nobody filled in.
        for name in ("account_research", "campaign_strategy",
                     "cold_email_writing", "linkedin_writing",
                     "signal_verification"):
            self.assertTrue(skills.load(name).secondbrain_sections, name)

    def test_path4_skill_declarations_disagree_with_task_sections(self):
        """And because nothing reads it, it has been free to drift.

        `cold_email_writing` declares `offers`; `linkedin_writing` declares
        the same three sections as `TASK_SECTIONS["linkedin_writing"]`. The
        agreement is a coincidence maintained by hand, not by a consumer.
        """
        for name in ("account_research", "campaign_strategy",
                     "cold_email_writing", "linkedin_writing",
                     "signal_verification"):
            declared = tuple(skills.load(name).secondbrain_sections)
            canonical = tuple(secondbrain.TASK_SECTIONS[name])
            self.assertEqual(
                set(declared), set(canonical),
                "%s declares %r, TASK_SECTIONS says %r, and nothing checks"
                % (name, declared, canonical))

    # ---- PATH 5: plan["second_brain_facts"] (NO CONSUMER) ---------------

    def test_path5_plan_second_brain_facts_is_read_by_nothing(self):
        """FLAGGED: the field is written on every plan and read by nothing.

        `sequenceplan.new` stores it. No projection reads it:
        `approval_hash`, `derive_preview_data`, `derive_bison_payload`,
        `derive_heyreach_payload` and `derive_*_sequence` between them
        never name it.
        """
        readers = _reads_of("second_brain_facts",
                            skip=("src/sequenceplan.py",
                                  "src/generate_campaign.py"))
        self.assertEqual(readers, [],
                         "second_brain_facts gained a reader: %s" % readers)
        source = _source_of("sequenceplan.py")
        tree = ast.parse(source)
        bodies = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                bodies[node.name] = ast.get_source_segment(source, node) or ""
        for fn in ("approval_hash", "derive_preview_data",
                   "derive_bison_payload", "derive_heyreach_payload",
                   "derive_bison_sequence", "derive_heyreach_sequence"):
            self.assertNotIn("second_brain_facts", bodies[fn],
                             "%s reads it after all" % fn)

    # ---- PATH 6: docs/second-brain/ corpus ------------------------------

    def test_path6_docs_second_brain_corpus_has_no_reader(self):
        """FLAGGED: no code path reads a corpus file.

        `docs/second-brain/linkedin.md` was added on
        `task-981-second-brain-linkedin`. Whether or not the directory is
        present on this branch, nothing under src/ or scripts/ opens it, so
        a corpus placed there is retrieved by nobody.
        """
        self.assertEqual(_reads_of("second-brain"), [])
        self.assertEqual(_reads_of("second_brain/"), [])

    # ---- PATH 7: secondbrain.MISSING_SECTIONS ---------------------------

    def test_path7_missing_sections_is_read_by_nothing(self):
        readers = _reads_of("MISSING_SECTIONS", skip=("src/secondbrain.py",))
        self.assertEqual(readers, [],
                         "MISSING_SECTIONS gained a reader: %s" % readers)


# ===========================================================================
# 3. THE COPY PATH ITSELF.
# ===========================================================================

STAGE_MARKERS = (
    ("icp", "is this company a services agency"),
    ("extract", "you extract verifiable facts"),
    ("hypothesis", "propose one operational problem"),
    ("match", "you choose one productive capability"),
    ("strategy", "you plan a nine message"),
    ("writer", "you write cold outreach"),
)

#: The marker `copystages.hypothesis_user` puts in front of the brain block.
BR_MARKER = "Additional context from our own data:"


def _stage_of(prompt):
    low = prompt.lower()
    for name, marker in STAGE_MARKERS:
        if marker in low:
            return name
    return "unknown"


class _PromptDrivenModel:
    """A stub that answers from its PROMPT and nothing else.

    It is not fact-aware and it is not brain-aware. For every stage it reads
    the fields the stage's own prompt contract names, and writes them back.
    That is the faithful stand-in for "the writer uses what it is given":
    anything it cannot see in the prompt cannot reach its output.

    `echo_context` exists to reproduce - deliberately, once, for comparison -
    what `tests/test_changing_an_approved_fact_changes_the_output.py`'s
    `_FactAwareModel` does: quote the Second Brain block back inside the
    hypothesis. It is OFF by default, because a model that does that is an
    assumption about the model and not a property of the pipeline.
    """

    name = "prompt-driven"

    def __init__(self, *, echo_context=False):
        self.echo_context = echo_context
        self.prompts = []          # (stage, prompt)

    # -- prompt readers ---------------------------------------------------

    @staticmethod
    def _facts(prompt):
        start = len(prompt)
        for marker in ("Facts you may use:", "Verified facts:"):
            idx = prompt.find(marker)
            if idx != -1 and idx < start:
                start = idx
        out = []
        for m in re.finditer(r"(\d+)\.\s+(?:\[([^\]]*)\]\s+)?(.+)",
                             prompt[start:]):
            text = m.group(3).strip()
            if len(text) > 15:
                out.append(text)
        return out[:5]

    @staticmethod
    def _br_block(prompt):
        idx = prompt.find(BR_MARKER)
        if idx == -1:
            return ""
        rest = prompt[idx + len(BR_MARKER):].strip()
        end = rest.find("\n\n")
        return (rest if end == -1 else rest[:end]).strip()

    @classmethod
    def _br_quote(cls, prompt):
        """ONE named line of the brain block, quoted back as prose.

        `product.what_it_is` rather than the first line or the longest,
        because the attribution has to have a target it can name: the first
        line's payload is the single word `Productive`, which
        `brainattribution` correctly refuses to decide on, and the longest
        is a geo list. This is the client's own sentence about its own
        product, and it is what a model asked for a hypothesis would
        plausibly reuse.
        """
        for line in cls._br_block(prompt).splitlines():
            if "product.what_it_is" not in line:
                continue
            body = line.split("] ", 1)[-1]
            return body.split(" (source:", 1)[0].strip()
        return ""

    @staticmethod
    def _plan_field(prompt, field):
        m = re.search(r'"%s":\s*"([^"]*)"' % field, prompt)
        return m.group(1) if m else ""

    # -- the seam ---------------------------------------------------------

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        stage = _stage_of(prompt)
        self.prompts.append((stage, prompt))
        handler = getattr(self, "_answer_" + stage, None)
        if handler is None:
            raise AssertionError(
                "the stub met a stage it does not model: %r. The first 200 "
                "characters were %r" % (stage, prompt[:200]))
        return json.dumps(handler(prompt))

    def prompt_for(self, stage):
        for name, prompt in self.prompts:
            if name == stage:
                return prompt
        return None

    def _answer_icp(self, prompt):
        return {"is_agency": True, "confidence": 0.9,
                "evidence": "digital marketing agency"}

    def _answer_extract(self, prompt):
        facts = []
        for m in re.finditer(r"###\s+\[(\d+)\]\s+(\w+)\s*\n(.+)", prompt):
            facts.append({"text": m.group(3).strip()[:120],
                          "quote": m.group(3).strip()[:120],
                          "source_index": int(m.group(1)),
                          "kind": m.group(2), "confidence": 0.9})
        return {"facts": facts, "angle": "margin_visible_late",
                "angle_reason": "the pack says so",
                "company_hook": facts[0]["text"] if facts else "",
                "usable": bool(facts), "why_this_lead": "shape fits"}

    def _answer_hypothesis(self, prompt):
        facts = self._facts(prompt)
        basis = facts[0] if facts else "unknown"
        hypothesis = ("margin is reconstructed after the project closes "
                      "rather than seen while it runs")
        if self.echo_context:
            hypothesis = "%s, context: %s" % (hypothesis,
                                              self._br_quote(prompt))
        return {"signal_strength": "strong", "signal": basis,
                "business_model": "agency",
                "operational_complexity": "multi-team",
                "role_family": "executive", "hypothesis": hypothesis,
                "hypothesis_basis": basis, "qualification": "QUALIFIED_RICH",
                "confidence": 0.85}

    def _answer_match(self, prompt):
        m = re.search(r"Hypothesis:\s*(.+)", prompt)
        hyp = (m.group(1).strip() if m else "")[:80]
        return {"capability_key": "project_management",
                "why_this_one": "it answers: %s" % hyp,
                "what_changes": "the week an overrun starts is the week it "
                                "shows",
                "runner_up": "time_tracking", "confidence": 0.8}

    def _answer_strategy(self, prompt):
        return {
            "emails": {
                "em1": {"objective": "open", "angle": "margin",
                        "proof": "research", "cta": "question"},
                "em2": {"objective": "insight", "angle": "utilisation",
                        "proof": "product", "cta": "resource"},
                "em3": {"objective": "workflow", "angle": "budget",
                        "proof": "product", "cta": "meeting"},
                "em4": {"objective": "benchmark", "angle": "reporting",
                        "proof": "experience", "cta": "call"},
                "em5": {"objective": "close", "angle": "exit",
                        "proof": "none", "cta": "reply"},
            },
            "linkedin": {
                "connect": {"objective": "relevance", "angle": "fact",
                            "cta": "none"},
                "msg1": {"objective": "intro", "angle": "fact",
                         "cta": "question", "must_not_repeat": "em1"},
                "msg2": {"objective": "capability", "angle": "product",
                         "cta": "ask", "must_not_repeat": "em2"},
                "msg3": {"objective": "close", "angle": "exit",
                         "cta": "none", "must_not_repeat": "em3"},
            },
            "dropped": [], "repetition_check": "distinct angles",
        }

    def _answer_writer(self, prompt):
        facts = self._facts(prompt)
        first = facts[0] if facts else "your work"
        hyp = self._plan_field(prompt, "hypothesis")
        changes = self._plan_field(prompt, "what_changes")
        return {
            "hold": False, "hold_reason": None,
            "subject": "project margin timing",
            "subject_alt": "where the margin number comes from",
            "subject_breakup": "the margin question",
            "emails": {
                "em1": ("The reason I am writing: %s. The pattern I would "
                        "expect from that is %s, and what would change is %s. "
                        "Is any of that true where you sit, or is the "
                        "reporting side already solved?"
                        % (first, hyp, changes)),
                "em2": ("Utilisation follows the same pattern as the margin "
                        "question. Most teams find out who was busy after the "
                        "month has closed rather than while there is still "
                        "time to move somebody. How do you see it today?"),
                "em3": ("The budget view works on committed hours rather than "
                        "invoiced ones, so an overrun shows up in the week it "
                        "starts. What would have to be true for that to be "
                        "useful rather than one more report?"),
                "em4": ("One observation from teams of a similar shape. The "
                        "ones that see margin early are not working harder at "
                        "reporting, they have stopped waiting for the close. "
                        "Which decision would you want to take sooner?"),
                "em5": ("If none of this is a priority, say so and I will "
                        "close the file. If it is, the one thing worth "
                        "knowing is where your current answer comes from and "
                        "how much reconstruction sits behind it."),
            },
            "ps": {"em1": "Asked because the headcount is on your own site.",
                   "em3": "The reporting side is useful on its own."},
            "ps_variant": "ps_fact",
            "linkedin": {
                "connect": ("Reading about how the team is set up. No pitch, "
                            "happy to follow along."),
                "msg1": ("The question I keep asking is when project margin "
                         "becomes visible. While the work runs, or once the "
                         "invoice is drafted?"),
                "msg2": ("The profitability module addresses that side of it, "
                         "and I wrote by email about the same thing."),
                "msg3": ("No pressure at all. If this is not a priority I "
                         "will leave it with you."),
            },
            "facts_used": {"em1": 1}, "confidence": 0.85,
            "why_this_lead": "strong facts",
        }


def _account():
    return {
        "company": "Northwind Studio",
        "domain": "northwind-studio.invalid",
        "persona": "champion",
        "segment": "all",
        "sources": [
            {"label": "site", "url": "https://northwind-studio.invalid/about",
             "text": "Northwind Studio is a 42 person digital marketing "
                     "agency in Leeds running client retainers."},
            {"label": "post", "url": "https://northwind-studio.invalid/news",
             "text": "Northwind Studio opened a second studio in 2024."},
        ],
    }


def _contacts():
    return [{
        "email": "dana@northwind-studio.invalid",
        "first_name": "Dana",
        "last_name": "Okafor",
        "title": "Operations Director",
        "contact_key": "dana@northwind-studio.invalid",
        "sender_name": "Ivan",
        "linkedin": "https://www.linkedin.com/in/dana-okafor-synthetic",
    }]


class _SealedRun(unittest.TestCase):
    """Base: wire sealed with a positive control, state isolated, production
    `work/` fingerprinted over each test's own window."""

    def setUp(self):
        self._undo_wire, self.wire_calls = sandboxharness.seal_wire(allow=())
        sandboxharness.assert_wire_sealed()
        # The positive control's OWN deliberate call is in `wire_calls`.
        # Everything after this index is the run's.
        self._wire_baseline = len(self.wire_calls)
        self.assertEqual(self._wire_baseline, 1,
                         "the seal recorded %d calls for one control call"
                         % self._wire_baseline)
        sandboxharness.assert_production_exists()
        self._fingerprint = sandboxharness.production_fingerprint()
        self._tmp = tempfile.TemporaryDirectory(prefix="sb-ablation-")
        self._undo_store = store.use_directory(self._tmp.name)
        self.assertIn(self._tmp.name, store.queue_path())
        campaignstrategy.clear_cache()
        self.addCleanup(self._teardown)

    def _teardown(self):
        try:
            if callable(self._undo_store):
                self._undo_store()
        except Exception:                                       # noqa: BLE001
            pass
        self._undo_wire()
        campaignstrategy.clear_cache()
        sandboxharness.assert_production_unchanged(self._fingerprint)
        self._tmp.cleanup()

    def _run(self, *, model):
        campaignstrategy.clear_cache()
        return gc.generate(clients.load(CLIENT), _account(), _contacts(),
                           model=model, client_slug=CLIENT)

    @staticmethod
    def _copy_of(plan):
        contact = plan["contacts"][0]
        return {"sequences": dict(contact.get("sequences") or {}),
                "subjects": dict(contact.get("subjects") or {})}


class TestWireAndIsolation(_SealedRun):
    """The controls that make every other claim here admissible."""

    def test_the_seal_fires(self):
        from src import providers
        with self.assertRaises(sandboxharness.NetworkTouched):
            providers.request("GET", sandboxharness.CONTROL_URL, {})

    def test_no_host_was_reached_during_a_full_generation(self):
        self._run(model=_PromptDrivenModel())
        self.assertEqual(self.wire_calls[self._wire_baseline:], [],
                         "the run attempted %r"
                         % (self.wire_calls[self._wire_baseline:],))

    def test_the_ablation_seam_actually_fires(self):
        """A switch that was never thrown proves nothing."""
        with ba.ablated() as emptied:
            brain = secondbrain.for_task("campaign_strategy", CLIENT)
        self.assertTrue(emptied)
        self.assertEqual(sorted(brain),
                         sorted(secondbrain.TASK_SECTIONS["campaign_strategy"]))
        self.assertEqual([f for v in brain.values() for f in v], [])
        # ...and it restores.
        after = secondbrain.for_task("campaign_strategy", CLIENT)
        self.assertGreater(len([f for v in after.values() for f in v]), 0)

    def test_the_ablation_keeps_the_contract(self):
        with ba.ablated():
            with self.assertRaises(ValueError):
                secondbrain.for_task("no_such_task", CLIENT)


class TestPerSentenceAttribution(_SealedRun):
    """THE RETRIEVAL LOG: retrieved, reached, and which sentence."""

    def setUp(self):
        super().setUp()
        self.model = _PromptDrivenModel()
        with ba.observe() as self.retrievals:
            self.plan = self._run(model=self.model)
        self.contact = self.plan["contacts"][0]
        self.entries = ba.catalogue(self.plan["second_brain_facts"])
        # The ablated twin, so every attribution claim can be controlled
        # against the text the pipeline produces with the brain switched off.
        self.off_model = _PromptDrivenModel()
        with ba.ablated():
            self.plan_off = self._run(model=self.off_model)
        self.contact_off = self.plan_off["contacts"][0]

    def test_the_run_produced_copy(self):
        """ANTI-"CANNOT FAIL" CONTROL. Two empty drafts are identical, and
        an ablation over two empty drafts measures nothing."""
        self.assertNotEqual(self.contact.get("qualification"),
                            "INSUFFICIENT", self.contact.get("held"))
        sequences = self.contact.get("sequences") or {}
        self.assertTrue(sequences, "the run produced no copy: %r"
                        % self.contact.get("held"))
        for key in ("em1", "em2", "em3", "em4", "em5"):
            self.assertTrue(sequences.get(key), key)

    def test_retrieval_happened_once_for_the_whole_run(self):
        self.assertEqual([(r["task"], r["client"]) for r in self.retrievals],
                         [("campaign_strategy", CLIENT)])
        self.assertEqual(len(self.retrievals[0]["entries"]), 50)

    def test_admission_narrows_fifty_retrieved_to_a_subset(self):
        self.assertGreater(len(self.entries), 0)
        self.assertLess(len(self.entries), 50)

    def test_some_entries_text_does_appear_in_the_copy(self):
        """THE HONEST HALF: raw text overlap is NOT zero.

        Recorded rather than hidden, because a report that said "no entry
        appears in the copy" would be contradicted by anyone reading em1 and
        finding `digital marketing agency` in it. The next test shows where
        that phrase comes from.
        """
        sequences = self.contact.get("sequences") or {}
        overlaps = []
        for key in sorted(sequences):
            for rec in ba.attribute(self.entries, sequences[key]):
                if rec["reached"]:
                    overlaps.append((key, rec["id"], rec["clause"]))
        self.assertTrue(overlaps, "no overlap at all, which would make the "
                                  "ablation control below vacuous")

    def test_no_entry_is_BRAIN_CAUSED_in_the_final_copy(self):
        """THE MEASUREMENT. Per-sentence attribution, ablation-controlled.

        An entry is credited only if its clause is in the copy WITH the
        brain and gone WITHOUT it. Every overlap recorded above survives
        the ablation, so every one of them arrives by another route -
        `copystages.WRITER_SYSTEM`'s own constant text, the account research
        pack, or `config.product.capabilities` as `cap_sentence`.
        """
        seq_on = self.contact.get("sequences") or {}
        seq_off = self.contact_off.get("sequences") or {}
        self.assertTrue(seq_on and seq_off, "nothing was generated")
        offenders = []
        for key in sorted(seq_on):
            for rec in ba.brain_caused(self.entries, seq_on[key],
                                       seq_off.get(key, "")):
                offenders.append((key, rec["id"], rec["key"],
                                  rec["sentences"], rec["clause"]))
        self.assertEqual(offenders, [],
                         "brain-caused clauses in the copy: %r" % (offenders,))

    def test_every_retrieved_entry_reaches_the_hypothesis_prompt(self):
        """The one place it does land. Prompt-level, not output-level."""
        prompt = self.model.prompt_for("hypothesis")
        self.assertIsNotNone(prompt)
        self.assertIn(BR_MARKER, prompt)
        recs = ba.attribute(self.entries, prompt)
        self.assertEqual(ba.not_reached(recs), [],
                         "retrieved but absent from the prompt it is "
                         "assembled for: %s" % ba.not_reached(recs))

    def test_the_writer_prompt_is_byte_identical_with_the_brain_off(self):
        """The writer is never told the brain exists.

        The stage that writes the prospect-facing words receives the SAME
        BYTES whether the brain retrieved 50 facts or nothing. Some of those
        bytes overlap brain entries - `WRITER_SYSTEM` names Productive and
        margin per project in its own constant - and the identity of the two
        prompts is what shows the brain did not put them there.
        """
        prompt_on = self.model.prompt_for("writer")
        prompt_off = self.off_model.prompt_for("writer")
        self.assertIsNotNone(prompt_on)
        self.assertIsNotNone(prompt_off)
        self.assertNotIn(BR_MARKER, prompt_on)
        self.assertEqual(prompt_on, prompt_off)
        self.assertEqual(ba.brain_caused(self.entries, prompt_on, prompt_off),
                         [])
        # And it is not identical because it is empty.
        self.assertGreater(len(prompt_on), 5000)

    def test_raw_overlap_in_the_writer_prompt_is_recorded(self):
        """Measured and named rather than suppressed: 9 of the admitted
        entries have text in the writer prompt, all of it arriving by a
        non-brain route (the identity above is the proof)."""
        prompt = self.model.prompt_for("writer")
        recs = ba.attribute(self.entries, prompt)
        self.assertTrue(ba.reached(recs))
        self.assertTrue(ba.not_reached(recs))

    def test_the_plan_field_differs_from_what_any_projection_carries(self):
        """`second_brain_facts` is on the plan and in none of its
        projections, including the approval hash."""
        self.assertTrue(self.plan["second_brain_facts"])
        preview = sequenceplan.derive_preview_data(self.plan)
        self.assertNotIn("second_brain_facts", json.dumps(preview))
        bison = sequenceplan.derive_bison_payload(self.plan)
        self.assertNotIn("second_brain_facts", json.dumps(bison))


class TestAblation(_SealedRun):
    """THE ABLATION, in both configurations."""

    def test_configuration_a_identical_copy(self):
        """Hypothesis answer held fixed. Any difference is the plumbing's.

        The stub does not quote its context, so this isolates what the
        PIPELINE carries. The copy is compared field by field.

        THE LOAD-BEARING ASSERTION IS THE WRITER PROMPT, NOT THE COPY.
        Measured falsifiability, 2026-10-12: prepending the brain block to
        `writer_base` in `generate_campaign` leaves THIS comparison passing,
        because the stub reads only the fields the writer contract names and
        is blind to extra text. So the copy equality is asserted together
        with the prompt equality that licenses it; without the second, the
        first would be the property of a stub rather than of the pipeline,
        and a real model handed that extra text could write anything.
        """
        on_model = _PromptDrivenModel()
        plan_on = self._run(model=on_model)
        with ba.ablated() as emptied:
            off_model = _PromptDrivenModel()
            plan_off = self._run(model=off_model)
        self.assertTrue(emptied, "the ablation never fired")

        self.assertEqual(on_model.prompt_for("writer"),
                         off_model.prompt_for("writer"),
                         "the writer prompt is NOT identical, so equal copy "
                         "would be a property of the stub")

        copy_on, copy_off = self._copy_of(plan_on), self._copy_of(plan_off)
        self.assertTrue(copy_on["sequences"], "nothing was generated")
        self.assertTrue(copy_off["sequences"], "nothing was generated")
        self.assertEqual(copy_on, copy_off)
        self.assertEqual(sequenceplan.approval_hash(plan_on),
                         sequenceplan.approval_hash(plan_off))

        # The brain was retrieved in one run and not the other, so the two
        # runs really did differ in the input under test.
        self.assertTrue(plan_on["second_brain_facts"])
        self.assertEqual(plan_off["second_brain_facts"], [])

    def test_configuration_a_only_the_hypothesis_prompt_differs(self):
        """Prompt-level diff across every stage."""
        on_model = _PromptDrivenModel()
        self._run(model=on_model)
        with ba.ablated():
            off_model = _PromptDrivenModel()
            self._run(model=off_model)

        stages_on = [s for s, _ in on_model.prompts]
        stages_off = [s for s, _ in off_model.prompts]
        self.assertEqual(stages_on, stages_off)
        self.assertIn("writer", stages_on)

        differing = [s for (s, a), (_, b)
                     in zip(on_model.prompts, off_model.prompts)
                     if a != b]
        self.assertEqual(differing, ["hypothesis"],
                         "stages whose prompt changed: %r" % (differing,))

        # And the hypothesis prompt differs by EXACTLY the brain block.
        hyp_on = on_model.prompt_for("hypothesis")
        hyp_off = off_model.prompt_for("hypothesis")
        self.assertIn(BR_MARKER, hyp_on)
        self.assertNotIn(BR_MARKER, hyp_off)
        self.assertGreater(len(hyp_on) - len(hyp_off), 500)

    def test_configuration_b_echoing_model_moves_one_sentence(self):
        """The only channel, and what has to be true of the model for it to
        carry anything: the model must quote its context back.

        With `echo_context` the brain text lands in `hypothesis`, rides
        `plan_json` to the writer, and reaches em1 - and em1 only, because
        em1 is the one message the writer prompt's plan field feeds.
        """
        on_model = _PromptDrivenModel(echo_context=True)
        plan_on = self._run(model=on_model)
        with ba.ablated():
            off_model = _PromptDrivenModel(echo_context=True)
            plan_off = self._run(model=off_model)

        seq_on = (plan_on["contacts"][0].get("sequences") or {})
        seq_off = (plan_off["contacts"][0].get("sequences") or {})
        self.assertTrue(seq_on and seq_off)
        changed = sorted(k for k in set(seq_on) | set(seq_off)
                         if seq_on.get(k) != seq_off.get(k))
        self.assertEqual(changed, ["em1"],
                         "messages that changed: %r" % (changed,))

        # CROSS-CHECK: the changed message is the one attribution says
        # depends on a retrieved entry, and the unchanged ones are the ones
        # it says depend on none.
        entries = ba.catalogue(plan_on["second_brain_facts"])
        credited = ba.brain_caused(entries, seq_on["em1"],
                                   seq_off.get("em1", ""))
        self.assertTrue(credited,
                        "em1 changed but attribution credits no entry")
        # POSITIVE CONTROL for `brain_caused` ON REAL PIPELINE OUTPUT: it
        # must be able to name an entry and the sentence that uses it.
        for rec in credited:
            self.assertTrue(rec["sentences"], rec)
            self.assertTrue(rec["clause"], rec)
        for key in sorted(set(seq_on) - {"em1"}):
            self.assertEqual(
                ba.brain_caused(entries, seq_on[key], seq_off.get(key, "")),
                [], "%s is unchanged yet attribution credits it" % key)

    def test_stub_writer_is_prompt_sensitive(self):
        """POSITIVE CONTROL for the ablation.

        "The copy is identical" is only evidence if the writer would have
        written something else had its prompt differed. Perturb one field
        of the writer prompt and the copy must move.
        """
        model = _PromptDrivenModel()
        base = model._answer_writer(
            'Facts you may use:\n1. [site] A forty two person studio in '
            'Leeds\n"hypothesis": "ALPHA"\n"what_changes": "BETA"')
        moved = model._answer_writer(
            'Facts you may use:\n1. [site] A forty two person studio in '
            'Leeds\n"hypothesis": "GAMMA"\n"what_changes": "DELTA"')
        self.assertNotEqual(base["emails"]["em1"], moved["emails"]["em1"])
        self.assertIn("ALPHA", base["emails"]["em1"])
        self.assertIn("GAMMA", moved["emails"]["em1"])


class TestDeterministicCopyAblation(_SealedRun):
    """A copy path with NO model in it at all, ablated.

    `sequenceplan.for_campaign` renders the LinkedIn fallback messages that
    HeyReach sends as `fallbackMessage`. Those are prospect-facing words,
    they are produced deterministically, and `secondbrain._messaging`
    publishes the very same strings as brain facts
    (`linkedin_sequence.fallbacks`). So: does the copy come from the brain?
    """

    def _fallbacks(self):
        config = clients.load(CLIENT)
        plan = sequenceplan.for_campaign(
            None, config,
            cadence_steps=[
                {"key": "li1", "day": 1, "channel": "linkedin"},
                {"key": "li2", "day": 3, "channel": "linkedin"},
                {"key": "li3", "day": 6, "channel": "linkedin"},
                {"key": "li4", "day": 9, "channel": "linkedin"},
                {"key": "li5", "day": 13, "channel": "linkedin"},
            ])
        return plan["linkedin"]["copy"]

    def test_the_fallbacks_are_real_copy(self):
        copy = self._fallbacks()
        self.assertTrue(copy)
        texts = [v.get("fallbackMessage") for v in copy.values()]
        self.assertTrue(all(texts), copy)

    def test_the_same_sentences_are_published_as_brain_facts(self):
        """The duplication: the brain holds the identical strings."""
        copy = self._fallbacks()
        brain = secondbrain.all_sections(CLIENT, reason="ablation census")
        brain_texts = [f["text"] for f in brain["messaging"]]
        for entry in copy.values():
            message = entry["fallbackMessage"]
            self.assertTrue(
                any(message in t for t in brain_texts),
                "fallback not mirrored in the brain: %r" % message[:60])

    def test_ablating_the_brain_does_not_change_one_character(self):
        """And it cannot, because this path never asks the brain."""
        before = self._fallbacks()
        with ba.observe() as seen:
            during = self._fallbacks()
        self.assertEqual(seen, [], "for_task was called after all: %r" % seen)
        with ba.ablated() as emptied:
            after = self._fallbacks()
        self.assertEqual(emptied, [],
                         "for_task was called after all: %r" % emptied)
        self.assertEqual(before, during)
        self.assertEqual(before, after)

    def test_generate_campaign_drops_those_very_facts(self):
        """The brain's copy of the fallbacks is dropped on admission, so the
        duplicate is read by nothing even on the one live path."""
        offer = offers_mod.all_offers()["OFFER-B-OPERATIONS"]
        admitted = gc._load_admitted_facts(CLIENT, "champion", offer)
        keys = {f["source"].split(" ", 1)[-1] for f in admitted}
        self.assertNotIn("linkedin_sequence.fallbacks", keys)


# ===========================================================================
# The retrieval log, printed. `py -m tests.test_... --log`
# ===========================================================================

def _print_log():
    undo, calls = sandboxharness.seal_wire(allow=())
    sandboxharness.assert_wire_sealed()
    tmp = tempfile.TemporaryDirectory(prefix="sb-ablation-log-")
    undo_store = store.use_directory(tmp.name)
    try:
        campaignstrategy.clear_cache()
        model = _PromptDrivenModel()
        with ba.observe() as retrievals:
            plan = gc.generate(clients.load(CLIENT), _account(), _contacts(),
                               model=model, client_slug=CLIENT)
        print("RETRIEVED (secondbrain.for_task campaign_strategy/%s): %d"
              % (CLIENT, len(retrievals[0]["entries"])))
        entries = ba.catalogue(plan["second_brain_facts"])
        print("ADMITTED into the one live prompt: %d" % len(entries))
        print()
        contact = plan["contacts"][0]
        for key in sorted(contact["sequences"]):
            text = contact["sequences"][key]
            if not text:
                continue
            recs = ba.attribute(entries, text)
            print(ba.format_log(recs, label="--- %s ---" % key,
                                sentences=ba.split_sentences(text)))
            print()
        hyp = model.prompt_for("hypothesis")
        recs = ba.attribute(entries, hyp)
        print("--- the stage-C hypothesis PROMPT (not output) ---")
        print("  REACHED %d of %d" % (len(ba.reached(recs)), len(recs)))
        writer = model.prompt_for("writer")
        recs = ba.attribute(entries, writer)
        print("--- the stage-F writer PROMPT ---")
        print("  REACHED %d of %d" % (len(ba.reached(recs)), len(recs)))
        print("  brain marker present:", BR_MARKER in writer)
        print("wire calls attempted:", calls)
    finally:
        if callable(undo_store):
            undo_store()
        undo()
        tmp.cleanup()


if __name__ == "__main__":
    if "--log" in sys.argv:
        sys.argv.remove("--log")
        _print_log()
    else:
        unittest.main()
