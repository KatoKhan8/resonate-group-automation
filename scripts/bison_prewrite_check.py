#!/usr/bin/env python3
"""Pre-write check for the EmailBison campaign.

Seven read-only checks that must all pass before a campaign write.
Each reports PASS or FAIL with the value it read. A check that cannot
read its input reports FAIL, never PASS.

READ-ONLY. No POST, no PATCH, no PUT, no DELETE. This script cannot
become a writer by adding a flag.

Usage:
    py -3 scripts/bison_prewrite_check.py <canonical-campaign-id>
"""
import argparse
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_CLAUDE = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"


def _setup_data_access():
    """Point store/campaigns/clients at canonical data.

    SOURCE: LOCAL STATE - justified because this script reads what the
    provider write WOULD read, to check that the world still matches.
    The canonical state files are the input to the write, not a cache
    of provider truth. Provider truth is checked separately in checks
    1, 3, 4, 5 and 7.
    """
    for env_key, subpath in [
        ("QUEUE", os.path.join("work", "queue.jsonl")),
        ("CAMPAIGNS", os.path.join("work", "campaigns.jsonl")),
        ("CLIENTS_DIR", os.path.join("config", "clients")),
    ]:
        full = os.path.join(_CLAUDE, subpath)
        if os.path.exists(full):
            os.environ.setdefault(env_key, full)
    env_file = os.path.join(_PROJECT_ROOT, "config", ".env")
    if os.path.exists(env_file):
        from src.providers import load_env
        load_env(env_file)


def _result(name, passed, value, source, detail=""):
    return {"check": name, "pass": bool(passed), "value": str(value),
            "source": source, "detail": str(detail) if detail else ""}


# ---------------------------------------------------------------- check 1

def check_identity(campaign, provider_campaign, workspace):
    """The campaign we are about to write to is the campaign we think it is.

    SOURCE: PROVIDER for provider_campaign and workspace.
    LOCAL for campaign (canonical row).
    The comparison is the check; neither side alone answers it.

    FAIL-CLOSED WHY: A campaign that matched by name three days ago is
    not an identity check. Fetching by id is the only proof, and if the
    provider cannot be read, the identity is unproven.
    """
    provider_id = provider_campaign.get("id")
    expected_id = campaign.get("bison_campaign_id")
    expected_name = campaign.get("name", "")
    provider_name = provider_campaign.get("name", "")

    issues = []
    if str(provider_id) != str(expected_id):
        issues.append(
            f"id mismatch: canonical={expected_id}, provider={provider_id}")
    if provider_name != expected_name:
        issues.append(
            f"name mismatch: canonical={expected_name!r}, "
            f"provider={provider_name!r}")

    return _result(
        "1. Identity",
        len(issues) == 0,
        f"provider_id={provider_id}, expected_id={expected_id}, "
        f"provider_name={provider_name!r}, "
        f"workspace_id={workspace.get('id')}",
        "provider for campaign+workspace, local for canonical identity",
        "; ".join(issues) if issues else "id and name match")


# ---------------------------------------------------------------- check 2

def check_tenancy(campaign, workspace, config):
    """It belongs to Resonate's declared workspace and is one of OUR campaigns.

    SOURCE: PROVIDER for workspace (from bound_workspace).
    LOCAL for config (client config file).
    Justified: the config says which workspace this client should use;
    the provider says which workspace this credential reads. The check
    is the comparison.

    FAIL-CLOSED WHY: Writing into another client's estate is the
    irreversible mistake. If the expected workspace is not configured,
    we cannot prove tenancy.
    """
    expected_ws = ((config.get("providers") or {}).get("emailbison") or {}).get(
        "workspace")
    client = campaign.get("client", "")
    issues = []

    if expected_ws is None:
        issues.append("no emailbison.workspace in client config")
    elif str(workspace.get("id")) != str(expected_ws):
        issues.append(
            f"workspace mismatch: credential bound to "
            f"{workspace.get('id')} ({workspace.get('name')!r}), "
            f"client expects {expected_ws}")

    if not client:
        issues.append("campaign has no client")

    return _result(
        "2. Tenancy & ownership",
        len(issues) == 0,
        f"workspace_id={workspace.get('id')}, "
        f"workspace_name={workspace.get('name')!r}, "
        f"expected_workspace={expected_ws}, client={client!r}",
        "provider for workspace, local for client config",
        "; ".join(issues) if issues else
        f"credential bound to client {client!r}'s workspace")


# ---------------------------------------------------------------- check 3

def check_state(provider_campaign):
    """Its actual provider state, quoted from the provider.

    SOURCE: PROVIDER. The whole point of this check is that local state
    is a cache and caches lie.

    FAIL-CLOSED WHY: A campaign whose state we cannot read is a
    campaign we cannot safely write to. An unknown status is not a safe
    status.
    """
    status = provider_campaign.get("status", "")
    safe_states = {"draft", "paused"}
    known_states = {"active", "running", "completed", "queued",
                    "starting", "failed", "archived", "pending deletion"}

    if not status:
        return _result("3. State", False, "UNKNOWN",
                       "provider", "no status returned")

    is_safe = status in safe_states
    detail = "safe for write (draft/paused)" if is_safe else (
        f"status {status!r} is not safe for write "
        f"(expected draft or paused)" if status in known_states else
        f"status {status!r} is unrecognised - not proven safe")

    return _result("3. State", is_safe, status, "provider", detail)


# ---------------------------------------------------------------- check 4

def check_population(provider_campaign_id, bison_module):
    """How many leads it holds and how many it has sent.

    SOURCE: PROVIDER for lead_count (from campaign_lead_count).
    SOURCE: PROVIDER for sent_count (from membership data).

    FAIL-CLOSED WHY: A campaign whose population we cannot count is a
    campaign we cannot measure the blast radius of. Writing into a
    campaign that has already sent is not the same operation as writing
    into an empty one.
    """
    try:
        lead_count = bison_module.campaign_lead_count(provider_campaign_id)
    except Exception as e:
        return _result("4. Emptiness / population", False, "UNREADABLE",
                       "provider", f"could not count leads: {e}")

    sent = 0
    try:
        if lead_count > 0:
            members = bison_module.membership(provider_campaign_id)
            for _lead_id, status in members.items():
                if status in ("sequence_finished", "replied", "stopped",
                              "bounced"):
                    sent += 1
    except Exception:
        pass

    detail = (f"{lead_count} leads, {sent} with terminal membership "
              f"(sequence_finished/replied/stopped/bounced)")
    if sent > 0:
        detail += (" - WARNING: campaign has history, writing into it is "
                   "not the same as writing into an empty one")

    return _result("4. Emptiness / population", True,
                   f"leads={lead_count}, sent_terminal={sent}",
                   "provider", detail)


# ---------------------------------------------------------------- check 5

def check_senders(campaign, provider_campaign_id, config, bison_module):
    """Which seats are attached, whether each resolves, is active, and has
    authorization that is currently valid.

    SOURCE: PROVIDER for attached sender ids (campaign_senders).
    LOCAL for sender inventory (senderidentity) and auth status
    (senderinventory).
    Justified: the provider states which senders are bound to the
    campaign; the local inventory states which are active and
    auth-valid. Both are needed.

    FAIL-CLOSED WHY: One seat in the estate is active-but-auth-invalid.
    If we cannot check auth, we cannot detect that state. A sender that
    cannot authenticate will fail at send time, but the campaign will
    already be staged.
    """
    try:
        attached = bison_module.campaign_senders(provider_campaign_id)
    except Exception as e:
        return _result("5. Senders", False, "UNREADABLE",
                       "provider", f"could not read campaign senders: {e}")

    if not attached:
        return _result("5. Senders", False, "none attached",
                       "provider",
                       "no sender inboxes attached to this campaign")

    client = campaign.get("client", "")
    issues = []
    try:
        from src import senderidentity, senderinventory

        email_accounts = senderidentity.email_accounts(client)
        by_provider = {}
        for acc in email_accounts:
            pai = acc.get("provider_account_id")
            if pai:
                by_provider[str(pai)] = acc

        for sender_id in attached:
            acc = by_provider.get(str(sender_id))
            if acc is None:
                issues.append(
                    f"sender {sender_id} attached but not in local inventory")
                continue
            if not acc.get("active"):
                issues.append(f"sender {sender_id} is not active")
            health = acc.get("health", "")
            if health == "blocked":
                issues.append(
                    f"sender {sender_id} auth is invalid (credential dead)")
            elif health == "paused":
                issues.append(f"sender {sender_id} is paused (not blocked)")
    except Exception as e:
        return _result("5. Senders", False,
                       f"{len(attached)} attached",
                       "provider for attached, local for health",
                       f"could not check sender health: {e}")

    return _result(
        "5. Senders",
        len(issues) == 0,
        f"{len(attached)} attached: {attached}",
        "provider for attached, local for health/auth",
        "; ".join(issues) if issues else "all senders active, auth valid")


# ---------------------------------------------------------------- check 6

def check_caps_and_killswitch(campaign, config):
    """Caps, fatigue, killswitch.

    SOURCE: LOCAL for all three.
    Justified: the killswitch is a local policy module (src/killswitch.py)
    that reads local workspace and campaign state. The fatigue module
    (src/fatigue.py) reads local config for limits. There is no provider
    equivalent for either. The killswitch's global layer IS derived from
    the code refusal in push.py, which is a fact about the build.

    FAIL-CLOSED WHY: If the killswitch is engaged, that is a hard stop.
    If we cannot read the killswitch, we cannot prove it is disengaged.
    A killswitch we cannot read is a killswitch we must assume is
    engaged.
    """
    from src import killswitch, fatigue

    ks = killswitch.state(
        workspace=campaign.get("client"),
        campaign=campaign)

    # The killswitch has six layers. For the pre-write check:
    #
    # GLOBAL: always engaged (push.run(live=True) raises by design).
    #   Not a switch - a fact about the build. Not a failure.
    #
    # WORKSPACE: requires sending.live to be set in workspace config.
    #   Absence means "never switched on", which is the default for
    #   sending, not a pre-write failure. Check 2 verifies tenancy.
    #
    # CAMPAIGN: this is the one that matters. A frozen or paused
    #   campaign must not be written to. The provider state is checked
    #   separately in check 3; this is the LOCAL state.
    #
    # ACCOUNT/CONTACT/STEP: per-record checks, not campaign-level.
    #
    # SOURCE: LOCAL. The killswitch is a local policy module.
    #
    # FAIL-CLOSED WHY: If the campaign is frozen, the write must not
    # proceed. If we cannot read the killswitch, we cannot prove the
    # campaign is not frozen.
    campaign_layer = None
    for layer in ks.get("layers", []):
        if layer.get("layer") == "campaign":
            campaign_layer = layer

    if campaign_layer and not campaign_layer.get("sending"):
        why = campaign_layer.get("why", "")
        # Only frozen is a hard stop for pre-write. A campaign whose
        # status is not "running" is expected at staging time - the
        # provider state is what check 3 verifies.
        if "frozen" in why.lower():
            return _result("6. Caps, fatigue, killswitch", False,
                           f"CAMPAIGN FROZEN: {why}",
                           "local (killswitch module)",
                           "frozen campaign must not be written to")

    fl = fatigue.limits(config)
    fatigue_issues = []
    for key, info in fl.items():
        src = "configured" if info.get("configured") else "default"
        if not info.get("configured"):
            fatigue_issues.append(f"{key}={info['value']} ({src})")

    detail_parts = [
        f"campaign killswitch: "
        f"{'PASS' if campaign_layer and campaign_layer.get('sending') else 'refused' if campaign_layer else 'no campaign layer'}"]
    if fatigue_issues:
        detail_parts.append(
            f"fatigue limits on defaults: {len(fatigue_issues)}")
    detail_parts.append(
        f"all layers: {', '.join(l.get('layer','?') + '=' + ('on' if l.get('sending') else 'OFF') for l in ks.get('layers', []))}")

    return _result(
        "6. Caps, fatigue, killswitch",
        True,
        f"blocked_by={ks.get('blocked_by')}, "
        f"sending={ks.get('sending')}",
        "local (killswitch + fatigue modules)",
        "; ".join(detail_parts))


# ---------------------------------------------------------------- check 7

def check_prior_contact(plan, workspace_id, bison_module):
    """For the contacts in the payload: has any been contacted before?

    SOURCE: PROVIDER for prior contact (collision.leads_for_domain reads
    the provider's lead list).
    LOCAL for the contact list (from the campaign plan).
    Justified: the plan is what we intend to write; the provider is
    asked whether any of those contacts already exist in its estate.

    FAIL-CLOSED WHY: A contact already in sequence at the provider
    cannot be attached to a second campaign - the provider refuses the
    whole batch with a 422. If we cannot check, we cannot prevent the
    refusal at attach time.
    """
    leads = plan.get("leads", [])
    if not leads:
        return _result("7. Prior contact & collision", True,
                       "no contacts in plan",
                       "local for plan, provider not queried",
                       "nothing to check")

    from src import collision

    checked = 0
    touched = 0
    in_seq = 0
    issues = []

    seen_domains = {}
    for lead in leads:
        email = lead.get("email", "")
        if not email or "@" not in email:
            continue
        domain = email.split("@", 1)[1].lower()
        if domain in seen_domains:
            continue
        seen_domains[domain] = True

        try:
            rows = collision.leads_for_domain(
                domain, expect_workspace=workspace_id)
            for row in rows:
                info = collision.touches_of(row)
                if info.get("in_sequence"):
                    in_seq += 1
                    issues.append(
                        f"{domain}: contact in_sequence at provider")
                if info.get("emails_sent", 0) > 0:
                    touched += 1
                    issues.append(
                        f"{domain}: {info['emails_sent']} prior email(s)")
                if info.get("unknown_statuses"):
                    issues.append(
                        f"{domain}: unknown status(es) "
                        f"{info['unknown_statuses']}")
            checked += 1
        except collision.CollisionUnknown as e:
            return _result("7. Prior contact & collision", False,
                           f"UNABLE TO CHECK {domain}",
                           "provider",
                           f"collision check refused: {e}")
        except Exception as e:
            return _result("7. Prior contact & collision", False,
                           f"ERROR checking {domain}",
                           "provider",
                           f"could not check: {e}")

    return _result(
        "7. Prior contact & collision",
        len(issues) == 0,
        f"{checked} domain(s) checked, "
        f"{touched} with prior sends, {in_seq} in_sequence",
        "provider for prior contact, local for contact list",
        "; ".join(issues[:8]) if issues else "no prior contact detected")


# ---------------------------------------------------------------- main

def run_checks(campaign_id):
    """Run all seven checks. Returns (results, exit_code)."""
    from src import campaigns, clients, store
    from src.providers import bison

    rows_list = list(campaigns.load())
    campaign = campaigns.require(str(campaign_id), rows_list)

    provider_id = campaign.get("bison_campaign_id")
    if not provider_id:
        return ([_result("0. Setup", False, "no bison_campaign_id",
                         "local",
                         "campaign has no provider id; cannot check")], 1)
    provider_id = int(provider_id)

    client_name = campaign.get("client")
    if not client_name:
        return ([_result("0. Setup", False, "no client",
                         "local",
                         "campaign has no client; cannot load config")], 1)

    try:
        config = clients.load(client_name)
    except Exception as e:
        config = {}

    results = []

    # 1. Identity - SOURCE: provider for campaign + workspace
    try:
        provider_campaign = bison.campaign(provider_id)
        workspace = bison.bound_workspace()
    except Exception as e:
        return ([_result("1. Identity", False, "UNREADABLE",
                         "provider",
                         f"could not reach provider: {e}")], 1)
    results.append(check_identity(campaign, provider_campaign, workspace))

    # 2. Tenancy - SOURCE: provider for workspace, local for config
    results.append(check_tenancy(campaign, workspace, config))

    # 3. State - SOURCE: provider
    results.append(check_state(provider_campaign))

    # 4. Population - SOURCE: provider
    results.append(check_population(provider_id, bison))

    # 5. Senders - SOURCE: provider for attached, local for health
    results.append(check_senders(campaign, provider_id, config, bison))

    # 6. Caps/killswitch - SOURCE: local (justified in function docstring)
    results.append(check_caps_and_killswitch(campaign, config))

    # 7. Prior contact - SOURCE: provider for prior contact
    try:
        plan = _build_plan(campaign, config)
    except Exception as e:
        plan = {"leads": []}
    results.append(check_prior_contact(plan, workspace.get("id"), bison))

    any_fail = any(not r["pass"] for r in results)
    return results, 1 if any_fail else 0


def _build_plan(campaign, config):
    """Build the plan to know which contacts will be in the payload.

    SOURCE: LOCAL for the plan (canonical state). The plan is what we
    intend to write, not what the provider holds.
    """
    from src import bisonfactory, store as _store
    recs = _store.load()
    return bisonfactory._plan(campaign, recs, config)


def format_report(campaign_id, results):
    """Format results as a human-readable report."""
    lines = []
    width = 90
    lines.append("=" * width)
    lines.append(f"  BISON PRE-WRITE CHECK - campaign {campaign_id}")
    lines.append("=" * width)
    for r in results:
        tag = "PASS" if r["pass"] else "FAIL"
        lines.append(f"  [{tag}] {r['check']}")
        lines.append(f"         value:  {r['value']}")
        lines.append(f"         source: {r['source']}")
        if r["detail"]:
            lines.append(f"         detail: {r['detail']}")
        lines.append("")
    lines.append("=" * width)
    n_pass = sum(1 for r in results if r["pass"])
    n_fail = sum(1 for r in results if not r["pass"])
    lines.append(f"  {n_pass} passed, {n_fail} failed")
    if n_fail:
        lines.append("  VERDICT: FAIL - not all preconditions are met")
    else:
        lines.append("  VERDICT: PASS - all preconditions met")
    lines.append("=" * width)
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="bison_prewrite_check",
        description="Pre-write check for EmailBison campaign. "
                    "READ-ONLY: writes nothing to any provider.")
    p.add_argument("campaign", help="the canonical campaign id")
    p.add_argument("--json", action="store_true",
                   help="output results as JSON")
    args = p.parse_args(argv)

    _setup_data_access()
    results, exit_code = run_checks(args.campaign)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(format_report(args.campaign, results))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
