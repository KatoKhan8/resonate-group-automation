# Lane M: three email cohorts, ready for the foreground to push

2026-09-25. Lane M built these; **Lane M made no provider write.** Every
number below is derived from files named here, and every denominator is
named with it.

## THE ONE THING TO DECIDE BEFORE PUSHING

**The cohort shape asks for five tags. Only four of them have data.**

`headcount band` has no source for this population. The brief said Lane J's
rows carry `_slice` like `Software Development|51_200|United States`. They do
not: **zero of the 12,407 rows carry `_slice` or `slice`**, and no row carries
an employee count. The `_slice` values live in a different file covering a
different population (`work/researchpack-us-cold-2026-09-25.jsonl`, Software
Development), which overlaps Lane J's domains by **4 domains**.

The only headcount source that touches this supply is
`US-COLD-SUPPLY-DOMAINS-2026-09-25.jsonl`, and it reaches **616 of the 10,418
Lane J domains (5.9%)**, carrying **850 of the 12,407 contacts (6.9%)**.
Cutting those 850 by geo, band and persona leaves a largest cell of **219**,
and that cell's geo is the `US-other` leftover bucket, which spans four
timezones and so has no recipient-local window. **Requiring a headcount band
yields zero valid cohorts.**

So these three cohorts are homogeneous on **geo, industry, signal state and
persona**, and are explicitly **unsegmented on headcount**. The campaign name
says `HCunknown` rather than omitting the tag, because a reader must not
mistake this for a band that was chosen. **Learning is confounded on the
headcount axis only.** Operator's call: push as-is, or delay for enrichment.

## THE THREE COHORTS

Geo is defined **by timezone**, which is what makes "recipient-local" well
defined. A location that matched two timezone groups, or none, was **dropped,
never guessed** (CLAUDE.md: a guessed timezone is worse than a missing one).

| # | Campaign name | Leads | Timezone |
|---|---|---|---|
| 1 | `PRODUCTIVE-USEast-MktgAdv-HCunknown-PackFact-FounderCEO-20260925` | 250 | America/New_York |
| 2 | `PRODUCTIVE-USPacific-MktgAdv-HCunknown-PackFact-FounderCEO-20260925` | 223 | America/Los_Angeles |
| 3 | `PRODUCTIVE-USCentral-MktgAdv-HCunknown-PackFact-FounderCEO-20260925` | 217 | America/Chicago |

Five tags in every name: geo, industry, headcount state, signal state, persona.

- **industry** = `Marketing & Advertising`, the label on Lane J's row.
- **signal state** = `PackFact`: the domain has at least one research-pack fact
  with a non-empty snippet. **All 690 leads are packed; none is generic.**
- **persona** = `FounderCEO`: title matches CEO / chief executive / founder /
  co-founder / owner / president.

**Lead ids are in `work/`, not here.** `work/copy-US-East.jsonl`,
`work/copy-US-Pacific.jsonl`, `work/copy-US-Central.jsonl`. One JSON object
per lead: `id` (domain), `email`, `first_name`, `company`, `subject_1`,
`steps` (five), `pack`. `work/` is gitignored; this file is tracked, so it
carries no address, company, domain or slug.

## HOW 12,407 BECAME 690

Denominators, each named:

| Stage | Count | Unit |
|---|---|---|
| Lane J cohort | 12,407 | contacts |
| on distinct domains | 10,418 | domains |
| domains with a packed fact | 6,057 | domains |
| contacts whose domain is packed | 7,416 | contacts |
| after geo/industry/persona/pack/safety gates | 3,148 | contacts |
| one contact per domain | 3,057 | domains |
| rendered, lint-clean, capped at 250/cohort | **690** | leads |

Gate log, against the 12,407:

| Dropped | Why |
|---|---|
| 2,820 | persona not FounderCEO |
| 2,447 | no research-pack fact on the domain |
| 1,942 | geo ambiguous or unknown, never guessed |
| 1,579 | industry not Marketing & Advertising |
| 471 | domain holds a person already excluded (replied/bounced) |

The 6,057 figure in the brief is correct but was attributed to the wrong file.
It is `work/researchpack-us-cohortJ-2026-09-25.jsonl`, whose 10,418 domains are
exactly Lane J's. The path the brief gave does not exist; Lane K's worktree
`work/` holds one unrelated script.

## COPY

**Pack coverage: 690 of 690 leads (100%) carry a pack fact.** No lead ships
generic. That is a consequence of making `PackFact` a cohort tag, not luck.

**Copylint rule 1 warnings: zero**, because every opener is grounded in its own
lead's pack. Re-verified after rebasing onto master `ed7bb96d`, which makes
rule 1 warning-only: all three batches report **`PASSED: N of N leads clean,
0 warned`**, zero offenders on all six rules. The warning-only change is
therefore not load-bearing for these batches — they passed under the strict
rule too.

Because every cohort lead is packed, the per-lead gate in `work/gencopy.py`
**still drops a draft that only warns**. An ungrounded opener here is a
generator failure, not an acceptable warning, and the next candidate is taken
instead.

Each lead carries **one subject and five bodies**. That mapping was derived by
**running** `bisonfactory._sequence_steps` and `_variables_for`, not read off a
document:

- All five provider steps carry `email_subject = {SUBJECT_1}`; bodies are
  `{BODY_1}`..`{BODY_5}`.
- `_variables_for` writes `subject_1` and `body_1..body_5` only.
  **`subject_2..subject_5` are never written**; `_stale_clearances` sets them,
  plus `subject_6`/`body_6`, to `""` (`MAX_SEQUENCE_STEPS` is 6).
- So **follow-up subjects are discarded by the provider path.** Generating five
  subjects per lead would be wasted work and would mislead a readback reader.

Waits `3/4/4/9/1` reproduce cadence days `1/4/8/12/21`; `_sequence_steps`
verifies the first four against the cadence and carries the fifth unchecked.
`thread_reply` is `[false, true, true, true, true]`.

### What the opener may assert

The opener quotes a phrase **taken verbatim from that lead's own crawled
page** and asserts nothing else about the company. Follow-ups carry no company
specific at all, which is what holds `untraceable_company_claim` at zero by
construction rather than by hoping a generator behaved.

**The rule-1 warning is not permission to invent, and nothing here invents.**

Five classes of defect were found by reading rendered samples, not by the
lint, and each is now filtered — the lint's own docstring says it cannot catch
a wrong sentence that carries no specific:

1. **Truncated snippet tails.** Every crawled snippet is cut at a fixed length,
   so its last fragment ends mid-word. One sample read `...food and beverage
   market, gett`. The final fragment is now discarded unless the snippet ends
   on punctuation.
2. **Navigation and carousel chrome** quoted as if it were copy
   (`...more use tab to navigate through the`).
3. **Lorem ipsum.** One sampled site ships Latin filler; quoting it back
   announces that nobody looked.
4. **Parked-domain hosting notices** (`this domain has been configured for use
   by ...`) quoted as company positioning.
5. **A real person's name and contact details.** Snippets contain live
   addresses and phone numbers in plain text. Any candidate
   phrase containing `@`, a digit, a URL or parentheses is rejected.

Two leads were **dropped rather than repaired** when the per-lead lint fired
(one non-Latin-script site whose tokens cannot ground an English opener, one
untraceable claim). CLAUDE.md: never widen a rule to make a draft pass.

## SCHEDULE

**Seven days a week, 06:00-22:00 recipient-local**, one timezone per campaign
as tabled above. This is a change from the estate's existing campaigns, which
are Mon-Fri (487 is 07:00-15:00Z, 489 is 13:00-21:00Z).

## SENDERS — SIZE AGAINST THE FORWARD BOOK, NOT THE MAILBOX COUNT

Do not take a number from this section on trust. From
`work/forward-book-census.json` (file mtime 2026-09-24 21:43, so **already a
day stale**):

| Date | Booked sends | Senders used |
|---|---|---|
| 2026-09-25 | 1,356 | 154 |
| 2026-09-26 | 86 | 59 |
| 2026-09-27 | 80 | 40 |
| 2026-09-28 | 1,008 | 169 |

Nominal cap is 2,310 (154 attested mailboxes x 15). Day-1 demand for all three
cohorts is **690 openers**. That is inside today's nominal residue of ~954, but
**nominal residue is not headroom**: run `src/senderheadroom.py` before
committing a send date, and remember its contract — a walk can only undercount,
so **REFUSED IS NOT ROOM**. The 26th and 27th are nearly empty and are the
cheaper landing days.

The send date is a property of the mailbox, not the campaign
(`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`). Activating today does not
mean sending today.

## EXPECTED READBACK

After the three creates, per campaign:

- Campaign exists with the tabled name, status ACTIVE, schedule seven-day
  06:00-22:00 in the tabled timezone.
- Sequence has **five steps**, waits `3/4/4/9/1`, `thread_reply`
  `[false,true,true,true,true]`, and **every step's `email_subject` is the
  literal `{SUBJECT_1}`**.
- Lead count **250 / 223 / 217**, total **690**.
- Each lead carries custom variables `record_id`, `contact_key`, `client`,
  `subject_1`, `body_1`..`body_5` — **nine values**.
- **`subject_2`..`subject_6` and `body_6` read back as empty strings.** A
  non-empty `subject_2` means the threaded shape did not take and the readback
  should be treated as a failure, not a cosmetic difference.

A campaign-creation call that returns 200 is not a staged campaign. Only a provider readback
against the real campaign id is evidence (`scripts/provider_truth.py`).

## WHAT WOULD MAKE THIS A FALSE PASS

- Reading the 690 as "leads ready" without the headcount caveat above.
- Reporting 6,057 as contacts. It is **domains**, and it is the denominator
  for the pack join, not for the cohorts.
- Assuming the industry label is verified. It is the supplier's free-text
  label carried through Lane J. At least one sampled domain in the
  Marketing & Advertising set is plainly an industrial sales-representative
  business, not an agency. Nothing here re-derives industry.
- Treating "copylint PASSED" as "the copy is good". It passed six mechanical
  rules. The five defect classes above were found by a person reading samples,
  and there may be more in the 675 leads nobody read.

## REPRODUCING

From this worktree:

    python work/build_cohorts.py       # gates + pools, writes work/cohort-*.jsonl
    python work/gencopy.py             # renders + per-lead lint, writes work/copy-*.jsonl
    python work/verify_and_sample.py   # independent re-check + work/SAMPLES.txt

`verify_and_sample.py` deliberately does not reuse the generator's filters: it
asserts on the rendered text, so a bug in a filter cannot hide behind itself.
