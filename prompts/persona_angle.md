# persona_angle

Domains lane. You are given the client's configured personas and angles, the
trimmed company facts, and one contact.

Return JSON only:

```json
{"angle": "one of the client's configured angle keys",
 "evidence": ["each item traceable to company_facts or the contact record"]}
```

Rules:

- `angle` must be a KEY of the `angles` object you were given, copied exactly.
  Not a new one, not the phrase the key maps to, and not the name of a persona.
  An angle that is not one of those keys is rejected and the step is retried.
  If `angles` is empty there is no answerable angle: say so rather than
  inventing one.
- Every element of `evidence` must be traceable to `company_facts` or the
  contact record. Evidence that cannot be traced is rejected and the step is
  retried. Do not paraphrase into something the record does not say.
- Evidence is the reason this person gets this angle, not a description of the
  product.
