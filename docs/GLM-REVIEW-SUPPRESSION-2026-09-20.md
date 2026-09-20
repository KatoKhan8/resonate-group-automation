# GLM adversarial review - suppression

2026-09-20T20:08:18.654998+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## inbound.ingest

`glm-5.3`, 107.42s, usage {'prompt_tokens': 948, 'completion_tokens': 8000, 'total_tokens': 8948, 'reasoning_tokens': 7247, 'cached_tokens': 512}.

**Verdict: mechanism PLAUSIBLE, consequence UNPROVEN — and the claim's central harm is likely mis-stated. I cannot confirm the "reply absent from canonical state → further message authorised" chain from the code provided. Partial findings below; the rest is UNKNOWN, not guessed.**

**1. Is the claim true?**
The two lines in evidence: digest read at `base = store.digest() if own else None`; refusal at `store.save(recs, expect_digest=base)`, gated by `if own and any(o["applied"] and o["applied"]["status"] == "applied" ...)`. I cannot name the line where the digest *changes* — it would be inside `_record`/`store.transaction()`, neither of which you gave me. The claim splits into three sub-claims with different truth values:

- "nested transaction changes digest" — UNKNOWN. Forks on store semantics you haven't shown: if `digest()` is a content hash, a rolled-back or read-only `_record` transaction changes nothing and `save` succeeds — claim dead. If it's a commit-counter bumped by any committed transaction, any `_record` commit bumps it — claim alive.
- "outer save raises QueueChanged" — TRUE *conditionally*: given a digest-visible commit in the window, yes, and the exception escapes `ingest` (no try/except), so the in-memory `recs` mutations are discarded.
- "the pause is discarded / reply does not exist in canonical state" — this is the weak part. You told me `_record` "opens its own `store.transaction()`". If that transaction *commits the stop and account pause*, they survive the outer refusal; what's actually lost is the record-level reply state and classification sitting in `recs`. The module is named `leadstop` — if authorisation consults the stop ledger `_record` persists, the worst failure (messaging a replied person) is *prevented*, and the claim's headline is false. The claim is only fully true if `_record` bumps the digest **without** persisting the stop (counter-digest + auxiliary-only write). Both readings fit every line you showed me.

**2. When does it fire?**
Necessary conditions, all from the shown code: (a) own mode — `recs=None`; pass `recs` in and `base=None` and there is **no save and no refusal at all**; (b) ≥1 outcome with `applied.status == "applied"` — all-duplicates polls never call `save`; (c) a digest-visible commit between `digest()` and `save()`. Is any `_record` call enough? UNKNOWN — same content-hash vs counter fork. Note the window also spans `store.load()`, the adapter, and every `handle` call including per-reply Slack I/O, so a *background job* hitting that window fires the same refusal with `_record` uninvolved.

**3. Lost permanently or recovered?**
UNKNOWN, and the claim's "one poll interval" is itself an assumption. Recovery needs the provider to re-deliver the reply; whether the poller acks/consumes independently of `ingest` raising is not shown — if ack happens regardless, loss is **permanent**. Concrete never-recovered path to check in `handle`: if the reply's seen/dedup marker is persisted by `_record`'s surviving transaction while the record-level replied flag lives in the discarded `recs`, then next poll the event is a duplicate → no "applied" outcome → `any(...)` is false → save never runs →

## leadstop._record

`glm-5.3`, 103.061s, usage {'prompt_tokens': 897, 'completion_tokens': 8000, 'total_tokens': 8897, 'reasoning_tokens': 7861, 'cached_tokens': 512}.

## VERDICT ON THE CLAIM: UNCONFIRMED — not false, but not establishable from the code shown

Four load-bearing facts live outside this snippet: (a) `store.transaction()` commits mutations visible to `digest()`, (b) `digest()` covers the event-appended row content, (c) `PROVIDER_STOP_CONFIRMED ∈ events.KNOWN`, (d) ingest discards `recs` on QueueChanged without retry, and the provider re-delivers the reply next poll. The trace below is conditional on all four.

**1. Trace.** Under (a)+(b): the digest changes at the *exit* of `with

