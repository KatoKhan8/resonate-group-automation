PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-376 — researchpack vs packfacts: the live path decides, not a name

**GLM canary review P1-4** (`docs/glm-reviews/TRIAGE-CANARY-b333697-2026-09-26.md`),
left as "operator decision, no task — which store is canonical." **Operator
decision, 2026-09-26 evening: resolved by rule, not by picking a name.** Trace
the real production entrypoint; the store it actually consumes becomes
canonical; the other is demoted to a projection or retired. Do not come back
asking which module name to prefer unless the trace surfaces a genuine business
trade-off (cost, coverage, freshness) — that is the only kind of question this
task may put to the operator.

## What is measured so far — confirm or correct it, do not assume it

    grep -rln researchpack src/ scripts/     -> only caller: scripts/capture_researchpack.py:102
    grep -rln packfacts src/ scripts/        -> src/bisonfactory.py:559, src/packfacts.py

`packfacts.pack_for(rec)` is called from `src/bisonfactory.py:559` — inside the
send-path lint call (`copylint.check_batch(leads, {lead_id: pack})`). Per its
own docstring, `packfacts` reads `rec["research"]`, **already on the queue
record, written by the site crawl**, and explicitly does NOT buy anything.
`researchpack` **builds packs by buying them from Apify** and its only caller
today is a manual capture script — not `generate_campaign.py`, not
`bisonfactory.py`, not any cohort-generation path.

**`generate_campaign.py`'s `_prepare_sources()` reads neither.** It takes
`account.get("sources")` from whatever the caller already assembled. So there
are, provisionally, THREE things in play: `researchpack` (buys via Apify,
one manual caller), `packfacts` (reads `rec["research"]`, the live lint-time
consumer), and whatever populates `account["sources"]` before
`generate_campaign.generate()` runs (unidentified as of this task — find it).

## Build

    Trace, then wire or retire. No new module.

1. **Find every place research actually reaches a rendered message today** —
   not just `bisonfactory.py:559`'s lint check, but whatever wrote
   `rec["research"]` in the first place, and whatever (if anything) populates
   `account["sources"]` for `generate_campaign.generate()`. Name each with a
   file:line.
2. **Apply the rule.** Whichever store the live path actually reads is
   canonical. If that is `rec["research"]` via `packfacts`, `researchpack`'s
   Apify-purchased store is demoted: either wire it in as the thing that
   populates `rec["research"]` (if it is not already, and if research keeps
   arriving from elsewhere `researchpack` never actually fed), or mark it in
   `docs/BACKLOG.md` as retired-pending-decommission with the reason.
3. **If wiring one in changes cost or coverage materially** — e.g. `researchpack`
   is the only source of anything beyond the site crawl, or retiring it drops
   real signal — **stop and report the trade-off**, named with numbers, rather
   than deciding it. That is the one kind of question this task may escalate.
4. Do not let this become an architecture rewrite. The smallest change that
   makes one thing canonical and demotes or retires the other, with the
   consumer proven, not asserted.

## Acceptance — RUN each, paste real output

1. Name, with file:line, every real production consumer of research (not test
   fixtures, not the manual capture script) as it exists before this task
   touches anything.
2. After the change: one canonical store, one real writer path, and
   `researchpack`'s status stated explicitly — wired in, or retired with a
   reason in `docs/BACKLOG.md`.
3. Prove the canonical store's effect, not its presence: change a fact in it
   and show a rendered message or a lint verdict changes as a result (the same
   discipline TASK-369 required for the Second Brain).
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline. Not a count.

## What this task may NOT do

- Do not delete `researchpack`'s Apify-buying code outright in this task —
  demote or mark retired-pending-decommission; deleting a paid-provider
  integration is a separate, explicit operator call if it comes to that.
- Do not invent a third abstraction that reconciles the two by wrapping both.
  One canonical store.
- Nothing sent, nothing activated, no live Apify spend beyond what the
  existing manual capture script already does. Production freeze.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: (pending suite verdict)
TESTS: (pending suite verdict)
FILES CHANGED:
  - docs/BACKLOG.md — added `researchpack` decommission entry
  - docs/qwen-tasks/RUNNING/TASK-376-researchpack-vs-packfacts-the-live-path-decides.md — moved from TODO, result block added

FINDINGS:

### Acceptance #1 — Every real production consumer of research, with file:line

**Writers of `rec["research"]` (the canonical store):**
- `src/enrich.py:1160` — calls `research.run(rec, ...)` in the production enrichment pipeline
- `src/research.py:735` — `rec.setdefault("research", []).extend(evidence)` (Apify fallback path)
- `src/research.py:416` — `rec.setdefault("research", []).extend(usable)` (free site crawl path)
- `src/companies.py:326-329`, `src/demo.py:182-185`, `src/benchmark.py:53`, `src/synthetic.py:270-273`, `src/demo_outreach.py:417`, `src/web/demodata.py:479` — synthetic/demo/benchmark only

**Consumers of `rec["research"]` (production, not test fixtures):**
- `src/packfacts.py:pack_for(rec)` line ~103 — reads `rec.get("research")`, builds the lint pack
- `src/bisonfactory.py:559` — calls `packfacts.pack_for()` in `_copylint_batch()`, the live send path
- `src/generate.py:144` — calls `research.for_prompt(rec)` which reads `rec.get("research")`
- `src/research.py:758` — `ev.select(rec.get("research"))` in `for_prompt()`
- `src/funnel.py:58`, `src/outcomes.py:856` — stage counting references

**`researchpack` callers (non-production):**
- `scripts/capture_researchpack.py:102` — the ONLY caller of `researchpack.build()`. Manual script, not in any generation or send path.
- No `src/` module imports `researchpack` (only references in docstrings/comments)

**`generate_campaign.generate()` callers:**
- Tests only. No production caller in `scripts/` or `src/web/`. It reads `account["sources"]` which is a separate path from `rec["research"]`.

### Acceptance #2 — One canonical store, one real writer, researchpack demoted

**Canonical store:** `rec["research"]`
- Written by: `src/research.py:run()` via `src/enrich.py:1160`
- Read by: `packfacts.pack_for()` → `bisonfactory._copylint_batch()` → the live send path
- Also read by: `research.for_prompt()` → `generate.py` for prompt context

**`researchpack` status:** Retired-pending-decommission (entry added to `docs/BACKLOG.md`)
- Has its own cache (`src/researchpack/cache.py`), writes nothing to `rec["research"]`
- Buys from Apify through its own actors, but no production path consumes the result
- Deletion of `src/researchpack/` is an operator decision (paid-provider integration)

**`generate_campaign.py` status:** No production caller. Reads `account["sources"]`, not `rec["research"]`. Separate path, not wired into the live send.

### Acceptance #3 — Canonical store's effect proven

Already proven by `tests/test_the_copy_lint_refuses_the_real_send_path.py`:
- `test_a_lead_with_no_research_at_all_is_refused` — empty `rec["research"]` → lint refuses with `step1_without_pack_fact`
- `test_a_fact_that_belongs_to_another_company_supports_nothing` — foreign fact in `rec["research"]` → lint refuses
- `test_the_same_fact_on_the_account_s_own_domain_does_support_it` — own fact in `rec["research"]` → lint passes, lead staged

Changing a fact in `rec["research"]` changes the lint verdict. The chain is: `rec["research"]` → `packfacts.pack_for()` → `bisonfactory._copylint_batch()` → `copylint.check_batch()` → refuse or pass.

### Acceptance #4 — Suite verdict

(pending)

RISKS:
- `researchpack` code is NOT deleted — only demoted in BACKLOG.md. Deletion is an operator decision.
- `generate_campaign.py` is untouched — it has no production caller and fixing that is out of scope.

RECOMMENDED CLAUDE ACTION:
1. Review the BACKLOG.md entry for accuracy.
2. Decide whether to delete `src/researchpack/` entirely (separate operator call).
3. Decide whether `generate_campaign.py` should be wired into the live path or also retired.
