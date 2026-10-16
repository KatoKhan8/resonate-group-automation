#!/usr/bin/env python3
"""Re-derive the write-site inventory and refuse what is neither door'd nor named.

TASK 0220 (GLM-C). The 58-site denominator existed until now only because a
lane counted it once. This script re-derives it from the tree on every run
and exits non-zero when a write site appears that is neither through the
write door nor on the named exemption list below.

WHAT IT ASKS, per direct mutating provider call (`bison.<verb>(...)` /
`heyreach.<verb>(...)`, verb inventories below):

    DOOR        the site reaches its transport only inside
                `providerwrites.perform` / `_perform` / `liststaging.stage_lead`
                - in-call, or through a name those calls reference
                (the three lexical rules of the 0210 brake test, which this
                classifier is ported from and must stay in lockstep with:
                tests/test_no_path_reaches_a_transport_without_passing_the_
                stop_sending_brake.py).

    NOT-DOOR    everything else. Each must appear in EXEMPTIONS below, keyed
                (file stem, provider.verb) with a PINNED SITE COUNT, a tier
                and a one-sentence reason. A site with no entry, an entry
                whose count no longer matches (a second site under an
                already-admitted key is a NEW site, not a rounding error),
                and a stale entry whose sites disappeared are all failures.
                Removing the sites an entry names - wiring them through the
                door - is exactly how an entry is meant to retire, and the
                count mismatch this raises is the handshake: the lane that
                wires them edits the table in the same commit.

FAIL-CLOSED. A file this cannot read or parse is a REFUSAL, not a skip: the
denominator is the proof, and a proof with a hole in it reports UNKNOWN as
clean. The same applies to the verb table - an inventory verb with no
operation mapping refuses rather than guessing - and to providerwrites'
own OPERATIONS shape. Exit codes: 0 clean, 1 violations, 2 refusals.

THREE CONTROLS print on every run, clean or not:
    1 the denominator - sites, door vs not-door;
    2 the tiers of the not-door sites (T1 prospect / T2 later-visible state /
      T3 unobservable), which must sum to the not-door count;
    3 integrity - refusals, unregistered sites, count mismatches, stale
      entries, and the inventory floor.

The tiers and every exemption reason are TASK 0220's recorded findings; the
two T1 entries are glm-a's TASK 0072 and are named here so the two lanes
cannot collide on the same lines silently.

No provider or network call is made. This reads source and one import of
src/providerwrites (for the facing flags OPERATIONS is the authority of).
"""
import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import providerwrites  # noqa: E402  (path set up first, on purpose)

DOOR_CALL_NAMES = {"perform", "_perform", "stage_lead"}

# The write inventories: every adapter verb that changes provider state.
# Deliberately a SUPERSET of the verbs that appear in the tree today, copied
# from the 0210 brake test so the two instruments share one denominator.
BISON_WRITE_VERBS = {
    "set_limits", "set_schedule", "attach_senders",
    "ensure_custom_variables", "update_lead", "create_lead",
    "create_campaign", "attach_leads", "pause_campaign",
    "resume_campaign", "stop_lead", "set_sequence",
}
HEYREACH_WRITE_VERBS = {
    "create_list", "create_campaign", "set_sequence",
    "add_leads_to_list", "add_leads_to_campaign", "start_campaign",
    "activate_campaign", "pause_campaign", "stop_lead_in_campaign",
    "resume_campaign",
}

# Adapter verb -> the operation constant(s) in src/providerwrites.py that
# declare it, or None where no operation is declared (itself a fact: routing
# that verb through the door would first need an OPERATIONS entry, which is
# an operator decision). heyreach.start_campaign is TWO operations told
# apart only by the zero-lead condition at the call site, so both are listed
# and the facing column prints both. A name that vanishes from
# providerwrites refuses below rather than printing a guessed flag.
VERB_OPERATIONS = {
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

# The named exemption list. Every NOT-DOOR site must land on a key here.
# count is the exact number of sites that key may carry; tier is TASK 0220's
# (T1 reaches a prospect, T2 changes provider state a prospect would notice
# later, T3 changes nothing a prospect can observe). reason is the recorded
# one-sentence finding - including, for T2, why the site is a named omission
# rather than a wiring: 0220 may not change what succeeds ("No cap or gate
# change"), and each of these wirings would.
EXEMPTIONS = {
    # ---- T1: glm-a's TASK 0072. 0220 did not touch these sites. ----
    ("batch_activate", "bison.resume_campaign"): {
        "tier": "T1", "count": 1,
        "reason": "glm-a TASK 0072 owns this prospect-facing email site; "
                  "0220 deliberately did not touch it, and this entry is "
                  "how the two lanes avoid colliding on the same lines."},
    ("resume_487", "bison.resume_campaign"): {
        "tier": "T1", "count": 1,
        "reason": "glm-a TASK 0072 owns this prospect-facing email site; "
                  "0220 deliberately did not touch it, and this entry is "
                  "how the two lanes avoid colliding on the same lines."},
    # ---- T2: named omissions and brakes, each with its measured reason. ----
    ("linkedin_activate", "heyreach.activate_campaign"): {
        "tier": "T2", "count": 2,
        "reason": "LINKEDIN_ACTIVATE is facing=True, so the door demands "
                  "per-lead executionguard Authorizations whose "
                  "preconditions live in production work/ state this task "
                  "may not read; the one-shot already fired under the "
                  "2026-09-22 operator authorization and the freeze bars a "
                  "rerun, so an unverifiable wiring would be dead code on a "
                  "spent script."},
    ("bisonfactory", "bison.pause_campaign"): {
        "tier": "T2", "count": 1,
        "reason": "_ensure_stopped IS a brake, and a brake must never "
                  "depend on a door that could refuse it (0210 design, "
                  "BRAKE_EXEMPT)."},
    ("make_481_inert", "bison.stop_lead"): {
        "tier": "T2", "count": 2,
        "reason": "a stop is a brake, and make_481_inert must run with the "
                  "door shut and the brake pulled (0210 design, "
                  "BRAKE_EXEMPT)."},
    # ---- T3: unwired by decision, one sentence each. ----
    ("batch_linkedin_push", "heyreach.create_list"): {
        "tier": "T3", "count": 1,
        "reason": "an empty list bound to no campaign reaches nobody - the "
                  "door's own LINKEDIN_CREATE_LIST argument."},
    ("batch_linkedin_push", "heyreach.create_campaign"): {
        "tier": "T3", "count": 1,
        "reason": "creates in DRAFT and a draft sends nothing; activation "
                  "is separately door'd and allowlisted."},
    ("batch_linkedin_push", "heyreach.set_sequence"): {
        "tier": "T3", "count": 1,
        "reason": "a sequence on a campaign no gated verb may start "
                  "reaches nobody."},
    ("batch_linkedin_reconcile", "heyreach.set_sequence"): {
        "tier": "T3", "count": 1,
        "reason": "reconciliation writes a sequence onto a campaign that "
                  "stays unstarted; unobservable until a gated verb "
                  "fires."},
    ("bisonfactory", "bison.set_limits"): {
        "tier": "T3", "count": 1,
        "reason": "a cap on a campaign that cannot send changes nothing "
                  "observable until a gated activation fires."},
    ("bisonfactory", "bison.set_schedule"): {
        "tier": "T3", "count": 1,
        "reason": "a sending window on a campaign that sends nothing is "
                  "unobservable until a gated activation fires."},
    ("bisonfactory", "bison.ensure_custom_variables"): {
        "tier": "T3", "count": 1,
        "reason": "variables written onto a campaign that cannot send "
                  "reach nobody by themselves."},
    ("bisonfactory", "bison.update_lead"): {
        "tier": "T3", "count": 2,
        "reason": "lead-row bookkeeping at the provider, not delivery; no "
                  "operation is declared for it."},
    ("bisonfactory", "bison.create_lead"): {
        "tier": "T3", "count": 1,
        "reason": "EMAIL_ADD_LEAD is prospect-facing and not in SUPPORTED; "
                  "routing it needs an operator grant TASK-198 recorded as "
                  "not given."},
    ("bisonfactory", "bison.attach_leads"): {
        "tier": "T3", "count": 1,
        "reason": "the EMAIL_ADD_LEAD family again: attaching needs the "
                  "operator grant first, and the factory only attaches to "
                  "a stopped campaign behind its own gate."},
    ("probe_list_staging", "heyreach.create_list"): {
        "tier": "T3", "count": 1,
        "reason": "an unbound empty list; nobody is reachable from it."},
    ("probe_list_staging", "heyreach.add_leads_to_list"): {
        "tier": "T3", "count": 2,
        "reason": "a lead parked in an unbound list is contacted by "
                  "nobody until a separately gated activation fires."},
    ("write_linkedin_lead_variables", "heyreach.add_leads_to_list"): {
        "tier": "T3", "count": 1,
        "reason": "the words are written onto a lead parked in an unbound "
                  "list; nothing renders them until a gated activation "
                  "fires."},
}

INVENTORY_FLOOR = 50  # 58 measured at e84108f5; the floor survives re-wiring

# Kept from the 0210 port so the printed rule matches the brake test's
# accounting labels exactly (DOOR-in-call / DOOR-by-name / WIRED /
# EXEMPT-brake) and the two instruments reconcile line for line.
BRAKE_EXEMPT = {
    ("make_481_inert", "main"),          # bison.stop_lead, twice
    ("bisonfactory", "_ensure_stopped"),  # bison.pause_campaign
}
BRAKE_VERBS = {"pause_campaign", "stop_lead"}


def _iter_python(directory):
    for name in sorted(os.listdir(directory)):
        if name.endswith(".py"):
            yield os.path.join(directory, name)


class WriteSiteModule:
    """One parsed file: its write sites and their door classification.

    Ported from the 0210 brake test's _Module so both instruments apply
    the same three lexical door rules to the same denominator. Divergence
    between the two is a bug in whichever was edited without the other.
    """

    def __init__(self, path):
        self.path = path
        self.stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as handle:
            self.tree = ast.parse(handle.read(), filename=path)
        self.parents = {}
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[id(child)] = parent
        self.door_referenced = set()
        self._collect_door_references()

    def _is_door_call(self, node):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in DOOR_CALL_NAMES
        if isinstance(func, ast.Attribute):
            return func.attr in DOOR_CALL_NAMES
        return False

    def _collect_door_references(self):
        for node in ast.walk(self.tree):
            if not self._is_door_call(node):
                continue
            for arg in list(node.args) + list(node.keywords):
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Name):
                        self.door_referenced.add(sub.id)

    def _ancestors(self, node):
        walk = node
        while True:
            walk = self.parents.get(id(walk))
            if walk is None:
                return
            yield walk

    def _enclosing_functions(self, node):
        return [a for a in self._ancestors(node)
                if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def _names_bound_to(self, node):
        names = {f.name for f in self._enclosing_functions(node)}
        chain = list(self._ancestors(node))
        chain_ids = {id(a) for a in chain}
        for ancestor in chain:
            parent = self.parents.get(id(ancestor))
            if isinstance(parent, ast.Assign) and \
                    isinstance(ancestor, ast.Lambda):
                for target in parent.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        for ancestor in chain:
            if not (isinstance(ancestor, ast.For)
                    and isinstance(ancestor.target, ast.Tuple)):
                continue
            rows = (ancestor.iter.elts
                    if isinstance(ancestor.iter, ast.Tuple)
                    else [ancestor.iter])
            for row in rows:
                slots = row.elts if isinstance(row, ast.Tuple) else [row]
                if len(slots) != len(ancestor.target.elts):
                    continue
                for target, element in zip(ancestor.target.elts, slots):
                    if isinstance(target, ast.Name) and any(
                            id(sub) in chain_ids
                            for sub in ast.walk(element)):
                        names.add(target.id)
        return names

    def _brake_wired(self, node):
        for function in self._enclosing_functions(node):
            for sub in ast.walk(function):
                if isinstance(sub, ast.Call) \
                        and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == "require_released":
                    return True
        return False

    def sites(self):
        """Yield (lineno, provider, verb, rule) for every write site.

        rule is one of DOOR-in-call, DOOR-by-name, WIRED, EXEMPT-brake,
        UNBRACED - the last being a 0210 question, not this check's, and
        still printed so a brake bypass cannot hide inside a door-clean
        inventory. The DOOR question this check asks is: rule startswith
        DOOR.
        """
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or \
                    not isinstance(func.value, ast.Name):
                continue
            provider, verb = func.value.id, func.attr
            if provider == "bison" and verb in BISON_WRITE_VERBS:
                pass
            elif provider == "heyreach" and verb in HEYREACH_WRITE_VERBS:
                pass
            else:
                continue

            if any(self._is_door_call(a) for a in self._ancestors(node)):
                yield node.lineno, provider, verb, "DOOR-in-call"
                continue
            if self._names_bound_to(node) & self.door_referenced:
                yield node.lineno, provider, verb, "DOOR-by-name"
                continue
            if self._brake_wired(node):
                yield node.lineno, provider, verb, "WIRED"
                continue
            enclosing = self._enclosing_functions(node)
            function = enclosing[0].name if enclosing else "<module>"
            if (self.stem, function) in BRAKE_EXEMPT:
                if verb not in BRAKE_VERBS:
                    # The 0210 guard, ported: the exempt list may only
                    # ever hold stops, and a non-brake verb on it is a
                    # violation, not an exemption.
                    yield node.lineno, provider, verb, "UNBRACED"
                    continue
                yield node.lineno, provider, verb, "EXEMPT-brake"
                continue
            yield node.lineno, provider, verb, "UNBRACED"


def collect(root):
    """Walk src/ and scripts/ under root.

    Returns (records, refusals). A file that cannot be read or parsed
    refuses: it lands in refusals with its error, and main() exits 2.
    records is a list of (stem, lineno, provider, verb, rule).
    """
    records, refusals = [], []
    for directory in (os.path.join(root, "src"),
                      os.path.join(root, "scripts")):
        if not os.path.isdir(directory):
            refusals.append(f"{directory} is not a directory - the walker "
                            f"has nowhere to look")
            continue
        for path in _iter_python(directory):
            try:
                module = WriteSiteModule(path)
                for lineno, provider, verb, rule in module.sites():
                    records.append(
                        (module.stem, lineno, provider, verb, rule))
            except (OSError, SyntaxError, ValueError) as error:
                refusals.append(f"{path}: {error!r}")
    return records, refusals


def _facing_of(provider, verb):
    """('op1,op2', facing_text) for an adapter verb, or None to refuse.

    facing_text is the flag(s) OPERATIONS declares; a verb with two
    candidate operations prints both flags because only the call site
    tells them apart. A constant name that no longer resolves, or an
    OPERATIONS entry that lost its (channel, bool, why) shape, refuses
    rather than printing a guess.
    """
    names = VERB_OPERATIONS.get(provider, {}).get(verb, ())
    if names is None:
        return "none", "none"
    resolved = []
    for name in names:
        if not hasattr(providerwrites, name):
            return None
        value = getattr(providerwrites, name)
        try:
            channel, facing, _why = providerwrites.describe(value)
        except Exception as error:             # noqa: BLE001 - refuse on any
            return None                        # surprise, never guess
        if not isinstance(facing, bool):
            return None
        resolved.append((name, facing))
    flags = "|".join(str(facing) for _name, facing in resolved)
    return ",".join(name for name, _facing in resolved), flags


def _check_tables():
    """Refusals about the verb/facing tables themselves."""
    refusals = []
    shape_bad = [
        f"OPERATIONS[{operation!r}] lost its (channel, facing, why) shape"
        for operation, entry in providerwrites.OPERATIONS.items()
        if not (isinstance(entry, tuple) and len(entry) == 3
                and isinstance(entry[1], bool))
    ]
    refusals.extend(shape_bad)
    for provider, verbs in (("bison", BISON_WRITE_VERBS),
                            ("heyreach", HEYREACH_WRITE_VERBS)):
        table = VERB_OPERATIONS.get(provider)
        if table is None or set(table) != set(verbs):
            missing = sorted(set(verbs) - set(table or ()))
            extra = sorted(set(table or ()) - set(verbs))
            refusals.append(
                f"VERB_OPERATIONS[{provider!r}] does not match the write "
                f"inventory: missing {missing}, extra {extra} - refusing "
                f"rather than printing a guessed facing")
    return refusals


def evaluate(records, refusals):
    """(violations, not_door_counts, exit_code) for a collected tree."""
    violations = []
    counts = {}
    for stem, lineno, provider, verb, rule in records:
        if rule.startswith("DOOR"):
            continue
        if rule == "UNBRACED":
            # Not this check's question (the 0210 brake test owns it), but
            # a brake bypass inside a door-clean inventory must not pass
            # silently either.
            violations.append(
                f"{stem}.py:{lineno} {provider}.{verb} is UNBRACED - "
                f"that is the 0210 brake test's violation and it is "
                f"reported here too")
        key = (stem, f"{provider}.{verb}")
        counts[key] = counts.get(key, 0) + 1

    for key in sorted(counts):
        stem, verb = key
        entry = EXEMPTIONS.get(key)
        if entry is None:
            violations.append(
                f"{stem}.py {verb} ({counts[key]} site(s)) is neither "
                f"through the door nor on the exemption list - THIS IS A "
                f"NEW BYPASS: register it with a tier and a reason, or "
                f"wire it through the door")
        elif counts[key] != entry["count"]:
            violations.append(
                f"{stem}.py {verb}: exemption pins {entry['count']} "
                f"site(s), the tree holds {counts[key]} - a new site "
                f"under an admitted key is a new bypass, and a "
                f"disappearing one retires this entry")
    for key in sorted(EXEMPTIONS):
        if key not in counts:
            violations.append(
                f"stale exemption {key[0]}.py {key[1]} "
                f"({EXEMPTIONS[key]['tier']}): the tree no longer holds "
                f"its sites - if they were wired through the door, retire "
                f"this entry in that same commit")
    if len(records) < INVENTORY_FLOOR:
        violations.append(
            f"only {len(records)} write sites classified, below the "
            f"floor of {INVENTORY_FLOOR} - the verb inventories or the "
            f"door rules rotted")
    code = 2 if refusals else (1 if violations else 0)
    return violations, counts, code


def main(root=None):
    root = root or ROOT
    refusals = _check_tables()
    records, walk_refusals = collect(root)
    refusals.extend(walk_refusals)

    # Facings resolve before anything prints, so a facing that cannot be
    # resolved lands in CONTROL 3 as the refusal it is, not after it.
    facings = {}
    for stem, lineno, provider, verb, rule in records:
        operations, facing = _facing_of(provider, verb)
        if operations is None:
            refusals.append(
                f"{stem}.py:{lineno} {provider}.{verb}: no facing could "
                f"be resolved for the printed inventory")
        facings[(stem, lineno, provider, verb)] = (operations, facing)

    violations, counts, _code = evaluate(records, refusals)

    door = [r for r in records if r[4].startswith("DOOR")]
    in_call = [r for r in records if r[4] == "DOOR-in-call"]
    by_name = [r for r in records if r[4] == "DOOR-by-name"]
    not_door = [r for r in records if not r[4].startswith("DOOR")]
    tiers = {"T1": 0, "T2": 0, "T3": 0}
    for key, seen in counts.items():
        entry = EXEMPTIONS.get(key)
        if entry:
            tiers[entry["tier"]] += seen

    print("CONTROL 1 - denominator")
    print(f"  write sites: {len(records)} "
          f"(floor {INVENTORY_FLOOR})")
    print(f"  through the door: {len(door)} "
          f"({len(in_call)} in-call, {len(by_name)} by-name)")
    print(f"  NOT through the door: {len(not_door)}")
    print("CONTROL 2 - tiers of the not-door sites")
    print(f"  T1 {tiers['T1']}  T2 {tiers['T2']}  T3 {tiers['T3']}"
          f"  (registered sites sum "
          f"{tiers['T1'] + tiers['T2'] + tiers['T3']})")
    print("CONTROL 3 - integrity")
    print(f"  refusals: {len(refusals)} (must be 0)")
    for refusal in refusals:
        print(f"    REFUSED {refusal}")
    print(f"  violations: {len(violations)} (must be 0)")
    for violation in violations:
        print(f"    VIOLATION {violation}")

    print("inventory:")
    for stem, lineno, provider, verb, rule in sorted(
            records, key=lambda r: (r[0], r[1])):
        operations, facing = facings[(stem, lineno, provider, verb)]
        facing_text = facing if operations is not None else "UNKNOWN"
        operations_text = operations if operations is not None else "?"
        if rule.startswith("DOOR"):
            tier = "door"
        else:
            entry = EXEMPTIONS.get((stem, f"{provider}.{verb}"))
            tier = entry["tier"] if entry else "UNREGISTERED"
        print(f"  {stem}.py:{lineno} {provider}.{verb} {rule} "
              f"op={operations_text} facing={facing_text} tier={tier}")

    code = 2 if refusals else (1 if violations else 0)
    if code:
        print(f"EXIT {code} - the inventory does not verify")
    else:
        print("EXIT 0 - the inventory verifies")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
