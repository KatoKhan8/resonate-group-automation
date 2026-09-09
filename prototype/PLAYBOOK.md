# PLAYBOOK

Read this at the start of a batch session, then work the queue. You are the
reasoning layer. The scripts are the memory and the guardrail. Do not hold
batch state in your head and do not summarise records to yourself between
steps; read and write through `bin/rec.py` every time.

## The loop

```
python3 bin/rec.py list --state queued
```

For each record, in order. One record fully finished before the next, so a
session that runs out of context leaves a clean queue rather than half state.

### 1. Read

`bin/rec.py get <id>` — read `context` (revive) or `signal` (cold) in full.
Never skim. The thing that makes the email work is almost always one sentence
buried in the middle of a quoted reply.

### 2. Enrich

`ContactOut decision-makers(domain, reveal_info=true)`.

Compare against whoever appears in the thread. Three outcomes worth noticing:
the original contact is still there, the original contact has left, or the
company's real mail domain is not its website domain. All three change the email.

If ContactOut returns nothing usable, run `AI Ark people_search` on the same
company before giving up. Different index, different coverage.

### 3. Verify

`ContactOut email-verifier(address)` on every address you intend to use.

- `valid` — use it
- `invalid` — discard, never "try it anyway"
- `accept_all` — write it to the record, then `bin/verify.py` runs Reoon power
  mode on it. Only `is_safe_to_send: true` clears it
- `unknown` — treat as unusable unless it also appears in the thread history

Patch the contacts array back. If no contact clears, drop the record with a
reason. A batch with honest drops beats a batch with guessed addresses.

### 4. Diagnose (revive lane) or hook (cold lane)

**Revive.** Order the thread. Find the specific moment it broke. Write
`diagnosis.died_on`, `diagnosis.died_because`, `diagnosis.last_position`.
Classify `failure_mode` as one of:

| mode | what it looks like |
|---|---|
| `unanswered_question` | they asked something direct and never got an answer |
| `no_pass_mark` | trial or key issued with no benchmark, no date, no review booked |
| `minimum_not_price` | died on the upfront commitment, not the unit rate |
| `ignored_preference` | they said how they wanted to buy, we did the opposite |

"Went cold" is not a diagnosis. If you cannot name the day and the sentence,
say so in the record rather than inventing one.

**Cold.** `hook` must be one specific, checkable fact about them, from the
signal. If the hook would be true of fifty other companies, it is not a hook.

### 5. Size (optional, free)

`ContactOut people-count` costs nothing. When the pitch is data, put their
actual buying market in the email instead of your own headline number.
Write it to `sizing`.

### 6. Draft

Voice is the `sender` on the record. Constraints, all enforced by `build.py`:

- One unbroken line per paragraph. Blank line between paragraphs. No hard wrapping
- Under 180 words, over 40
- Subject under 60 characters, lowercase-ish, reads like a human wrote it
- No em dashes or en dashes
- No attachments, no "attached"
- No placeholders. If you don't have the number, don't bracket it, ask a
  question instead or drop the record for human input
- No filler openers. The banned list is in `build.py`

Shape that works, both lanes:

1. Name the specific thing. The date and the sentence, or the signal.
2. Own the failure if it was ours. No blame, no excuses, no "apologies for the delay".
3. One concrete piece of new information. A number, a change, an answer to the question they asked.
4. One question that is answerable in a single line. Never a calendar link as the ask.

Patch as `draft` with `state: "drafted"`.

### 7. Build and review

```
python3 bin/build.py
```

Read the lint output. Fix your own failures, do not lower the bar. Then the
human reads `out/review.html` and only the red ones need their attention.

## Rules that override everything

- If the record shows they are a live or paying customer, drop it. Cold sequences
  into live accounts is the single most expensive mistake in this whole motion.
- If they declined a call in writing, the email does not ask for a call.
- If a commitment in the draft needs the sender's authority to make (a price, a
  discount, an absorbed fee), do not invent it. Drop to `needs_input` in the note
  and let the human fill it.
- Never write an email you would not be happy for the recipient to forward to
  the person on our side who dropped the ball.
