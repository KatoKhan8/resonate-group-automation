---
title: "LinkedIn Cadence As Built — 2026-09-26"
task: "TASK-325"
date: "2026-09-26"
status: "read-only audit — no behaviour changed"
---

# LinkedIn Cadence As Built — 2026-09-26

**TASK-325 deliverable.** The actual LinkedIn cadence tree, read from the code
and measured against the running system. No behaviour was changed. Any proposal
to modify the tree is under FINDINGS and waits for the operator.

## 1. The graph `PRODUCTIVE_LI_HEAVY_V1` as configured

**Source:** `src/cadencelibrary.py`, line 327, symbol `PRODUCTIVE_LI_HEAVY_V1`.
**Not** in `src/cadence.py` — that module holds the step-expansion engine, not
the graph definitions. The import path is `from src.cadencelibrary import
PRODUCTIVE_LI_HEAVY_V1`.

The cadence carries **10 steps total**: 5 LinkedIn and 5 email, interleaved
over 21 days.

| key | day | channel | action | capability | generated | template | notes |
|-----|-----|---------|--------|------------|-----------|----------|-------|
| li1 | 1 | linkedin | connect | `linkedin.connection_request` | No | `linkedin_intro` | Has `alternative` for open profiles |
| em1 | 1 | email | — | — | Yes | — | |
| li2 | 3 | linkedin | message | `linkedin.message` | Yes | — | `requires: CONNECTED` |
| em2 | 4 | email | — | — | Yes | — | |
| li3 | 6 | linkedin | message | `linkedin.message` | Yes | — | `requires: CONNECTED`; has `alternative` (InMail fallback) |
| em3 | 8 | email | — | — | Yes | — | |
| li4 | 10 | linkedin | message | `linkedin.message` | Yes | — | `requires: CONNECTED` |
| em4 | 12 | email | — | — | Yes | — | |
| li5 | 15 | linkedin | message | `linkedin.message` | Yes | — | `requires: CONNECTED` |
| em5 | 21 | email | — | — | Yes | — | |

**li1's alternative:** When the provider says a direct message needs no
connection (open profile), the action becomes `open_profile_message` with
capability `linkedin.open_profile_message`. This alternative is `generated:
True`.

**li3's alternative:** When the connection request is not accepted, the action
becomes `inmail` with capability `linkedin.inmail`. In practice this branch is
**never wired**: `cadencelibrary` holds every step naming `CAP_INMAIL` because
`INMAIL_ELIGIBILITY_DETECTABLE` is False, and no InMail copy has ever been
approved. The factory omits the InMail branch by default.

**Historical note:** The cadence originally carried a sixth LinkedIn step
(`li6`, day 18, message). TASK-179 removed it on 2026-09-16 because the graph
had no position for it — `COPY_MAPPING` only mapped li1..li5 — so li6 could
never fire. The current cadence has five LinkedIn steps.

## 2. Where the graph is defined

| What | File | Symbol / line |
|------|------|---------------|
| Cadence graph (step list) | `src/cadencelibrary.py` | `PRODUCTIVE_LI_HEAVY_V1`, line 327 |
| Cadence registry | `src/cadencelibrary.py` | `SEQUENCES` dict, line 457 |
| Ladder mapping | `src/cadencelibrary.py` | `_SEQUENCE_LADDERS`, line 429 (`"productive_li_heavy_v1": {"email": "email_five"}`) |
| Copy-to-graph role mapping | `src/heyreachfactory.py` | `COPY_MAPPING`, line 106 |
| Alternative mapping (InMail) | `src/heyreachfactory.py` | `ALTERNATIVE_MAPPING`, line 114 |
| Required roles | `src/heyreachfactory.py` | `REQUIRED_ROLES`, line 119 |
| Graph builder (no InMail) | `src/heyreachfactory.py` | `_build_sequence_no_inmail()`, line 365 |
| Graph builder (with InMail) | `src/providers/heyreach.py` | `linkedin_sequence()`, line 1198 |
| Staging entry point | `src/heyreachfactory.py` | `stage()`, line 591 |
| Plan builder | `src/heyreachfactory.py` | `_plan()`, line 725 |
| Copy assembler | `src/heyreachfactory.py` | `assemble_linkedin_copy()`, line 215 |
| Per-lead custom fields | `src/heyreachfactory.py` | `custom_fields_for()`, line 525 |
| Merge variable graph copy | `src/heyreachfactory.py` | `merge_sequence_copy()`, line 469 |
| Missing-copy refusal | `src/heyreachfactory.py` | `_refuse_missing()`, line 339 |

## 3. What `heyreachfactory` actually stages, step by step

### 3a. The copy-to-role mapping

`COPY_MAPPING` maps each cadence step to one or more graph roles:

| cadence step | graph role(s) | explanation |
|--------------|---------------|-------------|
| li1 | `connection_note` | The connection request note |
| li2 | `connected_1` AND `message_2` | Two branches, same first message |
| li3 | `connected_2` AND `message_3` | Two branches, same second message |
| li4 | `connected_3` AND `message_4` | Two branches, same third message |
| li5 | `connected_4` | Already-connected branch only |

li2 serves two roles because the graph has two branches that both start with
"the first message to a connection": `connected_1` on the already-connected
branch and `message_2` on the post-connection branch. The same generated words
fill both slots. A prospect walks ONE branch and never sees both.

### 3b. The staging flow

1. `_plan()` reads the cadence steps via `cadence.steps_for(campaign, config)`.
2. `merge_sequence_copy(config)` builds the **campaign-level graph** from merge
   variables (`{connection_note}`, `{connected_1}`, etc.), NOT from one
   contact's words. Each role's `messages` list carries `["{role}"]` and the
   `fallbackMessage` comes from `config.linkedin_sequence.fallbacks.<role>`.
3. `build_sequence()` calls `_build_sequence_no_inmail()` which constructs the
   graph tree from those variables.
4. For each contact in the campaign's records, `custom_fields_for()` collects
   that contact's own approved words, keyed by the variable name.
5. Contacts with missing copy or unsupported claims are excluded from the
   pushable set. The sequence is unaffected — one incomplete contact no longer
   decides what the whole campaign says.
6. The cohort is checked for semantic repetition across per-lead copy.
7. If live, `heyreach.set_sequence()` writes the graph and reads it back.

### 3c. What `_refuse_missing()` refuses

`_refuse_missing()` (line 339) receives a list of `(contact_key, step_key,
role)` tuples from `assemble_linkedin_copy()`. If any are present, it raises
`FactoryRefused` naming every gap:

```
FactoryRefused: approved LinkedIn copy is missing for:
  contact 'jane_doe', step 'li3' -> role 'connected_2';
  contact 'jane_doe', step 'li3' -> role 'message_3'.
  Every role the graph requires must have approved words;
  a step with no copy sends a blank to a real person
```

This is the **live path's refusal**: it fires when a contact's stored cadence
steps lack approved copy for any of the 8 required roles. The PHASE1-PLAN
claim that "`_refuse_missing()` refuses the whole staging" is correct in
principle — it refuses the push for any contact with gaps — but the per-contact
scoping in `_plan()` means a contact with complete copy is still pushable even
if another contact has gaps. The sequence itself is never refused for one
contact's missing copy.

## 4. The provider payload shape

The HeyReach sequence is a tree of nodes. Each node is a dict:

```python
{
    "nodeType": "MESSAGE" | "CONNECTION_REQUEST" | "VIEW_PROFILE" |
                "FOLLOW" | "CHECK_IS_CONNECTION" | "END" | ...,
    "actionDelay": int,          # e.g. 3
    "actionDelayUnit": str,      # "HOUR" | "DAY"
    "payload": {                 # MESSAGE and CONNECTION_REQUEST only
        "messages": ["{role}"],  # merge variable(s)
        "fallbackMessage": "..." # configured fallback text
    },
    "conditionalNode": {...},    # the "yes" branch (if applicable)
    "unconditionalNode": {...},  # the "next" node
}
```

For CONNECTION_REQUEST nodes, the payload also carries:
```python
    "toBeWithdrawnAfterDays": 21  # from withdraw_after_days parameter
```

The write endpoint is `/campaign/UpdateSequence` with body:
```python
{"campaignId": int, "sequence": <the tree>}
```

The no-InMail graph has **17 nodes** total (measured), with **8 message nodes**
(1 CONNECTION_REQUEST + 7 MESSAGE). The node types present are:
`CHECK_IS_CONNECTION`, `CONNECTION_REQUEST`, `END`, `FOLLOW`, `MESSAGE`,
`VIEW_PROFILE`.

### The graph structure (no-InMail)

```
CHECK_IS_CONNECTION (root, instant)
├── already connected →
│   MESSAGE {connected_1} (3h) →
│   MESSAGE {connected_2} (3d) →
│   VIEW_PROFILE (2d) →
│   MESSAGE {connected_3} (5d) →
│   MESSAGE {connected_4} (7d) →
│   END
│
└── not connected →
    VIEW_PROFILE (3h) →
    FOLLOW (3h) →
    CONNECTION_REQUEST {connection_note} (1d) →
    ├── accepted (conditionalNode) →
    │   MESSAGE {message_2} (3h) →
    │   VIEW_PROFILE (3d) →
    │   MESSAGE {message_3} (2d) →
    │   MESSAGE {message_4} (7d) →
    │   END
    │
    └── not accepted (unconditionalNode) →
        VIEW_PROFILE (5d) →
        END
```

## 5. The four-vs-five question: why review pages render four messages

**Answer: The five steps are distributed across two branches, and no single
execution path uses all five. This is a render-only difference — no step is
dropped before the provider.**

The cadence has 5 LinkedIn steps. The HeyReach graph has 8 MESSAGE/
CONNECTION_REQUEST nodes across two branches:

- **Already-connected branch:** `connected_1` (li2), `connected_2` (li3),
  `connected_3` (li4), `connected_4` (li5) — **4 messages**
- **Not-connected branch:** `connection_note` (li1, CONNECTION_REQUEST), then
  `message_2` (li2), `message_3` (li3), `message_4` (li4) — **1 connection
  request + 3 messages = 4 interactions**

li5 maps ONLY to `connected_4`, which sits on the already-connected branch.
The not-connected branch's last message is `message_4` from li4. The fifth
step is present in the graph but on a path a cold prospect never walks.

**The file and line that decides it:** `src/heyreachfactory.py`, lines 106-112
(`COPY_MAPPING`). li5's role tuple is `("connected_4",)` — a single role on the
already-connected branch. The not-connected branch's roles (`message_2`,
`message_3`, `message_4`) come from li2, li3, li4 respectively. No li5 role
appears on the cold path.

The review pages in `scripts/render_preview.py` (lines 670-672) state the two
branches explicitly:

```python
ALREADY_CONNECTED_BRANCH = ("connected_1", "connected_2",
                            "connected_3", "connected_4")
NOT_CONNECTED_BRANCH = ("connection_note", "message_2",
                        "message_3", "message_4")
```

Both branches carry four interactions. Neither carries five. The fifth step is
not lost — it is on the other branch.

**This is NOT a P0 finding.** No step is dropped before the provider. The graph
contains all 8 MESSAGE/CONNECTION_REQUEST nodes, and a prospect on the
already-connected path receives li2 through li5 as four sequential messages.

## 6. Merge variables vs baked words

**CONFIRMED: The HeyReach sequence carries merge variables, and the words
arrive per lead.**

`docs/CONTEXT-RESET-2026-09-15-E.md` states that the HeyReach sequence holds
merge variables and the words arrive per lead. This is verified against the
code:

1. `merge_sequence_copy(config)` (line 469) builds the graph with
   `["{role}"]` as the messages — literal placeholder strings like
   `{connection_note}`, `{connected_1}`, etc.
2. `merge_variable_of(role)` (line 464) returns the role name itself as the
   HeyReach custom-field name: `connection_note`, `connected_1`, etc.
3. `custom_fields_for()` (line 525) builds each contact's own words keyed by
   those variable names.
4. `heyreach.build_lead_pairs()` puts the words on the wire as
   `customUserFields` in the lead payload.
5. `heyreach.supplied_field_names()` derives the intersection of field names
   every row supplies.
6. `heyreach.refuse_unsupported_sequence()` refuses when the graph uses a
   variable the push does not supply.

The graph is campaign-level (one graph per campaign). The words are per-lead
(each lead's `customUserFields` carry their own approved copy). HeyReach
substitutes `{connected_1}` with the lead's own words at send time. If a
variable cannot be filled, HeyReach sends the `fallbackMessage` from the
client config — and `refuse_unsupported_sequence` makes that unreachable in
practice by refusing the push unless every lead supplies every variable.

## Verification commands

The graph symbol is in `cadencelibrary`, not `cadence`:

```
py -3 -c "import sys;sys.path.insert(0,'.');from src import cadencelibrary as cl;\
print('graph:', 'PRODUCTIVE_LI_HEAVY_V1' in dir(cl))"
```

Step count and types:

```
py -3 -c "import sys;sys.path.insert(0,'.');from src import cadencelibrary as cl;\
steps=cl.PRODUCTIVE_LI_HEAVY_V1;\
li=[s for s in steps if s['channel']=='linkedin'];\
print(f'LinkedIn steps: {len(li)}');\
[print(f'  {s[\"key\"]}: day={s[\"day\"]}, action={s.get(\"linkedin_action\")}') for s in li]"
```

Output:
```
LinkedIn steps: 5
  li1: day=1, action=connect
  li2: day=3, action=message
  li3: day=6, action=message
  li4: day=10, action=message
  li5: day=15, action=message
```

`heyreachfactory.describe` does not exist. The staging entry point is
`heyreachfactory.stage()` and the plan builder is `heyreachfactory._plan()`.

## FINDINGS

**No P0 findings.** The cadence, the graph, and the staging pipeline are
consistent with each other. The four-vs-five discrepancy is a branch structure,
not a silent drop.

**Observations for the operator:**

1. **li5 only fires for already-connected prospects.** A cold prospect who
   accepts the connection request receives three messages (li2/li3/li4 as
   message_2/message_3/message_4). An already-connected prospect receives four
   (li2/li3/li4/li5 as connected_1/connected_2/connected_3/connected_4). If
   the intent is five messages on every path, li5 needs a role on the
   not-connected branch too. **Do not make this change without an operator
   decision** — it would add a fifth message to the cold path and change the
   touch count.

2. **The `_refuse_missing` refusal is per-contact, not per-campaign.** A
   campaign with ten contacts where one has missing copy still stages and
   pushes the other nine. The PHASE1-PLAN's statement that "`_refuse_missing()`
   refuses the whole staging" is accurate for the contact but not for the
   campaign.

3. **The InMail branch is structurally present but practically dead.**
   `ALTERNATIVE_MAPPING` maps li3 to an `inmail` role, but
   `build_sequence(include_inmail=False)` — the default — omits it. No InMail
   copy has ever been approved. The not-accepted branch ends after a profile
   view instead of an InMail.
