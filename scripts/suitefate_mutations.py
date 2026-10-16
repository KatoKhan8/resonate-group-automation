#!/usr/bin/env python3
"""Break each guard in `src/suitefate.py` and name the tests that notice.

WHY A KILL-SET AND NOT A COUNT. A control that cannot go red licenses
nothing. This applies each mutation one at a time, runs
`tests/test_a_suite_whose_launcher_never_learned.py`, and reports the EXACT
test ids that failed - so a guard watched by nothing is visible as an empty
kill-set rather than hidden inside "26 tests pass".

AND WHY A SURVIVING MUTATION IS CHECKED FOR BEING A NO-OP. `webapp/0140`'s
M12 SURVIVED BECAUSE THE MUTATION WAS A NO-OP - it rewrote `x is not False`
to something that evaluates identically - and an empty kill-set then reads
exactly like an unwatched guard. So a mutation that NO TEST NOTICED is put
through the behaviour probe in `scripts/suitefate_probe.py`, which classifies
ten launch shapes and hashes the rendered page for each. Unchanged
fingerprint means the edit changes nothing and is reported `NO-OP`, with no
kill-set, because nothing was measured. Text changing is not behaviour
changing.

THE PROBE IS NOT CONSULTED FOR A KILLED MUTATION, and that ordering is the
point: a mutation some test failed on has changed behaviour by definition.
Gating the kill-set on the probe agreeing was this script's own first
version, and it reported six real mutations - including one that trusts an
mtime a copy contradicts - as no-ops, because the probe was narrower than
the controls. A verifier must be at least as wide as the thing it verifies.

THE REVERT IS A BYTE ROUND-TRIP, NEVER `git checkout`. This tree is LF and a
plain checkout hands files back CRLF, so the only honest proof a revert
worked is the original bytes going back and the sha256 matching what was
read. `git status` is not consulted and would not be evidence: 95.9% of this
repository's tracked files are byte-divergent while status reads clean.

    py -3 scripts/suitefate_mutations.py            # all of them
    py -3 scripts/suitefate_mutations.py --only M3  # one
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "src", "suitefate.py")
PAGES = os.path.join(ROOT, "src", "web", "pages.py")
MODULE = "tests.test_a_suite_whose_launcher_never_learned"

#: Each mutation: a file, the exact text to replace, what to replace it with,
#: and what it is meant to break. `old` must appear EXACTLY ONCE or the
#: mutation is refused - a replacement that hit two sites would be two
#: mutations reported as one.
MUTATIONS = [
    ("M1", "a launch nobody can be charged with becomes a result somebody read",
     TARGET,
     '''    if launcher is None:
        return FATE_UNKNOWN, (
            "no lane session could be tied to this launch, so whether "
            "anybody read its result is not a question this reader can "
            "answer")''',
     '''    if launcher is None:
        return FATE_FINISHED_READ, ("MUTANT M1")'''),

    ("M2", "everything is DIED-UNREAD",
     TARGET,
     '''    if launcher is None:
        return FATE_UNKNOWN, (
            "no lane session could be tied to this launch, so whether "
            "anybody read its result is not a question this reader can "
            "answer")
    if launcher["done"] is None:''',
     '''    if True:
        return FATE_DIED_UNREAD, ("MUTANT M2")
    if launcher["done"] is None:'''),

    ("M3", "nothing is ever DIED-UNREAD",
     TARGET,
     "        if earliest > launcher[\"done\"]:\n"
     "            return FATE_DIED_UNREAD, (",
     "        if earliest > launcher[\"done\"]:\n"
     "            return FATE_UNKNOWN, ("),

    ("M3b", "nothing is DIED-UNREAD on the exact-clock route either",
     TARGET,
     "    if result_exact is not None and launcher[\"done\"] < result_exact:\n"
     "        return FATE_DIED_UNREAD, (",
     "    if result_exact is not None and launcher[\"done\"] < result_exact:\n"
     "        return FATE_UNKNOWN, ("),

    ("M3c", "a killed run with a stranded lock is no longer DIED-UNREAD",
     TARGET,
     "            else:\n                fate = FATE_DIED_UNREAD\n",
     "            else:\n                fate = FATE_UNKNOWN\n"),

    ("M4", "the sessions are walked oldest-first again",
     TARGET,
     "    for row in reversed(rows):\n"
     "        if row[\"start\"] is None or row[\"start\"] > when:",
     "    for row in rows:\n"
     "        if row[\"start\"] is None or row[\"start\"] > when:"),

    ("M5", "a launch in a gap is given the previous session",
     TARGET,
     "        # The newest START at or before `when` closed BEFORE `when`, so\n"
     "        # nothing was open: the launch fell in a gap. Returning an older\n"
     "        # session here would be the nearest-available-name defect again.\n"
     "        return None\n",
     "        continue\n"),

    ("M6", "an mtime a copy contradicts is trusted as exact",
     TARGET,
     '        group["clobbered"] = len(stamps) > 1',
     '        group["clobbered"] = False'),

    ("M7", "a stranded lock is reported as a clean release",
     TARGET,
     "    return LOCKD_STRANDED, (\n",
     "    return LOCKD_RELEASED, (\n"),

    ("M8", "a holder is called dead when the process table cannot be read",
     TARGET,
     "    if lock_alive is None:\n        return LOCKD_UNDETERMINED, (\n",
     "    if lock_alive is None:\n        return LOCKD_STRANDED, (\n"),

    ("M9", "any non-empty session output counts as having read the result",
     TARGET,
     "    return bool(hits), \"; \".join(hits) if hits else (",
     "    return True, \"; \".join(hits) if hits else ("),

    ("M10", "a lane with nothing readable renders like a lane with all read",
     PAGES,
     '''            verdict = (tag("NO LAUNCH READABLE", "warn")''',
     '''            verdict = (tag("0 of 0 unread", "pass")'''),

    ("M11", "the independence banner is printed whether or not it holds",
     PAGES,
     '    if data["independent"]:\n'
     '        body += (\'<p class="note">\'\n'
     '                 + esc("THE TWO STATES ARE MEASURED INDEPENDENT',
     '    if True:\n'
     '        body += (\'<p class="note">\'\n'
     '                 + esc("THE TWO STATES ARE MEASURED INDEPENDENT'),

    ("M12", "a launch with no pid is asked of the lock anyway",
     TARGET,
     '''    if pid is None:
        return LOCKD_UNDETERMINED, (
            "no pid could be established for this launch, so the lock cannot "
            "be asked about it. Not released")''',
     '''    if pid is None:
        return LOCKD_RELEASED, ("MUTANT M12")'''),
]


#: The probe and the control run lives in its own module rather than in a
#: `%`-escaped string here, because a giant quoted program is unreadable and
#: its `%%s` escapes are a trap. See `scripts/suitefate_probe.py`.
PROBE = os.path.join(ROOT, "scripts", "suitefate_probe.py")


def _drop_bytecode(*paths):
    """Remove the `__pycache__` entry for each source file.

    THE TRAP THIS EXISTS FOR, AND IT COST THREE FALSE NO-OPS. CPython decides
    a `.pyc` is current by comparing the source's size and its mtime - and
    the mtime is stored in the `.pyc` header as WHOLE SECONDS. Three of the
    mutations below are the same edit size (`FATE_DIED_UNREAD` to
    `FATE_UNKNOWN`, -4 bytes), and the harness writes them within the same
    second as each other. So the second and third runs matched the first's
    cached bytecode on both fields, imported the PREVIOUS mutation, produced
    an identical fingerprint, and were reported NO-OP - a mutation that
    changes behaviour reading exactly like one that changes nothing.

    `-B` on the child is not enough: it stops a `.pyc` being WRITTEN, not an
    existing one being read.
    """
    for path in paths:
        folder = os.path.join(os.path.dirname(path), "__pycache__")
        stem = os.path.splitext(os.path.basename(path))[0] + "."
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if name.startswith(stem) and name.endswith(".pyc"):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass


def run_once():
    """`(fingerprint, failed, total)` from a fresh interpreter, or raise."""
    _drop_bytecode(TARGET, PAGES)
    proc = subprocess.run([sys.executable, "-B", PROBE], cwd=ROOT,
                          capture_output=True)
    text = proc.stdout.decode("utf-8", "replace")
    marker = text.rfind("@@@")
    if marker < 0:
        raise RuntimeError(
            "the runner printed no result.\nstdout:\n%s\nstderr:\n%s"
            % (text[-2000:], proc.stderr.decode("utf-8", "replace")[-2000:]))
    payload = json.loads(text[marker + 3:].strip())
    return payload["fingerprint"], payload["failed"], payload["total"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", default=None,
                        help="run just these mutation ids")
    args = parser.parse_args()

    # The originals, as BYTES, plus a sha256 each. The revert writes these
    # bytes back and the hash is checked afterwards; no git command is
    # involved at any point.
    original = {}
    for path in {TARGET, PAGES}:
        with open(path, "rb") as handle:
            blob = handle.read()
        original[path] = blob
        print("%-28s %d B  sha256 %s"
              % (os.path.basename(path), len(blob),
                 hashlib.sha256(blob).hexdigest()[:16]))

    print("\nBASELINE")
    base_print, base_failed, total = run_once()
    print("  %d tests, %d failing: %s" % (total, len(base_failed),
                                          base_failed or "none"))
    if base_failed:
        print("  REFUSED: the baseline is not green, so no kill-set measured "
              "against it means anything. A violation added to an already-red "
              "test is invisible.")
        return 2
    # THE GUARD THE FIRST RUN OF THIS SCRIPT NEEDED AND DID NOT HAVE. The
    # probe raised on a None lane, so the baseline fingerprint was a one-row
    # error string - and every mutated fingerprint was the SAME one-row error
    # string, so all twelve surviving mutations reported NO-OP and nothing
    # was measured. A probe that cannot run is not a probe, and it fails
    # exactly like a clean bill of health.
    if any(row and str(row[0]).startswith("PROBE RAISED")
           for row in base_print):
        print("  REFUSED: the behaviour probe itself raised - %s. Every "
              "mutation would compare equal to this and report NO-OP."
              % base_print[0])
        return 2
    if len(base_print) < 4:
        print("  REFUSED: the behaviour fingerprint has only %d rows, which "
              "is too few to distinguish the mutations below. It should "
              "carry a row per launch of both canonical instances plus a "
              "totals row each." % len(base_print))
        return 2
    print("  behaviour fingerprint: %d rows" % len(base_print))
    for row in base_print:
        print("    %s" % " | ".join(row))

    results = []
    for ident, what, path, old, new in MUTATIONS:
        if args.only and ident not in args.only:
            continue
        blob = original[path]
        text = blob.decode("utf-8")
        hits = text.count(old)
        if hits != 1:
            print("\n%-5s REFUSED: the anchor appears %d times, not once"
                  % (ident, hits))
            results.append((ident, what, "ANCHOR", []))
            continue
        mutated = text.replace(old, new, 1).encode("utf-8")
        assert mutated != blob, ident
        with open(path, "wb") as handle:
            handle.write(mutated)
        try:
            print("\n%-5s %s" % (ident, what))
            print("      target %s, %+d bytes"
                  % (os.path.basename(path), len(mutated) - len(blob)))
            try:
                finger, failed, ran = run_once()
            except RuntimeError as exc:
                # A mutation that stops the module importing at all. That IS
                # a behaviour change, and the whole suite failing is the
                # kill-set - reported rather than counted as a pass.
                print("      the module no longer imports: %s"
                      % str(exc).splitlines()[0])
                results.append((ident, what, "IMPORT ERROR", ["<all>"]))
                continue
            changed = finger != base_print
            drift = len([row for row in finger if row not in base_print])
            if failed:
                # A TEST FAILED, SO BEHAVIOUR CHANGED. The probe is not
                # consulted here and must not be: a mutation some control
                # noticed needs no second opinion about whether it did
                # anything, and asking for one is how six real mutations got
                # reported as no-ops.
                print("      KILLED BY %d of %d  (fingerprint rows changed: "
                      "%d)" % (len(failed), ran, drift))
                for name in failed:
                    print("        %s" % name)
                results.append((ident, what, "KILLED", failed))
                continue
            if not changed:
                # 0140's M12. Not "survived" - NOT MEASURED.
                print("      NO-OP: no control noticed AND the behaviour "
                      "fingerprint is byte-for-byte the baseline's across "
                      "all ten launch shapes and their rendered pages. This "
                      "edit changes nothing, so no kill-set is reported - "
                      "nothing was tested.")
                results.append((ident, what, "NO-OP", []))
                continue
            print("      SURVIVED: %d tests ran and none noticed, and the "
                  "fingerprint DID change in %d row(s). This guard is "
                  "watched by nothing." % (ran, drift))
            for row in finger:
                if row not in base_print:
                    print("        now: %s" % " | ".join(row))
            results.append((ident, what, "SURVIVED", []))
        finally:
            # THE REVERT: the original bytes, written back, and proved.
            with open(path, "wb") as handle:
                handle.write(blob)
            with open(path, "rb") as handle:
                back = handle.read()
            assert back == blob, (
                "%s did not revert to its original bytes" % path)
            assert (hashlib.sha256(back).hexdigest()
                    == hashlib.sha256(blob).hexdigest())

    print("\n" + "=" * 68)
    for ident, what, state, failed in results:
        print("%-5s %-9s %-2d  %s" % (ident, state, len(failed), what))
    unwatched = [r for r in results if r[2] == "SURVIVED"]
    noop = [r for r in results if r[2] == "NO-OP"]
    print("\n%d mutations, %d killed, %d survived, %d no-op (not measured)"
          % (len(results), len([r for r in results if r[2] == "KILLED"]),
             len(unwatched), len(noop)))

    # And the final proof, after everything: both files back to their
    # original sha256.
    print("\nREVERT PROOF, by byte round-trip and sha256 - no git command:")
    for path in sorted(original):
        with open(path, "rb") as handle:
            blob = handle.read()
        ok = blob == original[path]
        print("  %-28s %s  sha256 %s"
              % (os.path.basename(path), "IDENTICAL" if ok else "DIVERGED",
                 hashlib.sha256(blob).hexdigest()[:16]))
        if not ok:
            return 1
    return 1 if unwatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
