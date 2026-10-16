#!/usr/bin/env python3
"""No path reaches a transport without passing the STOP-SENDING brake.

PROPERTY UNDER TEST (the third of four):

    No bypass. pilotcaps/0160 found `bison.add_lead`'s seal bypassable
    through `_ensure_leads`. Prove by call graph that no path reaches a
    transport without passing this check, against the 58-path denominator
    already measured. If a path exists that does not, name it - that is
    the finding and it outranks shipping the switch.

This is the call-graph proof. It walks every module under `src/` and
`scripts/`, finds every DIRECT mutating provider call - `bison.<verb>(...)`
or `heyreach.<verb>(...)` where <verb> is in the write inventories below -
and requires each site to be one of exactly three things:

    DOOR      the verb is the transport of a write door. Detected three
              ways, all lexical:
              (a) the call sits inside a `perform` / `_perform` /
                  `stage_lead` call's arguments - the `transport=lambda:
                  bison.pause_campaign(...)` shape;
              (b) the function enclosing the verb is passed to a door
                  call in the same file, by name or by call - the
                  `def _create(p): bison.create_campaign(...)` then
                  `perform(..., transport=_create)` shape, and the
                  `def _transport_for(row)` factory shape;
              (c) the verb sits in a lambda or tuple element bound to a
                  name that a door call's arguments reference - the
                  `transport = lambda _p: heyreach.pause_campaign(...)`
                  then `perform(..., transport=transport)` shape, and
                  the resume tuple in `orchestrator._perform_resume`.
              The door checks the brake in `_perform` section 2c,
              immediately before the transport, pinned behaviorally by
              test_the_stop_sending_brake_refuses_the_transport_immediately.

    WIRED     the function enclosing the verb consults
              `haltfile.require_released()` - the eight bisonfactory
              sites and the twelve script sites TASK 0210 wired. This is
              FUNCTION-GRANULARITY: it proves a consult exists in the
              scope that performs the verb, not that it is the previous
              line. Immediacy is pinned separately and behaviorally, at
              the door and in bisonfactory, because no AST rule can pin
              "the night before" without becoming a rewrite of the code
              it guards.

    EXEMPT    a brake itself. `make_481_inert.main` (bison.stop_lead,
              twice) and `bisonfactory._ensure_stopped`
              (bison.pause_campaign) are stops, and pulling STOP-SENDING
              must never disable another brake. The exemption is pinned
              to (file, function) pairs AND to brake VERBS: an exempt
              site whose verb is not a stop fails this test, so the list
              cannot quietly grow a sending verb.

The door's four BRAKE_OPERATIONS are the four verbs that pass the door
WITHOUT consulting the file, and they are pinned equal to
`providerwrites.REPEATABLE` - the set the estate already pins to exactly
the four stops. If either grows without the other, a verb becomes
repeatable-but-brakeable or brake-exempt-but-not-repeatable, and both of
those are decisions nobody has made.

WHY STRUCTURAL, NOT LINE NUMBERS. The wiring moved every line after
itself; a line-number pin would fail on the next unrelated edit. This
test reads the call graph the way a reader must: what function holds the
verb, and what stands between it and the transport.

WHAT IT DOES NOT CATCH, named: a verb reached through `getattr` strings,
a verb called through an alias (`from src.providers.bison import
create_lead`), and a NEW mutating verb added to the adapters but not to
the inventories below. The inventories are the denominator, and the
denominator was measured before the wiring (TASK 0210's analyzer,
58 write paths) and re-measured after it; adding a mutating verb to
either adapter without adding it here is the one way to walk past this
guard, so the inventories carry the verbs that appear nowhere in the
tree yet (start_campaign, add_leads_to_campaign, resume_campaign on
heyreach) rather than only the ones that do.

Born-red at HEAD (pre-0210): ImportError on `src.haltfile`. The mutation
proof re-derives the true born-red: with `haltfile` present and the
wiring byte-reverted, this module fails naming all twenty unwired sites.
"""
import ast
import os
import unittest

from src import haltfile, providerwrites

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DOOR_CALL_NAMES = {"perform", "_perform", "stage_lead"}

# The write inventory: every adapter verb that changes provider state.
# Deliberately a SUPERSET of the verbs that appear in the tree today.
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

# A site here is a brake, and only a brake verb may live here.
BRAKE_EXEMPT = {
    ("make_481_inert", "main"),          # bison.stop_lead, twice
    ("bisonfactory", "_ensure_stopped"),  # bison.pause_campaign
}
BRAKE_VERBS = {"pause_campaign", "stop_lead"}


def _iter_python(directory):
    for name in sorted(os.listdir(directory)):
        if name.endswith(".py"):
            yield os.path.join(directory, name)


class _Module:
    """One parsed file: its sites, its door calls, its name flows."""

    def __init__(self, path):
        self.path = path
        self.stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as handle:
            self.tree = ast.parse(handle.read(), filename=path)
        self.parents = {}
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[id(child)] = parent

        # Names referenced anywhere inside a door call's arguments.
        self.door_referenced = set()
        # (file-relative site, rule) classifications, filled by classify().
        self.sites = []
        self._collect_door_references()

    # ------------------------------------------------------------ helpers
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
        """Every name the site's execution flows through:

        - the functions enclosing it (called or not, the verb only runs
          when something invokes them, and rule (b) asks whether that
          something is a door);
        - a lambda's Assign target (`transport = lambda: <verb>`);
        - a For-loop's tuple slot. Two shapes: a flat iter tuple
          (`for a, b in (x, lambda: <verb>)`) and a tuple of ROW tuples
          (`for chan, key, op, transport, ... in ((..., lambda: <verb>,
          ...), (...))` - orchestrator's resume table). In both, the
          slot is found by asking which iter element the site's ancestor
          chain passes through.
        """
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

    def _wired(self, node):
        """A `require_released` consult in ANY function enclosing the verb -
        the verb's own scope, or the scope that drives it. Checking only
        the innermost would miss a verb in a helper whose caller holds the
        consult, and that helper IS on the path the consult guards."""
        for function in self._enclosing_functions(node):
            for sub in ast.walk(function):
                if isinstance(sub, ast.Call) \
                        and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == "require_released":
                    return True
        return False

    # ------------------------------------------------------------ classify
    def classify(self):
        """(violations, inventory) for this file. Inventory lines carry
        file:line, the verb, and the rule that covered it."""
        violations, inventory = [], []
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

            where = f"{self.stem}.py:{node.lineno}"
            if any(self._is_door_call(a) for a in self._ancestors(node)):
                inventory.append(f"{where} {provider}.{verb} DOOR-in-call")
                continue
            if self._names_bound_to(node) & self.door_referenced:
                inventory.append(f"{where} {provider}.{verb} DOOR-by-name")
                continue
            if self._wired(node):
                inventory.append(f"{where} {provider}.{verb} WIRED")
                continue
            enclosing = self._enclosing_functions(node)
            function = enclosing[0].name if enclosing else "<module>"
            if (self.stem, function) in BRAKE_EXEMPT:
                if verb not in BRAKE_VERBS:
                    violations.append(
                        f"{where} {provider}.{verb} is on the BRAKE_EXEMPT "
                        f"list ({self.stem}.{function}) but is not a brake "
                        f"verb; the list may only ever hold stops")
                    continue
                inventory.append(f"{where} {provider}.{verb} EXEMPT-brake")
                continue
            violations.append(
                f"{where} {provider}.{verb} in {self.stem}.{function} "
                f"reaches a transport without the STOP-SENDING brake: not "
                f"a door transport, not wired, not exempt. THIS IS A "
                f"BYPASS - name it in the TASK 0210 lane entry, because "
                f"the finding outranks the switch")
        return violations, inventory


class NoPathReachesATransportWithoutTheBrake(unittest.TestCase):

    def test_every_mutating_provider_call_is_door_wired_or_a_brake(self):
        violations, inventory = [], []
        for directory in (os.path.join(ROOT, "src"),
                          os.path.join(ROOT, "scripts")):
            for path in _iter_python(directory):
                module_violations, module_inventory = _Module(path).classify()
                violations.extend(module_violations)
                inventory.extend(module_inventory)

        # The inventory is part of the assertion's failure message so a
        # red run shows the whole call graph, not one site at a time.
        self.assertEqual(
            violations, [],
            "paths that reach a transport without the brake:\n  "
            + "\n  ".join(violations)
            + "\n\nthe classified inventory:\n  "
            + "\n  ".join(inventory))

        # The proof has to cover ground: the 0210 analyzer measured 58
        # write paths through this tree. A structural test that
        # classified nothing proves nothing, and an inventory that lost
        # the door sites would pass while guarding air.
        self.assertGreaterEqual(
            len(inventory), 40,
            f"only {len(inventory)} mutating sites classified - the "
            f"denominator measured 58 write paths; if this dropped, the "
            f"verb inventories or the door rules rotted:\n  "
            + "\n  ".join(inventory))
        # Name-level positive verification, because an inventory that
        # silently stopped visiting a file would still be >= 40: the
        # (file, verb) pairs that carry each RULE must be present. Line
        # numbers are deliberately not pinned - they rot on every edit.
        present = set()
        for line in inventory:
            parts = line.split()
            if len(parts) >= 3:
                present.add((parts[0].split(".py:")[0], parts[1], parts[2]))
        for stem, verb, rule in (
                ("bisonfactory", "bison.set_limits", "WIRED"),
                ("bisonfactory", "bison.attach_leads", "WIRED"),
                # TASK 0395: was WIRED; the site now passes the door.
                ("resume_487", "bison.resume_campaign",
                 "DOOR-in-call"),
                ("batch_linkedin_push", "heyreach.create_campaign", "WIRED"),
                ("orchestrator", "bison.resume_campaign", "DOOR-by-name"),
                ("make_481_inert", "bison.stop_lead", "EXEMPT-brake"),
        ):
            self.assertIn(
                (stem, verb, rule), present,
                f"the inventory lost {stem} {verb} as {rule} - a file the "
                f"walker stopped visiting, or a rule that stopped "
                f"matching:\n  " + "\n  ".join(inventory))

    def test_the_door_verb_set_is_the_repeatable_set(self):
        self.assertEqual(
            set(haltfile.BRAKE_OPERATIONS), set(providerwrites.REPEATABLE),
            "BRAKE_OPERATIONS (verbs the door lets through with the brake "
            "pulled) and REPEATABLE (verbs whose repetition IS the point) "
            "are the same four stops by design. If one grew without the "
            "other, a verb became repeatable-but-brakeable or "
            "brake-exempt-but-not-repeatable, and both are decisions "
            "nobody has made")
        for operation in haltfile.BRAKE_OPERATIONS:
            self.assertIn(
                operation, providerwrites.SUPPORTED,
                f"{operation} is brake-exempt at the door but not "
                f"SUPPORTED; an exemption for a verb the door refuses "
                f"anyway is a typo, not a policy")


if __name__ == "__main__":
    unittest.main()
