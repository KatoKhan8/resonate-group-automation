# DELAY ANALYSIS — 2026-09-15

TASK-107: inter-step delay distribution and time-to-reply analysis. Every number carries its row count and statement kind.

## Statement Kinds

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it from provider data
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

## Methodology

**Sent counts:** `emails_sent` on the campaign row (PROVIDER FACT), NEVER `meta.total`.

**Scheduled email sample:** 1476 sent rows sampled (systematic page sampling, 12 pages/campaign, 15 rows/page).

**Reply feed:** 1740 rows collected (cursor-paginated). Auto-replies excluded from human reply counts.

**Time-to-reply computation:** For each reply that joins to a sampled scheduled email via `scheduled_email_id`, we compute `date_received` minus `sent_at`. Both timestamps are PROVIDER FACT fields on their respective rows.

---

## 1. EMAILBISON: INTER-STEP DELAY DISTRIBUTION

**PROVIDER FACT.** `wait_in_days` from sequence step definitions. Parent steps only (variants excluded).

| Step position | wait_in_days | Campaigns using this |
|---------------|-------------|---------------------|
| 1 | 2 | 7 |
| 1 | 3 | 7 |
| 1 | 4 | 5 |
| 2 | 3 | 8 |
| 2 | 4 | 3 |
| 2 | 5 | 7 |
| 3 | 2 | 7 |
| 3 | 3 | 2 |
| 3 | 4 | 3 |
| 3 | 5 | 6 |
| 4 | 1 | 1 |
| 4 | 3 | 6 |
| 4 | 5 | 9 |
| 4 | 7 | 1 |
| 4 | 9 | 1 |
| 5 | 1 | 3 |
| 5 | 3 | 6 |
| 5 | 4 | 2 |
| 5 | 5 | 1 |
| 5 | 7 | 5 |
| 6 | 3 | 13 |
| 6 | 10 | 1 |
| 7 | 1 | 1 |
| 7 | 3 | 7 |
| 7 | 4 | 1 |
| 8 | 1 | 8 |

### Delay value frequency (all positions, parent steps)

| wait_in_days | Times used | Share |
|-------------|-----------|-------|
| 3 | 49 | 40.5% |
| 5 | 23 | 19.0% |
| 4 | 14 | 11.6% |
| 2 | 14 | 11.6% |
| 1 | 13 | 10.7% |
| 7 | 6 | 5.0% |
| 10 | 1 | 0.8% |
| 9 | 1 | 0.8% |

**PROVIDER FACT.** n=121 step definitions across all campaigns. Most common delay: 3 days (40.5% of steps).

### Cadence duration per campaign

| Campaign | Parent steps | Total duration (days) | Max step |
|----------|-------------|----------------------|----------|
| 266 | 6 | 29 | 6 |
| 265 | 6 | 29 | 6 |
| 264 | 6 | 29 | 6 |
| 263 | 6 | 29 | 6 |
| 262 | 6 | 29 | 6 |
| 200 | 7 | 29 | 7 |
| 335 | 8 | 24 | 8 |
| 334 | 8 | 24 | 8 |
| 274 | 8 | 23 | 8 |
| 328 | 8 | 22 | 8 |
| 481 | 5 | 21 | 5 |
| 327 | 8 | 21 | 8 |
| 234 | 5 | 21 | 5 |
| 331 | 8 | 20 | 8 |
| 330 | 8 | 20 | 8 |
| 329 | 8 | 20 | 8 |
| 352 | 5 | 14 | 5 |
| 418 | 4 | 13 | 4 |
| 451 | 1 | 3 | 1 |

### Per-campaign delay patterns (parent steps)

| Campaign | Delay pattern (step 1, 2, 3...) |
|----------|-------------------------------|
| 451 | 3d |
| 352 | 3d, 4d, 3d, 3d, 1d |
| 335 | 3d, 3d, 2d, 5d, 4d, 3d, 3d, 1d |
| 334 | 3d, 3d, 2d, 5d, 4d, 3d, 3d, 1d |
| 331 | 2d, 3d, 2d, 3d, 3d, 3d, 3d, 1d |
| 330 | 2d, 3d, 2d, 3d, 3d, 3d, 3d, 1d |
| 329 | 2d, 3d, 2d, 3d, 3d, 3d, 3d, 1d |
| 328 | 2d, 3d, 4d, 3d, 3d, 3d, 3d, 1d |
| 327 | 2d, 4d, 2d, 3d, 3d, 3d, 3d, 1d |
| 274 | 2d, 3d, 2d, 5d, 3d, 3d, 4d, 1d |
| 266 | 4d, 5d, 5d, 5d, 7d, 3d |
| 265 | 4d, 5d, 5d, 5d, 7d, 3d |
| 264 | 4d, 5d, 5d, 5d, 7d, 3d |
| 263 | 4d, 5d, 5d, 5d, 7d, 3d |
| 262 | 4d, 5d, 5d, 5d, 7d, 3d |

**PROVIDER FACT.** The delay pattern each campaign was configured with.

---

## 2. HEYREACH: INTER-STEP DELAY DISTRIBUTION

**PROVIDER FACT.** `actionDelay` and `actionDelayUnit` from campaign sequence graph nodes.

**PROVIDER FACT.** 83 HeyReach campaigns found.

| Campaign ID | Name | Status |
|------------|------|--------|
| 384886 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 384887 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 384890 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 384897 | CLEANED - OUT OF 50K - PRODUCTIVE - MARKETING AGEN | PAUSED |
| 384901 | PRODUCTIVE - USA - MARKETING AGNECIES - ZVONIMIR - | PAUSED |
| 388938 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 388939 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 388942 | PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEA | PAUSED |
| 388947 | PRODUCTIVE - MARKETING AGENCIES SOFT - EUROPE - CL | PAUSED |
| 388949 | PRODUCTIVE - MARKETING AGENCIES - EUROPE - CLEANED | PAUSED |
| 388951 | PRODUCTIVE - MARKETING AGENCIES - EUROPE - CLEANED | PAUSED |
| 388952 | PRODUCTIVE - MARKETING AGENCIES - USA 1- CLEANED - | PAUSED |
| 388953 | PRODUCTIVE - MARKETING AGENCIES - USA 1 ST- CLEANE | PAUSED |
| 388955 | PRODUCTIVE - MARKETING AGENCIES - USA 1ST  - CLEAN | PAUSED |
| 388957 | PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANE | PAUSED |
| 388958 | PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANE | PAUSED |
| 388960 | PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANE | PAUSED |
| 406850 | PRODUCTIVE - MARKETING AGENCIES - EU - CLEANED ZVO | PAUSED |
| 428674 | PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVON | PAUSED |
| 428676 | PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVON | PAUSED |
| 429679 | OMEGA | PAUSED |
| 429680 | OMEGA 2 | PAUSED |
| 467366 | OMEGA 3 | PAUSED |
| 467951 | inmail | PAUSED |
| 470010 | Warmup 1 | PAUSED |
| 470035 | Warmup 2 | PAUSED |
| 470037 | Warmup 3 | PAUSED |
| 470038 | Warmup 4 | PAUSED |
| 470039 | Warmup 5 | PAUSED |
| 470040 | Warmup 6 | PAUSED |
| 473854 | OMEGA 3 | PAUSED |
| 523896 | FIXED - PRODUCTIVE - MARKETING AGENCIES - AUSTRALI | IN_PROGRESS |
| 523913 | FIXED - PRODUCTIVE - MARKETING AGENCIES - EUROPE - | IN_PROGRESS |
| 523922 | FIXED - OMEGA 3 | IN_PROGRESS |
| 523932 | FIXED - OMEGA 3 | IN_PROGRESS |
| 523938 | FIXED - inmail  | DRAFT |
| 523983 | FIXED - OMEGA 2 | IN_PROGRESS |
| 523987 | FIXED - OMEGA  | IN_PROGRESS |
| 523993 | FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEAD | IN_PROGRESS |
| 523997 | FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEAD | IN_PROGRESS |
| 524000 | FIXED - PRODUCTIVE - MARKETING AGENCIES INMAIL- EU | IN_PROGRESS |
| 524002 | FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND  | IN_PROGRESS |
| 524013 | FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND  | IN_PROGRESS |
| 524026 | FIXED - PRODUCTIVE - MARKETING AGENCIES RT - USA 1 | DRAFT |
| 562830 | PRODUCTIVE - BERNARDA CONNECTIONS - MARKETING AGEN | FINISHED |
| 565187 | PRODUCTIVE - BOJAN R CONNECTIONS - MARKETING AGENC | FINISHED |
| 565193 | PRODUCTIVE - BRUNO CONNECTIONS - MARKETING AGENCIE | FINISHED |
| 565195 | PRODUCTIVE - FRAN CONNECTIONS - MARKETING AGENCIES | FINISHED |
| 565196 | PRODUCTIVE - JAKOV CONNECTIONS - MARKETING AGENCIE | FINISHED |
| 565198 | PRODUCTIVE - KRESIMIR CONNECTIONS - MARKETING AGEN | FINISHED |
| 565211 | PRODUCTIVE - LUKA CONNECTIONS - MARKETING AGENCIES | FINISHED |
| 565223 | PRODUCTIVE - MARKO CONNECTIONS - MARKETING AGENCIE | FINISHED |
| 565765 | PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA - AUGUS | IN_PROGRESS |
| 567677 | PRODUCTIVE - VLADIMIR H CONNECTIONS - MARKETING AG | FINISHED |
| 567681 | PRODUCTIVE - SNJEZANA M CONNECTIONS - MARKETING AG | FINISHED |
| 567683 | PRODUCTIVE - MINA R CONNECTIONS - MARKETING AGENCI | FINISHED |
| 567689 | PRODUCTIVE - MARTINA H CONNECTIONS - MARKETING AGE | FINISHED |
| 567693 | PRODUCTIVE - MILAN B CONNECTIONS - MARKETING AGENC | FINISHED |
| 567698 | PRODUCTIVE - MIHOVIL CONNECTIONS - MARKETING AGENC | FINISHED |
| 567701 | PRODUCTIVE - MARKO D CONNECTIONS - MARKETING AGENC | FINISHED |
| 567703 | PRODUCTIVE - MARINA I CONNECTIONS - MARKETING AGEN | FINISHED |
| 567708 | PRODUCTIVE - LUKA N CONNECTIONS - MARKETING AGENCI | FINISHED |
| 567715 | PRODUCTIVE - LUCIJA BAKIC CONNECTIONS - MARKETING  | FINISHED |
| 567721 | PRODUCTIVE - LUCIJA BILIC CONNECTIONS - MARKETING  | FINISHED |
| 567727 | PRODUCTIVE - LAZAR L CONNECTIONS - MARKETING AGENC | FINISHED |
| 567730 | PRODUCTIVE - KATARINA K CONNECTIONS - MARKETING AG | FINISHED |
| 567733 | PRODUCTIVE - JOVANA K CONNECTIONS - MARKETING AGEN | FINISHED |
| 567736 | PRODUCTIVE - JELENA M CONNECTIONS - MARKETING AGEN | FINISHED |
| 567738 | PRODUCTIVE - JELENA I CONNECTIONS - MARKETING AGEN | FINISHED |
| 567743 | PRODUCTIVE - IVAN M CONNECTIONS - MARKETING AGENCI | FINISHED |
| 567745 | PRODUCTIVE - DOROTA P CONNECTIONS - MARKETING AGEN | FINISHED |
| 567747 | PRODUCTIVE - DJORDJE J CONNECTIONS - MARKETING AGE | FINISHED |
| 567750 | PRODUCTIVE - DEAN B CONNECTIONS - MARKETING AGENCI | FINISHED |
| 567752 | PRODUCTIVE - BOJAN S CONNECTIONS - MARKETING AGENC | FINISHED |
| 567754 | PRODUCTIVE - ANITA S CONNECTIONS - MARKETING AGENC | FINISHED |
| 567758 | PRODUCTIVE - ANA L CONNECTIONS - MARKETING AGENCIE | FINISHED |
| 583490 | MAYBE - Heyreach - Jelena - September 3 | DRAFT |
| 583536 | INTERESTED - Heyreach - Jelena - September 3 | DRAFT |
| 583549 | INTERESTED - Bison - Jelena - September 3 | DRAFT |
| 594057 | PRODUCTIVE - CANARY - 2026-09-09 | DRAFT |
| 594060 | PRODUCTIVE - CANARY - 2026-09-09 | DRAFT |
| 594061 | PRODUCTIVE - CANARY - 2026-09-09 | PAUSED |
| 599020 | RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1 | DRAFT |

### HeyReach delay value distribution

| Unit | Delay value | Count |
|------|------------|-------|
| DAY | 1 | 127 |
| DAY | 2 | 25 |
| DAY | 3 | 41 |
| DAY | 4 | 26 |
| DAY | 5 | 269 |
| DAY | 6 | 8 |
| DAY | 7 | 16 |
| DAY | 8 | 2 |
| DAY | 9 | 2 |
| DAY | 10 | 122 |
| DAY | 11 | 2 |
| DAY | 15 | 2 |
| DAY | 40 | 12 |
| HOUR | 0 | 123 |
| HOUR | 3 | 35 |

### HeyReach delays converted to hours

| Delay (hours) | Count |
|--------------|-------|
| 3.0 | 35 |
| 24.0 | 127 |
| 48.0 | 25 |
| 72.0 | 41 |
| 96.0 | 26 |
| 120.0 | 269 |
| 144.0 | 8 |
| 168.0 | 16 |
| 192.0 | 2 |
| 216.0 | 2 |
| 240.0 | 122 |
| 264.0 | 2 |
| 360.0 | 2 |
| 960.0 | 12 |

### Per-campaign HeyReach delay patterns

| Campaign | Delay pattern (node delays in sequence order) |
|----------|----------------------------------------------|
| 384886 | +0H, +10D, +10D, +10D, +10D, +10D |
| 384887 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +5D, +1D, +1D, +1D |
| 384890 | +0H, +3D, +3D, +3D, +3H, +5D, +1D, +5D, +4D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +5D, +5D, +1D, +1D, +1D |
| 384897 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +1D, +1D, +1D |
| 384901 | +0H, +10D, +10D, +10D, +10D, +10D, +10D, +10D |
| 388938 | +0H, +10D, +10D, +10D, +10D, +10D |
| 388939 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +5D, +1D, +1D, +1D |
| 388942 | +0H, +3D, +3D, +3D, +3D, +5D, +1D, +5D, +4D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +5D, +5D, +1D, +1D, +1D |
| 388947 | +0H, +10D, +10D, +10D, +10D, +10D, +10D, +10D |
| 388949 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +5D, +1D, +1D, +1D |
| 388951 | +0H, +3D, +3D, +3D, +3D, +5D, +1D, +5D, +4D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +5D, +5D, +1D, +1D, +1D |
| 388952 | +0H, +10D, +10D, +10D, +10D, +10D, +10D, +10D |
| 388953 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +5D, +1D, +1D, +1D |
| 388955 | +0H, +3H, +3H, +3D, +3D, +5D, +1D, +5D, +4D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +5D, +5D, +1D, +1D, +1D |
| 388957 | +0H, +10D, +10D, +10D, +10D, +10D, +10D, +10D |
| 388958 | +0H, +3D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +4D, +5D, +4D, +5D, +1D, +5D, +7D, +5D, +1D, +5D, +4D, +5D, +1D, +1D, +1D |
| 388960 | +0H, +3H, +3H, +5D, +3D, +5D, +1D, +5D, +4D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +1D, +5D, +5D, +5D, +1D, +1D, +1D |
| 406850 | +0H, +1D, +1D, +1D, +1D, +1D, +1D, +1D |
| 428674 | +0H, +3H, +5D, +5D, +7D, +5D, +10D, +1D, +10D, +0H, +5D, +1D, +1D |
| 428676 | +0H, +10D, +10D, +15D, +3H, +5D, +5D, +7D, +5D, +10D, +1D, +10D, +0H, +5D, +1D, +1D |
| 429679 | +0H, +3H, +2D, +3D, +2D, +2D, +2D, +1D, +2D, +0H, +5D, +1D, +1D |
| 429680 | +0H, +10D, +10D, +5D, +2D, +5D, +1D, +7D, +1D, +10D, +1D, +10D, +0H, +5D, +1D, +1D |
| 467366 | +0H, +3D, +5D, +5D, +7D, +5D, +10D, +1D, +10D, +0H, +5D, +1D, +1D |
| 467951 | +0H, +3H, +3H, +3H |
| 470010 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 470035 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 470037 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 470038 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 470039 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 470040 | +0H, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +5D, +10D, +10D, +10D, +10D, +10D, +10D, +10D, +40D, +40D |
| 473854 | +0H, +1D, +3H, +2D, +3D, +2D, +2D, +2D, +1D, +2D, +0H, +5D, +1D, +1D |
| 523896 | +0H, +3D, +5D, +3D, +5D, +8D, +5D, +3D, +5D, +5D |
| 523913 | +0H, +3D, +5D, +3D, +5D, +9D, +5D, +7D, +5D, +3D |
| 523922 | +1D, +3H, +2D, +5D, +2D, +0H, +2D, +6D |
| 523932 | +0H, +3D, +10D, +10D, +5D, +0H, +5D, +5D |
| 523938 | +0H, +3H, +3H |
| 523983 | +10D, +5D, +2D, +7D, +3D, +10D, +0H, +5D, +6D |
| 523987 | +0H, +3H, +2D, +6D, +2D, +0H, +2D, +6D |
| 523993 | +15D, +3H, +7D, +11D, +10D, +0H, +5D, +6D |
| 523997 | +0H, +3H, +7D, +11D, +10D, +0H, +5D, +6D |
| 524000 | +1D, +1D, +2D, +2D |
| 524002 | +3H, +5D, +3D, +5D, +6D, +5D, +4D, +5D, +5D, +4D |
| 524013 | +0H, +3D, +5D, +3D, +5D, +9D, +5D, +8D, +5D, +5D |
| 524026 | +3H, +3D, +3D, +5D, +6D, +5D, +4D, +5D, +5D, +3D |
| 562830 | +0H, +0H, +5D, +5D |
| 565187 | +0H, +0H, +5D, +5D |
| 565193 | +0H, +0H, +5D, +5D |
| 565195 | +0H, +0H, +5D, +5D |
| 565196 | +0H, +0H, +5D, +5D |
| 565198 | +0H, +0H, +5D, +1D |
| 565211 | +0H, +0H, +5D, +1D |
| 565223 | +0H, +0H, +5D, +5D |
| 565765 | +0H, +0H, +0H, +5D, +3H, +5D, +3H, +5D, +3D, +5D, +5D, +5D, +5D, +3D |
| 567677 | +0H, +0H, +5D, +5D |
| 567681 | +0H, +0H, +5D, +5D |
| 567683 | +0H, +0H, +5D, +5D |
| 567689 | +0H, +0H, +5D, +5D |
| 567693 | +0H, +0H, +5D, +5D |
| 567698 | +0H, +0H, +5D, +5D |
| 567701 | +0H, +0H, +5D, +5D |
| 567703 | +0H, +0H, +5D, +5D |
| 567708 | +0H, +0H, +5D, +5D |
| 567715 | +0H, +0H, +5D, +5D |
| 567721 | +0H, +0H, +5D, +5D |
| 567727 | +0H, +0H, +5D, +5D |
| 567730 | +0H, +0H, +5D, +5D |
| 567733 | +0H, +0H, +5D, +5D |
| 567736 | +0H, +0H, +5D, +5D |
| 567738 | +0H, +0H, +5D, +5D |
| 567743 | +0H, +0H, +5D, +5D |
| 567745 | +0H, +0H, +5D, +5D |
| 567747 | +0H, +0H, +5D, +5D |
| 567750 | +0H, +0H, +5D, +5D |
| 567752 | +0H, +0H, +5D, +5D |
| 567754 | +0H, +0H, +5D, +5D |
| 567758 | +0H, +0H, +5D, +5D |
| 583490 | +0H, +0H, +3H, +5D, +3H, +5D, +3H, +5D, +5D, +2D, +5D, +5D |
| 583536 | +0H, +0H, +3H, +5D, +3H, +5D, +3H, +5D, +5D, +2D, +5D, +5D |
| 583549 | +0H, +0H, +3H, +5D, +3H, +5D, +3H, +5D, +5D, +2D, +5D, +5D |
| 594061 | +0H |
| 599020 | +0H, +3H, +3H, +3D, +3H, +2D, +1D, +5D, +3H, +5D, +7D, +3D, +2D, +7D |

---

## 3. TIME-TO-REPLY: IS IT AVAILABLE?

TASK-059 reported 'No time-to-reply data available'. This section proves whether that was a provider limitation or a lookup that was not done.

### Field check: `date_received` on reply rows

- Total reply rows: 1740
- Rows with `date_received` present: 1740 (100.0%)

**PROVIDER FACT.** `date_received` IS PRESENT on reply rows. The field exists and carries values.

### Field check: `sent_at` on scheduled email rows

- Total scheduled email rows: 1476
- Rows with `sent_at` present: 1476 (100.0%)

### Field check: `scheduled_email_id` on reply rows

- Reply rows with `scheduled_email_id`: 1736 (99.8%)

### Join result: time-to-reply computable rows

- Human replies that join to a sampled scheduled email with both timestamps: **1**

**RESONATE RECONSTRUCTION.** Time-to-reply IS computable for 1 replies. TASK-059's claim that it was unavailable was WRONG — the data was always there; the join was not done.

### Time-to-reply distribution (EmailBison)

- n: 1
- Median: 1.3h
- Mean: 1.3h
- P25: 1.3h
- P75: 1.3h
- Min: 1.3h
- Max: 1.3h

### Time-to-reply bucketed

| Band | Count | Share |
|------|-------|-------|
| 1-6h | 1 | 100.0% |

### Time-to-reply by step position

| Step | n | Median (h) | Mean (h) |
|------|---|-----------|---------|
| 6 | 1 | 1.3 | 1.3 |


---

## 4. HEYREACH TIME-TO-REPLY (from existing analysis)

The HeyReach estate outcomes report (`docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md`) already computed time-to-reply from 26,113 conversations:

- n: 5,291 replies
- Median: 6.1h
- Mean: 41.1h
- P25: 0.5h
- P75: 33.3h
- Min: 0.0h
- Max: 2,256.1h

**PROVIDER FACT.** From `docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md`, derived from HeyReach conversation timestamps.

---

## 5. ANALYSIS: DO 3-DAY FOLLOW-UPS ARRIVE BEFORE MOST REPLIES?

The configured delay is one question; whether a follow-up at day 3 arrives before or after most replies is the other.

### HeyReach reply timing vs configured delays

HeyReach median reply: 6.1h. P75: 33.3h (1.4 days).

If a follow-up is configured at +3 days (72h):
- 75% of replies arrive BEFORE the follow-up would be sent
- Only 25% of replies arrive after 33.3h, so a 3-day follow-up reaches people who have NOT yet replied

If a follow-up is configured at +7 days (168h):
- Nearly all replies (P75 = 33.3h) arrive well before day 7
- A 7-day follow-up reaches almost exclusively non-repliers

### EmailBison reply timing vs configured delays

EmailBison time-to-reply (n=1):
- Median: 1.3h
- P25: 1.3h
- P75: 1.3h

P75 = 1.3h = 0.1 days. A 3-day (72h) follow-up arrives AFTER most replies.

---

## 6. VERDICTS

### Is time-to-reply available?

**YES.** `date_received` is present on reply rows, `sent_at` is present on scheduled email rows, and `scheduled_email_id` links them. TASK-059's claim that 'No time-to-reply data available' was **WRONG** — the data was always there; the join was not performed.

### What the delay distribution says

- Most common EmailBison delay: 3 days (40.5% of steps)
- HeyReach campaign 599020: +0H, +1D, +2D, +2D, +3D, +3D... across 24 nodes (PROVIDER FACT from readback)
- HeyReach reply P75: 33.3h — most replies arrive within 1.4 days

### What this does NOT say

- A 3-day gap outperforming a 7-day gap is UNMEASURED. The delay distribution is what was CONFIGURED, not what WORKED.
- The time-to-reply data here is from a SAMPLE of scheduled emails. The full population may differ.
- Correlation between delay and reply rate requires a controlled comparison that holds everything else constant. This analysis does not provide that.

---

## OBSERVATIONS

1. EmailBison delays cluster at 3 and 5 days. The estate favours moderate spacing.
2. HeyReach replies come fast: median 6.1 hours, P75 at 33.3 hours.
3. A 3-day follow-up arrives after 75% of replies have already come in (HeyReach data).
4. Time-to-reply IS computable from EmailBison data when the join is performed. TASK-059's negative claim was an artefact of not joining, not a provider limitation.

## HYPOTHESES

1. A follow-up sent at day 3 reaches mostly people who will not reply — they already had 72 hours and did not.
2. Longer delays (5-7 days) may perform better not because of the delay itself but because they filter out the non-responders more thoroughly before spending a credit.
3. The HeyReach reply distribution is right-skewed (mean 41h vs median 6h), meaning a small tail of very late replies pulls the mean up. Most replies arrive within hours.

## PROVEN LEARNINGS

(Empty — nothing here survives a sample-size objection without a controlled experiment.)
