#!/usr/bin/env python3
"""TASK 0235, SECOND OBSERVER: the nine CANARY-01 exit criteria, re-evaluated
with checks written here rather than the ones `scripts/exit_nine.py` wrote.

This is not a refactor of that instrument and it does not import it. It exists
to answer one question the first observer could not answer about itself: **can
the conjunction ever print MET?**

## The structural difference, and it is the whole point

`exit_nine.criterion_1` returns `verdict=UNKNOWN` as a LITERAL, and
`exit_nine.criterion_7` RAISES `Undetermined` on its green path. Neither
consults an authority that could change the answer, so no state of any file, in
any tree, at any SHA, can make those two rows MET - and therefore the
instrument's top line can only ever print UNKNOWN or, if a check regresses,
NOT MET. That is correct fail-closed behaviour and it is also an instrument
whose all-clear is unreachable, which is a thing a reader cannot see from its
output.

Here, a criterion with no instrument is modelled as a criterion whose AUTHORITY
IS ABSENT. The missing instrument becomes a named absolute path that is not
there, the verdict is UNKNOWN for the same fail-closed reason, and the all-MET
branch is reachable the moment the authority exists. Same verdict today; a
different thing to read.

## Four states, and three of them are not a pass

    MET       the authority was read and its predicate holds
    NOT MET   the authority was read and its predicate does not hold
    UNKNOWN   an authority is absent or unreadable - named by absolute path
    STALE     an authority's sha256 differs from the one pinned for it, so NO
              verdict is reported for that criterion at all

STALE is separate from UNKNOWN on purpose. An unreadable authority is a thing
we failed to read. A changed authority is a thing we read successfully and must
not report on, because the ground moved under whoever pinned it.

## The runner seam

Six of the nine criteria rest partly on a named-test run. In a real run those
tests are executed. With `OBS2_RESULTS` set to a JSON file, the results are
read from it instead - that is how the C1 fixture synthesises a state in which
all nine are satisfied, which cannot be done by editing files alone. The seam
is ONLY the test results. Authority reading, hashing, staleness, the UNKNOWN
rule and the conjunction are one code path in both modes, and those are what
C1 through C4 test.

## Exit codes

    0   conjunction MET
    1   conjunction NOT MET
    2   conjunction UNKNOWN or STALE
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys

MET = "MET"
NOT_MET = "NOT MET"
UNKNOWN = "UNKNOWN"
STALE = "STALE"

TEST_TIMEOUT = 900


class Unreadable(Exception):
    """An authority could not be read. Becomes UNKNOWN, never a pass."""


class Stale(Exception):
    """An authority's bytes differ from its pin. No verdict is reported."""


# ------------------------------------------------------------------ plumbing

def read_authority(path, pins):
    """Bytes of `path`, or raise. Hashes BEFORE the predicate sees anything."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise Unreadable("absent: %s" % path)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as blind:
        raise Unreadable("unreadable (%s): %s" % (blind.strerror or blind, path))
    digest = hashlib.sha256(raw).hexdigest()
    pinned = (pins or {}).get(os.path.basename(path))
    if pinned and pinned != digest:
        raise Stale("%s: pinned %s, read %s" % (path, pinned[:16], digest[:16]))
    return raw, digest


def run_tests(tree, modules, results):
    """(ran, failing-name-set). Name-sets, never counts - the estate's rule."""
    key = "|".join(sorted(modules))
    if results is not None:
        if key not in results:
            raise Unreadable("the results file has no entry for %s" % key)
        got = results[key]
        return int(got["ran"]), set(got.get("failing") or ())
    argv = [sys.executable, "-B", "-m", "unittest", "-v"] + list(modules)
    try:
        proc = subprocess.run(argv, cwd=tree, capture_output=True, text=True,
                              timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Unreadable("the test run timed out after %ds: %s"
                         % (TEST_TIMEOUT, key))
    out = proc.stdout + proc.stderr
    ran = re.search(r"^Ran (\d+) tests?", out, re.M)
    if not ran:
        raise Unreadable("unittest printed no 'Ran N tests' line for %s" % key)
    failing = set()
    for line in out.splitlines():
        hit = re.match(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", line)
        if hit:
            failing.add(hit.group(3))
    return int(ran.group(1)), failing


# -------------------------------------------------------------------- the nine
#: Each criterion returns (verdict, denominator-string). It may read only the
#: authorities declared beside it - that is what makes C3 and C4 meaningful.

def c1(ctx):
    """A suppressed address cannot reach the transport BY ANY PATH.

    TWO halves. The gated-path half runs. The 'by any path' half needs a
    per-write-path suppression-consult census, and in the real tree that file
    DOES NOT EXIST - so this reads UNKNOWN naming the path, rather than
    hardcoding UNKNOWN with no path to name.
    """
    ran, failing = run_tests(ctx["tree"], CONSULT_MODULES, ctx["results"])
    raw, _ = read_authority(ctx["census"], ctx["pins"])
    census = json.loads(raw.decode("utf-8"))
    sites, consulting = int(census["write_sites"]), int(census["consulting"])
    verdict = MET if (consulting == sites and not failing) else NOT_MET
    return verdict, ("%d of %d write sites consult suppression; gated-path "
                     "tests ran %d, %d failing" % (consulting, sites, ran, len(failing)))


def c2(ctx):
    """A removal request results in a written suppression row, demonstrated."""
    read_authority(os.path.join(ctx["tree"], "src", "suppression.py"), ctx["pins"])
    ran, failing = run_tests(ctx["tree"], DEMO_MODULES, ctx["results"])
    shown = [n for n in DEMONSTRATION if n not in failing]
    verdict = MET if len(shown) == len(DEMONSTRATION) else NOT_MET
    return verdict, ("%d of %d named demonstrating tests pass; the module ran "
                     "%d with %d failing" % (len(shown), len(DEMONSTRATION), ran, len(failing)))


def c3(ctx):
    """li1 renders a real connection note for every contact; RED if empty.

    READS THE NODE THE PROVIDER SENDS FROM, and this is where this harness and
    `exit_nine` differ in method rather than in verdict. `exit_nine.criterion_3`
    counts occurrences of the literal `{connection_note}` in the raw config
    text. That placeholder does not occur in this config at ALL - the note is
    `payload.messages` plus `payload.fallbackMessage` on the CONNECTION_REQUEST
    node of the HeyReach graph - so its count is 0 whatever the note says, and
    measured here with a real note planted it stayed 0. Same verdict today,
    for a reason that is not the reason.
    """
    raw, _ = read_authority(os.path.join(ctx["tree"], "config", "linkedin",
                                         "productive-standard.json"), ctx["pins"])
    cfg = json.loads(raw.decode("utf-8"))
    notes = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("nodeType") == "CONNECTION_REQUEST":
                payload = node.get("payload") or {}
                notes.extend(payload.get("messages") or [])
                if "fallbackMessage" in payload:
                    notes.append(payload["fallbackMessage"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(cfg)
    if not notes:
        raise Unreadable("no CONNECTION_REQUEST node carries a note field in "
                         "%s, so there is nothing to judge RED or not"
                         % os.path.join(ctx["tree"], "config", "linkedin",
                                        "productive-standard.json"))
    rendered = [n for n in notes if str(n).strip()]
    ran, failing = run_tests(ctx["tree"], NOTE_MODULES, ctx["results"])
    verdict = MET if (len(rendered) == len(notes) and not failing) else NOT_MET
    return verdict, ("%d of %d CONNECTION_REQUEST note slots carry text; %d "
                     "tests ran, %d failing"
                     % (len(rendered), len(notes), ran, len(failing)))


def c4(ctx):
    """Every template passes the ceiling and the floor, RED on escape."""
    read_authority(os.path.join(ctx["tree"], "scripts", "stage_s7_copy.py"), ctx["pins"])
    ran, failing = run_tests(ctx["tree"], TEMPLATE_MODULES, ctx["results"])
    return (MET if not failing else NOT_MET,
            "%d of %d template tests pass" % (ran - len(failing), ran))


def door_counts(ctx):
    """(write sites, bypassing sites).

    Criterion 5's instrument EXISTS, so it is run rather than read from a
    census - unlike criterion 1's consult half, which has none. In fixture
    mode the census stands in, which is the only way to synthesise a zero.
    """
    if os.path.exists(ctx["census"]):
        raw, _ = read_authority(ctx["census"], ctx["pins"])
        census = json.loads(raw.decode("utf-8"))
        return int(census["write_sites"]), int(census["bypass"])
    proc = subprocess.run([sys.executable, "-B",
                           "scripts/write_path_denominator.py", "."],
                          cwd=ctx["tree"], capture_output=True, text=True,
                          timeout=TEST_TIMEOUT)
    out = proc.stdout + proc.stderr
    bypass = re.search(r"BYPASS the door\s*:\s*(\d+)", out)
    gated = re.search(r"through the door\s*:\s*(\d+)", out)
    if not bypass or not gated:
        raise Unreadable("scripts/write_path_denominator.py printed no "
                         "'BYPASS the door : N' and 'through the door : N' pair")
    return int(gated.group(1)) + int(bypass.group(1)), int(bypass.group(1))


def c5(ctx):
    """Zero write paths bypass the gate, against a real denominator."""
    read_authority(os.path.join(ctx["tree"], "scripts",
                                "write_path_denominator.py"), ctx["pins"])
    sites, bypass = door_counts(ctx)
    ran, failing = run_tests(ctx["tree"], PIN_MODULES, ctx["results"])
    return (MET if bypass == 0 else NOT_MET,
            "%d BYPASS of %d write sites; pin modules ran %d with %d failing"
            % (bypass, sites, ran, len(failing)))


def _tally(raw, path):
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows:
        raise Unreadable("%s has zero data rows" % path)

    def total(key):
        return sum(int(float(r[key])) for r in rows if (r.get(key) or "").strip())
    sent, bounces = total("Emails Sent"), total("Bounces")
    connected = sum(1 for r in rows
                    if (r.get("Status") or "").strip().lower() == "connected")
    if not sent:
        raise Unreadable("%s records zero sends, so no bounce rate exists" % path)
    return dict(rows=len(rows), connected=connected, sent=sent, bounces=bounces,
                opens=total("Opens"), rate=100.0 * bounces / sent)


def c6(ctx):
    """Mailbox health, answered from the estate export.

    NUMERATOR  sum of column `Bounces`   (one row = one MAILBOX, so this is a
                                          count of bounced sends, not of rows)
    DENOMINATOR sum of column `Emails Sent` (likewise a count of SENDS)
    The rate is sends-over-sends. Dividing by the ROW count would be mailboxes
    into sends, which is the tenfold error the first observer caught in itself.
    """
    tallies = []
    for path in ctx["exports"]:
        raw, _ = read_authority(path, ctx["pins"])
        tallies.append((path, _tally(raw, path)))
    shape = "; ".join(
        "%s: bounces %d / sent %d = %.2f%%, connected %d of %d rows, opens %d"
        % (os.path.basename(p), t["bounces"], t["sent"], t["rate"],
           t["connected"], t["rows"], t["opens"]) for p, t in tallies)
    verdicts = {MET if (t["connected"] == t["rows"] and t["rate"] < 3.0)
                else NOT_MET for _, t in tallies}
    if len(verdicts) != 1:
        raise Unreadable("the %d pinned exports give %s for one criterion, so "
                         "the authority is unresolved: %s"
                         % (len(tallies), sorted(verdicts), shape))
    return verdicts.pop(), shape


def c7(ctx):
    """One owner across the attached pool; every body signed by that owner.

    The MECHANISM's tests run. The FACT is a property of the attached pool and
    its authority is a pool readback, which does not exist in this tree. Named
    by path and UNKNOWN. TASK 0231 owns the offline route to this fact; nothing
    here attempts it.
    """
    read_authority(os.path.join(ctx["tree"], "src", "sendersignature.py"), ctx["pins"])
    ran, failing = run_tests(ctx["tree"], SIGNING_MODULES, ctx["results"])
    raw, _ = read_authority(ctx["pool"], ctx["pins"])
    pool = json.loads(raw.decode("utf-8"))
    owners = {str(m.get("owner") or "").strip() for m in pool["mailboxes"]}
    owners.discard("")
    verdict = MET if (len(owners) == 1 and not failing) else NOT_MET
    return verdict, ("%d distinct owner(s) across %d pool mailboxes; signing "
                     "mechanism ran %d with %d failing"
                     % (len(owners), len(pool["mailboxes"]), ran, len(failing)))


def c8(ctx):
    """The review file is approved by the owner."""
    sheet_raw, sheet_digest = read_authority(ctx["sheet"], ctx["pins"])
    dec_raw, _ = read_authority(ctx["decision"], ctx["pins"])
    pinned = re.findall(r"\b([0-9a-f]{64})\b", dec_raw.decode("utf-8", "replace"))
    if not pinned:
        raise Unreadable("%s pins no sha256 for the sheet" % ctx["decision"])
    approvals = len(re.findall(r"^- verdict: APPROVED", sheet_raw.decode("utf-8", "replace"), re.M))
    rows = len(re.findall(r"^- verdict:", sheet_raw.decode("utf-8", "replace"), re.M))
    return (MET if sheet_digest in pinned and approvals else NOT_MET,
            "sheet sha256 %s.. matches %d of the %d digest(s) the decision "
            "pins; %d of %d rows carry `- verdict: APPROVED`"
            % (sheet_digest[:8], 1 if sheet_digest in pinned else 0,
               len(pinned), approvals, rows))


def c9(ctx):
    """A kill switch the operator can operate alone, named and tested."""
    read_authority(os.path.join(ctx["tree"], "src", "haltfile.py"), ctx["pins"])
    read_authority(os.path.join(
        ctx["tree"], "tests",
        "test_the_shipped_brake_constant_is_the_brake_itself.py"), ctx["pins"])
    ran, failing = run_tests(ctx["tree"], BRAKE_MODULES, ctx["results"])
    return (MET if not failing else NOT_MET,
            "%d of %d brake tests pass%s"
            % (ran - len(failing), ran,
               "" if not failing else "; red: " + ", ".join(sorted(failing)[:3])))


CONSULT_MODULES = ("tests.test_a_suppressed_address_cannot_reach_a_provider",)
DEMO_MODULES = CONSULT_MODULES
DEMONSTRATION = (
    "tests.test_a_suppressed_address_cannot_reach_a_provider"
    ".ARemovalRequestWritesARow.test_an_attributed_removal_request_writes_a_suppression_row",
    "tests.test_a_suppressed_address_cannot_reach_a_provider"
    ".ARemovalRequestWritesARow.test_an_unattributable_removal_request_still_writes_a_held_row",
)
NOTE_MODULES = ("tests.test_linkedin_note",
                "tests.test_a_linkedin_message_is_not_a_connection_request",
                "tests.test_the_empty_connection_note_is_an_operator_decision")
TEMPLATE_MODULES = ("tests.test_no_template_escapes_the_word_contract",
                    "tests.test_every_template_is_inside_the_word_contract",
                    "tests.test_the_word_ceiling_is_enforced_on_the_composed_body")
PIN_MODULES = ("tests.test_no_new_write_bypasses_the_door",
               "tests.test_the_eight_write_path_proposals_are_unapplied",
               "tests.test_a_non_facing_write_is_not_anonymous")
SIGNING_MODULES = ("tests.test_every_body_is_signed_by_the_pools_owner",
                   "tests.test_the_provider_does_the_signing")
BRAKE_MODULES = (
    "tests.test_the_shipped_brake_constant_is_the_brake_itself",
    "tests.test_bisonfactory_consults_the_stop_sending_brake_before_each_transport",
    "tests.test_no_path_reaches_a_transport_without_passing_the_stop_sending_brake",
    "tests.test_the_operator_can_pull_the_stop_sending_brake_alone",
    "tests.test_the_stop_sending_brake_asks_nobody_for_permission",
    "tests.test_the_stop_sending_brake_fails_closed_when_it_cannot_be_read",
    "tests.test_the_stop_sending_brake_refuses_the_transport_immediately",
    "tests.test_the_stop_sending_brake_stops_the_resume_scripts")

CRITERIA = [
    (1, "a suppressed address cannot reach the transport by any path", c1),
    (2, "a removal request writes a suppression row, demonstrated", c2),
    (3, "li1 renders a real connection note for every contact", c3),
    (4, "every template passes the ceiling and the floor", c4),
    (5, "zero write paths bypass the gate, against a real denominator", c5),
    (6, "mailbox health, answered from the estate export", c6),
    (7, "one owner across the attached pool, bodies signed by that owner", c7),
    (8, "the review file is approved by the owner", c8),
    (9, "a kill switch the operator can operate alone, named and tested", c9),
]


def conjoin(verdicts):
    """MET only if ALL nine are MET. One UNKNOWN or STALE dominates."""
    if len(verdicts) != len(CRITERIA):
        return UNKNOWN
    if any(v == STALE for v in verdicts):
        return STALE
    if any(v == UNKNOWN for v in verdicts):
        return UNKNOWN
    return MET if all(v == MET for v in verdicts) else NOT_MET


def context(args):
    base = os.path.abspath(args.ops)
    tree = os.path.abspath(args.tree)
    pins = {}
    if args.pins:
        with open(args.pins, encoding="utf-8") as handle:
            pins = json.load(handle)
    results = None
    if os.environ.get("OBS2_RESULTS"):
        with open(os.environ["OBS2_RESULTS"], encoding="utf-8") as handle:
            results = json.load(handle)
    canary = os.path.join(base, "canary")
    return dict(
        tree=tree, pins=pins, results=results,
        census=os.path.join(canary, "suppression-consult-census.json"),
        pool=os.path.join(canary, "pool-owner-readback.json"),
        sheet=os.path.join(canary, "APPROVAL-SHEET-2026-10-15.md"),
        decision=os.path.join(base, "DECISION-canary-approval-2026-10-15.md"),
        exports=sorted(
            os.path.join(canary, name) for name in os.listdir(canary)
            if re.match(r"sender-estate-export-.*\.csv$", name))
        if os.path.isdir(canary) else [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", default=".", help="the repository tree to measure")
    parser.add_argument("--ops", default=r"C:\Users\Zvonimir\Desktop\resonate-ops",
                        help="where the out-of-repo authorities live")
    parser.add_argument("--pins", help="JSON of basename -> sha256; a mismatch is STALE")
    parser.add_argument("--break-criterion", type=int,
                        help="C2: force this criterion NOT MET after it is evaluated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ctx = context(args)
    code, sha = 0, "(unknown)"
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ctx["tree"],
                              capture_output=True, text=True, timeout=60)
        sha = proc.stdout.strip() or "(git refused)"
    except Exception:
        sha = "(git refused)"

    rows = []
    for number, text, check in CRITERIA:
        row = dict(number=number, text=text, detail="")
        try:
            verdict, denominator = check(ctx)
            row.update(verdict=verdict, denominator=denominator)
        except Stale as moved:
            row.update(verdict=STALE, denominator="-",
                       detail="NO VERDICT REPORTED - the authority moved: %s" % moved)
        except Unreadable as blind:
            row.update(verdict=UNKNOWN, denominator="-",
                       detail="UNKNOWN - %s" % blind)
        except Exception as raised:   # fail closed on anything unanticipated
            row.update(verdict=UNKNOWN, denominator="-",
                       detail="UNKNOWN - the check raised %s: %s"
                              % (type(raised).__name__, raised))
        if args.break_criterion == number and row["verdict"] == MET:
            row.update(verdict=NOT_MET,
                       detail="forced NOT MET by --break-criterion (control C2)")
        rows.append(row)

    verdicts = [r["verdict"] for r in rows]
    conjunction = conjoin(verdicts)
    if args.json:
        print(json.dumps(dict(conjunction=conjunction, sha=sha, tree=ctx["tree"],
                              rows=rows), indent=2))
    else:
        print("=" * 76)
        print("SECOND OBSERVER - all nine MET at once?   %s" % conjunction)
        print("=" * 76)
        print("tree  %s" % ctx["tree"])
        print("SHA   %s" % sha)
        print("ops   %s" % os.path.abspath(args.ops))
        if ctx["results"] is not None:
            print("TEST RESULTS READ FROM %s - not executed (fixture mode)"
                  % os.environ["OBS2_RESULTS"])
        print()
        for row in rows:
            print("%d. %-62s %s" % (row["number"], row["text"][:62], row["verdict"]))
            print("     %s" % row["denominator"])
            if row["detail"]:
                print("     %s" % row["detail"])
        print("-" * 76)
        print("tally  MET %d   NOT MET %d   UNKNOWN %d   STALE %d"
              % (verdicts.count(MET), verdicts.count(NOT_MET),
                 verdicts.count(UNKNOWN), verdicts.count(STALE)))
        off = [str(r["number"]) for r in rows if r["verdict"] != MET]
        if off:
            print("NOT MET at once because of: %s" % ", ".join(off))
    return {MET: 0, NOT_MET: 1, UNKNOWN: 2, STALE: 2}[conjunction]


if __name__ == "__main__":
    sys.exit(main())
