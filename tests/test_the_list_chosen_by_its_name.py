"""The list chosen by its name, in a workspace that is not only ours.

TASK-0250. `pilotcaps/0244` found this on the way to something else and filed
it rather than working it:

    scripts/batch_linkedin_push.py
      :546-550  existing_lists = {str(r.get("name")): r.get("id")
                                  for r in heyreach.lists()}
      :584      list_id = existing_lists.get(name)
      :588      if not list_id:  ->  heyreach.create_list(name)

`heyreach.lists()` returns EVERY list in the shared HeyReach workspace. The
reuse branch at `:584` binds one by FREE-TEXT NAME. CLAUDE.md already carries
that lesson about EmailBison campaigns 327/328/352, where the operator's own
first name in a campaign title was read as ownership: a name is a hint, never
a measurement. This is the same mistake one layer down, in a list name.

WHY A SECOND MODULE AND NOT A CHANGE TO THE FIRST.
`test_the_door_does_not_ask_whose_campaign_it_is` (TASK-0241, recovered and
committed by 0244 at `2ffc0ecf9`) answers a different question and answers it
well: WHICH call sites reach a provider write without passing `perform`. Its
`direct_sites` keys on `(file, enclosing function, adapter verb)` and never on
an argument - deliberately, because a line number drifts under an unrelated
edit. 0244 measured the cost of that choice: three plants that replaced the
destination at `:588`, `:599` and `:603` with a not-ours value each produced an
EMPTY kill-set, 19 tests OK in all three cases. Blind by construction, not by
accident.

So this module keys on exactly the thing that one cannot see: the DESTINATION
an argument resolves to. The two together are the pair - one watches the
boundary, one watches the value crossing it. Neither replaces the other, and
the reader below reuses the first module's `write_capable` and `tree_sources`
rather than growing a second representation of "which adapter function writes".

WHAT THIS MODULE IS NOT. It adds no gate, no guard, no refusal and no cap. It
does not import or call `require_resonate_os_campaign`, and it changes nothing
under `src/` or `scripts/`. The gate change is written down as a PROPOSAL in
`LANE-pilotcaps.md` under TASK-0250, on the same reasoning that kept
`confirm_email_touches` out of a lane and that 0241 applied to this exact file:
an ownership refusal on the canary's own LinkedIn channel is the operator's
call, and a false refusal stops the canary.

NO NETWORK. Every assertion below either parses source with `ast` or evaluates
an expression extracted from that source against rows this file constructs. No
provider, Apify or Slack call; nothing opens a socket; HeyReach list 565765 and
EmailBison 327/328/352/417/418 are neither read nor written. `src/providers/*`
is parsed by `write_capable` as data and is not read as prose, which is the
boundary 0244 drew and kept.
"""
import ast
import os
import unittest

from tests.test_the_door_does_not_ask_whose_campaign_it_is import (
    _adapters, _callee, direct_sites, perform_sinks, tree_sources,
    write_capable)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The file this module is about.
TARGET = "scripts/batch_linkedin_push.py"

#: The only thing in that file that says a name is ours. It is a literal
#: prefix of an f-string template and it is all the evidence the file has -
#: which is the finding, not the instrument's limitation.
OURS_NAME_PREFIX = "RESONATE PRODUCTIVE LI B1 SEAT "

#: Root provenance tokens that are an acceptable destination for a direct
#: adapter write in `main`. Anything else is a violation, INCLUDING an
#: unresolvable expression: a destination whose origin cannot be established
#: offline is UNKNOWN, and UNKNOWN is never promoted to ours.
#:
#:   OURS_NAME        resolves to the f-string whose literal prefix is
#:                    OURS_NAME_PREFIX. The weakest kind of ours there is, and
#:                    named as such.
#:   CREATED_HERE:    resolves to a `heyreach.create_*` call in the same
#:                    function - the id did not exist before this run, so
#:                    there is nothing for an ownership guard to classify.
#:                    This is the argument 0238 accepted, and it does hold
#:                    for the two it was offered for.
#:   PLAN_LOCAL:      a value built in this process from the local plan or
#:                    from a local helper - a seat id off `plan.items()`, the
#:                    sequence graph off `standard_graph()`. Carries no
#:                    provider id of its own.
#:   SELECTED_FROM:   the finding. A value pulled out of a mapping that was
#:                    built from a provider listing, keyed by a name. Allowed
#:                    ONLY where NAME_KEYED_DESTINATIONS records it, so it
#:                    cannot grow a second site in silence.
ALLOWED_ROOT_PREFIXES = ("OURS_NAME", "CREATED_HERE:", "PLAN_LOCAL:")

#: Every direct adapter-write destination in the tree that resolves, even in
#: part, to a value selected out of a provider listing by a free-text key.
#: Keyed by (file, enclosing function, verb, argument source) - the argument
#: IS the key here, which is the whole point of this module.
#:
#: Compared BY SET, both directions. A second name-keyed destination makes
#: this red naming the site; keying the existing one on an id makes it red
#: too, so the record cannot quietly outlive the code.
NAME_KEYED_DESTINATIONS = {
    # `list_id` at `:599` is assigned twice in `main` and this reader unions
    # both branches rather than guessing which one ran: `create_list(name)`
    # on the create branch, `existing_lists.get(name)` on the reuse branch.
    # The reuse branch is the unowned one.
    (TARGET, "main", "heyreach.create_campaign", "list_id"),
}


# --------------------------------------------------------------- the readers
def _func(tree, name):
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return node
    return None


def selector(source=None, func="main", node=None):
    """Every name-keyed mapping built in `func`, and every selection off one.

    `{"builds": [...], "selects": [...]}`. A build is a dict comprehension
    assigned to a local; a select is `<that local>.get(...)`. Both carry the
    unparsed source of their key expression, so the assertions below quote the
    file rather than a paraphrase of it.

    Either `source` + `func`, or an already-parsed function `node` - the
    reader below has the node in hand and re-parsing per call site turned a
    linear walk into a quadratic one.
    """
    if node is None:
        node = _func(ast.parse(source, filename=func), func)
    builds = []
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Assign)
                and isinstance(sub.value, ast.DictComp)):
            continue
        comp = sub.value
        builds.append({
            "lineno": sub.lineno,
            "target": ast.unparse(sub.targets[0]),
            "key": ast.unparse(comp.key),
            "value": ast.unparse(comp.value),
            "iter": ast.unparse(comp.generators[0].iter),
            "comp": ast.unparse(comp),
        })
    targets = {b["target"] for b in builds}
    selects = []
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "get"
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id in targets):
            continue
        selects.append({
            "lineno": sub.lineno,
            "mapping": sub.func.value.id,
            "key_expr": ast.unparse(sub.args[0]) if sub.args else None,
            "has_default": len(sub.args) > 1,
            "src": ast.unparse(sub),
        })
    return {"builds": builds, "selects": selects}


def _bindings(node):
    """local name -> every expression ever assigned to it inside `node`.

    Branch-INSENSITIVE and deliberately so. `list_id` is assigned on both
    arms of the reuse `if`, and a reader that picked one arm would be
    choosing which half of the defect to look at.
    """
    env = {}

    def bind(target, value):
        if isinstance(target, ast.Name):
            env.setdefault(target.id, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                bind(element, value)

    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                bind(target, sub.value)
        elif (isinstance(sub, (ast.AnnAssign, ast.AugAssign))
                and sub.value is not None):
            bind(sub.target, sub.value)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            bind(sub.target, ("LOOP", sub.iter))
        elif isinstance(sub, ast.withitem) and sub.optional_vars is not None:
            bind(sub.optional_vars, sub.context_expr)
    return env


def roots(expr, env, mappings=(), seen=None, depth=0):
    """Resolve an expression to its set of provenance root tokens.

    `mappings` names the locals that hold a provider listing keyed by a
    free-text key; a `.get` off one of those is reported as SELECTED_FROM
    rather than followed, because that is exactly the step where ownership
    stops being knowable.

    Every branch that cannot resolve returns an UNKNOWN token. None of them
    returns the empty set, and none falls back to a pass.
    """
    if seen is None:
        seen = frozenset()
    if depth > 32:
        return {"UNKNOWN:depth"}
    if isinstance(expr, tuple) and expr and expr[0] == "LOOP":
        return {"PLAN_LOCAL:iter(" + ast.unparse(expr[1]) + ")"}
    if isinstance(expr, ast.Constant):
        value = expr.value
        if isinstance(value, str):
            if value.startswith(OURS_NAME_PREFIX):
                return {"OURS_NAME"}
            return {"LITERAL_STR:" + repr(value)}
        if isinstance(value, bool):
            return {"LITERAL_OTHER:" + repr(value)}
        if isinstance(value, (int, float)):
            return {"LITERAL_NUM:" + repr(value)}
        return {"LITERAL_OTHER:" + repr(value)}
    if isinstance(expr, ast.JoinedStr):
        lead = ""
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                lead += part.value
            else:
                break
        if lead.startswith(OURS_NAME_PREFIX):
            return {"OURS_NAME"}
        return {"FSTRING:" + ast.unparse(expr)}
    if isinstance(expr, ast.Subscript):
        # `name = f"..."[:50]` - the slice does not change where it came from.
        return roots(expr.value, env, mappings, seen, depth + 1)
    if isinstance(expr, ast.Name):
        if expr.id in seen:
            return {"UNKNOWN:cycle(" + expr.id + ")"}
        if expr.id not in env:
            return {"UNKNOWN:unbound(" + expr.id + ")"}
        out = set()
        for value in env[expr.id]:
            out |= roots(value, env, mappings, seen | {expr.id}, depth + 1)
        return out or {"UNKNOWN:empty(" + expr.id + ")"}
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        out = set()
        for element in expr.elts:
            out |= roots(element, env, mappings, seen, depth + 1)
        return out or {"UNKNOWN:empty_sequence"}
    if isinstance(expr, ast.Call):
        callee = _callee(expr) or ""
        if (isinstance(expr.func, ast.Attribute) and expr.func.attr == "get"
                and isinstance(expr.func.value, ast.Name)):
            base = expr.func.value.id
            if base in mappings:
                key = ast.unparse(expr.args[0]) if expr.args else "?"
                return {"SELECTED_FROM:" + base + "[" + key + "]"}
            return roots(expr.func.value, env, mappings, seen, depth + 1)
        if isinstance(expr.func, ast.Attribute) and expr.func.attr == "get":
            return roots(expr.func.value, env, mappings, seen, depth + 1)
        head = callee.split(".")[0]
        if head in ("heyreach", "bison") and expr.func.attr.startswith(
                "create"):
            return {"CREATED_HERE:" + callee}
        if callee in ("int", "str", "float"):
            if not expr.args:
                return {"UNKNOWN:call(" + callee + ")"}
            return roots(expr.args[0], env, mappings, seen, depth + 1)
        if callee and "." not in callee:
            return {"PLAN_LOCAL:call(" + callee + ")"}
        return {"UNKNOWN:call(" + (callee or "?") + ")"}
    if isinstance(expr, ast.Attribute):
        return roots(expr.value, env, mappings, seen, depth + 1)
    return {"UNKNOWN:" + type(expr).__name__}


def write_destinations(sources, capable, only=None):
    """Every DIRECT adapter-write call site, with each argument resolved.

    `{(rel, func, verb, arg_src): frozenset(roots)}`.

    Two questions this reader deliberately does not answer itself, because
    `test_the_door_does_not_ask_whose_campaign_it_is` already owns them and a
    second representation is how two readers drift:

      WHICH ADAPTER FUNCTIONS WRITE - `write_capable`, the reader that knows
      HeyReach answers `/list/GetAll` with a POST, so `heyreach.lists` at
      `:548` is a READ and is not reported while `create_list` is.

      WHICH CALL SITES ARE DIRECT - `direct_sites`, which resolves a callable
      laundered into `providerwrites.perform` as a named local def or an
      inline lambda. That is what keeps `:444`
      `heyreach.add_leads_to_list(payload["listId"], [_lead])` out of this
      set: it is inside the lambda handed to `liststaging.stage_lead`, and it
      is the one call in the push script that DOES go through the door. The
      first version of this reader reported it, which is how the composition
      got measured rather than assumed.

    What is new here, and the only new thing, is the ARGUMENT as part of the
    key and the provenance of what it resolves to.
    """
    direct = direct_sites(sources, capable, perform_sinks(sources))
    out = {}
    for rel, source in sorted(sources.items()):
        if only is not None and rel not in only:
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue
        spans = [(node.lineno, node.end_lineno, node.name, node)
                 for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        cache = {}
        for sub in ast.walk(tree):
            if not isinstance(sub, ast.Call):
                continue
            callee = _callee(sub) or ""
            if "." not in callee:
                continue
            best = None
            for start, end, name, node in spans:
                if start <= sub.lineno <= end and (best is None
                                                   or start > best[0]):
                    best = (start, name, node)
            func = best[1] if best else "<module>"
            if (rel, func, callee) not in direct:
                continue
            if best is None:
                continue
            if func not in cache:
                cache[func] = (_bindings(best[2]),
                               {b["target"] for b in
                                selector(node=best[2])["builds"]})
            env, mappings = cache[func]
            for arg in sub.args:
                key = (rel, func, callee, ast.unparse(arg))
                out[key] = (frozenset(roots(arg, env, mappings))
                            | frozenset(out.get(key, ())))
    return out


def violations(destinations, recorded=NAME_KEYED_DESTINATIONS):
    """Destinations whose roots are not all acceptable.

    A root is acceptable if it starts with one of `ALLOWED_ROOT_PREFIXES`, or
    if it is a `SELECTED_FROM:` at a site `recorded` already names. Everything
    else - a not-ours string literal, a bare numeric id, an unresolvable
    expression - is returned. Returns `{key: sorted(bad roots)}`.
    """
    bad = {}
    for key, found in sorted(destinations.items()):
        site = (key[0], key[1], key[2], key[3])
        offending = []
        for root in sorted(found):
            if root.startswith(ALLOWED_ROOT_PREFIXES):
                continue
            if root.startswith("SELECTED_FROM:") and site in recorded:
                continue
            offending.append(root)
        if offending:
            bad[key] = offending
    return bad


def name_selected_locals(source, func="main"):
    """The locals in `func` that take a value out of a name-keyed mapping."""
    tree = ast.parse(source, filename=func)
    node = _func(tree, func)
    mappings = {b["target"] for b in selector(node=node)["builds"]}
    out = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign):
            continue
        for inner in ast.walk(sub.value):
            if (isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "get"
                    and isinstance(inner.func.value, ast.Name)
                    and inner.func.value.id in mappings):
                for target in sub.targets:
                    if isinstance(target, ast.Name):
                        out.add(target.id)
    return out


def reach(source, capable, seeds, func="main", adapters=("heyreach", "bison")):
    """Which adapter WRITES in this file receive a seeded value.

    `{"all": {(func, verb, lineno)}, "reached": {...}, "stopped": [...]}`.

    Forward taint, intraprocedural with one interprocedural step per call
    edge inside the same file, by ARGUMENT POSITION. A call whose actual
    argument is tainted taints the corresponding parameter of the callee.

    `stopped` is the part that makes this an instrument rather than a claim.
    Where the flow leaves this file - into another module, or into a callback
    whose caller supplies the body - the reader records WHERE it stopped
    instead of returning a clean set. A reachability answer built on an
    unrecorded stop is the shape `C4` of TASK-0250 refuses.
    """
    tree = ast.parse(source, filename=func)
    funcs = {node.name: node for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    everything, reached, stopped = set(), set(), []

    def is_write(callee):
        if not callee or "." not in callee:
            return False
        head, verb = callee.split(".", 1)
        return head in adapters and verb in capable.get(head, ())

    def names_in(node):
        return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}

    def walk(fname, tainted, path, seen):
        node = funcs.get(fname)
        if node is None or (fname, frozenset(tainted)) in seen:
            return
        seen.add((fname, frozenset(tainted)))
        local = set(tainted)
        changed = True
        while changed:                       # transitive local assignment
            changed = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assign):
                    continue
                if not names_in(sub.value) & local:
                    continue
                for target in sub.targets:
                    for leaf in ast.walk(target):
                        if (isinstance(leaf, ast.Name)
                                and leaf.id not in local):
                            local.add(leaf.id)
                            changed = True
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            callee = _callee(sub)
            args = list(sub.args) + [kw.value for kw in sub.keywords]
            refs = set()
            for arg in args:
                refs |= names_in(arg)
            if is_write(callee):
                everything.add((fname, callee, sub.lineno))
                if refs & local:
                    reached.add((fname, callee, sub.lineno))
                continue
            if not (refs & local):
                continue
            if callee in funcs:
                params = [a.arg for a in funcs[callee].args.args]
                forward = set()
                for index, arg in enumerate(sub.args):
                    if names_in(arg) & local and index < len(params):
                        forward.add(params[index])
                for kw in sub.keywords:
                    if names_in(kw.value) & local and kw.arg:
                        forward.add(kw.arg)
                if forward:
                    walk(callee, forward, path + [fname], seen)
            elif callee and "." in callee:
                stopped.append({"in": fname, "call": callee,
                                "lineno": sub.lineno,
                                "via": sorted(refs & local),
                                "why": "call leaves this file"})
    # The whole denominator, including writes the taint never reaches.
    # Attributed by INNERMOST enclosing def, the same rule `direct_sites`
    # uses, so a nested def is not charged to its parent as well.
    spans = [(node.lineno, node.end_lineno, name)
             for name, node in funcs.items()]
    for sub in ast.walk(tree):
        if not (isinstance(sub, ast.Call) and is_write(_callee(sub))):
            continue
        best = None
        for start, end, name in spans:
            if start <= sub.lineno <= end and (best is None
                                               or start > best[0]):
                best = (start, name)
        everything.add((best[1] if best else "<module>",
                        _callee(sub), sub.lineno))
    walk(func, set(seeds), [], set())
    return {"all": everything, "reached": reached, "stopped": stopped}


# ------------------------------------------------------------- the fixtures
#: A two-function fake adapter: one function reaches a mutating request, one
#: does not. Used to show the write reader has both states rather than
#: asserting that it does.
FAKE_ADAPTER = '''
def _read_post(path, body):
    return request("POST", path, body)


def _write(path, params):
    return request("PUT", path, params)


def create_list(name):
    return _write("/list/Create", {"name": name})


def lists():
    return _read_post("/list/GetAll", {})
'''

#: A caller whose destination is a not-ours string literal.
FAKE_CALLER_NOT_OURS = '''
import heyreach


def main():
    heyreach.create_list("PRODUCTIVE - JELENA - NOT OURS")
    return 0
'''

#: The same caller with an ours-shaped name.
FAKE_CALLER_OURS = '''
import heyreach


def main():
    name = f"RESONATE PRODUCTIVE LI B1 SEAT {7}"[:50]
    heyreach.create_list(name)
    return 0
'''

#: A destination this reader cannot resolve offline at all.
FAKE_CALLER_UNRESOLVABLE = '''
import heyreach
import os


def main():
    heyreach.create_list(os.environ["SOME_NAME"])
    return 0
'''


def _fake_tree(caller_source):
    return {"src/providers/heyreach.py": FAKE_ADAPTER,
            "scripts/fake_caller.py": caller_source}


def _fake_capable():
    return {"heyreach": write_capable(FAKE_ADAPTER, "fake-heyreach")}


# ----------------------------------------------------------- the assertions
class TheSelectorIsKeyedOnAFreeTextName(unittest.TestCase):
    """What `:546-550` builds and what `:584` takes out of it, from bytes."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, TARGET), encoding="utf-8") as handle:
            cls.source = handle.read()
        cls.found = selector(cls.source)

    def test_exactly_one_name_keyed_mapping_is_built_in_main(self):
        self.assertEqual(len(self.found["builds"]), 1,
                         "a second provider-listing mapping appeared in "
                         "main, or the only one moved: " +
                         repr(self.found["builds"]))
        self.assertEqual(self.found["builds"][0]["target"], "existing_lists")

    def test_the_mapping_is_built_from_every_list_in_the_workspace(self):
        build = self.found["builds"][0]
        tree = ast.parse(self.source, filename=TARGET)
        node = _func(tree, "main")
        env = _bindings(node)
        # `rows_now` is assigned twice: from `heyreach.lists()` and from the
        # tuple-unwrap of itself. Both arms are followed.
        sources_of_rows = set()
        for value in env.get(build["iter"], ()):
            if isinstance(value, tuple):        # a loop binding, not an expr
                continue
            for sub in ast.walk(value):
                if isinstance(sub, ast.Call):
                    sources_of_rows.add(_callee(sub) or "")
        self.assertIn("heyreach.lists", sources_of_rows,
                      "the mapping no longer comes from the provider's own "
                      "list listing; its iterable resolves to " +
                      repr(sorted(sources_of_rows)))

    def test_the_mapping_key_is_a_name_and_the_value_is_the_id(self):
        build = self.found["builds"][0]
        self.assertEqual(build["key"], "str(r.get('name'))")
        self.assertEqual(build["value"], "r.get('id')")

    def test_the_reuse_branch_selects_by_that_name(self):
        self.assertEqual(len(self.found["selects"]), 1,
                         repr(self.found["selects"]))
        select = self.found["selects"][0]
        self.assertEqual(select["mapping"], "existing_lists")
        self.assertEqual(select["key_expr"], "name")
        self.assertFalse(select["has_default"],
                         "a default would make a missing name indistinguish"
                         "able from a present one whose id is None")

    def test_the_selection_carries_no_id_and_no_owner(self):
        """The whole finding, as one assertion.

        If the key expression ever mentions an id, a list id, a workspace or
        an owner, this goes red - and that is the direction of the fix, so a
        red here is the signal to delete this test and keep the change.
        """
        key = self.found["selects"][0]["key_expr"]
        for token in ("id", "owner", "workspace", "tenant"):
            self.assertNotIn(token, key,
                             "the reuse branch now keys on " + key +
                             "; if that is an id this test is obsolete and "
                             "P2 of TASK-0250 landed")


class TwoListsOneName(unittest.TestCase):
    """C3. The same-name behaviour, demonstrated on constructed rows.

    The comprehension is EXTRACTED from the file and evaluated, rather than
    retyped here. A retyped copy would be a second representation that could
    drift from the one that runs - this estate's signature defect.
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, TARGET), encoding="utf-8") as handle:
            cls.source = handle.read()
        found = selector(cls.source)
        cls.comp = found["builds"][0]["comp"]
        cls.select = found["selects"][0]["src"]

    def _build(self, rows):
        return eval(self.comp, {"rows_now": rows, "str": str})  # noqa: S307

    def _select(self, mapping, name):
        return eval(self.select,  # noqa: S307
                    {"existing_lists": mapping, "name": name})

    def test_two_lists_with_one_name_collapse_to_the_last_one(self):
        name = OURS_NAME_PREFIX + "7"
        mapping = self._build([{"name": name, "id": 111111},
                               {"name": name, "id": 999999}])
        self.assertEqual(mapping, {name: 999999})
        self.assertEqual(self._select(mapping, name), 999999,
                         "LAST match wins. The ordering authority is the "
                         "position of the row in the provider's own "
                         "response, which this system does not control")

    def test_the_first_list_is_discarded_with_no_error_and_no_count(self):
        name = OURS_NAME_PREFIX + "7"
        rows = [{"name": name, "id": 111111}, {"name": name, "id": 999999}]
        mapping = self._build(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(mapping), 1,
                         "two rows in, one key out - and nothing in the file "
                         "compares those two numbers, so a collision is "
                         "silent")
        self.assertNotIn(111111, mapping.values())

    def test_a_row_whose_id_is_missing_reads_as_absent(self):
        """And the create branch then makes a SECOND list with that name.

        `:584-588` is `list_id = existing_lists.get(name)` / `if list_id:`
        reuse `else:` create. A present row whose `id` is None maps the name
        to None, which is falsy, so the file creates another list carrying a
        name it has just proven is already taken.
        """
        name = OURS_NAME_PREFIX + "7"
        mapping = self._build([{"name": name}])
        self.assertIn(name, mapping)
        self.assertIsNone(mapping[name])
        self.assertFalse(self._select(mapping, name),
                         "falsy, so the reuse branch is not taken even "
                         "though the name exists in the workspace")

    def test_a_row_with_no_name_becomes_the_string_None(self):
        """`str(None)` is `'None'`, which is a reachable key.

        A list literally named `None` in the shared workspace would be
        selected by a seat whose computed name were the string `None`. That
        cannot happen from this file's template today; it is recorded because
        the key expression is `str(...)` of an absent field rather than a
        refusal, and `missing evidence is never positive evidence`.
        """
        mapping = self._build([{"id": 5}])
        self.assertEqual(mapping, {"None": 5})

    def test_an_empty_listing_selects_nothing(self):
        self.assertEqual(self._build([]), {})
        self.assertIsNone(self._select({}, OURS_NAME_PREFIX + "7"))


class TheTracerCanFindAWriteSite(unittest.TestCase):
    """C1. Both states of the reader, on fixtures and on the real tree."""

    def test_the_write_reader_separates_a_write_from_a_post_shaped_read(self):
        capable = _fake_capable()["heyreach"]
        self.assertIn("create_list", capable)
        self.assertNotIn("lists", capable,
                         "`lists` reaches a POST and is a READ; a verb-only "
                         "seed calls it a write")

    def test_the_tracer_finds_a_known_write_site_fed_to_it(self):
        found = write_destinations(_fake_tree(FAKE_CALLER_NOT_OURS),
                                   _fake_capable())
        self.assertEqual(
            set(found),
            {("scripts/fake_caller.py", "main", "heyreach.create_list",
              "'PRODUCTIVE - JELENA - NOT OURS'")},
            repr(found))

    def test_the_tracer_reports_nothing_for_a_caller_that_only_reads(self):
        reader = "import heyreach\n\n\ndef main():\n    heyreach.lists()\n"
        found = write_destinations({"src/providers/heyreach.py": FAKE_ADAPTER,
                                    "scripts/fake_caller.py": reader},
                                   _fake_capable())
        self.assertEqual(found, {},
                         "a read was reported as a write destination")

    def test_the_reach_tracer_finds_a_known_flow_fed_to_it(self):
        """C1 for the reachability reader, positive state."""
        caller = ("import heyreach\n\n\n"
                  "def main():\n"
                  "    picked = {'a': 1}.get('a')\n"
                  "    heyreach.create_list(picked)\n")
        result = reach(caller, _fake_capable(), {"picked"})
        self.assertEqual({(v, ln) for _f, v, ln in result["reached"]},
                         {("heyreach.create_list", 6)}, repr(result))

    def test_the_reach_tracer_reports_empty_when_the_value_does_not_flow(self):
        """C1 negative state. An empty `reached` must be earnable."""
        caller = ("import heyreach\n\n\n"
                  "def main():\n"
                  "    picked = {'a': 1}.get('a')\n"
                  "    heyreach.create_list('RESONATE PRODUCTIVE LI B1 "
                  "SEAT 7')\n"
                  "    return picked\n")
        result = reach(caller, _fake_capable(), {"picked"})
        self.assertEqual(result["reached"], set())
        self.assertEqual(len(result["all"]), 1,
                         "and the denominator is still 1, so the empty is a "
                         "measured empty and not an unmeasured one")

    def test_the_reach_tracer_follows_one_call_edge_inside_the_file(self):
        caller = ("import heyreach\n\n\n"
                  "def push(destination):\n"
                  "    heyreach.create_list(destination)\n\n\n"
                  "def main():\n"
                  "    picked = {'a': 1}.get('a')\n"
                  "    push(picked)\n")
        result = reach(caller, _fake_capable(), {"picked"})
        self.assertEqual({(f, v) for f, v, _l in result["reached"]},
                         {("push", "heyreach.create_list")}, repr(result))

    def test_the_tracer_finds_the_three_sites_in_the_real_file(self):
        sources = tree_sources()
        found = write_destinations(sources, _adapters(sources),
                                   only={TARGET})
        verbs = {key[2] for key in found}
        self.assertEqual(
            verbs,
            {"heyreach.create_list", "heyreach.create_campaign",
             "heyreach.set_sequence"},
            "the three direct write sites 0244 named are no longer the three "
            "this reader finds: " + repr(sorted(verbs)))
        self.assertNotIn("heyreach.lists", verbs)


class WhereTheNameSelectedListCanReach(unittest.TestCase):
    """The severity question. 3 of the 4 adapter writes in this file.

    Two hops the tracer measures, one it refuses to guess and this class
    pins by hand instead - each of the three links separately assertable, so
    a repair anywhere along the chain shows up as a named red rather than as
    a quietly shrinking number.
    """

    @classmethod
    def setUpClass(cls):
        sources = tree_sources()
        cls.sources = sources
        cls.capable = _adapters(sources)
        cls.push = sources[TARGET]
        cls.seeds = name_selected_locals(cls.push)
        cls.result = reach(cls.push, cls.capable, cls.seeds)

    def test_the_seed_is_the_reused_list_id_and_nothing_else(self):
        self.assertEqual(self.seeds, {"list_id"})

    def test_the_file_holds_four_adapter_write_sites(self):
        self.assertEqual(
            {(verb, lineno) for _f, verb, lineno in self.result["all"]},
            {("heyreach.add_leads_to_list", 444),
             ("heyreach.create_list", 588),
             ("heyreach.create_campaign", 599),
             ("heyreach.set_sequence", 603)},
            "the denominator moved: " + repr(sorted(self.result["all"])))

    def test_link_a_the_reused_id_reaches_create_campaign_and_set_sequence(
            self):
        """Measured by the tracer, in-file, with no hand step."""
        self.assertEqual(
            {(verb, lineno) for _f, verb, lineno in self.result["reached"]},
            {("heyreach.create_campaign", 599),
             ("heyreach.set_sequence", 603)},
            repr(sorted(self.result["reached"])))

    def test_link_b_it_is_handed_to_liststaging_as_the_list_to_stage_onto(
            self):
        """`stage_rows_to_list(list_id, ...)` -> `liststaging.stage_lead`.

        The tracer records this as a STOP because the call leaves the file.
        The hop itself is asserted here rather than inferred.
        """
        leaving = [s for s in self.result["stopped"]
                   if s["call"] == "liststaging.stage_lead"]
        self.assertEqual(len(leaving), 1,
                         "the staging hop is gone or moved: " +
                         repr(self.result["stopped"]))
        self.assertEqual(leaving[0]["in"], "stage_rows_to_list")
        self.assertEqual(leaving[0]["via"], ["list_id"])
        # and `main` is what puts the seed into that parameter
        tree = ast.parse(self.push, filename=TARGET)
        node = _func(tree, "main")
        passed = False
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and _callee(sub) == "stage_rows_to_list"
                    and sub.args
                    and isinstance(sub.args[0], ast.Name)
                    and sub.args[0].id in self.seeds):
                passed = True
        self.assertTrue(passed,
                        "main no longer passes the name-selected list_id as "
                        "stage_rows_to_list's first argument")

    def test_link_c_the_payload_list_id_is_that_same_parameter(self):
        """The hop the tracer will not guess: a callback inversion.

        `liststaging.stage_lead` builds `payload["listId"] = int(list_id)`
        from its own first parameter, hands it to
        `providerwrites.perform(payload=..., transport=_transport)`, and
        `perform` calls `transport(payload)`. The body of that transport is
        the lambda back in THIS file at `:444`, which posts
        `payload["listId"]`. Three modules and an inverted call direction;
        a forward taint reader cannot follow it, so it is asserted.
        """
        staging = self.sources["src/liststaging.py"]
        tree = ast.parse(staging, filename="src/liststaging.py")
        node = _func(tree, "stage_lead")
        self.assertIsNotNone(node)
        self.assertEqual([a.arg for a in node.args.args][0], "list_id",
                         "stage_lead's first parameter is no longer the list")
        built = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Dict):
                continue
            for key, value in zip(sub.keys, sub.values):
                if (isinstance(key, ast.Constant)
                        and key.value == "listId"):
                    built.add(ast.unparse(value))
        self.assertEqual(built, {"int(list_id)"},
                         "the payload's listId is no longer built from "
                         "stage_lead's own parameter: " + repr(built))
        # and the lambda in THIS file posts that key
        push_tree = ast.parse(self.push, filename=TARGET)
        posted = set()
        for sub in ast.walk(push_tree):
            if (isinstance(sub, ast.Call)
                    and _callee(sub) == "heyreach.add_leads_to_list"
                    and sub.args):
                posted.add(ast.unparse(sub.args[0]))
        self.assertEqual(posted, {"payload['listId']"}, repr(posted))

    def test_the_fourth_site_is_the_branch_reuse_does_not_take(self):
        """`create_list` is the only one a reused list cannot reach.

        Which is the whole asymmetry: the one write that would have made the
        list ours is the one that does not run when a name matches.
        """
        reached = {verb for _f, verb, _l in self.result["reached"]}
        self.assertNotIn("heyreach.create_list", reached)

    def test_the_reader_records_where_it_stopped_rather_than_rounding_down(
            self):
        self.assertTrue(self.result["stopped"],
                        "a reachability answer with no recorded stop is "
                        "either complete or lying, and this reader is not "
                        "complete")
        for stop in self.result["stopped"]:
            self.assertIn("why", stop)
            self.assertTrue(stop["via"])

    def test_both_reached_sites_bypass_the_write_door(self):
        direct = direct_sites(self.sources, self.capable,
                              perform_sinks(self.sources))
        for fname, verb, _lineno in self.result["reached"]:
            self.assertIn((TARGET, fname, verb), direct,
                          verb + " now goes through perform; if that is "
                          "intentional, P2 of TASK-0250 landed")


class EveryDirectWriteDestinationIsOursOrIsNamed(unittest.TestCase):
    """The assertion 0244 proved does not exist. It keys on the ARGUMENT.

    Proven by plant at each of `:588`, `:599` and `:603` separately -
    TASK-0250 C2. See `LANE-pilotcaps.md` for the three kill-sets.
    """

    @classmethod
    def setUpClass(cls):
        sources = tree_sources()
        cls.destinations = write_destinations(
            sources, _adapters(sources), only={TARGET})

    def test_every_destination_in_the_push_script_resolves_to_ours(self):
        bad = violations(self.destinations)
        self.assertEqual(
            bad, {},
            "a direct adapter write in " + TARGET + " has a destination "
            "this reader cannot establish as ours: " + repr(bad))

    def test_the_name_keyed_destinations_are_exactly_the_recorded_set(self):
        found = set()
        for key, got in self.destinations.items():
            if any(root.startswith("SELECTED_FROM:") for root in got):
                found.add(key)
        self.assertEqual(
            found, NAME_KEYED_DESTINATIONS,
            "the set of destinations selected out of a provider listing by a "
            "free-text key has changed. A new one is a new instance of the "
            "327/328/352 defect; a removed one means P2 landed and this "
            "record should go with it.")

    def test_the_recorded_one_is_the_reuse_branch_of_the_seat_list(self):
        key = (TARGET, "main", "heyreach.create_campaign", "list_id")
        self.assertIn(key, self.destinations)
        got = self.destinations[key]
        self.assertIn("CREATED_HERE:heyreach.create_list", got)
        self.assertIn("SELECTED_FROM:existing_lists[name]", got,
                      "both arms of the reuse `if` must be unioned; one arm "
                      "alone is half the defect")

    def test_a_not_ours_literal_destination_is_reported(self):
        found = write_destinations(_fake_tree(FAKE_CALLER_NOT_OURS),
                                   _fake_capable())
        bad = violations(found)
        self.assertEqual(len(bad), 1, repr(bad))
        self.assertEqual(list(bad.values())[0],
                         ["LITERAL_STR:'PRODUCTIVE - JELENA - NOT OURS'"])

    def test_an_ours_literal_destination_is_not_reported(self):
        found = write_destinations(_fake_tree(FAKE_CALLER_OURS),
                                   _fake_capable())
        self.assertEqual(violations(found), {},
                         "the ours arm must be clean, or a red above means "
                         "nothing: see `a-control-must-observe-the-guard-"
                         "it-tests`")

    def test_an_unresolvable_destination_is_a_violation_and_not_a_pass(self):
        found = write_destinations(_fake_tree(FAKE_CALLER_UNRESOLVABLE),
                                   _fake_capable())
        bad = violations(found)
        self.assertEqual(len(bad), 1, repr(bad))
        self.assertTrue(list(bad.values())[0][0].startswith("UNKNOWN:"),
                        repr(bad))

    def test_a_numeric_destination_is_a_violation(self):
        caller = ("import heyreach\n\n\ndef main():\n"
                  "    heyreach.set_sequence(908213447, {})\n")
        adapter = FAKE_ADAPTER + (
            "\n\ndef set_sequence(campaign_id, graph):\n"
            "    return _write('/campaign/UpdateSequence', graph)\n")
        found = write_destinations(
            {"src/providers/heyreach.py": adapter,
             "scripts/fake_caller.py": caller},
            {"heyreach": write_capable(adapter, "fake-heyreach")})
        bad = violations(found)
        self.assertIn(("scripts/fake_caller.py", "main",
                       "heyreach.set_sequence", "908213447"), bad)
        self.assertEqual(bad[("scripts/fake_caller.py", "main",
                              "heyreach.set_sequence", "908213447")],
                         ["LITERAL_NUM:908213447"])


class TheReaderHasOneNamedBlindSpot(unittest.TestCase):
    """And a second instance of the defect that sits inside it.

    `EveryDirectWriteDestinationIsOursOrIsNamed` is scoped to `TARGET` on
    purpose, and the reason is measured rather than asserted by taste. Run
    over the whole tree, `write_destinations` reports 42 destinations and
    `violations` returns 28 of them - almost all `UNKNOWN:unbound(...)`,
    because the destination is a FUNCTION PARAMETER (`provider_id`, `pid`) or
    a module constant (`LIST_ID`, `DORMANT`, `CAMPAIGN`). An intraprocedural
    reader cannot resolve a parameter, and UNKNOWN is a violation by this
    module's own fail-closed rule. Widening the green assertion to the tree
    would therefore have been 28 reds that say nothing new, so it is not
    widened - and the scope is written down with its number instead of left
    as a choice nobody can check.

    THE BLIND SPOT, which matters more than the 28.
    `scripts/batch_linkedin_reconcile.py` does the same thing as `:584` and
    does it to CAMPAIGNS: `provider_state` reads every campaign and every
    list in the shared workspace and keeps the ones whose NAME starts with
    `RESONATE PRODUCTIVE LI B1 SEAT `, and `main` posts
    `heyreach.set_sequence(campaign["id"], graph)` onto what that selected.
    0241 recorded it under NOT PROVEN and was right.

    This reader does NOT see it, and the two tests below say so in both
    directions. `provider_state` builds its maps with an explicit `for` loop
    in a DIFFERENT function; `selector` finds dict comprehensions in the
    SAME function. So `campaign` resolves to a loop over a local and comes
    back `PLAN_LOCAL` - a FALSE ALLOW, not a pass. It is named here because
    an instrument's limit recorded is worth more than a clean verdict that
    had no way to fail.
    """

    @classmethod
    def setUpClass(cls):
        cls.sources = tree_sources()
        cls.reconcile = "scripts/batch_linkedin_reconcile.py"

    def test_the_reconcile_script_also_selects_a_campaign_by_a_name_prefix(
            self):
        source = self.sources[self.reconcile]
        tree = ast.parse(source, filename=self.reconcile)
        node = _func(tree, "provider_state")
        self.assertIsNotNone(node, "provider_state is gone")
        prefixed = {ast.unparse(sub.func.value)
                    for sub in ast.walk(node)
                    if isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "startswith"}
        self.assertEqual(prefixed, {"name"},
                         "the prefix selection changed shape: "
                         + repr(sorted(prefixed)))
        posted = {ast.unparse(sub.args[0])
                  for sub in ast.walk(tree)
                  if isinstance(sub, ast.Call)
                  and _callee(sub) == "heyreach.set_sequence" and sub.args}
        self.assertEqual(posted, {"campaign['id']"}, repr(posted))

    def test_this_readers_destination_scan_cannot_see_that_one(self):
        """Fail-closed on the limitation itself.

        A red here means the reader grew the ability to resolve a
        loop-built map in another function - and then the prose above is
        obsolete and should be deleted with this test.
        """
        found = write_destinations(self.sources, _adapters(self.sources),
                                   only={self.reconcile})
        selected = {key for key, got in found.items()
                    if any(root.startswith("SELECTED_FROM:") for root in got)}
        self.assertEqual(selected, set(),
                         "the reader now sees the reconcile selection: "
                         + repr(sorted(selected)))
        self.assertTrue(found,
                        "and it does still read that file, so the empty "
                        "above is a measured empty rather than an "
                        "unvisited one")


class RoutingItThroughTheDoorWouldNotAskWhoseListItIs(unittest.TestCase):
    """0244's P2 assumed `perform` would supply the ownership check. It would not.

    `require_resonate_os_campaign` returns `None` on its SECOND statement for
    any operation in `LIST_SCOPED`, and both verbs that a reused list reaches
    are in it. So moving `:599` behind `perform` buys the killswitch, the
    ledgers and the execution grant - and specifically NOT an owner check.
    That is the single most expensive thing to get wrong about P2, so it is
    asserted here rather than left in prose.

    The exemption's own stated reasoning is quoted in `src/providerwrites.py`
    at `LIST_SCOPED`: *a list bound to nothing cannot reach any campaign,
    internal or otherwise*. That is true at the moment `add_lead_to_list`
    runs. The next statement in the push loop is `:599`, which BINDS that
    list to our campaign - so the property the exemption rests on is consumed
    one statement later, by the same iteration. Recorded as a finding;
    nothing here changes it.

    Parsed with `ast`, never imported, for the reason `ThisModuleAddsNoGate`
    asserts: a test about a guard must not be able to invoke it.
    """

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "src", "providerwrites.py")
        with open(path, encoding="utf-8") as handle:
            cls.tree = ast.parse(handle.read(), filename=path)

    def _assigned(self, name):
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name
                            for t in node.targets)):
                return node.value
        return None

    def test_list_scoped_holds_exactly_the_two_verbs_a_reused_list_reaches(
            self):
        value = self._assigned("LIST_SCOPED")
        self.assertIsNotNone(value, "LIST_SCOPED is gone")
        members = {ast.unparse(element) for element in value.elts}
        self.assertEqual(members,
                         {"LINKEDIN_ADD_LEAD_TO_LIST",
                          "LINKEDIN_CREATE_CAMPAIGN"},
                         "the exemption's membership changed: "
                         + repr(sorted(members)))

    def test_the_ownership_guard_returns_early_for_a_list_scoped_operation(
            self):
        node = _func(self.tree, "require_resonate_os_campaign")
        self.assertIsNotNone(node)
        early = []
        for sub in ast.walk(node):
            if not isinstance(sub, ast.If):
                continue
            test = ast.unparse(sub.test)
            if "LIST_SCOPED" not in test:
                continue
            for stmt in sub.body:
                if isinstance(stmt, ast.Return):
                    early.append((test, ast.unparse(stmt.value)
                                  if stmt.value is not None else "None"))
        self.assertEqual(early, [("operation in LIST_SCOPED", "None")],
                         "the LIST_SCOPED early return changed shape: "
                         + repr(early))

    def test_the_list_level_refusal_proposed_by_0244_does_not_exist(self):
        """P2's `require_resonate_os_list` is a PROPOSAL and is unwritten.

        A red here means it landed, and then this module's record of the gap
        should go with it.
        """
        defined = {node.name for node in ast.walk(self.tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertNotIn("require_resonate_os_list", defined)


class ThisModuleAddsNoGate(unittest.TestCase):
    """0241's discipline, applied to 0250: say it and assert it."""

    def test_it_does_not_import_or_name_the_ownership_refusal(self):
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=__file__)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported |= {alias.name for alias in node.names}
        self.assertNotIn("src.providerwrites", imported)
        self.assertNotIn("require_resonate_os_campaign", imported)
        for name in imported:
            self.assertFalse(name.startswith("src.providers."),
                             "this module must not import a provider adapter;"
                             " it parses them as data: " + name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
