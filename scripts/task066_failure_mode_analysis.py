#!/usr/bin/env python3
"""TASK-066: Classify the failure modes of the 3,869 unknown replies.

For each unknown reply, determine WHY the classifier could not read it.
Categories:
  - non_english: text is primarily non-English
  - emoji_only: reply is just emoji/unicode symbols
  - negative_missed: clear refusal that existing patterns should catch
  - not_relevant_missed: person says they left / wrong person
  - not_now_missed: person says not now / maybe later
  - referral_missed: person hands somebody on
  - positive_missed: clear interest that existing patterns should catch
  - unsubscribe_missed: removal request
  - genuinely_ambiguous: truly unclear what the reply means
  - other: does not fit any category

READS ONLY. Uses the cached reply texts from task066_unknown_replies.json.
"""
import json
import os
import re
import sys
import tempfile
from collections import Counter

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# --- Non-English detection ---
# Simple heuristic: check for characters from non-Latin scripts, or
# common non-English words in Latin-script languages.
_NON_LATIN = re.compile(
    r'[\u0400-\u04ff'   # Cyrillic
    r'\u0600-\u06ff'    # Arabic
    r'\u4e00-\u9fff'    # CJK
    r'\u3040-\u309f'    # Hiragana
    r'\u30a0-\u30ff'    # Katakana
    r'\uac00-\ud7af'    # Korean
    r'\u0900-\u097f'    # Devanagari
    r'\u0e00-\u0e7f'    # Thai
    r'\u0370-\u03ff'    # Greek
    r'\u0590-\u05ff'    # Hebrew
    r']')

# Common non-English words in Latin-script languages
_NON_EN_WORDS = {
    # Croatian/Serbian/Bosnian
    'hvala', 'zahvaljujem', 'ugodan', 'povratno', 'javim', 'svakom',
    'slucaju', 'ponudi', 'hvala', 'tjedan', 'mjesec', 'godina', 'jesam',
    'nisam', 'sam', 'si', 'je', 'smo', 'ste', 'su', 'bih', 'bi', 'ce',
    'cemo', 'dete', 'zelio', 'zeljela', 'molim', 'tzv', 'gdje', 'zasto',
    'kako', 'kada', 'tko', 'sto', 'tko',
    # Danish/Norwegian/Swedish
    'tak', 'hej', 'med', 'venlig', 'hilsen', 'hele', 'ikke', 'for',
    'hvordan', 'hvorfor', 'hvad', 'hvem', 'hvor', 'eller', 'men', 'og',
    'det', 'den', 'har', 'var', 'blev', 'bliver', 'skal', 'kan', 'ma',
    # Spanish
    'hola', 'gracias', 'contactar', 'interesado', 'interesada', 'no',
    'pero', 'por', 'favor', 'saludos', 'cordiales', 'atentamente',
    # French
    'bonjour', 'merci', 'revoir', 'cordialement', 'bien', 'suis',
    # German
    'hallo', 'danke', 'mit', 'freundlichen', 'gruessen', 'grüßen',
    # Italian
    'ciao', 'grazie', 'saluti', 'buongiorno',
    # Portuguese
    'ola', 'olá', 'obrigado', 'obrigada', 'saudacoes',
    # Dutch
    'hallo', 'bedankt', 'met', 'vriendelijke', 'groeten',
}


def _is_non_english(text):
    """Heuristic: is this text primarily non-English?"""
    # Non-Latin script is a strong signal
    non_latin_chars = len(_NON_LATIN.findall(text))
    if non_latin_chars > len(text) * 0.1:
        return True

    # For Latin-script languages, check word frequency
    words = set(re.findall(r'[a-zA-Z\u00c0-\u024f]+', text.lower()))
    non_en = words & _NON_EN_WORDS
    if len(non_en) >= 3 and len(non_en) / max(len(words), 1) > 0.3:
        return True
    return False


def _is_emoji_only(text):
    """Is this reply just emoji/symbols with no alphabetic content?"""
    stripped = text.strip()
    if not stripped:
        return True
    # Remove whitespace
    no_ws = re.sub(r'\s+', '', stripped)
    # Check if any ASCII or Latin letter exists
    has_alpha = bool(re.search(r'[a-zA-Z\u00c0-\u024f]', no_ws))
    if has_alpha:
        return False
    # Only emoji, numbers, punctuation
    return True


def _classify_failure_mode(reply_text):
    """Classify WHY this reply is unknown. Returns (category, evidence)."""
    text = reply_text.strip()
    low = text.lower()

    # 1. Emoji only
    if _is_emoji_only(text):
        return 'emoji_only', 'no alphabetic content'

    # 2. Non-English
    if _is_non_english(text):
        return 'non_english', 'non-English text detected'

    # 3. Negative patterns that should match but don't
    neg_missed = [
        (r'\bno interest\b', 'no interest'),
        (r'\bnot interested\b.*\bat the moment\b', 'not interested at the moment'),
        (r'\bcurrently (?:a |it\'s a )?no\b', 'currently a no'),
        (r'\b(?:it\'s|is) (?:a |going to be a )?no\b', 'it is a no'),
        (r'\bwe(?:\'re| are) good\b', 'we are good'),
        (r'\bnot (?:looking|seeking)\b', 'not looking/seeking'),
        (r'\bno (?:need|use) (?:for|at) (?:the )?(?:moment|time|now)\b',
         'no need at the moment'),
        (r'\b(?:don\'t|do not) (?:have|see) (?:a |any )?need\b',
         'don\'t have a need'),
        (r'\bnot (?:something|anything) (?:i\'m|i am) looking for\b',
         'not something I\'m looking for'),
        (r'\b(?:good on|good with|covered on) (?:the )?.*(?:right )?now\b',
         'good on X right now'),
        (r'\bno (?:budget|money|funds?|resources?)\b', 'no budget/money'),
        (r'\b(?:can\'t|cannot|won\'t) (?:afford|justify)\b',
         'can\'t afford'),
        (r'\bnot (?:a |the )?priority (?:at |right )?(?:now|the moment|this time)\b',
         'not a priority now'),
        (r'\bnot (?:going|going to) (?:to )?(?:be|work)\b', 'not going to work'),
        (r'\bpass (?:on|for) (?:this|now)\b', 'pass on this'),
        (r'\bnot (?:at |for )?this (?:stage|point|time)\b',
         'not at this stage'),
        (r'\bwe(?:\'re| are) (?:all )?(?:set|covered|sorted)\b',
         'we are set/covered'),
        (r'\bno thanks\b', 'no thanks'),
        (r'\bnot (?:really|particularly) interested\b',
         'not really interested'),
        (r'\b(?:i\'m|i am) (?:not )?(?:sure|uncertain)\b.*\b(?:not|no)\b',
         'not sure + negative'),
        (r'\bnot (?:looking to|in the market)\b', 'not looking to'),
    ]
    for pat, label in neg_missed:
        if re.search(pat, low):
            return 'negative_missed', label

    # 4. Not-relevant patterns that should match but don't
    nr_missed = [
        (r'\b(?:i\'m|i am) (?:no |not )?longer (?:with|at|working)\b',
         'no longer with/at'),
        (r'\b(?:i\'m|i am) not (?:at|with|working at) \w+ (?:anymore|any more|now)\b',
         'not at X anymore'),
        (r'\bleft (?:the )?(?:company|\w+)(?: in \w+)?\b', 'left company'),
        (r'\b(?:i\'m|i am) not (?:the |a )?(?:right|correct) person\b',
         'not the right person'),
        (r'\bnot (?:my |our )?(?:area|remit|department|responsibility)\b',
         'not my area/remit'),
        (r'\b(?:i|we) (?:don\'t|do not) (?:handle|manage|deal with)\b',
         'don\'t handle'),
        (r'\bnot (?:responsible|in charge) (?:for|of)\b',
         'not responsible for'),
        (r'\b(?:i\'m|i am) (?:in|working in) (?:a )?different (?:role|team|department)\b',
         'different role/team'),
        (r'\bbetween jobs\b', 'between jobs'),
        (r'\bnot (?:working|at \w+) (?:there |at )?anymore\b',
         'not working there anymore'),
        (r'\b(?:i have |i\'ve )?(?:left|resigned|moved on)\b',
         'left/resigned'),
        (r'\bno longer (?:in|with|at|working)\b', 'no longer in/with/at'),
        (r'\bdoes it look like.*\?\b', 'rhetorical - wrong target'),
        (r'\bwrong (?:person|department|team|contact)\b', 'wrong person'),
    ]
    for pat, label in nr_missed:
        if re.search(pat, low):
            return 'not_relevant_missed', label

    # 5. Not-now patterns that should match but don't
    nn_missed = [
        (r'\b(?:keep|keep me) (?:posted|informed|updated)\b',
         'keep me posted'),
        (r'\b(?:in the )?future\b.*\b(?:editions?|rounds?|time)\b',
         'in the future'),
        (r'\b(?:maybe|perhaps) (?:later|sometime|another time)\b',
         'maybe later'),
        (r'\bnot (?:at |for )?this (?:time|moment)\b',
         'not at this time'),
        (r'\b(?:reach|contact) (?:out to )?(?:me|us) (?:again )?(?:in|next|after)\b',
         'reach out again in'),
        (r'\b(?:circle|check|come|get) back (?:to )?(?:me|us)\b',
         'circle back'),
        (r'\b(?:shelve|park) (?:this|it)\b', 'shelve/park this'),
        (r'\b(?:bad|wrong) (?:timing|time)\b', 'bad timing'),
        (r'\b(?:revisit|review) (?:this )?(?:in|after|next)\b',
         'revisit in/after'),
        (r'\b(?:not |un)(?:likely|likely) (?:to )?(?:be|work|help)\b',
         'unlikely to work'),
    ]
    for pat, label in nn_missed:
        if re.search(pat, low):
            return 'not_now_missed', label

    # 6. Referral patterns that should match
    ref_missed = [
        (r'\b(?:forward|pass(?:ing|ed)?) (?:this |it )?(?:on )?(?:to|along)\b',
         'forward/pass to'),
        (r'\b(?:send|forward) (?:this |your )?(?:to|along to)\b',
         'send/forward to'),
        (r'\b(?:you )?can (?:reach|contact|email) (?:him|her|them|our)\b',
         'can reach him/her'),
        (r'\b(?:handled|managed|done) by\b', 'handled by X'),
        (r'\b(?:my|our) (?:colleague|team|assistant|EA) (?:handles|manages|can help)\b',
         'colleague handles'),
        (r'\b(?:please|kindly) (?:contact|reach|email|speak to|talk to)\b',
         'please contact X'),
        (r'\b(?:the )?(?:right|best|correct) person (?:is|would be|for) (?:this|that)\b',
         'right person is'),
    ]
    for pat, label in ref_missed:
        if re.search(pat, low):
            return 'referral_missed', label

    # 7. Positive patterns that should match
    pos_missed = [
        (r'\b(?:send|share) (?:me |us )?(?:the )?(?:details|info|more info|portfolio|proposal|pricing|deck|brochure)\b',
         'send me details'),
        (r'\b(?:what|how) (?:does|is|are|about|would)\b.*\b(?:cost|price|pricing|work)\b',
         'pricing question'),
        (r'\b(?:interested|curious) (?:to|in) (?:learn|know|hear|see|understand)\b',
         'interested to learn'),
        (r'\b(?:that|this|it) (?:sounds?|looks?) (?:interesting|good|great|useful)\b',
         'sounds interesting'),
        (r'\b(?:let\'s|lets) (?:connect|chat|talk|discuss)\b',
         'let\'s connect/chat'),
        (r'\b(?:i\'d|i would) (?:like|love) (?:to )?(?:to )?(?:learn|know|hear|see)\b',
         'I\'d like to learn'),
        (r'\b(?:can|could) (?:you |we )?(?:send|share)\b',
         'can you send'),
        (r'\b(?:yes|sure|absolutely|definitely)\b',
         'yes/sure/absolutely'),
        (r'\b(?:happy|glad) (?:to|for) (?:connect|chat|talk|hear|learn)\b',
         'happy to connect'),
        (r'\b(?:open|interested) (?:to|in) (?:a )?(?:call|chat|conversation|discussion)\b',
         'open to a call'),
        (r'\b(?:tell|show) me more\b', 'tell me more'),
        (r'\b(?:what|which) (?:platform|tool|software|system)\b.*\b(?:use|using)\b',
         'what platform do you use'),
        (r'\b(?:checked|checked out|looked at) (?:it|this|your)\b',
         'checked it out'),
    ]
    for pat, label in pos_missed:
        if re.search(pat, low):
            return 'positive_missed', label

    # 8. Unsubscribe patterns that should match
    unsub_missed = [
        (r'\b(?:please )?(?:do not|don\'t|stop) (?:contact|email|message|reach) (?:me|us)\b',
         'don\'t contact me'),
        (r'\b(?:remove|delete|unsubscribe) (?:me|us) (?:from|off)\b',
         'remove me from'),
        (r'\bno more (?:emails?|messages?|mail|contacts?)\b',
         'no more emails/messages'),
        (r'\b(?:opt|unsub)\b', 'opt-out/unsub'),
    ]
    for pat, label in unsub_missed:
        if re.search(pat, low):
            return 'unsubscribe_missed', label

    # 9. Genuinely ambiguous
    ambiguous_signals = [
        r'\b(?:thanks|thank you|thx|ty)\b',
        r'\b(?:hi|hello|hey)\b',
        r'\b(?:ok|okay|k)\b',
        r'\b(?:hmm|hm)\b',
        r'\?',
        r'\b(?:what|how|when|where|why|who)\b',
    ]
    for pat in ambiguous_signals:
        if re.search(pat, low):
            return 'genuinely_ambiguous', f'contains: {pat}'

    return 'other', 'no pattern matched'


def main():
    p = os.path.join(tempfile.gettempdir(), 'task066_unknown_replies.json')
    with open(p, 'r', encoding='utf-8') as f:
        unknowns = json.load(f)

    print(f'Analyzing {len(unknowns)} unknown replies...')

    categories = Counter()
    evidence_by_cat = {}
    categorized = []

    for r in unknowns:
        cat, evidence = _classify_failure_mode(r['reply_text'])
        categories[cat] += 1
        if cat not in evidence_by_cat:
            evidence_by_cat[cat] = Counter()
        evidence_by_cat[cat][evidence] += 1
        categorized.append({**r, 'failure_mode': cat, 'evidence': evidence})

    total = len(unknowns)
    print(f'\n{"="*60}')
    print(f'FAILURE MODE DISTRIBUTION (n={total})')
    print(f'{"="*60}')
    for cat, count in categories.most_common():
        pct = round(count / total * 100, 1)
        print(f'  {cat:30s} {count:5d}  {pct:5.1f}%')

    print(f'\n{"="*60}')
    print(f'EVIDENCE BREAKDOWN BY CATEGORY')
    print(f'{"="*60}')
    for cat in categories:
        print(f'\n  --- {cat} (n={categories[cat]}) ---')
        for ev, cnt in evidence_by_cat[cat].most_common(10):
            print(f'    {cnt:4d}  {ev}')

    # Save categorized results
    out_path = os.path.join(tempfile.gettempdir(),
                            'task066_categorized.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(categorized, f, ensure_ascii=False, indent=1)
    print(f'\nSaved categorized results to {out_path}')

    # Summary for actionable vs non-actionable
    actionable = sum(v for k, v in categories.items()
                     if k.endswith('_missed'))
    non_actionable = total - actionable
    print(f'\n{"="*60}')
    print(f'SUMMARY')
    print(f'{"="*60}')
    print(f'  Actionable (pattern missed): {actionable} '
          f'({round(actionable/total*100,1)}%)')
    print(f'  Non-actionable:              {non_actionable} '
          f'({round(non_actionable/total*100,1)}%)')
    print(f'    - emoji_only:              {categories.get("emoji_only", 0)}')
    print(f'    - non_english:             {categories.get("non_english", 0)}')
    print(f'    - genuinely_ambiguous:     {categories.get("genuinely_ambiguous", 0)}')
    print(f'    - other:                   {categories.get("other", 0)}')


if __name__ == '__main__':
    main()
