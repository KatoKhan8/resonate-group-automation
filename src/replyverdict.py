"""Whether a STORED reply verdict can be trusted as a current one.

OPERATOR, 2026-09-23: Phase D item 4 - positive replies into the client
channel - waits on the VERSION bump and the ledger write-back. Until then:
**a test that a `rules-3` verdict is never counted.**

## THE FIELD IS THERE AND IT CANNOT ANSWER THE QUESTION

`SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §3b said `account.replies()`
carried no `classifier`. Half right: the field was on the EVENT and dropped
in projection. Counted in the live estate on 2026-09-23 - 42 reply events,
20 carrying `classifier`, and the single stale `positive` carrying it
explicitly:

    {"type": "reply_classified", "contact": "jennifer-bagley",
     "at": "2026-09-22T18:35:03Z", "classification": "positive",
     "classifier": "rules-3", "confidence": "0.75",
     "reason": "matched 2 positive phrase(s)"}

`account.replies()` now projects it. **And it still cannot answer the
question**, because `replies.VERSION` is *also* `"rules-3"` - through two
rule changes on 2026-09-23 (`0b78fd68` at 13:18 rewrote the `\\bpass\\b`
pattern and moved two phrases out of NEGATIVE; `83a30652` at 14:46 added
QUESTION and SEND_INFO across 210 lines). The stale row and a row classified
this afternoon carry the same string.

**A field that is present, readable and cannot distinguish anything is worse
than an absent one.** An absent field forces the caller to admit it does not
know. A present one invites a guard that looks correct, compares
`classifier == VERSION`, passes the stale row, and announces an
autoresponder as a buying signal - the exact outcome the whole reply
classification effort exists to prevent.

## SO THIS MODULE REFUSES, AND SAYS WHAT WOULD CHANGE ITS MIND

`current_rule_identity()` asks `replies` for something that identifies the
RULE SET rather than the release - a hash over the patterns. Production is
bringing one with the `rules-4` bump. **Today there is none, so it returns
`None`, `is_confirmed` is False for every stored verdict, and
`confirmed_positives` is zero.**

That is not a placeholder. Zero is the true answer to "how many stored
positives can we currently prove are current", and a feature that reads it
posts nothing rather than posting the EA reply. The day the hash lands this
module starts answering without being edited, because it never hard-codes a
version string of its own - it asks.

## WHY NOT JUST RE-CLASSIFY THE TEXT

Because the text is not stored. None of the 42 reply events carries `text`,
`body` or `snippet`; the classification was made when the row was read from
the provider and only the verdict was kept. Re-classifying locally is not
available, and fetching every reply body back from the provider to settle a
report's footnote is a different and much larger decision.
"""

#: What `replies` would have to expose for a stored verdict to be checkable:
#: a digest of the RULES, not a name for the release. Asked for by name so
#: this module needs no edit on the day it appears.
RULE_IDENTITY_ATTRS = ("RULE_HASH", "RULES_HASH", "RULE_FINGERPRINT")

#: The reason, in one sentence, for every reader that has to print it.
WHY_UNCONFIRMED = (
    "the stored verdict names its classifier as a release string, and that "
    "string did not change when the rules did, so a verdict stored before "
    "the rules moved is indistinguishable from one stored after")


def current_rule_identity(replies_module=None):
    """A digest identifying the CURRENT rule set, or `None`.

    `VERSION` is deliberately NOT a fallback. Falling back to it is the
    single mistake this module exists to make impossible: it would make
    every stale `rules-3` verdict compare equal to a current one and turn
    the guard into a rubber stamp.
    """
    if replies_module is None:
        from . import replies as replies_module
    for attr in RULE_IDENTITY_ATTRS:
        value = getattr(replies_module, attr, None)
        if value:
            return str(value)
    return None


def rules_are_identifiable(replies_module=None):
    """Whether ANY stored verdict could currently be confirmed."""
    return current_rule_identity(replies_module) is not None


def is_confirmed(row, replies_module=None):
    """True only when this stored verdict is PROVABLY the current rules.

    `row` is one entry from `account.replies()`. Returns False when the
    rules are not identifiable at all, when the row names no classifier,
    and when the classifier it names is not the current digest. Three
    different reasons, one answer, and the answer is the conservative one
    in every case - this decides whether a client is told somebody is
    interested.
    """
    identity = current_rule_identity(replies_module)
    if identity is None:
        return False
    stored = (row or {}).get("classifier")
    if not stored:
        # A verdict that does not say who made it is not a verdict we can
        # stand behind, whatever the rules currently are.
        return False
    return str(stored) == identity


def split_positives(rows, positive_class="positive", replies_module=None):
    """`(confirmed, unconfirmed)` over reply rows, by class.

    Counted over `reply_classified` rows only - `positive_reply_detected` is
    the same reply seen a second time, and counting both doubles it. That is
    the bug `94725a3d` fixed at report scale and it is not being
    reintroduced here.
    """
    confirmed = unconfirmed = 0
    for row in rows or []:
        if (row or {}).get("classification") != positive_class:
            continue
        if is_confirmed(row, replies_module):
            confirmed += 1
        else:
            unconfirmed += 1
    return confirmed, unconfirmed
