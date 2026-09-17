# GLM adversarial review - attestation

2026-09-17T18:59:49.609760+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## senderownership.one_attested_human

`glm-5.3`, 50.533s, usage {'prompt_tokens': 1078, 'completion_tokens': 3507, 'total_tokens': 4585, 'reasoning_tokens': 2941, 'cached_tokens': 128}.

**1. NO FINDING** on the visible code — with one unverifiable load-bearing dependency worth naming.

Every branch is either a refusal or a return gated on all ids resolving to a single roster key. I tried to construct each defeat class and none closes on this snippet alone:

- *Return with mixed humans*: impossible without `resolve_owner` collapsing two humans into one key. `resolve_owner` is not shown; if it ever falls back to a shared value (workspace id, team id, `account.workspace`), two humans' inboxes pass as one — but I cannot assert that fallback exists. Same in reverse: if one human's two inboxes return two distinct keys, the function false-refuses — an availability cost, again contingent on hidden code.
- *Empty-ids leak*: `ids == []` raises before `si.load()`. With any id, every element lands in exactly one of `unknown`/`unattested`/`owners`; the first two raise, so `len(owners) != 1` can only mean ≥2. The `!=` (vs `>`) is loose but not exploitable.
- *Filtering*: `i not in (None, "")` lets through `" "`, `"None"`, `False`, `0` — all become `str(...)` and die as `unknown`. Misleading error text, still a refusal.
- *Duplicates*: `["A","A"]` → `owners = {human: ["A","A"]}` → returns human. Harmless.
- *Crash instead of refusal*: `sorted(owners)` and dict-keying assume owner keys are hashable/orderable — `TypeError`, not `NotOneHuman`, if `resolve_owner` ever returns an unhashable/mixed-type key. Contingent, not constructible.
- *TOCTOU on `rows`*: roster can change between this check and the send — but there is **no caller** (stated deliberately), so no call order exists to state.

**2.** The nearest thing to a measurable fact is in the docstring itself: 0 of 225 productive inboxes are attested, so if this were wired into `_sender_for` today, it refuses 100% of real send traffic as `unattested`. That is an availability fact about adoption, not a defect in the predicate — and the docstring claims it as intended.

**3.** No fix indicated. The smallest hardening — assert the returned owner key against a singleton registry (e.g., an attested-humans table) so a fallback value can't alias two humans — costs one lookup but cannot be written without seeing `resolve_owner`. Anything more would be a plausible-sounding guess.

## senderownership.resolve_owner

`glm-5.3`, 29.613s, usage {'prompt_tokens': 400, 'completion_tokens': 2099, 'total_tokens': 2499, 'reasoning_tokens': 1784, 'cached_tokens': 128}.

**1. NO FINDING** (for the code as shown).

**2. Candidates I constructed and rejected:**

- *"Stale `sender_id` beats a newer attestation"* — input would be an account with `sender_id=" departed-op" ` plus a later attestation from the new operator. But whether that state can arise depends entirely on how `sender_id` is written and whether transfers update it — none of that is visible here, and the docstring documents the priority as intended. Can't confirm the state exists.
- *"N+1 queries when `rows=None`"* — would require `attestation_for` to issue a DB query per call, making a 10k-reply ingest batch 10k queries. `attestation_for` isn't shown; I won't assert its I/O behavior.
- *"Empty-string `sender_id` falls through to attestation"* — input `{"sender_id": ""}` resolves via attestation or returns None. Either outcome is defensible; no misrouting or cost follows.
- *"Attestation present but missing `sender_id` key returns None"* — that's honest None by design, not a defeat.

Every real defect candidate lives in `attestation_for`, `_channel_of`, or the writer of `sender_id` — none in the branching logic shown.

**3.** N/A. If you want this review to have teeth, send `attestation_for`, `_channel_of`, and the call site in `assignment.resolve_reply_owner` that builds `rows`.


---

## CLAUDE VERIFICATION, 2026-09-17

**NO FINDING accepted, and the caveat GLM refused to assert is the useful
part.** It named one load-bearing dependency it could not see and declined to
guess about it: whether `resolve_owner` could ever collapse two humans into
one key by falling back to a shared value - a workspace id, a team id,
`account.workspace`. If it could, two humans' inboxes would pass as one and
the predicate would be defeated silently.

**Checked: it cannot.** `resolve_owner` returns `account["sender_id"]` when
the account carries one, otherwise `attestation["sender_id"]`, otherwise
`None`. Both paths return a sender id and nothing else; there is no fallback
to any shared field. The refusal-side mirror is also clean - one human's two
inboxes return the same `sender_id` from either path, so the false-refusal
GLM raised as the reverse risk does not arise either.

**Its point 2 is right and is stated in the docstring on purpose:** wired into
`_sender_for` today, this refuses 100% of real send traffic, because 0 of 225
productive inboxes are attested. That is an availability fact about adoption
and the reason the predicate has no caller yet.

**One thing tightened, not because it was exploitable but because the text was
wrong.** `i not in (None, "")` let `False`, `0` and `" "` through to become
the strings `"False"`, `"0"` and `" "`, which then died as "not in the
roster". A refusal either way - GLM said so - but the sentence an operator
reads would have named the wrong problem. Blanks and booleans are now dropped
before the lookup.

Not taken: GLM's suggested hardening of asserting the returned key against a
singleton registry. `si.require_sender` already raises `UnknownSender` and
`CrossWorkspaceSender`, and `attest` refuses an unknown sender at write time -
so the registry check exists, one layer earlier, where an attestation is
recorded rather than every time one is read.
