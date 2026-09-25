"""Does this tracked file name anybody? Asked BEFORE it is committed.

LANE O, 2026-09-25. Four agents leaked today. `work/` is gitignored and
`docs/` is not, so a number copied out of a report into a document is the
whole mechanism.

## IT CHECKS EVERY VALUE, NOT A SAMPLE

The habit this guards against is a filter written from the three examples
somebody happened to look at, which then passes because the leak was the
fourth. So the haystack is the ENTIRE cohort - every domain, every company
name, every email local-part, every contact surname - and the needle is the
file. One IPv4 has already reached a tracked file in this repository
because it was checked after the command rather than before.

## AND IT FAILS ON THE COMPANY NAME TOO, NOT ONLY THE DOMAIN

A domain is obvious and a company name is not: `single_word_top` in the
anchor report is a list of the words rule 1 matched on, and on this cohort
some of those words ARE company names - a one-word brand whose site says it
back. Printing that list into a document is a leak that looks like a
statistic. Tokens under `--min-len` are skipped, because a company named
`Group` would otherwise refuse every document ever written.
"""
import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A word, a domain or an address. THE TRAILING PUNCTUATION MATTERED: the
#: first version ended in `[A-Za-z0-9._-]*`, so a sentence's full stop came
#: into the token and the cohort contributed needles spelled `company.` and
#: `filter.` - which then matched this file's own prose and refused it.
WORD = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")

#: Endings stripped before asking whether a word is repository vocabulary.
#: `agents`, `roots` and `consolidated` are all ordinary words this
#: repository uses in the singular or the stem, and all three refused a
#: script until the inflection was handled.
SUFFIXES = ("s", "es", "ed", "ing", "er", "ers", "d", "ly")


def in_vocabulary(word, vocab):
    if word in vocab:
        return True
    for suffix in SUFFIXES:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if len(stem) >= 3 and (stem in vocab or stem + "e" in vocab):
                return True
    return False


#: A company-name token shared by more than this many companies is ordinary
#: English, not an identifier. THE FIRST VERSION OF THIS FILE HAD NO SUCH
#: RULE and its own control string - "a document about snippet caps and
#: anchor lengths only" - tripped two needles out of 81,923, because every
#: token of every company name was a needle and some companies are named
#: after ordinary words. A filter that refuses every document refuses
#: nothing: it gets switched off, and then it is not a filter.
#:
#: Distinctiveness is the actual question. A token belonging to one company
#: NAMES that company; a token belonging to ninety names an industry.
DISTINCTIVE_AT_MOST = 2


def needles(cohort, min_len=5, exempt=()):
    """Every string in the cohort a document must not carry.

    Whole values always - domain, domain stem, contact key, local-part,
    full company name, surname, LinkedIn url and slug. Single tokens out of
    a company name only when they are DISTINCTIVE and not already part of
    this repository's own vocabulary, see above.
    """
    exempt = set(exempt)
    out = {}
    token_owners = {}
    with open(cohort, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            domain = str(row.get("domain") or "").strip().lower()
            if len(domain) >= min_len:
                out.setdefault(domain, "domain")
                stem = domain.rsplit(".", 1)[0]
                if len(stem) >= min_len:
                    out.setdefault(stem, "domain stem")
            email = str(row.get("email") or "").strip().lower()
            if email:
                out.setdefault(email, "contact key")
                local = email.split("@")[0]
                if len(local) >= min_len:
                    out.setdefault(local, "email local-part")
            company = str(row.get("company") or "").strip().lower()
            if len(company) >= min_len:
                out.setdefault(company, "company name")
            surname = str(row.get("last_name") or "").strip().lower()
            if len(surname) >= min_len:
                out.setdefault(surname, "surname")
            for token in WORD.findall(company):
                token = token.lower()
                if len(token) >= min_len:
                    token_owners.setdefault(token, set()).add(
                        domain or company)
            url = str(row.get("linkedin") or "").strip().lower()
            if url:
                out.setdefault(url, "linkedin url")
                slug = url.rstrip("/").rsplit("/", 1)[-1]
                if len(slug) >= min_len:
                    out.setdefault(slug, "linkedin slug")
    for token, owners in token_owners.items():
        if len(owners) <= DISTINCTIVE_AT_MOST:
            out.setdefault(token, "distinctive company-name token")

    # THE EXEMPTION IS BY SHAPE, NOT BY CATEGORY, and the first version got
    # this wrong. It exempted only company-name tokens, and the check then
    # refused four of its own scripts over `branch`, `count`, `quote`,
    # `known`, `state` and `written` - real surnames and real email
    # local-parts in this cohort that are also ordinary words this
    # repository has used for months.
    #
    # A needle that is ONE BARE WORD is only as identifying as the word. A
    # needle carrying an @, a dot or a space is a contact key, a domain, a
    # url or a multi-word company name: those identify somebody however
    # common their parts are, and NOTHING exempts them.
    kept = {}
    for needle, kind in out.items():
        bare = not any(c in needle for c in "@. /")
        if bare and in_vocabulary(needle, exempt):
            continue
        if " " in needle and "@" not in needle and "/" not in needle:
            # A MULTI-WORD NAME MADE ENTIRELY OF COMMON WORDS IDENTIFIES
            # NOBODY, and one in this cohort is spelled out of two of the
            # commonest words in English - it matched this file's own prose.
            # A multi-word name has to contribute at least one word this
            # repository has never used before it can refuse a document.
            words = [w for w in WORD.findall(needle) if len(w) >= 3]
            if words and all(in_vocabulary(w, exempt) for w in words):
                continue
        kept[needle] = kind
    return kept


#: Vocabulary is gathered from THREE letters up, not from `--min-len` up.
#: A multi-word company name is exempt only when every one of its words is
#: ordinary, and the commonest words in English are four letters or fewer -
#: gathering at 5 left `that` unknown and a two-word name built from `that`
#: and `company` refused this file's own prose.
VOCAB_MIN_LEN = 3


def repo_vocabulary(repo, min_len=VOCAB_MIN_LEN, exclude=()):
    """Every word this repository already used BEFORE the cohort existed.

    THE EXEMPTION, DERIVED RATHER THAN HAND-LISTED. A hand-list is written
    from the words somebody happened to hit and grows one false positive at
    a time; this one is a rule. `src/**/*.py` and `CLAUDE.md` were written
    before this cohort was sourced, so a word that is already in them is
    part of this repository's vocabulary and its presence in a document is
    not evidence the cohort leaked. A company genuinely named after such a
    word is protected anyway: its DOMAIN, contact key, full name, surname
    and LinkedIn slug are whole-value needles and are never exempted here.

    Only single distinctive tokens are eligible for this exemption, which is
    the narrowest place it can apply and the only place the false positives
    were coming from.
    """
    vocab = set()
    # THE FILES UNDER TEST ARE EXCLUDED FROM THEIR OWN EXEMPTION. Without
    # this, a document that leaks a name puts that name into the vocabulary
    # that decides whether it leaked, and the check passes because it
    # leaked. `scripts/` is worth reading for vocabulary - it is the same
    # kind of prose as `src/` - but only once it cannot vouch for itself.
    skip = {os.path.abspath(p) for p in exclude}
    roots = [os.path.join(repo, "src"), os.path.join(repo, "tests"),
             os.path.join(repo, "scripts")]
    files = [os.path.join(repo, "CLAUDE.md")]
    for root in roots:
        for here, _dirs, names in os.walk(root):
            if "__pycache__" in here:
                continue
            files.extend(os.path.join(here, n) for n in names
                         if n.endswith(".py"))
    files = [p for p in files if os.path.abspath(p) not in skip]
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
        except OSError:
            continue
        for token in WORD.findall(text):
            if len(token) >= min_len:
                vocab.add(token.lower())
    return vocab


#: Kept as a floor under the derived vocabulary, for the category words the
#: report itself has to print. Visible and arguable rather than a threshold
#: quietly letting things through.
ALLOWED = {
    "marketing", "advertising", "digital", "creative", "media", "design",
    "group", "agency", "brand", "branding", "studio", "global", "direct",
    "solutions", "services", "software", "partners", "communications",
    "consulting", "technology", "content", "strategy", "collective",
    "social", "teams", "across", "company", "united", "states", "america",
    "north", "south", "first", "national", "premier", "advantage",
    "network", "systems", "products", "resources", "capital", "health",
    "energy", "financial", "insurance", "security", "research", "science",
    "education", "learning", "family", "community", "center", "centre",
    "international", "associates", "consultants", "enterprises", "holdings",
    "industries", "management", "development", "production", "productions",
    "project", "projects", "leader", "leads", "market", "markets", "point",
    "prime", "pride", "print", "press", "pulse", "reach", "story", "stories",
    "vision", "impact", "launch", "spark", "bright", "clear", "smart",
    "simple", "modern", "inspire", "elevate", "engage", "connect",
    "creative", "originals", "signs", "budget", "sourcing", "thanks",
    # Added after the check refused real files over them, each because the
    # only places this repository uses the word are the files under test -
    # which are excluded from the derived vocabulary so they cannot vouch
    # for themselves. `consolidated` is the crawler's own verb for turning
    # a log into a cache; `agence` is in lane K's CATEGORY_WORDS. In both
    # cases a company's FULL domain, contact key and full name stay needles
    # and are never exempt, so what is waived here is the bare word only.
    "consolidated", "consolidate", "agence",
}


def scan(text, hay, min_len):
    """The ONE matching path. Both the self-test and the real check use it,
    because a self-test that exercises a different path proves something
    about the double."""
    text = str(text or "").lower()
    tokens = {t.lower() for t in WORD.findall(text)
              if len(t) >= min_len and t.lower() not in ALLOWED}
    return sorted({(n, hay[n]) for n in hay
                   if n not in ALLOWED
                   and (n in tokens or (" " in n and n in text))})


def self_test(hay, min_len):
    """Fails loudly if the matcher cannot find a needle, AND if it finds one
    that is not there. The second half is the control: without it this
    passes for a `scan` that returns every needle every time."""
    probe = next(k for k, v in hay.items() if v == "domain")
    found = scan("a document that mentions %s in passing" % probe, hay,
                 min_len)
    if not any(n == probe for n, _k in found):
        return "the matcher does not find a known cohort domain"
    control = scan("a document about snippet caps and anchor lengths only",
                   hay, min_len)
    if control:
        return ("the matcher fires on text carrying no cohort value: %d "
                "spurious hit(s)" % len(control))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--min-len", type=int, default=5)
    args = ap.parse_args(argv)

    vocab = repo_vocabulary(REPO, exclude=args.file)
    hay = needles(args.cohort, args.min_len, exempt=vocab)
    print("%d word(s) of repository vocabulary (the %d file(s) under test "
          "excluded from it) exempt single tokens; %d distinct string(s) "
          "from the cohort must not appear"
          % (len(vocab), len(args.file), len(hay)))

    # THE SELF-TEST, BEFORE THE FIRST REAL CHECK, against EVERY value rather
    # than the three somebody looked at. One IPv4 reached a tracked file in
    # this repository because the filter was checked after the command.
    failure = self_test(hay, args.min_len)
    if failure:
        print("SELF-TEST FAILED: %s" % failure)
        return 2
    print("self-test: finds a known cohort domain in a probe string, and "
          "fires on nothing in a control string (needles withheld here)")

    bad = 0
    for path in args.file:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        hits = scan(text, hay, args.min_len)
        if hits:
            bad += len(hits)
            print("")
            print("LEAK in %s: %d value(s)" % (path, len(hits)))
            for needle, kind in hits[:40]:
                # The kind and the LENGTH, never the value. Printing it here
                # would put it in a transcript, which is the same leak one
                # step removed.
                print("  %-18s %d chars, starts %r"
                      % (kind, len(needle), needle[:2]))
        else:
            print("clean: %s" % path)
    if bad:
        print("")
        print("REFUSED: %d value(s) from the cohort appear in a tracked file"
              % bad)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
