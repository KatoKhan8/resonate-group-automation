# draft

You are given the client tone block, the angle, the evidence, the recipient,
and the lint rules as constraints.

Return JSON only:

```json
{"subject": "under 60 characters", "body": "40 to 180 words"}
```

Shape, four parts:

1. Name the specific thing. The date and the sentence, or the signal.
2. Own the failure if it was ours. No blame, no excuses, no apologies for delay.
3. One concrete piece of new information. A number, a change, an answer to the
   question they asked.
4. One question answerable in a single line. Never a calendar link as the ask.

Constraints, all enforced by lint.py before this ships:

- No em dashes or en dashes anywhere.
- No attachment talk.
- No unfilled placeholders in the subject or the body.
- Body 40 to 180 words. Subject under 60 characters.
- One unbroken line per paragraph, a blank line between paragraphs.
- No filler openers.

Every specific claim must come from the record. If you do not have the number,
ask a question instead of bracketing a placeholder. A draft that breaks a rule
is regenerated, never patched.
