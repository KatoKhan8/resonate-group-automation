# TASK-020 Report: Reply Classifier Changes

2026-09-14. Read-only analysis and code changes. Zero network, zero
credentials. All fixture bodies are invented.

## What changed

### 1. "No rule matched" is now UNKNOWN, not NEUTRAL

`src/replies.py` VERSION bumped from `rules-1` to `rules-2`. The fallback
when no rule matches and no model is available now returns
`{"classification": "unknown", "confidence": 0.0}` instead of
`{"classification": "neutral", "confidence": 0.5}`.

This is the single highest-value change in the task. On the live estate,
279 of 794 replies (35.1%) matched no rule and were reported as `neutral`.
NEUTRAL means "we read this and it is genuinely lukewarm" - a measurement.
UNKNOWN means "we could not read this" - a gap. Only one of them is a
measurement, and the estate was reporting the gap as if it were one.

A caller can now tell the two apart: `classification == "unknown"` and
`confidence == 0.0` means no rule matched; `classification == "neutral"`
means a model (or a future rule) read the text and judged it genuinely
mid-range.

### 2. Provider-flagged automated replies are marked and do not suppress

`replies.apply()` now sets `verdict["is_automated"] = True` when the
provider flagged the row as an automated reply. When `automated is True`
and the classification is NOT `out_of_office`, the policy application
(`accountpolicy.apply_reply()`) is skipped entirely - no HOLD or STOP
lands on the account because a mail server wrote back.

An out-of-office is the exception: it still defers the next touch (maps
to NOT_NOW outcome), which is what the operator instructed.

The classification event is still recorded for reporting. What changes is
that the policy effect is `None` for automated non-OOO replies.

### 3. Rule coverage raised with new patterns

New patterns added to five categories, all with tests on invented bodies:

- **UNSUBSCRIBE**: "stop sending", "no more emails", "remove me from your
  mailing list", "please don't send me any more emails"
- **NEGATIVE**: "not for me", "no need", "we're good", "don't need this",
  "not looking for this", "no interest at this time"
- **POSITIVE**: "yes, let's chat", "sure, happy to discuss", "let's do it",
  "I'm interested", "that sounds great", "send me a demo", "can we schedule"
- **NOT_NOW**: "maybe later", "not at this time", "get back to me sometime",
  "let's park this for now"
- **NOT_RELEVANT**: "not relevant for us", "doesn't apply to our team",
  "not something we need"

These are conservative additions - every pattern is clearly one category
and will not produce false positives on the existing test corpus.

### 4. Meeting decision: no split at the classifier level

The operator's hierarchy names MEETING separately from POSITIVE REPLY.
After analysis, the decision is NOT to split `positive` into `positive`
and `meeting` at the classifier level. Documented in code.

Reason: a meeting is determined by an action (calendar link accepted,
time agreed, meeting scheduled), not by words alone. "Let's talk Thursday"
is a positive reply until a calendar event exists. The classifier can flag
language that suggests a meeting, but confirming one requires observing a
downstream signal. The Slack alert already offers MARK_MEETING as an
action, which is where the distinction belongs: in a person's decision,
not in a pattern match.

### 5. Referral _points_at_somebody holds

Test added to prove that a hand-off phrase without a name is NOT
classified as referral, and one with a name IS. The existing guard in
`classify_rules()` already enforces this; the test pins it.

## The consumer chain: what exists and what does not

Traced: reply row → classification → canonical state → suppression → report.

| Link | Status |
|------|--------|
| Reply row → classification | EXISTS. `replies.classify()` and `replies.apply()`. |
| Classification → canonical state | EXISTS. `events.record(REPLY_CLASSIFIED)` and `accountpolicy.apply_reply()`. |
| Suppression | EXISTS. `accountpolicy.apply_reply()` sets HOLD/STOP per policy. |
| Report | EXISTS. `src/report.py` reads `REPLY_CLASSIFIED` events and counts classifications into `reply_breakdown`. |
| Automated flag → verdict | NEW. `verdict["is_automated"]` now set by `apply()`. |
| Automated flag → report | DOES NOT EXIST. The report counts classifications but does not separate automated from human. A reply breakdown that includes 84 automated replies in its "negative" count is overstating negative signal. |
| UNKNOWN → action | PARTIAL. UNKNOWN maps to the `reply.on_negative` policy (HOLD at contact scope). This is correct for safety - an unclassified reply holds the contact - but it means the 35% of replies that were UNKNOWN (previously reported as NEUTRAL) will now HOLD contacts rather than continue. This is the intended behavior: an unclassified reply should not let outreach continue blindly. |

### What is still broken

1. **The report does not separate automated from human replies.** The
   `reply_breakdown` counter in `src/report.py` counts all
   `REPLY_CLASSIFIED` events equally. After this change, an automated
   negative reply is still classified as negative and still counted in the
   breakdown, even though no policy was applied. A report consumer cannot
   tell the difference without also reading the `is_automated` flag from
   the event, which `events.record()` does not currently carry.

2. **The upstream pause in `events.apply()` happens before classification.**
   `inbound.handle()` calls `events.apply()` which pauses the company on
   ANY reply event, before `replies.apply()` classifies it. This means an
   automated reply still pauses the company at the event level, even
   though `replies.apply()` now skips the policy application. The pause
   from `events.apply()` is a separate mechanism from the policy HOLD/STOP
   and is not affected by the `automated` flag. Fixing this requires
   changes to `src/inbound.py` or `src/events.py`, which are outside the
   FILES ALLOWED for this task.

3. **LinkedIn rule coverage is still much worse than email.** The new
   patterns help, but the estate measurement showed 70% unmatched on
   LinkedIn vs 35% on email. LinkedIn replies are short, casual,
   frequently not in English, and often a single clause. The email rules
   do not transfer directly. A separate LinkedIn-specific rule set or a
   model-backed classifier is needed to close that gap. This task improved
   the floor but did not solve the LinkedIn problem.

## Tests

59 tests in `tests/test_replies.py`, all passing. New tests cover:
- Unmatched returns UNKNOWN, not NEUTRAL
- UNKNOWN and NEUTRAL are distinguishable by callers
- New unsubscribe, negative, positive, not_now, not_relevant patterns
- Referral requires _points_at_somebody
- Automated reply marked in verdict
- Automated non-OOO does not apply policy
- Automated OOO still defers
- Non-automated and automated=None apply policy normally

124 tests across related test files (test_inbox, test_conversation,
test_reply_transitions, test_reply_high_water, test_reply_escalation),
all passing.

## Files changed

- `src/replies.py` - VERSION bump, UNKNOWN fallback, automated handling,
  new patterns, meeting decision documented
- `tests/test_replies.py` - updated existing tests for UNKNOWN fallback,
  added new test class TestAutomatedReplies, added pattern tests
