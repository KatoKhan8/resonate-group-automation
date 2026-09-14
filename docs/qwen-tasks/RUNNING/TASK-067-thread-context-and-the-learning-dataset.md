# TASK-067 - The replies are readable; the classifier is reading them alone

## WHAT CLAUDE ALREADY MEASURED - START FROM THIS, DO NOT REDO IT

Probed `POST /inbox/GetConversationsV2` directly, 500-800 conversations:

    conversations sampled              500
    TRUNCATED (totalMessages > len)      0
    messages seen                     1235
    sender values        ME 1205, CORRESPONDENT 30
    EMPTY BODY                           0

**So it is NOT a provider access failure, NOT an extraction failure, NOT a
schema failure and NOT empty content.** The reply text is present, complete
and correctly extracted. Categories A, B, C and E are closed by measurement.

Classifying 36 real CORRESPONDENT replies with `replies.classify(model=None)`:

    unknown 28,  negative 7,  not_relevant 1      -> 78% unreadable

And here is what the 28 actually are:

    "No"
    "Show me"
    "Doing what?"
    "Hi <name>, A fit for what exactly?"
    "Hi. I am in no position to roll out such platform to my team."
    "Hello? What is the meaning for this message"
    "Hello, I have not seen any emails from you. What is it you are offering?"

Two DIFFERENT failures are mixed in there, and they need different fixes:

**1. OUTRIGHT MISSES.** "No" is negative. "Show me" is interested. "I am in
no position to roll out such platform to my team" is a clear decline. The
classifier simply has no pattern for them. These are cheap wins.

**2. GENUINELY CONTEXT-DEPENDENT.** "Doing what?", "A fit for what exactly?"
and "What is it you are offering?" are not ambiguous because the classifier
is weak. They are ambiguous BECAUSE THEY ARE REPLIES. Their meaning lives in
the message they answer, and classifying them alone is the actual defect.

TASK-066 added patterns and moved 73.6% to 68.2%. That is the ceiling of the
patterns-only approach and it is why this task exists.

## GOAL 1 - CLASSIFY WITH THE THREAD, NOT THE SENTENCE

Build the classification input from context:

    the outbound message being replied to
    the prospect's reply
    the preceding thread where it exists

`heyreach.direction`, `is_from_correspondent` and `inbound_messages` already
separate the sides. The conversation object carries the whole thread in
`messages`, each with `sender` (ME or CORRESPONDENT), `body` and `createdAt`.
Everything needed is already in one payload.

Report the unreadable rate with context versus without, on the SAME replies.
That comparison is the deliverable.

## GOAL 2 - THE TAXONOMY

Classify conservatively into:

    POSITIVE  INTERESTED  MEETING_INTENT  REFERRAL  NOT_NOW  OBJECTION
    NEGATIVE  UNSUBSCRIBE  OOO  AUTO_REPLY  WRONG_PERSON  NEUTRAL  UNKNOWN

**Do not force UNKNOWN into another class.** An UNKNOWN pauses the account
and is safe. A wrong POSITIVE lets automation continue at somebody who said
no. Report precision on a hand-labelled held-out set, not just the reduction.

## GOAL 3 - THE LEARNING DATASET

One row per outbound touch, joined to its reply where one exists:

    PROSPECT   lead id, first name, title, company, domain, LinkedIn URL,
               persona/segment where available
    CAMPAIGN   provider, campaign id and name, sequence, variant, sender,
               channel
    TOUCH      every outbound touch preceding the reply, the rendered message
               actually sent, touch number, timestamp, delay from previous,
               subject where applicable, and whether it was a connection
               request, message or InMail
    REPLY      exact text, timestamp, thread id, which outbound message it
               answered where determinable
    OUTCOME    the taxonomy above

Persist it somewhere re-derivable. **Do not commit prospect PII** - no names,
no emails, no LinkedIn URLs in git. Hash the identifier and say so.

## GOAL 4 - RERUN AND REPORT

Re-run the TASK-058 analysis over the corrected dataset and report:

    TOTAL TOUCHES / CONVERSATIONS / REPLIES
    REPLY TEXT RECOVERED
    UNREADABLE BEFORE / AFTER
    POSITIVE / MEETING_INTENT / REFERRAL / NOT_NOW / OBJECTION / NEGATIVE /
    UNSUBSCRIBE / OOO_AUTO / WRONG_PERSON / NEUTRAL / UNKNOWN

## ONE NUMBER TO RECONCILE

TASK-058 reported 5,291 replies from 26,113 conversations - about 20%. This
probe found 30 CORRESPONDENT messages in 500 conversations - about 6%. Those
disagree. Establish which definition of "a reply" each used and say which is
right. A reply rate that changes by 3x depending on the definition is not a
reply rate yet.

## DO NOT

- Do not optimise any copy against the current 0.233% positive rate. Until
  the unreadable population is resolved it is a LOWER BOUND from a biased
  sample, not a rate.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No provider write. Reads only.
- Do not commit prospect reply text verbatim beyond a handful of paraphrased
  illustrations with no name or company attached.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
