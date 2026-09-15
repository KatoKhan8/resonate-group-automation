#!/usr/bin/env python3
"""TASK-108: Hand-labelled sample of the 23.8% 'no pattern matched' bucket.

200 random replies from the 821 that remain unknown after TASK-066/067
patterns were applied. Each reply is labelled by hand into one of:

  genuinely_ambiguous  - truly unclear what the reply means
  non_english          - primarily non-English text
  negative             - clear refusal
  not_relevant         - wrong person, left company, not their area
  not_now              - deferral, bad timing
  positive             - clear interest/request for info
  unsubscribe          - removal request / spam complaint
  referral             - handing somebody on (names a person)
  meeting_intent       - concrete step towards a meeting
  interested           - curiosity without commitment (analysis category)
  competitor           - already using a competing/custom solution
"""
import json
import os
import sys
import tempfile
from collections import Counter

# Hand labels: index (1-based in the sample) -> (label, notes)
# The index matches the printout order from the sampling script.
LABELS = {
    1: ("not_relevant", "seeking employment, no team"),
    2: ("non_english", "Portuguese: 'no sentido, obg'"),
    3: ("genuinely_ambiguous", "acknowledgment: 'That's great'"),
    4: ("non_english", "Croatian: 'Moze, slobodno posaljite'"),
    5: ("not_now", "next year at best"),
    6: ("not_relevant", "dont work customer service anymore"),
    7: ("negative", "HQ already has a solution"),
    8: ("not_relevant", "don't have anything to do with that"),
    9: ("non_english", "German: 'nicht interessiert'"),
    10: ("genuinely_ambiguous", "single word: 'Done!'"),
    11: ("not_relevant", "moved to a new department"),
    12: ("not_relevant", "retired"),
    13: ("negative", "included in Lucanet setup already"),
    14: ("non_english", "Dutch: 'geen interesse'"),
    15: ("not_relevant", "doesn't know who handles it"),
    16: ("genuinely_ambiguous", "greeting: 'Lovely to connect'"),
    17: ("genuinely_ambiguous", "acknowledgment: 'Will do'"),
    18: ("genuinely_ambiguous", "informational: 'All in one at Brightroc'"),
    19: ("not_relevant", "domestic carrier, no IFRS"),
    20: ("referral", "reach to Karim Hamdan team leader"),
    21: ("non_english", "Serbian/Croatian long text"),
    22: ("genuinely_ambiguous", "informational: 'Business Central area'"),
    23: ("not_relevant", "sells crawfish, not consulting"),
    24: ("negative", "'Non interesting! Tks'"),
    25: ("not_now", "end of month, busy"),
    26: ("genuinely_ambiguous", "comment: 'stubborn man'"),
    27: ("non_english", "Croatian text"),
    28: ("negative", "entire team, not in need"),
    29: ("non_english", "Serbian text"),
    30: ("negative", "planning setup works well"),
    31: ("genuinely_ambiguous", "just a domain: 'board.com'"),
    32: ("not_relevant", "seeking employment"),
    33: ("negative", "'we good' + dont deal with that side"),
    34: ("genuinely_ambiguous", "single word: 'Done!'"),
    35: ("genuinely_ambiguous", "single letter: 'T'"),
    36: ("negative", "evaluated Productive, chose Workamajig"),
    37: ("genuinely_ambiguous", "joke: 'Number go up or down'"),
    38: ("non_english", "Croatian: 'Smiri se'"),
    39: ("meeting_intent", "'we can meet online this week'"),
    40: ("genuinely_ambiguous", "informational about current tools"),
    41: ("genuinely_ambiguous", "informational: 'tracking project time'"),
    42: ("positive", "'Pl share the demo video'"),
    43: ("not_relevant", "haven't worked at TikTok in 3 years"),
    44: ("genuinely_ambiguous", "acknowledgment: 'Will do'"),
    45: ("genuinely_ambiguous", "mixed: limited resources, conditional interest"),
    46: ("genuinely_ambiguous", "personal: 'Going well, trying to rest'"),
    47: ("unsubscribe", "'zero interest, STOP'"),
    48: ("genuinely_ambiguous", "informational: 'project manager, freelancing'"),
    49: ("negative", "'we are really good rn!'"),
    50: ("non_english", "German: 'nicht interessiert'"),
    51: ("not_now", "'not something we are looking at needing at the moment'"),
    52: ("genuinely_ambiguous", "single word: 'teamwork'"),
    53: ("non_english", "Croatian: 'Naravno, posalji'"),
    54: ("not_relevant", "'isn't for me but for our partners'"),
    55: ("not_relevant", "company dissolved, seeking own role"),
    56: ("non_english", "Croatian text"),
    57: ("genuinely_ambiguous", "acknowledgment: 'No problem'"),
    58: ("genuinely_ambiguous", "greeting: 'Welcome'"),
    59: ("genuinely_ambiguous", "unclear: 'One place'"),
    60: ("negative", "'Please do not pitch me'"),
    61: ("non_english", "German: 'follow ups sparen'"),
    62: ("genuinely_ambiguous", "expression: 'Oof'"),
    63: ("genuinely_ambiguous", "informational about business model"),
    64: ("genuinely_ambiguous", "incomplete: 'In Monday'"),
    65: ("non_english", "Croatian text"),
    66: ("non_english", "Spanish: 'Gracias'"),
    67: ("non_english", "Croatian greeting: 'Bok Andjela'"),
    68: ("negative", "using Workamajig, fully integrated"),
    69: ("negative", "on Anaplan, all good"),
    70: ("not_now", "'not conducting business'"),
    71: ("genuinely_ambiguous", "already using Productive"),
    72: ("non_english", "German: 'nicht interessiert'"),
    73: ("genuinely_ambiguous", "unclear: 'all together ;)'"),
    74: ("genuinely_ambiguous", "greeting: 'Hola, pleasure to connect'"),
    75: ("not_now", "procurement process needed"),
    76: ("genuinely_ambiguous", "requesting accommodation details"),
    77: ("positive", "'already engaged with Ivan looking at your product'"),
    78: ("non_english", "German: 'ware ich interessiert gewesen'"),
    79: ("genuinely_ambiguous", "already a client"),
    80: ("negative", "'all good, Productive is muy perfecto'"),
    81: ("genuinely_ambiguous", "informational about corporate structure"),
    82: ("not_relevant", "don't work as Finance Director anymore"),
    83: ("not_relevant", "do not work in DPI anymore"),
    84: ("genuinely_ambiguous", "joke: 'Winging it everyday'"),
    85: ("genuinely_ambiguous", "expression: 'smh'"),
    86: ("non_english", "Croatian: 'Moze .. na email'"),
    87: ("non_english", "Croatian: 'hvala na javljaju'"),
    88: ("not_relevant", "no longer work for TikMarketing"),
    89: ("not_relevant", "no longer working for ELF"),
    90: ("negative", "'No, I don't'"),
    91: ("genuinely_ambiguous", "closing: 'Hope that helps'"),
    92: ("non_english", "Croatian: 'ne treba'"),
    93: ("genuinely_ambiguous", "acknowledgment: 'Understood Take care'"),
    94: ("genuinely_ambiguous", "informational about capacity tracking"),
    95: ("not_relevant", "not at KARMAjack any longer"),
    96: ("interested", "'send link to your site, will check it out'"),
    97: ("genuinely_ambiguous", "unclear: 'Both...'"),
    98: ("non_english", "Croatian text"),
    99: ("genuinely_ambiguous", "acknowledgment: 'Seems fair'"),
    100: ("non_english", "Portuguese: 'nao tenho interesse'"),
    101: ("non_english", "French: 'ne m'interesse pas'"),
    102: ("negative", "'I only use SAP'"),
    103: ("genuinely_ambiguous", "single word: 'None'"),
    104: ("genuinely_ambiguous", "polite: liked outreach but no commitment"),
    105: ("negative", "'Sorry I don't I'm afraid'"),
    106: ("non_english", "Serbian/Croatian text"),
    107: ("genuinely_ambiguous", "question: 'usually the first day?'"),
    108: ("non_english", "Croatian: 'pogledacu i javicu se'"),
    109: ("not_relevant", "haven't been with them in 2 years"),
    110: ("interested", "'No - curious !! Let me know!!'"),
    111: ("genuinely_ambiguous", "greeting: 'Glad to e-meet you'"),
    112: ("negative", "developed custom made tool"),
    113: ("negative", "using our own software"),
    114: ("not_now", "'don't think we are ready yet'"),
    115: ("not_now", "can't this month, booked, then holiday"),
    116: ("meeting_intent", "'need an in person demo in Zagreb'"),
    117: ("negative", "'covering by ourselves'"),
    118: ("non_english", "Norwegian/Danish: 'Takk'"),
    119: ("genuinely_ambiguous", "informational: salaried staff, no tracking"),
    120: ("non_english", "Croatian: 'ne radim u poliklinici'"),
    121: ("not_relevant", "being made redundant in April"),
    122: ("genuinely_ambiguous", "greeting: 'Same to you Luka!'"),
    123: ("genuinely_ambiguous", "question about sales numbers"),
    124: ("unsubscribe", "'Stop spamming'"),
    125: ("unsubscribe", "'too intense, I'll report you'"),
    126: ("not_relevant", "just a home loan writer"),
    127: ("genuinely_ambiguous", "acknowledgment: 'Not a problem at all'"),
    128: ("genuinely_ambiguous", "'didn't understand'"),
    129: ("non_english", "Croatian: 'Koristimo jedan uzasan softver'"),
    130: ("genuinely_ambiguous", "answer: 'No, I have not seen'"),
    131: ("non_english", "French: 'ne m'interesse pas'"),
    132: ("genuinely_ambiguous", "informational about their job"),
    133: ("unsubscribe", "'enjoy spamming people'"),
    134: ("non_english", "Spanish: 'estoy jubilado'"),
    135: ("genuinely_ambiguous", "informational: 'delivery and ops!'"),
    136: ("genuinely_ambiguous", "acknowledgment: 'No problem'"),
    137: ("genuinely_ambiguous", "acknowledgment: 'sound powerful! Nice'"),
    138: ("negative", "'they would not agree'"),
    139: ("not_relevant", "'isn't my position or insight'"),
    140: ("not_now", "'once pilot programs completed'"),
    141: ("negative", "'Nop' (variant of nope)"),
    142: ("meeting_intent", "'April would be good to catch up'"),
    143: ("genuinely_ambiguous", "greeting: 'nice to e meet you'"),
    144: ("genuinely_ambiguous", "informational: 'shared with colleague'"),
    145: ("non_english", "Serbian text"),
    146: ("not_relevant", "focused on real estate"),
    147: ("not_now", "'will reach out to you soon'"),
    148: ("meeting_intent", "'catch up around end of March'"),
    149: ("non_english", "Croatian: 'sve dobro'"),
    150: ("genuinely_ambiguous", "conditional: 'something I haven't coded myself'"),
    151: ("interested", "'would love to hear first'"),
    152: ("non_english", "Croatian: 'Uper hvala'"),
    153: ("genuinely_ambiguous", "single word: 'good!'"),
    154: ("not_relevant", "'not on my radar'"),
    155: ("genuinely_ambiguous", "unclear: 'In stones.'"),
    156: ("non_english", "German: 'nicht interessiert'"),
    157: ("interested", "'send a link, happy to check it out'"),
    158: ("not_relevant", "'completely off my radar'"),
    159: ("genuinely_ambiguous", "acknowledgment: 'nice man'"),
    160: ("negative", "own application covers everything"),
    161: ("non_english", "German: 'nicht interessiert'"),
    162: ("referral", "send note to CEO Ryan Handel with email"),
    163: ("not_relevant", "'not with Nadel!'"),
    164: ("non_english", "German: 'nicht interessiert'"),
    165: ("not_relevant", "not the decision maker"),
    166: ("negative", "custom built system"),
    167: ("unsubscribe", "'Please delete me as a contact'"),
    168: ("unsubscribe", "spam complaint, threatening to block"),
    169: ("referral", "message Ashish Varghese with title"),
    170: ("negative", "'Happy with the setup we have'"),
    171: ("genuinely_ambiguous", "informational: 'one tool covers it all'"),
    172: ("genuinely_ambiguous", "informational about Excel in Argentina"),
    173: ("not_relevant", "Landy has nothing to do with Telecoms"),
    174: ("non_english", "German: 'nicht interessiert'"),
    175: ("negative", "specialist departments handle this"),
    176: ("referral", "'just connect with him'"),
    177: ("positive", "'Pls send me your proposal'"),
    178: ("not_relevant", "'Not on my radar, no'"),
    179: ("not_relevant", "not in a position to make decisions"),
    180: ("genuinely_ambiguous", "constraint: 'need to convince my company'"),
    181: ("non_english", "Croatian: 'bravo, tako se radi sales'"),
    182: ("negative", "'Unfortunately not'"),
    183: ("non_english", "German: 'nicht interessiert'"),
    184: ("genuinely_ambiguous", "acknowledgment: 'Thanks for reaching out'"),
    185: ("non_english", "Polish: 'nie jestem zainteresowany'"),
    186: ("referral", "'reach out to the main switchboard'"),
    187: ("referral", "reach out head of FP&A with email"),
    188: ("genuinely_ambiguous", "informational about current tools"),
    189: ("genuinely_ambiguous", "unclear: 'it is Pavel'"),
    190: ("genuinely_ambiguous", "informational about Cloudflare"),
    191: ("genuinely_ambiguous", "unclear: 'no before :)'"),
    192: ("genuinely_ambiguous", "greeting: 'Welcome to my network'"),
    193: ("non_english", "German: 'nicht interessiert'"),
    194: ("non_english", "French: 'ne m'interesse pas'"),
    195: ("genuinely_ambiguous", "just a URL"),
    196: ("not_now", "'Let's reconnect in 2026'"),
    197: ("genuinely_ambiguous", "acknowledgment: 'Understood'"),
    198: ("genuinely_ambiguous", "acknowledgment: 'Yeah that's fine'"),
    199: ("negative", "'Planning set up is working well!'"),
    200: ("non_english", "Dutch: 'geen interesse'"),
}


def main():
    assert len(LABELS) == 200, f"Expected 200 labels, got {len(LABELS)}"

    counts = Counter(label for label, _ in LABELS.values())
    total = len(LABELS)

    print(f"HAND-LABELLED SAMPLE: n={total}")
    print(f"{'='*60}")
    for cat, count in counts.most_common():
        pct = round(count / total * 100, 1)
        print(f"  {cat:30s} {count:5d}  {pct:5.1f}%")

    # Genuinely unclassifiable vs classifiable
    unclassifiable = counts.get("genuinely_ambiguous", 0) + counts.get("non_english", 0)
    classifiable = total - unclassifiable
    print(f"\n  Genuinely unclassifiable: {unclassifiable} ({round(unclassifiable/total*100,1)}%)")
    print(f"  Classifiable:             {classifiable} ({round(classifiable/total*100,1)}%)")

    # Actionable categories (could be caught by new patterns)
    actionable = sum(counts.get(c, 0) for c in [
        "negative", "not_relevant", "not_now", "positive",
        "unsubscribe", "referral", "meeting_intent", "interested"
    ])
    print(f"  Actionable (pattern-able): {actionable} ({round(actionable/total*100,1)}%)")


if __name__ == "__main__":
    main()
