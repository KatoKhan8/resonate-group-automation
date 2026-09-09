# Resonate Group Automation

One engine, two lanes. `revive` takes a stalled or dead account (CRM dump plus
the full thread) and must produce a diagnosis before it is allowed to write an
email. `cold` takes a signal and must produce a specific hook. Same enrichment,
same verification, same lint, same output files.

Deterministic work lives in the scripts so it costs no context. The reading,
diagnosing and writing is the batch session's job, and `PLAYBOOK.md` is the
contract it works to.

## Layout

```
batches/            input: a CSV, a JSONL, or a folder of pasted CRM dumps
config/suppress.txt live and current accounts. Never sequenced.
work/queue.jsonl    the entire state, one JSON line per record
bin/prep.py         ingest, normalise domains, dedupe, suppress
bin/rec.py          the only read/write path into state
bin/verify.py       Reoon power-mode check on catch-all addresses
bin/build.py        lint every draft, emit review sheet and push files
bin/push.py         EmailBison and HeyReach
out/                review.html, emailbison.csv, heyreach.csv, summary.json
```

## A run

```bash
python3 bin/prep.py batches/2026-08-16.csv --client contactout --lane revive
python3 bin/rec.py list --state queued
```

Open a Cowork session in this folder and say **work the queue**. Per record it
reads the context, calls ContactOut `decision-makers` and `email-verifier`,
falls back to AI Ark on misses, writes contacts back, diagnoses or hooks,
drafts, and patches the record to `drafted`.

```bash
python3 bin/verify.py --emit          # catch-all addresses needing Reoon
python3 bin/verify.py --ingest work/reoon.json
python3 bin/build.py                  # lint + outputs
open out/review.html                  # you read the red ones only
python3 bin/push.py --to both --live --campaign 42 --heyreach-campaign 7 --sender-account 3
```

`verify.py --direct` calls Reoon over HTTP instead, for n8n or your own machine.
In the Anthropic sandbox the egress proxy blocks it, so `--emit` plus WebFetch
is the path there.

## The lint is the scaling mechanism

Nothing reaches a CSV unless it passes `build.py`: no em or en dashes, no
attachment talk, no unfilled placeholders, no hard-wrapped paragraphs, 40 to
180 words, subject under 60 characters, no filler openers, and the recipient
must be a verified address that actually exists in that record's contact list.
Failures stay in `review.html` in red. You read exceptions instead of
proofreading thirty emails.

## Throughput and cost

Roughly 4 to 6 minutes of session time per revive record, faster for cold.
Credits per record: 1 search credit per decision maker returned, 1 email credit
per profile where an address is found, 1 verifier credit per definitive result.
`people-count` is free, so size the prospect's market before writing.

A 30 record batch is one session. Beyond that, split into two batches rather
than pushing one session further, because a session that runs long starts
summarising records to itself and the diagnoses get vaguer.

## Env

```
CONTACTOUT_TOKEN   only if you swap the MCP calls for REST at volume
REOON_KEY          verify.py --direct
BISON_KEY          push.py, base defaults to send.resonategroup.co/api
HEYREACH_KEY       push.py --to heyreach
```
