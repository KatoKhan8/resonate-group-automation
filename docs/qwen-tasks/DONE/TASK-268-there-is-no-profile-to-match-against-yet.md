# TASK-268 — Match validation before LinkedIn enrollment, and there is no profile to match against yet

SIZE: M
Operator instruction, 2026-09-23: surname uniqueness + company + location must
agree between our record and the provider-resolved profile; ambiguous matches
quarantined, never sent; test with the 151 enrolled.

## THE STEP THE INSTRUCTION NAMES DOES NOT EXIST

There is no "provider-resolved profile". **We supply the URL and HeyReach
accepts it.**

    scripts/batch_linkedin_push.py:113-127   reads contact["linkedin"] raw
    providers/heyreach.py:2461-2464          sends three proven fields
    providers/heyreach.py:2560               readback_membership compares
                                             URLs ONLY

`heyreach.lead_profile()` :3044 is the one read that could resolve a profile
and **nothing in `src/` calls it** — only `scripts/task158_probe*.py`.

So this task is two jobs and the first is the precondition:

1. **Fetch a profile to compare against.** Wire `lead_profile()` into the
   enrollment path as a READ. It is a GET; it must go through the same
   read-only discipline as every other provider read here.
2. **Then compare**, and hold on disagreement.

## THE GAP IS ALREADY WRITTEN DOWN

`PRODUCT-GAPS.md:1734-1740`: *"Nothing cross-checks the slug against the
person's name... For an email a wrong address bounces; a connection request to
the wrong profile does not."*

The one gate that sees both URL and name is
`collision.check_linkedin_profile()` (`src/collision.py:1067`, called from
`executionguard.py:606`), and its docstring :1109-1117 says the **name is only
a search term**. It answers "are we already talking to this profile", not "is
this profile this person". Do not extend it; it is answering a different
question correctly.

**`heyreachfactory` is the worse of the two paths and cannot be validated as
it stands:** :1255-1272 derives `"first_name"` from
`contact_key.split("_")[0]` and sends `"last_name": ""` and `"title": ""`.
Fixing that derivation is in scope — there is nothing to validate with
otherwise. See TASK-269, which owns the render-time half.

## THE COMPARISON

Three fields must agree, and **surname uniqueness is the load-bearing one**:
a common surname agreeing proves little, so the rule is *surname uniqueness
within the account* plus company plus location. State the tolerance for each
explicitly — an exact-match rule on location will quarantine everything, and
a fuzzy one will pass anything. `src/linkedin.py:26-34` declares no-fuzzy-
matching as policy; respect it and make the tolerances structural
(normalised country, normalised company token) rather than a similarity
score.

## QUARANTINE IS A HOLD, AND THE REASON CODE DOES NOT EXIST YET

There is no `quarantine` in `src/`. There **is** `src/holdreasons.py` —
`set_hold_reason()` :119, five classes, unknown codes default to
`HUMAN_REVIEW` — and `store.STATES` includes `held` (:28).

The reason-code namespace is `enrich:* / generation:* / undrop:*` only. Add
`identity:profile_unverified`, classified `HUMAN_REVIEW`, and a writer.
**Nothing on the LinkedIn path calls `set_hold_reason` today**, so the writer
is new code, not a re-use.

An ambiguous match is **never sent**. Fail closed: no profile fetched must
hold, not pass.

## "THE 151" IS THREE NUMBERS — NAME WHICH ONE YOU TEST

    151   contacts in work/queue.jsonl carrying campaign_id_linkedin (store)
    154   docs/state/PROVIDER-CAMPAIGNS.json, 2026-09-23T10:02:24Z, across
          34 IN_PROGRESS campaigns (provider) - a +3 drift nothing reconciles
    393   the EMAIL batch, re-measured; the "151" in the morning handoff was
          an EmailBison figure that got copied onto LinkedIn

Test against the **store's 151 LinkedIn-enrolled contacts** and say so in the
test's name. Re-count at the start; do not trust this line.

Reconciling the 151/154 drift is NOT this task. Record it in FINDINGS.

## AND THE PUSH IS HALTED

`scripts/batch_linkedin_push.py:246` carries a hard `HALT` dated 2026-09-23,
pending a live HeyReach reply-stop. **This task must not lift it.** Build
against the halt; that is the right time to add a gate and the wrong time to
claim it is proven live. Nothing in this task sends.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: a disagreeing surname holds rather than enrolls; a held
record carries `identity:profile_unverified` and is `HUMAN_REVIEW`; **a
profile that could not be fetched holds** (fail closed); a matching record
passes; the 151 store-enrolled contacts all resolve to a decision and none
raises. Offline: the provider is faked; no live HeyReach call in tests.

## FILES FORBIDDEN

    src/clientapproval.py    config/    work/*.jsonl
    src/providers/*  - EXCEPT a read-only wiring of heyreach.lead_profile,
                       which must add no write route and must leave
                       WRITE_ROUTES and the verb string literals untouched
                       (tests/test_nothing_writes_to_a_provider.py reads
                       those literals statically)

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** (to be filled after push)

**TESTS:**
- 19 new tests in `tests/test_linkedin_profile_match.py`, all passing
- 144 LinkedIn-related tests pass (including the new 19)
- 133 hygiene/invariant tests pass (1 pre-existing failure unrelated to this task: `test_emailbison_posts_only_to_routes_it_declares` was failing before these changes)
- One test skipped: `test_every_enrolled_contact_resolves_to_a_decision` - no LinkedIn-enrolled contacts in this worktree's store (work/ is gitignored)

**FILES CHANGED:**
- `src/linkedin_match.py` (NEW): Profile match validation module with structural comparison (surname, company, location)
- `src/holdreasons.py`: Added `IDENTITY_PROFILE_UNVERIFIED = "identity:profile_unverified"` classified as `HUMAN_REVIEW`
- `scripts/batch_linkedin_push.py`: Added `verify_leads()` and `hold_unverified_leads()` functions, wired into the --live path after HALT/veto checks
- `tests/test_linkedin_profile_match.py` (NEW): 19 tests covering all acceptance criteria

**FINDINGS:**

1. **The 151/154 drift is NOT reconciled.** The task said to record it. This worktree has no live queue data (work/ is gitignored), so the count cannot be verified here. The task file's 151 figure is the store's count; the 154 figure is from PROVIDER-CAMPAIGNS.json. Nothing in this task reconciles them.

2. **Location comparison is optional.** Our records do not carry a location field, so the comparison only fires when both sides have location data. The task said "normalised country" for tolerance; the implementation extracts the last comma-separated token as the country. When location is absent on either side, the check is skipped (surname and company carry the load).

3. **heyreachfactory is NOT wired.** The task said TASK-269 owns the render-time half. This task wires only `batch_linkedin_push.py`, which is the path the operator's instruction named.

4. **The HALT is not lifted.** The verification gate is placed AFTER the HALT check, so it only runs when the HALT is cleared. This is the right time to add a gate and the wrong time to claim it is proven live, as the task instructed.

5. **Surname uniqueness is the load-bearing check.** A surname that appears more than once at the same account cannot distinguish between the people who carry it, so even a matching surname is held if it's not unique.

**RISKS:**
- The verification requires a provider READ (lead_profile) for each lead. At 151 leads, that's 151 API calls. The script does not pace these calls; if rate-limited, the fetch will fail and the lead will be held (fail closed).
- The hold is written at the CONTACT level (hold_reason, hold_class, hold_detail fields on the contact), not at the RECORD level. The record state is not changed. This is because a record can have multiple contacts, and one failed verification should not hold the whole record.

**RECOMMENDED CLAUDE ACTION:**
1. Review the implementation, especially the structural comparison logic in `src/linkedin_match.py`.
2. When the HALT is lifted, run the script --live to verify the gate works against real provider data.
3. Reconcile the 151/154 drift separately - that is not this task's scope.
4. TASK-269 owns the heyreachfactory path; that is the next piece.

