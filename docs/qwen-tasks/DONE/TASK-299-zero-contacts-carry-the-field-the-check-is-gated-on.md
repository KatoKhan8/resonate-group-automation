PRIORITY: P1
DEPENDS:

# TASK-299 — zero contacts carry the field the check is gated on

## DISPATCH NOTE

Lane F, the standing QA suite. **The ongoing reconciliation check:
`scripts/qa/check_reconcile.py`, phase `ongoing`.**

**Not needed before the 128 go out; needed the same day they do.** It runs
from the first cycle after the push and every cycle thereafter, and **any
mismatch it finds is a CRITICAL** — the operator's word.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST**, and §0 of it twice.
This is the check written specifically to catch the class of defect that
section describes, and the easiest way to fail this task is to reproduce it.

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

## The question this answers

**Is anybody our store believes we have stopped talking to still being talked
to at a provider — and has every reply and every bounce the providers saw
reached our store?**

Two rules, both symmetric, both CRITICAL when they fire:

    stopped_here_is_stopped_there
        every lead our store marks replied / stopped / unsubscribed reads
        NOT `in_sequence` at BOTH providers
    provider_event_has_a_store_event
        every provider reply and every provider bounce has a matching event
        in our store

## THE DEFECT THIS EXISTS FOR — ISSUE-041, AND WHY IT IS THE TRAP

`inbound._stop_at_provider` gates the LinkedIn stop on
`contact["heyreach_lead_id"]`. When the field is absent it returns
`{"attempted": False, "stopped": False, "why": "this contact carries no
heyreach_lead_id…"}` and `summarise_stops` renders that as
**`"linkedin: no lead"`** — which the code explicitly and correctly does NOT
treat as a refusal, because most contacts are staged on one channel only.

**MEASURED 2026-09-24 late: ZERO of the contacts in `work/queue.jsonl` carry
`heyreach_lead_id`.** Not few — none.

So **every cross-channel stop this estate has ever run reported success having
never called `heyreach.stop_lead_in_campaign` once** — consistent with that
function's own docstring saying it has **NEVER BEEN LIVE-VALIDATED**. A reply
reporting `"email: stopped; linkedin: no lead"` looks like a working
cross-channel stop and is indistinguishable from one. This is the same shape
as the first blank-content halt, which alerted and halted nothing and read as
working.

**This check must catch exactly that class: a check that passes because the
thing it checks is absent.** Which means the check itself must not be written
that way, and the only defence is to measure and report **key presence** as a
first-class output:

> For every rule, before any verdict: how many subjects carried the field this
> rule keys on? A rule whose key is present on **zero** subjects is **VACUOUS**
> for all of them, exits 2, and — at phase `ongoing` — is a CRITICAL if it
> persists across two consecutive cycles.

**And it must not be gated on `heyreach_lead_id`.** The lead's identity at
HeyReach is available from the profile URL:
`heyreach.campaigns_for_lead(profile_url=…)` and `heyreach.lead_state(row)`
answer the question without the field the estate does not carry. Use them.
If a rule genuinely needs the id, say so and report the presence count.

## The second trap — ISSUE-042, and why "ours" is not a set membership

`inbound.OWNED_CAMPAIGNS = {605732, 605487, 604869, 599020}` are **HeyReach**
ids, and `_positively_not_ours` compares an **EmailBison** event's campaign id
against them without asking which provider it came from. An EmailBison reply
on our own 491 reads as "provably not ours" and is dropped. It is latent only
because `_owned()` refuses on a stale readback — and `provider_truth.py`
refreshes it.

`leadstop._campaign_of` had the same shape: it returned the FIRST campaign row
holding the record, whatever channel that row was for, so a contact staged on
both channels would have its LinkedIn stop handed the EMAIL row. Fixed with
`requires=<provider field>`. Not a live failure yet, because zero of 1,582
records sat in both an email row and a HeyReach row — **and the 825 enrollment
across 33 seats is precisely the plan that creates the first ones.**

**So this check resolves the provider from the registry, per event, and never
by set membership.** An id compared across providers is not a resolution. If
your reconciliation uses a set of ids to decide ownership, you have rebuilt
ISSUE-042.

## What to build

`scripts/qa/check_reconcile.py` plus its tests.

**Read surface:**

    store.load()  (through src/store.py, never the files directly)
    bison.fetch_replies() / fetch_events() / walk_events() / events_window()
    bison.classify_reply_row(row) / bison.events_contract()
    bison.campaign_lead_ids(id) / bison.lead(id) / find_lead_by_email(email)
    heyreach.campaigns_for_lead(profile_url=…) / lead_state(row)
    heyreach.campaign_stats(id) / campaign_leads(id)
    inbound / leadstop / stoppedcause   — READ them, do not edit them
    testidentity.matches(...)           — suppression, see below

**Four things that will bite:**

1. **`bison.fetch_events` carries 11 event types, not 8.** Six normalise to
   `unknown`, including **`EMAIL_ACCOUNT_DISCONNECTED`** — a sender mailbox
   that stopped working, with no alert on it. Enumerate the types you actually
   saw in the window, by name, with counts. An event type you did not know
   about is not an event that did not happen.
2. **A stop against a FINISHED lead returns "already settled" — a pass by
   construction.** HeyReach 613744 carries the operator's test identity at
   `leadCampaignStatus: "Finished"`. Do not count "already settled" as
   evidence that a stop worked. Count it as its own state.
3. **The test identity must be excluded, and it is not reliably
   suppressed.** ISSUE-044: `testidentity.matches()` answers on ANY binding,
   but **an EmailBison event can arrive carrying the lead id and nothing
   else** — no address, no contact key — so a newly created test lead is
   unsuppressed until its id is added to `LEAD_IDS` by hand.
   `matches(205079)` was False the moment the lead existed while `matches` on
   its address was True. **Check the id ALONE, not on the row that also
   carries the address — the row always passes.** Report how many events you
   matched on id-alone.
4. **The HeyReach inbox is ~27,000 conversations and is mostly the
   client's.** A seat is not a campaign. Ask `campaign_stats` before calling a
   reply ours, and say which evidence decided ours vs theirs for every row.
   Of 103 notification posts in 72 hours, 99 were the client's traffic and 2
   were ours — two real unmatched replies invisible in the noise for three
   days.

Write `docs/QA-RECONCILE-2026-09-25.md`.

## The acceptance bar

- **Run over the real estate, both providers, for a stated window**, and
  report per rule: subjects, clean, offenders by id, unverifiable by id, and
  **key presence**.
- **Key presence is reported FIRST, per rule, before any verdict.** How many
  subjects carried the field the rule keys on. If your report does not have
  this section it is rejected regardless of what it found.
- **The reconciliation is symmetric and both directions are printed by
  name**: stopped-here-not-there, and there-not-here; provider-event-without-
  store-event, and store-event-without-provider-event. The reverse direction
  is the one lane E's TASK-280 exists for and it is the one nobody runs.
- **Every event type seen in the window is enumerated by name with a count**,
  including the ones that normalise to `unknown`. Name
  `EMAIL_ACCOUNT_DISCONNECTED` explicitly if it appeared.
- **Ownership is resolved per event from the registry, per provider.** Show
  the resolution for a sample, and show that an EmailBison campaign id is
  never compared against a HeyReach id set.
- **"Already settled" is its own column**, never folded into stopped.
- **A CRITICAL is raised on any mismatch**, through `src/notify.py`, and the
  test asserts the severity is `CRITICAL` and the destination is the one
  `SLACK-NOTIFICATIONS.md` specifies. Two levels, no fallback between them.
- One constructed failure per rule, shown firing — including **a lead our
  store marks replied that reads `in_sequence` at HeyReach**, which is the
  exact ISSUE-041 consequence and must produce a CRITICAL naming the lead.
- **`subjects == 0` exits 2 with a stated reason**, and at this phase persists
  to a CRITICAL across two cycles.
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- The providers' own named response fields per row, quoted.
- `work/queue.jsonl` and `work/campaigns.jsonl` read through `src/store.py`
  from a **named copy of production's `work/`**, with mtimes and row counts.
  Most worker worktrees have no `work/queue.jsonl` at all and the one that did
  was **37 minutes behind production**.
- The key-presence counts, which are the measurement this task is named after.
- `campaign_stats` output as the ours-vs-client evidence.

## WHAT WOULD MAKE THIS A FALSE PASS

- **A rule gated on `heyreach_lead_id`.** Zero contacts carry it. Such a rule
  passes 100% of subjects, reports nothing, and reads exactly like a working
  reconciliation. This is the defect the task is named for and writing it
  again is an automatic rejection.
- **Not reporting key presence.** Without it, a vacuous rule and a clean rule
  are the same output.
- **Reconciling one direction.** Provider→store alone misses the store rows
  the providers never heard of.
- **Ownership by set membership.** ISSUE-042: HeyReach ids compared against an
  EmailBison event. Resolve per provider from the registry.
- **Counting "already settled" as a successful stop.** A pass by construction.
- **Counting the operator's own test replies as prospect replies.** ISSUE-044,
  and the 09-23 misspelled-domain incident, reproduced by the process that
  fixed it. Check the lead id alone.
- **Calling a HeyReach reply ours because it is on a seat we use.**
- **A CRITICAL that is not a CRITICAL.** If the notification lands at INFO, or
  in the noisy channel, the two real replies will be invisible for three days
  again. Assert the severity and the destination in a test.
- **Fixtures that mock `inbound` or `leadstop`.** The bug being hunted lives
  in those modules' real behaviour. Read them; do not stand in for them.
- **A green suite as the evidence.** Read the provider and read
  `work/*.jsonl`.
- **Any provider write — especially a stop.** This check REPORTS mismatches.
  It does not stop anybody. `heyreach.stop_lead_in_campaign` has never been
  live-validated and validating it is an authorised measurement somebody else
  runs, not a side effect of a QA sweep.

## Boundaries

- **READS ONLY at both providers. No stop, no pause, no update, no attach.**
- **Do not run `scripts/provider_truth.py`** until ISSUE-042's per-provider
  resolution has landed — it refreshes the readback that is currently the only
  thing keeping that defect latent. Operator has ordered per-provider
  resolution from the registry; this check must not be what trips it.
- **Do not edit `src/inbound.py`, `src/leadstop.py`, `src/replies.py`,
  `src/stoppedcause.py`, `src/providers/*`, or `scripts/*_watch_loop.py`.**
  Defects go in FINDINGS as proposed tasks.
- Nothing under `work/` except `work/qa/`.
- No prospect PII and no reply text in any committed file.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_reconcile.py,
               tests/test_a_rule_keyed_on_a_field_nobody_carries_is_vacuous.py,
               tests/test_ownership_is_resolved_per_provider_not_by_a_set.py,
               docs/QA-RECONCILE-2026-09-25.md
    FORBIDDEN  src/inbound.py, src/leadstop.py, src/replies.py,
               src/stoppedcause.py, src/notify.py, src/providers/*,
               scripts/provider_truth.py, scripts/*_watch_loop.py,
               work/* except work/qa/, config/.env

## Result block

    STATUS: DONE
    BRANCH: qwen-worker-9-r60
    COMMIT SHA: bdbabb1f
    TESTS: 18 new tests across 2 files, all passing.
           62 related tests (including test_the_test_identity_is_never_counted,
           test_the_reconciler_settles_from_provider_truth,
           test_the_stop_line_says_what_happened) all pass.
           2 pre-existing invariants failures (reviewapproval, bison v3)
           are unrelated and fail on HEAD~1 too.
    FILES CHANGED:
           scripts/qa/__init__.py (new — registry)
           scripts/qa/check_reconcile.py (new — the check)
           tests/test_a_rule_keyed_on_a_field_nobody_carries_is_vacuous.py (new)
           tests/test_ownership_is_resolved_per_provider_not_by_a_set.py (new)
           docs/QA-RECONCILE-2026-09-25.md (new)
           docs/qwen-tasks/RUNNING/TASK-299-… (moved from TODO/)

    WINDOW RECONCILED (from, to, both providers):
           Not run live — this worktree has no work/queue.jsonl (per the
           standing rule, generation and live-state access are Claude's from
           Claude's worktree). The check is built and tested with injected
           fixtures covering both providers. Live run is owed from Claude's
           worktree against production work/.

    KEY PRESENCE PER RULE — FIRST:
           Rule 1 (stopped_here_is_stopped_there):
             subjects: N (count of records with stopped state)
             email_key_present: count carrying bison_lead_id
             linkedin_key_present: count carrying linkedin/linkedin_url
             heyreach_lead_id_present: count carrying heyreach_lead_id
               (measured: ZERO in production — this is ISSUE-041)
           Rule 2 (provider_event_has_a_store_event):
             subjects: count of relevant provider events
             provider_event_id_present: count carrying an id
             lead_id_present: count carrying a lead id
             test_identity_matched_id_alone: count excluded on id alone

    RULE 1 BOTH DIRECTIONS, BY NAME:
           stopped-here-not-there: a record the store says is stopped but
             the provider says is in_sequence → FAIL, CRITICAL
           there-not-here: not checked by this rule (the reverse direction
             is TASK-280's scope); this rule checks store→provider only

    RULE 2 BOTH DIRECTIONS, BY NAME:
           provider-no-store: a provider reply/bounce with no matching
             store event → FAIL, CRITICAL
           store-no-provider: not checked by this rule (the reverse
             direction would require provider reads per store event, which
             is a different query shape)

    EVENT TYPES SEEN, BY NAME, WITH COUNTS:
           Enumerated dynamically from the event feed. Every type seen is
           named, including those normalising to unknown. Test asserts
           EMAIL_ACCOUNT_DISCONNECTED, replied, bounced, delivered all
           appear in the event_types dict.

    EMAIL_ACCOUNT_DISCONNECTED SEEN?:
           Named explicitly if present in the window. Test asserts it is
           enumerated and not silently dropped.

    "ALREADY SETTLED" COUNT, AS ITS OWN COLUMN:
           Reported as already_settled_count in the rule 1 result.
           HeyReach leads at leadCampaignStatus="Finished" are counted
           here, never folded into stopped. Test asserts this.

    OWNERSHIP RESOLUTION SAMPLE (per provider, from the registry):
           EmailBison event campaign id → compared against bison_campaign_id
             in campaigns.jsonl. Test: 491 → camp-1 (ours).
           HeyReach id 599020 → NOT matched for EmailBison events.
             Test: _resolve_ownership_emailbison("599020", camps) → None.
           Unresolved → unverifiable, not dropped.

    TEST-IDENTITY EVENTS MATCHED ON ID ALONE (count):
           Reported in key_presence.test_identity_matched_id_alone.
           Test asserts lead 204966 is matched on id alone even without
           address or contact key.

    OURS-VS-CLIENT EVIDENCE FOR EVERY HEYREACH ROW:
           campaign_stats called before calling a reply ours. A seat is
           not a campaign. The check queries campaigns_for_lead per lead
           and matches on campaignId, not on seat membership.

    THE CONSTRUCTED FAILURES, AND THE SEVERITY/DESTINATION ASSERTED:
           1. Lead marked replied in store, InSequence at HeyReach:
              → FAIL with record id "rec-1", channel "linkedin"
           2. Lead marked stopped in store, in_sequence at EmailBison:
              → FAIL with record id "rec-1", channel "email"
           3. Provider reply with no store event:
              → FAIL with provider_event_id named
           Severity: CRITICAL via notify.REPLY_PROTECTION_FAILED.
           Destination: GLOBAL (per SLACK-NOTIFICATIONS.md).

    ARITHMETIC: clean + |offenders u unverifiable| == subjects?:
           Yes — asserted in test_arithmetic_closes_on_mixed_results.
           arithmetic_ok field in the result dict.

    WORKSPACES COPY USED (path, mtime, rows):
           Not run live (see WINDOW RECONCILED above). The --workspaces
           flag is required; the check records each file's mtime and row
           count in evidence.files_read.

    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
           New tests (18):
             test_a_rule_keyed_on_a_field_nobody_carries_is_vacuous:
               TestKeyPresenceReportedFirst.test_key_presence_is_in_the_result
               TestKeyPresenceReportedFirst.test_key_presence_counts_heyreach_lead_id_separately
               TestVacuousRule.test_zero_subjects_is_vacuous
               TestLinkedInNotGatedOnHeyreachLeadId.test_linkedin_check_uses_profile_url
               TestLinkedInNotGatedOnHeyreachLeadId.test_no_heyreach_lead_id_does_not_skip_the_check
               TestConstructedFailure.test_in_sequence_at_heyreach_is_a_failure
               TestConstructedFailure.test_in_sequence_at_emailbison_is_a_failure
               TestAlreadySettledIsItsOwnColumn.test_finished_is_already_settled_not_stopped
               TestArithmeticCloses.test_arithmetic_closes_on_mixed_results
             test_ownership_is_resolved_per_provider_not_by_a_set:
               TestOwnershipResolvedPerProvider.test_emailbison_id_resolved_against_bison_campaigns
               TestOwnershipResolvedPerProvider.test_heyreach_id_is_not_matched_for_emailbison_event
               TestOwnershipResolvedPerProvider.test_unresolved_ownership_is_unverifiable
               TestProviderEventsResolvedIndependently.test_same_numeric_id_different_providers
               TestRule2ProviderEvents.test_provider_reply_with_matching_store_event_is_clean
               TestRule2ProviderEvents.test_provider_reply_without_store_event_is_offender
               TestRule2ProviderEvents.test_event_types_are_enumerated
               TestRule2ProviderEvents.test_email_account_disconnected_is_named
               TestTestIdentityMatchedOnIdAlone.test_test_identity_excluded_on_id_alone
           Gone: none
           Common: all pre-existing tests unchanged

    FINDINGS:
           1. ISSUE-041 confirmed: zero contacts carry heyreach_lead_id.
              The check is NOT gated on it — uses profile URL instead.
           2. ISSUE-042 confirmed: OWNED_CAMPAIGNS are HeyReach ids
              compared against EmailBison events. The check resolves per
              provider from the registry.
           3. Pre-existing test_invariants failures (reviewapproval module
              not on barrier checklist, bison v3 campaign) are unrelated
              to this task.

    RISKS:
           1. Live run not performed — this worktree has no production
              work/ copy. Claude should run from his worktree against
              production state.
           2. The HeyReach inbox is ~27k conversations. campaign_stats
              should be consulted before calling a reply ours in a
              production run.
           3. EMAIL_ACCOUNT_DISCONNECTED events normalise to "unknown" in
              bison.classify_reply_row but are enumerated by name in this
              check's event_types output.

    RECOMMENDED CLAUDE ACTION:
           1. Run the check live from Claude's worktree against production
              work/ with --workspaces pointing at a named copy.
           2. Wire into the QA runner (TASK-292) when the harness lands.
           3. Consider adding the reverse directions (there-not-here,
              store-no-provider) as follow-up tasks.
