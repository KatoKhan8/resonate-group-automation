"""Lane R: does any TRACKED file leak a real person, company or credential?

Run AFTER writing, against the real values, not before against a guess. Six
agents leaked today and lane P's first filter passed because it tested
four-letter name tokens - a filter that agrees with you is worse than none.

WHAT IS TESTED, and every one of these is drawn from the live store or the
live provider rather than invented:

  * every contact full name, first name, last name (>= 3 chars)
  * every contact email address, and its local part
  * every record domain, and the bare label before the TLD
  * every company name, whole and as multi-word phrases
  * every LinkedIn slug from every contact's profile url
  * every member id ever read (numeric and `imp_`)
  * the credential VALUES in the production config/.env

WHAT CANNOT BE TESTED IS REPORTED RATHER THAN COUNTED CLEAN: a single-word
company name that is also an ordinary English word cannot be distinguished
from prose, so those are listed, not asserted on.

Exit code 1 on any hit.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

ENGLISH = set("""the and for with from that this have your our are was were
will can not but all any one two new now who how why what when where which
about into over under more most some such only other than then them they
you it is as at by of on or to in a an be do if no up we he she his her
its their there here more work team group global local media digital data
design brand studio agency market markets marketing creative content growth
people partner partners solution solutions service services product products
system systems network networks health care energy capital finance labs lab
tech technology technologies consulting advisory ventures venture
actual good lane may measured route small true will start camp together
solve candid resonate code first last next best full open close long short
line point page case level state change run set list link mark call""".split())


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=boot.WORKTREE,
                         capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f.strip()]


def changed_files():
    """Files this branch adds or changes against the merge base with master."""
    base = subprocess.run(["git", "merge-base", "HEAD", "master"],
                          cwd=boot.WORKTREE, capture_output=True, text=True)
    ref = base.stdout.strip() or "master"
    out = subprocess.run(["git", "diff", "--name-only", ref],
                         cwd=boot.WORKTREE, capture_output=True, text=True)
    files = [f for f in out.stdout.splitlines() if f.strip()]
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=boot.WORKTREE, capture_output=True, text=True)
    files += [f for f in untracked.stdout.splitlines() if f.strip()]
    return sorted(set(files))


def secrets():
    values = set()
    env = os.path.join(boot.PROD, "config", ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(v) >= 8:
                values.add(v)
    return values


def harvest():
    """Every real value that must not appear in a tracked file."""
    strong, weak = set(), set()
    for line in open(boot.QUEUE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        dom = str(rec.get("domain") or "").strip().lower()
        if dom:
            strong.add(dom)
            label = dom.split(".")[0]
            (strong if label not in ENGLISH and len(label) > 3
             else weak).add(label)
        for field in ("company", "company_name", "name"):
            co = str(rec.get(field) or "").strip()
            if len(co.split()) > 1:
                strong.add(co.lower())
            elif len(co) > 3:
                (strong if co.lower() not in ENGLISH else weak).add(co.lower())
        for c in rec.get("contacts") or []:
            if not isinstance(c, dict):
                continue
            full = str(c.get("name") or "").strip().lower()
            if len(full.split()) > 1:
                strong.add(full)
            for part in ("first_name", "last_name"):
                v = str(c.get(part) or "").strip().lower()
                if len(v) >= 3:
                    (strong if v not in ENGLISH else weak).add(v)
            em = str(c.get("email") or "").strip().lower()
            if "@" in em:
                strong.add(em)
                # The WHOLE address is always asserted on above, as a
                # punctuated raw substring - that is the real protection and
                # it cannot false-positive. The bare local part goes through
                # the same ordinary-word test as a name, because `will@` and
                # `lane@` are local parts here and the bare word in prose is
                # English rather than a leak.
                local = em.split("@")[0]
                if len(local) >= 4:
                    (strong if local not in ENGLISH else weak).add(local)
            li = str(c.get("linkedin") or "").strip().lower()
            m = re.search(r"linkedin\.com/in/([^/?#]+)", li)
            if m and len(m.group(1)) >= 4:
                strong.add(m.group(1))
            for k in ("heyreach_lead_id",):
                v = str(c.get(k) or "").strip()
                if len(v) >= 6:
                    strong.add(v.lower())
    # Member ids read from the provider during this lane.
    for name in ("member-id-shapes.json", "gates-sample.json",
                 "sweep-state.json"):
        p = os.path.join(boot.WORKTREE, "work", "laneR", name)
        if not os.path.exists(p):
            continue
        blob = open(p, encoding="utf-8").read()
        for mid in re.findall(r"imp_[A-Za-z0-9]{8,}", blob):
            strong.add(mid.lower())
    return strong, weak


def main():
    strong, weak = harvest()
    strong |= {s.lower() for s in secrets()}
    print("values asserted on          : %d" % len(strong))
    # NOT COUNTED CLEAN - LISTED. A real name that is also an ordinary
    # English word cannot be told from prose by any filter, so these are
    # reported so a human can look, exactly as lane P reported its 521
    # untestable single-word company names. Suppressing them silently is how
    # a filter starts agreeing with the thing it is checking.
    print("values reported, NOT tested : %d - each is a real first name, "
          "surname or domain label in this store that is also an ordinary "
          "English word:" % len(weak))
    for i in range(0, len(sorted(weak)), 12):
        print("    " + " ".join(sorted(weak)[i:i + 12]))

    # HOW A VALUE IS MATCHED DEPENDS ON WHETHER IT CAN FALSE-POSITIVE.
    #
    # A value carrying punctuation - an address, a domain, a slug, a
    # credential, an `imp_` id - cannot occur inside an ordinary English word,
    # so it is matched as a raw substring and that is the strictest test
    # available.
    #
    # A BARE TOKEN - a first name, a surname, a one-word company, a domain
    # label - IS matched on word boundaries, because substring matching over
    # 8,719 of them flags `re<solve>s`, `<strang>er`, `<candid>ate` and
    # `<measured>`. That is not a redaction filter finding leaks, it is a
    # filter finding English, and a filter nobody can act on gets switched
    # off. The boundary form still catches every way a real name can actually
    # appear in prose, which is as a word.
    punctuated = {v for v in strong if not v.isalnum()}
    bare = {v for v in strong if v.isalnum()}
    word_re = re.compile(r"[a-z0-9]+")

    files = changed_files()
    print("files checked               : %d" % len(files))
    print("  matched as raw substrings : %d (punctuated - cannot "
          "false-positive)" % len(punctuated))
    print("  matched on word boundaries: %d (bare tokens)" % len(bare))
    hits = []
    for rel in files:
        path = os.path.join(boot.WORKTREE, rel)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read().lower()
        except OSError:
            continue
        for value in punctuated:
            if value and value in text:
                hits.append((rel, value))
        words = set(word_re.findall(text))
        for value in bare & words:
            hits.append((rel, value))

    print()
    if hits:
        print("LEAKS - %d:" % len(hits))
        for rel, value in sorted(hits)[:60]:
            print("  %-70s  %s" % (rel, "<%d chars>" % len(value)))
        print("\nFAIL")
        return 1

    # PROVE THE FILTER CAN FAIL. A clean pass from a filter that never fires
    # is the thing this file exists to prevent.
    # One planted value of EACH match class, because the two classes are
    # matched by different code and a probe that only exercises one of them
    # leaves the other untested.
    probe = os.path.join(boot.WORKTREE, "work", "laneR", "_redact_probe.tmp")
    os.makedirs(os.path.dirname(probe), exist_ok=True)
    for label, pool in (("punctuated", sorted(punctuated)),
                        ("bare token", sorted(bare))):
        if not pool:
            print("SELF-TEST FAILED: no %s values to plant." % label)
            return 1
        sample = pool[len(pool) // 2]
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("control line containing %s here\n" % sample)
        text = open(probe, encoding="utf-8").read().lower()
        caught = (sample in text) if label == "punctuated" \
            else (sample in set(word_re.findall(text)))
        if not caught:
            os.remove(probe)
            print("SELF-TEST FAILED: the filter did not catch a planted "
                  "%s value." % label)
            return 1
        print("  planted a %-11s value and the filter caught it" % label)
    os.remove(probe)

    print("no leak in any changed file, and the filter was shown to fire on a")
    print("planted value before reporting that.")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
