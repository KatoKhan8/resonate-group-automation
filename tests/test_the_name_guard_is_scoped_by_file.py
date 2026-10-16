#!/usr/bin/env python3
"""TASK 0170: the name guard's scope is the FILE, not the token list.

A token-scoped pass goes green the moment a real person is missing from
FORBIDDEN_NAMES. Three mailbox owners in the client's sending census sat
in two tracked files for a fortnight that way - inside files the guard
was ALREADY red on, red on five other surnames, green on theirs. These
tests pin the widening: revert the operative check to token scope and
they fail, on the same code path the suite runs.

No person is named in this file, on purpose. The census owners are
referred to by path and by what their lines look like: a count beside a
First+Last pair. If the guard's failure output ever prints a name that
came from here, that is a defect in this file.
"""
import re
import unittest

import tests.test_fixture_hygiene as hygiene

CENSUS_DOC = "docs/R2-SIGNATURE-MEASUREMENT-2026-10-01.md"
HANDOFF_DOC = "docs/HANDOFF-2026-09-30-PRODUCTION.md"

# A census line: leading blanks, a count, then a First+Last pair. This is
# the shape the census owners arrive in; matching the shape is how this
# file names their lines without naming them.
CENSUS_LINE = re.compile(r"^\s+\d+\s+[A-ZŠŽĆČĐ][a-zšžćčđ]+ [A-ZŠŽĆČĐ][a-zšžćčđ]+")
# A run of pairs separated by slashes, the other census shape (a handoff
# summary line).
SLASH_RUN = re.compile(r"[A-ZŠŽĆČĐ][a-zšžćčđ]+ [A-ZŠŽĆČĐ][a-zšžćčđ]+"
                       r" / [A-ZŠŽĆČĐ][a-zšžćčđ]+ [A-ZŠŽĆČĐ][a-zšžćčđ]+")


def _census_block(path):
    """The census lines of `path`: a count beside a First+Last pair, or a
    run of pairs separated by slashes. No name is returned, only lines."""
    out = []
    for line in hygiene.read(path).splitlines():
        if CENSUS_LINE.match(line) or SLASH_RUN.search(line):
            out.append(line)
    return out


def _unlisted_pairs(block_text):
    """Person-shaped pairs in the block that neither half of is a token."""
    unlisted = set()
    for pair in hygiene.person_shaped_pairs(block_text):
        first, last = pair.split(" ", 1)
        if (first.lower() not in hygiene.FORBIDDEN_NAMES
                and last.lower() not in hygiene.FORBIDDEN_NAMES):
            unlisted.add(pair)
    return unlisted


class TheNameGuardIsScopedByFile(unittest.TestCase):

    def test_census_owners_are_flagged_by_file_not_only_by_token(self):
        """The three unlisted census owners, by path and line shape.

        Each census file holds person-shaped pairs FORBIDDEN_NAMES does
        not cover. The biconditional is the pin: while those lines
        exist, the name rule must carry a person-shaped hit for that
        file; once they are redacted away, it must carry none. A guard
        that still reads only the token list fails the first half
        today, because it reports the files' surnames and stays silent
        about the pairs sitting beside them on the same lines.
        """
        for path in (CENSUS_DOC, HANDOFF_DOC):
            with self.subTest(path=path):
                region = "\n".join(_census_block(path))
                unlisted = _unlisted_pairs(region)
                carried = [h for h in hygiene.name_rule_hits()
                           if h.startswith(path + ":")
                           and "(person-shaped" in h]
                if unlisted:
                    self.assertTrue(
                        carried,
                        "the census region of this file holds person-shaped"
                        " pairs the token list does not cover, and the name"
                        " rule reports none of them: the rule has lost its"
                        " file scope")
                else:
                    self.assertFalse(
                        carried,
                        "the census region holds no unlisted pairs, yet the"
                        " name rule still reports person-shaped hits for the"
                        " file: reported lines moved somewhere the census"
                        " selector does not look")

    def test_one_known_name_escalates_the_whole_file_to_pairs(self):
        """Mutation control: token scope alone cannot pass this.

        The anchor is read from the list at runtime, and the pair is
        invented - two synthetic alpha words, not anybody's name, the
        same convention the corpus uses for fake contacts. Neither is
        written out anywhere in this file.
        """
        invented = "Qvex Zorma"
        anchor = sorted(hygiene.FORBIDDEN_NAMES)[0]
        text = ("contact {a} and {p} reviewed it\n"
                .format(a=anchor, p=invented))
        hits = hygiene.name_rule_hits(
            files=[("synthetic/escalation.md", text)])
        shaped = [h for h in hits if "(person-shaped" in h]
        self.assertTrue(
            shaped,
            "a file carrying one known name and an invented person-shaped"
            " pair produced no person-shaped hit: the rule read only the"
            " token list")
        self.assertEqual(len(shaped), 1)


if __name__ == "__main__":
    unittest.main()
