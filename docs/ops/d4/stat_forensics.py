"""Why does git re-hash only part of the tree? The index's own mtime.

git's "racily clean" rule: an index entry whose recorded mtime is NOT strictly
older than the index FILE's mtime cannot be trusted on stat alone, because the
file could have been written in the same clock tick as the index. Those entries
get re-hashed. Everything older is trusted on stat alone - and since an
autocrlf=true checkout records the CRLF file's own size in the stat cache, the
stat always matches, so the content is never looked at again.
"""
import os, subprocess, sys

tree = sys.argv[1]
gitdir = open(os.path.join(tree, ".git")).read().split("gitdir:")[1].strip()
index = os.path.join(gitdir, "index")
ix_mtime = os.stat(index).st_mtime
print("index FILE mtime        : %.6f   (%s)" % (ix_mtime, index))

status = subprocess.run(["git", "--no-optional-locks", "-C", tree, "status", "--short"],
                        capture_output=True, text=True)
reported = set(l[3:].strip().strip('"') for l in status.stdout.splitlines() if l.strip())
print("git status reports      : %d modified" % len(reported))

dbg = subprocess.run(["git", "--no-optional-locks", "-C", tree, "ls-files", "--debug", "-s"],
                     capture_output=True, text=True).stdout.splitlines()
rows, cur = [], None
for line in dbg:
    if not line.startswith("  "):
        meta, name = line.split("\t", 1)
        cur = {"name": name, "blob": meta.split()[1]}
        rows.append(cur)
    elif "mtime:" in line:
        s, ns = line.split("mtime:")[1].strip().split(":")
        cur["ix_mtime"] = int(s) + int(ns) / 1e9
    elif "size:" in line:
        cur["ix_size"] = int(line.split("size:")[1].split()[0])

racy = [r for r in rows if r.get("ix_mtime", 0) >= ix_mtime]
old  = [r for r in rows if r.get("ix_mtime", 0) <  ix_mtime]
print("entries RACY (mtime >= index mtime, must be re-hashed) : %d" % len(racy))
print("entries trusted on stat alone (never re-hashed)        : %d" % len(old))
print()
rn, on = set(r["name"] for r in racy), set(r["name"] for r in old)
print("reported & racy     : %d" % len(reported & rn))
print("reported & trusted  : %d" % len(reported & on))
print("racy but NOT reported: %d   <- unchanged files, correctly silent" % len(rn - reported))
print()
print("stat cache vs disk, for files git never looks at again:")
for r in rows[:4] + rows[len(rows)//2:len(rows)//2+2]:
    full = os.path.join(tree, r["name"].replace("/", os.sep))
    if not os.path.exists(full):
        continue
    disk = os.path.getsize(full)
    print("   %-45s index_size=%-8d disk_size=%-8d match=%s" %
          (r["name"][:45], r.get("ix_size", -1), disk, r.get("ix_size") == disk))
