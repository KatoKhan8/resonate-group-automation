# Resonate Group Automation — build spec

Handoff document. Drop this in the repo root as `BUILD-SPEC.md`, point Claude
Code at it, and build in the phases at the bottom. Everything here was
validated on real data in a working prototype, including the parts that broke.

---

## 1. What the tool is

An outbound engine with three lanes that share one pipeline. The reasoning
steps run in an LLM; everything else is deterministic code. The state file is
the source of truth and the lint gate is the release valve.

| Lane | Input | Must produce before drafting |
|---|---|---|
| `revive` | dead or stalled account: CRM record plus the full email thread | a diagnosis: the date, the sentence, a failure mode |
| `cold` | a signal (job change, post, intent hit, a conversation) | a hook: one specific checkable fact |
| `domains` | a CSV of company domains for a client's ICP | a persona set per domain, with per-persona angle |

Non-negotiable invariant: **no email is generated for an address that has not
passed verification, and no draft reaches a push file until it passes lint.**

---

## 2. Repo layout

```
batches/                      inputs, one file or folder per batch
config/
  clients/<client>.yaml       personas, geos, angles, sender identity, cadence
  suppress.txt                domains never to be contacted
  .env                        provider keys, gitignored
work/queue.jsonl              state, one JSON object per record
out/
  review.html                 human review, exceptions in red
  emailbison.csv              lint-clean email sends
  heyreach.csv                LinkedIn profiles plus personalised note
  summary.json                counts, failure modes, lint failures, drops
  domains/<domain>/           domains lane per-account export
    company.json people.json people.csv cadence.json
src/
  ingest.py                   normalise, dedupe, suppress, slug
  store.py                    the only read/write path to queue.jsonl
  providers/
    contactout.py  aiark.py  reoon.py  bison.py  heyreach.py
  personas.py                 domains lane: search, classify, cap
  enrich.py                   orchestrate provider waterfall per record
  lint.py                     the gate
  render.py                   review.html, CSVs, summary.json
  cadence.py                  expand a persona into a dated multichannel sequence
prompts/
  diagnose.md  hook.md  draft.md  persona_angle.md
PLAYBOOK.md                   the contract the LLM works to
```

---

## 3. Data model

One JSON object per line in `work/queue.jsonl`. Never delete a line; dropped
records stay with a `drop_reason` so a batch is auditable and re-runnable.

```jsonc
{
  "id": "arbor-test",                  // slug, unique
  "lane": "domains",                  // revive | cold | domains
  "client": "productive",             // keys into config/clients/productive.yaml
  "company": "Arbor",
  "domain": "arbor.test",
  "context": "...",                   // revive: CRM dump + thread, verbatim
  "signal": "...",                    // cold: the trigger
  "state": "queued",                  // queued -> enriched -> verified -> drafted
                                      // -> approved -> pushed | dropped | held
  "drop_reason": null,
  "company_facts": {                  // domains lane, from provider
    "employees": 26, "revenue": "$3.6M", "founded": 2010,
    "offices": ["Zagreb HR", "..."], "specialties": ["SEO", "..."],
    "notable": "Deloitte fastest-growing list, EMEA",
    "icp_flags": ["geo outside client's stated markets"]
  },
  "contacts": [{
    "name": "Petra Horvat",
    "title": "Head of Finance And Administration",
    "linkedin": "https://...",
    "email": "petra.horvat@arbor.test",
    "email_source": "pattern_from_verified_colleague",  // provider | thread | pattern
    "persona": "champion",            // domains lane
    "angle": "finance",               // which messaging angle this person gets
    "verdict": "accept_all",          // valid | invalid | accept_all | unknown
    "reoon": {"is_deliverable": true, "is_safe_to_send": false, "overall_score": 75},
    "sendable": false,                // computed, see 6.1
    "primary": true
  }],
  "excluded": [{"name": "...", "title": "...", "why": "company name collision"}],
  "diagnosis": {                      // revive lane
    "died_on": "2024-10-17",
    "died_because": "asked to run a realistic list, reply pivoted to a call",
    "failure_mode": "unanswered_question",
    "last_position": "$5,000 for 50k work emails",
    "what_changed": "True Companies launched May 2026"
  },
  "hook": "...",                      // cold lane
  "sizing": {"query": "...", "profiles": 230222, "mobiles": 125588},
  "cadence": {                        // per contact id
    "petra-horvat": {
      "day1":  {"channel": "email", "subject": "...", "body": "...", "generated": true},
      "day3":  {"channel": "linkedin", "note": "...", "generated": true},
      "day5":  {"channel": "email", "template": "ops_pain", "vars": {"line": "..."}},
      "day15": {"channel": "email", "subject": "...", "body": "...", "generated": true},
      "day21": {"channel": "email", "template": "breakup"}
    }
  },
  "log": [{"step": "enrich", "at": "2026-08-16T20:31:00Z", "note": "..."}]
}
```

`failure_mode` is a closed enum: `unanswered_question`, `no_pass_mark`,
`minimum_not_price`, `ignored_preference`. Anything else is a bug in the
diagnosis step, not a new category. These four covered every account in a
29-account audit.

---

## 4. Client config

```yaml
# config/clients/productive.yaml
name: Productive
domain: productive.test
booking_link: https://productive.test/get-started/
sender:
  mode: client_rep          # engine writes no signature, sending inbox adds it
market:
  must: services business that tracks time
  size_min_employees: 20
  geos: [United Kingdom, Ireland, Netherlands, Germany, France, Nordics,
         Australia, United States]
  exclude_geos: [India, Pakistan, United Arab Emirates]
  flag_dont_drop: true      # out-of-geo gets flagged for human call, not dropped
personas:
  champion:
    titles: [Operations Manager, Operations Director, Project Manager,
             Finance Manager, Head of Finance, Head of Operations]
    cap_per_domain: 2
    angles:
      finance: margin per project, month end reconciliation, multi entity billing
      delivery: live budget burn, scope creep, resourcing visibility
      ops:     utilisation, capacity planning, one system not five
  economic_buyer:
    titles: [CFO, COO, CEO, Owner, Founder, Managing Director, Direktor]
    cap_per_domain: 1
    start_offset_days: 5    # buyer track starts behind champion track
    angles:
      founder: profitability visible on Monday not two weeks late
cadence: productive_default
tone:
  email: polished, professional, no em dashes, no buzzwords, no fluff openers
  linkedin: casual, lowercase, human
```

Caps matter economically. 2 champions plus 1 buyer per domain on a 500 domain
list is 1,500 search credits and up to 1,500 email credits. Without caps the
same list is 5,000 to 6,000.

---

## 5. Providers

Load keys from `config/.env`. Each provider module exposes narrow functions and
returns trimmed dicts, never raw payloads. This matters: raw provider responses
are enormous and if they reach an LLM context they dominate it.

### 5.1 ContactOut (primary)
Base `https://api.contactout.com/v1`, headers `authorization: basic` and
`token: <CONTACTOUT_TOKEN>`.

- `decision-makers?domain=` — roles held today plus work history. Costs 1 search
  credit per profile returned, 1 email credit per profile with contact info found
  when `reveal_info=true`
- `people-search` — the domains lane workhorse. Filter on `domain`,
  `current_company_only=true`, `seniority`, `job_title`, `location`. Always pass
  `output_fields` to trim the response
- `people-count` — **free**. Use it to confirm a company is real and staffed
  before spending a credit, and to size a prospect's own market for the email.
  Use `location`, not `current_work_location`; the latter returns absurdly low
  numbers
- `email-verifier` — `valid` | `invalid` | `accept_all` | `disposable` |
  `unknown`. 1 verifier credit on a definitive result
- `company-information-from-domain` — firmographics, offices, tech stack,
  and it catches rebrands

### 5.2 AI Ark (fallback)
Remote MCP at `https://api.ai-ark.com/v1/mcp?token=<AIARK_KEY>`. Run it only on
ContactOut misses. Quirks that cost time: `industry`, `location` and
`technology` are strict enums, so call the corresponding lookup tool first; and
a `keyword` search requires `keywordSources` (e.g.
`HEADLINE,SUMMARY,ORGANIZATION`) or it returns `400 sources is required`.
`email_finder` is async: it returns a `trackId`, then you poll
`email_finder_results`.

### 5.3 Reoon (deep verify)
`GET https://emailverifier.reoon.com/api/v1/verify?email=&key=<REOON_KEY>&mode=power`

Run only on `accept_all`. Returns `is_catch_all`, `is_deliverable`,
`is_safe_to_send`, `mx_records`, `overall_score`, `status`. Only
`is_safe_to_send: true` clears an address.

### 5.4 EmailBison
Base `https://send.resonategroup.co/api`, `Authorization: Bearer <BISON_KEY>`.
`POST /campaigns/{id}/leads` with `leads[]`. Put the generated subject and body
in `custom_variables` so the client's existing 5 to 7 step cadence continues
after step one.

### 5.5 HeyReach
`POST https://api.heyreach.io/api/public/campaign/AddLeadsToCampaignV2`,
header `X-API-KEY`. Body is `{campaignId, accountLeadPairs: [{linkedInAccountId,
lead: {profileUrl, firstName, lastName, companyName, position,
customUserFields: [{name, value}]}}]}`. `GET /auth/CheckApiKey` is the health check.

---

## 6. The gate

### 6.1 Sendability
```
sendable = verdict == "valid"
        or (verdict == "accept_all" and reoon.is_safe_to_send is True)
```
Everything else is `held`, not dropped. Held records keep their drafts and show
amber in the review sheet, because the fix is usually one Reoon run away.

### 6.2 Lint rules, all blocking
- recipient exists, is in that record's own contact list, and is `sendable`
- no em dash or en dash anywhere
- no attachment talk. Match `attachment`, `attached is/are/please/here/below`,
  `see|find|i've attached`, `attached file|screenshot|deck|pdf`, and
  `file|screenshot|deck|pdf|image attached`. Do not naively match `attach`,
  it false-positives on the idiom "with no pitch attached"
- no unfilled placeholder: `[...]`, `{...}`, `<...>`, excluding URLs
- body 40 to 180 words
- subject under 60 characters
- no hard-wrapped paragraphs. One unbroken line per paragraph, `\n\n` between.
  Gmail preserves hard breaks and they render as ragged short lines
- no filler openers. Maintain a banned-phrase list: "i hope this email finds
  you well", "i wanted to reach out", "circling back", "just following up",
  "touching base", "as per my last email", "synergy", "game-changer"
- `revive` record with no `diagnosis.died_because` fails
- `cold` record with no `hook` fails
- `domains` record with a contact that has no `angle` fails

Failures never block a batch. They land in `review.html` in red and stay out of
the push files. The human reads exceptions, not thirty emails.

---

## 7. Cadence

`cadence.py` expands one contact into a dated multichannel sequence from the
client config. Default 21 days, 6 email steps, LinkedIn in parallel.

| Day | Channel | Generated per person? |
|---|---|---|
| 1 | email | yes |
| 3 | LinkedIn connection request with note | yes, short |
| 5 | email, persona pain | no, template with one generated line |
| 8 | LinkedIn message if connection accepted | no |
| 10 | email, comparable proof | no |
| 15 | email, a different angle from day 1 | yes |
| 21 | email, clean exit | no |

Rules the expander enforces:
- never two channels on the same day for the same person
- the LinkedIn note never references the email and vice versa
- if the LinkedIn connection is accepted, day 10 switches to the short variant
- any reply on either channel pauses **both** tracks for the whole company, not
  just that person
- economic buyer track starts `start_offset_days` behind the champion track
- only 2 of 6 emails are LLM-generated. That is the difference between a
  workable and an unworkable cost per lead at 500 domains

---

## 8. Prompt contracts

Each file in `prompts/` takes a trimmed record and returns strict JSON,
validated against a schema before it touches the store. Retry on schema
failure, do not repair by hand.

- `diagnose.md` → `{died_on, died_because, failure_mode, last_position, what_changed}`.
  "Went cold" is a rejected answer. If the date cannot be found, return null
  and say so rather than inventing one
- `hook.md` → `{hook}`. Rejected if it would be true of fifty other companies
- `persona_angle.md` → `{angle, evidence[]}`. Every element of `evidence` must
  be traceable to `company_facts` or the contact record
- `draft.md` → `{subject, body}`. Given the client tone block, the angle, the
  evidence, and the lint rules as constraints. Four-part shape: name the
  specific thing, own the failure if it was ours, one concrete new piece of
  information, one question answerable in a single line. Never a calendar link
  as the ask

Hard rule for the drafting prompt: every specific claim must come from the
record. In the validated run, everything specific was data — five offices
across three countries with 26 people, on the Deloitte list, founder there
since 2010, one finance lead covering all five locations. None of it invented.

---

## 9. Traps found on real data

Build the guards, they all cost real time.

1. **Company-name collisions.** Searching "Arbor" returned an owner in Nice and
   a plant manager in Peru at unrelated companies of the same name. Always
   filter on domain plus location, and keep the rejects in `excluded` so a human
   can see what was thrown away
2. **Catch-all domains lie both ways.** ContactOut returned `accept_all` for an
   address it separately marked as verified in its own data. Never trust one
   verifier on a catch-all
3. **Real mail domain is not always the website domain.** One account's mail ran
   on a completely different domain from its marketing site. Check
   `company.email_domain`
4. **Rebrands kill whole contact sets.** One account's domain was parked and the
   company was trading under a new name with new founders. `decision-makers`
   returned zero, `company-information-from-domain` found it
5. **The contact who ran the trial has often left.** Verify role currency, not
   just the address
6. **Live customers get cold-sequenced.** The single most expensive mistake in
   this motion. `suppress.txt` is checked at ingest, before anything is spent
7. **Sizing filter footgun.** `current_work_location` returned 86 where
   `location` returned 230,222 for the same query
8. **Provider payloads flood context.** A single `decision-makers` call on an
   eight-person company returned enough JSON to matter. Trim in the provider
   module, never downstream

---

## 10. Build phases

Each phase ends with a runnable command and a test.

**Phase 1 — store and ingest.** `store.py`, `ingest.py`, the schema, and
`suppress.txt`. Test: a CSV with a suppressed domain, a duplicate and a missing
domain yields the right queue and the right skip reasons.

**Phase 2 — lint and render.** `lint.py`, `render.py`. Test: a deliberately bad
draft (em dash, `[FIRST NAME]`, "Screenshot attached", 12 words, filler opener)
trips exactly five rules and is absent from `emailbison.csv`, while the good
records still render.

**Phase 3 — providers.** Each module with a `--check` health call and a cassette
fixture so tests do not spend credits. Test: `check.py` reports all five green.

**Phase 4 — enrich waterfall.** ContactOut, AI Ark on misses, Reoon on
catch-alls, `sendable` computed. Test: a catch-all domain ends `held` with
drafts intact and nothing in the push file.

**Phase 5 — the LLM steps.** `prompts/` with schema validation and retry. Test:
a known revive thread produces the correct `died_on` and `failure_mode`; a
draft that breaks a lint rule is regenerated, not patched.

**Phase 6 — personas and the domains lane.** `personas.py` with caps, angle
assignment, per-domain folder export. Test: one domain in, capped persona set
out, collisions in `excluded`.

**Phase 7 — cadence and push.** `cadence.py`, `bison.py`, `heyreach.py`. Dry run
is the default and `--live` is explicit. Test: reply on one channel pauses both
tracks company-wide.

**Phase 8 — runner.** A `run` command that walks a batch through every phase,
resumable, so a crash at record 40 of 500 restarts at 40. State is already in
`queue.jsonl`, so this is bookkeeping rather than new design.

---

## 11. CLAUDE.md seed

```md
# Resonate Group Automation
Read BUILD-SPEC.md before changing anything. PLAYBOOK.md is the contract for
the LLM steps.

Rules
- work/queue.jsonl is the only state. Touch it through src/store.py, never directly.
- Provider modules return trimmed dicts, never raw payloads.
- No email is generated for an unverified address. No draft ships without passing lint.py.
- Never widen a lint rule to make a draft pass. Regenerate the draft.
- Dry run is the default for anything that sends. --live is always explicit.
- Never delete a queue record. Drop it with a reason.
- Costs are real: people-count is free, everything else burns credits. Cap before you fan out.
```
