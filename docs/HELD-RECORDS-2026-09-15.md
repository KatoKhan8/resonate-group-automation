# Held Records Analysis — 2026-09-15

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
**Queue:** 550 records total, 36 in state `held`
**`hold_reason` on any record:** none — the field does not exist in `src/`

---

## 1. Where `held` is set

Two writers in production code set `rec["state"] = "held"`:

| Writer | File | Line | Trigger | Reason available? |
|--------|------|------|---------|-------------------|
| `enrich.outcome()` | `src/enrich.py` | 1249 | Returns `"held"` when contacts have unresolved verdicts (`None`, `"unknown"`, `"accept_all"`) | Yes — `reason` is computed but is `None` for the hold branch (line 816: `return "held", None`) |
| `generate` loop | `src/generate.py` | 1795 | Catches `llm.ModelError` during draft/persona_angle generation | Yes — the exception message `e` is logged but not stored as a field |

Neither writer sets `hold_reason`. The `store.log()` call records a human-readable note in the `log[]` array, but no machine-readable field is populated. `funnel._reason()` looks for `hold_reason` and falls through to `"state held, no reason recorded"` every time.

A third mechanism — un-drop — sets state to `"held"` outside these two paths. The un-drop log entry (`step: "un-dropped"`) is written but no code in `src/` matches that step name; it appears to be a manual or script-level intervention that reinstates a dropped record into `"held"` pending re-enrichment.

---

## 2. Per-record classification

All 36 records have a reconstructable reason from their log entries and contact verdicts. **36 of 36 are reconstructable; 0 are not.**

### Category A — Enrichment verification holds (13 records)

Enrichment completed but contacts were not cleared. `enrich.outcome()` returned `"held"` because at least one contact has verdict `None`, `"unknown"`, or `"accept_all"`.

| # | Record | Contact verdicts | Sub-reason | Reconstructable |
|---|--------|-----------------|------------|-----------------|
| 1 | `20northmarketing-com` | `[None]` | Contact verdict never resolved; 0 provider calls | Yes — log: "enriched: 0 provider call(s)" |
| 2 | `321webmarketing-com` | `[accept_all, accept_all]` | accept_all_uncleared — reoon says catch-all not safe | Yes — verify log: "accept_all_uncleared" |
| 3 | `arcoagency-se` | `[None]` | Contact verdict never resolved; 2 provider calls | Yes — log: "enriched: 2 provider call(s)" |
| 4 | `adinmo-com` | `[accept_all]` | accept_all, no clearing provider | Yes — log: "enriched: 2 provider call(s)" |
| 5 | `tractorbeam-com` | `[accept_all, accept_all]` | accept_all, no clearing provider | Yes — log: "enriched: 2 provider call(s)" |
| 6 | `mcompany-com` | `[None, accept_all, None, None, None, None]` | catch-all cleared by reoon, only 1 of 2 confirmations | Yes — verify log: "catch-all cleared by reoon, but only 1 of 2" |
| 7 | `zuzudigital-com` | `[accept_all]` | accept_all, no clearing provider | Yes — log: "enriched: 3 provider call(s)" |
| 8 | `divisiond-com` | 16× `[None]` | All contacts unresolved; 1 provider call | Yes — log: "enriched: 1 provider call(s)" |
| 9 | `swipemarket-com` | `[accept_all]` | accept_all, no clearing provider | Yes — log: "enriched: 2 provider call(s)" |
| 10 | `revupdental-com` | `[]` (no contacts) | No contacts found; enrichment held | Yes — log: "enriched: 2 provider call(s)" |
| 11 | `creativefruit-co` | `[]` (no contacts) | No contacts found; enrichment held | Yes — log: "enriched: 2 provider call(s)" |
| 12 | `atypiccraft-com` | `[]` (no contacts) | No contacts found; enrichment held | Yes — log: "enriched: 3 provider call(s)" |
| 13 | `pomplunspanier-com` | `[valid]` | Verifiers disagree: contactout says valid, reoon does not | Yes — verify log: "held (verifiers disagree)" |

### Category B — Generation model errors (14 records)

`generate` caught `llm.ModelError` (raised by `llm.py:837` as `SchemaError` after 3 failed attempts). The record was in or past enrichment and the model could not produce a valid persona_angle or draft.

| # | Record | Error | Sub-category |
|---|--------|-------|--------------|
| 1 | `2ton-com` | evidence not traceable to record | Evidence traceability |
| 2 | `yesandagency-com` | evidence not traceable to record | Evidence traceability |
| 3 | `seismicproductions-com` | evidence not traceable to record | Evidence traceability |
| 4 | `cyclonesocial-com` | evidence not traceable to record | Evidence traceability |
| 5 | `gracecreativela-com` | evidence not traceable to record | Evidence traceability |
| 6 | `codexglobal-net` | evidence not traceable to record | Evidence traceability |
| 7 | `academyxi-com` | evidence not traceable to record | Evidence traceability |
| 8 | `hartinc-com` | evidence must be a non-empty list | Evidence empty list |
| 9 | `ironcladmktg-com` | evidence must be a non-empty list | Evidence empty list |
| 10 | `aheadgroup-se` | evidence must be a non-empty list | Evidence empty list |
| 11 | `eliassen-com` | evidence must be a non-empty list | Evidence empty list |
| 12 | `surface51-com` | answer was not JSON | JSON parse failure |
| 13 | `nineyards-ie` | no draft passed lint (empty completion) | Lint failure / empty completion |
| 14 | `grayloon-com` | no draft passed lint | Lint failure |

### Category C — Un-drop pending re-enrichment (9 records)

These records were dropped (asserting no contact at domain), then reinstated when contacts were found. The un-drop mechanism set state to `"held"` pending re-enrichment, but no subsequent enrichment pass has cleared them.

| # | Record | Contacts on record | Original drop reason |
|---|--------|-------------------|---------------------|
| 1 | `blackdoggraphix-com` | 1 (verdict: None) | "no contact at domain, 1 set aside by identity check" |
| 2 | `omediaparis-com` | 0 | "no contact at domain, 5 set aside by identity check" |
| 3 | `modernmediahub-nl` | 1 (verdict: None) | "no contact at domain, 1 set aside by identity check" |
| 4 | `eyestormcreative-com` | 0 | "no contact at domain, 1 set aside by identity check" |
| 5 | `alligence-com` | 0 | "no contact at domain, 2 set aside by identity check" |
| 6 | `brandink-com` | 0 | "no contact at domain, 1 set aside by identity check" |
| 7 | `pdmg-expo-eu` | 0 | "no contact at domain, 1 set aside by identity check" |
| 8 | `businesswithgems-com` | 1 (verdict: None) | "no contact at domain, 2 set aside by identity check" |
| 9 | `forceofnatu-re` | 0 | "no contact at domain, 2 set aside by identity check" |

---

## 3. Actionability classification

| Classification | Count | Deciding field | Meaning |
|----------------|-------|----------------|---------|
| **RETRYABLE** | 12 | `log[-1].step` ∈ {persona_angle, draft}, `"held:"` in note | Model failed 3 attempts; a retry with a different model or more evidence may succeed. 7 evidence-traceability, 4 evidence-empty-list, 1 JSON parse. |
| **WAITING** | 9 | Contact verdicts contain `accept_all` or `None` | Verification cannot clear with current providers. Needs a clearing provider, manual verification, or a policy decision on accept_all domains. |
| **ACTIONABLE** | 9 | `log` contains `step: "un-dropped"` | Re-enrichment will resolve these. Contacts exist (or were found) but enrichment has not re-run since the un-drop. |
| **HUMAN_REVIEW** | 3 | Verifiers disagree, or lint failures with no clear path | `pomplunspanier-com` (verifier disagreement), `nineyards-ie` and `grayloon-com` (drafts that will not pass lint — may need manual copy). |
| **PERMANENT** | 3 | No contacts, no path to find more | `revupdental-com`, `creativefruit-co`, `atypiccraft-com` — enrichment found no contacts and the record has been held since. Should be dropped with reason. |

**Reconstructable: 36 of 36.** Every held record has enough data in its log entries and contact verdicts to determine why it is held. The information exists; it is just not in a machine-readable field.

---

## 4. Proposed writer change

The smallest change that makes every future hold carry a machine-readable reason is **two lines in two files**, both setting `rec["hold_reason"]` at the exact point where `rec["state"] = "held"` is already written:

### Change 1: `src/enrich.py`, function `outcome()` at line 816

Current:
```python
    if unresolved:
        return "held", None
```

Proposed:
```python
    if unresolved:
        reasons = []
        for c in unresolved:
            v = c.get("verdict")
            reasons.append(f"{c.get('email','?')}: {v}" if v else f"{c.get('email','?')}: no verdict")
        return "held", "; ".join(reasons)
```

This changes the `None` reason to a descriptive string. The caller at line 1249-1251 already writes `reason` to the log and would need one additional line:

```python
    rec["state"] = state
    if state == "held":
        rec["hold_reason"] = reason
```

### Change 2: `src/generate.py`, exception handler at line 1792-1795

Current:
```python
        except llm.ModelError as e:
            store.log(rec, op["step"], f"held: {e}")
            if rec.get("state") not in ("dropped", "pushed"):
                rec["state"] = "held"
```

Proposed:
```python
        except llm.ModelError as e:
            store.log(rec, op["step"], f"held: {e}")
            if rec.get("state") not in ("dropped", "pushed"):
                rec["state"] = "held"
                rec["hold_reason"] = f"generation:{op['step']}:{e}"
```

### Change 3 (optional): un-drop mechanism

Wherever the un-drop sets state to `"held"` (not in `src/` — likely a script or manual operation), add `rec["hold_reason"] = "undrop:pending_reenrichment"`.

### Why this is the minimum

- Two files, three insertion points, one new field (`hold_reason`).
- No schema migration needed — the field is simply absent on old records and present on new ones. `funnel._reason()` already checks for it (line 111: `for field in ("drop_reason", "hold_reason", "pause_reason")`).
- No new module, no new abstraction, no change to the state machine.
- `store.VALID_STATES` does not need updating — `hold_reason` is a data field, not a state.

---

## 5. Summary

| Metric | Value |
|--------|-------|
| Total held | 36 |
| Reconstructable | 36 (100%) |
| Not reconstructable | 0 |
| Writers that set held | 2 (`enrich.outcome`, `generate` exception handler) |
| Writers that set `hold_reason` | 0 |
| RETRYABLE | 12 (generation model errors) |
| WAITING | 9 (verification unresolved) |
| ACTIONABLE | 9 (un-drop pending re-enrichment) |
| HUMAN_REVIEW | 3 (verifier disagreement, lint failures) |
| PERMANENT | 3 (no contacts, should drop) |
| Proposed change | 2 files, 3 insertion points, 1 new field |
