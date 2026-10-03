# TASK-1001 — the channel model has two channels, so a call or a WhatsApp touch has nowhere to go

Opened 2026-10-03 on the operator's instruction, after three independent
measurements agreed that Farseer's coordinated cadence cannot be recorded by
this system even if its texts were recovered.

## Measured

    channels.MODES = ['multichannel', 'email_only', 'linkedin_only', 'none']

and `grep` over `src/channels.py`, `src/events.py` and `src/store.py` finds no
`phone`, `call` or `whatsapp` in any form. `channels.REASONS` carries ten
refusal reasons and every one of them is about an address or a profile.

Three lanes reached the same place from different directions on 2026-10-03:

- the local search: every `whatsapp` / `aircall` / `twilio` / `dialer` hit
  outside Slack history is a **prospect company description** — 9 queue rows,
  with the term in `research` (8) and `company_facts` (1). No call-shaped file
  exists in `work/`;
- the email lane: **Farseer ran on LinkedIn, voice, WhatsApp and the phone**,
  and per-meeting channel attribution went into a CRM this repository cannot
  read;
- the LinkedIn lane: **0 of the 40 HeyReach ledger rows also carry a
  `bison_campaign_id`**, so no cross-channel cadence is recordable today even
  for the two channels that DO exist.

## Why this is not a feature request

The operator's metric is the positive reply and the reference cadence is one
that **coordinated channels per account**. Both of those are unmeasurable while
a touch can only be an email or a LinkedIn action. The system cannot say "the
call came third and the positive reply came after it" because it has no third
channel to put the call in.

It is also an invariant-0 problem rather than a missing field: a touch that
happened and cannot be recorded makes the touch ledger INCOMPLETE, and an
incomplete ledger read as complete is how suppression and recontact windows
start being wrong.

## What to do, and the order matters

1. **Decide the vocabulary with the operator before writing code.** `phone` and
   `whatsapp` as channels, or one `manual` channel with a sub-type? The second
   is smaller and covers the case where somebody meets a prospect at a
   conference. This is a model decision, not a patch, and it is the operator's.
2. Add the channel to `channels.MODES` and to whatever enumerates a touch's
   channel in `events`, and give it a REFUSAL reason of its own — a channel
   with no way to be refused fails open.
3. **Suppression must read it.** A negative reply on a call suppresses the
   person on every channel, exactly as a negative email reply does.
4. **Attribution must NOT read it** without a decision: a manual call is not
   Resonate OS contact, and the five-step classification turns on whether
   RESONATE OS contacted them. Getting this wrong converts cold leads into
   revival leads by the hundred.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import channels; modes=set(channels.MODES); assert 'none' in modes, modes; extra=modes-{'multichannel','email_only','linkedin_only','none'}; assert extra, 'the channel model still has exactly the two channels: '+str(sorted(modes)); print('OK the model knows a third channel:', sorted(extra))"
```

```
python -c "import re,sys; sys.path.insert(0,'.'); from src import events; kinds={k for n in dir(events) if n.isupper() for k in ([getattr(events,n)] if isinstance(getattr(events,n),str) else list(getattr(events,n)) if isinstance(getattr(events,n),(set,tuple,list)) else [])}; kinds={str(k) for k in kinds}; email_or_li={k for k in kinds if re.match(r'^(email|linkedin|connection)_', k)}; assert email_or_li, 'the control failed: no email or linkedin channel kinds found at all, so this command is reading the wrong thing'; third={k for k in kinds if re.match(r'^(phone|whatsapp|voice|call|manual)_(reply|sent|logged|touch|made|received)$', k)}; assert third, 'every channel-specific event kind belongs to email or LinkedIn (%d of them) and none to a third channel - note that provider_call_* is an API call, not a phone call, and matching the bare word call reads as a false pass'%len(email_or_li); print('OK a third channel has its own touch kinds:', sorted(third))"
```

### NEGATIVE CONTROL

**Both fail today**, the first naming the four modes it found. Command 1 keeps
`none` asserted so a "fix" that empties the mode list cannot pass, and it
requires a mode BEYOND the existing four rather than a rename of one — a
rename would satisfy a looser assertion while recording nothing new.

Command 2 is the half that matters more: a mode nothing can write an event for
is a channel in name only, which is this repository's most common defect shape.
It asserts on `events`' own vocabulary rather than on source text, and it
carries a POSITIVE CONTROL — it first requires that email and LinkedIn kinds
are found, so a command reading the wrong object fails loudly instead of
reporting an absence it never looked for.

**The first version of command 2 PASSED, and it was wrong.** It matched the
bare word `call` against the event vocabulary and hit `provider_call_started`,
`provider_call_completed` and five siblings — an API call, not a phone call.
`phone`, `whatsapp` and `manual_touch` appear nowhere. That is the third time
in one day that an acceptance command of mine passed while measuring nothing,
so the suffix is required now (`_reply`, `_sent`, `_logged`, `_touch`, `_made`,
`_received`), which `provider_call_*` cannot satisfy.

Neither command asserts anything about suppression or attribution, because
those are the two decisions above and a command written now would prejudge
them.

## Files

`src/channels.py`, `src/events.py`, and whatever the operator's vocabulary
decision touches. `src/store.py` only if a contact gains a field.

## Not in scope

Importing Farseer's own data, which is TASK-1003 and needs access the operator
grants separately. This task makes the channel recordable; it recovers nothing.
