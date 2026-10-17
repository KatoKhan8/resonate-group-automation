"""webapp/0410 step 1 - the COMMA-SPLIT QUOTE PREDICATE's output, every commit.

The predicate is src/contested.py's own:  needle = entry["now"].split(",")[0]
(one site, line 983 at HEAD).  Nothing is retyped: the RECOMMENDATIONS tuple is
exec'd out of each commit's blob and the predicate applied to it.
"""
import hashlib
import subprocess
import sys

ESTATE = r"C:\Users\Zvonimir\Desktop\resonate-trees\wt-webapp-2026-10-15"
CONTESTED = "src/contested.py"


def git(args):
    p = subprocess.run(["git", "-C", ESTATE] + args, capture_output=True)
    if p.returncode != 0:
        raise SystemExit("git failed: %s\n%s" % (args, p.stderr.decode("utf-8", "replace")))
    return p.stdout


def timeline():
    out = git(["log", "--format=%H", "--", CONTESTED]).decode().split()
    return list(reversed(out))


def registry_at(sha):
    """exec ONLY the RECOMMENDATIONS literal out of the blob - no import."""
    blob = git(["cat-file", "blob", "%s:%s" % (sha, CONTESTED)])
    text = blob.decode("utf-8")
    i = text.index("RECOMMENDATIONS = (")
    # the literal ends at the first line that is exactly ")" at column 0
    j = text.index("\n)\n", i) + 3
    lit = text[i:j]
    ns = {}
    exec(compile(lit, "<registry@%s>" % sha[:9], "exec"), ns)
    return ns["RECOMMENDATIONS"], lit, blob


def main():
    print("#" * 78)
    print("# webapp/0410 STEP 1 - THE COMMA-SPLIT QUOTE PREDICATE, PER COMMIT")
    print("#" * 78)
    print()
    print("predicate source site(s) in src/contested.py at HEAD:")
    head_blob = git(["cat-file", "blob", "HEAD:%s" % CONTESTED]).decode("utf-8")
    sites = [(n + 1, l.strip()) for n, l in enumerate(head_blob.split("\n"))
             if 'split(",")[0]' in l]
    for n, l in sites:
        print("    :%-5d %s" % (n, l))
    print("    SITES: %d (if this is not 1, the predicate is not single-sourced)" % len(sites))
    print()

    tl = timeline()
    print("TIMELINE (git log --format=%%H -- %s, reversed): %d commits" % (CONTESTED, len(tl)))
    for s in tl:
        print("    %s" % s)
    print()

    allq = {}
    for sha in tl:
        recs, lit, blob = registry_at(sha)
        print("-" * 78)
        print("COMMIT %s   blob %s   %d B  CR=%d  sha256 %s"
              % (sha, git(["rev-parse", "%s:%s" % (sha, CONTESTED)]).decode().strip(),
                 len(blob), blob.count(b"\r"), hashlib.sha256(blob).hexdigest()[:16]))
        print("  RECOMMENDATIONS literal %d B sha256 %s"
              % (len(lit.encode()), hashlib.sha256(lit.encode()).hexdigest()[:16]))
        print("  entries: %d" % len(recs))
        for k, e in enumerate(recs, 1):
            now = e["now"]
            q = now.split(",")[0]
            split_fired = ("," in now)
            print("    #%d %-28s" % (k, e["path"]))
            print("        now    %r" % now)
            print("        needle %r    comma-actually-split=%s" % (q, split_fired))
            allq.setdefault(q, []).append((sha, k, e["path"], split_fired))
    print("-" * 78)
    print()
    print("DISTINCT COMMA-SPLIT QUOTE NEEDLES EVER PRODUCED: %d" % len(allq))
    for q, where in sorted(allq.items()):
        shas = ",".join("%s#%d" % (s[:9], k) for s, k, _p, _f in where)
        print("    %-58r  %s" % (q, shas))
    print()
    print("Of those, the ones where a comma was ACTUALLY present in `now`")
    print("(i.e. the split changed the string) - this is 0380's 'the comma split")
    print("is exactly the difference':")
    for q, where in sorted(allq.items()):
        if any(f for _s, _k, _p, f in where):
            print("    TRUNCATED  %r" % q)
        else:
            print("    WHOLE-NOW  %r" % q)


if __name__ == "__main__":
    main()
