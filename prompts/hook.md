# hook

Cold lane. You are given the signal that triggered this record, and the
company facts already gathered from providers.

Return JSON only:

```json
{"hook": "one specific, checkable fact about them"}
```

Rules:

- If the hook would be true of fifty other companies, it is not a hook.
- It must be checkable against the record. No inference about their strategy,
  their pain, or their plans.
- One sentence.
