#!/usr/bin/env python3
"""One batch of ~1,000 accounts, end to end, and the manifest that proves it.

OPERATOR DECISION, 2026-09-25: the supply chain stops being a set of stages
that each sweep the whole file and becomes a PIPELINE. A batch of ~1,000
contacts runs

    qualification -> MX -> contact discovery -> verification -> packs ->
    render -> lint -> cohort -> push

all the way through before the file's next batch needs the same stage, so
batches overlap and no stage idles.

## WHY A MODULE AND NOT A SCRIPT

Three things have to be true at once and only one of them is "run the stages".

**The manifest is the record, not the log.** Every per-stage count in the
two-hourly progress block is read back out of `work/batches/<file>/<n>.json`.
Nothing recomputes a count for a report, so the report cannot disagree with
what happened. `progress()` is a function precisely so the foreground session
can call it rather than re-deriving numbers by hand.

**A stage that returned nothing is not a stage that is through.** This
estate's signature failure, three times this week: a sweep reads an empty or
mis-keyed input, produces zero rows, exits zero, and is counted as complete.
`record_stage` REFUSES to write `done` when `produced` is zero and `attempted`
is not - the status is `empty`, it is red in the progress block, and
`percent_through` never counts it. See `StageEmpty`.

**Every percentage names its denominator.** 12,407 is CONTACTS. 10,418 is
COMPANY DOMAINS. 6,186 is domains in this file with a cached pack. 2,774 was
SENDABLE ADDRESSES out of a different population entirely. A stage declares
which one it is measured against, the manifest stores the name AND the value,
and there is no code path that prints a percentage without both.

## WHAT THIS DOES NOT DO

**It does not write to a provider.** Not one call here mutates anything at
EmailBison, HeyReach or Apify. `push` is declared as a stage so the pipeline
can hold a batch AT it and report the batch as waiting; performing it belongs
to the foreground session, which owns every provider write.

**It does not choose a budget and it never raises one.** `headroom` reads the
client's declared ceilings through `spendledger.caps` and the committed spend
through `spendledger.spent`. `size_against_ledger` shrinks a batch to fit and
returns zero rather than proposing a ceiling change.

**It does not verify.** The verification stage is a seam. Operator decision
2026-09-25 puts CheapVerifier second in the order, ahead of Deliverable, and
says explicitly not to spend the raised ceiling on the old order. Lane Q is
building `src/providers/cheapverifier.py`. Until that module imports and
answers `check()`, `verification_seam()` reports NOT LIVE and the stage is
`blocked`, not skipped and not fallen back. A blocked stage is visible in the
progress block; a silent fallback would spend real credits on the order the
operator declined.
"""
import datetime
import json
import os
import re
import unicodedata

from . import clients, geo, mx, personas, spendledger, store

MANIFEST_VERSION = 1

# --------------------------------------------------------------- stages

# The pipeline, in order. Each stage names the denominator it is measured
# against; `DENOMINATORS` below says what each name counts. A stage that
# wanted a denominator not in that table cannot be recorded at all.
QUALIFY = "qualification"
MX = "mx"
DISCOVERY = "discovery"
VERIFY = "verification"
PACKS = "packs"
LINKEDIN = "linkedin"
RENDER = "render"
LINT = "lint"
COHORT = "cohort"
PUSH = "push"

STAGES = (QUALIFY, MX, DISCOVERY, VERIFY, PACKS, LINKEDIN, RENDER, LINT,
          COHORT, PUSH)

# ---------------------------------------------------------- LinkedIn

# OPERATOR DECISION, 2026-09-25: LinkedIn is COLD LEADS ONLY.
#
# The 491-498 cohort is PERMANENTLY excluded, because the client already runs
# those people - the provider says 98% of them are already in a client
# LinkedIn campaign, median eleven each. Measured against this file: 126 of
# the 12,407 rows carry a membership in that range and are excluded by it.
#
# A range rather than a list, because that is how the operator named it, and
# `linkedin_excluded` reads the membership off the row rather than guessing
# from a cohort name.
LINKEDIN_EXCLUDED_CAMPAIGNS = range(491, 499)

# WHERE A LINKEDIN URL MAY COME FROM, AND THIS IS THE WHOLE POINT.
#
# Every one of the 12,407 rows in this file ALREADY carries a
# www.linkedin.com URL. It came with the 09-07 supplier list: the row's
# `provenance` block names `source_list`, `source_dated`,
# `approval_snapshot`, `supplier_email_status` and `us_classified_from`, and
# mentions neither ContactOut nor LinkedIn anywhere.
#
# So a gate that asked "does this row have a LinkedIn URL" would pass
# 12,407 of 12,407 TODAY, before a single ContactOut discovery call has been
# made, and would report a stage complete that has not started. That is the
# estate's signature failure wearing a new hat, and it is why this constant
# exists: the gate asks where the URL CAME FROM, not whether there is one.
LINKEDIN_FROM_DISCOVERY = "contactout_discovery"
LINKEDIN_FROM_SUPPLIER = "supplier_list"

# WHICH DENOMINATOR EACH STAGE IS MEASURED AGAINST, DECIDED ONCE.
#
# This table is the whole defence against the estate's second-commonest false
# pass: a percentage that silently changes what it is a percentage OF between
# one line of a report and the next. MX is a question about EMAIL DOMAINS, not
# contacts - one gateway decision covers every address at that domain, and
# reporting "1,634 of 12,407 MX-decided" understates a stage that is in fact
# further along than that. Packs are a question about COMPANY DOMAINS.
# Verification, render, lint and push are questions about CONTACTS.
STAGE_DENOMINATOR = {
    QUALIFY: "contacts_in_batch",
    MX: "email_domains_in_batch",
    DISCOVERY: "contacts_missing_address",
    VERIFY: "addresses_in_batch",
    PACKS: "company_domains_in_batch",
    LINKEDIN: "contacts_linkedin_eligible",
    RENDER: "contacts_verified",
    LINT: "contacts_rendered",
    COHORT: "contacts_linted",
    PUSH: "contacts_cohorted",
}

# What each denominator name COUNTS, in words, carried into the manifest so a
# reader never has to come back here to find out.
DENOMINATORS = {
    "contacts_in_batch":
        "rows in this batch; one row is one person at one company",
    "company_domains_in_batch":
        "distinct company domains across this batch's rows",
    "email_domains_in_batch":
        "distinct domains of the ADDRESSES in this batch - mx.email_domain, "
        "not the company domain, because a gateway guards the address's own "
        "domain",
    "addresses_in_batch":
        "distinct email addresses in this batch",
    "contacts_missing_address":
        "rows in this batch carrying no email address at all - the only rows "
        "discovery may be bought for",
    "contacts_linkedin_eligible":
        "rows in this batch NOT permanently excluded from LinkedIn - that is, "
        "carrying no membership of campaigns 491-498, whose people the client "
        "already runs",
    "contacts_verified":
        "rows this batch's verification stage returned a sendable verdict for",
    "contacts_rendered":
        "rows this batch's render stage produced a subject AND a body for",
    "contacts_linted":
        "rows that passed lint, including the full-sweep empty-render gate",
    "contacts_cohorted":
        "rows assigned to this batch's cohort campaign",
}

# Stage outcomes. `done` and `empty` are deliberately different words.
PENDING = "pending"
RUNNING = "running"
DONE = "done"
EMPTY = "empty"        # ran, attempted work, produced nothing. NOT done.
BLOCKED = "blocked"    # cannot start: a dependency is not live
HALTED = "halted"      # stopped at a ceiling, cleanly, part-way
SKIPPED = "skipped"    # deliberately not run, with a reason
FAILED = "failed"

TERMINAL_OK = (DONE, SKIPPED)


class PipelineError(RuntimeError):
    pass


class StageEmpty(PipelineError):
    """A stage attempted work and produced nothing, and was recorded `done`.

    Raised by `record_stage` rather than tolerated. The whole point of the
    manifest is that a zero cannot be dressed as a completion.
    """


class UnknownDenominator(PipelineError):
    """A stage tried to report against a denominator nobody named."""


class MixedBatch(PipelineError):
    """A batch carries more than one (geo, industry group, persona).

    A mixed batch does not map onto a cohort campaign, which is the entire
    reason batches are sliced this way rather than by file order.
    """


class BudgetExhausted(PipelineError):
    """No ceiling has room for the smallest useful unit of work."""


# ------------------------------------------------------- slicing a file

# The three dimensions a batch is keyed on, in the order they are spelled
# into the slice key. They are NOT equally binding - see below.
SLICE_DIMENSIONS = ("geo_zone", "industry_group", "persona")

# OPERATOR DECISION, 2026-09-25, on the 41-batch tail.
#
# GEO AND PERSONA NEVER MERGE. They are the two dimensions a cohort campaign
# is actually built around - the send window comes from the zone and the angle
# comes from the persona - so a batch mixing either does not map onto one
# campaign, whatever its size.
PINNED_DIMENSIONS = ("geo_zone", "persona")

# INDUSTRY MAY MERGE, and only when the slice is small enough that keeping it
# alone would produce a campaign nobody should run. 200 is the operator's
# number, not a tuned one.
MERGE_INDUSTRY_BELOW = 200

# NEVER A CAMPAIGN UNDER 50. Encoded as a REFUSAL rather than a preference:
# `plan_slices` cannot emit a batch below this, and `assert_emittable` raises
# if one is handed to it. PRODUCTION-SCALE-POLICY forbids a campaign per
# person, and the 15 batches of fewer than 5 contacts the first plan produced
# were exactly that in the making.
MIN_COHORT = 50

US_REGIONS = (geo.US_EAST, geo.US_CENTRAL, geo.US_WEST)

# A row the geo resolver cannot place. It gets its own slice and is NEVER
# merged into a placed one: "United States" with no city and no state is a
# real, common answer in this supplier's location free text (585 rows of it),
# and folding those into US East to make the batches tidier would put people
# three time zones away into a cohort whose send window was chosen for them.
UNZONED = "US Unzoned"

# A row this file calls US whose location text resolves to somewhere else.
# Held out rather than guessed at, and reported: either the supplier's US
# classification is wrong on that row or a city name is ambiguous across two
# countries, and both are facts an operator should see rather than a silent
# reassignment.
NON_US = "Non-US suspect"

UNSPECIFIED_INDUSTRY = "UNSPECIFIED"
UNMATCHED_PERSONA = "UNMATCHED"

# The US state names and abbreviations geo.US_STATES already knows, longest
# first so "west virginia" is tried before "virginia".
_STATE_TOKENS = sorted(geo.US_STATES, key=len, reverse=True)


def us_state_in(text):
    """The US state named in free location text, on whole tokens only.

    `geo.resolve` takes a `state` argument and narrows the zone with it, but
    it does not go looking for one inside a free-text `places` string - it
    looks for a CITY. This supplier writes "Austin, Texas, United States" and
    also "Dallas-Fort Worth Metroplex", so the city table carries the first
    and misses the second while the state is sitting in plain sight on 3,000
    of them.

    Whole-token matching, for the same reason `mx._matches` is on label
    boundaries: a substring test makes "ok" match "Brooklyn" and puts a New
    Yorker in the Central zone.
    """
    words = " " + " ".join(_normalise(text).replace(",", " ").split()) + " "
    for token in _STATE_TOKENS:
        if " " + token + " " in words:
            return token
    return None


def _normalise(value):
    return unicodedata.normalize("NFKD", str(value or "")).strip().lower()


def geo_zone(row, config=None):
    """Which US send zone this row belongs in, or why it has none.

    Returns (zone, evidence). `evidence` is the geo resolver's own `why`, kept
    so a slice label can always be traced back to the text it came from.
    """
    text = row.get("location") or ""
    state = us_state_in(text)
    placed = geo.resolve(country="United States", state=state, places=text,
                         config=config)
    region = placed.get("region")
    if region in US_REGIONS and placed.get("timezone"):
        return region, placed.get("why") or ""
    if region and region not in US_REGIONS and region != geo.OTHER:
        # Resolved confidently to somewhere that is not the United States.
        return NON_US, f"resolved to {region}: {placed.get('why') or ''}"
    return UNZONED, placed.get("why") or "no usable location evidence"


def industry_group(row):
    return (row.get("industry") or "").strip() or UNSPECIFIED_INDUSTRY


def persona_of(row, config):
    name, _score = personas.classify({"title": row.get("title")}, config)
    return name or UNMATCHED_PERSONA


def slice_key(row, config=None):
    """The (geo, industry, persona) triple a batch must be homogeneous on."""
    zone, _why = geo_zone(row, config)
    return (zone, industry_group(row), persona_of(row, config))


def slice_label(key):
    return " / ".join(key)


def pair_key(row, config=None):
    """The (geo_zone, persona) pair a batch may never mix."""
    zone, _why = geo_zone(row, config)
    return (zone, persona_of(row, config))


def assert_homogeneous(rows, config=None):
    """Every row shares one geo zone and one persona, or this refuses.

    INDUSTRY IS NO LONGER CHECKED HERE, and that is the operator's decision
    rather than a relaxation for convenience. A batch may now carry several
    industries - but only ones that were individually under
    `MERGE_INDUSTRY_BELOW`, and only with every one of them named in the
    campaign tag, so a reader sees the mix from the campaign name without
    opening anything. `industries_of` and `campaign_tag` are how that is kept
    true; this function guards the two dimensions that never merge.
    """
    pairs = {pair_key(r, config) for r in rows}
    if len(pairs) > 1:
        raise MixedBatch(
            f"{len(rows)} rows carry {len(pairs)} distinct "
            f"(geo_zone, persona) pairs. Geo and persona never merge: the "
            f"send window comes from the zone and the angle from the "
            f"persona, so a batch mixing either does not map onto one "
            f"cohort campaign.")
    return pairs.pop() if pairs else None


def assert_emittable(rows):
    """A batch that would produce a cohort under 50 is not emitted at all.

    A refusal, not a preference. The reservoir exists so this can be a
    refusal: rows that cannot make 50 WAIT rather than becoming a campaign of
    three people.
    """
    if 0 < len(rows) < MIN_COHORT:
        raise TooSmallToEmit(
            f"{len(rows)} contacts is under the {MIN_COHORT} floor. This is "
            f"not a batch to shrink a ceiling for - it belongs in the "
            f"reservoir for its (geo_zone, persona) pair until the next "
            f"batch of that pair can carry it.")
    return True


def industries_of(rows):
    """Every industry present in a batch, ordered by how many rows carry it."""
    counts = {}
    for row in rows:
        name = industry_group(row)
        counts[name] = counts.get(name, 0) + 1
    return [name for name, _n in sorted(counts.items(),
                                        key=lambda kv: (-kv[1], kv[0]))]


def _slug(value):
    text = _normalise(value).replace("&", " and ")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text)).strip("-")


def campaign_tag(zone, persona, industries):
    """The campaign name, and it must SHOW the mix.

    The operator's requirement is that a reader can see from the campaign name
    exactly which industries went into it, without opening anything. So a
    merged batch's tag is not `mixed` or `multi-4` - it is the industries
    themselves, joined, in the order they contribute rows.

    It gets long, and long is the point. A tag that hid the mix behind a
    count would be shorter and would make the merge invisible at exactly the
    moment somebody is deciding whether the campaign is what they think.
    """
    return "__".join([_slug(zone), _slug(persona),
                      "+".join(_slug(i) for i in industries)])


class TooSmallToEmit(PipelineError):
    """A batch under `MIN_COHORT`. It waits in the reservoir instead."""


def plan_slices(rows, config=None, size=1000):
    """Cut a file into batches under the operator's 2026-09-25 rule.

        geo + persona          pinned; never merged
        industry               may merge within a pair when a slice is under
                               MERGE_INDUSTRY_BELOW, named in the tag
        anything under 50      RESERVOIR, merged into the next batch of the
                               same geo + persona; never emitted alone

    Returns (batches, reservoir). The reservoir is returned rather than
    quietly dropped or quietly appended, because rows that no batch can carry
    are a fact an operator has to see - "a reservoir that only ever fills is a
    queue nobody drains".

    Order is deterministic - pairs by size, then label - so a re-plan of the
    same file produces the same batch numbers. A batch number that moves
    between runs makes every manifest ever written ambiguous.
    """
    pairs = {}
    for i, row in enumerate(rows):
        pairs.setdefault(pair_key(row, config), {}).setdefault(
            industry_group(row), []).append(i)

    batches, reservoir = [], []
    ordered_pairs = sorted(pairs.items(),
                           key=lambda kv: (-sum(len(v) for v in kv[1].values()),
                                           kv[0]))
    for pair, by_industry in ordered_pairs:
        emitted, held = _plan_one_pair(pair, by_industry, size)
        batches.extend(emitted)
        reservoir.extend(held)

    for n, batch in enumerate(batches, start=1):
        batch["batch"] = n
    for batch in batches:
        batch["of"] = len(batches)
    return batches, reservoir


def _plan_one_pair(pair, by_industry, size):
    """One (geo, persona) pair's batches, and what it could not place."""
    zone, persona = pair
    big = {i: idx for i, idx in by_industry.items()
           if len(idx) >= MERGE_INDUSTRY_BELOW}
    small = {i: idx for i, idx in by_industry.items()
             if len(idx) < MERGE_INDUSTRY_BELOW}

    emitted = []
    # A big industry keeps its own batches. Its FINAL chunk may come out under
    # the floor - 1,030 rows at size 1,000 leaves 30 - and that tail is now
    # itself a slice under MERGE_INDUSTRY_BELOW, so merging it is licensed by
    # the same rule. It joins the pair's small pool rather than being emitted.
    for industry in sorted(big, key=lambda i: (-len(big[i]), i)):
        indexes = big[industry]
        chunks = [indexes[s:s + size] for s in range(0, len(indexes), size)]
        if len(chunks) > 1 and len(chunks[-1]) < MIN_COHORT:
            small.setdefault(industry, []).extend(chunks.pop())
        for chunk in chunks:
            emitted.append({"pair": pair, "industries": [industry],
                            "indexes": chunk, "merged_industries": False})

    # The pair's small industries merge into one pool, largest first so the
    # tag's leading industry is the one that actually dominates the batch.
    pool, pool_industries = [], []
    for industry in sorted(small, key=lambda i: (-len(small[i]), i)):
        pool.extend(small[industry])
        pool_industries.append(industry)

    held = []
    if pool:
        chunks = [pool[s:s + size] for s in range(0, len(pool), size)]
        # A final chunk under the floor is folded back into the previous one
        # rather than emitted. Over `size` by under 50 is a batch slightly
        # larger than the target; under 50 is a campaign that must not exist.
        if len(chunks) > 1 and len(chunks[-1]) < MIN_COHORT:
            chunks[-2].extend(chunks.pop())
        if len(chunks) == 1 and len(chunks[0]) < MIN_COHORT:
            # Nothing in this pair can carry it. If the pair emitted a batch
            # above, the reservoir drains into it NOW - that is what "merged
            # into the next batch of the same geo + persona" means when the
            # next batch is already in front of us.
            if emitted:
                emitted[-1]["indexes"].extend(chunks[0])
                emitted[-1]["industries"] = sorted(
                    set(emitted[-1]["industries"]) | set(pool_industries))
                emitted[-1]["merged_industries"] = True
                emitted[-1]["drained_reservoir"] = len(chunks[0])
            else:
                held.append({"pair": pair, "industries": pool_industries,
                             "indexes": chunks[0]})
            chunks = []
        for chunk in chunks:
            emitted.append({"pair": pair, "industries": list(pool_industries),
                            "indexes": chunk,
                            "merged_industries": len(pool_industries) > 1})
    return emitted, held


# -------------------------------------------------------- denominators

def linkedin_excluded(row):
    """Is this row permanently excluded from LinkedIn?

    Read off the row's own provider memberships, not inferred from a cohort
    name: the exclusion is about which campaigns this PERSON is already in,
    and a batch label cannot know that.
    """
    memberships = ((row.get("provider_read") or {}).get("memberships") or [])
    for entry in memberships:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("campaign_id")
        if isinstance(cid, int) and cid in LINKEDIN_EXCLUDED_CAMPAIGNS:
            return True
    return False


def linkedin_source(row):
    """Where this row's LinkedIn URL came from, or None if it has none.

    A URL with no recorded discovery is attributed to the supplier list, not
    to discovery, and NOT to "probably fine". The row carries a
    `linkedin_discovery` block only once ContactOut has actually answered for
    it; until then the URL on the row is the 09-07 supplier's.
    """
    if not (row.get("linkedin") or "").strip():
        return None
    found = row.get("linkedin_discovery") or {}
    if found.get("provider") and found.get("url"):
        return LINKEDIN_FROM_DISCOVERY
    return LINKEDIN_FROM_SUPPLIER


def linkedin_ready(row):
    """May this row be pushed, as far as LinkedIn is concerned?

    Two ways to be ready and they are different facts:

      excluded    the client already runs this person on LinkedIn. There is
                  nothing to discover and nothing to wait for.
      discovered  ContactOut answered for this row.

    A supplier-provided URL is NEITHER. It is the 09-07 list's URL and the
    operator's decision is that the LinkedIn dimension comes from discovery.
    """
    if linkedin_excluded(row):
        return True
    return linkedin_source(row) == LINKEDIN_FROM_DISCOVERY


def linkedin_gate(rows):
    """The pre-push gate. Returns a verdict dict; `passed` is the answer.

    EVERY batch must carry a LinkedIn URL from discovery before push. This
    counts the three populations separately, because collapsing them is
    exactly how a supplier URL gets read as a discovered one.
    """
    excluded = [r for r in rows if linkedin_excluded(r)]
    eligible = [r for r in rows if not linkedin_excluded(r)]
    discovered = [r for r in eligible
                  if linkedin_source(r) == LINKEDIN_FROM_DISCOVERY]
    supplier_only = [r for r in eligible
                     if linkedin_source(r) == LINKEDIN_FROM_SUPPLIER]
    missing = [r for r in eligible if linkedin_source(r) is None]
    return {
        "passed": not supplier_only and not missing,
        "rows": len(rows),
        "permanently_excluded_491_498": len(excluded),
        "eligible": len(eligible),
        "discovered_by_contactout": len(discovered),
        "supplier_url_only": len(supplier_only),
        "no_url_at_all": len(missing),
        "why": ("every eligible row carries a discovered URL"
                if not supplier_only and not missing else
                f"{len(supplier_only)} row(s) carry only the 09-07 supplier's "
                f"URL and {len(missing)} carry none. A supplier URL is not a "
                f"discovered one: LinkedIn is cold-leads-only and the "
                f"dimension comes from ContactOut discovery."),
    }


def measure(rows):
    """Every denominator this batch's stages may be measured against.

    Computed once, from the rows themselves, and stored in the manifest. The
    downstream ones - verified, rendered, linted, cohorted - start at zero and
    are filled in by the stage that produces them, because a denominator that
    is itself an outcome cannot be known before the stage runs.
    """
    company = {(_normalise(r.get("domain"))) for r in rows if r.get("domain")}
    addresses = {(_normalise(r.get("email"))) for r in rows if r.get("email")}
    email_domains = set()
    for r in rows:
        d = mx.email_domain(r.get("email") or "")
        if d:
            email_domains.add(_normalise(d))
    return {
        "contacts_in_batch": len(rows),
        "company_domains_in_batch": len(company),
        "email_domains_in_batch": len(email_domains),
        "addresses_in_batch": len(addresses),
        "contacts_missing_address": sum(
            1 for r in rows if not (r.get("email") or "").strip()),
        "contacts_linkedin_eligible": sum(
            1 for r in rows if not linkedin_excluded(r)),
        "contacts_verified": 0,
        "contacts_rendered": 0,
        "contacts_linted": 0,
        "contacts_cohorted": 0,
    }


# -------------------------------------------------------------- budget

def headroom(client, config, rows=None, day=None):
    """How many credits are actually available, and which ceiling binds.

    Three ceilings and they do not agree, so the one that BINDS is named
    rather than left to the caller to work out:

      per_day   enforced by spendledger.check
      total     enforced by spendledger.check, LIFETIME
      per_run   declared by the client and NOT enforced by check(). Documented
                as a leak by lane N. Reported here so a runner can hold itself
                to it, which is the only thing holding it at all.

    Returns credits, never a suggestion to raise anything.
    """
    ledger = spendledger.load() if rows is None else rows
    day = day or spendledger.today()
    caps = spendledger.caps(config)
    spent_today = spendledger.spent(client, day=day, rows=ledger)
    spent_total = spendledger.spent(client, rows=ledger)

    room = {}
    if caps.get("per_day") is not None:
        room["per_day"] = caps["per_day"] - spent_today
    if caps.get("total") is not None:
        room["total"] = caps["total"] - spent_total

    if room:
        binding = min(room, key=lambda k: room[k])
        available = max(0, room[binding])
    else:
        binding, available = None, None            # None means UNLIMITED

    return {
        "client": client,
        "day": day,
        "spent_today": spent_today,
        "spent_total": spent_total,
        "ceilings": caps,
        "remaining": room,
        "binding": binding,
        "available": available,
        "per_run_declared": caps.get("per_run"),
        "per_run_enforced_by_check": False,
        "note": "per_run is declared and NOT enforced by spendledger.check. "
                "A runner must hold itself to it.",
    }


class LedgerNotCredible(PipelineError):
    """The spend ledger this process would enforce against is not the real one.

    THE WORKTREE HAZARD, AND IT IS A SPENDING ONE.

    `spendledger.path()` derives itself from `store.queue_path()`, which
    defaults to `<checkout>/work/queue.jsonl`. `work/` is gitignored, so every
    git worktree carries its OWN empty copy. A paid stage run from a worktree
    therefore reads an EMPTY ledger, computes `spent_today = 0` and
    `spent_total = 0`, and believes the client's full per_day and full
    lifetime total are available - when in fact most of both are already
    committed.

    Measured in this worktree, 2026-09-25: the production ledger carries
    18,809 credits against a lifetime ceiling of 50,000 and 14,365 of them
    were committed TODAY against a per_day of 15,000. The worktree's own
    ledger carries nothing. A runner started here would have believed it had
    15,000 credits of room where 635 remained - and `spendledger.check`, which
    re-reads the ledger before every call and is the only thing enforcing
    per_day across processes, would have agreed with it, because it would have
    been reading the same empty file.

    So an empty ledger is not treated as "nothing has been spent". For a
    client whose config declares a lifetime ceiling, it is treated as "this
    process is not looking at the ledger that ceiling is measured against",
    and paid work is refused until `QUEUE` points at the workspace that holds
    the real one.
    """


def require_credible_ledger(client, config, rows=None):
    """Refuse paid work against a ledger that cannot be the real one.

    Fail-closed and deliberately crude: it does not try to work out WHICH
    workspace is production, because a process that guessed wrong would be
    exactly as dangerous as one that did not check. It asks one question a
    wrong answer to is always unsafe - does this ledger have any history at
    all for a client that declares a lifetime ceiling - and makes the operator
    point `QUEUE` at the right workspace rather than guessing on their behalf.

    Free stages do not call this. Reading a file and resolving DNS spends
    nothing, and blocking them in a worktree would stop the work that can
    safely be done there.
    """
    caps = spendledger.caps(config)
    if caps.get("total") is None and caps.get("per_day") is None:
        return True                      # nothing durable to measure against
    rows = spendledger.load() if rows is None else rows
    committed = sum(1 for r in rows
                    if isinstance(r, dict) and r.get("client") == client)
    if committed:
        return True
    raise LedgerNotCredible(
        f"the spend ledger at {spendledger.path()} carries no rows for "
        f"{client}, whose config declares per_day={caps.get('per_day')} and "
        f"total={caps.get('total')}. An empty ledger here means this process "
        f"is reading a worktree's own copy, not the workspace the ceilings "
        f"are measured against - so every ceiling would read as fully "
        f"available. Point QUEUE at the production workspace before running "
        f"any paid stage.")


def size_against_ledger(wanted, cost_per_unit, client, config, rows=None,
                        day=None):
    """How many units of work this batch may actually buy, right now.

    RESERVE BEFORE ASKING. The known leak is that `check()` re-reads the
    ledger per call and so cannot see the calls a sibling worker is about to
    make; a chunk stopped at 2,044 against a 2,000 ceiling with every test
    green because the tests ran single-worker. So a caller asks this ONCE, up
    front, gets an integer, and never asks for more than that integer no
    matter how many workers it runs.

    Returns (affordable_units, why). `affordable_units` may be 0, and 0 is an
    answer - it is never rounded up to "one more won't hurt".
    """
    if cost_per_unit <= 0:
        raise PipelineError("a unit of paid work costs more than zero credits")
    # BEFORE the arithmetic, not after. Sizing against an empty ledger returns
    # a large, confident, wrong number, and the caller has no way to tell it
    # from a real one.
    require_credible_ledger(client, config, rows=rows)
    room = headroom(client, config, rows=rows, day=day)
    available = room["available"]
    per_run = room["per_run_declared"]

    if available is None:
        limit = per_run if per_run is not None else None
        if limit is None:
            return wanted, "no ceiling is declared; nothing here bounds it"
        affordable = min(wanted, limit // cost_per_unit)
        return affordable, (f"no durable ceiling declared; held to the "
                            f"declared per_run of {per_run}")

    by_ceiling = available // cost_per_unit
    why = (f"{room['binding']} leaves {available} credit(s) at "
           f"{cost_per_unit}/unit")
    if per_run is not None:
        by_run = per_run // cost_per_unit
        if by_run < by_ceiling:
            by_ceiling, why = by_run, (
                f"the declared per_run of {per_run} is the tighter bound "
                f"({available} left under {room['binding']}); check() does "
                f"NOT enforce per_run, this runner does")
    return max(0, min(wanted, by_ceiling)), why


# ------------------------------------------------- the verification seam

CHEAPVERIFIER_MODULE = "src.providers.cheapverifier"


def verification_seam():
    """Is the verifier the operator chose actually live?

    Operator decision, 2026-09-25, verification order:

        1 stored lookup (free)
        2 CheapVerifier
        3 `invalid` is DROPPED, no further spend
        4 Deliverable on valid / catch_all / unknown
        5 Reoon only as a third opinion

    Lane Q owns the adapter. This asks, and answers honestly, and does NOT
    fall back to the old ContactOut-first order: the operator said explicitly
    not to spend the raised ceiling on it, and a fallback that quietly buys
    the declined order is worse than a stage that stops and says why.

    Returns a dict. `live` false is a normal answer, not an error.
    """
    try:
        import importlib
        module = importlib.import_module(CHEAPVERIFIER_MODULE)
    except ImportError as exc:
        return {"live": False, "provider": "cheapverifier",
                "reason": f"{CHEAPVERIFIER_MODULE} does not import yet "
                          f"({exc.__class__.__name__}); lane Q owns it",
                "checked_at": store.now()}
    check = getattr(module, "check", None)
    if not callable(check):
        return {"live": False, "provider": "cheapverifier",
                "reason": f"{CHEAPVERIFIER_MODULE} imports but exposes no "
                          f"check(); it is not finished",
                "checked_at": store.now()}
    try:
        result = check()
    except Exception as exc:                        # an adapter mid-build
        return {"live": False, "provider": "cheapverifier",
                "reason": f"check() raised {exc.__class__.__name__}",
                "checked_at": store.now()}
    ok = bool(result.get("ok")) and not result.get("skipped")
    return {"live": ok, "provider": "cheapverifier",
            "reason": result.get("note") or "",
            "status": result.get("status"),
            "checked_at": store.now()}


# ------------------------------------------------------------ manifests

def batches_root():
    """Beside the queue, because a manifest is client state.

    NOT beside the checkout. `work/` is gitignored, so every git worktree
    carries its own nearly-empty copy, and a run from a worktree that read
    the checkout's stage found nothing and printed a clean zero. `QUEUE` is
    the one override the rest of the system already moves together.
    """
    return os.path.join(os.path.dirname(store.queue_path()), "batches")


def manifest_dir(file_slug):
    return os.path.join(batches_root(), file_slug)


def manifest_path(file_slug, n):
    return os.path.join(manifest_dir(file_slug), f"{int(n)}.json")


def new_manifest(file_slug, batch, of, slice_key_, denominators, client,
                 source, now=None, industries=None, merged=False,
                 drained_reservoir=0):
    """`slice_key_` is the (geo_zone, persona) pair; `industries` is the mix.

    The signature keeps `slice_key_` in third position so every existing
    caller keeps working, but it now carries TWO pinned dimensions rather
    than three. The industries that went in are a separate argument because
    there may be several of them, and because the campaign tag is derived
    from the list and not from any single one.
    """
    at = now or store.now()
    zone, persona = slice_key_[0], slice_key_[-1]
    industries = list(industries or [])
    return {
        "manifest_version": MANIFEST_VERSION,
        "file": file_slug,
        "batch": int(batch),
        "of": int(of),
        "client": client,
        "created_at": at,
        "updated_at": at,
        # REDACTION. This object carries counts, stage names and slice labels
        # and no identifier of any person or company. Membership lives in the
        # sibling members file, which is under work/ and gitignored; the
        # manifest names its path and its digest and not its contents.
        "source": dict(source),
        "slice": {
            "pinned_on": list(PINNED_DIMENSIONS),
            "geo_zone": zone,
            "persona": persona,
            # Every industry in this batch, most rows first. One name means
            # the batch was never merged; several means it was, and each was
            # individually under MERGE_INDUSTRY_BELOW when it was.
            "industries": industries,
            "industry_group": industries[0] if industries else UNSPECIFIED_INDUSTRY,
            "merged_industries": bool(merged),
            "merge_threshold": MERGE_INDUSTRY_BELOW,
            "min_cohort": MIN_COHORT,
            "drained_from_reservoir": int(drained_reservoir),
            # THE CAMPAIGN NAME SHOWS THE MIX. Named here, on the manifest,
            # so the push stage cannot invent a different one.
            "campaign_tag": campaign_tag(zone, persona, industries),
            "label": " / ".join([zone, "+".join(industries), persona]),
            "homogeneous_on_pinned": True,
        },
        "denominators": dict(denominators),
        "denominator_meaning": {k: DENOMINATORS[k] for k in denominators
                                if k in DENOMINATORS},
        "stages": {name: {
            "status": PENDING,
            "denominator": STAGE_DENOMINATOR[name],
            "denominator_value": denominators.get(STAGE_DENOMINATOR[name]),
            "attempted": 0,
            "produced": 0,
            "percent_of_denominator": None,
            "credits": 0,
            "apify_runs": 0,
            "apify_usd": 0.0,
            "started_at": None,
            "ended_at": None,
            "duration_s": None,
            "counted_from": None,
            "blocked_on": None,
            "note": "",
        } for name in STAGES},
        "budget": {
            "credits_this_batch": 0,
            "reserved": 0,
            "headroom_at_plan": None,
            "halted_at_ceiling": None,
        },
        "apify": {"runs_this_batch": 0, "usd_this_batch": 0.0},
        "gates": {name: None for name in GATES},
        # PROVIDER-CONFIRMED ONLY. Our own counters never populate these.
        "provider_confirmed": {
            "pushed": None, "sent": None,
            "read_at": None, "route": None,
            "note": "null means nobody has read it back from the provider. "
                    "It does NOT mean zero, and it is never filled in from "
                    "our own push counter.",
        },
    }


GATES = (
    "empty_render_full_sweep",   # full sweep, never a sample
    "post_attach_readback",
    "bounce_hard_stop",
    "account_rule",
    "provider_confirmed_numbers",
    "five_samples_15min_veto",
    # OPERATOR DECISION, 2026-09-25. Every batch carries a LinkedIn URL FROM
    # DISCOVERY before push - a supplier URL does not satisfy it.
    "linkedin_url_from_discovery",
    # And the one the reservoir rule needs: a cohort under 50 is not pushed,
    # because it should never have been emitted.
    "cohort_at_least_50",
)


def save(manifest):
    manifest["updated_at"] = store.now()
    path = manifest_path(manifest["file"], manifest["batch"])
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def load(file_slug, n):
    with open(manifest_path(file_slug, n), encoding="utf-8") as fh:
        return json.load(fh)


def load_all(file_slug):
    directory = manifest_dir(file_slug)
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory),
                       key=lambda s: int(s.split(".")[0])
                       if s.split(".")[0].isdigit() else 1 << 30):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


# --------------------------------------------------------- stage counts

def record_stage(manifest, stage, status, attempted=0, produced=0,
                 counted_from=None, credits=0, apify_runs=0, apify_usd=0.0,
                 started_at=None, ended_at=None, note="", blocked_on=None,
                 denominator_override=None):
    """Write one stage's outcome, and refuse the shapes that lie.

    THREE REFUSALS, EACH ONE A FAILURE THAT ALREADY HAPPENED HERE.

    1. `done` with `attempted` above zero and `produced` zero. That is the
       empty sweep, and it is recorded `empty`. A caller that passes `done`
       gets `StageEmpty` rather than a tidy manifest.

    2. A denominator nobody named, or a denominator whose VALUE is unknown.
       A percentage whose bottom half is None prints as a number and means
       nothing.

    3. `produced` above the denominator. A stage cannot deliver more rows
       than the batch has; when it appears to, the two numbers are counting
       different things and the report is already wrong.

    `counted_from` is mandatory for any stage that claims to have produced
    something: it is the sentence saying WHAT WAS READ BACK to get the number
    - a file and its line count, a provider route and its response - so a
    count can always be re-checked against its source.
    """
    if stage not in manifest["stages"]:
        raise PipelineError(f"{stage} is not a stage of this pipeline")
    entry = manifest["stages"][stage]

    name = denominator_override or entry["denominator"]
    if name not in DENOMINATORS:
        raise UnknownDenominator(
            f"{stage} reported against {name!r}, which is not a named "
            f"denominator. Named ones: {', '.join(sorted(DENOMINATORS))}")
    value = manifest["denominators"].get(name)
    if value is None:
        raise UnknownDenominator(
            f"{stage} is measured against {name!r} and this batch has no "
            f"value for it. A percentage with an unknown denominator is not "
            f"a measurement.")

    if status == DONE and attempted > 0 and produced == 0:
        raise StageEmpty(
            f"{stage} attempted {attempted} and produced 0, and was recorded "
            f"{DONE!r}. A stage that returned nothing to count is not through "
            f"the stage. Record it {EMPTY!r}, or say why it is {SKIPPED!r}.")

    if produced and produced > value:
        raise PipelineError(
            f"{stage} produced {produced} against a denominator "
            f"({name}) of {value}. Those two numbers are counting different "
            f"things; the percentage would be nonsense.")

    if produced and not counted_from:
        raise PipelineError(
            f"{stage} claims {produced} produced with no `counted_from`. "
            f"Name what was read back to get that number.")

    entry.update({
        "status": status,
        "denominator": name,
        "denominator_value": value,
        "attempted": int(attempted),
        "produced": int(produced),
        "percent_of_denominator": (round(100.0 * produced / value, 1)
                                   if value else None),
        "credits": int(credits),
        "apify_runs": int(apify_runs),
        "apify_usd": round(float(apify_usd), 4),
        "started_at": started_at or entry.get("started_at"),
        "ended_at": ended_at,
        "counted_from": counted_from,
        "blocked_on": blocked_on,
        "note": note,
    })
    if entry["started_at"] and entry["ended_at"]:
        entry["duration_s"] = round(
            _seconds_between(entry["started_at"], entry["ended_at"]), 1)

    manifest["budget"]["credits_this_batch"] = sum(
        int(s.get("credits") or 0) for s in manifest["stages"].values())
    manifest["apify"]["runs_this_batch"] = sum(
        int(s.get("apify_runs") or 0) for s in manifest["stages"].values())
    manifest["apify"]["usd_this_batch"] = round(sum(
        float(s.get("apify_usd") or 0.0)
        for s in manifest["stages"].values()), 4)

    # A stage that produced rows becomes the NEXT stage's denominator. Done
    # here rather than by the caller, so the chain cannot be wired up two
    # different ways in two different runners.
    downstream = {VERIFY: "contacts_verified", RENDER: "contacts_rendered",
                  LINT: "contacts_linted", COHORT: "contacts_cohorted"}
    if stage in downstream and status in TERMINAL_OK:
        manifest["denominators"][downstream[stage]] = int(produced)
        for other, spec in manifest["stages"].items():
            if spec["denominator"] == downstream[stage]:
                spec["denominator_value"] = int(produced)
    return entry


def _seconds_between(a, b):
    return (_parse_time(b) - _parse_time(a)).total_seconds()


def _parse_time(value):
    text = str(value or "").replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(text)


def percent_through(manifest, stage):
    """This batch's percentage through one stage, or None.

    None when the stage has not finished or finished empty. A batch that is
    `empty` at a stage is not 0% through it in the sense a reader would take
    from "0%" - it is a stage that ran and returned nothing, which needs a
    word, not a number.
    """
    entry = manifest["stages"][stage]
    if entry["status"] not in TERMINAL_OK:
        return None
    return entry["percent_of_denominator"]


# -------------------------------------------------- the progress block

def measured_rate(manifests, stage):
    """Rows per hour, measured from stages that actually completed.

    THE ETA RULE. Returns None when nothing has completed, and None is
    reported as "not measurable yet". An ETA from an assumed rate is the
    third false pass named in the brief and it is the easiest one to commit
    by accident, because a plausible number is always available.
    """
    produced = seconds = 0
    for m in manifests:
        entry = m["stages"].get(stage) or {}
        if entry.get("status") not in TERMINAL_OK:
            continue
        if not entry.get("duration_s") or not entry.get("produced"):
            continue
        produced += entry["produced"]
        seconds += entry["duration_s"]
    if not seconds or not produced:
        return None
    return produced / (seconds / 3600.0)


def progress(file_slug, config=None, client="productive", ledger=None):
    """THE TWO-HOURLY PROGRESS BLOCK, read back out of the manifests.

    A function, not a report generator, so the foreground session can call it
    and get the same object this module's own CLI prints. Every number in it
    came out of a manifest that a stage wrote when it finished; nothing here
    recomputes a count, which is what stops the block drifting from what
    happened.
    """
    manifests = load_all(file_slug)
    if not manifests:
        return {"file": file_slug, "batches": 0,
                "note": f"no manifests under {manifest_dir(file_slug)}"}

    of = max(m.get("of") or 0 for m in manifests)
    source_rows = manifests[0]["source"].get("rows_total")
    source_domains = manifests[0]["source"].get("company_domains_total")

    per_stage = {}
    for stage in STAGES:
        attempted = produced = credits = 0
        done = empty = blocked = halted = 0
        denominator_total = 0
        for m in manifests:
            e = m["stages"][stage]
            attempted += int(e.get("attempted") or 0)
            produced += int(e.get("produced") or 0)
            credits += int(e.get("credits") or 0)
            denominator_total += int(e.get("denominator_value") or 0)
            done += e["status"] == DONE
            empty += e["status"] == EMPTY
            blocked += e["status"] == BLOCKED
            halted += e["status"] == HALTED
        per_stage[stage] = {
            "denominator": STAGE_DENOMINATOR[stage],
            "denominator_means": DENOMINATORS[STAGE_DENOMINATOR[stage]],
            # SUMMED OVER BATCHES, WHICH IS NOT THE FILE'S DISTINCT COUNT.
            #
            # A company with one contact in US East and another in US West is
            # in two slices, so its domain is counted in both. Measured on
            # this file: the batch domain counts sum to 11,712 where the file
            # holds 10,418 distinct company domains. Both numbers are right
            # and they answer different questions - "how much work do the
            # batches contain" and "how many companies are there" - so the
            # key says which one this is.
            "denominator_total_across_batches": denominator_total,
            "denominator_total_is": "the sum over batches, not the file's "
                                    "distinct count; a domain in two slices "
                                    "is counted in both",
            "attempted": attempted,
            "produced": produced,
            "percent_of_file": (round(100.0 * produced / source_rows, 1)
                                if source_rows and
                                STAGE_DENOMINATOR[stage] == "contacts_in_batch"
                                else None),
            "percent_of_denominator": (
                round(100.0 * produced / denominator_total, 1)
                if denominator_total else None),
            "batches_done": done, "batches_empty": empty,
            "batches_blocked": blocked, "batches_halted": halted,
            "rows_per_hour_measured": measured_rate(manifests, stage),
        }

    credits_cum = sum(int(m["budget"].get("credits_this_batch") or 0)
                      for m in manifests)
    apify_runs = sum(int(m["apify"].get("runs_this_batch") or 0)
                     for m in manifests)
    apify_usd = round(sum(float(m["apify"].get("usd_this_batch") or 0.0)
                          for m in manifests), 4)

    # THE LATEST BATCH IS THE ONE THAT RAN, NOT THE LAST FILE ON DISK.
    #
    # `manifests[-1]` is batch 41 because `plan` writes every manifest up
    # front. Reporting "batch 41 of 41" after running batch 1 would say the
    # file was finished. A batch counts as started when any stage of it has
    # left `pending`.
    started = [m for m in manifests
               if any(s["status"] != PENDING for s in m["stages"].values())]
    complete = [m for m in manifests
                if all(s["status"] in TERMINAL_OK for s in m["stages"].values())]
    latest = started[-1] if started else manifests[0]
    room = headroom(client, config, rows=ledger) if config is not None else None

    # SENT IS PROVIDER-CONFIRMED OR IT IS NOT REPORTED.
    confirmed_pushed = [m["provider_confirmed"].get("pushed")
                        for m in manifests]
    confirmed_sent = [m["provider_confirmed"].get("sent") for m in manifests]
    pushed = (sum(v for v in confirmed_pushed if v is not None)
              if any(v is not None for v in confirmed_pushed) else None)
    sent = (sum(v for v in confirmed_sent if v is not None)
            if any(v is not None for v in confirmed_sent) else None)

    return {
        "file": file_slug,
        "as_of": store.now(),
        "batch": {"latest_started": latest["batch"], "of": of,
                  "batches_started": len(started),
                  "batches_complete": len(complete),
                  "manifests_written": len(manifests),
                  "note": "every manifest is written by `plan` up front, so "
                          "`manifests_written` is the plan and "
                          "`batches_started` is the work"},
        "source": {"rows_total": source_rows,
                   "rows_are": "contacts; one row is one person at one company",
                   "company_domains_total": source_domains},
        "leads": {
            "verified": per_stage[VERIFY]["produced"],
            "packed_domains": per_stage[PACKS]["produced"],
            "rendered": per_stage[RENDER]["produced"],
            "pushed_provider_confirmed": pushed,
            "sent_provider_confirmed": sent,
            "note": "pushed and sent are null until somebody reads them back "
                    "from the provider. Null is not zero.",
        },
        "stages": per_stage,
        "apify": {"runs_cumulative": apify_runs, "usd_cumulative": apify_usd,
                  "runs_this_batch": latest["apify"]["runs_this_batch"],
                  "usd_this_batch": latest["apify"]["usd_this_batch"]},
        "credits": {"this_batch": latest["budget"]["credits_this_batch"],
                    "cumulative_across_manifests": credits_cum,
                    "headroom": room},
        "eta": eta_for_file(manifests, source_rows),
        "funding_eta": funding_eta(manifests, room),
    }


# The measured cost of asking one address, 2026-09-25: lane N bought 7,182
# addresses for ~14,365 credits. 2.00 per address ASKED. The 5.17 figure in
# circulation is per SENDABLE address - 2,774 of those 7,182 came back
# sendable - and reserving against it would under-reserve by 2.6x, because
# the ledger is charged for every address asked and not only for the ones
# that answer well.
CREDITS_PER_ADDRESS_ASKED = 2


def funding_eta(manifests, room):
    """How many days of budget the file needs, and whether the money exists.

    THIS IS THE ETA THAT IS ACTUALLY MEASURABLE TONIGHT, and it is a
    different question from the throughput one. Throughput asks how fast the
    stages run; this asks how fast the ceilings refill. For this file the
    second is by far the binding constraint: verification alone is ~24,800
    credits against a per_day of 15,000 and a lifetime remainder of 31,191,
    so the file cannot complete in one day no matter how quick the stages
    are, and the lifetime ceiling is what decides whether it completes at all.

    Nothing here proposes raising a ceiling. It reports whether the declared
    ones cover the work, and says plainly when they do not.
    """
    if not room or room.get("available") is None:
        return {"measurable": False,
                "why": "no durable ceiling is declared, so nothing bounds "
                       "the spend and there is no funding schedule"}
    addresses = sum(int(m["denominators"].get("addresses_in_batch") or 0)
                    for m in manifests)
    already = sum(int(m["stages"][VERIFY].get("produced") or 0)
                  for m in manifests)
    outstanding = max(0, addresses - already)
    need = outstanding * CREDITS_PER_ADDRESS_ASKED

    per_day = (room["ceilings"] or {}).get("per_day")
    lifetime_left = (room["remaining"] or {}).get("total")
    today_left = (room["remaining"] or {}).get("per_day")

    days = None
    if per_day:
        # Today contributes only what is left of today, then whole days.
        after_today = max(0, need - max(0, today_left or 0))
        days = (1 if (today_left or 0) > 0 else 0) + -(-after_today // per_day)

    return {
        "measurable": True,
        "addresses_outstanding": outstanding,
        "addresses_are": "distinct addresses summed over the planned batches",
        "credits_per_address_asked": CREDITS_PER_ADDRESS_ASKED,
        "credits_needed": need,
        "credits_left_today": today_left,
        "credits_left_lifetime": lifetime_left,
        "days_of_budget_needed": days,
        "lifetime_ceiling_covers_it": (None if lifetime_left is None
                                       else need <= lifetime_left),
        "lifetime_margin": (None if lifetime_left is None
                            else lifetime_left - need),
        "why": "verification is the only paid stage this file needs; "
               "discovery is not bought because every row already carries an "
               "address, and the packs already cached cost nothing to reuse",
    }


def eta_for_file(manifests, source_rows):
    """When the whole file finishes, at the rate actually measured.

    The binding stage is the SLOWEST measured one, because the pipeline is
    only as quick as the stage every batch must still pass. A stage nothing
    has completed contributes no rate and is reported as unmeasured rather
    than assumed, and if the binding stage is unmeasured then so is the ETA.

    A BLOCKED STAGE MAKES THE ETA UNMEASURABLE, FULL STOP.

    This is not the same as unmeasured. Unmeasured means "we have not timed
    it yet"; blocked means "we know it cannot start, and we know it is on the
    critical path". Timing the two free stages and reporting that the file
    finishes in six minutes - while every paid stage waits on an adapter that
    does not exist - is an ETA from the stages that happen to be quick. It
    would be arithmetically correct and completely false, which is the exact
    shape of failure the brief names third.
    """
    blocked = {}
    for m in manifests:
        for stage, entry in m["stages"].items():
            if entry.get("status") == BLOCKED:
                key = entry.get("blocked_on") or stage
                blocked.setdefault(stage, set()).add(key)
    if blocked:
        return {
            "measurable": False,
            "blocked_stages": {s: sorted(v) for s, v in sorted(blocked.items())},
            "why": "at least one stage is BLOCKED. A blocked stage is known "
                   "to be on the critical path and known not to have started, "
                   "so no rate measured from the stages that DID run says "
                   "anything about when the file finishes. Unblock, measure, "
                   "then ask again.",
        }

    rates, unmeasured = {}, []
    for stage in STAGES:
        rate = measured_rate(manifests, stage)
        if rate is None:
            unmeasured.append(stage)
        else:
            rates[stage] = rate
    if not rates:
        return {"measurable": False, "unmeasured_stages": unmeasured,
                "why": "no stage has completed with a non-zero produced count "
                       "and a duration. Nothing here will invent a rate."}
    slowest = min(rates, key=lambda s: rates[s])
    remaining = (source_rows or 0) - (
        manifests and max((m["stages"][slowest]["produced"] for m in manifests),
                          default=0) or 0)
    done = sum(m["stages"][slowest]["produced"] for m in manifests)
    remaining = max(0, (source_rows or 0) - done)
    hours = remaining / rates[slowest] if rates[slowest] else None
    return {
        "measurable": True,
        "binding_stage": slowest,
        "binding_rate_rows_per_hour": round(rates[slowest], 1),
        "rows_remaining": remaining,
        "hours_remaining": round(hours, 1) if hours is not None else None,
        "finishes_at_utc": (
            (datetime.datetime.now(datetime.timezone.utc)
             + datetime.timedelta(hours=hours)).replace(
                 microsecond=0).isoformat()
            if hours is not None else None),
        "unmeasured_stages": unmeasured,
        "why": "the slowest MEASURED stage bounds the pipeline. Stages listed "
               "as unmeasured have completed nothing and contribute no rate; "
               "if one of them is slower, this ETA is optimistic and will "
               "move when it is first measured.",
        "caveat": ("every stage is measured" if not unmeasured else
                   f"{len(unmeasured)} of {len(STAGES)} stages have never "
                   f"completed, so this is a floor, not a forecast"),
    }


# ---------------------------------------------------------- redaction

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Fields that IDENTIFY. An address, a company domain and a LinkedIn URL are
# long, structured and never ordinary English, so finding one in an artefact
# is a leak and nothing else.
IDENTIFYING = ("email", "domain", "linkedin")

# Fields that NAME. A surname is frequently an ordinary English word, so a
# match is evidence and not proof, and it is reported as REVIEW rather than
# LEAK. Measured against this file's manifest on 2026-09-25: 65 name matches,
# every one of them a word in the manifest's own prose - `group` inside
# `industry_group`, `advertising` inside the slice label, `this`, `cache`,
# `owns`, `rows`. A filter that called those a leak would be ignored within a
# day; a filter that silently dropped them would be the filter that agrees
# with you. Neither. They are counted, separated and shown.
NAMING = ("company", "first_name", "last_name")

LEAK = "LEAK"
REVIEW = "REVIEW"


def _whole_token(needle, haystack):
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])",
                     haystack) is not None


def redaction_selftest(text, rows, extra_values=()):
    """Does `text` leak anything from `rows`? Checked value by value.

    NOT a regex sweep. A regex finds the shapes it was written for and
    silently passes the one it was not - the IPv4 that leaked on 2026-09-25
    went through a filter applied AFTER the value was formatted. This takes
    the ACTUAL VALUES out of the actual source rows and looks for each one.

    TWO VERDICTS, BECAUSE THERE ARE TWO QUESTIONS.

    `LEAK` is an identifier - an address, a domain, a profile URL - present in
    the artefact. There is no innocent reading of that and the caller should
    stop.

    `REVIEW` is a person's or company's NAME matched as a whole token. String
    search genuinely cannot tell a leaked surname from the same letters used
    as an English word, and pretending otherwise in either direction is worse
    than saying so. These are returned with a count so a human decides, and
    `structural_redaction_check` below answers the same question properly.

    Returns a list of findings. No `LEAK` entry means no identifier from
    these rows is present, which is a stronger statement than "no pattern
    matched".
    """
    haystack = text.lower()
    findings = []
    seen = set()
    for row in rows:
        for field in IDENTIFYING + NAMING:
            value = (row.get(field) or "").strip().lower()
            if len(value) < 4 or value in seen:
                continue
            seen.add(value)
            if field in IDENTIFYING:
                # Substring, not whole token: a domain is legitimately a
                # substring of a URL, and that is still the domain.
                if value in haystack:
                    findings.append({"field": field, "verdict": LEAK,
                                     "kind": "identifier from the source",
                                     "length": len(value)})
            elif _whole_token(value, haystack):
                findings.append({"field": field, "verdict": REVIEW,
                                 "kind": "name matched as a whole token; may "
                                         "be an ordinary word in the prose",
                                 "length": len(value)})
    for value in extra_values:
        if value and str(value).lower() in haystack:
            findings.append({"field": "extra", "verdict": LEAK,
                             "kind": "supplied value", "length": len(str(value))})
    for match in _EMAIL.findall(text):
        findings.append({"field": "regex", "verdict": LEAK,
                         "kind": "email-shaped string", "length": len(match)})
    return findings


def leaks(findings):
    return [f for f in findings if f.get("verdict") == LEAK]


# Every string a manifest is allowed to carry comes from one of these. The
# check below walks the object and proves it, which is a structural argument
# and does not depend on any value being an unusual-looking word.
def structural_redaction_check(manifest):
    """Prove a manifest carries no free-form value from the source rows.

    THE STRONGER ARGUMENT, AND THE ONE THAT SHOULD BE TRUSTED.

    Searching an artefact for leaked values can only ever say "none of the
    values I thought to look for are here". This instead walks the manifest
    and checks that every string in it came from a CLOSED VOCABULARY the code
    owns - stage names, statuses, denominator names, the slice's category
    labels, and prose written in this repository - plus a small allowlist of
    fields that are permitted to carry a filename.

    A field the format grows later and nobody adds here fails this check
    rather than passing it, which is the direction that has to be safe.
    """
    allowed_free_text = {
        "note", "why", "counted_from", "reason", "denominator_means",
        "rows_are", "members_are_under", "denominator_total_is",
    }
    # Fields that may carry a filename, never a prospect identifier.
    allowed_filename = {"path_basename", "members_file"}
    vocabulary = (set(STAGES) | set(DENOMINATORS) | set(GATES)
                  | {PENDING, RUNNING, DONE, EMPTY, BLOCKED, HALTED, SKIPPED,
                     FAILED}
                  | set(SLICE_DIMENSIONS) | set(PINNED_DIMENSIONS)
                  | set(US_REGIONS)
                  | {UNZONED, NON_US, UNSPECIFIED_INDUSTRY, UNMATCHED_PERSONA,
                     LINKEDIN_FROM_DISCOVERY, LINKEDIN_FROM_SUPPLIER})

    problems = []

    def walk(node, path, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}", k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]", key)
        elif isinstance(node, str):
            if key in allowed_free_text or key in DENOMINATORS:
                return                      # prose this repository wrote
            if key in allowed_filename:
                return
            if key in ("industry_group", "label", "industries",
                       "campaign_tag"):
                # An industry is a supplier CATEGORY - "Marketing &
                # Advertising" - shared by thousands of rows and identifying
                # none of them. `label` is checked below for being exactly
                # the three slice fields joined, which is a stronger claim
                # than any vocabulary test on its text.
                return
            if node in vocabulary or not node:
                return
            if key in ("created_at", "updated_at", "started_at", "ended_at",
                       "read_at", "checked_at", "at", "as_of", "day",
                       "client", "file", "route", "blocked_on", "binding",
                       "manifest_version", "geo_zone", "persona",
                       "keyed_on", "denominator", "status"):
                return
            problems.append({"path": path, "key": key,
                             "why": "a string outside the closed vocabulary "
                                    "and not an allowed free-text field"})

    walk(manifest, "manifest")

    # The slice label is DERIVED and must be exactly its three fields joined.
    # A label that has drifted from them is a free-text field wearing a
    # derived field's name, which is how a value nobody checked gets in.
    slice_ = manifest.get("slice") or {}
    industries = slice_.get("industries") or []
    expected = " / ".join([str(slice_.get("geo_zone")), "+".join(industries),
                           str(slice_.get("persona"))])
    if slice_.get("label") != expected:
        problems.append({"path": "manifest.slice.label",
                         "why": "the label is not its slice fields joined, "
                                "so it is free text"})

    # THE CAMPAIGN TAG MUST SHOW THE MIX, and must be derived rather than
    # typed. A tag that has drifted from the industries actually in the batch
    # is the exact failure the operator's rule is written to prevent: a reader
    # seeing one industry in the campaign name and getting four.
    expected_tag = campaign_tag(slice_.get("geo_zone"), slice_.get("persona"),
                                industries)
    if slice_.get("campaign_tag") != expected_tag:
        problems.append({"path": "manifest.slice.campaign_tag",
                         "why": "the campaign tag is not derived from the "
                                "batch's actual industries, so the campaign "
                                "name does not show the mix"})
    if slice_.get("merged_industries") != (len(industries) > 1):
        problems.append({"path": "manifest.slice.merged_industries",
                         "why": "the merged flag disagrees with the number "
                                "of industries actually in the batch"})

    # The geo zone and persona ARE closed vocabularies and are checked as such.
    zones = set(US_REGIONS) | {UNZONED, NON_US}
    if slice_.get("geo_zone") not in zones:
        problems.append({"path": "manifest.slice.geo_zone",
                         "why": f"{slice_.get('geo_zone')!r} is not one of "
                                f"{sorted(zones)}"})
    return problems


# ------------------------------------------------------------- reading

def read_source(path, limit=None):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
    return rows


def source_summary(path, rows):
    return {
        "path_basename": os.path.basename(path),
        "rows_total": len(rows),
        "rows_are": "contacts; one row is one person at one company",
        "company_domains_total": len({_normalise(r.get("domain"))
                                      for r in rows if r.get("domain")}),
        "addresses_total": len({_normalise(r.get("email"))
                                for r in rows if r.get("email")}),
        "rows_with_address": sum(1 for r in rows
                                 if (r.get("email") or "").strip()),
    }


def client_config(client="productive"):
    return clients.load(client)
