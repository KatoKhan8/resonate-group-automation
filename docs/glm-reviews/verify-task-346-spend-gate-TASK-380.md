# GLM Verification: TASK-346 — Model Spend Ceiling

**Reviewer:** GLM (independent pass, TASK-380)
**Date:** 2026-09-26
**Target commit:** `1a6d650d` (Integrate TASK-346)
**Current master:** `0077c76e`
**Files reviewed:** `src/llm.py`, `src/providers/glm.py`, `src/spendledger.py`,
`tests/test_model_spend_counts_against_the_client.py`

---

## 1. Ceiling-refusal claim: REPRODUCED

**Claim:** A second `complete()` call under an exceeded ceiling raises
`BudgetExceeded` naming "PROVIDER CEILING" or "CLIENT CEILING", and the
provider is NOT called.

**Independent reproduction (script, not test file):**

- Provider ceiling (anthropic per_day=1): `BudgetExceeded` raised with message
  containing `"PROVIDER CEILING"` and `"anthropic"`. Provider called 0 times.
- Client ceiling (per_day=1): `BudgetExceeded` raised with message containing
  `"CLIENT CEILING"`. Provider called 0 times.

**Verdict: CONFIRMED.** The mechanism works as claimed.

---

## 2. TASK-373 finding: "nothing supplies a real client" — CONFIRMED CURRENT

Every `complete()` call site in production code was inspected:

| File | Line | Call | client= | config= |
|------|------|------|---------|---------|
| `src/campaignstrategy.py` | 119 | `model.complete(full_prompt)` | — | — |
| `src/generate_campaign.py` | 385 | `model.complete(system + "\n\n" + user)` | — | — |
| `src/llm.py` | 1085 | `model.complete(text)` (inside `ask()`) | — | — |
| `src/slackconversation.py` | 623 | `model.complete(prompt)` | — | — |
| `src/slackconversation.py` | 1623 | `model.complete(prompt)` | — | — |
| `src/slackconversation.py` | 1662 | `model.complete(...)` | — | — |
| `scripts/glm_review.py` | 555 | `glm.complete(prompt, ...)` | — | — |
| `scripts/glm_audit_safety.py` | 147 | `glm.complete(prompt, ...)` | — | — |
| `scripts/slack_agent_briefing.py` | 232 | `model.complete(...)` | — | — |
| `scripts/task077_detailed.py` | 63 | `model.complete(prompt)` | — | — |

**No call site passes `client` or `config`.** Every reservation lands on
`"unattributed"`. The mechanism is reachable (the parameters exist and the
tests prove they work) but no current production path supplies a real client
identity.

**Note:** `generate.generate_record()` accepts `client=` and threads it to
`persona_angle()`, `linkedin_note()`, etc., but those functions call
`llm.ask()` → `model.complete(text)` without forwarding client/config. The
`client` parameter reaches the planning layer but NOT the spend gate.

**Verdict: TASK-373 is CONFIRMED CURRENT.** The ceiling mechanism is correct
but inert in production.

---

## 3. Narrowed `except Exception` and named row for unknown provider

### 3a. Narrowed except in `src/llm.py` (OpenAICompatibleModel.complete)

```python
except spendledger.BudgetExceeded:
    raise
except Exception as e:                       # noqa: BLE001
    spendledger.release(hold)
    raise ModelUnavailable(...) from None
```

`BudgetExceeded` is explicitly re-raised BEFORE the broad handler. Without
this, the generic handler would release the hold and raise `ModelUnavailable`,
swallowing the ceiling refusal. **Correct.**

### 3b. Named row for unknown provider (`_detect_provider`)

```python
def _detect_provider(self):
    ...
    if self.base:
        from urllib.parse import urlparse
        host = urlparse(self.base).hostname or "unknown-model"
        return host.replace(".", "_")
    return "unknown-model"
```

An unrecognized base URL returns a name derived from the hostname (e.g.
`my-local-server_example_com`) rather than None. **Reproduced independently:**
a model at `https://my-local-server.example.com/v1` wrote a row with
`provider="my-local-server_example_com"`, `unit="microusd"`.

**Verdict: Both confirmed correct.**

---

## 4. New findings

None. The mechanism is correctly implemented and the tests are genuine. The
only finding is the already-known TASK-373 wiring gap.

---

## 5. Test suite verification

All 22 tests in `tests/test_model_spend_counts_against_the_client.py` pass:

```
Ran 22 tests in 0.209s
OK
```

---

## Summary

| Claim | Status |
|-------|--------|
| Ceiling refuses BEFORE provider is called | CONFIRMED |
| `BudgetExceeded` names the scope (PROVIDER/CLIENT CEILING) | CONFIRMED |
| Unknown provider gets a named row | CONFIRMED |
| Narrowed `except` preserves ceiling refusal | CONFIRMED |
| 22 tests pass | CONFIRMED |
| Production threads a real client to the gate | NOT CURRENT (TASK-373) |

**Disposition:** TASK-346's mechanism is correct and verified. TASK-373
(client threading) remains the open wiring gap. No new findings.
