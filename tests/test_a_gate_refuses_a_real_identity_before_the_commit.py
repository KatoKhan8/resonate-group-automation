"""The PII gate FIRES. Proved by attempting a real commit and watching it fail.

TASK-938. Every assertion here is about an EFFECT: a `git commit` that returns
non-zero and leaves `HEAD` where it was, or one that returns zero and moves it.
Nothing in this file asserts that the gate's source contains a word.

## WHY A THROWAWAY REPOSITORY

The positive control needs a corpus of REAL-LOOKING identities, and planting one
in the operator's live `work/` would be writing invented rows into client state.
So each test builds a complete miniature of the real arrangement in a temp dir:

    .gitignore        with `work/` in it, exactly as the real repository
    work/queue.jsonl  the planted corpus - GITIGNORED, so no git tool can see it
    scripts/pii_gate.py           copied from this checkout, byte for byte
    tests/test_fixture_hygiene.py copied, because the gate imports its denylist
    config/pii-gate-exceptions.txt

and then installs the hooks and runs real `git commit` calls against it.

## THE PLANTED IDENTITY IS INVENTED, AND THAT IS LOAD-BEARING TWICE

`Thimbleforge Analytics`, `Quilla Nightingale` and `thimbleforge-analytics.example`
appear in no corpus anywhere. They are real-SHAPED - a company, a person, a
domain, a record id, a contact key, a vanity handle - which is all the gate's
corpus layer needs, because it learns from whatever the corpus contains rather
than from a list of known names.

Being invented also means this test file does not itself leak: the strings are
in the tracked tree, and if any of them were real this file would be the fourth
incident of 2026-10-01. The domain is on `.example` (RFC 2606) so the gate's own
structural email rule stays satisfied too. `scripts/pii_gate.py` deliberately
uses DIFFERENT invented names in its own docstrings and self-test controls, so
that a `git grep` for the planted identity finds nothing - which is the premise
of `test_the_corpus_is_invisible_to_every_git_tool_and_the_gate_still_fires`.

## ACCEPTANCE 5 IS TESTED DIRECTLY

That test proves the premise rather than assuming it: in the throwaway
repository `git grep`, `git ls-files` and `git check-ignore` all report that the
planted name is not there, and the commit is refused anyway. That is the
difference between a gate that reads the corpus and one that searches the tree
and reports a clean sheet.

## EVERY TEST HERE WAS PROVED ABLE TO FAIL

Measured 2026-10-02 with a mutation harness: the gate was mutated six ways - it
always passes, it never scans the message, the corpus is unreachable, it always
refuses, a malformed exception is ignored, top-level record ids are not read -
and the tests that went red were recorded each time. Two mutations initially
left the suite GREEN, and both gaps are closed here: see `FAKE_ID_ONLY` and
`TestTheOtherTwoLayers`.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import pii_gate

#: Invented. See the module docstring - these must never be real.
FAKE_COMPANY = "Thimbleforge Analytics Ltd"
FAKE_DOMAIN = "thimbleforge-analytics.example"
FAKE_RECORD = "thimbleforge-analytics-example"
FAKE_PERSON = "Quilla Nightingale"
FAKE_KEY = "quilla-nightingale"
FAKE_EMAIL = "q.nightingale@thimbleforge-analytics.example"

#: A SECOND planted record whose ONLY identity-bearing field is the top-level
#: `id`. It exists because the first record could not prove that top-level ids
#: are read at all: `thimbleforge-analytics-example` and
#: `thimbleforge-analytics.example` share a canonical form, so the DOMAIN matcher
#: covered the record id, and a mutation that stopped reading `id` entirely left
#: the suite green. Measured 2026-10-02.
FAKE_ID_ONLY = "gralefrit-whistlecombe"

#: Equally invented, and chosen NOT to be in the planted corpus. The negative
#: control: a legitimate commit full of synthetic fixtures must pass.
CLEAN_COMPANY = "Pennywhistle Ventures GmbH"
CLEAN_PERSON = "Marigold Underbough"
CLEAN_DOMAIN = "pennywhistle-ventures.example"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Gate Test",
    "GIT_AUTHOR_EMAIL": "gate@tests.example",
    "GIT_COMMITTER_NAME": "Gate Test",
    "GIT_COMMITTER_EMAIL": "gate@tests.example",
}


def run(repo, *args, **kw):
    env = dict(os.environ)
    env.update(GIT_ENV)
    env.update(kw.pop("env_extra", {}) or {})
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True,
                          text=True, errors="replace", timeout=180, env=env)


def head_count(repo):
    out = run(repo, "rev-list", "--count", "HEAD")
    return int(out.stdout.strip()) if out.returncode == 0 else 0


class GateRepo(unittest.TestCase):
    """A throwaway repository with the gate installed and a planted corpus."""

    maxDiff = None

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="pii-gate-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for sub in ("scripts", "tests", "config", "work"):
            os.makedirs(os.path.join(self.repo, sub))

        # The real arrangement: the corpus directory is IGNORED.
        self.write(".gitignore", "work/\ncache/\n")
        for rel in ("scripts/pii_gate.py", "tests/test_fixture_hygiene.py",
                    "config/pii-gate-exceptions.txt"):
            shutil.copyfile(os.path.join(ROOT, rel),
                            os.path.join(self.repo, rel))

        # TWO planted records, in the real schema the gate reads.
        rows = [
            {
                "id": FAKE_RECORD,
                "company": FAKE_COMPANY,
                "domain": FAKE_DOMAIN,
                "state": "verified",
                "contacts": [{
                    "name": FAKE_PERSON,
                    "key": FAKE_KEY,
                    "email": FAKE_EMAIL,
                    "linkedin": "https://www.linkedin.com/in/" + FAKE_KEY,
                    "title": "Operations Director",
                }],
            },
            # Nothing in this row spells the id any other way. See FAKE_ID_ONLY.
            {"id": FAKE_ID_ONLY, "lane": "domains", "state": "verified",
             "contacts": []},
        ]
        self.write("work/queue.jsonl",
                   "".join(json.dumps(row) + "\n" for row in rows))

        run(self.repo, "init", "-q")
        run(self.repo, "config", "user.name", "Gate Test")
        run(self.repo, "config", "user.email", "gate@tests.example")
        run(self.repo, "config", "commit.gpgsign", "false")
        run(self.repo, "add", "-A")
        first = run(self.repo, "commit", "-q", "--no-verify", "-m", "base")
        self.assertEqual(first.returncode, 0, first.stderr)

        installed = pii_gate.install(self.repo, out=io.StringIO())
        self.assertEqual(installed, 0)
        self.hooks = pii_gate.hooks_dir(self.repo)
        self.assertTrue(os.path.isfile(os.path.join(self.hooks, "pre-commit")))
        self.assertTrue(os.path.isfile(os.path.join(self.hooks, "commit-msg")))

    def write(self, rel, text):
        full = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return full

    def attempt(self, message, files=None, env_extra=None):
        """Stage `files`, try to commit, return (returncode, output, moved)."""
        before = head_count(self.repo)
        if files:
            run(self.repo, "add", "--", *files)
        done = run(self.repo, "commit", "-m", message, env_extra=env_extra)
        after = head_count(self.repo)
        return done.returncode, done.stdout + done.stderr, after - before


class TestThePositiveControl(GateRepo):
    """A gate that has never fired is not known to work. Acceptance 4."""

    def test_a_fixture_naming_a_planted_real_identity_cannot_be_committed(self):
        self.write("tests/fixtures/prospects.json", json.dumps(
            [{"company": FAKE_COMPANY, "contact": FAKE_PERSON,
              "contact_key": FAKE_KEY}], indent=2) + "\n")
        code, out, moved = self.attempt("add a prospect fixture",
                                        ["tests/fixtures/prospects.json"])
        self.assertNotEqual(code, 0, "THE GATE DID NOT FIRE:\n" + out)
        self.assertEqual(moved, 0, "a commit was created anyway:\n" + out)
        self.assertIn("REFUSED", out)
        # It must say WHICH line, or nobody can act on it.
        self.assertIn("tests/fixtures/prospects.json", out)

    def test_it_fires_on_the_slug_shape_of_a_domain_in_the_corpus(self):
        """The leak that already landed is a slug, not a prose company name.

        `thimbleforge-analytics-example` and `thimbleforge-analytics.example`
        share no substring a naive matcher would find; they share a CANONICAL
        FORM, which is the whole mechanism. This does NOT prove that top-level
        record ids are read - see the next test, added after a mutation left
        this one green with `id` extraction switched off.
        """
        self.write("scripts/replay.py", "RECORDS = [\"%s\"]\n" % FAKE_RECORD)
        code, out, moved = self.attempt("replay helper", ["scripts/replay.py"])
        self.assertNotEqual(code, 0, "THE GATE DID NOT FIRE:\n" + out)
        self.assertEqual(moved, 0)

    def test_it_fires_on_a_record_id_nothing_else_in_the_row_spells(self):
        """Isolates the top-level `id` field. See FAKE_ID_ONLY."""
        self.write("tests/fixtures/ids.txt", FAKE_ID_ONLY + "\n")
        code, out, moved = self.attempt("an id fixture",
                                        ["tests/fixtures/ids.txt"])
        self.assertNotEqual(code, 0, "THE RECORD ID WAS NOT READ:\n" + out)
        self.assertEqual(moved, 0)

    def test_it_fires_on_the_contact_key_slug(self):
        self.write("tests/fixtures/keys.txt", FAKE_KEY + "\n")
        code, out, moved = self.attempt("a key fixture",
                                        ["tests/fixtures/keys.txt"])
        self.assertNotEqual(code, 0, "THE GATE DID NOT FIRE:\n" + out)
        self.assertEqual(moved, 0)

    def test_a_real_identity_in_the_COMMIT_MESSAGE_alone_is_refused(self):
        """Incident 1. A tree-only scan passes this. Acceptance 2.

        The file committed is clean; only the message names the identity.
        """
        self.write("src/classify.py", "DEFAULT_LANE = 'domains'\n")
        code, out, moved = self.attempt(
            "classify replies for %s" % FAKE_COMPANY, ["src/classify.py"])
        self.assertNotEqual(code, 0, "THE MESSAGE WAS NOT SCANNED:\n" + out)
        self.assertEqual(moved, 0, "a commit was created anyway:\n" + out)
        self.assertIn("COMMIT_MSG", out)

    def test_nothing_is_committed_when_it_refuses_and_the_change_survives(self):
        """BEFORE, not after. Acceptance 1.

        The point of pre-commit placement is that there is nothing to repair:
        the work is still staged and the history is untouched, so fixing the
        value and committing again is the whole remedy. A post-hoc check leaves
        a commit to rewrite, and this repository has already paid for that once.
        """
        path = "tests/fixtures/leak.json"
        self.write(path, json.dumps({"company": FAKE_COMPANY}) + "\n")
        before = run(self.repo, "rev-parse", "HEAD").stdout.strip()
        code, out, moved = self.attempt("fixture", [path])
        self.assertNotEqual(code, 0)
        self.assertEqual(run(self.repo, "rev-parse", "HEAD").stdout.strip(),
                         before, "HEAD moved")
        staged = run(self.repo, "diff", "--cached", "--name-only").stdout.split()
        self.assertIn(path, staged, "the staged work was lost")


class TestTheOtherTwoLayers(GateRepo):
    """The corpus layer is not the only one, and the others need a commit too.

    Mutation evidence, 2026-10-02: with only the corpus tests present, switching
    off the imported denylist or the structural email rule left the suite green.
    A layer no test exercises THROUGH THE HOOK is a layer nobody knows runs.
    """

    def _a_denylist_name(self):
        """A hand-reviewed forbidden name, READ AT RUNTIME, never written here.

        The value is real. It goes into a file inside the throwaway repository,
        which is deleted on teardown; writing it into THIS file would make the
        test a leak of the kind it tests for.
        """
        from tests.test_fixture_hygiene import FORBIDDEN_NAMES
        longest = max(FORBIDDEN_NAMES, key=len)
        self.assertGreater(len(longest), 6)
        return longest

    def test_a_hand_reviewed_denylist_name_in_the_message_is_refused(self):
        value = self._a_denylist_name()
        self.write("docs/LAYER.md", "# Layer\n")
        code, out, moved = self.attempt("notes about %s" % value,
                                        ["docs/LAYER.md"])
        self.assertNotEqual(code, 0, "THE DENYLIST LAYER DID NOT RUN:\n" + out)
        self.assertEqual(moved, 0)

    def test_an_address_on_a_domain_that_resolves_is_refused(self):
        """The ABSOLUTE rule: it needs no list, so it catches the unlisted name.

        The domain is invented, but its TLD can resolve, and that is the entire
        test - the rule is about reachability, not about whether anybody
        recognises the name.

        THE ADDRESS IS ASSEMBLED AT RUNTIME AND NEVER SPELLED HERE. Written as
        one literal it would be an address on a resolvable domain inside a
        tracked file, which is precisely what this gate and
        `tests/test_fixture_hygiene.py`'s strongest rule both refuse - and this
        file would have been refused by the control it is testing. Splitting it
        is not a trick: the scanners are line-based, so what they see in this
        file is not an address, and what the fixture file receives is.
        """
        address = "hello@" + "dunmorrow-tessellate" + "." + "com"
        self.write("tests/fixtures/contact.json", json.dumps(
            {"email": address}) + "\n")
        code, out, moved = self.attempt("a contact fixture",
                                        ["tests/fixtures/contact.json"])
        self.assertNotEqual(code, 0,
                            "THE STRUCTURAL EMAIL RULE DID NOT RUN:\n" + out)
        self.assertEqual(moved, 0)


class TestTheNegativeControl(GateRepo):
    """It must also PASS, or it is a gate that blocks all work equally."""

    def test_a_legitimate_commit_with_synthetic_fixtures_is_committed(self):
        self.write("tests/fixtures/synthetic.json", json.dumps(
            [{"company": CLEAN_COMPANY, "contact": CLEAN_PERSON,
              "domain": CLEAN_DOMAIN,
              "email": "hello@" + CLEAN_DOMAIN}], indent=2) + "\n")
        code, out, moved = self.attempt(
            "add synthetic prospect fixtures for the classifier",
            ["tests/fixtures/synthetic.json"])
        self.assertEqual(code, 0, "A CLEAN COMMIT WAS REFUSED:\n" + out)
        self.assertEqual(moved, 1, out)

    def test_the_planted_corpus_does_not_make_every_commit_fail(self):
        """A matcher set that matched everything would pass every test above."""
        self.write("docs/NOTES.md",
                   "# Notes\n\nThe classifier reads the lane and the state.\n")
        code, out, moved = self.attempt("notes on the classifier",
                                        ["docs/NOTES.md"])
        self.assertEqual(code, 0, "ORDINARY PROSE WAS REFUSED:\n" + out)
        self.assertEqual(moved, 1)

    def test_a_git_trailer_carrying_a_machine_address_is_not_a_leak(self):
        """Measured on the real repository: every commit carries one.

        The mandated `Co-Authored-By:` footer carries a vendor `noreply` address
        on a domain that resolves, which the structural email rule is right
        about. Replaying the last 30 real commits produced 22 structural hits
        from that one line. A gate that refuses the repository's own commit
        footer is uninstalled the same hour.

        The address is assembled at runtime, as elsewhere in this file: written
        out it would be a resolvable address in a tracked file.
        """
        trailer = "Co-Authored-By: Claude <noreply@" + "anthropic" + ".com>"
        self.write("docs/TRAILER.md", "# Trailer\n")
        code, out, moved = self.attempt("notes\n\n" + trailer,
                                        ["docs/TRAILER.md"])
        self.assertEqual(code, 0, "THE MANDATED TRAILER WAS REFUSED:\n" + out)
        self.assertEqual(moved, 1)


class TestTheGitignoredCorpus(GateRepo):
    """Acceptance 5. The search tools cannot see the corpus. The gate can."""

    def test_the_corpus_is_invisible_to_every_git_tool_and_the_gate_still_fires(self):
        # 1. git agrees the corpus file is ignored.
        self.assertEqual(
            run(self.repo, "check-ignore", "-q", "work/queue.jsonl").returncode,
            0, "work/ is not ignored in the fixture repository, so this test "
               "would prove nothing")
        # 2. It is not tracked, so `ls-files` cannot list it.
        self.assertEqual(run(self.repo, "ls-files", "--", "work/").stdout, "")
        # 3. THE TRAP ITSELF: a repo-wide search for the planted identity finds
        #    nothing. `git grep` searches tracked content only, and the repo's
        #    Grep tooling honours .gitignore the same way. Exit 1 means no
        #    match - a clean sheet that means nothing.
        grep = run(self.repo, "grep", "-ri", "thimbleforge")
        self.assertEqual(grep.returncode, 1,
                         "git grep found the corpus; the premise of this test "
                         "is gone:\n" + grep.stdout)
        # 4. And the gate fires anyway, because it opens the file itself.
        self.write("tests/fixtures/x.json",
                   json.dumps({"company": FAKE_COMPANY}) + "\n")
        code, out, moved = self.attempt("fixture", ["tests/fixtures/x.json"])
        self.assertNotEqual(code, 0, "THE GATE IS BLIND IN THE SAME PLACE THE "
                                     "SEARCH TOOLS ARE:\n" + out)
        self.assertEqual(moved, 0)

    def test_no_corpus_value_is_written_into_a_tracked_file(self):
        """The gate must not become the leak.

        After a refusal, nothing under version control may carry the planted
        value: not the exception file, not a report, not a cache. The cache is
        allowed to exist - it holds fingerprints - but it has to be ignored.
        """
        self.write("tests/fixtures/y.json",
                   json.dumps({"contact": FAKE_PERSON}) + "\n")
        code, _out, _moved = self.attempt("fixture", ["tests/fixtures/y.json"])
        self.assertNotEqual(code, 0)
        tracked = run(self.repo, "ls-files").stdout.split()
        others = run(self.repo, "ls-files", "--others",
                     "--exclude-standard").stdout.split()
        for rel in tracked + others:
            if rel.startswith("tests/fixtures/"):
                continue            # the test's own planted fixture
            full = os.path.join(self.repo, rel)
            if not os.path.isfile(full):
                continue
            with open(full, encoding="utf-8", errors="replace") as handle:
                body = handle.read().lower()
            for needle in ("thimbleforge", "nightingale", "gralefrit"):
                self.assertNotIn(
                    needle, body,
                    "%s is committable and carries the corpus value" % rel)

    def test_the_fingerprint_cache_is_produced_gitignored_and_valueless(self):
        """Three claims, and the first one keeps the other two honest.

        An `if the cache exists` test passes vacuously the moment a change stops
        the cache being written at all - including the change that would matter
        most, moving it somewhere the gate then refuses to write. So this asserts
        it IS produced, THEN that git ignores it, THEN that it carries
        fingerprints rather than identities.
        """
        pii_gate.build_matcher(self.repo, use_cache=True)
        cache = "cache/pii-gate-fingerprints.json"
        full = os.path.join(self.repo, *cache.split("/"))
        self.assertTrue(os.path.isfile(full),
                        "no cache was produced, so this test would prove "
                        "nothing about where one goes")
        self.assertEqual(run(self.repo, "check-ignore", "-q", cache).returncode,
                         0, "the fingerprint cache is committable")
        with open(full, encoding="utf-8") as handle:
            body = handle.read().lower()
        for needle in ("thimbleforge", "nightingale", "gralefrit"):
            self.assertNotIn(needle, body, "the cache holds the raw value")

    def test_a_worktree_with_no_corpus_of_its_own_uses_the_main_checkouts(self):
        """A worktree has its own, EMPTY `work/` - the corpus is gitignored.

        Measured on this repository: without this fallback an agent working in a
        worktree gets an empty matcher set and a clean PASS on a real name. The
        gate resolves the main checkout through `--git-common-dir`.
        """
        wt = tempfile.mkdtemp(prefix="pii-gate-wt-")
        self.addCleanup(shutil.rmtree, wt, ignore_errors=True)
        shutil.rmtree(wt)
        added = run(self.repo, "worktree", "add", "-q", "-b", "probe", wt)
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertFalse(os.path.isfile(os.path.join(wt, "work", "queue.jsonl")),
                         "the worktree has a corpus of its own; this test would "
                         "prove nothing")
        resolved = pii_gate.corpus_root(wt)
        self.assertTrue(resolved and os.path.isfile(
            os.path.join(resolved, "queue.jsonl")),
            "a worktree resolved no corpus: %r" % resolved)


class TestTheExceptionIsCheapAndNamed(GateRepo):
    """Acceptance 6. A gate with an expensive override is a gate that is off."""

    def _refuse_and_get_token(self):
        self.write("docs/NOTE.md", "Our pilot account is %s.\n" % FAKE_COMPANY)
        code, out, _moved = self.attempt("note", ["docs/NOTE.md"])
        self.assertNotEqual(code, 0, out)
        tokens = [w for w in out.replace("\n", " ").split()
                  if w.startswith("pg-")]
        self.assertTrue(tokens,
                        "the refusal printed no fingerprint to excuse:\n" + out)
        return tokens

    def test_a_named_reviewed_exception_lets_the_same_commit_through(self):
        tokens = self._refuse_and_get_token()
        lines = "".join(
            "docs/NOTE.md | %s | Zvonimir | pilot account named with the "
            "client's written permission\n" % t for t in set(tokens))
        with open(os.path.join(self.repo, pii_gate.EXCEPTIONS), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(lines)
        code, out, moved = self.attempt("note", ["docs/NOTE.md",
                                                 pii_gate.EXCEPTIONS])
        self.assertEqual(code, 0, "THE EXCEPTION DID NOT WORK:\n" + out)
        self.assertEqual(moved, 1)

    def test_an_exception_for_another_path_does_not_excuse_this_one(self):
        tokens = self._refuse_and_get_token()
        with open(os.path.join(self.repo, pii_gate.EXCEPTIONS), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("docs/OTHER.md | %s | Zvonimir | a different file "
                         "entirely\n" % tokens[0])
        code, out, _moved = self.attempt("note", ["docs/NOTE.md",
                                                  pii_gate.EXCEPTIONS])
        self.assertNotEqual(code, 0, "A PATH-SCOPED EXCEPTION LEAKED:\n" + out)

    def test_an_exception_with_no_reviewer_refuses_the_commit(self):
        """Malformed REFUSES. It must never be silently skipped.

        "My exception did not parse and the gate said PASS" is the worst
        available outcome: the committer believes the hit was cleared.
        """
        with open(os.path.join(self.repo, pii_gate.EXCEPTIONS), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("docs/NOTE.md | pg-000000000000 |  | no reviewer\n")
        self.write("docs/CLEAN.md", "# Clean\n")
        code, out, moved = self.attempt("clean", ["docs/CLEAN.md",
                                                  pii_gate.EXCEPTIONS])
        self.assertNotEqual(code, 0,
                            "A MALFORMED EXCEPTION WAS IGNORED:\n" + out)
        self.assertIn("malformed", out.lower())
        self.assertEqual(moved, 0)

    def test_an_exception_holding_the_raw_value_is_refused(self):
        """The exception file is TRACKED. A value written there is the leak.

        So the format cannot accept one: the token must be a fingerprint or a
        rule name, and anything else stops the commit.
        """
        with open(os.path.join(self.repo, pii_gate.EXCEPTIONS), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("docs/NOTE.md | %s | Zvonimir | pasting the value in "
                         "here is the mistake\n" % FAKE_COMPANY)
        self.write("docs/CLEAN.md", "# Clean\n")
        code, out, _moved = self.attempt("clean", ["docs/CLEAN.md",
                                                   pii_gate.EXCEPTIONS])
        self.assertNotEqual(code, 0, "A RAW VALUE IN THE EXCEPTION FILE WAS "
                                     "ACCEPTED:\n" + out)

    def test_a_rule_scoped_exception_clears_a_whole_structural_rule(self):
        """The cheap override for the predictable class of false positive.

        The number is assembled at runtime for the same reason the address in
        `TestTheOtherTwoLayers` is: spelled out, it would be a phone number
        outside the reserved-fiction set in a tracked file, and
        `tests/test_fixture_hygiene.py` fails on exactly that. It has to be a
        number the gate rejects, so it cannot be one of the allowed fictions.
        """
        number = "+44 " + "20 " + "7123 " + "4567"
        self.write("docs/PHONE.md", "Call the office on %s.\n" % number)
        code, out, _moved = self.attempt("phone", ["docs/PHONE.md"])
        self.assertNotEqual(code, 0,
                            "a real-shaped phone number passed:\n" + out)
        with open(os.path.join(self.repo, pii_gate.EXCEPTIONS), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("docs/PHONE.md | rule:structural:phone | Zvonimir | "
                         "the agency switchboard, published on their website\n")
        code, out, moved = self.attempt("phone", ["docs/PHONE.md",
                                                  pii_gate.EXCEPTIONS])
        self.assertEqual(code, 0, "THE RULE EXCEPTION DID NOT WORK:\n" + out)
        self.assertEqual(moved, 1)


class TestTheGateDoesNotBreakTheRepository(GateRepo):
    """A control that blocks legitimate work gets removed, so it must not."""

    def test_a_branch_without_the_script_is_still_committable(self):
        """`.git/hooks` survives a branch switch; the script may not be there.

        Before this lands, `master` has no `scripts/pii_gate.py`. A hook that
        hard-failed on a missing script would make the previous commit of this
        very repository impossible to make.
        """
        os.remove(os.path.join(self.repo, "scripts", "pii_gate.py"))
        run(self.repo, "rm", "-q", "--cached", "scripts/pii_gate.py")
        self.write("docs/ANY.md", "# Any\n")
        code, out, moved = self.attempt("commit without the gate script",
                                        ["docs/ANY.md"])
        self.assertEqual(code, 0, "A CHECKOUT WITHOUT THE SCRIPT IS "
                                  "UNCOMMITTABLE:\n" + out)
        self.assertEqual(moved, 1)
        self.assertIn("NOT RUN", out)

    def test_the_hooks_are_installed_where_git_actually_looks(self):
        """`core.hooksPath` is set in this repository's LOCAL config.

        Installing into `.git/hooks` while git reads elsewhere gives a gate that
        exists, tests green and never runs.
        """
        elsewhere = os.path.join(self.repo, "myhooks")
        os.makedirs(elsewhere)
        run(self.repo, "config", "core.hooksPath", elsewhere)
        self.assertEqual(pii_gate.hooks_dir(self.repo), elsewhere)
        pii_gate.install(self.repo, out=io.StringIO())
        self.write("tests/fixtures/z.json",
                   json.dumps({"company": FAKE_COMPANY}) + "\n")
        code, out, moved = self.attempt("fixture", ["tests/fixtures/z.json"])
        self.assertNotEqual(code, 0, "THE HOOK WENT WHERE GIT DOES NOT "
                                     "LOOK:\n" + out)
        self.assertEqual(moved, 0)

    def test_installing_twice_does_not_stack_or_fail(self):
        self.assertEqual(pii_gate.install(self.repo,
                                          out=io.StringIO()), 0)
        with open(os.path.join(self.hooks, "pre-commit"),
                  encoding="utf-8") as handle:
            body = handle.read()
        self.assertEqual(body, pii_gate.PRE_COMMIT,
                         "a second install stacked onto the first")

    def test_a_foreign_pre_commit_hook_is_never_overwritten(self):
        path = os.path.join(self.hooks, "pre-commit")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("#!/bin/sh\necho somebody elses hook\n")
        pii_gate.install(self.repo, out=io.StringIO())
        with open(path, encoding="utf-8") as handle:
            self.assertIn("somebody elses hook", handle.read())


class TestTheSelfTest(unittest.TestCase):
    """Acceptance 3, against whatever corpus this machine actually has."""

    def test_every_protected_value_is_caught_by_the_real_scanner(self):
        """It runs each value through `scan_text`, not through an inspection.

        On the operator's machine this is 25,000+ live values. On a machine with
        no `work/` it is the imported denylist alone, and the assertion still
        has to hold - so the test checks the count it actually ran, which is the
        number that makes the PASS mean something.
        """
        buf = io.StringIO()
        code = pii_gate.selftest(ROOT, out=buf)
        report = buf.getvalue()
        self.assertEqual(code, 0, report)
        self.assertIn("SELFTEST: PASS", report)
        checked = [l for l in report.splitlines() if "real scanner" in l]
        self.assertTrue(checked)
        n = int(checked[0].rsplit(":", 1)[1])
        self.assertGreater(n, 50, "the self-test protected almost nothing, so "
                                  "its PASS says almost nothing:\n" + report)

    def test_the_canonical_form_collapses_the_shapes_an_identity_arrives_in(self):
        """One fingerprint for the slug, the domain, the key and the name.

        This is what lets a corpus that holds only `a-b-c` refuse a fixture that
        writes `A B C` - the shape a fixture author actually reaches for.
        """
        for a, b in (("thimbleforge-analytics.example",
                      "Thimbleforge Analytics Example"),
                     ("quilla-nightingale", "Quilla Nightingale"),
                     ("quilla.nightingale@x", "Quilla Nightingale X")):
            with self.subTest(a=a):
                self.assertEqual(pii_gate.canon(a), pii_gate.canon(b))
                self.assertEqual(pii_gate.fp(pii_gate.canon(a)),
                                 pii_gate.fp(pii_gate.canon(b)))

    def test_a_fingerprint_is_not_the_value(self):
        token = pii_gate.fp(pii_gate.canon(FAKE_PERSON))
        self.assertTrue(token.startswith("pg-"))
        self.assertEqual(len(token), 15)
        self.assertNotIn("quilla", token)
        self.assertNotIn("nightingale", token)


if __name__ == "__main__":
    unittest.main()
