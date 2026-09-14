#!/usr/bin/env python3
"""TASK-066: Hand-classified labels for 100 unknown replies.

Rules:
- positive: unambiguous interest (wants to meet, asks for info/demo, accepts connection with intent)
- negative: clear refusal (not interested, no thanks, not needed)
- not_now: deferral with a time signal (try later, too busy now, check back in Q1)
- not_relevant: wrong person, left company, not in that field
- unknown: genuinely ambiguous (just "thanks", emoji, greeting, unclear)

Conservative: when in doubt, unknown. A wrong positive is worse than an honest unknown.
"""

# Each entry: (index_in_sample, label, reason)
# Index is 1-based matching the sample output

HAND_LABELS = {
    1: ("positive", "asks for more information to share with partners"),
    2: ("not_relevant", "retired, not working anymore"),
    3: ("unknown", "just 'Thanks' - acknowledgment only"),
    4: ("positive", "wants to organize something next week"),
    5: ("positive", "Let's connect - accepting connection"),
    6: ("unsubscribe", "Croatian: 'please stop sending me messages'"),
    7: ("unknown", "emoji only - thumbs up"),
    8: ("unknown", "just a greeting 'how are you doing'"),
    9: ("negative", "not a burning issue at the moment"),
    10: ("unknown", "not active on LinkedIn, no signal either way"),
    11: ("unknown", "asking about the event, not responding to pitch"),
    12: ("negative", "Not for now, thanks for messages - polite refusal"),
    13: ("negative", "implementing SAP/PowerBI, declined for now"),
    14: ("not_relevant", "not in that field"),
    15: ("negative", "have own in-house solution"),
    16: ("unknown", "was using Productive at previous company, no current signal"),
    17: ("negative", "no interest"),
    18: ("negative", "No, thank you"),
    19: ("unknown", "just 'Interesting' - ambiguous"),
    20: ("unknown", "networking blurb, no response to pitch"),
    21: ("unknown", "just 'Hi there'"),
    22: ("not_relevant", "not allowed to disclose, aim higher up"),
    23: ("unknown", "just 'Thanks for sharing'"),
    24: ("unknown", "Croatian: thanks and offering help, no buying signal"),
    25: ("not_now", "locked into competitor, Let's talk in January"),
    26: ("not_now", "on sabbatical, will reach out in future"),
    27: ("unknown", "just 'Thanks'"),
    28: ("not_relevant", "Portuguese: don't work at SONDA"),
    29: ("positive", "Croatian: can you tell me more information"),
    30: ("not_now", "let's reconnect once EPM implementation completed"),
    31: ("positive", "Croatian: see space for collaboration, glad to"),
    32: ("negative", "no requirement for AI-driven workflow automation"),
    33: ("positive", "happy to connect"),
    34: ("not_relevant", "don't work at THG anymore"),
    35: ("positive", "Croatian: yes, send me info"),
    36: ("unknown", "emoji only"),
    37: ("positive", "didn't see emails, but worth a call in new year"),
    38: ("negative", "company sold operations, no window for a call"),
    39: ("negative", "one-person company, don't need external help"),
    40: ("negative", "completely off my radar"),
    41: ("negative", "not in a position right now to work on this"),
    42: ("not_relevant", "Not at Brevo anymore"),
    43: ("negative", "we compete - they built their own solution"),
    44: ("positive", "always up for connecting"),
    45: ("unknown", "It's great. Discover new stuff - unclear what 'it' refers to"),
    46: ("negative", "Croatian: we already have Productive for 3+ years"),
    47: ("unknown", "describing current subscription, no clear signal"),
    48: ("positive", "happy to connect"),
    49: ("unknown", "I'm not sure - ambiguous"),
    50: ("not_relevant", "handled by P&G, main sponsor"),
    51: ("negative", "quite well structured but not in one tool"),
    52: ("negative", "good grip on financials, pretty tight ship"),
    53: ("unknown", "No worries, Productive is muy perfecto - ambiguous"),
    54: ("positive", "gives specific availability for meeting"),
    55: ("not_relevant", "in between jobs now"),
    56: ("unknown", "just 'Tks'"),
    57: ("negative", "No, thanks"),
    58: ("positive", "Croatian: sounds excellent, yes of course"),
    59: ("unknown", "describing payables process, no clear signal"),
    60: ("unknown", "just 'Will do, thanks'"),
    61: ("unknown", "'This is not hinge' - unclear meaning"),
    62: ("negative", "focused on ERP stabilisation, other priorities"),
    63: ("not_relevant", "leaving Manserv"),
    64: ("negative", "scattergun approach, wide of the mark"),
    65: ("negative", "not something I have decision-making authority for"),
    66: ("positive", "yes sure!"),
    67: ("unknown", "'I am not' - incomplete, ambiguous"),
    68: ("negative", "no idea what problem software solves, pivoted"),
    69: ("negative", "already answered colleagues, not the best person"),
    70: ("positive", "scheduled demo for 6/29 at 9:30 am CT"),
    71: ("negative", "no, thanks"),
    72: ("positive", "Croatian: yes, send it"),
    73: ("negative", "just 'No'"),
    74: ("unknown", "emoji only"),
    75: ("not_relevant", "done working in finance, moved to new department"),
    76: ("unknown", "'in one place :)' - fragment, unclear"),
    77: ("positive", "did not get it, send me that will be great"),
    78: ("not_now", "swamped with client work, keep in mind for down the road"),
    79: ("not_relevant", "don't work at the moment, looking for a job"),
    80: ("negative", "have an internal department for this"),
    81: ("negative", "not something of interest sorry"),
    82: ("unknown", "just an email address - unclear intent"),
    83: ("not_now", "CEO travelling, will forward for review"),
    84: ("positive", "yes sure that will help, uses excel for planning"),
    85: ("negative", "don't have that, boutique company"),
    86: ("not_now", "not in need to purchase but happy to brainstorm"),
    87: ("unknown", "emoji only"),
    88: ("positive", "happy to have a quick chat, gives availability"),
    89: ("positive", "Brilliant! - enthusiastic acceptance"),
    90: ("negative", "don't have a team, just me, sarcastic"),
    91: ("unknown", "emoji only"),
    92: ("positive", "yes please send a pitch deck"),
    93: ("not_now", "not sure if relevant at this moment, will get back"),
    94: ("not_relevant", "in between jobs, don't deal with tools now"),
    95: ("unknown", "Croatian joke about AIs - no signal"),
    96: ("unknown", "emoji only"),
    97: ("unknown", "just 'Thanks Martina'"),
    98: ("negative", "don't have a need for that stack at the moment"),
    99: ("negative", "no tks"),
    100: ("negative", "Afraid not, asks who usually handles this"),
}

# Verify all 100 are labeled
assert len(HAND_LABELS) == 100, f"Expected 100 labels, got {len(HAND_LABELS)}"

# Count distribution
from collections import Counter
label_counts = Counter(v[0] for v in HAND_LABELS.values())
print("=== HAND-LABEL DISTRIBUTION (100 unknown replies) ===")
for label, count in label_counts.most_common():
    print(f"  {label:20s}  {count:3d}  {count}%")

# Save for use by other scripts
import json, os
temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
if not temp:
    temp = os.path.expanduser("~") + os.sep + "AppData" + os.sep + "Local" + os.sep + "Temp"
with open(os.path.join(temp, "task066_hand_labels.json"), "w", encoding="utf-8") as f:
    json.dump(HAND_LABELS, f, indent=2, ensure_ascii=False)
print(f"\nSaved to task066_hand_labels.json")
