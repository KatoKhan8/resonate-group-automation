"""The operator's account vocabulary. ONE definition, several readers.

OPERATOR, 2026-09-23: "One vocabulary for the Monday Slack post, the PDF and
later the portal."

This module exists because there were two, and they shared a word.
`slackagenttools` answered `account_status` and `weekly_report` in the
operator's eight states; `web/api._account_counts` fed the PDF's Account
Engagement section a different six - `targeted / contacted / engaged /
positive / multi_dm / referrals`. **Both spelled `engaged` and neither meant
the same thing by it**: in the PDF it was "at least one reply", here it is
deliberately SHORT of a reply. Mapping one onto the other put a different
number under the same word in a document a client receives, which is why
`SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §5a refused to write the adapter
and asked for a decision instead.

The decision was to give the PDF this vocabulary and RETIRE the old keys
rather than alias them. An alias would have been the same bug with a
forwarding address.

`src/account.py` also defines `ENGAGED`, at contact level, where it means
"this person replied". That one is not this one and is deliberately not
imported here; the account-level word is decided by `state_of` below.
"""

#: The operator's account states, weakest first. The order IS the commercial
#: progression, and `state_of` walks it from the strong end.
UNTOUCHED = "untouched"
SEQUENCED = "sequenced"
ENGAGED = "engaged"
REPLIED = "replied"
MEETING = "meeting"
WON = "won"
LOST = "lost"
DO_NOT_CONTACT = "do_not_contact"

ACCOUNT_STATES = (UNTOUCHED, SEQUENCED, ENGAGED, REPLIED, MEETING,
                  WON, LOST, DO_NOT_CONTACT)

#: A roll-up, NOT a state. Four of the eight, summed for the one-line answer.
#: Kept separate from `ACCOUNT_STATES` so nothing can iterate the states and
#: pick this up as a ninth, which would double-count every account in it.
IN_FLIGHT = (SEQUENCED, ENGAGED, REPLIED, MEETING)

#: TWO OF THE EIGHT HAVE NO SOURCE IN THIS REPOSITORY, and that is reported
#: rather than left to look like "it never happens". Nothing here records a
#: deal. The meetings ledger is hand-fed and stops at the meeting; there is
#: no CRM in this tree and no won/lost field on any record. An answer that
#: silently never returns two of the states it advertises is worse than one
#: that names the gap, because the gap is invisible from the outside.
STATES_WITHOUT_A_SOURCE = (WON, LOST)

#: What `unanswerable` means, in one sentence, for every reader that has to
#: print it. NEVER folded into `untouched` - that fold is the specific
#: falsehood this whole vocabulary was assembled to stop.
UNANSWERABLE_MEANS = (
    "could not be placed: the ledger carries no touch for the account AND "
    "is not recording this workspace's sends, so `untouched` cannot be "
    "asserted. This is not a count of untouched accounts.")


def state_of(record, detail, meetings_for_domain, ledger_ok=None):
    """One of `ACCOUNT_STATES`, with the evidence that decided it.

    Returns `(state, evidence)`. `state` is `None` when the account is
    UNANSWERABLE - see the `ledger_ok is False` branch, which is the one
    outcome that is deliberately not a state.

    `detail` is `account.graph(record)`. `meetings_for_domain` is a count
    from the hand-fed meetings ledger. `ledger_ok` is the workspace-level
    witness: whether the ledger is recording sends at all.

    PRECEDENCE, strongest first, and every step of it is a judgement worth
    arguing with rather than a lookup:

    `do_not_contact` OUTRANKS EVERYTHING, including `meeting`. It is the one
    state that answers "what may we do next" rather than "how far did this
    get", and an account that met us and then asked to be left alone is an
    account we may not write to. Ranking a meeting above it is how a good
    outcome becomes a reason to ignore a refusal.

    Then `meeting`, `replied`, `engaged`, `sequenced`, `untouched` - the
    operator's own order.

    `engaged` MEANS SOMETHING SHORT OF A REPLY: a connection accepted, an
    interaction recorded, nobody having written back yet. Without that
    distinction it collapses into `replied` and one of the two words stops
    meaning anything.
    """
    evidence = []
    # `graph()["contacts"]` IS A LIST, not a mapping - `by_contact` is the
    # mapping. Reading the wrong one raises on `.values()` and every account
    # comes back unreadable, so the shape is taken off the real return.
    contacts = (detail or {}).get("contacts") or []
    states = [str((c or {}).get("state") or "") for c in contacts]

    suppressed = [s for s in states if s in ("suppressed", "stopped")]
    if str(record.get("state") or "") == "do_not_contact" \
            or record.get("do_not_contact") \
            or (states and len(suppressed) == len(states)):
        evidence.append("every contact is suppressed or stopped"
                        if states else "the record carries do_not_contact")
        return DO_NOT_CONTACT, evidence

    if meetings_for_domain:
        evidence.append("%d meeting(s) in the hand-fed ledger"
                        % meetings_for_domain)
        return MEETING, evidence

    replied = len((detail or {}).get("replies") or [])
    if replied:
        evidence.append("%d reply event(s) on the account" % replied)
        return REPLIED, evidence

    # ENGAGED IS SHORT OF A REPLY. `account._contact_state` calls a contact
    # `engaged` when they have replied, so by the time we are here that
    # branch is already spent - what is left is a confirmed touch on a
    # channel that carries an acceptance. Reached deliberately and rarely;
    # it is not a synonym for `replied` and must never become one.
    if any(s == ENGAGED for s in states) \
            or any(t.get("channel") == "linkedin" and t.get("confirmed")
                   for t in ((detail or {}).get("touches") or [])):
        evidence.append("a LinkedIn touch landed and nobody has written back")
        return ENGAGED, evidence

    confirmed = len((detail or {}).get("confirmed_touches") or [])
    if confirmed:
        evidence.append("%d confirmed touch(es) in the ledger" % confirmed)
        return SEQUENCED, evidence

    if ledger_ok is False:
        # THE ONE CASE THAT IS NOT A STATE, and it is the whole reason this
        # function takes the witness. The ledger says nobody has been
        # touched AND the ledger is known not to be recording touches, so
        # `untouched` would be a guess dressed as an answer - in a client
        # channel, about an account we may well have emailed yesterday.
        evidence.append("the ledger carries no touch for this account AND "
                        "is not recording this workspace's sends, so "
                        "`untouched` cannot be asserted")
        return None, evidence

    evidence.append("no confirmed touch in the ledger")
    return UNTOUCHED, evidence


def empty_counts():
    """Every state at zero. A reader that renders tiles needs all eight keys
    present even when nothing is in them, or a missing key renders as "not
    tracked" and a real zero becomes indistinguishable from an unbuilt
    section."""
    return {state: 0 for state in ACCOUNT_STATES}


def in_flight(counts):
    """The four-state roll-up, from a counts mapping."""
    return sum((counts or {}).get(state, 0) for state in IN_FLIGHT)
