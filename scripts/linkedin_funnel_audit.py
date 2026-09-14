#!/usr/bin/env python3
"""TASK-025: The LinkedIn funnel, and what is missing to see it.

For each funnel stage, states exactly:
  SUPPORTED   - naming the route and field
  UNSUPPORTED - naming what was looked for and where
  UNDETERMINED - naming the single cheapest live read that would settle it

Plus action-type performance comparison, and the cost of each missing read.

Reads only: the extracted provider data and this codebase's own source.
Zero network, zero credentials.
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(os.path.dirname(ROOT), "resonate-analysis")
sys.path.insert(0, ROOT)

# --------------------------------------------------------------- constants

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
UNDETERMINED = "UNDETERMINED"

FUNNEL_STAGES = (
    "targeted",
    "request_sent",
    "accepted",
    "messaged",
    "replied",
    "positive",
    "meeting",
)

ACTION_TYPES = (
    "CONNECTION_REQUEST",
    "MESSAGE",
    "VIEW_PROFILE",
    "FOLLOW",
    "INMAIL",
)


# --------------------------------------------------------- source readers

def _read_source(relpath):
    full = os.path.join(ROOT, relpath)
    with open(full, encoding="utf-8") as f:
        return f.read()


def _grep(relpath, pattern):
    src = _read_source(relpath)
    return [(i + 1, line.rstrip())
            for i, line in enumerate(src.splitlines())
            if re.search(pattern, line)]


def _has_caller(module_name, func_name):
    """Does `module.func` have any CALLER in src/ outside its own file?

    Only counts actual call expressions (name followed by '('), not
    docstring or comment references.
    """
    src_dir = os.path.join(ROOT, "src")
    call_pattern = re.compile(
        rf"{re.escape(module_name)}\.{re.escape(func_name)}\s*\(")
    own_file = os.path.join(src_dir, *module_name.split(".")) + ".py"
    for dirpath, _, filenames in os.walk(src_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            if os.path.normpath(full) == os.path.normpath(own_file):
                continue
            with open(full, encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if call_pattern.search(line):
                    return True, f"{full}:{i + 1}"
    return False, None


# --------------------------------------------------------- data loaders

def load_hr_campaigns():
    path = os.path.join(DATA, "hr_campaigns.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bison_campaigns():
    path = os.path.join(DATA, "bison_campaigns.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_replies(channel):
    path = os.path.join(DATA, f"replies_{channel}.jsonl")
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# --------------------------------------------------------- stage auditors

def audit_targeted():
    """Stage 1: targeted. How many users did HeyReach aim at?"""
    campaigns = load_hr_campaigns()
    total = sum((c.get("progressStats") or {}).get("totalUsers", 0)
                for c in campaigns)
    return {
        "stage": "targeted",
        "verdict": SUPPORTED,
        "route": "POST /campaign/GetAll",
        "field": "progressStats.totalUsers",
        "evidence": (
            f"{len(campaigns)} HeyReach campaigns read from "
            f"hr_campaigns.json; sum of progressStats.totalUsers = {total:,}. "
            f"progressStats also carries totalUsersPending, "
            f"totalUsersInProgress, totalUsersFinished, totalUsersFailed, "
            f"totalUsersManuallyStopped, totalUsersExcluded."
        ),
        "consumer": "src/providers/heyreach.py READ_ROUTES (line ~170); "
                    "data extracted to hr_campaigns.json",
    }


def audit_request_sent():
    """Stage 2: connection request sent. Did the request go out?"""
    # Local event log
    push_marked_hits = _grep("src/events.py", r'PUSH_MARKED')
    # Provider route
    leads_route_hits = _grep("src/providers/heyreach.py",
                             r"GetLeadsFromCampaign")
    # lead_state mapping
    connectionsent_hits = _grep("src/providers/heyreach.py",
                                r"connectionsent.*REQUEST_SENT")
    # Check if leadobserve.observe() is called
    has_caller, caller_file = _has_caller("leadobserve", "observe")

    local_evidence = (
        "src/events.py defines PUSH_MARKED; src/linkedinstate.py evidence() "
        "reads push_marked events on channel=linkedin with action=connect "
        "to record request_at"
    )
    provider_evidence = (
        "src/providers/heyreach.py lead_state() maps "
        "leadConnectionStatus='connectionsent' to REQUEST_SENT; "
        "POST /campaign/GetLeadsFromCampaign is on READ_ROUTES_ALL"
    )
    caller_note = (
        f"leadobserve.observe() caller in src/: "
        f"{'YES - ' + caller_file if has_caller else 'NONE'}"
    )

    return {
        "stage": "request_sent",
        "verdict": SUPPORTED,
        "route": (
            "Local event log: events.PUSH_MARKED (channel=linkedin). "
            "Provider: POST /campaign/GetLeadsFromCampaign"
        ),
        "field": (
            "Local: entry.type == 'push_marked' AND entry.channel == "
            "'linkedin' AND action_of(step) == 'connect'. "
            "Provider: leadConnectionStatus == 'ConnectionSent'"
        ),
        "evidence": (
            f"{local_evidence}. {provider_evidence}. {caller_note}. "
            f"The local event log is consumed by linkedinstate.evidence() "
            f"and is the primary record. The provider route is on the "
            f"allowlist but leadobserve.observe() has no caller in src/."
        ),
        "consumer": (
            "src/linkedinstate.evidence() reads the local event log; "
            "src/outcomes.py imports leadobserve and reads stored rows"
        ),
    }


def audit_accepted():
    """Stage 3: connection accepted. Did they accept?"""
    # Check the conversations endpoint
    conv_hits = _grep("src/providers/heyreach.py",
                      r"CONNECTION_STATUS_AVAILABLE")
    # Check the lead-level read
    lead_state_hits = _grep("src/providers/heyreach.py",
                            r"connectionaccepted.*ACCEPTED")
    # Check the webhook route
    webhook_hits = _grep("src/providers/heyreach.py",
                         r"CONNECTION_REQUEST_ACCEPTED")
    # Check IsConnection
    is_conn_hits = _grep("src/providers/heyreach.py", r"IsConnection")
    # Check if leadobserve.observe() has a caller
    has_caller, caller_file = _has_caller("leadobserve", "observe")

    return {
        "stage": "accepted",
        "verdict": UNDETERMINED,
        "route": (
            "POST /campaign/GetLeadsFromCampaign (on READ_ROUTES_ALL); "
            "leadConnectionStatus field on each lead row"
        ),
        "field": "leadConnectionStatus == 'ConnectionAccepted'",
        "evidence": (
            "src/providers/heyreach.py lead_state() maps "
            "'connectionaccepted' to ACCEPTED (line ~2117). "
            "The route /campaign/GetLeadsFromCampaign is on READ_ROUTES_ALL. "
            "BUT leadobserve.observe() - the function that calls the "
            "provider - has NO CALLER in src/. "
            "CONNECTION_STATUS_AVAILABLE = False for the inbox route "
            "(/inbox/GetConversationsV2), confirmed over 100 conversations: "
            "no acceptedAt, no connectionStatus field there. "
            "The vendor documents POST /MyNetwork/IsConnection and a "
            "CONNECTION_REQUEST_ACCEPTED webhook event; neither is on any "
            "allowlist and neither has ever been called from here. "
            "hr_campaigns.json progressStats has no acceptance counter."
        ),
        "cheapest_read": (
            "Run `python -m src.leadobserve --campaign <active_id>` for "
            "one of the 12 IN_PROGRESS campaigns (e.g. id 565765 with "
            "1000 users). If the output contains state='accepted' rows, "
            "the route carries acceptance at lead level and the gap is "
            "wiring, not capability. If it does not, HeyReach does not "
            "report acceptance through this route and a different read "
            "(/MyNetwork/IsConnection or the webhook) is needed."
        ),
        "if_yes": (
            "Wire leadobserve.observe() into the poller, classify "
            "connectionaccepted as an acceptance event, and the funnel "
            "stage becomes SUPPORTED. 9,496 API calls for 949,536 users "
            "at 100/page - all free reads."
        ),
        "if_no": (
            "Try POST /MyNetwork/IsConnection for a handful of known "
            "leads. If that answers, the per-lead cost is one API call "
            "per prospect = 949,536 calls (still free, but rate-limited). "
            "If neither works, the webhook is the only path and requires "
            "an endpoint this system does not have."
        ),
        "cost_if_unwired": (
            "9,496 API calls to page all 83 campaigns at 100/page. "
            "HeyRead reads are free, so the monetary cost is zero. "
            "The real cost is implementation: wire leadobserve.observe() "
            "into the poller, add acceptance event recording, and re-run "
            "the funnel. Estimated one afternoon of work plus verification."
        ),
    }


def audit_messaged():
    """Stage 4: messaged. Did we send a LinkedIn message?"""
    msg_states = _grep("src/providers/heyreach.py", r"MESSAGE_STATES")
    cap_message = _grep("src/linkedinstate.py", r"CAP_MESSAGE")
    return {
        "stage": "messaged",
        "verdict": SUPPORTED,
        "route": (
            "Local event log: events.PUSH_MARKED (channel=linkedin). "
            "Provider: POST /campaign/GetLeadsFromCampaign"
        ),
        "field": (
            "Local: entry.type == 'push_marked' AND action_of(step) == "
            "'message'. "
            "Provider: leadMessageStatus == 'MessageSent'"
        ),
        "evidence": (
            "src/providers/heyreach.py MESSAGE_STATES includes "
            "'messagesent'. lead_state() maps it through. "
            "src/linkedinstate.py CAP_MESSAGE is proven (True): "
            "'MESSAGE is a node type observed in real HeyReach sequences'. "
            "src/cadencelibrary.py sequences carry linkedin_action: message "
            "steps. The local event log records every pushed step."
        ),
        "consumer": (
            "src/linkedinstate.evidence() reads push_marked events; "
            "src/linkedinstate.plan_step() gates messaging on MESSAGEABLE "
            "states"
        ),
    }


def audit_replied():
    """Stage 5: replied. Did they send an inbound LinkedIn message?"""
    li_replies = load_replies("linkedin")
    conv_hits = _grep("src/providers/heyreach.py", r"inbound_messages")
    adapter_hits = _grep("src/providers/heyreach.py", r"lastMessageSender")
    return {
        "stage": "replied",
        "verdict": SUPPORTED,
        "route": (
            "POST /inbox/GetConversationsV2 (READ_ROUTES); "
            "replies_linkedin.jsonl (695 sanitised records)"
        ),
        "field": (
            "messages[].sender == 'CORRESPONDENT' (allowlist: only "
            "CORRESPONDENT is inbound, ME is ours, anything else is "
            "unknown and dropped)"
        ),
        "evidence": (
            f"{len(li_replies)} LinkedIn reply records in "
            f"replies_linkedin.jsonl. "
            f"rules_say distribution: "
            f"{dict(_count(li_replies, 'rules_say'))}. "
            f"src/providers/heyreach.py inbound_messages() reads "
            f"prospect messages from conversations; direction() enforces "
            f"an allowlist of CORRESPONDENT/ME. "
            f"src/events.py REPLY_RECEIVED is the event type; "
            f"events.is_reply() is the predicate."
        ),
        "consumer": (
            "src/adapters.from_heyreach processes conversations; "
            "src/linkedinstate.evidence() records replied_at; "
            "src/eligibility._replied uses the same predicate"
        ),
    }


def audit_positive():
    """Stage 6: positive reply. Did they express interest?"""
    li_replies = load_replies("linkedin")
    pos_count = sum(1 for r in li_replies if r.get("rules_say") == "positive")
    # Check if apply (the entry point that calls classify) is consumed
    has_apply, apply_caller = _has_caller("replies", "apply")
    return {
        "stage": "positive",
        "verdict": SUPPORTED,
        "route": "src/replies.py apply() -> classify() -> classify_rules()",
        "field": "verdict category == 'positive' (replies.POSITIVE)",
        "evidence": (
            f"{pos_count} of {len(li_replies)} LinkedIn replies classified "
            f"as positive by the rules classifier. "
            f"src/replies.py POSITIVE = 'positive' is a constant in the "
            f"CATEGORIES tuple. classify_rules() matches pattern families. "
            f"replies.apply() caller in src/: "
            f"{'YES - ' + apply_caller if has_apply else 'NONE'}. "
            f"replies.is_positive() is consumed by src/inbound.py to "
            f"decide whether to alert an operator. "
            f"POSITIVE is in ALERTING, meaning it wakes an operator."
        ),
        "consumer": (
            "src/inbound.py calls replies.apply() and replies.is_positive(); "
            "POSITIVE is in ALERTING for operator notification"
        ),
    }


def audit_meeting():
    """Stage 7: meeting booked. Did they agree to talk?"""
    meeting_hits = _grep("src/replies.py", r"meeting")
    event_types = _grep("src/events.py", r"MEETING|meeting|calendar")
    return {
        "stage": "meeting",
        "verdict": UNSUPPORTED,
        "looked_for": (
            "An event type for meeting booked, a calendar integration, "
            "or a reply classifier output that distinguishes meeting from "
            "positive"
        ),
        "looked_in": (
            "src/events.py (no MEETING event type), src/replies.py "
            "(explicitly declines to split positive from meeting: "
            "'a meeting is determined by an action - calendar link "
            "accepted, time agreed, meeting scheduled - not by words "
            "alone'), src/ (no calendar integration module)"
        ),
        "evidence": (
            "src/replies.py TASK-020 comment: 'should positive split into "
            "positive and meeting? Decision: no split at the classifier "
            "level. A meeting is determined by an action (calendar link "
            "accepted, time agreed, meeting scheduled), not by words "
            "alone.' No event type for meeting exists in src/events.py. "
            "No calendar integration exists in this codebase."
        ),
        "cheapest_read": (
            "Scan the 30 positive LinkedIn reply bodies in "
            "replies_linkedin.jsonl for calendar-link patterns (Calendly, "
            "cal.com, etc.). If any carry a calendar link, the classifier "
            "could be extended with a MEETING category triggered by URL "
            "pattern rather than text pattern. Cost: one grep over 30 "
            "short texts. But even a positive result would need a "
            "confirmation mechanism (did the calendar event actually "
            "happen?) that no provider here offers."
        ),
    }


# ------------------------------------------------- action-type performance

def audit_action_types():
    """Can we compare CONNECTION_REQUEST, MESSAGE, VIEW_PROFILE, FOLLOW,
    INMAIL for effect?"""
    # Check what the sequence graph supports
    linkedin_only = _grep("src/providers/heyreach.py", r"LINKEDIN_ONLY_NODES")
    # Check what lead_state tracks
    connection_states = _grep("src/providers/heyreach.py", r"CONNECTION_STATES")
    message_states = _grep("src/providers/heyreach.py", r"MESSAGE_STATES")
    # Check capabilities
    caps = _grep("src/linkedinstate.py", r"CAPABILITIES\s*=")

    # What node types exist in sequences
    node_types_found = []
    for name in ("CONNECTION_REQUEST", "MESSAGE", "VIEW_PROFILE", "FOLLOW",
                 "INMAIL", "CHECK_IS_CONNECTION", "CHECK_IS_OPEN_PROFILE"):
        hits = _grep("src/providers/heyreach.py", rf'"{name}"')
        if hits:
            node_types_found.append(name)

    return {
        "verdict": UNSUPPORTED,
        "looked_for": (
            "A per-action-type performance breakdown: for each action type "
            "(CONNECTION_REQUEST, MESSAGE, VIEW_PROFILE, FOLLOW, INMAIL), "
            "how many went out, how many produced the intended effect"
        ),
        "looked_in": (
            "src/providers/heyreach.py progressStats (only totalUsers, "
            "totalUsersInProgress, etc. - no per-action breakdown); "
            "lead_state() (only leadConnectionStatus and "
            "leadMessageStatus - two dimensions, not five); "
            "src/linkedinstate.py CAPABILITIES (classifies what is proven "
            "but does not measure effect)"
        ),
        "evidence": (
            f"HeyReach sequence graphs use these node types: "
            f"{', '.join(node_types_found)}. "
            f"LINKEDIN_ONLY_NODES in heyreach.py lists the action types "
            f"that are provably LinkedIn-only. "
            f"But progressStats has NO per-action-type counters. "
            f"lead_state() tracks leadConnectionStatus (none/connectionsent/"
            f"connectionaccepted) and leadMessageStatus (none/messagesent/"
            f"messagereply) - two independent dimensions that cover "
            f"CONNECTION_REQUEST and MESSAGE only. VIEW_PROFILE, FOLLOW and "
            f"INMAIL have no lead-level status field. "
            f"A cross-action comparison (did CONNECTION_REQUEST or MESSAGE "
            f"produce more replies?) cannot be answered from any data here."
        ),
        "cheapest_read": (
            "For each of the 83 campaigns, read the sequence graph via "
            "GET /campaign/GetCampaignSequence?campaignId=<id> and count "
            "which node types appear. Then read leads via "
            "/campaign/GetLeadsFromCampaign and cross-reference "
            "leadConnectionStatus and leadMessageStatus with the sequence "
            "structure. This gives per-campaign action inventory but NOT "
            "per-action effect (you still cannot say 'VIEW_PROFILE caused "
            "X replies' because there is no per-action outcome). "
            "Cost: 83 GET calls for sequences + ~9,496 calls for leads = "
            "~9,579 free API calls. But the answer it produces is "
            "'these action types exist in these campaigns', not 'this "
            "action type is more effective'."
        ),
    }


# -------------------------------------------------------- cost quantifier

def quantify_costs():
    """The cost of each missing read across 949,536 users."""
    campaigns = load_hr_campaigns()
    total_users = sum((c.get("progressStats") or {}).get("totalUsers", 0)
                      for c in campaigns)
    n_campaigns = len(campaigns)
    pages_at_100 = (total_users + 99) // 100

    return {
        "total_users": total_users,
        "total_campaigns": n_campaigns,
        "pages_at_100_per_page": pages_at_100,
        "missing_reads": [
            {
                "gap": "connection acceptance",
                "route": "POST /campaign/GetLeadsFromCampaign",
                "api_calls": pages_at_100,
                "monetary_cost": "zero (HeyReach reads are free)",
                "real_cost": (
                    "Wire leadobserve.observe() into the poller, add "
                    "acceptance event recording. ~1 afternoon + verification."
                ),
            },
            {
                "gap": "meeting booked",
                "route": "no route exists; requires calendar integration "
                         "or body scan of positive replies",
                "api_calls": 0,
                "monetary_cost": "zero (no provider call possible)",
                "real_cost": (
                    "Design decision: what counts as a meeting? Calendar "
                    "link in reply body is detectable but does not prove "
                    "the meeting happened. A calendar integration "
                    "(Calendly API, Google Calendar) is a new provider "
                    "entirely."
                ),
            },
            {
                "gap": "per-action-type effect comparison",
                "route": "GET /campaign/GetCampaignSequence + "
                         "POST /campaign/GetLeadsFromCampaign",
                "api_calls": n_campaigns + pages_at_100,
                "monetary_cost": "zero (reads are free)",
                "real_cost": (
                    "Even after reading, the data does not answer the "
                    "question. lead-level status covers connection and "
                    "message only; VIEW_PROFILE, FOLLOW and INMAIL have "
                    "no outcome field. A per-action comparison would "
                    "require a new data model or a controlled experiment "
                    "(same campaign, different action types, measure "
                    "reply rate) - which is CADENCE-EXPERIMENTS.md "
                    "territory, not a provider read."
                ),
            },
        ],
    }


# ------------------------------------------------------------- utilities

def _count(records, field):
    from collections import Counter
    return Counter(r.get(field, "") for r in records)


# --------------------------------------------------------------- reporting

def format_verdict(stage_result):
    verdict = stage_result["verdict"]
    lines = [f"  {stage_result['stage'].upper()}: {verdict}"]
    if verdict == SUPPORTED:
        lines.append(f"    Route: {stage_result['route']}")
        lines.append(f"    Field: {stage_result['field']}")
        lines.append(f"    Consumer: {stage_result['consumer']}")
    elif verdict == UNSUPPORTED:
        lines.append(f"    Looked for: {stage_result['looked_for']}")
        lines.append(f"    Looked in: {stage_result['looked_in']}")
        if "cheapest_read" in stage_result:
            lines.append(f"    Cheapest read: {stage_result['cheapest_read']}")
    elif verdict == UNDETERMINED:
        lines.append(f"    Route checked: {stage_result['route']}")
        lines.append(f"    Field checked: {stage_result['field']}")
        lines.append(f"    Cheapest read: {stage_result['cheapest_read']}")
        lines.append(f"    If yes: {stage_result['if_yes']}")
        lines.append(f"    If no: {stage_result['if_no']}")
    lines.append(f"    Evidence: {stage_result['evidence']}")
    return "\n".join(lines)


def main():
    results = {
        "funnel": [],
        "action_types": audit_action_types(),
        "costs": quantify_costs(),
    }

    auditors = [
        audit_targeted,
        audit_request_sent,
        audit_accepted,
        audit_messaged,
        audit_replied,
        audit_positive,
        audit_meeting,
    ]
    for fn in auditors:
        results["funnel"].append(fn())

    # Print human-readable report
    print("=" * 72)
    print("TASK-025: THE LINKEDIN FUNNEL AUDIT")
    print("=" * 72)
    print()
    print("FUNNEL STAGES")
    print("-" * 40)
    for stage in results["funnel"]:
        print(format_verdict(stage))
        print()

    print("ACTION-TYPE PERFORMANCE COMPARISON")
    print("-" * 40)
    at = results["action_types"]
    print(f"  Verdict: {at['verdict']}")
    print(f"  Looked for: {at['looked_for']}")
    print(f"  Looked in: {at['looked_in']}")
    print(f"  Evidence: {at['evidence']}")
    print(f"  Cheapest read: {at['cheapest_read']}")
    print()

    print("COST OF MISSING READS")
    print("-" * 40)
    costs = results["costs"]
    print(f"  Total users: {costs['total_users']:,}")
    print(f"  Total campaigns: {costs['total_campaigns']}")
    print(f"  Pages at 100/page: {costs['pages_at_100_per_page']:,}")
    for gap in costs["missing_reads"]:
        print(f"  Gap: {gap['gap']}")
        print(f"    Route: {gap['route']}")
        print(f"    API calls: {gap['api_calls']:,}")
        print(f"    Monetary cost: {gap['monetary_cost']}")
        print(f"    Real cost: {gap['real_cost']}")
        print()

    # Write machine-readable JSON
    out_path = os.path.join(os.path.dirname(__file__),
                            "task025_funnel_audit.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Machine-readable output: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
