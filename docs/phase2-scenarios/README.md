# Phase-2 scenario files — the shape, and how to author one

Read this and `CATALOGUE.md` and you have everything you need to produce
`S01.yaml` … `S30.yaml` in this directory. One file per catalogue row, named by
its `id`. **Do not invent scenarios that are not in the catalogue, and do not
change a row's `expected` to match what you observe — a disagreement between
the catalogue and the code is the finding the catalogue exists to produce.**

---

## 1. The parser you are writing for

These files are read by **`src/clients.py` → `clients.parse`**, the project's
own YAML subset. **Not PyYAML.** The repository has no third-party
dependencies, and a folded scalar (`>-`) once broke `offers.load()` for the
whole library here.

`clients.parse` accepts nested maps by indentation, scalars, inline lists in
square brackets, comments, ints and booleans. Everything else either raises or
— worse — is silently misread. The four cases below were measured against the
parser on 2026-10-03, not inferred from its docstring:

| you write | what happens |
|---|---|
| `covers:` then `  - a` | **`ConfigError: block lists are not supported, use [a, b]`** |
| `intent: >-` then an indented line | **`ConfigError: cannot parse line: 'folded'`** — the `>-` becomes the value and the continuation line has no colon |
| a line with no `:` at all | **`ConfigError: cannot parse line: ...`** |
| `rate: 0.022` | **ACCEPTED AND WRONG.** `clients.scalar` promotes only integers (`text.isdigit()`), so this is the **string** `'0.022'`. |

So, as rules:

- **Inline lists only**: `covers: [lead_class, dnc]`. Never `- item`.
- **Every line carries a colon.** No continuation lines, no folded or literal
  block scalars, no multi-line strings. One line per key.
- **No floats anywhere.** Use an integer, or a word. If a scenario needs a
  proportion, express it as an integer count (`sends: 1`) or a label
  (`research_band: weak`). The parser will not tell you it mangled a float.
- Integers and `true` / `false` / `yes` / `no` / `null` / `~` are converted.
  Everything else is a string.
- A value may contain a colon: `partition(":")` splits on the **first** one, so
  `linkedin: https://www.linkedin.com/in/x` parses correctly and so does a
  `text:` containing a colon.
- A `#` preceded by a space starts a comment. Avoid `#` inside any value.
- Indent with **two spaces per level**. Tabs are not indentation here.

Verify every file you write before handing it in:

    py -3 -c "from src import clients, json; \
      print(clients.parse(open('docs/phase2-scenarios/S01.yaml').read()))"

A file that raises `ConfigError` is not a scenario, and a file whose numbers
came back as strings is worse than one that raised.

---

## 2. The three blocks

Exactly three top-level blocks — `setup`, `event`, `expected` — plus four
scalar keys that identify the row. Nothing else at the top level.

### Identity (four scalars, all required)

```yaml
id: S01
intent: A removal request blocks the lead forever and stops both channels
rule: CLAUDE.md rule 2 step 1 - BLOCKED FOREVER
covers: [lead_class, reply_class, dnc, cross_channel_stop]
```

- `id` — the catalogue row id, and the filename.
- `intent` — the catalogue's one-line intent, copied verbatim. One line.
- `rule` — the authority this row tests, copied from the catalogue.
- `covers` — tags from the catalogue's `covers` column, as an inline list.

### `setup` — the world before the event

```yaml
setup:
  record:
    id: s01-acme
    company: Acme Services S01
    domain: s01-acme.invalid
    client: demo
    state: enriched
    synthetic: true
  contact:
    key: s01-champ
    persona: champion
    email: champ@s01-acme.invalid
    linkedin: https://www.linkedin.com/in/s01-champ
    verified: true
  history:
    os_campaign: 491
    sends: 1
    last_touch_day: 3
```

**`record.domain` MUST end in `.invalid` and `record.synthetic` MUST be
`true`, in every file, with no exception.** Note that `synthetic: true`
protects nothing on its own — 0 of 15 pool queries exclude on it — so the
safety is the store copy and the host seal, not this flag. It is here so a row
that escapes is identifiable, not so it is safe.

Keys the catalogue may ask for under `setup`:

- `record`: `id`, `company`, `domain`, `client`, `state`, `synthetic`, and
  optionally `drop_reason`, `headcount_sources` (inline list of ints),
  `vertical`, `cohort`.
- `contact`: `key`, `persona` (`champion` or `economic_buyer` — the only two
  measured in the real store), `email`, `linkedin`, `verified`, and optionally
  `unsubscribed`, `bounced`, `stopped_reason`.
- `history`: `os_campaign` (an integer campaign id, or `none`),
  `non_os_campaign`, `sends`, `last_touch_day`, `last_manual_touch_day`,
  `prior_reply_class`.
- `research`: `band` — one of `unusable`, `weak`, `medium`, `strong`. **The
  band is DERIVED and not injectable**: `usable()` recomputes it through
  `recheck()` (`<0.35 unusable / 0.35-0.649 weak / >=0.65 medium / >=0.75
  strong`), so the harness has to make the scorer produce the band rather than
  write it onto the row. Name the band you need; do not write a score.
- `campaign`: `id`, `status` (`active`, `paused`, `sending_paused`,
  `completed`, `archived`, `draft`), `owner` (`resonate_os`,
  `resonate_internal`, `unknown`).

`last_touch_day` and friends are **day offsets inside the 90-day simulation**,
not dates. Day 0 is the first simulated day. A negative offset means before
the simulation started.

### `event` — the one thing that happens

```yaml
event:
  on_day: 5
  kind: reply
  channel: email
  provider: emailbison
  text: please remove me from your list. do not contact me again
  automated: false
```

- `on_day` — an integer in `0..90`.
- `kind` — one of `reply`, `bounce`, `unsubscribe`, `connection_accepted`,
  `send_attempt`, `clock_advance`, `none`.
- `channel` — `email` or `linkedin`.
- `provider` — `emailbison` or `heyreach`.
- `text` — for `kind: reply`, the body, **on one line**. Invent it. No real
  wording from a real reply, ever.
- `automated` — the provider's `automated_reply` flag, `true` or `false`. It is
  the provider's flag and NOT our classification; keep them apart.
- `return_day` — for an out-of-office, the day offset they say they are back.
- `kind: none` is legal and means "nothing happens; assert the state as set
  up". Use it for the rows that test classification alone.

A reply event is fed through **`inbound.ingest` in the provider's own shape**,
never written into the store by hand — a hand-built row lets a wrong shape in
through the fixture. The harness builds the provider payload from these keys;
your job is the keys.

### `expected` — one line per authority, named by the authority

**Never a single invented verdict.** Each key names the module and function
whose answer is being asserted, so a row that fails says which authority
disagreed. Use only the keys below, and only the ones the catalogue row lists.

| key | the authority | legal values |
|---|---|---|
| `replies_classify` | `replies.classify(...)["classification"]` | one of the 17 in `replies.CATEGORIES` |
| `replies_confidence_at_least` | same call, `["confidence"]` | an integer percent, e.g. `75` for 0.75 — **not a float** |
| `accountpolicy_outcome` | `accountpolicy.classify_outcome` | one of the 12 in `accountpolicy.OUTCOMES` |
| `channels_email_allowed` | `channels.email_verdict(...)[0]` | `true` / `false` |
| `channels_email_reason` | `channels.email_verdict(...)[1]` | `unsubscribed`, `bounced`, `suppressed`, `operator_excluded`, `no_address`, `not_verified`, `mx_security_provider`, `none` |
| `channels_linkedin_allowed` | `channels.linkedin_verdict(...)[0]` | `true` / `false` |
| `channels_linkedin_reason` | `channels.linkedin_verdict(...)[1]` | `no_profile`, `profile_unusable`, `identity_uncertain`, plus the shared ones above |
| `eligibility_verdict` | `eligibility.decide(...)` | `eligible`, `held`, `blocked`, `skipped` |
| `eligibility_reason` | same | a `blocked:*` or `held:*` constant from `src/eligibility.py`, spelled exactly |
| `collision_decision` | `collision.account_policy(...)` | `allow`, `hold`, `stop`, `unknown` |
| `hygiene_verdict` | `hygiene.check(...)["verdict"]` | one of the 12 in `hygiene.VERDICTS` |
| `hygiene_action` | same, `["action"]` | one of the 6 in `hygiene.ACTIONS` - `suppress`, `exclude`, `hold`, `route`, `review`, `eligible` |
| `oooreturn_verdict` | `oooreturn.assess(...)["verdict"]` | `due`, `not_yet`, `never`, `needs_a_person` |
| `oooreturn_why` | same, `["why"]` | a constant from `src/oooreturn.py`, e.g. `NOT_DUE`, `BACK`, `REFUSED` |
| `headroom_verdict` | `senderheadroom.verdict(...)[0]` | `FULL`, `ROOM`, `REFUSED` |
| `cross_channel_stop` | both channels refuse after the event | `true` / `false` |
| `rule2_step` | the **label** from CLAUDE.md rule 2 | `BLOCKED_FOREVER`, `ON_HOLD`, `STARI_LEAD`, `COLD_LEAD`, `UNKNOWN` |
| `provider_writes` | provider write attempts the scenario must produce | always `0` |

**`rule2_step` IS A LABEL AND NOT A CODE VERDICT, and this matters.** Measured
on `e967271d`: `grep -rn "BLOCKED_FOREVER\|ON_HOLD\|COLD_LEAD" src/` and
`grep -rni "stari" src/` each return **zero hits**. The five ordered steps of
rule 2 exist in CLAUDE.md and in no module. What exists is four partial
authorities that nothing composes — `hygiene.check` (local history, 12
verdicts), `collision.account_policy` (provider truth, 3 verdicts),
`eligibility.must_not_contact` (person-level blocks) and `reengagement.classify`
(5 lanes under different names, and with **no production caller**). Rule 2's
load-bearing split — *did RESONATE OS contact them, judged by provider truth* —
is implemented nowhere.

So every row carries `rule2_step` as the answer rule 2 **requires**, beside the
`expected` keys for the authorities that actually answer today. Where the two
cannot agree, the row also carries:

```yaml
  rule2_step_unimplemented: true
```

That is not an excuse for the row. It is the row's output.

`provider_writes: 0` is on every file. Phase 2 performs no provider write of
any kind, and a scenario that would require one is a scenario that must be
reported rather than run.

---

## 3. The whole of S01, as a worked example

Copy this shape exactly. It has been parsed by `clients.parse` and every value
came back as the intended type.

```yaml
id: S01
intent: A removal request blocks the lead forever and stops both channels
rule: CLAUDE.md rule 2 step 1 - BLOCKED FOREVER
covers: [lead_class, reply_class, dnc, cross_channel_stop]

setup:
  record:
    id: s01-acme
    company: Acme Services S01
    domain: s01-acme.invalid
    client: demo
    state: enriched
    synthetic: true
  contact:
    key: s01-champ
    persona: champion
    email: champ@s01-acme.invalid
    linkedin: https://www.linkedin.com/in/s01-champ
    verified: true
  history:
    os_campaign: 491
    sends: 1
    last_touch_day: 3

event:
  on_day: 5
  kind: reply
  channel: email
  provider: emailbison
  text: please remove me from your list. do not contact me again
  automated: false

expected:
  replies_classify: unsubscribe
  accountpolicy_outcome: unsubscribe
  channels_email_allowed: false
  channels_email_reason: unsubscribed
  channels_linkedin_allowed: false
  cross_channel_stop: true
  eligibility_verdict: blocked
  eligibility_reason: blocked:unsubscribed
  rule2_step: BLOCKED_FOREVER
  provider_writes: 0
```

---

## 4. Four things that will cost you time if you rediscover them

Each was measured, and each is on the path these scenarios walk.

1. **The clock is injected, so do not write dates.** `store.clock_driven_by`
   drives `store.now()` and `store.utcnow()`; every offset in a scenario is a
   day number and the harness turns it into a date. A scenario carrying a
   literal date would be asserting something about the day it was authored.
   See `tests/test_simclock.py`.
2. **`senderheadroom`'s census goes stale after 24 hours and its freshness
   gate is LAST**, so any row expecting `headroom_verdict: ROOM` needs the
   forward book re-walked on the simulated day. A stale walk can still prove
   `FULL` — that asymmetry is the module's safety contract, not a bug — so
   `FULL` rows are cheap and `ROOM` rows are not.
3. **A pure out-of-office stops the contact exactly as a refusal does.**
   `accountpolicy.CLASSIFIER_OUTCOME` maps `out_of_office` to `not_now`, whose
   plan is `replier=stop`, and nothing lifts it. `oooreturn` reports that
   somebody is due back; it does **not** clear the stop, and a row expecting a
   cleared stop is expecting something this system is not allowed to do
   automatically.
4. **The only blocking signal is a reply** (operator's rule, 2026-10-02).
   Membership in a non-OS campaign, a paused campaign or a HeyReach list blocks
   nothing — several rows test exactly that. The 40 OS campaigns are declared
   in `config/resonate-os-campaigns.txt` on `task-eligibility-reply-only`;
   274/327/328/352 are **internal, never OS, and never written to**.

---

## 5. What a finished scenario file is not

- Not a test. It carries no assertions of its own and imports nothing.
- Not a fixture with a verdict written beside the text. `expected` is what the
  **real** classifier and the **real** gates must answer; the harness calls
  them. A row whose expected verdict was copied from an observed run proves
  only that the run was repeated.
- Not permission to weaken anything. If the only way to make a row pass is to
  loosen a gate, a lint rule or an assertion, **stop and report both sides**.
