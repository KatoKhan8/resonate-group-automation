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
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READER = os.path.join(ROOT, "scripts", "check_baseline_provenance.py")
BASELINE_REL = ".github/suite-baseline.txt"

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


def main():
    tmp = tempfile.mkdtemp(prefix="cbp-controls-")
    arms, failures, findings = [], [], []

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

        # --- MEASURED DEFECT, REPORTED AND NOT REPAIRED --------------------
        # Arm (a) asks "is there a provenance block at all?" as a case-folded
        # SUBSTRING test over `#` lines, so a header that merely uses the word
        # answers the question YES.
        #
        # NOT A DISCOVERY, AND THAT IS THE FINDING. merge/0270 knew: its own
        # commit message says the absent-block message is written "in words
        # that do not contain the token the reader looks for". The mitigation
        # is a WORDING CONVENTION, held in a commit message, that every future
        # writer has to remember - and a convention nobody can be made to read
        # is indistinguishable from no convention at all. It is measured here
        # so the next lane does not rediscover it, and deliberately NOT
        # asserted as expected behaviour: blessing a defect as an expectation
        # is how it survives its own test. It is arm (a), not the units
        # question, so the repair is named in this branch's docs and left
        # undone rather than smuggled into the units diff.
        wordy = os.path.join(tmp, "word-in-header-only.txt")
        with open(wordy, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# failing test names. This file carries no provenance "
                     "block.\n")
            for i in range(3):
                fh.write(f"synthetic_module.SyntheticCase.test_planted_{i}\n")
        findings.append(("a blockless file whose header uses the word",
                         run(wordy, tip)[:2],
                         "NO-PROVENANCE", "arm (a) detects prose, not a marker"))

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

        # --- the table ----------------------------------------------------
        print()
        hdr = f"{'':<4} {'arm':<42} {'got':<28} {'rc':>3}  {'want':<28} {'rc':>3}  note"
        print(hdr)
        print("-" * len(hdr))
        for ok, name, gv, grc, wv, wrc, note in arms:
            print(f"{ok:<4} {name:<42} {gv:<28} {grc:>3}  {wv:<28} {wrc:>3}  {note}")
        print(f"\n{len(arms) - len(failures)}/{len(arms)} arms as expected")
        if findings:
            print("\nMEASURED, NOT ASSERTED - a defect this control exposed, "
                  "reported and not repaired here:")
            for name, got, want, why in findings:
                print(f"  {name}\n"
                      f"      was {got[0]!r} exit {got[1]}   "
                      f"should be {want!r}   {why}")
        if failures:
            print("\nFAILED ARMS: " + ", ".join(failures))
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())