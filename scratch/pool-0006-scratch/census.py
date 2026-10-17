"""POOL 0006 census — sweep src/ and scripts/ for send entry points.

For each provider-write call site, classify:
  - DOOR        : reaches the transport via providerwrites.perform /
                  liststaging.stage_lead / heyreachfactory._mint_authorization
  - NOT-DOOR    : reaches the transport directly

For DOOR sites, classify the fatigue-check status:
  - GATED-FACING   : door is facing=True, requires Authorization, which calls
                     executionguard.authorize -> eligibility.decide ->
                     _account_fatigue. Fatigue IS consulted.
  - GATED-DECIDE   : caller invokes eligibility.decide directly before the
                     door. Fatigue IS consulted.
  - UNGATED-STAGING: door is facing=False (staging), no Authorization required.
                     Fatigue IS NOT consulted.
  - DEAD           : the path raises before reaching the provider (refuse_live,
                     LiveSendNotEnabled, sealed operation, etc.)
  - BEHIND-FLAG    : reachable only with a flag or env var
  - BEHIND-RAISE   : reachable only if a specific exception is caught / lifted

For NOT-DOOR sites, the same classification applies, but the site bypasses
perform entirely, so the default is UNGATED unless something else gates it.

The brief's question: of the paths the canary would actually send from,
which reach the fatigue hold and which bypass it?
"""
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import providerwrites  # noqa: E402


# Provider write verbs. Same shape as check_write_site_inventory.py.
BISON_WRITE_VERBS = {
    "set_limits", "set_schedule", "attach_senders", "ensure_custom_variables",
    "update_lead", "create_lead", "create_campaign", "attach_leads",
    "pause_campaign", "resume_campaign", "stop_lead", "set_sequence",
}
HEYREACH_WRITE_VERBS = {
    "create_list", "create_campaign", "set_sequence", "add_leads_to_list",
    "add_leads_to_campaign", "start_campaign", "activate_campaign",
    "pause_campaign", "stop_lead_in_campaign", "resume_campaign",
}

# Map provider verb -> providerwrites operation constant name(s).
VERB_TO_OP = {
    "bison": {
        "set_limits": ("EMAIL_SET_LIMITS",),
        "set_schedule": None,
        "attach_senders": ("EMAIL_ASSIGN_SENDER",),
        "ensure_custom_variables": None,
        "update_lead": None,
        "create_lead": ("EMAIL_ADD_LEAD",),
        "create_campaign": ("EMAIL_CREATE_CAMPAIGN",),
        "attach_leads": ("EMAIL_ADD_LEAD",),
        "pause_campaign": ("EMAIL_PAUSE",),
        "resume_campaign": ("EMAIL_RESUME",),
        "stop_lead": ("EMAIL_STOP_LEAD",),
        "set_sequence": ("EMAIL_SET_SEQUENCE",),
    },
    "heyreach": {
        "create_list": ("LINKEDIN_CREATE_LIST",),
        "create_campaign": ("LINKEDIN_CREATE_CAMPAIGN",),
        "set_sequence": ("LINKEDIN_SET_SEQUENCE",),
        "add_leads_to_list": ("LINKEDIN_ADD_LEAD_TO_LIST",),
        "add_leads_to_campaign": ("LINKEDIN_ADD_LEAD",),
        "start_campaign": ("LINKEDIN_ACTIVATE",
                           "LINKEDIN_START_EMPTY_FOR_STAGING"),
        "activate_campaign": ("LINKEDIN_ACTIVATE",),
        "pause_campaign": ("LINKEDIN_PAUSE",),
        "stop_lead_in_campaign": ("LINKEDIN_STOP_LEAD",),
        "resume_campaign": ("LINKEDIN_RESUME",),
    },
}


def list_py_files(ref="HEAD"):
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", ref, "--", "scripts", "src"],
        text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    files = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if path.endswith(".py"):
            files.append(path)
    return files


def read_blob(ref, path):
    return subprocess.check_output(
        ["git", "show", "%s:%s" % (ref, path)],
        text=True, encoding="utf-8", errors="replace", cwd=ROOT)


def enclosing_scope(lines, lineno):
    """Nearest enclosing def/class for lineno (1-based)."""
    if lineno < 1 or lineno > len(lines):
        return "<module-level>"
    hit_indent = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip())
    scope = "<module-level>"
    for i in range(lineno - 2, -1, -1):
        ln = lines[i]
        s = ln.lstrip()
        if not s or s.startswith("#"):
            continue
        indent = len(ln) - len(s)
        if indent < hit_indent:
            if s.startswith(("def ", "class ", "async def ")):
                scope = s.rstrip()
                if indent == 0:
                    return scope
                hit_indent = indent
    return scope


def is_inside_perform_or_stage_lead(lines, lineno):
    """Is this call site inside a def whose body is perform/stage_lead?"""
    scope = enclosing_scope(lines, lineno)
    return any(name in scope for name in
               ("def perform(", "def _perform(", "def stage_lead("))


def operation_facing(op_name):
    """Is this operation prospect-facing in providerwrites.OPERATIONS?"""
    if op_name is None:
        return None
    op = getattr(providerwrites, op_name, None)
    if op is None:
        return None
    entry = providerwrites.OPERATIONS.get(op)
    if entry is None:
        return None
    return entry[1]  # (channel, facing, why)


def classify_site(provider, verb, path, lineno, lines):
    """Classify one call site.

    Returns a dict with keys:
      provider, verb, path, lineno, scope,
      door, operation, facing, fatigue_check, reachability, notes
    """
    scope = enclosing_scope(lines, lineno)

    # 1. Is this call inside liststaging.stage_lead or providerwrites._perform?
    inside_door = is_inside_perform_or_stage_lead(lines, lineno)
    # Also treat heyreachfactory._mint_authorization as a door (it calls
    # executionguard.authorize which consults fatigue).
    if "_mint_authorization" in scope:
        inside_door = True

    # 2. The prototype push.py is dead.
    if "prototype" in path.replace("\\", "/"):
        reachability = "DEAD"
        door = "NOT-DOOR"
        notes = "prototype/bin/push.py: refuse_live() on every --live path"
        return {
            "provider": provider, "verb": verb, "path": path,
            "lineno": lineno, "scope": scope, "door": door,
            "operation": None, "facing": None,
            "fatigue_check": "NOT-CONSULTED",
            "reachability": reachability, "notes": notes,
        }

    # 3. Determine the operation constant
    op_names = VERB_TO_OP.get(provider, {}).get(verb)
    op_name = op_names[0] if op_names else None

    # 4. Facing?
    facing = operation_facing(op_name) if op_name else None

    # 5. Is the operation sealed?
    sealed = op_name == "LINKEDIN_ADD_LEAD"
    # LINKEDIN_ADD_LEAD is sealed at perform-time: the CONDITIONAL predicate
    # refuses it because the destination campaign must be DRAFT. So even
    # though facing=True, it cannot succeed today.
    if sealed and inside_door:
        reachability = "SEALED"
        notes = ("LINKEDIN_ADD_LEAD is prospect-facing but CONDITIONAL on "
                 "campaign being DRAFT; the canary campaign is not")
        return {
            "provider": provider, "verb": verb, "path": path,
            "lineno": lineno, "scope": scope, "door": "DOOR",
            "operation": op_name, "facing": facing,
            "fatigue_check": "CONSULTED-IF-REACHABLE",
            "reachability": reachability, "notes": notes,
        }

    # 6. Classify
    if inside_door:
        door = "DOOR"
        if facing is True:
            fatigue_check = "CONSULTED"
            reachability = "REACHABLE-DEFAULT"
            notes = ("facing=True: perform demands an Authorization from "
                     "executionguard.authorize, which calls "
                     "eligibility.decide -> _account_fatigue")
        elif facing is False:
            fatigue_check = "NOT-CONSULTED"
            reachability = "REACHABLE-DEFAULT"
            notes = ("facing=False: perform does NOT demand an Authorization, "
                     "eligibility.decide is not called, fatigue is not asked")
        else:
            fatigue_check = "UNKNOWN"
            reachability = "UNKNOWN"
            notes = "no OPERATIONS entry for this verb"
    else:
        door = "NOT-DOOR"
        fatigue_check = "NOT-CONSULTED"
        # Some NOT-DOOR sites are still alive (batch scripts, factory helpers).
        # Others are probes or one-shots.
        if "probe" in path.lower() or "make_" in path.lower():
            reachability = "DEAD/PROBE"
            notes = "probe or one-shot script"
        elif "activate" in path.lower():
            # Activation scripts call authorize directly before perform, so
            # they ARE gated even if the perform call itself is bypassed.
            reachability = "REACHABLE-DEFAULT"
            notes = ("NOT-DOOR but caller may invoke executionguard.authorize "
                     "elsewhere in the same flow - see harness sweep")
        else:
            reachability = "REACHABLE-DEFAULT"
            notes = "live NOT-DOOR site; check the call chain"

    return {
        "provider": provider, "verb": verb, "path": path,
        "lineno": lineno, "scope": scope, "door": door,
        "operation": op_name, "facing": facing,
        "fatigue_check": fatigue_check,
        "reachability": reachability, "notes": notes,
    }


def sweep(ref="HEAD"):
    """Walk every .py file under scripts/ and src/ at the given ref.

    Returns a list of call sites (dicts).
    """
    files = list_py_files(ref)
    sites = []
    adapter_pattern = re.compile(
        r"(?<!\w)(bison|heyreach)\.(\w+)\s*\(")
    for path in files:
        try:
            text = read_blob(ref, path)
        except subprocess.CalledProcessError:
            continue
        lines = text.splitlines()
        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            for m in adapter_pattern.finditer(raw):
                provider = m.group(1)
                verb = m.group(2)
                verb_set = (BISON_WRITE_VERBS if provider == "bison"
                            else HEYREACH_WRITE_VERBS)
                if verb not in verb_set:
                    continue
                site = classify_site(provider, verb, path, lineno, lines)
                sites.append(site)
    return sites


def sweep_eligibility_callers(ref="HEAD"):
    """Find direct callers of eligibility.decide / authorize / for_record.

    These are GATED by definition - they consult the fatigue check
    directly.
    """
    patterns = [
        ("eligibility.decide",
         re.compile(r"(?<!\w)eligibility\.decide\s*\(")),
        ("eligibility.require",
         re.compile(r"(?<!\w)eligibility\.require\s*\(")),
        ("eligibility.for_record",
         re.compile(r"(?<!\w)eligibility\.for_record\s*\(")),
        ("executionguard.authorize",
         re.compile(r"(?<!\w)executionguard\.authorize\s*\(")),
    ]
    files = list_py_files(ref)
    callers = []
    for path in files:
        try:
            text = read_blob(ref, path)
        except subprocess.CalledProcessError:
            continue
        lines = text.splitlines()
        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            for label, rx in patterns:
                if rx.search(raw):
                    callers.append({
                        "name": label, "path": path, "lineno": lineno,
                        "scope": enclosing_scope(lines, lineno),
                        "line": stripped,
                    })
    return callers


def main():
    ref = "HEAD"
    print("=" * 72)
    print("POOL 0006 - send-path census at %s" % ref)
    print("=" * 72)
    print()

    sites = sweep(ref)
    print("--- provider-write call sites: %d ---" % len(sites))
    for s in sites:
        print(("  {path}:{lineno}  {provider}.{verb}"
               "  door={door}  facing={facing}  fatigue={fatigue_check}"
               "  reach={reachability}"
               .format(**s)))
        if s["notes"]:
            print("      notes: %s" % s["notes"])
    print()

    # ----- summarise by reachability
    by_reach = {}
    for s in sites:
        by_reach.setdefault(s["reachability"], []).append(s)
    print("--- by reachability ---")
    for reach, items in sorted(by_reach.items()):
        print("  %s: %d" % (reach, len(items)))
    print()

    # ----- summarise by fatigue check
    by_fatigue = {}
    for s in sites:
        by_fatigue.setdefault(s["fatigue_check"], []).append(s)
    print("--- by fatigue check ---")
    for fatigue, items in sorted(by_fatigue.items()):
        print("  %s: %d" % (fatigue, len(items)))
    print()

    # ----- direct callers of eligibility
    callers = sweep_eligibility_callers(ref)
    print("--- direct callers of eligibility / authorize: %d ---" %
          len(callers))
    by_name = {}
    for c in callers:
        by_name.setdefault(c["name"], []).append(c)
    for name, items in sorted(by_name.items()):
        print("  %s: %d callers" % (name, len(items)))
        for c in items[:10]:
            print("    %s:%d  [%s]" % (c["path"], c["lineno"], c["scope"]))
        if len(items) > 10:
            print("    ... and %d more" % (len(items) - 10))
    print()

    # ----- the denominator the brief asks for
    print("=" * 72)
    print("DENOMINATOR (the brief's question)")
    print("=" * 72)
    print()
    total = len(sites)
    reachable = [s for s in sites
                 if s["reachability"] == "REACHABLE-DEFAULT"]
    gated_reachable = [s for s in reachable
                       if s["fatigue_check"] == "CONSULTED"]
    ungated_reachable = [s for s in reachable
                         if s["fatigue_check"] == "NOT-CONSULTED"]
    dead = [s for s in sites if s["reachability"] in ("DEAD", "DEAD/PROBE")]
    sealed = [s for s in sites if s["reachability"] == "SEALED"]
    unknown = [s for s in sites if s["reachability"] == "UNKNOWN"]

    print("  total provider-write sites  : %d" % total)
    print("  REACHABLE-DEFAULT           : %d" % len(reachable))
    print("    -> fatigue CONSULTED      : %d" % len(gated_reachable))
    print("    -> fatigue NOT-CONSULTED  : %d" % len(ungated_reachable))
    print("  DEAD / PROBE                : %d" % len(dead))
    print("  SEALED                      : %d" % len(sealed))
    print("  UNKNOWN                     : %d" % len(unknown))
    print()
    print("  direct eligibility.decide callers (in src/ + scripts/):")
    for name, items in sorted(by_name.items()):
        print("    %s: %d" % (name, len(items)))
    print()

    if ungated_reachable:
        print("--- UNGATED-REACHABLE sites (the risk the brief names) ---")
        for s in ungated_reachable:
            print("  %s:%d  %s.%s  [%s]" %
                  (s["path"], s["lineno"], s["provider"], s["verb"],
                   s["scope"]))
            print("      notes: %s" % s["notes"])


if __name__ == "__main__":
    main()
