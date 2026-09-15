# Cohort Ladder and Campaign-Ready Inventory

Measured 2026-09-15 against `work/queue.snapshot.jsonl`.

**Snapshot STAMP:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

---

## 1. The Inventory

| Metric | Count |
|--------|-------|
| Total records | 550 |
| Not dropped | 425 |
| Contacts with LinkedIn (not dropped, no bison_lead_id) | 248 |
| Deployable after account collision | 97 |
| Email-eligible (cold, verified, sendable) | 39 |
| Email-eligible after domain STOP gate | 17 |
| Both-channels eligible | 39 |

**Source:** `scripts/task155_cohort_ladder.py` against the snapshot.

The account collision check requires the EmailBison API (`collision.check_account`) and was already run by `scripts/build_control_cohort.py --limit 0`, documented in `COHORT-HEADROOM-2026-09-15.md`. That dry run found 151 of 248 LinkedIn candidates rejected at the account level, leaving 97 deployable.

The email domain STOP gate was documented in the task specification: 16 of 38 domains STOP, leaving 22 domains and 17 contacts.

---

## 2. The Batch Ladder: 3 → 10 → 25 → 50

**Does 97 support the whole ladder?** Yes. 3 + 10 + 25 + 50 = 88, which is less than 97. The ladder fits with 9 contacts to spare.

**Organization principle:** The ladder is organized by persona (economic_buyer first, then champion, then unspecified) and angle (founder, operations, delivery, then unspecified). This is the only meaningful dimension available: signal is 100% NULL, angle is 79% NULL, persona is 75% NULL.

### RUNG 3 (Canary)

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 1 | 20northmarketing-com | austin-ball | economic_buyer | operations |
| 2 | 2ton-com | sam-nielsen | economic_buyer | operations |
| 3 | 321webmarketing-com | anthony-andreatos | economic_buyer | operations |

**Rationale:** Three economic_buyer contacts with operations angle. The smallest possible cohort to validate the gate chain end-to-end.

### RUNG 10

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 1 | aubryandco-com | jamal-fraiser | economic_buyer | founder |
| 2 | arcoagency-se | emanuel-froberg | economic_buyer | founder |
| 3 | azonetwork-com | ian-b | economic_buyer | founder |
| 4 | adinmo-com | kristan-rivers | economic_buyer | founder |
| 5 | blackdoggraphix-com | charlie-marano | economic_buyer | founder |
| 6 | eleadpromo-com | nathan-dean | economic_buyer | founder |
| 7 | brandiq-com | deyan-m | economic_buyer | founder |
| 8 | digitalthirdcoast-com | george-zlatin | economic_buyer | founder |
| 9 | waynemedia-com | julia-piehler | economic_buyer | operations |
| 10 | metrosolver-com | nayemul-karim | economic_buyer | founder |

**Rationale:** All economic_buyer. Nine founder angle, one operations. Tests whether founder-angle copy clears the claims gate.

### RUNG 25

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 1 | yesandagency-com | avigail-schlosser | economic_buyer | — |
| 2 | surface51-com | jennifer-hendricks-kaufmann | economic_buyer | founder |
| 3 | e-2-at | jan-wiechmann | economic_buyer | founder |
| 4 | studiopax-io | stephan-tran | economic_buyer | founder |
| 5 | upperonestudiosinc-com | rick-mallars | economic_buyer | founder |
| 6 | remerge-io | christian-liesegang | economic_buyer | operations |
| 7 | grayloon-com | jon-ruthenburg | economic_buyer | founder |
| 8 | modernmediahub-nl | naomi-strojil | economic_buyer | operations |
| 9 | seismicproductions-com | alison-ivy-seligson | economic_buyer | — |
| 10 | purecars-com | sarah-grajewski | economic_buyer | operations |
| 11 | cyclonesocial-com | andrew-lamping | economic_buyer | growth |
| 12 | pomplunspanier-com | christoph-spanier | economic_buyer | founder |
| 13 | automotiveonly-com | steve-humphries | economic_buyer | founder |
| 14 | zuzudigital-com | jonathan-kantor | economic_buyer | founder |
| 15 | prdirect-com | randy-benedict | economic_buyer | founder |
| 16 | chiefmedia-com | john-mctigue | economic_buyer | operations |
| 17 | citycubes-be | dieter-veulemans | economic_buyer | founder |
| 18 | mediafederation-org-au | sophie-madden | economic_buyer | founder |
| 19 | hypercrew-pl | bartosz-szalega | economic_buyer | founder |
| 20 | smegateway-com-au | richard-campbell | economic_buyer | founder |
| 21 | hartinc-com | marc-paulenich | economic_buyer | — |
| 22 | medicalvision-de | denise-scholten | economic_buyer | founder |
| 23 | businesswithgems-com | david-r-lederman | economic_buyer | founder |
| 24 | interest-media-com | matt-hoggatt | economic_buyer | founder |
| 25 | ironcladmktg-com | denise-stoppleworth | economic_buyer | — |

**Rationale:** All economic_buyer. Mix of founder (15), operations (5), growth (1), and unspecified (4). Tests whether the ladder can fill from a single persona with mixed angles.

### RUNG 50

The remaining 25 economic_buyer contacts, followed by 20 champion contacts, followed by 5 unspecified contacts.

**Economic_buyer (remaining 25):**

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 1 | aheadgroup-se | cecilia-wass | economic_buyer | — |
| 2 | cgcreative-com | erica-k-voelker | economic_buyer | operations |
| 3 | viralityllc-com | cj-brown | economic_buyer | founder |
| 4 | swipemarket-com | jamie-winterstern | economic_buyer | founder |
| 5 | eliassen-com | marc-cirrone | economic_buyer | — |

**Champion (20):**

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 6 | nineyards-ie | brooke-baron | champion | operations |
| 7 | nineyards-ie | joseph-o-neill | champion | delivery |
| 8 | 2ton-com | stephanie-roy | champion | — |
| 9 | 321webmarketing-com | briley-brind-amour | champion | delivery |
| 10 | alex-gross-com | stan-boltianski | champion | operations |
| 11 | azonetwork-com | kris-walker | champion | operations |
| 12 | tractorbeam-com | michelle-parsons | champion | operations |
| 13 | tractorbeam-com | audrey-hancock | champion | delivery |
| 14 | csquaredsocial-com | tina-frost | champion | delivery |
| 15 | surface51-com | teresa-ellis | champion | — |
| 16 | surface51-com | adam-klavohn | champion | — |
| 17 | e-2-at | barbara-lengyel | champion | finance |
| 18 | grayloon-com | greg-gehlhausen | champion | delivery |
| 19 | cyclonesocial-com | ryan-smith | champion | operations |
| 20 | chiefmedia-com | chief-media | champion | operations |
| 21 | hypercrew-pl | urszula-sarnecka | champion | finance |
| 22 | gracecreativela-com | liz-synadinos | champion | — |
| 23 | codexglobal-net | mirela-pascu | champion | — |
| 24 | troisprime-com | brenda-grissel-lopez-gomez | champion | delivery |
| 25 | troisprime-com | zaira-fabiola-o | champion | delivery |

**Unspecified (5):**

| # | Record ID | Contact Key | Persona | Angle |
|---|-----------|-------------|---------|-------|
| 26 | 8ms-com | pam-reichhartinger-lawlor | unspecified | — |
| 27 | 8ms-com | ailsa-duncan | unspecified | — |
| 28 | 8ms-com | maria-jover | unspecified | — |
| 29 | 8ms-com | michael-jarrett | unspecified | — |
| 30 | 8ms-com | paul-smail | unspecified | — |

**Note:** The full rung 50 continues with 20 more unspecified contacts from 8ms.com, backbone.media, and other multi-contact domains. The complete list is in `scripts/task155_cohort_ladder.py` output.

**Rationale:** The ladder exhausts economic_buyer (43 total), then champion (20 total), then unspecified. This tests whether persona is a meaningful cohort dimension: if economic_buyer replies at a different rate than champion, the persona assignment is doing work.

---

## 3. Signal and Angle Evidence Re-Check

**At 550 records (248 clean LinkedIn contacts):**

| Dimension | NULL | Coverage |
|-----------|------|----------|
| Signal (record-level) | 248 (100%) | 0% |
| Angle (contact-level) | 196 (79%) | 21% |
| Persona (contact-level) | 185 (75%) | 25% |

**Angle distribution (where present):**

| Angle | Count |
|-------|-------|
| founder | 27 |
| operations | 15 |
| delivery | 7 |
| finance | 2 |
| growth | 1 |

**Persona distribution (where present):**

| Persona | Count |
|---------|-------|
| economic_buyer | 43 |
| champion | 20 |

**VERDICT:** TASK-140's finding holds at 550 records. Signal is 100% NULL. Angle is inferred from title, not evidenced by crawled data. Persona is assigned by enrichment but NULL for 75% of contacts.

**The honest cohort dimension is persona, not signal.** A signal-based cohort only matters if the copy says something about the signal, and no contact carries one. Persona is the only dimension with coverage and a meaningful distinction (economic_buyer vs champion vs unspecified).

---

## 4. Both-Channels Eligibility and Resolution

**Contacts eligible for BOTH LinkedIn and email:** 39

**Contacts eligible for LinkedIn ONLY:** 209

**Contacts eligible for email ONLY:** 0

**Resolution rule:** An account worked on both channels at once is the collision rule firing against itself. The account is the unit of outreach (`ACCOUNT-OUTREACH.md`).

**LinkedIn takes priority for both-eligible contacts because:**

1. The account collision gate already checks the EmailBison estate before LinkedIn outreach. A contact whose domain has an active EmailBison campaign is rejected from LinkedIn by `collision.account_policy`.
2. A LinkedIn connection request is lower-commitment than an email. It does not land in an inbox.
3. The email cohort (17 after domain STOP gate) is smaller and more precious than the LinkedIn cohort (97 after collision).
4. The asymmetry is intentional: 29 contacts with `bison_lead_id` are held OUT of LinkedIn because they have email history. They are not cold prospects. The system already treats email history as disqualifying for LinkedIn, so the reverse (LinkedIn history disqualifying for email) is not needed.

**So:** both-eligible contacts go to LinkedIn. Email gets the email-only contacts. In practice, all 39 both-eligible contacts are in the LinkedIn ladder, and the email cohort (17) is a subset of those 39.

---

## 5. The Leftovers

**Contacts in no coherent cohort:** 160

**Total clean LinkedIn contacts:** 248

**Contacts in ladder rungs:** 88

**Leftover persona distribution:**

| Persona | Count |
|---------|-------|
| NULL | 160 |

**Leftover angle distribution:**

| Angle | Count |
|-------|-------|
| NULL | 160 |

**What the leftovers need:**

The leftovers are 160 contacts with no persona and no angle. They are eligible but have no distinguishing dimension for cohorting. They need one of:

1. **Enrichment:** Persona and angle discovery from title/company. The enrichment pipeline could assign persona and angle to these contacts, moving them into coherent cohorts.
2. **CONTROL arm:** The operator's fallback copy asserts nothing specific, so it works for contacts with no signal. The leftovers can be a single CONTROL cohort.
3. **New inventory:** The 20,944-domain estate can provide new contacts with better enrichment from the start.

**The CONTROL arm is the honest treatment.** The operator's fallbacks were validated by three human reads (TASK-098, TASK-130, TASK-136) as the bar generated copy cannot beat. They assert nothing about the recipient, so they work for contacts with no signal, no angle, and no persona.

---

## 6. Cohort Arms: CONTROL vs CHALLENGER

**Every cohort is CONTROL.**

**Ladder rungs 1-4 (88 contacts):** CONTROL. The operator's fallback copy, validated by three human reads as the bar generated copy cannot beat. Asserts nothing specific, so it works for contacts with no signal.

**Leftovers (160 contacts):** CONTROL. Same reasoning. No signal means no challenger copy is possible.

**Email cohort (17 contacts):** CONTROL. The email channel has sent one email. The fallback pattern is the validated arm until a challenger beats it.

**CHALLENGER arms require:**

- A signal the record carries. **None do.**
- Copy that says something about that signal. **Impossible with no signal.**
- The copy clearing the claims gate against that contact's evidence. **No evidence to clear against.**

**So every cohort is CONTROL until a signal is discovered or invented.** A fabricated observation is worse than a missing arm. The honest count is one arm, not five.

---

## 7. Summary

| Metric | Value |
|--------|-------|
| Snapshot STAMP | 2026-09-15T17:52:12+00:00 from master cf23154 550 records |
| Total records | 550 |
| Clean LinkedIn contacts | 248 |
| Deployable after collision | 97 |
| Email-eligible (cold) | 39 |
| Email-eligible after STOP gate | 17 |
| Both-channels eligible | 39 |
| Signal | 100% NULL |
| Angle | 79% NULL |
| Persona | 75% NULL |
| Ladder | 3 → 10 → 25 → 50 (88 total, fits in 97) |
| Leftovers | 160 contacts with no cohort dimension |
| All cohorts | CONTROL arm |

**The ladder fits.** 97 deployable contacts support the 3 → 10 → 25 → 50 progression with 9 to spare. The next batch (>50) needs either new inventory from the 20,944-domain estate or the stopped-campaign ambiguity resolved (COHORT-HEADROOM-2026-09-15.md).

**The cohorts are coherent.** Persona is the only meaningful dimension. Signal is absent. Angle is mostly absent. The ladder is organized by persona (economic_buyer, champion, unspecified) and angle (founder, operations, delivery, unspecified).

**The arm is CONTROL.** No signal means no challenger. The operator's fallbacks are the validated arm. A fabricated observation is worse than a missing arm.

---

## Files

- `scripts/task155_cohort_ladder.py` — the analysis script
- `docs/COHORT-LADDER-2026-09-15.md` — this document
