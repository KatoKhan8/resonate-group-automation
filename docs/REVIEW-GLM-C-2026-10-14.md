# Review — GLM lane C, 2026-10-14

Branch `task-glm-c-2026-10-14` (base origin/master `2bf7b8a57`), carries commit
`bd4de5abe`. Scope per `resonate-ops/NEXT-glm-c.md`: **B4** (every template
inside the word contract — table, structural guard, mutation proof), then the
**reverse-test matrix** over the corrected 45-control inventory. B3 was
reassigned to lane A mid-flight and is skipped here (§5).

Everything prospect-facing was left untouched: over-ceiling bodies are listed
for the owner in §2 and were **not** rewritten, per the lane rules.

---

## 1. B4 — every template inside the word contract

### 1.1 The table

Every renderable copy artefact `stage_s7_copy` can produce, measured
2026-10-14 with `lint.countable_words` (chars for LinkedIn notes), **rendered
across the client's whole declared angle space** — 4 families for `champion`,
3 for `economic_buyer`, 7 combinations total. Personas come from the template
names; angle families from `clients.angles_for(config, persona)` on
`config/clients/productive.yaml`.

The s6 step-3/4/5 templates and the 489 hard copy are rendered by
`stage_s7_copy`'s own functions; the rest through `cadence.template_vars` +
`cadence.render`, the path `cadence.expand_step` takes. All 14 artefacts
rendered for all 7 family combinations — **no template is unrenderable, no
family refused**.

| artefact | rendered size (7 families) | binding | bounds | verdict |
|---|---|---|---|---|
| `rung3_champion` | 88 words (flat) | em3 | 60–90 | in bounds |
| `rung3_economic_buyer` | 105 words (flat) | em3 | 60–90 | **OVER by 15** |
| `angle_shift_champion` | 129 words (flat) | em4 | 45–90 | **OVER by 39** |
| `angle_shift_economic_buyer` | 126–131 words | em4 | 45–90 | **OVER by 36–41** |
| `close_champion` | 62–68 words | em5 | 45–90 | in bounds |
| `close_economic_buyer` | 59–64 words | em5 | 45–90 | in bounds |
| **489 `BODY_1`** (live campaign copy) | **100–107 words** | em1 | 60–90 | **OVER by 10–17** |
| 489 `BODY_2` | 87 words (flat) | em2 | 45–90 | in bounds |
| `comparable_proof` | 87 words (flat) | em2 | 45–90 | in bounds |
| `comparable_proof_short` | 59 words (flat) | em2 | 45–90 | in bounds |
| `persona_pain` | 95–102 words | generic | 40–180 | in bounds |
| `breakup` | 75–82 words | generic | 40–180 | in bounds |
| `linkedin_intro` | 119–158 chars | note | 40–300 | in bounds |
| `linkedin_followup` | 130–169 chars | note | 40–300 | in bounds |

Where the bindings come from (recorded in the guard's docstring too):

- `rung3_*` → em3, `angle_shift_*` → em4, `close_*` → em5, by
  `stage_s7_copy._steps_three_four_and_five`'s own rule: "THE NAMES ARE STEP
  KEYS, NOT PROVIDER POSITIONS. `body_3` is em3's words because the step is
  called em3."
- `comparable_proof` / `comparable_proof_short` → em2 (the proof beat is the
  second email of the five-step batch; the short one is its accepted-connection
  variant under balanced_v1's day10).
- `persona_pain`, `breakup` → the generic `lint.MIN_WORDS..MAX_WORDS` (40–180)
  that `lint.check` applies at a day key today. No em slot names them;
  tightening is the owner's call (§2, item 5), not this file's guess.
- `linkedin_intro` / `linkedin_followup` → the note char bounds
  `lint.check_linkedin` applies (40–300).

`BODY_3` (the retired breakup text in `stage_s7_copy`) is no longer rendered
by any path and has no slot; it is listed here for completeness and bound to
nothing.

"Flat" means the count does not move across the 7 families; ranges move
because the angle phrase is inside the body.

### 1.2 What was missing before B4

**No door applied a body word count to a TEMPLATE.** `lint.check` bounds the
words stored on a *record* under a step key; `stage_s7_copy.render` checks
subjects and unresolved placeholders only; and the six step-3/4/5 templates
are bound to no cadence step at all — they are rendered straight out of
`cadence.TEMPLATES` by `stage_s7_copy._steps_three_four_and_five`. That is how
four over-ceiling bodies (§2) sat in the tree with a green suite. This is the
same shape as the six controls THE-CATALOGUE.md records as unable to fail.

### 1.3 The guard — `tests/test_every_template_is_inside_the_word_contract.py`

Commit `bd4de5abe`. Built so it cannot become the seventh:

- **Coverage is structural, both directions.** The universe is
  `cadence.TEMPLATES` itself; `TEMPLATE_BINDINGS` must name every entry and
  nothing else, *in both directions*. A template added with no binding is a
  hard failure naming it (the way phantom sinks abort `tier_from_sinks.py`);
  a binding whose template was deleted fails too.
- **Both bounds, always, from the authority.** Floor and ceiling together,
  read from `skills.cold_email_writing.WORD_CONTRACT` and `lint`'s own
  constants — never retyped in the test.
- **The render space is the client's own.** Personas from the template names,
  angle families from the client config at import: a new family is rendered
  the day it is declared, and a persona whose angles vanish is a REFUSED
  failure, never a silent skip. Every bounds test asserts it walked renders —
  a vacuous pass is impossible.
- **The proof is in the file.** `test_a_planted_uncovered_template_is_named`
  plants a probe template in the real universe and demands the guard name it
  (try/finally restore); `test_a_binding_for_an_absent_template_is_named`
  does the opposite direction. The same function that returns `[]` when green
  returns the probe's name when planted, so a pass proves the guard ran.

### 1.4 The mutation proof

Three layers, none left behind as a planted mutation (CLAUDE.md rule):

1. **In-file probe** — the planted-uncovered-template test above, permanent.
2. **In-file reverse probe** — the absent-template test, permanent.
3. **Source-level demonstration** — `zzz_planted_by_mutation_proof` planted in
   `cadence.TEMPLATES` at src/cadence.py:357, guard run → RED with two
   failures naming it; removed; `git diff` verified empty; guard green again.
   Nothing was staged or committed while planted.

### 1.5 Steady state

Five test classes green; **two red by design** —
`TestTheSixStep345Templates.test_every_render_is_inside_both_bounds` (10
failure lines) and `TestThe489Copy.test_the_live_campaign_copy_is_inside_em1_and_em2`
(7 failure lines, em1 only) — until the owner rewrites the four bodies in §2.
The guard's own docstring says it: **DO NOT WIDEN A BOUND TO MAKE THESE PASS.**

---

## 2. For the owner — over-ceiling bodies to rewrite

Rendered counts, all 7 families, `lint.countable_words`. Per the lane rules
these are yours to rewrite; the guard stays red until then.

1. `angle_shift_champion` — 129 words, em4 ceiling 90, **over by 39** (every
   champion family).
2. `angle_shift_economic_buyer` — 126–131 words, em4 ceiling 90, **over by
   36–41** (family-dependent).
3. `rung3_economic_buyer` — 105 words, em3 ceiling 90, **over by 15** (every
   family).
4. **489 `BODY_1` — the live campaign copy — 100–107 words rendered, em1
   ceiling 90, over by 10–17.** New finding, not in the briefing: the raw
   template reads 92 only because the unrendered `{ANGLE}` placeholder
   undercounts; substituted the way `stage_s7_copy.render` substitutes it,
   the body crosses the ceiling in all 7 families. This is the copy campaign
   489 would resume with.
5. Owner's call, no action demanded: `persona_pain` (95–102) and `breakup`
   (75–82) sit inside the generic 40–180 but far above any em floor pattern;
   if they should carry an em slot, say which and the guard inherits it via
   `TEMPLATE_BINDINGS`.

---

## 3. Discrepancies against the briefing numbers

- The briefing said `comparable_proof_short` = 42 words. **Measured: 59**
   (flat, 7/7 renders) — in bounds for em2 either way. The 42 does not
   reproduce.
- The briefing's other figures (127 / 122–127 / 104) differ from mine (129 /
   126–131 / 105) by render values, not verdicts; mine are the full-family
   walk through the client's own declared angles.
- `_email_templates()`, named in the briefing, **does not exist in this tree**.

---

## 4. Duplication — lane A delivered a parallel B4 guard

Lane A's queue doc (their branch `task-glm-review-2026-10-14`, unmerged) ships
`tests/test_no_template_escapes_the_word_contract.py`. Same mandate, different
design choices — the operator picks or merges:

| | lane A's guard | this lane's guard |
|---|---|---|
| coverage universe | derived by walking `cadence.STEPS` + cadencelibrary UPPER lists | `cadence.TEMPLATES` ↔ `TEMPLATE_BINDINGS`, set-diff both directions |
| day-keyed templates | generic 40–180 | `persona_pain`/`breakup` generic 40–180; **`comparable_proof*` bound to em2** (floor 45 — matches the briefing's own floor claim) |
| 489 hard copy (`BODY_1`/`BODY_2`) | not covered | **covered** (this is where BODY_1's over-ceiling was found) |
| over-ceiling bodies | under `expectedFailure` with a ledger-flip demo (rewrite lands → UNEXPECTED SUCCESS forces marker removal) | honest RED with the rewrite list in the failure messages |
| measured violators | 104 / 127 / 124–129, comparable_proof_short 58 | 105 / 129 / 126–131, comparable_proof_short 59 |

Differences trace to stand-in render values, not method; verdicts agree
except that theirs leaves BODY_1 invisible and comparable_proof* floored at
40 rather than 45. Both guards agree on the three over-ceiling s6/s7
templates.

## 5. B3 — reassigned

Reassigned to lane A per the updated briefing; their diagnosis is closed. My
earlier read-only measurements (`work/b3_measure.py`, gitignored)
independently corroborate the "template renders fine" half. Nothing further
from this lane.

---

## 6. The reverse-test matrix — 45 controls, one question each

Lane A built this against Tier 1 = 20 / Tier 2 = 10 and marked it PARTIAL.
The corrected inventory (`control-inventory-2026-10-14/TIER-1-2.json`, after
the phantom-sink fix) is **Tier 1 = 36, Tier 2 = 9 — 45 rows**, all walked
here. Per the brief, no missing tests were written; this is the map.

### 6.1 Method

For every one of the 45 controls: (a) read the function and its exact span;
(b) find every test that names it and judge whether the test asserts the
control's refusal/effect *as an outcome* — call-only and self-referential
shapes are called out; (c) hunt mutation evidence — an entry in
`tools/mutation_audit.py` counts **only if its guard text lies inside the
control's span** (same module is not enough; `push.run`'s entry does not
demonstrate `push.main`), and docs-recorded planted mutations count too;
(d) verdict. Static archaeology only — the only mutation planted this session
was the B4 guard's own proof (§1.4).

**DEMONSTRATED** = a mutation of this control's span was actually run and a
named test went red. **UNPROVEN** = a test asserts the refusal outcome, but
no mutation was ever demonstrated. **NEVER** = nothing goes red if the
control is deleted.

### 6.2 Headline counts

| verdict | rows |
|---|---|
| DEMONSTRATED | **9** |
| UNPROVEN | **31** |
| NEVER | **5** |

Two corrections to the inventory's `test_asserts_it_fires` proxy column,
both directions:

- **The proxy understates.** `apply_reply`, `providerwrites.perform` and
  `run.main` were marked "control only" (no test names it) but have genuine
  outcome tests — `apply_reply` is even DEMONSTRATED. `_find_or_create` and
  `_copylint_report`, marked NEVER, are covered stage-driven (UNPROVEN).
- **The proxy overstates.** `heyreachfactory.stage` and
  `leadstop.stop_linkedin_contact` were marked "names both" but no test
  asserts their refusals — both are NEVER.

The proxy is a name-grep; it measures naming, not coverage. Row-level truth
required reading the tests.

### 6.3 The matrix

| # | control | where | the test(s) that name it | mutation demonstrated | verdict |
|---|---|---|---|---|---|
| 1 | `apply_reply` | src/accountpolicy.py:604 | test_stop_buttons.py:108, :121; test_reply_transitions.py:66+ | audit entries at :639/:651 (in span) → tests.test_stop_buttons | **DEMONSTRATED** |
| 2 | `stage` | src/bisonfactory.py:76 | test_the_copy_lint_refuses_the_real_send_path.py:194+; test_a_dry_run_runs_the_sequence_gate.py:182; test_staging_a_campaign_twice_builds_one.py:552 | none | UNPROVEN |
| 3 | `_copylint_report` | src/bisonfactory.py:645 | none by name; report keys via stage (…real_send_path.py:201, :301) | none | UNPROVEN |
| 4 | `_refuse_copylint` | src/bisonfactory.py:662 | …real_send_path.py:217, :226, :235, :247, :281, :287, :311; test_a_dry_run…:261 | none | UNPROVEN |
| 5 | `_refuse_missing_cta` | src/bisonfactory.py:807 | test_the_offer_cta_link_reaches_the_prospect.py:203, :229, :367, :390 | none (in-test dependency break at :203 is the closest) | UNPROVEN |
| 6 | `_find_or_create` | src/bisonfactory.py:1680 | test_two_campaigns_do_not_collide_at_the_provider.py:201, :215, :224, :400, :408; test_crash_restart_idempotency.py:159 | none on master; **lane A's unmerged branch has M1–M4** | UNPROVEN (DEMONSTRATED on lane A's branch) |
| 7 | `_ensure_sequence` | src/bisonfactory.py:1912 | test_bison_campaign_write.py:309, :339; test_crash_restart_idempotency.py:197 | none | UNPROVEN |
| 8 | `_variables_for` | src/bisonfactory.py:2049 | test_threaded_sequence.py:275+; test_the_offer_cta…:108+; test_compare_bison.py:155 | none | UNPROVEN |
| 9 | `_ensure_leads` | src/bisonfactory.py:2308 | test_lead_writes_respect_the_killswitch.py:72, :87, :100; test_an_approval_certifies_the_words_that_ship.py:349; test_task400_rework2.py:530 | none — and the TASK-566 pair (:205, :212) is source-text only | UNPROVEN |
| 10 | `_refuse_unvariabled_leads` | src/bisonfactory.py:2589 | **NONE — zero hits on name, refusal text, or report key** | none | **NEVER** |
| 11 | `record_event` | src/cadence.py:1169 | test_cadence.py:271, :283, :303; test_reply_transitions.py:330 | none in span (all 9 cadence entries elsewhere); one historical accidental regression caught by the suite (CONTEXT-RESET-2026-09-15-D.md) | UNPROVEN |
| 12 | `_expected_lead_variables` | src/configdiff.py:553 | test_the_cadence_lands_in_every_file.py:279; test_no_activation_without_an_exact_match.py:672 | none | UNPROVEN |
| 13 | `approved_bison` | src/configdiff.py:636 | …exact_match.py:722, :919; test_compare_bison.py:296+ | none | UNPROVEN |
| 14 | `compare_bison` | src/configdiff.py:1099 | test_compare_bison.py:283, :351, :378, :409; …exact_match.py:640 | none in span — its tests mutate the fake provider's *data*, never the comparator | UNPROVEN |
| 15 | `check_batch` | src/copylint.py:1506 | dozens — test_copylint.py; test_task904_opt_out.py:90; more | docs: `subject_list[:-1]` removed at copylint.py:1604 (in span) → test_only_the_last_subject_may_claim_finality; whole-function stub → 2 more modules | **DEMONSTRATED** |
| 16 | `_generate_via_campaign` | src/generate.py:2798 | test_task400_rework2.py:882, :907, :778+; test_only_the_selected_offer_is_validated.py:342 | TASK-400 mutation C (:2826-2837); record = task mandate + catching test's docstring | **DEMONSTRATED** (thinnest of the nine) |
| 17 | `generate` | src/generate_campaign.py:254 | …selected_offer…:233, :327, :355, :364, :377 | none in span (TASK-427's target is `_check_offers`, outside) | UNPROVEN |
| 18 | `_process_contact` | src/generate_campaign.py:740 | test_task400_rework3.py:171, :248, :258; test_the_research_pack_has_one_shape.py:353, :372 | TASK-400-REWORK3-MUTATIONS.md M2 (:1238-1247), M3 (:1249-1263), recorded FAILED for the intended reason | **DEMONSTRATED** |
| 19 | `stage` | src/heyreachfactory.py:505 | test_one_plan_decides_both_providers.py:509 (call-only); test_heyreachfactory.py:376-380 admits the refusal test "is NOT written" | none | **NEVER** |
| 20 | `ensure_leads` | src/heyreachfactory.py:1135 | test_heyreachfactory_ensure_leads.py:400, :424, :445, :471, :507, :910+; test_sending_live_off_blocks_only_our_new_writes.py:94 | none | UNPROVEN |
| 21 | `handle` | src/inbound.py:365 | test_an_out_of_office_pauses_the_company.py:82, :121, :224, :379; test_a_reply_stops_a_person_on_every_record.py:111+; test_task238_attribution.py:128 | none (zero inbound entries in the harness) | UNPROVEN |
| 22 | `ingest` | src/inbound.py:528 | test_a_reply_and_its_stop_are_saved_together.py:117, :135 | none; the adapter `ValueError` (:531-533) untested | UNPROVEN |
| 23 | `stop_contact` | src/leadstop.py:39 | test_one_person_can_be_stopped_without_stopping_the_rest.py:128, :140, :152 | none | UNPROVEN |
| 24 | `stop_linkedin_contact` | src/leadstop.py:137 | **NONE** — zero `assertRaises(StopRefused)`; test_the_linkedin_stop…:174 is fronted by `perform`'s ownership guard | none | **NEVER** |
| 25 | `stage_lead` | src/liststaging.py:249 | test_list_staging.py:338-429; test_list_staging_permission.py:268-439; test_list_staging_rehearsal.py:188, :227 | none (one recorded regression catch, liststaging.py:293-296) | UNPROVEN |
| 26 | `pause` | src/orchestrator.py:534 | test_orchestration.py:196; test_the_stop_can_be_performed.py:576; test_an_emergency_stop…:88, :117 | none | UNPROVEN |
| 27 | `_perform_pause` | src/orchestrator.py:595 | test_an_emergency_stop_is_not_refused_by_its_own_history.py:88-157 | none | UNPROVEN |
| 28 | `resume` | src/orchestrator.py:616 | test_orchestration.py:171, :183 | none in span (the audit entry hits the api call site) | UNPROVEN |
| 29 | `_resume_at_providers` | src/orchestrator.py:648 | test_a_resume_leaves_a_ledger_row.py:233+; test_a_resume_revalidates_suppression_first.py:267, :293 | none | UNPROVEN |
| 30 | `perform` | src/providerwrites.py:2358 | test_an_internal_campaign_is_never_touched.py:350, :415, :542, :594, :621; test_the_write_layer_is_sealed.py:162+; test_the_stop_can_be_performed.py:222, :381; test_task235…:199 | none in the harness; but an inline mutation-style test (verb removed from SUPPORTED, test_task235:199) and a deliberate negative control (:594) | UNPROVEN — the best-covered control in the estate |
| 31 | `main` | src/push.py:542 | **NONE — no test invokes `push.main` at all** | none (the "push: enable the sender" entry is `push.run:495`) | **NEVER** |
| 32 | `simulate` | src/replaysim.py:109 | test_replaysim.py:74, :101, :159 | audit entry at replaysim.py:170 (in span) → tests.test_replaysim; :101 discriminates | **DEMONSTRATED** |
| 33 | `main` | src/run.py:527 | test_run.py:92; test_a_spend_needs_a_ceiling.py:87; test_generate.py:733 | none (zero run.py entries in the harness) | UNPROVEN |
| 34 | `stage_push` | src/run.py:359 | **NONE** — masked from above by `run.run`:386-388 and below by `push.LiveSendNotEnabled` | none | **NEVER** |
| 35 | `pause_campaign` | src/web/api.py:3149 | test_web_pause_replies.py:56, :63 | none | UNPROVEN |
| 36 | `resume_campaign` | src/web/api.py:3205 | test_web_pause_replies.py:84, :101 | audit entry at api.py:3223-3224 (in span) → tests.test_web_pause_replies | **DEMONSTRATED** |
| 37 | `run` | src/enrich.py:1355 | test_enrich_batch.py:72-137 | audit ×2 (:3452, :3458) → tests.test_enrich_batch | **DEMONSTRATED** |
| 38 | `enrich_record` | src/enrich.py:843 | test_enrich.py:455-487; test_icp_spend_gate.py:53-138 | audit entry at :1268 (MX screen) → tests.test_enrich | **DEMONSTRATED** |
| 39 | `spend` | src/enrich.py:865 | test_waterfall.py:230-243; test_a_cap_that_survives_the_run.py:179 | audit entry at :957-958 (waterfall ledger) → tests.test_waterfall | **DEMONSTRATED** |
| 40 | `complete` | src/providers/glm.py:220 | test_model_spend_counts_against_the_client.py:196, :100, :138, :633; test_a_model_call_writes_a_priced_ledger_row.py:59; test_glm_adapter.py:163+ | none (zero glm.py entries) | UNPROVEN |
| 41 | `run_actor` | src/researchpack/pack.py:102 | test_a_provider_ceiling_refuses_before_the_call.py:1124, :1139, :1154, :1184; test_researchpack.py:219 | none | UNPROVEN |
| 42 | `build` | src/researchpack/pack.py:197 | test_researchpack.py:138-209, :231, :237 | none | UNPROVEN |
| 43 | `stage_enrich` | src/run.py:117 | test_cap_is_not_a_verdict.py:97, :103; test_run_flags.py:326; test_scale_import.py:873 | none | UNPROVEN |
| 44 | `settle` | src/spendledger.py:748 | test_a_provider_ceiling_refuses…:722, :940, :520-637; test_ledger_does_not_sum_across_units.py:93 | none; exactly-once `RuntimeError` (:756-757) untested; the unmerged fix (task-spendledger-day `21ba5fab5`) is invisible from this tree | UNPROVEN |
| 45 | `verify` | src/verification.py:652 | test_a_provider_ceiling…:1029-1046; test_a_stopped_run_is_not_a_finished_one.py:37; test_contactout_first.py:203 | none in span — all five verification entries sit one hop outside (`DEFAULT_POLICY`, `_verdict`, `confirmations`, `is_sendable`) | UNPROVEN |

### 6.4 The five NEVERs

1. **`bisonfactory._refuse_unvariabled_leads`** (src/bisonfactory.py:2589) —
   the structural half of the 2026-09-23 blank-emails incident fix (set
   variables, read back, *then* attach). No test names it, its refusal text
   appears nowhere in tests/, and both FakeBison implementations merge
   variable patches too faithfully for it to ever fire. It could be deleted
   tomorrow with a green suite.
2. **`heyreachfactory.stage`** (src/heyreachfactory.py:505) — the comment at
   tests/test_heyreachfactory.py:376-380 says the refusal test "belongs here
   and is NOT written"; the only caller-test asserts projections.
3. **`leadstop.stop_linkedin_contact`** (src/leadstop.py:137) — zero
   `assertRaises(StopRefused)` anywhere; its one generic "still refuses"
   test is fronted by `perform`'s ownership guard, so deleting the control's
   own URL guard leaves it green.
4. **`push.main`** (src/push.py:542) — no test invokes it; worse, its
   `--live` handler prints "REFUSED" and returns 2 *without ever passing
   `live=True` down*, so the print is the entire guard.
5. **`run.stage_push`** (src/run.py:359) — its `if live: raise` is
   unreachable through its only caller (`run.run` refuses live at :386-388
   first) and has no direct test. Defence-in-depth in exactly the
   configuration in which a guard rots.

### 6.5 Sub-guards never exercised inside UNPROVEN controls

- `inbound.ingest`'s unknown-adapter `ValueError` (src/inbound.py:531-533).
- `spendledger.settle`'s exactly-once `RuntimeError` (:756-757) — nothing
  tests a double settle.
- `generate_campaign.generate`'s empty-contacts guard (:294-297, masked from
  above by `_generate_via_campaign`'s own refusal) and its `ConfigError`
  wrapper (:300-307).
- `enrich.run`'s prefetch-bridge refusal — covered only by a source-text
  test (see 6.6).

### 6.6 Fake demonstrations and weak shapes found

The brief asked for more of lane A's `test_no_write:965-975` shape. Found:

1. **`tests/test_task904_opt_out.py:178-207` (`TestMutationCheck`) and :69-76**
   — claims to "prove the check is load-bearing" by asserting the test's own
   raw fixture string contains zero opt-out lines. No code is mutated,
   nothing can go red; it stays green with the guard deleted. (The genuinely
   load-bearing sibling is `test_body_with_existing_opt_out_is_duplicate`
   at :90.)
2. **Source-text assertions** — `tests/test_task566_campaign_scoped_authority.py:202-218`
   (`inspect.getsource` + `assertIn` on `_ensure_leads`) and
   `tests/test_prefetch_headcount.py:640-653` (`inspect.getsource(enrich.run)`
   contains the bridge-refusal string). Both go red on deletion but stay
   green when a guard is behaviorally neutered while its text remains — the
   exact anti-pattern this repo's own rules name ("a test that fails when
   somebody writes a comment"). `tests/base.py:550-554` overstates the
   TASK-566 pair as proving an unauthorized `_ensure_leads` still refuses.
3. **`tests/test_heyreachfactory.py:357`** — effectively self-referential:
   asserts Python's own `int()` raising on a dict the test itself wrote,
   while the real refusal test is admitted unwritten at :376-380.
4. **Confirmed, outside the 45**: `tests/test_no_write_happens_without_every_gate.py:965-975`
   (lane A's find — the spy is the test's own stand-in; concerns the
   actionledger layer).
5. **Docstring-advertised coverage that isn't**: `test_a_dead_cta_link_is_refused.py`
   names `_refuse_copylint` as "the production path" but only drives
   `copylint.check_batch`; it would stay green if the wiring were cut
   (harmless only because `test_the_copy_lint_refuses_the_real_send_path.py`
   genuinely drives `stage`).

### 6.7 The mutation harness itself needs maintenance

- **Zero entries** for whole control-bearing modules: bisonfactory,
  heyreachfactory, leadstop, liststaging, providerwrites, inbound,
  configdiff, copylint, providers/glm, researchpack/pack, spendledger, run.
  Every DEMONSTRATED verdict outside `enrich.py`/`accountpolicy.py`/
  `replaysim.py`/`web-api-resume` rests on docs records or task mandates.
- **Stale anchors**: "generate: read the stored flag instead of the
  resolver" no longer matches src/generate.py:884 (source now passes
  `lint.policy_for_record(rec)`) — the harness would report "did not apply".
  "accountpolicy: activate a referred contact nobody authorised" is in-span
  but its named catcher no longer discriminates it on today's tree.
- Lane A's §8 note ("the audit corroborates most UNPROVEN rows would be
  caught — corroboration, not in-suite proof") is consistent with these
  findings at row level; their category labels were right more often than
  the inventory's per-row proxy.

### 6.8 What waits on the operator

1. The five NEVERs — decide what gets written and by whom (the brief
   reserves that decision). `_refuse_unvariabled_leads` is the one I would
   not leave: it is the incident fix.
2. The 31 UNPROVENs: the highest-leverage first mutations are the ones whose
   tests already assert outcomes — one audit entry each for
   `providerwrites.perform`, `heyreachfactory.ensure_leads`,
   `verification.verify` would convert the three most safety-critical rows.
3. The fake/weak tests in 6.6 — the `TestMutationCheck` shape should be
   deleted or rewritten before it teaches a reader that green means proven.
4. The harness's stale anchors and empty modules (6.7) — an audit entry that
   silently does not apply is a miss that reports a pass.
