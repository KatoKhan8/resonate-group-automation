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
