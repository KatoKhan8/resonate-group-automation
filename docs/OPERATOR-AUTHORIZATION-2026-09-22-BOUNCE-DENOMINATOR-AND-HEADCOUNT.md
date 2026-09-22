# Operator authorization — 2026-09-22 — bounce denominator, export route, one-off headcount amendment

Recorded verbatim, Zvonimir, 2026-09-22. Nothing below the grant reinterprets
it. Sending identifiers are redacted to reserved domains under ISSUE-006; the
live values are in the session's scratch read, never in git.

---

## A. BOUNCE STOP — rule change, recorded with name and date

    A. BOUNCE STOP, rule change recorded with my name and date: the
       bounce hard stop evaluates a mailbox only once it has at least 20
       sends in the 7-day window; below that the rate is UNDEFINED and
       does not trip. The two mailboxes that tripped on n=2 and n=3 are
       excluded from new enrollment until they reach 20 sends; their
       scheduled rows continue. The stop is cleared; proceed with the AU
       ninth campaign and the 289 US re-engagement leads: stats, 15-minute
       veto, push.

### What tripped, and why the denominator was the defect

Read live at 2026-09-22T16:0xZ, per mailbox over the trailing 7 days:

    <mailbox-a>@example.test      1 sent  1 bounced   50.00%
    <mailbox-b>@example.test      2 sent  1 bounced   33.33%
    estate-wide                 147 sent  2 bounced    1.34%

Both tripped "bounce > 2% on any mailbox over 7 days" on denominators of 2 and
3. **A rate over n=2 is not a measurement**, and the estate is at 1.34%. The
amendment fixes the rule rather than waiving the incident, so the next mailbox
to send its first email does not halt the estate the same way.

### The rule as it now reads

    a mailbox with FEWER THAN 20 sends in the trailing 7 days has an
    UNDEFINED bounce rate and CANNOT trip the stop
    at 20 sends or more, bounce > 2% over 7 days halts the push as before

**UNDEFINED is not PASS.** The two mailboxes above are excluded from NEW
enrollment until they reach 20 sends. Their already-scheduled rows continue —
the amendment does not pause a mailbox, it declines to judge one.

### What this does NOT touch

Every other hard stop is unchanged and still halts PUSH, never enrichment: any
spam complaint, a reply not stopping the other channel within 15 minutes, an
unsubscribe not propagated, a verification rule weakened.

---

## B. EXPORT ROUTE

    B. EXPORT ROUTE: ship a QUALIFIED-only export today from the estate we
       hold (the 1,508 candidates plus the store, through S3, MX,
       collision, client suppression). In parallel measure whether AI-ARK
       people_search partitions on country/industry/headcount, and add
       ContactOut company search (/v1/company/search with industry, size
       and location filters, free /count first) to the same measurement.
       Whichever proves its filters are honoured becomes tomorrow's larger
       export path. Record the finding.

This supersedes the sliced-AI-ARK-company-search instruction for today's
deliverable. The reason is measured, not argued: `companyIndustry` and
`companyLocation` on AI ARK company search are **accepted and inert** —
identical `totalElements` (72,657,969) and byte-identical row hashes across
all four filter combinations. A filter that changes nothing cannot partition a
72M-row corpus into slices under 10k.

---

## D. HEADCOUNT — one-off amendment, this file and this run only

    D. HEADCOUNT, this run only:
       1. Remove the headcount criterion from the S3 ICP verdict for the
          2026-09-07 Productive file (24,404 domains). Geo and industry
          rules unchanged; unknown country stays FLAGGED. Record as a
          one-off amendment for this file with my name and date, not a
          change to config/clients/productive.yaml; the 20+ floor still
          applies to sourced accounts and future exports.
       2. Re-run S3 with the amended judge; report the new IN / OUT /
          FLAGGED split against 5,094 / 15,642 / 3,668.
       3. Process everything that clears: MX, local collision with the
          recency rule and client suppression, S5 in the recorded order,
          S7, no asking. Batches under the pacing rule against the forward
          book, dual-channel, stats, veto, push. US cohorts first; UK/EU
          and AU tagged and waiting.
       4. The 3,668 FLAGGED stay on the re-qualification path.
       5. At the 18:00 summary: domains recovered by this amendment,
          contacts verified, READY added, and the collision cut shown
          separately from the ICP cut.

### The scope line that matters

**`config/clients/productive.yaml` IS NOT EDITED.** The amendment is carried as
a one-off judge parameter bound to the 2026-09-07 Productive snapshot
(24,404 domains) and to nothing else. The 20+ headcount floor still applies to
every sourced account and every future export. A session that reads the config
and concludes the floor was dropped has read the wrong artifact.

### Baseline the re-run is diffed against

    IN       5,094
    OUT     15,642
    FLAGGED  3,668
             ------
            24,404

Per the baseline rule, the diff is on the SET of domains, not on the counts:
regenerate the JSON and diff the domain sets, because two runs can agree on a
count and disagree on every member.
