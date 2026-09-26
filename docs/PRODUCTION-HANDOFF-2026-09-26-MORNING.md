# PRODUCTION HANDOFF — 2026-09-26 morning

Written at the close of the 2026-09-25 night session. **Read this first.** It
supersedes earlier handoffs on everything it covers.

**Nothing was sent tonight. No campaign was activated. No provider write
touched a client campaign except four pauses ordered by the operator.**

---

## 1. CAMPAIGN STATE, from the provider

    id   status     leads  sent  repl  bounced
    491  paused       333   411    11        1
    492  paused       206   245    11        1
    493  ACTIVE        22    22     0        0
    494  paused        76    95     0        0
    495  archived      60    42     0        1
    496  paused        43     3     0        0
    497  completed     20     7     1        0
    498  completed     15    10     0        0
    503  paused       250    25     0        2
    504  paused       223    14     1        0
    505  paused       217    25     0        0

**493 is the only thing sending.** It was left active deliberately: it has zero
blank rows and zero incident copy. It is also 18 of 22 collision with the
client's own live campaigns 327 and 328, which the operator has accepted.

**Nothing may be resumed without a review file the operator has approved.**
`reviewapproval.require` refuses `bison.resume_campaign` and
`heyreach.activate_campaign`, and since `c3fbc106` it also refuses
`attach_leads` into any campaign in a live state.

---

## 2. TWO INCIDENTS, BOTH CONTAINED

**INCIDENT 1, the Resonate copy.** 64 emails from 503/504/505 carried a
different agency's pitch signed with the operator's name from Productive
mailboxes. Root cause: `work/gencopy.py`, a scratch script that invented copy
and referenced `productive.yaml` zero times, pushed through
`bison.create_lead` + `attach_leads` and so never entered the factory where
the lint lived. Apology drafts per sender in
`work/INCIDENT-apology-drafts.md`. **Operator decision: suppress, senders send
their own apologies, no automated mail.**

**INCIDENT 2, the blank emails.** **77 emails with an empty subject and
`<p></p>` body reached real prospects** from 491-498 on 09-23. 102 more were
stopped. Cause: EmailBison keeps one lead per address per workspace, so the
push attached the client's EXISTING leads by id, inheriting their enrichment
variables and writing none of ours. 44 of the 46 blank leads in 491 were
already in a client campaign; 0 of 60 correctly-rendering ones were.

**All 76 recipients are suppressed** (`unsubscribed=True`, verified through
`channels.email_verdict`, not just written) **and stopped at the provider**.
Four of them replied to a blank email and need their senders personally:
491/142778, 491/190068, 492/142663, 497/167877.

---

## 3. DIRECTIVES AND GATES IN FORCE

    docs/OPERATOR-DIRECTIVES-2026-09-25.md   standing policy. Sections 1, 2
                                             and 11 apply to EVERY task:
                                             GitHub is the source of truth, a
                                             local commit is not a completed
                                             task, every task closes with a
                                             remote SHA and URL
    docs/ARCHITECTURE-UPGRADE-SPEC.md        next-phase architecture, verbatim
    docs/COPY-ENGINE-SPEC-v2.md              copy strategy, 10 improvements
    docs/PHASE1-PLAN-2026-09-26.md           five tasks, approved to start
    docs/BUGGIE-EVALUATION-2026-09-26.md     third-party tool evaluation

**Gates that refuse, all on master:**

    reviewapproval.require        activation without the operator's approval
    providerwrites.perform        a mutating call with no open write scope
    spendledger.check             a ceiling, by reservation, before the call
    copylint.check_batch          per message, now including P.S. and LinkedIn
    sequencegate.check            per SEQUENCE, repetition and duplication
    emptyrender.scan              a step that renders to nothing
    bison attach_leads            a top-up into a live campaign

**Cadence and threading, unchanged and not to be shortened:** five email steps
at days 1/4/8/12/21, em1 new thread subject A, em2 reply in A, em3 new thread
subject B, em4 reply in B, em5 new breakup thread subject C. Five LinkedIn
steps in `PRODUCTIVE_LI_HEAVY_V1`.

---

## 4. VERIFIED ON MASTER TONIGHT

    origin/master = b965a416 (verify with git rev-parse master origin/master)

- **Per-provider ceilings** merged, 104 tests green, and the lane's paired
  full-suite runs came back identical: 129 failing names before and after, so
  nothing newly red.
- **Ledger units**: `usd_estimate` on every row, dollars stored as integer
  **micro-dollars** because `expected_cost` is `int()` and $0.00256 a lead
  truncated a 50-lead cohort to zero. Credits return `usd_estimate: None` with
  `rate_source: "unknown"` rather than an invented rate.
- **Model ceilings** in microusd: anthropic $50/day, groq $10, openrouter $20.
- **One key per provider**: `providers.model_key()` returns
  `(value, name_it_was_found_under)`. `LLM_API_KEY` and `OPENROUTER_API_KEY`
  held the same credential, verified by digest.
- **Lint**: `unrendered_variable` and `empty_sentence` REFUSE, and the dash
  rule now reads P.S. lines and all four LinkedIn messages.
- **`src/secondbrain.py`** (TASK-317) merged, then found defective. See §6.
- **`src/sequencegate.py`** fixed after GLM review. 19 tests green.
- **`scripts/provision_worktrees.sh`** — the fix for §7.

**MERGE-BLOCKED:**

    TASK-308 Anthropic adapter   hardcodes expected_cost 0 and puts dollars in
                                 a new `amount` field, so spent() totals zero
                                 and no ceiling can ever fire. Must be
                                 rewritten through record(..., unit="microusd").
                                 docs/MERGE-BLOCKER-ANTHROPIC-SPEND-IS-UNCAPPED-2026-09-25.md
    TASK-309 ledger units        superseded by the surgical version on master;
                                 its int(expected_cost) would re-zero dollars
    qwen r9 branches             258 branches, all pushed, most carrying more
                                 than their task. Cherry-pick, do not merge.

---

## 5. THE FIFTY — PRODUCED, NOT YET POSTED

`work/review/503-FIFTY-v2-2026-09-25.html` (332 KB) and `.xlsx` (50 rows x 25
columns) in **`resonate-qwen-2`'s worktree**, not the main checkout.

    total 50    written 31    held 19    errored 0
    qualification   QUALIFIED_THIN 31, UNQUALIFIED 13, INSUFFICIENT 4, HELD 2
    capabilities    3 distinct: profitability, project_management,
                    resource_planning
    cost            cheap models $0.1337, Sonnet $3.0127, total $3.1464
                    = 10.15 cents per lead

**The cost is the finding.** 10.15c against a 0.3c target, because this run was
uncached, unbatched, and Sonnet now writes em1 whole. Sonnet is 96% of it.
Batching and prompt caching are the two levers and both are unbuilt.

**ACTION: verify the file against the ten's shape and post it.** It has not
been posted to `#resonate-os` and the operator has not seen it.

---

## 6. TONIGHT'S CORRECTIONS, INCLUDING MINE

**GLM found two things I had personally checked and signed off.**

**TASK-317, the Second Brain**, merged at `4ff299a9` after I ran its
acceptance check. GLM found and I reproduced: `all_sections()` is public and
returns everything, `TASK_SECTIONS` is a mutable dict, `**scope` is accepted
and discarded, `source` is a hardcoded literal at 19 sites **regardless of
client**, `index_html` writes no file, and **`for_task` has zero callers**.

**My acceptance check had the defect it was meant to catch.**
`assert all(f.get('source') and f.get('date') ...)` — both are stamped
unconditionally at retrieval, so it could never fail. It tested that the
stamping code ran, not that the provenance was true. **TASK-322** carries the
fix and a check that asks for a different client and asserts the source does
not name Productive.

**`sequencegate.py`, which I wrote as the answer to "five phrasings of one
argument", could not catch a paraphrase.** Two steps arguing the same thing in
different words score 0.125 against a 0.45 threshold. My test used a verbatim
copy, which lexical overlap catches trivially. Fixed: emptiness and a missing
qualification are refusals, `INSUFFICIENT_DATA` no longer sails through,
three-letter terms are no longer dropped, the batch check is case-folded, and
**the paraphrase blind spot is now reported rather than silent.**

Other corrections: the HeyReach "one step from six" finding is **stale** -
`_refuse_missing()` refuses the whole staging now; `productive.yaml` was never
missing `our_company`/`capability`, my page builder passed empties; the
refuse-list as substring matching would refuse 286 of 333 leads of the
client's own approved copy.

---

## 7. THE WORKTREE PROVISIONING GAP

`config/.env` and `work/` are both gitignored, correctly. **A fresh worktree
therefore has neither**, so a dispatched worker cannot reach a provider or read
a lead. Twelve workers were raised into that state and TASK-316 reported five
blockers, every one "this file exists only on another worktree".

Fixed by `scripts/provision_worktrees.sh`. **Run it after creating any
worktree.** `work/queue.jsonl` is deliberately NOT copied: it is live state
with a cross-process lock, and twelve private copies would be twelve divergent
truths.

---

## 8. WORKFORCE AND ARTIFACTS

**Qwen, pool raised 8 -> 12.** Sized against measurement: Ryzen 7 7735HS, 16
logical cores, 31.2 GB RAM, ~350 MB per worker. **RAM is the binding
constraint, not cores** - CPU sat at 13-34%. More capacity means more RAM.

    DONE, artifact verified   305 Groq adapter, 307 ContactOut linkedin route,
                              310 training capture, 311 ingest, 313 AUDIT,
                              314 cadence regression test, 315 cross-channel
                              tests, 316 the fifty, 317 Second Brain (then
                              found defective), 216 219 221 279 QA
    WRITTEN, NOT STARTED      318 Offer Engine, 319 five skills, 322 the
                              Second Brain fix
    NOT YET WRITTEN           320 campaign-first strategy, 321 wiring
                              copystages and sequencegate

**GLM** — `docs/glm-reviews/`: `TASK-317-secondbrain.md`, `sequencegate.md`,
`copylint.md`. Two of three found real defects. **Note: GLM returns
`finish_reason='length'` and the adapter refuses rather than returning an
empty string. Budget 12,000 max_tokens, not 3,000.**

**Grok** — `docs/provider-answers/`: `heyreach-step-limits.md` (8.2 KB),
`emailbison-remove-and-pause.md` (4.6 KB), `apify-actor-limits.md`,
`cheapverifier-rate-limits.md`. **The CheapVerifier answer FAILED** - 179
chars of the model narrating what it was about to do. Re-run it.

**Buggie** — already installed (13 agents in `~/.claude/agents/`). Evaluated:
no network calls, Apache 2.0, but **all 13 agents are granted `Bash`**, which
subsumes the denied Edit and Write. Contained by running against a fresh clone
at `/tmp/buggie-target`, verified to hold no `.env` and no `work/`. **It has
not been run yet** - it is 13 Claude agents and Claude was at 70-75% of the
weekly limit.

---

## 9. SPEND

**The ledger shows zero rows for today, and that is expected, not a fault.**
Tonight's model work ran through direct scripts with the ledger deliberately
bypassed on the operator's instruction, and `glm.py` has never had a
`spendledger` reference. **Model spend is currently invisible to the ledger.**

By hand, tonight:

    the ten (v1)        $0.0921    10 leads,  0.92c each
    the ten (v2)        $0.6399    10 leads,  6.40c each
    the fifty (v2)      $3.1464    50 leads, 10.15c each
    GLM reviews         3 calls, not metered
    Grok answers        4 calls, not metered
    TOTAL, by hand      ~$3.88

Provider credits: no verification, enrichment or Apify spend tonight.

---

## 10. OPEN DECISIONS, ONE LINE EACH

1. **The fifty** — 31 written, 19 held, 10.15c per lead. Post and review, or
   change the copy path first?
2. **Cost** — 10.15c against 0.3c. Batching and caching are the levers. Build
   them before the 690, or accept the cost at this volume?
3. **A zero-cost call to an undeclared provider is still allowed.** Two
   deliberate positions in tension; test skipped and escalated at `9ac59bbb`.
4. **`blitz`/`aiark`** are decided; **the cents-vs-credits backfill rate** for
   existing rows is not. Providers with no establishable rate write
   `usd_estimate: null`.
5. **The 9,107 already-verified leads** revert to `held` under the new
   verification order. Recommendation: grandfather them.
6. **Missing client assets** — no case studies, benchmarks, dashboard example,
   calculator or demo link. `offers.missing()` will list them; only the client
   can supply them.
7. **`booking_link` is `https://productive.test/...`** — a reserved TLD that
   resolves nowhere. Any CTA offering a link offers a dead one.
8. **Live authorisation for the email->LinkedIn stop.** Synthetic tests exist;
   the verb `LINKEDIN_STOP_LEAD` is sealed and the path has never run.

---

## 11. THE FIRST THREE ACTIONS FOR THE NEXT SESSION

**1. Post the fifty.** It exists in `resonate-qwen-2`'s worktree and the
operator has not seen it. Verify it carries what the ten carried — ICP
evidence, facts with sources, hypothesis marked as hypothesis, capability and
why, five emails with threading, both P.S. lines, signature, four LinkedIn
messages, copylint and sequencegate results — then upload both files to
`#resonate-os`. Do not link into `work/`.

**2. Dispatch TASK-322, then 318 and 319.** 322 fixes the Second Brain that is
on master with fabricated provenance and no callers. 318 and 319 are written
and unstarted. Run `scripts/provision_worktrees.sh` first or the workers will
fail the same way TASK-316 did.

**3. Re-run the CheapVerifier Grok question and read `docs/glm-reviews/copylint.md`.**
The Grok answer is 179 chars of preamble. The copylint review has not been
read by anyone, and GLM is two for two on finding real defects in reviewed
code.

**Do not** resume any campaign, merge a qwen r9 branch wholesale, or merge
TASK-308 until it writes through `record(..., unit="microusd")`.
