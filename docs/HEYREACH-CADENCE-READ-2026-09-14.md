# LinkedIn Cadence Read - 2026-09-14

**TASK-064**: Read the LinkedIn cadence as a human would, on both branches.

## BOUNDARY

This worktree has no credentials (`config/.env` exists only in Claude's worktree). Reading HeyReach campaign 599020 is permitted but requires provider credentials. This analysis uses the fixture data from `scripts/render_preview.py heyreach`, which demonstrates both branches with invented records. Production record analysis requires Claude to run the preview or grant provider read access.

**Records analyzed**: 3 fixture records (Maia Torres, Declan Reilly, Rachel Okafor), both branches each = 6 branch walks. Production campaign `productive-linkedin-production-v1` holds 14 records; analyzing all of them requires provider credentials or Claude running the preview.

**The task asks for "at least eight records"**. The fixtures provide 3. This is a boundary: I cannot generate more fixture records without modifying the render_preview script, and I cannot access production records without credentials. The 3 records analyzed demonstrate both branches and answer the six questions, but a full production analysis requires Claude to run `py -3 scripts/render_preview.py productive-linkedin-production-v1`.

---

## THE TWO BRANCHES

From `src/heyreachfactory.py` and `src/providers/heyreach.py:linkedin_sequence`:

```
Already connected:   connected_1 -> connected_2 -> connected_3 -> connected_4
Not yet connected:   connection_note -> message_2 -> message_3 -> message_4
```

Both branches share `li2`..`li4` as their source steps, but the graph roles differ:
- Already-connected branch uses `connected_1`, `connected_2`, `connected_3`, `connected_4`
- Not-yet-connected branch uses `connection_note`, `message_2`, `message_3`, `message_4`

The copy mapping (`src/heyreachfactory.py:COPY_MAPPING`):
```python
"li1": {"role": "connection_note"}
"li2": {"role": ("connected_1", "message_2")}  # same step, two roles
"li3": {"role": ("connected_2", "message_3")}
"li4": {"role": ("connected_3", "message_4")}
"li5": {"role": ("connected_4",)}
```

---

## QUESTION 1: Does the sequence progress WHO -> PROBLEM -> WHAT PRODUCTIVE IS -> DIFFERENT ANGLE -> EASY OUT?

### Branch: Already Connected

**Record: Maia Torres (Studio Manager, resource_management angle)**

| Step | Role | Job | Copy |
|------|------|-----|------|
| connected_1 | li2 | WHO IS WRITING + WHY | "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did." |
| connected_2 | li3 | PROBLEM | "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?" |
| connected_3 | li4 | WHAT PRODUCTIVE IS | "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?" |
| connected_4 | li5 | EASY OUT | "happy to leave it here if the timing is wrong Maia. is there someone else who owns resourcing at Cascadia Design Collective?" |

**Verdict**: YES. The sequence progresses correctly. Each step has a distinct job.

**Record: Declan Reilly (Head of Operations, operations angle)**

| Step | Role | Job | Copy |
|------|------|-----|------|
| connected_1 | li2 | WHO IS WRITING + WHY | "thanks for connecting Declan. no pitch. if utilisation visibility is on your radar this quarter, happy to share what similar teams did." |
| connected_2 | li3 | PROBLEM | "most agency ops leads i speak to find out about margin erosion at the end of a project rather than during it. is that how it works at Bastion?" |
| connected_3 | li4 | WHAT PRODUCTIVE IS | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" |
| connected_4 | li5 | EASY OUT | "happy to leave it here if the timing is wrong Declan. is there someone else who owns this at Bastion Digital?" |

**Verdict**: YES. Same structure, different angle (utilisation/margin vs resourcing).

### Branch: Not Yet Connected

**Record: Maia Torres**

| Step | Role | Job | Copy |
|------|------|-----|------|
| connection_note | li1 | WHO IS WRITING + WHY CONNECT | "hi Maia, i work with design studios on who is booked on what next week. curious how Cascadia Design Collective handles resourcing at your size. happy to connect." |
| message_2 | li2 | WHO IS WRITING + WHY | "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did." |
| message_3 | li3 | PROBLEM | "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?" |
| message_4 | li4 | WHAT PRODUCTIVE IS | "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?" |

**Verdict**: YES, but the branch is SHORTER. It has only 4 messages, not 5. The "EASY OUT" step (connected_4 / li5) is missing from this branch. The not-yet-connected branch ends after the product pitch.

**Record: Declan Reilly**

| Step | Role | Job | Copy |
|------|------|-----|------|
| connection_note | li1 | WHO IS WRITING + WHY CONNECT | "hi Declan, i work with agency operations leads on utilisation visibility. curious how Bastion Digital tracks it across projects. happy to connect." |
| message_2 | li2 | WHO IS WRITING + WHY | "thanks for connecting Declan. no pitch. if utilisation visibility is on your radar this quarter, happy to share what similar teams did." |
| message_3 | li3 | PROBLEM | "most agency ops leads i speak to find out about margin erosion at the end of a project rather than during it. is that how it works at Bastion?" |
| message_4 | li4 | WHAT PRODUCTIVE IS | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" |

**Verdict**: YES, same structure. Missing the easy-out step.

### FINDING

**The two branches are DIFFERENT LENGTHS.** The already-connected branch has 4 messages (connected_1..connected_4). The not-yet-connected branch has 4 messages (connection_note + message_2..message_4), but the connection_note is the invite, so the POST-CONVERSATION message count is:
- Already connected: 4 messages
- Not yet connected: 3 messages after the connection is accepted

This is intentional per `src/heyreachfactory.py`:
```
not connected yet    li1 invite -> li2 -> li3 -> li4
already connected    li2 -> li3 -> li4 -> li5      (no invite needed)
```

The branches share li2..li4, but the already-connected branch gets li5 as the easy-out. The not-yet-connected branch does not.

**Is this a defect?** No. The branches start from different places. A prospect who is already connected does not need an invite, so they get one more message (li5) to reach the same endpoint. A prospect who was cold gets the invite (li1) and then three messages (li2..li4). Both branches end at the product pitch; only the already-connected branch gets the breakup/easy-out.

---

## QUESTION 2: Is the product named, and on which step?

**Estate baseline**: `li4` names Productive in 21 of 50 stored notes (from `config/clients/productive.yaml` comment).

**This fixture**:

| Record | Branch | Step | Names Productive? |
|--------|--------|------|-------------------|
| Maia Torres | Already connected | connected_3 (li4) | YES: "we built productive so the schedule, the budget and the resourcing plan talk to each other" |
| Maia Torres | Not yet connected | message_4 (li4) | YES: "we built productive so the schedule, the budget and the resourcing plan talk to each other" |
| Declan Reilly | Already connected | connected_3 (li4) | YES: "we built productive so budgets, time tracking and resourcing talk to each other" |
| Declan Reilly | Not yet connected | message_4 (li4) | YES: "we built productive so budgets, time tracking and resourcing talk to each other" |

**Verdict**: YES. Productive is named on step li4 (connected_3 / message_4) for both branches. This matches the estate baseline: li4 is the product pitch step.

**Count**: 4 of 4 fixture records name Productive on li4. The estate baseline is 21 of 50 (42%). The fixture is a small sample and both records have li4 approved; the estate includes records where li4 was not generated or failed lint.

---

## QUESTION 3: Does the connection note say WHO IS WRITING and WHY CONNECT, without asking a question that needs thought?

**Record: Maia Torres**

> "hi Maia, i work with design studios on who is booked on what next week. curious how Cascadia Design Collective handles resourcing at your size. happy to connect."

**Analysis**:
- WHO IS WRITING: "i work with design studios on who is booked on what next week" - YES
- WHY CONNECT: "curious how Cascadia Design Collective handles resourcing at your size" - YES
- Question that needs thought: "curious how... handles resourcing" - this is a question, but it is LOW-THOUGHT. It does not ask "how do you currently ensure resourcing visibility across projects?" (which would need a process answer). It asks "how do you handle it at your size?" which is a soft opener.

**Verdict**: PASS. The connection note says who and why, and the question is a soft opener, not a discovery question.

**Record: Declan Reilly**

> "hi Declan, i work with agency operations leads on utilisation visibility. curious how Bastion Digital tracks it across projects. happy to connect."

**Analysis**:
- WHO IS WRITING: "i work with agency operations leads on utilisation visibility" - YES
- WHY CONNECT: "curious how Bastion Digital tracks it across projects" - YES
- Question that needs thought: "curious how... tracks it across projects" - again, a soft opener, not a process question.

**Verdict**: PASS.

---

## QUESTION 4: Is any message a contextless discovery question?

A contextless discovery question is "how do you currently ensure profitability is visible in your projects?" with no preceding context.

**Record: Maia Torres, Already Connected**

| Step | Copy | Contextless? |
|------|------|--------------|
| connected_1 | "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did." | NO. This is an offer, not a question. |
| connected_2 | "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?" | NO. Preceded by context: "most studios i speak to find out..." |
| connected_3 | "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?" | NO. This is a pitch, not a discovery question. |
| connected_4 | "happy to leave it here if the timing is wrong Maia. is there someone else who owns resourcing at Cascadia Design Collective?" | NO. This is a breakup/redirect, not discovery. |

**Record: Maia Torres, Not Yet Connected**

| Step | Copy | Contextless? |
|------|------|--------------|
| connection_note | "hi Maia, i work with design studios on who is booked on what next week. curious how Cascadia Design Collective handles resourcing at your size. happy to connect." | NO. Preceded by "i work with design studios on..." |
| message_2 | "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did." | NO. Offer, not question. |
| message_3 | "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?" | NO. Preceded by context. |
| message_4 | "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?" | NO. Pitch, not discovery. |

**Record: Declan Reilly, Already Connected**

| Step | Copy | Contextless? |
|------|------|--------------|
| connected_1 | "thanks for connecting Declan. no pitch. if utilisation visibility is on your radar this quarter, happy to share what similar teams did." | NO. |
| connected_2 | "most agency ops leads i speak to find out about margin erosion at the end of a project rather than during it. is that how it works at Bastion?" | NO. Preceded by context. |
| connected_3 | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | NO. |
| connected_4 | "happy to leave it here if the timing is wrong Declan. is there someone else who owns this at Bastion Digital?" | NO. |

**Record: Declan Reilly, Not Yet Connected**

| Step | Copy | Contextless? |
|------|------|--------------|
| connection_note | "hi Declan, i work with agency operations leads on utilisation visibility. curious how Bastion Digital tracks it across projects. happy to connect." | NO. |
| message_2 | "thanks for connecting Declan. no pitch. if utilisation visibility is on your radar this quarter, happy to share what similar teams did." | NO. |
| message_3 | "most agency ops leads i speak to find out about margin erosion at the end of a project rather than during it. is that how it works at Bastion?" | NO. |
| message_4 | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | NO. |

**Verdict**: NO contextless discovery questions in these fixture records. Every question is preceded by context ("most studios i speak to...", "curious how...").

---

## QUESTION 5: Do the two branches read as the SAME conversation?

**Already-connected branch** (Maia Torres):
1. connected_1: "thanks for connecting... no pitch... happy to share what similar studios did"
2. connected_2: "most studios i speak to find out who is double-booked when a person quits... is that how it works at Cascadia?"
3. connected_3: "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?"
4. connected_4: "happy to leave it here if the timing is wrong... is there someone else who owns resourcing..."

**Not-yet-connected branch** (Maia Torres, after connection accepted):
1. connection_note: "hi Maia, i work with design studios on who is booked on what next week... happy to connect"
2. message_2: "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did."
3. message_3: "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?"
4. message_4: "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?"

**Comparison**:
- message_2 (not-yet-connected) == connected_1 (already-connected): YES, identical copy
- message_3 (not-yet-connected) == connected_2 (already-connected): YES, identical copy
- message_4 (not-yet-connected) == connected_3 (already-connected): YES, identical copy
- connected_4 (already-connected) has no counterpart in the not-yet-connected branch

**Verdict**: YES, the two branches read as the same conversation for steps li2..li4. The already-connected branch gets one additional step (li5 / connected_4) as the easy-out. The not-yet-connected branch starts with the connection note (li1) and then joins the same path at li2.

A prospect who could have walked either branch would receive the same messages from li2 onward. The only difference is whether they got a connection note first (cold) or started with "thanks for connecting" (already connected).

---

## QUESTION 6: Does the generated copy beat the eight hand-written fallbacks, record by record?

The eight fallbacks from `config/clients/productive.yaml`:

```yaml
connection_note: hi, i work with agencies on project profitability and thought it would be good to connect.
connected_1: how do you currently get visibility on whether a project is making money while it is still running?
connected_2: most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?
connected_3: we built productive so budgets, time tracking and resourcing talk to each other. worth a look?
connected_4: happy to leave it here if the timing is wrong. is there someone else who owns this?
message_2: how do you currently get visibility on whether a project is making money while it is still running?
message_3: most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?
message_4: we built productive so budgets, time tracking and resourcing talk to each other. worth a look?
```

### Record: Maia Torres (Studio Manager, resource_management angle)

| Role | Fallback | Generated | Better? |
|------|----------|-----------|---------|
| connection_note | "hi, i work with agencies on project profitability and thought it would be good to connect." | "hi Maia, i work with design studios on who is booked on what next week. curious how Cascadia Design Collective handles resourcing at your size. happy to connect." | **YES**. Names the person, names the company, names the specific angle (resourcing), asks a soft question. The fallback is generic. |
| connected_1 | "how do you currently get visibility on whether a project is making money while it is still running?" | "thanks for connecting Maia. no pitch here. if resourcing visibility is on your list this quarter i am happy to share what similar studios did." | **YES**. The fallback is a contextless discovery question (the defect this task is checking for). The generated copy is a soft offer with no question. |
| connected_2 | "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?" | "most studios i speak to find out who is double-booked when a person quits rather than before. is that how it works at Cascadia?" | **YES**. Same structure, but the generated copy is specific to the angle (resourcing/double-booking) and names the company. The fallback is generic. |
| connected_3 | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | "we built productive so the schedule, the budget and the resourcing plan talk to each other. worth a look?" | **TIE**. Nearly identical. The generated copy says "the schedule, the budget and the resourcing plan" vs "budgets, time tracking and resourcing". Both name Productive. |
| connected_4 | "happy to leave it here if the timing is wrong. is there someone else who owns this?" | "happy to leave it here if the timing is wrong Maia. is there someone else who owns resourcing at Cascadia Design Collective?" | **YES**. Generated copy names the person and the specific role (resourcing) and the company. |

**Verdict for Maia Torres**: Generated copy beats the fallback on 4 of 5 steps. Step connected_3 is a tie.

### Record: Declan Reilly (Head of Operations, operations angle)

| Role | Fallback | Generated | Better? |
|------|----------|-----------|---------|
| connection_note | "hi, i work with agencies on project profitability and thought it would be good to connect." | "hi Declan, i work with agency operations leads on utilisation visibility. curious how Bastion Digital tracks it across projects. happy to connect." | **YES**. Names the person, names the company, names the angle (utilisation visibility). |
| connected_1 | "how do you currently get visibility on whether a project is making money while it is still running?" | "thanks for connecting Declan. no pitch. if utilisation visibility is on your radar this quarter, happy to share what similar teams did." | **YES**. Fallback is a contextless discovery question. Generated is a soft offer. |
| connected_2 | "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?" | "most agency ops leads i speak to find out about margin erosion at the end of a project rather than during it. is that how it works at Bastion?" | **YES**. Generated copy is specific to the angle (margin erosion) and names the company. |
| connected_3 | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | **TIE**. Identical. |
| connected_4 | "happy to leave it here if the timing is wrong. is there someone else who owns this?" | "happy to leave it here if the timing is wrong Declan. is there someone else who owns this at Bastion Digital?" | **YES**. Generated copy names the person and the company. |

**Verdict for Declan Reilly**: Generated copy beats the fallback on 4 of 5 steps. Step connected_3 is a tie (identical).

### Record: Rachel Okafor (Delivery Director, delivery angle) - THE HI-JACOB DEFECT

This record demonstrates the hi-jacob defect class: Rachel's copy contains "Declan" (another contact's name at the same company). The render_preview script flags this:

```
!!! LITERAL NAME: lead 'rachel-okafor', role 'connection_note' contains name 'Declan' from another contact - the hi-jacob defect class
!!! LITERAL NAME: lead 'rachel-okafor', role 'connected_1' contains name 'Declan' from another contact - the hi-jacob defect class
!!! LITERAL NAME: lead 'rachel-okafor', role 'message_2' contains name 'Declan' from another contact - the hi-jacob defect class
```

| Role | Fallback | Generated (with defect) | Better? |
|------|----------|-----------|---------|
| connection_note | "hi, i work with agencies on project profitability and thought it would be good to connect." | "hi Declan, i work with consulting teams on budget burn visibility. curious how Keystone Partners handles it. happy to connect." | **NO - DEFECT**. Rachel receives "hi Declan" - wrong name. The fallback is generic but correct. |
| connected_1 | "how do you currently get visibility on whether a project is making money while it is still running?" | "thanks for connecting Declan. no pitch. if budget visibility is on your list, happy to share what similar teams did." | **NO - DEFECT**. Rachel receives "thanks for connecting Declan" - wrong name. The fallback is a contextless discovery question, but at least it does not misname the recipient. |
| connected_2 | "most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?" | "most consulting leads i speak to find out about scope creep at month end. is that how it works at Keystone Partners?" | **YES**. No name in this message, and the generated copy is angle-specific. |
| connected_3 | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | "we built productive so budgets, time tracking and resourcing talk to each other. worth a look?" | **TIE**. Identical. |
| connected_4 | "happy to leave it here if the timing is wrong. is there someone else who owns this?" | "happy to leave it here if the timing is wrong. is there someone else who owns this?" | **TIE**. Identical. |

**Verdict for Rachel Okafor**: Generated copy is DEFEATED by the fallback on 2 of 5 steps because of the hi-jacob defect. The fallback, despite being generic and carrying a contextless discovery question, is CORRECT because it does not misname the recipient.

**This is the defect class the task is checking for.** A prospect who receives "hi Declan" when their name is Rachel will immediately know this is a mass message, and the sequence is dead on arrival. The fallback, despite its flaws, does not make this mistake.

### UPDATED FINDING

**The generated copy DOES NOT beat the hand-written fallbacks, record by record, when the generated copy carries a defect.**

- Record 1 (Maia Torres): Generated beats fallback on 4 of 5 steps, 1 tie
- Record 2 (Declan Reilly): Generated beats fallback on 4 of 5 steps, 1 tie
- Record 3 (Rachel Okafor): Generated is DEFEATED by fallback on 2 of 5 steps (hi-jacob defect), 2 ties, 1 win

**Overall**: 9 of 15 steps are better, 4 are ties, 2 are worse (defect).

**The defect is not in the generation logic; it is in the copy that was generated.** The model was given Rachel's evidence but wrote "Declan" into her copy. This is the hi-jacob defect class documented in `scripts/render_preview.py` and `src/heyreachfactory.py`. The detection caught it; the generation should not have produced it.

### FINDING

**The generated copy DOES beat the hand-written fallbacks, record by record.**

- 8 of 10 steps: generated is better (names the person, company, angle)
- 2 of 10 steps: tie (identical or nearly identical product pitch on li4)
- 0 of 10 steps: fallback is better

**Why the generated copy is better**:
1. **Personalisation**: Names the person, names the company, names the specific angle
2. **No contextless discovery questions**: The fallback for connected_1 / message_2 is "how do you currently get visibility on whether a project is making money while it is still running?" - this is exactly the defect the task is checking for. The generated copy replaces it with a soft offer.
3. **Angle-specific**: The fallback is generic ("project profitability"). The generated copy is specific to the persona's angle (resourcing, utilisation, margin erosion).

**The fallbacks are the floor, and the generated copy clears the floor.** The fallbacks assert nothing about the reader and are true of any agency. The generated copy asserts specific things about the reader (name, company, angle) and is true of this agency.

---

## SUMMARY

### Question 1: Does the sequence progress correctly?
**YES**. Both branches progress WHO -> PROBLEM -> WHAT PRODUCTIVE IS -> (EASY OUT for already-connected). The not-yet-connected branch is one step shorter because it starts with the connection note.

### Question 2: Is the product named?
**YES**. On step li4 (connected_3 / message_4) for both branches. 4 of 4 fixture records name Productive.

### Question 3: Does the connection note say who and why?
**YES**. Both fixture connection notes say who is writing and why they want to connect, without asking a high-thought question.

### Question 4: Any contextless discovery questions?
**NO**. Every question in the fixture records is preceded by context. The fallback for connected_1 / message_2 IS a contextless discovery question, but the generated copy replaces it with a soft offer.

### Question 5: Do the two branches read as the same conversation?
**YES**. Steps li2..li4 are identical across both branches. The already-connected branch gets one additional step (li5) as the easy-out.

### Question 6: Does the generated copy beat the fallbacks?
**MIXED**. When the generated copy is correct, it beats the fallback on personalisation and angle-specificity. When the generated copy carries the hi-jacob defect, the fallback wins because it does not misname the recipient.

- Record 1 (Maia Torres): Generated beats fallback on 4 of 5 steps, 1 tie
- Record 2 (Declan Reilly): Generated beats fallback on 4 of 5 steps, 1 tie  
- Record 3 (Rachel Okafor): Generated is DEFEATED by fallback on 2 of 5 steps (hi-jacob defect), 2 ties, 1 win

**Overall**: 9 of 15 steps are better, 4 are ties, 2 are worse (defect).

**The fallback is the floor, and the generated copy usually clears it - but not always.** When the generation produces a defect (wrong name), the fallback is the safer choice. The fallback's flaw (contextless discovery question) is less damaging than the generated copy's flaw (wrong name).

---

## CAVEATS

1. **Fixture data, not production**: This analysis uses 2 invented records. Production campaign `productive-linkedin-production-v1` holds 14 records. The task asks for "at least eight records". Analyzing production records requires provider credentials or Claude running the preview.

2. **The defect that started this effort**: The task description says "four messages asking the same profitability question" was found in production. The fixture records do not show this defect. This could mean:
   - The defect was fixed before the fixtures were written
   - The fixtures were written to demonstrate the correct behavior
   - The defect exists in production records not represented in the fixtures

3. **The fallback IS the defect**: The fallback for connected_1 / message_2 is "how do you currently get visibility on whether a project is making money while it is still running?" - this is a contextless discovery question. If a lead's copy fails to generate or fails lint, HeyReach sends this fallback, and the prospect receives exactly the defect the task is checking for. The generated copy avoids this; the fallback does not.

4. **li5 and li6 have no graph position**: The cadence names six LinkedIn steps (li1..li6), but the graph has positions for only five roles (connection_note, connected_1..connected_4, message_2..message_4). li5 fills connected_4, and li6 has no position. This is documented in `src/heyreachfactory.py` and is intentional.

---

## RECOMMENDED CLAUDE ACTION

1. **Run the preview on production records**: `py -3 scripts/render_preview.py productive-linkedin-production-v1` to see all 14 records and verify the fixture analysis holds. The task asks for "at least eight records"; the fixtures provide 3.

2. **Check for the hi-jacob defect in production**: The Rachel Okafor fixture demonstrates the defect class. If production records carry this defect, the generated copy is defeated by the fallback on those records. The detection caught it in the fixture; verify it catches it in production.

3. **Check for the four-profitability-questions defect**: The task description says this was found in production. The fixtures do not show it (except in the fallback for connected_1/message_2). If it exists in production generated copy, identify which records carry it and regenerate.

4. **The fallback is the floor, and it has a crack**: connected_1 / message_2 fallback is a contextless discovery question. If a lead's copy fails or carries a defect, HeyReach sends this fallback. The fallback's flaw (contextless question) is less damaging than a hi-jacob defect (wrong name), but it is still a flaw. Consider whether the fallback should be rewritten to match the generated copy's pattern (soft offer, no question).

5. **The generated copy usually clears the floor**: In 2 of 3 fixture records, the generated copy is better than the fallback on 4 of 5 steps. This is the intended outcome. The generation pipeline is working when it does not produce defects.

6. **The two branches are different lengths, and that is correct**: The already-connected branch has 4 messages; the not-yet-connected branch has 3 messages after connection. Both branches share li2..li4. This is intentional per the graph structure.
