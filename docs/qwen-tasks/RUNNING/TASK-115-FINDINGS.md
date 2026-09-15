# TASK-115: The diversity check asks a binary question about a five-valued design

## VERDICT: The declared opening is NOT consistently honored in the generated copy

This is a **generation defect**, not a measurement defect. The approaches declare five opening types (statement, question, pain, evidence, outcome), but the model does not consistently honor them. Comparing declared values would compare labels rather than copy, and a check that compares labels passes five identical messages that merely carry five different tags.

---

## HAND-JUDGED EVIDENCE PER APPROACH

Generated against the real model on aubryandco.com (li2, li3, li4), 2026-09-15.

### li2 (first LinkedIn message after connection note)

| Approach | Declared | Actual Opening | Honored? |
|----------|----------|----------------|----------|
| concise_direct | statement | "i'm jamal fraiser from a&co." | ✅ YES |
| conversational | question | "hi jamal, how do you currently get visibility..." | ✅ YES |
| problem_led | pain | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |
| observation_led | evidence | "hi jamal, i noticed a&co's impressive work..." | ✅ YES |
| value_led | outcome | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |

**li2 verdict**: 3/5 honored. problem_led and value_led both open with an introduction instead of pain/outcome.

### li3 (second LinkedIn message)

| Approach | Declared | Actual Opening | Honored? |
|----------|----------|----------------|----------|
| concise_direct | statement | "hi jamal, i'm jonathon from a&co." | ✅ YES |
| conversational | question | "hi jamal, how do you currently handle..." | ✅ YES |
| problem_led | pain | "hi jamal, without clear visibility on resource planning, teams often scramble..." | ✅ YES |
| observation_led | evidence | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |
| value_led | outcome | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |

**li3 verdict**: 3/5 honored. observation_led and value_led both open with an introduction instead of evidence/outcome.

### li4 (third LinkedIn message - product introduction rung)

| Approach | Declared | Actual Opening | Honored? |
|----------|----------|----------------|----------|
| concise_direct | statement | "hi jamal, i'm reaching out from Productive..." | ✅ YES |
| conversational | question | "hi jamal, i'm reaching out from productive..." | ❌ NO - introduction |
| problem_led | pain | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |
| observation_led | evidence | "hi jamal, i'm reaching out from productive..." | ❌ NO - introduction |
| value_led | outcome | "hi jamal, i'm jonathon from productive." | ❌ NO - introduction |

**li4 verdict**: 1/5 honored. Only concise_direct opens with the declared type. All others open with an introduction.

---

## AGGREGATE VERDICT

| Approach | Honored (li2) | Honored (li3) | Honored (li4) | Total |
|----------|---------------|---------------|---------------|-------|
| concise_direct | ✅ | ✅ | ✅ | **3/3 (100%)** |
| conversational | ✅ | ✅ | ❌ | **2/3 (67%)** |
| problem_led | ❌ | ✅ | ❌ | **1/3 (33%)** |
| observation_led | ✅ | ❌ | ❌ | **1/3 (33%)** |
| value_led | ❌ | ❌ | ❌ | **0/3 (0%)** |

**Overall**: 7/15 openings honored (47%). The most common failure mode is opening with "hi [name], i'm [name] from [company]" - an introduction - instead of the declared opening type.

**value_led is NEVER honored.** It declares "outcome" but always opens with an introduction.

---

## THE HONEST COUNT OF MATERIALLY DIFFERENT LINKEDIN ARMS

Today, the honest count is **two, not five**:

1. **concise_direct** - opens with a statement (always honored)
2. **conversational** - opens with a question (mostly honored)

The other three approaches (problem_led, observation_led, value_led) declare different opening types but the model does not consistently honor them. When they do honor the declaration, it is intermittent and unreliable.

**Five arms is a claim this system cannot yet make.** The generation does not reliably produce five materially different openings.

---

## WHY THIS IS A GENERATION DEFECT, NOT A MEASUREMENT DEFECT

The task asked: "should the diversity check compare the approach's declared SEMANTIC opening instead of, or alongside, the punctuation binary?"

**Answer: NO, not until the generation is fixed.**

If we compared declared values today:
- problem_led would be labeled "pain" but opens with "hi jamal, i'm jonathon from productive"
- value_led would be labeled "outcome" but opens with "hi jamal, i'm jonathon from productive"
- observation_led would be labeled "evidence" but opens with "hi jamal, i'm jonathon from productive"

A check that compares declared values would report these as different when they are structurally identical. That is the single most dangerous outcome available in this task: **a check that passes five identical messages that merely carry five different tags.**

The check must be derivable from the TEXT, not from the approach's own label. Today, the text does not match the label reliably enough to trust the label.

---

## WHAT MUST BE FIXED UPSTREAM

The approaches declare five opening types, but the model defaults to an introduction ("hi [name], i'm [name] from [company]") instead of honoring the declaration. This is a prompt engineering or generation defect, not a measurement defect.

**Possible causes:**
1. The approach descriptions are not strong enough to override the model's default greeting pattern
2. The rung purpose or context block is overriding the approach's structural instruction
3. The model has a strong prior for LinkedIn messages to open with an introduction

**What must happen before the check can be widened:**
1. Fix the generation so the declared opening is honored consistently (say, 90%+ of the time)
2. Validate the fix against the real model on multiple records
3. Only then consider widening the check to compare semantic openings

**Until then:** The diversity check correctly refuses every LinkedIn set, and that is the property worth protecting. The honest count of materially different LinkedIn arms per step is two, not five.

---

## MEASUREMENT DETAILS

- Record: aubryandco.com (aubryandco-com)
- Contact: Jamal Fraiser (Ceo)
- Sequence: productive_li_heavy_v1
- Steps measured: li2, li3, li4
- Model: OpenAI-compatible (from config/.env)
- Generated: 2026-09-15
- Variants files: work/task089_variants_li2.json, work/task089_variants_li3.json, work/task089_variants_li4.json
