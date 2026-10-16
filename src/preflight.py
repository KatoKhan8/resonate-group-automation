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
        return Undecided("the lead-row listing could not be read: %s"
                         % (str(exc)[:400],))

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
     "ask": None,
     "about": "the client suppressed this record"},
    {"name": "client_own_domain",
     "decides": "eligibility._client_own_domain",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the address is at the client's own domain - their staff, "
              "never a prospect"},
    {"name": "record_state",
     "decides": "eligibility._record_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "dropped, or in an unshippable state. Whether `held` and "
              "`drafted` block a send is recorded as UNSETTLED in the "
              "approval sheet's own note, and enforced in code regardless"},
    {"name": "contact_flags",
     "decides": "eligibility._replied, the flag branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "unsubscribed, suppressed, stopped or paused on the contact"},
    {"name": "contact_reply_event",
     "decides": "eligibility._replied, the event branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "this person replied; their sequence is answered"},
    {"name": "account_suppressed",
     "decides": "eligibility._paused, the account suppression branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the company asked not to be contacted"},
    {"name": "account_review_open",
     "decides": "eligibility._paused, the open-review branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "a human review is open on this account"},
    {"name": "account_paused",
     "decides": "eligibility._paused via cadence.pause_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the account is paused by reply policy"},
    {"name": "account_reply_log",
     "decides": "suppression.decide step 2 via account.replies",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "a reply recorded against the contact but not flagged on it is "
              "still a reply"},
    {"name": "bounce_history",
     "decides": "channels._bounced, and bouncepolicy.decide for the "
                "hard/soft split",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "this address has already bounced. Keyed to the CONTACT, not "
              "the account"},
    {"name": "mx_and_verification",
     "decides": "channels.email_verdict via mx.allows_email and the client's "
                "verification policy",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the address cannot receive mail, or is not verified to this "
              "client's policy. No email is generated for an unverified "
              "address"},
    {"name": "hygiene_workspace_history",
     "decides": "hygiene.check step 2 via hygiene.index",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "we have worked this person before, by strong identity"},
    {"name": "hygiene_account_history",
     "decides": "hygiene.check step 3",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "we have worked this company before"},
    {"name": "client_approval_register",
     "decides": "hygiene.check step 0 via clientapproval.is_suppressed",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
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


def controls():
    """The seven, as rows. `ok` is False the moment one disagrees.

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
                            (7, _control_seven)):
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
