PRIORITY: P0
DEPENDS:

# TASK-203 - 159 contacts with an address and no verification at all

## WHERE THIS SITS

TASK-196 went looking for a broken parser and found something better. The
parser was fine; its gate had never been opened. And the number everybody had
been repeating was wrong:

    240   contacts with an email address
    159   have NO verification evidence at all - they never entered the
          waterfall
     81   did enter; all 81 carry Deliverable=error, 80 of those
          ContractNotVerified, and 68 were verified anyway via
          ContactOut + Reoon
     10   accept_all_uncleared
      3   held

TASK-194's "143 contacts held by insufficient confirmations" came from the
stale snapshot and does not survive contact with this. Exactly ONE contact
would benefit from a working Deliverable.

So the real question is the 159. They have addresses. Verification is what
stands between an address and a campaign - `CLAUDE.md`: "No email is generated
for an unverified address." And nothing verified them.

This has a precedent. TASK-160 asked why 250 records never reached ICP and the
answer was not a defect: no runner was ever invoked. Check that first.

## THE QUESTION

1. **Why did 159 contacts never enter the waterfall?** Test the cheap
   explanation before any other: was the verification stage simply never run
   over them? Look for the run in `EXECUTION-LOG.md`, in the event log, in the
   waterfall ledger. If a runner was invoked, say when and what it selected.
2. **If a runner DID run and skipped them, find the predicate.** Read the
   selection in `src/run.py` and `src/verification.py`. Candidates worth
   ruling in or out explicitly: the record is not in a state verification
   looks at, the contact lacks a field the selector requires, a lane filter,
   a cap that stopped the run short, a spend ledger refusal, or the contact was
   added after the last run.
3. **Distinguish the two populations inside the 159.** Contacts whose record
   never reached the stage that verifies, versus contacts whose record did and
   who were passed over individually. Those are different defects and only the
   second one is a selection bug.
4. **What would verifying them cost?** Per contact, which providers the
   waterfall would call and how many credits, and the total for 159. Note that
   `DELIVERABLE_RESULT_SHAPE` is unset by deliberate operator decision as of
   2026-09-16, so Deliverable is currently refused locally - give the cost both
   with and without that leg.
5. **Do NOT verify them.** Report the cost and the cause. A 159-contact
   verification run is a credit spend and it is the operator's.

## THE TRAP

`spent=0` and `skipped` and `refused` and `never selected` all look identical
in a summary line, and this repository has already been misled by exactly that:
the free-path run's own output showed `refused=[...]` entries that were the cap
working correctly, next to records that were never reached at all. Distinguish
refused-by-a-gate from never-offered-to-the-gate, per contact, and say which
field you read to tell them apart.

Second trap: do not relax `required_confirmations: 2`. TASK-196 measured that
relaxing it to 1 would admit 3 more contacts - three - and it is the rule that
keeps this system from mailing an address nobody confirmed.

## WHAT YOU MAY NOT DO

- No paid provider calls. No verification run, no credits. Reads of local state
  and the ledger only.
- No provider writes.
- Do not change the confirmation policy, a threshold, or
  `DELIVERABLE_RESULT_SHAPE`.
- Do not move contacts or records between states.
- Read live state, name the file, quote its record count. The snapshot is stale
  and is what produced the wrong number this task replaces.
- Never commit an email address, a contact name or a domain.

## FILES ALLOWED

    docs/NEVER-VERIFIED-2026-09-16.md   (new)
    scripts/task203_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

Whether a runner was ever invoked over them, the selection predicate that
skipped them if one did, the two populations separated with counts, the cost of
verifying 159 with and without the Deliverable leg, and the field that
distinguishes refused from never-offered.
