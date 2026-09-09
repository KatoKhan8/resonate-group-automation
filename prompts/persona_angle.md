# persona_angle

Domains lane. You are given the client's configured personas and angles, the
trimmed company facts, and one contact.

Return JSON only:

```json
{"angle": "one of the client's configured angle keys",
 "evidence": ["each item traceable to company_facts or the contact record"]}
```

Rules:

- `angle` must be one of the angles configured for that persona. Not a new one.
- Every element of `evidence` must be traceable to `company_facts` or the
  contact record. Evidence that cannot be traced is rejected and the step is
  retried. Do not paraphrase into something the record does not say.
- Evidence is the reason this person gets this angle, not a description of the
  product.
