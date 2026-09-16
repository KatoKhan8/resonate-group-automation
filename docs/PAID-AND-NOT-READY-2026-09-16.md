# Paid and not ready: the funnel below qualified

2026-09-16. TASK-194. Read-only analysis of `work/queue.snapshot.jsonl`
(2026-09-15T17:52:12+00:00 from master cf23154, 550 records).

All record IDs, domains, contact keys and emails are SHA-256 hashed. No PII.
No provider writes. No paid calls. No state changes. Gates re-run from the
snapshot, not reconstructed.

---

## THE NUMBERS

    qualified                    113
    with contacts                 88    (25 without)
    with email contacts           85
    with verified contacts        66
    campaign-ready                25

Contact-level: 274 contacts on qualified records, 237 with email, 67 verified
(confirmation_count >= 2), 67 sendable. 923 excluded contacts across the 113
records.

The task description's figures (91/67/32) were from an earlier measurement.
The snapshot is the current truth. The shape is the same: roughly a quarter
of qualified records convert to campaign-ready.

---

## GAP 1: 25 records with no contacts

All 25 had person discovery run. None were skipped by a scheduler or blocked
by `dmplan`. The question was not "why did discovery never run" - it ran on
every one - but "why did it keep nobody."

### Breakdown by outcome

    all contacts excluded by persona filter    10
    all contacts excluded by provider          8
      ("the provider returned a row that
       identifies nobody")
    dropped: no contact found                   7
      (same provider-empty outcome, but the
       record was also dropped)
    mixed: collision + persona + provider       0
      (these are counted in the two above)

### The 25, hashed, with reason

| Hash         | Domain       | State    | Excluded | Reason |
|-------------|-------------|---------|---------|--------|
| `1394329e3e13` | `2b6b1845ad88` | verified | 5 | all persona |
| `aad28b82e30b` | `0a92f0f6c474` | verified | 2 | all persona |
| `89b61edc55d1` | `993ebe91f2d5` | verified | 2 | all persona |
| `2985b9dc06f6` | `c8ef0fedd9ae` | verified | 2 | all persona |
| `060ffd5da60f` | `3241010e80c1` | verified | 2 | all persona |
| `806b02af5204` | `48b1829af949` | verified | 3 | all persona |
| `47f5c2f9d3af` | `c0e9b502e151` | held     | 4 | 3 persona + 1 collision |
| `e5ed223817b2` | `35ae9ef0be62` | held     | 26 | 20 provider + 1 collision + 5 persona |
| `0eb2f3ac2c08` | `df110833f867` | held     | 2 | 1 collision + 1 persona |
| `a4e45fdf9696` | `e2af2258cfb0` | held     | 9 | 7 provider + 1 collision + 1 persona |
| `2d2d170bf01b` | `f106c40bad46` | held     | 3 | all persona |
| `36a3c71f57fc` | `cce7ce95f8a8` | held     | 14 | 12 provider + 2 persona |
| `8ebe1d5dabda` | `871d6e8a34fb` | held     | 10 | 8 provider + 1 collision + 1 persona |
| `b7abf0b2b67b` | `538bcb87830b` | held     | 6 | 5 provider + 1 persona |
| `7b098679c623` | `1fbca7357d35` | held     | 17 | 15 provider + 2 persona |
| `a8f0b00fba81` | `1921d3df0e6d` | verified | 14 | 11 collision + 3 persona |
| `7ea8b6c1c25f` | `e7569d367e69` | dropped  | 2 | all provider |
| `62425a998d9b` | `b7bb1749ab42` | dropped  | 0 | provider found 0 profiles |
| `965686ad0966` | `077b67abf57b` | dropped  | 1 | all provider |
| `b9e3a93aab9e` | `ecc540b60059` | dropped  | 2 | all provider |
| `666c02c1eac9` | `34b6390f9481` | dropped  | 10 | 9 provider + 1 collision |
| `c43d39a582a5` | `5863dbbe2121` | dropped  | 2 | all provider |
| `79391164c592` | `573564e6034f` | dropped  | 6 | 5 provider + 1 collision |
| `a222761e6b9a` | `71c2d62495b7` | dropped  | 1 | all provider |
| `270b752d9bc7` | `6aa28f50465f` | dropped  | 1 | all provider |

### Why discovery kept nobody

**TASK-160's answer was "no runner was invoked."** That is NOT the answer here.
Every one of these 25 records has `people-count` and `decision-makers` in its
enrichment log. The runner ran. The providers answered. The answer was nobody.

Two reasons, both permanent:

1. **Persona filter excluded everybody found (10 records, 6 still live).**
   ContactOut found people, but none matched the client's target persona
   (economic_buyer, founder, operations lead). The filter is correct - it is
   the system working as designed. These 6 records in `verified`/`held` state
   have contacts in `excluded` but not in `contacts`. Recoverable only by
   widening the persona filter, which is a policy decision, not a bug.

2. **Provider found nobody usable (15 records, 9 dropped, 6 held).**
   ContactOut returned rows that "identify nobody" (generic company profiles,
   not people), or returned zero profiles at all. AI Ark and Blitz fallbacks
   also found zero. This is a provider coverage question: the domain is too
   small, too new, or too foreign for the providers' databases. The 6 held
   records have exhausted every waterfall leg and have nothing to show for it.

**Recoverable: 0 of 25.** The persona filter is working correctly and widening
it is a policy decision. The provider-empty records have been through every
waterfall leg and have nothing left to try.

---

## GAP 2: 207 contacts enriched but not verified

Of 274 contacts on qualified records, 67 are verified and 207 are not. These
207 span 42 unique records (some records have multiple unverified contacts).

### Split: "we found nobody" vs "we found somebody and could not verify"

    found email but could not verify it    170
    no email found at all                   37

### Failure kinds

| Kind                                  | Count | Fix |
|---------------------------------------|------:|-----|
| `insufficient_confirmations`          |   143 | Need one more provider to confirm |
| `no_email_found`                      |    37 | No address discovered |
| `mx_blocked`                          |    15 | Domain's email gateway filters cold mail |
| `catch_all_uncleared`                 |    11 | Catch-all domain, Reoon did not clear |
| `insufficient_confirmations_primary_only` | 1 | ContactOut said valid, Deliverable errored |

### What each kind means

**insufficient_confirmations (143 contacts).** The policy requires two
independent provider confirmations. ContactOut said `valid` but Deliverable
returned `error` (its response shape is undocumented and has not been parsed).
Reoon either was not called or agreed with ContactOut but Deliverable's failure
left the count at one confirmed. The address is probably real - ContactOut and
often Reoon both say valid - but the policy demands two, and Deliverable's
error means the second never arrives.

This is the single largest bucket. 143 contacts are probably sendable but are
held by a provider that returns unparseable responses.

**no_email_found (37 contacts).** These contacts have a LinkedIn profile but
no email address. They are LinkedIn-only reachable. Not a verification failure
- a discovery outcome.

**mx_blocked (15 contacts).** The domain's email security gateway (typically
a corporate Exchange or Proofpoint deployment) is classified as filtering cold
mail. The address may be valid but the MX gate refuses to send. This is a
permanent property of the domain's infrastructure.

**catch_all_uncleared (11 contacts).** The domain accepts all addresses
(catch-all/accept-all). ContactOut says `accept_all`, which is not a
confirmation. Reoon's `is_safe_to_send` is the only path to clear a catch-all,
and either Reoon was not called or said no. These addresses may be real but
cannot be distinguished from `firstname@domain` guesses.

### Recoverable

    insufficient_confirmations    143    recoverable IF Deliverable is fixed
                                         OR policy is changed to 1 confirmation
    no_email_found                 37    not recoverable (LinkedIn-only)
    mx_blocked                     15    not recoverable (domain infra)
    catch_all_uncleared            11    recoverable by calling Reoon
    primary_only                    1    recoverable (same as insufficient)

If Deliverable were fixed or the policy relaxed to one confirmation, 144 of
170 contacts with email would become verified. That would move many of the 42
records into the verified pool.

---

## GAP 3: 41 records with verified contacts but not campaign-ready

66 records have at least one verified contact. 25 are campaign-ready. 41 are
not. This is the biggest single drop and the most expensive, because every one
of those 66 records has been paid for.

### Why 41 are not ready, by gate

| Gate                              | Records | Steps affected |
|-----------------------------------|--------:|---------------:|
| No cadence generated              |      15 | 0 (no steps exist) |
| Cadence exists, zero approvals    |      23 | 289 steps held |
| Cadence exists, some approvals    |       3 | 10 steps held |

### The 15 with no cadence

These records have verified contacts but `cadence` is empty. No generation
ever ran. They are in `verified` (12) or `held` (3) state. The generation
step - which reads research, builds the ladder, and writes the cadence - was
never invoked for these records.

| Hash         | Domain       | State    | Verified contacts |
|-------------|-------------|---------|------------------:|
| `983554753669` | `20ba2bec38b5` | verified | 1 |
| `ef5030d04109` | `31720b152ed1` | verified | 1 |
| `4b37ea891b56` | `3afb5e0010d9` | verified | 1 |
| `4b0bc54de0a0` | `1baa1b616956` | held     | 1 |
| `8953a27075c2` | `c3f09366d72f` | verified | 1 |
| `9d4ced9d713d` | `4ddc9c81177c` | verified | 1 |
| `828868a84abf` | `51c42e632f20` | verified | 1 |
| `fe1f35998ca8` | `1e332d6fbb50` | held     | 1 |
| `aa86bcae3d3f` | `f2f4b0d278ed` | verified | 1 |
| `024ba413ded7` | `a3a16ee58d26` | verified | 1 |
| `8a259a870a3c` | `53e895a2e32a` | verified | 1 |
| `9888d6a9d54d` | `41da47c0397b` | verified | 1 |
| `a965f4ebe3bb` | `39afdf9aca50` | verified | 1 |
| `83cc7c8ac60b` | `947f2f9d81ff` | verified | 1 |
| `84f5e945edbd` | `5f4a81ca417b` | held     | 1 |

**Recoverable: yes, by running generation.** These records have everything
generation needs: qualified verdict, verified contacts, research (in most
cases). The action is to run the generation pipeline.

### The 23 with cadence but zero approvals

Generation ran, cadence steps exist, but no human approved any of them. The
eligibility gate reports `held:draft_not_approved` for 289 step instances
across these 23 records.

**Recoverable: yes, by human approval.** But see `docs/LEADS-ARE-BLOCKED-2026-09-14.md`:
bulk-approving is named as the most damaging action available. The copy must
be READ first, and `docs/LEADS-ARE-BLOCKED-2026-09-14.md` records that a human
read found the generated copy inferior to the fallbacks on every verdict.

### The 3 with partial approvals

| Hash         | Domain       | Approved/Total | Refusals |
|-------------|-------------|---------------:|---------|
| `13f19e079ea0` | `c3c86b5e9b04` | 1/7 | lint_failed:2, unsupported_claim:2, not_approved:3 |
| `06e296b9eb12` | `ad83ab4912c1` | 1/17 | not_approved:16, awaiting_dependency:1 |
| `361967c27122` | `663c917ceea0` | 2/11 | not_approved:7, approval_stale:1, awaiting_dependency:2, unsupported_claim:1 |

These are closest to ready. The approved steps exist but later steps have
lint failures, unsupported claims, or stale approvals. The fix is
regeneration (lint/claims) followed by re-approval.

### Refusal reasons across all 41 records (step-level)

| Reason                          | Count | Category |
|---------------------------------|------:|----------|
| `held:draft_not_approved`       |   289 | recoverable (human approval) |
| `blocked:unsupported_claim`     |     3 | recoverable (regenerate copy) |
| `held:awaiting_dependency`      |     3 | recoverable (earlier step) |
| `blocked:lint_failed`           |     2 | recoverable (regenerate copy) |
| `held:approval_stale`           |     2 | recoverable (regenerate+approve) |

**Every refusal on these 41 records is recoverable.** Zero are permanent
blocks. No contact was refused by collision, fatigue, prior contact,
suppression, MX, or any other permanent gate. The entire gap is: generation
never ran (15), or generation ran but nobody approved (26).

---

## RECOVERABLE vs NOT: THE SPLITS

### Gap 1 (25 records, no contacts): 0 recoverable

The providers found nobody or the persona filter excluded everybody found.
Neither is fixable without a policy change (widen personas) or a different
provider (better coverage on small/foreign domains).

### Gap 2 (207 contacts, not verified): ~155 recoverable

    insufficient_confirmations    143    fix Deliverable OR relax to 1 conf.
    catch_all_uncleared            11    call Reoon
    primary_only                    1    fix Deliverable
    no_email_found                 37    not recoverable
    mx_blocked                     15    not recoverable

If Deliverable were fixed, ~144 contacts would become verified, moving ~38
records into the verified pool.

### Gap 3 (41 records, not campaign-ready): 41 recoverable

All 41 are blocked by missing generation or missing approval. Every refusal
is `held` or `blocked:lint/claims`, both recoverable by running generation
and/or having a human approve.

---

## THE ONE NUMBER

If every recoverable refusal were resolved:

    current campaign-ready                    25
    + Gap 3 recoverable (generation/approval) 41
    = best case from already-verified records 66

That is the ceiling from records that are ALREADY verified. No additional
provider spend needed - just generation and approval.

For comparison, the 66 review-state records' best case (from the task
context) depends on whether they can be qualified and then enriched. These 66
verified records are past all of that.

**The 25 campaign-ready contacts are the floor. The 66 verified records are
the ceiling. The gap between them is generation and approval, not enrichment
spend.**

### If verification failures were also fixed

    already-verified best case               66
    + Gap 2 recoverable contacts (~144)
      spanning ~38 additional records
    = potential campaign-ready              ~104

But this requires fixing Deliverable's response parser or relaxing the
two-confirmation policy, AND running generation AND approval on all of them.
The cost is engineering time, not provider credits - the enrichment spend
already happened.

---

## TIME-DEPENDENT GATES

The following gates were re-run from the snapshot and are current as of
2026-09-15T17:52:12+00:00:

- `held:account_fatigue` - derived from the event log with a rolling 7-day
  window. Changes as touches age out. NOT present on any of the 41 records.
- `held:approval_stale` - changes when the draft content changes. Present on
  2 steps. Will become `held:draft_not_approved` if the draft is regenerated.
- `held:awaiting_dependency` - changes as earlier steps complete. Present on
  3 steps.
- `held:evidence_aged_out` - NOT present on any record currently, but will
  fire when research evidence ages past its TTL.

The gates that are NOT time-dependent and are permanent until acted on:
- `held:draft_not_approved` - permanent until a human approves
- `blocked:lint_failed` - permanent until the copy is regenerated
- `blocked:unsupported_claim` - permanent until the copy is regenerated
- No cadence - permanent until generation runs

---

## WHAT THIS MEANS

The pipeline's problem is not at the enrichment end. The 113 qualified
records already paid for their enrichment. The drop is at the BOTTOM of the
funnel:

1. **15 records were verified and generation never ran.** This is a pipeline
   orchestration gap, not a cost question. Running generation on these 15 is
   free.

2. **23 records were generated and nobody approved.** This is the approval
   gate working as designed. `docs/LEADS-ARE-BLOCKED-2026-09-14.md` explains
   why bulk approval would be damaging. The remedy is a human read, per
   record, per step.

3. **3 records are almost there.** Partial approvals with lint and claim
   failures on remaining steps. Regeneration and re-approval.

4. **207 contacts are held by verification.** The single biggest bucket (143)
   is Deliverable returning unparseable responses. Fixing that one parser
   would move 143 contacts from unverified to verified, potentially adding
   ~38 records to the verified pool.

The priority order is:
1. Fix Deliverable's response parser (143 contacts, ~38 records, engineering)
2. Run generation on the 15 verified-but-no-cadence records (free)
3. Human read and approve the 23 generated-but-unapproved records (human time)
4. Regenerate and approve the 3 partial records (engineering + human time)
