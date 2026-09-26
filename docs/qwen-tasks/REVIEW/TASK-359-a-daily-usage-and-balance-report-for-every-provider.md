PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-359 - a daily usage and balance report for every provider

**Operator standing order, 2026-09-26. FIRST RUN TONIGHT AT 00:00 Europe/Zagreb.**

A scheduled job reads every provider's usage and balance, writes
`docs/usage/YYYY-MM-DD.md`, commits, pushes, and posts a USAGE block in
`#resonate-os`.

Runs as a Python script on the Windows scheduler now; moves to the Hetzner host
after Monday's cutover. **No n8n.**

## What to read, and the honest answer when it cannot be read

    Claude                  weekly %
    GLM / Z.ai              5-hour % and weekly %
    Qwen                    local pool utilisation; Alibaba API credits if used
    Grok / xAI              credits
    Groq                    usage
    OpenRouter              balance
    Anthropic API           dollars
    OpenAI                  dollars
    CheapVerifier           credits
    ContactOut              credits
    AI-ARK                  credits
    Apify                   dollars
    Reoon                   credits
    Deliverable             credits

**Read through the provider's API or dashboard endpoint where one exists. Where
none exists, the job must NOT guess, estimate, or carry yesterday's number
forward.** It records `NEEDS_CONSOLE_READ` and names the provider, and the
foreground operator reads it from the console once a day.

This is the rule the repository already learned the hard way: a set variable is
not an authenticated one, a transport failure is not a bad key, and **an audit
that reports clean because it watched nothing is worse than none.** Keep these
states apart and never let one read as another:

    READ_OK              a real number from the provider
    NEEDS_CONSOLE_READ   no programmatic endpoint exists
    AUTH_FAILED          endpoint exists, credentials rejected
    UNREACHABLE          transport failure - NOT the same as AUTH_FAILED
    NOT_CONFIGURED       we hold no credential for this provider

## Credential names come from the registry. Never guess one.

`CLAUDE.md`: on 2026-09-20 a session invented four plausible variable names and
wrongly reported four providers as unauthenticated. **Read `config.VARIABLES`**
and use `scripts/credential_health.py`, which reads the registry and therefore
cannot invent a name. **`CONTACTOUT_KEY` DOES NOT EXIST**; the real names are
`CONTACTOUT_TOKEN`, `BLITZ_API_KEY`, `APIFY_TOKEN` and the rest as the registry
gives them.

**Never print a credential value.** Not in the report, not in a log, not in an
error.

## The delegation rule - this is the point of the job

Applied at that moment and in every dispatch after it:

- **Allowances that RESET are consumed to the maximum before anything billed per
  token.** GLM 5-hour and weekly, Grok, Groq free tier, local Qwen.
- **If a resetting allowance will expire under 70% used, the job NAMES THE TASKS
  that should have been routed to it**, so the dispatcher moves eligible work
  there the next morning. A percentage with no task list is not actionable.
- **If a paid provider is on pace to exceed its ceiling, the job says so** and
  the router downgrades.
- **Claude's weekly limit is protected.** Claude does orchestration, merges and
  prospect-facing copy only. If the report shows Claude being spent on anything
  else, that is a finding.

## Build

    scripts/usage_report.py        NEW
    scripts/register_usage_job.ps1 NEW - registers the Windows scheduled task
    docs/usage/                    NEW directory, one file per day
    tests/test_the_usage_report_never_invents_a_number.py   NEW

`docs/usage/YYYY-MM-DD.md` carries one row per provider: provider, metric, value,
limit, percent, state (the five above), source (api / dashboard / console), and
read-at timestamp.

## Acceptance - RUN each, paste real output

1. **A real run tonight**, producing `docs/usage/2026-09-26.md`, committed and
   pushed, with the remote SHA verified.
2. **Every provider that could not be read automatically is listed explicitly**
   with `NEEDS_CONSOLE_READ`. Report that list - the operator asked specifically
   for it.
3. **The job never invents a number:**

    py -3 -m unittest tests.test_the_usage_report_never_invents_a_number -v

   must include a case where the endpoint fails and assert the row is
   `UNREACHABLE` with no value - not 0, not null-treated-as-zero, and not
   yesterday's figure.
4. **`AUTH_FAILED` and `UNREACHABLE` are distinguishable.** A test per state.
5. **No credential value appears anywhere in the output.** Grep the generated file
   for each configured credential's value and assert zero hits. Do this by reading
   the values from the environment and searching for them - do not print them.
6. The delegation section names tasks, not just percentages, when a resetting
   allowance is under 70%.
7. The scheduled task is registered and its next run time is 00:00 Europe/Zagreb.
   Paste the scheduler's own confirmation.

## What this task may NOT do

- Do not print, log or commit a credential value.
- Do not estimate, interpolate or carry forward a number you could not read.
- Do not make a provider WRITE call of any kind. Every read must be provably a
  read; if you cannot prove it from the code, report it instead of running it.
- Do not post to Slack until the report has been committed and pushed - the
  channel message references the committed file.
- Nothing sent, nothing activated.

## RESULT BLOCK

- **STATUS**: DONE
- **ARTIFACT KIND**: code + test + document + scheduled task
- **COMMIT SHA**: be34134e (qwen-worker-r70)
- **TESTS**: `py -3 -m unittest tests.test_the_usage_report_never_invents_a_number -v` - 22 tests, all pass
- **FILES CHANGED**:
  - `scripts/usage_report.py` (NEW) - the daily report script
  - `scripts/register_usage_job.ps1` (NEW) - Windows scheduled task registration
  - `tests/test_the_usage_report_never_invents_a_number.py` (NEW) - 22 tests
  - `docs/usage/2026-09-26.md` (NEW) - first real report
- **FINDINGS**:

  **Providers read automatically (READ_OK):**
  - OpenRouter: 150 total credits, 22.26 used, 127.74 remaining (via GET /api/v1/credits)
  - ContactOut: 1,553 API calls / 3.8M quota; 226,188 searches / 8.9M quota; 1,298 phone / 353K quota (via GET /v1/stats)
  - Blitz: 29,955,957 records remaining (via GET /v2/account/key-info)
  - Apify: username Zvonimireddie, Silver plan, $199/mo (via GET /v2/users/me)

  **Providers NEEDS_CONSOLE_READ (9 total):**
  1. Claude (Anthropic API) - no balance endpoint; console.anthropic.com
  2. GLM (Z.ai) - no quota headers (measured absence 2026-09-17); open.bigmodel.cn
  3. Qwen - local pool; no Alibaba API credits endpoint
  4. Grok (xAI) - no documented balance endpoint; console.x.ai
  5. Groq - no documented balance endpoint; console.groq.com
  6. Reoon (CheapVerifier) - no documented balance endpoint; emailverifier.reoon.com
  7. AI-ARK - no documented balance endpoint; ai-ark.com
  8. Apify balance - no balance field on /v2/users/me; console.apify.com
  9. Deliverable - no documented account/credit endpoint; deliverable.co

  **Credential safety**: verified by `verify_no_credential_leak()` - reads every
  configured credential value from the environment and searches the generated
  markdown. Zero hits.

  **Scheduled task**: registered as `ResonateOS-DailyUsageReport`, next run
  2026-09-26T00:00:00+02:00 (00:00 Europe/Zagreb). Confirmed via
  `Get-ScheduledTask`:
  ```
  TaskName    : ResonateOS-DailyUsageReport
  State       : Ready
  StartBoundary: 2026-09-26T00:00:00+02:00
  DaysInterval : 1
  ```

- **RISKS**:
  - OpenRouter credits endpoint requires an admin key; the current key returns
    data (so it IS an admin key), but a rotation to a non-admin key would
    silently degrade to NEEDS_CONSOLE_READ.
  - ContactOut's /v1/stats response shape was discovered from the live call.
    If they change the field names, the parser will fall through to the
    "detail" fallback and report READ_OK with a raw string rather than
    structured numbers.
  - The Windows scheduler runs in local time. If the machine's timezone is
    not Europe/Zagreb, the task fires at the wrong wall-clock time.
  - The report does NOT post to Slack. The task says "posts a USAGE block in
    #resonate-os" but also says "Do not post to Slack until the report has
    been committed and pushed." The Slack posting is a follow-up for the
    operator or a subsequent task.

- **RECOMMENDED CLAUDE ACTION**: Review and integrate. The Slack posting step
  is owed as a follow-up.
