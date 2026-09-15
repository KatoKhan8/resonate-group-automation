PRIORITY: P0
DEPENDS: 

# TASK-126 - build a sequence that carries five variants per node

## WHAT IS NOW PROVEN, AND WHY THIS TASK EXISTS

TASK-121 walked the whole HeyReach account and Claude verified it
independently on a fresh sample:

    campaigns carrying multi-message nodes   67 of 83
    copy-bearing nodes with >1 message      243 of 289
    MESSAGE            up to 20 entries
    CONNECTION_REQUEST up to 15
    INMAIL             up to  5
    most common non-zero count: 3

**The provider carries variants per node. The question is closed.** Five arms
is well inside what this estate already does routinely.

Our campaign 599020 carries exactly ONE message on every copy-bearing node -
one of ~14 such campaigns in an account where 67 do more. **The constraint was
never HeyReach. It is that our factory has never built a multi-message node.**

## WHAT TO BUILD

`src/heyreachfactory.py` builds the sequence payload. Today each copy-bearing
node gets one message. Make it carry the variant set.

1. **Trace the path from `variantgen` output to `payload.messages`.** Existence
   is not function - find where a variant list would have to become a list of
   messages, and prove whether anything does it today. The copy lives in
   `payload.messages` and NOWHERE else; `message`, `note`, `text` and `body`
   do not exist on this graph and return a confident empty.
2. **Build the node from N variants**, preserving order, so arm identity is
   positional and a later readback can say which arm a reply came from.
3. **A FAILING TEST FIRST**, pinning that a node built from N variants carries
   N entries in `payload.messages`. Then make it pass.
4. **Respect the ceilings**: 20 for MESSAGE, 15 for CONNECTION_REQUEST, 5 for
   INMAIL. Refuse rather than truncate - silently dropping an arm would make
   an experiment report on arms that never sent.
5. **`validate_sequence_for_write` must accept the multi-message node.** Check
   what it does today with a list of more than one, and whether
   `_check_words` and `_words_of` handle each entry. An INMAIL entry is an
   object with subject+body; every other node's entry is a string, and the
   provider rejects the wrong one.

## WHAT NOT TO DO

- **NO PROVIDER WRITES.** Build and validate the payload, do not send it.
  Rewriting 599020's sequence is Claude's and needs the copy to pass a human
  read first.
- Do not pad to five by repeating a variant. Four honest arms beat five where
  one is a copy - and the structural diversity check would refuse it anyway,
  correctly.
- Do not weaken the diversity check to let a set through. If it refuses the
  arms, the arms are the problem.
- Hash prospect identifiers in anything tracked.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

The factory change, the failing-test-first evidence, a built payload for a
real record written to a file with identifiers hashed, and the readback shape
that would confirm it. State plainly how many arms the current generator
actually produces per node for that record - if it is four because
`observation_led` has no licensed evidence, say four and say why.
