# The crawler audit: it exists, it works, and the prompt cannot see it

Run as a parallel audit 2026-09-15 while production work continued. Nothing was
changed. Every number read from the live estate or the source.

---

## FOUND

**`src/webfetch.py`** - 428 lines, free, standard library only (`urllib`,
`html.parser`, `urllib.robotparser`). No paid dependency, no browser, no
external package.

Its own docstring states the three refusals that make it an evidence layer
rather than a personalisation toy:

- **It never pretends.** JS-required, 403, timeout and 404 are each classified
  as themselves. `JS_RENDERING_REQUIRED` routes the account onward rather than
  being hidden as a failure.
- **It never wanders.** Own domain only, only pages the site links or a sitemap
  declares, `text/html` only, hard ceilings on pages, bytes, redirects and
  wall-clock.
- **It never guesses a URL into evidence.** An earlier approach handed Apify a
  list of hoped-for paths - `/about`, `/company` - and two of five 404'd on the
  first live run, with the navigation text kept as though the page were real.

It is wired at `research._from_the_site_itself` as the **free leg that runs
before the paid crawl**, and `tests/test_the_free_leg_runs_before_the_paid_one.py`
pins that ordering.

## CURRENT STATUS: USED, AND ITS OUTPUT REACHES THE CLAIMS GATE

Not orphaned, not broken, not disabled. Live estate:

    records carrying research[]        203 of 300
    evidence rows                      695
      provider apify                   625
      provider local_http (webfetch)    70
    every row carries: fact, source_url, source_type, provider, retrieved_at,
                       record_id, evidence_id, published_at, subject,
                       contact_key, confidence, age_days

**That is precisely the evidence-with-provenance architecture the brief asks
for, and it already exists.** Value, source URL, extraction timestamp,
confidence, supporting context - all present, on 203 records.

`src/claims.py:447` reads `rec["research"]` when deciding whether a claim is
supported. So the crawler's output IS consumed by the gate that matters.

## WHY IT ISN'T HELPING: THE PROMPT READS A DIFFERENT KEY

This is the finding, and it is not the one the brief anticipated.

    src/claims.py:447     reads rec["research"]    <- 695 provenanced rows
    src/generate.py:575   reads rec["evidence"]    <- something else entirely

`rec["evidence"]` is **not** the crawler's output. `claims.py:449` says so in
as many words:

> AND NOT `rec["evidence"]`. That is `generate.persona_angle`'s output - the
> model's own sentences ... Reading them back as support closed the loop a
> third time: the model wrote the line, `check_evidence` certified it, the
> prospect read it, and this function then treated it as the reason it was
> allowed to be said.

So the separation is **deliberate and correct** - the claims gate must not
accept the model's own sentences as support for the model's own claims.

**But the generation prompt reads that same model-authored key**, and it is
almost empty:

    records with an evidence dict          4 of 300
    CONTACTS whose key carries evidence    2 of 92

**Ninety of ninety-two contacts are handed an EMPTY evidence list when their
copy is written**, while 695 rows of real, source-backed, timestamped web
evidence sit in `rec["research"]` that the prompt never reads.

## HOW THIS CAUSES THE UNSUPPORTED-CLAIMS PROBLEM

The operator asked whether crawler absence contributes to the claims failures.
It does, and the mechanism is exact:

    the model is asked to personalise
      -> it is given no facts
      -> it writes something plausible: "i admire how [company]..."
      -> the claims gate checks it against rec["research"]
      -> no support -> REJECTED

TASK-130 found that phrase in **11 of 69** sequences. The four blocked
`em_dash` records show **43 unsupported-claim rejections** in their logs.

The loop is not "guess, then send". The gate holds. The loop is **"guess, then
get rejected, then guess again"** - three attempts per step, all refused, and
the old copy left in place. That is the system being safe and unproductive at
the same time.

**And the evidence to do it properly is already on disk.** Of the 51-contact
cohort, **43 sit on records that carry `research[]` rows.** The facts exist;
the prompt is simply not shown them.

## CURRENT DATA PATH INSTEAD

Where the current "truth" about a company comes from, end to end:

    company_facts    industry, employees, employee_range, revenue, offices,
                     linkedin, icp_flags, research_outcome
                     -> NO source_url, NO provider, NO timestamp on ANY field.
                        Provenance-free. 7 conflicts and 64 range/value
                        disagreements across 300 records were measured earlier,
                        and this is why they cannot be adjudicated.

    research[]       the real evidence layer. 203 records, 695 rows, full
                     provenance. Read by claims.py. NOT read by the prompt.

    evidence{}       the model's own cited sentences, per contact. 4 records,
                     2 contacts. READ BY THE PROMPT.

So campaign generation is currently working from `company_facts` (no
provenance) plus a near-empty `evidence{}` - and not from the 695 crawled facts.

## WHAT WE ARE MISSING

Nothing that needs a new crawler. What is missing is the wiring from
`research[]` into the generation prompt, and the provenance fields on
`company_facts`.

## RECOMMENDED INTEGRATION POINT

`src/generate.py:575`, the `block["evidence"]` assignment. The prompt block
should carry the record's `research[]` rows - filtered to this contact where
`contact_key` is set, falling back to company-level rows - alongside, and
clearly distinguished from, the model's own prior sentences.

**The distinction must survive.** `claims.py` is right that model-authored
lines may never license a claim. Adding research rows to the PROMPT is a
different act from accepting them as SUPPORT, and the two keys must not be
merged.

## RISK

- **Merging the two keys would be the serious mistake.** If research rows and
  model sentences become indistinguishable, `claims.py:447` starts certifying
  the model's own output and the loop closes for a fourth time.
- More prompt context costs tokens on every generation.
- A stale fact presented as current is worse than no fact. `retrieved_at` and
  `age_days` are already on every row and must be shown to the model, not just
  stored.

## EFFICIENCY - ALREADY SOLVED

The brief warns against crawling one company twenty times for twenty
prospects. `research[]` is stored **per record**, which is per company, and
rows carry an optional `contact_key` for the contact-specific ones. Company
evidence is already gathered once and reusable across contacts.

**CORRECTED BY PART 2:** this section originally said `retrieved_at` and
`age_days` "already support a staleness policy". `age_days` is NULL on all
695 rows and nothing reads `retrieved_at` back. The fields exist; the policy
does not.

## NEXT SAFE ACTION

The smallest proven step: show the prompt what already exists. Pass
`rec["research"]` rows into the generation block as a clearly separate field
from `rec["evidence"]`, regenerate a SAMPLE, and measure whether the
unsupported-claim rejection rate falls.

No crawl, no new dependency, no new tool, no change to the claims gate. If
rejections fall, the evidence layer was never the problem - only its
visibility to the model was.

**Do not enable Apify or add a crawler.** The free leg works, runs first, and
has produced 70 rows; the paid leg produced 625. Neither is the constraint.


---

# PART 2: THE PROVENANCE CHAIN, AND WHY NOTHING REFRESHES

## The chain, traced in code

    rec["research"]
      <- research.py:204   rec.setdefault("research", []).extend(usable)
         <- research._from_the_site_itself(rec, config)
            <- webfetch.research(domain, config)        FREE LEG, stdlib urllib
               <- the company own domain: homepage, then only pages that page
                  links or a sitemap declares
            evidence rows stamped provider="local_http"

    rec["research"]
      <- research.py:410   rec.setdefault("research", []).extend(evidence)
         <- research.run(rec, config, live=...)         PAID LEG, Apify actor
            evidence rows stamped provider="apify"

Both legs pass every row through `evidence.boilerplate()` before
retaining it, and both emit `SCRAPE_COMPLETED` and `EVIDENCE_ADDED` events. The free leg runs
first; the paid one is the fallback.

## What the 695 rows actually are - REAL CRAWLS OF REAL PAGES

    provider        local_http 70, apify 625
    source_url      693 https, 2 http - all real URLs
    pages crawled   /  202,  /about 91,  /about-us 29,  /team 22,
                    /services/ 15,  /company 15,  /about/ 7,  /services 7
    retrieved_at    4 distinct dates, 2026-09-07 .. 2026-09-12

So this is genuine website extraction from the companies own sites, with the
page each fact came from retained. The newest evidence is **3 days old**, the
oldest **8 days**.

## THREE PROVENANCE FIELDS EXIST AND ARE NULL ON ALL 695 ROWS

    age_days      None x 695
    published_at  None x 695
    confidence    None x 695

The schema carries exactly the fields the intended architecture needs for
freshness and evidence quality, and not one of them has a value. Staleness can
currently only be derived from , which IS populated.

## THE ROOT CAUSE: THERE IS NO REFRESH, BY CONSTRUCTION

 decides whether to crawl, and it opens:

    if existing_evidence(rec):
        return None                               # already have it

**Once a record has any evidence, research never runs on it again.** There is
no TTL, no staleness comparison, no age threshold - grepping  for
stale/refresh returns only the lines that WRITE , never one that
reads it back to decide anything.

So the intended architecture

    cached research if fresh -> crawler if missing OR STALE

has no  branch. It is

    cached research if PRESENT -> crawler only if ABSENT

 exists to answer the staleness question and is null everywhere,
which is consistent: nothing computes it because nothing asks.

## WHAT TRIGGERS A CRAWL TODAY, AND IS IT REACHABLE

Reachable, and deliberately narrow.  returns a reason only when
structured data has already failed a downstream step:

    NEED_HOOK_EVIDENCE    lane=cold, no hook, and no notable/specialties
    NEED_ANGLE_EVIDENCE   lane=domains, a contact has no angle, and neither
                          specialties nor industry is known

Its own docstring: *"Structured data wins. This only fires when a step
downstream has nothing to work with, which is the only honest reason to go and
read someone website."* That is a good rule and it is why the crawl is cheap.

**It also explains the 8 of 51 cohort records with no research[]**: all eight
report , meaning research never ran - they had enough
structured data that no evidence was ever *needed*. Nothing failed. The crawler
was simply never asked.

## WHAT THIS CHANGES ABOUT THE RECOMMENDATION

Nothing about the next safe action, which stands: show the prompt the 695 rows
it already cannot see.

But it adds a second, separable defect. Even after the prompt can read
, the facts it reads will be 3-8 days old with no mechanism to
notice when they age, because  is null and nothing consults
. For company positioning and services that is tolerable for
now. For hiring signals and recent announcements - which the brief names - it
is not, and a TTL would be needed before those are trusted.

**Still no new tool. The free leg works; what is missing is a refresh policy
and prompt visibility, neither of which needs a crawler.**

---

# PART 3: A CORRECTION. THE MODEL WAS NEVER BLIND.

**Part 1 of this document is wrong on its central claim, and TASK-135 found
it.** Recording it here rather than editing it away, because the operator acted
on the wrong version.

## What Part 1 said

> the generation prompt reads that same model-authored key ... Ninety of
> ninety-two contacts are handed an EMPTY evidence list when their copy is
> written, while 695 rows of real, source-backed, timestamped web evidence sit
> in `rec["research"]` that the prompt never reads.

## What is actually true

`src/generate.py:490` - **five lines above the `block["evidence"]` line I did
read** - has always done this:

    public = research.for_prompt(rec)
    if public:
        block["public_evidence"] = public

And `research.for_prompt` reads `existing_evidence(rec)`, which is
`rec["research"]`, returning `field`, `source_url`, `retrieved_at` and `fact`
per row. Its docstring: *"A model is given a fact and where it came from, never
a page."*

**The prompt has been receiving attributed, sourced, timestamped facts all
along.** `block["evidence"]` is a second, additional channel; its emptiness
meant much less than I claimed.

### How I got it wrong

`block["public_evidence"] = public` appeared in my own grep output at line 493.
I read `block["evidence"]` at 575, recognised the model-authored key from
`claims.py`'s comment, and stopped - I had a complete-sounding story and did
not follow the line above it. **A confident narrative is the most effective way
to stop looking**, and this one survived a full write-up because every other
fact in it was true.

## What TASK-135 measured

26 drafts across 13 records, generated with and without a new quality-filtered
`research` field: **zero unsupported-claim rejections in either variant.** The
model extracted the same company facts from `public_evidence` as from the new
field, producing functionally identical sentences.

The 43 rejections Part 1 cited came from log entries on the four blocked
records, from an earlier generation pass. They were real when written and are
not reproduced now.

## THE REAL CONSTRAINT, which this does expose

Verified independently by Claude:

    research rows that are navigation text, not prose   237 of 695  (34%)
    records whose FIRST THREE rows are all junk          47 of 203

`for_prompt` takes `existing_evidence(rec)[:3]` - **the first three, in stored
order, with no quality ordering at all.** So for 47 records the model is shown
three fragments of menu text and nothing else. Not blind, but shown the wrong
three things.

That is what the TASK-135 change fixes: quality-filtering to medium+strong,
contact-awareness, and five entries instead of three. It changed no
claims-gate outcome in the sample and it still makes 47 records show facts
instead of navigation.

**And it reframes the crawler work.** The constraint was never that evidence
does not reach the model. It is that a third of what was extracted is not
evidence - it is page furniture. Improving extraction beats adding prompt
fields, which is exactly what TASK-135 concluded.
