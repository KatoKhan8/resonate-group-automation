# VERIFY — TASK-400's copylint finding, independently reproduced

**Reviewed branch head SHA: `848a08322cd98206522f9b3c167d0fc79ed6ad50`**
(branch `task400-rework3`, `git fetch origin` then `git worktree add --detach`
of that exact commit; `git rev-parse origin/task400-rework3` = the same SHA).

**Branch base: `5c356b7d`** — `git merge-base --is-ancestor 5c356b7d origin/master`
exits **1**, so the base is NOT an ancestor of master and master is the wrong
tree for this claim. Both trees were checked out separately and both were
measured. Current `origin/master` at review time: `aaec85b3`.

Reviewer: Claude subagent, independent verification, 2026-09-28. Read-only with
respect to production code: two mutations were applied inside the isolated
`848a0832` worktree and restored byte-identically (proof at the end).
Provider writes: **0**. No real provider and no real model was called;
`urllib.request.urlopen` was booby-trapped in every driver script and
`copylint.CTA_LINK_SKIP_REASON` was set, so a network call would have raised.

---

## THE CLAIM UNDER REVIEW

> Copylint retry — `copylint.check_batch` was computed, stored on the result and
> read by nothing. Measured: **every lead the pipeline has ever produced was in
> fact refused**, for `empty_sentence`, because `em2`/`em4` were given an empty
> subject and the blank line that left is "a variable rendered to nothing".

## VERDICT: **UPHELD IN NARROWER FORM**

Two of the three assertions hold and are reproducible. The third — the absolute
"every lead the pipeline has ever produced" — is **overstated and, read as a
statement about leads that actually shipped, false**. The precise true statement
is at the end of assertion 3.

| # | assertion | verdict |
|---|-----------|---------|
| 1 | `check_batch`'s result was read by nothing | **UPHELD for the call site**, false for the function |
| 2 | `em2`/`em4` got an empty subject and it produces `empty_sentence` | **UPHELD**, reproduced through the real entrypoint |
| 3 | EVERY lead the pipeline has ever produced was refused | **REFUTED as stated** → narrower statement below |

---

## ASSERTION 1 — was the verdict read by nothing?

### The call graph, both trees

`copylint.check_batch` has exactly **two** production call sites, identical on
the base and on the branch head:

    src/generate_campaign.py:438 (base) / :521 (head)   result["copylint"] = check_batch([lead_for_lint])
    src/bisonfactory.py:624       (both)                found = check_batch(leads, packs, steps_expected=expected)

(`src/copylint.py:4` and `src/packfacts.py:5` are docstring examples, not calls.)

**Call site A — `generate_campaign`, at the base `5c356b7d`: ZERO production
consumers. DISCONNECTED.** `git grep` for every read of the field across
`src scripts tools hosts prototype` at `5c356b7d` returns only the write:

    5c356b7d:src/generate_campaign.py:438:  result["copylint"] = copylint.check_batch([lead_for_lint])

and no reader. The two functions that receive the plan both ignore it:
`generate._plan_to_ops` (base `src/generate.py:1965`) reads only
`generation_stamp` and `sequences`; `generate._adapt_plan_to_cadence`
(base `src/generate.py:2070`) reads only `contact_key`, `held`, `qualification`,
`sequences` and `subjects`.

Not proved by grep alone. **Driven at the base tree**: a contact result carrying
the loudest possible verdict —

    "copylint": {"refused": True,
                 "offenders": {"empty_sentence": [ck], "buzzword": [ck], "dash": [ck]}}

— was handed to the base's own `_adapt_plan_to_cadence`, the store door and the
last place a refusal could be honoured before copy becomes canonical state:

    contact result carried copylint refused=True
    steps the store door wrote  : [('rowan-blake', 'em1'), ('rowan-blake', 'em2'), ('rowan-blake', 'em3')]
    cadence now holds           : ['em1', 'em2', 'em3']

The refusal changed nothing. **This is the DISCONNECTED defect as OPERATING-MODE
defines it (zero production callers / nothing downstream reads it), on the copy
path.**

**Call site B — `bisonfactory`: it DOES have a live, behaviour-changing
consumer**, so the claim's unqualified wording is wrong about the function.
`_copylint_report` → `_refuse_copylint` (`src/bisonfactory.py:630`) raises
`FactoryRefused` on `refused`, before the first provider call. Two limits on
that consumer, both worth naming because they narrow how much cover it gives:

* **It runs only on `live=True`.** `stage()` at `src/bisonfactory.py:75-78`
  computes `report["copylint"] = _copylint_report(plan, recs)` and **returns**
  (`src/bisonfactory.py:75-78` at `848a0832`)
  when `live` is false — the verdict is reported and refuses nothing. This is the
  "a dry run does not run the sequence gate" item already open in OPERATING-MODE,
  and it applies to copylint too.
* **HeyReach has no copylint gate at all.** `check_batch` appears nowhere in
  `src/heyreachfactory.py` on either tree.
* **It never sees a subject.** `_copylint_batch` builds
  `"steps": [{"body": step.get("body")}]` with no `subject` key, deliberately
  (its docstring explains why). So the empty-subject defect of assertion 2 could
  not have been caught on the staging path even when that path ran.

### At the branch head the verdict IS consumed — proved by mutation

`src/generate_campaign.py:538` `failures = copylint_failures(result["copylint"],
contact_key)`, then `:543 if not failures: break`, `:545 rejected.append(...)`,
and on exhaustion `:551 result["held"] = "no draft passed lint in %d attempts"`
with `result["sequences"] = {}`.

**MUTATION 1 (the implementer's, reproduced independently).**
`copylint_failures` made to `return []` — byte-level edit, CRLF preserved,
md5 `aaa0a4f5…` → `fe69cf2a…`, file asserted changed before anything was run.

    py -3 -m unittest tests.test_task400_rework3        Ran 19 tests, FAILED (failures=3)

    FAIL test_a_draft_copylint_refuses_is_regenerated_and_never_stored
         AssertionError: 1 != 2 : the writer was not asked again, so a draft
         copylint refused went straight through
    FAIL test_a_set_that_never_passes_leaves_no_row_anywhere
    FAIL test_the_budget_is_bounded_rather_than_a_loop

That is the intended test, failing for the intended reason, with the exact
message `docs/TASK-400-REWORK3-MUTATIONS.md` records. **Did a different guard
fire first? No** — `test_the_isolation_holds_before_anything_else_is_claimed`
PASSED under the mutation (it asserts `lint.check` returns `[]` for the same body
while `copylint.check_batch` refuses it), so the only gate that can cause the
regeneration is the batch lint; and `test_the_rule_was_not_widened_to_let_it_through`
passed, so the rule itself is untouched. The two collateral failures drive the
same buzzword fixture, which the implementer's record also predicts.

Unmutated, at `848a0832`: `tests.test_task400_rework3` 19/19 OK and
`tests.test_generate` 51/51 OK — the "51 tests, 0 failures, 0 errors" the
implementer reports is correct.

### Assertion 1 verdict

**UPHELD for the call site the claim is about** — `generate_campaign`'s
`result["copylint"]` had zero production consumers at `5c356b7d` and the branch
head makes it decide something. **The sentence is too broad as written**:
`copylint.check_batch` itself is consumed by `bisonfactory._refuse_copylint`,
which does refuse a real push — on `live=True`, on EmailBison only, and without
ever looking at a subject.

---

## ASSERTION 2 — the empty subject, and `empty_sentence`

### Where the empty subject comes from

`src/generate_campaign.py` at the base `5c356b7d`, lines **424 and 427**, inside
the `lead_for_lint` the module hands its own lint:

    {"subject": result["subjects"].get("A", ""), "body": ...em1},
    {"subject": "", "body": ...em2},          <-- line 424
    {"subject": result["subjects"].get("B", ""), "body": ...em3},
    {"subject": "", "body": ...em4},          <-- line 427
    {"subject": result["subjects"].get("C", ""), "body": ...em5},

The writer returns three subjects for five steps (A/B/C for em1/em3/em5) because
em2 and em4 are same-thread replies. The two literals are the empty subject.
Head `848a0832:500` replaces them with `em2 <- A`, `em4 <- B`.

### The mechanism, named exactly

`copylint.check_batch` builds
`rendered = whole + "\n" + subjects + "\n" + extra`, where
`subjects = "\n".join(_subject(s) for s in steps)`. With steps 2 and 4 empty that
is `A\n\nB\n\nC` — a blank line at each junction. The rule that fires is
`empty_sentence`, and the specific pattern is
**`EMPTY_SENTENCE_RES[1] = [A-Za-z]\s{2,}[a-z]`** ("thing  does"):

    EMPTY_SENTENCE_RES[0] (?:^|\n)\s*[.!?]\s*(?:$|\n)  -> None
    EMPTY_SENTENCE_RES[1] [A-Za-z]\s{2,}[a-z]          -> 'd\n\nt'
       context: 'answer to that.\nthe question we never answered\n\nthe developer we'
    EMPTY_SENTENCE_RES[2] \s+[.!?](?:\s|$)             -> None
    EMPTY_SENTENCE_RES[3] ,\s*[.!?]                    -> None

So the claim's paraphrase ("the blank line that left is a variable rendered to
nothing") is the right rule for the right reason, and the precise trigger is the
*letter → blank line → lowercase letter* junction the empty subject creates.

**It is conditional on the following subject starting lowercase.** Varying only
the capitalisation of the same three subjects, everything else held constant:

    all lowercase subjects              refused=True   fired=['empty_sentence', 'step1_without_pack_fact']
    all Capitalised subjects            refused=False  fired=['step1_without_pack_fact']
    Capitalised, A ends with '?'        refused=False  fired=['step1_without_pack_fact']
    Capitalised, ends with a digit      refused=False  fired=['step1_without_pack_fact']

(`step1_without_pack_fact` is in `copylint.WARNING_RULES` and does not refuse.)

**That condition is not luck — the writer prompt mandates it.**
`src/copystages.py:322`, the SUBJECTS section of `WRITER_SYSTEM`: *"Four to seven
words, **lowercase** except real proper nouns, a NOUN PHRASE about …"*. Measured
on the real store: **3,861 of 4,060 stored email subjects start with a lowercase
letter.** So the refusal is a systematic consequence of the prompt contract, not
an accident of one sample.

### Reproduced through the real production entrypoint

`generate.run(model=CampaignModel(...), live=True, ids=["harbourline"])` — the
real entrypoint, the suite's canonical CLEAN copy, a scripted model, no provider.

Unmutated head (`848a0832`):

    writer calls 1 · state drafted · stored steps ['day1','day15'] · held None

**MUTATION 2**: lines 500-506's `_subj` reverted for em2/em4 to `""` — exactly
the base's two literals. Byte-level, CRLF preserved, md5 `aaa0a4f5…` →
`facb9884…`, file asserted changed. Same run, same clean copy:

    writer calls 3 · state verified · stored steps [] · email_steps walked []
    log: "Rowan: no draft passed lint, nothing stored (no draft passed lint in 3
          attempts: a sentence rendered to nothing: a bare full stop, or a gap
          where a variable should have been…"

That is `empty_sentence`'s own rule text, on a draft with nothing else wrong with
it. Capturing the plan the pipeline actually produced under the same mutation
plus MUTATION 1 (so the verdict is ignored, i.e. base behaviour end to end):

    contact rowan-blake
      lint refused    : True
      hard offenders  : ['empty_sentence']        <- the ONLY one
      held            : None
      gate_attempts   : 1
    STORED step keys  : ['day1', 'day15']
    STORED state      : drafted

**Both halves of the finding, simultaneously, through the real entrypoint: the
lint refuses for `empty_sentence` alone, and the refused copy is stored anyway.**

### Assertion 2 verdict

**UPHELD.** Directly demonstrable and demonstrated, with the exact regex, the
exact source lines, and the exact condition (`lowercase` next subject) that the
writer prompt guarantees.

---

## ASSERTION 3 — "EVERY lead the pipeline has ever produced"

### Method

`work/queue.jsonl` is gitignored runtime state and is present on this machine. It
was **copied** to a scratch directory and every measurement ran against the copy
with `QUEUE` pointed at it. Production store md5, before and after all work:

    before  3c487bd73cf6b6c72b1a5bad8d7d1dcf  work/queue.jsonl
            7825b9aee14fee6bfd4667003e7d55e0  work/campaigns.jsonl
    after   3c487bd73cf6b6c72b1a5bad8d7d1dcf  work/queue.jsonl
            7825b9aee14fee6bfd4667003e7d55e0  work/campaigns.jsonl

Byte-identical. Nothing was written to the production store.

### What produced the estate's copy — and it was not this call site

**`generate_campaign` has never had a production caller on master.** On
`origin/master` the string `generate_campaign` appears in exactly one place in
the whole repository, a comment at `src/sequenceplan.py:207`. `git grep` over
`work/`, `scripts/` and `tools/` finds no caller either. The three commits that
introduce `_generate_via_campaign` into `src/generate.py` — `58d75916`,
`6a115023`, `8cd963bf` — are each **not** an ancestor of `origin/master`
(`git merge-base --is-ancestor` exits 1 for all three). The wiring exists only on
the unmerged rework branches, of which this one is the third.

The leads that exist were produced by two other things:

1. **`work/v2_run.py`** — the earlier production entrypoint. It calls
   `copylint.check_batch` itself (line 212) and stores the report as
   `rec["lint"]`, which nothing reads either; its own lint shape gives a subject
   **only to em1** (line 207: `"subject": w.get("subject") if k == "em1" else ""`).
2. **`src/generate.py`'s `draft()` path** — the old per-step path, which produced
   the 1,081 records in the store that carry rendered email copy.

### Measurement 1 — the real 09-25 production run, `work/v2-data.json`

10 leads, 7 with written copy, 7 carrying a stored lint report. **The stored
reports say `empty_sentence: 0` for all 7**; 2 were refused, both for
`unrendered_variable`, 5 passed.

Re-judged today with the branch head's `copylint`, same real writer output, three
lint shapes, nothing else changed:

    shape                                       result
    base_gc  em2/em4 subject ""     (5c356b7d)  refused 7/7 · empty_sentence 7/7 · only-reason 5/7
    head_gc  reply carries thread subject        passed 5 · refused 2 (unrendered_variable)
    v2run    subject on em1 only  (what ran)     passed 5 · refused 2 (unrendered_variable)

    subject A ends with a letter : 6 of 7 True
    subject B starts lowercase   : 7 of 7 True

So under the `generate_campaign` shape **7 of 7 real writer answers are refused
and `empty_sentence` is the only hard rule for 5 of them** — but under the shape
that actually ran, `empty_sentence` fired **zero** times, which the artifact's
own contemporaneous reports independently confirm.

### Measurement 2 — the whole production store

1,582 records; 1,099 with a cadence; **1,081 records / 1,323 contact-level leads
carry rendered email copy**. Judged with the branch head's `copylint`, with
`steps_expected` set to the number of email steps that lead actually has (the
same rule `bisonfactory._copylint_report` uses, so `empty_step` is not counting
the cadence rollout instead of the copy):

    shape        refused   passed   empty_sentence   empty_sentence is the ONLY hard rule
    as_stored      613      710           0                    —
    head_gc        613      710           0                    —
    base_gc      1,305       18       1,287                  692

    hard rules, as_stored / head_gc : untraceable_company_claim 592 ·
                                      finality_before_last_step 15 · dash 11 · buzzword 9
    hard rules, base_gc             : the same, plus empty_sentence 1,287

Two things follow. First, **the branch's fix is verdict-neutral on everything
else**: `head_gc` is identical to `as_stored`, so it removes exactly the
`empty_sentence` mass refusal and changes no other rule. Second, even in the
counterfactual `base_gc` shape it is **1,287 of 1,323, not all of them** — 36
leads do not fire it (their subject junction does not present
letter → gap → lowercase). And none of these 1,323 leads ever went through that
code path, so this row is a counterfactual, not history.

### Assertion 3 verdict

**REFUTED as stated.** "Every lead the pipeline has ever produced was in fact
refused" is not true of any lead that shipped: the call site that refuses them
has never run in production on master, the entrypoint that did run
(`work/v2_run.py`) gave a subject only to em1 and its own stored reports record
`empty_sentence: 0`, and the store's 1,323 rendered leads were written by
`draft()`, which never called `check_batch` at all.

**The precise true statement, which is the useful one:**

> Under the `lead_for_lint` shape `src/generate_campaign.py` builds at `5c356b7d`
> — em2 and em4 given an empty subject — `copylint` refuses for `empty_sentence`
> **7 of 7 real writer answers from the 2026-09-25 production run**
> (`work/v2-data.json`), with `empty_sentence` the sole hard reason for 5 of the 7,
> and **1,287 of the 1,323 rendered leads in `work/queue.jsonl`** if their stored
> copy is put through that shape. Because the verdict had zero consumers, no lead
> was ever actually stopped by it — and because `generate_campaign` has zero
> production callers on master, no lead ever reached that lint on the live path at
> all. The defect would have refused essentially the entire output of the copy
> pipeline **the moment TASK-400 wired the pipeline up**, which is exactly when
> the branch found it.

That reading also removes a contradiction the absolute wording created: if every
lead had really been refused, the 09-23 incident could not have put 77 emails in
front of real prospects. It could, because nothing read the verdict — and it
reached them through a different path from the one this lint call sits on.

---

## WHAT I DID NOT VERIFY

* **The branch's suite attribution** (258 → 192 failing names, 67 fixed, 0 new).
  Out of scope here and **not verified**.
* **The other three operator behaviours** (2, 3, 4) and mutations 3-6 in
  `docs/TASK-400-REWORK3-MUTATIONS.md`. Not verified. Only mutation 1 and the
  subject change were reproduced, because only those bear on this claim.
* **Whether `head_gc`'s subject choice is the right product answer.** It matches
  `EMAILBISON-COPY-REQUIREMENTS.md` ("a sequence is one conversation, same-thread
  follow-ups use the provider's `thread_reply`") and the provider sends
  `Re: <subject>`, so a reply carrying its thread's subject is consistent with the
  standing contract. Whether the provider projection actually renders it that way
  was **not** checked — that is a `TASK-425` question.
* **`untraceable_company_claim` on 592 of 1,323 real leads** (44.7%) is the
  largest refusal cause in the store today, in the `as_stored` shape, after
  TASK-330 tightened `_traces`. Reported as a measurement, not investigated.
  It is a bigger number than anything in this claim.

## BOUNDARIES OBSERVED

Provider writes 0. No real provider or model called; `urlopen` trapped in every
driver. Campaigns 487/489/493 untouched and never read for mutation.
`src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`,
`src/executionguard.py`, `COMPLIANCE.md` and `tests/test_compliance_gate.py` were
read only. Production freeze respected. Nothing merged, nothing pushed to master.

## MUTATION HYGIENE

One file was mutated, `src/generate_campaign.py`, inside the throwaway
`848a0832` worktree only. Edits were made in **binary mode** against exact byte
patterns, so the tree's CRLF endings could not be normalised; each mutation
asserted its pattern occurred exactly once and asserted the file's bytes actually
changed before anything that depended on the change was run.

    original (as checked out)   md5 aaa0a4f59c364eee67adc844634bcfcb  CRLF 634  bare LF 0
    MUTATION empty_subject      md5 facb98845afd8ae19ce14d0b49a494f0  CRLF 634  bare LF 0
    MUTATION disconnect         md5 fe69cf2adec3f704f0a046312bda9b12  CRLF 635  bare LF 0
    after restore               md5 aaa0a4f59c364eee67adc844634bcfcb  CRLF 634  bare LF 0

Restoration checked against the commit itself, not against a memory of it: the
blob `848a0832:src/generate_campaign.py` converted to CRLF hashes to
`aaa0a4f59c364eee67adc844634bcfcb`, the same md5 as the restored working file.
`tests.test_task400_rework3` and `tests.test_generate` were re-run afterwards:
70 tests, OK.
