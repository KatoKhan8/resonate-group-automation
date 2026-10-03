# The second brain

Opened 2026-10-03 on the operator's instruction. This directory is where
everything the system LEARNS lives — the part that cannot be derived from the
code, and that a fresh session would otherwise have to rediscover by spending
credits or by making the same mistake again.

## The five files

| file | what belongs in it | who writes it |
|---|---|---|
| `linkedin.md` | every HeyReach campaign on the seat: our own texts in full, recipients anonymised, then the synthesis | the lane reading the provider |
| `email.md` | the same for EmailBison: what the old campaigns did, what earned replies, what did not | the lane reading the provider |
| `scenarios.md` | what the phase-2 scenarios showed, and **which rules turned out not to exist** | the simulation lane |
| `defects.md` | the PATTERNS behind the defect maps, not the individual defects | whoever finds the second instance of one |
| `decisions.md` | every operator decision, with its date and its reason | the main session |

## The four rules, which are not style

1. **Every line carries its source, its date and its `n`.** A rate without a
   denominator is an opinion. "Short notes do better" is not a finding;
   "9.75% acceptance over 4,256 sent, seat lifetime, 2026-10-03" is.
2. **Nothing goes in without a measurement.** Advice that is not a number with
   an `n` beside it does not belong here. If something is worth saying and
   cannot be measured, say that it cannot be measured and what would measure it
   — that sentence is itself a finding.
3. **Updated at each finding, never retroactively.** Same discipline as the
   defect map: a file somebody has to remember to backfill is a file that
   drifts, and a drifted record is worse than none because it is believed.
   An entry is written when the measurement is made, with that day's date, and
   a later correction is ADDED and dated rather than edited over.
4. **The writer reads only approved exemplars, never the syntheses** — until
   the operator approves otherwise. A synthesis is this system's reading of its
   own history; feeding it back into generation would let the copy engine learn
   from its own summary of itself.

## PII

**Recipient names and companies are anonymised here. Our own texts — connection
notes, messages, emails — are ours and stay in full.** Real recipient data stays
in `work/`, which is gitignored for exactly this reason.

Run a PII scan **with a positive control** before every commit: a scan that
finds nothing is only trustworthy once you have proved it can find something.
And do not spell the forbidden tokens inside the file that forbids them — on
2026-10-02/03 a check reintroduced the names it existed to keep out three times
in one night: an anonymiser's own metadata field listed its substitution
patterns (twice), and then a test's literal list of forbidden strings was
matched by the scan over the staged diff.

## Where this is reported

The weekly handover carries a section **"what is new in the second brain"**.
That is the only summary of this directory anybody is asked to read; the files
themselves are the record.
