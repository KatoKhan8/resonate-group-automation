# TASK-244 — export / clean / import, and suppression that sticks at S1

**THIS REPLACES the earlier TASK-244 ("two approval intake readers").** The
operator changed the model on 2026-09-21 after that brief was written: there
is no per-domain Yes/No column and no Slack approval flow. Approval is a file
that goes to the client and comes back shorter.

OPERATOR DECISION, 2026-09-21, Zvonimir, recorded verbatim:

> EXPORT. On demand and by default weekly, produce a candidate snapshot for
> the client: sourced domains that passed S3 ICP, S4b MX and local collision,
> minus everything on that client's suppression. Columns: domain, company,
> headcount, industry, country, website. CSV, no contacts, no emails, no PII.
> Record the snapshot: id, date, domain set, hash. Target size 40 to 50k
> domains per snapshot when supply allows; report the count.
>
> IMPORT. When the cleaned file comes back, match it to its snapshot by id or
> by content. Domains present in the returned file become client_approval =
> approved. Domains in the snapshot but absent from the return become CLIENT
> SUPPRESSION for that client, permanent, with reason "removed by client in
> snapshot <id>". Domains in the return that were not in the snapshot are
> reported as anomalies and not approved. Report: sent, returned, approved,
> suppressed, anomalies.
>
> Client suppression is per workspace, never shared across clients, and is
> applied at S1 for every future sourcing run and every future export, so a
> removed domain never reappears in that client's list. Global suppression
> (unsubscribes, bounces, legal) stays global.
>
> This is an engine feature, not a Productive branch: workspace config holds
> the export columns and cadence; the logic lives once in src/.

## THE DIFF IS BUILT AND TESTED. YOU DO NOT REBUILD IT.

`src/clientapproval.py` is on master as of tonight, with 27 tests. **Rebase
first.** It already owns: the four states, `require_approved`,
`is_suppressed`, `record_snapshot`, `snapshot_matching` (content hash, so a
re-saved file still matches), `diff_return` and `apply_return`.
`scripts/client_snapshot.py` is the export/import/adopt/counts mouth on it.

Your job is the three things that module deliberately does not do.

## 1. THE EXPORT IS A REAL CSV, BUILT FROM CANDIDATES

`scripts/client_snapshot.py export` takes a domain list and records it. It
does not BUILD the list and it does not write the client's CSV. Build both:

- select from TASK-245's candidate list: S3 ICP IN, S4b MX known_allowed or
  unknown_provider, local collision cleared, **minus
  `clientapproval.suppressed_domains(client)`**, minus anything already
  approved (do not re-ask a client a question they have answered)
- columns EXACTLY: `domain, company, headcount, industry, country, website`
- **NO contacts, NO emails, NO person names, ever.** There is a PII guard in
  the suite and it is now green; a person's name in a client export would be
  a new leak in a file we hand to a third party.
- target 40,000-50,000 domains when supply allows. Report the count, and
  report it honestly when supply does not allow - a 4,000-row snapshot is a
  supply finding, not a failure to pad.
- the id, date, count and content hash are recorded through
  `clientapproval.record_snapshot`, which refuses a re-used id.

## 2. SUPPRESSION APPLIES AT S1, ON EVERY RUN, FOREVER

`clientapproval.is_suppressed(domain, client)` is the question. Ask it in S1
hygiene for every future sourcing run and in the export builder, per client.

**The failure this prevents is specific and expensive:** a client deletes 600
domains from a snapshot, the next nightly run sources them again because they
still match the ICP, and they appear in the next export. The client deletes
them again and concludes we do not listen. One test must reproduce exactly
that: suppress, re-source the same domains, and assert they reach neither the
candidate list nor the export.

Cross-client isolation gets its own test: the same domain suppressed for
Productive and approved for another workspace stays both.

## 3. CONFIG, BECAUSE THIS IS AN ENGINE FEATURE

Workspace config holds the export columns and the cadence (weekly default,
Monday 07:00 Zagreb, and it moves with DST - ask `geo`, do not hardcode a UTC
hour; `DIGEST_HOUR` moves 5 -> 6 on 2026-10-25). A second client must be
onboardable by adding config, not by editing logic. Productive's values go in
config; no `if client == "productive"` anywhere.

## WHAT IS ALREADY TRUE AND MUST NOT BE RE-DERIVED

Productive's `productive_ICP_safe_to_send (1).csv` is ADOPTED as snapshot
`PRODUCTIVE-2026-09-07`: 24,710 domains, all approved, nothing suppressed.
Do not re-import it, do not diff against it, do not "clean up" its
provenance. The next export is the first real one.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions. Baseline tonight: 10,671 / 50 /
33 (your rebase will move it; diff against what master gives you).

Required tests beyond the two above: the export excludes already-approved
domains; the export carries no column that can hold PII; a snapshot id is
recorded exactly once; an export built while supply is short reports the
short count rather than relaxing a filter to reach it.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/.env    work/*.jsonl
