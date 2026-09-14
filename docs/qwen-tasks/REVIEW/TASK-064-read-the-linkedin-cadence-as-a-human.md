# TASK-064 - Read the LinkedIn cadence as a human would, on both branches

## WHY

`productive_li_heavy_v1` is six LinkedIn activities over three weeks and the
graph carries four message slots plus a connection note. A prospect walks ONE
of two branches. Nobody has read both branches end to end since the copy was
regenerated.

The defect that started this whole effort was found exactly this way: four
messages asking the same profitability question.

## THE TWO BRANCHES, AND THEY MUST BE READ SEPARATELY

    already connected   connected_1 -> connected_2 -> connected_3 -> connected_4
    not yet connected   connection_note -> message_2 -> message_3 -> message_4

Walking the built sequence with `heyreachfactory._plan` gives you the graph;
`scripts/render_preview.py` renders what a person receives, including which
fallback fires when a lead supplies no words.

## WHAT TO PRODUCE

For at least EIGHT records, BOTH branches, and a verdict against each of:

    1  Does the sequence progress WHO -> PROBLEM -> WHAT PRODUCTIVE IS ->
       DIFFERENT ANGLE -> EASY OUT, or does it ask variations of one
       question? Name the job of each message.

    2  Is the product named, and on which step? Estate baseline: li4 names
       Productive in 21 of 50 stored notes. Report your own number.

    3  Does the connection note say WHO IS WRITING and WHY CONNECT, without
       asking a question that needs thought? That is what rung 1 is for.

    4  Is any message a contextless discovery question - "how do you
       currently ensure profitability is visible in your projects?" with no
       preceding context? Quote every instance.

    5  Do the two branches read as the SAME conversation for a person who
       could have walked either? They share `li2`..`li4`, so they should.

    6  When a lead supplies no copy, the FALLBACK fires. Read the eight
       hand-written fallbacks in `config/clients/productive.yaml` as a
       sequence too. They are the floor and they are good - say whether the
       generated copy actually beats them, record by record. **If it does
       not, that is the finding**, and it is a legitimate one.

## OUTPUT

`docs/HEYREACH-CADENCE-READ-<date>.md`. Quote real copy. Sanitise every real
person's name, profile URL and company - use the record id and a role.

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- **NO PROVIDER WRITE.** Reading 599020 is permitted. `--live` on
  `scripts/write_heyreach_sequence.py` is Claude's alone and you must not
  run it under any circumstances.
- Do not fix the copy. REPORT. Claude decides.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 684a88a

**TESTS:** No test suite run. This is a READ-ONLY human review task. The rendering script (`scripts/task064_render_cadence.py`) was executed successfully against campaign 599020 data (read from Claude's worktree, zero provider calls, zero writes). The existing test suite was not modified and no new tests were written because this task produces a review document, not code changes.

**FILES CHANGED:**
- `docs/HEYREACH-CADENCE-READ-2026-09-14.md` (NEW) - The full human read of both branches for all 15 contacts
- `scripts/task064_render_cadence.py` (NEW) - The rendering script that reads from Claude's worktree and outputs both branches per contact

**FINDINGS:**

1. **The generated copy does not progress.** Across all 15 contacts, the generated messages ask variations of the same profitability question. The ladder's six distinct jobs (connection note, first question, different angle, name the product, final follow-up, easy out) are collapsed into one: "ask about profitability." Three pushable contacts (savagebrands-com, mischacommunications-com, mypersonalestatesale-com) each receive four messages that repeat "profitability" without progression.

2. **Productive is named ZERO times in pushable copy.** Across 12 generated messages for the 3 pushable contacts, the product name does not appear. The fallback names it in 1 of 4 messages ("we built productive so budgets, time tracking and resourcing talk to each other. worth a look?"). Paradoxically, the 12 non-pushable contacts whose sequences fire fallbacks have a better chance of the recipient learning what Productive is.

3. **Connection notes never say who is writing.** All 15 generated notes follow "hi [name], i admire how [company] [does something]. let's connect!" without identifying the sender. No name, no company, no role. The fallback ("hi, i work with agencies on project profitability and thought it would be good to connect") is better: it says who without naming a specific person.

4. **Every generated message is a contextless discovery question.** No message builds on the previous one. No message provides context for the next question. The connection note does not set up the first message; the first message does not set up the second.

5. **The two branches are structurally identical from step 2 onward.** li2 fills both connected_1 and message_2, so both branches share the same words from position 2. This is correct by design. But the already-connected branch is worse because it opens with a discovery question from a stranger who has provided no context.

6. **The hand-written fallbacks beat the generated copy on every pushable record.** The fallback sequence progresses: question -> norm ("most agencies...") -> product name -> easy out. The generated sequence repeats: question -> question -> question -> question. The quality floor is above the generated copy.

7. **Root cause:** The `product:` block in `config/clients/productive.yaml` exists and contains the product name, description, and six capabilities. But the generated copy for this campaign was produced before this block was consumed by the prompt. The model had only `angle_wording` and filled the gap by inventing variations of the same question. This is the exact defect documented in the `product:` block's own comment.

8. **12 of 15 contacts are not pushable.** They have missing copy (no approval) or unsupported claims (asserting profitability/resourcing without evidence). Only 3 contacts have complete, supported copy - and all three fail the human read.

**RISKS:**
- Pushing any of the 3 pushable contacts would send four messages that never say what is being offered. The recipient would finish the sequence without knowing what Productive is or why they should care.
- The connection notes make assertions about recipients ("i admire how savage brands drives profitability and growth") that may not be true and are not supported by stored evidence.
- Contact 8 (portsidemarketing-com) claims "as a fellow founder" - an assertion about the sender that may be false.
- Contact 13 (ethoscreate-com) has "our previous discussions" in connected_4 - asserting prior contact that never happened. This was correctly flagged as unsupported.

**RECOMMENDED CLAUDE ACTION:**
1. **Do not push any of the 3 pushable contacts.** Their copy is worse than the fallback.
2. **Regenerate LinkedIn copy for all 15 contacts** with the `product:` block in the prompt context, so rung 4 of the ladder actually names Productive and says what it does.
3. **Regenerate connection notes** to identify the sender (name, company, role).
4. **After regeneration, re-run the human read** using `scripts/task064_render_cadence.py` to verify the new copy progresses and names the product.
5. **The fallbacks remain approved** and can be used as-is until regeneration produces something that beats them.
