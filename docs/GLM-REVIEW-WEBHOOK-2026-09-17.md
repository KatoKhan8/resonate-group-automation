# GLM adversarial review - webhook

2026-09-17T18:47:26.547875+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## bisonevents.normalise

`glm-5.3`, 33.442s, usage {'prompt_tokens': 638, 'completion_tokens': 2360, 'total_tokens': 2998, 'reasoning_tokens': 1756, 'cached_tokens': 128}.

## 1. FINDING

Unhandled `ValueError` from `int(raw_ws)` — a non-integer `workspace_id` crashes outside the documented exception contract (`TenancyRefused` / `MalformedPayload`).

## 2. Trigger and consequence

**Input:** any POST with `event.workspace_id` that isn't int-coercible:

```json
{"event": {"type": "email.opened", "id": "e1", "workspace_id": "bison"},
 "data": {"occurred_at": "2024-01-01T00:00:00Z", "lead_id": 1,
          "campaign_id": 2, "email": "a@b.c"}}
```

**Call order:** pin check passes (env set) → `int("bison")` raises `ValueError: invalid literal for int() with base 10` *before* the tenancy comparison and before any field validation.

**Consequence:** the handler's caller almost certainly catches only the two documented exceptions; this becomes a 500. Webhook providers retry 5xx with backoff (typically ~10–20 attempts over 24h), so **one malformed payload costs ~15 requests, ~15 5xx alerts, and error-budget burn — repeatable at will by anyone who can reach the endpoint.** If this runs in a queue consumer instead, an escaping exception typically nack/requeues → poison-message loop on a single bad event. Secondary, same line: `workspace_id: true` (JSON bool) → `int(True) == 1`, and `1.0` → `int(1.0) == 1`; if the pinned workspace is `1`, these pass tenancy. Also note the crash precedes the tenancy compare, so a cross-tenant fuzz gets a 500 instead of a clean refusal — a distinguishable probe signal.

## 3. Smallest fix

```python
try:
    payload_ws = int(raw_ws)
except (TypeError, ValueError):
    raise MalformedPayload(f"event.workspace_id {raw_ws!r} is not an integer")
```

**Risks:** (a) these payloads now return whatever `MalformedPayload` maps to (4xx) instead of 500 — monitoring/error-rate dashboards shift, and if retry-reaping was accidentally "handling" them via crash, they're now silently classified malformed; (b) it does *not* fix the `true`/`1.0` coercion — fixing that requires `isinstance(raw_ws, int) and not isinstance(raw_ws, bool)`, which risks rejecting a legitimate producer that sends string or float ids.

Also worth flagging (no claim without seeing downstream): `provider_event_id` is passed through unvalidated and may be `None`; if anything dedups on it, all id-less events collapse to one key and get dropped. Verify before acting.

## bisonevents.event_key

`glm-5.3`, 75.417s, usage {'prompt_tokens': 574, 'completion_tokens': 4667, 'total_tokens': 5241, 'reasoning_tokens': 4202, 'cached_tokens': 128}.

**1. FINDING (primary): unguarded indexing on the fallback path crashes ingestion.**

**2. Trigger.** Input: `{"kind": "sent", "workspace_id": "ws1", "campaign_id": "c1", "lead_id": "l1"}` — no `provider_event_id`, no `occurred_at`. The `.get()` on line one is guarded; the five "required" fields are `event[...]` → `KeyError: 'occurred_at'` before any key exists. Consequence depends on the caller, but the standard shape: one malformed event at position *i* of a serially-processed webhook batch aborts the batch → events *i+1..n* never processed, and the provider's full-batch retry re-crashes at the same poison pill. Stated scale: 1 bad event in a 500-event batch = up to 499 dropped events, non-self-healing. Any provider schema change dropping one field converts 100% of id-less events into 500s.

**3. Smallest fix.** Catch the `KeyError`, log, route the event to a dead-letter path, continue the batch. **Risk of the *wrong* fix:** replacing `event[k]` with `.get(k, "")` converts the loud failure into silent mass collision — e.g., a provider sending `"lead_id": null` (which passes indexing, renders as literal `None`) on a batch with a shared `occurred_at` collapses N distinct leads onto one key; first write wins, N−1 events silently deduped. If the kind is `unsubscribe`, those leads keep getting mail. Fail-loud is the correct posture here; it just must not take the batch tail with it.

**Secondary, one line:** explicit `null` fields already produce that `None`-collapse today without any crash — trigger is null `lead_id` + same-second `occurred_at` across ≥2 distinct leads; worth a guard that rejects nulls, not just missing keys.

**Not a new finding:** the `occurred_at` delivery-stamp instability is real but already declared ASSUMED in the docstring; nothing in the code contradicts that flag.


---

## CLAUDE VERIFICATION, 2026-09-17 — ALL THREE CONFIRMED, ALL THREE FIXED

Reproduced before fixing, with the pin set to this estate's 10:

    workspace_id = "bison"  -> ValueError: invalid literal for int()
    workspace_id = True     -> coerced to 1, refused only because our pin is 10
    workspace_id = 1.0      -> coerced to 1, same
    event_key without occurred_at -> KeyError: 'occurred_at'

**The timing is the whole value of this review.** All three live in the two
expressions that decide whether an unauthenticated inbound payload reaches our
state, and none of them had a caller yet. The alternative discovery route was
a production 5xx.

**1. `int(raw_ws)` raising a bare ValueError.** Fixed via `_workspace_id`,
which refuses as `MalformedPayload` - an exception the handler already has to
catch. GLM's secondary point is the sharper one and is now asserted: the crash
happened BEFORE the tenancy comparison, so a malformed id got a 500 while a
foreign-but-valid id got a clean refusal. Two distinguishable answers to a
probe. Both are refusals now.

**2. `int(True) == 1`, because `bool` subclasses `int`.** A JSON `true` or a
`1.0` would have PASSED tenancy on a workspace pinned to 1. This estate is
pinned to 10, so it was safe by accident - which stops being true the moment
there is a second tenant. Both refused explicitly.

**3. `event_key`'s unguarded indexing.** Fixed, and GLM's warning about the
WRONG fix is why the fix looks the way it does. `.get(k, "")` would convert a
loud failure into a silent mass collision: `"lead_id": null` renders as the
literal `None`, and a batch sharing one `occurred_at` collapses N distinct
leads onto one key - first write wins, N-1 silently deduped. **If the kind is
`unsubscribed`, those people keep getting mail.** So it fails loudly, as
`MalformedPayload`, naming the missing fields, and a handler can dead-letter
one event without taking a batch's tail down with it.

Seven new tests, including one that asserts the wrong fix stays un-applied:
two distinct `lead_id`s must produce two distinct keys, and a null one must
refuse.

**Still owed before this is wired to anything**, and neither is GLM's to
answer: every ASSUMED field in the module's own table needs checking against a
real payload, and `occurred_at` needs checking against a real RETRY rather
than a real first delivery - because if the provider stamps delivery time, the
fallback key changes between retries and dedupe fails in silence.
