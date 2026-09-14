#!/usr/bin/env python3
"""TASK-076: Measure taxonomy precision and recall against hand labels.

Draws at random from the estate (UNKNOWN replies the taxonomy did NOT match),
hand-labels each one, then compares the taxonomy's labels against mine.

The taxonomy (TASK-074) runs ONLY when production rules return UNKNOWN.
So the sample frame is the 3869 UNKNOWN replies from the estate.

Sample method:
  - ALL 63 replies the taxonomy labeled (for precision)
  - 200 drawn at random (seed=42) from the 3806 the taxonomy did NOT label
    (for recall - these measure what the taxonomy missed)
  - Total: 263 replies hand-labeled

Hand labels: interested, meeting_intent, objection, or none.
'none' means the reply is genuinely unknown, a refusal, not relevant,
or otherwise not fitting any taxonomy category.

READS ONLY. No provider calls.
"""
import json
import os
import random
import sys
import tempfile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src import replies  # noqa: E402


# ---------------------------------------------------------------------------
# Hand labels for the 63 taxonomy-matched replies (precision set).
# These are the replies the taxonomy labeled INTERESTED, MEETING_INTENT,
# or OBJECTION.  I read each one and assigned what I believe is correct.
#
# Label key:
#   interested      - genuine interest/curiosity about the product/service
#   meeting_intent  - concrete step towards scheduling a meeting
#   objection       - specific stated constraint (budget, time, resources)
#   None            - none of the above (refusal, not relevant, ambiguous)
# ---------------------------------------------------------------------------

HAND_LABELS_TAXONOMY_MATCHED = {
    # --- INTERESTED as labeled by taxonomy ---
    1:  ("interested",    "'Show me' - clear request to see the product"),
    2:  ("interested",    "'Interesting' - bare word, ambiguous but taxonomy treats as interest"),
    3:  ("interested",    "'actually interesting' - genuine engagement"),
    4:  (None,            "says 'seems interesting' but then says not working there, not the best time - decline"),
    5:  ("meeting_intent","'Lets hop on a call... pick a time' - concrete meeting step"),
    6:  ("interested",    "'Interesting' - bare word"),
    7:  ("interested",    "'Interesting' - bare word"),
    8:  ("interested",    "'Curious what you have in mind' - genuine curiosity"),
    9:  (None,            "'Very interesting product. I'm not in need to purchase' - polite decline"),
    10: (None,            "'Might be interesting to have a look' over summer - deferral, not commitment"),
    11: ("interested",    "'could you show me your product?' - clear request"),
    12: ("interested",    "'Interesting' - bare word"),
    13: ("interested",    "'curious to what you have to say! Let me know' - genuine interest"),
    14: ("interested",    "'Can you send over a deck? ... curious if there is expertise' - clear interest"),
    15: (None,            "complaining about inbox volume, 50 pitches - not interested in product"),
    16: (None,            "'wouldn't call it a major pain point' - vague acknowledgment, no interest signal"),
    17: ("interested",    "'Interesting' - bare word"),
    18: (None,            "'sound interesting, but I'm pretty swamped... don't have bandwidth' - decline"),
    19: (None,            "'sounds super interesting... Don't think it would be suitable for my line of work' - decline"),
    20: (None,            "'working on an interesting project for one of our clients' - 'interesting' describes THEIR project, not ours"),
    21: (None,            "'Curious about the comment on timesheets' + 'I don't work at Rentslam anymore' - not relevant"),
    22: (None,            "'Out of curiosity, why target me then?' - defensive, not product interest"),
    23: (None,            "'I appreciate your curiosity, but I'm unclear about the purpose' - declining"),
    24: (None,            "talking about RIT campus in Zagreb - completely off-topic"),
    25: ("objection",     "'Too expensive' - clear budget objection"),
    26: (None,            "'I am curious is your agency hiring?' - job inquiry, not product interest"),
    27: (None,            "'cooperation in the future is always interesting' - vague networking, no commitment"),
    28: ("objection",     "'I don't have time to fill this information' - time constraint"),
    29: ("meeting_intent","'better to speak in few weeks time. pl send invite in 2nd week of may' - concrete scheduling"),
    30: (None,            "'we don't wanna interesting in additional system' - broken English decline"),
    31: (None,            "'sound very interesting indeed. I am currently on PTO' - deferral"),
    32: (None,            "'interesting product, but I do not longer work at Metraco' - not relevant"),
    33: (None,            "'I am not a CFO but work in CFO Advisory' - wrong person clarification"),
    34: (None,            "'It's interesting tks for hsare it' - bare acknowledgment"),
    35: ("objection",     "'no time for this right now' - time constraint"),
    36: (None,            "'Sounds very interesting, however... everything is pretty structured and fixed' - decline"),
    37: ("interested",    "'That's pretty interesting. How much of the work gets outsourced?' - genuine engagement"),
    38: ("objection",     "'dont have time available' - time constraint"),
    39: ("interested",    "'curious how it compares to Smartsheet and ClickUp' - genuine product interest"),
    40: (None,            "'pretty busy... I had never heard before of the Festival but it sounds very interesting' - vague, about an event"),
    41: ("interested",    "'Yes please send It to me. It sounds really interesting' - clear request"),
    42: (None,            "'review my schedule... It looks very interesting, so I'll come back to you' - deferral"),
    43: (None,            "'Sound really interesting, but I'm still not sure if I can go' - decline"),
    44: (None,            "'interesting for us. We already cemented plans to be in Spain' - decline"),
    45: ("interested",    "'sounds like a very interesting event... I'd be happy to take a look' - genuine interest"),
    46: ("interested",    "'could be interesting. Please share a quick overview' - request for info"),
    47: ("objection",     "'we don't have the budget right now' - clear budget objection"),
    48: ("interested",    "'Im curious about new tools' + 'Do you have a demo' - genuine interest"),
    49: ("interested",    "'I am curious about this tool but I am just exploring' - genuine interest"),
    50: ("meeting_intent","'let's schedule a meeting for next week. Im available Monday or Tuesday morning' - concrete"),
    51: (None,            "'sounds fun and interesting, but I'm more focusing on other sectors' - decline"),
    52: ("interested",    "'Show me what you have' - clear request"),
    53: ("interested",    "'I would appreciate the overview if there's something you can share' - request for info"),
    54: ("meeting_intent","'I definitely am. I'm abroad now - can we talk in the 2nd week of March?' - concrete"),
    55: (None,            "'looks quite interesting; however, this is not something we are looking to pursue' - decline"),
    56: ("interested",    "'That sound interesting I understand I have to pay for this Programme isnt it?' - pricing inquiry"),
    57: (None,            "'Non interesting! Tks' - this is NOT interested (non = not in multiple languages)"),
    58: ("interested",    "'It is, of course, interesting. Guess I need an in person demo in Zagreb' - genuine + demo request"),
    59: ("meeting_intent","'Sure, let's set up a short call the second week of January' - concrete"),
    60: (None,            "'unlikely to commit to system and process changes. More of a personal curiosity' - explicitly not buying"),
    61: (None,            "'our finance team has a smooth process... everything flows good' - no need"),
    62: ("objection",     "'We don't have budget till 2Q 2026' - clear budget objection"),
    63: ("interested",    "'Yes, sounds super interesting' + gives contact details - clear interest"),
}


# ---------------------------------------------------------------------------
# Hand labels for the 200 random UNKNOWN replies (recall set).
# These are replies the taxonomy did NOT label (they stayed UNKNOWN).
# I read each one and decide whether any taxonomy category applies.
# ---------------------------------------------------------------------------

HAND_LABELS_RANDOM_UNKNOWN = {
    64:  (None,            "promoting their own event"),
    65:  (None,            "asking what we're suggesting - clarification, no interest signal"),
    66:  (None,            "emoji only"),
    67:  (None,            "'Not relevant'"),
    68:  (None,            "'I don't think we're in need of these services'"),
    69:  (None,            "emoji only"),
    70:  (None,            "'check my profile and rethink' - annoyed"),
    71:  (None,            "'Have we spoken before?' - clarification"),
    72:  (None,            "'its working fine for now'"),
    73:  (None,            "emoji only"),
    74:  (None,            "'sorry for my late response' - no content"),
    75:  (None,            "'let's review in July 26' - deferral"),
    76:  (None,            "'happy to connect' - networking only"),
    77:  (None,            "'Ok'"),
    78:  (None,            "'I no longer work at [company]'"),
    79:  (None,            "Croatian: already in contact about partnership"),
    80:  (None,            "emoji only"),
    81:  (None,            "'I'm not sure to be honest'"),
    82:  (None,            "'No, thanks'"),
    83:  (None,            "'home grown TMS' - have own system"),
    84:  ("interested",    "'let me know how to reconnect' - wants to reconnect"),
    85:  ("interested",    "'Happy to hear more about your platform' - explicit interest"),
    86:  (None,            "'I have retired'"),
    87:  (None,            "'not involved with financial activities' - wrong person"),
    88:  (None,            "'not a priority for me right now'"),
    89:  (None,            "'I'm no longer in [company]'"),
    90:  (None,            "'No'"),
    91:  (None,            "'Thanks, you too'"),
    92:  (None,            "Croatian: looking for employer, can't collaborate"),
    93:  (None,            "'not the right point of contact'"),
    94:  (None,            "'not directly responsible' - redirect"),
    95:  (None,            "emoji only"),
    96:  (None,            "'I'm in marketing so it's a small sliver'"),
    97:  (None,            "'always of interest but... in the midst of a planning and forecasting tool' - deferral"),
    98:  (None,            "'happy to connect' - networking only"),
    99:  (None,            "'third person from your sales team' - annoyed"),
    100: (None,            "'isn't something I'm looking to explore at the moment'"),
    101: (None,            "'Not for now'"),
    102: (None,            "Danish: 'not interested'"),
    103: (None,            "emoji only"),
    104: (None,            "'we have automated almost all of our reporting'"),
    105: (None,            "emoji only"),
    106: (None,            "greeting only"),
    107: (None,            "'happy to connect'"),
    108: (None,            "'i will :) good luck'"),
    109: (None,            "'No'"),
    110: (None,            "'already sorted'"),
    111: (None,            "'Thanks'"),
    112: (None,            "'no one of your team has contacted me yet'"),
    113: (None,            "'What are your goals? What would you like to know?' - clarification"),
    114: (None,            "Swedish: 'not interested'"),
    115: ("interested",    "'can you elaborate?' - asking for more about the offering"),
    116: (None,            "email redirect to colleague"),
    117: (None,            "'we had the call, Sven was great!' - already happened"),
    118: (None,            "'I'll take a look and give you a message if I'm wanting to know more' - non-committal"),
    119: (None,            "'happy to connect'"),
    120: (None,            "'Love it!' - no clear referent"),
    121: (None,            "'I don't attend many events as attendee'"),
    122: (None,            "'we do everything internally'"),
    123: (None,            "'I left [company]'"),
    124: (None,            "'I would leave it for now'"),
    125: (None,            "'Let's keep in touch' - networking"),
    126: (None,            "'Have moved on'"),
    127: (None,            "pitching their own services"),
    128: (None,            "'We are a GHL agency' - info about themselves"),
    129: (None,            "'happy to connect'"),
    130: (None,            "'I don't think I'm in contact with anyone from your team'"),
    131: (None,            "'I have no clue what... you're talking about' + 'I don't work at [company] anymore'"),
    132: (None,            "pitching their own product"),
    133: (None,            "'We have an in-house built bespoke system'"),
    134: (None,            "'I did not get any e-mail... Can this be sent again' - admin request"),
    135: (None,            "'sent it to my partner... if he sees we can participate I will let you know'"),
    136: (None,            "'We will review whether this is of interest to us' - non-committal"),
    137: (None,            "'Let's stay connected and perhaps one day' - deferral"),
    138: ("objection",     "'we are restricted by Marriott as to programs used' - corporate constraint"),
    139: (None,            "'really happy with the software we have'"),
    140: (None,            "'We were using [product] at [company]' - past tense"),
    141: (None,            "'stop, ty'"),
    142: (None,            "'I am not sure I am the right audience'"),
    143: (None,            "'these messages are intense' - annoyed"),
    144: (None,            "'We have it handled'"),
    145: ("objection",     "'not big enough to be investing big amounts of money in systems' - budget/size"),
    146: (None,            "'both handled in [product]'"),
    147: (None,            "'system change is not in our roadmap'"),
    148: (None,            "'I'm the one that manages the budget' - describing role"),
    149: ("interested",    "'i don't understand what you want. explain deal' - asking for explanation"),
    150: (None,            "'check in around July is fine' - deferral"),
    151: (None,            "'currently we have that in one place. Our IT guy made that'"),
    152: (None,            "'No'"),
    153: (None,            "'I already have a solution in place'"),
    154: ("interested",    "'Do you work as part of a consultancy service?' - asking about offering"),
    155: (None,            "'No, sorry'"),
    156: (None,            "'We have got a quite different proposition' - redirecting"),
    157: (None,            "'No'"),
    158: (None,            "'we are clear about all these things, because of our own software'"),
    159: (None,            "'I don't think we are ready yet' - vague, not a specific constraint"),
    160: (None,            "'I don't work for [company]'"),
    161: ("interested",    "'What do you have in mind?' - asking about offering"),
    162: ("interested",    "'Why not? I'm always open' - open to hearing more"),
    163: (None,            "'Thanks'"),
    164: (None,            "'I have just left [company]... I couldn't move forward'"),
    165: (None,            "'At this stage I will not proceed as yet'"),
    166: (None,            "'won't be able to participate unfortunately'"),
    167: (None,            "'Thanks'"),
    168: (None,            "Slovenian: 'Thank you very much'"),
    169: (None,            "greeting only"),
    170: (None,            "'I'm not an agency... Not sure this would be a good fit'"),
    171: (None,            "'I am not the relevant person'"),
    172: (None,            "'That is great. Thanks for connecting!'"),
    173: (None,            "Croatian: 'I don't work for [company] anymore'"),
    174: (None,            "'We don't have any investment plan for this year'"),
    175: (None,            "'I don't have anything to do with that'"),
    176: ("interested",    "'is this a career opportunity or a product/demo session?' - asking for clarification about offering"),
    177: (None,            "emoji only"),
    178: (None,            "Spanish: 'not interested'"),
    179: (None,            "greeting only"),
    180: (None,            "'being made redundant in April' - can't consider"),
    181: (None,            "'Between jobs at the moment'"),
    182: (None,            "hostile"),
    183: (None,            "'let's reconnect once the EPM implementation is completed' - deferral"),
    184: (None,            "French: acknowledgment"),
    185: (None,            "'Pleased to connect'"),
    186: (None,            "'Thanks, you too'"),
    187: (None,            "emoji only"),
    188: ("interested",    "'How is this different than a claude agent' - product question"),
    189: (None,            "'I no longer work at [company]'"),
    190: (None,            "'Not yet' - no clear signal"),
    191: (None,            "French: 'not interested'"),
    192: (None,            "'not in a position to help at this time'"),
    193: (None,            "'we are already using [product]'"),
    194: (None,            "'No, thank you'"),
    195: (None,            "'I'm a free-lancer... don't know how they track'"),
    196: (None,            "'sure' - ambiguous, no clear signal"),
    197: (None,            "'happy to connect'"),
    198: (None,            "'happy to connect'"),
    199: ("interested",    "'Will be good to receive summary of your findings' - request for info"),
    200: (None,            "'that is drive by our Trance headquarters' - info about current setup"),
    201: (None,            "'No, thanks'"),
    202: (None,            "'I'm in a good place and deliver projects successfully'"),
    203: (None,            "'Hi there'"),
    204: (None,            "emoji only"),
    205: (None,            "'No, thanks'"),
    206: (None,            "'I'm not involved in evaluating planning software'"),
    207: (None,            "'I'm actually looking for employment'"),
    208: ("interested",    "'I will have a look in the morning or later this evening' - will review"),
    209: (None,            "emoji only"),
    210: (None,            "'Thanks'"),
    211: (None,            "emoji only"),
    212: (None,            "'One place' - fragment"),
    213: (None,            "'we already have perfect platform'"),
    214: (None,            "'We are Happy with the setup we have'"),
    215: (None,            "emoji only"),
    216: (None,            "'No, thank you'"),
    217: (None,            "'No idea what you are talking about'"),
    218: (None,            "'I have already been contacted by one of your colleagues'"),
    219: ("interested",    "Serbian: 'sounds interesting, send it anyway and I'll take a look'"),
    220: (None,            "'happy to connect'"),
    221: (None,            "'happy to connect'"),
    222: (None,            "'Nope'"),
    223: (None,            "'We have an entire team... Not in need of more consulting help'"),
    224: (None,            "Serbian: closed agency, now consulting with HubSpot"),
    225: (None,            "domain expertise commentary, not responding to pitch"),
    226: (None,            "'Thanks'"),
    227: (None,            "'happy to connect'"),
    228: (None,            "'happy to connect'"),
    229: (None,            "networking blurb"),
    230: (None,            "'no interest on your product at this point'"),
    231: (None,            "'Sure, no problem'"),
    232: ("objection",     "'we are restricted by Marriott as to programs used' - corporate constraint"),
    233: (None,            "Polish: 'not interested'"),
    234: (None,            "'Thanks'"),
    235: (None,            "'good to stay in touch... looking into organizing some nice events' - networking"),
    236: (None,            "feedback about pitch quality"),
    237: (None,            "'Thanks'"),
    238: (None,            "'Currently it's not' - not interested"),
    239: (None,            "'happy to connect'"),
    240: (None,            "'not of interest!'"),
    241: (None,            "'Its actually handled really well'"),
    242: (None,            "'I am not with [company] anymore'"),
    243: (None,            "'Not for now. If we notice this need, I will let you know'"),
    244: (None,            "'Not plan for this semester'"),
    245: (None,            "'we already use [product] and we're very satisfied'"),
    246: (None,            "'No, thanks'"),
    247: (None,            "'Not sure I'm ready to discuss profitability tracking'"),
    248: (None,            "'I'll be out of town early May'"),
    249: (None,            "'No.'"),
    250: (None,            "'[company] was dissolved... I'm currently looking for my own role'"),
    251: (None,            "emoji only"),
    252: (None,            "greeting only"),
    253: (None,            "'Spread' - unclear"),
    254: (None,            "'Both. Have a nice day.' - unclear"),
    255: ("interested",    "'I don't know what it is. Please feel free to pitch it' - open to hearing pitch"),
    256: (None,            "Italian: 'not interested at the moment'"),
    257: (None,            "'Already pointed her who should be reached' - redirect"),
    258: (None,            "describing their own company"),
    259: (None,            "'I am already retired'"),
    260: ("interested",    "'Sure, thanks for the link' - willing to look at it"),
    261: (None,            "'we don't have these issues - we will never be using a different system'"),
    262: (None,            "'I am not familiar with [product]' - no signal"),
    263: (None,            "Croatian joke: 'do AIs work?' - joke"),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Load cached replies
    cache_path = os.path.join(tempfile.gettempdir(), "task066_all_replies.json")
    with open(cache_path, encoding="utf-8") as f:
        all_replies = json.load(f)

    unknowns = [r for r in all_replies if r["classification"] == "unknown"]
    print(f"UNKNOWN replies (taxonomy input pool): {len(unknowns)}")

    # Run taxonomy on each unknown
    tax_labeled = []
    tax_unlabeled = []
    for r in unknowns:
        verdict = replies.classify_taxonomy(r["reply_text"])
        if verdict:
            tax_labeled.append({**r, "taxonomy_label": verdict["classification"]})
        else:
            tax_unlabeled.append(r)

    print(f"Taxonomy labeled: {len(tax_labeled)}")
    print(f"Taxonomy unlabeled: {len(tax_unlabeled)}")

    # Reproduce the random sample
    random.seed(42)
    sample_unlabeled = random.sample(tax_unlabeled, 200)

    # Build combined sample with IDs matching the hand labels
    combined = []
    for i, r in enumerate(tax_labeled):
        combined.append({
            "sample_id": i + 1,
            "reply_text": r["reply_text"],
            "taxonomy_label": r["taxonomy_label"],
            "source": "taxonomy_matched",
        })
    for i, r in enumerate(sample_unlabeled):
        combined.append({
            "sample_id": len(tax_labeled) + i + 1,
            "reply_text": r["reply_text"],
            "taxonomy_label": None,
            "source": "random_unknown",
        })

    assert len(combined) == 263, f"Expected 263, got {len(combined)}"

    # -----------------------------------------------------------------------
    # Compare taxonomy labels against hand labels
    # -----------------------------------------------------------------------

    # Precision: for taxonomy-matched replies, how many were correct?
    categories = ["interested", "meeting_intent", "objection"]
    precision_tp = {c: 0 for c in categories}
    precision_fp = {c: 0 for c in categories}
    precision_errors = {c: [] for c in categories}
    precision_correct = {c: [] for c in categories}

    for item in combined:
        if item["source"] != "taxonomy_matched":
            continue
        sid = item["sample_id"]
        tax_label = item["taxonomy_label"]
        hand_label, reason = HAND_LABELS_TAXONOMY_MATCHED[sid]

        if hand_label == tax_label:
            precision_tp[tax_label] += 1
            precision_correct[tax_label].append((sid, item["reply_text"], reason))
        else:
            precision_fp[tax_label] += 1
            precision_errors[tax_label].append(
                (sid, item["reply_text"], hand_label, reason)
            )

    # Recall: of all replies I labeled as category X, how many did taxonomy find?
    # Denominator = taxonomy TP + random-unknown false negatives
    recall_tp = {c: 0 for c in categories}
    recall_fn = {c: 0 for c in categories}
    recall_missed = {c: [] for c in categories}

    # Count TP from taxonomy-matched set
    for item in combined:
        if item["source"] != "taxonomy_matched":
            continue
        sid = item["sample_id"]
        hand_label, reason = HAND_LABELS_TAXONOMY_MATCHED[sid]
        tax_label = item["taxonomy_label"]
        if hand_label == tax_label:
            recall_tp[tax_label] += 1

    # Count FN from random-unknown set
    for item in combined:
        if item["source"] != "random_unknown":
            continue
        sid = item["sample_id"]
        hand_label, reason = HAND_LABELS_RANDOM_UNKNOWN[sid]
        if hand_label is not None:
            recall_fn[hand_label] += 1
            recall_missed[hand_label].append((sid, item["reply_text"], reason))

    # -----------------------------------------------------------------------
    # Print results
    # -----------------------------------------------------------------------

    print("\n" + "=" * 78)
    print("TAXONOMY PRECISION MEASUREMENT - TASK-076")
    print("=" * 78)
    print(f"\nSample: {len(combined)} replies")
    print(f"  Taxonomy-matched: {len(tax_labeled)} (all of them)")
    print(f"  Random UNKNOWN:   {len(sample_unlabeled)} (seed=42)")
    print(f"  Total UNKNOWN pool: {len(unknowns)}")

    print("\n" + "-" * 78)
    print("PRECISION (of what the taxonomy labeled, how much was correct)")
    print("-" * 78)

    total_tp = 0
    total_fp = 0
    for cat in categories:
        tp = precision_tp[cat]
        fp = precision_fp[cat]
        total = tp + fp
        prec = tp / total if total > 0 else 0
        total_tp += tp
        total_fp += fp
        print(f"\n  {cat.upper()}")
        print(f"    Precision: {prec:.2f} (n={total})")
        print(f"    Correct: {tp}, Wrong: {fp}")
        if precision_errors[cat]:
            print(f"\n    MISCLASSIFIED (taxonomy said {cat.upper()}, hand label says otherwise):")
            for sid, text, true_label, reason in precision_errors[cat]:
                text_clean = text[:140].replace("\n", " ")
                true_str = true_label if true_label else "none"
                print(f"      [{sid:3d}] true={true_str:15s} | {text_clean}")
                print(f"             reason: {reason}")

    total_labeled = total_tp + total_fp
    overall_prec = total_tp / total_labeled if total_labeled > 0 else 0
    print(f"\n  OVERALL: precision {overall_prec:.2f} (n={total_labeled})")

    print("\n" + "-" * 78)
    print("RECALL (of what I labeled, how much did the taxonomy find)")
    print("-" * 78)

    for cat in categories:
        tp = recall_tp[cat]
        fn = recall_fn[cat]
        total = tp + fn
        rec = tp / total if total > 0 else 0
        print(f"\n  {cat.upper()}")
        print(f"    Recall: {rec:.2f} (n={total})")
        print(f"    Found: {tp}, Missed: {fn}")
        if recall_missed[cat]:
            print(f"\n    MISSED (hand-labeled {cat.upper()}, taxonomy said UNKNOWN):")
            for sid, text, reason in recall_missed[cat]:
                text_clean = text[:140].replace("\n", " ")
                print(f"      [{sid:3d}] {text_clean}")
                print(f"             reason: {reason}")

    print("\n" + "-" * 78)
    print("PATTERN ANALYSIS")
    print("-" * 78)

    # Count which patterns cause false positives
    fp_patterns = {}
    for cat in categories:
        for sid, text, true_label, reason in precision_errors[cat]:
            body = replies.normalise(text)
            matched_pattern = None
            for pattern in getattr(replies, f"{cat.upper()}_PATTERNS", ()):
                import re
                m = re.search(pattern, body, re.I)
                if m and not replies._is_negated(body, m.start()):
                    matched_pattern = pattern
                    break
            if matched_pattern:
                key = (cat, matched_pattern)
                if key not in fp_patterns:
                    fp_patterns[key] = 0
                fp_patterns[key] += 1

    print("\n  False positives by pattern:")
    for (cat, pattern), count in sorted(fp_patterns.items(), key=lambda x: -x[1]):
        print(f"    {cat:15s} | {count:3d} FPs | {pattern}")

    # Save full results
    results = {
        "sample_size": len(combined),
        "taxonomy_matched": len(tax_labeled),
        "random_unknown": len(sample_unlabeled),
        "total_unknown_pool": len(unknowns),
        "precision": {},
        "recall": {},
    }
    for cat in categories:
        tp = precision_tp[cat]
        fp = precision_fp[cat]
        total = tp + fp
        results["precision"][cat] = {
            "value": round(tp / total, 2) if total > 0 else None,
            "correct": tp,
            "wrong": fp,
            "total": total,
        }
        tp2 = recall_tp[cat]
        fn2 = recall_fn[cat]
        total2 = tp2 + fn2
        results["recall"][cat] = {
            "value": round(tp2 / total2, 2) if total2 > 0 else None,
            "found": tp2,
            "missed": fn2,
            "total": total2,
        }

    out_path = os.path.join(tempfile.gettempdir(), "task076_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
