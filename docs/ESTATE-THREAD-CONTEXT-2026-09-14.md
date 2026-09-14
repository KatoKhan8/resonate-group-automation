# TASK-067: Thread Context and the Learning Dataset - 2026-09-14

## WHAT THIS IS

Read-only analysis of reply classification with and without thread context. Every reply is classified two ways: `replies.classify(text, model=None)` (the before) and `replies.classify_with_context(reply, outbound)` (the after). The comparison on the SAME replies is the deliverable.

## DATA QUALITY

- **Conversations analysed**: 5864 replies from 26174 conversations
- **Before (without context)**: 4285/5864 unreadable (73.1%)
- **After (with context)**: 4163/5864 unreadable (71.0%)
- **Improved**: 122 replies moved from UNKNOWN to a named category (2.1%)

## BEFORE/AFTER COMPARISON

### Before (without context)

| Category | Count |
| --- | --- |
| unknown | 4285 |
| negative | 1074 |
| positive | 209 |
| not_relevant | 124 |
| not_now | 93 |
| out_of_office | 36 |
| unsubscribe | 31 |
| referral | 12 |

### After (with context)

| Category | Count |
| --- | --- |
| unknown | 4163 |
| negative | 1074 |
| positive | 209 |
| not_relevant | 124 |
| interested | 98 |
| not_now | 93 |
| out_of_office | 36 |
| unsubscribe | 31 |
| objection | 22 |
| referral | 12 |
| meeting_intent | 2 |

## IMPROVEMENT DETAIL

122 replies moved from UNKNOWN to a named category:

| New category | Count |
| --- | --- |
| interested | 98 |
| objection | 22 |
| meeting_intent | 2 |

## ONE NUMBER TO RECONCILE

TASK-058 reported 5,291 replies from 26,113 conversations (~20% per-conversation rate). The TASK-067 probe found 30 CORRESPONDENT messages in 500 conversations (~6%).

**Two different definitions of 'a reply':**

- **TASK-058**: counted every CORRESPONDENT message in the thread as a reply. A conversation with 3 prospect messages counts as 3 replies. The 5,291 is the total CORRESPONDENT messages across all conversations.
- **TASK-067 probe**: counted conversations where the LAST message was from CORRESPONDENT. 30 out of 500 conversations had lastMessageSender=CORRESPONDENT. This is a per-conversation measure, not a per-message one.

**This analysis**: 26113 conversations, 3987 with at least one reply (15.3%), 5266 total reply touches.

**Which is right**: TASK-058's definition (every CORRESPONDENT message is a reply) is the correct one for measuring engagement. The probe's definition (lastMessageSender) measures 'unanswered conversations' - a different question. Both are valid measures but they answer different questions and must not be conflated.

## LEARNING DATASET

Built 76315 rows (one per outbound touch). Written to `C:\Users\Zvonimir\AppData\Local\Temp\task067_dataset/learning_dataset.json`.

Each row carries:
- `conv_id`, `prospect_url_hash` (SHA-256[:12]), `prospect_company_hash` (SHA-256[:12])
- `touch_num`, `total_outbound`, `channel`, `send_time`
- `outbound_text_hash` (SHA-256[:12])
- `replied`, `reply_text_hash` (SHA-256[:12])
- `before_classification`, `before_confidence`
- `after_classification`, `after_confidence`

No PII committed. All identifiers hashed.

## PROVENANCE

Read from `POST /inbox/GetConversationsV2`. 26174 conversations fetched. Classification before: `replies.classify(model=None)`. Classification after: `replies.classify_with_context()`. No write of any kind was made.
