"""Per contact, per rule: was every suppression rule asked, and what did it say?

## The question this answers, and the one it refuses to answer

Before CANARY-01 sends, somebody has to be able to say of **each named
contact** that every rule which could exclude them was asked and answered.
Not that the rules exist - they do, and they are good - but that each one was
*put to this person* and gave an answer.

Nothing in this estate produced that. `eligibility.must_not_contact` answers
six questions in one tuple, `suppression.decide` adds five more, `hygiene.check`
adds four, `channels.email_verdict` composes a different subset again, and each
one collapses to a single verdict. A single verdict cannot distinguish the two
states this file exists to keep apart:

    EXCLUDED   the rule was asked and it refused
    UNKNOWN    the rule could not be asked at all

**UNKNOWN IS NOT PASS AND NEVER BECOMES PASS.** A contact with any UNKNOWN
cell is not cleared. That is invariant 0 applied to a cohort: an unreadable
authority means UNKNOWN, and UNKNOWN never becomes PASS, zero, idle, complete
or safe.

## THE AUTHORITY IS CHECKED BEFORE THE RULE, AND THAT IS THE WHOLE DESIGN

Measured 2026-10-16 in `wt-suppression-2026-10-14`:

    agencydnc.load()      ->  {}   with work/agency-dnc.jsonl ABSENT
    agencydnc.lookup(x)   ->  None for every x
    store.load()          ->  0 rows, NO RAISE, with work/queue.jsonl ABSENT
    ingest.load_suppress()->  2 domains, with config/suppress.local.txt ABSENT

So in this tree every contact passes the agency do-not-contact list, and
nothing anywhere says the list was never read. `agencydnc.load`'s own
docstring states it: *"Missing file is empty."* That is a reasonable choice
for a send path which must not take the estate down on a damaged byte - and
it is the wrong answer for a preflight, because a preflight's entire job is
to distinguish "asked and clean" from "not asked".

`src/supervisor.py` already took the opposite decision for the same shape and
wrote down why: *"`campaigns.load()` returns an EMPTY SNAPSHOT when the
registry file is absent - it does not raise. Reading it straight would
therefore turn 'I cannot see the registry' into 'there are no campaigns'."*
It raises `RegistryUnreadable` instead. Nothing does that for the DNC.

**This module does not change any of those readers.** They sit on send paths
and changing one is a gate change. Instead every rule DECLARES the authority
files it needs, `authorities()` reports each one's state by path AND BY
RECORD COUNT, and a rule whose authority is not PRESENT_POPULATED is UNKNOWN
before the rule is even called. The reader keeps its behaviour; the preflight
stops being fooled by it.

## AND "IS THE FILE THERE" WAS NOT THE WHOLE QUESTION - TASK-0190

The first version of that gate asked one thing: does the file exist. It left
the estate one command away from a false clear-to-send, because this module
had already measured the mechanism and written it down two paragraphs above:
`store.load()` answers 0 rows without raising, and `store.PRODUCTION_WORK`
resolves against the CALLING tree. So a rotated, truncated, half-written or
wrong-tree `queue.jsonl` read as PRESENT, the FOURTEEN rules that need the
queue were asked, found nothing, and reported PASS - and the report's own
headline sentence would have said CLEARED TO SEND. Fourteen is measured;
the number carried in the brief and in every earlier note was thirteen.

An authority therefore has FIVE states, not two, and the record count is
printed beside each one:

    ABSENT               no file at the resolved absolute path
    PRESENT_UNREADABLE   resolving, opening or parsing raises
    PRESENT_EMPTY        opens, parses, yields ZERO records
    PRESENT_POPULATED    opens, parses, yields at least one record
    OUTSIDE_TREE         a hard refusal: not this tree's file at all

`PRESENT_EMPTY` is **not** an answer about this cohort for any rule whose
question is "is this contact in here". It is UNKNOWN. The asymmetry is kept:
an EXCLUSION found on an empty or partial authority is still an exclusion,
and only a PASS needs `PRESENT_POPULATED`.

## Read-only, and it makes no provider call

Every rule needing a provider read is UNKNOWN by declaration, named, with the
read that would answer it. Nothing here enriches, writes, suppresses, enrols
or sends.

## Real addresses do not come from here

This module takes contacts as an argument. It never reads a cohort file and it
never prints one. The addresses live in `resonate-ops/` and in gitignored
paths; the tests use synthetic ones.
"""
import os

from . import store

# ------------------------------------------------------------- the cells

PASS = "PASS"
EXCLUDED = "EXCLUDED"
UNKNOWN = "UNKNOWN"

#: The three answers and the only three. A fourth would be a way to say
#: "probably fine", which is the thing this file exists to refuse.
CELLS = (PASS, EXCLUDED, UNKNOWN)

EXIT_CLEARED, EXIT_EXCLUDED, EXIT_UNKNOWN = 0, 1, 2

# -------------------------------------------------------- the authorities
#
# ONE ROW PER FILE THAT A RULE READS, resolved through the module that owns
# the path - never spelled out here. `test_invariants` fails any module but
# `store` that names a state file, and a second spelling of a path is a
# second thing that can be wrong.

# FOUR STATES, NOT TWO - AND THE MISSING ONE WAS THE DANGEROUS ONE.
#
# TASK-0190. The first version of this gate asked exactly one question: IS
# THE FILE THERE. That is not enough, and this module had already written
# down why: `store.PRODUCTION_WORK` resolves against the CALLING tree's root,
# and `store.load()` answers 0 rows without raising. So a rotated, truncated,
# half-written or wrong-tree `queue.jsonl` came out PRESENT, the FOURTEEN
# rules that read it were asked, found nothing, and reported PASS - and the
# report's headline sentence would have become a clear-to-send.
#
# FOURTEEN, MEASURED. The brief said thirteen and so did the first draft of
# this comment; `[r for r in RULES if "queue" in r["needs"]]` is 14 of 22,
# all 14 consulted on the email path and 11 on the linkedin path. Counted
# rather than carried over.
#
# Nothing in the instrument could tell that world from one where the queue
# WAS read and this person genuinely is not in it. Nor could any of the three
# controls: control 2 plants a read that RAISES, which is the one failure
# mode a present-and-empty file does not have. Control 3 was worse than
# silent - it planted "present, empty, readable authority files" and asserted
# PASS, so the instrument's own proof-of-PASS was a demonstration of the
# defect.
#
#     ABSENT               no file at the resolved absolute path
#     PRESENT_UNREADABLE   resolving, opening or parsing raises
#     PRESENT_EMPTY        opens, parses, yields ZERO records
#     PRESENT_POPULATED    opens, parses, yields at least one record
#
# PRESENT_EMPTY IS NOT AN ANSWER ABOUT ANYBODY. For every rule whose question
# is "is this contact in here", it is UNKNOWN - the same decision
# `src/supervisor.py` already took for the campaign registry, for the
# identical reason: *"Reading it straight would therefore turn 'I cannot see
# the registry' into 'there are no campaigns'."*
#
# THE ASYMMETRY IS KEPT. An EXCLUSION found on an empty or partial authority
# is still an exclusion; only a PASS needs PRESENT_POPULATED. That is
# `senderheadroom`'s rule - a walk can only undercount, so FULL is provable
# from any walk and ROOM is not.
ABSENT = "ABSENT"
PRESENT_UNREADABLE = "PRESENT_UNREADABLE"
PRESENT_EMPTY = "PRESENT_EMPTY"
PRESENT_POPULATED = "PRESENT_POPULATED"

# A FIFTH ROW THAT IS NOT A STATE OF A FILE. The four above are answers about
# the file at a path. This one is a refusal to accept the path at all: an
# authority resolving outside the tree it was asked for is exactly how a
# preflight silently reads another checkout's `work/`, and the per-tree
# resolution that makes it possible is measured in `production_work` below.
# A hard refusal with BOTH paths printed, never a warning.
OUTSIDE_TREE = "OUTSIDE_TREE"

AUTHORITY_STATES = (ABSENT, PRESENT_UNREADABLE, PRESENT_EMPTY,
                    PRESENT_POPULATED, OUTSIDE_TREE)

#: The ONLY state that can make a PASS true. Named once, in one place, so a
#: weakening has to be made here and is visible, rather than spread across
#: five comparisons where one could be changed quietly.
ANSWERABLE = (PRESENT_POPULATED,)

#: The states where the instrument determined nothing. Every rule depending
#: on one is UNKNOWN, **and the run exits non-zero even if no rule reads it**:
#: a preflight that cannot see one of its own declared inputs has not passed.
REFUSALS = (PRESENT_UNREADABLE, OUTSIDE_TREE)


def tree_root():
    """The tree whose authorities these are: the one this module lives in.

    Every authority path must resolve INSIDE it. Named as a function rather
    than a constant because `authorities()` takes it as an argument - the
    controls plant their files in a temporary directory and are asked about
    that directory, not about this checkout.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _inside(root, path):
    """Is `path` within `root`? Normcased, because this runs on Windows.

    A different drive makes `commonpath` raise; that is NOT inside, and
    swallowing the raise into True is the only way this function could be
    dangerous.
    """
    root = os.path.normcase(os.path.abspath(root))
    candidate = os.path.normcase(os.path.abspath(path))
    try:
        return os.path.commonpath([root, candidate]) == root
    except ValueError:
        return False


# ---------------------------------------------------- counting the records
#
# THROUGH THE MODULE THAT OWNS THE FORMAT, never a parser of our own. A
# counter written here would be a second representation of "what a record is
# in this file", and the two would drift - which is the same defect one level
# up from the one this file exists to fix. So each counter calls the real
# reader, in the STRICTEST form that reader offers, and raises rather than
# returning a number it is not sure of. A raise is PRESENT_UNREADABLE.
#
# None of these is a send-path change: the readers keep their behaviour and
# are called with an explicit path.


def _count_operator_exclusions(path):
    from . import operatorexclusion
    rows, bad = operatorexclusion.rows(path)
    if bad:
        # `rows` SKIPS AND COUNTS a corrupt line, and its own docstring says
        # why that matters: "a register that quietly lost half its rows is
        # indistinguishable from an empty one and one of the two is safe".
        raise ValueError("%d line(s) could not be read as an exclusion "
                         "operation" % bad)
    return len(rows), "%d exclusion operation(s)" % len(rows)


def _count_suppress_domains(path):
    from . import ingest
    # `path=` reads EXACTLY this file. The default unions the other half and
    # would report a count that is not this authority's - which is how an
    # absent roster hid behind a populated template in the first place.
    domains = ingest.load_suppress(path=path)
    return len(domains), "%d domain(s)" % len(domains)


def _count_agency_dnc(path):
    from . import agencydnc
    # `strict=True` exists, in agencydnc's own words, for "a caller that
    # would rather refuse than suppress fewer people than the file names".
    # That caller is this one. The send path keeps the lenient default.
    index = agencydnc.load(file_path=path, strict=True)
    return len(index), "%d fingerprint(s)" % len(index)


def _count_declared_internal(path):
    from . import providerwrites
    # RAISES `InternalCampaignsUnreadable` on a malformed line, which is the
    # behaviour this counter wants and the reason it is not re-implemented
    # here: a line nobody can parse may be the one protecting a live
    # campaign, and providerwrites already refuses rather than skipping it.
    declared = providerwrites.declared_internal(path)
    total = sum(len(ids) for ids in declared.values())
    return total, "%d declared internal campaign(s) across %s" % (
        total, ", ".join(sorted(declared)))


def _count_campaign_ledger(path):
    # The ledger is the ONLY positive record of a Resonate OS campaign. An
    # empty one does not mean "we have no campaigns"; it means every
    # campaign at the provider classifies `unknown`, which is do-not-touch.
    rows = store.read_jsonl(path)
    return len(rows), "%d canonical campaign row(s)" % len(rows)


def _count_campaign_lead_rows(path):
    from . import campaignmembership
    # RAISES `MembershipUnreadable` unless the listing is of the declared
    # shape. A listing missing `by_email` is not a listing of nobody.
    index = campaignmembership.load(path)
    return (campaignmembership.records(index),
            "%d indexed address(es) from %d campaign(s), read %s"
            % (campaignmembership.records(index),
               len(index.get("campaigns") or {}),
               index.get("generated_at")))


def _count_queue_records(path):
    # `store.read_jsonl` is store's own line reader and takes a path;
    # `store.load()` takes none, replays the journal and resolves against
    # the calling tree. A line that is not JSON raises here, which is
    # PRESENT_UNREADABLE and not an empty queue.
    rows = store.read_jsonl(path)
    return len(rows), "%d record(s)" % len(rows)


def _operator_exclusion_path():
    from . import operatorexclusion
    return operatorexclusion.path()


def _agency_dnc_path():
    from . import agencydnc
    return agencydnc.path()


def _suppress_template_path():
    from . import ingest
    return ingest.SUPPRESS


def _suppress_local_path():
    from . import ingest
    return ingest.SUPPRESS_LOCAL


def _internal_campaign_declaration_path():
    from . import providerwrites
    return providerwrites.internal_campaigns_path()


def _campaign_ledger_path():
    from . import campaigns
    return campaigns.path()


def _campaign_lead_rows_path():
    from . import campaignmembership
    return campaignmembership.path()


AUTHORITIES = (
    {
        "name": "operator_exclusion_register",
        "counter": _count_operator_exclusions,
        "empty_means": "a register holding no operations rules out an "
                        "exclusion for nobody, and `blocks_address` "
                        "answers False from an empty file exactly as it "
                        "does from one nobody ever wrote",
        "resolver": _operator_exclusion_path,
        "holds": "every account and address the operator permanently excluded, "
                 "including this estate's own sending addresses",
        "absent_means": "no permanent exclusion can be ruled out for anybody",
    },
    {
        "name": "suppression_template",
        "counter": _count_suppress_domains,
        "empty_means": "the tracked half contributed no domain, and "
                        "`load_suppress` unions the two halves without "
                        "reporting which of them was empty",
        "resolver": _suppress_template_path,
        "holds": "the tracked never-sequence domain template",
        "absent_means": "the tracked half of the domain suppression list is "
                        "unread",
    },
    {
        "name": "suppression_local_roster",
        "counter": _count_suppress_domains,
        "empty_means": "`config/suppress.txt`'s own header already says "
                        "this in words - an empty roster suppresses nothing "
                        "while looking exactly like a roster that happens to "
                        "match nothing",
        "resolver": _suppress_local_path,
        "holds": "the real customer never-sequence roster, gitignored",
        "absent_means": "the half of the suppression list that holds real "
                        "customers is unread, and `load_suppress` merges it "
                        "silently - an absent roster contributes nothing and "
                        "says nothing",
    },
    {
        "name": "agency_dnc",
        "counter": _count_agency_dnc,
        "empty_means": "`agencydnc.load` returns {} for an EMPTY file as "
                        "readily as for a missing one, so every contact "
                        "passes and nothing says the list held nobody",
        "resolver": _agency_dnc_path,
        "holds": "everybody who told Resonate directly not to contact them, "
                 "across every workspace",
        "absent_means": "`agencydnc.load` returns {} for a missing file, so "
                        "EVERY contact passes the agency do-not-contact check "
                        "and nothing reports that the list was never read",
    },
    {
        "name": "internal_campaign_declaration",
        "counter": _count_declared_internal,
        "empty_means": "the operator has declared NO campaign internal, so "
                       "nothing can be recognised as internal - and "
                       "`declared_internal` answers an empty declaration for "
                       "a missing file exactly as for an empty one",
        "resolver": _internal_campaign_declaration_path,
        "holds": "the operator's declaration of which provider campaigns the "
                 "team runs by hand - the ONLY place ownership of those is "
                 "recorded, because the provider carries no owner field",
        "absent_means": "every campaign the operator would have declared "
                        "internal classifies `unknown` instead. Still "
                        "do-not-touch, but the refusal stops being explicable",
    },
    {
        "name": "campaign_ledger",
        "counter": _count_campaign_ledger,
        "empty_means": "no campaign can be shown to be OURS, so every "
                       "campaign a contact holds a row in classifies "
                       "`unknown` - which is the safe direction and is NOT an "
                       "answer about who owns it",
        "resolver": _campaign_ledger_path,
        "holds": "the canonical campaign rows whose provider binding is the "
                 "only positive record of a Resonate OS campaign",
        "absent_means": "`classify_campaign` swallows an unreadable ledger "
                        "and returns `unknown` for everything, so ours and "
                        "somebody else's become one answer",
    },
    {
        "name": "campaign_lead_rows",
        "counter": _count_campaign_lead_rows,
        "empty_means": "a listing that indexed NO address is not a workspace "
                       "where nobody is in 327 - and this is the authority "
                       "whose absence let a member of an internal campaign "
                       "pass all twenty-two rules",
        "resolver": _campaign_lead_rows_path,
        "holds": "one record per lead row read from the providers, keyed by "
                 "address, each naming the campaign it was read from, under "
                 "the read's own timestamp",
        "absent_means": "nothing can say whether this contact holds a lead "
                        "row in a campaign that is not ours. It is produced "
                        "by a provider read this instrument may not make: "
                        "see campaignmembership.HOW_TO_PRODUCE",
    },
    {
        "name": "queue",
        "counter": _count_queue_records,
        "empty_means": "`store.load()` answers 0 rows for a "
                        "present-and-empty file exactly as it does for an "
                        "absent one, so a rotated, truncated, half-written "
                        "or wrong-tree queue turns FOURTEEN UNKNOWN cells "
                        "into fourteen PASS cells - the single hazard "
                        "TASK-0190 exists for",
        "resolver": store.queue_path,
        "holds": "the records and contacts every person-level and "
                 "account-level rule reads",
        "absent_means": "`store.load()` returns 0 rows without raising, so "
                        "'this person has no history' and 'the history is not "
                        "here' are the same answer",
    },
)

AUTHORITY_NAMES = tuple(a["name"] for a in AUTHORITIES)


def authorities(resolvers=None, counters=None, root=None):
    """Each authority's state, BY PATH AND BY RECORD COUNT. Resolved now.

    Five states and the record count behind each one, because the question
    "is the file there" has three different yes answers and only one of them
    licenses a PASS - see the state block above.

    `resolvers` and `counters` replace the table's own by name, which is how
    the controls plant a populated authority set, an empty one, and a reader
    that raises. `root` is the tree these authorities are being asked about:
    a path outside it is a HARD REFUSAL, not a warning, because
    `store.PRODUCTION_WORK` resolving against the calling tree is exactly how
    a preflight reads another checkout's `work/` and reports it as this
    one's.

    Nothing here is cached. A state measured once and reused is a reference
    bound to something that can move.
    """
    resolvers = resolvers or {}
    counters = counters or {}
    root = tree_root() if root is None else root
    out = {}
    for entry in AUTHORITIES:
        name = entry["name"]
        resolver = resolvers.get(name, entry["resolver"])
        counter = counters.get(name, entry["counter"])
        row = {"name": name, "holds": entry["holds"],
               "absent_means": entry["absent_means"],
               "empty_means": entry["empty_means"],
               "tree_root": root, "path": None,
               "bytes": None, "records": None}
        try:
            path = resolver()
        except Exception as exc:                                # noqa: BLE001
            # A RESOLVER THAT RAISES IS PRESENT_UNREADABLE, NOT ABSENT: the
            # path is unknown, so absence was never established either, and
            # calling it ABSENT would name no file at all. "Any authority
            # whose state cannot be determined is PRESENT_UNREADABLE."
            row.update({"state": PRESENT_UNREADABLE,
                        "why": "the path could not be resolved: %s: %s"
                               % (type(exc).__name__, exc)})
            out[name] = row
            continue
        row["path"] = path
        if not _inside(root, path):
            # BOTH PATHS, AND IT IS A REFUSAL. Printed rather than resolved,
            # repaired or warned about.
            row.update({"state": OUTSIDE_TREE,
                        "why": "HARD REFUSAL: this authority resolves to %s, "
                               "which is NOT inside the tree this run was "
                               "asked about (%s). A preflight reading another "
                               "checkout's state would report that tree's "
                               "answer as this one's" % (path, root)})
            out[name] = row
            continue
        try:
            if not os.path.exists(path):
                row.update({"state": ABSENT,
                            "why": "no file at %s" % (path,)})
            else:
                with open(path, "rb") as handle:
                    row["bytes"] = len(handle.read())
                records, note = counter(path)
                row["records"] = records
                # THE ONE LINE THIS WHOLE TASK IS ABOUT. Zero records is
                # PRESENT_EMPTY, which is not an answer about any contact.
                row.update({
                    "state": PRESENT_POPULATED if records else PRESENT_EMPTY,
                    "why": "%s, %d bytes, at %s" % (note, row["bytes"], path)})
        except Exception as exc:                                # noqa: BLE001
            # BROAD AND FAIL-CLOSED. OSError from the open, and whatever the
            # owning reader raises from the parse: `agencydnc.load(strict=1)`
            # raises ValueError, `store.read_jsonl` raises JSONDecodeError,
            # `operatorexclusion.rows` is made to raise on a counted corrupt
            # line. Every one of them means the same thing - this file was
            # not read - and the direction is UNKNOWN, which clears nobody.
            row.update({"state": PRESENT_UNREADABLE,
                        "why": "%s is there and could not be read: %s: %s"
                               % (path, type(exc).__name__,
                                  str(exc)[:200])})
        out[name] = row
    return out


def unanswerable(state):
    """The authorities that cannot license a PASS, in table order."""
    return [n for n in AUTHORITY_NAMES
            if state.get(n, {}).get("state") not in ANSWERABLE]


def refused(state):
    """The authorities the instrument could not determine at all.

    Separated from `unanswerable` because these force a non-zero exit even
    when no rule happens to read them: ABSENT and PRESENT_EMPTY are answers
    about a file, and these two are the instrument failing to look.
    """
    return [n for n in AUTHORITY_NAMES
            if state.get(n, {}).get("state") in REFUSALS]


# -------------------------------------------------------------- the rules
#
# ONE ROW PER RULE THAT CAN EXCLUDE A CONTACT FROM A SEND.
#
# `decides` names the module and function that actually takes the decision,
# so a reader can go and look rather than trust this table. `channel` is
# which path consults it. `needs` is the authorities it reads, and
# `needs_record` / `needs_provider_read` are the two other ways a rule can be
# unanswerable.
#
# `ask` is the real decider, called with a context, returning a REASON STRING
# when the rule refuses and None when it does not. `None` for `ask` means the
# rule has no address-only form and is UNKNOWN by construction here - stated
# rather than omitted, because a rule left out of the table is a rule nobody
# notices is unasked.


def _ask_operator_excluded_address(ctx):
    from . import operatorexclusion
    email = (ctx.get("email") or "").strip().lower()
    if "@" not in email:
        return None
    if operatorexclusion.blocks_address(email):
        return "the operator permanently excluded this address"
    domain = email.rsplit("@", 1)[1]
    if operatorexclusion.blocks_domain(domain):
        return ("the operator permanently excluded %s or a parent of it"
                % (domain,))
    return None


def _ask_operator_excluded_company(ctx):
    from . import operatorexclusion
    domain = (ctx.get("domain") or "").strip().lower()
    if not domain:
        return None
    if operatorexclusion.blocks_domain(domain):
        return ("the operator permanently excluded the company domain %s or a "
                "parent of it" % (domain,))
    return None


def _ask_suppressed_domain(ctx):
    from . import ingest
    domain = (ctx.get("domain") or "").strip().lower()
    if not domain:
        return None
    if domain in ingest.load_suppress():
        return "%s is on the never-sequence domain list" % (domain,)
    return None


class Undecided:
    """A rule that WAS asked and could not answer. The third return.

    `ask` has had two answers until now - a reason string for EXCLUDED and
    `None` for PASS - and two are not enough for a rule that can be fully
    equipped and still unable to answer. `internal_campaign_membership` is
    that rule: with every authority present and populated, a walk that
    covered 39 of 40 campaigns cannot rule out membership of the fortieth,
    and both "refused" and "clean" would be false.

    A plain string could not carry it: every string is truthy, so an
    UNKNOWN would have been read as an exclusion - the right direction for
    safety and the wrong statement about the contact, which is how a report
    starts naming people it cannot judge.
    """

    __slots__ = ("why",)

    def __init__(self, why):
        self.why = why

    def __repr__(self):                                      # pragma: no cover
        return "Undecided(%r)" % (self.why,)


def _ask_internal_campaign_membership(ctx):
    """CLAUDE.md standing rule 2, asked of a CONTACT for the first time.

    THE CAMPAIGN SET IS NEVER A LITERAL HERE. Every campaign id found
    against this address is handed to `providerwrites.classify_campaign`,
    which reads the operator's declaration and the ledger. `274, 327, 328,
    352` appears nowhere in this file, and the authority's own `owner` field
    is ignored - it is a retyped literal that disagrees with the declaration
    in both directions, measured in `campaignmembership`'s docstring.

    THE ASYMMETRY, ONE LAYER DOWN: a MATCH is an exclusion even from a
    partial walk, because a lead row that was read exists. A NON-MATCH needs
    every internal-or-unknown campaign PROVEN COMPLETE, because a truncated
    walk can only undercount.
    """
    from . import campaignmembership as cm
    from . import providerwrites

    channel = ctx.get("channel") or "email"
    try:
        index = cm.load()
    except cm.MembershipUnreadable as exc:
        # NOT CLIPPED, AND THAT IS THE WHOLE POINT OF THIS RULE.
        #
        # A `[:400]` cap stood here and amputated the refusal mid-word.
        # Measured 2026-10-16 on `e59b70258`: with the authority's path
        # resolved ABSOLUTE the message is 432 characters, so the 32 that
        # say WHERE the listing has to be written - "s the authority beside
        # the queue" - were dropped, and the sentence the operator reads
        # ended "at the providers read-only and write".
        #
        # The cap guarded nothing. This handler catches exactly ONE exception
        # type; every `raise MembershipUnreadable` composes its own message
        # from a path plus fixed prose, and the single site that embeds a
        # foreign exception already bounds it at 160 characters
        # (`campaignmembership.load`). So there was no unbounded string to
        # defend against - only our own instruction to the operator, cut.
        #
        # It survived because the test that checks this cell asserts
        # `"build_collision_index" in why`, a substring near the START, and
        # the amputation is at the END. A rule whose entire deliverable today
        # is a refusal that says how to lift it cannot clip that refusal.
        return Undecided("the lead-row listing could not be read: %s"
                         % (exc,))

    covered, why = cm.covers_channel(index, channel)
    if not covered:
        return Undecided("%s. %s" % (why, cm.HOW_TO_PRODUCE))

    hit = cm.lookup(index, email=ctx.get("email"))

    # ---- the matched campaigns, classified by the module that owns it
    internal, unknown_owner, ours = [], [], []
    for cid in hit["campaigns"]:
        owner = providerwrites.classify_campaign("email", cid)
        if owner == providerwrites.RESONATE_INTERNAL:
            internal.append(cid)
        elif owner == providerwrites.UNKNOWN_OWNER:
            unknown_owner.append(cid)
        else:
            ours.append(cid)

    if internal:
        return ("this contact holds a lead row in campaign(s) %s, which the "
                "operator has DECLARED internal in %s. CLAUDE.md standing "
                "rule 2: never written to, and anyone with a lead row in one "
                "is NOT CLEAN for outreach"
                % (", ".join(str(c) for c in sorted(internal)),
                   providerwrites.internal_campaigns_path()))
    if unknown_owner:
        return ("this contact holds a lead row in campaign(s) %s, whose owner "
                "is UNKNOWN - neither declared internal nor bound by a "
                "canonical ledger row. UNKNOWN means do-not-touch and members "
                "NOT CLEAN"
                % (", ".join(str(c) for c in sorted(unknown_owner))))

    # ---- no disqualifying match. Now the walk has to have been able to see.
    partial = []
    for cid in sorted((index.get("campaigns") or {})):
        owner = providerwrites.classify_campaign("email", cid)
        if owner == providerwrites.RESONATE_OS:
            # A TRUNCATED WALK OF ONE OF OUR OWN CAMPAIGNS CANNOT HIDE AN
            # INTERNAL MEMBERSHIP, so completeness is only required of the
            # campaigns this rule is about.
            continue
        ok, note = cm.proven_complete(index, cid)
        if not ok:
            partial.append(note)
    for cid in cm.declared_but_not_walked(index):
        partial.append("campaign %s is DECLARED INTERNAL and was never "
                       "walked at all, so a non-match says nothing about it"
                       % (cid,))
    if partial:
        return Undecided(
            "no lead row for this contact in any internal or unknown-owner "
            "campaign the listing covers - but the listing cannot prove it "
            "covered them: %s" % ("; ".join(partial[:6])))

    if ours:
        return None
    return None


def _ask_agency_dnc(ctx):
    from . import agencydnc
    hit = agencydnc.lookup({"email": ctx.get("email"),
                            "linkedin": ctx.get("linkedin")})
    return hit or None


def _ask_bounce_history(ctx):
    """Has this address already bounced? EXCLUDED or UNKNOWN. Never PASS.

    TASK-0250. Before this, `bounce_history` carried `ask: None`, so the cell
    read UNKNOWN in EVERY world the controls can build - including a
    populated queue and a record carrying a hard bounce event right there in
    `events`. A rule that cannot say EXCLUDED when the exclusion is in its
    own input is an instrument that only ever refuses, which is as useless as
    one that only ever passes; measured in all four worlds and recorded in
    docs/THE-BOUNCE-THAT-READS-PASS-2026-10-16.md section 2.

    THROUGH THE DECIDER THE ROW DECLARES, never a re-implementation.
    `channels._bounced` is private and is called anyway for exactly the
    reason this module calls `store.read_jsonl` rather than counting lines:
    a second reading of "what a recorded bounce is" would drift from the one
    `channels.email_verdict` consults, and then the preflight and the send
    path would disagree about the same person. `_bounced` is also the
    narrowest form of the question - `email_verdict` composes it with MX and
    verification, which is `mx_and_verification`'s row and not this one.

    AND THE ABSENCE OF THE EVENT IS NOT A PASS, which is the whole of
    TASK-0250. `channels._bounced` answers `False` for a missing event, and
    TASK-0220 measured why that `False` cannot be believed here: the bounce
    recorder's own failure line, emitted by `scripts/bison_watch_loop.py`,
    has one writer and ZERO readers, so the only production caller of
    `leadobserve.record_bounces` can fail for an UNBOUNDED time with the
    watcher still reporting UP. "This address never bounced" and "the
    recorder has not worked since a date nobody can name" are the same empty
    `events` list. So the honest third answer is `Undecided`, and it stays
    that way until the recorder's failure reaches a verdict somewhere - see
    `WHAT_WOULD_ANSWER["bounce_recorder"]`.

    THE FAILURE LINE'S EXACT TEXT IS DELIBERATELY NOT SPELLED OUT HERE, and
    that is not squeamishness about a string. TASK-0220 pins ZERO
    occurrences of it anywhere under `src/`, because `src/` is where a
    reader of it would live and any occurrence is therefore worth looking
    at. A mention in this docstring would be a false positive in that search
    for ever, which is how a working instrument gets taught to ignore
    itself. Do not add it back; name the emitting module instead.

    The soft count goes in the sentence because the row declares
    `bouncepolicy.decide for the hard/soft split`, and "2 of 3 consecutive
    softs recorded" is a materially different UNKNOWN from "none".
    """
    from . import bouncepolicy, channels

    rec = ctx.get("record") or {}
    address = (ctx.get("email") or "").strip().lower()
    if channels._bounced(rec, ctx):
        return ("this address has a recorded EMAIL_BOUNCED event - the "
                "closure event `bouncepolicy.decide` writes for a hard "
                "bounce and for the third consecutive soft one, which "
                "`channels.email_verdict` refuses the address on")
    limit = bouncepolicy.thresholds()["soft_bounces_before_suppression"]
    try:
        softs = bouncepolicy.consecutive_soft(rec, ctx.get("key"), address)
    except Exception as exc:                                    # noqa: BLE001
        # A RAISE IS NOT A ZERO. The count is decoration on an UNKNOWN that
        # is already decided, so it may not turn one into an exception and
        # lose the refusal - but it may not be reported as "none" either.
        softs = "UNCOUNTED (%s)" % (type(exc).__name__,)
    return Undecided(
        "no EMAIL_BOUNCED event is recorded against this contact in the "
        "record supplied for them (%s consecutive soft bounce(s) recorded, "
        "of %s before suppression) - AND THAT IS NOT A PASS: %s"
        % (softs, limit, WHAT_WOULD_ANSWER["bounce_recorder"]))


# --------------------------------------------------------------- canary/0002
#
# THE THIRTEEN. Until this block landed, every rule below `bounce_history`
# carried `ask: None` and answered UNKNOWN in every world, including the one
# where its own input held the exclusion - the defect TASK-0250 named for one
# row and audit/0001 measured for thirteen: 0 lane-closable, 13 operator,
# 0 provider-read, because the records these rows read live in the main
# checkout's gitignored work/. "The code is lane-buildable, the sight is
# not." This block is the lane-buildable half, built against synthetic
# records and pinned by tests/test_canary_0002_the_13_ask_functions.py:
# three controls per row - satisfies PASS, violates EXCLUDED, field absent
# UNKNOWN and never PASS.
#
# THE HOUSE RULES ALL THIRTEEN OBEY:
#
#   THROUGH THE DECLARED DECIDER. Every row calls the function its RULES
#   entry names - eligibility._suppressed, _client_own_domain,
#   _record_state, _replied, _paused, account.replies, mx.allows_email,
#   lint.sendable, hygiene.index/_from_contact/_from_account,
#   clientapproval.is_suppressed - and maps its answer. None re-implements
#   a decision, for the reason _ask_bounce_history gives: a second reading
#   drifts, and then the preflight and the send path disagree about the
#   same person. Private functions are called anyway, same precedent.
#
#   WHERE ONE DECIDER SERVES TWO ROWS, EACH ROW TAKES ONLY ITS DECLARED
#   BRANCH. _replied answers contact_flags (flag branch) and
#   contact_reply_event (event branch); _paused answers account_suppressed,
#   account_review_open and account_paused. A decider firing on another
#   row's branch reads as "did not fire" HERE - and the other row is the
#   one that excludes, so the table's verdict never depends on the split.
#
#   FAIL FIRST, FLOOR SECOND, PASS LAST. An exclusion found on a partial
#   record is still an exclusion - evaluate()'s own fires_on_partial
#   asymmetry, applied inside the ask. Only a PASS needs every field the
#   decider reads to be PRESENT: skeleton-guaranteed fields missing from
#   the record dict, and writer-added blocks no writer ever created, are
#   Undecided rather than "clean".
#
#   WRITER-ADDED ABSENCE IS UNKNOWN. `events`, `suppression`, `review` and
#   `paused` are created by their writers, never by store.new_record. No
#   production writer writes `unsubscribed: False` or `open: False` back,
#   so for those rows a PASS is reachable only where a writer (or a
#   synthetic plant) put the block down - and a real record no reply-policy
#   path ever touched reads UNKNOWN, never clear. Same shape as
#   bounce_history's "can EXCLUDE, never PASS", and named in the canary/0002
#   report rather than hidden.
#
# These are VERDICTS, not clearance. Clearance is the operator's judgement
# over the whole table; nothing in this block claims a contact is cleared.


def _matched_record_entry(rec, ctx):
    """(entry, None) or (None, why): THIS contact inside rec["contacts"].

    Two rows - `contact_flags` and `mx_and_verification` - read fields that
    live on the record's own contact entry rather than on the candidate row.
    The entry is found the way the codebase finds one: `lint.find_contact`
    by key first, then the one strong identity a cohort row and a record
    entry share by construction, the normalised email
    (`dedupe.normalise_email`). A name is never identity, here or anywhere.

    NOT FOUND IS UNKNOWN, NOT `blocked:contact_not_on_record`. That
    exclusion is `eligibility._identity`'s answer and NO row of this table
    declares it, so borrowing it here would print an exclusion nobody asked
    this row for. The honest cell is UNKNOWN, naming the gap.
    """
    from . import dedupe, lint

    if "contacts" not in rec:
        return None, ("the record carries no `contacts` list at all, so no "
                      "field of this person can be read from it")
    key = ctx.get("key")
    if key:
        entry = lint.find_contact(rec, key)
        if entry is not None:
            return entry, None
    want = dedupe.normalise_email(ctx.get("email"))
    if want:
        for entry in rec.get("contacts") or []:
            if dedupe.normalise_email(entry.get("email")) == want:
                return entry, None
    return None, ("the record's contact list does not carry this person "
                  "(key %r): eligibility._identity answers "
                  "blocked:contact_not_on_record for a contact missing from "
                  "the record, but no row of this table declares that "
                  "question, so this row answers UNKNOWN rather than "
                  "borrowing another decider's exclusion" % (key,))


def _ask_client_suppressed_drop(ctx):
    """Was this record dropped as a client suppression?

    THROUGH `eligibility._suppressed`, and only its `drop_reason` branch.
    The other two branches belong to other rows: the domain-list branch to
    `suppression_domain_list` (so `suppressed` is pinned to the empty set
    and `ingest.load_suppress` is never read here), the agency branch to
    `agency_dnc` (so `contact` stays None and `agencydnc.lookup` is never
    reached). The split is the table's, not the decider's.

    THE FIELD IS SKELETON-GUARANTEED, AND ITS ABSENCE IS STILL UNKNOWN.
    `store.REQUIRED` names `drop_reason`, so a validated queue record
    always carries it - but a record dict that does not is not a record
    this row guesses about: `.get()` would read a missing field as "no
    suppression recorded", and a missing field is not an answer.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    reason = eligibility._suppressed(rec, None, suppressed=set(),
                                     contact=None)
    if reason == eligibility.BLOCKED_CLIENT_SUPPRESSED:
        return ("the record's own drop_reason (%r) starts with 'suppress': "
                "eligibility._suppressed's drop_reason branch refuses it on "
                "every channel" % (rec.get("drop_reason"),))
    if "drop_reason" not in rec:
        return Undecided(
            "the record carries no `drop_reason` field at all - "
            "store.REQUIRED names it, so this record did not come through "
            "store.new_record or store.validate, and a missing field is "
            "not 'no suppression recorded'")
    return None


def _ask_client_own_domain(ctx):
    """Is this address at the client's OWN domain - their staff?

    THROUGH `eligibility._client_own_domain` (TASK-354), with the client
    config loaded HERE rather than left to the decider's default path,
    because that default is the fail-open audit/0001 named: when
    `clients.load` raises, `_client_own_domain` returns None - a PASS - and
    "the config could not be read" becomes "the address is not at the
    client's domain". This ask loads the config first and answers
    Undecided when it cannot, so the decider only ever runs with the
    domain in hand. The wrap is one-directional: it can turn a fake PASS
    into an UNKNOWN, never an UNKNOWN into a PASS.

    Email-channel row. The decider reads the CONTACT'S email, never the
    record's domain: a record for acme.test whose contact sits at the
    client's own domain is still refused.
    """
    from . import clients, eligibility

    rec = ctx.get("record") or {}
    client = rec.get("client")
    if not client:
        return Undecided("the record names no client, so the client's own "
                         "domain cannot be resolved")
    try:
        config = clients.load(client)
    except Exception as exc:                                    # noqa: BLE001
        return Undecided(
            "the client config for %r could not be loaded (%s: %s) - and "
            "that is UNKNOWN, not PASS: eligibility._client_own_domain "
            "returns None when clients.load raises, a fail-open this row "
            "does not inherit" % (client, type(exc).__name__, exc))
    client_domain = (config.get("domain") or "").strip().lower()
    if not client_domain:
        return Undecided(
            "the client config for %r carries no `domain`, so the question "
            "'is this address at the client's own domain' has no second "
            "term" % (client,))
    email = (ctx.get("email") or "").strip().lower()
    if not email:
        return Undecided("the candidate carries no email address, and this "
                         "row's decider reads the address, never the name")
    if eligibility._client_own_domain(rec, {"email": email}, config):
        return ("%s is at %s, the client's own domain: their staff, never "
                "a prospect - eligibility._client_own_domain refuses it"
                % (email, client_domain))
    return None


def _ask_record_state(ctx):
    """Is the record dropped, or in an unshippable state?

    THROUGH `eligibility._record_state` unchanged: state == "dropped", any
    drop_reason, or a state in `lint.UNSHIPPABLE` other than "pushed".
    FAIL FIRST, FLOOR SECOND: a record with no `state` field but a
    drop_reason still EXCLUDES, because an exclusion found on a partial
    record is still an exclusion; only the PASS needs every field the
    decider reads, and `state` is skeleton-guaranteed by store.REQUIRED.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    if eligibility._record_state(rec):
        return ("the record's own state refuses it (state=%r, "
                "drop_reason=%r): eligibility._record_state blocks a "
                "dropped record, any drop_reason, and any state in "
                "lint.UNSHIPPABLE other than pushed"
                % (rec.get("state"), rec.get("drop_reason")))
    if "state" not in rec:
        return Undecided(
            "the record carries no `state` field - store.REQUIRED names "
            "it, and a missing state is not a shippable one")
    return None


def _ask_contact_flags(ctx):
    """Does THIS contact's own entry on the record carry a stop flag?

    THROUGH `eligibility._replied` with the record's entry for this contact
    as its argument, and only its FLAG branch is this row's answer:
    unsubscribed/suppressed, stopped, paused - flags written on the contact
    by `accountpolicy.apply_reply` and its siblings, read as written and
    never re-derived from event text. The event branch
    (blocked:replied) is `contact_reply_event`'s declared question: when
    the decider fires THERE, this row answers "asked, did not fire" and
    the other row excludes. One function, two rows, each row its own
    branch - the split cannot lose an exclusion, because the branch not
    taken here is taken there.

    The entry is found through `_matched_record_entry`; a record whose
    contact list does not carry this person is UNKNOWN, never PASS.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    entry, why = _matched_record_entry(rec, ctx)
    if entry is None:
        return Undecided(why)
    reason = eligibility._replied(rec, entry)
    if reason in (eligibility.BLOCKED_UNSUBSCRIBED,
                  eligibility.BLOCKED_CONTACT_STOPPED,
                  eligibility.BLOCKED_CONTACT_PAUSED):
        return ("the record's own entry for this contact carries a stop "
                "flag (%s): eligibility._replied's flag branch, which "
                "must_not_contact refuses on every channel" % (reason,))
    return None


def _ask_contact_reply_event(ctx):
    """Did THIS person reply? The event branch of `eligibility._replied`.

    The decider is handed `{"key": key}` and not the record's entry, so
    the flag branch cannot fire in this row - flags are `contact_flags`'
    question - and the only answer this decider can give here is
    blocked:replied or None. `events.is_reply` decides what a reply event
    is; this ask does not.

    AND NO `events` LIST IS UNKNOWN, NOT PASS - TASK-0250's doctrine, one
    row over. `rec["events"]` is writer-added (`events.record` creates it
    by setdefault), so a record no event writer ever touched carries no
    list at all, and "this person never replied" is indistinguishable from
    "no reply recorder ever ran for this record". An empty list a writer
    created is an answer; an absent list is not.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    key = ctx.get("key")
    if not key:
        return Undecided("the candidate carries no key, and the event "
                         "branch matches reply events by contact key")
    if eligibility._replied(rec, {"key": key}) == \
            eligibility.BLOCKED_REPLIED:
        return ("a reply event is recorded against this contact in the "
                "record's event log: eligibility._replied's event branch "
                "ends the sequence, and suppression.decide step 2 refuses "
                "the send")
    if "events" not in rec:
        return Undecided(
            "the record carries no `events` list at all - it is "
            "writer-added, so absence is not 'no reply recorded' but 'no "
            "event writer ever ran for this record', and this row will "
            "not read the second as the first (the TASK-0250 doctrine)")
    return None


def _ask_account_suppressed(ctx):
    """Did the COMPANY ask not to be contacted?

    THROUGH `eligibility._paused` with an empty contact dict, so the
    contact-paused branch cannot fire in this row (that is
    `contact_flags`' flag read); the answer this row takes is its FIRST
    branch only, blocked:account_suppressed - the most final one, which
    `_paused` checks before review, pause and contact flags. A decider
    that fires on a LATER branch answers "did not fire" here, because
    those are `account_review_open`'s and `account_paused`'s rows and one
    of them excludes.

    NO `suppression` BLOCK IS UNKNOWN, NOT PASS. Its only writer is
    `accountpolicy._suppress_account`, which writes `unsubscribed: True`;
    no production writer ever writes the block back as False. A record
    without the block is a record the suppression path never touched -
    which the record itself cannot distinguish from a suppression nobody
    recorded - and this row refuses to read either as clearance. The
    satisfies arm exists only where a writer, or a synthetic plant, put
    the block down.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    if eligibility._paused(rec, {}) == \
            eligibility.BLOCKED_ACCOUNT_SUPPRESSED:
        return ("the record's `suppression` block carries unsubscribed: "
                "the company asked not to be contacted. "
                "accountpolicy._suppress_account is the block's only "
                "writer, and eligibility._paused reports it as the most "
                "final answer there is")
    if "suppression" not in rec:
        return Undecided(
            "the record carries no `suppression` block. Its only writer "
            "writes unsubscribed: True and nothing ever writes the block "
            "back False, so an absent block is not a recorded 'not "
            "suppressed' - it is a question no writer ever answered for "
            "this record")
    return None


def _ask_account_review_open(ctx):
    """Is a human review open on this account?

    THROUGH `eligibility._paused`'s second branch, blocked:review_required.
    The same writer-added absence doctrine as the row above: `rec["review"]`
    is created by `accountpolicy._require_review`, which writes
    `{"open": True, ...}`, and NO production writer ever records a review
    closed by writing open: False - the block is simply absent from a
    record no review was ever opened on. Absent is therefore UNKNOWN:
    "no review is open" and "no review writer ever ran here" are the same
    missing block, and this row will not report the second as the first.
    """
    from . import eligibility

    rec = ctx.get("record") or {}
    if eligibility._paused(rec, {}) == \
            eligibility.BLOCKED_REVIEW_REQUIRED:
        return ("a human review is open on this account: the record's "
                "`review` block carries open: True, which "
                "eligibility._paused refuses the whole company on")
    if "review" not in rec:
        return Undecided(
            "the record carries no `review` block. Its only writer writes "
            "open: True and no writer ever records a review closed, so an "
            "absent block cannot be read as 'no review is open'")
    return None


def _ask_account_paused(ctx):
    """Is the account paused by the reply policy?

    THROUGH `eligibility._paused` via `cadence.pause_state`, the row's
    declared decider, taking only its blocked:company_paused answer.
    pause_state composes four sources - the suppression block,
    `rec["paused"]`, an open review, and the event log (a booked meeting,
    or a reply whose policy holds the account) - and the event-log sources
    are why FAIL is asked BEFORE the floor: a meeting pauses the company
    with no `paused` field ever written, and an exclusion found on a
    partial record is still an exclusion. The other two sources are other
    rows' branches and answer "did not fire" here.

    THE FLOOR IS `rec["paused"]`, writer-added by
    `accountpolicy._hold_account` and by `inbound`'s restore - which may
    write None, the one production negative this row can PASS on. Absent,
    "not paused" is indistinguishable from "the reply-policy path never
    ran for this record": UNKNOWN.
    """
    from . import cadence, eligibility

    rec = ctx.get("record") or {}
    if eligibility._paused(rec, {}) == \
            eligibility.BLOCKED_COMPANY_PAUSED:
        pause = cadence.pause_state(rec) or {}
        return ("the account is paused by the reply policy (%s since %s): "
                "cadence.pause_state, which eligibility._paused reports "
                "as blocked:company_paused"
                % (pause.get("reason"), pause.get("since")))
    if "paused" not in rec:
        return Undecided(
            "the record carries no `paused` field. Its writers are "
            "accountpolicy._hold_account and inbound's restore (which may "
            "write None), so an absent field is not a recorded 'not "
            "paused' - it is a policy path that never ran here")
    return None


def _ask_account_reply_log(ctx):
    """A reply in the account's log, whether or not flagged on the contact.

    THROUGH `account.replies(rec, key)` - the exact read
    `suppression.decide`'s step 2 makes when step 1 found no flag: "a
    reply recorded against the contact but not flagged on it is still a
    reply". Keyed, as step 2 keys it; unscoped, `account.replies` answers
    with the WHOLE account's replies, which is `account_paused`'s question
    and not this one. What counts as a reply event is `account.replies`'
    own type set - REPLY_RECEIVED, REPLY_CLASSIFIED,
    POSITIVE_REPLY_DETECTED - not a list spelled out here.

    NO `events` LIST IS UNKNOWN - the same writer-added absence as
    `contact_reply_event`, and `account.replies`' own `or []` is exactly
    the silent-empty read this row refuses to inherit.
    """
    from . import account

    rec = ctx.get("record") or {}
    key = ctx.get("key")
    if not key:
        return Undecided("the candidate carries no key, and "
                         "account.replies unscoped would answer with the "
                         "whole account's replies - suppression.decide "
                         "step 2 asks it keyed")
    found = account.replies(rec, key)
    if found:
        return ("%d reply event(s) recorded against this contact in the "
                "account's log (%s), whether or not any flag was written "
                "on the contact: suppression.decide step 2 appends "
                "blocked:replied on exactly this read"
                % (len(found),
                   ", ".join(str(f.get("type")) for f in found)))
    if "events" not in rec:
        return Undecided(
            "the record carries no `events` list at all - account.replies "
            "reads a missing list as [] through `or []`, and an empty "
            "answer from a list no writer ever created is not 'no reply "
            "recorded'")
    return None


def _ask_mx_and_verification(ctx):
    """Can this address receive mail, and is it verified to the client's policy?

    The two legs `channels.email_verdict` composes after the flag and
    bounce legs other rows own, each asked through its own decider:
    `lint.sendable` under `lint.policy_for_record` for verification, and
    `mx.allows_email` for the channel. Neither leg is re-implemented, and
    the earlier legs are deliberately NOT composed in here:
    operator_exclusion, suppression, agency_dnc and bounce_history are
    their own rows, and folding them in would let one row's exclusion be
    reported under another row's name.

    THE VERIFICATION LEG FAILS ON ABSENT EVIDENCE, AND THAT IS THE
    DECIDER'S OWN ANSWER, not an absence floor: `verification.decide([])`
    returns unknown / not sendable, "no verification evidence", and
    CLAUDE.md makes that a hard rule - no email is generated for an
    unverified address. An unverified address is a VIOLATED row, not an
    unanswered one; the asymmetry with the MX leg below is the two
    deciders' own, and this ask reports each as its decider decides.

    THE MX LEG FAILS OPEN IN PRODUCTION, AND THIS ROW WRAPS IT.
    `mx.allows_email` answers (True, "no MX check has been run") for a
    contact with no stored `mx` block. A check nobody ran is not
    clearance, so the wrap turns that one fail-open into Undecided - the
    only such wrap among the thirteen, and like the row-2 wrap it is
    one-directional: it can never turn an UNKNOWN into a PASS. When the
    block IS stored, `allows_email` re-derives the verdict from the stored
    hostnames and ignores the stored verdict, so a hand-flipped
    `email_cadence_allowed` changes nothing here either.

    FAIL FIRST: verification is asked before the MX floor, so an
    unverified address EXCLUDES even when the MX block is absent.

    The client config is loaded for the MX policy leg only, and a load
    that raises falls back to `mx.settings(None)`'s defaults - the same
    doctrine `lint.policy_for_record` already chose for verification ("a
    missing or unreadable client config must not decide that an address is
    sendable; None means the default policy, which is the conservative
    one").
    """
    from . import clients, lint, mx, verification

    rec = ctx.get("record") or {}
    entry, why = _matched_record_entry(rec, ctx)
    if entry is None:
        return Undecided(why)
    try:
        config = clients.load(rec.get("client")) \
            if rec.get("client") else None
    except Exception:                                       # noqa: BLE001
        config = None
    policy = lint.policy_for_record(rec)
    if not lint.sendable(entry, policy):
        decision = verification.resolve(entry, policy)
        return ("the address is not sendable under this client's "
                "verification policy (%s: %s; %d of %d required "
                "confirmations from %s): channels.email_verdict refuses an "
                "unverified address, and no email is generated for one"
                % (decision["state"], decision["reason"],
                   decision["confirmation_count"],
                   decision["required_confirmations"],
                   ", ".join(decision["confirmed_by"]) or "nobody"))
    if not entry.get("mx"):
        return Undecided(
            "the record's entry for this contact carries no `mx` block: "
            "mx.allows_email answers (True, 'no MX check has been run') "
            "for it - a fail-open this row wraps into UNKNOWN, because a "
            "check nobody ran is not clearance")
    allowed, mx_why = mx.allows_email(entry, config)
    if not allowed:
        return ("MX policy closes the email channel for this address (%s): "
                "channels.email_verdict re-derives the same decision from "
                "the stored hostnames and refuses the send" % (mx_why,))
    return None


def _ask_hygiene_workspace_history(ctx):
    """Have WE WORKED THIS PERSON before, by strong identity?

    `hygiene.check`'s step 2 through hygiene's own functions: the index is
    `hygiene.index()` over `store.load()` - the whole queue, which is the
    workspace history this row declares - the identity keys are
    `_candidate_keys`, one matched history's verdict is `_from_contact`,
    and `worst()` orders multiple matches exactly as `check` orders them.
    Nothing is re-implemented.

    NO STRONG IDENTIFIER IS UNKNOWN. Email, LinkedIn profile or provider
    id - a name and a company are never identity, in hygiene or anywhere.
    A candidate carrying none cannot be matched, and "could not be
    matched" is not "no history exists".

    The index covers the WHOLE queue, deliberately: hygiene's suppression
    verdicts are agency-level, and a person we worked for another client
    is still a person we worked. Where a per-workspace scoping would
    answer differently, the more conservative answer is the one this row
    gives.
    """
    from . import hygiene

    try:
        history = hygiene.index()
    except Exception as exc:                                    # noqa: BLE001
        return Undecided("the workspace history index could not be built "
                         "from the queue authority: %s: %s"
                         % (type(exc).__name__, exc))
    keys = hygiene._candidate_keys(ctx)
    if not keys:
        return Undecided("the candidate carries no strong identifier "
                         "(email, LinkedIn profile or provider id), so "
                         "hygiene.check's step 2 has nothing to match on "
                         "- identity is proved, never guessed")
    verdicts, matched = [], []
    for key in keys:
        for facts in history["by_identity"].get(key, ()):
            verdict, why = hygiene._from_contact(facts)
            verdicts.append(verdict)
            matched.append((key, verdict, why))
    if not verdicts:
        return None      # asked, matched nothing: hygiene's own FRESH path
    worst = hygiene.worst(verdicts)
    if worst != hygiene.FRESH:
        key, _verdict, why = next(m for m in matched if m[1] == worst)
        return ("we have worked this person before: %s - %s (matched on "
                "%s, worst of %d matched history row(s)): hygiene.check "
                "step 2" % (worst, why, key, len(matched)))
    return None


def _ask_hygiene_account_history(ctx):
    """Have we worked THIS COMPANY before?

    `hygiene.check`'s step 3 through `_from_account`, INCLUDING the
    seen-keys exclusion step 2 applies: contacts already matched by strong
    identity answer for themselves, and the account row must not restate
    their history as a vaguer one. The account's OWN state - a
    suppression, a hold - still applies to everybody including them,
    because that is a fact about the company; `_from_account` reads it,
    not this ask. `_from_account` is handed config=None, so a positive
    reply elsewhere resolves under the default reply policy - the same
    answer `check` gives a caller with no client config in hand, and the
    config can move ACTIVE_CONVERSATION to PREVIOUSLY_CONTACTED but never
    either to FRESH, so no policy choice can turn this row's FAIL into a
    PASS.

    NO DOMAIN IS UNKNOWN: step 3 matches the account on its normalised
    domain, and a candidate without one cannot be asked. A POPULATED
    queue holding no record at this domain IS an answer - nobody has
    worked the company - and passes, exactly as `check` passes it; the
    queue's own PRESENT_EMPTY floor is evaluate()'s gate, upstream of
    this ask.
    """
    from . import dedupe, hygiene

    domain = dedupe.normalise_domain(ctx.get("domain"))
    if not domain:
        return Undecided("the candidate carries no domain, and "
                         "hygiene.check's step 3 matches the account on "
                         "its normalised domain: the account question "
                         "cannot be asked")
    try:
        history = hygiene.index()
    except Exception as exc:                                    # noqa: BLE001
        return Undecided("the workspace history index could not be built "
                         "from the queue authority: %s: %s"
                         % (type(exc).__name__, exc))
    seen = set()
    for key in hygiene._candidate_keys(ctx):
        for facts in history["by_identity"].get(key, ()):
            seen.add(facts["contact_key"])
    verdicts, reasons = [], []
    for entry in history["by_domain"].get(domain, ()):
        verdict, why = hygiene._from_account(entry, None, exclude=seen)
        if verdict != hygiene.FRESH:
            verdicts.append(verdict)
            reasons.append(why)
    if verdicts:
        return ("we have worked this company before: %s - %s "
                "(hygiene.check step 3, domain %s)"
                % (hygiene.worst(verdicts), reasons[0], domain))
    return None


def _ask_client_approval_register(ctx):
    """Did THE CLIENT remove this domain from a snapshot, for good?

    `hygiene.check` step 0 through `clientapproval.is_suppressed`. The
    register is NOT one of this module's eight declared authorities, so
    evaluate()'s five-state gate never sees it - the state discipline is
    enforced here, in the ask, in the states' own order:

      ABSENT     -> UNKNOWN. `clientapproval.load()` answers [] for a
                    missing file and `is_suppressed` answers False for
                    []: a PASS manufactured by an absent authority. This
                    is the SPEC HAZARD audit/0001 named, and it is why the
                    file is stat'ed before anything is read.
      UNREADABLE -> UNKNOWN, the raise named.
      EMPTY      -> UNKNOWN. PRESENT_EMPTY is not an answer for any rule
                    whose question is "is this in here" - this module's
                    own TASK-0190 doctrine, applied to a file the gate
                    cannot see. A suppression is born from a snapshot
                    DIFF; a register that never held a row is a client
                    who was never asked.
      POPULATED  -> the decider decides: a PERMANENT row (suppressed or
                    rejected; last row wins unless a later row names it
                    in `reverses`) EXCLUDES, and anything else passes
                    THIS row.

    WHAT THIS ROW DOES NOT ASK: `clientapproval.require_approved` -
    "unknown is pending and pending is refused" - is the stricter SPEND
    gate, and no row of this table declares it. A domain the register
    never heard of PASSES here and would be REFUSED there. The difference
    is named in the canary/0002 report rather than papered over.

    The register path is `clientapproval.path()`: the CLIENT_APPROVAL env
    or beside `store.queue_path()`, so in the operator's real run it is
    the main checkout's work/client-approval.jsonl - the same resolution
    the decider itself uses, never a path spelled out here.
    """
    from . import clientapproval, dedupe

    domain = dedupe.normalise_domain(ctx.get("domain"))
    if not domain:
        return Undecided("the candidate carries no domain, and client "
                         "approval is per account: the question cannot be "
                         "asked")
    rec = ctx.get("record") or {}
    client = rec.get("client")
    if not client:
        return Undecided("the record names no client, and the register is "
                         "per client - never shared across them")
    path = clientapproval.path()
    if not os.path.exists(path):
        return Undecided("the client-approval register is ABSENT at %s: "
                         "clientapproval.load() answers [] for a missing "
                         "file and is_suppressed would read that [] as "
                         "'not suppressed' - a clearance manufactured by "
                         "an absent authority, which this row refuses"
                         % (path,))
    try:
        rows = clientapproval.load()
    except Exception as exc:                                    # noqa: BLE001
        return Undecided("the client-approval register at %s could not be "
                         "read: %s: %s" % (path, type(exc).__name__, exc))
    if not rows:
        return Undecided("the client-approval register at %s is PRESENT "
                         "but EMPTY: a suppression is born from a snapshot "
                         "diff, and a register that never held a row is a "
                         "client who was never asked - PRESENT_EMPTY is "
                         "not an answer" % (path,))
    if clientapproval.is_suppressed(domain, client, rows=rows):
        row = clientapproval.state_of(domain, client, rows=rows) or {}
        return ("the client's approval register carries %s for %s (by %s "
                "at %s): permanent, per workspace, and no re-sourcing "
                "brings it back - hygiene.check step 0 refuses the row "
                "before any contact-level question is asked"
                % (row.get("state"), domain, row.get("who"),
                   row.get("at")))
    return None


RULES = (
    # ---- answerable from an address and a tracked register
    {"name": "operator_exclusion_address",
     "decides": "operatorexclusion.blocks_address / blocks_domain, reached "
                "from eligibility._operator_excluded",
     "channel": "both",
     "needs": ("operator_exclusion_register",),
     "ask": _ask_operator_excluded_address,
     "about": "this person's own mailbox is at a permanently excluded "
              "address or domain - the check that caught our own 225 sending "
              "addresses passing as recipients"},
    {"name": "operator_exclusion_company",
     "decides": "operatorexclusion.blocks_domain, reached from "
                "eligibility._operator_excluded",
     "channel": "both",
     "needs": ("operator_exclusion_register",),
     "ask": _ask_operator_excluded_company,
     "about": "the company is permanently excluded"},
    {"name": "suppression_domain_list",
     "decides": "eligibility._suppressed via ingest.load_suppress",
     "channel": "both",
     # BOTH HALVES. `load_suppress` merges the tracked template with the
     # gitignored roster and reports neither, so a missing roster makes this
     # rule unanswerable even though the template is right there.
     "needs": ("suppression_template", "suppression_local_roster"),
     "ask": _ask_suppressed_domain,
     # `load_suppress` UNIONS the two files, so whichever half is on disk can
     # still fire - see the asymmetry note in `evaluate`.
     "fires_on_partial": True,
     "about": "the company is on the never-sequence domain list"},
    {"name": "agency_dnc",
     "decides": "agencydnc.lookup, reached from eligibility._suppressed",
     "channel": "both",
     "needs": ("agency_dnc",),
     "ask": _ask_agency_dnc,
     "about": "this person told Resonate directly not to contact them, in "
              "any workspace"},

    # ---- need the queue record, and say so
    {"name": "internal_campaign_membership",
     "decides": "campaignmembership.lookup, classified by "
                "providerwrites.classify_campaign - the preflight only. NO "
                "SEND PATH ASKS THIS",
     "channel": "both",
     "needs": ("internal_campaign_declaration", "campaign_ledger",
               "campaign_lead_rows"),
     "ask": _ask_internal_campaign_membership,
     # A MATCH FIRES EVEN HALF-BLIND. A lead row in a DECLARED internal
     # campaign needs only the declaration, so it is an exclusion whether or
     # not the ledger is readable - and a non-match on a partial read is
     # UNKNOWN, which is what `fires_on_partial` already means here.
     "fires_on_partial": True,
     "about": "CLAUDE.md standing rule 2 and docs/OPERATING-MODE.md: anyone "
              "with a lead row in an internal or unknown-owner campaign is "
              "NOT CLEAN for outreach, whoever owns them. Until TASK-0200 "
              "nothing asked this of a CONTACT, so a member of every "
              "declared internal campaign passed all twenty-two rules"},
    {"name": "client_suppressed_drop",
     "decides": "eligibility._suppressed, the `drop_reason` branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_client_suppressed_drop,
     "about": "the client suppressed this record"},
    {"name": "client_own_domain",
     "decides": "eligibility._client_own_domain",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": _ask_client_own_domain,
     "about": "the address is at the client's own domain - their staff, "
              "never a prospect"},
    {"name": "record_state",
     "decides": "eligibility._record_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_record_state,
     "about": "dropped, or in an unshippable state. Whether `held` and "
              "`drafted` block a send is recorded as UNSETTLED in the "
              "approval sheet's own note, and enforced in code regardless"},
    {"name": "contact_flags",
     "decides": "eligibility._replied, the flag branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_contact_flags,
     "about": "unsubscribed, suppressed, stopped or paused on the contact"},
    {"name": "contact_reply_event",
     "decides": "eligibility._replied, the event branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_contact_reply_event,
     "about": "this person replied; their sequence is answered"},
    {"name": "account_suppressed",
     "decides": "eligibility._paused, the account suppression branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_account_suppressed,
     "about": "the company asked not to be contacted"},
    {"name": "account_review_open",
     "decides": "eligibility._paused, the open-review branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_account_review_open,
     "about": "a human review is open on this account"},
    {"name": "account_paused",
     "decides": "eligibility._paused via cadence.pause_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_account_paused,
     "about": "the account is paused by reply policy"},
    {"name": "account_reply_log",
     "decides": "suppression.decide step 2 via account.replies",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_account_reply_log,
     "about": "a reply recorded against the contact but not flagged on it is "
              "still a reply"},
    {"name": "bounce_history",
     "decides": "channels._bounced, and bouncepolicy.decide for the "
                "hard/soft split",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     # TASK-0250: `None` UNTIL 2026-10-16, and that is the defect it closed.
     # With the queue POPULATED and the record supplied carrying a hard
     # bounce, the cell still read UNKNOWN "this rule has no form that can be
     # evaluated" - so the one rule in the table whose whole job is to see a
     # bounce could not report one it was holding.
     "ask": _ask_bounce_history,
     "about": "this address has already bounced. Keyed to the CONTACT, not "
              "the account"},
    {"name": "mx_and_verification",
     "decides": "channels.email_verdict via mx.allows_email and the client's "
                "verification policy",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": _ask_mx_and_verification,
     "about": "the address cannot receive mail, or is not verified to this "
              "client's policy. No email is generated for an unverified "
              "address"},
    {"name": "hygiene_workspace_history",
     "decides": "hygiene.check step 2 via hygiene.index",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_hygiene_workspace_history,
     "about": "we have worked this person before, by strong identity"},
    {"name": "hygiene_account_history",
     "decides": "hygiene.check step 3",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_hygiene_account_history,
     "about": "we have worked this company before"},
    {"name": "client_approval_register",
     "decides": "hygiene.check step 0 via clientapproval.is_suppressed",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": _ask_client_approval_register,
     "about": "the client removed this domain from a snapshot: permanent, "
              "per workspace, and no re-sourcing brings it back"},

    # ---- need a provider read this task may not make
    {"name": "hold_active_sequence",
     "decides": "suppression.decide, HOLD_ACTIVE_SEQUENCE",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "they are in an active sequence somewhere, on any channel, "
              "belonging to anyone"},
    {"name": "hold_recent_touch",
     "decides": "suppression.decide, HOLD_RECENT_TOUCH "
                "(hold_after_last_touch_days, default 30)",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "a last touch inside the window holds, whoever made it"},
    {"name": "hold_total_sends",
     "decides": "suppression.decide, HOLD_SEND_VOLUME "
                "(hold_above_total_sends, default 10)",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "more than the configured lifetime sends holds for manual "
              "review"},
    {"name": "cooling_90_days",
     "decides": "suppression.decide, `cooled` from thresholds()['cooling_days']",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "the operator-confirmed 90 days. It LIFTS the volume hold "
              "rather than imposing one, and it is computed from the same "
              "provider last-touch this file may not read"},
)

RULE_NAMES = tuple(r["name"] for r in RULES)

#: Rules declaring no authority file at all. TASK-0190 §3: such a rule may
#: not report PASS, and the declaration itself is the defect - so it is
#: LISTED and printed rather than tolerated silently.
#:
#: All four entries today are the provider-read rules, which are UNKNOWN by
#: their own declaration before the floor in `evaluate` is reached. That is
#: why the list being non-empty is not an alarm; a name here that is NOT a
#: provider-read rule is.
RULES_WITHOUT_DECLARED_AUTHORITY = tuple(
    r["name"] for r in RULES if not r["needs"])


# ------------------------------------- rules expected and NOT found in code
#
# "A rule you cannot locate in code does not exist for this purpose. Say
# which ones you expected and did not find." - TASK-0170.
#
# These are DECLARED somewhere this project treats as authority and have no
# implementation on any path that could exclude a contact from a send. They
# are not in `RULES` because a row there implies something asks it; they are
# here because the gap is the finding.
#
# Each one is pinned by a test, in BOTH directions: if an implementation
# appears, the test fails and the entry has to be deleted rather than
# quietly outliving its own gap.

RULES_EXPECTED_BUT_NOT_FOUND = (
    {
        # REWRITTEN BY TASK-0200, NOT DELETED, and the distinction is the
        # finding: the rule now exists IN THE PREFLIGHT and still does not
        # exist on any send path. A preflight gate is not a send gate. A
        # cohort that goes out through `eligibility.must_not_contact`
        # without this instrument is checked by nothing, exactly as before.
        "name": "internal_campaign_membership_on_the_send_path",
        "declared_in": "CLAUDE.md standing rule 2 and docs/OPERATING-MODE.md: "
                       "\"anyone with a lead row in 327/328/352 is NOT CLEAN "
                       "for outreach, whoever owns them\", and UNKNOWN means "
                       "do-not-touch and members NOT CLEAN",
        "what_exists": "TWO THINGS NOW. providerwrites carries the "
                       "three-state classifier - RESONATE_OS / "
                       "RESONATE_INTERNAL / UNKNOWN_OWNER - governing "
                       "provider WRITES TO A CAMPAIGN; and since "
                       "TASK-0200 the "
                       "`internal_campaign_membership` rule in RULES above "
                       "asks it OF A CONTACT, through campaignmembership and "
                       "the same classifier",
        "what_is_missing": "nothing in eligibility, suppression, hygiene or "
                           "channels asks it. The preflight refuses; a send "
                           "that does not go through the preflight is "
                           "checked by nobody, and `must_not_contact` is "
                           "what the send path actually calls",
        "would_need": "the same rule on the enrol path, which needs the "
                      "lead-row listing to be readable at send time rather "
                      "than at preflight time - a different question about "
                      "freshness, and an operator decision about what a "
                      "stale listing licenses",
    },
    {
        "name": "ninety_day_no_contact",
        "declared_in": "the operator's confirmed 90-day cooling rule, carried "
                       "in suppression.DEFAULTS as cooling_days: 90",
        "what_exists": "cooling_days=90 is real and is consulted - but it "
                       "LIFTS the volume hold, it does not impose a hold. The "
                       "recency hold is hold_after_last_touch_days, default "
                       "30",
        "what_is_missing": "no rule refuses a contact BECAUSE they were "
                           "contacted within 90 days. A contact touched 45 "
                           "days ago passes the recency hold and the cooling "
                           "window does not re-impose it",
        "would_need": "an operator decision on which of the two the 90 days "
                      "is, and then either a threshold change or a new rule. "
                      "It is a one-line config change if the answer is 90, "
                      "and this file must not guess",
    },
    {
        "name": "self_send_exclusion_as_its_own_rule",
        "declared_in": "the task's own list of rules to enumerate",
        "what_exists": "it IS implemented, in two places: the estate's own "
                       "225 sending addresses are entries in the operator "
                       "exclusion register, and eligibility._client_own_domain "
                       "refuses an address at the client's own domain",
        "what_is_missing": "nothing, but it is not where a reader would look "
                           "and it is not one rule. Named here so a future "
                           "audit does not conclude it is absent and add a "
                           "third implementation",
        "would_need": "nothing. This entry is a pointer, not a gap",
    },
)

EXPECTED_NOT_FOUND_NAMES = tuple(r["name"]
                                 for r in RULES_EXPECTED_BUT_NOT_FOUND)

def production_work():
    """Where production `work/` actually is, which is NOT this tree's.

    `store.PRODUCTION_WORK` resolves against the CALLING tree's root, so a
    preflight run from any worktree resolves the queue to that worktree's own
    empty `work/` - and `store.load()` answers 0 rows without raising. That
    is the same per-tree resolution that made six concurrent suite runs
    serialise nothing, and CLAUDE.md names the one path that is identical
    from the main checkout and from every worktree:
    `git rev-parse --path-format=absolute --git-common-dir`.

    Reported, never read. A RELATIVE answer from git is refused rather than
    resolved, because `abspath` would resolve it against the caller's cwd and
    reintroduce the per-tree path this function exists to escape.
    """
    import subprocess

    try:
        done = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception as exc:                                    # noqa: BLE001
        return None, "git could not be asked: %s" % (type(exc).__name__,)
    out = (done.stdout or "").strip()
    if done.returncode != 0 or not out:
        return None, "git refused: %s" % ((done.stderr or "").strip()[:160],)
    if not os.path.isabs(out):
        return None, "git answered a relative path (%r); refusing to resolve "                     "it against this tree's cwd" % (out,)
    return os.path.join(os.path.dirname(out), "work"), "from --git-common-dir"


#: The instrument's own files. A provenance line that names a SHA not
#: carrying these is an unverified claim about where the table came from.
INSTRUMENT_FILES = ("src/preflight.py", "scripts/canary_preflight.py")


def _git(args, runner=None):
    """Run one git command from the repository root. Returns (rc, out, err).

    `runner` exists so the refusal paths can be tested without needing a
    branch shaped to produce them; the default is the real git.
    """
    if runner is not None:
        return runner(list(args))
    import subprocess

    try:
        done = subprocess.run(
            ["git"] + list(args), capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception as exc:                                    # noqa: BLE001
        return 128, "", "git could not be asked: %s" % (type(exc).__name__,)
    return done.returncode, done.stdout or "", done.stderr or ""


def provenance(sha=None, runner=None):
    """The SHA the check ran at, and whether that SHA CARRIES the instrument.

    TASK-0170's own report named `117d96595` as the SHA it ran at, and
    `src/preflight.py` and `scripts/canary_preflight.py` are ABSENT from git
    at that SHA - they first exist at `045babe5f`. The run was made from a
    tree holding them uncommitted and `--sha` was free text, so the one line
    a reader needs in order to reproduce the table pointed at a commit that
    does not contain the instrument. A provenance line nobody measures is
    this repository's signature defect wearing the costume of an audit trail.

    Three states per file, not two, the same discipline `authorities()` uses:

        ABSENT     the blob is not at that SHA at all
        MODIFIED   it is there and differs from what actually ran
        CONFIRMED  it is there and is byte-identical to the working tree

    The comparison is `git diff --quiet <sha> -- <path>` rather than a hash
    of the file, because this tree is MIXED - `requirements.txt` is CRLF and
    the instrument's own files are LF - and `git hash-object` without
    `--path` applies no filter, so a raw hash would report MODIFIED for a
    line ending. git normalises; a hand-rolled comparison would not.

    UNKNOWN is not a pass here either: if git cannot be asked, the answer is
    not confirmed. Read-only - `rev-parse`, `cat-file -e` and `diff` only.
    """
    rc, out, err = _git(["rev-parse", "HEAD"], runner=runner)
    head = (out or "").strip()
    if sha is None:
        if rc != 0 or not head:
            return {"sha": None, "confirmed": False, "files": {},
                    "detail": "UNKNOWN - git could not name HEAD: %s"
                              % (err.strip()[:160],)}
        sha = head

    files, bad = {}, []
    for path in INSTRUMENT_FILES:
        rc, _, _ = _git(["cat-file", "-e", "%s:%s" % (sha, path)],
                        runner=runner)
        if rc != 0:
            files[path] = "ABSENT"
            bad.append("%s is ABSENT at %s" % (path, sha))
            continue
        rc, _, err = _git(["diff", "--quiet", sha, "--", path], runner=runner)
        if rc == 0:
            files[path] = "CONFIRMED"
        elif rc == 1:
            files[path] = "MODIFIED"
            bad.append("%s at %s is MODIFIED relative to the tree that ran"
                       % (path, sha))
        else:
            files[path] = "UNKNOWN"
            bad.append("%s could not be compared at %s: %s"
                       % (path, sha, err.strip()[:120]))

    return {"sha": sha, "confirmed": not bad, "files": files,
            "detail": "; ".join(bad) if bad
                      else "both instrument files CONFIRMED at this SHA"}


#: What would answer each unanswerable class, named once rather than per row.
WHAT_WOULD_ANSWER = {
    "queue": "a read of the canonical queue - `store.load()` against the "
             "production work/ directory, which this task's boundaries "
             "forbid",
    "provider_read": "one fully paginated EmailBison and HeyReach read of "
                     "every campaign's lead and send rows for these "
                     "addresses, which this task's boundaries forbid",
    # TASK-0250. The third thing that is unavailable here, and unlike the
    # other two it is not a read this task declined to make - it is a read
    # NOBODY can make, because the failure it would look for is not recorded
    # anywhere a verdict consults.
    "bounce_recorder": "something that reaches a verdict from the bounce "
                       "recorder's own health. TASK-0220 measured the "
                       "recorder's failure line - emitted by "
                       "scripts/bison_watch_loop.py, and its exact text is "
                       "kept out of src/ on purpose, see "
                       "_ask_bounce_history - with ONE writer and ZERO "
                       "readers, so an empty event list cannot be told apart "
                       "from a recorder that has been failing for an "
                       "unbounded time with the watcher still reporting UP. "
                       "Until a reader of that failure reaches a verdict, a "
                       "missing bounce event licenses no PASS",
}


def evaluate(contact, state=None, channel="email"):
    """One contact's row: a cell per rule, plus whether they are cleared.

    THE ORDER IS THE POINT. The authority is checked before the rule, so a
    rule whose list is not on disk is UNKNOWN rather than silently clean -
    see this module's docstring for the `agencydnc` measurement that makes
    that necessary.
    """
    state = authorities() if state is None else state
    # THE CHANNEL IS PART OF THE QUESTION, so it is part of what a rule is
    # asked. `internal_campaign_membership` answers EMAIL from a listing that
    # walked EmailBison and must answer UNKNOWN for LINKEDIN from the same
    # listing, because HeyReach was never walked - and a rule that cannot see
    # which channel it is being asked about cannot say that. Added as a key
    # rather than a second positional argument so every existing `ask`, and
    # every planted one in the tests, keeps working unchanged.
    ctx = dict(contact, channel=channel)
    cells = {}
    for rule in RULES:
        if rule.get("channel") not in ("both", channel):
            cells[rule["name"]] = {
                "cell": PASS, "why": "not consulted on the %s path" % channel,
                "not_applicable": True}
            continue
        # NOT `!= PRESENT`. PRESENT_EMPTY and PRESENT_POPULATED are both
        # "the file is there"; only the second can license a PASS.
        missing = [name for name in rule["needs"]
                   if state.get(name, {}).get("state") not in ANSWERABLE]
        if missing:
            why = "; ".join(
                "the %s authority is %s - %s"
                % (name, state.get(name, {}).get("state", "UNDECLARED"),
                   state.get(name, {}).get("why", "not in the table"))
                for name in missing)
            # WHAT AN EMPTY ONE MEANS, in the cell, for the reader who never
            # scrolls up to the authority table. A PRESENT_EMPTY authority is
            # the one state that looks like a healthy row at a glance.
            for name in missing:
                row = state.get(name, {})
                if row.get("state") == PRESENT_EMPTY:
                    why += "; WHICH MEANS: %s" % row.get("empty_means")
            # AN EXCLUSION FOUND ON A PARTIAL READ IS STILL AN EXCLUSION, and
            # a rule that did NOT fire on one has still not been answered.
            #
            # `bounce_stop_7day` states the same asymmetry one layer down and
            # it is `senderheadroom`'s: a PASS needs a complete read and a
            # STOP does not. Here: the tracked suppression template is on
            # disk while the real customer roster is absent, so a domain
            # found on the template is excluded whatever the roster says,
            # and a domain absent from the template proves nothing.
            if rule.get("fires_on_partial") and rule.get("ask"):
                try:
                    reason = rule["ask"](ctx)
                except Exception as exc:                        # noqa: BLE001
                    reason = None
                    why += ("; and the readable half raised %s: %s"
                            % (type(exc).__name__, str(exc)[:120]))
                else:
                    # AN `Undecided` IS NOT AN EXCLUSION. Every instance is
                    # truthy, so without this it would have been read as a
                    # reason and reported as a refusal - the safe direction
                    # and the wrong statement about a person.
                    if isinstance(reason, Undecided):
                        why += ("; the readable half WAS asked and could not "
                                "answer: %s" % (reason.why,))
                        reason = None
                    else:
                        why += ("; the readable half WAS asked and did not "
                                "fire, which is not an answer about the "
                                "missing half")
                if reason:
                    cells[rule["name"]] = {
                        "cell": EXCLUDED,
                        "why": "%s - found on the readable half, so the "
                               "missing one cannot change it" % reason}
                    continue
            cells[rule["name"]] = {"cell": UNKNOWN, "why": why}
            continue
        if rule.get("needs_provider_read"):
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "needs a provider read: %s"
                       % WHAT_WOULD_ANSWER["provider_read"]}
            continue
        if rule.get("needs_record") and not contact.get("record"):
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "needs this contact's queue record: %s"
                       % WHAT_WOULD_ANSWER["queue"]}
            continue
        if not rule["needs"]:
            # A RULE THAT DECLARES NO AUTHORITY MAY NOT REPORT PASS.
            # TASK-0190 §3. There is nothing whose state could make its PASS
            # true, so a PASS here would rest on no evidence at all - and a
            # rule reaching this line is a defect in the DECLARATION, which
            # `RULES_WITHOUT_DECLARED_AUTHORITY` lists and the report prints.
            #
            # The four provider-read rules declare none and are caught
            # above, by the branch that names the provider read; this is the
            # structural floor under any rule added later.
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "this rule declares no authority, so nothing could "
                       "make a PASS true. A declaration defect, listed in "
                       "RULES_WITHOUT_DECLARED_AUTHORITY"}
            continue
        ask = rule.get("ask")
        if ask is None:
            # DECLARED UNANSWERABLE, which is not the same as unasked. A rule
            # with no address-only form and all its authorities present still
            # has nothing to go on here, and saying so by name is the whole
            # value of the row.
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "this rule has no form that can be evaluated without "
                       "a record or a provider read"}
            continue
        try:
            reason = ask(ctx)
        except Exception as exc:                                # noqa: BLE001
            # A RULE THAT RAISED DID NOT PASS. Broad because one rule's
            # failure must not stop the other twenty being asked, and safe
            # because the direction is UNKNOWN - which clears nobody.
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "the rule raised %s: %s"
                       % (type(exc).__name__, str(exc)[:200])}
            continue
        # ORDER MATTERS AND IT IS NOT ALPHABETICAL. `Undecided` is truthy,
        # so it has to be tested before the exclusion branch or every UNKNOWN
        # becomes an EXCLUDED.
        if isinstance(reason, Undecided):
            cells[rule["name"]] = {"cell": UNKNOWN,
                                   "why": "asked and could not answer: %s"
                                          % (reason.why,)}
        elif reason:
            cells[rule["name"]] = {"cell": EXCLUDED, "why": reason}
        else:
            cells[rule["name"]] = {"cell": PASS, "why": "asked, did not fire"}

    excluded = sorted(n for n, c in cells.items() if c["cell"] == EXCLUDED)
    unknown = sorted(n for n, c in cells.items() if c["cell"] == UNKNOWN)
    return {
        "key": contact.get("key"),
        "name": contact.get("name"),
        "company": contact.get("company"),
        "email": contact.get("email"),
        "domain": contact.get("domain"),
        "channel": channel,
        "cells": cells,
        "excluded_by": excluded,
        "unknown_on": unknown,
        # CLEARED NEEDS EVERY CELL. Not "no exclusion found" - an exclusion
        # not found by a rule that never ran is not an absence of exclusions.
        "cleared": not excluded and not unknown,
        "verdict": (EXCLUDED if excluded else
                    UNKNOWN if unknown else PASS),
    }


def _utc_now():
    """The run time, to the minute, as a UTC instant. Never a local time."""
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%MZ")


def assess(contacts, state=None, channel="email", control_rows=None):
    """The whole table, the three totals and one verdict.

    THE THIRD TOTAL IS THE ONE THAT MATTERS: not-cleared-because-UNKNOWN. It
    is the number most likely to read zero because the instrument cannot see,
    so it is computed from the rows rather than from an absence of problems.
    """
    state = authorities() if state is None else state
    control_rows = list(control_rows or [])
    rows = [evaluate(c, state=state, channel=channel) for c in contacts or []]
    cleared = [r for r in rows if r["cleared"]]
    excluded = [r for r in rows if r["excluded_by"]]
    unknown = [r for r in rows if not r["excluded_by"] and r["unknown_on"]]
    bad_controls = [c for c in control_rows if not c.get("ok")]
    # AN AUTHORITY NOBODY COULD DETERMINE IS AN INSTRUMENT FAULT, counted
    # here rather than only in the cells. TASK-0190 §3: a rule depending on
    # it is UNKNOWN *and the run exits non-zero* - which it would not, from
    # the cells alone, for an authority no rule happens to read. That hole
    # is also closed by construction: every declared authority is read by at
    # least one rule, and a test asserts it.
    refusals = refused(state)

    # ORDER: a broken instrument outranks a finding, because a table whose
    # controls did not hold does not support either answer.
    if bad_controls or refusals:
        verdict, code = UNKNOWN, EXIT_UNKNOWN
    elif excluded:
        verdict, code = EXCLUDED, EXIT_EXCLUDED
    elif unknown:
        verdict, code = UNKNOWN, EXIT_UNKNOWN
    elif rows:
        verdict, code = PASS, EXIT_CLEARED
    else:
        # NO CONTACT IS NOT A CLEAN COHORT. An empty table is an instrument
        # that was handed nothing, and reporting it as cleared is the exact
        # shape of every defect this lane has been fixing.
        verdict, code = UNKNOWN, EXIT_UNKNOWN

    out = {
        # PRODUCED, not defaulted. `assessment["at"]` had exactly one
        # occurrence in this tree and it was the `.get` that READ it, so
        # every report said "Measured see the lane entry on SHA ..." - the
        # fallback string standing in for the run time, and the run time
        # silently lost. Same reader-with-no-producer shape as `delivered`.
        "at": _utc_now(),
        "rows": rows,
        "authorities": state,
        "controls": control_rows,
        "controls_ok": not bad_controls,
        "authority_refusals": refusals,
        "authorities_unanswerable": unanswerable(state),
        "channel": channel,
        "totals": {"contacts": len(rows), "cleared": len(cleared),
                   "excluded": len(excluded),
                   "not_cleared_because_unknown": len(unknown)},
        "verdict": verdict,
        "exit_code": code,
    }
    out["sentence"] = sentence(out)
    return out


def sentence(assessment):
    """The one line at the top of the report. Never a tick.

    It says cleared-or-not FIRST and why, because a reader who stops after
    one sentence must not stop on a number that looks like a pass.
    """
    totals = assessment["totals"]
    if assessment["verdict"] == PASS:
        return ("CANARY-01 IS CLEARED TO SEND on the %s path: all %d contact(s) "
                "passed every rule, every authority was readable and every "
                "control held."
                % (assessment["channel"], totals["cleared"]))
    parts = []
    if totals["excluded"]:
        parts.append("%d EXCLUDED by a rule that fired" % totals["excluded"])
    if totals["not_cleared_because_unknown"]:
        parts.append("%d NOT CLEARED because at least one rule could not be "
                     "asked at all" % totals["not_cleared_because_unknown"])
    if not assessment["controls_ok"]:
        parts.append("the controls did not hold, so this table proves nothing")
    if assessment.get("authority_refusals"):
        parts.append("the instrument could not determine the state of %s, so "
                     "it does not know what it did not read"
                     % ", ".join(assessment["authority_refusals"]))
    if not totals["contacts"]:
        parts.append("no contact was assessed, which is not a clean cohort")
    return ("CANARY-01 IS NOT CLEARED TO SEND on the %s path: %d cleared of "
            "%d; %s. UNKNOWN is not a pass."
            % (assessment["channel"], totals["cleared"], totals["contacts"],
               "; ".join(parts)))


# ------------------------------------------------------------- the controls
#
# Three, every run. Without the third the table could be all-EXCLUDED and
# still look rigorous; without the second it is the B7 instrument - clean
# because it never managed to ask anything.
#
# SYNTHETIC ADDRESSES ONLY. Reserved domains, planted into temporary
# authority files, so a control never touches a real roster and a real
# address never enters this module's own data.

_CONTROL_SUPPRESSED = "blocked-control@example.test"
_CONTROL_CLEAN = "clean-control@example.invalid"


#: The synthetic campaign ids a planted world uses. One DECLARED INTERNAL
#: and one bound by a planted ledger row, so a planted contact can be a
#: member of something that is not ours and a planted non-member can be
#: cleared against a world where ownership is actually known. Six digits, so
#: they cannot collide with a real provider id in this estate.
_CONTROL_INTERNAL_CAMPAIGN = 999001
_CONTROL_OUR_CAMPAIGN = 999002

#: The filler record a planted authority holds so that the planted world is
#: POPULATED while matching nobody. Reserved domains, and never one of the
#: control contacts' own - a filler that matched a control would make the
#: control a test of this constant.
_CONTROL_FILLER_DOMAIN = "filler-control.invalid"
_CONTROL_FILLER_ADDRESS = "filler-control@other.invalid"


def plant_authority_files(tmpdir, empty=()):
    """One file per authority in `tmpdir`, each holding ONE REAL RECORD.

    Returns {name: path}. An authority named in `empty` gets a file that
    exists, opens and parses and holds NOTHING - which is the world this
    module was revised for, and the world control 3 used to plant while
    asserting PASS.

    THE RECORDS GO IN THROUGH THE REAL WRITERS where one exists, so a
    planted file is in the format the real reader parses and the counter
    counts. A plant the owning module would reject would turn every control
    into a test of this function.
    """
    from . import agencydnc, operatorexclusion

    paths = {}
    for entry in AUTHORITIES:
        name = entry["name"]
        path = os.path.join(tmpdir, name + ".planted")
        paths[name] = path
        # TRUNCATE FIRST, ALWAYS. `agencydnc.add` and
        # `operatorexclusion.exclude` are append-only, so a second plant into
        # the same directory would otherwise silently double a record count
        # and control 5's "exactly one record" would stop being true.
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("")
        if name in empty:
            continue
        if name == "operator_exclusion_register":
            operatorexclusion.forget()
            operatorexclusion.exclude(
                _CONTROL_FILLER_DOMAIN,
                by="preflight.plant_authority_files",
                reason="synthetic filler, so this authority is POPULATED and "
                       "still matches nobody",
                authority="TASK-0190 control plant",
                file_path=path)
            operatorexclusion.forget()
        elif name == "agency_dnc":
            agencydnc.add("email", _CONTROL_FILLER_ADDRESS, file_path=path)
        elif name in ("suppression_template", "suppression_local_roster"):
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# planted by preflight.plant_authority_files\n"
                             "%s\n" % _CONTROL_FILLER_DOMAIN)
        elif name == "queue":
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write('{"id": "filler-control", "domain": "%s"}\n'
                             % _CONTROL_FILLER_DOMAIN)
        elif name == "internal_campaign_declaration":
            # The operator's own format: `<channel> <provider campaign id>`.
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# planted by preflight.plant_authority_files\n"
                             "bison %d\n" % _CONTROL_INTERNAL_CAMPAIGN)
        elif name == "campaign_ledger":
            # One canonical row binding the OTHER synthetic campaign, so the
            # planted world can tell ours from somebody else's at all.
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    '{"campaign_id": "filler-control-campaign", '
                    '"bison_campaign_id": %d}\n' % _CONTROL_OUR_CAMPAIGN)
        elif name == "campaign_lead_rows":
            _write_lead_rows(path)
        else:
            # A NEW AUTHORITY WITH NO PLANT IS A BROKEN CONTROL, not a
            # control that quietly stops covering it.
            raise AssertionError("no plant written for authority %r" % name)
    return paths


def _write_lead_rows(path, members=()):
    """A planted lead-row listing of the declared shape.

    PROVEN COMPLETE ON PURPOSE: both synthetic campaigns carry
    `leads_reported` equal to `leads_read`, which is the accounting the real
    producer does not write yet. A planted world that could not prove its own
    walk complete could never show a PASS, and then the control that proves a
    PASS is reachable would be impossible to build - which is exactly the
    hole control 5 exists to keep out of this module.

    `members` is a list of (address, campaign id) to plant as lead rows.
    """
    import json as _json

    rows = {}
    for address, campaign in members:
        rows.setdefault(address, {"domain": (address.split("@") + [""])[1],
                                  "touches": []})
        rows[address]["touches"].append({"campaign": campaign,
                                         "status": "in_sequence",
                                         "emails_sent": 1})
    index = {
        "generated_at": "2026-10-16T00:00:00+00:00",
        "source": "planted by preflight.plant_authority_files - no provider "
                  "was called",
        "campaigns": {
            str(_CONTROL_INTERNAL_CAMPAIGN): {
                "name": "planted internal", "status": "active",
                "leads_read": 1, "leads_reported": 1, "complete": True},
            str(_CONTROL_OUR_CAMPAIGN): {
                "name": "planted ours", "status": "active",
                "leads_read": 1, "leads_reported": 1, "complete": True}},
        "incomplete": [],
        "by_email": rows or {
            _CONTROL_FILLER_ADDRESS: {
                "domain": "other.invalid",
                "touches": [{"campaign": _CONTROL_OUR_CAMPAIGN,
                             "status": "finished", "emails_sent": 1}]}},
        "heyreach": {"read": False,
                     "why": "planted: EmailBison only, exactly as the real "
                            "listing records today"},
    }
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        _json.dump(index, handle, indent=1, sort_keys=True)
    return index


def _planted_state(tmpdir, raising=(), empty=(), paths=None):
    """(state, paths) for a planted tree. `tmpdir` IS the tree asked about.

    `root=tmpdir` is the point: the planted files are outside this checkout,
    and the OUTSIDE_TREE refusal would otherwise fire on every control.
    Passing the tree explicitly is also what makes that refusal testable.

    `raising` names authorities whose resolver raises instead, which is how
    control 2 plants a store read that cannot be done. `paths` re-reads an
    existing plant rather than writing it again - the record count has to be
    re-resolved after a control appends, and re-planting would wipe it.
    """
    paths = paths or plant_authority_files(tmpdir, empty=empty)
    resolvers = {}
    for entry in AUTHORITIES:
        name = entry["name"]
        if name in raising:
            def _boom(_name=name):
                raise OSError("planted control: %s cannot be read" % _name)
            resolvers[name] = _boom
            continue
        resolvers[name] = (lambda _p=paths[name]: _p)
    return authorities(resolvers=resolvers, root=tmpdir), paths


def _pointed(paths):
    """The real readers pointed at a planted authority set.

    One context manager rather than four at every call site, because a
    control that pointed three of the four readers would be measuring this
    repository's own files for the fourth without saying so.
    """
    import contextlib

    from . import (agencydnc, campaigns, campaignmembership, operatorexclusion,
                   providerwrites)

    stack = contextlib.ExitStack()
    stack.enter_context(_using(agencydnc, "path",
                               lambda: paths["agency_dnc"]))
    stack.enter_context(
        _using(operatorexclusion, "path",
               lambda: paths["operator_exclusion_register"]))
    stack.enter_context(_suppress_paths(paths["suppression_template"],
                                        paths["suppression_local_roster"]))
    # THE THREE THE OWNERSHIP RULE READS. Without these the rule would read
    # THIS CHECKOUT's declaration, ledger and listing while the state table
    # described the plant - a control measuring one world and reporting
    # another.
    stack.enter_context(
        _using(providerwrites, "internal_campaigns_path",
               lambda: paths["internal_campaign_declaration"]))
    stack.enter_context(_using(campaigns, "path",
                               lambda: paths["campaign_ledger"]))
    stack.enter_context(_using(campaignmembership, "path",
                               lambda: paths["campaign_lead_rows"]))
    operatorexclusion.forget()
    stack.callback(operatorexclusion.forget)
    return stack


def _row(control, planted, expected, observed, note=None):
    out = {"control": control, "planted": planted, "expected": expected,
           "observed": observed, "ok": observed == expected}
    if note:
        out["note"] = note
    return out


def _control_one(where):
    """A planted suppressed address shows EXCLUDED with its reason."""
    from . import agencydnc

    try:
        _, paths = _planted_state(where)
        # Through `agencydnc.add`, so the control exercises the real
        # fingerprinting and the real lookup rather than a stub that would
        # agree with anything.
        agencydnc.add("email", _CONTROL_SUPPRESSED,
                      file_path=paths["agency_dnc"])
        state = _planted_state(where, paths=paths)[0]
        with _pointed(paths):
            row = evaluate({"key": "control-1", "email": _CONTROL_SUPPRESSED,
                            "domain": "example.test"}, state=state)
        cell = row["cells"]["agency_dnc"]
        observed = [state["agency_dnc"]["state"], cell["cell"],
                    bool(cell["why"])]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None]
    return _row(
        "a planted suppressed address shows EXCLUDED with its reason",
        "%s added to a populated temporary agency-DNC file through "
        "agencydnc.add" % _CONTROL_SUPPRESSED,
        [PRESENT_POPULATED, EXCLUDED, True], observed)


def _control_two(where):
    """A read that RAISES is UNKNOWN, and the run exits non-zero."""
    contact = {"key": "control-2", "email": _CONTROL_CLEAN,
               "domain": "example.invalid", "record": {"id": "r"}}
    try:
        state, _ = _planted_state(where, raising=("queue",))
        row = evaluate(contact, state=state)
        whole = assess([contact], state=state)
        # THE AUTHORITY'S OWN STATE IS IN THE OBSERVATION, not only the
        # cell. Without it this control passed with the gate deliberately
        # blinded to PRESENT, because `record_state` has no address-only
        # form and came out UNKNOWN for a different reason - a different
        # guard firing first, which is the trap CLAUDE.md names. Measured
        # while writing TASK-0170's test file.
        observed = [state["queue"]["state"],
                    row["cells"]["record_state"]["cell"],
                    whole["exit_code"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None]
    return _row(
        "a planted contact whose store read raises shows UNKNOWN and the run "
        "exits non-zero",
        "the queue authority's resolver raising OSError",
        [PRESENT_UNREADABLE, UNKNOWN, EXIT_UNKNOWN], observed)


def _control_three(where):
    """A planted clean contact shows PASS - against POPULATED authorities.

    THIS CONTROL WAS ITSELF THE DEFECT. It planted "present, empty, readable
    authority files" and asserted PASS on four rules, which is exactly the
    world TASK-0190 says is UNKNOWN: the instrument's own proof that a PASS
    was reachable was a demonstration of the hazard. The plant is now
    populated, which is what "readable and answered" has to mean.
    """
    try:
        state, paths = _planted_state(where)
        with _pointed(paths):
            row = evaluate({"key": "control-3", "email": _CONTROL_CLEAN,
                            "domain": "example.invalid"}, state=state)
        observed = [row["cells"][n]["cell"]
                    for n in ("operator_exclusion_address",
                              "operator_exclusion_company",
                              "suppression_domain_list", "agency_dnc")]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc)]
    return _row(
        "a planted clean contact shows PASS on every rule that can be asked",
        "%s against present, POPULATED, readable authority files, each "
        "holding a filler record that matches nobody" % _CONTROL_CLEAN,
        [PASS] * 4, observed)


def _control_four(where):
    """PRESENT AND EMPTY YIELDS UNKNOWN. The control this module lacked."""
    contact = {"key": "control-4", "email": _CONTROL_CLEAN,
               "domain": "example.invalid", "record": {"id": "r"}}
    try:
        state, paths = _planted_state(where, empty=("agency_dnc",))
        with _pointed(paths):
            row = evaluate(contact, state=state)
            whole = assess([contact], state=state)
        observed = [state["agency_dnc"]["state"],
                    state["agency_dnc"]["records"],
                    row["cells"]["agency_dnc"]["cell"],
                    whole["exit_code"] != 0]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None, None]
    return _row(
        "a present-and-EMPTY authority yields UNKNOWN, not PASS, and the run "
        "exits non-zero",
        "an agency-DNC file that exists, opens and parses to zero records, "
        "with every other authority populated and the contact's record "
        "supplied",
        [PRESENT_EMPTY, 0, UNKNOWN, True], observed,
        note="THE CELL IS THE DISCRIMINATOR HERE, NOT THE EXIT CODE: other "
             "rules are UNKNOWN for their own reasons, so this run exits 2 "
             "either way. Weaken the state check so PRESENT_EMPTY maps to "
             "PRESENT_POPULATED and the agency_dnc cell becomes PASS, which "
             "is what this row catches.")


def _control_five(where):
    """A POPULATED authority really fires. The twin of control 4.

    WHY IT EXISTS: control 4 and the non-zero exit are both passed by an
    instrument that answers UNKNOWN to everything. This row differs from
    control 4 in exactly one fact - the same authority holds ONE record
    instead of none - and demands a real verdict out of it.
    """
    from . import agencydnc

    try:
        state, paths = _planted_state(where, empty=("agency_dnc",))
        agencydnc.add("email", _CONTROL_SUPPRESSED,
                      file_path=paths["agency_dnc"])
        state = _planted_state(where, paths=paths)[0]
        with _pointed(paths):
            row = evaluate({"key": "control-5", "email": _CONTROL_SUPPRESSED,
                            "domain": "example.test"}, state=state)
        observed = [state["agency_dnc"]["state"],
                    state["agency_dnc"]["records"],
                    row["cells"]["agency_dnc"]["cell"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None]
    return _row(
        "a POPULATED authority returns a real verdict rather than UNKNOWN",
        "the same agency-DNC authority as control 4, holding exactly ONE "
        "record: the synthetic %s" % _CONTROL_SUPPRESSED,
        [PRESENT_POPULATED, 1, EXCLUDED], observed,
        note="EXISTS BECAUSE CONTROL 4 AND THE EXIT CODE ARE BOTH PASSED BY "
             "AN INSTRUMENT THAT ANSWERS UNKNOWN TO EVERYTHING. One record "
             "versus none is the only difference between this row and that "
             "one.")


#: A member of the planted internal campaign. Reserved domain, and planted
#: only into a temporary listing - no real cohort address goes into any
#: fixture, committed file or authority this module writes.
_CONTROL_MEMBER = "member-control@example.test"


def _control_six(where):
    """A PLANTED MEMBER OF AN INTERNAL CAMPAIGN IS EXCLUDED, by number.

    The control the rule could not have before TASK-0200, because there was
    no rule. A membership check with no member planted is an instrument that
    sees nothing, and this estate has shipped one of those already.
    """
    contact = {"key": "control-6", "email": _CONTROL_MEMBER,
               "domain": "example.test"}
    try:
        state, paths = _planted_state(where)
        _write_lead_rows(paths["campaign_lead_rows"],
                         members=[(_CONTROL_MEMBER,
                                   _CONTROL_INTERNAL_CAMPAIGN)])
        state = _planted_state(where, paths=paths)[0]
        with _pointed(paths):
            row = evaluate(contact, state=state)
            whole = assess([contact], state=state)
        cell = row["cells"]["internal_campaign_membership"]
        observed = [state["campaign_lead_rows"]["state"], cell["cell"],
                    str(_CONTROL_INTERNAL_CAMPAIGN) in cell["why"],
                    whole["totals"]["excluded"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None, None]
    return _row(
        "a planted member of a DECLARED INTERNAL campaign is EXCLUDED, with "
        "the campaign named",
        "%s given a lead row in campaign %d, which a planted declaration "
        "names internal" % (_CONTROL_MEMBER, _CONTROL_INTERNAL_CAMPAIGN),
        [PRESENT_POPULATED, EXCLUDED, True, 1], observed,
        note="THE CAMPAIGN NUMBER IS PART OF THE OBSERVATION. An exclusion "
             "that cannot say which campaign is an exclusion nobody can "
             "check, and the headline moving to `1 EXCLUDED` is the fourth "
             "cell because that is the sentence a reader acts on.")


def _control_seven(where):
    """A PLANTED NON-MEMBER IS PASS, against a listing that proves its walk.

    The opposite control, and without it a rule answering UNKNOWN to
    everybody passes control 6 and the exit code both. It is also the only
    row that exercises PROVEN COMPLETE positively: the planted listing
    carries the `leads_reported` accounting the real producer does not write
    yet, which is why the real cohort cannot reach PASS here today.
    """
    contact = {"key": "control-7", "email": _CONTROL_CLEAN,
               "domain": "example.invalid"}
    try:
        state, paths = _planted_state(where)
        with _pointed(paths):
            row = evaluate(contact, state=state)
        cell = row["cells"]["internal_campaign_membership"]
        observed = [state["campaign_lead_rows"]["state"], cell["cell"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc)]
    return _row(
        "a planted NON-member is PASS against a listing that proves its walk "
        "complete",
        "%s absent from a populated listing whose every internal campaign "
        "records leads_reported == leads_read" % _CONTROL_CLEAN,
        [PRESENT_POPULATED, PASS], observed,
        note="EXISTS BECAUSE CONTROL 6 IS PASSED BY A RULE THAT ANSWERS "
             "UNKNOWN TO EVERYBODY. It is also the proof that PASS is "
             "reachable at all for this rule - today it is reachable only "
             "against a planted listing, because the real producer discards "
             "the provider's own total and so cannot prove a walk complete.")


#: THE PLANTED BOUNCE. A reserved domain, written only into a temporary
#: queue file - no real address enters any authority this module writes.
_CONTROL_BOUNCED = "already-bounced-control@example.test"


def _bounce_queue_row(path, bounced=True):
    """Write ONE real queue record into the planted queue authority.

    Handed back THROUGH `store.read_jsonl` - the same reader
    `_count_queue_records` counts the authority with - so the record
    `evaluate` is given is the row that reader returns rather than a dict
    built beside the file. A control that built its own record would prove
    the rule can read a dict, which nobody doubted, and would prove nothing
    about the authority.
    """
    import json as _json

    from . import events as _events

    row = {"id": "bounce-control", "domain": "example.test",
           "contacts": [{"key": "control-8", "email": _CONTROL_BOUNCED}],
           "events": ([{"type": _events.EMAIL_BOUNCED,
                        "contact": "control-8",
                        "at": "2026-10-16T00:00:00+00:00"}]
                      if bounced else [])}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_json.dumps(row, sort_keys=True) + "\n")
    return store.read_jsonl(path)[0]


def _control_eight(where):
    """A RECORDED BOUNCE IS EXCLUDED, NOT UNKNOWN. TASK-0250's C2.

    The control that could not have existed before TASK-0250, because
    `bounce_history` carried `ask: None` and answered UNKNOWN in every world
    including this one. Controls 4 and 9 and the non-zero exit are all passed
    by a rule that refuses everybody; this row is the only thing that proves
    the one rule whose job is to see a bounce can report one it is holding.
    """
    try:
        state, paths = _planted_state(where)
        rec = _bounce_queue_row(paths["queue"], bounced=True)
        state = _planted_state(where, paths=paths)[0]
        contact = {"key": "control-8", "email": _CONTROL_BOUNCED,
                   "domain": "example.test", "record": rec}
        with _pointed(paths):
            row = evaluate(contact, state=state)
            whole = assess([contact], state=state)
        cell = row["cells"]["bounce_history"]
        observed = [state["queue"]["state"], state["queue"]["records"],
                    cell["cell"], "EMAIL_BOUNCED" in cell["why"],
                    whole["totals"]["excluded"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc),
                    None, None, None]
    return _row(
        "a RECORDED bounce in the queue authority is EXCLUDED with the event "
        "named, not UNKNOWN",
        "%s given ONE queue record carrying an EMAIL_BOUNCED event, read "
        "back through store.read_jsonl" % _CONTROL_BOUNCED,
        [PRESENT_POPULATED, 1, EXCLUDED, True, 1], observed,
        note="THE EVENT NAME IS PART OF THE OBSERVATION, and so is the "
             "headline moving to `1 EXCLUDED`. Before TASK-0250 this row "
             "observed UNKNOWN: the authority was populated, the record was "
             "supplied, the bounce was in it, and the cell said the rule had "
             "no form that could be evaluated.")


def _control_nine(where):
    """THE SAME PLANT WITH NO BOUNCE EVENT IS UNKNOWN, NOT PASS.

    The twin, and the one that keeps TASK-0250 from being a rule that fires
    on everybody. It differs from control 8 in exactly one fact - the
    record's `events` list is empty - and demands UNKNOWN rather than the
    PASS `channels._bounced` would license, naming the unbounded recorder
    window that is the reason.
    """
    try:
        state, paths = _planted_state(where)
        rec = _bounce_queue_row(paths["queue"], bounced=False)
        state = _planted_state(where, paths=paths)[0]
        contact = {"key": "control-8", "email": _CONTROL_BOUNCED,
                   "domain": "example.test", "record": rec}
        with _pointed(paths):
            row = evaluate(contact, state=state)
        cell = row["cells"]["bounce_history"]
        observed = [state["queue"]["state"], state["queue"]["records"],
                    cell["cell"], "ZERO readers" in cell["why"]]
    except Exception as exc:                                    # noqa: BLE001
        observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc),
                    None, None]
    return _row(
        "the same record with NO bounce event is UNKNOWN naming the "
        "recorder, not PASS",
        "the control-8 plant with an EMPTY events list - exactly what an "
        "unrecorded bounce looks like",
        [PRESENT_POPULATED, 1, UNKNOWN, True], observed,
        note="EXISTS BECAUSE CONTROL 8 IS PASSED BY A RULE THAT EXCLUDES "
             "EVERYBODY. One event versus none is the only difference "
             "between this row and that one, and `channels._bounced` "
             "answers False here - so a cell reading PASS would be reporting "
             "that `False` as a fact about the address.")


def controls():
    """The nine, as rows. `ok` is False the moment one disagrees.

    THREE OF THESE EXISTED AND WERE NOT ENOUGH. 1 proves an exclusion is
    seen, 2 proves a read that raises is UNKNOWN, 3 proves a PASS is
    reachable at all - and none of the three could tell a present-and-empty
    authority from one that was read and holds nobody, because 2 plants the
    one failure mode an empty file does not have. 4 and 5 are that pair, and
    they share a plant so the only difference between them is one record.

    6 and 7 are the same shape again, for the rule TASK-0200 added: 6 plants
    a member of a declared internal campaign and demands an EXCLUDED naming
    the number, 7 plants a non-member against a listing that can prove its
    own walk and demands a PASS. Neither could exist before the rule did,
    and 6 alone would be satisfied by a rule that refused everybody.

    8 and 9 are that pair a third time, for `bounce_history`, and TASK-0250
    added them because the rule had NO control of its own and answered
    UNKNOWN in every world the other seven build - a populated queue and a
    record holding a hard bounce included. 8 plants the bounce and demands
    EXCLUDED; 9 plants the same record with an empty `events` list and
    demands UNKNOWN, because `channels._bounced` answers `False` there and
    that `False` is indistinguishable from a recorder that stopped working
    on a date nobody can name. Their only difference is one event.

    Each control gets its OWN directory. The writers are append-only and
    `operatorexclusion` caches, so a shared directory let one control's
    plant change another's record count.

    SYNTHETIC ADDRESSES ONLY. Reserved domains, planted into temporary
    authority files, so a control never touches a real roster and a real
    address never enters this module's own data.
    """
    import shutil
    import tempfile

    from . import operatorexclusion

    tmp = tempfile.mkdtemp(prefix="rga-preflight-control-")
    out = []
    try:
        for number, run in ((1, _control_one), (2, _control_two),
                            (3, _control_three), (4, _control_four),
                            (5, _control_five), (6, _control_six),
                            (7, _control_seven), (8, _control_eight),
                            (9, _control_nine)):
            where = os.path.join(tmp, "c%d" % number)
            os.makedirs(where, exist_ok=True)
            out.append(run(where))
    finally:
        operatorexclusion.forget()
        shutil.rmtree(tmp, ignore_errors=True)

    for row in out:
        row["ok"] = bool(row["ok"])
    return out


class _using:
    """Swap one module attribute for the duration of a block.

    Local rather than `unittest.mock`, because this runs in production code
    and `mock` is a test dependency. Restores the original even on a raise.
    """

    def __init__(self, module, name, value):
        self.module, self.name, self.value = module, name, value

    def __enter__(self):
        self.previous = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)
        return self

    def __exit__(self, *exc):
        setattr(self.module, self.name, self.previous)
        return False


class _suppress_paths:
    """`ingest.SUPPRESS` and `SUPPRESS_LOCAL` pointed at planted files."""

    def __init__(self, template, local):
        self.template, self.local = template, local

    def __enter__(self):
        from . import ingest
        self.ingest = ingest
        self.previous = (ingest.SUPPRESS, ingest.SUPPRESS_LOCAL)
        ingest.SUPPRESS, ingest.SUPPRESS_LOCAL = self.template, self.local
        return self

    def __exit__(self, *exc):
        self.ingest.SUPPRESS, self.ingest.SUPPRESS_LOCAL = self.previous
        return False
