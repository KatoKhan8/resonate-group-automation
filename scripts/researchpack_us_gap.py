"""Is the US supply already packed? Asked of the caches, not of a headline.

LANE K, 2026-09-25. The brief states that zero of the 32,951 sourced domains
carry a research pack and that the 439 packed domains are disjoint from the
supply. This re-measures it against the files, because this project's
recurring failure is a headline number from a stage that had not asked the
next stage's question, and because the whole lane is justified by it.

Reads every `work/research*.json` cache EXCEPT the quarantined pre-fix pilot
cache - `researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json`, where 50 of 71
job rows belonged to a different company - and except this lane's own output.
A cache entry counts as packed only when it carries at least one fact: an
entry with an empty `facts` list is a 30-day promise that the domain has been
researched, and it has not been.
"""
import argparse
import glob
import json
import os


def supply(path):
    everything, us = set(), set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            domain = str(rec.get("domain") or "").lower()
            everything.add(domain)
            if rec.get("country") == "United States":
                us.add(domain)
    return everything, us


#: Never read. 50 of its 71 job rows belonged to a different company, which
#: is why it carries DO-NOT-SERVE in its own filename.
QUARANTINED = "PRE-FIX-DO-NOT-SERVE"


def packed(work, skip=("us-cold",)):
    found, per = set(), {}
    for path in sorted(glob.glob(os.path.join(work, "research*.json"))):
        base = os.path.basename(path)
        if QUARANTINED in base or any(s in base for s in skip):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        domains = set()
        for key, entry in data.items():
            if isinstance(entry, dict) and entry.get("facts"):
                domains.add(str(entry.get("domain")
                                or str(key).split("::")[0]).lower())
        if domains:
            per[base] = len(domains)
        found |= domains
    return found, per


def named_anywhere(work):
    """Every domain named by ANY research artefact, cache-shaped or report.

    Wider than `packed` on purpose. The brief says 439 domains are packed;
    the servable caches carry far fewer, because most of the artefacts in
    `work/` are RUN REPORTS (`summary`/`packs`/`charges`) rather than caches
    a pack build can be served from. The two numbers answer different
    questions and this prints both so neither is mistaken for the other.
    """
    found = {}
    for path in sorted(glob.glob(os.path.join(work, "research*.json"))):
        base = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        domains = set()
        packs = data.get("packs")
        if isinstance(packs, dict):
            domains = {str(k).split("::")[0].lower() for k in packs}
        elif isinstance(packs, list):
            domains = {str((p or {}).get("domain") or "").lower() for p in packs}
        else:
            domains = {str((v or {}).get("domain")
                           or str(k).split("::")[0]).lower()
                       for k, v in data.items()
                       if isinstance(v, dict) and "facts" in v}
        domains.discard("")
        if domains:
            found[base] = domains
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--supply", required=True)
    ap.add_argument("--work", required=True)
    args = ap.parse_args(argv)

    everything, us = supply(args.supply)
    found, per = packed(args.work)
    print("caches read (%s never opened):" % QUARANTINED)
    for name, count in sorted(per.items()):
        print("  %-58s %5d" % (name, count))
    print("domains with at least one fact, across them all   %5d" % len(found))
    print("  ...that appear anywhere in qualified-supply     %5d"
          % len(found & everything))
    print("  ...that appear in the US slice                  %5d"
          % len(found & us))
    print("qualified-supply rows %d, US slice %d" % (len(everything), len(us)))

    wide = named_anywhere(args.work)
    union = set()
    print("")
    print("every domain NAMED by any research artefact, reports included:")
    for name, domains in sorted(wide.items()):
        union |= domains
        print("  %-58s %5d%s" % (name, len(domains),
                                 "   QUARANTINED" if QUARANTINED in name else ""))
    print("  union                                                     %5d"
          % len(union))
    print("  ...in qualified-supply  %5d      ...in the US slice  %5d"
          % (len(union & everything), len(union & us)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
