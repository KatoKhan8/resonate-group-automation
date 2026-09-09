# Cadence experiments: what exists, and the one wire that does not

Read `CADENCE-MODEL.md` first — it describes the graph. Read
`COPY-EXPERIMENTS.md` for the other experiment layer. This file is about
the second dimension: whether different sequence *structures* perform
differently, and what would have to be true before Resonate could answer
that.

It opens with an audit rather than a design, because the audit changes
what the design should be.

---

## 1. The audit

The question the audit had to settle: **what actually decides which steps
a contact receives?**

The answer is `src/cadence.py`:

```python
STEPS = (
    {"key": "day1",  "day": 1,  "channel": "email"},
    {"key": "day3",  "day": 3,  "channel": "linkedin"},
    {"key": "day5",  "day": 5,  "channel": "email"},
    {"key": "day8",  "day": 8,  "channel": "linkedin", "requires": ...},
    {"key": "day10", "day": 10, "channel": "email"},
    {"key": "day15", "day": 15, "channel": "email"},
    {"key": "day21", "day": 21, "channel": "email"},
)
```

A module-level constant. `cadence.build` iterates it directly for every
contact of every record in every campaign in every workspace.

**Cadence length is not a variable in this system.** It is seven, always,
and the days and channels are fixed with it. Nothing about a campaign
changes it.

`src/cadencegraph.py` is a different thing: a real graph model with
fourteen node types, conditions, versioning, validation, four templates
and a screen. It is genuinely built and genuinely good. It is also not
connected to execution, and the code says so in its own words -
`campaignqa._structure` reports:

> "This campaign has no cadence graph; it runs the legacy linear cadence."

`PRODUCT-INVENTORY.md` has carried the row honestly for some time:
*Cadence graph in the builder — MISSING — previewed and validated, not yet
stored on a campaign.*

### Classification

| capability | class | where |
| --- | --- | --- |
| Linear cadence execution | **EXISTS AND WIRED** | `cadence.STEPS`, fixed at 7 |
| Branching cadence model | **EXISTS BUT UNUSED** | `cadencegraph`, never stored on a campaign |
| Cadence templates (shapes) | **EXISTS BUT UNUSED** | `cadencegraph.TEMPLATES`, 4 of them |
| Per-campaign cadence | **MISSING** | `campaign.cadence_version` exists and is always `None` |
| Cadence length variation | **MISSING** | nothing can express 4 steps |
| Cadence arm assignment | **MISSING** | — |
| Step purpose / angle / CTA metadata | **PARTIAL** | node *types* exist; purpose, angle and CTA do not |
| Copy variants | **EXISTS BUT UNUSED** | nothing calls `variants.apply_to_step`; see PRODUCT-GAPS §3d |
| Variant recorded on the event | **EXISTS AND WIRED** | fixed in the pilot-hardening pass |
| Exposure from confirmed touches | **EXISTS AND WIRED** | `variants.journey_of`, `results_from` |
| Statistical discipline | **EXISTS AND WIRED** | Wilson bounds, sample floor, five states |
| Reply attribution to latest touch | **EXISTS AND WIRED** | `results_from`, and it says it is a convention |
| Cohort maturity | **MISSING** | — |
| Diminishing returns analysis | **MISSING** | — |
| Fatigue as an experiment cost | **PARTIAL** | `fatigue` exists; not joined to experiment reporting |
| Account-level randomisation | **MISSING** | variants randomise per contact |
| Provider mapping per arm | **MISSING** | one campaign maps to one provider campaign per channel |

### What the audit means for this mission

Almost everything the mission asks for sits on top of one thing that does
not exist: **execution reading a cadence from the campaign rather than
from a module constant.**

Arms, assignment, exposure, maturity, step contribution and diminishing
returns are all analysis over a variable that is currently fixed. Building
them first would produce a reporting layer over an experiment that cannot
run — which is precisely the defect this codebase keeps finding in itself,
and it would be the third instance found this week.

So the order is: make the cadence a property of the campaign, then
everything else.

---

## 2. What must stay true while that changes

`cadence.build` is not a leaf. `eligibility`, `push`, `approval`,
`fatigue`, `campaignqa`, the outreach preview and the account view all
read what it produces. A change here is a change to the execution path of
every campaign.

Three properties are non-negotiable:

**A campaign with no cadence behaves exactly as it does today.** Not
approximately - identically. The fallback is the existing constant and
there is a test that walks a record through both paths and compares.

**Step keys stay stable.** `day1` is an identity, not a label: approvals
are fingerprinted per step key, events carry it, and `push_id` is
`record:contact:step:channel`. A cadence that renamed steps would
invalidate every stored approval and orphan every event.

**A shorter cadence is not a truncated longer one.** Arm A's step 4 and
Arm D's step 4 are different steps in different sequences. Treating them
as the same because they share a key would pool two experiments.

---

## 3. What this file will describe once it is built

Reserved deliberately. Writing the design of assignment, exposure and
maturity before the foundation exists would be documentation of a system
nobody can run - and this repository has a rule about describing
connections in the present tense before they are connected.

See `PRODUCT-GAPS.md` for what is missing today.
