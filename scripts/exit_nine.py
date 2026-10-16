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

def criterion_1():
    """A suppressed address cannot reach the transport BY ANY PATH."""
    ran, failed, _, _ = unittest_names(
        ["tests.test_a_suppressed_address_cannot_reach_a_provider"])
    sites, bypass = write_path_counts()
    #: The criterion is a conjunction: the gated paths must refuse AND no path
    #: may be unguarded. The first half has an instrument. The second half -
    #: "how many of the 58 write paths carry no suppression consult" - does
    #: NOT exist as code in this tree; the 21-of-58 figure in the 2026-10-15
    #: audit was produced by reading call sites by eye. A criterion whose
    #: second half has no instrument is UNKNOWN, not MET.
    return dict(
        verdict=UNKNOWN,
        authority=[(os.path.join(ROOT, "src", "suppression.py"),
                    authority(os.path.join(ROOT, "src", "suppression.py"))[1]),
                   (os.path.join(ROOT, "scripts", "write_path_denominator.py"),
                    "present")],
        denominator="%d write paths; the gated-path tests ran %d with %d failing"
                    % (sites, ran, len(failed)),
        condition="NO INSTRUMENT for the 'by any path' half: nothing in this "
                  "tree counts suppression consults per write path. The "
                  "module's own tests are %s. The 21-of-58 figure quoted "
                  "elsewhere was hand-derived, not computed, so it is not "
                  "reproducible here."
                  % ("green" if not failed else "RED: " + ", ".join(sorted(failed))),
        detail=sorted(failed))


def criterion_2():
    """A removal request results in a written suppression row, demonstrated."""
    ran, failed, _, _ = unittest_names(
        ["tests.test_a_suppressed_address_cannot_reach_a_provider",
         "tests.test_a_provider_bounce_reaches_the_record"])
    return dict(
        verdict=MET if not failed else NOT_MET,
        authority=require_readable(os.path.join(ROOT, "src", "suppression.py")),
        denominator="%d tests across the two modules, %d failing" % (ran, len(failed)),
        condition="Holds only while every name in both modules passes. A "
                  "born-red test inherited from another lane still makes this "
                  "NOT MET here, because the criterion asks for a "
                  "DEMONSTRATION and a red demonstration is not one.",
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


def criterion_5():
    """The count of write paths that bypass the gate is zero, against a real
    denominator."""
    sites, bypass = write_path_counts()
    ran, failed, _, _ = unittest_names(
        ["tests.test_no_new_write_bypasses_the_door",
         "tests.test_the_eight_write_path_proposals_are_unapplied",
         "tests.test_a_non_facing_write_is_not_anonymous"])
    return dict(
        verdict=MET if bypass == 0 else NOT_MET,
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
                  "floor and not a ceiling." % bypass,
        detail=sorted(failed))


def criterion_6():
    """Mailbox health, answered from the estate export."""
    path, state = authority(ESTATE_EXPORT)
    require_readable(path)
    rows = connected = 0
    sent = 0
    bounced = 0.0
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        header = handle.readline().rstrip("\n").split(",")
        lower = [h.strip().strip('"').lower() for h in header]

        def column(*names):
            for name in names:
                for index, head in enumerate(lower):
                    if name in head:
                        return index
            return None

        i_status = column("status", "connected")
        i_sent = column("sent", "emails sent")
        i_bounce = column("bounce")
        if i_status is None:
            raise Undetermined(
                "the estate export has no status/connected column (header: %s) "
                "- a health verdict with no health column is UNDETERMINED"
                % ",".join(lower[:8]))
        for line in handle:
            if not line.strip():
                continue
            cells = next(__import__("csv").reader([line]))
            rows += 1
            if i_status < len(cells) and "connect" in cells[i_status].lower():
                connected += 1
            if i_sent is not None and i_sent < len(cells):
                try:
                    sent += int(float(cells[i_sent] or 0))
                except ValueError:
                    pass
            if i_bounce is not None and i_bounce < len(cells):
                try:
                    bounced += float((cells[i_bounce] or "0").rstrip("%"))
                except ValueError:
                    pass
    if rows == 0:
        raise Undetermined("the estate export has zero data rows - an empty "
                           "authority is UNKNOWN, never a clean bill of health")
    rate = bounced / rows
    healthy = connected == rows and rate < 3.0
    return dict(
        verdict=MET if healthy else NOT_MET,
        authority=[(path, state)],
        denominator="%d mailboxes, %d connected, %d sent, mean bounce %.2f%%"
                    % (rows, connected, sent, rate),
        condition="Holds for the export as captured 2026-10-15. It is a "
                  "SNAPSHOT of a shared estate, not a live read, and the "
                  "181-vs-225 mailbox reconciliation is still unmeasured - so "
                  "this answers health for the rows the export contains and "
                  "says nothing about rows it omits.",
        detail=[])


def criterion_7():
    """One owner across the attached pool; every body signed by that owner."""
    ran, failed, _, unexpected = unittest_names(
        ["tests.test_every_body_is_signed_by_the_pools_owner",
         "tests.test_the_provider_does_the_signing"])
    return dict(
        verdict=MET if not failed and not unexpected else NOT_MET,
        authority=[(os.path.join(ROOT, "src", "bisonfactory.py"), "present")],
        denominator="%d tests, %d failing, %d unexpected successes"
                    % (ran, len(failed), unexpected),
        condition="The MECHANISM being green is not the FACT being true: these "
                  "tests prove the signing path, and the pool's actual owner "
                  "spread is a provider question this run does not ask, "
                  "because the boundary forbids a provider call.",
        detail=sorted(failed))


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
