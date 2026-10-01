#!/usr/bin/env python3
"""Refuse a commit that introduces a REAL identity - in a file or in the message.

    py -3 scripts/pii_gate.py --install          # write the two git hooks
    py -3 scripts/pii_gate.py --staged           # what `pre-commit` runs
    py -3 scripts/pii_gate.py --message FILE     # what `commit-msg` runs
    py -3 scripts/pii_gate.py --selftest         # acceptance 3
    py -3 scripts/pii_gate.py --worktree         # scan uncommitted edits by hand

TASK-938. Three leaks on 2026-10-01, all caught by somebody LOOKING:

  * a real company name in a COMMIT MESSAGE (repaired by squashing to 36445185),
  * fixtures naming a real prospect (removed in 0afb9642),
  * a real record id and a real contact key for the SAME live row of
    `work/queue.jsonl` already on master, in `scripts/run_persona_stage.py` and
    `docs/HANDOFF-2026-10-01-LIVE.md`. Neither value is repeated here: this file
    is tracked, and a gate that quotes the identity it protects has leaked it
    itself. `--worktree` on those two files names them to whoever is looking.

`tests/test_fixture_hygiene.py` is the existing control and it is a good one, but
it has three holes this closes, and the third is the one that let the names above
land:

  TIMING     it is a unit test. It runs when somebody runs the suite, which is
             after the commit exists. A redaction filter in this repository has
             already leaked an IPv4 because it checked afterwards.
  MESSAGE    it walks files. A commit message is not a file in the tree, so a
             tree-only scan passes the first incident untouched.
  KNOWLEDGE  its lists are HAND-MAINTAINED. Nobody added the canary's record id,
             so nothing could fail. This gate derives its matchers from the LIVE CORPUS
             instead, so a value that is real is forbidden whether or not a
             human remembered it.

## THE CORPUS IS GITIGNORED, AND THAT CUTS BOTH WAYS

The real identities live in `work/` (580 MB on the operator's machine), which is
gitignored - deliberately, it is client data. Two consequences:

  * A search tool that honours `.gitignore` CANNOT SEE IT. `git grep`, and the
    repo's Grep tooling, silently match nothing there, so "I searched for PII and
    found none" is not a measurement. This module reads the files directly with
    `open()` and resolves the corpus root itself (`corpus_root`), and
    `tests/test_a_gate_refuses_a_real_identity_before_the_commit.py` proves the
    gate fires on a value that `git grep` cannot find.
  * The gate must not become the leak. It never writes a corpus value anywhere
    tracked. Comparison is by SALTED FINGERPRINT of a canonical form: the
    in-memory matcher is a set of `pg-<12 hex>`, the on-disk cache holds only
    fingerprints AND lives inside the gitignored corpus tree (and is refused if
    that tree turns out not to be ignored), and an EXCEPTION is written as a
    fingerprint plus a human reason - never as the value.

    The salt is public, as in `scripts/task189_scrub_pii.py` and
    `scripts/history_pii_scan.py`, and that is a deliberate trade: a fingerprint
    is a stable name an operator can paste into the exception file and into an
    issue. It is a name, not a cipher - a fingerprint plus a guess confirms the
    guess. That is acceptable for a value the holder already has and is why the
    cache is kept in the ignored tree as well as being hashed.

## FOUR LAYERS, AND WHY THERE ARE FOUR

  CORPUS     fingerprints of company names, domains, record ids, full contact
             names, contact keys, addresses and LinkedIn vanities read live out
             of `work/`. Catches the name nobody listed. Degrades to a loud
             warning when the corpus is absent (a fresh clone has no `work/`,
             and a machine with no corpus has nothing to leak from) - see
             `--require-corpus` to make its absence fatal.
  DENYLIST   `tests/test_fixture_hygiene.py`'s own FORBIDDEN_* tuples, IMPORTED
             rather than copied. A second list is a second thing that can
             disagree, and copying them here would make this file trip the
             scanner it serves. Covers the short, common-word identities the
             corpus layer deliberately drops (bare given names, 4-letter
             companies) because a human already reviewed each one.
  STRUCTURAL rules that need no list at all: an email on a domain that can
             resolve, a phone outside the reserved-fiction set, a
             `linkedin.com/in/<vanity>` that is not a known invention. These
             cannot rot.
  EXCEPTIONS `config/pii-gate-exceptions.txt`. A false positive must be cheap
             to clear or the gate gets deleted the first time it blocks good
             work. An entry needs a path, a token, a reviewer and a reason, and
             a malformed entry REFUSES rather than being skipped.

## WHAT IT SCANS

ADDED LINES ONLY, from `git diff --cached`, plus the whole commit message. Added
lines rather than whole files for one reason: two tracked files ALREADY carry
real identities on master (named in the third bullet above).
Whether to rewrite that history is the operator's decision (TASK-938 scope note),
and a gate that scans whole files would block every future edit to those two
files until that decision was made - which is how a gate gets turned off. Adding
the value again is still refused.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

#: As `scripts/task189_scrub_pii.py` and `scripts/history_pii_scan.py`, so one
#: entity has one name across every tool here. `pg-` rather than their `px-`
#: because this hashes the CANONICAL form (see `canon`) and a fingerprint that
#: looks like theirs but is not equal to theirs would waste somebody's hour.
SALT = "resonate-pii-salt-2026-09-16"
FP_VERSION = 2                      # bump to invalidate every cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCEPTIONS = "config/pii-gate-exceptions.txt"

#: Files that hold forbidden values BY DESIGN. Self-exemption, the same argument
#: `scripts/history_pii_scan.py` makes about its GUARD constant: the list has to
#: name what it forbids in order to forbid it. Narrow and named, never a
#: directory - as `HYGIENE_EXEMPT` in tests/test_fixture_hygiene.py.
SELF_EXEMPT = (
    "scripts/pii_gate.py",
    "tests/test_fixture_hygiene.py",
    "scripts/history_pii_scan.py",
    "scripts/task189_scrub_pii.py",
    EXCEPTIONS,
)

#: The corpus files identity actually arrives from. Named rather than globbed:
#: `work/` is 580 MB and most of it is provider dumps and mailbox utilisation
#: that carry no prospect identity, so a glob would cost a minute per commit and
#: buy nothing. Missing files are skipped silently; a missing corpus is reported.
CORPUS_FILES = (
    "queue.jsonl",            # the records: id, company, domain, contacts
    "candidates.jsonl",
    "campaigns.jsonl",
    "reply-drafts.jsonl",
    "agency-dnc.jsonl",
)

#: Identity-bearing keys, at any depth. `key` is the one TASK-174 wrote in clear
#: as a name-shaped slug; `linkedin` is a vanity name, which identifies a person
#: as precisely as an address does.
RECORD_KEYS = ("company", "domain", "name", "first_name", "last_name",
               "email", "linkedin", "key", "contact_key", "company_name")
#: `id` only at the TOP level of a record. Nested `id` is a provider integer.
TOP_ID_KEYS = ("id",)

#: A single-token corpus value must be at least this long to become a matcher.
#: Below it the token is a word, not a name, and the gate would fire on prose.
MIN_SINGLE = 6
#: A multi-token value needs this many characters of canonical form in total.
MIN_MULTI = 8
#: Longest n-gram built from scanned text, and therefore the longest canonical
#: form a scan can possibly produce. MEASURED against the live corpus rather
#: than guessed: of 28,489 extracted values the canonical token counts run
#: 1:4949  2:14148  3:6851  4:1692  5:315  6:189  7:128  8:72  9:30  10+:12.
#: Six covers all but 242 of them, and `fingerprints_for` adds a six-token
#: PREFIX for anything longer so no value is structurally uncatchable. At four,
#: the first self-test run against the corpus reported 490 values that no scan
#: could ever match - a matcher nothing can trigger is a matcher that is not
#: there.
MAX_NGRAM = 6

#: Single tokens that are industry vocabulary, not identities. Every one of these
#: appears as a whole company name or a name fragment somewhere in the live
#: corpus, and every one of them also appears in ordinary English in this
#: repository's documents. Matching them would make the gate noise.
STOP = {
    "agency", "agencies", "marketing", "digital", "software", "studio",
    "studios", "creative", "design", "designs", "media", "consulting",
    "consultancy", "solutions", "systems", "services", "partner", "partners",
    "holdings", "limited", "company", "ventures", "capital", "technology",
    "technologies", "labs", "group", "global", "online", "network", "networks",
    "interactive", "collective", "commerce", "analytics", "insight", "insights",
    "platform", "security", "health", "finance", "financial", "mobile", "cloud",
    "performance", "growth", "content", "brand", "brands", "social", "search",
    "email", "outbound", "inbound", "pipeline", "revenue", "advertising",
    "advertisement", "recruitment", "staffing", "engineering", "development",
    "production", "productions", "communications", "management", "resource",
    "resources", "operations", "delivery", "project", "projects", "director",
    "founder", "manager", "unknown", "contact", "contacts", "account",
    "accounts", "campaign", "campaigns", "prospect", "prospects", "client",
    "clients", "record", "records", "domains", "domain", "verified", "research",
    "linkedin", "google", "github", "gmail", "outlook", "website", "https",
    "person", "people", "number", "string", "object", "default", "example",
    "sample", "testing", "fixture", "fixtures", "builder", "builders",
    "business", "businesses", "london", "zagreb", "berlin", "dublin", "sydney",
    "amsterdam", "copenhagen", "stockholm", "croatia", "england", "ireland",
}

#: PUBLIC MAILBOX PROVIDERS. A contact in the corpus whose address is on a
#: free-mail provider puts that provider's name into the `domain` field, and the
#: registrable label is then `hotmail` or `gmail` - which identifies nobody and
#: appears in ordinary documentation about address quality. Measured: `hotmail`
#: was a false positive in the commit replay, from exactly this path.
#: `tests/test_fixture_hygiene.py` makes the same carve-out in prose for
#: email-gateway vendor hostnames, and for the same reason: treating
#: infrastructure as PII makes a guard that gets skipped.
PUBLIC_MAIL = {
    "hotmail", "gmail", "googlemail", "yahoo", "ymail", "outlook", "live",
    "msn", "icloud", "aol", "gmx", "protonmail", "proton", "mail", "yandex",
    "zoho", "fastmail", "hushmail", "inbox", "btinternet", "sky",
    "virginmedia", "comcast", "verizon", "orange", "wanadoo", "free",
    "t-online", "web", "seznam", "libero", "bluewin", "telenet", "ziggo",
    "xs4all", "chello", "tiscali", "bigpond", "optusnet", "rogers", "shaw",
    "sympatico", "cox", "earthlink", "juno", "netzero", "qq", "163", "126",
    "naver", "daum", "rediffmail", "bol", "uol", "terra",
}

#: As `tests/test_fixture_hygiene.py`. Nothing on these can resolve.
SAFE_SUFFIXES = (".test", ".example", "example.com", "example.org",
                 "example.net", "localhost", ".invalid")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"\+\d[\d ().-]{7,}\d")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-_]+)")
DOMAIN_RE = re.compile(r"\b([a-z0-9][a-z0-9-]{1,62}(?:\.[a-z0-9-]{2,63})+)\b")
NONWORD_RE = re.compile(r"[^\w]+", re.UNICODE)

#: As `tests/test_fixture_hygiene.py`'s tuple of the same name: the extensions
#: that are text a person could read an identity out of.
TEXT_SUFFIXES = (".py", ".json", ".jsonl", ".csv", ".txt", ".md", ".yaml",
                 ".yml", ".cfg", ".ini", ".toml", ".html", ".js", ".css")


# --------------------------------------------------------------------------
# canonical form and fingerprint
# --------------------------------------------------------------------------

def canon(value):
    """One canonical string for every spelling of the same identity.

    THIS IS THE WHOLE TRICK, and it is why the gate catches a value it has only
    ever seen in one shape. With an invented identity: `dunmorrow.example`,
    `dunmorrow-example` and `Dunmorrow Example` all canonicalise to
    `dunmorrow example`; `orrin-blackvale`, `Orrin Blackvale` and
    `orrin.blackvale@` all canonicalise to `orrin blackvale`. The examples are
    invented on purpose - the real pair this gate was written for is in two
    tracked files already and is not going to be copied into a third. They are
    also DIFFERENT invented names from the ones the test plants, so that a
    `git grep` for the planted identity cannot find it in this file: that search
    returning nothing is the premise of
    `test_the_corpus_is_invisible_to_every_git_tool_and_the_gate_still_fires`.
    The corpus holds the domain and the contact key; a fixture writer reaches for
    whichever shape is to hand, and one fingerprint covers all of them.
    """
    if not isinstance(value, str):
        return ""
    low = value.strip().lower()
    return " ".join(NONWORD_RE.sub(" ", low).split())


def fold(text):
    """Diacritics stripped: `prošić` -> `prosic`.

    Several Croatian surnames in `FORBIDDEN_NAMES` are listed TWICE BY HAND, once
    with the diacritic and once without, which is the evidence that
    both shapes occur. The corpus holds whichever the provider returned; a
    fixture written from memory loses the diacritic. So every value is
    fingerprinted twice.
    """
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


def fp(canonical):
    return "pg-" + hashlib.sha256(
        (SALT + "|%d|" % FP_VERSION + canonical).encode("utf-8")
    ).hexdigest()[:12]


def _now():
    return int(time.time())


#: Tokens that are THIS REPOSITORY'S OWN ENGLISH, derived from it rather than
#: typed by hand. See `load_vocabulary`. Empty until loaded, and empty means
#: "more matchers", never fewer - a gate that silently loses its vocabulary gets
#: noisier, which is noticed, rather than quieter, which is not.
_VOCAB = frozenset()

#: A token in at least this many tracked files is vocabulary, not an identity.
#: MEASURED, not guessed. Document frequency over 2,460 tracked text files:
#:
#:     four words that are ALSO registrable labels of real corpus domains
#:                                              df 464, 1068, 1118, 1883
#:     five prospect and client identity tokens      df 1, 1, 1, 1, 2
#:     one real record id from the live canary row            df 2
#:     four hand-reviewed surnames already in tracked files   df 3, 4, 10, 19
#:
#: Two populations, two orders of magnitude apart, and the words are not quoted
#: here because four of them are real domain labels. Before this threshold
#: existed those four produced 445 of the 657 hits in a replay of the last 30
#: commits, and all 30 commits were refused - a gate nobody would keep.
#:
#: THE SELF-DEFEATING EDGE, named rather than hidden: document frequency counts
#: the leaks too, so a real name that has already reached 25 tracked files stops
#: being a corpus matcher. That is why the DENYLIST layer is unconditional - a
#: hand-reviewed name is matched as a literal whatever its frequency.
VOCAB_MIN_DOCS = 25
VOCAB_MAX_AGE = 7 * 86400


def load_vocabulary(repo, force=False):
    """The repository's own word list, built from the repository.

    A HAND-MAINTAINED stoplist is the thing that already failed here: nobody
    remembered the canary's record id, so nothing could fail. The same
    objection applies to
    hand-listing the words NOT to match on, so this derives them. A token that
    is already spread across this repository's prose cannot be what identifies
    one client.

    Costs about 6 seconds over 2,460 files, which is far too slow to pay per
    commit, so it is cached in the gitignored `cache/` tree and rebuilt when the
    tracked file COUNT changes or the cache is a week old. A stoplist that lags
    by a week is harmless: English does not acquire new words that fast, and a
    stale one can only make the gate noisier.
    """
    global _VOCAB
    path = os.path.join(repo, "cache", "pii-gate-vocabulary.json")
    listing = git(repo, "ls-files").stdout.split()
    files = [p for p in listing if p.endswith(TEXT_SUFFIXES)]
    if not force and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                blob = json.load(handle)
            fresh = (blob.get("n_files") == len(files)
                     and blob.get("min_docs") == VOCAB_MIN_DOCS
                     and (_now() - blob.get("built_at", 0)) < VOCAB_MAX_AGE)
            if fresh:
                _VOCAB = frozenset(blob["tokens"])
                return _VOCAB
        except (OSError, ValueError, KeyError):
            pass

    df = {}
    for rel in files:
        full = os.path.join(repo, rel)
        try:
            with open(full, encoding="utf-8", errors="replace") as handle:
                text = handle.read(400_000)
        except OSError:
            continue
        for token in set(NONWORD_RE.sub(" ", text.lower()).split()):
            df[token] = df.get(token, 0) + 1
    _VOCAB = frozenset(t for t, n in df.items() if n >= VOCAB_MIN_DOCS)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"built_at": _now(), "n_files": len(files),
                       "min_docs": VOCAB_MIN_DOCS,
                       "tokens": sorted(_VOCAB)}, handle)
        os.replace(tmp, path)
    except OSError:
        pass
    return _VOCAB


def _usable(canonical):
    """Is this canonical form distinctive enough to match on?

    The judgement that keeps the gate from being noise. A one-word value has to
    be long and not vocabulary; a multi-word value is already distinctive.
    """
    if not canonical:
        return False
    tokens = canonical.split()
    if any(t.isdigit() for t in tokens) and len(tokens) == 1:
        return False
    if len(tokens) == 1:
        t = tokens[0]
        return (len(t) >= MIN_SINGLE and t not in STOP and t not in _VOCAB
                and not t.isdigit())
    if len(canonical.replace(" ", "")) < MIN_MULTI:
        return False
    # "digital agency", "project manager": every token is vocabulary, so the
    # pair is vocabulary too. A real name has at least one distinctive token.
    # The repository's own word list applies here as well as in `STOP` - an
    # n-gram of nothing but this repository's English is this repository's
    # English.
    return any(t not in STOP and t not in _VOCAB and len(t) > 2 for t in tokens)


def fingerprints_for(value, kind):
    """{fingerprint: kind} for one raw corpus value, plus its useful parts.

    THE VANITY CASE IS NOT COSMETIC. The corpus stores `linkedin` sometimes as a
    bare handle and sometimes as a full `https://www.linkedin.com/in/<handle>`
    URL. Canonicalising the URL whole gives a SIX-token form that no scan of a
    fixture could ever produce, because `_ngrams` only builds windows up to
    `MAX_NGRAM`. The first run of `--selftest` against the live corpus reported
    exactly that: 2,011 of 25,848 protected values uncatchable, every one of them
    a vanity. The handle is the identity; the URL around it is boilerplate.
    """
    out = {}
    if kind == "vanity" and isinstance(value, str) and "/" in value:
        # The LAST PATH SEGMENT, by splitting - not by `LINKEDIN_RE`, whose
        # character class is ASCII-only. Six handles in the live corpus carry a
        # non-ASCII letter, and extracting with the ASCII regex truncated each
        # at that letter into a fragment no scan could reproduce. The self-test
        # is what found them; they were the last six misses of 25,823.
        value = value.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    for form in (canon(value), fold(canon(value))):
        tokens = form.split()
        if len(tokens) > MAX_NGRAM:
            #: A FORM LONGER THAN THE WIDEST WINDOW IS NOT REGISTERED AT ALL.
            #: No scan can produce a 9-token canonical form, so a matcher for
            #: one is a matcher nothing can ever trigger - and `--selftest`
            #: found exactly two of them in the live corpus (a `company` field
            #: holding a sentence about working from home, and a `name` field
            #: holding a mail-merge fragment). Only the first MAX_NGRAM tokens
            #: are registered, and only if that prefix is itself distinctive;
            #: when it is not, the value is corpus noise and gets no matcher,
            #: which is the honest outcome rather than a decorative one.
            prefix = " ".join(tokens[:MAX_NGRAM])
            if _usable(prefix):
                out.setdefault(fp(prefix), kind + "-prefix")
        elif _usable(form):
            out[fp(form)] = kind
    # The registrable label of a domain, on its own. A corpus domain
    # `<label>.co.uk` has to catch a bare `<label>` in a commit message, which
    # is the exact shape of incident 1: a company name with no TLD attached.
    if kind == "domain" and isinstance(value, str) and "." in value:
        label = canon(value.split(".")[0])
        if _usable(label) and label not in PUBLIC_MAIL:
            out.setdefault(fp(label), "domain-label")
    return out


# --------------------------------------------------------------------------
# where the corpus is
# --------------------------------------------------------------------------

def git(repo, *args, **kw):
    done = subprocess.run(("git", "-C", repo) + args, capture_output=True,
                          text=True, errors="replace", timeout=kw.get("timeout", 60))
    return done


def corpus_root(repo):
    """The directory holding the live corpus, or None.

    A WORKTREE HAS ITS OWN, EMPTY `work/`. `work/` is gitignored, so
    `git worktree add` creates none - and an agent working in a worktree would
    otherwise get a gate with an empty corpus and a clean PASS on a real name.
    Measured on this repository: the fix is to fall back to the MAIN checkout,
    which `--git-common-dir` names unambiguously from inside any worktree.

    `PII_GATE_CORPUS` overrides, for a machine that keeps the corpus elsewhere.
    """
    override = os.environ.get("PII_GATE_CORPUS")
    if override:
        return override if os.path.isdir(override) else None

    here = os.path.join(repo, "work")
    if os.path.isdir(here) and any(
            os.path.isfile(os.path.join(here, n)) for n in CORPUS_FILES):
        return here

    common = git(repo, "rev-parse", "--path-format=absolute",
                 "--git-common-dir").stdout.strip()
    if common:
        main = os.path.dirname(common.rstrip("/\\"))
        cand = os.path.join(main, "work")
        if os.path.isdir(cand) and any(
                os.path.isfile(os.path.join(cand, n)) for n in CORPUS_FILES):
            return cand
    return here if os.path.isdir(here) else None


def _is_ignored(repo, path):
    try:
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
    except ValueError:                 # different drive: not in this repo at all
        return False
    return git(repo, "check-ignore", "-q", rel).returncode == 0


def _outside(repo, path):
    """Is `path` outside the repository working tree entirely?

    A worktree reads the MAIN checkout's corpus, so the cache it writes is
    outside its own tree and cannot be committed from there whatever
    `.gitignore` says. Different drives raise rather than compare, hence the
    try.
    """
    try:
        return os.path.commonpath([os.path.abspath(repo),
                                   os.path.abspath(path)]) != os.path.abspath(repo)
    except ValueError:
        return True


# --------------------------------------------------------------------------
# reading the corpus
# --------------------------------------------------------------------------

def _walk(node, out, top=True):
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                if key in RECORD_KEYS:
                    out.append((value, "name" if key in
                                ("name", "first_name", "last_name", "key",
                                 "contact_key") else
                                "domain" if key == "domain" else
                                "email" if key == "email" else
                                "vanity" if key == "linkedin" else "company"))
                elif top and key in TOP_ID_KEYS:
                    out.append((value, "record-id"))
            else:
                _walk(value, out, top=False)
    elif isinstance(node, list):
        for item in node:
            _walk(item, out, top=False)


def values_in(path):
    """Raw identity values from one JSONL corpus file.

    `open()`, not a search tool. The whole point: `work/` is gitignored and
    every tool that honours `.gitignore` reports zero here.
    """
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                _walk(row, out)
    except OSError:
        return []
    # A full name as well as its halves: the halves are usually below MIN_SINGLE
    # and get dropped, which is correct - a bare given name is the hand-reviewed
    # denylist's job - but "First Last" must be a matcher.
    return out


class Matcher(object):
    """Fingerprint -> kind, plus whatever provenance the caller needs.

    `values` is populated ONLY on a live build and only in memory. `--selftest`
    needs the raw values to prove each one is caught, so it forces a live build;
    everything else runs from the cache and never holds a real value at all.
    """

    def __init__(self):
        self.fps = {}
        self.values = []          # in-memory only, never written anywhere
        self.corpus_present = False
        self.sources = []
        self.notes = []

    def add(self, value, kind):
        got = fingerprints_for(value, kind)
        if got:
            self.fps.update(got)
            return True
        return False


def _cache_path(repo):
    """`<repo>/cache/`, which `.gitignore` already ignores wholesale.

    NOT inside `work/`. Two reasons, and the second is the operative one:
    `work/` is the live client corpus and a tool that protects it has no business
    writing into it, and a worktree reads the MAIN checkout's `work/` - so a
    cache there would be written by every agent worktree into one shared
    directory. `cache/` is per-checkout, already ignored, and holds nothing but
    fingerprints keyed by (size, mtime).
    """
    return os.path.join(repo, "cache", "pii-gate-fingerprints.json")


def build_matcher(repo, use_cache=True, keep_values=False):
    matcher = Matcher()
    load_vocabulary(repo)
    root = corpus_root(repo)
    if not root:
        matcher.notes.append(
            "corpus=absent (no work/ reachable from this checkout): the CORPUS "
            "layer is OFF. DENYLIST and STRUCTURAL still apply.")
        _add_denylist(matcher)
        return matcher

    present = [n for n in CORPUS_FILES
               if os.path.isfile(os.path.join(root, n))]
    if not present:
        matcher.notes.append("corpus=empty (%s holds none of %s)"
                             % (root, ", ".join(CORPUS_FILES)))
        _add_denylist(matcher)
        return matcher

    matcher.corpus_present = True
    cache, cache_ok = {}, False
    cache_file = _cache_path(repo)
    #: A cache of fingerprints is still a derivative of client data, so it is
    #: only ever written INSIDE the ignored tree, and only after asking git
    #: whether that tree really is ignored. If `work/` ever stops being
    #: gitignored this writes nothing rather than planting a committable file.
    cache_allowed = _is_ignored(repo, cache_file) or _outside(repo, cache_file)
    if use_cache and os.path.isfile(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as handle:
                cache = json.load(handle)
            cache_ok = cache.get("fp_version") == FP_VERSION
        except (OSError, ValueError):
            cache, cache_ok = {}, False
    files = cache.get("files", {}) if cache_ok else {}

    fresh = {}
    dirty = False
    for name in present:
        path = os.path.join(root, name)
        stat = os.stat(path)
        key = "%d:%d" % (stat.st_size, stat.st_mtime_ns)
        entry = files.get(name)
        if entry and entry.get("key") == key and not keep_values:
            matcher.fps.update(entry["fps"])
            fresh[name] = entry
            matcher.sources.append("%s (cached, %d fp)" % (name, len(entry["fps"])))
            continue
        dirty = True
        got = {}
        n_values = 0
        for value, kind in values_in(path):
            n_values += 1
            got.update(fingerprints_for(value, kind))
            if keep_values:
                matcher.values.append((value, kind))
        matcher.fps.update(got)
        fresh[name] = {"key": key, "fps": got}
        matcher.sources.append("%s (read, %d values -> %d fp)"
                               % (name, n_values, len(got)))

    if dirty and cache_allowed and not keep_values:
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            tmp = cache_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"fp_version": FP_VERSION, "files": fresh}, handle)
            os.replace(tmp, cache_file)
        except OSError:
            pass

    _add_denylist(matcher)
    return matcher


def _add_denylist(matcher):
    """`tests/test_fixture_hygiene.py`'s tuples, imported rather than copied.

    The same reasoning `scripts/history_pii_scan.py` gives for importing them:
    a second copy is a second thing that can disagree, and a copy here would
    make THIS file a violation of the guard it extends.
    """
    try:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from test_fixture_hygiene import (FORBIDDEN_DOMAINS, FORBIDDEN_NAMES,
                                          FORBIDDEN_FIGURES)
    except Exception as exc:                       # pragma: no cover
        matcher.notes.append("denylist=unavailable (%s)" % exc)
        return
    n = 0
    for value in FORBIDDEN_DOMAINS:
        n += 1 if matcher.add(value, "denylist-domain") else 0
    for value in FORBIDDEN_NAMES:
        n += 1 if matcher.add(value, "denylist-name") else 0
    matcher.denylist_literals = tuple(
        v.lower() for v in FORBIDDEN_DOMAINS + FORBIDDEN_NAMES)
    matcher.denylist_figures = tuple(FORBIDDEN_FIGURES)
    matcher.sources.append("test_fixture_hygiene denylist (%d fp)" % n)


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------

class Hit(object):
    def __init__(self, path, line, rule, surface, token):
        self.path, self.line = path, line
        self.rule, self.surface, self.token = rule, surface, token

    def __repr__(self):
        return "%s:%s %s %r [%s]" % (self.path, self.line, self.rule,
                                     self.surface, self.token)


def _ngrams(text):
    """(canonical form, surface) for every 1..MAX_NGRAM word window."""
    low = text.lower()
    tokens = [t for t in NONWORD_RE.sub(" ", low).split() if t]
    out = []
    for i in range(len(tokens)):
        for n in range(1, MAX_NGRAM + 1):
            if i + n > len(tokens):
                break
            out.append(" ".join(tokens[i:i + n]))
    return out


def scan_text(text, matcher, path, line_no=None, structural=True):
    """Every hit in one piece of text. The ONE place a rule is evaluated."""
    hits = []
    seen = set()

    for form in _ngrams(text):
        # `fold` is only a second candidate when there is something to fold.
        # Measured: the diacritic pass doubled the cost of every scan to cover
        # the handful of n-grams that are not already ASCII.
        folded = form if form.isascii() else fold(form)
        for candidate in ((form,) if folded == form else (form, folded)):
            if not _usable(candidate):
                continue
            token = fp(candidate)
            if token in matcher.fps and (token, candidate) not in seen:
                seen.add((token, candidate))
                hits.append(Hit(path, line_no, "corpus:" + matcher.fps[token],
                                candidate, token))

    low = text.lower()
    for literal in getattr(matcher, "denylist_literals", ()):
        if literal in low:
            token = fp(canon(literal))
            if (token, literal) in seen:
                continue
            seen.add((token, literal))
            hits.append(Hit(path, line_no, "denylist", literal, token))
    for figure in getattr(matcher, "denylist_figures", ()):
        if figure in text:
            hits.append(Hit(path, line_no, "denylist-figure", figure,
                            fp(canon(figure))))

    if not structural:
        return hits

    for domain in set(EMAIL_RE.findall(text)):
        low_d = domain.lower()
        if not any(low_d == s or low_d.endswith(s) for s in SAFE_SUFFIXES):
            hits.append(Hit(path, line_no, "structural:email-domain", low_d,
                            fp(canon(low_d))))
    for raw in PHONE_RE.findall(text):
        number = raw.strip()
        if number not in _allowed_phones():
            hits.append(Hit(path, line_no, "structural:phone", number,
                            fp(canon(number))))
    #: THE EMAIL AND PHONE RULES APPLY IN `tests/` TOO. Only the vanity rule is
    #: relaxed there, which is the same split `tests/test_fixture_hygiene.py`
    #: makes: its email rule is repository-wide and its LinkedIn rule skips
    #: `tests/` because a synthetic fixture handle cannot be enumerated in
    #: advance. Relaxing all three inside `tests/` would retire the gate for
    #: exactly the files TASK-938 exists to protect.
    for vanity in (() if path.startswith("tests/") else LINKEDIN_RE.findall(text)):
        low_v = vanity.lower()
        if low_v in _fake_vanities():
            continue
        if any(x in low_v for x in ("-demo", "-test", "-example", "-acme")):
            continue
        hits.append(Hit(path, line_no, "structural:linkedin-vanity", low_v,
                        fp(canon(low_v))))
    return hits


def _allowed_phones():
    try:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from test_fixture_hygiene import ALLOWED_PHONES
        return ALLOWED_PHONES
    except Exception:                              # pragma: no cover
        return set()


_VANITY_CACHE = None


def _fake_vanities():
    """The invented-handle allowlist, read out of the existing guard's source.

    It is a local inside a test method there, so it cannot be imported. Reading
    the literal set from the source is still better than copying it: there is
    one place to edit, and if the shape ever changes this returns empty and the
    structural vanity rule gets noisier - it never goes quiet.
    """
    global _VANITY_CACHE
    if _VANITY_CACHE is not None:
        return _VANITY_CACHE
    _VANITY_CACHE = set()
    try:
        with open(os.path.join(ROOT, "tests", "test_fixture_hygiene.py"),
                  encoding="utf-8") as handle:
            src = handle.read()
        start = src.index("FAKE_VANITY = {")
        end = src.index("}", start)
        import ast
        _VANITY_CACHE = ast.literal_eval(src[start + len("FAKE_VANITY = "):end + 1])
    except Exception:                              # pragma: no cover
        pass
    return _VANITY_CACHE


# --------------------------------------------------------------------------
# what is being committed
# --------------------------------------------------------------------------

def staged_added_lines(repo):
    """[(path, line_no, text)] for every line this commit ADDS.

    `-U0` so only added lines come back, and `--diff-filter` keeps deletions out.
    Binary files produce no `+` lines, so they need no special case.
    """
    done = git(repo, "diff", "--cached", "--no-color", "-U0", "-M",
               "--diff-filter=ACMR")
    out, path, new_line = [], None, 0
    for line in done.stdout.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target[2:] if \
                target.startswith(("a/", "b/")) else target
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if path is not None:
                out.append((path, new_line, line[1:]))
            new_line += 1
    return out


# --------------------------------------------------------------------------
# exceptions
# --------------------------------------------------------------------------

class BadException(Exception):
    pass


def load_exceptions(repo):
    """[(path_glob, token, reviewer, reason)].

    An entry carries a FINGERPRINT, never a value, so clearing a false positive
    cannot itself commit the identity. Reviewer and reason are mandatory: an
    unexplained exception is how a gate dies quietly. A malformed line RAISES -
    the gate then refuses the commit rather than silently honouring nothing,
    because "my exception did not work and the gate said PASS" is the worst
    outcome available.
    """
    path = os.path.join(repo, EXCEPTIONS)
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as handle:
        for n, raw in enumerate(handle, 1):
            line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("#") else ""
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 4:
                raise BadException(
                    "%s:%d needs exactly 4 fields separated by '|': "
                    "path-glob | token | reviewer | reason" % (EXCEPTIONS, n))
            glob, token, reviewer, reason = parts
            if not glob or not token:
                raise BadException("%s:%d empty path-glob or token" % (EXCEPTIONS, n))
            if not reviewer or reviewer.lower() in ("", "-", "todo", "unknown"):
                raise BadException(
                    "%s:%d needs a named reviewer, got %r" % (EXCEPTIONS, n, reviewer))
            if len(reason) < 12:
                raise BadException(
                    "%s:%d needs a reason of at least 12 characters, got %r"
                    % (EXCEPTIONS, n, reason))
            if not (token.startswith("pg-") or token.startswith("rule:")):
                raise BadException(
                    "%s:%d token must be a pg- fingerprint or rule:<name>, got %r. "
                    "NEVER put the real value here." % (EXCEPTIONS, n, token))
            out.append((glob, token, reviewer, reason))
    return out


def excused(hit, exceptions):
    for glob, token, _reviewer, _reason in exceptions:
        if not fnmatch.fnmatch(hit.path, glob):
            continue
        if token == hit.token:
            return True
        if token.startswith("rule:") and hit.rule.startswith(token[5:]):
            return True
    return False


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------

def gate(repo, scan_staged=False, message_file=None, worktree=False,
         require_corpus=False, use_cache=True, out=sys.stderr):
    matcher = build_matcher(repo, use_cache=use_cache)
    try:
        exceptions = load_exceptions(repo)
    except BadException as exc:
        out.write("PII-GATE: REFUSED - the exception file is malformed.\n  %s\n"
                  % exc)
        return 1

    if require_corpus and not matcher.corpus_present:
        out.write("PII-GATE: REFUSED - --require-corpus and the corpus is not "
                  "reachable.\n  " + "\n  ".join(matcher.notes) + "\n")
        return 1

    hits, excused_n = [], 0

    def take(found):
        nonlocal excused_n
        for hit in found:
            if excused(hit, exceptions):
                excused_n += 1
            else:
                hits.append(hit)

    if scan_staged:
        for path, line_no, text in staged_added_lines(repo):
            if path in SELF_EXEMPT:
                continue
            take(scan_text(text, matcher, path, line_no))

    if worktree:
        for path, line_no, text in _worktree_added_lines(repo):
            if path in SELF_EXEMPT:
                continue
            take(scan_text(text, matcher, path, line_no))

    if message_file:
        try:
            with open(message_file, encoding="utf-8", errors="replace") as handle:
                body = handle.read()
        except OSError as exc:
            out.write("PII-GATE: REFUSED - cannot read the message (%s)\n" % exc)
            return 1
        # A comment line is stripped by git and never becomes part of the
        # message, so scanning it would fire on the `# Changes to be committed`
        # block listing a path that happens to carry a name.
        #: GIT TRAILERS ARE NOT PROSE, and one of them is mandatory here.
        #: Every commit in this repository ends with a `Co-Authored-By:` line
        #: carrying a vendor `noreply` address, which the STRUCTURAL email rule
        #: below correctly reads as an address on a domain that resolves. The
        #: address is not spelled out here, because this file would then be a
        #: violation of its own rule. Replaying the last 30 real commits
        #: produced 22 hits from that one trailer line alone. A gate
        #: that refuses the repository's own mandated commit footer is a gate
        #: that gets uninstalled within the hour.
        kept = [l for l in body.splitlines()
                if not l.startswith("#")
                and not re.match(r"(?i)\s*(co-authored-by|signed-off-by|"
                                 r"reported-by|reviewed-by|acked-by|tested-by)\s*:",
                                 l)]
        for n, line in enumerate(kept, 1):
            take(scan_text(line, matcher, "COMMIT_MSG", n))

    head = "corpus=%s  matchers=%d  sources=[%s]" % (
        "present" if matcher.corpus_present else "ABSENT",
        len(matcher.fps), "; ".join(matcher.sources))
    for note in matcher.notes:
        out.write("PII-GATE: note: %s\n" % note)

    if not hits:
        out.write("PII-GATE: PASS  %s  excused=%d\n" % (head, excused_n))
        return 0

    out.write("\nPII-GATE: REFUSED - this commit introduces %d real identity "
              "match(es).\n%s\n\n" % (len(hits), head))
    for hit in hits:
        where = hit.path if hit.line is None else "%s:%s" % (hit.path, hit.line)
        out.write("  %-44s %-34s %r\n  %s%s\n"
                  % (where, hit.rule, hit.surface, " " * 44, hit.token))
    out.write(
        "\nWHAT TO DO\n"
        "  1. The usual answer is that the value is real. Replace it with an\n"
        "     obviously synthetic one and commit again. Nothing has been\n"
        "     committed, so there is nothing to rewrite.\n"
        "  2. If it is a FALSE POSITIVE, add one line per hit to %s:\n"
        "         <path-glob> | <pg- token above> | <your name> | <why>\n"
        "     The token, never the value - that file is tracked.\n"
        "  3. `git commit --no-verify` bypasses every hook. It is in git, it\n"
        "     cannot be removed, and using it here is a reportable decision.\n"
        % EXCEPTIONS)
    return 1


def _worktree_added_lines(repo):
    done = git(repo, "diff", "--no-color", "-U0", "HEAD")
    out, path, new_line = [], None, 0
    for line in done.stdout.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target[2:] if \
                target.startswith(("a/", "b/")) else target
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if path is not None:
                out.append((path, new_line, line[1:]))
            new_line += 1
    others = git(repo, "ls-files", "--others", "--exclude-standard").stdout.split()
    for rel in others:
        full = os.path.join(repo, rel)
        if not os.path.isfile(full) or os.path.getsize(full) > 2_000_000:
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as handle:
                for n, line in enumerate(handle, 1):
                    out.append((rel, n, line.rstrip("\n")))
        except OSError:
            continue
    return out


# --------------------------------------------------------------------------
# acceptance 3: self-test against EVERY value it claims to protect
# --------------------------------------------------------------------------

def selftest(repo, out=sys.stdout):
    """Run every protected value through the real scanner. Print no value.

    A filter that has not been run against the actual corpus values is a filter
    that agrees with you. So this does not inspect the matcher - it feeds each
    value into `scan_text`, the same function the hook calls, inside a sentence
    shaped like a fixture line, and demands a hit whose fingerprint is the one
    that value should produce.

    Forces a live build: the cache holds only fingerprints, and a self-test that
    can only see fingerprints is a tautology.
    """
    matcher = build_matcher(repo, use_cache=False, keep_values=True)
    checked = missed = skipped = 0
    misses = []
    by_kind = {}
    for value, kind in matcher.values:
        wanted = fingerprints_for(value, kind)
        if not wanted:
            skipped += 1               # deliberately below the usable threshold
            continue
        checked += 1
        found = {h.token for h in
                 scan_text('  "company": "%s",' % value, matcher,
                           "selftest", 1, structural=False)}
        if not (set(wanted) & found):
            missed += 1
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if len(misses) < 20:
                misses.append((fp(canon(value)), kind))
    for value in getattr(matcher, "denylist_literals", ()):
        checked += 1
        found = {h.token for h in
                 scan_text("fixture mentions %s here" % value, matcher,
                           "selftest", 1, structural=False)}
        if fp(canon(value)) not in found:
            missed += 1
            if len(misses) < 20:
                misses.append((fp(canon(value)), "denylist"))

    #: THE OTHER DIRECTION. A matcher that fires on everything would pass the
    #: loop above and block every commit, so the self-test also proves a set of
    #: obviously invented identities is NOT matched.
    clean = ["Dunmorrow Tessellate Ltd", "orrin-blackvale",
             "Orrin Blackvale", "dunmorrow-tessellate.example",
             "Wilmot Ashgrove", "fenwick-oakhollow", "zz-nobody-at-all",
             "Acme Widgets Inc", "test-prospect-001"]
    false_pos = []
    for value in clean:
        found = scan_text('  "company": "%s",' % value, matcher,
                          "selftest", 1, structural=False)
        if found:
            false_pos.append((value, [h.rule for h in found]))

    ok = missed == 0 and not false_pos
    out.write("PII-GATE SELFTEST: %s\n" % ("PASS" if ok else "FAIL"))
    out.write("  corpus=%s  sources=[%s]\n"
              % ("present" if matcher.corpus_present else "ABSENT",
                 "; ".join(matcher.sources)))
    out.write("  protected values run through the real scanner: %d\n" % checked)
    out.write("  values below the distinctiveness threshold (not matchers): %d\n"
              % skipped)
    out.write("  values the scanner FAILED to catch: %d %s\n"
              % (missed, sorted(by_kind.items()) if by_kind else ""))
    for token, kind in misses:
        out.write("    MISS %s (%s)\n" % (token, kind))
    out.write("  synthetic controls wrongly matched: %d\n" % len(false_pos))
    for value, rules in false_pos:
        out.write("    FALSE POSITIVE %r %s\n" % (value, rules))
    return 0 if ok else 1


# --------------------------------------------------------------------------
# install
# --------------------------------------------------------------------------

PRE_COMMIT = r"""#!/bin/sh
# Installed by scripts/pii_gate.py --install (TASK-938). Do not edit here;
# edit the script and re-install, because .git/hooks is not tracked.
#
# A CHECKOUT WITHOUT THE SCRIPT MUST STILL BE COMMITTABLE. .git/hooks is shared
# by every worktree and survives a branch switch, so a hook that hard-failed
# when the script is absent would make `master` uncommittable before this
# lands. Missing script => warn and allow.
root=$(git rev-parse --show-toplevel) || exit 0
gate="$root/scripts/pii_gate.py"
if [ ! -f "$gate" ]; then
  echo "pii-gate: $gate not on this branch; PII gate NOT RUN." >&2
  exit 0
fi
for py in py python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    if [ "$py" = "py" ]; then set -- -3 "$gate" --staged; else set -- "$gate" --staged; fi
    exec "$py" "$@"
  fi
done
echo "pii-gate: no python interpreter found; PII gate NOT RUN." >&2
exit 0
"""

COMMIT_MSG = r"""#!/bin/sh
# Installed by scripts/pii_gate.py --install (TASK-938).
# $1 is the file holding the proposed message. This runs BEFORE the commit
# object exists, which is the only placement that can stop incident 1 - a real
# company name in a commit message, which no tree scan can see.
root=$(git rev-parse --show-toplevel) || exit 0
gate="$root/scripts/pii_gate.py"
if [ ! -f "$gate" ]; then
  echo "pii-gate: $gate not on this branch; message NOT SCANNED." >&2
  exit 0
fi
for py in py python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    if [ "$py" = "py" ]; then set -- -3 "$gate" --message "$1"; else set -- "$gate" --message "$1"; fi
    exec "$py" "$@"
  fi
done
echo "pii-gate: no python interpreter found; message NOT SCANNED." >&2
exit 0
"""


def hooks_dir(repo):
    """Where git will actually LOOK for a hook, not where hooks usually live.

    This repository sets `core.hooksPath` in its LOCAL config (measured
    2026-10-02: an absolute path to the main checkout's `.git/hooks`). Installing
    into `.git/hooks` while git reads somewhere else produces a gate that is
    present, correct, tested and never executed - which is the single worst
    outcome for a control like this, because every later commit then looks
    checked. So the config wins when it is set.
    """
    configured = git(repo, "config", "--get", "core.hooksPath").stdout.strip()
    if configured:
        return configured if os.path.isabs(configured) else \
            os.path.join(repo, configured)
    out = git(repo, "rev-parse", "--path-format=absolute",
              "--git-common-dir").stdout.strip()
    return os.path.join(out or os.path.join(repo, ".git"), "hooks")


def install(repo, out=sys.stdout):
    target = hooks_dir(repo)
    os.makedirs(target, exist_ok=True)
    written = []
    for name, body in (("pre-commit", PRE_COMMIT), ("commit-msg", COMMIT_MSG)):
        path = os.path.join(target, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                existing = handle.read()
            if "pii_gate.py" not in existing:
                out.write("PII-GATE: %s exists and is not this gate. NOT "
                          "overwritten - merge by hand.\n" % path)
                continue
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        os.chmod(path, 0o755)
        written.append(path)
    out.write("PII-GATE: installed %d hook(s) in %s\n"
              "  Hooks live in .git, which is NOT tracked and NOT cloned, so "
              "every checkout must run this once.\n"
              "  Shared by every worktree of this repository.\n"
              % (len(written), target))
    for path in written:
        out.write("    %s\n" % path)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=ROOT)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--worktree", action="store_true")
    ap.add_argument("--message")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--require-corpus", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--explain", action="store_true",
                    help="print the resolved corpus root and matcher count")
    args = ap.parse_args(argv)

    if args.install:
        return install(args.repo)
    if args.selftest:
        return selftest(args.repo)
    if args.explain:
        matcher = build_matcher(args.repo, use_cache=not args.no_cache)
        print("repo         %s" % args.repo)
        print("corpus root  %s" % corpus_root(args.repo))
        print("corpus       %s" % ("present" if matcher.corpus_present else "ABSENT"))
        print("matchers     %d" % len(matcher.fps))
        for line in matcher.sources:
            print("  - %s" % line)
        for line in matcher.notes:
            print("  ! %s" % line)
        print("exceptions   %d" % len(load_exceptions(args.repo)))
        return 0
    if not (args.staged or args.message or args.worktree):
        ap.error("one of --staged, --message, --worktree, --selftest, "
                 "--install, --explain")
    return gate(args.repo, scan_staged=args.staged, message_file=args.message,
                worktree=args.worktree, require_corpus=args.require_corpus,
                use_cache=not args.no_cache)


if __name__ == "__main__":
    sys.exit(main())
