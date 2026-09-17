# Webhook Ingest — normalise a Bison event, once, and never twice

2026-09-17. Pure module, no server, no endpoint, no provider call.

## What was built

`src/bisonevents.py` — two public functions:

- **`normalise(payload)`** — takes one decoded webhook payload (a `dict`),
  returns a trimmed event dict with: `provider_event_type`,
  `provider_event_id`, `workspace_id`, `campaign_id`, `lead_id`, `email`,
  `occurred_at`, `kind`, `raw_keys`.
- **`event_key(event)`** — the idempotency key. Prefers the provider's own
  event id; falls back to a derived composite of
  `(kind, workspace_id, campaign_id, lead_id, occurred_at)`.

Two exceptions:
- `TenancyRefused` — payload workspace_id does not match the pin.
- `MalformedPayload` — required field missing.

## Falsifiable targets — all green

| Target | Test | Result |
|--------|------|--------|
| Two identical payloads → one event_key | `test_two_identical_payloads_produce_one_key` | PASS |
| Two different events → different keys | `test_two_different_events_never_share_a_key` | PASS |
| Same lead, same type, different time → different keys | `test_same_lead_same_type_different_time_are_different_events` | PASS |
| Unknown type → kind "unknown" | `test_unknown_type_maps_to_unknown` | PASS |
| TAG_ATTACHED not mapped to a known kind | `test_tag_attached_is_not_mapped_to_replied` | PASS |
| Wrong workspace_id → raises | `test_payload_for_another_workspace_raises` | PASS |
| Unpinned workspace → refuses everything | `test_unpinned_workspace_refuses_everything` | PASS |
| Missing data → raises | `test_missing_data_raises` | PASS |
| Missing event.type → raises | `test_missing_event_type_raises` | PASS |
| Missing workspace_id → raises | `test_missing_workspace_id_raises` | PASS |
| Late sent orders before earlier replied | `test_late_sent_carries_an_earlier_timestamp_than_the_reply` | PASS |
| occurred_at always present | `test_occurred_at_is_always_present` | PASS |
| All required fields present | `test_required_fields_are_present` | PASS |
| Kind from allowlist for all six known types | `test_kind_is_from_allowlist` | PASS |
| raw_keys carries provider field names | `test_raw_keys_carries_the_provider_field_names` | PASS |
| Correct workspace accepted | `test_payload_for_our_workspace_is_accepted` | PASS |

16 tests, all pass. Fixture hygiene: 13/13 green. Pre-existing
`test_invariants` failure (`test_emailbison_posts_only_to_routes_it_declares`)
confirmed on clean tree — not caused by this change.

## What is NOT consumed yet

`grep -rn bisonevents src/` returns nothing outside the module itself.
This is by design: the brief says wiring to a real endpoint is Claude's,
after GLM has reviewed it. The module is pure and has no caller.

## Agreement with actionledger.settle

The dedupe semantics agree with `actionledger.settle`'s same-state rule:

- **Identical redelivery** → same `event_key` → consumer treats as no-op.
- **Redelivery with new fields** → same `event_key` but different
  `raw_keys` → consumer can detect the new evidence.

The normaliser does not implement the same-state-with-new-evidence logic
itself; it carries `raw_keys` so the consumer can. This matches the
settlement pattern: identical replay is a no-op, a replay carrying new
information is not silently dropped.

## ASSUMED payload fields — Claude must check against a real webhook

| Field | Status | Notes |
|-------|--------|-------|
| `event.type` | ASSUMED | UPPER_SNAKE values: EMAIL_SENT, EMAIL_OPENED, CONTACT_REPLIED, EMAIL_BOUNCED, CONTACT_UNSUBSCRIBED, CONTACT_INTERESTED, TAG_ATTACHED, TAG_REMOVED, UNTRACKED_REPLY_RECEIVED. The docs use English names ("Email Sent"); the example uses UPPER_SNAKE. Both handled by normalising, but real values must be confirmed. |
| `event.id` | ASSUMED | Present in every payload. OpenAPI spec shows `id` on webhook event objects but the research doc does not reproduce a full payload. If absent, event_key falls back to a derived composite. |
| `event.workspace_id` | ASSUMED | Integer. The poller reads this from reply payloads; webhooks expected at same path. |
| `data.lead_id` | ASSUMED | Integer. Every event-specific data shape expected to carry this. |
| `data.campaign_id` | ASSUMED | Integer. Same assumption as lead_id. |
| `data.email` | ASSUMED | String. The contact's email address. |
| `data.occurred_at` | ASSUMED | ISO-8601 string with timezone. The poller already reads `occurred_at`/`createdAt` from reply payloads. |
| `data.message_id` | ASSUMED | Present on EMAIL_SENT, EMAIL_OPENED, CONTACT_REPLIED, EMAIL_BOUNCED. Absent on TAG_ATTACHED, CONTACT_INTERESTED. Not used in normalise; noted for the consumer. |

## RESULT BLOCK

- **STATUS:** DONE
- **COMMIT SHA:** 82016ff3
- **TESTS:** 16/16 pass in `tests/test_a_webhook_delivered_twice.py`. 13/13 fixture hygiene green. Pre-existing `test_invariants` failure confirmed unrelated.
- **FILES CHANGED:**
  - `src/bisonevents.py` (new — the only src file)
  - `tests/test_a_webhook_delivered_twice.py` (new)
  - `docs/WEBHOOK-INGEST-2026-09-17.md` (new — this file)
- **FINDINGS:**
  - The module is pure and has no caller in `src/`. Wiring to a real HTTP endpoint is owed.
  - The TYPE_TO_KIND mapping uses UPPER_SNAKE event type names. If the real webhook uses different casing or format, the normalisation (`strip().upper().replace(" ", "_")`) should handle it, but this must be confirmed against a real payload.
  - The event_key fallback (when event.id is absent) uses `(kind, workspace_id, campaign_id, lead_id, occurred_at)`. This is sufficient for the documented retry semantics but has not been tested against a real payload without an id.
- **RISKS:**
  - The ASSUMED payload fields have not been verified against a real webhook. Every one is marked in the module docstring and the table above.
  - The tenancy check reads `BISON_WORKSPACE_ID` from `os.environ`. If the webhook endpoint loads `config/.env` before calling `normalise`, the pin will be available. If not, every payload is refused. The consumer must ensure the env is loaded.
- **RECOMMENDED CLAUDE ACTION:**
  1. Check every ASSUMED field against a real webhook payload (use `POST /api/webhook-events/test-event` to generate one).
  2. Wire the module to a real HTTP endpoint with signature verification.
  3. Build the consumer that applies same-state-with-new-evidence logic (agreeing with `actionledger.settle`).
  4. Reconcile against `/api/events` (last 10 days) to catch anything missed during the gap.
