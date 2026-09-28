# P0-C — the account TASK-425's run D can actually measure

**Branch `task-p0c-causal-fixture`. Base `origin/master` `d0e95d20`.
`sending.live` false, freeze active, provider writes 0.**

Step 1 of the operator's sequencing: **select a real account from the estate's
own source through the normal qualification and eligibility path, gather and
store its public evidence, and prove the chosen fact is admitted, licensed and
that removal test D is constructible.** The A/A2/B/C/D matrix waits for the
P0-B signal and is NOT claimed here.

Every line below carries CLAIM / AUTHORITY / MEASURED AT / STATE. **A test count
is never a PASS**, and none is offered as one.

---

## 0. THE ONE-LINE ANSWER

    account   Brand IQ                     domain   brandiq.com
    record    brandiq-com                  batch    productive-live-pilot-0050.csv
    claim     ISO 9001:2015  (token 9001)  page     https://brandiq.com/about

Evidence present, both claim gates license the claim. Evidence removed, both
refuse it and the pack is not emptied. A negative control is refused with the
full pack present. **Run D is constructible on this account.**

**Operator chose option A, 2026-09-28: Brand IQ proceeds as the P0-C target.**

---

## 0a. READ THIS BEFORE ANYTHING ELSE — THE MILESTONE IS NOT MET AS WORDED

**CLAIM** Brand IQ comes from a **pilot batch of 50 records**, not from the
~30k-domain source file. The milestone as worded — "a real company from the
~30k source file" — is **NOT MET**.
**AUTHORITY** `qualify.state_of` over all 1,582 production records, grouped by
`batch.source`.
**MEASURED AT** 2026-09-28T11:5xZ.
**STATE** NOT MET, and stated here rather than buried.

    24k staging track                554 records     0 qualified
    batch-1 + batch-2 2026-09-21     477 records     0 qualified
    intake 00000-00250               250 records     0 qualified
    the three pilot batches          300 records   113 qualified

**The large sources hold zero qualified records because nothing was ever run
on them — not because they were searched and found wanting.** This document
must not be read as a judgement on the ~30k pool. It was never qualified, never
researched, and therefore never in a position to offer a candidate. The 113
qualified records in the estate come entirely from 300 pilot records.

What this means for the reading of section 2: the selection funnel below is a
funnel over **the qualified 113**, which is a funnel over 300 pilot records. It
is not a search of 30,000 domains and no number in it should be quoted as one.

Supplying that pool — a bounded sample, with a spend cap — is a **separate,
separately owned task** and is deliberately not started here.

---

## 0b. THE CLAIM IS A MECHANISM PROOF, NOT A SELLING ANGLE

**Operator, 2026-09-28, recorded because it governs how this artifact should be
read:**

> *"the ISO 9001 claim proves the licensed-claim mechanism and run D; whether
> it is a good selling angle for Productive is a separate question I will judge
> from the copy."*

So nothing in this document argues that ISO 9001 is a strong angle for
Productive, and no fact was chosen because it would sell better. It was chosen
because it is **admitted, licensed and removable** — the three properties that
make run D a measurement. Whether it is worth saying to a prospect is judged
from the generated copy, by the operator, and is out of scope here.

---

## 1. WHY THE PREVIOUS FIXTURE MADE RUN D UNMEASURABLE

**CLAIM** The old fixture's declared claim under test could not be seen by
either claim gate, so removing its evidence changed nothing observable and
criterion 4's "exact claim licensed" column was empty for all nine messages.
**AUTHORITY** `copylint.specifics_in`, executed.
**MEASURED AT** 2026-09-28, worktree `agent-a1f47252ae28404a3`, master `d0e95d20`.
**STATE** REPRODUCED.

    copylint.specifics_in(
        "You run project delivery on retained monthly engagements.")  ->  []

`retained monthly engagements` carries no digit, no quoted phrase and no
capitalised multi-word name, so it is not a `SPECIFIC_RES` match.
`copylint.untraceable` only examines specifics inside a company-claim sentence,
and `claims.check` only examines figures, months and events. Neither gate ever
looked at it. **Run D read NOT COMPARABLE for a reason that had nothing to do
with the copy engine: there was nothing to remove.**

That property was invisible in the fixture — a long, careful, heavily
documented file whose one load-bearing property was absent. It is now asserted
mechanically in `tests/test_the_claim_under_test_is_load_bearing.py`.

---

## 2. HOW THE ACCOUNT WAS SELECTED — THE GATES CHOSE IT

**CLAIM** Exactly one account in the estate can currently license a
prospect-specific figure that one research row grants and the rest do not.
**AUTHORITY** `qualify.state_of`, `verification.is_sendable`,
`packfacts.pack_for`, `copylint.untraceable` and `claims.check`, executed over
every record in production `work/queue.jsonl` (1,582 rows, read-only).
**MEASURED AT** 2026-09-28T11:5x–12:0xZ.
**STATE** MEASURED.

The filters are SEQUENTIAL, applied in this order, and the numbers below are
what each one removed from what reached it — not five independent counts. They
sum to 113 exactly, which is the check that none of them is double-counting.

    1,582  records in the estate
      113  qualify.state_of == qualified          <- the real gate, first
        7  removed: domain on test_fixture_hygiene.FORBIDDEN_DOMAINS
        4  removed: a FORBIDDEN_NAMES token anywhere in the record
       41  removed: no contact passes verification.is_sendable
       16  removed: fewer than two identity-admitted research rows
       43  removed: no figure that ONE row licenses and the others do not
        2  survive every filter
        1  licenses a figure from a real operational fact rather than from a
           blog index's own post dates

The second survivor, `savagebrands.com`, licenses only `10` and `16` — the day
numbers in "July 10, 2026" and "June 16, 2026" on its blog index. That is a
date on a listing page, not an operational fact about the company, so it is
reported and not used.

**Nothing was relaxed to reach a candidate.** The account arrives through
`qualify.state_of`; its ICP verdict is the stored one; its contact is sendable
by `verification.is_sendable`. The only filters added on top of the real gates
are "can run D actually remove something" and "is it safe to name in git".

### The selected account, through the real gates

    qualify.state_of            qualified
    icp_status / icp_tier       qualified / C        icp_score 42.0
    structural verdict          icp_pass_with_uncertainty,  eligible: True
      geography                 pass
      company_type              pass
      services_business         pass
      employees                 pass
      tracks_time               unknown
    contacts / sendable         1 / 1
    persona of the sendable     economic_buyer
    record state                verified
    batch source                productive-live-pilot-0050.csv

`tracks_time: unknown` is the estate-wide gap the ten-account preparation
already reported. It is **not** relaxed here: it is `unknown`, and per invariant
0 unknown is not a pass. The ICP model's own rule is that unknown leaves a
company eligible-with-uncertainty, which is what the stored verdict says, and
`qualify.state_of` — the canonical authority for "is this prospect qualified" —
answers `qualified`. That is the state, stated as it is.

`persona: economic_buyer` matters beyond bookkeeping: run C's declared
intervention is economic buyer → operations, so the matrix's contact has to
START there. It does.

---

## 3. THE SOURCE-FILE FINDING — AND IT IS THE UNCOMFORTABLE ONE

**CLAIM** No record from the large staging tracks is qualified, and none has an
identity-admitted research pack at all. Every account that can license a claim
today comes from the three small `productive-*pilot*` batches — 300 records in
total.
**AUTHORITY** `qualify.state_of` and `packfacts.pack_for` over
`work/queue.jsonl`, grouped by `batch.source`.
**MEASURED AT** 2026-09-28T11:5xZ.
**STATE** MEASURED. BLOCKS any claim that the milestone was met "on the ~30k
source file".

    batch source                         recs  qualified  admitted-pack  q+research+sendable
    24k staging track                     554          0              0                    0
    batch-1-2026-09-21                    285          0              0                    0
    productive-intake-00000-00250.csv     250          0            187                    0
    productive-live-pilot-0250.csv        200         68            132                   33
    batch-2-2026-09-21                    192          0              0                    0
    productive-pilot-2026-09-07            50         25             44                   21
    productive-live-pilot-0050.csv         50         20             31                   12
    (no batch)                              1          0              0                    0

**This is the honest answer to "select a real company from the ~30k-domain
source file", and the reason matters more than the number.** The 24k staging
track and the two 09-21 batches — 1,031 records, two thirds of the estate —
carry **zero** qualified records and **zero** admitted research **because
nothing has been run on them**. They were not evaluated and rejected. They were
never evaluated. `productive-intake-00000-00250.csv` is the intermediate case:
it has research on 187 of 250 and a qualified verdict on none, so qualification
has not run there either.

**Nothing in this document is evidence about the quality of the ~30k pool.** It
could be excellent. It is simply unmeasured, and an unmeasured pool is UNKNOWN,
which per invariant 0 never becomes "poor", "exhausted" or "searched". Any later
reader quoting section 2's funnel as "only 2 candidates in 30,000" would be
quoting a funnel over **300 pilot records**.

So the account below is a real company that arrived through the real client
source and the real gates — but through the **pilot** batches, because those are
the only records qualification and research have ever been run on. Supplying the
large pool — a bounded sample with a spend cap — is a **separate, separately
owned task**, opened after this artifact is posted, and is deliberately not
started here.

---

## 4. ADMITTED — `packfacts.pack_for`

**CLAIM** The row carrying the claim is identity-admitted for this account, by
the stronger of the two admissions, and it is `strong` quality so the writer is
actually shown it.
**AUTHORITY** `packfacts.pack_for` and `packfacts.identity_of` on the record as
the store holds it.
**MEASURED AT** 2026-09-28T12:0xZ.
**STATE** PASS.

    ADMITTED    https://brandiq.com/about               quality strong
    ADMITTED    https://brandiq.com/                    quality strong
    ADMITTED    https://brandiq.com/e-commerce/         quality unusable
    ADMITTED    https://brandiq.com/financial-services/ quality weak
    refused 0   unverifiable 0   client_supplied 2

    identity_of(about row, domain, record_id="brandiq-com")        admitted
    identity_of(about row, domain, record_id="somebody-else")      refused

Two of the four reach a prompt (`evidence.USABLE`); all four are in the pack the
claim gates read. That asymmetry is worth naming: **a claim can be licensed by a
row the writer was never shown.** It errs safe — the licence is wider than the
prompt, never narrower — but an artifact that reports "the source of the claim"
must read the pack, not the prompt.

---

## 5. LICENSED — both gates, and a negative control

**CLAIM** Both independent claim gates permit a second-person claim grounded in
the ISO certification, and both refuse the same sentence with an ISO number that
is on no page of theirs.
**AUTHORITY** `copylint.untraceable` and `claims.check`, executed.
**MEASURED AT** 2026-09-28T12:0xZ, on the record as the store holds it AND on
the committed offline reconstruction. Identical verdicts on both.
**STATE** PASS.

The sentence:

> You are ISO 9001:2015 certified, confirming a structured, consistent and
> quality-driven approach to managing your internal processes.

    evidence present    copylint.untraceable   []            LICENSED
                        claims.check           []            LICENSED

    negative control    "ISO 27701:2019", same frame, FULL pack present
                        copylint.untraceable   ['27701', '2019']
                        claims.check           "the figure 27701 appears in
                                                no stored fact"

The control matters more than the pass. Without it, "licensed" would be
consistent with a gate that licenses everything.

A SHORT claim sentence is refused even with the row present — `copylint._traces`
requires two shared content words with the pack sentence, and a four-word
assertion does not have them. That is the gate being right, and it is part of
why the copy path needs its retry loop.

---

## 6. TEST D IS CONSTRUCTIBLE — evidence removed

**CLAIM** Removing only `https://brandiq.com/about` withdraws the claim's
licence in both gates, and leaves the account with research, so a hold cannot be
confounded with "it had nothing to write from".
**AUTHORITY** `copylint.untraceable` and `claims.check` on the record with that
one row removed.
**MEASURED AT** 2026-09-28T12:0xZ, real record and offline reconstruction.
**STATE** PASS.

    admitted rows remaining   3      prompt-usable rows remaining   1

    copylint.untraceable      ['9001', '2015']
    claims.check              "the figure 9001 appears in no stored fact"

So run D's two permitted outcomes are both reachable and both attributable:

    the writer drops the claim          -> the claim is GONE
    the writer writes it anyway         -> copylint refuses the draft, the
                                           regeneration loop runs out, the
                                           lead HOLDs

`9001` and `2015` each appear in exactly one admitted row, asserted by
`test_every_withdrawn_token_really_is_only_in_that_row` — which is not implied
by anything, because `copylint._traces` does a SUBSTRING search over the
normalised pack sentence (`ISSUE-055`, open) and a short token can trace against
a longer number containing it.

### Run B, and the constraint a real account adds

Run B swaps one admitted fact for **another real fact on the same page** — the
Inc. 5000 nomination and the Martech Outlook award instead of the certification
and the expansion timeline. The previous fixture could write any replacement it
liked because its company did not exist. **Fabricating a different operating
shape for a real firm would be exactly the invented provenance the directives
forbid.** The replacement scores `medium`, is admitted, and carries neither
`9001` nor `2015` — so run B also withdraws the claim under test, and the
artifact has to say so rather than report B as holding it constant.

---

## 7. NOT YET MEASURED — "actually used"

**CLAIM** Whether the generated copy really makes this claim is UNKNOWN.
**AUTHORITY** a generation run through `generate.run`, which has not happened.
**MEASURED AT** —
**STATE** UNKNOWN. Not a pass, not a fail.

**And section 10d is now the reason it may stay UNKNOWN.** The claim under test
is licensed and removable — that is measured, twice, through both gates. But
the copy that would carry it has to climb Offer A's ladder, and two of its five
rungs cannot be written for this account at all. "Actually used" is blocked
behind a sourcing problem, not behind the writer.

Admitted and licensed are properties of the pack and the gates. **Actually used
is a property of the writer**, it needs model calls, and it is what the matrix
measures. It waits for the P0-B signal, as instructed. Nothing in this document
should be read as criterion 1.

---

## 8. HOW BOTH HALVES OF THE PRIVACY CONSTRAINT ARE SATISFIED

A real company with verifiable public evidence, and no real personal data in a
tracked file. They are satisfied by two separate mechanisms, not by one
compromise.

**The record is real and it is NOT committed.** `record_from_store()` returns
the account as the estate holds it — its stored ICP verdict, its `company_facts`,
its Apify-fetched research and its one sendable contact — out of `work/`, which
is gitignored because it is real companies and real people. **The matrix runs on
that.** Nothing about the contact is in git: not a name, not an address, not a
key, not a title.

**The account's public identity and evidence ARE committed.** `brandiq.com` is a
company domain and is not on `test_fixture_hygiene.FORBIDDEN_DOMAINS`. The two
source URLs are public pages. `tests/fixtures/task425-evidence.json` holds
verbatim excerpts re-verified against the LIVE pages, with http status,
retrieval time and a sha256 of the text as read:

    https://brandiq.com/about   200   2026-09-28T12:03:08Z   14,401 chars
        sha256 207b7c75567f2e0264023e3ed7fe1a318f7431d40bf22c1bd88832ca5da9a539
    https://brandiq.com/        200   2026-09-28T12:03:08Z    8,673 chars
        sha256 8f8424e8f46122c44b6bc41347b4741a173593da451125583df69698fbf1fc44

**The authority for a fact is the live URL plus the verbatim excerpt.** The
sha256 pins what this repository read on that date; it is not a promise about
what a marketing page says tomorrow, and it is not offered as one.

**The about page names four real executives** in its schema.org block, and the
estate's own research row for that page carries all four, because the extractor
took the whole page. **That row is not committed.** What is committed is built
by JOINING chosen, name-free excerpts, and the choice was self-tested at build
time against every one of those names before a single value was written — the
redaction ran before the write, not after it. **That list of names is not in
this repository and must never be**: a guard that has to name real people in
order to protect them has retired itself. The committed check is a property
instead: every multi-word capitalised phrase in every stored value must be one
of an enumerated set of organisations, awards and products. A person's name is
exactly that shape, so a new one fails the test and becomes a human decision.

**The placeholder contact is not the prospect.** The offline reconstruction
needs a contact to build a record at all. It is `Ada Tester` at
`p0c-fixture.test` — a suffix reserved by RFC 2606, which cannot resolve and so
cannot be mailed. It is deliberately **not** derived from the account's real
domain: `ada@brandiq.test` becomes a plausible real address the moment somebody
edits one character, and this account's real mailboxes exist. A test asserts the
account's domain stem appears in no placeholder address or key.

---

## 9. THE KILLED MUTATIONS

**CLAIM** The guards fire when broken, and the source was restored
byte-identical.
**AUTHORITY** `scratchpad/kill_mutation.py` — patch, assert the file on disk
changed, run the intended test, restore, compare sha256.
**MEASURED AT** 2026-09-28T12:1xZ, on the PRE-MERGE fixture, and re-run on the
merged one — both results below.
**STATE** 2 of 3 clean kills, 1 partial, reported as such.

**The hashes below are of the pre-merge file and are stale on purpose, kept so
the two runs are distinguishable.** The merge resolution rewrote
`tests/task425fixture.py`, so a sha256 quoted from before it would be a
different file's hash presented as this one's — which is the exact error this
document keeps naming elsewhere. The post-merge re-run's hashes are in the
second block.

    PRE-MERGE
    fixture sha256 before  1718627a95189e4b3901e5dd5cd7069a4fe59bc20a923bd96f1695f28b9108d8
    fixture sha256 after   1718627a95189e4b3901e5dd5cd7069a4fe59bc20a923bd96f1695f28b9108d8

| # | mutation | intended test | result |
|---|---|---|---|
| 1 | `CLAIM_UNDER_TEST` back to `retained monthly engagements` | `test_the_declared_claim_is_a_specific_both_gates_can_see` | RED, intended reason: `'retained monthly engagements' not found in []` |
| 2 | `EVIDENCE_UNDER_TEST` pointed at the homepage row | `test_copylint_licenses_the_claim_and_then_refuses_it` | RED — but **a different guard fired first**: `research_rows`' usability assertion, `quality='unusable' relevance=0.0`. Reported as a PARTIAL kill: the mutation is caught, by a guard one layer earlier than the one aimed at |
| 3 | a research row retyped with an unsourced figure `400` | `test_strict_rule_every_licensable_token_is_sourced` | RED, intended reason: `'400' not found in ...` |

Mutation 2 is recorded as partial rather than counted as a kill. "The intended
test failed" and "the intended test failed for the intended reason" are
different claims and only the second is evidence.

    POST-MERGE
    fixture sha256 before  PENDING
    fixture sha256 after   PENDING

**STATE of the post-merge re-run: PENDING, and deliberately not started.** All
three mutation targets survive the merge verbatim — `CLAIM_UNDER_TEST = "9001"`
at line 255, `EVIDENCE_UNDER_TEST = ABOUT` at 254, and the `RESEARCH` tuple at
246 — so the re-run is expected to reproduce. It is not run yet because the
full suite is running and the suite section above claims that **nothing else
ran alongside it**; starting a second test process now would make that claim
false and any unexpected failing name ambiguous. Order, not optionality:

    py -3 scratchpad/kill_mutation.py     # after the suite exits

Until it reports, the guards are proven on the pre-merge fixture and UNKNOWN on
the merged one. What IS proven on the merged one is that they are all green
there: 57 tests, 0 failures, 4 skipped.

---

## 10. FINDINGS THAT ARE ABOUT THE SYSTEM, NOT ABOUT THIS ACCOUNT

**Two of these are now separately owned and are NOT worked on here.** They stay
recorded because deleting a finding when it changes hands is how one gets
rediscovered: **10.2 (the crawler)** is `TASK-547` on master, which **refuted
half of what I reported** — the correction is written into 10.2 rather than
quietly removed — and **the ~30k pool supply** (sections 0a and 3) is
`docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md`, a bounded 500-record sample with a spend
cap. Neither is started here.

**10.1 `ISSUE-048` reproduces on a real record, in a different key.** A claim
resting on the account's `company_facts` — "you employ 28 people across your
offices" — is REFUSED by `copylint` (`['28', 'Advertising Services']`) and
LICENSED by `claims.check`. `claims.support_text` skips
`packfacts.INGEST_FACT_KEYS`, and this record's figures sit under `employees`
and `offices`, which are not in that set because they came from a provider
rather than the client CSV. The stricter gate wins for shipping, so nothing
unsafe ships — but the two gates disagree about what is licensed, and an
artifact that names "the exact claim licensed" from one of them will be wrong.
REPORTED. Not fixed: tightening a claim gate is not this task's licence.

**10.2 The crawler cannot READ this account's pages — and my inference from
that was wrong. CORRECTED.**

The measurement stands: `webfetch.readable_text` returns **0 characters** for
both URLs, because the site is an Inertia app whose copy lives in a `data-page`
JSON attribute rather than in text nodes, so `looks_like_an_app` is True. The
evidence file records `crawler_readable_text_chars: 0` beside the decoded
character count so the asymmetry is visible rather than inferred.

**What I inferred from it does not reproduce.** I wrote *"a re-crawl would
silently empty this account's pack"*. `TASK-547`, on master at `417dfc02`,
checked that before building a guard and the guard turned out not to be needed:

    CLAIM      a recrawl of an app-shell site cannot empty a stored pack
    AUTHORITY  webfetch `looks_like_an_app` -> finish(JS_RENDERING_REQUIRED)
               with `pages` empty; research.py's `if not pages: ... return None`
               returns BEFORE touching rec["research"]; and
               rec.setdefault("research", []).extend(...) appends, never replaces
    STATE      VERIFIED, with a control: an app shell reads 0 chars and
               `looks_like_an_app` True, a prose page reads 1,199 and False

So the crawler already **fails closed and names the failure** —
`JS_RENDERING_REQUIRED`, recorded as `SCRAPE_FAILED` — and the stored evidence
is untouched. Its own comment states the position: *"a shell is not evidence
about the company inside it."*

**The correction matters more than the finding.** "The crawler returns nothing"
is a measurement; "a recrawl would empty the pack" was a guess about code I had
not read, stated with the same confidence. What is actually true is narrower and
is a CLASS rather than an account: Brand IQ's pack **cannot be rebuilt** from its
live site by the free crawler, so if that stored evidence were ever lost by some
other route, a recrawl would recover nothing. That is a coverage limitation, it
applies to every JavaScript-rendered site in the estate, and it is `TASK-547`'s
to carry — not mine.

**10.3 `generate.size` has no caller.** It is the free ContactOut people-count
enrichment; `grep` finds one call site and it is a test. Noted while checking
whether a real domain could cause a provider request during generation — it
cannot, via that path. REPORTED.

**10.5 `claims.asserts_about_them` does not see a bare possessive.** Found by
the corridor check in 10d, reproduced on the real record:

    "You have margin visibility on every project."      REFUSED
    "Your margin visibility slips between projects."    SUPPORTED

`SECOND_PERSON_ASSERTIONS` is a phrase list — `you are `, `you have `,
`you track `, `your team is `, `your agency is `, `your studio is ` — and a
bare `your <noun>` matches none, so the sentence is never examined even though
it asserts exactly what the refused one asserts. The safe direction is to
tighten it, and that is **not** this task's licence: it would change what may
ship for every stored lead in the estate. REPORTED, not exploited, not fixed.
It is the more dangerous half of P0-B's corridor: the phrasing that HOLDs and
the phrasing that ships an unsupported claim differ by one word.

**10.4 The claim-licensing pack is wider than the prompt.** `packfacts.pack_for`
admits on identity alone; `research.for_prompt` additionally filters on
`evidence.USABLE`. Two of this account's four admitted rows are `weak` or
`unusable` and are never shown to the writer, yet they can license a specific.
Safe direction, and it means "where did this claim come from" must be answered
from the pack. REPORTED.

---

## 10a. THE SUITE — WHAT IS MEASURED AND WHAT IS STILL UNKNOWN

**CLAIM** This change adds no failing test name to the suite.
**AUTHORITY** the full `python -m unittest discover -s tests -v` run, diffed
AS A SET of failing names against
`docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names).
**MEASURED AT** —
**STATE** **UNKNOWN, and on this branch it is no longer ATTRIBUTABLE.**

Two full-suite runs were started and both were **discarded, not reported**. The
first measured a fork point 30 commits behind master. The second was still
running when `origin/task-p0b-copy-engine-pareto` was merged in, so its tree
changed underneath it.

**A third run would not answer the question either**, and that is worth stating
rather than quietly running one. This branch now deliberately carries an
unreviewed branch — P0-B — merged for measurement. A set diff against the
128-name baseline would report P0-B's failures and P0-C's indistinguishably, and
"the suite is clean" would then be a claim about somebody else's unreviewed
work. **A full-suite verdict for this branch belongs to P0-B's review, not to
this artifact.**

What IS attributable to P0-C is measured below, and it is bounded because the
change is five new files plus one pre-existing one.

What IS measured, targeted at the ways this change can add a failure — it adds
five new files and modifies one, `tests/task425fixture.py`, whose every
consumer came in with the merge:

| risk | measurement | state |
|---|---|---|
| the new tests themselves fail | `tests.test_the_claim_under_test_is_load_bearing` + `tests.test_the_accounts_research_is_grounded_in_a_stored_page`: 33 tests, 4 skipped, 0 failures. The 4 skipped are the store-backed class; run with `QUEUE` pointed at production's queue they are 4 passes, not 4 skips | PASS |
| new tracked bytes trip `test_fixture_hygiene` | run twice, once with the five new files present and once with them moved out of the tree: **identical** — the same 2 failures both times, citing `productive.io` in pre-existing files | PASS, and the 2 are not mine |
| a meta-test that enumerates `tests/` reacts to two new modules | `tests.test_invariants`: 85 tests, 2 failures, and both names are already on lines 89-90 of the baseline | PASS |
| **the account swap breaks master's own consumer of the fixture** | `tests.test_the_offer_ladder_is_enforced_as_step_objectives` — master's new ladder test, which builds its record from `fixture.record()` — run on the merged tree with Brand IQ in place: 24 tests, 0 failures, including its own booby-trap test proving the zero-write claim | PASS |

The first three were measured before the merges and the fourth after them.
Re-run together on the final tree — with master `8399b728` and P0-B `cdac64f4`
both merged — the four modules that can see this change are **97 tests, 0
failures, 4 skipped**: my two, master's ladder test, and P0-B's own new
`test_the_copy_engine_converges_and_still_refuses`. The 4 skips are the
store-backed class and are 4 passes with `QUEUE` pointed at production's queue.

**No test imports the harness**, so the changes in 10c cannot move the baseline
at all; `grep` over `tests/` returns nothing for any `scripts/task425_*` module.

The only pre-existing file this branch changes is `tests/task425fixture.py`,
and the row above is the measurement of that change's blast radius.

To finish the check:

    py -3 -m unittest discover -s tests -v > raw.txt 2>&1
    grep -E '^(FAIL|ERROR): ' raw.txt \
      | sed -E 's/^(FAIL|ERROR): [^ ]+ \((.*)\)$/\1 \2/' | sort -u \
      > measured.txt
    # diff measured.txt against the FAIL/ERROR lines of
    # docs/state/SUITE-BASELINE-2026-09-26.txt as SETS. Any name in measured
    # and not in baseline BLOCKS.

One caveat a later reader needs, stated precisely rather than absolutely: the
targeted runs above share the machine with the Qwen worker pool, so no wall
clock here is comparable to the baseline's 2,152s. Each of the four modules was
run alone or with its siblings and nothing else; the read-only corridor and
refusal scripts in `scratchpad/` bind no port, touch no `tests/` module and
write nothing.

## 10b. MASTER IS MERGED IN, AND HOW THE ONE CONFLICT WAS RESOLVED

**CLAIM** This branch is measured against master as it actually is, not against
a fork point 30 commits back.
**AUTHORITY** `git merge-base` and `git merge origin/master`.
**MEASURED AT** 2026-09-28T1x:xxZ.
**STATE** MERGED, and verified by ancestry rather than by the merge printing no
error: `git merge-base --is-ancestor origin/master HEAD` answers YES.

Fork point was `d0e95d20`. Master was `439aa169` (the TASK-425 merge) when this
branch merged it — 30 commits — and advanced to `417dfc02` **during** that
merge, so it was merged a second time. `417dfc02` is the commit that files both
of the separately-owned findings, which is why this artifact can point at
`docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md` and `TASK-547` by name.

**A merge that printed no error is not a merged branch.** The first check here
answered NO, and the reason was not a failed merge — it was master moving under
it. Ancestry against the CURRENT `origin/master`, after a fresh fetch, is the
authority; the merge command's exit code is not.

Exactly one file conflicted: `tests/task425fixture.py`, add/add — master's
TASK-425 merge created the Brightmoor version of it at the same path this
branch created the Brand IQ version.

**Resolved toward master's module plus this branch's account, and master's
fixture was NOT discarded wholesale.** What was kept and what was replaced:

| from master's fixture | disposition |
|---|---|
| the `evidence.make` finding — hand-written rows carry no `quality`, so `research.for_prompt` drops them and the contact is held `UNQUALIFIED` | KEPT, in the prose of `research_rows` |
| the `is_agency` finding — a fixture that does not read as the client's ICP is held by `signal_verification`, and no copy exists to measure | KEPT, and applied: the two rows open with the account's own "advertising technology and services firm" / "full-service … agency" wording |
| the verification-evidence finding — `sendable: True` with no evidence builds zero email candidates and reports no error | KEPT verbatim in `verification_evidence` |
| the one-contact / same-person rationale | KEPT, and now moot in a useful way: this account HAS one contact, which is itself a finding about what the estate's qualified accounts look like |
| the declared-cadence rationale for `CAMPAIGN_ID` | KEPT |
| `BATCH`, `COMPANY_FACTS`, `_FIELD_OF`, `account()`, `generate_contacts()`, `record()`, `research_rows()`, `PERSONA_*`, `CONTACT_UNDER_TEST`, `EVIDENCE_UNDER_TEST`, `FACT_CHANGED_B`, `RESEARCH`, `RECORD_ID`, `CAMPAIGN_ID` | KEPT as names — the module is API-compatible, so every existing consumer still imports |
| the Brightmoor ACCOUNT — company, domain, invented research, three invented contacts, the six invented `company_facts` | REPLACED, because its claim under test was unmeasurable, which is the whole reason P0-C exists |

Two of master's carried-forward details changed because a real account cannot
invent them: `BATCH["row"]` is `UNKNOWN` rather than `412`, because the real
record's row ordinal was never captured and `packfacts`'s own rule is that a
fabricated row number is worse than an honest absence; and `COMPANY_FACTS` holds
one key rather than six, because the real record's facts are provider-derived
and only two of its keys map onto `packfacts.INGEST_FACT_KEYS`.

**CLAIM** Swapping the account breaks no existing consumer.
**AUTHORITY** `tests.test_the_offer_ladder_is_enforced_as_step_objectives` —
master's new ladder test, which builds its record from `fixture.record()`.
**MEASURED AT** 2026-09-28, post-merge.
**STATE** PASS — 24 tests, 0 failures, including its own booby-trap test that
proves the zero-write claim.

---

## 10c. THE HARNESS NOW REFUSES RATHER THAN FALLING BACK

**AUTHORISED**, Zvonimir via coordinator, 2026-09-28, with the refusal as a
condition rather than an extra. `scripts/task425_one_account_dry_run.py` is
edited on this branch. P0-B holds `src/generate.py` and
`src/generate_campaign.py` only; nothing else is active in this file.

The two wiring changes are what was asked for. **The refusal is the point.**

    record_for()      fixture.record()  ->  the real record from the store
    completion check  fixture.CONTACT_UNDER_TEST  ->  the resolved real key

**CLAIM** The harness cannot run on the offline reconstruction, under any
condition, and says why when it stops.
**AUTHORITY** `scratchpad/prove_refusal.py` — the refusal fired deliberately,
three ways, plus the happy path and a no-mutation check.
**MEASURED AT** 2026-09-28, against production's `work/queue.jsonl`.
**STATE** PASS, 6 of 6.

| # | check | result |
|---|---|---|
| 1 | an empty queue | `TheRealAccountIsNotAvailable`, a `SystemExit`, naming record id `brandiq-com`, the account, and every path tried |
| 2 | `the_account()` before the load | refuses, and names the ordering rule it depends on |
| 3 | `contact_under_test()` before the load | refuses rather than answering with the placeholder |
| 4 | the happy path | resolves `brandiq-com`, 4 research rows, 1 contact, and a key that is **not** the placeholder |
| 5 | B and D | B replaces `/about` **in place** (4 rows, order preserved) with the nominated real alternative, stamped `brandiq-com` and scored `medium`; D removes it (3 rows) |
| 6 | the shared account | still 4 rows after all five runs are built — `record_for` deep-copies |

And the matrix's own variable, measured through `copylint` on the records the
harness now builds:

    A  admitted 4   claim LICENSED      C  admitted 4   claim LICENSED
    A2 admitted 4   claim LICENSED      D  admitted 3   claim REFUSED ['9001','2015']
    B  admitted 4   claim REFUSED ['9001','2015']

### A DEFECT THE PROOF CAUGHT, WHICH IS WHY IT WAS RUN

The first attempt **could not make the refusal fire**. Pointed at an empty
queue, `queue_candidates` searched on, found the real estate two candidates
later, and returned the account. The search is right when nobody said where to
look and wrong the moment somebody did: a mistyped `--queue` would have silently
read a different store while the artifact printed the path the operator typed.
An explicit `--queue` is now the only candidate. **An unfired refusal is an
interceptor that never fired**, and this one was two characters from being
exactly that.

### ONE MORE REFUSAL THAT WAS NOT ASKED FOR

`record_for` also refuses if run B finds no row to replace, or run D finds no
row to remove. Without it, B would report "one fact changed" having changed
nothing and D would report an evidence removal that was a copy of run A — both
as a full set of plausible diffs. Same defect class, same answer.

### STILL OPEN, NAMED NOT PATCHED

`scripts/task425_criterion4_completeness.py` reads `fixture.CONTACT_UNDER_TEST`
in three places and would report the placeholder. It was not authorised and is
not edited. The harness now writes `account.contact_under_test` — the resolved
real key — into its result JSON, so that script has a correct value to read when
somebody picks it up.

---

---

## 10d. THE CORRIDOR CHECK — **STOP. DO NOT RUN THE MATRIX.**

P0-B landed and asked for one cheap check before any model call: does Offer A's
ladder close on Brand IQ the way it closed on P0-B's own account? **It does, and
worse than expected — it closes on every qualified account in the estate.**

**CLAIM** Two rungs of the ladder this account's persona selects cannot be
written for it. The matrix would spend its USD 10 ceiling producing five runs
that all HOLD for a reason that is not the variable under test.
**AUTHORITY** `offers.load` for the ladder, `sequencegate.objective_overlap`
for what each rung requires, `claims.check` against the record as the store
holds it — the same gate that refused P0-B's account.
**MEASURED AT** 2026-09-28, on the tree with P0-B merged.
**STATE** **CORRIDOR CLOSED. The matrix is NOT run.**

`economic_buyer` selects `OFFER-A-ECONOMIC-BUYER` (capability `profitability`),
whose ladder is the operator's own:

| rung | objective | `sequencegate` wants a stem in | `claims.check`, second person |
|---|---|---|---|
| 1 | margin visibility | `marg`, `visi` | **REFUSED** — *"'margin' is asserted about them and nothing stored supports it"* |
| 2 | quote versus burn | `quot`, `vers`, `burn` | supported |
| 3 | resource decisions that move margin | `deci`, `marg`, `move`, `reso` | **REFUSED** — *"'resource' is asserted about them and nothing stored supports it"* |
| 4 | Report Intelligence as mechanism… | `angl`, `inte`, `mech`, `repo`, `stre` | supported |
| 5 | reframe and close | `clos`, `refr` | supported |

Rungs 2, 4 and 5 are supported only because none of their words is an
`evidence.OPERATIONAL_TERM`, so `claims.asserts_about_them` never asks for
evidence. Rungs 1 and 3 are the two that make an operational assertion, and
those are the two with no evidence behind them.

### THE ONE SURVIVOR IS A HOLE IN THE GATE, NOT A PATH

A word-by-word sweep found `margin` and `resource` surviving in exactly one
sentence frame. It is not a way to write the rung — it is a blind spot:

    "You have margin visibility on every project."        REFUSED
    "You track margin on every retainer."                 REFUSED
    "Your team is running margin visibility by hand."     REFUSED
    "Your agency is losing margin visibility…"            REFUSED
    "Your margin visibility slips between projects."      SUPPORTED   <--
    "Your resource decisions move margin every week."     SUPPORTED   <--

`claims.SECOND_PERSON_ASSERTIONS` is a list of phrases that all begin `you …`
or `your team/agency/studio is`. **A bare possessive matches none of them**, so
`asserts_about_them` returns False and the sentence is never examined — while
asserting exactly what the refused ones assert.

**NEW FINDING, 10.5 below. Not exploited and not fixed.** Writing the rung
possessively would get copy through by phrasing around a gate, which corrupts
the matrix more thoroughly than a HOLD ever could; and tightening
`asserts_about_them` changes what may ship for every stored lead, which is not
this task's licence. It is also the more dangerous half of P0-B's result: the
same corridor that produces an honest HOLD on one phrasing produces an
**unsupported margin claim in a live email** on another.

### IT IS NOT A BRAND IQ PROBLEM — IT IS THE WHOLE ESTATE

**CLAIM** No qualified account in the estate can support both closed rungs.
**AUTHORITY** `qualify.state_of` + `packfacts.pack_for` + `claims.check` over
all 1,582 production records.
**MEASURED AT** 2026-09-28.
**STATE** MEASURED.

    qualified                              113
    with an admitted pack                   93
    no admitted pack                        20
    pack carries margin and/or resource      18
    BOTH rung probes supported                0     <--
    one rung probe supported                  2
    both rung probes REFUSED                 91

Eighteen packs contain the words and none clears the gate, because
`asserts_about_them` returns **every** operational term in the sentence and each
must be supported: rung 1 needs `margin` **and** `visibility`, rung 3 needs
`resource` **and** `margin`. Brand IQ has `visibility` and not `margin`, which
is why its rung 1 fails on one word.

### AND THE ACCOUNT'S OWN PAGES CANNOT SUPPLY IT

The honest fix the coordinator named first is a further admitted fact from the
account's public pages. Measured across every page of theirs that resolves —
`/`, `/about`, `/e-commerce/`, `/financial-services/`, `/contacts/`, plus five
404s — against `margin, profitab, resourc, utilis, billab, quote, burn rate,
overrun, capacity, headcount, timesheet, time track, forecast, budget, scope
creep, staffing, allocation`:

**one hit, and it is not a fact about them** — `From Awareness to Allocation`,
the title of a case study about a client's media-budget funnel. It says nothing
about how Brand IQ resources its own work, so it cannot honestly ground a
second-person claim about their resource decisions.

### WHAT I DID NOT DO

Per the instruction, and because each would have produced a green-looking
matrix that measured nothing:

- **no rung exempted**, and no `step_objectives` edited;
- **`claims.asserts_about_them` not relaxed** — and its blind spot not used;
- **persona not switched.** `champion` selects Offer B, whose ladder is
  `project visibility / time / resourcing / AI Time Tracking / one operational
  view`, and switching to reach it is run C's own intervention. Using C's
  variable to escape a gate would make run C incomparable with run A by
  construction.

### THE DECISION THIS PUTS TO THE OPERATOR

This is a **sourcing** result, not a gate result. Both gates are right: the
ladder asks for an assertion about the prospect's margin and resourcing, and
nothing public about these companies states it. Three options, none of which I
have taken:

1. **Accept the HOLD as the measurement.** Run the matrix knowing rungs 1 and 3
   will refuse, and report the corridor as criterion 1's finding. Costs the
   USD 10 and produces five runs that differ by nothing measurable — which is
   what P0-B already measured 0-of-5.
2. **Source the evidence the ladder needs.** Margin and resourcing facts do not
   live on agency marketing sites; they live in job ads, interviews, review
   sites and case studies. That is a research-coverage task, and it is the same
   gap the ~30k pool task exists for.
3. **Judge Offer A unwritable from website research and say so.** The ladder was
   approved on 2026-09-27 against an assumption about evidence that 0 of 93
   accounts meets. That is a finding about the offer, for the operator.

## 11. WHAT IS IN THE BRANCH

    tests/task425fixture.py                                 the account definition
                                                            (master's module, the
                                                            account replaced — 10b)
    tests/fixtures/task425-evidence.json                    the stored public evidence
    tests/test_the_claim_under_test_is_load_bearing.py      admitted / licensed / D
    tests/test_the_accounts_research_is_grounded_in_a_stored_page.py
                                                            grounding + redaction
    docs/P0C-CAUSAL-FIXTURE-2026-09-28.md                   this file
    scripts/task425_one_account_dry_run.py                  the two authorised
                                                            wiring changes and
                                                            the refusal — 10c

Everything else on this branch arrived by merging `origin/master` (`417dfc02`)
and `origin/task-p0b-copy-engine-pareto` (`cdac64f4`).

**P0-B IS MERGED FOR MEASUREMENT AND IS NOT INTEGRATED.** It is unreviewed and
not on master. It is on this branch so that a matrix run would measure the
fixed copy engine rather than master's; no claim in this document depends on it
except section 10d, which was measured on the tree with it merged. Nothing here
should be read as P0-B being accepted, and this branch must not be merged to
master while it carries an unreviewed branch inside it.

**Criterion 4's verifier is confirmed broken** (P0-B, verified by the
coordinator): it tests whether a field's LABEL appears in the rendered markdown
and never reads a value, so "all fields present" was true while every value was
empty. It is not this task's file. **No criterion-4 output is treated as
meaningful anywhere in this document** — which is the same defect, from the
other side, that section 1 describes: the "exact claim licensed" column read as
populated because the label was there.

**No gate was touched, and no gate was weakened.** `src/generate.py`,
`src/generate_campaign.py`, `src/sequencegate.py`, `src/copylint.py`,
`src/packfacts.py`, `src/claims.py` and the signature/sender-identity modules
carry exactly what master has. Two places where a gate refused something were
left refusing: `ISSUE-055`'s substring match in `copylint._traces`, and the
`claims` / `copylint` disagreement in 10.1. Tightening either would be the safe
direction and is still not this task's licence.

**Provider writes: 0.** The only network this task made was HTTP GET against
`brandiq.com` through `src.webfetch.fetch`, the robots-respecting free crawler,
and two search queries. No provider adapter was called, no model was called, no
campaign, lead, sequence or sender was created or modified, and production
`work/` was read and never written.

---

## 12. WHAT HAPPENS NEXT

1. **P0-B has landed and is merged into this branch FOR MEASUREMENT ONLY** —
   `origin/task-p0b-copy-engine-pareto` at `cdac64f4`, which is **not merged to
   master** and is unreviewed. It is here so the matrix would measure the fixed
   engine rather than master; nothing on this branch integrates it, and it must
   not be read as integrated.

   **The matrix is still NOT run, and now for a second and better reason**
   (10d): the corridor check says two rungs of Offer A cannot be written for
   this account, or for any of the other 92 qualified accounts with research.
   Running it would burn the USD 10 ceiling on five runs that all HOLD for a
   reason that is not the variable. **That decision is the operator's**, and
   the three options are in 10d.
2. **The harness is ready** (10c): it runs on the real record with the real
   contact, and it **refuses** rather than falling back — proven by firing the
   refusal three ways. The matrix command is

       py -3 scripts/task425_one_account_dry_run.py \
         --queue <the checkout holding the estate>/work/queue.jsonl \
         --json work/task425.json --out docs/TASK-425-...md

   `--queue` is now used alone when given, so it must be right; the run stops
   with a sentence if it is not.
3. The matrix will not be labelled PASS unless every required comparison is
   valid. Comparability is evidence to be shown, not a default.
4. **Not started here, by instruction**: the ~30k pool supply task, and the
   crawler guard for a recrawl that empties a previously-populated page. Both
   are separately owned.
