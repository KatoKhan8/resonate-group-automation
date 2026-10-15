#!/usr/bin/env python3
"""TASK-0050 - does a restore keep the suppressions?

    py -3 scripts/suppression_restore_drill.py --state-dir FIXTURE --into SCRATCH
    py -3 scripts/suppression_restore_drill.py --state-dir FIXTURE --restored DIR
    py -3 scripts/suppression_restore_drill.py --state-dir FIXTURE --into SCRATCH \
            --touches touches.json --keep

A RESTORE THAT LOSES SUPPRESSION DOES NOT LOOK BROKEN. It looks like a clean
estate, and the first thing a clean estate does is contact everybody in it -
including the people who opted out. That is the one failure on the backup path
with a named victim, and before this file nothing asserted against it.

## What was already asserted, and what was not

`scripts/server/backup.py --drill` compares the source tree against the
restored tree BY NAME AND BY HASH. That is a good drill and this file calls it
rather than reimplementing it. What it proves is that the FILESYSTEM round
-trips: every byte came back.

`scripts/restore_drill.py` loads the restored queue through `store.load()` and
compares record counts and two histograms against the live store. That proves
one file parses.

Neither asks the question this file asks: **does `src/suppression.py` still
refuse the same people?** A file can come back byte for byte and still be read
by a module that no longer finds the suppression in it - a moved path, an index
beside the queue that was never in the archive, a flag on a contact the loader
drops. Bytes are not verdicts. This drill asks the module.

## The method

1. Census the SOURCE. Every (record, contact) in it, named
   `<rec_id>::<contact_key>`, with the verdict `suppression.decide` gives at
   BOTH scopes - `SCOPE_ENROL`, where the hold rules are evaluated, and
   `SCOPE_SEND`, the door immediately before a provider write.
2. Back up the source with the live engine, `scripts/server/backup.py`.
3. Restore into a scratch directory.
4. Census the RESTORED tree with the SAME inputs.
5. Compare BY NAME. Never by count: three censuses can hold the same number of
   BLOCK rows and be three different sets of people.

## Why names and not counts

The repository has already paid for this once - three finished suites each
reported exactly 231 failing names and one of them was a different 231. A
count that has not moved is not a set that has not moved. So every comparison
here is a set difference over member names, reported in both directions, and
`--verbose` prints the names rather than the totals.

## UNKNOWN IS NOT A PASS

`suppression.UNKNOWN_IS_NOT_A_PASS` is checked at startup and this drill
refuses to run if it has been turned off, because every verdict it would then
collect is a different question from the one it reports. Within the drill the
same rule holds in three places:

  * a member in the source census that is not in the restored census is LOST,
    which is a failure, whatever its verdict was;
  * a member whose record will not parse out of the restored tree is not
    present, and absence is never ALLOW;
  * a census with no BLOCK rows at all cannot fail, so it is refused as
    vacuous rather than reported as a pass.

## WHERE EACH REFUSAL'S AUTHORITY LIVES, AND WHY THAT BOUNDS THE PROOF

Not every reason a person is suppressed is stored in `work/`, and `work/` is
the only thing the backup contains. The drill therefore classifies each BLOCK
by where its authority actually sits and reports the three groups separately,
because a BLOCK whose authority was never in the archive is NOT PROVEN by a
restore of the archive - it merely happened to be re-read from the same place
both times.

  IN_ARCHIVE      the record itself (`work/queue.jsonl`) and the agency
                  do-not-contact index (`work/agency-dnc.jsonl`). These are
                  the ones a restore can lose, and the ones this drill proves.
  IN_GIT          `config/suppress.txt`, `config/operator-exclusions.jsonl`,
                  the client configs. Outside the archive, but reconstructible
                  from a clone, so a lost laptop does not lose them.
  NOWHERE_ELSE    `config/suppress.local.txt` - the gitignored local roster,
                  read by `ingest.load_suppress` as a merge partner of the
                  tracked file. Not in git and not in `work/`, so it is in
                  NEITHER copy. If it exists, it is the one suppression source
                  with no backup at all.

## No production state

The source directory is refused if it is one of `store.protected_directories()`
- this tree's `work/` or the main checkout's. The drill reads a fixture or a
copy, writes only under `--into`, and restores `QUEUE` and every
`STATE_OVERRIDES` entry in a `finally` so the process is never left pointed at
a deleted scratch directory.

## No addresses are printed

A member is named `<rec_id>::<contact_key>`. The email is used for the agency
index lookup and never reaches stdout, stderr or a report, because this drill
is meant to be runnable against a real archive and a real archive is prospect
PII.
"""
import argparse
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import eligibility, store, suppression        # noqa: E402

BACKUP_SCRIPT = os.path.join(ROOT, "scripts", "server", "backup.py")

#: `<rec_id>::<contact_key>`. Chosen over the email because this runs against
#: real archives and an email in a log is a disclosure.
MEMBER_SEP = "::"

#: Where a refusal's authority is stored. See the module docstring.
IN_ARCHIVE = "in_archive"
IN_GIT = "in_git"
NOWHERE_ELSE = "not_backed_up_anywhere"
UNCLASSIFIED = "unclassified"

#: Read off the queue record or the agency index, both of which are in `work/`
#: and therefore in the archive. A restore can lose these, which is the point.
_IN_ARCHIVE_REASONS = frozenset({
    eligibility.BLOCKED_CLIENT_SUPPRESSED,
    eligibility.BLOCKED_AGENCY_DNC,
    eligibility.BLOCKED_DROPPED,
    eligibility.BLOCKED_COMPANY_PAUSED,
    eligibility.BLOCKED_CONTACT_PAUSED,
    eligibility.BLOCKED_REPLIED,
    eligibility.BLOCKED_UNSUBSCRIBED,
    eligibility.BLOCKED_ACCOUNT_SUPPRESSED,
    eligibility.BLOCKED_CONTACT_STOPPED,
    eligibility.BLOCKED_REVIEW_REQUIRED,
})

#: Read from a tracked file under `config/`. Not in the archive, but a clone
#: brings them back, so losing the laptop does not lose them.
_IN_GIT_REASONS = frozenset({
    eligibility.BLOCKED_OPERATOR_EXCLUDED,
    eligibility.BLOCKED_CLIENT_DOMAIN,
})


def _suppress_authority():
    """Which file a `blocked:suppressed` could have come from, as a group.

    `ingest.load_suppress` merges the tracked `config/suppress.txt` with the
    gitignored `config/suppress.local.txt`. The merged set cannot say which
    file a given domain came from, so this reports the WEAKEST authority that
    is actually present: if the local roster exists, a domain refusal may rest
    on a file that is in neither git nor the archive, and the drill must say
    so rather than quietly credit the tracked file.
    """
    from src import ingest
    if os.path.exists(ingest.SUPPRESS_LOCAL):
        return NOWHERE_ELSE
    return IN_GIT


def authority_of(reason):
    """Where this refusal is stored. See the module docstring."""
    if reason in _IN_ARCHIVE_REASONS:
        return IN_ARCHIVE
    if reason in _IN_GIT_REASONS:
        return IN_GIT
    if reason == eligibility.BLOCKED_SUPPRESSED:
        return _suppress_authority()
    return UNCLASSIFIED


# ------------------------------------------------------------------ census


class Member:
    """One (record, contact) pair and what suppression said about it.

    Not a dict, because a dict can be assembled by anybody and the comparison
    below treats equality of these as "the restore kept this person's
    verdict". A shape that is easy to fabricate is a comparison that is easy
    to make vacuous.
    """

    __slots__ = ("name", "enrol", "enrol_reasons", "send", "send_reasons",
                 "eligibility_reasons")

    def __init__(self, name, enrol, send):
        self.name = name
        self.enrol = enrol.action
        self.enrol_reasons = tuple(enrol.reasons)
        self.send = send.action
        self.send_reasons = tuple(send.reasons)
        # The eligibility slots that actually fired, taken from the SEND
        # verdict: it is the one with no hold rules in it, so what is left is
        # exactly the permanent refusals and their authorities.
        self.eligibility_reasons = tuple(
            send.detail.get("eligibility_reasons") or ())

    @property
    def blocked(self):
        return self.enrol == suppression.BLOCK or self.send == suppression.BLOCK

    @property
    def verdicts(self):
        """What must be identical across the restore."""
        return (self.enrol, self.enrol_reasons, self.send, self.send_reasons)

    def authorities(self):
        return sorted({authority_of(r) for r in self.eligibility_reasons})

    def describe(self):
        return "%s  enrol=%s%s  send=%s%s" % (
            self.name, self.enrol, list(self.enrol_reasons),
            self.send, list(self.send_reasons))


def member_name(rec, contact, index):
    key = (contact or {}).get("key")
    if not key:
        # A contact with no key cannot be named by its key, and two of them on
        # one record would collide. The position is stable within a census and
        # is reported as what it is.
        key = "#%d" % index
    return "%s%s%s" % ((rec or {}).get("id") or "?", MEMBER_SEP, key)


def census(state_dir, touches=None, config=None, now=None):
    """Every member in `state_dir`, by name, with its verdict.

    Points the whole store at `state_dir` for the duration - the agency index,
    like every other state file, resolves beside `store.queue_path()` and so
    follows it - and puts the environment back in a `finally`.

    Returns `(members, consulted)`. `consulted` is
    `suppression.consultations()` for this census, so a caller can prove the
    module was ASKED rather than inferring it from a verdict. Four controls in
    this repository have already been found unable to fail and the usual
    mechanism is a guard nobody called.
    """
    touches = touches or {}
    members = {}
    put_back = store.use_directory(state_dir)
    try:
        suppression.reset_consultations()
        for rec in store.load():
            for index, contact in enumerate(rec.get("contacts") or []):
                name = member_name(rec, contact, index)
                if name in members:
                    raise SystemExit(
                        "REFUSING: two members are both named %r in %s. A "
                        "census compared by name cannot hold a duplicate "
                        "name - one of the two would silently stand in for "
                        "the other." % (name, state_dir))
                enrol = suppression.decide(
                    rec, contact, config=config, now=now,
                    provider_touches=touches.get(name),
                    scope=suppression.SCOPE_ENROL)
                send = suppression.decide(
                    rec, contact, config=config, now=now,
                    scope=suppression.SCOPE_SEND)
                members[name] = Member(name, enrol, send)
        consulted = suppression.consultations()
    finally:
        put_back()
    return members, consulted


# --------------------------------------------------------------- comparison


class Report:
    """The drill's answer. `ok` is False unless every check below passed."""

    def __init__(self):
        self.lost_blocks = []       # BLOCK before, absent after. THE FAILURE.
        self.lost_members = []      # present before, absent after, any verdict
        self.new_members = []       # absent before, present after
        self.changed = []           # (name, before, after)
        self.weakened = []          # (name, before, after) - BLOCK/HOLD -> ALLOW
        self.refusals = []          # a reason the drill will not report a pass
        self.before_blocks = []
        self.after_blocks = []
        self.members_before = 0
        self.members_after = 0
        self.by_authority = {}
        self.archive = None
        self.restored_into = None
        self.consulted_before = 0
        self.consulted_after = 0

    @property
    def ok(self):
        return not (self.lost_blocks or self.lost_members or self.changed
                    or self.weakened or self.refusals)

    def lines(self, verbose=False):
        out = ["SUPPRESSION RESTORE DRILL %s"
               % ("PASSED" if self.ok else "FAILED")]
        if self.archive:
            out.append("  archive            %s" % self.archive)
        if self.restored_into:
            out.append("  restored into      %s" % self.restored_into)
        out.append("  members            %d before, %d after"
                   % (self.members_before, self.members_after))
        out.append("  suppression asked  %d times before, %d after"
                   % (self.consulted_before, self.consulted_after))
        out.append("  BLOCK rows         %d before, %d after"
                   % (len(self.before_blocks), len(self.after_blocks)))
        out.append("  LOST BLOCK rows    %d %s"
                   % (len(self.lost_blocks), self.lost_blocks or ""))
        out.append("  lost members       %d %s"
                   % (len(self.lost_members), self.lost_members or ""))
        out.append("  unexpected members %d %s"
                   % (len(self.new_members), self.new_members or ""))
        out.append("  CHANGED verdicts   %d" % len(self.changed))
        for name, before, after in self.changed:
            out.append("      %s  %s -> %s" % (name, before[0], after[0]))
            out.append("          reasons %s -> %s"
                       % (list(before[1]), list(after[1])))
        out.append("  WEAKENED to ALLOW  %d %s"
                   % (len(self.weakened), [n for n, _b, _a in self.weakened] or ""))
        for group in (IN_ARCHIVE, IN_GIT, NOWHERE_ELSE, UNCLASSIFIED):
            names = self.by_authority.get(group) or []
            if names:
                out.append("  authority %-22s %d BLOCK row(s) %s"
                           % (group, len(names), names if verbose else ""))
        for reason in self.refusals:
            out.append("  REFUSED: %s" % reason)
        if verbose:
            out.append("  BLOCK before: %s" % self.before_blocks)
            out.append("  BLOCK after:  %s" % self.after_blocks)
        if self.ok:
            out.append("  every BLOCK row came back, by name, with the same "
                       "verdict from src/suppression.py.")
        return out


def compare(before, after, consulted_before=(), consulted_after=()):
    """Two censuses, by NAME. Returns a `Report`.

    The ordering of the checks is the ordering of how much each failure would
    cost. A lost BLOCK row is first because it is the one with a named victim.
    """
    report = Report()
    report.members_before = len(before)
    report.members_after = len(after)
    report.consulted_before = len(consulted_before)
    report.consulted_after = len(consulted_after)
    report.before_blocks = sorted(n for n, m in before.items() if m.blocked)
    report.after_blocks = sorted(n for n, m in after.items() if m.blocked)

    # 1. A BLOCK row that is not in the restored census. The whole reason this
    #    file exists: an absent row is not a row that passes, it is a person
    #    the restored estate believes it has never heard of.
    report.lost_blocks = sorted(set(report.before_blocks) - set(after))

    # 2. Any member that did not come back, whatever it said. A HOLD that
    #    vanishes is a person who gets a full new sequence.
    report.lost_members = sorted(set(before) - set(after))
    report.new_members = sorted(set(after) - set(before))

    # 3. A verdict that changed. Equal sets of names with different answers is
    #    exactly the failure a count-based comparison cannot see.
    for name in sorted(set(before) & set(after)):
        if before[name].verdicts != after[name].verdicts:
            report.changed.append((name, before[name].verdicts,
                                   after[name].verdicts))
            if (after[name].enrol == suppression.ALLOW
                    and before[name].enrol != suppression.ALLOW):
                report.weakened.append((name, before[name].enrol,
                                        after[name].enrol))

    # 4. Where the surviving refusals' authority lives. Reported, not failed:
    #    a BLOCK resting on a file outside the archive is not WRONG, it is
    #    UNPROVEN by this drill, and saying so is the difference between a
    #    measurement and a reassurance.
    groups = {}
    for name in report.before_blocks:
        for group in before[name].authorities():
            groups.setdefault(group, []).append(name)
    report.by_authority = {k: sorted(v) for k, v in groups.items()}

    # 5. The vacuous-pass traps, closed explicitly.
    if not before:
        report.refusals.append(
            "the source census is empty. A drill over nobody cannot fail, and "
            "a pass here would mean only that nothing was asked.")
    elif not report.before_blocks:
        report.refusals.append(
            "the source census holds no BLOCK row. There is no suppression to "
            "lose, so a pass proves nothing about suppression.")
    expected = 2 * len(before)
    if len(consulted_before) != expected:
        report.refusals.append(
            "suppression was asked %d times for %d members; %d were expected "
            "(one SCOPE_ENROL and one SCOPE_SEND each). A verdict nobody "
            "asked for is not a refusal."
            % (len(consulted_before), len(before), expected))
    if not suppression.UNKNOWN_IS_NOT_A_PASS:
        report.refusals.append(
            "suppression.UNKNOWN_IS_NOT_A_PASS is False, so an unknown touch "
            "history reads as ALLOW and every verdict collected here answers "
            "a different question from the one reported.")
    return report


# ------------------------------------------------------------------ driving


def _backup_module():
    """`scripts/server/backup.py` imported, so the LIVE engine is used.

    Imported rather than reimplemented and rather than shelled out to: this
    drill's claim is about the backup path that actually runs, and a second
    tar-and-compare written here would be a drill of itself.
    """
    spec = importlib.util.spec_from_file_location("resonate_backup",
                                                  BACKUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _refuse_production(state_dir):
    resolved = os.path.abspath(state_dir)
    for protected in store.protected_directories():
        if resolved == protected or resolved.startswith(protected + os.sep):
            raise SystemExit(
                "REFUSING: %s is production state. This drill reads a fixture "
                "or a copy. Point --state-dir at one." % resolved)


def _load_touches(path):
    """`{member name: provider touch dict}`, or `{}`.

    Deliberately NOT restored from the archive and deliberately an argument:
    the provider's touch history is not in `work/` at all, so holding it
    constant across the two censuses is what makes the restored STATE the only
    variable. A snapshot that moved between the two would make a changed
    verdict unattributable.
    """
    if not path:
        return {}
    with io.open(path, encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise SystemExit("REFUSING: %s is not an object of "
                         "{member: touches}." % path)
    return loaded


def run(state_dir, into=None, restored=None, touches=None, keep=False):
    """The drill. Returns `(report, restored_dir)`.

    `restored` skips the backup and restore and compares against a tree that
    is already on disk, which is how the mutation proof is run: restore once,
    remove a BLOCK row from the restored copy, point this at it.
    """
    _refuse_production(state_dir)
    if restored:
        _refuse_production(restored)
    if not os.path.isdir(state_dir):
        raise SystemExit("REFUSING: %s does not exist. There is no state to "
                         "drill." % state_dir)

    archive = None
    scratch = None
    if restored is None:
        if not into:
            raise SystemExit("REFUSING: --into is required unless --restored "
                             "names a tree to compare against.")
        _refuse_production(into)
        backup = _backup_module()
        archive = backup.backup(state_dir, into)
        scratch = restored = tempfile.mkdtemp(
            prefix="resonate-suppression-restore-", dir=into)
        # `restore` refuses a non-empty destination; mkdtemp made it empty.
        backup.restore(archive, restored)

    try:
        touches = _load_touches(touches) if isinstance(touches, str) else (touches or {})
        before, asked_before = census(state_dir, touches)
        after, asked_after = census(restored, touches)
        report = compare(before, after, asked_before, asked_after)
        report.archive = archive
        report.restored_into = restored
        return report, restored
    finally:
        if scratch and not keep:
            shutil.rmtree(scratch, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Prove a restore does not lose the suppressions")
    ap.add_argument("--state-dir", required=True,
                    help="the state directory to back up and drill. Never "
                         "production work/.")
    ap.add_argument("--into", help="where the archive is written and the "
                                   "restore scratch directory is made")
    ap.add_argument("--restored", help="compare against this already-restored "
                                       "tree instead of taking a new backup")
    ap.add_argument("--touches", help="JSON {member: provider touch dict}, "
                                      "held constant across both censuses")
    ap.add_argument("--keep", action="store_true",
                    help="leave the restored scratch directory in place")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print member names rather than only totals")
    args = ap.parse_args(argv)

    report, restored = run(args.state_dir, into=args.into,
                           restored=args.restored, touches=args.touches,
                           keep=args.keep)
    print("\n".join(report.lines(verbose=args.verbose)))
    if args.keep and restored:
        print("  kept %s" % restored)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
