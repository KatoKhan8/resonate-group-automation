"""Is the reported set exactly git's RACILY-CLEAN set?

git/read-cache.c, is_racy_timestamp(): an index entry whose recorded mtime is
not strictly older than the index FILE's own mtime cannot be trusted, because
the file might have been rewritten within the same clock tick. Those entries
are content-compared. Every other entry is trusted on stat alone, and an
autocrlf=true checkout recorded the CRLF file's OWN size and mtime, so stat
always matches and the content is never looked at.

Read in this order: index file mtime, ls-files --debug (no refresh), THEN
status (which rewrites the index and destroys the evidence).
"""
import os, subprocess, sys

tree = sys.argv[1]
def git(*a):
    r = subprocess.run(["git", "--no-optional-locks", "-C", tree, *a],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout

gitdir = open(os.path.join(tree, ".git")).read().split("gitdir:")[1].strip()
ix_file_mtime = int(os.stat(os.path.join(gitdir, "index")).st_mtime)

rows, cur = [], None
for line in git("ls-files", "--debug", "-s").splitlines():
    if not line.startswith("  "):
        meta, name = line.split("\t", 1)
        cur = {"name": name}; rows.append(cur)
    elif "mtime:" in line:
        cur["sec"] = int(line.split("mtime:")[1].strip().split(":")[0])

racy = set(r["name"] for r in rows if r.get("sec", 0) >= ix_file_mtime)
reported = set(l[3:].strip().strip('"')
               for l in git("status", "--short").splitlines() if l.strip())

print("index FILE mtime (sec)         : %d" % ix_file_mtime)
print("tracked entries                : %d" % len(rows))
print("RACY (entry mtime >= index mtime): %d" % len(racy))
print("git status reported modified    : %d" % len(reported))
print()
print("reported SUBSET of racy?        : %s" % (reported <= racy))
print("racy and not reported           : %d" % len(racy - reported))
print("reported and not racy           : %d" % len(reported - racy))
if reported - racy:
    print("   e.g. %s" % sorted(reported - racy)[:3])
print()
print("So the files git never content-checks: %d of %d (%.0f%%)" %
      (len(rows) - len(racy), len(rows), 100.0 * (len(rows) - len(racy)) / len(rows)))
