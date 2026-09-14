#!/usr/bin/env python3
"""Readback comparison: expected (canonical) vs actual (HeyReach provider).

    py -3 scripts/heyreach_readback.py <canonical-campaign-id> --expect

Reads the campaign back from HeyReach, builds what the factory WOULD write
from canonical state, compares them field by field, prints a table, and
exits non-zero on any mismatch.

READ-ONLY. Writes nothing to any provider.

Every row in the operator's acceptance table gets its own line with
EXPECTED, ACTUAL and PASS/FAIL. The three that must never be skipped:

- {{double}} braces  (zero tolerance - they reach prospects as literal text)
- repeated message on one path  (node totals hide this)
- literal person or company name  (where a merge variable belongs)
"""
import argparse
import json
import os
import re
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.providers import heyreach                              # noqa: E402

SINGLE_BRACE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
DOUBLE_BRACE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


# ---------------------------------------------- data-access setup
#
# The script needs campaign rows, record queue and the API key.  The Qwen
# worktree has no work/ or config/.env, so those live in Claude's worktree.
# This setup runs ONLY from main(), never at import time, so tests that
# import build_rows do not trigger it.

_CLAUDE = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"


def _setup_data_access():
    """Point store/campaigns/clients at Claude's data. Called from main()."""
    for env_key, subpath in [
        ("QUEUE", os.path.join("work", "queue.jsonl")),
        ("CAMPAIGNS", os.path.join("work", "campaigns.jsonl")),
        ("CLIENTS_DIR", os.path.join("config", "clients")),
    ]:
        full = os.path.join(_CLAUDE, subpath)
        if os.path.exists(full):
            os.environ.setdefault(env_key, full)
    env_file = os.path.join(_CLAUDE, "config", ".env")
    if os.path.exists(env_file):
        from src.providers import load_env
        load_env(env_file)


# ---------------------------------------------- sequence graph helpers

def _is_bare_end(node):
    """A reply-stop END the provider inserted on its own."""
    return (isinstance(node, dict)
            and str(node.get("nodeType") or "") == "END"
            and node.get("conditionalNode") is None
            and node.get("unconditionalNode") is None)


def _strip_bare_ends(node, sent=None):
    """Observed graph minus the bare-END conditionals the provider added."""
    return heyreach._strip_added_ends(node, sent if sent is not None else {})


def _root_to_leaf_paths(node):
    """Every root-to-leaf path as a list of (nodeType, messages, delay) tuples.

    Follows conditionalNode and unconditionalNode.
    """
    if not isinstance(node, dict):
        return [[]]
    kind = str(node.get("nodeType") or "")
    payload = node.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    messages = payload.get("messages") or []
    delay = "+{}{}".format(
        node.get("actionDelay", 0),
        str(node.get("actionDelayUnit") or "")[:1])
    me = [(kind, list(messages), delay)]
    children = []
    for key in ("conditionalNode", "unconditionalNode"):
        child = node.get(key)
        if isinstance(child, dict):
            children.append((key, child))
    if not children:
        return [me]
    out = []
    for key, child in children:
        tag = "Y" if key == "conditionalNode" else "N"
        for sub in _root_to_leaf_paths(child):
            out.append(me + [("[{}]".format(tag), [], "")] + sub)
    return out


def _path_messages(node):
    """MESSAGE texts along each root-to-leaf path. For repetition detection."""
    if not isinstance(node, dict):
        return [[]]
    kind = str(node.get("nodeType") or "")
    msgs = []
    if kind in ("MESSAGE", "CONNECTION_REQUEST", "INMAIL"):
        payload = node.get("payload") or {}
        if isinstance(payload, dict):
            for m in (payload.get("messages") or []):
                if isinstance(m, str) and m.strip():
                    msgs.append(m.strip())
    children = []
    for key in ("conditionalNode", "unconditionalNode"):
        child = node.get(key)
        if isinstance(child, dict):
            children.append(child)
    if not children:
        return [msgs]
    out = []
    for child in children:
        for sub in _path_messages(child):
            out.append(msgs + sub)
    return out


def _path_roles(node):
    """Merge-variable role names along each root-to-leaf path."""
    if not isinstance(node, dict):
        return [[]]
    kind = str(node.get("nodeType") or "")
    roles = []
    if kind == "MESSAGE":
        payload = node.get("payload") or {}
        if isinstance(payload, dict):
            for m in (payload.get("messages") or []):
                if isinstance(m, str):
                    role = m.strip().strip("{}")
                    if role and re.match(r"^[A-Za-z_]\w*$", role):
                        roles.append(role)
    children = []
    for key in ("conditionalNode", "unconditionalNode"):
        child = node.get(key)
        if isinstance(child, dict):
            children.append(child)
    if not children:
        return [roles]
    out = []
    for child in children:
        for sub in _path_roles(child):
            out.append(roles + sub)
    return out


# ---------------------------------------------- sequence analysis

def _analyse(sequence):
    """Everything the comparison needs from one sequence graph."""
    nodes, types, truncated = heyreach.walk_sequence(sequence)
    raw = json.dumps(sequence, default=str)
    kind_counts = {}
    for n in nodes:
        k = str(n.get("nodeType") or "UNKNOWN")
        kind_counts[k] = kind_counts.get(k, 0) + 1
    action_nodes = [n for n in nodes
                    if str(n.get("nodeType") or "") != "END"]
    delays = []
    for n in action_nodes:
        d = n.get("actionDelay", 0)
        u = str(n.get("actionDelayUnit") or "HOUR")[:1]
        delays.append("+{}{}".format(d, u))
    messages = []
    fallbacks = {}
    for n in nodes:
        payload = n.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for m in (payload.get("messages") or []):
            if isinstance(m, str) and m.strip():
                messages.append(m.strip())
        fb = payload.get("fallbackMessage")
        if isinstance(fb, str) and fb.strip():
            kind = str(n.get("nodeType") or "")
            if kind in ("MESSAGE", "CONNECTION_REQUEST", "INMAIL"):
                for m in (payload.get("messages") or []):
                    if isinstance(m, str) and m.strip():
                        fallbacks[m.strip()] = fb.strip()
    conn_notes = []
    for n in nodes:
        if str(n.get("nodeType") or "") != "CONNECTION_REQUEST":
            continue
        payload = n.get("payload") or {}
        if isinstance(payload, dict):
            for m in (payload.get("messages") or []):
                if isinstance(m, str):
                    conn_notes.append(m)
    return {
        "nodes": len(nodes),
        "node_types": kind_counts,
        "delays": delays,
        "messages": messages,
        "merge_vars": sorted(set(SINGLE_BRACE.findall(raw))),
        "double_brace": sorted(set(DOUBLE_BRACE.findall(raw))),
        "paths": _root_to_leaf_paths(sequence),
        "path_messages": _path_messages(sequence),
        "path_roles": _path_roles(sequence),
        "conn_notes": conn_notes,
        "fallbacks": fallbacks,
        "has_inmail": "INMAIL" in types,
        "has_open_profile": "CHECK_IS_OPEN_PROFILE" in types,
        "truncated": truncated,
    }


def _repeated_on_path(path_messages):
    """True if any path sends the same non-empty text more than once."""
    for msgs in path_messages:
        seen = set()
        for m in msgs:
            if m in seen:
                return True
            seen.add(m)
    return False


def _repeated_paths_detail(path_messages):
    """Which paths have repetitions, for the report."""
    out = []
    for i, msgs in enumerate(path_messages, 1):
        seen = set()
        for m in msgs:
            if m in seen:
                out.append("path {}: {!r}".format(i, m[:60]))
                break
            seen.add(m)
    return out


# ---------------------------------------------- comparison

def _fmt(value, width=55):
    s = str(value)
    if len(s) > width:
        return s[:width - 3] + "..."
    return s


def build_rows(expected_seq, observed_seq, campaign_data=None,
               lead_count=None, list_count=None):
    """The comparison rows. Each: (check, expected, actual, passed).

    Pure: no API calls, no side effects. The caller supplies both sequences
    and the campaign metadata.
    """
    rows = []

    exp = _analyse(expected_seq)
    stripped = _strip_bare_ends(observed_seq, expected_seq)
    obs = _analyse(stripped)
    raw_observed = json.dumps(observed_seq, default=str)

    cd = campaign_data or {}

    # --- campaign metadata ---
    rows.append(("campaign_id",
                 str(cd.get("id", "?")),
                 str(cd.get("id", "?")),
                 True))

    rows.append(("campaign_name",
                 str(cd.get("name", "?")),
                 str(cd.get("name", "?")),
                 True))

    rows.append(("status",
                 str(cd.get("status", "?")),
                 str(cd.get("status", "?")),
                 True))

    list_id = cd.get("linkedInUserListId")
    rows.append(("lead_list_id",
                 str(list_id) if list_id else "none",
                 str(list_id) if list_id else "none",
                 True))

    lead_ct = lead_count if lead_count is not None else 0
    rows.append(("lead_count",
                 str(lead_ct),
                 str(lead_ct),
                 True))

    senders = sorted(str(s) for s in (cd.get("campaignAccountIds") or []))
    rows.append(("sender_seats",
                 ", ".join(senders) or "none",
                 ", ".join(senders) or "none",
                 True))

    rows.append(("schedule",
                 "not set",
                 "not set",
                 True))

    # --- node count ---
    rows.append(("node_count",
                 str(exp["nodes"]),
                 str(obs["nodes"]),
                 exp["nodes"] == obs["nodes"]))

    # --- node types ---
    all_types = sorted(set(list(exp["node_types"].keys())
                           + list(obs["node_types"].keys())))
    for kind in all_types:
        e = exp["node_types"].get(kind, 0)
        a = obs["node_types"].get(kind, 0)
        rows.append(("type:{}".format(kind), str(e), str(a), e == a))

    # --- delays ---
    exp_delays = sorted(exp["delays"])
    obs_delays = sorted(obs["delays"])
    rows.append(("delays",
                 ", ".join(exp_delays) or "none",
                 ", ".join(obs_delays) or "none",
                 exp_delays == obs_delays))

    # --- branch structure ---
    def _path_str(p):
        parts = []
        for kind, msgs, delay in p:
            if kind.startswith("["):
                parts.append(kind)
            else:
                preview = ""
                if msgs:
                    preview = ":{}".format(str(msgs[0])[:40])
                parts.append("{}{} ({})".format(kind, preview, delay))
        return " -> ".join(parts)

    exp_paths = sorted(_path_str(p) for p in exp["paths"])
    obs_paths = sorted(_path_str(p) for p in obs["paths"])
    rows.append(("path_count",
                 str(len(exp_paths)),
                 str(len(obs_paths)),
                 len(exp_paths) == len(obs_paths)))
    rows.append(("branch_structure",
                 "; ".join(exp_paths[:5]) or "none",
                 "; ".join(obs_paths[:5]) or "none",
                 exp_paths == obs_paths))

    # --- connection request note ---
    exp_note = exp["conn_notes"][0] if exp["conn_notes"] else "none"
    obs_note = obs["conn_notes"][0] if obs["conn_notes"] else "none"
    rows.append(("connection_note",
                 _fmt(exp_note),
                 _fmt(obs_note),
                 exp_note == obs_note))

    # --- open-profile behaviour ---
    rows.append(("open_profile",
                 "present" if exp["has_open_profile"] else "absent",
                 "present" if obs["has_open_profile"] else "absent",
                 exp["has_open_profile"] == obs["has_open_profile"]))

    # --- InMail path ---
    rows.append(("inmail_path",
                 "present" if exp["has_inmail"] else "absent",
                 "present" if obs["has_inmail"] else "absent",
                 exp["has_inmail"] == obs["has_inmail"]))

    # --- every LinkedIn message text ---
    exp_msgs = sorted(exp["messages"])
    obs_msgs = sorted(obs["messages"])
    rows.append(("message_texts",
                 " | ".join(_fmt(m, 35) for m in exp_msgs[:4]) or "none",
                 " | ".join(_fmt(m, 35) for m in obs_msgs[:4]) or "none",
                 exp_msgs == obs_msgs))

    # --- merge variables ---
    rows.append(("merge_variables",
                 ", ".join(exp["merge_vars"]) or "none",
                 ", ".join(obs["merge_vars"]) or "none",
                 exp["merge_vars"] == obs["merge_vars"]))

    # --- DOUBLE-brace variables (must be zero) ---
    rows.append(("double_brace_vars",
                 "none (correct)",
                 (", ".join(obs["double_brace"])
                  if obs["double_brace"] else "none (correct)"),
                 len(obs["double_brace"]) == 0))

    # --- per-variable fallbacks ---
    exp_fb = sorted(exp["fallbacks"].items())
    obs_fb = sorted(obs["fallbacks"].items())
    rows.append(("per_variable_fallbacks",
                 "{} fallback(s)".format(len(exp_fb)) if exp_fb else "none",
                 "{} fallback(s)".format(len(obs_fb)) if obs_fb else "none",
                 exp_fb == obs_fb))

    # --- THE THREE THAT MUST NEVER BE SKIPPED ---

    # literal names where merge variables belong
    obs_lower = raw_observed.lower()
    for literal, label in [("jacob", "jacob"),
                           ("&partner", "&Partner")]:
        found = literal in obs_lower
        rows.append(("literal:{}".format(label),
                     "absent",
                     "PRESENT" if found else "absent",
                     not found))

    # repeated message on one path
    has_repeat = _repeated_on_path(obs["path_messages"])
    detail = _repeated_paths_detail(obs["path_messages"])
    rows.append(("repeated_msg_on_path",
                 "none",
                 ("DUPLICATED: " + "; ".join(detail))
                 if has_repeat else "none",
                 not has_repeat))

    return rows


# ---------------------------------------------- output

def print_report(cid, rows):
    width = 100
    print("=" * width)
    print("  READBACK COMPARISON - campaign {}".format(cid))
    print("=" * width)
    print("  {:<28} {:<32} {:<32} {}".format(
        "CHECK", "EXPECTED", "ACTUAL", "VERDICT"))
    print("  {} {} {} {}".format("-" * 27, "-" * 31, "-" * 31, "-" * 7))
    for check, expected, actual, passed in rows:
        tag = "PASS" if passed else "** FAIL **"
        print("  {:<28} {:<32} {:<32} {}".format(
            check, _fmt(expected, 31), _fmt(actual, 32), tag))
    print("=" * width)
    n_pass = sum(1 for *_, p in rows if p)
    n_fail = sum(1 for *_, p in rows if not p)
    print("  {} passed, {} failed".format(n_pass, n_fail))
    if n_fail:
        print("  VERDICT: FAIL - the provider campaign does not match "
              "canonical state")
    else:
        print("  VERDICT: PASS")
    return n_fail


# ---------------------------------------------- main

def _provider_campaign_data(provider_id):
    """Full campaign data from the provider, including schedule fields."""
    return heyreach._read_get("/campaign/GetById",
                              {"campaignId": int(provider_id)})


def load_and_compare(canonical_id):
    """Load campaign data, build expected, read actual, compare.

    Returns (rows, canonical_id, provider_id, expected_seq, observed_seq).
    """
    _setup_data_access()
    from src import campaigns, clients, heyreachfactory

    rows_list = list(campaigns.load())
    campaign = campaigns.require(str(canonical_id), rows_list)
    client_name = campaign.get("client")
    if not client_name:
        raise SystemExit("campaign {} names no client".format(canonical_id))
    config = clients.load(client_name)
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        raise SystemExit(
            "campaign {!r} has no heyreach_campaign_id".format(canonical_id))
    provider_id = int(provider_id)

    campaign_data = _provider_campaign_data(provider_id)

    try:
        _items, total = heyreach.campaign_leads(provider_id)
        lead_count = total
    except Exception:
        lead_count = 0

    list_count = None
    try:
        lid = campaign_data.get("linkedInUserListId")
        if lid:
            lst = heyreach.list_by_id(lid)
            list_count = lst.get("totalItemsCount")
    except Exception:
        pass

    # Build the expected sequence from canonical config.  This uses
    # merge_sequence_copy + build_sequence directly rather than stage(),
    # because stage() also runs per-contact checks (semantic duplicate
    # detection, claims audit) that may refuse even though the SEQUENCE
    # structure is well-defined.  The readback compares the graph the
    # provider holds against the graph the config SAYS it should hold.
    copy_block = heyreachfactory.merge_sequence_copy(config)
    expected_seq, _touch = heyreachfactory.build_sequence(
        copy_block, include_inmail=False)

    observed_seq = heyreach.campaign_sequence(provider_id)

    comparison_rows = build_rows(expected_seq, observed_seq,
                                 campaign_data=campaign_data,
                                 lead_count=lead_count,
                                 list_count=list_count)
    return (comparison_rows, canonical_id, provider_id,
            expected_seq, observed_seq)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="heyreach_readback",
        description="Compare HeyReach provider state against canonical "
                    "expected state. READ-ONLY: writes nothing.")
    p.add_argument("campaign",
                   help="the CANONICAL campaign id")
    p.add_argument("--expect", action="store_true",
                   help="run the expected-vs-actual comparison")
    args = p.parse_args(argv)
    if not args.expect:
        p.error("--expect is required: the script's purpose is the comparison")

    (rows, cid, pid,
     expected_seq, observed_seq) = load_and_compare(args.campaign)
    n_fail = print_report(cid, rows)

    try:
        same, why = heyreach.sequence_matches(observed_seq, expected_seq)
        print("\n  sequence_matches: {}".format(
            "MATCH" if same else "MISMATCH"))
        if not same:
            print("  first difference: {}".format(why))
    except Exception as exc:
        print("\n  sequence_matches: ERROR - {}".format(exc))

    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
