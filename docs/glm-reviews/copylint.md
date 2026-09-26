# GLM adversarial review: copylint

_2026-09-26, file `src/copylint.py`_

## 1. BYPASS

**Primary: three refusal rules are pointed at `whole` (email bodies only), while the module's own `rendered = whole + "\n" + subjects + "\n" + extra` proves it knows subjects, P.S. lines and LinkedIn messages are prospect-read.**

- `untraceable(whole, pack)` — subjects, `ps`, `linkedin` never traceability-checked
- `buzzwords_in(whole)` — same blind spot
- `for earlier in bodies[:-1]` (finality) — same blind spot

Concrete call path:

```python
lead = {"id": "L1",
        "steps": [ ...five clean, traceable email bodies... ],
        "linkedin": {"connect":
          "Congrats on your $120M raise and your 40% headcount jump. "
          "This is my last note, so I will stop chasing here."}}
copylint.check_batch([lead], {})["refused"]   # -> False
```

Invented `$120M`, invented `40%`, false finality claim — zero rules fire, because only `UNRENDERED_RE`, `EMPTY_SENTENCE_RES` and `DASH_RE` see `rendered`. A buzzword-laden subject ("Seamless synergy with your $40M raise") also passes.

**Secondary:** `COMPANY_CLAIM` is a whitelist of 13 words (you/your/they/their/announced/launched/…). "Acme closed a $40M round in March" contains no trigger word, so its specifics are never extracted for tracing. Also `\b\d[\d,.]{1,}\b` requires ≥2 characters, so single-digit inventions ("8 of your posts") are never specifics at all.

**Tertiary:** `WARNING_RULES` is documented as "explicitly time-boxed to 2026-09-28" but no code enforces the date — the time box is a comment. After expiry the step-1-opener rule stays non-blocking until a human remembers.

## 2. WHO READS THIS OUTPUT?

- `report["rules"] = dict(RULES)` is written into every report and read by **nothing** — `report_lines` iterates the module-global `for name, why in RULES:`, not `report["rules"]`. Dead field, same shape as the INSUFFICIENT_DATA precedent.
- The gate itself lives entirely in the caller's `if report["refused"]`. And there is a live disconnection risk: `_subject`'s own docstring says the provider's sequence rows carry "`email_subject`/`email_body` and nothing else" — `_subject` was patched to read `email_subject`, but `_body(step)` still reads only `body`/`text`. Feed those rows in and every body reads as `""`, so **every lead fires `empty_step` and the batch refuses 100% of the time**. A gate that false-refuses everything during "get leads sending today" PROOF MODE gets dropped by its caller, and then `report_lines` has no reader at all.

## 3. A TEST THAT CANNOT FAIL

There are no tests in this file. The vacuous-green magnets if tests get written against it:

- `assert report["counts"][k] == len(report["offenders"][k])` — constructed from the same list in `check_batch`; tautological.
- `assert report["rules"] == dict(RULES)` — expectation identical to the thing checked.
- `check_batch([])` → `refused: False`, `report_lines` prints "PASSED" — an empty collection matching everything; any test asserting PASS-on-empty cannot fail.
- A test asserting `refused == False` for a `step1_without_pack_fact` offender tests the `WARNING_RULES` override against itself, not correctness.
