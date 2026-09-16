---
title: "Bison CONTROL Payload — Variable Resolution and Staging Data"
task: "TASK-167"
date: "2026-09-16"
builds_on:
  - "docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md"
  - "docs/BISON-COHORT-LIVE-2026-09-15.md"
---

# Bison CONTROL Payload — 2026-09-16

**TASK-167 deliverable.** Variable resolution, rendered text, gate verdicts, and the exact staging payload for the 17-contact CONTROL sequence.

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). No email address, person name, company name, or domain appears in this document. Body text shows `<name:HASH>` and `<company:HASH>` placeholders.

## 1. Per-Contact Variable Resolution

| # | domain_hash | name_hash | first_name | company | angle_phrase | angle_word | sector | line | fallbacks |
|---|-------------|-----------|------------|---------|--------------|------------|--------|------|-----------|
| 1 | da9fa0575ce8 | b6882cfd6d48 | <name:b6882cfd6d48> (contact.name) | <company:d04727ad8c34> (rec.company) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Marketing & Advertising (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 2 | 4efeb3fe2afd | 32ab93ceddc6 | <name:32ab93ceddc6> (contact.name) | <company:e0021595d160> (rec.company) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Marketing & Advertising (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 3 | c768a0660316 | dd4e53f0860a | <name:dd4e53f0860a> (contact.name) | <company:cb79987b5b25> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 4 | 68af8ce671c1 | 8cdfd2d06cae | <name:8cdfd2d06cae> (contact.name) | <company:0b074108431f> (rec.company) | utilisation and capacity acros (config.personas.angl) | utilisation and capacity (config.angle_labels) | Marketing & Advertising (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 5 | 63084828d69e | 33afc169e069 | <name:33afc169e069> (contact.name) | <company:3c2ffdae042b> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 6 | 3afb5e0010d9 | 04b2cd185949 | <name:04b2cd185949> (contact.name) | <company:28d156625850> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |
| 7 | 500976b76607 | 164c11029ec9 | <name:164c11029ec9> (contact.name) | <company:e3c4b280322a> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 8 | ceb55a89127b | aaaba6610b02 | <name:aaaba6610b02> (contact.name) | <company:2aa30d36d863> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 9 | 1203bef7ae16 | 2aa47f23fd95 | <name:2aa47f23fd95> (contact.name) | <company:3919702a36cb> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 10 | c3f09366d72f | d2844b2886b3 | <name:d2844b2886b3> (contact.name) | <company:09aa79e621e5> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |
| 11 | 395be3330be3 | c243e114f58c | <name:c243e114f58c> (contact.name) | <company:b8fbedce7c47> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Marketing Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 12 | f2f4b0d278ed | 4c0edf0fb2c4 | <name:4c0edf0fb2c4> (contact.name) | <company:5a422f505e8c> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |
| 13 | c3c9e6e49e77 | 177f9fa54bfb | <name:177f9fa54bfb> (contact.name) | <company:8c67236c3b7d> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 14 | a3a16ee58d26 | d4cebca2a680 | <name:d4cebca2a680> (contact.name) | <company:8c7260724ab3> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |
| 15 | 41da47c0397b | 0955c3c3cc63 | <name:0955c3c3cc63> (contact.name) | <company:c83c2cc6d6de> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |
| 16 | ddef577b8d3c | 3f3976404204 | <name:3f3976404204> (contact.name) | <company:c88cd6d09613> (company_facts.name) | profitability visible on Monda (config.personas.angl) | profitability on Monday (config.angle_labels) | Marketing Services (company_facts.industry) | (generic intro) (FALLBACK) | 1 |
| 17 | 947f2f9d81ff | 27c77cac3505 | <name:27c77cac3505> (contact.name) | <company:a6a205eb782d> (company_facts.name) | margin per project (FALLBACK (first angl) | project margin at month e (config.angle_labels) | Advertising Services (company_facts.industry) | (generic intro) (FALLBACK) | 2 |

## 2. Contacts That Cannot Render

**None.** All 17 contacts have a resolvable `company` name. No contact is blocked.

## 3. Lint Verdict

| # | step | day | words | subject_len | verdict | failures |
|---|------|-----|-------|-------------|---------|----------|
| 1 | persona_pain | 1 | 104 | 50 | PASS | - |
| 1 | comparable_proof | 5 | 87 | 50 | PASS | - |
| 1 | breakup | 21 | 82 | 16 | PASS | - |
| 2 | persona_pain | 1 | 110 | 50 | PASS | - |
| 2 | comparable_proof | 5 | 89 | 50 | PASS | - |
| 2 | breakup | 21 | 84 | 16 | PASS | - |
| 3 | persona_pain | 1 | 106 | 50 | PASS | - |
| 3 | comparable_proof | 5 | 88 | 50 | PASS | - |
| 3 | breakup | 21 | 83 | 16 | PASS | - |
| 4 | persona_pain | 1 | 105 | 45 | PASS | - |
| 4 | comparable_proof | 5 | 88 | 51 | PASS | - |
| 4 | breakup | 21 | 81 | 16 | PASS | - |
| 5 | persona_pain | 1 | 106 | 50 | PASS | - |
| 5 | comparable_proof | 5 | 88 | 50 | PASS | - |
| 5 | breakup | 21 | 83 | 16 | PASS | - |
| 6 | persona_pain | 1 | 101 | 18 | PASS | - |
| 6 | comparable_proof | 5 | 88 | 54 | PASS | - |
| 6 | breakup | 21 | 78 | 16 | PASS | - |
| 7 | persona_pain | 1 | 106 | 50 | PASS | - |
| 7 | comparable_proof | 5 | 88 | 50 | PASS | - |
| 7 | breakup | 21 | 83 | 16 | PASS | - |
| 8 | persona_pain | 1 | 100 | 50 | PASS | - |
| 8 | comparable_proof | 5 | 86 | 50 | PASS | - |
| 8 | breakup | 21 | 81 | 16 | PASS | - |
| 9 | persona_pain | 1 | 103 | 50 | PASS | - |
| 9 | comparable_proof | 5 | 87 | 50 | PASS | - |
| 9 | breakup | 21 | 82 | 16 | PASS | - |
| 10 | persona_pain | 1 | 98 | 18 | PASS | - |
| 10 | comparable_proof | 5 | 87 | 54 | PASS | - |
| 10 | breakup | 21 | 77 | 16 | PASS | - |
| 11 | persona_pain | 1 | 106 | 50 | PASS | - |
| 11 | comparable_proof | 5 | 88 | 50 | PASS | - |
| 11 | breakup | 21 | 83 | 16 | PASS | - |
| 12 | persona_pain | 1 | 98 | 18 | PASS | - |
| 12 | comparable_proof | 5 | 87 | 54 | PASS | - |
| 12 | breakup | 21 | 77 | 16 | PASS | - |
| 13 | persona_pain | 1 | 112 | 50 | PASS | - |
| 13 | comparable_proof | 5 | 90 | 50 | PASS | - |
| 13 | breakup | 21 | 85 | 16 | PASS | - |
| 14 | persona_pain | 1 | 98 | 18 | PASS | - |
| 14 | comparable_proof | 5 | 87 | 54 | PASS | - |
| 14 | breakup | 21 | 77 | 16 | PASS | - |
| 15 | persona_pain | 1 | 98 | 18 | PASS | - |
| 15 | comparable_proof | 5 | 87 | 54 | PASS | - |
| 15 | breakup | 21 | 77 | 16 | PASS | - |
| 16 | persona_pain | 1 | 103 | 50 | PASS | - |
| 16 | comparable_proof | 5 | 87 | 50 | PASS | - |
| 16 | breakup | 21 | 82 | 16 | PASS | - |
| 17 | persona_pain | 1 | 98 | 18 | PASS | - |
| 17 | comparable_proof | 5 | 87 | 54 | PASS | - |
| 17 | breakup | 21 | 77 | 16 | PASS | - |

**Overall: ALL PASS**

## 4. Claims Gate Verdict

The CONTROL templates are deliberately written to avoid assertions about the prospect. The check looks for:
- Prior contact claims ("following up", "as I mentioned")
- Flat second-person operational assertions ("you are running X")

| # | step | day | verdict | issues |
|---|------|-----|---------|--------|
| 1 | persona_pain | 1 | PASS | - |
| 1 | comparable_proof | 5 | PASS | - |
| 1 | breakup | 21 | PASS | - |
| 2 | persona_pain | 1 | PASS | - |
| 2 | comparable_proof | 5 | PASS | - |
| 2 | breakup | 21 | PASS | - |
| 3 | persona_pain | 1 | PASS | - |
| 3 | comparable_proof | 5 | PASS | - |
| 3 | breakup | 21 | PASS | - |
| 4 | persona_pain | 1 | PASS | - |
| 4 | comparable_proof | 5 | PASS | - |
| 4 | breakup | 21 | PASS | - |
| 5 | persona_pain | 1 | PASS | - |
| 5 | comparable_proof | 5 | PASS | - |
| 5 | breakup | 21 | PASS | - |
| 6 | persona_pain | 1 | PASS | - |
| 6 | comparable_proof | 5 | PASS | - |
| 6 | breakup | 21 | PASS | - |
| 7 | persona_pain | 1 | PASS | - |
| 7 | comparable_proof | 5 | PASS | - |
| 7 | breakup | 21 | PASS | - |
| 8 | persona_pain | 1 | PASS | - |
| 8 | comparable_proof | 5 | PASS | - |
| 8 | breakup | 21 | PASS | - |
| 9 | persona_pain | 1 | PASS | - |
| 9 | comparable_proof | 5 | PASS | - |
| 9 | breakup | 21 | PASS | - |
| 10 | persona_pain | 1 | PASS | - |
| 10 | comparable_proof | 5 | PASS | - |
| 10 | breakup | 21 | PASS | - |
| 11 | persona_pain | 1 | PASS | - |
| 11 | comparable_proof | 5 | PASS | - |
| 11 | breakup | 21 | PASS | - |
| 12 | persona_pain | 1 | PASS | - |
| 12 | comparable_proof | 5 | PASS | - |
| 12 | breakup | 21 | PASS | - |
| 13 | persona_pain | 1 | PASS | - |
| 13 | comparable_proof | 5 | PASS | - |
| 13 | breakup | 21 | PASS | - |
| 14 | persona_pain | 1 | PASS | - |
| 14 | comparable_proof | 5 | PASS | - |
| 14 | breakup | 21 | PASS | - |
| 15 | persona_pain | 1 | PASS | - |
| 15 | comparable_proof | 5 | PASS | - |
| 15 | breakup | 21 | PASS | - |
| 16 | persona_pain | 1 | PASS | - |
| 16 | comparable_proof | 5 | PASS | - |
| 16 | breakup | 21 | PASS | - |
| 17 | persona_pain | 1 | PASS | - |
| 17 | comparable_proof | 5 | PASS | - |
| 17 | breakup | 21 | PASS | - |

**Overall: ALL PASS**

## 5. Fallback Count Per Contact

A fallback that reads well is still a fallback. Six variables per contact; the maximum fallback count is 6 (every variable fell back).

| # | domain_hash | fallbacks | detail |
|---|-------------|-----------|--------|
| 1 | da9fa0575ce8 | 1 | line -> generic intro |
| 2 | 4efeb3fe2afd | 1 | line -> generic intro |
| 3 | c768a0660316 | 1 | line -> generic intro |
| 4 | 68af8ce671c1 | 1 | line -> generic intro |
| 5 | 63084828d69e | 1 | line -> generic intro |
| 6 | 3afb5e0010d9 | 2 | angle_phrase -> fallback; line -> generic intro |
| 7 | 500976b76607 | 1 | line -> generic intro |
| 8 | ceb55a89127b | 1 | line -> generic intro |
| 9 | 1203bef7ae16 | 1 | line -> generic intro |
| 10 | c3f09366d72f | 2 | angle_phrase -> fallback; line -> generic intro |
| 11 | 395be3330be3 | 1 | line -> generic intro |
| 12 | f2f4b0d278ed | 2 | angle_phrase -> fallback; line -> generic intro |
| 13 | c3c9e6e49e77 | 1 | line -> generic intro |
| 14 | a3a16ee58d26 | 2 | angle_phrase -> fallback; line -> generic intro |
| 15 | 41da47c0397b | 2 | angle_phrase -> fallback; line -> generic intro |
| 16 | ddef577b8d3c | 1 | line -> generic intro |
| 17 | 947f2f9d81ff | 2 | angle_phrase -> fallback; line -> generic intro |

**Total fallbacks across 17 contacts: 23**

## 6. Signature

The CONTROL templates carry **no signature**. The sender identity is `Ivan, founder, Productive, works on project profitability for agencies` (from `config/clients/productive.yaml`). Whether to append a signature is an operator decision. The templates as they stand do not include one.

## 7. Staging Payload

The exact JSON payload Claude writes to EmailBison. `thread_reply` follows the F,T,F pattern. Subjects on step 2 are the same as step 1 (provider auto-prepends "Re:"). Step 3 opens a new thread with "closing the loop".

```json
[
  {
    "contact_hash": "b6882cfd6d48",
    "domain_hash": "da9fa0575ce8",
    "email_hash": "eb4715ab1b94",
    "company_hash": "d04727ad8c34",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:b6882cfd6d48>, I work with Marketing & Advertising teams on profitability visible on Monday not two weeks late, and I do not know how <company:d04727ad8c34> handles it\n\nThe pattern I see in teams the size of <company:d04727ad8c34> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:d04727ad8c34> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:b6882cfd6d48>, the teams I work with that look most like <company:d04727ad8c34> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:b6882cfd6d48>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:d04727ad8c34> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "32ab93ceddc6",
    "domain_hash": "4efeb3fe2afd",
    "email_hash": "d6e29c496d88",
    "company_hash": "e0021595d160",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:32ab93ceddc6>, I work with Marketing & Advertising teams on profitability visible on Monday not two weeks late, and I do not know how <company:e0021595d160> handles it\n\nThe pattern I see in teams the size of <company:e0021595d160> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:e0021595d160> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:32ab93ceddc6>, the teams I work with that look most like <company:e0021595d160> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:32ab93ceddc6>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:e0021595d160> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "dd4e53f0860a",
    "domain_hash": "c768a0660316",
    "email_hash": "529930f7e146",
    "company_hash": "c768a0660316",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:dd4e53f0860a>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:cb79987b5b25> handles it\n\nThe pattern I see in teams the size of <company:cb79987b5b25> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:cb79987b5b25> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:dd4e53f0860a>, the teams I work with that look most like <company:cb79987b5b25> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:dd4e53f0860a>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:cb79987b5b25> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "8cdfd2d06cae",
    "domain_hash": "68af8ce671c1",
    "email_hash": "34bc6d04c490",
    "company_hash": "0b074108431f",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "utilisation and capacity across live projects",
        "body": "<name:8cdfd2d06cae>, I work with Marketing & Advertising teams on utilisation and capacity across live projects, and I do not know how <company:0b074108431f> handles it\n\nThe pattern I see in teams the size of <company:0b074108431f> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:0b074108431f> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle utilisation and capacity",
        "body": "<name:8cdfd2d06cae>, the teams I work with that look most like <company:0b074108431f> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:8cdfd2d06cae>, if utilisation and capacity across live projects is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:0b074108431f> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "33afc169e069",
    "domain_hash": "63084828d69e",
    "email_hash": "1e8b00e31c98",
    "company_hash": "63084828d69e",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:33afc169e069>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:3c2ffdae042b> handles it\n\nThe pattern I see in teams the size of <company:3c2ffdae042b> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:3c2ffdae042b> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:33afc169e069>, the teams I work with that look most like <company:3c2ffdae042b> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:33afc169e069>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:3c2ffdae042b> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "04b2cd185949",
    "domain_hash": "3afb5e0010d9",
    "email_hash": "13caeb399698",
    "company_hash": "3afb5e0010d9",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:04b2cd185949>, I work with Advertising Services teams on margin per project, and I do not know how <company:28d156625850> handles it\n\nThe pattern I see in teams the size of <company:28d156625850> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:28d156625850> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:04b2cd185949>, the teams I work with that look most like <company:28d156625850> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:04b2cd185949>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:28d156625850> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "164c11029ec9",
    "domain_hash": "500976b76607",
    "email_hash": "0ffd563b26fa",
    "company_hash": "500976b76607",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:164c11029ec9>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:e3c4b280322a> handles it\n\nThe pattern I see in teams the size of <company:e3c4b280322a> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:e3c4b280322a> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:164c11029ec9>, the teams I work with that look most like <company:e3c4b280322a> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:164c11029ec9>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:e3c4b280322a> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "aaaba6610b02",
    "domain_hash": "ceb55a89127b",
    "email_hash": "185d72e07fc8",
    "company_hash": "ceb55a89127b",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:aaaba6610b02>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:2aa30d36d863> handles it\n\nThe pattern I see in teams the size of <company:2aa30d36d863> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:2aa30d36d863> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:aaaba6610b02>, the teams I work with that look most like <company:2aa30d36d863> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:aaaba6610b02>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:2aa30d36d863> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "2aa47f23fd95",
    "domain_hash": "1203bef7ae16",
    "email_hash": "3c5271f31289",
    "company_hash": "1203bef7ae16",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:2aa47f23fd95>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:3919702a36cb> handles it\n\nThe pattern I see in teams the size of <company:3919702a36cb> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:3919702a36cb> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:2aa47f23fd95>, the teams I work with that look most like <company:3919702a36cb> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:2aa47f23fd95>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:3919702a36cb> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "d2844b2886b3",
    "domain_hash": "c3f09366d72f",
    "email_hash": "74aacac30fce",
    "company_hash": "c3f09366d72f",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:d2844b2886b3>, I work with Advertising Services teams on margin per project, and I do not know how <company:09aa79e621e5> handles it\n\nThe pattern I see in teams the size of <company:09aa79e621e5> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:09aa79e621e5> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:d2844b2886b3>, the teams I work with that look most like <company:09aa79e621e5> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:d2844b2886b3>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:09aa79e621e5> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "c243e114f58c",
    "domain_hash": "395be3330be3",
    "email_hash": "985b119c2038",
    "company_hash": "395be3330be3",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:c243e114f58c>, I work with Marketing Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:b8fbedce7c47> handles it\n\nThe pattern I see in teams the size of <company:b8fbedce7c47> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:b8fbedce7c47> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:c243e114f58c>, the teams I work with that look most like <company:b8fbedce7c47> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:c243e114f58c>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:b8fbedce7c47> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "4c0edf0fb2c4",
    "domain_hash": "f2f4b0d278ed",
    "email_hash": "effdf39e626b",
    "company_hash": "f2f4b0d278ed",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:4c0edf0fb2c4>, I work with Advertising Services teams on margin per project, and I do not know how <company:5a422f505e8c> handles it\n\nThe pattern I see in teams the size of <company:5a422f505e8c> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:5a422f505e8c> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:4c0edf0fb2c4>, the teams I work with that look most like <company:5a422f505e8c> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:4c0edf0fb2c4>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:5a422f505e8c> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "177f9fa54bfb",
    "domain_hash": "c3c9e6e49e77",
    "email_hash": "13a755016ef4",
    "company_hash": "c3c9e6e49e77",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:177f9fa54bfb>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:8c67236c3b7d> handles it\n\nThe pattern I see in teams the size of <company:8c67236c3b7d> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:8c67236c3b7d> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:177f9fa54bfb>, the teams I work with that look most like <company:8c67236c3b7d> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:177f9fa54bfb>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:8c67236c3b7d> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "d4cebca2a680",
    "domain_hash": "a3a16ee58d26",
    "email_hash": "0241ca9824c4",
    "company_hash": "a3a16ee58d26",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:d4cebca2a680>, I work with Advertising Services teams on margin per project, and I do not know how <company:8c7260724ab3> handles it\n\nThe pattern I see in teams the size of <company:8c7260724ab3> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:8c7260724ab3> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:d4cebca2a680>, the teams I work with that look most like <company:8c7260724ab3> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:d4cebca2a680>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:8c7260724ab3> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "0955c3c3cc63",
    "domain_hash": "41da47c0397b",
    "email_hash": "ce7690b61dd8",
    "company_hash": "41da47c0397b",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:0955c3c3cc63>, I work with Advertising Services teams on margin per project, and I do not know how <company:c83c2cc6d6de> handles it\n\nThe pattern I see in teams the size of <company:c83c2cc6d6de> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:c83c2cc6d6de> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:0955c3c3cc63>, the teams I work with that look most like <company:c83c2cc6d6de> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:0955c3c3cc63>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:c83c2cc6d6de> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "3f3976404204",
    "domain_hash": "ddef577b8d3c",
    "email_hash": "5f883d184ce8",
    "company_hash": "ddef577b8d3c",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "profitability visible on Monday not two weeks late",
        "body": "<name:3f3976404204>, I work with Marketing Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:c88cd6d09613> handles it\n\nThe pattern I see in teams the size of <company:c88cd6d09613> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:c88cd6d09613> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle profitability on Monday",
        "body": "<name:3f3976404204>, the teams I work with that look most like <company:c88cd6d09613> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:3f3976404204>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:c88cd6d09613> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  },
  {
    "contact_hash": "27c77cac3505",
    "domain_hash": "947f2f9d81ff",
    "email_hash": "c123a704afd9",
    "company_hash": "947f2f9d81ff",
    "steps": [
      {
        "step": "persona_pain",
        "day": 1,
        "thread_reply": false,
        "subject": "margin per project",
        "body": "<name:27c77cac3505>, I work with Advertising Services teams on margin per project, and I do not know how <company:a6a205eb782d> handles it\n\nThe pattern I see in teams the size of <company:a6a205eb782d> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.\n\nIs that roughly how it works at <company:a6a205eb782d> today, or have you already put something in place for it?"
      },
      {
        "step": "comparable_proof",
        "day": 5,
        "thread_reply": true,
        "subject": "how teams your size handle project margin at month end",
        "body": "<name:27c77cac3505>, the teams I work with that look most like <company:a6a205eb782d> tend to arrive at the same place.\n\nThey stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.\n\nWould it be useful to see what that looked like for a team your size?"
      },
      {
        "step": "breakup",
        "day": 21,
        "thread_reply": false,
        "subject": "closing the loop",
        "body": "<name:27c77cac3505>, if margin per project is not something you are looking at right now, that is a fair answer in itself. I will leave it here.\n\nIf it becomes relevant later, the thing worth knowing is that most teams the size of <company:a6a205eb782d> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.\n\nAnything you would want me to send over, or shall I leave it there?"
      }
    ]
  }
]
```

## 8. Rendered Text Sample (Contact #1, PII hashed)

domain_hash: `da9fa0575ce8`, name_hash: `b6882cfd6d48`

### Step: persona_pain (day 1, thread_reply=False)

**Subject:** profitability visible on Monday not two weeks late

```
<name:b6882cfd6d48>, I work with Marketing & Advertising teams on profitability visible on Monday not two weeks late, and I do not know how <company:d04727ad8c34> handles it

The pattern I see in teams the size of <company:d04727ad8c34> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.

Is that roughly how it works at <company:d04727ad8c34> today, or have you already put something in place for it?
```

### Step: comparable_proof (day 5, thread_reply=True)

**Subject:** how teams your size handle profitability on Monday

```
<name:b6882cfd6d48>, the teams I work with that look most like <company:d04727ad8c34> tend to arrive at the same place.

They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.

Would it be useful to see what that looked like for a team your size?
```

### Step: breakup (day 21, thread_reply=False)

**Subject:** closing the loop

```
<name:b6882cfd6d48>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.

If it becomes relevant later, the thing worth knowing is that most teams the size of <company:d04727ad8c34> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.

Anything you would want me to send over, or shall I leave it there?
```
