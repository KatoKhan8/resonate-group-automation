"""Every direct provider write in a factory must be declared.

TASK-198. `providerwrites.SUPPORTED` is read as the complete write surface,
but `bisonfactory` calls eight provider write functions directly, bypassing
`providerwrites.perform`. `heyreachfactory` routes every write through
`perform`. This test fails if a new direct write call appears in either
factory without being declared in the registry below.

The defect this catches: a developer adds `bison.new_verb(...)` to a factory
function. The call reaches the provider without going through `perform`, so
`SUPPORTED` does not name it, `executionguard` does not gate it, and the
audit surface has a hole nobody enumerated. The test fails, the developer
either routes the call through `perform` or adds it to the declared set, and
the surface stays known.

WHAT COUNTS AS A WRITE. The provider modules carry both reads and writes.
This test names the write functions explicitly: anything in
`_PROVIDER_WRITE_FUNCS` is a write, anything else is a read and is not
checked. The set is conservative — it includes every function that mutates
provider state, even staging-only ones like `ensure_custom_variables`.

WHAT COUNTS AS ROUTED. A write call is "routed" if it appears inside a
function or lambda that is passed as the `transport` argument to
`providerwrites.perform`. The test resolves transport arguments through
named functions, lambdas, and factory functions that return closures.
"""
import ast
import os
import unittest


_PROVIDER_WRITE_FUNCS = {
    "bison": frozenset({
        "create_campaign", "set_sequence", "set_limits", "set_schedule",
        "attach_senders", "ensure_custom_variables", "create_lead",
        "attach_leads", "update_lead", "pause_campaign", "resume_campaign",
        "stop_lead",
    }),
    "heyreach": frozenset({
        "set_sequence", "add_leads_to_campaign", "pause_campaign",
        "resume_campaign", "create_campaign", "add_senders",
        "remove_senders", "start_campaign", "add_leads_to_list",
    }),
}

# The declared set of direct (non-`perform`) provider write calls in each
# factory. Every call to a function in `_PROVIDER_WRITE_FUNCS` that does NOT
# appear inside a `providerwrites.perform(...)` transport must be here.
#
# Adding a new direct call to a factory WITHOUT adding it here is the defect
# this test exists to catch, and the test will fail.
_DECLARED_DIRECT_CALLS = {
    "bisonfactory.py": frozenset({
        ("bison", "set_limits"),
        ("bison", "set_schedule"),
        ("bison", "attach_senders"),
        ("bison", "ensure_custom_variables"),
        ("bison", "create_lead"),
        ("bison", "attach_leads"),
        ("bison", "update_lead"),
        ("bison", "pause_campaign"),
    }),
    "heyreachfactory.py": frozenset(),
}

_SRC_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "src")


def _parse(path):
    with open(path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=path)


def _is_perform_call(node):
    """True if `node` is a call to `providerwrites.perform`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Attribute)
            and func.attr == "perform"
            and isinstance(func.value, ast.Name)
            and func.value.id == "providerwrites")


def _collect_write_calls(node, provider_module, write_funcs):
    """Collect all (module, func_name) write calls inside an AST node."""
    found = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id != provider_module:
            continue
        if func.attr in write_funcs:
            found.add((provider_module, func.attr))
    return found


def _find_routed_write_calls(tree, provider_module):
    """Find all provider write calls that are routed through perform.

    Resolves transport arguments through:
    - Lambda nodes passed directly to perform
    - Name references to FunctionDef nodes (all matching names, to handle
      multiple functions with the same name in different scopes)
    - Call nodes whose result is a transport (factory functions)
    """
    write_funcs = _PROVIDER_WRITE_FUNCS.get(provider_module, frozenset())

    # Build a map of function name -> list of FunctionDef nodes.
    # Multiple functions can share a name (e.g. _transport in different scopes).
    func_defs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_defs.setdefault(node.name, []).append(node)

    routed = set()

    def _mark_routed(ast_node):
        """Collect all write calls inside an AST node and mark them routed."""
        for write in _collect_write_calls(ast_node, provider_module, write_funcs):
            routed.add(write)

    # Find all perform calls and resolve their transport arguments.
    for node in ast.walk(tree):
        if not _is_perform_call(node):
            continue
        # Look at all arguments for transport sources.
        all_args = list(node.args)
        for kw in node.keywords:
            all_args.append(kw.value)

        for arg in all_args:
            # Lambda directly in the perform call.
            if isinstance(arg, ast.Lambda):
                _mark_routed(arg)

            # Name reference to a function definition.
            # Check ALL functions with that name (handles scope collisions).
            elif isinstance(arg, ast.Name) and arg.id in func_defs:
                for fdef in func_defs[arg.id]:
                    _mark_routed(fdef)

            # Call node: the result of a factory function is the transport.
            # Find the function being called and collect writes inside it,
            # including any inner functions it defines.
            elif isinstance(arg, ast.Call):
                callee = arg.func
                if isinstance(callee, ast.Name) and callee.id in func_defs:
                    for fdef in func_defs[callee.id]:
                        _mark_routed(fdef)

    return routed


def _find_all_write_calls(tree, provider_module):
    """Find ALL provider write calls in the file."""
    write_funcs = _PROVIDER_WRITE_FUNCS.get(provider_module, frozenset())
    return _collect_write_calls(tree, provider_module, write_funcs)


def _find_direct_write_calls(tree, provider_module):
    """Find write calls that are NOT routed through perform.

    Returns the set of (module, func_name) tuples for direct calls.
    """
    all_writes = _find_all_write_calls(tree, provider_module)
    routed = _find_routed_write_calls(tree, provider_module)
    return all_writes - routed


class WriteSurfaceEnumeration(unittest.TestCase):
    """Every direct provider write in a factory is declared."""

    def test_bisonfactory_direct_calls_are_declared(self):
        """Every bison write call that bypasses perform is in the registry."""
        path = os.path.join(_SRC_DIR, "bisonfactory.py")
        tree = _parse(path)
        routed = _find_routed_write_calls(tree, "bison")
        direct = _find_direct_write_calls(tree, "bison")

        declared = _DECLARED_DIRECT_CALLS["bisonfactory.py"]
        undeclared = direct - declared

        self.assertFalse(
            undeclared,
            f"bisonfactory.py has {len(undeclared)} direct provider write "
            f"call(s) not in the declared registry: "
            f"{sorted(f'{m}.{f}' for m, f in undeclared)}. "
            f"Either route them through providerwrites.perform or add them "
            f"to _DECLARED_DIRECT_CALLS in this test file. "
            f"Routed through perform: "
            f"{sorted(f'{m}.{f}' for m, f in routed)}")

    def test_heyreachfactory_has_no_undeclared_direct_calls(self):
        """HeyReach routes everything through perform; the declared set is empty."""
        path = os.path.join(_SRC_DIR, "heyreachfactory.py")
        tree = _parse(path)
        routed = _find_routed_write_calls(tree, "heyreach")
        direct = _find_direct_write_calls(tree, "heyreach")

        declared = _DECLARED_DIRECT_CALLS["heyreachfactory.py"]
        undeclared = direct - declared

        self.assertFalse(
            undeclared,
            f"heyreachfactory.py has {len(undeclared)} direct provider write "
            f"call(s) not in the declared registry: "
            f"{sorted(f'{m}.{f}' for m, f in undeclared)}. "
            f"Either route them through providerwrites.perform or add them "
            f"to _DECLARED_DIRECT_CALLS in this test file. "
            f"Routed through perform: "
            f"{sorted(f'{m}.{f}' for m, f in routed)}")

    def test_declared_registry_is_not_stale(self):
        """Every entry in the declared registry actually appears in the source.

        The inverse check: if a direct call is removed from a factory (e.g.
        routed through perform), the registry entry becomes stale and should
        be removed. A stale registry is as misleading as an incomplete one.
        """
        for filename, declared in _DECLARED_DIRECT_CALLS.items():
            path = os.path.join(_SRC_DIR, filename)
            tree = _parse(path)
            provider = "bison" if "bison" in filename else "heyreach"
            direct = _find_direct_write_calls(tree, provider)
            stale = declared - direct
            self.assertFalse(
                stale,
                f"{filename} registry has {len(stale)} stale entries that no "
                f"longer appear as direct calls: "
                f"{sorted(f'{m}.{f}' for m, f in stale)}. "
                f"Remove them from _DECLARED_DIRECT_CALLS")

    def test_heyreachfactory_routes_every_write_through_perform(self):
        """The HeyReach factory has zero direct write calls.

        This is the property that distinguishes the two factories and the
        reason the bisonfactory's direct calls are the defect. Every HeyReach
        write goes through providerwrites.perform; every EmailBison write
        does not have to.
        """
        path = os.path.join(_SRC_DIR, "heyreachfactory.py")
        tree = _parse(path)
        routed = _find_routed_write_calls(tree, "heyreach")
        direct = _find_direct_write_calls(tree, "heyreach")

        self.assertEqual(
            direct, set(),
            f"heyreachfactory.py has {len(direct)} direct write call(s): "
            f"{sorted(f'{m}.{f}' for m, f in direct)}. "
            f"Expected zero; all HeyReach writes should go through "
            f"providerwrites.perform")

        self.assertTrue(
            routed,
            "heyreachfactory.py should have at least one routed write call")


if __name__ == "__main__":
    unittest.main()
