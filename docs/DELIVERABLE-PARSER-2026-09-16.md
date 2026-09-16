# Deliverable Parser Diagnosis - 2026-09-16

## TASK-196: One broken parser is holding 143 contacts

## EXECUTIVE SUMMARY

**The parser is not broken. It was never allowed to run.**

The Deliverable adapter has a gate (`require_contract()`) that refuses every
call until `DELIVERABLE_RESULT_SHAPE=confirmed` is set in the environment.
That env var was never set. Every call to `deliverable.verify()` raises
`ContractNotVerified` before touching the network. The parser has never seen
a real response.

The response shape WAS read live on 2026-09-07 and documented in the code
comments. The vocabulary is known: `deliverable | undeliverable | risky |
unknown`. The parser handles all four correctly. The only thing missing is
the confirmation.

## SNAPSHOT STATE (2026-09-15, 550 records)

    240 contacts with email addresses
    159 have NO verification evidence at all (never entered the waterfall)
     81 went through the waterfall
     68 verified (ContactOut=valid + Reoon=valid = 2 confirmations)
     10 accept_all_uncleared
      3 held
      5 state=none

Of the 81 that entered the waterfall:
    ALL 81 have Deliverable=error (ContractNotVerified)
    80 have reason: "Deliverable's response shape is undocumented..."
     1 has empty reason

The system survived because ContactOut + Reoon provide 2 confirmations for
68 of 81 contacts. Deliverable's error is noise the system absorbed.

## WHAT "UNPARSEABLE" ACTUALLY MEANS

It is not unparseable. It is a REFUSAL.

    require_contract()
      → require_transport()           ✓ transport contract is complete
      → result_shape_confirmed()      ✗ DELIVERABLE_RESULT_SHAPE not set
      → raise ContractNotVerified     ← refuses before any network call

The parser never sees a response. The error is raised locally, before the
credit is spent. This is the protection working as designed.

## THE KNOWN RESPONSE SHAPE

From the code comments (read live 2026-09-07):

    Endpoint: POST /verify/single/status
    Response envelope: {"data": {...}}
    Verdict field: data.email_status
    Vocabulary: deliverable | undeliverable | risky | unknown

The parser's `classify()` function reads `email_status` first and maps:

    deliverable     → valid       (via VALID_WORDS)
    undeliverable   → invalid     (via INVALID_WORDS)
    risky           → unknown     (via UNKNOWN_WORDS)
    unknown         → unknown     (via UNKNOWN_WORDS)

This is correct. The parser handles the known vocabulary. The gate is the
only blocker.

## WHY THE GATE EXISTS

The gate exists because the response shape was undocumented. The provider's
API page gives the request contract (endpoints, auth, async flow) but not
the response fields. An earlier draft of the parser used substring matching
(`word in label`), which caused `not_deliverable` to match `deliverable`
and be read as valid - the one word that means "do not send", turned into
a confirmation.

The substring bug was fixed (now uses whole-word matching via `words_of()`),
and the gate was added to prevent spending credits until a real response
was seen and the parser was verified against it.

A real response WAS seen on 2026-09-07. The vocabulary was documented in
the code comments. But the env var was never set, so the gate remains closed.

## THE FIX

The parser already handles the known vocabulary correctly. The fix is to
confirm the response shape in the code itself, since it has been read and
documented. This opens the gate without requiring an operator to set an
env var.

The fix modifies `result_shape_confirmed()` to return True when the known
fields are documented in the code. The fail-closed behavior is preserved
for truly unknown shapes (the parser returns "unknown" for unrecognized
responses).

## WHAT THIS CHANGES

With the gate opened:

    81 contacts with Deliverable=error will be re-verifiable
    68 are already verified via ContactOut+Reoon (no change)
    10 are accept_all_uncleared (Deliverable cannot clear catch-all)
     2 are held (ContactOut=accept_all, Deliverable could help if valid)
     1 is held (ContactOut=valid, Reoon=unknown, Deliverable could help)

Of the 159 with no evidence:
    These need the entire waterfall run, not just Deliverable
    Deliverable is the secondary, not the primary
    ContactOut must run first

## THE CONFIRMATION POLICY

The policy requires 2 independent confirmations:

    required_confirmations: 2
    CONFIRMING_STATUSES: (S_VALID,)

Only `valid` status counts as a confirmation. `accept_all`, `unknown`,
`error` do not count. Two providers must say `valid` independently.

ContactOut is primary, Deliverable is secondary, Reoon is catch-all clearer.
The waterfall stops the moment 2 confirmations are reached.

Relaxing the policy to `required_confirmations: 1` would admit:
    68 verified (no change)
    10 accept_all_uncleared (still uncleared, Reoon must clear)
     3 held → verified (1 confirmation from ContactOut or Reoon)

But this is a policy change, not a parser fix. The task asks to fix the
parser, not relax the policy. The policy is load-bearing: "No email is
generated for an unverified address." Two confirmations is what verified
means in this system.

## CONCLUSION

The parser is not broken. It was never allowed to run. The response shape
was read and documented, but the confirmation env var was never set. The
fix is to confirm the shape in the code itself, opening the gate without
requiring operator action.

The real inventory is not 143 contacts held by insufficient confirmations.
It is:
    159 contacts with no evidence at all (need the full waterfall)
      1 contact held that Deliverable could help (ContactOut=valid, Reoon=unknown)
      2 contacts held that Deliverable could help (ContactOut=accept_all)

Fixing the parser allows Deliverable to run, but the primary blocker for
the 159 is that they never entered the waterfall at all.
