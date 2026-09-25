# Merge request — rung 3 for approval, copylint on the real send path, and the pack-fact check

Lane D (Copy), 2026-09-24 late. Background agent, own locked worktree.

    worktree   .claude/worktrees/agent-a63bd2d9102384dba
    branch     worktree-agent-a63bd2d9102384dba
    base       24acafff  (= master at the time this lane started)

**Nothing here is merged and nothing here was pushed to a provider.** No
EmailBison call, no HeyReach call, no write to `work/`, no edit to
`config/.env`, `src/providers/*`, `scripts/*_watch_loop.py`, or to the three
files LANE B holds (`config/clients/productive.yaml`, `src/cadence.py`,
`scripts/batch1_build.py`).

**Read §2 before deciding anything.** The copylint wiring is correct, is
proved on the real send path, and **refuses every push this system can make
today** — including tomorrow's 128. That is not a bug in the wiring; it is
what the lint says about the estate. The decision it puts in front of you is
named at the end of that section.

---

## 1. Rung 3 — DRAFT, FOR YOUR APPROVAL. NOT APPROVED, NOT WIRED.

Your brief, verbatim: **name Productive, one capability, one consequence, per
persona.** This takes the cadence from four steps to five.

Rung 3 sits between `comparable_proof` (rung 2) and `angle_shift_*` (rung 4).
It is a **thread reply** and carries `SUBJECT_1`, so the thread-reply pattern
becomes `[false, true, true, false, true]` — em1 opens, em2 and em3 reply into
it, em4 opens a new thread with `SUBJECT_2`, em5 replies into that.

Neither draft asserts a prior message. `cadence.py` already carries that rule
in full for `breakup`, `persona_pain` and `comparable_proof`: a record with no
confirmed touch is the default shape, `claims.py` cannot see a claim about US,
and `outreachclaims` still has no consumer on the send path. So no "following
up", no "as I mentioned", no "one more note" — and no "I will leave it here"
either, because two rungs follow this one and that sentence would be false on
every send.

### 1.1 economic_buyer — capability `profitability`

    subject   how teams your size handle {angle_word}
    thread    reply into thread 1

> {first_name}, here is the specific thing {our_company} does, in one line, so
> you can decide whether it is worth any more of your attention.
>
> {capability}.
>
> The consequence is the part that matters at your level. A project heading
> under margin is visible while there is still a decision to make about it:
> move somebody, change the scope, or let it run knowing what it will cost.
> Month end tells you which of those you did not do.
>
> Is that readable at {company} while a project is open, or only after it
> closes?

`{capability}` resolves to the client's own words in
`config/clients/productive.yaml` → `product.capabilities.profitability`:
*"margin per project while it is running, not after it closes"*. Not a new
claim about the product — the client's sentence, unedited.

### 1.2 champion — capability `budgeting`

    subject   how teams your size handle {angle_word}
    thread    reply into thread 1

> {first_name}, here is the specific thing {our_company} does, in one line.
>
> {capability}.
>
> The consequence is that the weekly number stops being something a person has
> to build. Nobody exports hours on a Thursday afternoon so that Friday has a
> figure in it, because the figure is already there and it is the same one
> finance is reading.
>
> Would that change how the week runs at {company}, or is it already close to
> that?

`{capability}` → `product.capabilities.budgeting`: *"what a project was quoted
at and what it has burned so far"*. `budgeting` rather than
`resource_planning` because it is the one capability that is true to all four
champion angles — `finance`, `delivery`, `operations` and
`resource_management` — and the template carries one capability, not a menu.

### 1.3 Both drafts were run through the real lints, not read over

    persona           words  subject  buzzwords  dash  substituted  untraceable
                                                       punctuation  with NO pack
    economic_buyer      103   50 ch      none    none      none         none
    champion             86   50 ch      none    none      none         none

`lint.MIN_WORDS` 40, `lint.MAX_WORDS` 180, `lint.MAX_SUBJECT` 60. The last
column is the one worth your eye, and §3 explains why: **`persona_pain` is the
only template in `cadence.py` that produces an untraceable company claim**, and
it is the one that renders as `body_1`.

    persona_pain                 untraceable with NO pack: ['Northwind Studio']
    comparable_proof             none
    comparable_proof_short       none
    angle_shift_economic_buyer   none
    angle_shift_champion         none
    close_economic_buyer         none
    close_champion               none
    breakup                      none

Rung 3 as drafted joins the seven, not the one. It names `{company}` once, in a
question that makes no claim about them.

### 1.4 What rung 3 needs that does not exist yet — LANE B's files, not edited here

`cadence.template_vars` returns `first_name`, `company`, `angle`, `angle_word`,
`angle_phrase`, `sector` and `line`. It returns **no name for the client's own
product and no capability**, so both `{our_company}` and `{capability}` are
new variables. Three small changes, all in files this lane must not touch:

1. `src/cadence.py` — `template_vars` gains `our_company` from
   `config["product"]["name"]` and `capability` from
   `config["product"]["capabilities"][key]`, the key chosen per persona.
   **Hardcoding the literal "Productive" into `TEMPLATES` would be wrong**:
   `TEMPLATES` is client-agnostic and every other client would then name
   Productive in their own rung 3.
2. `src/cadence.py` — two new entries in `TEMPLATES`, `rung3_economic_buyer`
   and `rung3_champion`, with the bodies above.
3. `config/clients/productive.yaml` — `email_sequence.steps` gains the rung-3
   key between em2 and em4, and `thread_reply_pattern` becomes the five-entry
   list above. Final step `wait_in_days` stays **1, never 0** (campaign 485).

Lane B is taking that file and `src/cadence.py` from three steps to four
tonight. **Rung 3 should land after lane B's four-step change, not beside it**,
or the two edits collide in the same two files.

And S7 must then re-render: `s7-copy.jsonl` carries `subject_1` and
`body_1..3` today — measured below, 1,908 rendered steps across 636 rows,
exactly three per row — so `body_4`, `body_5`, `subject_2` and now `body_3`'s
replacement do not exist yet.

---

## 2. Copylint is on the real send path

### 2.1 What was wrong with TASK-277, confirmed by reading it

Commit `c0c63d58` on branch `qwen-worker-4-r9`, "TASK-277: the copy lint is on
the send path, not merely present". Checked against the files on that branch,
not against the report:

- it adds `push.run_with_copylint(leads, packs)` to `src/push.py`;
- `git grep -n run_with_copylint qwen-worker-4-r9 -- 'src/*' 'scripts/*'
  'tests/*'` returns **nine lines: one definition and eight test calls.**
  Nothing in `src/` or `scripts/` calls it. `git log --all -S` over the same
  name returns one commit, its own;
- its 234-line test file has 8 `def test_`, makes 8 direct
  `push.run_with_copylint(...)` calls, and contains `push.run(` **zero** times;
- and `src/push.py` is not the send path. Its `run()` raises
  `LiveSendNotEnabled` on `live=True`.

A lint wired into a module that refuses to send, through a function nobody
calls, proved by tests that call it directly. **That is the defect the task was
written about, reproduced by its own fix. Do not merge `c0c63d58`.**

### 2.2 Where it is wired now, by name

    src/bisonfactory.py  line 86   _refuse_copylint(plan, recs, report)
                         line 76   report["copylint"] = _copylint_report(plan, recs)   (dry run)

Inside `bisonfactory.stage`. It sits **after `_plan()` and before
`bison.bound_workspace()`** — before the tenancy read, therefore before the
first provider call of any kind, not merely before the attach.

`stage` is the chokepoint, so one wiring covers every caller rather than one
of them. Every call site in the repository, live and dry:

    scripts/batch1_push.py:137            stage(slug, live=bool(args.live))   THE PUSH
    scripts/repoint_to_all_mailboxes.py:178  stage(slug, live=True)
    scripts/write_control_campaign.py:156    stage(CAMPAIGN_ID, live=...)
    scripts/write_control_campaign_v3.py:177 stage(CAMPAIGN_ID, live=...)
    scripts/batch_preflight.py:160        stage(..., live=False)["plan"]      dry run

The last one is a free win: the preflight is already a dry run, and it now
carries `report["copylint"]` — so the verdict is readable before `--live`
rather than during it.

**The LinkedIn path is NOT covered and this lane did not extend it.**
`heyreachfactory.stage` is a separate function that follows the same
plan/refuse/write/read-back pattern; the copy that travels to HeyReach in
merge variables passes no batch lint today. Named here so nobody reads "the
copy lint is wired" as covering both channels.

That placement is deliberate and it is ISSUE-037's lesson: the blank-render
gate refuses *after* `_ensure_leads` and its refusal does not roll back, which
on 2026-09-24 left 49 leads attached across 496/497/498 while all three push
reports said `REFUSED`. A gate that raises is not a gate that stopped
something.

Three properties of the wiring, each of which a test asserts:

- **It enumerates no rules.** It calls `copylint.check_batch`, and the refusal
  text is `copylint.report_lines(...)` verbatim. A rule added to
  `copylint.RULES` next week is carried into the refusal with no line changing
  in `bisonfactory`.
- **`steps_expected` is this plan's own sequence length**, not
  `copylint.STEPS_EXPECTED`. The constant is 5, your target cadence; checking
  a four-step push against it would refuse every lead for a reason that is
  about the cadence rollout wearing a copy lint's name.
- **The packs are identity-checked**, through the new `src/packfacts.py`. §3.

### 2.3 The test that asserts the push REFUSING

`tests/test_the_copy_lint_refuses_the_real_send_path.py`, 10 tests, all
driving `bisonfactory.stage` against a fake provider. **None of them calls
`copylint`, `_refuse_copylint`, or anything below `stage`.**

    test_a_lead_whose_copy_breaks_a_rule_cannot_be_pushed
    test_the_refusal_names_the_lead_and_the_rule_in_the_lint_s_words
    test_nothing_reaches_the_provider_when_the_lint_refuses
    test_a_rule_added_to_the_lint_later_is_enforced_here
    test_a_lead_with_no_research_at_all_is_refused
    test_a_fact_that_belongs_to_another_company_supports_nothing
    test_the_same_fact_on_the_account_s_own_domain_does_support_it
    test_a_batch_whose_copy_is_clean_is_staged
    test_the_lint_is_told_this_plan_s_length_and_not_the_target
    test_a_dry_run_reports_the_refusal_without_raising

Every refusal test asserts the provider counter dictionary equals

    {"workspace_reads": 0, "created_campaigns": 0, "created_leads": 0,
     "attached": 0, "sequences": 0}

so "it raised" is never the whole assertion. The refusal a person reads, taken
from a run:

    the batch copy lint refuses this push, and it runs before any provider
    write so nothing has reached the estate:
    REFUSED: 0 of 1 leads clean
      step1_without_pack_fact      1  r1/ada-byron
                                      step 1 opens with a line no pack fact supports
    REGENERATE the affected copy; CLAUDE.md forbids widening a lint rule to
    let a draft through.

### 2.4 The red check — all ten fail when the wiring is removed

Deleting line 86 and re-running:

    6 FAIL   "AssertionError: FactoryRefused not raised"     — the intended reason,
                                                               not another guard
    3 ERROR  KeyError: 'copylint'                            — the control tests,
                                                               which read the report

Deleting the dry-run line at 76 as well takes the tenth
(`test_a_dry_run_reports_the_refusal_without_raising`) red too: **10 of 10.**
`src/bisonfactory.py` was then restored with `git checkout` and the file
re-verified green.

### 2.5 THE DECISION THIS PUTS IN FRONT OF YOU

Measured, by name, on the 38 test modules that import `bisonfactory`, at
HEAD versus HEAD~1:

    baseline at HEAD~1        1 failing name  (test_campaign_audit
                                 .TestNoSecretsOrRealPeople
                                 .test_no_test_fixture_carries_a_real_looking_slack_token
                                 — pre-existing, not this lane's)
    at HEAD                  69 failing names
    NEW failures              68
    failures that disappeared  0

    test_two_campaigns_do_not_collide_at_the_provider       25
    test_crash_restart_idempotency                           9
    test_a_five_step_campaign_sends_five_different_emails    8
    test_staging_a_campaign_twice_builds_one                 8
    test_lead_writes_respect_the_killswitch                  5
    test_staging_refuses_colliding_contacts                  5
    test_lead_variables                                      4
    test_an_approval_is_not_a_fact_check                     2
    test_threaded_sequence                                   2

And the rules those 68 fire on, counted from the refusals:

    step1_without_pack_fact   46
    duplicate_first_line      17

**The one full-suite pass agrees, by name.** `py -3 scripts/run_suite.py
--offline`, one pass, 1,279.9s, not timed out:

    FAILED - 111 failure(s), 68 error(s) of 12527      exit 1

    full suite failing names                                 179
      of which this lane's 68                                 68   ALL of them
      this lane's 68 that the full run did NOT reproduce        0
      failing for reasons unrelated to any file this lane touched  111
        test_e2e 14 · test_preproduction 6 · test_enrich 5 ·
        test_a_resume_leaves_a_ledger_row 5 · test_for_prompt_quality 5 ·
        test_ownership_readback_staleness 5 · and 26 more modules

So **179 = 111 + 68**, and the 68 are exactly the set measured against HEAD~1,
with none appearing or disappearing under full discovery. The 111 are not this
lane's: the previously committed `scripts/suite_verdict.txt` recorded 110 on a
different tree, which corroborates rather than proves — that file is stale and
was not used as a baseline.

**Every one of them is "this fixture stages copy with no research pack behind
it".** That is not a fixture problem that happens to be in tests. It is the
estate: §3 measures that **0 of 636** production leads with rendered copy have
a single identity-checked pack fact, so with this merged, **tomorrow's push of
128 refuses too**.

So the wiring is right and the lint is right, and merging it as it stands stops
all sending. Three ways forward, and this is yours to pick. **(c) is the
cheapest and it is measured, not estimated — read §3.4 before choosing.**

- **(a) Land the research packs first, then merge this unchanged.** Branch
  `researchpack-four-sources-2026-09-24` (`7d7cf5a6`, not merged, not an
  ancestor of master) carries the four verified actors and the identity guard;
  S7 then has to attach a pack per lead at render time. This is the version
  where the lint means what it says on day one.
- **(b) Merge this now with the pack-grounded rules not yet blocking.** That
  needs a change in `copylint` — `step1_without_pack_fact` and
  `untraceable_company_claim` reported as *not evaluated* rather than as a
  pass — and it is a change to the contract you merged this morning
  (*"A lead with NO pack is not quietly excused"*), so **this lane did not make
  it.** Four rules stay blocking today: `duplicate_first_line`, `empty_step`,
  `dash`, `buzzword`.
- **(c) Run the free site crawl over the 128 before pushing them, and merge
  this unchanged.** No Apify, no credits, no branch merge. The estate already
  holds crawl research for 394 records and it is exactly the shape
  `packfacts` reads. **Measured in §3.4: 366 of those 394 (93%) would pass
  rule 1 today.** That clears production's 636 — the push goes out. It does
  not clear `untraceable_company_claim`, and §3.4 has that number and the one
  sentence that fixes it.

  **It does not clear the 68 tests, and nothing except the tests can.** A
  crawl over production leads changes no fixture: the 46
  `step1_without_pack_fact` failures each need a `research` row on their
  fixture record, and the 17 `duplicate_first_line` ones are two leads sharing
  one body, which is a real defect in the fixture. That is a day of work in 9
  files this lane was not sent to change, and it is the same work under (a),
  (b) and (c). **Whichever is chosen, those 9 files are a task to write, not a
  thing to discover during a merge.**

I did not take (b) on my own authority, and I did not soften the lint to make
the suite green. Widening a rule to let a draft through is the one thing
`CLAUDE.md` forbids by name.

---

## 3. Every rendered step checked against pack facts

`scripts/packfact_check.py`, read-only, plus the new `src/packfacts.py` that
both it and the send path ask.

### 3.1 Identity, not presence — and it fails closed

`packfacts.identity_of(row, domain, record_id)` returns one of three answers,
never a boolean:

    admitted      the fact says whose it is, and it is this account's
    refused       the fact says whose it is, and it is somebody else's
    unverifiable  the fact does not say, so the question was never asked

The third is not a pass, and it is reported apart from the second because
"could not ask" and "asked, and the answer was no" have different fixes. The
test is applied to what the row can answer with: its **own website field**
where it has one (`companyWebsite`, `website` — the field
`researchpack.actors.is_this_company` reads and the one the jobs defect
contradicted while `companyName` agreed), otherwise the **host of the page it
was read from**, which is right for a site crawl and the only test available
for it. A LinkedIn post's host is LinkedIn's, so it is `unverifiable` here and
its identity has to be established upstream where the fact is made.

### 3.2 The negative control — it fires on the real artefact

Presence-only would have called all of this covered. Run over the quarantined
pre-fix pilot cache (`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json`):

    source                       this    other  unknown
    company_slug                   13        2        2
    open_roles                     21       50        0

    accounts where NO row was this company: 9
      <a prospect domain>        open_roles   10 rows      3gsllc.com      company_slug  1
      4thwhale.com     open_roles   10 rows      5p-retail.be    company_slug  1
      56kdigital.se    open_roles   10 rows      7t.co           company_slug  1
      62miles.be       open_roles   10 rows      aciworldwide.com company_slug 1
      academyxi.com    open_roles   10 rows

**50 of 71 job rows refused on identity**, reproducing the measurement exactly.
Five of the eight accounts that returned job rows had every one of their ten
rows belonging to somebody else — the late handoff says four; the count from
the artefact is five, and the two `company_slug` refusals are a second instance
of the same defect on a different actor.

### 3.3 The 927 rendered rows

    py -3 scripts/packfact_check.py --rendered work/stage/s7-copy.jsonl \
                                    --queue work/queue.jsonl

    rendered_rows                              927
    matched_to_a_record                        636
    no_record                                  291
    rendered_steps                            1908
    empty_steps                                  0
    leads_with_a_pack                            0
    leads_without_a_pack                       636
    facts_admitted                               0
    facts_refused_on_identity                    0
    facts_identity_unverifiable                  0
    leads_whose_opener_no_fact_supports        636
    leads_with_an_unsupported_specific         280
    steps_with_an_unsupported_specific         280

    unsupported specifics by step:  body_1  280   (body_2 0, body_3 0)

Five things in that table are worth your time.

1. **1,908 steps over 636 rows is exactly three per row.** The rendered copy is
   still the three-step cadence. §1.4's dependency, confirmed from the file
   rather than from the handoff.
2. **291 of 927 rendered rows match no record in `work/queue.jsonl` at all** —
   31%. Copy exists for leads the queue does not know, and for those no
   pack-fact check is even attemptable. That is its own question and this lane
   did not chase it.
3. **0 leads with a pack.** Cross-tabulated directly: 394 records carry
   `research`, 554 records carry a rendered email, and **the intersection is
   zero**. The rendered set and the researched set are disjoint. That is the
   number §2.5 turns on, and it is not an artefact of the identity test — the
   identity test refused nothing here, because those 636 records have no
   research to refuse.
4. **280 unsupported specifics, all at `body_1`, and every one of them is the
   company's own name.** `Zebra Advertisement`, `Sign Specialists Ltd`, `Blue
   Flame Thinking`. The cause is exact: `persona_pain` is the only template in
   `cadence.py` whose rendered body puts `{company}` inside a sentence that
   also addresses the reader, so the company name becomes a checkable specific
   in a claim about the company. 280 rather than 636 because the proper-noun
   pattern needs two capitalised words, and a one-word company name slips past
   it. **These are not 280 invented facts** — they are 280 leads whose own name
   nobody can trace, which is a different and quieter problem.
5. **A control, because "everything fails" proves nothing.** Of the 394 records
   that DO carry research, their own company name traces to their own pack in
   **215** and fails in **179** — 45%. So attaching packs is necessary and is
   not sufficient: nearly half of today's crawled packs never say the company's
   name in a form the lint can match.

### 3.4 Would a free crawl be enough? 366 of 394, measured

The question option (c) turns on: if the 128 were crawled before the push,
would the lint let them through? Answered against the 394 records that already
carry crawl research, by rendering `persona_pain`'s opener for each of them
and asking `copylint`'s own rule-1 question of it:

    records with crawl research                               394
      rule 1 - the opener has a token the pack supports       366   (93%)
      rule 1 - fails                                           28   (7%)
      own company name traces to its own pack                 215   (55%)
      own company name does NOT                               179   (45%)

The first pair is the answer: **the crawl already on this estate is enough for
rule 1 in 93% of cases.** No Apify run, no credits, no branch merge.

The second pair is what it is not enough for. `untraceable_company_claim` asks
whether every checkable specific in a sentence that addresses the reader
traces, and on 45% of these packs the company's own NAME does not — the crawl
snippet is often a navigation dump that never says the name in prose. So the
128 would still hit §3.3's item 4 wherever the name is two capitalised words.

Two ways to close that, and the second is cheap:

- give `persona_pain`'s closing question a wording that does not pair a direct
  address with `{company}`, the way the other seven templates already do not
  (§1.3). One sentence, in `src/cadence.py`, which LANE B holds tonight;
- or require the crawl to keep a snippet that names the company. That is a
  crawler change and a bigger one.

Rung 3 as drafted needs neither: it is already clean with no pack at all.

### 3.5 What this check cannot do, said out loud

It inherits `copylint.untraceable`'s reach. It extracts figures, money,
percentages, dates, quoted phrases and capitalised multi-word names from
sentences that make a claim about the company, and requires each to trace. A
sentence that is wrong while carrying no specific — "you must be struggling
with scale" — passes this and is still a person's judgement call.

---

## 4. Files in this branch

Six files. Run `git diff --stat 24acafff HEAD` for the sizes rather than
trusting a number typed here, which is stale the moment this file is edited
again:

    src/bisonfactory.py                     MODIFIED  the wiring, +2 imports
    src/packfacts.py                        new       identity, not presence
    scripts/packfact_check.py               new       §3, read-only
    tests/test_the_copy_lint_refuses_the_real_send_path.py  new  10 tests
    docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md      new  this file
    docs/state/LANE-D-BISONFACTORY-FAILURE-DIFF-2026-09-24.json  new  §2.5 BY NAME

`src/bisonfactory.py` is the only file changed rather than added, and its one
deleted line is the `from . import ...` line that gained `copylint` and
`packfacts`. The last file exists because this repository has learned twice
that a baseline which is a COUNT cannot say which tests changed: it carries
all 68 new failing names and the one pre-existing one.

Not edited: `config/clients/productive.yaml`, `src/cadence.py`,
`scripts/batch1_build.py` (LANE B), `config/.env`, `src/providers/*`,
`scripts/*_watch_loop.py`, anything under `work/`.

## 5. What this lane did NOT do — three tasks, written out, numbers left blank

The pool is at depth 1 and I am not allocating numbers, because 034 was taken
twice the same evening and the register's own lesson is to allocate before
writing rather than after. These are ready to number.

**A. The nine fixture files that stage copy with no research.** §2.5 names
them and `docs/state/LANE-D-BISONFACTORY-FAILURE-DIFF-2026-09-24.json` carries
all 68 test names. 46 need one `research` row on their fixture record — the
shape is in `tests/test_the_copy_lint_refuses_the_real_send_path.py`'s
`OWN_FACT`, four keys. 17 are two leads sharing one body, which is a real
fixture defect and wants two bodies. Do NOT satisfy either by weakening a
rule. Required under every option in §2.5.

**B. One sentence in `persona_pain`.** It is the only template of eight that
pairs a direct address with `{company}`, which makes the company's own name a
checkable specific inside a claim about the company — 280 of 636 production
rows, and 179 of 394 crawled packs could not support it (§3.4). The other
seven templates already show the shape that does not have this problem. One
sentence, `src/cadence.py`, after lane B.

**C. The 291 rendered rows that match no record.** 31% of `s7-copy.jsonl` is
copy for an address `work/queue.jsonl` does not hold (§3.3 item 2). Either the
render ran against a wider input than the queue, or records were dropped after
rendering, or the addresses were rewritten. This lane measured it and did not
chase it; no pack-fact check is even attemptable for those rows, and neither
is a push.

## 6. What a reviewer should check first

1. §2.5. The 68 is the whole question and the rest is detail.
2. That `_refuse_copylint` really is above `bison.bound_workspace()` in
   `stage`, because "before the attach" and "before the provider" are
   different claims and only the second one is safe under ISSUE-037.
3. That rung 3 is read as a DRAFT. It is not in `cadence.py`, it is not in any
   config, and nothing renders it.
