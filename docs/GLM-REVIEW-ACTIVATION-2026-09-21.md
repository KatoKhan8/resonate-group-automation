# GLM adversarial review - activation

2026-09-21T09:55:24.136665+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## providerwrites._is_the_authorized_email_campaign

`glm-5.3`, 175.485s, usage {'prompt_tokens': 2172, 'completion_tokens': 10670, 'total_tokens': 12842, 'reasoning_tokens': 9494, 'cached_tokens': 2112}.

## FINDINGS

**1. The pin is dead code; the grant moves with the row. (Answers your Q2 and Q4.)**

- Mechanism: every current entry carries `None` in its provider slot (your own context), so `if want_provider is not None` never executes. `bound` is therefore *whatever the mutable row's `bison_campaign_id` says*, constrained only by `bound in _NEVER_ACTIVATE` — an enumerated denylist of exactly two campaigns, 481 and 485. The "reproduced 2026-09-18, row re-bound to 327, permitted" defeat in the docstring is only closed by the pin — which is inert in the shipped state.
- Trigger/state: one field edit on a local file — v3 row's `bison_campaign_id`: 487 → 489.
- Call order: `require_conditional_permission(op, provider_campaign_id=489, campaign_id="<authorized v3 row name>")` → name matches an entry → row reads back as dict → `_provider_key(489)` truthy → pin skipped (None) → `489 not in {481, 485}` → `offered_provider == bound` → **returns True**.
- Prospect-facing result: activation of 489, which holds four people currently mid-conversation (the 481∩489 cohort) — an unapproved second send. The identical call with `327`, `328`, `352`, or **any campaign created after the denylist was written** returns True: protection = the entire provider estate minus two ids. The docstring's claim that "every campaign created after this line was written" is refused by the first check is false — the first check refuses unknown *row names*, never provider ids.

**2. `next()` first-match silently disarms any future pin.**

- Mechanism: `next((e for e in _AUTHORIZED_EMAIL_CAMPAIGNS if e[1] == offered))` returns the *first* entry whose canonical name matches. If an operator later "pins" the v3 row by adding `(487, "v3")` while the original `(None, "v3")` sits earlier in the tuple, the pin is never consulted.
- Trigger/state: tuple contains `(None, "v3")` before `(487, "v3")`.
- Call order: identical to Finding 1; pin branch skipped; Finding 1's result stands, now with the operator *believing* the pin is armed.

**3. This function never reads `LIVE_ACTIVATION_GRANTS`; the two-table AND exists only by call convention.**

- Mechanism: nothing in this function consults the second table, and the function is module-level and directly callable. Knowledge of the row name is the only credential; it authenticates nothing about the caller.
- Trigger/call order: operator revokes the ACT in `LIVE_ACTIVATION_GRANTS`; any code path that calls `providerwrites._is_the_authorized_email_campaign(487, "<v3>")` directly — or a `require_conditional_permission` that ORs the two checks or catches broadly — gets True with zero reference to the revocation.
- Prospect-facing result: the ten leads on live 487 receive mail the operator withdrew that day.

**4. Conditional, unverifiable from what's shown: never-activate is a type-equality bet on `_provider_key`.**

`bound in _NEVER_ACTIVATE` is exact membership. If `_provider_key` returns stripped **strings** while `_NEVER_ACTIVATE` holds **ints** {481, 485}, then for a row edited to `" 481 "`: bound = `"481"`, `"481" in {481, 485}` is False, the denylist never fires for *any* input, caller passes `" 481 "`, equality holds → True → ten live-487 leads double-messaged. Same dependency covers Q3's zero case: if `_provider_key(0)` returns `"0"`, `not bound` is False (truthy string) and a row bound to 0 is admitted. If `_provider_key` returns ints, both collapse — audit its return type before trusting item 1's denylist as a backstop.

## NO FINDING

- **Q1:** All four spellings — `489`, `"489"`, `" 489"`, `"489\n"` — behave *identically*: canonical ids collapse through `str(x or "").strip()` before the allowlist compare, and both sides of the provider-id equality pass through the same `_provider_key`. Formatting noise cannot flip a refusal or split the comparison here. (`0` → `""` → refused; float row names stringify with `.0` and match nothing.)
- **Q3:** Missing row, non-dict row, `None`, `""` all hit explicit refusals; normalization happens *before* the denylist check, so a value matching 481/485 only after normalization is still refused. Float bindings either fail to parse ("no usable `bison_campaign_id`" refusal) or normalize to the int and hit the denylist. Only the `0`/"0" truthiness case is live, covered under item 4.
- **Q5:** No path in this function converts an error into True — there is no try/except; every non-True path raises. The residual hazard (an unseen caller catching broad exceptions *around the write* and proceeding) is outside this code.

## executionguard.activation_is_granted

The call did not return.

GlmTimeout: glm: the call did not return: HTTP POST timed out after 180s

