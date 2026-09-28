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
**MEASURED AT** 2026-09-28T12:1xZ.
**STATE** 2 of 3 clean kills, 1 partial, reported as such.

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
**MEASURED AT** re-started against the MERGED tree, 2026-09-28T1x:xxZ.
**STATE** **UNKNOWN. Not a pass.** The full set diff has not completed, and per
invariant 0 an unread authority is UNKNOWN, which never becomes PASS.

An earlier run against the pre-merge tree was **discarded, not reported**: it
would have measured a fork point 30 commits behind master, which answers a
question nobody is asking.

What IS measured, targeted at the ways this change can add a failure — it adds
five new files and modifies one, `tests/task425fixture.py`, whose every
consumer came in with the merge:

| risk | measurement | state |
|---|---|---|
| the new tests themselves fail | `tests.test_the_claim_under_test_is_load_bearing` + `tests.test_the_accounts_research_is_grounded_in_a_stored_page`: 33 tests, 4 skipped, 0 failures. The 4 skipped are the store-backed class; run with `QUEUE` pointed at production's queue they are 4 passes, not 4 skips | PASS |
| new tracked bytes trip `test_fixture_hygiene` | run twice, once with the five new files present and once with them moved out of the tree: **identical** — the same 2 failures both times, citing `productive.io` in pre-existing files | PASS, and the 2 are not mine |
| a meta-test that enumerates `tests/` reacts to two new modules | `tests.test_invariants`: 85 tests, 2 failures, and both names are already on lines 89-90 of the baseline | PASS |
| **the account swap breaks master's own consumer of the fixture** | `tests.test_the_offer_ladder_is_enforced_as_step_objectives` — master's new ladder test, which builds its record from `fixture.record()` — run on the merged tree with Brand IQ in place: 24 tests, 0 failures, including its own booby-trap test proving the zero-write claim | PASS |

The first three were measured before the merge and the fourth after it. All
four were re-run together on the fully merged tree: **57 tests, 0 failures, 4
skipped**, and the 4 skips are 4 passes with `QUEUE` pointed at production's
queue.

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

One caveat a later reader needs: the run shares the machine with the Qwen worker
pool, so its wall clock is not comparable to the baseline's 2,152s. Unlike the
first attempt, **nothing else was run alongside it** — an earlier run had
`test_invariants` and `test_fixture_hygiene` executing concurrently, and both
bind git or loopback, which would have made any unexpected name ambiguous
between a real regression and interference. That run was discarded rather than
reported, and re-started clean against the merged tree.

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

### TWO HARNESS PREREQUISITES FOR THE MATRIX — NAMED, NOT SILENTLY PATCHED

`scripts/task425_one_account_dry_run.py` is TASK-425's file, not this task's,
and as merged it cannot run the matrix on the selected account:

1. `record_for(run)` builds every run from `fixture.record()` — the OFFLINE
   RECONSTRUCTION with the placeholder contact. It must call
   `fixture.record_from_store()` instead, or the matrix measures a redacted
   copy of the account rather than the account.
2. The run-completion check matches `fixture.CONTACT_UNDER_TEST`, which is now
   the placeholder key. It must resolve the real one through
   `fixture.contact_under_test(rec)`, or no run will ever register as having
   got copy through.

Both are one-line changes and both are deliberately NOT made here: the file
belongs to another lane, and changing somebody's harness without their knowledge
is how two sessions come to disagree about what ran. Raised as a prerequisite to
be agreed before step 3.

---

## 11. WHAT IS IN THE BRANCH

    tests/task425fixture.py                                 the account definition
                                                            (master's module, the
                                                            account replaced — 10b)
    tests/fixtures/task425-evidence.json                    the stored public evidence
    tests/test_the_claim_under_test_is_load_bearing.py      admitted / licensed / D
    tests/test_the_accounts_research_is_grounded_in_a_stored_page.py
                                                            grounding + redaction
    docs/P0C-CAUSAL-FIXTURE-2026-09-28.md                   this file

Everything else on this branch arrived by merging `origin/master`.

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

1. **Waiting on the P0-B signal** before running A/A2/B/C/D on this account and
   this identity, through the normal generation and retry path. Running the
   matrix before P0-B's copy-engine fixes land would reproduce the same BLOCK,
   at the cost of the model calls.
2. **The two harness prerequisites in 10b must be agreed first** — the matrix
   runs on `record_from_store()`, the real record with the real contact, the
   same person on every side. A run that quietly fell back to the offline
   reconstruction would be measuring a different account under the same name,
   and would look exactly like a successful run.
3. The matrix will not be labelled PASS unless every required comparison is
   valid. Comparability is evidence to be shown, not a default.
4. **Not started here, by instruction**: the ~30k pool supply task, and the
   crawler guard for a recrawl that empties a previously-populated page. Both
   are separately owned.
