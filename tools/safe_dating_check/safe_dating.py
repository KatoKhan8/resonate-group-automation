"""webapp/0380 - coupling-safe dating instrument.

A `git log -S<needle>` hit at commit C is confirmed as the INTRODUCTION of the
needle only if the literal occurrence count in C's blob is >= 1 AND the count in
EVERY parent of C is 0.  A root commit with count >= 1 and no parents is
CONFIRMED-INTRODUCTION by definition.

Occurrence counting is LITERAL NON-OVERLAPPING BYTE counting on the raw blob
bytes as git stores them (`git cat-file blob`), never on a decoded string, so
the LF/CRLF flavour of the blob cannot move the number.  The CR count of each
blob is printed so the flavour is on the record.

Read-only against any repository: only `git rev-list`, `git log`, `git rev-parse`
and `git cat-file` are ever run.
"""

import hashlib
import subprocess
import sys

NEEDLE_ENCODING = "utf-8"

# Every blob this instrument counts a needle in, measured rather than composed.
BLOBS_COUNTED = [0]


def git(repo, args):
    """Run a git command in `repo` and return raw stdout BYTES.

    text=True would decode with the console codepage (cp1250 here) and mangle
    any non-ASCII byte, so every read is bytes and stays bytes.
    """
    proc = subprocess.run(
        ["git", "-C", repo] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", "replace").strip()
    return proc.stdout, None


def count_literal(haystack, needle):
    """Non-overlapping literal byte count. bytes.count is exactly that."""
    return haystack.count(needle)


def blob_at(repo, commit, path):
    """(blob_sha, bytes, cr_count) for `path` at `commit`, or None if absent.

    An absent path is NOT an error and NOT a zero that means anything else: it
    is reported as ABSENT and counted as 0 occurrences, which is the only
    reading that makes the parent test work across the commit that ADDS a file.
    """
    out, err = git(repo, ["rev-parse", "%s:%s" % (commit, path)])
    if out is None:
        return None
    sha = out.decode("ascii").strip()
    data, err = git(repo, ["cat-file", "blob", sha])
    if data is None:
        return None
    return sha, data, data.count(b"\r")


def parents(repo, commit):
    out, err = git(repo, ["rev-list", "--parents", "-1", commit])
    if out is None:
        raise RuntimeError("rev-list failed for %s: %s" % (commit, err))
    fields = out.decode("ascii").split()
    return fields[1:]


def log_s(repo, needle, path):
    """`git log -S<needle> -- <path>` commits, OLDEST FIRST."""
    args = ["log", "-S" + needle.decode(NEEDLE_ENCODING), "--format=%H"]
    if path is not None:
        args += ["--", path]
    out, err = git(repo, args)
    if out is None:
        raise RuntimeError("log -S failed: %s" % err)
    shas = out.decode("ascii").split()
    return list(reversed(shas))


def describe_blob(repo, commit, path, needle, label):
    BLOBS_COUNTED[0] += 1
    got = blob_at(repo, commit, path)
    if got is None:
        print("    %-24s %s blob=ABSENT(path not in commit) count=0 flavour=n/a"
              % (label, commit))
        return 0, "ABSENT"
    sha, data, cr = got
    n = count_literal(data, needle)
    flavour = "CRLF" if cr else "LF"
    print("    %-24s %s blob=%s count=%d bytes=%d CR=%d flavour=%s"
          % (label, commit, sha, n, len(data), cr, flavour))
    return n, sha


def uniqueness_precheck(repo, path, needle, ref):
    """Is the needle UNIQUE in the blob you are dating FROM?

    This is the guard the parent-count rule does not supply.  A needle that
    occurs more than once at the reference is satisfied by two different pieces
    of text, so NO dating of either one is trustworthy: refuse.
    """
    print("  UNIQUENESS PRECHECK at ref %s" % ref)
    n, sha = describe_blob(repo, ref, path, needle, "ref blob")
    if n == 0:
        print("  PRECHECK: NEEDLE-ABSENT-AT-REF -> REFUSE (nothing to date)")
        return "NEEDLE-ABSENT-AT-REF", n
    if n > 1:
        print("  PRECHECK: AMBIGUOUS-NEEDLE occurrences=%d -> REFUSE "
              "(disambiguate the needle before dating)" % n)
        return "AMBIGUOUS-NEEDLE", n
    print("  PRECHECK: UNIQUE-AT-REF occurrences=1 -> proceed")
    return "UNIQUE-AT-REF", n


def classify_commit(repo, path, needle, commit):
    """Apply the parent-count rule to ONE named commit.

    Needed because `git log -S` applies history simplification and can omit a
    merge commit entirely when the merge is TREESAME to one parent.  A commit
    absent from the -S walk is not a commit the rule cannot judge, and the
    merge treatment has to be on the record either way.
    """
    print("  CLASSIFY (direct, not via -S) %s" % commit)
    n_c, _ = describe_blob(repo, commit, path, needle, "commit blob")
    ps = parents(repo, commit)
    if not ps:
        print("    parents: NONE (root commit)")
        verdict = "CONFIRMED-INTRODUCTION" if n_c >= 1 else "MOVED-COUNT-ONLY"
        print("    => %s:%s (ROOT-COMMIT BRANCH)" % (verdict, commit))
        print()
        return verdict
    print("    parents: %s" % " ".join(ps))
    parent_counts = []
    for p in ps:
        n_p, _ = describe_blob(repo, p, path, needle, "parent blob")
        parent_counts.append((p, n_p))
    pc = ", ".join("%s=%d" % (p[:9], n) for p, n in parent_counts)
    if n_c >= 1 and all(n == 0 for _, n in parent_counts):
        print("    => CONFIRMED-INTRODUCTION:%s (count %d >= 1, every parent 0)"
              % (commit, n_c))
        verdict = "CONFIRMED-INTRODUCTION"
    else:
        print("    => MOVED-COUNT-ONLY:%s (count %d; parent counts: %s)"
              % (commit, n_c, pc))
        verdict = "MOVED-COUNT-ONLY"
    print()
    return verdict


def date_needle(repo, path, needle, ref="HEAD", precheck=True):
    """Walk the -S hits oldest-first and classify each one."""
    print("=" * 78)
    print("NEEDLE  %r  (encoding %s, %d bytes)"
          % (needle, NEEDLE_ENCODING, len(needle)))
    print("REPO    %s" % repo)
    print("PATH    %s" % path)
    print("-" * 78)

    verdict = None
    if precheck:
        verdict, _ = uniqueness_precheck(repo, path, needle, ref)
        print("-" * 78)

    hits = log_s(repo, needle, path)
    print("  -S HITS (oldest first): %d" % len(hits))
    for h in hits:
        print("      %s" % h)
    print("-" * 78)

    naive = hits[0] if hits else None
    print("  NAIVE-OLDEST-HIT: %s" % (naive or "NONE"))
    print("-" * 78)

    blobs_counted = 0
    confirmed = []
    for commit in hits:
        print("  HIT %s" % commit)
        n_c, _ = describe_blob(repo, commit, path, needle, "commit blob")
        blobs_counted += 1
        ps = parents(repo, commit)
        if not ps:
            print("    parents: NONE (root commit)")
            if n_c >= 1:
                print("    => CONFIRMED-INTRODUCTION:%s "
                      "(ROOT-COMMIT BRANCH: count>=1 and no parents)" % commit)
                confirmed.append(commit)
            else:
                print("    => MOVED-COUNT-ONLY:%s (root, count 0)" % commit)
            print()
            continue
        print("    parents: %s" % " ".join(ps))
        parent_counts = []
        for p in ps:
            n_p, _ = describe_blob(repo, p, path, needle, "parent blob")
            blobs_counted += 1
            parent_counts.append((p, n_p))
        all_parents_zero = all(n == 0 for _, n in parent_counts)
        if n_c >= 1 and all_parents_zero:
            print("    => CONFIRMED-INTRODUCTION:%s "
                  "(count %d >= 1, every parent 0)" % (commit, n_c))
            confirmed.append(commit)
        else:
            pc = ", ".join("%s=%d" % (p[:9], n) for p, n in parent_counts)
            print("    => MOVED-COUNT-ONLY:%s (count %d; parent counts: %s)"
                  % (commit, n_c, pc))
        print()

    print("-" * 78)
    print("  CONFIRMED-INTRODUCTIONS: %s"
          % (" ".join(confirmed) if confirmed else "NONE"))
    print("  DENOMINATORS: hits walked=%d  blobs counted=%d" % (len(hits), blobs_counted))
    if precheck:
        print("  PRECHECK VERDICT: %s" % verdict)
    print("=" * 78)
    print()
    return {
        "needle": needle,
        "hits": hits,
        "naive": naive,
        "confirmed": confirmed,
        "precheck": verdict,
        "blobs": blobs_counted,
    }


def sha256_of(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: safe_dating.py <repo> <path> <needle> [ref]")
        sys.exit(2)
    repo, path, needle = sys.argv[1], sys.argv[2], sys.argv[3].encode(NEEDLE_ENCODING)
    ref = sys.argv[4] if len(sys.argv) > 4 else "HEAD"
    date_needle(repo, path, needle, ref)
