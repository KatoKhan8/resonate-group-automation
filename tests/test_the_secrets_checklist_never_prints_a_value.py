"""2d — the secrets checklist comes from the registry, and leaks no value.

TWO THINGS ARE BEING HELD HERE, and the second is the one that would hurt.

1. THE CHECKLIST IS DERIVED. CLAUDE.md opens a section with "CREDENTIAL NAMES
   COME FROM `config.VARIABLES`. NEVER GUESS ONE", because a session once
   invented four plausible names, reported four providers as unauthenticated,
   and concluded decision-maker discovery was impossible. All four were set.
   A hand-written checklist is that failure with a longer half-life: a list
   somebody must remember to edit, whose cost of forgetting is a cutover that
   completes with a credential missing and an estate that looks configured.

2. NO VALUE IS EVER PRINTED. This tool reads the file that holds every
   provider credential. The test below plants distinctive values and asserts
   that not one of them appears in stdout or stderr, on the success path AND
   on the error paths — because the 2026-09-23 redaction defect got exactly
   this wrong: the filter was correct and the check was in the wrong place,
   so one value went through on the first probe that used it. The self-test
   has to assert against EVERY value, and it has to cover the paths nobody
   expects to take.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "server", "secrets_checklist.py")

from src import config  # noqa: E402

#: Distinctive, and shaped like the real things they stand for. None is a
#: real credential.
PLANTED = {
    "BISON_KEY": "bkey-ZZTOPSECRET111",
    "CONTACTOUT_TOKEN": "co-ZZTOPSECRET222",
    "AUTH_CLIENT_SECRET": "acs-ZZTOPSECRET333",
    "SLACK_BOT_TOKEN": "xoxb-ZZTOPSECRET444",
    "A_TYPO_NOBODY_DECLARED": "typo-ZZTOPSECRET555",
}


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args),
                          cwd=ROOT, capture_output=True, text=True)


class TheChecklistComesFromTheRegistry(unittest.TestCase):

    def test_every_declared_variable_is_on_the_checklist(self):
        out = _run().stdout
        for entry in config.VARIABLES:
            self.assertIn("`%s`" % entry[0], out,
                          "%s is declared but not on the checklist" % entry[0])

    def test_it_does_not_invent_a_name_that_does_not_exist(self):
        """`CONTACTOUT_KEY` is the specific invention CLAUDE.md records.

        Asserted against the CHECKLIST ITEMS, not the whole document: the
        prose names it deliberately, as the counter-example. What must never
        happen is it appearing as a box somebody ticks."""
        items = [l for l in _run().stdout.splitlines()
                 if l.strip().startswith("- [ ]")]
        self.assertTrue(items, "no checklist items were produced at all")
        self.assertFalse([l for l in items if "CONTACTOUT_KEY" in l],
                         "a name that does not exist became a checklist item")
        self.assertTrue([l for l in items if "`CONTACTOUT_TOKEN`" in l])

    def test_the_generated_doc_says_it_is_generated(self):
        """A generated file that does not say so is one somebody hand-edits,
        and the edit vanishes at the next regeneration."""
        self.assertIn("GENERATED", _run().stdout)

    def test_live_variables_are_not_required_for_a_shadow_deploy(self):
        """The shadow deploy installs the app and starts nothing. Marking a
        provider key as needed before install would block it for no reason."""
        self.assertIn("not needed for a shadow deploy", _run().stdout)


class NoValueIsEverPrinted(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-secrets-")
        self.path = os.path.join(self.tmp, "secrets.env")
        with io.open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# a comment with no value in it\n")
            for name, value in PLANTED.items():
                fh.write("%s=%s\n" % (name, value))
            fh.write("export QUEUE=/srv/state/queue.jsonl\n")

    def _assert_no_value_in(self, proc, where):
        blob = proc.stdout + proc.stderr
        for name, value in PLANTED.items():
            self.assertNotIn(value, blob,
                             "%s's VALUE leaked in %s" % (name, where))
        self.assertNotIn("/srv/state/queue.jsonl", blob,
                         "a non-credential value leaked in %s" % where)

    def test_verify_names_reports_state_without_the_value(self):
        proc = _run("--verify-names", "--file", self.path)
        self._assert_no_value_in(proc, "--verify-names")
        # and it is actually doing the job, not silently printing nothing
        self.assertIn("BISON_KEY", proc.stdout)
        self.assertIn("SET", proc.stdout)
        self.assertIn("ABSENT", proc.stdout)

    def test_an_undeclared_name_is_shown_but_its_value_is_not(self):
        """A typo'd variable name looks exactly like this, so it is worth
        surfacing - but surfacing the name must not surface the secret."""
        proc = _run("--verify-names", "--file", self.path)
        self.assertIn("A_TYPO_NOBODY_DECLARED", proc.stdout)
        self._assert_no_value_in(proc, "the undeclared-name report")

    def test_a_missing_file_leaks_nothing_and_exits_2(self):
        """An error path. The redaction defect of 2026-09-23 was a check in
        the wrong place, not a wrong filter - so the paths nobody expects to
        take are the ones worth asserting."""
        proc = _run("--verify-names", "--file",
                    os.path.join(self.tmp, "nope.env"))
        self.assertEqual(2, proc.returncode)
        self._assert_no_value_in(proc, "the missing-file path")

    def test_a_directory_where_a_file_should_be_leaks_nothing(self):
        proc = _run("--verify-names", "--file", self.tmp)
        self.assertNotEqual(0, proc.returncode)
        self._assert_no_value_in(proc, "the unreadable-path error")

    def test_the_plain_checklist_never_reads_the_secrets_file_at_all(self):
        proc = _run("--file", self.path)
        self._assert_no_value_in(proc, "the checklist")

    def test_a_set_variable_is_not_called_an_authenticated_one(self):
        """The distinction that cost a wrong answer once: a set variable is
        not a working one, and a transport failure is not a bad key."""
        proc = _run("--verify-names", "--file", self.path)
        self.assertIn("not an authenticated one", proc.stdout)
        self.assertIn("credential_health.py", proc.stdout)


class TheCommittedDocMatchesItsGenerator(unittest.TestCase):
    """`provision.sh` step 8 points a person at docs/SECRETS-MOVE.md, so the
    committed file is what somebody reads at 23:00 during a cutover. A
    generated document that has drifted from its generator is worse than no
    document, because it is believed - the same sentence CLAUDE.md uses about
    a drifted ledger."""

    def test_the_committed_checklist_is_what_the_generator_produces(self):
        path = os.path.join(ROOT, "docs", "SECRETS-MOVE.md")
        self.assertTrue(os.path.exists(path),
                        "provision.sh points at a doc that does not exist")
        with io.open(path, encoding="utf-8") as fh:
            committed = fh.read()
        self.assertEqual(
            _run().stdout.replace("\r\n", "\n"), committed,
            "docs/SECRETS-MOVE.md has drifted from its generator. "
            "Regenerate it: py -3 scripts/server/secrets_checklist.py "
            "--out docs/SECRETS-MOVE.md")


if __name__ == "__main__":
    unittest.main()
