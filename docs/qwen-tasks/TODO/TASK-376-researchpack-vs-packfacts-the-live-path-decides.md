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
