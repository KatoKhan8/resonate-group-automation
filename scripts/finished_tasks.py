#!/usr/bin/env python3
"""Which task ids already have a finished (REVIEW/DONE) copy on ANY ref.

Scans refs/remotes, refs/heads AND refs/preserve. refs/preserve matters because
a result whose branch copy was destroyed is still a result: re-running that task
duplicates work that exists. 29 such results were measured on 2026-10-12.

The scan costs one `ls-tree` per ref and there are a few thousand refs, so the
answer is CACHED against a fingerprint of every ref and the commit it points
at. If no ref moved, the classification cannot have changed. A cache that
cannot be written is not fatal - the scan just runs again.

    finished_tasks.py <repo> --has TASK-123     exit 0 if finished, 1 if not
    finished_tasks.py <repo> --list             print the whole set
    finished_tasks.py <repo> --rebuild          force a fresh scan

Decoding is explicit UTF-8 from bytes; a git failure is counted and reported,
never silently turned into an empty result, because an empty result here reads
as "no result exists" and would authorise a duplicate dispatch.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

NAMESPACES = ("refs/remotes/", "refs/heads/", "refs/preserve/")
FINISHED = ("REVIEW", "DONE")
TID = re.compile(r"(TASK-\d+)")


def git(repo, *args, timeout=900):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=timeout)
    return r.stdout.decode("utf-8", "replace"), r.returncode


def fingerprint(repo):
    out, rc = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", *NAMESPACES)
    if rc != 0:
        return None
    return hashlib.sha256(out.encode("utf-8")).hexdigest()


def scan(repo):
    refs, rc = git(repo, "for-each-ref", "--format=%(refname)", *NAMESPACES)
    if rc != 0:
        raise RuntimeError("for-each-ref failed")
    refs = [r for r in refs.split() if r and not r.endswith("/HEAD")]
    finished, failed = set(), 0
    for ref in refs:
        out, rc = git(repo, "ls-tree", "-r", "--name-only", ref, "docs/qwen-tasks/")
        if rc != 0:
            failed += 1
            continue
        for path in out.splitlines():
            parts = path.split("/")
            if len(parts) >= 4 and parts[2] in FINISHED:
                m = TID.match(parts[3])
                if m:
                    finished.add(m.group(1))
    return sorted(finished), len(refs), failed


def load(repo, cache_path, rebuild=False):
    fp = fingerprint(repo)
    if fp is None:
        raise RuntimeError("could not fingerprint refs")
    if not rebuild and os.path.exists(cache_path):
        try:
            c = json.load(open(cache_path, encoding="utf-8"))
            if c.get("fingerprint") == fp and c.get("schema") == 1:
                return set(c["finished"]), c, True
        except Exception:
            pass
    finished, nrefs, failed = scan(repo)
    c = {"schema": 1, "fingerprint": fp, "refs_scanned": nrefs,
         "refs_failed": failed, "finished": finished}
    try:
        tmp = cache_path + ".tmp"
        json.dump(c, open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, cache_path)
    except Exception:
        pass
    return set(finished), c, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--has")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    cache = a.cache or os.path.join(a.repo, ".finished-tasks-cache.json")
    try:
        s, meta, hit = load(a.repo, cache, a.rebuild)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 3
    if meta["refs_failed"]:
        print(f"WARNING: {meta['refs_failed']} refs failed to scan", file=sys.stderr)
        return 3
    if a.list:
        print(f"# refs_scanned={meta['refs_scanned']} cache_hit={hit} count={len(s)}")
        for t in sorted(s, key=lambda x: int(x.split("-")[1])):
            print(t)
        return 0
    if a.has:
        print(f"{a.has} finished={a.has in s} refs_scanned={meta['refs_scanned']} cache_hit={hit}")
        return 0 if a.has in s else 1
    print(f"finished={len(s)} refs_scanned={meta['refs_scanned']} cache_hit={hit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
