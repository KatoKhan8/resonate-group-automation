PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-406 — GLM first-pass verification: TASK-396 (training-pair capture, finding only)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-396, in REVIEW on `qwen-worker-7-r9` — its own commit says "nothing
captures a training pair — finding only." Verify the NEGATIVE finding
itself: is it actually true that no training-pair capture exists, or did
the worker miss one?

## What GLM's pass must produce

1. Your own grep/trace for anything resembling training-pair capture
   (prompt+output+verdict), independent of the worker's search terms.
2. Confirm or refute "nothing exists" as the honest current state.
3. Any new finding, file:line.

## Result

**STATUS:** REVIEW
**COMMIT:** (pending)
**TESTS:** N/A - verification-only task, no code changed
**FILES CHANGED:** This task file only
**ARTIFACT KIND:** Finding (verification of TASK-396's finding)

### Independent verification: TASK-396's finding HOLDS

I traced the same question with my own search terms, independent of the
worker's paths. The finding is correct: **nothing in the current codebase
captures a training pair (prompt + output + verdict).**

### My own grep/trace

**Search terms used (different from worker's):**
- `prompt.*output|input.*output|prompt.*response` - found 5 matches, all
  descriptive comments or pricing fields, none storing content
- `training.*pair|pair.*training|feedback.*loop|annotation` - 0 matches
- `dataset|corpus|examples.*jsonl|samples.*jsonl` - 64 matches, all about
  the synthetic benchmark dataset, Apify research datasets, or cohort
  analysis, none about training pairs
- `label|verdict|approved.*output|rejected.*output` - 1933 matches, all
  operational verdicts (channel eligibility, ICP status, variant ranking),
  none linking prompt+output+human verdict
- `training|fine.?tun|fine_tun` - 0 matches in src/
- `prompt.*store|store.*prompt|save.*prompt|prompt.*save` - 2 matches:
  `generate.py:35` defines a PROMPTS directory path (for prompt templates,
  not stored outputs), `llm.py:208` explicitly says "The raw payload carries
  the prompt back and is not stored anywhere"
- `output.*store|store.*output|save.*output|output.*save` - 1 match:
  `candidateexport.py:175` writes exports to an output directory, not
  training data
- `jsonl.*prompt|prompt.*jsonl|jsonl.*output|output.*jsonl` - 0 matches
- `append.*pair|pair.*append|write.*pair|pair.*write` - 15 matches, all
  about duplicate detection, lead pairing, or pairing labels, not training
  pairs
- `work.*training|training.*work` - 0 matches
- `reviewapproval.*record|record.*reviewapproval` - 0 matches (no hook)
- `training.*count|count.*training` - 0 matches
- `prompt.*output.*verdict|input.*output.*label` - 0 matches
- `capture.*pair|pair.*capture` - 0 matches

**Files checked:**
- `src/training.py` - does NOT exist (glob confirmed)
- `work/training/` - does NOT exist (ls confirmed)
- `src/learning.py` - exists but is cohort analysis (observational statistics
  on which cohorts perform better), NOT training data capture
- `src/reviewapproval.py` - `record()` writes approval metadata (campaign,
  review_hash, by, source, note) but NOT the prompt text or approved content
- `src/llm.py` - `record_usage_since()` writes usage metrics (tokens, cost,
  model name, step) to `rec["model_calls"]`, NOT prompt text or output content
- `src/variants.py` - `evaluate()` ranks A/B test variants by outcome rates
  (exposures, replies, Wilson intervals), does NOT capture training pairs
- `work/*.jsonl` - 5 files found (provider-write-refusals, researchpack
  snapshots, retired queue snapshot), none are training data

**What does NOT exist:**
- No `src/training.py` module
- No `work/training/` directory
- No JSONL file storing prompt+output+verdict triples
- No function that hooks `reviewapproval.record()` to capture pairs
- No function that stores prompt text anywhere
- No function that stores model output text anywhere
- No function that links a model prompt to its output AND a later human verdict

**What TASK-310 describes but has not been built:**
`docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md`
specifies the capture: hook `reviewapproval.record()`, write one JSONL row
per approved pair to `work/training/`, with input (the prompt facts), output
(the approved copy), and metadata (hash, campaign, model, confidence). That
task is still in TODO.

### Disposition

**TASK-396's finding: CONFIRMED**

The negative finding is correct. No training-pair capture exists. This is a
valid finding, not a defect - the task explicitly permits this answer, and
TASK-310 describes the capture to build but is still in TODO.

**Disposition: FALSE POSITIVE → no, the finding holds**

The worker's search was thorough and the finding is accurate. No new finding
emerged from my independent trace.

### Protocol format (eight dispositions)

The protocol lists eight dispositions for GLM findings:
- FIXED + VERIFIED - N/A (no code to fix)
- EXISTING TASK - TASK-310 describes the capture to build
- NEW TASK - N/A (TASK-310 already exists)
- RUNTIME VERIFICATION REQUIRED - N/A (static proof sufficient)
- SUPERSEDED - N/A
- FALSE POSITIVE - The finding is NOT a false positive; it holds
- ACCEPTED DEFERRED RISK - N/A (not a risk, just unbuilt)
- OPERATOR DECISION REQUIRED - N/A

**This verification's disposition: EXISTING TASK (TASK-310)**

The finding is correct, and the work to address it (building the capture) is
already queued in TASK-310.

### Evidence

**File:line citations:**
- `src/llm.py:208` - "The raw payload carries the prompt back and is not
  stored anywhere"
- `src/llm.py:977-1005` - `record_usage_since()` appends usage metrics only
- `src/reviewapproval.py:97-115` - `record()` writes metadata only
- `src/variants.py:434-480` - `evaluate()` ranks variants, does not capture
- `src/learning.py:0-50` - module docstring: cohort analysis, not training
- `docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md` -
  the capture specification, still in TODO

**Reproducible commands:**
```
grep -rn "training" src/                    # 0 matches
ls src/training.py                          # does not exist
ls work/training/                           # does not exist
grep -rn "prompt.*store\|store.*prompt" src/  # 2 matches, neither stores content
grep -rn "jsonl.*prompt\|prompt.*jsonl" src/  # 0 matches
```

### FINDINGS

- TASK-396's negative finding is correct: no training-pair capture exists
- The three paths the worker traced (llm.record_usage_since,
  reviewapproval.record, variants.evaluate) were correctly identified and
  correctly characterised
- TASK-310 describes the capture to build and is still in TODO
- No new finding emerged from independent verification

### RISKS

- None from this verification (read-only investigation)

### RECOMMENDED CLAUDE ACTION

- Proceed with TASK-310 to build the capture, or defer if lower priority
- TASK-396 is complete: the finding is verified and honest
