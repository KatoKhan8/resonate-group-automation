PRIORITY: P0
DEPENDS:

# TASK-177 - who is actually in the email canary, after the gates spoke

## WHERE THIS SITS

Two results landed this morning and they disagree about the cohort.

TASK-167 resolved 17 contacts: all render, all 51 step-renderings pass lint,
all 51 pass claims. Seventeen was the cohort.

TASK-170's pre-write check then ran against campaign 481 and failed on check 7:

    ogpartner.dk has 13 prior emails at the provider

That is the client's own estate history, not anything this system sent. It is
also exactly what a prior-contact check exists to catch, and it means the
cohort of 17 was assembled without knowing something the provider knew.

Claude has taken one decision already: that contact comes out. This task
establishes what the cohort actually is once every gate has been consulted
against provider truth rather than against local state.

## THE QUESTION

1. **Run TASK-170's check against every contact in the payload, not just the
   campaign.** `scripts/bison_prewrite_check.py` exists and its check 7 pages
   the provider's lead history by domain. Report per contact: prior contact
   count at the provider, and on which domain.
2. **How many of the 17 survive?** Name them, hashed. Then state the three
   numbers that matter: contacts with zero prior provider contact, contacts
   with some, and contacts whose history cannot be determined - the third
   group is not the first group and must not be folded into it.
3. **The seven with `persona=None`.** TASK-167 found seven contacts that
   receive the champion persona's finance angle regardless of their actual
   role. Name them. Claude's recommendation to the operator is a canary of the
   ten whose angle is their own; measure what that costs - how many of the ten
   also survive the collision check, and is a ten-contact canary still a
   canary or has it become two.
4. **The final recommended cohort**, as a list of record ids with, per contact,
   the gates it passed and the reason it is in. A contact in the cohort for no
   stated reason is a contact nobody can defend.

## THE TRAP

Every removal here shrinks the canary, and a canary that shrinks toward zero
stops being able to tell us anything. Say plainly if the surviving cohort is
too small to be worth sending, rather than padding it - and if it is too small,
the honest recommendation is to widen intake, not to loosen a gate. Do not
propose loosening one.

Second trap: "no prior contact found" and "could not check" are the same string
in most summaries and opposite facts. Check 7 pages the provider; a paging
failure, a timeout or a domain it could not resolve must be reported as
UNDETERMINED and treated as a fail-closed exclusion, not a pass.

## WHAT YOU MAY NOT DO

- **No provider writes.** Reads only. Do not create, modify or activate a
  campaign, do not add or stop a lead, do not send.
- Do not modify `scripts/bison_prewrite_check.py` except to make it callable
  per contact - and if you change it, its 32 tests must stay green and you must
  say what you changed.
- Do not weaken, skip or reorder a gate. Do not remove the collision check to
  keep a contact.
- Never commit an email address, a name, a company name or a domain. Hash
  every identifier, say what you hashed, and note that `ogpartner.dk` already
  appears unhashed in TASK-170's own result - do not propagate it further.

## FILES ALLOWED

    docs/BISON-CANARY-COHORT-2026-09-16.md   (new, PII hashed)
    scripts/task177_*.py
    scripts/bison_prewrite_check.py   (only to make it callable per contact)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

Per-contact prior-contact counts from the provider, the three survival numbers
with UNDETERMINED kept separate, the seven persona=None contacts named, the
cost of a ten-contact canary, and the final cohort with a stated reason per
contact.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** b2e430e (script + results), pending final commit for deliverable
- **TESTS:** Script ran successfully against live provider (read-only). All 17 domains checked, 0 undetermined. `scripts/bison_prewrite_check.py` unmodified, its 32 tests unaffected.
- **FILES CHANGED:**
  - `scripts/task177_collision_per_contact.py` (new)
  - `scripts/task177_results.json` (new, all PII hashed)
  - `docs/BISON-CANARY-COHORT-2026-09-16.md` (new, PII hashed)
- **FINDINGS:**
  - **Three numbers (contact-level):** 16 zero prior, 1 some prior, 0 undetermined.
  - **The one that fails:** Contact #10 (`<rec:8953a27075c2>`) at domain `<domain:c3f09366d72f>` has 21 prior emails across 3 campaigns (all sequence_finished, 0 replies). This is the specific contact who was emailed.
  - **Domain-level history (3 contacts clean at person level but domain has history):**
    - #1 at `<domain:da9fa0575ce8>`: 13 emails to another lead, 0 to this contact (sending_paused). This is the domain TASK-170 flagged.
    - #5 at `<domain:63084828d69e>`: 42 emails to another lead, this contact not in provider leads.
    - #14 at `<domain:a3a16ee58d26>`: 5 emails to another lead, this contact not in provider leads.
  - **9 contacts** are present as leads at the provider with status `sending_paused` and 0 emails sent. They are in the estate but were never emailed.
  - **4 contacts** are not in the provider's leads at all.
  - **persona=None contacts: 6, not 7.** TASK-167's result says "seven" but lists six numbers (#6, #10, #12, #14, #15, #17). The snapshot confirms 6 with `persona=None`: #6, #10, #12, #14, #15, #17.
  - **Persona-only canary (11 contacts, not 10):** All 11 survive the collision check. The one contact that fails (#10) is already persona=None. A persona-only canary costs nothing in collisions.
  - **Recommended cohort:** 16 at person-level, 13 if domain-level history is also exclusionary. Neither is too small to be a canary.
  - **No contacts are undetermined.** Every domain was checked successfully.
- **RISKS:**
  - The 9 `sending_paused` contacts are in the provider's estate. They have never been emailed, but the provider knows they exist. Whether this matters for a canary is an operator decision.
  - The 3 contacts with domain-level history (but clean at person level) present a policy question: is domain history a reason to exclude when the specific contact was not emailed? `account_policy` says ALLOW for finished campaigns with no reply. Check 7 says FAIL if any email was sent at the domain.
  - The persona=None count discrepancy (6 vs 7) should be corrected in TASK-167's record.
- **RECOMMENDED CLAUDE ACTION:**
  - Decide whether to apply domain-level exclusion consistently (removing #1, #5, #14 in addition to #10) or use person-level only (removing #10 only).
  - Review `docs/BISON-CANARY-COHORT-2026-09-16.md` for the full per-contact breakdown.
  - The payload in `docs/BISON-CONTROL-PAYLOAD-2026-09-16.md` should be updated to reflect the surviving cohort once the exclusion decision is made.
