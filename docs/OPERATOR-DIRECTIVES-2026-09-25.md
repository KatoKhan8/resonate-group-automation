# RESONATE OS — ADDITIONAL OPERATOR DIRECTIVES

These instructions supplement the existing ARCHITECTURE-UPGRADE-SPEC.md and TASK-313.

Treat them as additional operator requirements for the current audit, implementation planning, and all subsequent development.

Do not replace or rewrite the existing architecture specification.

The primary objective is to ensure that all work is properly documented, version-controlled, tested, committed, and pushed to GitHub.

Repository:
https://github.com/KatoKhan8/resonate-group-automation

## 1. GITHUB IS THE SOURCE OF TRUTH

All development work must be saved to the existing GitHub repository.

No completed work should exist only in a local terminal session, temporary workspace, Claude conversation, Qwen session, or Slack message.

This applies to:

- Source code and configuration changes.
- Architecture specifications.
- Audit reports.
- Implementation plans.
- Task definitions.
- Research findings relevant to implementation.
- Test cases and test results.
- Migration scripts.
- Deployment documentation.
- Operational SOPs and agent skills.
- Relevant decisions and implementation notes.

Every completed task must produce a persistent, traceable GitHub artifact.

Do not store credentials, API keys, customer secrets, personal contact data, private prospect research, raw provider responses containing personal information, or other sensitive information in GitHub.

Store safe documentation, code, schemas, synthetic test fixtures, and references to protected data instead.

Never commit `.env` files, access tokens, API responses containing secrets, or production database exports.

Before committing, inspect the staged changes for secrets and sensitive information.

## 2. MANDATORY GIT WORKFLOW

At the beginning of every task:

1. Confirm the correct repository and working directory.
2. Check the current branch and working tree.
3. Fetch the latest remote changes.
4. Confirm the current HEAD and remote tracking branch.
5. Identify uncommitted changes from other tasks.
6. Avoid overwriting or accidentally committing unrelated work.

Use task-specific branches or isolated worktrees when multiple agents are working concurrently.

Do not allow Claude and Qwen to modify the same working tree simultaneously without coordination.

For each completed task:

1. Save all relevant files in the repository.
2. Review the complete diff.
3. Run the appropriate tests and validation checks.
4. Record actual test results.
5. Stage only the files belonging to that task.
6. Commit with a descriptive message referencing the task ID.
7. Push the commit to the appropriate remote branch.
8. Verify that the remote branch contains the commit.
9. Report the exact commit SHA and GitHub URL.

A local commit is NOT sufficient.

A successful task requires confirmation that the commit exists on GitHub.

If a push fails, resolve the problem or report the exact blocker.

Never claim that work has been saved to GitHub unless the remote commit has been verified.

Do not use force push to overwrite other agents' work.

Do not automatically merge incomplete or unreviewed changes into master.

## 3. TASK-313: AUDIT DELIVERABLES

Continue the existing TASK-313 audit.

The audit must inspect the actual codebase and identify:

- Confirmed bugs.
- Architectural limitations.
- Missing functionality.
- Existing functionality that can be reused.
- Modules that exist but are disconnected from operational workflows.
- Duplicate functionality.
- Production integration risks.
- Missing tests.
- Data integrity risks.
- Unnecessary complexity.

Do not assume a feature is missing without inspecting the relevant files and functions.

Distinguish verified findings from recommendations and hypotheses.

The audit must include exact file paths and relevant function names.

Save the completed report to:

docs/AUDIT-2026-09-26.md

Commit and push the report to GitHub.

Verify the remote commit before reporting completion.

Do not mark TASK-313 as completed until the audit report is available on GitHub.

If the audit is incomplete, document what remains unverified instead of claiming full completion.

## 4. VERIFY THE EXISTING HEYREACH CADENCE

The previous log identified a potential discrepancy between the configured HeyReach graph and the number of steps actually reaching the provider.

This requires explicit investigation.

Trace the entire workflow:

Campaign configuration → Cadence graph → LinkedIn message generation → Provider mapping → HeyReach API payload → Provider response → Campaign preview.

Determine whether all configured steps are preserved.

Check:

- Connection request.
- Follow-up messages.
- Step ordering.
- Delays.
- Sender assignment.
- Personalization variables.
- Message bodies.
- Provider-specific step types.
- Unsupported provider operations.
- Campaign preview consistency.

Compare the internal cadence with the actual provider payload and returned campaign configuration.

Do not assume that a successful API response proves that every step was correctly configured.

If a six-step graph produces only one provider step, identify the exact location where the remaining steps are lost.

Add regression tests that fail when a configured step is silently omitted.

Preserve the existing multi-step HeyReach cadence.

Do not reduce the number of LinkedIn steps.

Do not modify active HeyReach campaigns during this investigation.

## 5. VERIFY CROSS-CHANNEL REPLY STOPPING

The previous log also identified that email-to-LinkedIn stopping has not been fully validated.

Investigate this as a separate production safety requirement.

Verify both directions:

Email reply → Stop pending LinkedIn outreach.

LinkedIn reply → Stop pending email outreach.

Check:

- Contact identity matching across providers.
- Account-level identity resolution.
- Reply ingestion.
- Reply classification.
- Pending step cancellation.
- Provider campaign removal or pause behavior.
- Duplicate webhook handling.
- Retry behavior.
- Delayed events.
- Race conditions.
- Suppression propagation.
- Audit logging.

A reply must not be considered successfully processed merely because an internal database status changed.

Confirm that the relevant provider-side action actually occurred.

Use synthetic events and safe integration tests wherever possible.

Any live provider test must be separately authorized and must not affect existing active campaigns.

Document which scenarios are confirmed by tests and which still require live validation.

If cross-channel stopping is unverified, do not label it production-ready.

## 6. CONNECT EXISTING MODULES BEFORE BUILDING NEW ONES

The previous audit identified that some existing modules may not be connected to the workflows that should consume their output.

For every proposed new module, first answer:

1. Does equivalent functionality already exist?
2. Where is the current source of truth?
3. Which existing module produces the required data?
4. Which module should consume that data?
5. Is the problem missing functionality or missing integration?
6. Can the requirement be implemented by extending an existing module?

Specifically inspect:

- Client configuration.
- Research packs.
- Context packs.
- Playbooks.
- Campaign strategy.
- Signal scoring.
- Copy generation.
- Learning and reporting.

The Client Second Brain must build on existing infrastructure.

Do not create a parallel database containing duplicated client facts.

Every fact must have one canonical source of truth, with source information and date.

The system should retrieve and reuse existing knowledge instead of repeatedly researching the same information.

Every new module must have an identified consumer.

A module that generates data nobody uses is not a completed feature.

## 7. PRESERVE THE CURRENT OUTREACH ARCHITECTURE

The existing five-step email cadence is mandatory.

Preserve the current threading:

Email 1: New thread, subject A.

Email 2: Reply to thread A.

Email 3: New thread, subject B.

Email 4: Reply to thread B.

Email 5: New breakup thread, subject C.

Preserve the existing multi-step HeyReach cadence.

The proposed two-offer strategy refers to TWO CAMPAIGN OFFERS, not two outreach messages.

The Offer Engine should improve the strategic quality of all five email messages and the existing LinkedIn sequence.

Do not shorten the cadence.

Do not change active campaign schedules.

Do not change existing provider campaign configurations without explicit approval.

## 8. PHASE 1 SCOPE CONTROL

Follow the operator overrides already recorded in the previous session.

Deployment environment: Hetzner, not Railway.

Do not introduce Railway-specific deployment changes.

Do not implement Reddit or Google Reviews integration in Phase 1.

Start with five skills:

1. Account Research.
2. Signal Verification.
3. Campaign Strategy.
4. Cold Email Writing.
5. LinkedIn Writing.

Additional skills can be introduced in later phases.

Build the Client Second Brain using existing client configuration, research, playbooks, context packs, and documentation.

The Offer Engine must use confirmed client capabilities and approved commercial terms.

Where a real offer is missing, record the gap and request the required information from the operator.

Do not invent commercial offers.

Use the existing model strategy unless a change is justified:

Groq and Qwen for research, extraction, relevance assessment, and semantic validation.

Sonnet for prospect-facing copy.

Preserve existing quality gates, approval mechanisms, spending limits, and provider safeguards.

Do not expand Phase 1 unnecessarily.

## 9. PROTECT EXISTING CAMPAIGNS AND DELIVERY PRIORITIES

The architecture upgrade must not interfere with the existing operational priorities.

Preserve:

- The existing ten-lead V2 review.
- The planned 50-lead batch.
- The existing cutover plan.
- Active campaigns.
- Historical campaign data.
- Current sender configurations.
- Existing provider integrations.

The architecture upgrade should proceed through isolated tasks and reviewed changes.

Do not deploy unfinished architecture changes into production.

Do not silently migrate existing campaigns to a new copy engine.

Any migration must have an explicit plan, validation criteria, and rollback procedure.

Nothing should be sent or activated as part of the architecture audit.

## 10. TESTING AND ACCEPTANCE CRITERIA

Every implementation task must define acceptance criteria before coding.

Tests must verify the actual behavior of the changed functionality.

For the copy engine, include tests for:

- Five email steps.
- Correct threading.
- Correct subject assignment.
- Two approved campaign offers.
- No unsupported commercial claims.
- No invented research.
- No unresolved personalization variables.
- Correct sender identity.
- Correct signature rendering.
- Correct LinkedIn step generation.
- No silent loss of cadence steps.
- Cross-channel coordination.
- Existing suppression and approval protections.

Do not claim that tests passed without executing them.

If a test cannot be executed, report it as NOT RUN.

If an integration requires live validation, report it as LIVE VALIDATION REQUIRED.

Do not substitute mocked provider responses for proof of real provider behavior.

Record the relevant test results in the task documentation.

## 11. MANDATORY GITHUB VERIFICATION

At the end of every task, provide a completion report containing:

TASK ID:

TASK NAME:

STATUS:

FILES CREATED:

FILES MODIFIED:

TESTS EXECUTED:

TEST RESULTS:

KNOWN LIMITATIONS:

LOCAL COMMIT SHA:

REMOTE COMMIT SHA:

GITHUB COMMIT URL:

BRANCH:

MERGE STATUS:

DEPLOYMENT STATUS:

PRODUCTION IMPACT:

NEXT TASK:

A task is not complete if the relevant files exist only locally.

A task is not complete if the GitHub push failed.

A task is not complete if the reported commit cannot be verified on the remote.

If the task is intentionally audit-only, the required deliverable is the committed audit report, not code changes.

## 12. NEXT ACTIONS

Continue the existing workflow in this order.

FIRST:

Confirm that docs/ARCHITECTURE-UPGRADE-SPEC.md and the TASK-313 task definition exist on the remote GitHub repository.

Report their exact commit SHAs and GitHub URLs.

SECOND:

Continue the TASK-313 audit.

Include the HeyReach cadence discrepancy and cross-channel stopping validation as explicit findings requiring investigation.

Do not claim either issue is resolved without evidence.

THIRD:

Complete the audit report and push it to GitHub.

Verify the remote commit.

FOURTH:

Prepare the Phase 1 implementation plan with exact files, dependencies, acceptance criteria, risks, and task breakdown.

Save the plan in the repository.

Commit and push it.

FIFTH:

Present the implementation plan for operator approval.

Do not begin Phase 1 implementation before approval.

Do not interrupt the existing ten-lead, 50-lead, or cutover priorities.

FINAL RULE:

Every meaningful piece of work must be reproducible from GitHub.

If the local machine or Claude session disappears, another engineer must be able to clone the repository, read the documentation, understand the current state, and continue the work without relying on conversation history.

GitHub is the persistent source of truth.

Start by verifying the existing remote commits, then continue TASK-313.

## 13. THE WORKFORCE (standing order, permanent, 2026-09-26)

Qwen does all heavy lifting.

The pool runs at 100% capacity at all times, with a queue of at least two or three ready tasks per worker waiting behind the running one.

Claude orchestrates only:

- writes tasks with acceptance checks,
- verifies artifacts,
- merges,
- pushes,
- reports.

Claude does not implement.

When the queue drops below two ready tasks per worker, Claude refills it from the standing backlog - phase 1 tasks, pipeline batches, ingest, ledger write-back, reconciliation checks, QA, docs - before doing anything else.

Every status report must show:

- workers running,
- tasks queued per worker,
- tasks completed and verified since the last status.

A queue under two ready tasks per worker is reported as a DEFECT.

An idle worker is reported as a DEFECT.
