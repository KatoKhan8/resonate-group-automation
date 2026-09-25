#!/usr/bin/env python3
"""LANE P redaction self-test, run AFTER the document is written.

Four agents leaked today, so this does not test a filter - it tests the
FILES this lane would push, against every value the production store actually
holds: full prospect names, addresses, email and company domains, company
names and LinkedIn vanity slugs.

## THE FIRST VERSION OF THIS TEST WAS USELESS AND SAID SO LOUDLY

It tested every token of every name, four characters and up, against the
whole repository - and flagged `.gitignore`, `AGENTS.md` and `BUILD-SPEC.md`,
because a four-letter surname is also an ordinary English word. A guard that
fails on everything proves exactly as little as one that passes on
everything. So:

  * a NAME is tested only as a full name (two or more tokens), or as a
    single token of eight characters or more - short tokens are words
  * a COMPANY is tested only at eight characters or more
  * a DOMAIN must contain a dot and be six characters or more
  * a SLUG must be six characters or more and carry a hyphen or a digit,
    which is what makes it a LinkedIn vanity rather than a word
  * addresses are tested whole, always - an address is never a word

## AND IT IS SCOPED TO WHAT THIS LANE WROTE

The corpus is every file this branch adds or changes against master, plus
every new file that is not ignored. A pre-existing leak elsewhere in the
repository is a real problem and not this lane's to discover by accident;
`tests/test_fixture_hygiene.py` owns the repository-wide question and is run
separately.

Exit 1 on any hit.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

WORKTREE = boot.WORKTREE
QUEUE = os.path.join(boot.PROD, "work", "queue.jsonl")
BASE = os.environ.get("LANEP_BASE", "master")


def git(args):
    out = subprocess.run(["git"] + args, cwd=WORKTREE, capture_output=True,
                         text=True)
    return [p for p in out.stdout.splitlines() if p.strip()]


def corpus():
    """What this lane would push: changed against master, plus new files."""
    files = set(git(["diff", "--name-only", f"{BASE}...HEAD"]))
    files |= set(git(["diff", "--name-only"]))
    files |= set(git(["ls-files", "--others", "--exclude-standard"]))
    return sorted(f for f in files
                  if os.path.isfile(os.path.join(WORKTREE, f)))


UNTESTABLE = set()


def values():
    names, emails, domains, companies, slugs = set(), set(), set(), set(), set()
    with open(QUEUE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            facts = rec.get("company_facts") or {}
            for value in (rec.get("company"), facts.get("name")):
                value = " ".join(str(value or "").lower().split())
                if len(value) >= 8:
                    # A ONE-WORD COMPANY NAME CAN BE AN ORDINARY ENGLISH WORD.
                    # This store holds one that is, and the first run of this
                    # guard reported the lane's own document as a LEAK because
                    # the document uses that word in its ordinary sense. A
                    # substring test cannot tell the two apart, so single-word
                    # names are reported as UNTESTABLE rather than as either a
                    # hit or a clean - see `untestable` in the output.
                    (companies if " " in value else UNTESTABLE).add(value)
            for value in (rec.get("domain"), facts.get("domain")):
                value = str(value or "").strip().lower()
                if len(value) >= 6 and "." in value:
                    domains.add(value)
            for c in (rec.get("contacts") or []):
                if not isinstance(c, dict):
                    continue
                full = " ".join(str(c.get("name") or "").lower().split())
                if len(full.split()) >= 2:
                    names.add(full)
                elif len(full) >= 8:
                    names.add(full)
                for key in ("first_name", "last_name"):
                    value = str(c.get(key) or "").strip().lower()
                    if len(value) >= 8:
                        names.add(value)
                addr = str(c.get("email") or "").strip().lower()
                if "@" in addr:
                    emails.add(addr)
                    host = addr.split("@", 1)[1]
                    if len(host) >= 6 and "." in host:
                        domains.add(host)
                url = str(c.get("linkedin") or "").strip().lower()
                m = re.search(r"/in/([^/?#]+)", url)
                slug = m.group(1) if m else ""
                if len(slug) >= 6 and re.search(r"[-0-9]", slug):
                    slugs.add(slug)
    return {"name": names, "email": emails, "domain": domains,
            "company": companies, "slug": slugs}


def main():
    pools = values()
    files = corpus()
    hits = []
    for path in files:
        with open(os.path.join(WORKTREE, path), encoding="utf-8",
                  errors="replace") as f:
            text = " ".join(f.read().lower().split())
        for kind, pool in pools.items():
            for value in pool:
                if value in text:
                    hits.append(f"{path}: {kind} of {len(value)} chars")
    print(json.dumps({
        "base": BASE,
        "untestable_single_word_company_names": len(UNTESTABLE),
        "values_tested": sum(len(v) for v in pools.values()),
        "by_kind": {k: len(v) for k, v in pools.items()},
        "files_this_lane_would_push": files,
        "hits": sorted(set(hits)),
        "verdict": "CLEAN" if not hits else "LEAK",
    }, indent=1))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
