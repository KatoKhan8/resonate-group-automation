#!/usr/bin/env python3
"""Re-render steps 1, 3, 4 and 5 for the UK/EU cohort FROM EACH LEAD'S OWN PACK.

    py -3 scripts/lane_h_pack_grounded_render.py --work <production work dir>

LANE H, 2026-09-25. READ ONLY except for the two NEW files it writes under
`--work`. No provider call of any kind. Nothing under `src/` is edited: the
modules this needs from other lanes are loaded FROM THEIR BRANCH BLOBS, so
their code is used rather than copied.

## THE PROBLEM THIS EXISTS FOR

Lane C crawled the 153 UK/EU domains for free and rule-1 pass on the 128 went
from 0 to 80 of 128. Lane C then said the part that matters: 54 of 117 passes
rested on ONE word and that word was `marketing` in 53 of them. S7 rendered
the copy BEFORE any pack existed, so the openers share vocabulary with the
research instead of referencing it. A higher rule-1 rate bought that way is
the defect, not the fix.

So step 1 is re-rendered to QUOTE a span of that lead's own site, verbatim,
with the page it came from named in the sentence. The grounding is then
structural - there is a sourced string in the opener - rather than a
coincidence of vocabulary, and the measurement below reports the difference
as the length of the longest contiguous run of opener words that appears in
the pack, not as a pass rate.

A lead whose pack yields no quotable span is HELD. It is not given a generic
line, because a generic line is exactly what was wrong.

## WHAT IS NOT REWRITTEN HERE

- **Step 2** is byte-identical to what is sending. Lane B measured
  `subject_1`/`body_1`/`body_2` unchanged across the cadence change and
  `LIVE copy moved: 0`. It is rendered from lane B's own constant.
- **Steps 3, 4 and 5** are lane B's `cadence.TEMPLATES` - rung 3 approved
  2026-09-25, em4/em5 approved 2026-09-24 - rendered by lane B's own
  `_steps_three_four_and_five`. Not a word of approved copy is retyped here.
- **The subject** is lane B's `subject_for`, unchanged.

## THE VARIABLE MAPPING, DERIVED FROM THE CODE

    scripts/batch1_build.py     journal `body_N` -> record cadence[key]["body"]
                                for key in STEP_KEYS = em1..em5
    src/bisonfactory.py         _copy_for_contact walks `sequence`, which
      _sequence_steps           _sequence_steps built from the cadence's email
      _variables_for            steps sorted by (day, key); _variables_for then
                                numbers them BY POSITION: body_{position}
    config email_sequence       emN.body = "<p>{BODY_N}</p>"

NOT READ OFF A DOCUMENT. `scripts/lane_h_mapping_check.py` feeds lane B's
`CADENCE_STEPS` and lane B's `email_sequence` block to the REAL
`bisonfactory._sequence_steps` and then asks the REAL `_variables_for` which
variable each step's words land in. Measured against lane B at `24cc4bac`:

    cadence days   1 / 4 / 8 / 12 / 21      gaps 3 / 4 / 4 / 9
    declared waits 3 / 4 / 4 / 9 / 1        thread [F, T, T, T, T]
    em1 -> {BODY_1}   em2 -> {BODY_2}   em3 -> {BODY_3}
    em4 -> {BODY_4}   em5 -> {BODY_5}

**The agreement between key number and position number is a COINCIDENCE of
this shape.** At four steps em4 was the third provider step and read
`{BODY_3}`. Nothing here relies on it: this emits the STEP-KEY names lane B's
`batch1_build` reads, and `bisonfactory` owns the translation.

## THE BRANCH MOVED UNDER THIS LANE ONCE, SO THE SHAS ARE RECORDED

Lane B's `productive.yaml` said waits 3/4/5/5/1 when this file was first
written and 3/4/4/9/1 an hour later. The blobs are read live, so the output
is always the branch's current copy - and the summary JSON therefore records
the three branch HEADs it was built from. A number quoted without them is a
number about a tree that no longer exists.
"""
import argparse
import collections
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LANE_B = "worktree-agent-a68c1abeb4d3a99f5"
LANE_C = "worktree-agent-aea4a82ef07084898"
LANE_D = "worktree-agent-a63bd2d9102384dba"

UK = {"United Kingdom", "Ireland"}
EU = {"Germany", "Sweden", "France", "Finland", "Netherlands", "Denmark",
      "Norway", "Belgium", "Austria", "Switzerland", "Poland", "Spain",
      "Italy", "Croatia", "Portugal", "Czechia"}
CAPS = {"uk": 2 * 45, "eu": 1 * 45}

#: CATEGORY WORDS. A pass resting only on these is a pass on vocabulary: every
#: agency site on earth carries them, so matching one says nothing about THIS
#: account. Hand-listed here and reported as a number, exactly as lane C did,
#: so the two measurements are comparable. `marketing` is counted separately
#: as well, because lane C found it doing the work in 53 of 54 single-word
#: passes and it is the specific thing this re-render has to move.
CATEGORY_WORDS = {
    "marketing", "advertising", "digital", "design", "designs", "creative",
    "agency", "agencies", "media", "brand", "brands", "branding", "content",
    "strategy", "strategic", "communications", "consultancy", "consulting",
    "studio", "teams", "clients", "client", "services", "service",
    "business", "company", "people", "projects", "project", "solutions",
    "growth", "development", "production", "commerce", "online", "website",
    "websites", "platform", "campaigns", "campaign", "experience",
}

#: Nothing below this is a quotable fact. A five-word fragment cannot be
#: recognised on a website and a thirty-word one is a paragraph.
MIN_QUOTE_WORDS = 6
MAX_QUOTE_WORDS = 26

#: Prose has function words. A navigation menu does not. Two of these in a
#: candidate is the cheapest test that separates "An independent creative
#: agency based in Clerkenwell, East London" from "Automotive Education
#: Hospitals Commercial Hotels Leisure Pubs Restaurants Retail".
#:
#: SEVEN LANGUAGES, NOT ONE, AND THAT IS NOT DECORATION. 117 of the 128 are
#: continental EU and their sites are in German, Swedish, Dutch, French,
#: Danish, Norwegian and Finnish. An English-only prose test scores every one
#: of those pages as navigation and HOLDS the lead for a reason that is about
#: this file rather than about the pack. Measured: it rejected 64 spans as
#: "not prose" on the first pass, and the samples were ordinary Dutch and
#: Swedish sentences.
STOPWORDS = {
    "en": {"the", "a", "an", "and", "of", "in", "for", "with", "that", "to",
           "our", "we", "is", "are", "as", "on", "from", "by", "at", "it",
           "its", "than", "into", "who", "where", "been", "have", "has",
           "was", "were", "not", "you", "your", "their", "this", "be", "but",
           "all", "what", "when", "which", "more", "over", "about", "based"},
    "de": {"und", "der", "die", "das", "wir", "mit", "fur", "für", "von",
           "den", "dem", "ist", "sind", "auf", "eine", "einen", "einer", "im",
           "zu", "nicht", "auch", "sich", "unsere", "unser", "als", "bei",
           "aus", "dass", "seit", "uber", "über", "wird", "einem", "ihre",
           "unserer", "unseren", "unserem", "ihnen", "sie", "ihr", "wenn",
           "oder", "durch", "schon", "alle", "mehr", "kann", "haben"},
    "nl": {"en", "de", "het", "een", "van", "wij", "onze", "met", "voor",
           "dat", "is", "zijn", "op", "aan", "door", "te", "niet", "ook",
           "bij", "uit", "worden", "waar", "ons", "maar", "als", "naar"},
    "sv": {"och", "att", "det", "ett", "vi", "var", "vår", "våra", "med",
           "for", "för", "som", "ar", "är", "pa", "på", "av", "till", "inte",
           "om", "den", "har", "kan", "vara", "eller", "sig"},
    "dansk": {"og", "at", "det", "en", "et", "vi", "vores", "med", "for",
              "som", "er", "pa", "på", "af", "til", "ikke", "om", "den",
              "har", "kan", "vaere", "være", "eller", "sig", "men"},
    "fr": {"et", "le", "la", "les", "de", "des", "du", "nous", "notre",
           "nos", "pour", "que", "qui", "est", "sont", "avec", "dans", "une",
           "un", "en", "sur", "au", "aux", "par", "plus", "vous", "votre",
           "ses", "son", "sa", "ne", "pas"},
    "fi": {"ja", "on", "se", "me", "meidan", "meidän", "etta", "että", "ei",
           "seka", "sekä", "kanssa", "tai", "joka", "ovat", "myos", "myös"},
    "es_it": {"y", "el", "los", "las", "que", "con", "para", "es", "son",
              "una", "nostro", "nostra", "della", "il", "dei", "gli", "e",
              "per", "non", "come", "sono", "nel"},
}
FUNCTION_WORDS = set().union(*STOPWORDS.values())

#: Page field -> what the sentence calls it. `extra.field` is written by
#: lane C's site source and is the crawler's own label for the page.
PAGE_LABEL = {
    "company_website": "home page",
    "about": "about page",
    "services": "services page",
    "work": "work page",
    "industries": "industries page",
    "careers": "careers page",
    "team": "team page",
    "blog": "blog",
    "news": "news page",
}

#: THE ONLY NEW COPY IN THIS LANE, and it is a frame around a quotation
#: rather than a claim of its own. Paragraphs 2 and 3 are campaign 489's
#: approved argument with the two sentences that named the company removed:
#: lane D measured 280 unsupported specifics at `body_1` and every one was
#: the company's own name in a sentence that also addressed the reader
#: (`persona_pain` is the only template of eight that does that). Nothing
#: here pairs a direct address with `{COMPANY}`, so that rule cannot fire.
BODY_1_GROUNDED = (
    "{FIRST}, I read {DOMAIN} before writing this rather than after. "
    "The {PAGE} says \"{QUOTE}\".\n\n"
    "I work with {INDUSTRY} teams on {ANGLE}. A position that specific is "
    "usually sold on scope and delivered in hours, and the two only meet at "
    "month end. Utilisation and margin per project are known after the month "
    "in which something could have been done about them. The work itself is "
    "rarely the problem. The visibility into it is.\n\n"
    "Is that roughly how it runs today, or is there already something in "
    "place for it?")


# ------------------------------------------------------------------ loading
#
# THE OTHER LANES' CODE, NOT A COPY OF IT. Three modules this needs live on
# three other branches and two of them are files this lane must not edit. A
# second copy of an identity guard is the thing the brief forbids by name, so
# the blob is read out of git and executed as the module it would have been.

def _blob(branch, path):
    out = subprocess.run(["git", "show", f"{branch}:{path}"], cwd=ROOT,
                         capture_output=True)
    if out.returncode:
        raise SystemExit(f"cannot read {branch}:{path}\n"
                         f"{out.stderr.decode('utf-8', 'replace')}")
    return out.stdout.decode("utf-8")


def _head(branch):
    out = subprocess.run(["git", "rev-parse", branch], cwd=ROOT,
                         capture_output=True)
    return out.stdout.decode().strip()[:8] if not out.returncode else "?"


def _module(name, text, package=None, origin="<blob>", file=None):
    spec = importlib.util.spec_from_loader(name, loader=None, origin=origin)
    mod = importlib.util.module_from_spec(spec)
    if package:
        mod.__package__ = package
    if file:
        # The blob computes its own ROOT from `__file__`. Given this tree's
        # path for the file it would have been, it lands on this worktree.
        mod.__file__ = file
    sys.modules[name] = mod
    exec(compile(text, origin, "exec"), mod.__dict__)
    return mod


def load_lanes(work=None):
    """`(cadence, s7, packfacts, actors)` - lane B's, lane D's and lane C's."""
    import src  # noqa: F401  (the package must exist before a submodule does)
    cad = _module("src.cadence", _blob(LANE_B, "src/cadence.py"),
                  package="src", origin=f"{LANE_B}:src/cadence.py",
                  file=os.path.join(ROOT, "src", "cadence.py"))
    s7 = _module("laneb_stage_s7_copy",
                 _blob(LANE_B, "scripts/stage_s7_copy.py"),
                 origin=f"{LANE_B}:scripts/stage_s7_copy.py",
                 file=os.path.join(ROOT, "scripts", "stage_s7_copy.py"))
    if work:
        # The supplier file lives in PRODUCTION's `work/`, not this locked
        # worktree's empty one. Repointed rather than copied.
        s7.SOURCE_CSV = os.path.join(work, "Productive",
                                     "productive_ICP_safe_to_send (1).csv")
    pf = _module("src.packfacts", _blob(LANE_D, "src/packfacts.py"),
                 package="src", origin=f"{LANE_D}:src/packfacts.py")
    ac = _module("lanec_actors", _blob(LANE_C, "src/researchpack/actors.py"),
                 origin=f"{LANE_C}:src/researchpack/actors.py")
    return cad, s7, pf, ac


def capability_by_persona():
    """Lane B's `product.capability_by_persona`, read from lane B's file.

    `config/clients/productive.yaml` is lane B's to edit and is not in this
    worktree's tree, so the one key rung 3 needs is read out of their blob and
    overlaid on the loaded config. Overlaid rather than reimplemented: the
    mapping is theirs and a second copy would be the drift this repository
    keeps finding.
    """
    import yaml
    doc = yaml.safe_load(_blob(LANE_B, "config/clients/productive.yaml")) or {}
    return ((doc.get("product") or {}).get("capability_by_persona")) or {}


# ------------------------------------------------------------------- packs

def _jsonl(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def cohort_rows(work_dir):
    """Every cached cohort fact, per domain, DE-DUPLICATED BY `fact_id`.

    Two caches hold the same crawl - lane C ran the site pass twice under two
    names - so a fact counted twice would inflate every number below.
    """
    out = collections.defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(
            work_dir, "researchpack-cohort-*-cache.json"))):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in (data or {}).values():
            if not isinstance(entry, dict):
                continue
            domain = str(entry.get("domain") or "").lower()
            for fact in entry.get("facts") or []:
                if isinstance(fact, dict) and fact.get("snippet"):
                    key = fact.get("fact_id") or json.dumps(fact, sort_keys=True)
                    out[domain][key] = fact
    return {d: list(v.values()) for d, v in out.items()}


def queue_rows(records):
    """`record["research"]` rows, per domain, as the same shape."""
    out = collections.defaultdict(list)
    for record in records:
        domain = str(record.get("domain") or "").lower()
        for row in record.get("research") or []:
            if isinstance(row, dict) and (row.get("fact") or row.get("snippet")):
                out[domain].append(dict(row, snippet=row.get("fact")
                                        or row.get("snippet")))
    return out


def admitted_pack(rows, domain, packfacts, actors):
    """`(pack, verdicts)` - identity-checked, with BOTH guards, fail-closed.

    `packfacts.identity_of` is lane D's and answers admitted / refused /
    unverifiable, and unverifiable is not a pass. `actors.is_this_company` is
    lane C's and is applied to `source_url` - the only website field a crawled
    page carries - which makes it the same host test asked a second time by a
    second author. A fact must satisfy BOTH. A LinkedIn post satisfies
    neither, because its host is LinkedIn's: identity for those has to be
    established upstream and was not, so they are excluded and counted.
    """
    rec = {"id": None, "domain": domain,
           "research": [dict(r) for r in rows]}
    pack, unused = packfacts.pack_for(rec)
    verdicts = collections.Counter()
    admitted = []
    for row in rows:
        verdict = packfacts.identity_of(row, domain)
        second = actors.is_this_company(row, domain, "source_url")
        if verdict == packfacts.ADMITTED and second:
            admitted.append(row)
            verdicts["admitted"] += 1
        elif verdict == packfacts.ADMITTED and not second:
            verdicts["admitted_but_second_guard_refused"] += 1
        else:
            verdicts[verdict] += 1
    pack = {"facts": [{"snippet": r.get("snippet"),
                       "source_url": r.get("source_url")} for r in admitted]}
    assert len(pack["facts"]) <= len(rows)
    del unused
    return pack, admitted, verdicts


# -------------------------------------------------------- the quotable fact

#: WRITTEN AS ESCAPES, NOT AS CHARACTERS, exactly as `lint` writes its
#: own: a replacement character and a non-breaking space are invisible
#: in a diff. U+FFFD is a LOST ENCODING - the page said an apostrophe
#: or a dash and the bytes did not survive - and quoting it puts a box
#: in front of a prospect where their own sentence had a letter.
_BAD_CHARS = re.compile("[\ufffd\u00a0\u202f\u2028\u2029]")
_URLISH = re.compile(r"https?://|www\.|@|\.com\b|\.co\.uk\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")

#: A CRAWLER READS THE CHROME AS WELL AS THE PAGE. None of these is what a
#: company says about itself, and every one was found inside a candidate this
#: extractor had already accepted - `The store will not work correctly in the
#: case when cookies are disabled` went out as idegroup.se's own words before
#: the list existed.
BOILERPLATE = (
    "browser does not support", "cookies are disabled", "enable javascript",
    "javascript is disabled", "privacy policy", "cookie policy",
    "all rights reserved", "skip to", "your browser", "video tag",
    "accept all cookies", "this website uses", "wordt geladen",
)

#: Words a QUOTATION may not OPEN on. They are the page's furniture - a menu
#: item, a section label, a stat-block header - and a quotation that begins on
#: one is a sentence the reader will not find on the page in that form.
NAV_WORDS = {
    "home", "menu", "search", "contact", "kontakt", "aktuellt", "us",
    "cases", "case", "blog", "news", "previous", "next", "explore", "read",
    "more", "start", "close", "skip", "video", "file", "years", "cities",
    "experts", "jobs", "careers", "team", "portfolio", "work", "works",
    "studies", "insights", "shop", "login", "download", "hem", "over",
}

#: A sentence usually opens on one of these, or on a name and then a verb.
#: Used to SCORE rather than to reject, because plenty of real sentences open
#: on neither and a reject here would be this file's taste, not a rule.
SENTENCE_OPENERS = {"we", "our", "the", "it", "this", "at", "since",
                    "founded", "established"}

#: A quotation may not OPEN on a coordinating conjunction. `And we know how
#: to bring the two together` is the second half of a sentence whose first
#: half was a heading, and the reader will not find it on the page that way.
CONJUNCTIONS = {"and", "but", "or", "so", "yet", "nor", "because", "als",
                "und", "och", "maar", "mais", "men"}

#: A capitalised word mid-sentence is ordinary English after one of these -
#: `based in Clerkenwell, East London`, `from Creative Direction`, `for
#: A-brands`. After anything else it is usually a heading that ran into the
#: prose behind it: `the new Exceeding your expectations`. An ACRONYM is the
#: exception and is allowed anywhere, because `an established FMCG agency`
#: and `stores in the EU` are sentences, not seams.
BEFORE_A_NAME = {"in", "at", "of", "from", "to", "for", "with", "by", "near",
                 "and", "or", "the", "a", "an", "across", "around", "into",
                 "on", "as", "like", "including", "between"}
COPULAS = {"is", "are", "was", "were", "has", "have", "helps", "help",
           "builds", "build", "creates", "create", "works", "work", "offers",
           "offer", "delivers", "deliver", "designs", "design", "makes",
           "make", "brings", "bring", "turns", "turn", "started", "began"}


def _strip_nav(rows):
    """Drop the word-prefix every page of this site shares.

    Every crawled page of one site opens with the same menu, so the longest
    common word prefix across the site's snippets IS the navigation. Measured
    on this cohort: 30 words on sign-specialists.co.uk, 52 on pushon.co.uk -
    where it is the whole snippet, which is how that domain correctly ends up
    with nothing to quote.
    """
    snips = [str(r.get("snippet") or "") for r in rows]
    tails = []
    if len(snips) > 1:
        words = [s.split() for s in snips]
        limit = min(len(w) for w in words)
        i = 0
        while i < limit and all(w[i] == words[0][i] for w in words):
            i += 1
    else:
        i = 0
    for row, snip in zip(rows, snips):
        tails.append((row, " ".join(snip.split()[i:])))
    return tails, i


def _prose_start(words):
    """Index where this page stops being a menu and starts being prose.

    `_strip_nav` removes the menu every page of a site SHARES. It cannot help
    a domain that returned one page, or whose pages carry different menus, and
    on this cohort that left navigation glued to the front of the first real
    sentence. So each page is scanned as well: prose begins at the first
    six-word window carrying three or more uncapitalised words, which a menu
    (Title Case end to end) never does.
    """
    for i in range(0, max(0, len(words) - 5)):
        window = words[i:i + 6]
        if sum(1 for w in window if w[:1].islower()) >= 3:
            return i
    return 0


def language_of(text):
    """`(language, hits)` - the stopword set this span matches best.

    NOT A LANGUAGE DETECTOR, and it is not pretending to be one. It answers
    the only question this lane has to ask: is this sentence English, so that
    quoting it inside an English email reads as one sentence rather than two
    languages. Ties and thin evidence come back as `unknown`, which is held.
    """
    tokens = [w.strip(".,;:!?()\"'").lower() for w in text.split()]
    tokens = [t for t in tokens if t]
    scores = {lang: sum(1 for t in tokens if t in words)
              for lang, words in STOPWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    top = scores[best]
    # THREE, NOT TWO, AND IT IS MEASURED. At two, `Konzeption all unserer
    # Projekte denken wir zunaechst an Sie` scored English 2 on `all` and `an`
    # - both of which are also German words - against German 1, and a German
    # sentence was quoted inside an English email.
    if top < 3:
        return "unknown", scores
    if sum(1 for v in scores.values() if v == top) > 1:
        # A tie between English and anything else is not English enough to
        # quote. Shared words - "de", "en", "for", "is" - are exactly what
        # ties look like.
        return "unknown", scores
    return best, scores


def _candidates(text, truncated):
    """Sentence-ish spans of a page's prose, with the truncated tail dropped.

    Every snippet is cut at a fixed length, so its LAST span is very often a
    half sentence ending mid-word. Quoting one would put a fragment in front
    of a prospect that does not appear on their site in that form, which is
    the opposite of grounding. It is dropped unless the snippet ends on
    sentence punctuation.
    """
    parts = [p.strip(" \t ") for p in _SENT.split(text) if p.strip()]
    if parts and truncated:
        parts = parts[:-1]
    return parts


def _starts(words):
    """Offsets a QUOTATION may begin at: 0, and each place a heading ends.

    A crawled page glues its headings to its prose with no punctuation
    between, so the sentence-split above hands back one span holding both:
    `in advertising Products Techniques Our strength We are Fotolight
    Fotolight is a production company with 70 years of experience...`. A
    sentence begins where a capitalised word is followed by a lowercase one,
    so every such offset is offered and `_quality` throws away the ones that
    still carry a menu. The clean suffix of that example is `Fotolight is a
    production company with 70 years of experience in outdoor and instore
    communication for A-brands`, which is the sentence on the page.
    """
    out = [0]
    for i in range(1, len(words) - 1):
        if words[i][:1].isupper() and words[i + 1][:1].islower():
            out.append(i)
    return out


def _quality(cand, copylint):
    """Why this span may not be quoted, or None when it may be."""
    if _BAD_CHARS.search(cand):
        return "mojibake"          # a lost encoding is not their sentence
    if _URLISH.search(cand):
        return "url or address"
    words = cand.split()
    if not (MIN_QUOTE_WORDS <= len(words) <= MAX_QUOTE_WORDS):
        return "length"
    # A QUOTATION STARTS WHERE A SENTENCE STARTS. `& BEVERAGE Delivering the
    # tastiest...` is a fragment of a heading and putting it in quotation
    # marks in front of a person claims their page says something it does not
    # say in that form. A first word ending in a comma or a colon - `Dance:`,
    # `Hits,` - is the middle of one.
    if not (words[0][:1].isalpha() and words[0][:1].isupper()):
        return "starts mid-sentence"
    if words[0].rstrip()[-1:] in (",", ":", ";"):
        return "starts mid-sentence"
    low_all = cand.lower()
    if any(phrase in low_all for phrase in BOILERPLATE):
        return "boilerplate"
    if any(w.strip(".,;:!?()").lower() in NAV_WORDS for w in words[:3]):
        return "opens on navigation"
    run = 0
    for word in words:
        run = run + 1 if word[:1].isupper() else 0
        if run >= 4:
            return "heading run"   # four capitalised words together is a menu
    low = [w.strip(".,;:!?()").lower() for w in words]
    for a, b in zip(low, low[1:]):
        if a and a == b:
            return "glued repeat"  # `Fotolight Fotolight` is two page regions
    # TWO PAGE REGIONS WITH NO PUNCTUATION BETWEEN THEM. `We handle the
    # funding We are a data-driven growth engine` is a heading and a sentence
    # run together by the crawler. The tell is a capitalised FUNCTION word in
    # the middle of a sentence: a proper noun there is ordinary English -
    # `based in Clerkenwell, East London` must survive - but `We`, `And`,
    # `At` and `The` mid-sentence mean a new region started.
    if low[0] in CONJUNCTIONS:
        return "opens on a conjunction"
    for i in range(1, len(words)):
        prev, here = words[i - 1], words[i]
        if not here[:1].isupper() or prev[:1].isupper():
            continue
        if prev.rstrip()[-1:] in (".", "!", "?", ":"):
            continue
        if len(here) > 1 and here[0].isupper() and here[1].isupper():
            continue          # an acronym: FMCG, EU, AI-driven, DTC
        if low[i] in STOPWORDS["en"] or low[i - 1] not in BEFORE_A_NAME:
            return "glued sentence"
    if copylint.DASH_RE.search(cand):
        return "dash"              # copylint rule 5 fires on the whole body
    if copylint.buzzwords_in(cand):
        return "buzzword"          # copylint rule 6, and agency sites are full
    low = [w.strip(".,;:!?()").lower() for w in words]
    if sum(1 for w in low if w in FUNCTION_WORDS) < 2:
        return "not prose"
    titled = sum(1 for w in words if w[:1].isupper())
    if titled > 0.6 * len(words):
        return "navigation"        # a menu is Title Case end to end
    if not any(len(w) > 3 and w.lower() not in CATEGORY_WORDS for w in low):
        return "category words only"
    if '"' in cand:
        return "nested quotation"
    return None


def _score(cand, field):
    """Higher is a better sentence to put in front of a person.

    THE CAPITAL-LETTER PENALTY IS THE LOAD-BEARING TERM. Without it the
    longest span wins, and the longest span is the one with the menu still
    glued to the front: `Contact Us Shomei is built around creative minds...`
    outscored `Shomei is built around creative minds...` purely on length.
    Every capitalised word after the first is evidence of a heading, so each
    one costs more than an extra distinct word earns.
    """
    words = cand.split()
    low = [w.strip(".,;:!?()").lower() for w in words]
    distinct = sum(1 for w in set(low)
                   if len(w) > 4 and w not in CATEGORY_WORDS)
    score = 2.0 * distinct
    score -= 2.5 * sum(1 for w in words[1:] if w[:1].isupper())
    score += 3.0 if field == "about" else 1.0 if field == "services" else 0.0
    score += 2.0 if re.search(r"\b(19|20)\d{2}\b", cand) else 0.0
    score += 1.0 if re.search(r"\bbased in\b|\bfounded\b|\bestablished\b",
                              cand, re.I) else 0.0
    score += 2.0 if low[0] in SENTENCE_OPENERS else 0.0
    score += 2.0 if len(low) > 1 and low[1] in COPULAS else 0.0
    score -= 3.0 if re.search(r"\byou\b|\byour\b", cand, re.I) else 0.0
    score -= abs(len(words) - 14) * 0.25
    return score


from src import lint as _LINT                                    # noqa: E402


def grounded_fact(rows, copylint, english_only=True):
    """The one span this lead's step 1 will quote, or None.

    `rows` are already identity-admitted. Returns `(best, reason, seen)`;
    `seen` carries the best NON-ENGLISH candidate as well, so the cost of the
    English-only rule is a number in the report rather than an assertion.
    """
    site = [r for r in rows if (r.get("kind") or "site_page") == "site_page"]
    if not site:
        return None, "no site page admitted to this pack", {}
    tails, nav = _strip_nav(site)
    best, foreign, rejected = None, None, collections.Counter()
    for row, tail in tails:
        words = tail.split()
        tail = " ".join(words[_prose_start(words):])
        if not tail.strip():
            rejected["page is navigation end to end"] += 1
            continue
        snippet = str(row.get("snippet") or "")
        truncated = not snippet.rstrip().endswith((".", "!", "?"))
        field = (row.get("extra") or {}).get("field") or ""
        spans = []
        for cand in _candidates(tail, truncated):
            # `lint.normalise_punctuation`, the estate's own map, applied to
            # the QUOTE before anything else looks at it. A site writes a
            # curly apostrophe and `lint` calls that a substituted character
            # because it is what becomes "you?re" the moment something in the
            # chain guesses an encoding. `lint` says out loud that this is
            # pre-processing rather than patching a failing draft, and it
            # cannot change whether the quote traces: `copylint.pack_text`
            # strips punctuation on both sides of the comparison.
            cand = _LINT.normalise_punctuation(cand)
            words = cand.split()
            spans.extend(" ".join(words[i:]) for i in _starts(words))
        for cand in spans:
            why = _quality(cand, copylint)
            if why:
                rejected[why] += 1
                continue
            lang, _scores = language_of(cand)
            entry = {"quote": cand.rstrip(".").strip(),
                     "score": _score(cand, field), "field": field,
                     "language": lang, "source_url": row.get("source_url"),
                     "fact_id": row.get("fact_id"),
                     "page": PAGE_LABEL.get(field, "site"),
                     "nav_words_stripped": nav}
            if lang == "en":
                if best is None or entry["score"] > best["score"]:
                    best = entry
            else:
                rejected[f"not english ({lang})"] += 1
                if foreign is None or entry["score"] > foreign["score"]:
                    foreign = entry
    seen = {"best_non_english": foreign}
    if best is not None:
        return best, None, seen
    if foreign is not None and not english_only:
        return foreign, None, seen
    if foreign is not None:
        return None, ("the only quotable spans on this site are not in "
                      f"English ({foreign['language']})"), seen
    top = ", ".join(f"{k} {v}" for k, v in rejected.most_common(3))
    return None, f"no quotable span on any admitted page ({top or 'none'})", seen


# ------------------------------------------------------------- measurement

def matched_tokens(opener, pack, copylint):
    """Rule 1's own tokens, and which of them the pack supports."""
    supported = copylint.pack_text(pack)
    tokens = [t for t in copylint._WORD.findall(str(opener or "").lower())
              if len(t) > 4]
    hit = sorted({t for t in tokens if t and t in supported})
    return supported, hit


def anchor_run(opener, pack, copylint):
    """Longest contiguous run of opener words that appears in the pack.

    THIS IS THE MEASUREMENT THAT MATTERS AND RULE 1 IS NOT. Rule 1 asks
    whether ANY word over four letters appears anywhere in the pack, which a
    long dump of a site's prose answers by accident - 53 of lane C's passes on
    the single word `marketing`. A contiguous run cannot be answered by
    accident: a run of six words present verbatim is a quotation, and a run of
    one is a coincidence.
    """
    supported = copylint.pack_text(pack)
    words = copylint._norm(opener).split()
    if not supported or not words:
        return 0, ""
    for length in range(min(len(words), 30), 0, -1):
        for i in range(0, len(words) - length + 1):
            span = " ".join(words[i:i + length])
            if span in supported:
                return length, span
    return 0, ""


def measure(opener, pack, copylint):
    supported, hit = matched_tokens(opener, pack, copylint)
    run, span = anchor_run(opener, pack, copylint)
    return {
        "rule1": bool(supported) and bool(hit),
        "matched": hit,
        "n_matched": len(hit),
        "single_word": len(hit) == 1,
        "single_word_is_marketing": hit == ["marketing"],
        "category_only": bool(hit) and all(t in CATEGORY_WORDS for t in hit),
        "anchor_words": run,
        "anchor": span,
    }


# ------------------------------------------------------------------- render

def render_lead(lead, row, fact, config, s7, copylint, prelint=True):
    """`(variables, hold_reason)` for one lead at five steps."""
    first = s7.first_name(row.get("First Name"))
    company = (row.get("Company") or "").strip()
    industry = (row.get("Industry") or "").strip()
    title = (row.get("Job Title") or "").strip()
    if not first:
        return None, "no usable first name"
    if not company:
        return None, "no company name"
    if not industry:
        return None, "no industry"
    persona, angle_key, angle = s7.angle_for(title, config)
    if not persona:
        return None, f"title matches no persona: {title!r}"
    if not angle:
        return None, f"no angle written for {persona!r} with title {title!r}"

    subject_1 = s7.subject_for(angle, config)
    if len(subject_1) > s7.MAX_SUBJECT:
        return None, f"subject is {len(subject_1)} characters"

    body_1 = BODY_1_GROUNDED
    for key, value in (("FIRST", first), ("DOMAIN", lead["domain"]),
                       ("PAGE", fact["page"]), ("QUOTE", fact["quote"]),
                       ("INDUSTRY", industry), ("ANGLE", angle)):
        body_1 = body_1.replace("{" + key + "}", value)
    left = s7.PLACEHOLDER.search(body_1)
    if left:
        return None, f"body_1 did not fully render: {left.group(0)}"

    body_2 = s7.BODY_2
    for key, value in (("FIRST", first), ("COMPANY", company),
                       ("INDUSTRY", industry), ("ANGLE", angle)):
        body_2 = body_2.replace("{" + key + "}", value)
    if s7.PLACEHOLDER.search(body_2):
        return None, "body_2 did not fully render"

    later, reason = s7._steps_three_four_and_five(
        persona, angle_key, angle, first, company, config)
    if reason:
        return None, reason

    words = len(body_1.split())
    if not 40 <= words <= 180:
        return None, f"body_1 is {words} words"

    # THE LINT IS ASKED PER LEAD HERE SO THE BATCH CANNOT BE REFUSED FOR IT,
    # and every lead it catches is HELD with the rule's own name rather than
    # quietly shipped. This is deliberately not a way of making the batch
    # report green: the counts moved into `hold_reasons`, where §HOLDS reports
    # them, and a reader can add the two together.
    #
    # `dash` is the one that fires, and NOT on anything written here. Nine of
    # the 179 carry a SUPPLIER company name containing a spaced hyphen -
    # "Quickfire - Shopify Premier Partner" - and steps 2 to 5 all embed
    # `{company}`, so the rule fires on approved copy because of a CSV field.
    bodies = [body_1, body_2] + [later[f"body_{i}"] for i in (3, 4, 5)]
    whole = "\n".join(bodies)
    hit = copylint.DASH_RE.search(whole) if prelint else None
    if hit:
        where = "the company name" if copylint.DASH_RE.search(company) \
            else "the rendered copy"
        return None, f"copylint dash: a dash used as punctuation, in {where}"
    buzz = copylint.buzzwords_in(whole) if prelint else []
    if buzz:
        return None, f"copylint buzzword: {', '.join(buzz[:3])}"

    out = {"subject_1": subject_1, "body_1": body_1, "body_2": body_2,
           "persona": persona, "angle": angle, "angle_key": angle_key,
           "title": title, "company": company, "industry": industry}
    out.update(later)
    out["pack_fact"] = {
        "quote": fact["quote"], "page": fact["page"],
        "source_url": fact["source_url"], "fact_id": fact["fact_id"],
        "nav_words_stripped": fact["nav_words_stripped"]}
    return out, None


# --------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--client", default="productive")
    parser.add_argument("--out-prefix", default="lane-h")
    parser.add_argument(
        "--no-prelint", action="store_true",
        help="THE RED CHECK. The batch report below PASSES because every "
             "lead that would have failed was HELD here first, and a gate "
             "that cannot fail is not evidence. This turns the per-lead "
             "hold off so copylint sees those leads and refuses them by "
             "name.")
    parser.add_argument(
        "--allow-non-english", action="store_true",
        help="quote a span in the site's own language. OFF by default: it is "
             "grounded, and whether a Swedish sentence belongs inside an "
             "English email is a copy decision no measurement here can make.")
    args = parser.parse_args(argv)

    work = os.path.abspath(args.work)
    os.environ["QUEUE"] = os.path.join(work, "queue.jsonl")
    os.environ["CLIENT_APPROVAL"] = os.path.join(work, "client-approval.jsonl")

    cadence, s7, packfacts, actors = load_lanes(work)
    from src import clientapproval as ca, clients, copylint, store

    config = clients.load(args.client)
    caps = capability_by_persona()
    config.setdefault("product", {})["capability_by_persona"] = caps
    print(f"  capability_by_persona from {LANE_B}: {caps}")

    stage = os.path.join(work, "stage")
    icp = {str(r.get("domain", "")).lower(): r
           for r in _jsonl(os.path.join(stage, "s3-icp.jsonl"))}

    journal = list(_jsonl(os.path.join(stage, "s7-copy.jsonl")))
    rendered = [r for r in journal if r.get("state") == "rendered"]

    leads = []
    for row in rendered:
        email = str(row.get("email", "")).lower()
        domain = email.split("@")[-1]
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = "uk" if country in UK else "eu" if country in EU else None
        if not cohort or not ca.is_approved(domain, args.client):
            continue
        leads.append({"email": email, "domain": domain, "cohort": cohort,
                      "country": country, "journal": row.get("variables") or {}})

    records = store.load()
    have_record = {str(r.get("domain") or "").lower() for r in records}
    capped, per = [], collections.Counter()
    for lead in leads:
        if per[lead["cohort"]] < CAPS[lead["cohort"]]:
            per[lead["cohort"]] += 1
            capped.append(lead)
    capped_emails = {x["email"] for x in capped}
    the_128 = [x for x in leads if x["domain"] not in have_record]

    print(f"\n  journal rows          {len(journal)}")
    print(f"  rendered              {len(rendered)}")
    print(f"  UK/EU rendered+appr   {len(leads)} over "
          f"{len({x['domain'] for x in leads})} domain(s)")
    print(f"  under the caps        {len(capped)}")
    print(f"  NO queue record       {len(the_128)} over "
          f"{len({x['domain'] for x in the_128})} domain(s)")

    cohort_by_domain = cohort_rows(work)
    queue_by_domain = queue_rows(records)
    supplier = s7.merge_index([x["email"] for x in leads])
    supplier_all = s7.merge_index([str(r.get("email", "")) for r in rendered])

    verdict_totals = collections.Counter()
    out_rows = []
    for lead in leads:
        rows = (cohort_by_domain.get(lead["domain"]) or []) \
            + (queue_by_domain.get(lead["domain"]) or [])
        pack, admitted, verdicts = admitted_pack(rows, lead["domain"],
                                                 packfacts, actors)
        verdict_totals.update(verdicts)
        before = measure(copylint.first_line(lead["journal"].get("body_1")),
                         pack, copylint)
        fact, why, seen = grounded_fact(admitted, copylint,
                                        english_only=not args.allow_non_english)
        entry = {"email": lead["email"], "domain": lead["domain"],
                 "cohort": lead["cohort"], "country": lead["country"],
                 "in_128": lead["domain"] not in have_record,
                 "in_105": lead["email"] in capped_emails,
                 "pack_rows": len(rows), "pack_facts_admitted": len(admitted),
                 "identity": dict(verdicts), "before": before,
                 "has_non_english_span": bool(seen.get("best_non_english"))}
        if fact is None:
            entry.update({"state": "held", "reason": why, "after": None})
            out_rows.append(entry)
            continue
        supplier_row = supplier.get(lead["email"])
        if supplier_row is None:
            entry.update({"state": "held",
                          "reason": "not in the supplier file", "after": None})
            out_rows.append(entry)
            continue
        variables, reason = render_lead(lead, supplier_row, fact, config, s7,
                                        copylint,
                                        prelint=not args.no_prelint)
        if reason:
            entry.update({"state": "held", "reason": reason, "after": None})
            out_rows.append(entry)
            continue
        entry.update({
            "state": "rendered", "reason": None,
            "after": measure(copylint.first_line(variables["body_1"]), pack,
                             copylint),
            "variables": variables})
        out_rows.append(entry)

    # ---- the batch lint, asked of the re-rendered cohort at FIVE steps
    lint_sets = collections.OrderedDict()
    for label, pool in (("the 128 (no queue record)",
                         [r for r in out_rows if r["in_128"]]),
                        ("all UK/EU rendered + approved (179)", out_rows),
                        ("under the cohort caps (105)",
                         [r for r in out_rows if r["in_105"]])):
        shipped = [r for r in pool if r["state"] == "rendered"]
        batch, packs = [], {}
        for r in shipped:
            v = r["variables"]
            batch.append({"id": r["email"],
                          "steps": [{"body": v[f"body_{i}"]} for i in range(1, 6)]})
            rows = (cohort_by_domain.get(r["domain"]) or []) \
                + (queue_by_domain.get(r["domain"]) or [])
            pack, admitted, _ = admitted_pack(rows, r["domain"], packfacts,
                                              actors)
            packs[r["email"]] = pack
        report = copylint.check_batch(batch, packs, steps_expected=5)
        lint_sets[label] = {"pool": len(pool), "rendered": len(shipped),
                            "held": len(pool) - len(shipped),
                            "copylint": report}

    heads = {"lane_b": _head(LANE_B), "lane_c": _head(LANE_C),
             "lane_d": _head(LANE_D), "lane_h": _head("HEAD"),
             "english_only": not args.allow_non_english,
             "prelint": not args.no_prelint}
    print("\n  built from  lane B %s | lane C %s | lane D %s | this lane %s"
          % (heads["lane_b"], heads["lane_c"], heads["lane_d"],
             heads["lane_h"]))
    summary = {"branches": heads, "sets": {}, "identity": dict(verdict_totals),
               "lint": {k: {kk: vv for kk, vv in v.items()}
                        for k, v in lint_sets.items()}}
    for label, pool in (("the 128 (no queue record)",
                         [r for r in out_rows if r["in_128"]]),
                        ("all UK/EU rendered + approved (179)", out_rows),
                        ("under the cohort caps (105)",
                         [r for r in out_rows if r["in_105"]])):
        def tally(key):
            got = [r[key] for r in pool if r[key]]
            passes = [m for m in got if m["rule1"]]
            return {
                "leads": len(pool),
                "measured": len(got),
                "rule1_pass": len(passes),
                "single_word_passes": sum(1 for m in passes if m["single_word"]),
                "single_word_marketing": sum(
                    1 for m in passes if m["single_word_is_marketing"]),
                "category_only_passes": sum(
                    1 for m in passes if m["category_only"]),
                "anchor_ge_4": sum(1 for m in passes if m["anchor_words"] >= 4),
                "anchor_median": sorted(m["anchor_words"] for m in passes)[
                    len(passes) // 2] if passes else 0,
            }
        summary["sets"][label] = {
            "before": tally("before"),
            "after": tally("after"),
            "held": sum(1 for r in pool if r["state"] == "held"),
            "rendered": sum(1 for r in pool if r["state"] == "rendered"),
            "hold_reasons": dict(collections.Counter(
                r["reason"].split("(")[0].strip() for r in pool
                if r["state"] == "held")),
            "with_pack_fact": sum(1 for r in pool if r["pack_facts_admitted"]),
        }

    for label, block in summary["sets"].items():
        print(f"\n{label.upper()}")
        print(f"  leads {block['before']['leads']}   "
              f"carry an identity-admitted fact {block['with_pack_fact']}")
        print(f"  re-rendered {block['rendered']}   HELD {block['held']}")
        for name, row in (("before", block["before"]), ("after", block["after"])):
            print(f"    {name:<7} measured {row['measured']:>4}  "
                  f"rule1 {row['rule1_pass']:>4}  "
                  f"single-word {row['single_word_passes']:>4}  "
                  f"of which `marketing` {row['single_word_marketing']:>4}  "
                  f"category-only {row['category_only_passes']:>4}  "
                  f"anchor>=4 {row['anchor_ge_4']:>4}  "
                  f"median anchor {row['anchor_median']}")
        for reason, count in sorted(block["hold_reasons"].items(),
                                    key=lambda kv: -kv[1]):
            print(f"      HELD  {reason[:62].ljust(62)} {count:>4}")

    # A SUPPLIER FIELD THAT REFUSES THE PUSH, and it is not a UK/EU property.
    # `copylint`'s dash rule reads the WHOLE body, steps 2 to 5 all embed
    # `{company}`, and some Company cells in the supplier CSV are
    # "Quickfire - Shopify Premier Partner". The rule then fires on APPROVED
    # copy because of a CSV cell, on every cohort, not only this one.
    dashed = [r for r in rendered
              if copylint.DASH_RE.search(
                  (supplier_all.get(str(r.get("email", "")).lower()) or {})
                  .get("Company") or "")]
    print("\nCOMPANY NAMES CARRYING A copylint DASH  (a supplier-field defect)")
    print(f"  of the 814 rendered journal rows   {len(dashed)}")
    for label, pool in (("of the 128", [r for r in out_rows if r["in_128"]]),
                        ("of the 179", out_rows),
                        ("of the 105", [r for r in out_rows if r["in_105"]])):
        hit = [r for r in pool
               if copylint.DASH_RE.search(
                   (supplier.get(r["email"]) or {}).get("Company") or "")]
        print(f"  {label:<33} {len(hit)}")
    summary["dashed_company_names"] = {
        "rendered_journal_rows": len(dashed),
        "the_128": sum(1 for r in out_rows if r["in_128"] and
                       copylint.DASH_RE.search(
                           (supplier.get(r["email"]) or {}).get("Company") or "")),
        "names": sorted({(supplier.get(r["email"]) or {}).get("Company")
                         for r in out_rows
                         if copylint.DASH_RE.search(
                             (supplier.get(r["email"]) or {}).get("Company")
                             or "")}),
    }

    print("\nIDENTITY OVER EVERY FACT OFFERED TO THESE 179 LEADS")
    for name, count in verdict_totals.most_common():
        print(f"  {name.ljust(40)} {count:>6}")

    print("\nCOPYLINT, five steps, on what would actually be pushed")
    for label, block in lint_sets.items():
        print(f"\n  {label}: {block['rendered']} rendered, "
              f"{block['held']} held")
        for line in copylint.report_lines(block["copylint"]):
            print("    " + line)

    os.makedirs(work, exist_ok=True)
    detail = os.path.join(work, f"{args.out_prefix}-render-2026-09-25.json")
    with open(detail, "w", encoding="utf-8") as handle:
        json.dump(out_rows, handle, indent=1, ensure_ascii=False, default=str)
    brief = os.path.join(work, f"{args.out_prefix}-summary-2026-09-25.json")
    with open(brief, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, ensure_ascii=False, default=str)
    print(f"\nwrote {detail}\nwrote {brief}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
