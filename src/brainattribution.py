"""Does a Second Brain entry REACH the text, and WHICH SENTENCE uses it.

WHAT THIS IS FOR
================
`secondbrain.for_task` is a producer. The operator's question is not whether
it produces - it demonstrably does, 50 facts for `productive` - but whether
anything downstream is CHANGED by what it produced. "Entry 7 was retrieved"
is not evidence. "Entry 7 supplies the clause `live budget burn` in sentence
2 of em1" is evidence, and so is "entry 7 reached nothing".

So this module answers three questions about one piece of text:

    which entries were RETRIEVED      `catalogue`
    which of those REACHED the text   `attribute`, field `reached`
    WHICH SENTENCE uses each one      `attribute`, field `sentences`

OFF BY DEFAULT, AND NOTHING IN THE COPY PATH IMPORTS IT
=======================================================
This is an OBSERVATION module. `src/generate_campaign.py`,
`src/copystages.py`, `src/generate.py` and `src/sequenceplan.py` do not
import it and must not: the seams it needs already exist (`model` is
injectable on `generate_campaign.generate`, `secondbrain.for_task` is a
module attribute). `observe()` and `ablated()` are context managers that
patch and restore, so a process that never calls them runs the production
flow unaltered.

WHY THE MATCH RULE IS CONTIGUOUS WORDS AND NOT A BAG OF WORDS
=============================================================
A bag-of-words or single-keyword rule is the checker that cannot fail. Every
one of `productive`'s brain entries is about agencies, margin, budgets and
time, and so is every piece of copy the pipeline writes - so "does any word
of the entry appear in the sentence" answers YES for all 50 entries against
any draft, and an attribution that says everything is used says nothing.

The rule here is therefore: an entry reaches a sentence when the entry's own
VALUE (its payload, with the formatter's label prefix stripped) shares a
CONTIGUOUS run of words with that sentence, at least `MIN_NGRAM` words long,
containing at least `MIN_CONTENT` words that are not stopwords. The matched
run is returned verbatim as the `clause`, so every claim of use can be read
and disagreed with.

`MIN_CONTENT` is the half that makes it falsifiable. Without it, "and what
it has" clears a three-word bar and a run of stopwords licenses a match
against almost any sentence - which is the bag-of-words failure wearing an
n-gram's clothes.

THREE BUCKETS, NOT TWO, AND WHY THE THIRD IS NOT ROUNDED DOWN
=============================================================
Some entries cannot be decided by text matching at all. `Min employees: 20`
has the payload `20`; `Product: Productive` has the payload `Productive`.
A sentence containing the digit 2 or the client's own brand name is not
evidence that the brain supplied it, and declaring such an entry UNUSED
would be just as wrong - the measurement simply cannot see.

So `attribute` reports REACHED, NOT REACHED and UNATTRIBUTABLE separately.
Rounding the third bucket down into "not used" would make a negative verdict
cheaper to reach, which is the direction a measurement must never be
generous in.

AND TEXT OVERLAP IS NOT CAUSATION. `copystages.WRITER_SYSTEM` names
Productive, margin per project and projects/tasks/delivery in its own
constant text, and `config/clients/<client>.yaml product.capabilities`
reaches the writer as `cap_sentence` without passing through the brain at
all. So an entry's words appearing in a prompt or a draft proves nothing on
its own. The authoritative measure is `brain_caused`: reached WITH the brain
and not reached WITHOUT it.
"""
import contextlib
import re

#: Shortest contiguous word run that counts as a use.
MIN_NGRAM = 3

#: How many of those words must carry meaning. See the module docstring: a
#: run of stopwords is not evidence of anything.
MIN_CONTENT = 2

STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for
with without from by as is are was were be been being am do does did doing
have has had having it its it's they them their there here what which who
whom whose when where why how all any both each few more most other some
such no nor not only own same so too very can will just should now up down
out off over under again further once about into through during before after
above below between you your yours we us our ours i me my mine he him his
she her hers one two also while rather instead per
""".split())

_WORD = re.compile(r"[a-z0-9][a-z0-9'/_.-]*")

#: The label prefixes `secondbrain`'s own extractors prepend. Stripping them
#: matters: `Persona 'champion', angle 'delivery': live budget burn` carries
#: the words "persona", "angle", "champion" and "delivery" that are the
#: FORMATTER's, not the client's knowledge. Attributing a sentence to an
#: entry because both contain the word "delivery" would credit the brain for
#: a word the brain's own formatting invented.
_LABEL_SPLIT = re.compile(
    r"^(?:"
    r"Product|Domain|ICP must|Target geos|Excluded geos|Company types|"
    r"Verticals|Min employees|Size min employees|Tone \([a-z]+\)|"
    r"Angle label '[^']*'|Capability for [a-z_]+|"
    r"LinkedIn fallback \([a-z0-9_]+\)|"
    r"Persona '[^']*'(?:, angle '[^']*')?(?: titles| cap per domain)?"
    r"): ?")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def entry_id(index):
    """The stable id an entry is reported under. One scheme, everywhere."""
    return "SB-%02d" % (index + 1)


def fact_value(text):
    """The entry's PAYLOAD: what the client said, without the label the
    formatter put in front of it.

    Falls back to the whole text when no known label matches, so an entry
    from a section this function has never seen is attributed on its full
    text rather than silently on nothing.
    """
    text = str(text or "")
    stripped = _LABEL_SPLIT.sub("", text, count=1)
    return stripped.strip() or text.strip()


def _words(text):
    return _WORD.findall(str(text or "").lower())


def _content_count(words):
    return sum(1 for w in words if w not in STOPWORDS and len(w) > 2)


def split_sentences(text):
    """Sentences, numbered from 1, with the raw text of each.

    Deliberately simple. The unit this reports against must be something a
    reader can point at in the output, and the copy this pipeline writes is
    plain prose with terminal punctuation.
    """
    parts = [p.strip() for p in _SENT_SPLIT.split(str(text or ""))]
    return [p for p in parts if p]


def catalogue(brain):
    """The RETRIEVED set, as a flat list of entries with ids.

    `brain` is either `secondbrain.for_task`'s dict of sections or a flat
    list of facts (which is what `generate_campaign._load_admitted_facts`
    returns). Both shapes occur in the live path, so both are accepted and
    the id scheme is the same.
    """
    flat = []
    if isinstance(brain, dict):
        for section in sorted(brain):
            for fact in brain[section] or ():
                flat.append((section, fact))
    else:
        for fact in brain or ():
            flat.append((_section_of(fact), fact))

    out = []
    for i, (section, fact) in enumerate(flat):
        source = fact.get("source", "")
        key = source.split(" ", 1)[-1] if " " in source else source
        out.append({
            "id": entry_id(i),
            "section": section,
            "key": key,
            "source": source,
            "text": fact.get("text", ""),
            "value": fact_value(fact.get("text", "")),
            "verified": bool(fact.get("verified")),
            "canonical_status": fact.get("canonical_status"),
        })
    return out


def _section_of(fact):
    """Best-effort section for a flat fact. Only a label; never a gate."""
    key = fact.get("source", "")
    key = key.split(" ", 1)[-1] if " " in key else key
    if key.startswith("personas."):
        return "customers"
    if key.startswith(("market.", "icp.")):
        return "market"
    if key.startswith(("tone.", "angle_labels", "linkedin_sequence.",
                       "product.capability_by_persona")):
        return "messaging"
    return "profile"


def longest_shared_run(value, sentence):
    """The longest contiguous word run `value` and `sentence` share.

    Returns `(words, start_in_sentence)` or `(None, -1)`. Plain dynamic
    programming over the two word lists; the texts here are a sentence and a
    config line, so the quadratic cost is irrelevant and the result is exact
    rather than a heuristic.
    """
    a, b = _words(value), _words(sentence)
    if not a or not b:
        return None, -1
    best_len, best_end_b = 0, -1
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len, best_end_b = cur[j], j
        prev = cur
    if best_len == 0:
        return None, -1
    start = best_end_b - best_len
    return b[start:best_end_b], start


def attribute(entries, text, *, min_ngram=MIN_NGRAM, min_content=MIN_CONTENT):
    """Per-entry, per-sentence attribution of `entries` into `text`.

    Returns a list of records in the order of `entries`, each carrying:

        id, key, text            the entry, as `catalogue` reported it
        reached                  did it reach the final text at all
        sentences                1-based sentence numbers that use it
        clause                   the longest matched run, verbatim
        match_kind               "verbatim" | "run" | None

    An entry whose value appears whole in a sentence is `verbatim`; one that
    shares a long enough run is `run`; one that shares neither is NOT USED,
    and that verdict is the point of the module.

    An entry whose payload is too short to decide on - fewer than
    `min_ngram` words, or fewer than `min_content` of them carrying meaning -
    is reported `attributable=False` with a `reason`, and is NEITHER reached
    nor not-reached. See the module docstring.
    """
    sentences = split_sentences(text)
    lowered = [s.lower() for s in sentences]
    out = []
    for entry in entries:
        value = entry.get("value") or fact_value(entry.get("text", ""))
        value_words = _words(value)
        if (len(value_words) < min_ngram
                or _content_count(value_words) < min_content):
            out.append({
                "id": entry.get("id"), "key": entry.get("key"),
                "text": entry.get("text", ""), "value": value,
                "attributable": False,
                "reason": "payload %r is %d word(s) with %d content word(s); "
                          "text matching cannot decide it"
                          % (value, len(value_words),
                             _content_count(value_words)),
                "reached": False, "sentences": [], "clause": "",
                "match_kind": None,
            })
            continue
        hits, clause, kind = [], "", None
        needle = " ".join(value_words)
        for n, (raw, low) in enumerate(zip(sentences, lowered), start=1):
            hay = " ".join(_words(raw))
            if needle and needle in hay:
                hits.append(n)
                if len(needle) > len(clause):
                    clause, kind = needle, "verbatim"
                continue
            run, _start = longest_shared_run(value, raw)
            if not run or len(run) < min_ngram:
                continue
            if _content_count(run) < min_content:
                continue
            hits.append(n)
            candidate = " ".join(run)
            if kind != "verbatim" and len(candidate) > len(clause):
                clause, kind = candidate, "run"
        out.append({
            "id": entry.get("id"),
            "key": entry.get("key"),
            "text": entry.get("text", ""),
            "value": value,
            "attributable": True,
            "reason": "",
            "reached": bool(hits),
            "sentences": hits,
            "clause": clause,
            "match_kind": kind,
        })
    return out


def reached(records):
    return [r["id"] for r in records if r["reached"]]


def not_reached(records):
    return [r["id"] for r in records
            if r.get("attributable", True) and not r["reached"]]


def unattributable(records):
    return [r["id"] for r in records if not r.get("attributable", True)]


def brain_caused(entries, text_with, text_without, **kwargs):
    """THE AUTHORITATIVE MEASURE: reached WITH the brain, not reached WITHOUT.

    Text overlap on its own is not causation - `copystages.WRITER_SYSTEM`
    and `product.capabilities` put the same words in front of the writer by
    another route. An entry is credited here only when ABLATING the brain
    takes its clause out of the text.

    Works on the short payloads the three-bucket rule cannot decide too,
    because the comparison is between two texts rather than between a
    payload and a sentence: a digit that appears in both is credited to
    neither.
    """
    with_recs = {r["id"]: r for r in attribute(entries, text_with, **kwargs)}
    without = {r["id"]: r for r in attribute(entries, text_without, **kwargs)}
    out = []
    for key, rec in with_recs.items():
        other = without.get(key) or {}
        if rec["reached"] and not other.get("reached"):
            out.append(rec)
    return out


def format_log(records, *, label="", sentences=()):
    """The per-sentence retrieval log, as text a human reads.

    Entries that reached the text come first with their sentence numbers and
    the clause; the ones that did not are listed by id and key, because
    "these 46 were retrieved and reached nothing" is the finding.
    """
    lines = []
    if label:
        lines.append(label)
    for n, sentence in enumerate(sentences, start=1):
        lines.append("  S%d: %s" % (n, sentence))
    used = [r for r in records if r["reached"]]
    unused = [r for r in records
              if r.get("attributable", True) and not r["reached"]]
    undecidable = [r for r in records if not r.get("attributable", True)]
    lines.append("  RETRIEVED %d | REACHED %d | NOT USED %d | "
                 "UNATTRIBUTABLE %d"
                 % (len(records), len(used), len(unused), len(undecidable)))
    for rec in used:
        lines.append("  %s %-44s -> sentence(s) %s  [%s] %r"
                     % (rec["id"], rec["key"],
                        ",".join(str(s) for s in rec["sentences"]),
                        rec["match_kind"], rec["clause"]))
    for rec in unused:
        lines.append("  %s %-44s -> NOT USED" % (rec["id"], rec["key"]))
    for rec in undecidable:
        lines.append("  %s %-44s -> UNATTRIBUTABLE (%s)"
                     % (rec["id"], rec["key"], rec["reason"]))
    return "\n".join(lines)


# --------------------------------------------------------------- the seams

@contextlib.contextmanager
def observe():
    """Record every `secondbrain.for_task` call made inside the block.

    Yields a list of `{"task", "client", "entries"}`. The real function still
    runs and its real answer is still returned - this watches, it does not
    substitute. Restores the original attribute on the way out, including on
    an exception.
    """
    from . import secondbrain

    log = []
    original = secondbrain.for_task

    def watched(task, client):
        result = original(task, client)
        log.append({"task": task, "client": client,
                    "entries": catalogue(result)})
        return result

    secondbrain.for_task = watched
    try:
        yield log
    finally:
        secondbrain.for_task = original


@contextlib.contextmanager
def ablated():
    """THE ABLATION. Inside the block the Second Brain retrieves nothing.

    `for_task` keeps its contract - it still raises `ValueError` for an
    unknown task and still returns a dict keyed by exactly the sections that
    task asks for - and every section is EMPTY. That is what "switched off"
    has to mean here: not a different shape the callers would crash on, and
    not `None`, but a brain that answers truthfully that it holds nothing.

    Yields a list of the calls it emptied, so a test can prove the ablation
    was actually exercised rather than silently bypassed by a caller that
    never asked.
    """
    from . import secondbrain

    log = []
    original = secondbrain.for_task

    def empty(task, client):
        needed = secondbrain.TASK_SECTIONS.get(task)
        if needed is None:
            raise ValueError(
                "unknown task %r; known tasks: %s"
                % (task, sorted(secondbrain.TASK_SECTIONS)))
        log.append({"task": task, "client": client})
        return {section: [] for section in needed}

    secondbrain.for_task = empty
    try:
        yield log
    finally:
        secondbrain.for_task = original
