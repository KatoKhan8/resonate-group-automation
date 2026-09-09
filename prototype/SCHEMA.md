# Record schema

One JSON object per line in `work/queue.jsonl`. Every script and every batch
session reads and writes this and nothing else. The file is the whole state.

```jsonc
{
  "id": "jobstream",                  // slug, unique, assigned by prep.py
  "lane": "revive",                  // "revive" = dead/stalled account | "cold" = net-new lead
  "client": "contactout",            // which Resonate client's campaign this belongs to
  "company": "JobStream",
  "domain": "jobstream.test",          // normalised, lowercase, no scheme/www
  "context": "...",                  // revive lane: raw CRM dump + full email thread, verbatim
  "signal": "...",                   // cold lane: the trigger (job change, hiring, post, intent hit)
  "sender": {                        // who the email comes from
    "name": "Operator Operator",
    "title": "Senior Manager",
    "company": "ContactOut",
    "email": "operator@contactout.test"
  },

  "state": "queued",                 // queued -> enriched -> verified -> drafted -> approved -> pushed
                                     // terminal: dropped
  "drop_reason": null,

  "contacts": [                      // filled at enrich, pruned at verify
    {
      "name": "...",
      "title": "...",
      "linkedin": "...",
      "email": "...",
      "source": "contactout|aiark|thread",
      "verdict": "valid|accept_all|invalid|unknown",
      "reoon": { "is_deliverable": true, "is_safe_to_send": true, "score": 92 },
      "primary": true
    }
  ],

  "diagnosis": {                     // revive lane only
    "died_on": "2026-02-18",
    "died_because": "asked where the search lookups were, never answered",
    "failure_mode": "unanswered_question",   // see PLAYBOOK for the four
    "last_position": "quoted $0.15/email, $5,000 minimum",
    "what_changed": "..."            // the honest reason to write today
  },

  "hook": "...",                     // cold lane: the one specific, checkable fact the email opens on
  "sizing": { "query": "...", "profiles": 230222, "mobiles": 125588 },

  "draft": {
    "to": "first.last@company.test",
    "subject": "...",
    "body": "...",                   // one unbroken line per paragraph, \n\n between
    "checks": { "no_em_dash": true, "no_attachment_ref": true, "under_180_words": true }
  },

  "log": [ { "step": "enrich", "at": "2026-08-16T20:31:00Z", "note": "..." } ]
}
```

## State rules

- A record only reaches `drafted` if it has at least one contact with
  `verdict` in {valid, accept_all-with-reoon-safe}. No verified address, no draft.
- `dropped` needs a `drop_reason` string. Never silently disappear a record.
- Nothing is ever deleted from `queue.jsonl`; dropped records stay in the file
  so the batch is auditable and re-runnable.
