#!/usr/bin/env python3
"""Report-mode provenance verdicts over a tip population. Gates nothing.

BESIDE, NOT INSIDE. This file CALLS `check_baseline_provenance.py` and does not
change one byte of it, of `.github/workflows/suite.yml`, or of `BASELINE_MODE`.
It exists because merge/0270 recommended two things and named the order: first
"a re-measurement, then a report-mode step beside the existing gate". merge/0280
did the re-measurement and left 0270's operator recommendation standing -
`BASELINE_MODE` not flipped, reader not wired into CI. This is the other half:
the step that PRINTS, so a human can read the population without anything being
armed.

WHERE THE SHAPES COME FROM. The reader prints its verdicts to stdout and returns
an exit code (0 VALID, 3 any other verdict, 2 usage or repo-unreadable). This
step runs it as the reader's own `__main__` in a subprocess, captures that
stdout, and lifts the `VERDICT` line. It does not re-implement any check and it
does not import the reader's internals, so a change to the reader's logic shows
up here as a changed verdict rather than as two implementations that drift.

ALWAYS EXIT 0, AND THAT IS THE POINT. A report that can fail is a gate, and
arming a gate is the operator's decision and not this file's. So every path
leads to exit 0: a tip whose reader exits 3 still exits 0 here, an unreadable
repository prints `UNKNOWN:repo-unreadable` per tip and still exits 0, a reader
that prints no VERDICT line at all is reported as `UNKNOWN:reader-no-verdict`
and still exits 0, and even a usage error is turned into an `UNKNOWN:` line and
exit 0. That is deliberately the opposite of the reader's own contract, and the
reason is the same one that keeps the reader unwired: the exit code must not be
mistakable for a gate somebody armed by accident.

THE PIN IS A BLOB ID, NOT A DISK SHA256. This repository sets
`core.autocrlf=true`, so one blob is written CRLF in one tree and LF in
another and the two renderings have two sha256s. A header pinning only the disk
sha256 would name the same reader differently in two trees at the same commit -
the exact failure a provenance line exists to prevent. The pinned name is
therefore the git blob id (`git hash-object`, clean filter applied, so the
checkout is normalised away) and the disk sha256 is printed beside its CR count
so which rendering was measured is stated rather than assumed. See `identity()`.

WHAT THE READER'S OWN EXIT CODE IS STILL SHOWN FOR. Throwing it away would hide
whether the step is standing beside a gate that still refuses. It is counted in
the summary (`reader-rc exit0=.. exit3=.. other=..`) rather than folded into the
verdict, so the two questions stay separate: what the block says, and what the
gate beside it did.

THE TIME BOX. A tip that measures for longer than `--time-box` seconds is killed
and reported as `UNKNOWN:time-box` rather than being allowed to hold the run -
`UNKNOWN` because an authority that could not be read is never zero and never
safe. It needs a real, killable process, which is the other reason the reader is
called as a subprocess rather than imported: a thread cannot be killed in
CPython, so an in-process timeout would report a box it had not actually
enforced.

USAGE

    provenance_report.py --baseline PATH [--tip SHA]... [--repo PATH]
                         [--time-box SECONDS] [--master-ref REF] [--detail]
    provenance_report.py --pair BASE::TIP [--pair BASE::TIP]...

With no `--tip`, the carrier-tip population is discovered: every ref whose tree
holds the baseline path, reduced to its distinct tip commits. With `--tip`, only
those commits are measured. `--pair` measures named (baseline, tip) pairs
instead, which is how a single run shows every verdict shape at once: one
baseline cannot produce VALID and MISMATCH for the same tip, so a demonstration
that must print both needs more than one block. In `--pair` mode the pairs are
listed in order above the verdicts, because the verdict line names the TIP and
several pairs may share one - without that list a run measuring one tip against
four blocks prints four lines a reader cannot tell apart. `--detail`
additionally echoes each tip's full reader output, which is what a human reads
when a verdict needs explaining.

OUTPUT, one line per measured tip and then the denominators:

    VERDICT <sha> <verdict>
    SUMMARY tips=<n> valid=<n> stale=<n> mismatch=<n> no-provenance=<n> unknown=<n> other=<n>
    READER-RC exit0=<n> exit3=<n> other=<n>
    EXIT 0 (report mode - a report that can fail is a gate)
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READER = os.path.join(ROOT, "scripts", "check_baseline_provenance.py")
BASELINE_REL = ".github/suite-baseline.txt"
DEFAULT_TIME_BOX = 600


def env():
    """The GIT_CONFIG_COUNT family is cleared for the same reason the reader
    clears it: an inherited GIT_CONFIG_COUNT with no matching KEY_/VALUE_ pair
    makes every git call in this shell fail, which is a property of the caller
    and not of the repository."""
    return {k: v for k, v in os.environ.items()
            if k != "GIT_CONFIG_COUNT"
            and not k.startswith("GIT_CONFIG_KEY_")
            and not k.startswith("GIT_CONFIG_VALUE_")}


def git(args, repo):
    p = subprocess.run(["git"] + list(args), cwd=repo, env=env(),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def identity(path, repo):
    """What this file IS, in names that do not move with the checkout.

    A sha256 taken from the file on disk is NOT a stable name for it. This
    repository sets `core.autocrlf=true`, so one blob is written CRLF in one
    tree and LF in another: measured 2026-10-17, the reader is 19669 B with 382
    CRs here and 19287 B with 0 CRs as a blob, and the two renderings have two
    different sha256s. A provenance line that pins only the disk sha256
    therefore reports a different value for the same reader at the same commit
    depending on which tree it is read in - which is the defect this repository
    already has a name for, and the one thing a provenance reader must not do.

    So the pinned name is the git BLOB ID, which `git hash-object` computes with
    the clean filter applied and therefore normalises the checkout away, and the
    disk sha256 is printed beside its CR count so that what was measured is
    stated rather than assumed.

    Two things measured rather than assumed about that id, 2026-10-17: it is
    exactly what THIS TREE would commit for the file, since the filter is
    whatever config git can reach from `repo` - not an unconditional claim about
    the blob on some other branch. And `git hash-object` is repo-independent
    plumbing: it exits 0 even when `git rev-parse --git-dir` exits 128 in the
    same directory, so an unreadable repository still yields an id here rather
    than a blank. That is why the reader's own `UNKNOWN:repo-unreadable` verdict
    and this id can appear in the same report without either being wrong.

    Returns (blob_id_or_None, reason)."""
    rc, out, err = git(["hash-object", path], repo)
    if rc == 0 and out:
        return out, None
    return None, (err.splitlines()[0] if err else f"git exit {rc}")


def render(path):
    """(bytes, crs, sha256) for the file as this checkout wrote it, or Nones."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None, None, None
    return len(raw), raw.count(b"\r"), hashlib.sha256(raw).hexdigest()


def discover_tips(repo):
    """Every ref whose tree holds BASELINE_REL, reduced to distinct tips.

    Returns (tips, detail). `detail` is the population in the three sizes the
    control harness prints, because this population has three and naming only
    one of them invites the reader to take it for another: refs scanned, refs
    whose tree holds the file, and the distinct tips those refs point at."""
    rc, out, err = git(["for-each-ref", "--format=%(refname) %(objectname)",
                        "refs/heads", "refs/remotes"], repo)
    if rc != 0:
        return None, f"for-each-ref failed: {err.splitlines()[0] if err else 'no stderr'}"
    refs, carrier_refs, tips = 0, 0, {}
    for line in out.splitlines():
        if not line.strip():
            continue
        refs += 1
        name, sha = line.split(" ", 1)
        rc2, blob, _ = git(["rev-parse", "-q", "--verify",
                            f"{sha}:{BASELINE_REL}"], repo)
        if rc2 == 0 and blob:
            carrier_refs += 1
            tips.setdefault(sha, blob)
    return (sorted(tips),
            f"refs scanned {refs}, carrier refs {carrier_refs}, "
            f"distinct tips {len(tips)}")


def classify(verdict):
    """The reader's vocabulary folded to the five shapes this report counts.
    Prefix-matched rather than exact-matched, so a new stale reason the reader
    grows is counted as stale instead of falling through to `other`."""
    if verdict == "VALID":
        return "valid"
    if verdict.startswith("STALE-UNRESOLVED:") or verdict.startswith("STALE:"):
        return "stale"
    if verdict.startswith("MISMATCH:"):
        return "mismatch"
    if verdict == "NO-PROVENANCE":
        return "no-provenance"
    if verdict.startswith("UNKNOWN:"):
        return "unknown"
    return "other"


def measure(baseline, tip, repo, master_ref, time_box, detail_out):
    """(verdict, reader_rc) for one tip. Never raises: every failure mode this
    can reach is a named UNKNOWN rather than an exception, because an exception
    here would take the report down and a report is not allowed to fail."""
    argv = [sys.executable, READER, "--baseline", baseline, "--tip", tip,
            "--repo", repo, "--master-ref", master_ref]
    try:
        p = subprocess.run(argv, cwd=repo, env=env(), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=time_box)
    except subprocess.TimeoutExpired:
        return "UNKNOWN:time-box", None
    except OSError as exc:
        return f"UNKNOWN:reader-not-runnable ({type(exc).__name__}: {exc})", None
    out = p.stdout or ""
    if detail_out is not None:
        detail_out.append((tip, out, p.stderr or "", p.returncode))
    line = [ln for ln in out.splitlines() if ln.startswith("VERDICT")]
    if not line:
        return "UNKNOWN:reader-no-verdict", p.returncode
    parts = line[0].split(None, 1)
    return (parts[1] if len(parts) > 1 else "UNKNOWN:reader-empty-verdict",
            p.returncode)


def run(argv=None):
    ap = argparse.ArgumentParser(
        prog="provenance_report.py",
        description="Report-mode provenance verdicts. Prints; gates nothing.")
    ap.add_argument("--baseline", default=None,
                    help="the baseline file to measure against every tip")
    ap.add_argument("--tip", action="append", default=None,
                    help="a commit carrying this file; repeatable. With none "
                         "given, the carrier-tip population is discovered.")
    ap.add_argument("--pair", action="append", default=None, metavar="BASE::TIP",
                    help="one (baseline, tip) pair; repeatable. `::` because a "
                         "Windows path may hold `:` and `=`, and this is how a "
                         "single run measures tips against DIFFERENT blocks, "
                         "which is what lets one run print every verdict shape.")
    ap.add_argument("--repo", default=ROOT)
    ap.add_argument("--master-ref", default="origin/master")
    ap.add_argument("--time-box", type=int, default=DEFAULT_TIME_BOX,
                    help=f"seconds per tip before UNKNOWN:time-box "
                         f"(default {DEFAULT_TIME_BOX})")
    ap.add_argument("--detail", action="store_true",
                    help="echo each tip's full reader output")
    args = ap.parse_args(argv)

    print("REPORT-MODE: prints, gates nothing, exits 0 on every path.")
    print(f"reader      {READER}")
    r_blob, r_why = identity(READER, args.repo)
    print(f"  blob      {r_blob if r_blob else 'not computable: ' + str(r_why)}")
    n, crs, sha = render(READER)
    print(f"  on disk   {n} B  CR {crs}  sha256 {sha}")
    print(f"repository  {args.repo}")

    # A job is (label, baseline, tip). `--pair` supplies its own baseline, which
    # is what lets one run print every verdict shape; `--baseline` with `--tip`
    # measures one block against many tips, which is the population case.
    jobs = []
    if args.pair:
        for spec in args.pair:
            if "::" not in spec:
                print(f"pair        MALFORMED (no `::`): {spec}")
                print("\nSUMMARY tips=0 valid=0 stale=0 mismatch=0 "
                      "no-provenance=0 unknown=0 other=0")
                print("READER-RC exit0=0 exit3=0 other=0")
                print("\nEXIT 0 (report mode - a report that can fail is a gate)")
                return 0
            base, tip = spec.split("::", 1)
            # Resolved against THIS process's cwd, not the reader's, which is
            # run with cwd=repo. A relative path left alone would silently mean
            # two different files depending on --repo.
            jobs.append((tip, os.path.abspath(base), tip))
        print(f"population  {len(jobs)} (baseline, tip) pair(s), named on the "
              f"command line")
        # The verdict line names the TIP, and several pairs may share a tip, so
        # the pair list is printed in order and the nth line here is the nth
        # VERDICT below. Without it a run that measures one tip against four
        # blocks prints four lines a reader cannot tell apart.
        for i, (label, base, _tip) in enumerate(jobs, 1):
            b_blob, b_why = identity(base, args.repo)
            bn, bcr, _ = render(base)
            where = (f"{bn} B  CR {bcr}" if bn is not None else "ABSENT")
            print(f"  pair {i:<3} {where:<20} "
                  f"blob {b_blob if b_blob else 'n/a: ' + str(b_why)}")
            print(f"            baseline {base}")
            print(f"            tip      {label}")
    else:
        if not args.baseline:
            print("population  NO BASELINE - pass --baseline with --tip, or --pair")
            print("\nSUMMARY tips=0 valid=0 stale=0 mismatch=0 "
                  "no-provenance=0 unknown=0 other=0")
            print("READER-RC exit0=0 exit3=0 other=0")
            print("\nEXIT 0 (report mode - a report that can fail is a gate)")
            return 0
        # Same reason as the pair branch: resolved here so that --repo cannot
        # change which file a relative --baseline names.
        args.baseline = os.path.abspath(args.baseline)
        print(f"baseline    {args.baseline}")
        b_blob, b_why = identity(args.baseline, args.repo)
        print(f"  blob      {b_blob if b_blob else 'not computable: ' + str(b_why)}")
        bn, bcr, bsha = render(args.baseline)
        if bn is None:
            print("  on disk   ABSENT")
        else:
            print(f"  on disk   {bn} B  CR {bcr}  sha256 {bsha}")
        tips = args.tip
        if tips is None:
            tips, detail = discover_tips(args.repo)
            if tips is None:
                print(f"population  UNDISCOVERABLE - {detail}")
                print("VERDICT <none> UNKNOWN:population-undiscoverable")
                print("\nSUMMARY tips=0 valid=0 stale=0 mismatch=0 "
                      "no-provenance=0 unknown=0 other=0")
                print("READER-RC exit0=0 exit3=0 other=0")
                print("\nEXIT 0 (report mode - a report that can fail is a gate)")
                return 0
            print(f"population  {detail}")
        else:
            print(f"population  {len(tips)} tip(s), named on the command line")
        jobs = [(t, args.baseline, t) for t in tips]

    print()
    counts = {k: 0 for k in ("valid", "stale", "mismatch", "no-provenance",
                             "unknown", "other")}
    rcs = {"exit0": 0, "exit3": 0, "other": 0}
    details = [] if args.detail else None
    for label, base, tip in jobs:
        verdict, rc = measure(base, tip, args.repo, args.master_ref,
                              args.time_box, details)
        print(f"VERDICT {label} {verdict}")
        counts[classify(verdict)] += 1
        if rc == 0:
            rcs["exit0"] += 1
        elif rc == 3:
            rcs["exit3"] += 1
        else:
            rcs["other"] += 1

    if details:
        for tip, out, err, rc in details:
            print(f"\n--- reader output for {tip} (exit {rc}) ---")
            sys.stdout.write(out)
            if err:
                sys.stdout.write(f"--- stderr ---\n{err}\n")

    print()
    print("SUMMARY tips={} valid={} stale={} mismatch={} no-provenance={} "
          "unknown={} other={}".format(
              len(jobs), counts["valid"], counts["stale"], counts["mismatch"],
              counts["no-provenance"], counts["unknown"], counts["other"]))
    print(f"READER-RC exit0={rcs['exit0']} exit3={rcs['exit3']} "
          f"other={rcs['other']}")
    print()
    print("EXIT 0 (report mode - a report that can fail is a gate)")
    return 0


def main(argv=None):
    """Any failure at all is a printed UNKNOWN and exit 0. This is the one
    place the always-exit-0 contract is enforced, so it is stated once here
    rather than trusted to every branch above."""
    try:
        return run(argv)
    except SystemExit as exc:
        # argparse exits 2 on a usage error. A report is not allowed to fail on
        # one, so it is reported as the UNKNOWN it is.
        if exc.code not in (0, None):
            print(f"VERDICT <none> UNKNOWN:usage (exit {exc.code})")
            print("\nSUMMARY tips=0 valid=0 stale=0 mismatch=0 "
                  "no-provenance=0 unknown=0 other=0")
            print("READER-RC exit0=0 exit3=0 other=0")
            print("\nEXIT 0 (report mode - a report that can fail is a gate)")
        return 0
    except Exception as exc:  # noqa: BLE001 - the contract, not a fallback
        print(f"VERDICT <none> UNKNOWN:report-crashed ({type(exc).__name__}: {exc})")
        print("\nSUMMARY tips=0 valid=0 stale=0 mismatch=0 no-provenance=0 "
              "unknown=0 other=0")
        print("READER-RC exit0=0 exit3=0 other=0")
        print("\nEXIT 0 (report mode - a report that can fail is a gate)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())