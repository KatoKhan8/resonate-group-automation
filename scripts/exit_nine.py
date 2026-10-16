#!/usr/bin/env python3
"""All nine CANARY-01 exit criteria, evaluated ONCE, in ONE tree, at ONE SHA.

## The sentence this exists to close

`CONTINUITY.md` §6: *"All nine true at once has still never been measured
anywhere."* Nine criteria have been measured many times - in different trees,
at different SHAs, by different lanes, on different days - and at least three
times a later measurement moved an earlier verdict. **A set of nine verdicts
collected over two days is not a statement about any moment.** The canary needs
the CONJUNCTION, evaluated once, here, now.

## What this is NOT

It is not a reader of `EXIT-CRITERIA-2026-10-16.md` or of any lane document.
Re-reading those is what produced two wrong beliefs on 2026-10-15, both caught
by re-measuring. **Every verdict below comes from running that criterion's own
check in this tree at this SHA.** Where a criterion has no check as code, it is
UNKNOWN with `no instrument` as the reason, and it is named in the closing list
rather than glossed. This module deliberately builds none of those missing
checks.

## Fail closed, and the three rules that make UNKNOWN load-bearing

1. A check that raises, times out, or cannot resolve its authority is
   **UNKNOWN**, never a pass, and the run exits non-zero.
2. The conjunction may print MET only if all nine are MET **in this run, in
   this tree, at this SHA**. One UNKNOWN makes the conjunction UNKNOWN - not
   false, and certainly not true.
3. If HEAD cannot be verified to carry THIS FILE as committed bytes, every
   verdict is UNKNOWN. A verdict measured against uncommitted bytes already
   cost this estate a corrected report, so the instrument hashes itself
   against `HEAD:scripts/exit_nine.py` rather than trusting `git status`.

## MET-WITH-CAVEAT is not a verdict here, and that is a decision

Earlier audits used MET-WITH-CAVEAT. A conjunction cannot consume a caveat: if
the criterion as WORDED is not satisfied, the conjunction must not be allowed
to read MET on it. So a caveat that the criterion's own wording does not permit
resolves to **NOT MET**, and the caveat goes in the condition column where a
reader sees it. This is stated in the report, because it is a judgement and it
moves two rows.

## Exit codes

    0   conjunction MET
    1   conjunction NOT MET  (every criterion determined, at least one failing)
    2   conjunction UNKNOWN  (at least one criterion undetermined)
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

MET = "MET"
NOT_MET = "NOT MET"
UNKNOWN = "UNKNOWN"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.join(ROOT, "scripts", "exit_nine.py")

#: The two authorities that live OUTSIDE the repository. Overridable ONLY so
#: the C1/C2 controls can plant a fixture or blind an authority; a plain run
#: never sets them, and the report prints the path actually read.
OPS = os.environ.get("EXIT_NINE_OPS",
                     r"C:\Users\Zvonimir\Desktop\resonate-ops")
ESTATE_EXPORT = os.environ.get(
    "EXIT_NINE_ESTATE",
    os.path.join(OPS, "canary", "sender-estate-export-2026-10-15.csv"))
APPROVAL_SHEET = os.environ.get(
    "EXIT_NINE_SHEET",
    os.path.join(OPS, "canary", "APPROVAL-SHEET-2026-10-15.md"))
APPROVAL_DECISION = os.environ.get(
    "EXIT_NINE_DECISION",
    os.path.join(OPS, "DECISION-canary-approval-2026-10-15.md"))

TEST_TIMEOUT = 900


class Undetermined(Exception):
    """Raised by a check that cannot determine its criterion. Becomes UNKNOWN."""


def _run(argv, timeout=TEST_TIMEOUT):
    try:
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Undetermined("timed out after %ds: %s" % (timeout, " ".join(argv)))
    return proc.returncode, proc.stdout + proc.stderr


def unittest_names(modules):
    """Run modules and return (ran, failing-name-set, raw). Counts are never
    the method here either - the failing set is returned by NAME."""
    code, out = _run([sys.executable, "-B", "-m", "unittest", "-v"] + list(modules))
    ran = re.search(r"^Ran (\d+) tests?", out, re.M)
    if not ran:
        raise Undetermined("unittest printed no 'Ran N tests' line for %s; "
                           "an unparseable run is UNDETERMINED, not a pass"
                           % ", ".join(modules))
    names = set()
    for line in out.splitlines():
        hit = re.match(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", line)
        if hit:
            names.add(hit.group(3))
    unexpected = len(re.findall(r"unexpected success", out))
    return int(ran.group(1)), names, out, unexpected


#: `unittest -v`'s COMPLETE set of terminal status tokens. Nothing else can
#: appear after the `... `, so this alternation is the whole input space of any
#: row that reads a named test's result, and TASK-0243 measured all six by
#: forcing each one.
TERMINAL_STATUS = re.compile(
    r"\.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)")
#: What each token lets a row CONCLUDE. Three buckets and not two, because
#: "did not pass" and "failed" are different facts: a skipped, expectedly
#: failing or unexpectedly succeeding test did not execute as the thing it was
#: named to demonstrate, so it establishes neither verdict.
PASSED = ("ok",)
REFUTED = ("FAIL", "ERROR")
INCONCLUSIVE = ("skipped", "expected failure", "unexpected success")

#: TASK-0243, AND THE REASON THE STATUS IS READ AS A TOKEN AND NEVER AS A
#: SUBSTRING OF A LABEL. Until this commit, criterion 2 scored itself with
#:
#:     bad = [s for s in shown if "NOT ok" in s]
#:
#: against labels built by `"%s (RAN, %s)" % (leaf, token)`. `"NOT ok"` is a
#: string NO branch of that builder can produce, so the row could not print
#: NOT MET for ANY state of its input and a FAILING demonstration read as a
#: pass. Measured over the complete input space, not sampled: with each of the
#: six tokens above forced in turn, the unrepaired row printed MET six times
#: out of six.
#:
#: It was not born wrong. At dcd618d9c the label WAS `leaf + " (RAN, NOT ok)"`
#: and the detector matched it exactly. 5b8dfd108 fixed a real false negative
#: by printing the true status instead - and left the detector reading the
#: retired literal. One fact, two representations, and the two drifted the
#: moment one of them was repaired. So the two are kept apart by role here:
#: `status_label` is for the operator's eye and is never parsed back, and the
#: TOKEN is the only thing a verdict branches on.


def terminal_statuses(out):
    """{dotted test name: terminal status token} from a `unittest -v` stream.

    ONE parser, consumed by every row that needs a named test's result.

    `unittest -v` prints `leaf (dotted.path.Class.leaf)` and then, when the
    test HAS a docstring, the docstring's first line and the terminal `... ok`
    on the FOLLOWING line. A regex anchored to the name line alone reported two
    green tests as failing in this very file (5b8dfd108), so the status is read
    from the name line AND the lines after it - stopping at the next test's
    name line, so a long docstring can never let one test inherit the next
    one's status.
    """
    lines = out.splitlines()

    def is_name_line(line):
        head = re.match(r"^(\w+) \(([\w.]+)\)", line)
        if head and head.group(2).endswith("." + head.group(1)):
            return head
        return None

    statuses = {}
    for index, line in enumerate(lines):
        head = is_name_line(line)
        if not head:
            continue
        for offset, follow in enumerate(lines[index:index + 4]):
            if offset and is_name_line(follow):
                break
            hit = TERMINAL_STATUS.search(follow)
            if hit:
                statuses[head.group(2)] = hit.group(1)
                break
    return statuses


def status_label(dotted, token):
    """The string an operator reads. NEVER parsed back into a verdict."""
    leaf = dotted.rsplit(".", 1)[-1]
    return leaf if token in PASSED else "%s (RAN, %s)" % (leaf, token)


def agrees_with_the_failure_summary(statuses, failed, scope):
    """Undetermined unless the -v stream and unittest's own FAIL/ERROR summary
    name the SAME red tests inside `scope`.

    The two are independent readings of one run. If a parser here ever drifts
    from unittest's own accounting - a format change, a wrapped line, a token
    nobody anticipated - this makes the row UNKNOWN instead of letting the
    friendlier reading stand. It is the interlock the `"NOT ok"` detector never
    had: that defect was undetectable precisely because nothing compared the
    row's own reading against a second one.
    """
    inside = set(name for name in scope if name in statuses)
    red_here = set(name for name in inside if statuses[name] in REFUTED)
    red_there = set(name for name in failed if name in scope)
    if red_here != red_there:
        raise Undetermined(
            "the -v stream and unittest's own failure summary disagree about "
            "which of these tests are red: the stream says %s, the summary "
            "says %s. Two readings of one run that disagree make the authority "
            "UNRESOLVED, not the friendlier of the two"
            % (sorted(red_here) or "none", sorted(red_there) or "none"))
    return sorted(red_here)


def authority(path):
    """(path, state) on the pattern the suppression preflight uses."""
    if not os.path.exists(path):
        return path, "absent"
    try:
        with open(path, "rb") as handle:
            handle.read(1)
    except OSError as blind:
        return path, "unreadable (%s)" % (blind.strerror or blind)
    return path, "present"


def require_readable(*paths):
    read = []
    for path in paths:
        got, state = authority(path)
        read.append((got, state))
        if state != "present":
            raise Undetermined("authority %s is %s - an unreadable authority "
                               "is UNKNOWN and UNKNOWN never becomes a pass"
                               % (got, state))
    return read


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# ---------------------------------------------------------------- the nine

#: CRITERION 1'S SECOND HALF HAS AN INSTRUMENT, AND HAS HAD ONE SINCE TASK-0160.
#: `scripts/suppression_on_every_write_path.py` was committed FOR this criterion,
#: names "CANARY-01 exit criterion 1" in its own docstring, and sits at the SAME
#: SHA as this file. The first version of this row never called it. It called
#: `write_path_denominator.py` - which answers criterion 5's question (does the
#: write pass the DOOR) and says nothing about suppression consults - and read
#: "no instrument" off that silence, then wrote the inference into the condition
#: column as a fact, including the claim that the 21-of-58 figure "was
#: hand-derived, not computed". It was computed, by that script, and it
#: reproduces: 58 paths, 5 in-function, 32 via the door, 21 with no consult.
#: Failure family 4, a measurement taken on the wrong artifact, with family 6
#: on top - "NO INSTRUMENT" was the nearest name this row had for "not wired".
SUPPRESSION_CONSULT_INSTRUMENT = os.path.join(
    ROOT, "scripts", "suppression_on_every_write_path.py")


def suppression_consult_counts():
    """(paths, in_function, via_door, no_consult) from the committed instrument.

    Fails closed in four directions, because the number this returns is read
    immediately before a decision about a first live send:

    * instrument ABSENT or UNREADABLE -> Undetermined, naming the absolute
      path. "No instrument" is a claim about THIS tree and has to be measured;
      inferring it from another script's silence is what this row did for a day.
    * any of the four lines UNPARSEABLE -> Undetermined. A partially parsed
      report whose missing field defaults to zero reads exactly like a clean
      one.
    * the three buckets NOT SUMMING to the denominator -> Undetermined. A
      numerator that does not close against its own denominator is this
      estate's own named defect.
    * the EXIT CODE disagreeing with the count -> Undetermined. The script's
      contract is exit 0 iff NO CONSULT is zero; two readings of one run that
      disagree make the authority UNRESOLVED, not the friendlier of the two.
    """
    path, state = authority(SUPPRESSION_CONSULT_INSTRUMENT)
    if state != "present":
        raise Undetermined(
            "the suppression-consult instrument %s is %s - and a 'no "
            "instrument' verdict has to be measured from THAT, by path, rather "
            "than inferred from another script's silence" % (path, state))
    code, out = _run([sys.executable, "-B", path, "."])
    read = {}
    for name, pattern in (
            ("paths", r"provider write paths\s*:\s*(\d+)"),
            ("in_function", r"a suppression consult in the function\s*:\s*(\d+)"),
            ("via_door", r"through the door, consult per verb\s*:\s*(\d+)"),
            ("no_consult",
             r"NO SUPPRESSION CONSULT ON THIS PATH\s*:\s*(\d+)")):
        hit = re.search(pattern, out)
        if not hit:
            raise Undetermined(
                "%s printed no %r line; an unparseable consult report is "
                "UNDETERMINED, because a missing field defaulting to zero is "
                "indistinguishable from a clean one" % (path, name))
        read[name] = int(hit.group(1))
    closes = read["in_function"] + read["via_door"] + read["no_consult"]
    if closes != read["paths"]:
        raise Undetermined(
            "%s reports %d + %d + %d = %d against a denominator of %d; a "
            "numerator that does not close against its own denominator is "
            "UNDETERMINED" % (path, read["in_function"], read["via_door"],
                              read["no_consult"], closes, read["paths"]))
    expected = 0 if read["no_consult"] == 0 else 1
    if code != expected:
        raise Undetermined(
            "%s exited %d while reporting %d path(s) with no consult; its own "
            "contract is exit 0 iff that count is zero, so the two readings of "
            "one run disagree and the authority is UNRESOLVED"
            % (path, code, read["no_consult"]))
    return (read["paths"], read["in_function"], read["via_door"],
            read["no_consult"])


def criterion_1():
    """A suppressed address cannot reach the transport BY ANY PATH."""
    ran, failed, _, _ = unittest_names(
        ["tests.test_a_suppressed_address_cannot_reach_a_provider"])
    paths, in_function, via_door, no_consult = suppression_consult_counts()
    #: The criterion is a CONJUNCTION and is scored as one: the gated paths
    #: must refuse AND no path may be unguarded. What the criterion MEANS is
    #: untouched here - only which file this row reads to answer the second
    #: half. Three outcomes, and the middle one is why MET is not simply
    #: `no_consult == 0`:
    #:
    #:   no_consult > 0                 -> NOT MET. A path carrying no consult
    #:     at all settles "by any path" negatively, and no resolution of the
    #:     via-the-door bucket can rescue it, so this verdict does not rest on
    #:     the analyzer's unresolved middle.
    #:   no_consult == 0, via_door == 0 -> MET, if the gated-path tests are
    #:     green. Every path carries a consult the analyzer can SEE.
    #:   no_consult == 0, via_door > 0  -> UNDETERMINED. Those sites pass the
    #:     door, but whether the door consults suppression depends on the
    #:     verb's `facing` flag, which the instrument reports and explicitly
    #:     does not resolve per call site. "Not disproven" is not "proven on
    #:     every path", and crediting it would be MET-WITH-CAVEAT, which this
    #:     module's docstring forbids.
    if failed:
        verdict = NOT_MET
    elif no_consult > 0:
        verdict = NOT_MET
    elif via_door > 0:
        raise Undetermined(
            "every one of the %d write paths carries a consult or the door, "
            "and the gated-path tests are green - but %d of them are credited "
            "ONLY 'via the door', where the consult runs or not according to "
            "the verb's facing= flag, which %s reports and does not resolve "
            "per call site. 'By any path' is therefore not established, and an "
            "unresolved path is UNKNOWN rather than the friendlier verdict"
            % (paths, via_door, SUPPRESSION_CONSULT_INSTRUMENT))
    else:
        verdict = MET
    return dict(
        verdict=verdict,
        authority=[(os.path.join(ROOT, "src", "suppression.py"),
                    authority(os.path.join(ROOT, "src", "suppression.py"))[1]),
                   (SUPPRESSION_CONSULT_INSTRUMENT, "present")],
        denominator="%d of %d provider write paths carry NO suppression "
                    "consult (%d consult in-function, %d via the door); the "
                    "gated-path tests ran %d with %d failing"
                    % (no_consult, paths, in_function, via_door, ran, len(failed)),
        condition="Both halves are measured in this tree at this SHA. The "
                  "NO-CONSULT count bounds the question in NEITHER direction, "
                  "and the instrument's own docstring calls it a floor. It "
                  "OVER-credits: a consult anywhere in the write's function, "
                  "or in a same-module helper that function calls, is counted "
                  "without proving it runs before the write on every branch. "
                  "It also UNDER-credits, measured by TASK-0239: a consult "
                  "reached through an indirection the AST rule cannot follow "
                  "- a callable held in a module-level dict and invoked "
                  "through a local name - is not credited, so a path reported "
                  "as unconsulted may in fact be consulted. So %d is the "
                  "analyzer's number and NOT MET here means the 'by any path' "
                  "half is NOT ESTABLISHED; the instrument names every one of "
                  "those paths by file and line, and they are checked "
                  "individually rather than trusted as a total. The module's "
                  "own tests are %s."
                  % (no_consult,
                     "green" if not failed else "RED: " + ", ".join(sorted(failed))),
        detail=sorted(failed))


#: Criterion 2's demonstration, pinned BY NAME. The first draft of this check
#: ran `test_a_provider_bounce_reaches_the_record` alongside, and read NOT MET
#: off 5 red names in it - but that module is BORN RED by its own docstring and
#: it asks a DIFFERENT question (whether a bounce EVENT ever arrives, which is
#: the ingestion gap). Charging another lane's deliberate born-red work to this
#: criterion is exactly the misattribution this instrument exists to stop.
#:
#: AND THE CLASS IN THESE TWO NAMES WAS `ARemovalRequestWritesARow`, WHICH HAS
#: NEVER EXISTED. Measured by TASK-0243 across every ref in this repository:
#: the string appears only in this file, introduced with the row itself at
#: dcd618d9c, and no `class ARemovalRequestWritesARow` is in tests/ on any
#: branch. The real class is `ARemovalRequestIsWrittenAndSurvivesARestart`.
#: Nothing noticed for the same reason the `"NOT ok"` detector went unnoticed:
#: the matcher compared only the LEAF name and threw the dotted path away, so a
#: pin that could not resolve behaved exactly like one that did. Corrected here
#: - the same two demonstrations, by the same leaf names, now pinned to the
#: class that actually contains them, so a class rename makes this row UNKNOWN
#: instead of silently pinning nothing.
REMOVAL_DEMONSTRATION = (
    "tests.test_a_suppressed_address_cannot_reach_a_provider"
    ".ARemovalRequestIsWrittenAndSurvivesARestart"
    ".test_an_attributed_removal_request_writes_a_suppression_row",
    "tests.test_a_suppressed_address_cannot_reach_a_provider"
    ".ARemovalRequestIsWrittenAndSurvivesARestart"
    ".test_an_unattributable_removal_request_still_writes_a_held_row",
)


def criterion_2():
    """A removal request results in a written suppression row, demonstrated."""
    ran, failed, out, _ = unittest_names(
        ["tests.test_a_suppressed_address_cannot_reach_a_provider"])
    #: Verify the demonstrating tests POSITIVELY - found running, by name, and
    #: with a terminal status read as a TOKEN. Absence proves nothing, which is
    #: this estate's own baseline rule.
    statuses = terminal_statuses(out)
    observed, missing = [], []
    for dotted in REMOVAL_DEMONSTRATION:
        if dotted not in statuses:
            missing.append(dotted.rsplit(".", 1)[-1])
            continue
        observed.append((dotted, statuses[dotted]))
    if missing:
        raise Undetermined(
            "the demonstrating test(s) %s were not found RUNNING with a "
            "terminal status in this module; a criterion whose demonstration "
            "cannot be located is UNDETERMINED, because absence proves nothing"
            % ", ".join(missing))
    agrees_with_the_failure_summary(statuses, failed, REMOVAL_DEMONSTRATION)
    shown = [status_label(dotted, token) for dotted, token in observed]
    #: THREE ways to score, so that repairing the dead NOT MET branch does not
    #: leave a row which only ever says no:
    #:
    #:   any demonstration FAIL or ERROR     -> NOT MET. The demonstration ran
    #:     and refuted the criterion. This is the branch TASK-0243 repaired;
    #:     before it, no state of the input could reach NOT MET.
    #:   every demonstration ok              -> MET. Demonstrated, in this tree,
    #:     at this SHA.
    #:   ran but neither passed nor failed   -> UNDETERMINED. A skipped,
    #:     expectedly-failing or unexpectedly-succeeding test did not execute
    #:     as the demonstration it is named for, so the population is not
    #:     established and UNKNOWN never becomes a pass.
    refuted = [(dotted, token) for dotted, token in observed
               if token in REFUTED]
    unclear = [(dotted, token) for dotted, token in observed
               if token not in PASSED and token not in REFUTED]
    if refuted:
        verdict = NOT_MET
    elif unclear:
        raise Undetermined(
            "the demonstration ran but neither passed nor failed: %s. A %s "
            "test did not execute as the thing it is named to demonstrate, so "
            "a written suppression row is NOT demonstrated and is not refuted "
            "either - that is UNDETERMINED, and UNKNOWN never becomes a pass"
            % (", ".join("%s (%s)" % (d.rsplit(".", 1)[-1], t)
                         for d, t in unclear),
               "/".join(INCONCLUSIVE)))
    else:
        verdict = MET
    return dict(
        verdict=verdict,
        authority=require_readable(os.path.join(ROOT, "src", "suppression.py")),
        denominator="%d tests in the module, %d failing; the demonstration is "
                    "%d named test(s), each verified running with its terminal "
                    "status: %s"
                    % (ran, len(failed), len(shown), ", ".join(shown)),
        condition="Scoped to the removal-request demonstration BY NAME. The "
                  "module's other %d failing name(s) are not charged here. "
                  "test_a_provider_bounce_reaches_the_record is deliberately "
                  "excluded: it is born red by its own docstring and asks "
                  "whether a bounce EVENT arrives, which is a different "
                  "question and belongs to criterion 1's territory. The "
                  "verdict is read from each demonstration's STATUS TOKEN and "
                  "cross-checked against unittest's own failure summary; it is "
                  "not read from the label above, which exists for the reader."
                  % len(failed)
                  + ("" if not refuted else "  REFUTED BY: " + ", ".join(
                      "%s (%s)" % (d.rsplit(".", 1)[-1], t)
                      for d, t in refuted)),
        detail=sorted(failed))


def criterion_3():
    """li1 renders a real connection note for every contact; RED if empty."""
    cfg = os.path.join(ROOT, "config", "linkedin", "productive-standard.json")
    require_readable(cfg)
    with open(cfg, "r", encoding="utf-8") as handle:
        raw = handle.read()
    occurrences = raw.count("{connection_note}")
    ran, failed, _, _ = unittest_names(
        ["tests.test_linkedin_note",
         "tests.test_a_linkedin_message_is_not_a_connection_request",
         "tests.test_the_empty_connection_note_is_an_operator_decision"])
    return dict(
        verdict=MET if (occurrences > 0 and not failed) else NOT_MET,
        authority=[(cfg, "present")],
        denominator="{connection_note} occurs %d times in the li1 config; "
                    "%d tests ran, %d failing" % (occurrences, ran, len(failed)),
        condition="Reads the config THIS TREE would send from. Zero "
                  "occurrences means li1 renders no note, which the criterion "
                  "calls RED regardless of what any test says."
                  + ("" if not failed else "  Failing: " + ", ".join(sorted(failed))),
        detail=sorted(failed))


def criterion_4():
    """Every template stage_s7_copy can render passes the ceiling and floor."""
    ran, failed, _, unexpected = unittest_names(
        ["tests.test_no_template_escapes_the_word_contract",
         "tests.test_every_template_is_inside_the_word_contract",
         "tests.test_the_word_ceiling_is_enforced_on_the_composed_body"])
    if unexpected:
        raise Undetermined(
            "%d unexpected successes - an expectedFailure that passed means "
            "the instrument and the code disagree about what is pinned, which "
            "is UNDETERMINED rather than either verdict" % unexpected)
    return dict(
        verdict=MET if not failed else NOT_MET,
        authority=[(os.path.join(ROOT, "scripts", "stage_s7_copy.py"), "present")],
        denominator="%d tests across the three modules, %d failing" % (ran, len(failed)),
        condition="Measures the TEMPLATES. It does not measure the ten "
                  "approved bodies, which are 81-89 words without the opt-out "
                  "sentence and 92-100 with it against a ceiling of 90 - no "
                  "test in this tree says so, and that caveat is the "
                  "operator's.",
        detail=sorted(failed))


def write_path_counts():
    code, out = _run([sys.executable, "-B", "scripts/write_path_denominator.py", "."])
    bypass = re.search(r"BYPASS the door\s*:\s*(\d+)", out)
    total = re.search(r"(\d+)\s+(?:provider )?write (?:path|site)s?", out)
    if not bypass:
        raise Undetermined("the denominator printed no 'BYPASS the door : N' "
                           "line; an unparseable denominator is UNDETERMINED")
    sites = None
    for pattern in (r"TOTAL\s*:\s*(\d+)", r"sites\s*:\s*(\d+)",
                    r"(\d+)\s+write sites", r"of\s+(\d+)\s+sites"):
        hit = re.search(pattern, out)
        if hit:
            sites = int(hit.group(1))
            break
    if sites is None:
        gated = re.search(r"through the door\s*:\s*(\d+)", out)
        if gated:
            sites = int(gated.group(1)) + int(bypass.group(1))
    if sites is None:
        raise Undetermined("the denominator printed a BYPASS count with no "
                           "total; a numerator without its denominator is "
                           "exactly the number this criterion exists to stop")
    return sites, int(bypass.group(1))


#: CRITERION 5'S PIN MODULES, SPLIT BY WHETHER A RED NAME IN THEM IS THIS
#: CRITERION'S OWN QUESTION. All three were already RUN and PRINTED by this
#: row; until TASK-0243 the verdict read NONE of them - `MET if bypass == 0`
#: - so the row could print MET with eight of the guards beside it red. That
#: is failure family 4: the printed evidence was not the evidence.
#:
#: The split is not cosmetic and it is the whole reason this is not simply
#: "charge every red":
#:
#:   CHARGED. `test_no_new_write_bypasses_the_door` derives the current bypass
#:     set from the same analyzer this row's count comes from and compares it,
#:     both directions, against the sanctioned baseline - which is this row's
#:     second declared authority and which, before this change, nothing in the
#:     row read. `test_a_non_facing_write_is_not_anonymous` is the sink refusal
#:     that makes an ungated write fail at all. Both are this criterion's own
#:     clause.
#:   NOT CHARGED. `test_the_eight_write_path_proposals_are_unapplied` is BORN
#:     RED by its own module docstring - "EVERY TEST IN THIS MODULE IS EXPECTED
#:     TO FAIL TODAY ... the thing that turns green when the operator orders
#:     that fix". Its six red names assert that eight proposals are UNAPPLIED,
#:     which is the operator's decision and a different question. Charging them
#:     would hold this criterion NOT MET until eight fixes are ordered, which
#:     would change what the criterion means - exactly the misattribution
#:     criterion 2 already refuses for test_a_provider_bounce_reaches_the_record.
#: AND TWO OF THE CHARGED MODULE'S OWN TESTS ARE EXCLUDED, WHICH IS NOT A
#: RELAXATION - IT IS THE DIFFERENCE BETWEEN A REPAIRED ROW AND THE SAME
#: DEFECT MIRRORED. `TheInstrumentIsNotDegenerate.test_it_classifies_both_ways`
#: asserts `verdicts["BYPASS"] > 0`, and its own failure message says what that
#: means: *"nothing was found bypassing the door - if that is genuinely true,
#: this module has done its job and should be retired, not relaxed."*
#: `test_the_baseline_is_not_empty` asserts the sanctioned baseline records at
#: least one bypass. BOTH ARE RED BY CONSTRUCTION IN EXACTLY THE WORLD THIS
#: CRITERION CALLS MET. Measured: with a door planted in all 26 bypassing
#: functions and the baseline regenerated, those two are the only reds left,
#: and charging them would make this row's MET cell UNREACHABLE for any state
#: of the tree - a row that can only ever print no, which is the defect under
#: repair with its sign flipped. They are instrument self-checks on the
#: analyzer, not readings of the criterion, so they are named and excluded
#: rather than silently dropped.
CHARGED_PIN_SCOPES = (
    "tests.test_a_non_facing_write_is_not_anonymous",
    "tests.test_no_new_write_bypasses_the_door.NoNewWriteBypassesTheDoor",
)
UNCHARGED_PIN_SCOPES = (
    #: red by construction when the criterion is satisfied - see above
    "tests.test_no_new_write_bypasses_the_door.NoNewWriteBypassesTheDoor"
    ".test_the_baseline_is_not_empty",
    "tests.test_no_new_write_bypasses_the_door.TheInstrumentIsNotDegenerate",
    #: born red by its own module docstring, awaiting an operator order
    "tests.test_the_eight_write_path_proposals_are_unapplied",
)
PIN_MODULES = (
    "tests.test_no_new_write_bypasses_the_door",
    "tests.test_the_eight_write_path_proposals_are_unapplied",
    "tests.test_a_non_facing_write_is_not_anonymous",
)


def is_charged(name):
    """Does a red in this test count against criterion 5? Exclusion wins."""
    if name.startswith(tuple(s + "." for s in UNCHARGED_PIN_SCOPES)) \
            or name in UNCHARGED_PIN_SCOPES:
        return False
    return name.startswith(tuple(s + "." for s in CHARGED_PIN_SCOPES))


def criterion_5():
    """The count of write paths that bypass the gate is zero, against a real
    denominator."""
    sites, bypass = write_path_counts()
    ran, failed, out, _ = unittest_names(PIN_MODULES)
    statuses = terminal_statuses(out)
    charged = dict((name, token) for name, token in statuses.items()
                   if is_charged(name))
    #: The vacuous-pass guard, which the charged module applies to its own
    #: analyzer and this row now applies to the module: "no red in it" read off
    #: a scope that contributed no tests is a clean bill of health from an
    #: instrument that watched nothing.
    for scope in CHARGED_PIN_SCOPES:
        if not any(name.startswith(scope + ".") for name in charged):
            raise Undetermined(
                "no charged test from %s was found running with a terminal "
                "status, so 'no red name in it' would be read off a scope that "
                "did not run - a clean verdict from an instrument watching "
                "nothing, which is UNDETERMINED" % scope)
    red = agrees_with_the_failure_summary(statuses, failed, charged)
    unclear = sorted(name for name, token in charged.items()
                     if token not in PASSED and token not in REFUTED)
    uncharged_red = sorted(name for name in failed if not is_charged(name))
    #: Three ways, and NOT MET stays where the criterion puts it - on the count.
    #: A red charged guard cannot make a zero count positive, so it does not
    #: produce NOT MET; what it does is leave the count and the authority that
    #: sanctions it disagreeing, and two readings of one question that disagree
    #: make the authority UNRESOLVED. That is this file's own rule for
    #: suppression_consult_counts, applied to the row that reads it.
    if bypass > 0:
        verdict = NOT_MET
    elif red:
        raise Undetermined(
            "the analyzer counts 0 of %d write sites bypassing the door while "
            "%d of this criterion's own charged guard(s) are RED: %s. Two "
            "readings of one question that disagree make the authority "
            "UNRESOLVED, not the friendlier of the two - and the guards are "
            "the reading that names the sites"
            % (sites, len(red), ", ".join(red)))
    elif unclear:
        raise Undetermined(
            "the analyzer counts 0 of %d write sites bypassing the door, but "
            "%d charged guard(s) neither passed nor failed: %s. A suspended "
            "guard is not a green one, so the count is not corroborated and "
            "that is UNDETERMINED" % (sites, len(unclear), ", ".join(unclear)))
    else:
        verdict = MET
    return dict(
        verdict=verdict,
        authority=[(os.path.join(ROOT, "scripts", "write_path_denominator.py"), "present"),
                   (os.path.join(ROOT, "scripts", "known_write_bypasses.json"),
                    authority(os.path.join(ROOT, "scripts", "known_write_bypasses.json"))[1])],
        denominator="%d BYPASS of %d write sites; pin modules ran %d with %d failing"
                    % (bypass, sites, ran, len(failed)),
        condition="The criterion asks for LITERAL ZERO, so any positive count "
                  "is NOT MET. The analyzer's same-function rule errs in BOTH "
                  "directions - over-crediting a helper called only from a "
                  "gated function, and under-crediting a callback handed to a "
                  "sanctioned holder - so %d is the analyzer's number, not a "
                  "floor and not a ceiling. Of the %d failing pin name(s) "
                  "printed below, %d are CHARGED to this verdict and %d are "
                  "NOT, and the split is stated rather than left for a reader "
                  "to assume: charged = %s, which are this criterion's own "
                  "clause and the only reading that consults the sanctioned "
                  "baseline; not charged = %s, which are a born-red proposal "
                  "module awaiting an operator order plus two instrument "
                  "self-checks that are RED BY CONSTRUCTION whenever the "
                  "bypass count reaches zero."
                  % (bypass, len(failed), len(red), len(uncharged_red),
                     ", ".join(s.split(".", 2)[-1] for s in CHARGED_PIN_SCOPES),
                     ", ".join(s.split(".", 2)[-1] for s in UNCHARGED_PIN_SCOPES))
                  + ("" if not red else "  CHARGED AND RED: " + ", ".join(red))
                  + ("" if not uncharged_red else "  NOT CHARGED: "
                     + ", ".join(n.rsplit(".", 1)[-1] for n in uncharged_red)),
        detail=sorted(failed))


def _tally_export(path):
    """Tally one estate export with csv.DictReader over the WHOLE file.

    Not line by line: the `Signature` column carries HTML that may contain an
    embedded newline, and a per-line split silently mis-slices those rows. The
    first draft of this check did exactly that.
    """
    import csv
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise Undetermined("%s has zero data rows - an empty authority is "
                           "UNKNOWN, never a clean bill of health" % path)
    need = {"Status", "Emails Sent", "Bounces", "Opens"}
    missing = need - set(rows[0].keys())
    if missing:
        raise Undetermined("%s lacks the column(s) %s - a health verdict with "
                           "no health column is UNDETERMINED"
                           % (path, ", ".join(sorted(missing))))

    def total(key):
        got = 0
        for row in rows:
            raw = (row.get(key) or "").strip()
            if not raw:
                continue
            try:
                got += int(float(raw))
            except ValueError:
                raise Undetermined("%s has a non-numeric %s (%r); a health "
                                   "number that cannot be parsed is "
                                   "UNDETERMINED" % (path, key, raw))
        return got

    sent, bounces, opens = total("Emails Sent"), total("Bounces"), total("Opens")
    connected = sum(1 for r in rows
                    if (r.get("Status") or "").strip().lower() == "connected")
    #: BOUNCES IS A COUNT, NOT A PERCENTAGE. The rate is bounces over SENDS.
    #: The first draft of this check divided by the ROW COUNT and reported
    #: 9.69% where the real figure is 1.01% - a tenfold overstatement that
    #: would have failed this criterion for the wrong reason.
    rate = (100.0 * bounces / sent) if sent else None
    return dict(path=path, rows=len(rows), connected=connected, sent=sent,
                bounces=bounces, opens=opens, rate=rate,
                digest=sha256(path))


def criterion_6():
    """Mailbox health, answered from the estate export.

    TWO exports exist, (a) and (b), both hash-pinned in the cohort decision,
    and they DISAGREE on the clause the criterion states: (a) reads 181 of 181
    Connected, (b) reads 179. Where two pinned authorities give two verdicts
    for one criterion, the authority is unresolved and the verdict is UNKNOWN -
    not the friendlier of the two.
    """
    primary, primary_state = authority(ESTATE_EXPORT)
    require_readable(primary)
    sibling = os.path.join(os.path.dirname(primary),
                           os.path.basename(primary).replace(".csv", "b.csv"))
    tallies = [_tally_export(primary)]
    read = [(primary, primary_state)]
    if os.path.exists(sibling):
        tallies.append(_tally_export(sibling))
        read.append((sibling, "present"))

    verdicts = []
    for tally in tallies:
        if tally["rate"] is None:
            raise Undetermined("%s records zero sends, so no bounce rate "
                               "exists to judge health by" % tally["path"])
        verdicts.append(MET if (tally["connected"] == tally["rows"]
                                and tally["rate"] < 3.0) else NOT_MET)

    verdict = verdicts[0] if len(set(verdicts)) == 1 else UNKNOWN
    shape = "; ".join(
        "%s: %d mailboxes, %d connected, %d sent, %d bounces = %.2f%%, "
        "opens %d" % (os.path.basename(t["path"]), t["rows"], t["connected"],
                      t["sent"], t["bounces"], t["rate"], t["opens"])
        for t in tallies)
    if verdict == UNKNOWN:
        raise Undetermined(
            "the two pinned exports disagree on this criterion - %s. The "
            "criterion's own wording is 'all 181 mailboxes read Connected', "
            "which (a) satisfies and (b) does not, and both are hash-pinned "
            "in the cohort decision. Two authorities, two verdicts, so the "
            "authority is UNRESOLVED and that is UNKNOWN, not the friendlier "
            "of the two." % shape)
    return dict(
        verdict=verdict,
        authority=read,
        denominator=shape,
        condition="Holds for the exports as captured 2026-10-15. A SNAPSHOT of "
                  "a shared estate, not a live read; the 181-vs-225 mailbox "
                  "reconciliation is still unmeasured, so this answers health "
                  "for the rows the exports contain and says nothing about "
                  "rows they omit. Opens reads 0 across every row, so no "
                  "metric may be built on open tracking.",
        detail=[])


def criterion_7():
    """One owner across the attached pool; every body signed by that owner."""
    ran, failed, _, unexpected = unittest_names(
        ["tests.test_every_body_is_signed_by_the_pools_owner",
         "tests.test_the_provider_does_the_signing"])
    #: THE MECHANISM BEING GREEN IS NOT THE FACT BEING TRUE, and this check
    #: originally read MET off green tests while its own condition column said
    #: so - which is the MET-WITH-CAVEAT defect this instrument's docstring
    #: forbids, committed by the instrument itself. The criterion asserts a
    #: FACT about the attached pool: one owner across it. That fact is a
    #: provider question, and the boundary forbids a provider call, so there is
    #: NO INSTRUMENT for it in this run. UNKNOWN, with the tests reported as
    #: the evidence they are.
    if failed or unexpected:
        return dict(
            verdict=NOT_MET,
            authority=[(os.path.join(ROOT, "src", "sendersignature.py"), "present")],
            denominator="%d tests, %d failing, %d unexpected successes"
                        % (ran, len(failed), unexpected),
            condition="The signing MECHANISM is red, which settles the "
                      "criterion negatively without needing the pool fact.",
            detail=sorted(failed))
    raise Undetermined(
        "the signing mechanism is green (%d tests, 0 failing), but the "
        "criterion asserts a FACT about the attached pool - one owner across "
        "it - and NO INSTRUMENT in this tree establishes that fact. It needs a "
        "provider read of the pool's senders, which this run's boundary "
        "forbids. A green mechanism is not the fact, so this is UNKNOWN rather "
        "than MET." % ran)


def criterion_8():
    """The review file is approved by the owner."""
    sheet, sheet_state = authority(APPROVAL_SHEET)
    decision, decision_state = authority(APPROVAL_DECISION)
    require_readable(sheet, decision)
    digest = sha256(sheet)
    size = os.path.getsize(sheet)
    with open(decision, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    pinned = re.findall(r"\b([0-9a-f]{64})\b", text)
    if not pinned:
        raise Undetermined(
            "%s pins no sha256 for the sheet, so the sheet cannot be checked "
            "against the decision that approves it" % decision)
    matches = digest in pinned
    return dict(
        verdict=MET if matches else NOT_MET,
        authority=[(sheet, sheet_state), (decision, decision_state)],
        denominator="sheet sha256 %s..%s, %d bytes; decision pins %d digest(s)"
                    % (digest[:8], digest[-8:], size, len(pinned)),
        condition="A byte-match proves the sheet is the one approved. It does "
                  "NOT prove the approval binds a mailbox or a signature, and "
                  "the estate's own rule is that an approval which binds "
                  "neither went stale. That caveat is the operator's and this "
                  "row does not resolve it.",
        detail=[])


def criterion_9():
    """A kill switch the operator can operate alone, named and tested - and
    its verdict must come from the SHIPPED STOP_SENDING_PATH default."""
    brake = os.path.join(ROOT, "src", "haltfile.py")
    path, state = authority(brake)
    if state != "present":
        raise Undetermined(
            "src/haltfile.py is %s in this tree - the only code that reads the "
            "STOP-SENDING file. With no reader, creating the brake file stops "
            "nothing, so the criterion is UNDETERMINED here" % state)
    ran, failed, _, _ = unittest_names([
        "tests.test_the_shipped_brake_constant_is_the_brake_itself",
        "tests.test_bisonfactory_consults_the_stop_sending_brake_before_each_transport",
        "tests.test_no_path_reaches_a_transport_without_passing_the_stop_sending_brake",
        "tests.test_the_operator_can_pull_the_stop_sending_brake_alone",
        "tests.test_the_stop_sending_brake_asks_nobody_for_permission",
        "tests.test_the_stop_sending_brake_fails_closed_when_it_cannot_be_read",
        "tests.test_the_stop_sending_brake_refuses_the_transport_immediately",
        "tests.test_the_stop_sending_brake_stops_the_resume_scripts",
    ])
    #: The default must be EXERCISED, not patched. pilotcaps/0225 added the
    #: identity assertion; without it, 36 tests passed while the constant
    #: pointed at a sibling file. Verified here by import rather than assumed.
    sys.path.insert(0, ROOT)
    for stale in [m for m in sys.modules if m.startswith("src.haltfile")]:
        del sys.modules[stale]
    from src import haltfile
    shipped = haltfile.STOP_SENDING_PATH
    pin = os.path.join(ROOT, "tests",
                       "test_the_shipped_brake_constant_is_the_brake_itself.py")
    if not os.path.exists(pin):
        raise Undetermined(
            "no test pins the shipped constant's identity, so a brake pointed "
            "at a sibling file would pass - which is the defect pilotcaps/0225 "
            "measured. UNDETERMINED until that pin exists")
    home = os.path.dirname(shipped)
    if not os.path.isdir(home):
        raise Undetermined("the brake's home %s is not a readable directory, "
                           "so the brake state is UNKNOWN" % home)
    pulled = os.path.lexists(shipped)
    return dict(
        verdict=MET if not failed else NOT_MET,
        authority=[(path, state), (shipped, "pulled" if pulled else "released"),
                   (pin, "present")],
        denominator="%d tests across the eight brake modules, %d failing; "
                    "shipped constant exercised and pinned by identity" % (ran, len(failed)),
        condition="Measured from the SHIPPED STOP_SENDING_PATH default, not a "
                  "patched constant - which is the whole reason 9 once read MET "
                  "while the default was never exercised. Holds while the brake "
                  "is %s. The brake stops a STARTING action and cannot end a "
                  "campaign already running."
                  % ("RELEASED (file absent)" if not pulled else "PULLED"),
        detail=sorted(failed))


CRITERIA = [
    (1, "a suppressed address cannot reach the transport by any path", criterion_1),
    (2, "a removal request writes a suppression row, demonstrated", criterion_2),
    (3, "li1 renders a real connection note for every contact; RED if empty", criterion_3),
    (4, "every template passes the ceiling and the floor, RED on escape", criterion_4),
    (5, "zero write paths bypass the gate, against a real denominator", criterion_5),
    (6, "mailbox health, answered from the estate export", criterion_6),
    (7, "one owner across the attached pool, bodies signed by that owner", criterion_7),
    (8, "the review file is approved by the owner", criterion_8),
    (9, "a kill switch the operator can operate alone, named and tested", criterion_9),
]


def conjoin(verdicts):
    """The conjunction. One UNKNOWN makes it UNKNOWN - not false, and
    certainly not true."""
    if any(v == UNKNOWN for v in verdicts):
        return UNKNOWN
    if len(verdicts) != len(CRITERIA):
        return UNKNOWN
    return MET if all(v == MET for v in verdicts) else NOT_MET


def head_carries_this_instrument():
    """The SHA is DERIVED and verified to carry this file's exact bytes."""
    code, sha = _run(["git", "rev-parse", "HEAD"], timeout=60)
    if code != 0:
        return None, "git rev-parse HEAD failed: %s" % sha.strip()
    sha = sha.strip()
    code, committed = _run(
        ["git", "rev-parse", "HEAD:scripts/exit_nine.py"], timeout=60)
    if code != 0:
        return sha, ("HEAD does not carry scripts/exit_nine.py: every verdict "
                     "is UNKNOWN, because a verdict measured against "
                     "uncommitted bytes is not a measurement of this SHA")
    code, ondisk = _run(["git", "hash-object", SELF], timeout=60)
    if code != 0:
        return sha, "git hash-object refused to read this file: %s" % ondisk.strip()
    if ondisk.strip() != committed.strip():
        return sha, ("this file on disk (%s) differs from HEAD (%s): every "
                     "verdict is UNKNOWN"
                     % (ondisk.strip()[:12], committed.strip()[:12]))
    return sha, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test-conjunction", action="store_true",
                        help="C3: feed nine synthetic MET verdicts and confirm "
                             "the conjunction can print MET at all")
    parser.add_argument("--only", type=int, action="append",
                        help="evaluate only these criteria; the conjunction is "
                             "then UNKNOWN by rule, because a partial set is "
                             "not a statement about all nine")
    args = parser.parse_args()

    if args.self_test_conjunction:
        print("C3 - can the conjunction print MET at all?")
        for label, synthetic in [
                ("nine MET", [MET] * 9),
                ("eight MET + one NOT MET", [MET] * 8 + [NOT_MET]),
                ("eight MET + one UNKNOWN", [MET] * 8 + [UNKNOWN]),
                ("one UNKNOWN + one NOT MET", [MET] * 7 + [UNKNOWN, NOT_MET]),
                ("eight only (partial set)", [MET] * 8)]:
            print("  %-28s -> %s" % (label, conjoin(synthetic)))
        return 0

    started = datetime.datetime.now(datetime.timezone.utc)
    sha, sha_problem = head_carries_this_instrument()

    rows = []
    wanted = [c for c in CRITERIA if not args.only or c[0] in args.only]
    for number, text, check in wanted:
        if sha_problem:
            rows.append(dict(number=number, text=text, verdict=UNKNOWN,
                             authority=[("(SHA unverified)", "unreadable")],
                             denominator="-", condition=sha_problem, detail=[]))
            continue
        try:
            got = check()
            got.update(number=number, text=text)
        except Undetermined as undetermined:
            got = dict(number=number, text=text, verdict=UNKNOWN,
                       authority=[("(undetermined)", "-")], denominator="-",
                       condition=str(undetermined), detail=[])
        except Exception as raised:   # fail closed on anything unanticipated
            got = dict(number=number, text=text, verdict=UNKNOWN,
                       authority=[("(raised)", "-")], denominator="-",
                       condition="the check raised %s: %s - an unanticipated "
                                 "failure is UNKNOWN, never a pass"
                                 % (type(raised).__name__, raised), detail=[])
        rows.append(got)

    finished = datetime.datetime.now(datetime.timezone.utc)
    verdicts = [r["verdict"] for r in rows]
    conjunction = UNKNOWN if args.only else conjoin(verdicts)

    if args.json:
        print(json.dumps(dict(conjunction=conjunction, sha=sha,
                              started=started.isoformat(),
                              finished=finished.isoformat(), rows=rows),
                         indent=2))
    else:
        print("=" * 78)
        print("THE CONJUNCTION: all nine exit criteria MET at once?   %s"
              % conjunction)
        print("=" * 78)
        print("tree        %s" % ROOT)
        print("SHA         %s  (derived from HEAD, %s)"
              % (sha, "instrument bytes verified against HEAD" if not sha_problem
                 else "UNVERIFIED: " + sha_problem))
        print("run clock   %s -> %s  (%.1fs)"
              % (started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 (finished - started).total_seconds()))
        if args.only:
            print("PARTIAL RUN - only %s evaluated, so the conjunction is "
                  "UNKNOWN by rule." % sorted(args.only))
        print()
        for row in rows:
            print("-" * 78)
            print("%d. %s" % (row["number"], row["text"]))
            print("   VERDICT      %s" % row["verdict"])
            for path, state in row["authority"]:
                print("   authority    %s  [%s]" % (path, state))
            print("   denominator  %s" % row["denominator"])
            print("   condition    %s" % row["condition"])
            if row["detail"]:
                for name in row["detail"][:6]:
                    print("      red: %s" % name)
                if len(row["detail"]) > 6:
                    print("      ... and %d more" % (len(row["detail"]) - 6))
        print("-" * 78)
        tally = {v: verdicts.count(v) for v in (MET, NOT_MET, UNKNOWN)}
        print("tally  MET %d   NOT MET %d   UNKNOWN %d"
              % (tally[MET], tally[NOT_MET], tally[UNKNOWN]))
        blind = [r["number"] for r in rows if r["verdict"] == UNKNOWN]
        if blind:
            print("UNDETERMINED: %s - UNKNOWN is not a pass, exiting non-zero."
                  % ", ".join(str(b) for b in blind))

    return {MET: 0, NOT_MET: 1, UNKNOWN: 2}[conjunction]


if __name__ == "__main__":
    sys.exit(main())
