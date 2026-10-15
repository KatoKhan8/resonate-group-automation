"""Read-only census: does the WORKING TREE hold the bytes the COMMIT names?

For every tracked path:
  commit_blob  = sha the commit's tree records          (git ls-tree -r HEAD)
  index_blob   = sha the index records                  (git ls-files -s)
  disk_blob    = sha1("blob <len>\0" + raw file bytes)  computed here, NO git,
                 so NO clean filter, NO autocrlf, NO stat cache: the literal
                 bytes on disk.

Only read-only git plumbing is used (ls-tree, ls-files). Neither refreshes or
rewrites an index, so another lane's tree is never mutated by looking at it.
"""
import hashlib, os, subprocess, sys, json

PREFIXES = ("src/", "scripts/", "tests/", "config/", "docs/")

def git(path, *args):
    out = subprocess.run(["git", "--no-optional-locks", "-C", path, *args],
                         capture_output=True, text=True, errors="replace")
    if out.returncode != 0:
        raise SystemExit("git %s failed in %s: %s" % (args, path, out.stderr.strip()))
    return out.stdout

def disk_blob(full):
    try:
        with open(full, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return None, None
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(raw))
    h.update(raw)
    return h.hexdigest(), raw

def census(path, limit_prefixes=True):
    head = git(path, "rev-parse", "HEAD").strip()
    commit = {}
    for line in git(path, "ls-tree", "-r", "HEAD").splitlines():
        meta, name = line.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind != "blob":
            continue
        if limit_prefixes and not name.startswith(PREFIXES):
            continue
        commit[name] = (mode, sha)
    index = {}
    for line in git(path, "ls-files", "-s").splitlines():
        meta, name = line.split("\t", 1)
        mode, sha, stage = meta.split()
        index[name] = sha
    rows = {}
    for name, (mode, sha) in commit.items():
        if mode == "120000":
            continue
        d, raw = disk_blob(os.path.join(path, name.replace("/", os.sep)))
        rows[name] = {"commit": sha, "index": index.get(name), "disk": d,
                      "crlf": (raw.count(b"\r\n") if raw else 0),
                      "lf": ((raw.count(b"\n") - raw.count(b"\r\n")) if raw else 0),
                      "size": (len(raw) if raw is not None else None)}
    return head, rows

if __name__ == "__main__":
    path = sys.argv[1]
    tag = sys.argv[2]
    head, rows = census(path)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "census-%s.json" % tag)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"path": path, "head": head, "rows": rows}, fh, indent=0, sort_keys=True)
    drift_commit = sorted(n for n, r in rows.items() if r["disk"] != r["commit"])
    drift_index  = sorted(n for n, r in rows.items() if r["disk"] != r["index"])
    idx_vs_head  = sorted(n for n, r in rows.items() if r["index"] != r["commit"])
    print("tree        %s" % path)
    print("HEAD        %s" % head)
    print("tracked (src/scripts/tests/config/docs) %d" % len(rows))
    print("disk != COMMIT blob   %d" % len(drift_commit))
    print("disk != INDEX  blob   %d" % len(drift_index))
    print("index != COMMIT blob  %d" % len(idx_vs_head))
    for n in drift_commit[:40]:
        r = rows[n]
        print("   %-55s commit=%s disk=%s crlf=%d lf=%d" %
              (n, r["commit"][:8], (r["disk"] or "MISSING")[:8], r["crlf"], r["lf"]))
    if len(drift_commit) > 40:
        print("   ... %d more, full list in %s" % (len(drift_commit) - 40, out))
