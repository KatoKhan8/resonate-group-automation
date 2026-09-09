# Queue schema

One JSON object per line in `work/queue.jsonl`. It is the whole state. Read and
write it through `src/store.py` and nothing else. A line is never deleted: a
record that cannot proceed is dropped, keeping its `drop_reason`, so a batch
stays auditable and re-runnable.

Field shape is defined once, in `store.new_record()`. This file documents it.

```jsonc
{
  "id": "arbor-test",          // slug, unique across the queue
  "lane": "domains",          // revive | cold | domains
  "client": "productive",     // keys into config/clients/<client>.yaml
  "company": "Arbor",
  "domain": "arbor.test",      // normalised: lowercase, no scheme, no www, no path
  "context": "",              // revive: CRM dump plus the full thread, verbatim
  "signal": "",               // cold: the trigger
  "state": "queued",
  "drop_reason": null,        // required whenever state is "dropped"

  "company_facts": {},        // domains lane, from the provider          (phase 4)
  "contacts": [],             // name, title, linkedin, email, email_source,
                              // persona, angle, verdict, reoon, sendable,
                              // primary                                  (phase 4)
  "excluded": [],             // rejected people, with a why              (phase 6)
  "diagnosis": null,          // revive: died_on, died_because,
                              // failure_mode, last_position, what_changed (phase 5)
  "hook": null,               // cold: the one specific checkable fact    (phase 5)
  "sizing": null,             // query, profiles, mobiles                 (phase 5)
  "cadence": {},              // per contact, the dated multichannel steps (phase 7)

  "log": [{"step": "queued", "at": "2026-08-25T10:00:00Z", "note": "..."}]
}
```

## States

```
queued -> enriched -> verified -> drafted -> approved -> pushed
                                   terminal: dropped | held
```

`held` is not a failure. It is an address that did not clear verification and
keeps its drafts, because the fix is usually one Reoon run away. `dropped` is
terminal and always carries a reason.

`approved` is **derived, not set**. `approve.sync_state()` recomputes it from
the per-step approval fingerprints: a record is `approved` when every step a
human could approve carries a current signature, and falls back to `drafted`
the moment one is edited or revoked. Nothing else writes it, and it only ever
moves between those two values — a `dropped`, `held` or `pushed` record has a
state that means something the sync has no business overwriting.

### Company qualification is a substate, not a state

A company that is `rejected` for ICP purposes is still a perfectly ordinary
`enriched` record: it has a domain, it may have contacts, and every record
invariant still holds for it. Putting the ICP verdict in the top-level state
machine would mean a single field answering two unrelated questions — how far
through the pipeline is this, and is it our market — and the first one would
lose. So the qualification lifecycle lives under `qualification` on the record,
with its own vocabulary in `dmplan.STATES`:

```
not_processed -> company_enriched -> classified
              -> review_required | qualified | rejected
              -> dm_enrichment_pending -> dm_enrichment_approved
              -> dm_enrichment_complete
```

`qualify.state_of(rec)` reads it back off the record rather than storing it as
a field, so the two can never disagree.

## Where a generated email lives

There is no top-level `draft`. A generated email is a cadence step, keyed by the
contact slug, exactly as in BUILD-SPEC section 3:

```jsonc
"cadence": {
  "petra-horvat": {                          // slug of the contact's name
    "day1":  {"channel": "email", "generated": true, "subject": "...", "body": "..."},
    "day3":  {"channel": "linkedin", "note": "..."},
    "day5":  {"channel": "email", "template": "ops_pain", "vars": {"line": "..."}}
  }
}
```

The unit of lint is therefore one *(record, contact, step)*, and one record can
carry several drafts. `lint.py` reads only steps where `channel` is `email` and
a `body` is present: LinkedIn notes are not linted yet, and a template step with
no body is one the cadence expander has not filled (phase 7).

The recipient is not stored on the step. It is the contact whose slug matches
the cadence key, which is what makes "the recipient is in that record's own
contact list" checkable.

### Known risks, for phase 6 and 7

- **Template steps are unlinted while they have no body.** A step like
  `{"channel": "email", "template": "ops_pain", "vars": {...}}` is skipped by
  `lint.email_steps()` because there is nothing to check yet. Phase 7 must lint
  the **final expanded** email and nothing may enter a push path unlinted.
  Four of the six emails in the default cadence are template steps, so this is
  most of the sending volume.
- **Cadence keys lose non-Latin characters.** The key is `slug(contact.name)`,
  and `slug()` keeps only `a-z0-9`, so `Ćuk Šimić` becomes `uk-imi` and a name
  with no Latin characters at all falls back to `record`. It is deterministic,
  so phase 2 resolves whatever key exists, but two such contacts on one domain
  would collide on a single key. Phase 6 generates these keys and owns the fix
  (transliteration, or a key that is not derived from the name). Do not change
  `slug()` for this without deciding what happens to existing record ids.

## Rules

- Nothing is ever removed from the file. Drop it with a reason instead.
- `drop_reason` is mandatory when `state` is `dropped`. `store.validate()` enforces it.
- `lane` and `state` are closed enums, in `store.LANES` and `store.STATES`.
- Ids are unique. `store.append()` refuses a collision.
- The queue is written atomically, whole file at a time, via a temp file and a
  rename, so a crash mid-write leaves the previous queue intact.

## What Phase 1 fills

`id`, `lane`, `client`, `company`, `domain`, `context`, `signal`, `state`,
`drop_reason`, `log`. Everything else is created empty and filled by a later
phase, marked above.

## What phases 4, 5 and 6 add

Three additions to the section 3 shape, all additive and all optional:

- `contacts[].key` — the contact id the cadence is keyed by, assigned by
  `src/identity.py` (phase 6). Section 3 keys `cadence` "per contact id"; this
  is that id, stored so it never moves under a record already in flight. A
  record with no stored key still resolves by computing it.
- `contacts[].sendable` — computed from `verdict` and `reoon` by phase 4 and
  recomputed on every enrich pass. Lint never trusts the stored value.
- `evidence` — a top-level map of contact key to the evidence behind that
  contact's angle (phase 5). Every element is checked as traceable to
  `company_facts` or the contact before it is stored.

`log` entries may carry structured extras beyond `step`, `at` and `note`: the
number of model attempts, what was rejected, and the evidence for an angle.
That is the audit trail for a generated record.

## What phase 7 adds

Cadence and push state, all additive, all on the record:

```jsonc
"cadence": {
  "ivana-saric": {
    "day1": {"channel": "email", "generated": true, "subject": "...", "body": "...",
             "status": "pushed",              // pending | eligible | paused |
                                              // waiting | blocked | pushed
             "push_id": "meridian:ivana-saric:day1:email",
             "pushed_at": "2026-08-26T09:00:00+00:00"}
  }
},
"events": [{"type": "email_reply", "contact": "ivana-saric", "at": "..."}],
"paused": {"since": "...", "reason": "email_reply", "by": "ivana-saric"}
```

- `events` is append only: `email_reply`, `linkedin_reply`, `connection_accepted`.
- `paused` is derived from the first reply on either channel and applies to the
  whole company, both channels, every contact. A step is never deleted when a
  company pauses: it keeps its place in the timeline with status `paused`.
- `push_id` is `record:contact:day:channel`. It is the idempotency key: a step
  that carries one has been sent and is never offered again, so a retry after a
  crash cannot double send.
- Template steps carry `template` and are expanded at read time. The expansion
  is what gets linted, so a template variable cannot smuggle a violation past
  the gate.

## What phase 8 adds

One field, so a batch can resume:

```jsonc
"stages": {
  "enrich":   {"status": "done",    "at": "...", "note": ""},
  "personas": {"status": "done",    "at": "...", "note": ""},
  "generate": {"status": "partial", "at": "...", "note": "1 step still outstanding"},
  "render":   {"status": "planned", "at": "...", "note": ""}
}
```

Statuses: `done`, `partial`, `planned` (a dry run), `skipped`, `failed`. A stage
marked `done` is not repeated, which is what makes a crash at record 40 of 500
restart at 40 rather than at 1. A `failed` stage carries the reason on the
record that caused it, and never stops the rest of the batch.

The queue file remains the only state. There is no second state file: enrichment
completion, model completion, persona completion, cadence readiness, lint
readiness, push readiness, pushed-step identity and pause state are all on the
record, and a test asserts nothing else is written into `work/`.

## What pre-production adds

**Approval.** A step is not push eligible because it is lint clean. It is push
eligible because a person approved these exact words:

```jsonc
"cadence": {"ivana-saric": {"day1": {
  "subject": "...", "body": "...",
  "approval": {"by": "operator", "at": "...", "fingerprint": "9f2c1a…"}}}}
```

The fingerprint is a hash of the channel, subject, body and note. Edit any of
them and `approval.is_approved` returns false, so the step drops back to
`unapproved` and out of every payload. Template steps are expanded on read, so
a change to the template, the angle or the evidence invalidates the approval
too. Approval is refused outright for a record that is dropped, pushed, held or
paused, for a recipient that is not sendable, and for a step that fails lint.

**Batch.** Ingest stamps every record with the batch it arrived in, so
reporting can group by it:

```jsonc
"batch": {"id": "batch.csv-2026-08-26T09:00:00", "source": "batch.csv",
          "at": "...", "client": "productive", "lane": "domains"}
```

**Events.** One append-only stream per record, in the stable vocabulary in
`src/events.py`: `batch_ingested`, `record_suppressed`, `record_dropped`,
`enrichment_started`, `enrichment_completed`, `contact_found`,
`verification_result`, `persona_selected`, `draft_generated`, `lint_failed`,
`draft_approved`, `cadence_prepared`, `push_prepared`, `push_marked`,
`email_delivered`, `email_bounced`, `reply_received`, `linkedin_connected`,
`company_paused`. An event carrying a `provider_event_id` is applied once, so a
replayed webhook changes state once. Reporting is derived from this stream
rather than from counters kept by hand.

**Locking.** `work/queue.jsonl.lock` is held for the duration of any write, and
for the whole read-change-write of `store.transaction()`. A second process
waits, then fails cleanly with `QueueLocked` having written nothing. A lock
left by a killed process is reclaimed after five minutes.

## What the provider waterfall adds

**Verification.** One block per contact, written only by `src/verification.py`:

```jsonc
"contacts": [{
  "email": "someone@example.test",
  "email_source": "provider",         // where it was FOUND, never why it may be used
  "verdict": "accept_all",            // a projection of the evidence below
  "reoon": {...},                     // the same, kept readable
  "sendable": false,
  "verification": {
    "state": "accept_all_uncleared",  // verified | invalid | accept_all_uncleared
                                      // | unknown | held
    "sendable": false,
    "reason": "catch-all with nothing that clears it",
    "cost": 2,
    "providers": ["contactout", "deliverable"],
    "evidence": [{"provider": "contactout", "status": "accept_all",
                  "catch_all": true, "disposable": false, "safe_to_send": null,
                  "score": null, "reason": null, "at": "..."}]
  }
}]
```

`verdict` and `reoon` are kept for anything that already reads them, but they
are a projection: once a `verification` block exists it is the only thing
`is_sendable` looks at, so editing a legacy field cannot flip a decision.

**The ledger.** One row per paid call, appended by `enrich.spend()` — the one
closure every provider call passes through, so a call that reached a provider
without a row here would not have been charged either:

```jsonc
"waterfall": [{
  "stage": "people_discovery",       // one of the seven declared stages
  "provider": "contactout",
  "call": "decision-makers",
  "cost_unit": "credits",
  "reason": "contactout_no_people",  // required for a fallback, refused if absent
  "expected_cost": 10,
  "actual_cost": null,               // null unless a provider actually said
  "result": null, "next_reason": null,
  "at": "..."
}]
```

`actual_cost` stays `null` rather than copying the estimate. No provider in
this stack reports per-call spend, and a guess in that field would make the
whole ledger worthless. `waterfall.audit(rec)` reads these rows and names any
step taken without a reason the stage accepts — which only means anything
because the rows are written by the code that spends rather than by a test.

**Research.** Public-web evidence, attributed and bounded:

```jsonc
"research": [{
  "source_type": "apify", "provider": "apify",
  "source_url": "https://example.test/careers",
  "actor": "apify~website-content-crawler",
  "retrieved_at": "...", "field": "careers",
  "title": "Careers", "fact": "trimmed plain text, never HTML",
  "record_id": "..."
}]
```

Raw datasets never reach the queue. A prompt sees at most three entries, each
trimmed, each with its source URL, inside the untrusted fence.

## What company qualification adds

Written by `src/qualify.py` before any person is looked up. Spends nothing, and
is skipped on a re-run when `inputs_fingerprint` has not moved — which is what
makes a 5,000-company batch resumable at company 2,731.

```jsonc
"qualification": {
  "inputs_fingerprint": "9f2c...",   // the facts the verdict was derived from
  "at": "2026-08-27T09:00:00Z",
  "verdict": {
    "icp_score": 78.5, "icp_raw_score": 78.5,
    "icp_status": "qualified",       // qualified | review | rejected | unknown
    "icp_tier": "A",                 // A | B | C | REVIEW | NOT_ICP
    "icp_confidence": "high",        // high | medium | low
    "scoring_version": "2026-08-27.1",
    "positive_signals": [{"dimension": "agency_fit", "weight": 20,
                          "why": "...", "matched": [...]}],
    "negative_signals": [...],       // same shape, negative weights
    "missing_evidence": ["employee count unknown"],
    "classification_reasons": [...],
    "confidence_components": {       // five fractions, each with its reason
      "coverage": {"score": 0.75, "why": "9 of 12 dimensions scored"},
      "source_diversity": {...}, "source_quality": {...},
      "recency": {...}, "consistency": {...},
      "contradictions": [{"kind": "size_vs_offices", "why": "..."}],
      "researched": false
    },
    "contradictions": [...],         // the same list, hoisted for readability
    "dimensions_scored": 9
  },
  "segment": {                       // vertical, geo, size, timezone
    "vertical": "digital_marketing", "subvertical": "...", "industry": "...",
    "business_model": "agency", "delivery_model": "mixed",
    "employee_band": "50_99", "company_maturity": "established",
    "country": "United Kingdom", "region": "UK", "city": "London",
    "timezone": "Europe/London", "timezone_source": "city",
    "timezone_confidence": "high", "office_count": 2, "distributed": true
  },
  "persona_plan": {
    "strategy": "operations_led",
    "persona_priority": ["operations", "finance", "resource_management"],
    "target_titles": ["COO", "Operations Director", "..."],
    "max_contacts_to_enrich": 3,     // the number that controls spend
    "cap_reason": "tier A allows up to 3 contact(s)"
  },
  "messaging": {...},                // structured angles, never copy
  "cost_plan": {...},                // expected / maximum / fallback exposure
  "segment_key": "PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS",
  "segment_rung": "full",            // which merge rung it ended on
  "segment_reason": "...",           // and why
  "dm_approved": false
}
```

`missing_evidence` is deliberately a list of gaps rather than an absence of
signals: a company with no employee count records that it has no employee
count, and its confidence drops. Missing information never scores as positive.

`segment_key` can only be written after the whole batch has been assigned — the
rung a company lands on depends on how many others share its key — so it is
filled in at the end of `qualify.run`, not by `company()`.

## What Phase 2 reads

`lint.py` and `render.py` are read-only. They compute sendability (section 6.1)
from `contacts[].verdict` and `contacts[].reoon` on every run rather than
trusting a stored flag, so `contacts[].sendable` stays unwritten until phase 4,
and a record whose only problem is an uncleared address shows amber in the
review sheet without its `state` changing to `held`. Phase 4 owns both writes.
