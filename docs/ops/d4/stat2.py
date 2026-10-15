"""Read the index BEFORE any status/diff runs, then correlate.

The question: for a tree whose every text file is CRLF on disk while every
blob is LF, which files does `git status` report, and what distinguishes them?
Candidate discriminators measured per file: index mtime vs disk mtime, index
size vs disk size.
"""
import os, subprocess, sys

tree = sys.argv[1]

def git(*a):
    r = subprocess.run(["git", "--no-optional-locks", "-C", tree, *a],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout

# 1. index state, read with ls-files --debug, which does NOT refresh.
rows, cur = [], None
for line in git("ls-files", "--debug", "-s").splitlines():
    if not line.startswith("  "):
        meta, name = line.split("\t", 1)
        cur = {"name": name, "blob": meta.split()[1]}
        rows.append(cur)
    elif "mtime:" in line:
        s, ns = line.split("mtime:")[1].strip().split(":")
        cur["ix_mtime"] = (int(s), int(ns))
    elif "size:" in line:
        cur["ix_size"] = int(line.split("size:")[1].split()[0])

# 2. disk state
for r in rows:
    full = os.path.join(tree, r["name"].replace("/", os.sep))
    try:
        st = os.stat(full)
    except OSError:
        r["disk_size"] = None; continue
    r["disk_size"] = st.st_size
    r["disk_mtime"] = (int(st.st_mtime), int(round((st.st_mtime % 1) * 1e9)))

# 3. what status says (this is the step that rewrites the index, so it is last)
reported = set(l[3:].strip().strip('"')
               for l in git("status", "--short").splitlines() if l.strip())

size_ok  = lambda r: r.get("ix_size") == r.get("disk_size")
mtime_ok = lambda r: r.get("ix_mtime", (0, 0))[0] == r.get("disk_mtime", (1, 1))[0]

print("tracked entries            : %d" % len(rows))
print("git status reported        : %d" % len(reported))
print()
print("%-34s %8s %8s" % ("", "reported", "silent"))
for label, pred in (("index size == disk size", size_ok),
                    ("index mtime sec == disk mtime sec", mtime_ok)):
    t = [r for r in rows if pred(r)]
    f = [r for r in rows if not pred(r)]
    print("%-34s   T:%4d/%4d  F:%4d/%4d" % (
        label,
        sum(1 for r in t if r["name"] in reported), len(t),
        sum(1 for r in f if r["name"] in reported), len(f)))
print()
bad_mtime = [r for r in rows if not mtime_ok(r)]
print("entries whose index mtime SEC differs from disk : %d" % len(bad_mtime))
print("  of those, reported modified                   : %d" %
      sum(1 for r in bad_mtime if r["name"] in reported))
print()
for r in rows:
    if r["name"] in reported:
        print("REPORTED example : %s" % r["name"])
        print("   index mtime %s  disk mtime %s" % (r.get("ix_mtime"), r.get("disk_mtime")))
        print("   index size  %s  disk size  %s" % (r.get("ix_size"), r.get("disk_size")))
        break
for r in rows:
    if r["name"] not in reported and r["name"].endswith(".md"):
        print("SILENT example   : %s" % r["name"])
        print("   index mtime %s  disk mtime %s" % (r.get("ix_mtime"), r.get("disk_mtime")))
        print("   index size  %s  disk size  %s" % (r.get("ix_size"), r.get("disk_size")))
        break
