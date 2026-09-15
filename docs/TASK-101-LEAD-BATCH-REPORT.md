# TASK-101 Lead Batch Report

**Snapshot:** `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`
**Cohort:** Persona = economic_buyer (largest honest cohort from TASK-096)
**Date:** 2026-09-15

---

## Funnel Summary

| Stage | Input | Survived | Dropped | Drop Rate |
|-------|------:|---------:|--------:|----------:|
| Cohort selected | 70 | 70 | 0 | 0.0% |
| dedupe | 70 | 70 | 0 | 0.0% |
| exclusion | 70 | 51 | 19 | 27.1% |
| personalisation | 51 | 51 | 0 | 0.0% |
| greeting_proof | 51 | 51 | 0 | 0.0% |
| quality_gates | 51 | 46 | 5 | 9.8% |

**Final batch size: 46 leads**

## Drops at Stage: exclusion

| Reason | Count |
|--------|------:|
| not_sendable | 19 |
| email_held | 1 |

### Individual Drops

- **e46dd5323aa3** (6470a1ce45790bb9): not_sendable: contact.sendable is False
- **c1c4b4de39d3** (983eaf822ae5c213): not_sendable: contact.sendable is False
- **d2d11b5b2a87** (58504dc133aa21c5): not_sendable: contact.sendable is False
- **7fa82eea81a9** (8101ba0056500d5c): not_sendable: contact.sendable is False
- **d5541a7c0d51** (bebde11480899cb3): not_sendable: contact.sendable is False
- **9536bb3a8cd7** (0f49d47e06969e2e): not_sendable: contact.sendable is False
- **8c92231b7a8a** (aed9d63cc7837049): not_sendable: contact.sendable is False
- **baf35e64c0dd** (be507979eb16621e): not_sendable: contact.sendable is False
- **f1f2d9d151cc** (692d2a788fd4223b): not_sendable: contact.sendable is False
- **7ef6212caf77** (1a41146af582c624): not_sendable: contact.sendable is False
- **7e55d09386a9** (97e37d536482d08b): not_sendable: contact.sendable is False
- **49ce56e95739** (e1b61d97f490b34c): email_held: verification state is held (verifiers disagree: ['contactout'] say valid, ['reoon'] do not); not_sendable: contact.sendable is False
- **a416462fb1d2** (a5d42d6af212d2d9): not_sendable: contact.sendable is False
- **5c2a3cfd7eec** (0781ef26f3256a5b): not_sendable: contact.sendable is False
- **6782ab63df5d** (62f914b4c3641059): not_sendable: contact.sendable is False
- **a2e8942303e3** (69fde51bd9d9c137): not_sendable: contact.sendable is False
- **9bffb9cef5a1** (cef7910a6492fdb5): not_sendable: contact.sendable is False
- **49447c5db61f** (5a1528395ebae51c): not_sendable: contact.sendable is False
- **cc590e15b3fc** (01f5862b250e4a67): not_sendable: contact.sendable is False

## Drops at Stage: quality_gates

| Reason | Count |
|--------|------:|
| no_cadence | 3 |
| no_email_steps | 2 |

### Individual Drops

- **13f19e079ea0** (df0bdf7c94c554db): no_email_steps: cadence has no email steps
- **4b0bc54de0a0** (19f1d9a27fb6b6c2): no_cadence: no generated copy for this contact
- **fe1f35998ca8** (b662dd455783d688): no_cadence: no generated copy for this contact
- **01180bdb9de5** (8ad98c6b399e59b6): no_email_steps: cadence has no email steps
- **84f5e945edbd** (c17452ef749af8e5): no_cadence: no generated copy for this contact

## Batch File

The batch file is at `work/task101_batch.json` (gitignored).
It contains 46 leads with resolved fields and greeting proofs.

## What the Operator Would Be Authorising

If the operator enabled `heyreach.add_leads` in `providerwrites.SUPPORTED`, they would be authorising:

1. **46 new leads** added to HeyReach campaign 599020
2. Each lead carries a LinkedIn profile URL, first name, last name, company, title, and custom fields (record_id, contact_key, client)
3. The campaign's sequence would begin acting on each lead immediately (LinkedIn connection requests and messages)
4. The sequence is already configured on 599020 with 8 per-variable fallbacks, so a missing merge variable resolves to the fallback rather than to 'undefined' or 'null'

**This task does NOT perform that write.** It produces the batch and the evidence that it is safe to write, so the operator's decision is a yes/no on a real artefact rather than on a promise.

## Observations

- Started with 70 contacts in the economic_buyer cohort (contacts with email on not-dropped records)
- 24 contacts dropped across all stages (34.3% drop-off)
- 46 contacts survive all gates and form the batch

### Drop-off Between Stages

- **dedupe:** 0 dropped (0.0% of 70 entering)
- **exclusion:** 19 dropped (27.1% of 70 entering)
- **personalisation:** 0 dropped (0.0% of 51 entering)
- **greeting_proof:** 0 dropped (0.0% of 51 entering)
- **quality_gates:** 5 dropped (9.8% of 51 entering)

**The drop-off between stages is the most useful number.** If many leads drop at exclusion, the cohort is smaller than the raw count suggests. If many drop at quality, the copy needs work before the batch is safe to write.

## PII Statement

All identifiers in this report are hashed (SHA-256 prefix). The batch file at `work/task101_batch.json` may hold real data as an operational artefact under `work/`, which is gitignored. This report is tracked and holds no real PII.
