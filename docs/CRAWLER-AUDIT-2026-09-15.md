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
evidence is already gathered once and reusable across contacts, and
`retrieved_at` / `age_days` already support a staleness policy.

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
