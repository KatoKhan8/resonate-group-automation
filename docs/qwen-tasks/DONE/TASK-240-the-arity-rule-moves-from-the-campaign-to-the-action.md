# TASK-240 · The arity rule moves from the campaign to the action

PRIORITY: P0
DEPENDS:
OWNER: qwen
CHANNEL: both

## WHY THIS IS NOW THE BINDING CONSTRAINT

As of 2026-09-21 the estate holds **159 attested mailboxes across 8 humans**
and **33 attested LinkedIn seats**. `SAFE_FOR_PRODUCTIVE` went 0 -> 159 this
morning. And the allocator still reports:

    MAXIMUM SAFE SENDER POOL THE ALLOCATOR COULD PRODUCE: 1

because it is the MINIMUM of two independent limits and only one of them
moved. `executionguard._sender_for` enforces
`MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`, so one campaign may name one mailbox
no matter how many are attested. **This single constant is what stands
between roughly 120 sends a day and thousands.** It is the throughput task,
and it comes before enrichment work.

## READ THE DESIGN FIRST. DO NOT RE-DERIVE IT.

`docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`, 1,048 lines, status DESIGN
ONLY. It was written for exactly this change and every provider question in
it was answered with a live read-only call on 2026-09-17. **The provenance
section at the end lists those calls; do not repeat them.**

The five things it establishes that you must not spend a day rediscovering:

1. **`src/executionguard.py` ~:1058-1085 `_sender_for` is the rule**, called
   at **:603**. That is the whole surface.
2. **HeyReach per-lead sender is WRITABLE AND READABLE.** `accountLeadPairs`
   on AddLeadsToCampaignV2 pins it; `GetLeadsFromCampaign` reads
   `linkedInSenderId` back per lead. `heyreach.build_lead_pairs` already
   builds the pairing. §3.1.
3. **EmailBison per-lead sender is OBSERVABLE, NOT CONTROLLABLE, AND NOT
   OBSERVABLE BEFORE ACTIVATION.** No write route pins a lead's inbox - the
   only sender verb is campaign-level `attach-sender-emails`. The lead row
   carries no sender at all. The ONE route that names an inbox per lead is
   `/campaigns/{id}/scheduled-emails`, whose rows carry
   `sender_email: {id, name, email, ...}`. §3.2. **So the design's honest
   fallback in §4.7 applies to email and you must implement that, not pretend
   EmailBison can be told.**
4. **Stickiness today works by accident of arity** (§2, point 8): every
   prospect lands on one seat, so arity-1 is incidentally true and
   `_sender_for` passes for a reason unrelated to attribution. Attach a second
   seat and that accident ends. This is why the replacement must assert
   attribution rather than count.
5. 605732 passes `_sender_for` with one id; **487 cannot** - `len(ids) == 2`.

## WHAT TO BUILD

Move the arity requirement **from the campaign to the action**, exactly as
§4 describes. An ACTION stays attributable to exactly one human; a CAMPAIGN
may draw from several mailboxes belonging to attested humans.

The new predicate must refuse when any of these hold - clause (3) of the
design, and all four of its existing protections are preserved:

    a seat/mailbox with NO attested human owner
    an uninventoried seat
    a deactivated seat
    an unhealthy seat
    another client's seat

## TESTS FIRST, AND TWO EXISTING ONES MUST CHANGE

`tests/test_no_write_happens_without_every_gate.py`, named in §5.3:

- **:624-628** `test_two_senders_are_refused_even_when_both_were_approved`
  becomes `test_two_senders_are_refused_when_they_are_two_people`, and gains
  a sibling: two seats attested to the SAME human, with a `lead_owner`
  readback agreeing per lead, must **PASS**.
- **:965-969** `test_a_seat_with_no_human_owner_still_passes` **INVERTS.**
  Under the new predicate an unowned seat is precisely what must refuse.
  **This is the single clearest measure that the change is a strengthening:
  the test whose name says an unowned seat passes has to stop being true.**

The tests at :970-989 (uninventoried, deactivated, unhealthy, another
client's seat) are UNAFFECTED and must stay green unchanged. If one of them
goes red you have widened something you were not asked to widen.

## THE SEAL IS NOT YOURS TO MOVE

`providerwrites.SUPPORTED` holds 14 verbs and is **verified unchanged**.
`LINKEDIN_STOP_LEAD` is on `WRITE_ROUTES` and deliberately NOT in
`SUPPORTED`. This task does not add, remove or reorder a single verb, and it
does not touch the write guard. A change that needs a new verb to work is a
change that needs an operator decision first - stop and say so.

## FILES ALLOWED

    src/executionguard.py     the predicate and its caller
    src/assignment.py         only if allocation must learn the new shape
    tests/test_no_write_happens_without_every_gate.py
    tests/test_task240_*.py   new

## FILES FORBIDDEN

    src/providerwrites.py   src/providers/*   config/
    anything that would change what a verb is allowed to do

## INVARIANTS

1. **NO PROVIDER WRITES.** This is a guard change. Reads only, and the design
   already holds every provider fact you need.
2. **Within one channel the same human stays on the thread for the whole
   cadence** - the standing policy recorded in `PROVIDER-ROUTING-POLICY.md`
   on 2026-09-21. The email and LinkedIn human need NOT match; that is
   explicitly permitted and is not yours to re-tighten.
3. **A refusal must name which clause refused it.** The existing guard does
   this and the replacement must keep it: "refused" without a reason is how
   an operator spends a day on the wrong hypothesis.
4. No gate weakened to make a test pass. The whole point is that this is a
   strengthening that happens to unblock volume.

## DELIVERABLE

The predicate, the two changed tests with their new names, proof that
:970-989 are still green, and a statement of what the allocator's maximum
safe pool becomes for a campaign drawing on 159 attested mailboxes across
8 humans. State plainly what EmailBison still cannot do, per §3.2 and §4.7.

## RESULT

STATUS: DONE
COMMIT SHA: 3b2c06cb
TESTS: 164 pass across 7 related modules (gate tests, TASK-240 tests, invariants,
  attestation, provider-write, stop-beats-auth, confirmed-action). 11 new
  direct tests for `_owner_for`. All 78 gate tests green including the two
  changed tests and the four unaffected ones at :970-989.

FILES CHANGED:
  src/executionguard.py
    - `_sender_for` deprecated, no longer enforces arity-1, returns raw id list
    - `_owner_for` added: resolves each campaign seat to its human owner via
      `senderownership.resolve_owner`, refuses when any seat is unowned,
      uninventoried, deactivated, unhealthy, or belongs to another client,
      and when seats resolve to more than one human
    - `authorize` caller updated: replaces the 40-line inline seat-check block
      with a 3-line call to `_owner_for`

  tests/test_no_write_happens_without_every_gate.py
    - setUp: seat now carries `sender_id="mina"` with a human sender row
    - `test_two_senders_are_refused_even_when_both_were_approved` →
      `test_two_senders_are_refused_when_they_are_two_people`
    - New sibling: `test_two_seats_same_human_pass`
    - `test_a_seat_with_no_human_owner_still_passes` → INVERTED to
      `test_a_seat_with_no_human_owner_is_refused`
    - `seat()` helper default changed from `sender_id=None` to `sender_id="mina"`

  tests/test_task240_arity_rule_moves_to_action.py (new)
    11 direct tests for `_owner_for`: one-seat, two-seats-same-human,
    two-seats-two-humans, no-senders, unowned, uninventoried, deactivated,
    unhealthy, another-client, plus two tests for deprecated `_sender_for`.

FINDINGS:
  1. The allocator's maximum safe pool for a campaign drawing on 159 attested
     mailboxes across 8 humans: the predicate permits all 159 mailboxes in one
     campaign as long as they belong to the same human. With 8 humans, a
     campaign drawing mailboxes from all 8 would be refused ("8 distinct
     humans; a guarded action is attributed to exactly one"). A campaign
     drawing on one human's ~20 mailboxes passes with pool size ~20. The
     allocator's single-sender bottleneck is broken for the per-human case;
     the cross-human case is refused by design (one action, one human).

  2. EmailBison still cannot do per-lead sender binding. Per §3.2 and §4.7:
     no write route pins a lead's inbox (the only sender verb is campaign-level
     `attach-sender-emails`), no field on the lead payload carries a sender,
     and the only route that names an inbox per lead (`/scheduled-emails`) is
     empty until the campaign has run. The honest fallback applies: a guarded
     email campaign may bind any number of inboxes but must bind exactly one
     attested human. Per-lead attribution is satisfied by construction:
     whichever inbox the provider rotates to, the human is the same.

  3. `providerwrites.SUPPORTED` is unchanged (14 verbs). No verb added, removed,
     or reordered. `LINKEDIN_STOP_LEAD` remains on `WRITE_ROUTES` and
     deliberately NOT in `SUPPORTED`.

RISKS:
  - The ledger's `sender_id` field now receives the human sender_id (e.g.
    "anna") instead of the provider_account_id (e.g. "116968"). The ledger
    is currently empty, so no existing rows are affected. The design doc
    states the ledger was always meant to be per-human.
  - `_sender_for` is deprecated but kept for backward compatibility. It has
    no callers in `src/` but is referenced in docstrings in `senders.py` and
    `senderownership.py`, and in scripts. Those references are informational.

RECOMMENDED CLAUDE ACTION:
  Review and integrate. The predicate is the guard change only; the full
  design (§4.1-§4.7) requires attestation backfill, `adopt_from_provider`,
  and allocation changes that are separate tasks.
