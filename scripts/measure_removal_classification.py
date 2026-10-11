#!/usr/bin/env python3
"""Does the removal classifier still read what it read, and nothing more?

    py -3 scripts/measure_removal_classification.py
    py -3 scripts/measure_removal_classification.py --corpus <replies.json>
    py -3 scripts/measure_removal_classification.py --baseline <git-rev>
    py -3 scripts/measure_removal_classification.py --names

READ-ONLY on the repository. No provider call, no network, no write outside
`--out`.

## Why this is a script and not a paragraph

TASK-990 shipped a 559-row before/after measurement, a positives-unchanged
count and a name-set baseline diff - IN PROSE. GLM reviewed the branch and
returned FAIL with, among other things, "as delivered the acceptance check
is vacuous": the numbers existed only in a commit message, so the next
reviewer could believe them or not and had no third option.

A derived report is only as good as its last verification. This regenerates
the whole table on demand, so the claim and the thing that proves it ship
together.

## Three measurements, and they answer different questions

  1. THE CONSTRUCTED CORPUS - `ADVERSARIAL` and `MUST_BE_REMOVALS` below,
     committed, no PII, always runnable. It proves nothing regressed on
     traffic WE HAVE NOT SEEN YET, and it is the one that caught the real
     defect: the 559 real replies contain no warm reply carrying an
     unsubscribe footer, so the corpus measurement was sound and blind at
     the same time.

  2. THE REAL CORPUS - 559 inbound EmailBison replies. It proves nothing
     regressed on real traffic, and it is the only thing that can show a
     removal request being MISSED. It is NOT in this repository and never
     will be: it is real prospect correspondence with real addresses. Pass
     `--corpus` to point at it; without it this section says SKIPPED
     loudly rather than printing a green zero.

  3. THE NAME-SET DIFF - `--names`. Every classifier test module run twice,
     once with the baseline's `src/replies.py` swapped in, and the FAILING
     NAMES compared as sets. A baseline is a named list, never a count.

## What makes it fail

Exit 1 on: a constructed input classified as a removal; a constructed
removal request NOT classified as one; a bare one-word reply losing its
removal verdict; a reply the baseline called POSITIVE becoming a removal;
or a new failing test name. Three of those five are the same way of
costing money - a buying signal silently suppressed.
"""
import argparse
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

REMOVAL = ("unsubscribe", "account_do_not_contact")

#: Replies that must NOT be read as a removal request. Every one is written
#: by hand - none is copied from the live feed, so this file carries no
#: prospect data at all.
#:
#: The first four are GLM's, 2026-10-12, and all four were real defects:
#: three this branch introduced and one master already had.
ADVERSARIAL = (
    ("Sounds great, Thursday works. You can unsubscribe from our mailing "
     "list at any time.", "a footer describing a mechanism"),
    ("I'm out of office until Monday. To unsubscribe from this list click "
     "here.", "an infinitive in a footer, not an imperative"),
    ("How do we stop spam filters blocking your invoices?",
     "spam as a modifier of the prospect's own noun"),
    ("No further emails needed - just send the contract.",
     "a logistics statement inside a warm reply"),
    ("Happy to meet. Please note you may unsubscribe from this list at any "
     "time.", "a standing permission in a footer"),
    ("Yes - let's talk Thursday. If you prefer not to receive these, "
     "remove from the list using the link below.",
     "a footer instruction to a widget"),
    ("Interested. How do you stop spam folders eating these?",
     "spam folders are the prospect's own problem"),
    ("Sounds good, no more emails required until we sign.",
     "a condition on timing, not a refusal of contact"),
    ("Can you remove the duplicate from the contact list on slide 4?",
     "an object named, and it is not the writer"),
    ("We can delete from the list any names you flag - just say which.",
     "an offer about the prospect's own data"),
    # The footer on its OWN LINE WITH NO DELIMITER - the shape a gateway
    # actually appends, and the one `_strip_signature` cannot cut. Only
    # the first-content-line guard refuses this one.
    ("Sounds great, Thursday works. Talk then.\n\nTo manage your "
     "subscription, remove from the mailing list here.",
     "an object-less removal phrase on an undelimited footer line"),
    ("Hi, we are in year one of using a one stop tool and it is going "
     "well. This message is confidential. If received in error, please "
     "notify us and remove from your system.",
     "a confidentiality footer, reply 1602466's shape"),
    ("Please remove the second slide before you send it.",
     "an object after the verb"),
    ("Stop guessing, what does it cost?",
     "a sharp question, which is a refusal and not a removal"),
    ("please stop asking and send me a price",
     "the same words inside a sentence"),
)

#: Replies that MUST be read as a removal request. The mirror of the set
#: above, and the reason a guard cannot pass this by refusing everything.
#: Each is the human's own wording with names and addresses replaced.
MUST_BE_REMOVALS = (
    ("remove", "the bare imperative"),
    ("Remove", "the bare imperative, capitalised"),
    ("REMOVE", "the bare imperative, shouted"),
    ("unsub", "the abbreviation"),
    ("Unsub", "the abbreviation, capitalised"),
    ("unsubscribe", "the whole word"),
    ("stop", "the one-word reply"),
    ("STOP.", "the same with punctuation"),
    ("dnc", "the outbound-sales initialism"),
    ("opt out", "two words"),
    ("stop please", "the branch's addition"),
    ("please stop", "the branch's addition, reversed"),
    ("do not contact", "the branch's addition"),
    ("no contact", "the branch's addition"),
    ("Stop\n\nKind regards\nA Person\nSome Company Ltd",
     "one word over a signature block"),
    ("Remove from your list.", "the object implied"),
    ("remove from list\n\nSent from my iPhone", "no determiner at all"),
    ("Please remove from all mailing lists.", "the list qualified"),
    ("No remove from list", "a refusal and a request in four words"),
    ("You can remove us from this list!", "the plural pronoun"),
    ("please remove us from your list", "the plural pronoun, polite"),
    ("Hi,\n\nThis company has been closed permanently, so please remove us "
     "from all the mailing lists.", "the request on a later line"),
    ("Remove my email now", "the contact detail named"),
    ("Wrong company. Please remove.", "the polite bare imperative"),
    ("No thx please remove.", "the same after a refusal"),
    ("No thx, plse remove…", "the same, misspelled"),
    ("Sorry, but we are not interested. Please remove us (Some Company) "
     "from your contact list", "the company named in an aside"),
    ("not interested please delete my data and dont email me again",
     "a refusal carrying an erasure demand"),
    ("could you remove us from your distribution list? Not something we "
     "are interested in.", "the row that was announced as a buying signal"),
    ("Stop spam idiot", "an insult is not infrastructure"),
    ("Please stop spam me. THX!", "a pronoun is not infrastructure"),
    ("I would like to unsubscribe from your list",
     "a FIRST-PERSON request the footer mask must not touch"),
    ("I want to unsubscribe", "the same, shorter"),
    ("Please unsubscribe me", "the same, imperative"),
    ("Please remove me from your list. This message is confidential and "
     "you may unsubscribe at any time.",
     "a real request in a body that ALSO carries a footer"),
)


def baseline_module(rev, workdir):
    """`src/` as of *rev*, as an importable package. None if unavailable."""
    proc = subprocess.run(["git", "archive", rev, "src"], cwd=ROOT,
                          capture_output=True)
    if proc.returncode != 0:
        return None
    archive = os.path.join(workdir, "src.tar")
    with open(archive, "wb") as fh:
        fh.write(proc.stdout)
    shutil.unpack_archive(archive, workdir, format="tar")
    pkg = os.path.join(workdir, "baselinesrc")
    os.rename(os.path.join(workdir, "src"), pkg)
    if not os.path.exists(os.path.join(pkg, "replies.py")):
        return None
    sys.path.insert(0, workdir)
    return importlib.import_module("baselinesrc.replies")


_ADDR = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_ADDR_LOOSE = re.compile(r"\S*@\S*")


def scrub(value):
    """Every address-shaped token replaced by <addr>.

    The real corpus holds real prospect addresses. Nothing read from it
    reaches stdout or `--out` without passing through here.
    """
    return _ADDR_LOOSE.sub("<addr>", _ADDR.sub("<addr>", str(value or "")))


def selftest_scrub(rows):
    """Prove the filter over every string in the corpus BEFORE reporting.

    Checked first rather than afterwards: a filter verified after the fact
    has leaked a value in this repository before.
    """
    for i, row in enumerate(rows):
        for key, value in row.items():
            if isinstance(value, str) and "@" in scrub(value):
                raise SystemExit("SCRUB SELFTEST FAILED at row %d key %r"
                                 % (i, key))
    control = "write to First.Last+tag@example.co.uk about it"
    if "@" in scrub(control) or "<addr>" not in scrub(control):
        raise SystemExit("SCRUB SELFTEST FAILED: the control was not redacted")


def banner(text):
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def run_constructed(before, after):
    """Both constructed sets, through the baseline and the working tree."""
    banner("1. THE CONSTRUCTED CORPUS (committed, always runnable)")
    failures = []

    print("\n-- must NOT be a removal --")
    print("%-9s %-9s  %s" % ("baseline", "now", "why"))
    for text, why in ADVERSARIAL:
        now = after.classify(text, model=None)
        was = before.classify(text, model=None) if before else {}
        bad = now["classification"] in REMOVAL
        print("%-9s %-9s  %s%s"
              % (was.get("classification", "n/a"), now["classification"],
                 why, "   <<< SUPPRESSED" if bad else ""))
        if bad:
            failures.append("constructed non-removal read as %s: %r (%s) on %s"
                            % (now["classification"], text, why,
                               now.get("evidence")))

    print("\n-- must BE a removal --")
    print("%-9s %-9s  %s" % ("baseline", "now", "why"))
    for text, why in MUST_BE_REMOVALS:
        now = after.classify(text, model=None)
        was = before.classify(text, model=None) if before else {}
        bad = now["classification"] not in REMOVAL
        print("%-9s %-9s  %s%s"
              % (was.get("classification", "n/a"), now["classification"],
                 why, "   <<< LOST" if bad else ""))
        if bad:
            failures.append("constructed removal read as %s: %r (%s)"
                            % (now["classification"], text, why))

    print("\n%d constructed inputs, %d failing"
          % (len(ADVERSARIAL) + len(MUST_BE_REMOVALS), len(failures)))
    return failures


def run_corpus(before, after, path, out):
    """The 559 real inbound replies, before and after, if they are here."""
    banner("2. THE REAL CORPUS (inbound EmailBison replies)")
    if not path:
        print("SKIPPED - no --corpus given.")
        print("This section is the only one that can show a removal request")
        print("being MISSED. It is skipped, not passed: the corpus is real")
        print("prospect correspondence and is not in this repository.")
        return []
    if not os.path.exists(path):
        print("SKIPPED - --corpus %r does not exist." % path)
        return []
    if before is None:
        print("SKIPPED - no baseline module to compare against.")
        return []

    with open(path, encoding="utf-8") as fh:
        rows = [r for r in json.load(fh)
                if (r.get("folder") or "").lower() == "inbox"]
    selftest_scrub(rows)
    print("scrub selftest OK. inbound rows: %d" % len(rows))

    def classify_all(mod):
        done = []
        for row in rows:
            body = row.get("text_body") or ""
            v = mod.classify(body, model=None, subject=row.get("subject"))
            done.append({
                "id": row.get("id"),
                "cls": v.get("classification"),
                "ev": [scrub(e) for e in (v.get("evidence") or [])],
                "first": scrub(mod._first_content_line(
                    mod.extract_prospect_text(body)["text"]))[:90]})
        return done

    was, now = classify_all(before), classify_all(after)

    def counts(res):
        c = {}
        for r in res:
            c[r["cls"]] = c.get(r["cls"], 0) + 1
        return c

    bc, ac = counts(was), counts(now)
    b_rem = sum(1 for r in was if r["cls"] in REMOVAL)
    a_rem = sum(1 for r in now if r["cls"] in REMOVAL)
    print("\nremoval-signal total  BEFORE=%d  AFTER=%d" % (b_rem, a_rem))
    print("\n%-26s %7s %7s %7s" % ("category", "before", "after", "delta"))
    for cat in sorted(set(bc) | set(ac)):
        print("%-26s %7d %7d %+7d"
              % (cat, bc.get(cat, 0), ac.get(cat, 0),
                 ac.get(cat, 0) - bc.get(cat, 0)))

    moved_in, moved_out, other = [], [], []
    for b, a in zip(was, now):
        if b["cls"] == a["cls"]:
            continue
        br, ar = b["cls"] in REMOVAL, a["cls"] in REMOVAL
        if ar and not br:
            moved_in.append((b, a))
        elif br and not ar:
            moved_out.append((b, a))
        else:
            other.append((b, a))

    print("\nMOVED INTO a removal verdict    : %d" % len(moved_in))
    print("MOVED OUT  of a removal verdict : %d" % len(moved_out))
    print("changed, neither side a removal : %d" % len(other))
    for label, rows_ in (("moved in", moved_in), ("moved out", moved_out),
                         ("other", other)):
        if not rows_:
            continue
        print("\n-- %s --" % label)
        for b, a in rows_:
            print("  %s  %-22s -> %-22s first=%r ev=%s"
                  % (b["id"], b["cls"], a["cls"], b["first"][:62],
                     a["ev"][:2]))

    failures = []

    # A bare one-word reply may never lose its removal verdict.
    bare = re.compile(r"^(?:remove|unsub|unsubscribe|stop|dnc|"
                      r"opt\s*-?\s*out)[\s.!]*$", re.I)
    lost = [(b, a) for b, a in zip(was, now)
            if bare.match(b["first"] or "") and a["cls"] not in REMOVAL]
    bare_total = sum(1 for b in was if bare.match(b["first"] or ""))
    print("\nbare one-word rows: %d, of which LOST a removal verdict: %d"
          % (bare_total, len(lost)))
    for b, a in lost:
        failures.append("bare one-word row %s lost its removal verdict "
                        "(%s -> %s)" % (b["id"], b["cls"], a["cls"]))

    # A reply the baseline called POSITIVE may never become a removal.
    pos = [(b, a) for b, a in zip(was, now) if b["cls"] == "positive"]
    suppressed = [(b, a) for b, a in pos if a["cls"] in REMOVAL]
    print("rows the baseline called positive: %d, of which suppressed: %d"
          % (len(pos), len(suppressed)))
    for b, a in suppressed:
        failures.append("positive row %s was suppressed as %s"
                        % (b["id"], a["cls"]))

    if out:
        payload = {"baseline_rule_hash": before.RULE_HASH,
                   "rule_hash": after.RULE_HASH,
                   "rows": len(rows),
                   "removal_before": b_rem, "removal_after": a_rem,
                   "moved_in": len(moved_in), "moved_out": len(moved_out),
                   "other_changes": len(other),
                   "bare_one_word_rows": bare_total, "bare_lost": len(lost),
                   "positive_before": len(pos),
                   "positive_suppressed": len(suppressed),
                   "categories_before": bc, "categories_after": ac}
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True)
        print("\nwrote %s (scrubbed; counts and provider ids only)" % out)
    return failures


MODULES = (
    "tests.test_a_removal_request_is_decided_first",
    "tests.test_replies",
    "tests.test_a_forwarding_assistant_is_not_a_refusal",
    "tests.test_an_assistant_is_not_a_buying_signal",
    "tests.test_a_rules_3_verdict_is_never_counted",
    "tests.test_a_stored_verdict_names_the_rules_that_made_it",
    "tests.test_not_now",
    "tests.test_referral",
    "tests.test_ooo",
    "tests.test_taxonomy_safety",
    "tests.test_an_out_of_office_pauses_the_company",
    "tests.test_inbox",
    "tests.test_reporting_honesty",
    "tests.test_minimization",
    "tests.test_a_provider_flag_is_not_a_positive_reply",
    "tests.test_reachable_controls",
)
#: The module this change adds. Its names are EXPECTED to fail against the
#: baseline - the baseline has none of the patterns it asserts - so they are
#: not charged to this change. Every other module's names are.
NEW_MODULE = "test_a_removal_request_is_decided_first"
_FAILED = re.compile(r"^(?:FAIL|ERROR): (\S+)", re.M)


def _wipe_pycache():
    for base, dirs, _ in os.walk(ROOT):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(base, d), ignore_errors=True)


def _unittest_names():
    _wipe_pycache()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, "-m", "unittest"] + list(MODULES),
                          cwd=ROOT, capture_output=True, env=env)
    err = (proc.stderr or b"").decode("utf-8", "replace")
    ran = re.search(r"^Ran (\d+) tests", err, re.M)
    return set(_FAILED.findall(err)), (ran.group(1) if ran else "?")


def run_names(rev):
    """Failing-test NAMES, baseline versus working tree, compared as sets.

    The baseline's `replies.py` is swapped in, measured, and swapped back -
    asserted on disk both ways, with every `__pycache__` wiped between
    runs, because an equal-length mutation has been served from a stale
    `.pyc` in this repository before.
    """
    banner("3. THE NAME-SET DIFF (%d classifier modules)" % len(MODULES))
    live = os.path.join(ROOT, "src", "replies.py")
    with open(live, encoding="utf-8") as fh:
        mine = fh.read()

    proc = subprocess.run(["git", "show", "%s:src/replies.py" % rev],
                          cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        print("SKIPPED - cannot read src/replies.py at %r" % rev)
        return []
    baseline = proc.stdout.decode("utf-8")
    if baseline == mine:
        print("SKIPPED - the working tree matches %s, nothing to diff" % rev)
        return []

    after_names, after_ran = _unittest_names()
    try:
        with open(live, "w", encoding="utf-8", newline="") as fh:
            fh.write(baseline)
        with open(live, encoding="utf-8") as fh:
            if fh.read() != baseline:
                raise SystemExit("the baseline swap never reached the disk")
        before_names, before_ran = _unittest_names()
    finally:
        with open(live, "w", encoding="utf-8", newline="") as fh:
            fh.write(mine)
        with open(live, encoding="utf-8") as fh:
            if fh.read() != mine:
                raise SystemExit("THE RESTORE FAILED - src/replies.py is not "
                                 "what it was. Fix it before committing.")
        _wipe_pycache()

    print("BASELINE %s: ran %s, %d failing names"
          % (rev, before_ran, len(before_names)))
    for n in sorted(before_names):
        print("   %s" % n)
    print("WORKING TREE: ran %s, %d failing names"
          % (after_ran, len(after_names)))
    for n in sorted(after_names):
        print("   %s" % n)

    new = sorted(n for n in after_names - before_names if NEW_MODULE not in n)
    gone = sorted(before_names - after_names)
    print("\nNEW failing names introduced by this change: %d" % len(new))
    for n in new:
        print("   NEW  %s" % n)
    print("names that stopped failing: %d" % len(gone))
    for n in gone:
        print("   GONE %s" % n)
    return ["new failing test name: %s" % n for n in new]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", help="path to the real inbound replies JSON")
    ap.add_argument("--baseline", default="origin/master",
                    help="git rev to measure against (default origin/master)")
    ap.add_argument("--names", action="store_true",
                    help="also run the failing-test name-set diff")
    ap.add_argument("--out", help="write the corpus summary here, scrubbed")
    args = ap.parse_args(argv)

    from src import replies as after

    workdir = tempfile.mkdtemp(prefix="removal-baseline-")
    try:
        before = baseline_module(args.baseline, workdir)
        banner("RULE IDENTITY")
        print("baseline %-20s %s"
              % (args.baseline, before.RULE_HASH if before else "UNAVAILABLE"))
        print("working tree %-16s %s" % ("", after.RULE_HASH))
        if before and before.RULE_HASH == after.RULE_HASH:
            print("\nWARNING: the digest did not move. A pattern edit must")
            print("move it; if you changed one, _rule_material cannot see it.")

        failures = run_constructed(before, after)
        failures += run_corpus(before, after, args.corpus, args.out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if args.names:
        failures += run_names(args.baseline)

    banner("VERDICT")
    if failures:
        print("FAIL - %d problem(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1
    print("PASS - no constructed input misread, no bare one-word reply lost")
    print("       its verdict, no positive suppressed, no new failing name.")
    if not args.corpus:
        print("\nNote: the real-corpus section was SKIPPED. Pass --corpus to")
        print("measure it. This PASS does not cover a MISSED removal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
