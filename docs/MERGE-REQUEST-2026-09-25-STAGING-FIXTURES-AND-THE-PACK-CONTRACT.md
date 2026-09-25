# Lane L — the staging fixtures and the pack-fact contract

**Branch** `lane-l-staging-fixtures-packfacts`
**Base** `32c37e98` — master as of this morning, carrying lane B
(`7d4ed841`, the five-step cadence and `_require_declared_cadence`) and
lane D (`32c37e98`, the copy lint on the send path and `src/packfacts.py`).
**Date** 2026-09-25, morning
**Nothing live was touched.** No provider call, no paid call, no write to
`config/.env`, `src/providers/*`, `scripts/*_watch_loop.py` or `work/`.

---

## 0. The headline

Master was red on **77 test names across 10 staging modules**. All 77 are
green. Two things were wrong and only one of them was the one in the brief.

1. **68 names**: the batch copy lint refusing fixtures whose leads carry no
   pack fact. The lint is right; the fixtures were modelling a push the
   product now refuses.
2. **9 names**: `tests/test_the_copy_lint_refuses_the_real_send_path.py` —
   **lane D's own module, the one whose entire job is to watch the copy lint
   refuse** — was being refused by **lane B's cadence guard**, one gate
   earlier. Its campaign row declared no `cadence_steps`, `_plan` refuses
   before the lint runs, and so **the suite could not observe the copy lint
   refuse anywhere at all.** A guard masked by another guard, on master, in
   the module written to prove the first guard fires.

That second one is the same shape `test_threaded_sequence` produced within
the last hour, and
it is why the brief's non-negotiable — *the suite must still be able to
observe the lint REFUSING* — was not a hypothetical risk here. It was
already true.

---

## 1. The decision: option (a), and what was rejected

### (a) Give the fixtures pack facts — **CHOSEN**

The contract genuinely changed. `bisonfactory.stage` runs
`copylint.check_batch` before the first provider call, and rule 1 is that
step 1 opens on a line **this account's own research supports**. A fixture
that stages a campaign without one is not testing staging against the
product; it is testing staging against a product that no longer exists.

Three things settled it:

- **Lane D's own merge doc reached the same conclusion and said nothing
  else can.** `docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md` §2, option (c):
  *"It does not clear the 68 tests, and nothing except the tests can. A
  crawl over production leads changes no fixture: the 46
  `step1_without_pack_fact` failures each need a `research` row on their
  fixture record, and the 17 `duplicate_first_line` ones are two leads
  sharing one body, **which is a real defect in the fixture**."* The lint
  found a genuine fault in the fixtures, not only a contract change.
- **Precedent from an hour earlier.** Lane B updated eight fixtures for
  `_require_declared_cadence` and verified each still failed for its
  original reason. Same situation, same answer.
- **The estate agrees.** Of 927 rendered rows, 636 matched a record and
  **zero** carried a pack fact. A fixture with no pack was modelling
  production exactly — and production is refused. Making the fixture match
  the contract is the only version where a green suite means anything.

### (b) Scope the lint so it refuses only where packs are required — **REJECTED**

The argument for it is real and I want it on the record: a crash-restart
idempotency test failing because of copy grounding is a test failing for a
reason it was never about, and that is how a suite stops telling you
anything. I rejected it anyway, for three reasons.

- **It is a lint being widened, which `CLAUDE.md` forbids by name.** Lane D
  said so itself: option (b) needs `step1_without_pack_fact` and
  `untraceable_company_claim` reported as *not evaluated* rather than as a
  pass, and that contradicts the sentence merged this morning — *"A lead
  with NO pack is not quietly excused."*
- **There is no honest place to put the scope.** `bisonfactory.stage` is
  the one send path; `scripts/batch1_push.py` goes through it and so does
  everything else. A "packs not required here" switch is a switch
  production can set. The only truthful scoping would be per-campaign
  policy, which nobody asked for and which would have to be defaulted —
  and defaulted to off, it is (b) with extra steps.
- **It would blind the suite to the failure that is currently true.** Zero
  of 636 production leads carry a pack fact. Scope the rule down and the
  suite goes green while the estate sits in exactly the state the rule
  exists to refuse. That is the false pass the brief warns about.

The fix for (b)'s real complaint is not to scope the lint. It is to give
the crash-restart fixture what a real push carries, so that it goes back to
failing only for crash-restart reasons — which is what §2 does, and §5
proves.

### (c) Run the free site crawl first — **NOT APPLICABLE TO THIS LANE**

Lane D's third option is about production's 636 leads, and lane D measured
that it clears **zero** fixtures. It is the operator's call for the push; it
is not a way to make master green.

---

## 2. What changed

### `tests/packfixture.py` (new, 106 lines, test-only)

One sentence — `GROUNDING = "runs delivery scheduling for independent
clinics"` — and both halves built from it:

- `own_fact(record_id, domain, company)` — a research row `packfacts`
  **ADMITS**. It states no website of its own, so `identity_of` falls back
  to the host of the page it was read from, which is the right test for a
  site crawl and the shape the estate's 394 crawled records already hold.
  The `record_id` is stamped, because `pack_for` refuses a row stamped for
  a different record and a fixture that omitted it would be admitted for
  the weaker of the two reasons.
- `opener(first, company)` — a step-1 body whose **first line** carries the
  grounding. Not under a greeting: `copylint.first_line` takes the first
  non-empty line of step 1, and a fixture opening with `"Hi Ada,"` carries
  no word longer than four characters there and fires the rule with a
  perfectly good pack sitting behind it.
- `foreign_fact(record_id, company)` — the same words read off somebody
  else's site, which `packfacts` returns as **UNVERIFIABLE** rather than
  admitting.

**Why one module rather than nine hand-written pairs.** The fact and the
opener have to agree — the opener's words must appear in the fact, or rule 1
fires — and nine independent pairs is nine chances for them to drift apart,
each discovered later as a staging failure that looks like a product bug.
The sentence is also chosen against the lint's *other* five rules, not for
its prose: no figure, no date, no quoted phrase, no capitalised pair for
`untraceable_company_claim` to extract, no banned phrase, no word in
`copylint.BUZZWORDS`, no spaced hyphen. It was checked against every
company shape the nine modules use, including the two-word
(`Northwind Studio`), two-letter (`Co r1`) and camel-case (`TestCo`) ones,
because the proper-noun pattern behaves differently for each.

**No fixture fakes a fact.** Every one is admitted by `packfacts` on
identity, and the negative control is `foreign_fact`: same words, wrong
site, not admitted. *Unverifiable is not a pass* holds in the fixtures as
well as in the code.

### Three identical record builders became one

`test_staging_a_campaign_twice_builds_one`,
`test_crash_restart_idempotency` and
`test_lead_writes_respect_the_killswitch` each carried a byte-for-byte copy
of the same `_record`. That copy cost fourteen of the 77 names: a second
hand-written record is a second place to forget what a stageable record now
has to carry. It is now one module-level `record()` the other two import.
Nothing else about those modules moved.

### One `src/` change — `_refuse_copylint` does not lint an incomplete plan

This is the only production change in the branch and it needs the argument
spelled out, because it looks adjacent to option (b) and is not.

**What the lint's `empty_step` rule did to the missing-copy refusal.**
`_ensure_leads` refuses a push where any lead carries no approved copy for a
step, and its refusal **names the step**:

    rec-2/rec-2-c1 missing em3 ... Generate and approve the missing steps

`copylint`'s `empty_step` rule answers the same question, but the batch it
is handed is a list of bodies with no step keys in it, so all it can say is
*"one of the 5 steps is empty"* against the lead. And it runs first.
Measured this morning, the consequence was:

- the refusal an operator reads for the **commonest real failure** lost the
  step name;
- the refusal in `_ensure_leads` that carries it became **unreachable on
  the live path** — a correct guard nothing can call, which is the defect
  `CLAUDE.md` names by name;
- and it **masked the tenancy refusal**, which `_approved_copy` is
  positioned where it is specifically to avoid. Its docstring says so:
  *"raising here would mask a tenancy refusal with a copy complaint."*
  `test_a_tenancy_mismatch_is_still_the_first_refusal` is the test that has
  been holding that line, and it was one of the 77.

So `_refuse_copylint` now returns without asking the lint when the plan
already carries a `missing_copy` lead.

**This is not a rule being widened, and here is the test of that:** *no
push that was refused becomes accepted.* An incomplete batch cannot be
staged at all — `_ensure_leads` refuses the whole run, nothing reaches a
provider, not one lead is created. Once the missing steps are generated and
approved, the next run is linted **in full, every rule, still before the
first provider call**. What changed is only *which of two refusals* an
operator is handed for one condition, and the one that names the step wins.
The lint's own scope, rules, and position above `bison.bound_workspace()`
are untouched; `test_the_copy_lint_refuses_the_real_send_path` still
asserts `workspace_reads: 0` and still passes.

### `tests/test_the_copy_lint_refuses_the_real_send_path.py`

Its campaign row now declares `cadence_steps` — the same steps the fallback
through its own `CONFIG` produces, so nothing under test changes. Without
it, lane B's guard refuses in `_plan` before the lint is ever reached, and
all ten tests in the module were measuring the cadence guard.

---

## 3. The by-name failure diff, both directions

Measured with `py -3 -m tests.offline -v`, one pass each, same machine, same
day. `scripts/suite_baseline.py`'s rule applies and is the reason this
section exists at all: *a baseline that is a COUNT cannot say WHICH tests
changed.*

| | before (`32c37e98`) | after (`a272d9a5`) |
|---|---|---|
| tests run | 12,554 | 12,555 (+1, the new by-effect test) |
| failing names, whole suite | **187** | **110** |
| of which this lane's 10 modules | **77** | **0** |
| in modules this lane never touched | 110 | 110 |
| newly broken | — | **0** |

Both runs completed; neither timed out. `187 − 77 = 110`, and the 110 are
**the same names**, not the same count — see §3.3.

### 3.1 FIXED — 77 names, by module

| module | names |
|---|---|
| `test_two_campaigns_do_not_collide_at_the_provider` | 25 |
| `test_crash_restart_idempotency` | 9 |
| `test_the_copy_lint_refuses_the_real_send_path` | 9 |
| `test_staging_a_campaign_twice_builds_one` | 8 |
| `test_a_five_step_campaign_sends_five_different_emails` | 8 |
| `test_staging_refuses_colliding_contacts` | 5 |
| `test_lead_writes_respect_the_killswitch` | 5 |
| `test_lead_variables` | 4 |
| `test_threaded_sequence` | 2 |
| `test_an_approval_is_not_a_fact_check` | 2 |

The full 77 names are listed in
`docs/state/LANE-L-STAGING-FIXTURE-FAILURE-DIFF-2026-09-25.json`, with the
before and after sets and the reason each was failing.

**Cause, counted from the run's own tracebacks:** 68 `FactoryRefused: the
batch copy lint refuses this push`, 9 `FactoryRefused: campaign
'camp-copylint' declares no cadence_steps of its own`. 68 + 9 = 77, which
is exactly the ten modules' total — so every failure in them is accounted
for and none is something else wearing a copy lint's name.

### 3.2 BROKEN — 0 names

`set(after) − set(before)` is **empty**. Not "no regression I noticed": the
set difference was computed and it has no members. No test that passed at
`32c37e98` fails at `a272d9a5`.

### 3.3 The 110 that are not this lane's — the same 110, by name

`test_e2e` 14 · `test_preproduction` 6 · `test_enrich` 5 ·
`test_for_prompt_quality` 5 · `test_a_resume_leaves_a_ledger_row` 5 ·
`test_ownership_readback_staleness` 5 ·
`test_two_providers_disagreeing_is_not_a_headcount` 5 · and 42 more
modules. None of them reaches `bisonfactory.stage`. Two that look as though
they might, and do not:

- `test_staging_the_same_material_twice` (2) — HeyReach list staging;
  `WriteRefused not raised` and an absent ledger entry.
- `test_campaign_cannot_send` (2) — `heyreach.ProviderError not raised`.

Both were also run alone, before and after, and are unchanged.
`test_campaign_audit.TestNoSecretsOrRealPeople.test_no_test_fixture_carries_a_real_looking_slack_token`
was failing at the base too; it is lane D's recorded single base failure, so
it predates both lanes.

### 3.4 The environment, stated rather than buried — and why it did not matter

Another lane was running its own full suite **concurrently** with the
baseline pass (two `python -m tests.offline` processes, 11:00 and 11:04).
`CLAUDE.md` warns that two runs overlap on loopback and teardown and that
one HTTP test fails intermittently, so a diff measured across them is
exactly where a phantom regression would appear.

It did not. **The residue is identical as a SET, not merely as a count:**
110 names before, the same 110 names after, zero appearing, zero
disappearing. An intermittent would have shown up as a name on one side and
not the other, and none did. The ten modules were additionally each run
alone and are green there too.

---

## 4. The test that proves the lint can still refuse

`tests/test_staging_a_campaign_twice_builds_one.py`:

    def test_a_lead_with_no_pack_fact_reaches_no_provider(self)

Built the way lane B built
`test_a_campaign_that_declares_no_cadence_reaches_no_provider` an hour
earlier, and for the same reason: once every fixture satisfies a guard,
nothing is left able to observe the guard firing.

**Asserted by effect, not by message.** It strips the research off both
records (`record(..., grounded=False)`), stages live, and asserts that
`FakeBison.created_campaigns` and `FakeBison.created_leads` are **unchanged**.
The wording of the refusal may be changed; *nothing reached the provider*
may not.

It is not the only one — and that matters, because a single by-effect test
is itself a single point of failure. `tests/test_the_copy_lint_refuses_the_real_send_path.py`
is now reachable again and carries nine more, including the two that make
the identity claim falsifiable in both directions:

- `test_a_lead_with_no_research_at_all_is_refused`
- `test_a_fact_that_belongs_to_another_company_supports_nothing` — a
  well-formed fact containing every word the opener leans on, whose only
  fault is whose it is
- `test_the_same_fact_on_the_account_s_own_domain_does_support_it` — the
  other half of that pair, so the one above cannot pass by refusing
  everything

and `test_nothing_reaches_the_provider_when_the_lint_refuses`, which asserts
the fake's `bound_workspace` was **never even called**.

---

## 5. Each touched fixture still fails for its own original reason

**Method.** For each of the ten modules, the guard that module is ABOUT was
disabled by monkey-patch (nothing on disk changed), the module was run, and
three things were required:

1. the module was **green before** the break;
2. the named test went **red**, with the **named reason** in its message;
3. the failure was **not** a `FactoryRefused` from some other gate firing
   first — the trap `test_threaded_sequence` fell into this morning, and the
   one lane B was warned about an hour ago;

and then the patch was lifted and the module had to be **green again**.

All eleven cases below passed, including the attack on this lane's own new
test. Eleven rather than ten because `test_staging_a_campaign_twice_builds_one`
is checked twice: once for its own subject, and once as the holder of the
unguarded copy-lint case.

| module | break applied | went red for its own reason | red under the break |
|---|---|---|---|
| `test_staging_a_campaign_twice_builds_one` | `_bind` is a no-op: the provider id is never recorded | `test_the_provider_id_is_persisted_where_it_can_be_found` — *"does not name its provider campaign"* | 3 |
| `test_crash_restart_idempotency` | `find_campaigns_by_name` returns nothing: an orphan cannot be recovered | `test_crash_after_find_or_create_before_bind` — *"a second provider campaign was built"* | 1 |
| `test_lead_writes_respect_the_killswitch` | `killswitch.workspace_state` is permissive | `test_a_tripped_killswitch_stops_lead_creation` — *FactoryRefused not raised* | 2 |
| `test_staging_refuses_colliding_contacts` | `_refuse_colliding_leads` is a no-op | `test_in_sequence_is_refused_by_name` — *FactoryRefused not raised* | 4 |
| `test_lead_variables` | `_stale_clearances` returns nothing | `test_stale_numbered_variables_are_cleared` — *"still holds non-empty"* | 5 |
| `test_threaded_sequence` | `_stale_clearances` returns nothing | `test_threaded_campaign_clears_stale_subjects_on_existing_lead` — *"must be cleared"* | 5 |
| `test_a_five_step_campaign_sends_five_different_emails` | `_approved_copy` matches by position, not by step key (steps 2 and 3 swapped) | `test_every_step_gets_its_own_words` | 1 |
| `test_two_campaigns_do_not_collide_at_the_provider` | `find_campaigns_by_name` returns nothing | `test_a_campaign_created_and_never_recorded_is_recovered` — a second campaign, `502 != 501` | 4 |
| `test_the_copy_lint_refuses_the_real_send_path` | `copylint.check_batch` never refuses | `test_a_lead_with_no_research_at_all_is_refused` — *FactoryRefused not raised* | 6 |
| `test_an_approval_is_not_a_fact_check` | `_refuse_unsupported` is a no-op | `test_staging_refuses_a_contact_who_was_never_contacted` — *FactoryRefused not raised* | 3 |
| `test_staging_a_campaign_twice_builds_one` **(the new test attacked)** | `copylint.check_batch` never refuses | `test_a_lead_with_no_pack_fact_reaches_no_provider` — *FactoryRefused not raised* | **1** |

That last row is the one worth reading twice. With the lint disabled,
**exactly one** test in that module goes red, and it is the new one. No
other test in the module was covering for it, and it is not a test that
cannot fail.

---

## 7. What this lane did NOT do, and what is left for the operator

- **It did not move lane D's lint above or below the tenancy read.** The
  lint still runs before `bison.bound_workspace()`. What §2 changed is that
  an already-incomplete plan is not handed to it — which restores the
  tenancy ordering for that one condition without touching where the lint
  sits. If the operator wants the lint *below* the tenancy read in general
  (so a wrong-estate push is always reported as a wrong estate), that is a
  one-line move plus an assertion change in
  `test_the_copy_lint_refuses_the_real_send_path`, and it is a decision
  between two lanes rather than one this lane should take alone.
- **It did not touch production leads.** The estate still has 0 of 636
  rendered leads carrying an identity-checked pack fact. Lane D's option
  (c) — the free site crawl over the 128, measured at 366 of 394 (93%)
  clearing rule 1 — is still the cheapest way to clear the real push, and
  it is still the operator's to take. **Master being green does not mean
  the push will pass.**
- **It did not cover `heyreachfactory.stage`.** Lane D said the copy lint
  does not reach it; that is still true.
- **`untraceable_company_claim` on production copy** is unmeasured by this
  lane. §3.4 of lane D's doc has the number.
