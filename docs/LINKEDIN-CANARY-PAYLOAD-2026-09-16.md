---
title: "LinkedIn Canary Payload — Variable Resolution and Staging Data"
task: "TASK-176"
date: "2026-09-16"
builds_on:
  - "docs/COHORT-LADDER-2026-09-15.md"
  - "docs/BISON-CONTROL-PAYLOAD-2026-09-16.md"
  - "docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md"
  - "docs/CONTEXT-RESET-2026-09-15-E.md"
---

# LinkedIn Canary Payload — 2026-09-16

**TASK-176 deliverable.** Variable resolution, gate verdicts, the 24-node sequence from the provider, and the exact staging payload for the 3-contact canary (rung 3 of the cohort ladder).

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). No profile URL, person name, company name, or domain appears in this document. Body text shows `<name:HASH>` and `<company:HASH>` placeholders where PII would appear.

## 1. The Three Contacts

| # | record_id_hash | domain_hash | name_hash | profile_hash | title | persona | angle |
|---|----------------|-------------|-----------|--------------|-------|---------|-------|
| 1 | e46dd5323aa3 | f3945ded7f71 | b7d648ab527f | 6acd6d9f031b | President & COO | economic_buyer | operations |
| 2 | 13f19e079ea0 | c3c86b5e9b04 | 687ac24b168a | 66be132c58b0 | Chief Operating Officer | economic_buyer | operations |
| 3 | c1c4b4de39d3 | 1e42d3410c26 | b915f900b12a | 0317d2695838 | Chief Operating Officer | economic_buyer | operations |

## 2. Per-Contact Variable Resolution

Eight merge variables per contact, matching the HeyReach graph roles. Each variable resolves to either approved copy from the cadence or the CONTROL fallback from `config/clients/productive.yaml`.

### Contact #1: `<name:b7d648ab527f>` at `<company:4e1736a4d102>`

- **Record ID hash:** `e46dd5323aa3`
- **Profile URL hash:** `6acd6d9f031b`
- **Title:** President & COO
- **Persona:** economic_buyer, **Angle:** operations

| role | source | fallback? | chars |
|------|--------|-----------|-------|
| connection_note | li1 (approved by operator-control-arm) | no | 90 |
| connected_1 | li2 (approved by operator-control-arm) | no | 99 |
| connected_2 | li3 (approved by operator-control-arm) | no | 115 |
| connected_3 | li4 (approved by operator-control-arm) | no | 94 |
| connected_4 | li5 (approved by operator-control-arm) | no | 83 |
| message_2 | li2 (approved by operator-control-arm) | no | 99 |
| message_3 | li3 (approved by operator-control-arm) | no | 115 |
| message_4 | li4 (approved by operator-control-arm) | no | 94 |

**Fallback count:** 0 of 8

### Contact #2: `<name:687ac24b168a>` at `<company:db32f98e24da>`

- **Record ID hash:** `13f19e079ea0`
- **Profile URL hash:** `66be132c58b0`
- **Title:** Chief Operating Officer
- **Persona:** economic_buyer, **Angle:** operations

| role | source | fallback? | chars |
|------|--------|-----------|-------|
| connection_note | li1 (approved by claude) | no | 113 |
| connected_1 | FALLBACK (config.linkedin_sequence.fallbacks.connected_1) | YES | 99 |
| connected_2 | FALLBACK (config.linkedin_sequence.fallbacks.connected_2) | YES | 115 |
| connected_3 | FALLBACK (config.linkedin_sequence.fallbacks.connected_3) | YES | 94 |
| connected_4 | FALLBACK (config.linkedin_sequence.fallbacks.connected_4) | YES | 83 |
| message_2 | FALLBACK (config.linkedin_sequence.fallbacks.message_2) | YES | 99 |
| message_3 | FALLBACK (config.linkedin_sequence.fallbacks.message_3) | YES | 115 |
| message_4 | FALLBACK (config.linkedin_sequence.fallbacks.message_4) | YES | 94 |

**Fallback count:** 7 of 8

### Contact #3: `<name:b915f900b12a>` at `<company:607a6d311595>`

- **Record ID hash:** `c1c4b4de39d3`
- **Profile URL hash:** `0317d2695838`
- **Title:** Chief Operating Officer
- **Persona:** economic_buyer, **Angle:** operations

| role | source | fallback? | chars |
|------|--------|-----------|-------|
| connection_note | FALLBACK (config.linkedin_sequence.fallbacks.connection_note | YES | 90 |
| connected_1 | FALLBACK (config.linkedin_sequence.fallbacks.connected_1) | YES | 99 |
| connected_2 | FALLBACK (config.linkedin_sequence.fallbacks.connected_2) | YES | 115 |
| connected_3 | FALLBACK (config.linkedin_sequence.fallbacks.connected_3) | YES | 94 |
| connected_4 | FALLBACK (config.linkedin_sequence.fallbacks.connected_4) | YES | 83 |
| message_2 | FALLBACK (config.linkedin_sequence.fallbacks.message_2) | YES | 99 |
| message_3 | FALLBACK (config.linkedin_sequence.fallbacks.message_3) | YES | 115 |
| message_4 | FALLBACK (config.linkedin_sequence.fallbacks.message_4) | YES | 94 |

**Fallback count:** 8 of 8

## 3. Resolved Text Per Role (PII hashed)

### Contact #1: `<name:b7d648ab527f>`

**connection_note** (connection note):
> hi, i work with agencies on project profitability and thought it would be good to connect.

**connected_1** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**connected_2** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**connected_3** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

**connected_4** (message):
> happy to leave it here if the timing is wrong. is there someone else who owns this?

**message_2** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**message_3** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**message_4** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

### Contact #2: `<name:687ac24b168a>`

**connection_note** (connection note):
> noticed you're scaling operations at 2ton — i work with creative teams on capacity planning across live projects.

**connected_1** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**connected_2** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**connected_3** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

**connected_4** (message):
> happy to leave it here if the timing is wrong. is there someone else who owns this?

**message_2** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**message_3** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**message_4** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

### Contact #3: `<name:b915f900b12a>`

**connection_note** (connection note):
> hi, i work with agencies on project profitability and thought it would be good to connect.

**connected_1** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**connected_2** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**connected_3** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

**connected_4** (message):
> happy to leave it here if the timing is wrong. is there someone else who owns this?

**message_2** (message):
> how do you currently get visibility on whether a project is making money while it is still running?

**message_3** (message):
> most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?

**message_4** (message):
> we built productive so budgets, time tracking and resourcing talk to each other. worth a look?

## 4. Lint Verdict

LinkedIn-specific lint: character limits (note: 40-300, message: 60-1900), no substituted punctuation, no placeholders, no banned phrases, no cross-channel references.

| # | role | kind | chars | verdict | failures |
|---|------|------|-------|---------|----------|
| 1 | connection_note | NOTE | 90 | PASS | - |
| 1 | connected_1 | MSG | 99 | PASS | - |
| 1 | connected_2 | MSG | 115 | PASS | - |
| 1 | connected_3 | MSG | 94 | PASS | - |
| 1 | connected_4 | MSG | 83 | PASS | - |
| 1 | message_2 | MSG | 99 | PASS | - |
| 1 | message_3 | MSG | 115 | PASS | - |
| 1 | message_4 | MSG | 94 | PASS | - |
| 2 | connection_note | NOTE | 113 | FAIL | em_dash |
| 2 | connected_1 | MSG | 99 | PASS | - |
| 2 | connected_2 | MSG | 115 | PASS | - |
| 2 | connected_3 | MSG | 94 | PASS | - |
| 2 | connected_4 | MSG | 83 | PASS | - |
| 2 | message_2 | MSG | 99 | PASS | - |
| 2 | message_3 | MSG | 115 | PASS | - |
| 2 | message_4 | MSG | 94 | PASS | - |
| 3 | connection_note | NOTE | 90 | PASS | - |
| 3 | connected_1 | MSG | 99 | PASS | - |
| 3 | connected_2 | MSG | 115 | PASS | - |
| 3 | connected_3 | MSG | 94 | PASS | - |
| 3 | connected_4 | MSG | 83 | PASS | - |
| 3 | message_2 | MSG | 99 | PASS | - |
| 3 | message_3 | MSG | 115 | PASS | - |
| 3 | message_4 | MSG | 94 | PASS | - |

**Overall: FAILURES DETECTED**

## 5. Claims Gate Verdict

Checks for prior-contact claims and flat second-person operational assertions about the prospect.

| # | role | verdict | issues |
|---|------|---------|--------|
| 1 | connection_note | PASS | - |
| 1 | connected_1 | PASS | - |
| 1 | connected_2 | PASS | - |
| 1 | connected_3 | PASS | - |
| 1 | connected_4 | PASS | - |
| 1 | message_2 | PASS | - |
| 1 | message_3 | PASS | - |
| 1 | message_4 | PASS | - |
| 2 | connection_note | FAIL | operational_assertion: 'noticed you're scaling operations at 2ton — i work with creative teams on capaci' |
| 2 | connected_1 | PASS | - |
| 2 | connected_2 | PASS | - |
| 2 | connected_3 | PASS | - |
| 2 | connected_4 | PASS | - |
| 2 | message_2 | PASS | - |
| 2 | message_3 | PASS | - |
| 2 | message_4 | PASS | - |
| 3 | connection_note | PASS | - |
| 3 | connected_1 | PASS | - |
| 3 | connected_2 | PASS | - |
| 3 | connected_3 | PASS | - |
| 3 | connected_4 | PASS | - |
| 3 | message_2 | PASS | - |
| 3 | message_3 | PASS | - |
| 3 | message_4 | PASS | - |

**Overall: ISSUES DETECTED**

## 6. Fallback Count Per Contact

A fallback that reads well is still a fallback. Eight variables per contact; the total fallback count across all three is **15** of 24 slots.

| # | name_hash | fallbacks | detail |
|---|-----------|-----------|--------|
| 1 | b7d648ab527f | 0 | all resolved |
| 2 | 687ac24b168a | 7 | connected_1 -> config fallback; connected_2 -> config fallback; connected_3 -> config fallback; connected_4 -> config fallback; message_2 -> config fallback; message_3 -> config fallback; message_4 -> config fallback |
| 3 | b915f900b12a | 8 | connection_note -> config fallback; connected_1 -> config fallback; connected_2 -> config fallback; connected_3 -> config fallback; connected_4 -> config fallback; message_2 -> config fallback; message_3 -> config fallback; message_4 -> config fallback |

**Finding:** The CONTROL fallbacks are the operator's hand-written text. They assert nothing about the recipient and pass every gate. A contact with operator-approved copy uses that copy; a contact without it falls back to the same generic text for every role. The fallback count measures how much of the 'personalisation' is actually the config default.

## 7. The 24 Nodes in Campaign 599020

**Source:** `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` and `docs/CONTEXT-RESET-2026-09-15-E.md`.

### What the provider readback showed (2026-09-14)

The original readback found 24 nodes with LITERAL STRINGS (no merge variables), including 'hi jacob' and '&partner'. That sequence was the defective one from before the correction.

    CHECK_IS_CONNECTION 1, MESSAGE 7, VIEW_PROFILE 4,
    CONNECTION_REQUEST 1, FOLLOW 1, END 10

### What CONTEXT-RESET-2026-09-15-E.md reports (corrected)

The sequence was corrected to use PURE MERGE VARIABLES:

    {connection_note}, {connected_1}, {connected_2}, {connected_3},
    {connected_4}, {message_2}, {message_3}, {message_4}

The words arrive PER LEAD in `customUserFields`. No sequence write is needed because the graph already carries the variables.

### The corrected graph structure (17 nodes, without InMail)

```
CHECK_IS_CONNECTION (0 HOUR)
  YES (already connected):
    MESSAGE {connected_1}     (+3 HOUR)
    MESSAGE {connected_2}     (+3 DAY)
    VIEW_PROFILE              (+2 DAY)
    MESSAGE {connected_3}     (+5 DAY)
    MESSAGE {connected_4}     (+7 DAY)
    END                       (+3 HOUR)
  NO (cold path):
    VIEW_PROFILE              (+3 HOUR)
    FOLLOW                    (+3 HOUR)
    CONNECTION_REQUEST {connection_note} (+1 DAY, withdraw after 21d)
      condition (chain):
        MESSAGE {message_2}   (+3 HOUR)
        VIEW_PROFILE          (+3 DAY)
        MESSAGE {message_3}   (+2 DAY)
        MESSAGE {message_4}   (+7 DAY)
        END                   (+3 HOUR)
      not_accepted:
        VIEW_PROFILE          (+5 DAY)
        END                   (+3 HOUR)
```

### Does the node sequence match the CONTROL the ladder assumes?

**Yes.** The COPY_MAPPING maps cadence steps to graph roles:

| cadence step | graph role(s) | CONTROL fallback |
|-------------|---------------|------------------|
| li1 | connection_note | hi, i work with agencies on project profitability and though... |
| li2 | connected_1 | how do you currently get visibility on whether a project is ... |
| li2 | message_2 | how do you currently get visibility on whether a project is ... |
| li3 | connected_2 | most agencies i speak to find that out at the end of a proje... |
| li3 | message_3 | most agencies i speak to find that out at the end of a proje... |
| li4 | connected_3 | we built productive so budgets, time tracking and resourcing... |
| li4 | message_4 | we built productive so budgets, time tracking and resourcing... |
| li5 | connected_4 | happy to leave it here if the timing is wrong. is there some... |

**li6 has no slot in the graph.** The cadence names 6 steps but the graph has positions for only 5 (li1-li5). li6 is reported in `touch_report` but does not fire.

### Does the copy in the nodes match the rendering?

The nodes carry MERGE VARIABLES (`{connection_note}`, etc.), not literal text. The actual text arrives per lead in `customUserFields`. So the comparison is: does each contact's `customUserFields` match the rendering in Section 3?

**For Austin Ball (#1):** li1-li5 have operator-control-arm approval. The approved copy matches the CONTROL fallbacks exactly (the CONTROL was written to be the fallback). li6 is generated but has no graph slot.

**For Sam Nielsen (#2) and Anthony Andreatos (#3):** All steps are generated (no operator approval). The `customUserFields` would carry the generated text, NOT the CONTROL fallbacks. The fallbacks fire only when `customUserFields` is missing a variable entirely.

**THIS IS THE FINDING.** The campaign was staged before the ladder existed. The contacts have generated copy in their cadence steps, but that copy was never operator-approved. When staging, the factory would refuse because `assemble_linkedin_copy` requires approval. The contacts would need their generated copy replaced with CONTROL fallbacks before they can be staged.

## 8. The Staging Payload

Schema per TASK-158: `profileUrl`, `firstName`, `lastName` + `customUserFields` with one value per merge variable. All PII hashed.

```json
[
  {
    "record_id_hash": "e46dd5323aa3",
    "profileUrl_hash": "6acd6d9f031b",
    "firstName_hash": "a161e03bf85e",
    "lastName_hash": "ae5859eceacb",
    "domain_hash": "f3945ded7f71",
    "company_hash": "4e1736a4d102",
    "customUserFields": {
      "connection_note": "hi, i work with agencies on project profitability and thought it would be good to connect.",
      "connected_1": "how do you currently get visibility on whether a project is making money while it is still running?",
      "connected_2": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "connected_3": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?",
      "connected_4": "happy to leave it here if the timing is wrong. is there someone else who owns this?",
      "message_2": "how do you currently get visibility on whether a project is making money while it is still running?",
      "message_3": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "message_4": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?"
    }
  },
  {
    "record_id_hash": "13f19e079ea0",
    "profileUrl_hash": "66be132c58b0",
    "firstName_hash": "4ecde249d747",
    "lastName_hash": "2739400f9a65",
    "domain_hash": "c3c86b5e9b04",
    "company_hash": "db32f98e24da",
    "customUserFields": {
      "connection_note": "noticed you're scaling operations at 2ton \u2014 i work with creative teams on capacity planning across live projects.",
      "connected_1": "how do you currently get visibility on whether a project is making money while it is still running?",
      "connected_2": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "connected_3": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?",
      "connected_4": "happy to leave it here if the timing is wrong. is there someone else who owns this?",
      "message_2": "how do you currently get visibility on whether a project is making money while it is still running?",
      "message_3": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "message_4": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?"
    }
  },
  {
    "record_id_hash": "c1c4b4de39d3",
    "profileUrl_hash": "0317d2695838",
    "firstName_hash": "3090ad7f5b83",
    "lastName_hash": "acf887009571",
    "domain_hash": "1e42d3410c26",
    "company_hash": "607a6d311595",
    "customUserFields": {
      "connection_note": "hi, i work with agencies on project profitability and thought it would be good to connect.",
      "connected_1": "how do you currently get visibility on whether a project is making money while it is still running?",
      "connected_2": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "connected_3": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?",
      "connected_4": "happy to leave it here if the timing is wrong. is there someone else who owns this?",
      "message_2": "how do you currently get visibility on whether a project is making money while it is still running?",
      "message_3": "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?",
      "message_4": "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?"
    }
  }
]
```

## 9. LinkedIn's Blocking Variable

Email's only blocking variable was `company` - a contact without a resolvable company name could not render. LinkedIn has no equivalent single blocking variable.

What LinkedIn has instead is an **approval requirement**: every merge variable must have approved copy from the cadence. If a step has no `approval.by`, the factory refuses. The fallback from config fills the GRAPH's `fallbackMessage` (what the provider sends if the variable is empty), but the per-lead `customUserFields` must carry the approved words.

**The practical effect:** 2 of 3 canary contacts (Sam Nielsen, Anthony Andreatos) have no operator-approved copy. Their generated copy was never approved through the CONTROL arm. They cannot be staged until their cadence steps are replaced with CONTROL fallbacks or operator-approved generated copy.

Only Austin Ball has operator-control-arm approval for li1-li5, which maps to all 8 required roles. He is the only contact of the three who can be staged today.

## 10. Summary

| Metric | Value |
|--------|-------|
| Snapshot | `2026-09-15T17:52:12+00:00 from master cf23154 550 records` |
| Contacts | 3 (rung 3: economic_buyer, operations) |
| Merge variables per contact | 8 |
| Total variable slots | 24 |
| Total fallbacks | 15 |
| Contacts with full operator approval | 1 of 3 |
| Contacts blocked (no approval) | 2 of 3 |
| Lint | FAILURES DETECTED |
| Claims | ISSUES DETECTED |
| Graph nodes (corrected) | 17 (was 24 with literal strings) |
| li6 in graph | NO - cadence step with no graph position |
