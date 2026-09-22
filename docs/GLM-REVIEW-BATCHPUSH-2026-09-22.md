# GLM adversarial review - batchpush

2026-09-22T18:54:46.432395+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## bison.attach_leads

`glm-5.3`, 86.592s, usage {'prompt_tokens': 1423, 'completion_tokens': 6097, 'total_tokens': 7520, 'reasoning_tokens': 5296, 'cached_tokens': 0}.

## A. Lead enrolled twice

**Routes I tried that are closed:**

- **Two processes racing / retried call after client-reported failure.** Both read `before` as empty, both POST `missing`. Closed by the provider's own refusal to double-add (docstring, and surfaced as `LeadsNotAttachable` at `if REFUSED_ATTACH in _message(data).lower()`). Even with a stale `before` inside the consistency window, the second POST is refused, not duplicated. Not constructible here.
- **Partial success then re-run.** Same closure; re-run's pre-check finds the persisted 20, POSTs only the residue.

**One seam I cannot close and cannot prove — intra-payload duplicates.**

`wanted = [i for i in (lead_ids or []) if i is not None]` is the only filtering; nothing dedupes. Concrete input: `attach_leads(c, [7, "7"])`. Both pass (`int("7") == 7`), so `missing = [7, "7"]` and the POST body is `{"lead_ids": [7, "7"]}`. Every verification in the function is set-based (`before`, `after`, `int(i) not in ...`), so this case is structurally invisible: if the provider enrolled twice, `absent` is still `[]`, and the function returns success with `attached: [7, "7"]`, `members: [7]` — nothing compares them. The docstring's provider guarantee ("Existing leads were not added") covers leads already *in the campaign*, not two copies in one payload; nothing shown measures that case. I cannot construct the end-to-end defeat because the provider's behavior is unmeasured, but this is the one input the code passes through unfiltered and cannot detect. One-line close: dedupe via `dict.fromkeys`, assert `len(missing) == len(set(missing))` before POST.

**Cross-campaign.** `before = membership(campaign_id, wanted)` is scoped to the campaign named in this call. `attach_leads(492, [5]); attach_leads(493, [5])` both return `attached: [5]` by construction; no per-person suppression is consulted here. Whether A's two-campaign case is closed lives in the caller, which I was not shown. Show it.

**Adjacent measurable cost (not A, not B):** the refusal branch raises `LeadsNotAttachable` *before* any readback. Sequence: write succeeds, lag exceeds the poll window, call raises `ProviderError`; re-run lands while `before` is still stale; POST hits "Existing leads were not added"; `raise LeadsNotAttachable(_attach_refusal(...))` fires with no membership read to contradict it — operator reads "not attachable" on a fully-enrolled campaign, at exactly the docstring's measured scale (60 of 77 on campaign 494, 157 of 206 on 492). The readback-polling fix only covers the 200 path. Close it by re-reading membership before raising in that branch.

## B. Send from an unattested mailbox

**NO FINDING** — from this code. `attach_leads` has no sender surface: no mailbox id, no from-address, no attestation lookup, no reference to the three excluded identities. Every B route (campaign naming an ungranted sender, send-loop mailbox selection, an attestation check reading stored state instead of the provider) lives in campaign creation and the send path, neither shown. To audit B I need the sender-bind code, the send loop's mailbox choice, and where attestation and the exclusion list are checked. Anything I said now would be the plausible-sounding guess you told me not to make.

## providerwrites.perform

`glm-5.3`, 142.638s, usage {'prompt_tokens': 3049, 'completion_tokens': 10630, 'total_tokens': 13679, 'reasoning_tokens': 9290, 'cached_tokens': 64}.

## FINDING A — DEFEATED, two independent constructions

### A-1. The exception path manufactures the exact "missing touch" the code says is unacceptable. No concurrency required.

1. `perform(LINKEDIN_ADD_LEAD, authorization=tok, campaign="A", payload={lead: L})`. The provider POST lands server-side; the client socket times out; `transport(payload)` raises.
2. The `except` branch runs `actionledger.settle(key, UNRESOLVED, ...)` and raises `WriteUnverified`. `_record_confirmed_touch` is reachable only under `if facing and verdict == ACCEPTED` — no verdict was classified, so **no touch is written for a lead the provider has enrolled**.
3. The operator follows the raised instruction: reads provider truth, sees L in campaign A, hand-settles the key. `settle` writes ledger state only; it creates no touch row.
4. Next day: `executionguard.authorize(LINKEDIN_ADD_LEAD, campaign="B", lead=L)` — eligibility reads the touch store, finds zero touches for L, mints. `perform` → `revalidate(authorization)` reads the same empty store → passes → transport adds L to B.
5. L receives both sequences.

The function's own comment states the invariant — "a missing touch costs a second message to a real person" — and the exception branch is a machine for producing missing touches at provider-side success. Cost: at a 1–2% transport-exception rate on 10,000 enrollments/week, 100–200 people per week are re-enrollable unless a human performs a step no code performs.

### A-2. Cross-campaign concurrent enrollment; the last stop reads our lagging store, not provider membership.

1. Two workers enroll the same list into campaigns A and B. Both `authorize` calls pass (neither write has landed). Reservations K_A, K_B both `ATTEMPTED` — different campaigns, different keys, so the reservation check is satisfied twice by design.
2. W1: `perform` passes all gates → transport adds L to A → accepted → **touch written only now**.
3. W2's `revalidate(authorization)` executes inside the window between W1's transport acceptance and W1's touch commit → reads no touch → passes → transport adds L to B.
4. L is in both campaigns; both sequences send.

The window is one provider round trip plus the readback (~0.3–1s per lead). With a 5,000-lead list processed by both workers, duplicates ≈ 5,000 × P(W2.revalidate(L) precedes W1.touch_commit(L)). No line in `perform` ever asks the provider "is L already a member?" — even though `require_conditional_permission` already does a provider read for campaign state and `readback()` is standing right there.

**Caveat on their crash argument:** for the touch-then-settle crash interleaving, the comment claims the retry is refused "by fatigue and by the reservation." The reservation does not refuse — the ledger is still `ATTEMPTED` (settle never ran). Fatigue-at-mint is the only thing standing there.

## FINDING B — DEFEATED, unless a gate I cannot see exists

1. `perform(ASSIGN_SENDER, authorization=None, campaign="C", payload={"mailbox": "<one of the three excluded identities>"})`. `describe` returns `facing=False` for staging verbs, so the entire `if facing:` block — the only place any Authorization, attestation, or identity check lives — is skipped. `require_conditional_permission` is a no-op (no condition is registered for assign-sender). First assign passes the fingerprint guard; a *different* mailbox is a different fingerprint anyway. Transport assigns; ACCEPTED; `record_staged`.
2. `perform(LINKEDIN_START_EMPTY_FOR_STAGING, campaign="C")` — condition holds, campaign starts.
3. Every subsequent send carries a fully valid Authorization, because nothing in `perform` inspects which mailbox the campaign now names. Cost: the full first-touch volume of campaign C (a 500-lead campaign = 500 first touches from an excluded identity) before detection.

**Swap variant, if a send-time attestation gate exists in `authorize`:** assign-sender needs no token, so it can run *between* send-mint and send-perform — mint the send token against an attested sender, reassign the excluded mailbox (new fingerprint, passes), then `perform(SEND, tok)`. `revalidate` per its own comment checks "whether the PERSON still wants to hear from us" — person stops, not the campaign→sender binding. Closure would require `revalidate` to re-read the assignment; nothing shown does.

**What would close B:** a gate in `executionguard.authorize` for the send operation that resolves campaign→assigned sender→attestation/exclusion, re-checked in `revalidate`. That line is not in this file, and the architecture works against it: the ladder belongs to the named *send* operation while the verb that actually binds a human identity to a campaign carries no token at all. Show me `authorize`'s gate list or this stands.

## Routes I could not defeat — closing lines

- **Retry after a classified success:** `authorization.spend()` plus `state_of(key) != ATTEMPTED` (ledger shows SENT) refuses a re-perform — *provided* `authorize` will not mint over a terminal row; that behavior is not visible here.
- **add_lead token driving activate:** closed by `authorization.operation != operation`.
- **Dict-shaped token:** closed by the `isinstance` check.
- **Unapproved copy on an approved token:** `_require_approved_words`, correctly ordered after the local token checks.
- **Double staging of identical material:** `staged_already` fingerprint guard, non-REPEATABLE verbs.

## NO FINDING

**Identity resolving to more than one human or to none:** resolution happens upstream of this door; `perform` never compares identities, so no line here can either cause or close it. Audit the resolver separately — if it splits one human into two lead rows, A-2's race isn't even needed, but that defeat must be constructed against the resolver's code, not this function's.

## senderownership.one_attested_human

`glm-5.3`, 149.377s, usage {'prompt_tokens': 1527, 'completion_tokens': 11796, 'total_tokens': 13323, 'reasoning_tokens': 10684, 'cached_tokens': 192}.

## A. LEAD ENROLLED TWICE — NO FINDING, because nothing shown can even attempt it

Nothing in the provided artifact observes a lead. `one_attested_human` maps provider ids → one owner; no lead id, email, campaign membership, or staging table appears anywhere. Every vector you named — partial success + retry, two processes racing, provider-write-succeeded/client-told-failure, re-staging an already-present lead — executes in enrolment code that was not attached. I won't guess at its uniqueness key. To make A reviewable I need: (1) the enrolment entrypoint and its lead key — `(email, campaign)` vs `(normalized email, workspace)` vs provider lead id; (2) whether the provider enrol call carries an idempotency key; (3) whether "already present" is checked against our DB or the provider's campaign membership — the last is where a provider-side re-sync re-stages a lead our DB suppressed.

## B. SEND FROM AN UNATTESTED MAILBOX — FINDING, and it is not an edge case

**Finding 1 — present state, arithmetic from the artifact's own numbers.** The only attestation predicate in the codebase has no caller (its own header: "Why it has no caller yet, on purpose"). The live gate is `_sender_for`'s arity rule, which per this docstring refuses only campaigns naming >1 sender — arity cannot distinguish attested from unattested. The same docstring states **zero of 225 productive inboxes are attested**, while `scripts/bison_sender_stickiness.py` measured real traffic: 243 leads, campaigns holding 59 and 222 sender slots — 281 slots over a 225-inbox estate, all of them by definition productive, therefore all unattested. B has already occurred at the scale of every send the estate has made; this predicate is the planned fix, not the current guard. (Only escape: `_sender_for` carries an unmentioned attestation check — but then 0/225 forces refusal of 100% of productive campaigns, contradicting the observed sends. One of the two holds; check `_sender_for`.)

**Finding 2 — concrete sequence defeating the planned wiring** (your "reads our own stored state" vector): canonical row names `{A, B}`, both attested to human H; the EmailBison campaign's actual pool is `{A, C}` (edited at the provider after row sync). `one_attested_human(["A","B"], …)` returns H; the future `_sender_for` passes; the provider selects the **step-1** sender from the real pool and picks C. The docstring's own stickiness quote only pins the sender for "the remaining steps" *after* first touch — first-touch selection is the provider's choice, and the zero-rotations evidence (243 leads) measures steps 2..n, not step 1. The planned remedy — record the human, observe the inbox afterward from `scheduled_emails[].sender_email` — learns about C only once the send is already populated. Detection, not prevention.

**Routes closed inside the function** (naming the guard, per your instruction): no ids → `if not ids: raise`; foreign-workspace inbox → `by_provider_account` scoping feeding `if unknown: raise`; unattested → `if unattested: raise`; two humans → `if len(owners) != 1: raise`; malformed scalars → the `isinstance(raw, bool) or not str(raw).strip().isdigit()` raise. A falsy owner falls into the unattested branch — wrong text, safe direction.

**Three residual notes, none a defeat as shown:**
- A bare `str` passed as `provider_account_ids` is iterated per character: `"1053"` → `["1","0","5","3"]`, each passing `isdigit`, so the row-level malformed refusal the comment promises never fires and id 1053 is never examined. With provider-issued ids this lands as `unknown inbox(es) ['0','1','3','5']` — a refusal with garbage text, not a send. The comment's claim "anything else that is not a usable id is REFUSED" is false at row level; an `isinstance(provider_account_ids, (list, tuple))` check closes it.
- No exclusion of your three excluded identities appears anywhere in this function. If that exclusion is not inside `resolve_owner`, input `[account_of_E]` returns E as the owner. That is the single place it can be closed; verify it.
- The `rows=` parameter lets a long-lived worker attest against a stale snapshot after a revocation; the `si.load()` default closes this, the parameter reopens it. And if `resolve_owner` can return a collection, `owners.setdefault(collection, …)` raises `TypeError`, not `NotOneHuman` — a caller catching only `NotOneHuman` crashes instead of refusing. Availability, not B.

**Bottom line:** A is unreviewable from this artifact — send the enrolment path. B needs no constructed input today; by the docstring's own counts the estate sends exclusively from unattested mailboxes, and the planned fix gates on our stored row where the provider picks from its own pool.

## senderownership.resolve_owner

`glm-5.3`, 88.279s, usage {'prompt_tokens': 551, 'completion_tokens': 6613, 'total_tokens': 7164, 'reasoning_tokens': 5599, 'cached_tokens': 192}.

## A. Double enrolment — NO FINDING

Not constructible from the evidence provided. `resolve_owner`'s inputs and outputs never touch lead or campaign identity; it is provably orthogonal to A. Every scenario you listed is decided by code I haven't seen, so anything I built would be invented. What I need, and the single guard that closes each route so you can check it yourself:

- **Partial success / provider wrote, client saw error:** defeat exists iff enrolment dedupe consults our stored "enrolled" flag rather than the provider's membership list. Sequence would be: enrol → provider adds lead → response lost → flag unset → retry → second membership. Closed by a pre-write provider-membership read or a provider-side idempotency key.
- **Two processes racing:** closed only by a DB unique constraint on the membership key or provider idempotency. Check-then-insert in application code is open.
- **Already-present lead re-staged:** same guard, plus the dedupe key itself. If it's raw email string, `a@example.test` / `a@example.test` double-enrols trivially — that's the first thing I'd audit in the staging code.
- **Two campaigns:** closed only by a lead-level invariant (one active membership) or a global suppression check at send.

NO FINDING here is a statement about missing evidence, not about safety.

## B. Unattested / excluded sender — findings against the shown code

**B1 — The direct path makes "attested" and "merely recorded" indistinguishable.**
Input: `{"sender_id": "ops-shared@example.test", ...}` — any account row whose `sender_id` was populated by provisioning, import, or migration, with no attestation row.
Call: `resolve_owner(account)` → path 1, `if direct: return direct` → returns that sender_id.
Consequence: the return value is identical in type and content to an attested owner. If the send gate is `owner = resolve_owner(acct); if owner: send()`, one imported row puts an unattested mailbox behind an entire campaign's sends.
Closing line that isn't there: an attestation-existence check on the direct path, or a gate-side `attestation_for(...)` call. The docstring's own principle — honesty about uncertainty — is violated by path 1 collapsing two epistemic states into one return. Verify the gate; this is conditional only on that.

**B2 — Exclusion enforced at attestation time goes stale at read time.**
Call order: attest `(W, ch, A1) → "S"` at T0; `"S"` added to the three excluded identities at T1; `resolve_owner` at T2 → `attestation_for` returns the T0 row → `"S"`.
Consequence: `resolve_owner` reads our stored attestation, never the live exclusion set. Every send on A1 attributes to (and passes any owner gate for) a now-excluded identity until manual intervention. This is your "reads our own stored state" defect instantiated: the thing that changed is policy, not the row. Same staleness applies to path 1's `direct`.
Closing line that isn't there: `if att and att.get("sender_id") in EXCLUDED: return None` (or the equivalent in the gate).

**B3 — Duplicate attestations make the owner nondeterministic.**
State: two rows for `(W, ch, A1)` with sender_id `"S1"` and `"S2"` — writable iff there's no `UNIQUE(workspace, channel, account_id)`.
Call: `resolve_owner` → whichever row `attestation_for` returns first; no ordering is specified, so ownership flips across processes/restarts. If either claimant is excluded or departed, you get a probabilistic excluded-identity send. Need `attestation_for` and the DDL to confirm writability.

**Dispatched:**
- *Identity resolving to none:* safe direction — returns `None` → rendered UNKNOWN. But note the docstring explicitly delegates the meaning of `None` to the caller; the entire None path is only safe if the gate blocks UNKNOWN rather than merely labeling it. That enforcement is nowhere in evidence.
- *Campaign naming an ungranted sender:* `resolve_owner` answers ownership, not grant. If it's the only sender check before send, an attested-but-ungranted mailbox sends. Separate check required; location unknown.
- *Revocation:* no path back to `None` exists. A mis-clicked "I own this" on someone else's mailbox stays attested until data surgery.

To convert B1–B3 from conditional to confirmed: send the send-gate code, `attestation_for` plus schema, and for A, the enrolment write and its dedupe key.

