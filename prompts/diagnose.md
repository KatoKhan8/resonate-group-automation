# diagnose

Revive lane. You are given one record: the CRM dump and the full thread,
verbatim, plus the contacts already verified on it.

Order the thread. Find the specific moment it broke.

Return JSON only:

```json
{"died_on": "YYYY-MM-DD or null",
 "died_because": "the specific thing that happened, naming the sentence",
 "failure_mode": "unanswered_question | no_pass_mark | minimum_not_price | ignored_preference",
 "last_position": "where the commercial conversation stopped, if there was one",
 "what_changed": "the honest reason to write today, or null"}
```

Rules, all enforced before your answer is stored:

- `failure_mode` is a closed enum. Those four covered every account in a
  29 account audit. A fifth category is a bug in this step, not a new category.
- "Went cold", "no response", "never replied" are rejected answers. Name the day
  and the sentence.
- If the date cannot be found, return `died_on: null` and say so in
  `died_because`. Do not invent one.
- Every specific claim must come from the record. Nothing you cannot point at.
