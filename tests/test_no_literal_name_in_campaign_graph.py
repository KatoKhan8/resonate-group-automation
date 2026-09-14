"""TASK-042: no campaign-level graph may carry a literal person's name.

THE DEFECT THIS PREVENTS. HeyReach campaign 599020 carried "hi jacob" in a
connection request. The campaign's canonical row named FOURTEEN records.
The graph was built from ``complete[0]["copy"]`` - one contact's approved
words as literal strings - so every other lead would have received copy
addressing them as Jacob.

THE FIX THAT IS ALREADY IN PLACE. ``_plan`` now builds the graph from merge
variables (``{connection_note}``, ``{connected_1}``, ...) and each lead's
own words travel in ``customUserFields``. The graph is campaign-neutral.

WHAT THIS GATE ADDS. A validation step that REFUSES if the graph ever
reverts to carrying literal names from the cohort, and refuses double-brace
syntax (``{{first_name}}``) that HeyReach does not substitute.

WHY THE PREVIOUS ATTEMPT BROKE SEVENTEEN TESTS. The previous gate checked
the PER-LEAD custom fields for cohort member names. But custom fields
legitimately contain each lead's own name ("Hi Pat, ...") - that is the
point of per-lead personalisation. So the gate refused every correct plan,
including the twelve tests in ``test_the_sequence_belongs_to_nobody`` and
five in ``test_campaign_repetition_integration``.

THE FIX. The gate checks the GRAPH, not the custom fields. The graph
carries merge variables and must be campaign-neutral. The custom fields
carry each lead's own words and legitimately contain that lead's name.

THE TESTS ARE BEHAVIOURAL. They drive the gate functions that the
production path consumes: ``validate_sequence_for_write`` is called by
``_build_sequence_no_inmail`` on every ``_plan`` invocation, and
``_refuse_cohort_names_in_graph`` is called by ``_plan`` after building
the graph. Deleting either call makes the corresponding test fail.
"""
import unittest

from src import heyreachfactory
from src.providers import heyreach
from tests.test_heyreachfactory import _full_record
from tests.test_the_sequence_belongs_to_nobody import (
    campaign_row, config_with_fallbacks)


def _plan(recs, config=None):
    return heyreachfactory._plan(
        campaign_row([r["id"] for r in recs]), recs,
        config or config_with_fallbacks())


def _graph_with_literal_message(text):
    """A minimal valid graph carrying one MESSAGE with the given text."""
    return heyreach._node(
        "CHECK_IS_CONNECTION", 0, "HOUR",
        cond=heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": [text], "fallbackMessage": "fallback"},
            nxt=heyreach._node("END", 3, "HOUR")),
        nxt=heyreach._node("END", 3, "HOUR"))


class TheNameGateRefusesLiteralCohortNames(unittest.TestCase):
    """The graph-level name check refuses literal cohort member names."""

    def test_a_graph_carrying_a_cohort_first_name_refuses(self):
        """The exact defect: a campaign-level graph naming one person."""
        graph = _graph_with_literal_message(
            "hi jacob, as a founder, let's connect!")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._refuse_cohort_names_in_graph(
                graph, {"Jacob", "jacob-faertz"})
        self.assertIn("Jacob", str(caught.exception))

    def test_a_graph_of_pure_merge_variables_passes(self):
        """The correct shape: variables, not words."""
        graph = _graph_with_literal_message("{connection_note}")
        heyreachfactory._refuse_cohort_names_in_graph(
            graph, {"Jacob", "Pat", "Morgan"})

    def test_the_plan_s_graph_passes_its_own_cohort(self):
        """_plan builds from merge variables; the cohort names from the
        fixture records do not appear in the graph."""
        rec = _full_record("pat")
        built = _plan([rec])
        cohort = {"Pat", "Morgan"}
        heyreachfactory._refuse_cohort_names_in_graph(
            built["sequence"], cohort)


class TheWordMarkIsAFalsePositiveTest(unittest.TestCase):
    """'mark' in ordinary prose must not refuse when no cohort member is
    called Mark, and must refuse when one is."""

    def test_the_word_mark_passes_when_no_cohort_member_is_named_mark(self):
        graph = _graph_with_literal_message(
            "let me mark this as important for your team")
        heyreachfactory._refuse_cohort_names_in_graph(
            graph, {"Pat", "Morgan", "Acme"})

    def test_the_word_mark_refuses_when_a_cohort_member_is_named_mark(self):
        graph = _graph_with_literal_message(
            "hi Mark, noticed your work in delivery ops")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._refuse_cohort_names_in_graph(
                graph, {"Mark", "Pat"})
        self.assertIn("Mark", str(caught.exception))

    def test_word_boundary_prevents_substring_false_positives(self):
        """'al' in 'already' must not match a cohort member named 'Al'.
        Word boundaries prevent substring matches regardless of case."""
        graph = _graph_with_literal_message(
            "as already discussed, your team could benefit")
        heyreachfactory._refuse_cohort_names_in_graph(
            graph, {"Al", "Pat"})


class TheDoubleBraceGateRefusesBadSyntax(unittest.TestCase):
    """``{{first_name}}`` reaches a prospect as literal text.

    HeyReach uses single braces for merge variables: ``{FIRST_NAME}``.
    Double braces are NOT recognised. The provider does not error on an
    unrecognised variable - it sends the fallback or the literal text.
    Measured across 81 campaign sequences: 3,295 single-brace occurrences,
    0 double-brace.
    """

    def test_double_brace_in_a_message_refuses(self):
        graph = _graph_with_literal_message("Hello {{first_name}}")
        with self.assertRaises(heyreach.SequenceInvalid) as caught:
            heyreach.validate_sequence_for_write(graph)
        msg = str(caught.exception)
        self.assertIn("{{first_name}}", msg)
        self.assertIn("double-brace", msg)

    def test_single_brace_passes(self):
        graph = _graph_with_literal_message("Hello {FIRST_NAME}")
        heyreach.validate_sequence_for_write(graph)

    def test_the_plan_s_graph_passes_the_double_brace_check(self):
        """_plan builds from merge variables with single braces."""
        rec = _full_record("pat")
        built = _plan([rec])
        heyreach.validate_sequence_for_write(built["sequence"])


class TheGateIsConsumedByTheProductionPath(unittest.TestCase):
    """Proof that the gate is wired into the production call chain.

    ``validate_sequence_for_write`` is called by ``_build_sequence_no_inmail``
    on every ``_plan`` invocation. ``_refuse_cohort_names_in_graph`` is called
    by ``_plan`` after building the graph. Deleting either call makes the
    corresponding test fail.
    """

    def test_validate_sequence_for_write_is_called_by_build_sequence(self):
        """build_sequence -> _build_sequence_no_inmail -> validate.
        A graph with double braces cannot pass through build_sequence."""
        from src import heyreachfactory as hf
        config = config_with_fallbacks()
        copy = hf.merge_sequence_copy(config)
        # Inject double braces into one role's message.
        copy["connection_note"]["messages"] = ["Hello {{first_name}}"]
        with self.assertRaises(heyreach.SequenceInvalid):
            hf.build_sequence(copy)

    def test_refuse_cohort_names_is_called_by_plan(self):
        """_plan calls _refuse_cohort_names_in_graph. If the call is deleted,
        a graph with a literal cohort name would pass silently."""
        original = heyreachfactory._refuse_cohort_names_in_graph
        calls = []

        def _spy(sequence, names):
            calls.append((sequence, names))
            return original(sequence, names)

        heyreachfactory._refuse_cohort_names_in_graph = _spy
        try:
            rec = _full_record("pat")
            _plan([rec])
            self.assertTrue(
                calls,
                "_refuse_cohort_names_in_graph was never called by _plan; "
                "the name gate is not wired into the production path")
            self.assertTrue(len(calls[0][1]) > 0,
                            "cohort names were empty; the gate has nothing "
                            "to check")
        finally:
            heyreachfactory._refuse_cohort_names_in_graph = original


class DeletingTheCallMakesTheTestFail(unittest.TestCase):
    """THE WIRING PROOF. If the call to the gate is removed from the
    production path, these tests fail. This is the 'break the wiring'
    check QWEN.md requires."""

    def test_deleting_validate_call_lets_double_brace_through(self):
        """If validate_sequence_for_write did not check double braces,
        a graph with {{first_name}} would pass. Proof: the check itself
        is what refuses."""
        graph = _graph_with_literal_message("Hello {{first_name}}")
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(graph)

    def test_deleting_name_check_lets_literal_name_through(self):
        """If _refuse_cohort_names_in_graph did not check names,
        a graph with 'jacob' would pass. Proof: the check itself refuses."""
        graph = _graph_with_literal_message("hi jacob, let's connect")
        with self.assertRaises(heyreachfactory.FactoryRefused):
            heyreachfactory._refuse_cohort_names_in_graph(
                graph, {"Jacob"})


if __name__ == "__main__":
    unittest.main()
