PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-909 — offer selection must read the contact's persona, not an absent account field

**Filed by Claude 2026-09-28. Operator pre-authorised "ONLY the smallest
correction required for the production offer selector to consume the canonical
persona authority". Nothing else.** This blocks the one-account review
artifact: the operator will not accept copy whose offer was selected by an
accidental default.

## The defect, measured on two real records

`src/generate.py:2542` inside `_generate_via_campaign`:

    "persona": rec.get("persona", "champion"),

**That is an ACCOUNT-level field. Neither real record has it.** So it defaults
to `champion`, and the contact's own stored persona — the only persona anyone
actually classified — is never consulted by offer selection.

Proven, both directions:

    generate_campaign._select_offers('all', 'champion')        -> OFFER-B-OPERATIONS
    generate_campaign._select_offers('all', 'economic_buyer')  -> OFFER-A-ECONOMIC-BUYER

So the default **changes which offer ships.**

    record 2020companies-com  contact rachele-crumpler (CFO)
      contact['persona']            economic_buyer      <- canonical, stored
      rec.get('persona')            None                <- absent
      persona used by selection     champion            <- DEFAULTED
      offer selected                OFFER-B-OPERATIONS
      offer that should ship        OFFER-A-ECONOMIC-BUYER

    record brandiq-com        contact deyan-m (Co-CEO)
      same shape: contact economic_buyer, account absent, selection champion

**Both real records measured carry `economic_buyer` contacts and got the
champion offer.** This is not a one-record accident.

## What to build — ONE expression, not a framework

In `_generate_via_campaign` (`src/generate.py` ~2542), the account persona must
prefer, in order:

1. `rec.get("persona")` when present — an explicit account-level statement
   still wins, because an operator may have set it deliberately.
2. otherwise the **stored persona of the contacts being passed to
   `generate_campaign.generate()`**, when they agree.
3. otherwise the existing `"champion"` default, unchanged.

**Do NOT** add a persona module, a classifier, a config key, a new state field,
or a `persona_of()` helper. **Do NOT** change
`generate_campaign._select_offers`, `_applies_to`, or the offers yaml — they
are correct and already read the persona they are given. **Do NOT** touch the
rendering chain (TASK-560/904/905/906/907/908) or `src/sequenceplan.py`.

### The disagreement case must not guess
`generate()` takes ONE account persona for a list of contacts. If the contacts
being passed carry **different** personas, there is no single right answer:
**keep the current default and say so in your result block.** Do not pick the
first, the most common, or the "strongest". A silent choice there is the same
class of defect as the silent default this task exists to remove. Both real
records have exactly one sendable contact, so the ambiguous branch is not
exercised by the artifact — it must simply not be resolved by guessing.

## Acceptance

1. **The real record selects Offer A.** `2020companies-com`, whose only
   sendable contact `rachele-crumpler` is `economic_buyer`, must produce
   `OFFER-A-ECONOMIC-BUYER`.
2. **An explicit account persona still wins.** A record with
   `rec['persona'] = 'champion'` and an `economic_buyer` contact selects
   `OFFER-B-OPERATIONS` — the operator's explicit statement is not overridden.
3. **NEGATIVE CONTROL:** contacts with **disagreeing** personas fall back to
   `champion` and the result block says the branch was taken. No guessing.
4. **NEGATIVE CONTROL:** a contact with **no** persona, and no account
   persona, still yields `champion` and does not raise. Absence is not an
   error.
5. **No behaviour change anywhere else:** the rendering chain modules stay
   green (commands below).
6. **MUTATION:** revert your expression to `rec.get("persona", "champion")`;
   acceptance 1 must go red for that reason and no other guard may fire first.
   Restore and verify **byte-identical by sha256**. Files are **CRLF** — an
   `\n`-anchored regex matches zero times and the mutation becomes a silent
   no-op.

### ACCEPTANCE COMMANDS — run these exactly, paste the real output

**These must stay in THIS section.** GLM's extractor enters at the first
`## Acceptance` heading and stops at the next `## `; commands in a later
section are invisible to it. Only lines beginning `py -3`, `python`, `grep` or
`scripts/` are taken.

    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task560_ps_reaches_the_person
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task905_projection_from_plan
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_task908_approval_hash_covers_sender
    py -3 -m unittest tests.test_approve

All eight green; `tests.test_render_preview` must be **29 tests, 0 failures**.

**The persona assertion, which is the whole task** — exits 0 only when the
persona actually reaching offer selection is the contact's:

    py -3 -c "import sys; from src import generate_campaign as gc; a=sorted(gc._select_offers('all','champion')); b=sorted(gc._select_offers('all','economic_buyer')); sys.exit('offers do not differ by persona: %r vs %r' % (a,b)) if a==b else print('OK: champion->%s economic_buyer->%s' % (a,b))"

**Read exit codes OFF THE PROCESS, never through a pipe** — `| tail` masks a
failure and reports 0.

**Production `work/` is READ-ONLY.** Do not point at it and do not copy it for
this task; the acceptance above needs no estate data. Verify
`work/queue.jsonl` and `work/campaigns.jsonl` unchanged **by sha256 from a
fresh process** if you touch anything near it.

## Files
`src/generate.py` only, plus your own tests.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`** and verify HEAD equals
  `origin/master` before working — six of twelve dispatches once built on
  months-old history for 30-50 minutes.
- **NEVER WIDEN A GATE.** Fix what a gate CONSULTS, never what it PERMITS.
- **A test count is never a PASS.** Name the production path, the negative
  control, and the killed mutation.
- **Do not report a PREDICTED result.** Run it and measure it. A claim one
  command contradicts is worse than no claim.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active, nothing sent,
  enrolled or attached.
- **Write suite logs OUTSIDE the repository.** A suite with no `Ran N tests`
  line is an **absent measurement, not a failure** — sweep `%TEMP%`, re-run.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt` is compared **AS SETS,
  NEVER COUNTS**, and is **known stale** (TASK-549).
  `test_set_regeneration...test_successful_regeneration_replaces_all_notes`
  fails on master at `5 != 6` **with no branch at all** — not yours.
- Commit and push to your own branch; **verify the remote with
  `git rev-parse`**. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your exact branch
  head SHA. GLM verifies against that SHA.

**The operator is waiting on one real account's final copy. Offer A versus
Offer B changes every message in the sequence, so this one expression decides
whether the artifact shows the right offer or an accident.**
