# Independent re-review: P0-B copy engine, head `142ca537`

**Round 2.** Round 1 reviewed `e4e2a35d` and returned **DO NOT MERGE** with four
blocking defects (`docs/REVIEW-P0B-cdac64f4.md`, branch `review-p0b-cdac64f4`,
`d306bead`). This pass verifies whether those four are closed and hunts for what
round 2 introduced.

    HEAD REVIEWED     142ca537  "Three more ladder refusals the B4 fix
                                 correctly surfaced, and my slice missed"
                                 = origin/task-p0b-copy-engine-pareto
    origin/master     3bc00f2d  (was 9497b11d when this review was commissioned)
    REAL MERGE BASE   d0e95d20  computed, not assumed - the branch is 37+
                                commits behind master and its merge base is
                                NOT the master head named in the brief
    ROUND 1 HEAD      e4e2a35d

### The head moved twice during this review, and it does not matter

The brief named `e1fbd75b`. After a re-fetch `origin` carried `142ca537`, and a
further commit `556593a0` exists **unpushed** in the author's worktree
(`worktree-agent-ad1f958477fbec868`). All three carry the **same `src/` tree**:

    git rev-parse e1fbd75b:src 142ca537:src 556593a0:src
      319e22e57b976309d6eb90a08babced46441c28e   (identical, all three)

`e1fbd75b -> 142ca537` changes one test file only
(`tests/test_the_research_pack_has_one_shape.py`). `142ca537 -> 556593a0`
changes the task doc only. **Every code measurement below therefore holds at all
three SHAs**, and each was re-stamped at `142ca537` after re-pointing. I review
and name `142ca537`, because that is what `origin` carries and what anyone else
can reproduce.

---

## Verdict

# DO NOT MERGE — `142ca537`

**All seven of round 1's exit conditions are met.** B4, B3, B1, B2, F1, the
three unpinned mutations and the P.S. decision are each genuinely closed, and
several are closed better than asked. The work is honest: the author retracted
two of its own claims unprompted, found and disclosed a defect in its own
verification instrument, and its reported numbers reproduce against my
independent re-derivation.

**One new blocking defect, and it is in the fix for B1.** The support check that
round 1 demanded was added — and it licenses a worded quantity when the research
pack contains **any word sharing its first four characters**. `threat` licenses
"three times". `several` licenses "seven times". `trip` licenses "tripled".
`doubt` licenses "double". Measured against the real production corpus:
**134 of the 394 records that carry a research pack (34.0%)** license at least
one fabricated multiplier this way, and **nothing downstream catches it** —
`claims.check`, `copylint.untraceable` and `heyreachfactory.unsupported_claims`
are all blind to an impersonal benchmark, which is the entire reason this gate
was written. It reaches a prospect on LinkedIn.

Round 1's B1 was a gate that **over**-refused: annoying, convergence-hostile,
safe. Round 2's B1 **under**-refuses on a third of the estate. On a safety path
that is the wrong direction, and it is a five-line fix.

**It is one defect, in one expression, and I would re-review this in an hour.**

| | |
|---|---|
| **R1** | `_invented_quantities`' support check is a 4-char PREFIX, not a stem. **BLOCKING** |
| **R2** | `_NOT_A_QUANTITY`'s `half the`/`half of` exempts real magnitude claims. **Non-blocking, same family, fix with R1** |
| B4 | **CLOSED.** Fires on the production path; proved by a mutation that reverts only the B4 comparison |
| B3 | **CLOSED.** Figure gate on all five LinkedIn keys; clean note still passes; observed firing 7 times in the author's own real-model runs |
| B1 | Support check added — **and it introduced R1** |
| B2 / F1 | **CLOSED.** 15 of 15 date/ratio cases correct through the live path |
| M3 / M7 / M8 | **All three die.** Plus six mutations of my own, all killed |
| F3a retraction | **VERIFIED CORRECT.** The P.S. reaches no prospect-facing surface, and no operator-facing one either |
| The three new suite failures | **The guard working, not over-reaching.** Repaired without loss of test power |
| 2 of 5 (40%) | **Reproduced exactly** from the author's own five artifacts. Not a pass, not a regression |

---

## 0. What I attacked

Falsification attempts that **failed** — the branch held:

- the tenant guard still being inert on the dict path — it fires
- the tenant guard now firing for a client that never approved the ladder —
  `{"name": "Acme Corp"}` resolves to `acme-corp` and declines
- the LinkedIn figure gate missing `li5`/`msg4` — it refuses on all five keys
- a clean LinkedIn note being refused — passes
- the P.S. escaping the content gates — refused identically in body and P.S.
- the repetition gate silently acquiring the P.S. as input — it does not;
  `_quality_of` still reads `body` only
- a real date being refused, or a fabricated ratio exempted — 15/15 correct
- the new `_ladder_model_no_claim()` fixture passing by accident — the gate
  genuinely runs (`offer_id=OFFER-B-OPERATIONS`, 12 checks, `passed=True`) and
  is clean on attempt **1**, not salvaged on attempt 3
- the fixture repair costing the test file its power — it did not; the same six
  tests catch a broken research projection before and after
- the numeric branch having the same prefix bug as the worded branch — it does
  not; numeric membership is exact-string
- source left mutated after mutation testing — all three modules byte-identical
- production state touched — `queue.jsonl`/`campaigns.jsonl` hash-identical

Falsification attempts that **succeeded**: R1 and R2 below.

---

## 1. R1 — BLOCKING. The B1 support check is a four-character prefix, not a stem

**CLAIM.** *"A stemmed form of the matched word in the support text licenses
it, exactly as a stored digit licenses a digit."*
**AUTHORITY.** `src/generate.py`, `_invented_quantities`, the worded-quantity
loop. **MEASURED AT.** 2026-09-28, at `142ca537`. **STATE: REFUTED.**

```python
support_stems = {w[:4] for w in re.findall(r"[a-z]+", support.lower())}
...
head = re.findall(r"[a-z]+", match.group(0).lower())
if head and head[0][:4] in support_stems:
    continue
```

`w[:4]` is a truncation, not a stem. It collapses `threat`, `threats`,
`thread`, `threshold` and `three` onto `thre`; `several` and `seven` onto
`seve`; `trip` and `triple` onto `trip`; `doubt` and `double` onto `doub`.
A research pack containing any of the left-hand words licenses every fabricated
multiplier built on the right-hand one.

### Measured, through `_invented_quantities` directly

Base support in every row: *"Brightmoor Studio has moved to 2 week delivery
cycles across concurrent client projects, with resourcing decided a sprint
ahead."* One ordinary sentence is added per row.

| support sentence adds | copy under test | measured |
|---|---|---|
| — (control) | `That would double the effect on final margin.` | REFUSED |
| — (control) | `We tripled margin for an agency like yours.` | REFUSED |
| — (control) | `It has three times the impact on final margin.` | REFUSED |
| — (control) | `It quadrupled the margin last year.` | REFUSED |
| *"There is no **doubt** the resourcing call is made early."* | `That would double the effect on final margin.` | **PASSED** |
| *"The partners took a **trip** to the Amsterdam studio."* | `We tripled margin for an agency like yours.` | **PASSED** |
| *"Their utilisation **threshold** is set by the studio lead."* | `It has three times the impact on final margin.` | **PASSED** |
| *"Margin leak is the standing **threat** to the practice."* | `It has three times the impact on final margin.` | **PASSED** |
| *"They run **several** concurrent client projects."* | `Seven times the throughput on final margin.` | **PASSED** |
| *"They plot accounts on a value **quadrant** each quarter."* | `It quadrupled the margin last year.` | **PASSED** |

Six of eight attacks bypass. The support text never contains the licensing
word: `'doub' in support_stems` → `True` while `'double' in support` → `False`.

### It fires through the LIVE path, on both channels

Through `_step_refusals`, which is what the regeneration loop consults:

| step | copy | support word | measured |
|---|---|---|---|
| `msg3` (LinkedIn) | `Rowan, we tripled margin for an agency like yours.` | `trip` | **PASSED — no refusal at all** |
| `msg3` (LinkedIn) | `Rowan, this has three times the impact on your final margin.` | `threat` | **PASSED — no refusal at all** |
| `em4` (email) | `Resource decisions have three times the impact on final margin.` | `threshold` | **PASSED** — only the unrelated `the body is under 40 words` fired |

### Nothing downstream catches it — which is the whole point of this gate

The gate exists because `claims.is_claim` discards an impersonal sentence
before the numeric test can run, and `copylint.COMPANY_CLAIM` never examines
it. Measured on the bypassed note, with a real pack:

    note: "We tripled margin for an agency like yours."
      generate._invented_quantities          -> []   CLEAN
      claims.check                           -> []   CLEAN
      claims.is_claim                        -> False
      copylint.untraceable                   -> []   CLEAN
      copylint.check_batch untraceable count -> 0
      heyreachfactory.unsupported_claims     -> []   CLEAN

    note: "Your team would see three times the impact on final margin."
      ... identical: every gate CLEAN

`heyreachfactory.unsupported_claims` (`src/heyreachfactory.py:452`) is the one
real backstop on the LinkedIn path and it is `claims.check`, so it inherits the
same blind spot. **There is no second line.**

### How reachable is it? 34% of the estate

Read-only scan of production `work/queue.jsonl` (1,582 records). For each
quantity word the gate can match, a record counts only when its research pack
contains the 4-char prefix and **no word of that quantity word's own
morphological family** — so no inflection is miscounted as a bypass:

    production records carrying a research pack        : 394
    records licensing >=1 fabricated multiplier
      through a SPURIOUS prefix collision              : 134   (34.0%)

      thrice        53 records   colliders: thrive, thrives, thrilled, thriving
      seven times   45 records   colliders: several, severity, seventh
      three times   37 records   colliders: threats, threat, thresholds, thread
      tripled        8 records   colliders: trip, trips
      double         4 records   colliders: doubt
      four times     3 records   colliders: fourth
      nine times     2 records   colliders: ninety, nineteen
      quadrupled     1 record    colliders: quadrant
      eight times    1 record    colliders: eighties

`several` and `threat`/`threshold` are not exotic vocabulary for an agency
operations pack. This is not a theoretical hole.

### Why this shipped, and it rhymes with round 1

Round 1's B1 shipped because the class had a **positive control and no negative
one**. Round 2 added four negative controls — and every one of them uses a
support pack containing the **literal** word (`doubled`, `twice`). The missing
control this time is the **near-miss**: a support pack containing a word that
merely *looks* like the quantity word. The author's own positive control
(`test_it_still_refuses_an_unsupported_multiplier`) runs against `REC`, which
happens to contain no collider. One fixture sentence away from being caught.

### The fix

Compare whole words against an explicit family, not a prefix — e.g. license
`double` only when the support contains one of `double|doubled|doubles|
doubling`, matched at a word boundary. The author's own comment already states
the right rule (*"a stemmed form"*); four characters is not a stem. Add the
near-miss negative control alongside it.

---

## 2. R2 — non-blocking, same family. `half the` / `half of` exempts real claims

**CLAIM.** *"THE MULTIPLIER SENSE IS UNTOUCHED."*
**AUTHORITY.** `_NOT_A_QUANTITY`,
`\bhalf\s+(?:an?\s+(?:hour|day|week|month)|the|of|a\s+dozen)\b`.
**MEASURED AT.** 2026-09-28. **STATE: PARTIALLY REFUTED.**

The idiom alternative `half\s+the` cannot tell *"Half the team had changed by
then"* (an idiom) from *"That is half the cost of your current stack"* (an
unsupported magnitude claim). Both are exempted:

| input | measured |
|---|---|
| `Half the team had changed by then.` (intended) | PASSED — correct |
| `Half an hour would be enough to settle it.` (intended) | PASSED — correct |
| `You would spend half the time on reporting.` | **PASSED — exempt** |
| `That is half the cost of your current stack.` | **PASSED — exempt** |
| `It takes half the effort to close the month.` | **PASSED — exempt** |
| `Half of your margin leaks before anyone notices.` | **PASSED — exempt** |
| `You would spend 50% of the time on reporting.` (control) | REFUSED |
| `That would halve your reporting time.` (control) | REFUSED |

The last two rows are the point: the identical claim refuses when written with
a digit or the verb, and passes when written `half the`. That is the same
one-character-of-phrasing shape as B2's `60%` vs `60/90`, which round 1 blocked
on. It is smaller than R1 (narrower vocabulary, and the reachability is not
measured), so I record it rather than block on it — but it should be fixed in
the same change, because it is the same lesson.

---

## 3. B4 — CLOSED. The guard fires on the path production takes

**CLAIM.** `_generate_via_campaign` threads `client_slug` from `rec["client"]`;
`_client_slug()` resolves explicit slug → `config["client"]` → normalised
display name; the dict path matches, the string path matches, `Acme Corp` does
not. **AUTHORITY.** `src/generate_campaign.py:_client_slug`, `generate()`,
`_process_contact`; `src/generate.py:_generate_via_campaign`.
**MEASURED AT.** 2026-09-28. **STATE: CONFIRMED, all four halves.**

    _offer_library_tenant()                       -> 'productive'
    clients.load("productive")["name"]            -> 'Productive'   (the old bug)
    clients.load("productive").get("client")      -> None
    _client_slug(clients.load("productive"))      -> 'productive'   MATCHES
    _client_slug({"client": "ACME ", "name": "X"}) -> 'acme'        (precedence 1)
    _client_slug({"name": "Acme Corp"})           -> 'acme-corp'    DECLINES
    generate("productive", ...)                   -> 'productive'   MATCHES

**And on the production path specifically.** `_generate_via_campaign` reads
`client_name = rec.get("client") or ""` and passes it as `client_slug`. Scanned
all 1,582 production records:

    distinct values of rec["client"]  :  'productive'  x 1582   MATCHES tenant

So the explicitly-threaded slug is the exact authority `offers.py` is keyed on,
for every record in the estate.

**Proved load-bearing by mutation, not by reading.** I ran a mutation that
reverts **only** the B4 comparison — `tenant_slug ==` back to
`str(client_name) ==` — leaving everything else at `142ca537`:

    M7b   ONLY the B4 fix reverted        KILLED
          FAIL: test_the_gate_is_read_when_the_client_is_a_config_dict
          FAIL: test_the_refused_contact_stores_no_copy
          (test_the_gate_is_read_when_the_client_is_a_slug_string still PASSES,
           which is exactly right - the string path worked before B4 too)

That is the cleanest possible evidence: the dict-path test dies, the
string-path test does not. Round 1's central finding is closed and pinned.

**Live in the author's own real-model runs.** Its five artifacts carry
`sequencegate step_objectives` **6 times** across 183 refusal instances. Before
B4 that number was structurally zero on the dict path.

### Latent, non-blocking: the two sides normalise differently

`_client_slug()` lowercases and slugifies the dict path. The string path and an
explicitly-passed `client_slug` are used **verbatim**:

    generate("productive",  ...)  -> matches
    generate("Productive",  ...)  -> does NOT match     (silently re-inert)
    generate("productive ", ...)  -> does NOT match

No production record spells it any other way today, so this is latent. But it
is the same shape as the bug just fixed, and `client_slug.strip().lower()` at
the two assignment sites removes it.

---

## 4. B3 — CLOSED. The figure gate refuses on LinkedIn, and a clean note passes

**CLAIM.** `_invented_quantities` is wired into the LinkedIn branch;
`claims.check`/`_quality_of` deliberately not, because that asymmetry is
pre-existing and wider. **AUTHORITY.** `src/generate.py:_step_refusals`.
**MEASURED AT.** 2026-09-28. **STATE: CONFIRMED.**

Through the live `_step_refusals` path, with the round-1 note verbatim
(*"Rowan, we cut delivery overhead by 73% across 41 studios and tripled margin
last year."*):

| step key | measured |
|---|---|
| `connect` | REFUSED — *the figure 73 appears in no stored fact...* |
| `msg1` | REFUSED |
| `msg2` | REFUSED |
| `msg3` | REFUSED |
| `msg4` (= `li5`, the one this branch newly plumbed) | REFUSED |
| `msg3`, clean note referencing the stored `2 week` fact | **PASSED**, no refusals |

Killed by mutation M12 (the wiring removed →
`test_a_linkedin_note_with_an_invented_figure_is_refused` fails).

**Observed firing in the real runs, not only in tests.** Of the 15 `no stored
fact` refusals across the author's five artifacts, **7 carry a `liN:` prefix** —
LinkedIn steps. Before B3 that count was zero by construction.

### Is the remaining asymmetry safe to leave? Mostly yes, with one exception

The LinkedIn branch still skips `claims.check` and `_note_quality`. Assessed:

- **`claims.check` has a real downstream backstop.** `heyreachfactory.
  unsupported_claims` (`src/heyreachfactory.py:452`) runs `claims.check` over
  every merge-variable's text before a push, and its docstring says exactly why
  it exists (*"the email half has three gates and the LinkedIn half had one"*).
  A note asserting something the record does not support is caught there.
  Leaving it out of the generator costs writer attempts, not safety.
- **`_note_quality` (note repetition) has no backstop**, but repetition is a
  quality defect, not a safety one. Acceptable to defer.
- **`_invented_quantities` has NO backstop at all** — that is the whole premise
  of the gate. Which is why R1 lands where it does: the one check with no
  second line is the one round 2 made bypassable.

The author's judgement to scope the fix to the gate this branch introduced is
correct. **What is not safe is that the gate it introduced can now be licensed
away by an unrelated word.**

---

## 5. B2 / F1 — CLOSED. 15 of 15 through the live path

**CLAIM.** Only a full date with a year is exempt; `60/90`, `70/30`, `90/10`
refuse; `17/10/2024` passes; `"2024 agencies"` still refuses.
**AUTHORITY.** `_DATE_FIGURE`. **MEASURED AT.** 2026-09-28.
**STATE: CONFIRMED.** Driven through `_step_refusals`, not the regex:

| input | expected | measured |
|---|---|---|
| `Decisions at 60% burn versus 90% differ sharply.` | REFUSED | REFUSED |
| `Decisions at a 60/90 burn split differ sharply.` | REFUSED | **REFUSED** (was PASSED in round 1) |
| `We normally see a 70/30 split in margin recovery.` | REFUSED | **REFUSED** |
| `Early intervention gives a 90/10 recovery rate.` | REFUSED | **REFUSED** |
| `On 17/10/2024 we spoke about the key.` | PASSED | PASSED |
| `On 2024-10-17 we spoke about the key.` | PASSED | PASSED |
| `On 17 October Jesse asked about the list.` | PASSED | PASSED |
| `We last spoke in October 2024 about this.` | PASSED | **PASSED** (F1) |
| `The practice has been running since 2019.` | PASSED | **PASSED** (F1) |
| `Nothing has been decided since Q1 2025.` | PASSED | **PASSED** (F1) |
| `We work with 2024 agencies like yours.` | REFUSED | **REFUSED** — the year exemption did not over-reach |
| `Your 2 week delivery cycles are unusual.` (stored) | PASSED | PASSED |
| `Since 2016 the healthcare practice has run.` (stored) | PASSED | PASSED |
| `A 5 minute call would settle it.` (1 char) | PASSED | PASSED |
| `We improved margin by 15% last quarter.` | REFUSED | REFUSED |

**Mismatches: 0 of 15.** Killed by mutation M16 (the bare `\d{1,2}/\d{1,2}`
alternative restored → three `test_a_bare_ratio_is_refused` subtests fail).

The F1 year exemption is bounded by a date context (`month|Q[1-4]|since|in|
from|until|...` beside a `(19|20)\d\d`), which is why `"2024 agencies"` still
refuses. `in 2024` is the loosest alternative and could in principle exempt a
figure in that narrow numeric range beside the preposition; I could not
construct natural copy where that matters, so I record it and do not block.

---

## 6. F3b — CLOSED. The P.S. is inside the gated text

**MEASURED AT.** 2026-09-28. **STATE: CONFIRMED**, and with no side effect on
the repetition gate.

| case | measured |
|---|---|
| clean body, no P.S. | no figure refusal |
| `...73% across 41 studios...` in the **body** | REFUSED — *figure 73*, *figure 41* |
| the identical sentence in the **P.S.** | **REFUSED — identically** (round 1: stored clean) |
| clean P.S. | no figure refusal |

Checked for a side effect the change could have had and does not:
`_quality_of` receives the trial cadence, not the concatenated `text`, and its
sibling set is still `s.get("body")` only — so the two shared P.S. lines cannot
inflate the repetition comparison. Killed by mutation M13.

---

## 7. Mutation testing — my own harness, nine mutations, all killed

Applied in this worktree at `142ca537`, with the two assertions this repository
demands, plus one this repository's own memory note earns:

1. the mutated bytes really reached disk (`sha256` before ≠ after);
2. the source restored **byte-identical** afterwards;
3. **the anchor matched exactly once.** The source files are CRLF on disk, and
   my first run's multi-line anchors — written with `\n` — matched **zero**
   times. Five mutations silently applied nothing and would have been reported
   as anchor misses, not as survivors, only because the harness counts matches.
   A mutation harness that does not assert its anchor found the text is
   indistinguishable from one whose mutations all survive.

Baseline before every mutation: **262 tests, OK** across the branch's own test
file plus `test_generate`, `test_only_the_last_subject_may_claim_finality`,
`test_task400_rework2/3`, `test_the_research_pack_has_one_shape`,
`test_the_offer_ladder_is_enforced_as_step_objectives`,
`test_changing_an_approved_fact_changes_the_output` and the three entrypoint
files.

| # | Mutation | Verdict | Killed by |
|---|---|---|---|
| **M3** | repetition gate back to `subject + body` siblings | **KILLED** | `test_the_near_miss_pair_is_clean_on_bodies` |
| **M7** | sequencegate verdict no longer read in the retry loop | **KILLED** | the dict-path, slug-path and no-copy-stored tests (3) |
| **M7b** | *only* the B4 comparison reverted | **KILLED** | dict-path test dies, slug-path test correctly survives |
| **M8** | `missing_required` no longer reaches `failures` | **KILLED** | withheld `msg4`, blanked P.S. |
| **M12** | the B3 LinkedIn figure-gate wiring removed | **KILLED** | the LinkedIn invented-figure test |
| **M13** | the F3b P.S. plumbing removed from the gated text | **KILLED** | the P.S. invented-figure test |
| **M14** | the B1 support check removed (refuse on match alone) | **KILLED** | both new negative controls |
| **M15** | the B1 idiom test by PRESENCE instead of POSITION | **KILLED** | `test_an_idiom_does_not_exempt_a_real_multiplier_beside_it` |
| **M16** | the B2 fix reverted (bare `d/d` ratio exempt again) | **KILLED** | `test_a_bare_ratio_is_refused` ×3 |

**M3, M7 and M8 — the three round-1 survivors — all die.** M15 is the one worth
naming: the author's stated reasoning for matching idioms *by position rather
than by presence* ("presence-anywhere would let one `double-check` license
every fabricated multiplier in the same message") is not just sound, it is
**asserted by a test that fails when the reasoning is reversed**. That is the
standard round 1 asked for and did not get.

**Source integrity after all nine:**

    src/generate.py           e303e40345ec7857a3d680fa8834116d26691d0f49e98d9058e7b4837a58d405
    src/generate_campaign.py  2a10a9ece4b51d842e11a48ca61ea77954154b86749e7c50f159b59a048d0e7e
    src/copystages.py         a8b66d8698c562a5c40166f998be1bb64de4c0bae60c71140b711696063b2150

Identical to the pre-mutation hashes, and `git status --porcelain` empty.

---

## 8. F3a — the retraction is CORRECT, and understated

**CLAIM (the author's retraction).** *"My earlier report that the P.S. now
renders was wrong. `bisonfactory.py` contains zero `ps` references and
`render.py` reads `subject`/`body` only, so the P.S. reaches the stored step
and no prospect-facing surface. Operator defect 1 is NOT fixed."*
**AUTHORITY.** Independent trace of every `ps` consumer plus an executed
end-to-end marker run. **MEASURED AT.** 2026-09-28. **STATE: VERIFIED CORRECT.**

`ps` references in `src/bisonfactory.py`: **0** (`git grep -nE '\bps\b'` and
`git grep -nE '"ps"|'"'"'ps'"'"''` both return nothing, exit 1). A
`grep -c "ps"` of 102 is substring noise — `steps`, `keeps`, `perhaps`.

`src/render.py` reads `step.get("subject")` and `step.get("body")` at `:52` and
`:122-123`; `HEADER` at `:36-37` has no `ps` column.

**Four `ps` levels exist and only the step-level one is at issue:** a writer
level (`src/copystages.py:467`, read at `generate_campaign.py:1068`), a
sequence level (`generate_campaign.py:1131` → `sequencegate.py:255/438`), a
lead level (`generate_campaign.py:1116` → `copylint.py:192`), and the **step**
level — written at `src/generate.py:2327`, read at `src/generate.py:2804`
(`_step_refusals`, the F3b gate) **and nowhere else**.

**Executed proof.** A marker `ZZMARKERPS` driven through the real
`_candidate_steps`, then through the real staging path:

    _candidate_steps -> day1 ps='P.S. ZZMARKERPS one.'   day8 ps='P.S. ZZMARKERPS three.'
      (em1 and em3 - exactly the two steps the operator named)

    MARKER survives bisonfactory._certified_copy   : False
    MARKER on the EmailBison wire (_variables_for) : False
    MARKER in push.emailbison_rows                 : False
    MARKER in render CSV rows / render.card() HTML : False
    MARKER in heyreachfactory._step_copy (all 4 actions) : False
    MARKER in the operator preview                 : False

The chain dead-ends independently at eight places, each of which rebuilds a
fresh dict from named fields: `bisonfactory.py:1150` and `:1651-1670`,
`push.py:227-228`, `render.py:52` and `:122-123`, `preview.py:234-244`,
`previewpage.py:415-417`, `heyreachfactory.py:198-222`, `web/api.py:2111`.
`src/web/` has zero `ps` hits across all 19 modules.

**The retraction is if anything understated.** The P.S. is absent from the
operator preview and the client-visible export too, so the operator's literal
words — *"the artifact has no P.S. field anywhere, for any message"* — remain
true of the artifact as well, not only of the wire.

### Two things the retraction does not mention

1. **The P.S. is stored on an approved step but is not covered by the
   approval.** `src/approval.py:59-67` hashes `channel`, `subject`, `body`,
   `note`. Measured: `fingerprint(step WITH ps) == fingerprint(step WITHOUT
   ps)` = `d01f663e335f9794`. The benign half is that this change invalidates
   no existing approval. The latent half is that whoever plumbs `ps` to the
   wire ships it **uncertified** unless they also extend the fingerprint.
2. **`bisonfactory.py:1168`** — `_certified_copy`'s post-fingerprint guard is
   `forbidden = set(extra) & {"subject","body","note","message"}`. `ps` is not
   in that set, so a future caller could route a P.S. through `extra` *after*
   the approval check. Unreachable today; it is precisely the hatch that
   function's own docstring warns about.

**Both belong in the follow-up that renders the P.S.**, and neither blocks this
branch. Operator defect 1 is **not** fixed on any prospect-facing path and the
task now says so plainly, which is what round 1 asked for.

---

## 9. The three new suite failures — the guard working, and the repair is sound

This is the place the coordinator flagged as easiest to get wrong, and round 1
already got it wrong once in this same file. I measured it four ways.

**They were real, and they were the branch's own.** Before the author's
`142ca537`, `tests.test_the_research_pack_has_one_shape` failed 3 of 19 at
`e1fbd75b`, with `hold_kind='copy_refused'` and
`sequencegate step_objectives/em2..em5`. Attribution:

| tree | result |
|---|---|
| `e4e2a35d` (round 1 head) | 19/19 **OK** |
| `origin/master` | 19/19 **OK** |
| `e1fbd75b` | **3 failures** |
| in the 128-name baseline? | **No** — `grep` returns nothing |
| mutation M7b (B4 comparison reverted, everything else at `e1fbd75b`) | the 3 failures **disappear** |

So the cause is the B4 fix, exactly as the author says: once the guard matched,
`sequencegate` started reading Offer B's spine for every test in the file, and
`CampaignModel()`'s default copy predates the ladder.

**The repair is a compliant draft, not a widened gate.** `_ladder_model()` and
`_ladder_model_no_claim()` supply copy that follows the rungs; no rule,
threshold or exemption moved. That is the direction `CLAUDE.md` requires
(*"never widen a lint rule to make a draft pass. Regenerate the draft"*), and
the same direction `e4e2a35d` took for the literal-string test.

**The fixture does not pass by accident.** Measured through
`_generate_via_campaign`:

    canonical list    hold_kind=None  attempts=1  steps=12
                      sequence_gate: passed=True  checks=12  failures=0
    absent research   hold_kind=None  attempts=1  steps=12   (same)
    empty list        hold_kind=None  attempts=1  steps=12   (same)
    offer_id on the entry: OFFER-B-OPERATIONS

The gate **ran** (an UNCHECKED ladder would need `offer=None`; `offer_id` is
present and 12 checks were evaluated) and was clean on attempt **1**, not
salvaged on the third.

**It discriminates.** Breaking one element at a time:

| perturbation | measured |
|---|---|
| remove the shared word `offices` from `em1` | **copy_refused**, 3 attempts — `sequencegate reason_for_outreach/em1: shares no content word with any researched fact` |
| make `ps_em1` identical to `ps_em3` | **copy_refused**, 3 attempts — `sequencegate no_repetition/ps: both P.S. lines make the same point` |
| replace `project visibility` with `general housekeeping` | passes — see below |
| rewrite `em1` as a statement rather than a question | passes — see below |

Two of the four gates the author names are genuinely load-bearing in the
fixture. The other two are not: the rung-1 objective is satisfied by the rest of
the paragraph (*"keeps each project visible while the work is still open"*),
not by the phrase named, and the question form carries no gate at all. **The
fixture is correct and the explanation over-attributes.** Precision note, not a
defect — but the author should not cite a phrase as load-bearing without having
perturbed it, which is the habit that produced B4.

**The repair cost the file no power.** The tests' subject is the canonical
research-pack projection. With `generate._account_sources()` mutated to return
`[]`:

    at 142ca537 (repaired fixtures)  : 6 failures
    at e4e2a35d (original fixtures)  : the SAME 6 failures

Identical sets. `test_the_canonical_list_shape_produces_copy` did not detect a
broken projection before the repair either — that is pre-existing, and five
sibling tests in the same file do detect it, including
`test_the_projection_is_the_canonical_one_and_not_a_second_reading` and
`test_the_literal_acceptance_call_produces_copy`.

**At `142ca537` the module is 19/19 OK**, reproduced.

### The slice defect the author disclosed is real, and the disclosure is right

`work/slice.py` chose modules by grepping single-line imports and missed this
file, whose `from src import (...)` spans two lines — so it reported "zero new
failures" while three existed. I did not use the slice: the 3 failures surfaced
in my own baseline run before the author disclosed it. **The "1,561 tests across
66 affected modules, zero new" figure is correctly retracted and I do not rely
on it.** The full-suite set diff is the only authority, and the author's own
correction says so.

---

## 10. Suite

**Baseline:** `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 distinct failing
names, compared as **SETS**. TASK-549 records this baseline is stale on master —
four of its names fail on master with no branch — so inherited noise is
expected and is attributed, not counted.

**Author reports:** 13,681 tests, 124 distinct failing names, 7 absent from the
baseline: 4 inherited (proved by revert-and-rerun at the merge commit) and 3 its
own, now fixed.

**This review's measurement:** the affected-surface run (262 tests over 11
modules, every module this branch changes plus its dependents) is **green at
`142ca537`** — including the three that were failing at `e1fbd75b`. A full
`unittest discover` run at `142ca537` was launched from a swept `%TEMP%` (851
`rga-*` directories reduced to 102, leaving only those younger than three
minutes, which belong to other agents' live runs) with its log written outside
the repository per OPERATING-MODE 22.

> ⚠ **THE FULL-SUITE SET DIFF IS UNSETTLED BY THIS REVIEW, AND STAYS UNKNOWN.**
> The run was **killed part-way** when this review was ordered to stop and push
> (operator moved the estate to minimum-Claude mode, 2026-09-28). It produced
> **no `Ran N tests` line**, which per invariant 0 is an ABSENT measurement, not
> a failing suite — the same rule the author recorded for itself. It is not
> evidence in either direction and nothing here rests on it. Whoever picks this
> up should sweep `%TEMP%` for `rga-*` first and run it uninterrupted.
> The author's own full-suite figure (13,681 tests, 124 failing names, 7 absent
> from the baseline, 4 inherited + 3 its own) is therefore **unverified by me**;
> I independently confirmed only the 3-that-were-its-own half of it, in §9.

**Operational note that cost the author an hour and nearly cost me one.** Two
earlier full runs in this review were discarded, not because they failed but
because I swapped `src/` under a running suite while checking an attribution.
A suite whose source changed mid-run is an absent measurement exactly as a
suite with no `Ran` line is. Mutation work and full-suite work cannot overlap
in one worktree, and I re-sequenced to run them strictly in series.

**The suite does not carry this verdict either way.** R1 is a measured
behavioural defect on a live path; no suite result would clear it, because the
branch's own tests pass while it is present — that is the finding.

---

## 11. The 40% rate — reproduced independently, and it is neither a pass nor a regression

**CLAIM.** The contact under test gets copy through 2 of 5 runs (40%), the same
rate as the original 6 of 15, after round 1 regressed it to 0 of 5.
**AUTHORITY.** The author's own five artifacts,
`work/p0b-r2-{1..5}.json` in its worktree (**not** production `work/`).
**MEASURED AT.** 2026-09-28, re-derived by this review from those files.
**STATE: REPRODUCED EXACTLY.**

| run | c1 | c2 | c3 |
|---|---|---|---|
| 1 | refused | **12 steps** | refused |
| 2 | **12 steps** | **12 steps** | refused |
| 3 | **12 steps** | refused | refused |
| 4 | refused | refused | refused |
| 5 | refused | **12 steps** | **12 steps** |

    contact c1 (the contact under test) : 2 of 5   = 40%
    all three contacts                  : 6 of 15  = 40%   (= the original rate)
    runs where ANY contact stored copy  : 4 of 5
    total refusal instances             : 183
    step_objectives                     : 6 of 183   (author: 6 of 183)

All four numbers match the author's report. **Provider writes 0** is structural,
not asserted: every `api.emailbison.com` POST in the artifacts is recorded
`"trap": true, "allowed": false`, and the run store is a `%TEMP%` directory.

**I am not rounding 40% up to a pass, and I am not calling it a regression.**
The author explicitly declines to claim the engine reliably gets copy through,
and that restraint is correct: five runs of a stochastic model is a small
sample. The bar genuinely rose — 10 required steps, a required P.S., the gate
read natively rather than through the harness, the figure gate on both channels
— and the same rate against a higher bar is a real, modest gain that the task
does not overstate.

**Two footnotes on the numbers, neither material:**

- The stored step count is **12**, not the 10 the table says — five emails, five
  LinkedIn notes, and the two P.S. entries `ps_em1`/`ps_em3`, which the harvest
  carries in `sequences`. The "10 required steps" framing is about required
  *messages*; worth stating once so a later reader does not chase the gap.
- The "claim family, 67 of 183 (~37%)" is `sequencegate claims_supported` (44) +
  copylint `not traceable to a pack fact` (23). A broader reading that also
  counts `claims.check`'s `unsupported claim` (27) and the new figure gate (15)
  gives **109 of 183 (60%)**. The 37% is not wrong, it is a narrower
  definition than the label suggests, and the stable-finding conclusion holds
  under either.
- **`spelled as words` fired 0 times in 183 instances.** The worded-quantity
  branch — the one R1 is about — contributed nothing to the measured refusals,
  so R1 is a latent exposure in these runs rather than a demonstrated one. It is
  blocking on reachability (34% of packed records) and on the absence of any
  backstop, not on observed frequency.

---

## 12. Carried forward from round 1, still true, still not this branch's to fix

**The tenancy scoping is upside down**, and the author has recorded it at §9.0a
of its own doc, which is the right outcome. `bisonfactory._refuse_sequence_gate`
(`src/bisonfactory.py:822`) has **no tenant guard at all** while `offers.py` is
single-tenant, so at the push gate one client's approved ladder refuses every
client's push. `src/bisonfactory.py` and `src/offers.py` are byte-identical to
master on this branch — confirmed, they do not appear in
`git diff origin/master e1fbd75b` — so this is a master finding and belongs in
its own task. **The guard added here is necessary and is not sufficient**, and
the branch now says exactly that.

---

## 13. Production state: untouched

No provider writes. No Slack post. No write to production `work/`. No merge, no
push to `task-p0b-copy-engine-pareto`. `src/sequencegate.py`, `src/quality.py`,
`src/claims.py`, `src/copylint.py`, `src/lint.py` and `src/bisonfactory.py` were
not modified by this review.

Hashed from a fresh process before any work and again after all of it:

    work/queue.jsonl      dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
    work/campaigns.jsonl  00b6f103bbdb469f25a7977665e4e08339f30f2b827d9e2a3c82be560d4c5931

Production `queue.jsonl` was **read** — that is how the 34% reachability figure
in R1 was measured — and the scan reports counts and generic English collider
words only. No domain, company, contact or fact text left the process.

Mutation testing ran **in this review's own worktree**, never in the author's
and never against production state, with the source restored byte-identical and
verified by hash. Suite and mutation logs were written to `%TEMP%`, outside the
repository, per OPERATING-MODE 22.

---

## 14. What has to happen before this merges

1. **R1 — BLOCKING.** Replace the 4-character prefix in `_invented_quantities`'
   support check with a word-boundary match against each quantity word's own
   inflection family. Add the **near-miss negative control** that is missing:
   a pack containing `threat`, `several`, `trip` or `doubt` must still refuse
   `three times`, `seven times`, `tripled` and `double`. That control is the
   direct analogue of the one round 1 said was missing, one axis out.
2. **R2 — fix with R1.** Narrow `half\s+the|half\s+of` so it exempts the idiom
   without exempting `half the cost`, or drop those two alternatives and accept
   the false refusal on `half the team`, which is the safe direction.
3. **Non-blocking, worth doing in the same change:** normalise the string and
   explicit-`client_slug` paths (`\.strip().lower()`) so the two sides of the
   tenant comparison cannot drift apart again.
4. **Non-blocking, for the follow-up that renders the P.S.:** extend
   `approval.fingerprint` to cover `ps` and add `ps` to `_certified_copy`'s
   `forbidden` set, before anything puts a P.S. on the wire.
5. **Correct §9's fixture narrative** to name the elements that are actually
   load-bearing (`offices`, the distinct `ps_em1`) rather than the two that are
   not.

Items 2-5 are small and none of them is a reason to hold the branch on its own.
**Item 1 is the whole verdict.**

I fixed nothing. This review changed no file outside `docs/` on its own branch.
