# GLM adversarial review - ledger

2026-09-17T18:14:23.287613+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## actionledger.reserve

The call did not return.

GlmMalformedResponse: glm: answered 200 with an empty completion (finish_reason='length'). Refusing rather than returning '', which would be read as a bad answer instead of no answer

## actionledger.settle

`glm-5.3`, 85.956s, usage {'prompt_tokens': 729, 'completion_tokens': 5327, 'total_tokens': 6056, 'reasoning_tokens': 4711, 'cached_tokens': 128}.

**1. NO FINDING on the safety property.**

The two-step walk the comment describes is actually closed, and closed by construction, not just by the added check: `settle` only ever appends onto a last row that is non-terminal, `reserve` (per the comment) refuses terminal keys, and same-state calls return without appending. So a TERMINAL row can never stop being the last row; `state_of` can never regress it; the key can never be re-reserved. I can't construct a call sequence through this function that re-opens a SENT key.

Two residual items exist, but they are record-fidelity costs, not defeats — I'm reporting them at that size:

**2a. Stale payload inheritance.** Call order: `settle(k, UNRESOLVED, provider_response={"code":"421","phase":"deferred"})` → `settle(k, FAILED)` with `provider_response=None`. Because `row = dict(prior)` and the field is only overwritten when explicitly passed, the FAILED row carries the UNRESOLVED event's 441/deferred response as if the failure produced it. Consequence: any downstream classification of failures by provider code counts deferrals as hard failures on every key that transits UNRESOLVED→FAILED; at N such settlements, N misattributed rows in the durable audit trail.

**2b. Silent payload drop on same-state replay.** Call order: `settle(k, SENT, provider_response={"mid": M})` commits; any later `settle(k, SENT, why=..., readback=...)` hits the `state == state` branch *before* the terminal guard and returns `found[-1]` — no append, no error, the new `why`/`readback` discarded. Consequence: anything learned after the first SENT settlement (corrected message id, delivery readback) can never be attached via this API; a caller doing so gets a success return while nothing was recorded. This is a silent-loss path, which is worse than raising, but it costs data, not a second contact.

**3. Smallest fixes.**
- 2a: before `row.update(...)`, `row.pop("provider_response", None); row.pop("readback", None)` and re-add only when passed. Risk: consumers that assume the key exists on every row (or relied on "last known response" carry-forward) break or read `None`.
- 2b: on the same-state hit, if any of `why`/`provider_response`/`readback` differ from the stored row, append a correction row instead of returning, or raise. Risk: turns a cheap idempotent no-op into an append (log growth) or an exception (at-least-once retries start failing on the retry leg, which is the more dangerous direction — pick the append).

Neither changes reservation semantics; both only touch what the ledger remembers.


---

## CLAUDE VERIFICATION, 2026-09-17 — BOTH ACCEPTED AND BOTH FIXED

`settle`'s two findings were confirmed against the source and fixed the same
hour. Neither was a safety defeat - reservation semantics are untouched - and
GLM said so itself rather than inflating them, which is the behaviour that
makes this tool worth running.

**2a stale payload inheritance: CONFIRMED.** `row = dict(prior)` at
`actionledger.py`, and `provider_response` / `readback` were re-set only when
a caller passed them. Both are now dropped forward and re-added only when
passed.

**2b silent payload drop: CONFIRMED.** `if found[-1].get("state") == state:
return dict(found[-1])` sat before any use of the arguments. A same-state
replay that DISAGREES with the stored row now appends a correction row; an
identical replay still appends nothing, which is GLM's own advice - "at
least-once retries start failing on the retry leg, which is the more dangerous
direction - pick the append".

`tests/test_a_settlement_does_not_inherit_the_last_events_evidence.py`, eight
tests. Two go red when the two `pop` lines are removed. 410 tests across the
fifteen modules touching the ledger stay green.

**`actionledger.reserve` has no review.** The call returned 200 with an empty
completion and the adapter refused to hand back `""`. Re-run it with a larger
`--max-tokens`: the budget went to reasoning tokens, not to an answer.
