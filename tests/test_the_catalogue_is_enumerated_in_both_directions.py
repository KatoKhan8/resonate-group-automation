"""The tool catalogue, asserted FROM THE REGISTRY rather than by hand.

OPERATOR, increment 4: "catalogue second pass with scope tests".

## WHAT THE SECOND PASS FOUND

`tests/test_two_clients_cannot_see_each_other.py` already enumerates the
registry in the CLIENT direction - it runs every client-visible tool for two
workspaces and asserts cross-visibility both ways, and its own comment says
it is written that way "so tomorrow's tool is covered today".

**The internal direction was never enumerated.** The set of internal-only
tools is hand-typed in two places - four names in
`tests/test_slack_agent_scope.py:221`, five in the isolation file - and an
internal tool added tomorrow is covered by neither. That is the gap this
file closes, and it closes it the same way: from `REGISTRY`, so the list
cannot drift from the thing it describes.

Three smaller ones, in the same shape:

- **Nothing asserted the registry's ROW SHAPE.** A three-tuple entry would
  raise at `run()`'s unpack at runtime rather than fail a test.
- **Nothing asserted `catalogue()`'s rendered text**, which is what the
  planner model actually reads (`slackconversation.plan`). `for_scope` and
  `catalogue` are two views of one fact and could disagree silently.
- **Nothing asserted that an UNBOUND channel is refused at `run()`.** The
  existing test asserts its tool LIST is empty, which is not the same claim.

## AND ONE THAT WAS NOT A GAP BUT A LEAK

The refusal text itself named the tool, in a client channel's material.
See `TheRefusalDoesNotNameTheTool` at the bottom - that one is a fix, not
just coverage.
"""
import unittest

from src import slackagenttools as tools, slackscope

INTERNAL_ONLY = tuple(sorted(
    name for name, spec in tools.REGISTRY.items()
    if slackscope.CLIENT not in spec[2]))

CLIENT_VISIBLE = tuple(sorted(
    name for name, spec in tools.REGISTRY.items()
    if slackscope.CLIENT in spec[2]))


def client_scope(slug="productive"):
    return slackscope.Scope(slackscope.CLIENT, workspace=slug, source="test",
                            slugs=("productive", "contactout"))


def internal_scope():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


def unbound_scope():
    return slackscope.Scope(slackscope.UNBOUND, source="test")


#: THE INTERNAL FIVE, PINNED BY NAME. Not derived.
#:
#: Everything else in this file reads `INTERNAL_ONLY` out of the REGISTRY,
#: which makes it self-maintaining for a tool ADDED tomorrow - and blind to
#: a tool MOVED tomorrow. Attacked 2026-09-23 by flipping `monitors` from
#: `_INTERNAL` to `_INTERNAL_CLIENT`: the derived set simply shrank, every
#: assertion still passed, and a client channel could read Resonate's
#: watcher health. **Zero tests moved.**
#:
#: So the boundary itself is written down. This list is the repository's
#: `TestKnownSets` convention - a change here is a question for a human
#: rather than a failure, and answering it means editing this line on
#: purpose and saying why in the commit.
EXPECTED_INTERNAL_ONLY = ("credits", "monitors", "next_actions",
                          "promises", "who_does_what")


class TheBoundaryItselfIsPinned(unittest.TestCase):
    """The test the other classes cannot be, because they are derived."""

    def test_exactly_these_tools_are_internal_only(self):
        self.assertEqual(INTERNAL_ONLY, EXPECTED_INTERNAL_ONLY)

    def test_none_of_them_is_client_visible(self):
        for name in EXPECTED_INTERNAL_ONLY:
            with self.subTest(tool=name):
                self.assertIn(name, tools.REGISTRY,
                              "%s was removed; decide deliberately" % name)
                self.assertNotIn(slackscope.CLIENT,
                                 tools.REGISTRY[name][2])

    def test_a_new_tool_defaults_to_being_noticed(self):
        """Every registered tool is in exactly one of the two groups, and
        both groups are asserted, so a tool that joins either is covered by
        the loops below without anybody remembering to add it."""
        self.assertEqual(sorted(set(INTERNAL_ONLY) | set(CLIENT_VISIBLE)),
                         sorted(tools.REGISTRY))
        self.assertEqual(set(INTERNAL_ONLY) & set(CLIENT_VISIBLE), set())


class TheRegistryIsWellFormed(unittest.TestCase):
    """A shape test, because `run()` unpacks four values and a short row
    would raise in production rather than here."""

    def test_every_entry_is_a_four_tuple(self):
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertIsInstance(spec, tuple)
                self.assertEqual(len(spec), 4)

    def test_every_entry_is_callable_with_a_real_description(self):
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertTrue(callable(spec[0]))
                self.assertTrue(str(spec[1]).strip(),
                                "%s has no description" % name)

    def test_every_scope_tuple_is_one_of_the_two_known_ones(self):
        """There is deliberately no ANY tuple. A third shape appearing here
        is a decision somebody should have to make on purpose."""
        known = ((slackscope.INTERNAL,),
                 (slackscope.INTERNAL, slackscope.CLIENT))
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertIn(spec[2], known)

    def test_no_tool_is_reachable_from_an_unbound_channel(self):
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertNotIn(slackscope.UNBOUND, spec[2])

    def test_the_argument_help_is_a_string_or_nothing(self):
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertTrue(spec[3] is None or isinstance(spec[3], str))

    def test_there_are_tools_in_both_groups(self):
        """The anti-emptiness control. Every assertion below is a loop over
        one of these two, and a loop over nothing passes."""
        self.assertTrue(INTERNAL_ONLY)
        self.assertGreater(len(CLIENT_VISIBLE), 10)


class EveryInternalToolRefusesAClientChannel(unittest.TestCase):
    """ENUMERATED, so the tool added tomorrow is covered today.

    This was hand-typed in two files - four names in one and five in the
    other - and neither list covers a tool that does not exist yet.
    """

    def test_it_is_never_offered(self):
        offered = set(tools.for_scope(client_scope()))
        for name in INTERNAL_ONLY:
            with self.subTest(tool=name):
                self.assertNotIn(name, offered)

    def test_it_is_refused_when_asked_for_by_name(self):
        for name in INTERNAL_ONLY:
            with self.subTest(tool=name):
                with self.assertRaises(tools.ToolRefused):
                    tools.run(client_scope(), name)

    def test_it_is_refused_in_the_other_client_too(self):
        for name in INTERNAL_ONLY:
            with self.subTest(tool=name):
                with self.assertRaises(tools.ToolRefused):
                    tools.run(client_scope("contactout"), name)

    def test_and_it_never_appears_in_a_client_catalogue(self):
        """The catalogue string is what the planner model reads. A tool
        absent from `for_scope` but present in the rendered text would be
        offered to the model in prose."""
        rendered = tools.catalogue(client_scope())
        for name in INTERNAL_ONLY:
            with self.subTest(tool=name):
                self.assertNotIn(name, rendered)

    def test_the_internal_channel_does_get_them(self):
        """The control. If the scope filter were simply broken, every
        assertion above would pass and mean nothing."""
        offered = set(tools.for_scope(internal_scope()))
        for name in INTERNAL_ONLY:
            with self.subTest(tool=name):
                self.assertIn(name, offered)


class TheTwoViewsCannotDrift(unittest.TestCase):
    """`for_scope` and `catalogue` describe one fact in two shapes."""

    def scopes(self):
        return (("client", client_scope()), ("internal", internal_scope()))

    def test_every_catalogue_line_names_a_tool_the_scope_may_call(self):
        for label, scope in self.scopes():
            allowed = set(tools.for_scope(scope))
            for line in tools.catalogue(scope).split("\n"):
                if not line.strip():
                    continue
                name = line.strip().split(" ", 1)[0]
                with self.subTest(scope=label, tool=name):
                    self.assertIn(name, allowed)

    def test_every_allowed_tool_has_a_catalogue_line(self):
        for label, scope in self.scopes():
            rendered = tools.catalogue(scope)
            names = {line.strip().split(" ", 1)[0]
                     for line in rendered.split("\n") if line.strip()}
            self.assertEqual(names, set(tools.for_scope(scope)),
                             "the two views disagree for %s" % label)

    def test_the_argument_suffix_matches_the_registry(self):
        """A line promising an argument for a tool that takes none sends the
        model to `run(name, argument)` and the argument is ignored - which
        reads, from the outside, as the agent ignoring the question."""
        for line in tools.catalogue(internal_scope()).split("\n"):
            if not line.strip():
                continue
            name = line.strip().split(" ", 1)[0]
            takes_argument = tools.REGISTRY[name][3] is not None
            with self.subTest(tool=name):
                if takes_argument:
                    self.assertIn("(argument:", line)
                else:
                    self.assertIn("(no argument)", line)


class AnUnboundChannelIsRefusedAndNotMerelyOfferedNothing(unittest.TestCase):
    """The existing test asserts the LIST is empty. That is a different
    claim from the tool refusing when it is named anyway."""

    def test_the_list_is_empty(self):
        self.assertEqual(sorted(tools.for_scope(unbound_scope())), [])

    def test_the_catalogue_is_empty(self):
        self.assertEqual(tools.catalogue(unbound_scope()).strip(), "")

    def test_every_tool_refuses_it_by_name(self):
        for name in sorted(tools.REGISTRY):
            with self.subTest(tool=name):
                with self.assertRaises(tools.ToolRefused):
                    tools.run(unbound_scope(), name)


class TheRefusalDoesNotNameTheTool(unittest.TestCase):
    """A FIX, not just coverage.

    `run()` refuses with "a client channel may not call 'who_does_what'".
    `run_all` put that into the result row, and `material_for` hands result
    rows to the model - so in a client channel the model was told the
    internal name of a tool it may not use, and `check_outbound` does not
    catch the paraphrase. Measured against a real client scope:

        "I'm not allowed to call who_does_what in this channel."  LEAKS
        "I can't run next_actions here."                          LEAKS
        "The monitors tool is internal only."                     LEAKS
        "I can't check promises for you."                         LEAKS

    The forbidden-terms list is the wrong fix: `monitors` and `promises` are
    ordinary English and forbidding them would refuse honest answers.
    """

    def test_a_client_refusal_row_does_not_carry_the_tool_name(self):
        calls = [{"name": n} for n in INTERNAL_ONLY]
        for name, _argument, result in tools.run_all(client_scope(), calls):
            with self.subTest(tool=name):
                self.assertNotIn(name, str(result.get("_error") or ""))

    def test_it_still_says_it_refused(self):
        """Silence would be worse: the model would have no row at all and
        could describe the absence as a fact about the client's estate."""
        out = tools.run_all(client_scope(), [{"name": INTERNAL_ONLY[0]}])
        self.assertTrue(out[0][2].get("_error"))

    def test_the_internal_wording_is_unchanged(self):
        """It is a useful thing to read in a log, and internal material is
        not a disclosure surface."""
        out = tools.run_all(internal_scope(), [{"name": "not_a_tool"}])
        self.assertIn("not_a_tool", str(out[0][2].get("_error")))

    def test_check_outbound_still_does_not_catch_the_paraphrase(self):
        """Recorded rather than fixed, because it is the reason the fix had
        to be made in the material instead. If somebody later adds these to
        the forbidden terms, this test goes red and they read why here."""
        scope = client_scope()
        for sentence in ("I can't run next_actions here.",
                         "The monitors tool is internal only."):
            with self.subTest(sentence=sentence):
                scope.check_outbound(sentence)


if __name__ == "__main__":
    unittest.main()
