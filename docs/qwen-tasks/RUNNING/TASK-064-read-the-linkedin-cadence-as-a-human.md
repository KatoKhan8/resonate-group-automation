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

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
