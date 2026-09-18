# GLM adversarial review - activation

2026-09-18T06:32:29.079790+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## providerwrites._is_the_authorized_email_campaign

`glm-5.3`, 154.82s, usage {'prompt_tokens': 1823, 'completion_tokens': 9095, 'total_tokens': 10918, 'reasoning_tokens': 7822, 'cached_tokens': 1792}.

**FINDINGS**

**1. Re-binding defeat: the never-activate list is enumerated, the row is not pinned.**
- **Trigger / state:** Every allowlist entry has provider slot `None`, so `want_provider` is whatever `bison_campaign_id` says at call time. `_NEVER_ACTIVATE` covers only 481 and 485. Campaign 489 is live, not on that list, and shares four people with the approved cohort.
- **Call order:** Edit `bison_campaign_id` on the authorized canonical row from 487 → 489 (one field on the mutable local file). Call `require_conditional_permission(EMAIL_ACTIVATE, "489", <authorized canonical>)`. Entry found → row resolves to `"489"` → not in `_NEVER_ACTIVATE` → `"489" == "489"` → **returns True**.
- **Prospect-facing result:** Campaign 489 — never named in any operator grant — starts sending. At minimum the four shared people receive a second, unapproved message mid-conversation. This also answers your Q4: the two tables never disagree; both pass. The disagreement is row-vs-both-tables, and it still permits the write because **neither table stores the provider id** — the permission's decisive parameter lives in neither gate.

**2. Never-activate bypass via non-canonical numeric representation (your Q3, float case).**
- **Trigger / state:** `bison_campaign_id` set to `481.0` (or `"481.0"`, or `"0481"`). `str(481.0).strip()` = `"481.0"`, which is not `"481"`, so the never-activate membership misses. `bound` is truthy, so the empty-binding refusal also misses.
- **Call order:** Row edited to 481.0; caller passes `provider_campaign_id="481.0"` → `"481.0" == "481.0"` → **returns True** for a campaign the code's own docstring says must refuse "whatever row resolves to it."
- **Prospect-facing result:** If any layer coerces the id numerically before the API call (the context says ids arrive as str/int/float, so something is coercing), campaign 481 activates: nine of the ten live leads plus four people on 489 — 13 duplicate unapproved touches. Even with no coercion, the guard has returned True where its contract demands refusal.

**3. Possible dead never-activate check: str-vs-int membership (conditional — one line to verify).**
- **Trigger / state:** The comparison is `want_provider in _NEVER_ACTIVATE` where `want_provider` is **always a str**. Your brief says the list "holds provider campaigns 481 and 485." If the tuple literal is `(481, 485)` — ints — then `"481" in (481, 485)` is `False` always, and the entire refusal is dead code. This branch only executes on a row edit, i.e., exactly the day it's needed, so normal operation would never expose it.
- **Call order:** Row → 481, caller → 481, list holds ints: never-activate misses, `"481" == "481"` → **True**.
- **Prospect-facing result:** Same 13-person duplicate send as finding 2. Verify with `assert "481" in _NEVER_ACTIVATE and "485" in _NEVER_ACTIVATE`; if that fails, this is your worst finding.

**4. Third exit state: exceptions that are neither WriteRefused nor True (your Q5).**
- **Trigger / state:** (a) campaigns file row degraded to a scalar — `us_cohort_v3: 487` instead of a mapping: `_campaigns.get()` returns truthy int, `or {}` doesn't fire, `.get` raises `AttributeError`. (b) campaigns file unparseable → import/loader error inside the function. (c) allowlist entry not a 2-tuple → `ValueError` at unpack, or at `sorted(...)` inside the first refusal message itself.
- **Call order:** `require_conditional_permission(EMAIL_ACTIVATE, 487, "us_cohort_v3")` with state (a) → `AttributeError: 'int' object has no attribute 'get'` escapes.
- **Prospect-facing result:** Transport not reached from *this* frame — but the function exits in a state that is neither refusal nor acceptance. If `require_conditional_permission` or anything above it handles only `WriteRefused` as denial (e.g., `except WriteRefused: return False` with other exceptions falling into a retry/continue path), the staged campaign is not stopped here. The trigger states are single-token edits to the same mutable file your threat model already includes.

**NO FINDING on your Q1 and Q2 specifics:**

- **Q1:** `str(x or "").strip()` collapses `"489"`, `489`, `" 489"`, and `"489\n"` to the same `"489"` — all four behave identically in both the entry lookup and the final compare; there is no differential behavior to exploit, and no padding bypass of `_NEVER_ACTIVATE` since that check reads the row value, never the caller's. Caller-side `0`, `None`, `""` all reduce to `""` → refusal. Caller-side float `489.0` → `"489.0" ≠ "489"` → refusal (safe direction).
- **Q2:** No caller-only input converts a refusal into `True`. Both conversions above (findings 1–2) require one prior edit to the campaigns file; the caller cannot produce them alone. `" us_cohort "`-style padding widens string matching to the *same already-authorized rows* — not a defeat by itself.

## executionguard.activation_is_granted

`glm-5.3`, 149.39s, usage {'prompt_tokens': 752, 'completion_tokens': 8260, 'total_tokens': 9012, 'reasoning_tokens': 7354, 'cached_tokens': 704}.

Findings below are for the only function whose source you pasted — `activation_is_granted`. The other gate's code (`require_conditional_permission`, the `_AUTHORIZED_EMAIL_CAMPAIGNS` check, `_NEVER_ACTIVATE` comparison, `bison_campaign_id` resolution) never arrived; see the bottom.

**1. Truthy non-dict row escapes as `AttributeError`, not a refusal.**
- Trigger: canonical row is a truthy non-dict — a `list` (CSV reader row), a `str` (mis-decoded fetch), a pandas `Series`.
- Call order: `require_conditional_permission(op, p, c)` → row fetch returns non-dict → `activation_is_granted(op, row)` → `(row or {})` passes the non-dict through → `.get` raises `AttributeError` before any `return`.
- Result: the guard's verdict is an exception, not `WriteRefused`. Under your contract, only `WriteRefused` is safe, so the send/refuse decision for that row transfers to whatever `except` clause sits above — code not shown. Note the boundary: `None`, `0`, `""`, `[]` all fall to `{}`/falsy and are refused; only *truthy* non-dicts crash, i.e., exactly the partially-parsed-row case.

**2. The final `in` assumes the stored grant value is a set. Two malformed states break it.**
- State A (acceptance): `LIVE_ACTIVATION_GRANTS[cid]` is a `str`, e.g. an operator note `"send_email denied pending review"` stored by a buggy grant-writer. `or frozenset()` doesn't fire (str is truthy); `"send_email" in "send_email denied..."` is *substring* matching → returns **True**. A textual non-grant containing the operation name authorizes the operation.
- State B (escape): value stored as `bytes` (BLOB/latin-1 path) → `str in bytes` raises `TypeError`, same escape class as finding 1.
- Result A: both-tables path completes and the batch sends. Reachability of the state depends on the unseen grant-writer, but the guard performs no type assertion.

**3. Unhashable `operation` raises before line 1 returns** — if `ACTIVATION_OPERATIONS` is set/frozenset-typed, `operation=[]` → `TypeError: unhashable type` at the membership test. Same escape-not-refusal class; conditional on the constant's type, which I wasn't shown.

**Answers to your enumerated cases in this function:**
- Item 1: `"489"`, `" 489"`, `"489\n"` against int-keyed grants all miss the dict → **False**. Fails closed; no whitespace/type acceptance exists here. The one loose edge is numeric aliasing: `489.0` and `True` hit int keys `489`/`1` (equal hash/equality). A pandas-fetched float id inherits the int grant — same numeric campaign, so no unauthorized audience *from this table alone*, but if the providerwrites side compares type-strictly, the two tables disagree on one row. Whether that disagreement still permits a write is decided by the unseen conjunction.
- Item 2 (caller forces refusal→acceptance): **NO FINDING** in this function. It reads `campaign_id` from the row, not the caller's argument; every falsy or mistyped key misses and returns False.
- Item 3 (`bison_campaign_id` = 0/None/""/float/matching 481/485 after normalization): **cannot be adjudicated** — that resolution lives in the code you did not paste.
- Item 4 (tables disagree, write permitted): **cannot be adjudicated** — the conjunction logic was not provided.
- Item 5: findings 1–3 above are the complete escape set constructible from this source.

To audit the 481/485 leak and the `bison_campaign_id`-as-provider-slot issue, I need the body of `require_conditional_permission`, the `_NEVER_ACTIVATE`/allowlist comparison code, and the grant-writer. I will not guess at those.

