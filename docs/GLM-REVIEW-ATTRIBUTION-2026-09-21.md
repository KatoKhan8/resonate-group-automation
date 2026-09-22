# GLM adversarial review - attribution

> ## VOID — THIS REVIEW WAS RUN WITHOUT THE CODE IN THE PROMPT
>
> **Marked 2026-09-22 (branch `infra`). Do not cite anything below as a review
> finding.** `ATTRIBUTION_QUESTION` carried no `{source}` placeholder, and
> `str.format` ignores a keyword the template never mentions, so both calls
> shipped the question text alone. The model was asked about
> `inbound._positively_not_ours` and `inbound.handle` and shown neither.
>
> The receipt is in this file. Both calls report `'prompt_tokens': 312` —
> **identical, for two different functions**, because the prompt did not depend
> on which function was under review. Every other target in this directory
> varies with its function: 400, 752, 1078, 1823, 2172.
>
> The model reported it too, and was ignored: *"assertable without your
> code"*, *"I cannot construct a concrete drop without the body of
> `_positively_not_ours`"*, *"If you already do positive client-list matching,
> this finding is void — tell me which comparison you use."*
>
> So this is not a weak review, it is not a review. What survives is what any
> competent reader could write from the question text alone, and the two
> coercion probes in (2), which are language facts and need no source. The
> ISSUE-001 attribution path has NOT had a second opinion and still needs one.
>
> Fixed in `scripts/glm_review.py`: `build_prompt` refuses a prompt that does
> not contain its function's source, on the dry-run path before `--live` is
> consulted. Regression test:
> `tests/test_a_review_call_carries_its_source.py`. Re-run
> `--target attribution --live` to get the review this file was supposed to be.

2026-09-21T12:15:27.880548+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## inbound._positively_not_ours

`glm-5.3`, 139.147s, usage {'prompt_tokens': 312, 'completion_tokens': 7266, 'total_tokens': 7578, 'reasoning_tokens': 6592, 'cached_tokens': 0}.

**FINDING (assertable without your code, closest to (1)):** If `_positively_not_ours` proves foreignness by *absence from our lists* (`seat ∉ OUR_SEATS`), list staleness silently drops our replies and is undetectable against background. Fail-closed guards parse failure, not staleness. A renamed campaign or newly provisioned HeyReach seat makes every field present and parseable — no fail-closed branch fires — and all replies on it drop. Arithmetic: any seat/campaign producing ≤80 replies/day is fully swallowable inside the 80/day client noise with zero signal, unless every drop is logged (seat+campaign) and baselined. Fix: drop only on *positive* client-list membership (`seat ∈ CLIENT_SEATS`), and alert on drop-rate deviation from the 80/day mean. If you already do positive client-list matching, this finding is void — tell me which comparison you use.

**(1)** Otherwise NO FINDING — I cannot construct a concrete drop without the body of `_positively_not_ours` and the drop site. Two probes worth one synthetic event each: membership type mismatch (`7 in {"7"}` → False → drop; would eat 100% of int-typed events — a smoke test catches this day one); any "known foreign" cache — one poisoned entry suppresses every later event on that seat until restart.

**(2)** Language facts; outcome depends on your parse layer: `int(False)==0` / `int(True)==1` (JSON boolean seat → probe `{"seatId": false}`); `int(7.9)==7` (truncation onto our int); `int("1_0")==10`. Unicode digits (`int("٧")==7`, `int("７")==7`) alias the *same* integer, so they can only push a foreign spelling toward "ours" — alert kept, fail-closed safe. Unicode cannot make a distinct foreign seat collide with a *different* number of ours. In every case the dangerous direction is comparing against a string-keyed set, not the coercion itself.

**(3)** UNKNOWN — need the call order. Both failure shapes are one-line checks: (a) drop before hold → a false drop also skips the hold → we keep sending to someone who replied (worst outcome, compounded); (b) hold before drop → the ~80/day client events each place a hold with no notification explaining it.

**(4)** UNKNOWN. The double-delivery input is guaranteed, not hypothetical — webhook retries are at-least-once. Replay one event ID twice and inspect what the hold is keyed on.

**(5)** UNKNOWN. Two conditions: (a) webhook signature verification — a self-consistent forged event claiming a foreign seat passes "positively not ours" *by construction*; the predicate validates attribution, not authenticity; (b) any seen/dedupe cache keyed on event-supplied IDs — the only path by which a fake event consumes a real one's alert. Absent (b), a forged event is merely dropped, which is by design.

Send me `_positively_not_ours`, the drop site, and the hold call, and I'll convert each UNKNOWN to a finding or a NO FINDING.

## inbound.handle

`glm-5.3`, 116.65s, usage {'prompt_tokens': 312, 'completion_tokens': 6049, 'total_tokens': 6361, 'reasoning_tokens': 5132, 'cached_tokens': 256}.

**Ground truth first:** I was not given the source of `inbound.handle` or `_positively_not_ours`. I will not fabricate inputs against unseen code. Answers below are NO FINDING / UNKNOWN plus the exact probe that settles each, except (2), where the Python semantics are verifiable regardless of code.

**(1) Real reply on our seat dropped — NO FINDING** (unconstructable without the predicate). Three one-line shapes that *would* produce it; grep for each:
- Raw-type membership: `seat not in OUR_SEATS` with `OUR_SEATS = {8, ...}` (ints) and seat arriving as JSON string `"8"`. `"8" in {8}` → `False` → "not ours" → drop. Every our-seat event with a string-typed seat is silently discarded. Population: exactly the true positives the alert exists to catch (our replies that attribution already missed), so nothing downstream moves — the loss is unmeasurable without a canary.
- `except Exception: return True` — converts missing/unparseable (rule says KEEP) into drop.
- Fallback chains (`event.get("seat") or event.get("campaign_seat")`) that pull a foreign field when seat is absent.

**(2) `int(seat)` coercion — verified semantics, by risk direction:**
- DROP-direction exists only via comparison-type asymmetry, never via `int()` itself: every successful parse is value-faithful, so our seat cannot parse to a foreign number. The dangerous line is membership without coercion (`"8"` vs `8`), in either typing direction.
- KEEP-direction (safe, but shows `int()` is the wrong parseability gate): `int(" 8 ")`→8, `int("+8")`→8, `int("08")`→8, `int("1_0")`→10, `int("٨")`→8 (U+0668), `int("８")`→8 (U+FF18). A foreign fullwidth-８ event is adjudicated as seat 8 and kept if 8 is ours.
- Silent adjudication of non-ints: `int(True)`→1, `int(8.9)`→8 (truncation). Rule says bool/float seats are unparseable→KEEP; bare `int()` will judge them anyway. `int(None)`→TypeError, `int("8.0")`→ValueError — the handler must map *both* exceptions to "not proven," not "not ours."
- If any comparison is string-based, NFKC on one side only makes `"８" != "8"`; direction depends on which side normalizes. Inspect; don't assume.

**(3) Hold on every path including drop — UNKNOWN.** Settles by call order: the dropped path must fall through the hold, not `return` at the predicate. Test: instrument the hold, replay one foreign event, assert hold count = 1.

**(4) Idempotent — UNKNOWN.** Settles by the hold's key: must be the stable upstream event/message id, not a per-receipt uuid or timestamp. Realistic duplicate source is webhook redelivery (n retries per failure). Test: replay byte-identical payload twice; assert hold count = 1 and identical outcome.

**(5) Crafted suppression — UNKNOWN, plus one spec hole I can name now:** "proves it sits on a seat **or** campaign we do not operate" is undefined when dimensions disagree. Input `{"campaign_id": <ours>, "seat": <foreign>}` — if implemented as `foreign_seat or foreign_campaign`, this DROPS an event on our campaign; a webhook POST with chosen fields then suppresses an alert it should raise. The predicate must be AND-of-proofs (both dimensions present-and-foreign) or treat disagreement as doubt→keep. Also verify which fields are sender-controlled: string-matching a client-forgeable campaign *name* (vs id) is spoofable in both directions.

**One measurable control:** every failure mode above is *silent suppression* — no metric moves, by design. Ship a canary: one synthetic our-seat event per day per release, asserted to raise UNMATCHED_REPLY. Without it, a fail-open regression at any scale produces zero signal until a human notices a reply that never got answered.

