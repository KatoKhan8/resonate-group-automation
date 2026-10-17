#!/usr/bin/env python3
"""Every arm of `check_baseline_provenance.py`, planted and asserted.

ADVISORY AND UNWIRED, like the reader it controls. Nothing in CI calls this.

WHY IT EXISTS. `check_baseline_provenance.py` reads a provenance block and
prints a verdict. A verdict is only worth something if the instrument can be
shown to print the OTHER answer too, so this file plants each arm and asserts
the exact string and exit code it must produce. Without it, a "fix" that makes
the reader print VALID by making MISMATCH unreachable is indistinguishable from
a fix - and that is precisely the failure mode this repository keeps meeting.

WHAT IS PLANTED, AND ON WHAT. The carrier population is MEASURED, never
assumed: a carrier tip is any ref whose tree holds `.github/suite-baseline.txt`,
and the block under test is whatever those refs hold. No SHA is written down in
this file; the declared SHA and the carrier tips are read out of the repository
at run time, and every plant is asserted to have applied before it is believed.
Fixtures are written to a temp directory OUTSIDE the tree, so this control does
not add anything to the fixture-hygiene corpus.

MEASURED, 2026-10-17, branch task-merge-0280-units-reconcile-2026-10-17:
the committed block is honest in EVENTS and the reader compared it in NAMES, so
`failures(172) + errors(93) = 265` was held against 261 names. The block now
declares the bridge (`collapsed`), and the reader subtracts it. Before the
change the block read `MISMATCH:265!=261` at 36 of 36 distinct carrier tips;
after it reads VALID at 36 of 36, and every arm below still fires.

REPAIRED, 2026-10-17, branch task-merge-0300-arm-a-repair-2026-10-17: the one
defect this control exposed and did NOT assert - arm (a) answering "is there a
block?" with a case-folded substring of the word - is now an arm like the rest,
asserting `NO-PROVENANCE` where it used to print `STALE-UNRESOLVED:`. It was the
only producer of the "measured, not asserted" section, so that section is
removed rather than left printing nothing forever. Both answers exit 3, so the
repair moved a diagnosis and not a gate.

REPAIRED AGAIN, 2026-10-17, branch task-merge-0320-f1-writer-repair-2026-10-17:
0300 reported and deliberately did not repair F1 - the IDENTICAL predicate
live in the WRITER (`ci_suite.read_provenance_block`), with no anchored marker
and no `seen_names` guard, on the path that WRITES the baseline. This is that
repair, and the arm it added is the last one below. Like every other arm it
runs against the PRE-repair writer through `CBP_CI_SUITE`, where it is the
only arm that moves - so it observes the guard it tests rather than being
answered by another one.
"""
import contextlib
import hashlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READER = os.path.join(ROOT, "scripts", "check_baseline_provenance.py")
BASELINE_REL = ".github/suite-baseline.txt"

#: The WRITER this control's last arm drives, resolved at run time.
#: merge/0320 repaired the same case-folded substring in
#: `ci_suite.read_provenance_block` that merge/0300 repaired in the reader,
#: and a repair with no control is a repair nobody can watch fail.
#: `CBP_CI_SUITE` points this at a blob extracted with `git cat-file` (no
#: checkout, no tree mutation) so the SAME arm can be run against the
#: PRE-repair writer and shown to fail - the born-red this repository asks
#: of every repair. The path actually used is printed, so no run has to be
#: trusted about which writer answered it.
CI_SUITE = (os.environ.get("CBP_CI_SUITE")
            or os.path.join(ROOT, "scripts", "ci_suite.py"))

#: The runner line the committed block carries, and the one byte-exact line
#: plus its continuations that the units repair adds after it. The 261 names
#: are not touched, so the set the reader compares against is unchanged.
ANCHOR = "#   runner     Ran 14900, failures=172 errors=93 skipped=17 expected=18\n"
SPEC_ADDED = (
    "#   collapsed  4 - one parameterised subTest printed five closing FAIL\n"
    "#              lines, `(steps=2)` through `(steps=6)`, and\n"
    "#              `_parse_failures` keys all five by the dotted path, so\n"
    "#              these 265 closing lines are 261 distinct names\n"
)

#: What the unchanged block must read, everywhere it is carried.
BEFORE_VERDICT = "MISMATCH:265!=261"


def env():
    """The reader clears the GIT_CONFIG_COUNT family for the same reason."""
    return {k: v for k, v in os.environ.items()
            if k != "GIT_CONFIG_COUNT"
            and not k.startswith("GIT_CONFIG_KEY_")
            and not k.startswith("GIT_CONFIG_VALUE_")}


def git(args):
    p = subprocess.run(["git"] + args, cwd=ROOT, env=env(), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def is_ancestor(a, b):
    """(True/False, exit) - three states, because git says 1 for NO and 128
    for `I could not tell you` and those are not the same answer."""
    rc, _, _ = git(["merge-base", "--is-ancestor", a, b])
    return rc == 0, rc


def carrier_tips():
    """(distinct tip SHAs, the blob they carry, refs scanned, carrier refs).

    Four numbers, not two, because the population has three sizes and printing
    only two of them invites the reader to take one for another: every ref in
    the repository, the refs whose tree holds the file, and the distinct tips
    those refs point at. Measured 2026-10-17 that is 1181 / 62 / 36, and this
    line previously labelled the FIRST of those "carrier refs"."""
    rc, out, err = git(["for-each-ref", "--format=%(refname) %(objectname)",
                        "refs/heads", "refs/remotes"])
    if rc != 0:
        raise SystemExit(f"for-each-ref failed: {err[:200]}")
    found, refs, carrier_refs = {}, 0, 0
    for line in out.splitlines():
        if not line.strip():
            continue
        refs += 1
        name, sha = line.split(" ", 1)
        _, blob, _ = git(["rev-parse", "-q", "--verify",
                          f"{sha}:{BASELINE_REL}"])
        if blob:
            carrier_refs += 1
            found.setdefault(sha, blob)
    blobs = set(found.values())
    if len(blobs) != 1:
        raise SystemExit(f"expected one baseline blob across carriers, got "
                         f"{sorted(blobs)} - the population is not well defined")
    return sorted(found), blobs.pop(), refs, carrier_refs


def run(baseline, tip, repo=ROOT):
    p = subprocess.run([sys.executable, READER, "--baseline", baseline,
                        "--tip", tip, "--repo", repo],
                       cwd=ROOT, env=env(), capture_output=True, text=True,
                       encoding="utf-8")
    line = [ln for ln in (p.stdout or "").splitlines()
            if ln.startswith("VERDICT")]
    return (line[0].split(None, 1)[1] if line else "<no VERDICT line>",
            p.returncode, p.stdout or "")


def load_writer(path):
    """`ci_suite` as a module, loaded from an explicit PATH.

    By path for the same reason the reader is: the arm has to be runnable
    against a PRE-repair blob that is not what sits at that path now.
    Sourcing is asserted rather than assumed - a file that does not define
    the function the arm drives would leave the arm answered by nothing.
    """
    spec = importlib.util.spec_from_file_location("cbp_writer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not callable(getattr(mod, "read_provenance_block", None)):
        raise SystemExit(f"{path} does not define read_provenance_block")
    return mod


def writer_block(writer, path):
    """(the block the writer READS, the CARRIED lines it WRITES) of `path`.

    BOTH halves, because they are two links of one chain and the WRITE is
    the half that does the damage: `regen_baseline` puts the block it read
    back out under `CARRIED` and `INHERITED`, so a fabricated block does not
    merely sit in memory, it lands in the baseline. `regen` reads and then
    overwrites `--out`, so it is pointed at a COPY: the fixture the read
    half is measured on is never mutated by the write half measured against
    it.
    """
    block = writer.read_provenance_block(path) or []
    out = path + ".regen.txt"
    shutil.copyfile(path, out)
    with contextlib.redirect_stdout(io.StringIO()):
        writer.regen_baseline(types.SimpleNamespace(logs=[], out=out))
    text = open(out, encoding="utf-8").read()
    carried = sum(1 for ln in text.splitlines()
                  if ln.startswith(writer.CARRIED))
    return block, carried


def main():
    tmp = tempfile.mkdtemp(prefix="cbp-controls-")
    arms, failures = [], []

    def arm(name, got, want_v, want_rc, note=""):
        ok = got[0] == want_v and got[1] == want_rc
        arms.append((("OK " if ok else "FAIL"), name, got[0], got[1],
                     want_v, want_rc, note))
        if not ok:
            failures.append(name)

    try:
        tips, blob, refs, carrier_refs = carrier_tips()
        raw = subprocess.run(["git", "cat-file", "blob", blob], cwd=ROOT,
                             env=env(), capture_output=True).stdout
        real = os.path.join(tmp, "baseline-as-committed.txt")
        with open(real, "wb") as fh:
            fh.write(raw)
        amended = os.path.join(tmp, "baseline-with-collapsed.txt")
        with open(amended, "wb") as fh:
            fh.write(raw.replace(ANCHOR.encode(), (ANCHOR + SPEC_ADDED).encode()))

        print(f"tree            {ROOT}")
        print(f"HEAD            {git(['rev-parse','HEAD'])[1]}")
        print(f"refs scanned    {refs}")
        print(f"carrier refs    {carrier_refs}  (trees holding {BASELINE_REL})")
        print(f"distinct tips   {len(tips)}")
        print(f"blob            {blob}")
        print(f"  committed     {len(raw)} B  sha256 "
              f"{hashlib.sha256(raw).hexdigest()}")
        print(f"  amended       {os.path.getsize(amended)} B  sha256 "
              f"{hashlib.sha256(open(amended,'rb').read()).hexdigest()}")

        # --- the plants are asserted to have applied -----------------------
        if raw.count(ANCHOR.encode()) != 1:
            raise SystemExit("anchor is not unique in the committed block")
        if os.path.getsize(amended) != len(raw) + len(SPEC_ADDED):
            raise SystemExit("the amended block is not the committed block "
                             "plus the declared line")
        names_before = [ln for ln in raw.decode().splitlines()
                        if ln and not ln.startswith("#")]
        names_after = [ln for ln in open(amended, encoding="utf-8").read()
                       .splitlines() if ln and not ln.startswith("#")]
        if names_before != names_after:
            raise SystemExit("the repair moved a name, which it must not")
        print(f"plant check     anchor unique; +{len(SPEC_ADDED)} B; "
              f"{len(names_after)} names identical before and after")

        # --- the declared SHA, as the reader reads it ----------------------
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("cbp", READER)
        cbp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cbp)
        declared = cbp.parse(real)["fields"]["sha"]
        print(f"declared SHA    {declared} (parsed, not retyped)")

        # --- arm: before, at every carrier tip -----------------------------
        for tip in tips:
            anc, rc = is_ancestor(declared, tip)
            if rc != 0:
                raise SystemExit(f"cannot ask about ancestry of {tip}: exit {rc}")
            if not anc:
                raise SystemExit(f"{tip} carries the file but is NOT descended "
                                 f"from the declared SHA - c1 would gate first "
                                 f"and this arm would prove nothing")
        got = [run(real, t)[:2] for t in tips]
        uniq = set(got)
        arm("committed block, all carrier tips",
            (f"{uniq.pop()[0]}" if len(uniq) == 1 else f"{len(uniq)} verdicts",
             got[0][1] if len(set(got)) == 1 else 9),
            BEFORE_VERDICT, 3, f"{len(tips)}/{len(tips)} tips")

        # --- arm: after the spec, at every carrier tip ---------------------
        got = [run(amended, t)[:2] for t in tips]
        uniq = set(got)
        arm("amended block, all carrier tips",
            (uniq.pop()[0] if len(uniq) == 1 else f"{len(uniq)} verdicts",
             got[0][1] if len(set(got)) == 1 else 9),
            "VALID", 0, f"{len(tips)}/{len(tips)} tips")

        tip = tips[0]

        # --- arm: STALE, on a real ref that is not descended from the SHA ---
        rc, out, _ = git(["rev-parse", "origin/master"])
        master = out
        anc, arc = is_ancestor(declared, master)
        if arc != 1:
            arm("stale: tip does not contain the SHA", ("<premise not met>",
                 arc), "STALE:not-an-ancestor-of-tip", 3,
                "ARM NOT USABLE: origin/master DOES contain the declared SHA")
        else:
            arm("stale: tip does not contain the SHA",
                run(amended, master)[:2],
                "STALE:not-an-ancestor-of-tip", 3, f"tip origin/master {master[:9]}")

        # --- arm: STALE-UNRESOLVED ----------------------------------------
        ghost = os.path.join(tmp, "ghost-sha.txt")
        with open(ghost, "wb") as fh:
            fh.write(raw.replace(
                declared.encode(), b"0" * 40))
        arm("stale: the SHA names no commit", run(ghost, tip)[:2],
            "STALE-UNRESOLVED:" + "0" * 40, 3)

        # --- arm: STALE:inherited -----------------------------------------
        inh = os.path.join(tmp, "inherited.txt")
        with open(inh, "wb") as fh:
            fh.write(raw.replace(ANCHOR.encode(),
                                 (ANCHOR + SPEC_ADDED
                                  + "#   inherited  true\n").encode()))
        arm("stale: block says it was carried forward", run(inh, tip)[:2],
            "STALE:inherited", 3)

        # --- arm: MISMATCH, bridge declared but not closing ----------------
        off = os.path.join(tmp, "collapsed-3.txt")
        with open(off, "wb") as fh:
            fh.write(raw.replace(
                ANCHOR.encode(),
                (ANCHOR + SPEC_ADDED.replace("collapsed  4", "collapsed  3"))
                .encode()))
        got = run(off, tip)[:2]
        if got[0] == "MISMATCH:262!=261" and got[1] == 3:
            arm("mismatch: bridge declared, does not close", got,
                "MISMATCH:262!=261", 3, "declared 3, measured 4")
        else:
            arm("mismatch: bridge declared, does not close", got,
                "MISMATCH:262!=261", 3, "THE ARM THAT PROVES MISMATCH IS LIVE")

        # --- arm: MISMATCH, no bridge declared ----------------------------
        arm("mismatch: units left undeclared", run(real, tip)[:2],
            BEFORE_VERDICT, 3, "the committed block, unamended")

        # --- arm: MISMATCH, synthetic 4 events against 5 names -------------
        syn = os.path.join(tmp, "synthetic-4-vs-5.txt")
        with open(syn, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# PROVENANCE\n#\n"
                     f"#   sha        {declared}\n"
                     "#   runner     Ran 5, failures=3 errors=1\n#\n")
            for i in range(5):
                fh.write(f"synthetic_module.SyntheticCase.test_planted_{i}\n")
        arm("mismatch: 4 events against 5 names", run(syn, tip)[:2],
            "MISMATCH:4!=5", 3, "synthetic, no real data")

        # --- arm: NO-PROVENANCE -------------------------------------------
        nop = os.path.join(tmp, "no-provenance.txt")
        with open(nop, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# failing test names, one per line, written by the "
                     "runner\n")
            for i in range(3):
                fh.write(f"synthetic_module.SyntheticCase.test_planted_{i}\n")
        arm("no block at all", run(nop, tip)[:2], "NO-PROVENANCE", 3)

        absent = os.path.join(tmp, "does-not-exist.txt")
        arm("no file at all", run(absent, tip)[:2], "NO-PROVENANCE", 3)

        # --- arm: a blockless file whose header USES THE WORD --------------
        # This used to be a finding rather than an arm. merge/0280 measured
        # that (a) answered "is there a block at all?" with a case-folded
        # SUBSTRING over `#` lines, so a header that merely used the word
        # answered YES - and, because the block the reader invented declares no
        # SHA, the verdict was `STALE-UNRESOLVED:` at exit 3. 0280 reported it
        # and deliberately did NOT assert it: blessing a defect as an
        # expectation is how it survives its own test, and the repair belonged
        # to (a) and not to the units question that branch opened. The repair
        # landed on merge/0300, so it is now asserted like every other arm. The
        # expected verdict is what 0280 already recorded it SHOULD be, so this
        # arm grew no new opinion - it moved from prose to an assertion.
        wordy = os.path.join(tmp, "word-in-header-only.txt")
        with open(wordy, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# failing test names. This file carries no provenance "
                     "block.\n")
            for i in range(3):
                fh.write(f"synthetic_module.SyntheticCase.test_planted_{i}\n")
        arm("no block: the header only uses the word", run(wordy, tip)[:2],
            "NO-PROVENANCE", 3, "arm (a) reads the marker, not the word")

        # --- arm: UNKNOWN:repo-unreadable ---------------------------------
        notrepo = os.path.join(tmp, "not-a-repository")
        os.makedirs(notrepo, exist_ok=True)
        probe = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=notrepo,
                               env=env(), capture_output=True)
        if probe.returncode == 0:
            raise SystemExit(f"{notrepo} IS inside a repository, so the probe "
                             f"arm would not prove anything")
        arm("repository git cannot be asked about",
            run(amended, tip, repo=notrepo)[:2], "UNKNOWN:repo-unreadable", 2,
            "premise asserted: git says this is not a repo")

        # --- writer control, printed BEFORE the table ----------------------
        # Two known answers for the WRITER under test, because a repair that
        # only shows the new arm passing proves nothing about the case that
        # already worked.
        #   POSITIVE  the committed block must be READ IDENTICALLY and must
        #             produce an IDENTICAL file, pre- and post-repair. The
        #             sha256 below is the WHOLE written baseline, so two runs
        #             agreeing on it is byte-equality and not a summary of it.
        #   NEGATIVE  the prose fixture must read as carrying a block pre-
        #             repair and must not post-repair, and the instrument
        #             prints which answer it got rather than which it wanted.
        writer = load_writer(CI_SUITE)
        print(f"\nwriter          {CI_SUITE}")
        print(f"  ci_suite blob {git(['hash-object', CI_SUITE])[1]}  "
              f"({os.path.getsize(CI_SUITE)} B on disk)")
        rblock, rcarried = writer_block(writer, real)
        rout = open(real + ".regen.txt", encoding="utf-8").read()
        print(f"  real block    read {len(rblock)} line(s), wrote {rcarried} "
              f"CARRIED line(s), output sha256 "
              f"{hashlib.sha256(rout.encode()).hexdigest()}")

        prose = os.path.join(tmp, "word-in-writer-header.txt")
        with open(prose, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# Failing test NAMES. This file carries no PROVENANCE "
                     "block: it was\n"
                     "# written by hand, and this run re-measures the NAMES "
                     "only.\n"
                     "#\n"
                     "# names: 3\n")
            for i in range(3):
                fh.write(f"synthetic_module.SyntheticCase.test_planted_{i}\n")
        pblock, pcarried = writer_block(writer, prose)

        # --- arm: the WRITER, on a blockless header that USES the word ----
        # merge/0300 found this predicate live in the WRITER path (F1) and
        # repaired the reader instead; this is the repair. A file whose
        # header only MENTIONS the word is not a file carrying a block, and
        # a writer that says otherwise does not merely mislabel the file -
        # it writes the fabricated block back into it. ONE arm, asserting
        # both halves of the chain: the read and the write must agree, and a
        # disagreement is a failure of its own rather than half a pass.
        if not pblock and not pcarried:
            got = ("NO-PROVENANCE", 0)
        elif pblock and pcarried:
            got = ("fabricated-block-PRESENT", len(pblock))
        else:
            got = (f"WRITER-DISAGREES: read {len(pblock)} wrote {pcarried}",
                   pcarried)
        arm("writer: a blockless header that uses the word", got,
            "NO-PROVENANCE", 0,
            f"read {len(pblock)} line(s), wrote {pcarried} CARRIED")
        print(f"  prose fixture {got[0]}")

        # --- the table ----------------------------------------------------
        print()
        hdr = f"{'':<4} {'arm':<42} {'got':<28} {'rc':>3}  {'want':<28} {'rc':>3}  note"
        print(hdr)
        print("-" * len(hdr))
        for ok, name, gv, grc, wv, wrc, note in arms:
            print(f"{ok:<4} {name:<42} {gv:<28} {grc:>3}  {wv:<28} {wrc:>3}  {note}")
        print(f"\n{len(arms) - len(failures)}/{len(arms)} arms as expected")
        if failures:
            print("\nFAILED ARMS: " + ", ".join(failures))
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())