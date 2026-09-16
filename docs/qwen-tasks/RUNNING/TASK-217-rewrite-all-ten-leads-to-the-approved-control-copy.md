PRIORITY: P0
DEPENDS:

# TASK-217 - every variable on all ten leads, or no send

## WHERE THIS SITS

This is the last thing between campaign 485 and the first real send. Claude
stopped the activation because the corrected comparator found that the ten
leads at EmailBison carry the OLD model-generated copy, not the approved
CONTROL copy. Activating would have sent ten real prospects words the operator
never approved.

Measured, per lead, provider side against approved side:

    approved  "Al, I work with Advertising Services teams on profitability
               visible on Monday not two weeks late..."
    provider  "Agency59 describes itself as an independent branding ad
               agency..."

and the provider holds `subject_1..subject_5` and `body_1..body_5` - FIVE
steps - while CONTROL is three.

## THE DIAGNOSIS, ALREADY DONE. DO NOT REDISCOVER IT.

Two separate causes, both in `bisonfactory`.

**1. Stale numbered variables can never be cleared.**
`_variables_for(lead, campaign)` builds the wanted set by enumerating
`lead["copy"]` and numbering it from 1:

    for position, node in enumerate(copy, start=1):
        values[f"subject_{position}"] = ...
        values[f"body_{position}"] = ...

A three-step campaign therefore names `subject_1..3` and `body_1..3` and
NOTHING ELSE. `_ensure_leads` then computes
`stale = [v for v in wanted_vars if held.get(v["name"]) != v["value"]]` -
so `subject_4`, `subject_5`, `body_4` and `body_5` are not in `wanted_vars`,
are never compared, and are never cleared. They are left on the lead from the
five-step era.

**2. The copy written at stage time came from broken approvals.**
`_approved_copy` reads the record's approved steps. When `stage()` ran, the 30
approvals had been fingerprinted WITHOUT campaign context, so
`approval.is_approved(rec, ck, sk, expanded_step)` was false for every step and
the copy it produced was not the CONTROL copy. Those approvals have since been
revoked and retaken with `campaign=` - `apply_control_approval.py` now reports
0 stale and `is_approved` passes 30/30 against the CONTROL-expanded steps.

So the copy source is correct NOW. It was not when the leads were written.

## THE QUESTION

1. **Clear stale numbered variables.** Extend the wanted set so that any
   `subject_N` / `body_N` the campaign's sequence does NOT use is explicitly
   written EMPTY rather than omitted. The provider's own variable list is
   readable - `bison.custom_variables()` and `bison.variables_of` - so the set
   to clear is discoverable rather than guessed. Do not delete variables if the
   provider has no delete; an empty value that the template never reads is
   enough, and say which you did.
2. **Refresh all ten leads against the CORRECTED approvals.** Every
   `subject_1..3` and `body_1..3` must equal the approved CONTROL copy for that
   contact. All ten leads, every variable, not the subset that happens to
   differ from a stale comparison.
3. **Then read all ten back from the provider** and compare the PROVIDER-HELD
   words against the approved fingerprints. Require:
     - 30 of 30 exact matches (10 contacts x 3 steps)
     - ZERO non-empty `subject_4/5` or `body_4/5` on any lead
   Report per lead, identifiers hashed.
4. **Do not activate.** Claude runs the preflight and the activation.
5. **Add a regression test** that fails if a lead can hold a numbered variable
   beyond the campaign's sequence length. That is the defect that made this
   invisible, and it would otherwise recur on the next campaign with fewer
   steps than its predecessor.

## THE TRAP

`_ensure_leads` refuses a lead whose approved copy is missing, and its comment
says why: "a lead staged without them produces an email with an empty subject
and an empty body, and nothing in the staging readback would have shown it".
That refusal is the thing keeping this safe. **Do not weaken it to make an
empty `body_4` acceptable** - the distinction you need is between a variable
the SEQUENCE reads (must be approved and non-empty) and one it does not
(must be empty). Encode that distinction; do not relax the check.

Second trap: do not regenerate, rewrite or "improve" any copy. The approved
CONTROL text exists and is fingerprinted. Your job is to make the provider
hold exactly it.

Third trap: campaign 485 holds the canonical approved state and 0 sent. Do not
create a campaign, do not change the sequence, do not add or remove a lead, do
not touch the cap.

## WHAT YOU MAY NOT DO

- Do NOT activate, resume or start anything. No `resume_campaign`.
- Do not create a campaign or a lead. The ten leads exist.
- Do not change the sequence, the cap, the schedule or the sender.
- Do not set, clear or re-take any approval. They are correct now.
- Do not weaken `_ensure_leads`' empty-copy refusal.
- Never commit an email address, a contact name, a company name, a domain or
  any copy text. Hash every identifier; report copy as match/mismatch only.

## FILES ALLOWED

    src/bisonfactory.py
    tests/test_lead_variables.py   (new)
    docs/LEAD-VARIABLES-2026-09-16.md   (new, no copy text)
    scripts/task217_*.py

## FILES FORBIDDEN

    src/providerwrites.py   src/approve.py   src/approval.py   config/

## DELIVERABLE

The stale-variable clearing implemented and its mechanism named; all ten leads
refreshed against the corrected approvals; a provider readback showing 30/30
exact matches and zero non-empty out-of-range variables, per lead, hashed; and
the regression test green with the exit code read off the process.
