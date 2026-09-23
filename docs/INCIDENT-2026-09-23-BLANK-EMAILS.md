# Incident — 76 blank emails reached real prospects, 2026-09-22/23

Operator decision, 2026-09-23 night: a written root-cause analysis, and three
controls that make it impossible.

**No prospect identifiers appear in this file.** Leads are named by their
EmailBison numeric id. `tests/test_fixture_hygiene.py` is why, and the
identifiers in the artifacts under `work/` are why those stay gitignored.

---

## 1. WHAT HAPPENED

Between 2026-09-22 13:04Z and 2026-09-23 14:30Z, **76 emails with an empty
subject and a body of `<p></p>` were sent** to real prospects across five
campaigns. One prospect **replied** to one of them.

    campaign   blank sent
    491            42
    492            21
    494             7
    495             1
    497             5
    ---------------------
    total          76

487, 489, 493, 496 and 498 sent none. Re-measured independently on
2026-09-23 at 21:0xZ against provider-recorded content, with a predicate that
treats `<p></p>` and `Re:` -only subjects as blank — **the same 76**, and
**0 blank rows still scheduled across 487–498**.

**It was found by reading what the provider records as SENT, not our render.**
That distinction is the whole incident: every local check said the copy was
fine, and every local check was looking at the wrong object.

---

## 2. ROOT CAUSE

### 2.1 The mechanism

Our sequence steps are **pure merge templates**. Campaign 497, read from the
provider:

    step 4769  order 1  thread_reply False  subject '{SUBJECT_1}'  body '<p>{BODY_1}</p>'
    step 4770  order 2  thread_reply True   subject 'Re: {SUBJECT_1}'  body '<p>{BODY_2}</p>'
    step 4771  order 3  thread_reply True   subject 'Re: {SUBJECT_1}'  body '<p>{BODY_3}</p>'

EmailBison renders those templates against the lead's custom variables when it
builds the `scheduled-emails` queue. **A lead carrying no `subject_1` /
`body_1` renders to subject `''` and body `<p></p>`** — and the provider sends
it. There is no provider-side guard that refuses an empty render. The
follow-up rows prove the substitution rather than a storage fault: they read
`Re: ` exactly, `{SUBJECT_1}` having resolved to nothing.

### 2.2 Who those leads are — 73 of the 76 were never ours

Every scheduled row in 487–498 was attributed by asking whether its lead
carries the two variables `bisonfactory` always writes, `record_id` and
`contact_key`:

    FOREIGN / sent    / blank        73
    FOREIGN / sent    / ok            1
    FOREIGN / stopped / blank       101
    FOREIGN / stopped / ok            1
    factory / sent    / blank         3
    factory / sent    / ok          581
    factory / scheduled / ok        543
    factory / stopped / ok          101
    factory / bounced / ok            3

**176 rows belong to leads our factory never created, and 174 of them are
blank.** They carry `headline` and `location` — LinkedIn-export shaped — and
no copy variables at all. Their `created_at` is **2026-04-08** and
**2026-06-09**: they predate these campaigns by months. They are the client's
own historical estate, sitting inside campaigns 491–498.

Apart from three rows, **every lead the factory did create rendered
correctly**: 581 sent, 543 scheduled, 101 stopped, 3 bounced, none blank.

### 2.3 The other three — the render is a snapshot

Three blank sends in 491 went to leads that carry correct copy **now**:

    lead    created_at            blank sent at         lead updated_at
    141278  2026-04-08T18:32:58   2026-09-22T13:04:01   2026-09-22T13:58:45
    190068  2026-06-09T15:21:34   2026-09-22T13:11:28   2026-09-22T13:58:45
    140657  2026-04-08T18:32:56   2026-09-22T13:47:36   2026-09-22T13:58:01

All three were **updated after the blank email had already gone out**. They
are client-estate leads that our factory later adopted by email
(`bison.find_lead_by_email`) and PATCHed our `record_id`, `contact_key`,
`subject_1` and `body_1` onto — at 13:58, up to 54 minutes *after* the empty
render had been queued and sent.

**Patching a lead does not re-render a queue row that already exists.** This
is the half of the root cause that survives fixing the first half, and it is
the reason a guard that reads the LEAD is not sufficient. Read the lead today
and the copy is perfect; the email the prospect received was still empty.

### 2.4 Why the account rule mattered here

Two of the three (141278, 190068) are at the same account. The "one new person
per account per week" rule and this incident have the same underlying cause:
people arriving in a campaign by a path that did not go through staging.

---

## 3. WHY EVERY LOCAL CHECK PASSED

| check | what it looks at | why it saw nothing |
|---|---|---|
| `bisonfactory._approved_copy` → `missing_copy` | the leads **we stage** (`wanted`) | The 73 were never in `wanted`. The refusal at `bisonfactory.py:1442` is real, correct, and was never reached. |
| `_refuse_bad_greetings`, `_refuse_unsupported` | the same `wanted` set | same |
| `bison_readback.py` | the **sequence** | Every field it compares is a placeholder — `{SUBJECT_1}` on both sides. It passes on an empty render and is right to. |
| `queued_copy_readback.py` | the **rendered queue row** | **This one would have caught it.** It has no automated caller: only `scripts/resume_487.py` and a test. Nothing runs it on a schedule. |
| `bison_watch_loop` | row **counts** per campaign | Counts rows, never content. And `MONITORS` held **no watcher for 496, 497 or 498** — 497 is where this was found, by hand. |
| reading the lead afterwards | the lead's variables | Correct by then for the three in §2.3. The evidence of the fault lives only in the queue row. |

The pattern this repository keeps recording, once more: **the failure looked
exactly like the success.** Every object we inspected was in the state we
expected. The object we did not inspect was the only one that was wrong.

---

## 4. THE SECOND FAULT, SEPARATE AND CONTAINED

Factory leads carry the literal four-character string `'None'` in
`body_4`, `body_5`, `body_6` and `subject_2`..`subject_6`:

    body_1    'Julian, I work with Marketing & Advertising teams on ...'
    body_4    'None'
    subject_2 'None'

`bison._variables` drops empty values (`if str(value or "").strip()`) and
`_variables_for` writes `node.get("body") or ""`, so **neither can produce
`'None'`** — some other writer did, and it has not been found. It did not
cause these 76: 491/492/497 are three-step sequences, so `{BODY_4}` is never
referenced, and the threaded steps read `{SUBJECT_1}` rather than
`subject_2`.

**It is one step of cadence growth away from sending the word "None" to a
prospect.** The guard in §5 refuses `"None"` for exactly this reason, which
is why the operator specified it, and the writer is still to be found.

---

## 5. THE THREE CONTROLS

### (a) The push guard — necessary, and not sufficient on its own

Refuse any push where a required `SUBJECT_n` or `BODY_n` for any step of any
lead would be empty, `"None"`, or a placeholder, **verified by reading back
from the provider what it will send** rather than by checking what we
intended to send.

**Stated honestly: this control would not have prevented 73 of the 76.**
Those leads were never pushed by us. It prevents the three in §2.3 only if the
readback happens *after* staging and reads the **queue row**, not the lead.
The guard's readback is therefore defined as: stage, then re-read
`scheduled-emails` for the campaign, and refuse — and halt — if any row for
any of our leads renders empty.

### (b) The watcher check — this is the one that catches this class

Every cycle, for every ACTIVE campaign, scan **every scheduled row** for empty
or placeholder subject/body, **regardless of whether the lead is ours**, and
halt that campaign with a CRITICAL alert on any hit.

This is the control that would have caught all 76, because it asks the only
question that was never asked: *what is the provider about to send, to
everybody in this campaign.* It needs watchers for **496, 497 and 498**, which
`MONITORS` still does not have.

### (c) The regression fixture

From step 4769 and lead 167865: a lead with `headline` and `location` and no
copy variables, against the real template `<p>{BODY_1}</p>`. It must fail on
the pre-fix code for both (a) and (b), and the `'None'` case of §4 alongside
the empty case.

---

## 6. WHAT THIS CHANGES ABOUT THE ESTATE

The open question this incident raises and does not answer: **how did the
client's 2026-04-08 leads come to be inside campaigns 491–498?** Our code has
exactly one path that attaches leads to a bison campaign
(`bisonfactory._ensure_leads` → `bison.attach_leads`), and the 73 carry no
trace of having been through it. Either they were attached by that path after
being matched by email, or they were attached outside our system. Until that
is answered, **the campaigns contain people we did not choose**, and §5(b) is
what stands between them and another send.
