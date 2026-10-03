# TASK-1002 — a meeting is not a first-class outcome, and the one authority that reads it is never written

Opened 2026-10-03 on the operator's instruction, the same day they made the
positive reply the system's primary metric. The thing one step past a positive
reply — the meeting — cannot be counted from this system's own state.

## Measured, by two lanes independently

- `work/queue.jsonl` holds **0 `meeting_marked` events in 1,584 records**,
  against **42 other event types** that are present.
- `meeting_booked` appears in **no file** under `work/` or `docs/`.
- The provider has no such field: **22 stat keys** on the HeyReach side carry
  none, and EmailBison's campaign record carries none.
- And the part that makes it a defect rather than a gap: **`outcomes.funnel`
  reads `MEETING_MARKED` and nothing appends it.** The Slack `MARK_MEETING`
  action exists and **has no caller that writes the event.**

So the funnel's last stage is permanently zero, and a permanent zero is
indistinguishable from "no meetings happened".

## Why it matters now rather than later

The operator's own account of the reference campaign is **35 meetings in 14
countries**. Two lanes went looking for that number on 2026-10-03:

- the email lane found **56 meetings INVOICED Feb–Jun 2026**, and reported that
  "35 in 14 countries" **appears in no artefact** — "35" and "countries" never
  co-occur with the client across 165 Slack messages;
- **country is never a field anywhere**, so the 14 is not checkable at all;
- per-meeting channel and step attribution went into a CRM this repository
  cannot read.

Neither number is wrong — the invoices are evidence and the operator's memory
is evidence — but **this system cannot confirm or refute either**, and that is
exactly what a first-class outcome would fix. The next campaign's meeting count
should be a measurement, not a recollection.

## What to do

1. **`MEETING_MARKED` gets a production writer.** The Slack action is the
   obvious first caller; a reply classified `meeting_intent` is the second, and
   the LinkedIn lane measured that `meeting_intent` fired **0 times in 3,164
   real replies**, which is its own finding (see the classifier audit).
2. **A `meetings` key on `work/campaigns.jsonl`**, so a campaign can be ranked
   by meetings the way it is now ranked by positives.
3. **Country, or no claim about countries.** Either the account record carries
   one — it already carries a domain and research — or the system stops being
   asked questions it has no field for.
4. **A meeting is attributed to a channel and a step**, or it is attributed to
   `unknown`. Never to a guess: 55.4% of the LinkedIn lane's operator-positive
   replies already join to no campaign and stay `unknown campaign`.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import events; names=[n for n in dir(events) if n.isupper()]; kind=next((n for n in names if 'MEETING' in n), None); assert kind, 'events has no MEETING kind: '+str(names[:12]); import inspect, src.outcomes as o; readers=[n for n in dir(o) if 'funnel' in n or 'meeting' in n]; assert readers, 'outcomes exposes nothing that reads a meeting'; print('OK the event kind exists and outcomes reads it:', kind, readers)"
```

```
python -c "import os,subprocess,sys; sys.path.insert(0,'.'); r=subprocess.run(['grep','-rn','MEETING_MARKED','src/','scripts/'],capture_output=True,text=True,encoding='utf-8',errors='replace'); lines=[l for l in r.stdout.splitlines() if l.strip()]; writers=[l for l in lines if 'append' in l or 'record_event' in l or 'add_event' in l]; assert writers, 'MEETING_MARKED has readers but no writer - the funnel stage is permanently zero:\n'+'\n'.join(lines[:8]); print('OK', len(writers), 'production site(s) WRITE the event:'); [print('   ', w[:120]) for w in writers[:4]]"
```

### NEGATIVE CONTROL

**Command 2 fails today** and is the one that matters: it asserts a WRITER
exists, not merely that the constant does. That is the whole defect — the
constant, the reader and the Slack action all exist already, so a command that
only checked for the name would pass today and prove nothing.

It greps source, which this repository forbids as a rule, and the exception is
argued rather than hidden: the defect IS the absence of a call site, there is no
runtime state that distinguishes "never called" from "called and nothing
happened", and the assertion accepts any of three append spellings so a rewrite
that keeps a writer satisfies it.

Command 1 is the structural half and may pass earlier than command 2; both are
required, and command 1 alone must never be read as this task being done.

## Files

`src/events.py`, `src/outcomes.py`, the Slack action's handler, and
`work/campaigns.jsonl`'s shape through `src/store.py`.

## Not in scope

Recovering the reference campaign's meeting count. That needs the other
workspace (TASK-1003) and a CRM this repository does not read; this task makes
the NEXT campaign's count a measurement.
