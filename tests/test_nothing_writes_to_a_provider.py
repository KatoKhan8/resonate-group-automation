#!/usr/bin/env python3
"""Repo-wide: no code may issue an HTTP write to a provider.

An audit that found nothing is worth exactly as much as the day it was run.
`tests/test_audit.py` pins the two provider modules that were known to matter;
this asks the same question of EVERY file, so a POST added next month to a
module nobody thought about fails here rather than in somebody's inbox.

WHY BY SOURCE INSPECTION, which this repository's own guidance warns against.
The rule is about code that does not exist yet, in modules not yet written, so
there is no object to interrogate and no behaviour to exercise. The usual
failure mode of a source-text test - breaking when somebody writes a comment -
is handled by stripping comments and docstrings before matching, and the
allowlist is by (file, verb) so a legitimate new write has to be named here
deliberately.

WHAT IS ALLOWED, and why each one is not a prospect-facing write:

  providers/apify.py       POST starts a crawler on the COMPANY'S OWN website.
                           Billable, bounded, and no person is contacted.
  providers/slack.py       POST posts into the team's own Slack. Internal.
  providers/contactout.py  POST is how this vendor spells a lookup. Reads.
  providers/aiark.py       the same.
  providers/blitz.py       the same.
  providers/deliverable.py DYNAMIC - its verb comes from an env var, so it is
                           declared as unreadable rather than as a POST. It
                           submits an address to a verification vendor.
  providers/heyreach.py    POST is how this vendor spells EVERY call including
                           reads; `_read` checks `READ_ROUTES_ALL` before the
                           request, which `tests/test_audit.py` pins.

AND A VERB THIS TEST CANNOT READ IS ITSELF A FINDING. `deliverable.py` calls
`request(plan["method"], ...)`, where the method comes from an environment
variable - so no amount of matching on literal strings can tell what it sends.
That is exactly the shape a future bypass would have, whether or not anybody
intended one, so a non-literal verb is reported as DYNAMIC and has to be
declared here too.
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# HTTP verbs that change something on the far side.
WRITE_VERBS = ("POST", "PUT", "PATCH", "DELETE")

# (relative path, verb) pairs that are deliberate. Adding a row here is the
# decision; the test is only the thing that makes it a decision.
ALLOWED = {
    ("src/providers/apify.py", "POST"),
    ("src/providers/slack.py", "POST"),
    ("src/providers/contactout.py", "POST"),
    ("src/providers/aiark.py", "POST"),
    ("src/providers/blitz.py", "POST"),
    ("src/providers/deliverable.py", "DYNAMIC"),
    ("src/providers/heyreach.py", "POST"),
    # EmailBison gained real write verbs on 2026-09-13, after the routes this
    # repository had written off as absent turned out to be documented. Each
    # is declared here on purpose, and each is one of two kinds:
    #
    #   STAGING - create_campaign (a DRAFT, which cannot send), set_sequence,
    #   set_limits, create_lead, attach_leads, ensure_custom_variables. None
    #   reaches a person: the campaign they build is left `paused`, and
    #   `bison.activate` is still unsupported, so nothing here can start it.
    #
    #   STOPPING - pause_campaign and stop_lead, which can only ever mean
    #   somebody receives LESS. `stop_lead` is the per-lead stop the safety
    #   argument needs, and refusing it would make this system less safe, not
    #   more.
    #
    # The prospect-facing verb on this provider - activate - is still absent
    # from `providerwrites.SUPPORTED`, which is what keeps the invariant in
    # this file true.
    ("src/providers/bison.py", "POST"),
    ("src/providers/bison.py", "PATCH"),
    # PUT, added 2026-09-13, and it writes exactly one thing: the SENDING
    # WINDOW of a campaign that already has one. `POST .../schedule` creates a
    # schedule and refuses to replace one - it answers 200 carrying
    # `success: false, "Schedule already exists"` and writes nothing - so
    # without this verb a window could be set once and never narrowed, and the
    # attempt to narrow it read as a success. `PATCH` and `DELETE` are both
    # 405 on that route; the 405 names GET, HEAD, POST, PUT.
    #
    # It is STAGING, and of the constraining kind: the only thing it can
    # change is when a campaign is allowed to send, and the route is already
    # in `bison.WRITE_ROUTES`. It starts nothing - `/campaigns/{id}/resume` is
    # the only verb here that reaches a person and it is a PATCH, declared
    # above and guarded in `resume_campaign`.
    ("src/providers/bison.py", "PUT"),
    # A completion is a POST that changes nothing at the other end: it creates
    # no campaign, touches no lead, and is not prospect-facing, so it does not
    # belong under `providerwrites`. It is declared here rather than waved
    # through because it is still egress that SPENDS MONEY, and the point of
    # this list is that somebody chose each row on purpose.
    ("src/llm.py", "POST"),
}

# Calls that name a verb. `request("POST", ...)` is this repo's own transport;
# the `requests` library spellings are what a prototype reaches for.
CALLS = re.compile(
    r"""(?:\brequest\s*\(\s*["'](?P<verb1>[A-Z]+)["']"""
    r"""|requests\s*\.\s*(?P<verb2>post|put|patch|delete)\s*\("""
    r"""|urlopen\s*\([^)]*method\s*=\s*["'](?P<verb3>[A-Z]+)["'])""",
    re.VERBOSE)

STRINGS = re.compile(r'("""|\'\'\')(?:.|\n)*?\1', re.MULTILINE)

# `request(` whose first argument is not a quoted literal. The verb is decided
# at runtime, so no amount of reading can say what it sends.
#
# `\brequest` and not `request`: without the boundary this matched every
# identifier ENDING in request - `campaign_approval_request(`,
# `emailbison_request(`, `redirect_request(` - and reported seven modules that
# issue no HTTP at all. A guard that cries wolf is a guard somebody switches
# off. The `def ` lookbehind excludes the transport's own definition.
DYNAMIC = re.compile(r"""(?<!def )\brequest\s*\(\s*(?!["'])[A-Za-z_]""")


def code_of(path):
    """The file with docstrings and comments removed.

    So that describing a POST in prose - which several modules do at length,
    on purpose - is never mistaken for issuing one.
    """
    text = io.open(path, encoding="utf-8").read()
    text = STRINGS.sub("", text)
    return "\n".join(line.split("#")[0] for line in text.splitlines())


def python_files():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("__pycache__", ".git", "work", "node_modules",
                                "venv", ".venv")]
        for name in names:
            if name.endswith(".py"):
                full = os.path.join(base, name)
                yield full, os.path.relpath(full, ROOT).replace("\\", "/")


class NoUndeclaredProviderWrite(unittest.TestCase):

    def writes(self):
        found = []
        for full, rel in python_files():
            if rel.startswith("tests/"):
                continue
            code = code_of(full)
            for match in CALLS.finditer(code):
                verb = (match.group("verb1") or match.group("verb2")
                        or match.group("verb3") or "").upper()
                if verb in WRITE_VERBS:
                    found.append((rel, verb))
            if DYNAMIC.search(code):
                found.append((rel, "DYNAMIC"))
        return sorted(set(found))

    def test_every_http_write_in_the_repository_is_declared(self):
        undeclared = [w for w in self.writes() if w not in ALLOWED]
        self.assertEqual(
            undeclared, [],
            "HTTP writes nobody declared: %s\n"
            "If one of these is a prospect-facing action it must go through "
            "src/executionguard.py and src/providerwrites.py. If it is a read "
            "a vendor spells as POST, add it to ALLOWED with the reason."
            % (undeclared,))

    def test_the_allowlist_has_no_dead_rows(self):
        """A row that stops matching is a claim nobody is checking any more."""
        actual = set(self.writes())
        dead = sorted(row for row in ALLOWED if row not in actual)
        self.assertEqual(dead, [],
                         "ALLOWED names writes that no longer exist: %s" % (dead,))

    def test_the_prototype_carries_no_transport(self):
        """It cannot be brought under the guard - it imports nothing from src.

        `prototype/bin/push.py` held two fully formed `requests.post` bodies to
        HeyReach and EmailBison behind three hand-placed `refuse_live()` calls.
        A refusal somebody can delete is not the same as a capability that is
        not there.
        """
        offenders = [rel for _, rel in python_files()
                     if rel.startswith("prototype/")
                     and any(v in WRITE_VERBS
                             for m in CALLS.finditer(code_of(os.path.join(ROOT, rel)))
                             for v in [(m.group("verb1") or m.group("verb2")
                                        or m.group("verb3") or "").upper()])]
        self.assertEqual(offenders, [],
                         "the prototype can reach a provider again: %s"
                         % (offenders,))

    def test_the_scanner_would_notice_one(self):
        """Guard the guard: a regex that matches nothing passes everything."""
        self.assertTrue(CALLS.search('request("POST", url)'))
        self.assertTrue(CALLS.search("requests.post(url)"))
        self.assertTrue(CALLS.search('request("DELETE", url)'))

    def test_a_verb_decided_at_runtime_is_reported(self):
        """The evasion this test would otherwise be blind to."""
        self.assertTrue(DYNAMIC.search('request(plan["method"], url)'))
        self.assertTrue(DYNAMIC.search("request(verb, url)"))
        self.assertIsNone(DYNAMIC.search('request("GET", url)'),
                          "a literal GET was reported as unreadable")

    def test_it_does_not_fire_on_prose(self):
        """The failure mode of every source-text test."""
        self.assertEqual(
            [m for m in CALLS.finditer(code_of(os.path.join(
                ROOT, "src", "providerwrites.py")))
             if (m.group("verb1") or "").upper() in WRITE_VERBS],
            [],
            "providerwrites.py documents POST routes in prose and the scanner "
            "read them as calls")


if __name__ == "__main__":
    unittest.main()
