# TASK-1003 — import the Farseer campaigns from the workspace this repo does not configure

Opened 2026-10-03. **BLOCKED ON ACCESS, which the operator grants on
2026-10-04.** Nothing in this task may be started by guessing at a credential
or a workspace id.

## Why it exists

The operator has named the Farseer cadence **the reference** for every copy
decision. Two lanes then established, by reading both providers exhaustively,
that **it is not reachable from this machine**:

| where it was looked for | result |
|---|---|
| EmailBison, all 40 campaigns, fully paginated | **no Farseer campaign.** Zero name matches |
| HeyReach, all 121 campaigns on org unit `118832` | **not on this seat.** One org unit is reachable with this key, and `config.VARIABLES` holds one HeyReach credential |
| `config/clients/` | only `productive`, `demo`, `contactout.example` |
| the whole repo | the client's own domain on `config/suppress.local.txt` — which is what a CLIENT of ours looks like in that file, and which is deliberately not spelled in a tracked file — and the name in `tests/test_fixture_hygiene.py:60` and `scripts/slack_question_catalogue.py:97` as an agency name |
| `work/` | the name in **11 Slack-history files**: conversation ABOUT the campaign, never the campaign |

It ran on **LinkedIn, voice, WhatsApp and the phone**, and its per-meeting
attribution went into a CRM this repository cannot read.

## What the import has to produce, and what it must not

**Must produce**, per the operator's own list:
- the whole cadence **per channel with the days**;
- the text of **every step**;
- the **order of channels per account**;
- **which step and which channel produced each positive reply**;
- how many touches preceded the first positive;
- the persona that replied.

**Must not** do any of these:
- **reconstruct a missing piece from a name, a memory or a plausible pattern.**
  Where the data does not hold one of the six, the import records WHAT IS
  MISSING AND WHERE IT SHOULD BE, which is what both lanes did today and is why
  this task is well specified at all;
- **write to the other workspace.** Reads only. Nothing created, paused,
  started, stopped or enrolled, there or here;
- **claim ownership.** Farseer's campaigns are not Resonate OS campaigns unless
  the ledger positively records them, and it does not. They enter as a
  **read-only learning asset**, the same class as the internal campaigns —
  their replies, angles, personas and verticals inform copy, and nothing goes
  back to a provider;
- **import recipients into `docs/`.** Our own texts are ours and stay in full;
  recipient names and companies are anonymised, and the real rows live in
  gitignored `work/`.

## Two prerequisites that are separate tasks

- **TASK-1001** — the channel model knows only `email` and `linkedin`, so the
  voice, WhatsApp and phone steps have nowhere to be recorded. Importing before
  that lands means dropping the channels that made the cadence what it was.
- **TASK-1002** — a meeting is not a first-class outcome, so "35 meetings" (or
  the **56 invoiced Feb–Jun 2026** that the email lane actually found) cannot be
  attached to the campaigns that produced them.

Doing this import first would produce a cadence with two of its four channels
and no outcome, which is worse than waiting: it would be the authoritative
record of the reference campaign, and it would be wrong in a way nobody could
see from inside it.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import clients, config; have=[v for v in config.VARIABLES if 'HEYREACH' in str(v).upper() or 'BISON' in str(v).upper()]; print('provider credentials the registry knows:', have); assert clients.exists('farseer') or any('FARSEER' in str(v).upper() for v in config.VARIABLES), 'no Farseer workspace is configured and no Farseer credential is registered - this task is still BLOCKED ON ACCESS, which is the correct state until the operator grants it'; print('OK a Farseer workspace or credential is configured')"
```

### NEGATIVE CONTROL

**It fails today, and failing is the correct outcome** — that is unusual for an
acceptance command and it is deliberate. This task is blocked on access, so the
command's job until 2026-10-04 is to state the blockage in a way nobody can
mistake for progress. It prints the provider credentials the registry actually
knows before it asserts, so the reason is visible rather than inferred, and it
reads `config.VARIABLES` rather than guessing a variable name — a session once
invented four plausible credential names and declared four providers dead.

When access arrives, this command passes and the real acceptance is written
then: six measurements, one per item in the list above, each naming what was
found and what was missing.

## Files

A new client config, a credential in `config.VARIABLES`, and a read-only import
script under `scripts/`. No change to `src/` unless TASK-1001's channel
decision requires one.

## Not in scope

Anything about the current campaigns. This is a historical import of a finished
campaign for the purpose of learning from it.
