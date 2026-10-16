"""TASK-0241. Two guards, one door, and the one that is campaign-blind.

`providers.refuse_unauthorized_write` sits on the FIRST LINE of
`providers._urllib_transport`, so every mutating call to either
prospect-facing host passes it and `heyreach.py`/`bison.py` naming it zero
times each proves no bypass rather than a hole. But it is URL-keyed: it asks
the method, the host, the declared-read list and whether any
`allow_writes` scope is open. **It never asks whose campaign this is.**

Ownership is a different guard - `providerwrites.require_resonate_os_campaign`
- and it is called from exactly two places, both inside
`providerwrites._perform`. So a call that reaches an adapter write WITHOUT
going through `perform` gets the door and not the ownership default, and the
ownership default is the one that refuses an internal Resonate campaign and
treats `unknown` as do-not-touch.

WHAT THIS MODULE IS AND IS NOT
------------------------------
It is a TEST. It asserts; it refuses nothing. It is imported by no writer, it
adds no gate, guard, cap or refusal, and it cannot stop a live provider call -
`resonate-ops\\queue\\_STANDING-RULES.md` forbids a lane adding one and
`suppression/0180` was right to withhold the same shape. The gate change this
measurement argues for is a PROPOSAL recorded in `LANE-pilotcaps.md`, for the
operator to take or leave.

WHY IT PARSES SOURCE RATHER THAN CALLING ANYTHING
-------------------------------------------------
CLAUDE.md's rule is to test behaviour rather than the text of the source,
"assert on the import graph or on what a function returns", because a word
search fails when somebody writes a comment. This asserts on the parsed CALL
GRAPH, which is the import-graph half of that rule: no string in any file
under test is searched for, and the fixtures below prove the reader has teeth
by exercising it against planted code rather than against the tree.

It has to be structural, because the defect is a guard that is ABSENT at a
call site. Nothing returns a value when a check does not happen, and the
existing `require_resonate_os_campaign` tests all drive `perform` - which is
exactly the path that already has the guard. A test that can only see the
guarded path cannot see the unguarded one, and that is why this gap was
invisible while a different guard was present.
"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ADAPTERS = ("heyreach", "bison")

#: The adapters' own read helpers. BOTH GUARDED PROVIDERS READ WITH POST -
#: HeyReach answers `/campaign/GetAll`, `/li_account/GetAll`, `/list/GetAll`
#: and the inbox as POSTs behind `heyreach.READ_ROUTES_ALL` - so seeding
#: "write-capable" from the verb alone calls `li_accounts` and `lists` writes.
#: The modules keep their own separation and that is what is keyed on.
READ_HELPERS = frozenset({"_read", "_read_get", "_read_post", "_get"})

WRITE_VERBS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Every direct adapter-write call site in the tree, keyed by file, enclosing
#: function and adapter verb - never by line number, which drifts under an
#: unrelated edit. Compared BY SET, both directions: a new bypass makes this
#: red naming the site, and a bypass that is removed makes it red too, so the
#: list cannot quietly outlive the code.
#:
#: Being on this list is NOT a safety argument. It records that the site was
#: read on 2026-10-16 and what was found. Three classes, and only the first is
#: safe by construction:
#:
#:   CREATES      the campaign or list does not exist yet, so there is nothing
#:                for an ownership guard to classify. This is the argument
#:                0238 accepted for `batch_linkedin_push.py`, and it holds for
#:                the two create verbs there and for `probe_list_staging`'s.
#:   OURS-BY-ID   the destination is a literal constant or a binding this
#:                system wrote, so it is ours in fact - but nothing asks, and
#:                a changed constant or a stale binding is not detected.
#:   NOT PROVEN   the destination comes from a PROVIDER listing or a report
#:                file and is selected by name. The by-construction argument
#:                does NOT hold here and these are the finding.
DIRECT_SITES_ACCEPTED = {
    # --- CREATES: nothing exists yet to classify ------------------------
    ("scripts/batch_linkedin_push.py", "main", "heyreach.create_list"),
    ("scripts/batch_linkedin_push.py", "main", "heyreach.create_campaign"),
    ("scripts/probe_list_staging.py", "main", "heyreach.create_list"),
    # `set_sequence` on the id `create_campaign` returned one statement
    # earlier. Safe for the same reason - and only while that stays true.
    ("scripts/batch_linkedin_push.py", "main", "heyreach.set_sequence"),

    # --- OURS-BY-ID: a constant or a binding we wrote, unverified -------
    # `CAMPAIGN = 487`, a literal, and the grant is spent.
    ("scripts/resume_487.py", "main", "bison.resume_campaign"),
    # `DORMANT = 481`, a literal.
    ("scripts/make_481_inert.py", "main", "bison.stop_lead"),
    # `row["bison_campaign_id"]` off a canonical campaign row - the same
    # binding `require_resonate_os_campaign` would read, read by nobody.
    ("scripts/batch_activate.py", "main", "bison.resume_campaign"),
    # `campaign["heyreach_list_id"]`, and stage 2 adds to a list BOUND to a
    # live campaign.
    ("scripts/probe_list_staging.py", "main", "heyreach.add_leads_to_list"),
    # A module-level `LIST_ID`, reached by an `except TypeError` fallback
    # that wraps a whole `liststaging.stage_lead` call - so a TypeError
    # raised anywhere inside `perform` is converted into an unguarded write.
    ("scripts/write_linkedin_lead_variables.py", "main",
     "heyreach.add_leads_to_list"),
    # `provider_id` from `bisonfactory._find_or_create`, which REUSES
    # `campaign["bison_campaign_id"]` when the row carries one. The module
    # says so itself at `_ensure_leads`: "`_ensure_leads` does not go through
    # `providerwrites.perform` ... so the write door's killswitch gate does
    # not cover it". The workspace killswitch and an `executionscope` grant
    # are the controls there; neither asks who owns the campaign.
    ("src/bisonfactory.py", "_ensure_limits", "bison.set_limits"),
    ("src/bisonfactory.py", "_ensure_schedule", "bison.set_schedule"),
    ("src/bisonfactory.py", "_ensure_senders", "bison.attach_senders"),
    ("src/bisonfactory.py", "_ensure_leads", "bison.ensure_custom_variables"),
    ("src/bisonfactory.py", "_ensure_leads", "bison.create_lead"),
    ("src/bisonfactory.py", "_ensure_leads", "bison.update_lead"),
    ("src/bisonfactory.py", "_ensure_leads", "bison.attach_leads"),
    ("src/bisonfactory.py", "_ensure_stopped", "bison.pause_campaign"),

    # --- READER LIMITATION, recorded rather than hidden -----------------
    # `orchestrator._resume_at_providers` builds its transports in a TUPLE
    # LITERAL, unpacks them into a loop variable and passes that variable to
    # `perform` as `transport=lambda _p, t=transport, ...`. These two DO go
    # through the door; the reader below resolves a named local def and an
    # inline lambda but not a tuple-unpacked loop variable, so it reports
    # them. Verified by reading `src/orchestrator.py` at b1d54717b.
    ("src/orchestrator.py", "_resume_at_providers", "bison.resume_campaign"),
    ("src/orchestrator.py", "_resume_at_providers",
     "heyreach.resume_campaign"),

    # --- NOT PROVEN: this is the finding --------------------------------
    # `heyreach.campaigns()` lists EVERY campaign in the shared HeyReach
    # workspace; `provider_state` keeps the ones whose NAME starts with
    # "RESONATE PRODUCTIVE LI B1 SEAT " and `main` posts `set_sequence` onto
    # `campaign["id"]`. A name is free text with no referential integrity -
    # CLAUDE.md records that lesson about 327/328/352 already - and this is
    # the only thing standing between an `UpdateSequence` write and any
    # campaign in an estate where most of what runs is not ours. No create,
    # so "a just-created campaign is not in the ledger" does not apply.
    ("scripts/batch_linkedin_reconcile.py", "main", "heyreach.set_sequence"),
    # `row["id"]` from `work/linkedin-batch-campaigns.json`, a REPORT file,
    # not the campaign ledger - and the verb is START.
    ("scripts/linkedin_activate.py", "main", "heyreach.activate_campaign"),
}


# ----------------------------------------------------------------- the reader
def _callee(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        parts, cur = [f.attr], f.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _toplevel(tree):
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def write_capable(source, filename="<adapter>"):
    """Adapter functions that transitively reach a MUTATING request."""
    tree = ast.parse(source, filename=filename)
    funcs = _toplevel(tree)
    seeds, edges = set(), {}
    for name, node in funcs.items():
        calls = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            callee = _callee(sub)
            if callee is None:
                continue
            tail = callee.rsplit(".", 1)[-1]
            calls.add(tail)
            if tail == "request" and sub.args and name not in READ_HELPERS:
                first = sub.args[0]
                if (isinstance(first, ast.Constant)
                        and isinstance(first.value, str)
                        and first.value.strip().upper() in WRITE_VERBS):
                    seeds.add(name)
        edges[name] = calls
    for helper in ("_write", "_write_body"):
        if helper in funcs:
            seeds.add(helper)
    seeds -= READ_HELPERS
    reached, frontier = set(seeds), list(seeds)
    while frontier:
        cur = frontier.pop()
        for name, calls in edges.items():
            if cur in calls and name not in reached:
                reached.add(name)
                frontier.append(name)
    return reached


def perform_sinks(sources):
    """Functions that FORWARD an injected transport into `perform`.

    `{rel: source}` in, `{(rel, func)}` out. Two shapes, and the first
    version of this reader only found the second - reporting zero sinks and
    therefore calling `liststaging.stage_lead` a bypass, which is the one
    site in `batch_linkedin_push.py` that does go through the door:

        transport=transport                         the parameter itself
        def _transport(p): return transport(p)      a closure over it
    """
    sinks = set()
    for rel, source in sources.items():
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue
        for name, node in _toplevel(tree).items():
            params = {a.arg for a in list(node.args.args)
                      + list(node.args.kwonlyargs)}
            if not params:
                continue
            local = {}
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    local[sub.name] = sub
                elif isinstance(sub, ast.Assign) and isinstance(sub.value,
                                                                ast.Lambda):
                    for tgt in sub.targets:
                        if isinstance(tgt, ast.Name):
                            local[tgt.id] = sub.value
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                if (_callee(sub) or "").rsplit(".", 1)[-1] != "perform":
                    continue
                for kw in sub.keywords:
                    if kw.arg != "transport":
                        continue
                    if (isinstance(kw.value, ast.Name)
                            and kw.value.id in params):
                        sinks.add((rel, name))
                        continue
                    body = (local.get(kw.value.id)
                            if isinstance(kw.value, ast.Name)
                            else kw.value if isinstance(kw.value, ast.Lambda)
                            else None)
                    if body is None:
                        continue
                    for ref in ast.walk(body):
                        if (isinstance(ref, ast.Name)
                                and isinstance(ref.ctx, ast.Load)
                                and ref.id in params):
                            sinks.add((rel, name))
                            break
    return sinks


def direct_sites(sources, capable, sinks, key_on_adapter_name=False):
    """{(rel, enclosing func, adapter call)} that bypass `perform`.

    `key_on_adapter_name` is the control: keyed on whether the FILE mentions
    the door rather than on the transport boundary, which is how the
    placement argument is reproduced instead of quoted.
    """
    sink_tails = {name for _rel, name in sinks} | {"perform"}
    found = set()
    for rel, source in sources.items():
        if rel in ("src/providers/heyreach.py", "src/providers/bison.py"):
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        named, spans = {}, []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                named.setdefault(node.name, []).append(node)
                spans.append((node.lineno, node.end_lineno, node.name))
            elif isinstance(node, ast.Assign) and isinstance(node.value,
                                                             ast.Lambda):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        named.setdefault(tgt.id, []).append(node.value)
        # Every callable handed to a perform sink. A NAMED one is resolved by
        # name: the `ast.Name` at the call is a different node from the
        # `def` whose body holds the adapter call, so an ancestor test
        # against the Name alone can never match and the first version of
        # this reader called nine `bisonfactory`/`heyreachfactory` closures
        # bypasses.
        laundered = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (_callee(node) or "").rsplit(".", 1)[-1] not in sink_tails:
                continue
            for arg in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(arg, (ast.Lambda, ast.FunctionDef)):
                    laundered.add(arg)
                elif isinstance(arg, ast.Name):
                    laundered.update([arg] + named.get(arg.id, []))
                elif isinstance(arg, ast.Attribute):
                    laundered.update([arg] + named.get(arg.attr, []))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _callee(node)
            if callee is None or "." not in callee:
                continue
            owner, fn = callee.rsplit(".", 1)
            owner = owner.rsplit(".", 1)[-1]
            if owner not in ADAPTERS or fn not in capable.get(owner, ()):
                continue
            if key_on_adapter_name:
                through = ("refuse_unauthorized_write" not in source
                           and "_urllib_transport" not in source)
            else:
                through, cur = False, parent.get(node)
                while cur is not None:
                    if cur in laundered:
                        through = True
                        break
                    cur = parent.get(cur)
            if through:
                continue
            best = None
            for a, b, name in spans:
                if a <= node.lineno <= b and (best is None or a > best[0]):
                    best = (a, name)
            found.add((rel, best[1] if best else "<module>", callee))
    return found


def tree_sources(root=ROOT, subdirs=("src", "scripts")):
    out = {}
    for sub in subdirs:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, sub)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, "rb") as fh:
                    out[os.path.relpath(path, root).replace("\\", "/")] = (
                        fh.read().decode("utf-8", "replace"))
    return out


def _adapters(sources):
    return {a: write_capable(sources["src/providers/%s.py" % a])
            for a in ADAPTERS}


# ----------------------------------------------------------- the fixtures
#
# Minimal trees, so a leg that must go RED can be forced without touching a
# real file. Each one is a whole fake repository: two adapters, a door, and
# callers.

_FAKE_ADAPTER = '''
from . import request


def _read(path, body):
    return request("POST", BASE + path, {}, body)


def _write(path, params):
    return request("POST", BASE + path, {}, {})


def create_campaign(name):
    return _write("/campaign/Create", {"name": name})


def set_sequence(campaign_id, graph):
    return _write("/campaign/UpdateSequence", {"id": campaign_id})


def campaigns():
    return _read("/campaign/GetAll", {})
'''

_FAKE_SINK = '''
from . import providerwrites


def stage(list_id, transport):
    def _transport(p):
        return transport(p)
    return providerwrites.perform("op", transport=_transport, readback=None)
'''


def _fake_tree(caller_body):
    return {
        "src/providers/heyreach.py": _FAKE_ADAPTER,
        "src/providers/bison.py": _FAKE_ADAPTER,
        "src/liststaging.py": _FAKE_SINK,
        "scripts/caller.py": caller_body,
    }


class TheDoorIsOnTheTransportAndIsCampaignBlind(unittest.TestCase):
    """What `refuse_unauthorized_write` refuses, and what it does not.

    Asserted against the real module, because the placement is the whole of
    0238's "zero mentions proves no bypass" argument.
    """

    def test_the_door_is_the_first_statement_of_the_transport(self):
        from src import providers

        with open(providers.__file__, "rb") as fh:
            source = fh.read().decode("utf-8")
        tree = ast.parse(source)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_urllib_transport")
        first = fn.body[0]
        self.assertIsInstance(first, ast.Expr)
        self.assertEqual(_callee(first.value), "refuse_unauthorized_write")

    def test_it_is_on_the_transport_rather_than_on_each_adapter(self):
        """ONE caller, and it is the transport. This is what makes the
        adapters' zero mentions proof of coverage rather than of a hole."""
        from src import providers

        with open(providers.__file__, "rb") as fh:
            source = fh.read().decode("utf-8")
        tree = ast.parse(source)
        callers = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and _callee(node) == "refuse_unauthorized_write"):
                enclosing = [
                    n.name for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno <= node.lineno <= n.end_lineno]
                callers.update(enclosing)
        self.assertEqual(callers, {"_urllib_transport"})

        for adapter in ADAPTERS:
            path = os.path.join(ROOT, "src", "providers", adapter + ".py")
            with open(path, "rb") as fh:
                blob = fh.read()
            self.assertNotIn(b"refuse_unauthorized_write", blob)

    def test_the_door_refuses_by_url_and_never_by_campaign(self):
        """It takes `(method, url)` and nothing else. A campaign id is not a
        parameter it has, so it cannot be a question it asks."""
        from src import providers

        with open(providers.__file__, "rb") as fh:
            source = fh.read().decode("utf-8")
        tree = ast.parse(source)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "refuse_unauthorized_write")
        self.assertEqual([a.arg for a in fn.args.args], ["method", "url"])
        self.assertEqual(fn.args.kwonlyargs, [])

    def test_the_ownership_guard_is_reachable_only_from_perform(self):
        from src import providerwrites

        with open(providerwrites.__file__, "rb") as fh:
            source = fh.read().decode("utf-8")
        tree = ast.parse(source)
        callers = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and _callee(node) == "require_resonate_os_campaign"):
                for n in ast.walk(tree):
                    if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and n.lineno <= node.lineno <= n.end_lineno
                            and n.name != "require_resonate_os_campaign"):
                        callers.add(n.name)
        self.assertEqual(callers, {"_perform"})


class AnAdapterWriteThatSkipsTheDoorIsNamed(unittest.TestCase):
    """THE CHECK THAT WOULD FIRE. Compared by set, both directions."""

    @classmethod
    def setUpClass(cls):
        cls.sources = tree_sources()
        cls.capable = _adapters(cls.sources)
        cls.sinks = perform_sinks(cls.sources)

    def test_the_reader_finds_the_sinks_it_has_to_find(self):
        self.assertIn(("src/liststaging.py", "stage_lead"), self.sinks)

    def test_every_direct_adapter_write_is_an_accepted_and_reasoned_site(self):
        found = direct_sites(self.sources, self.capable, self.sinks)
        new = found - DIRECT_SITES_ACCEPTED
        gone = DIRECT_SITES_ACCEPTED - found
        self.assertEqual(
            new, set(),
            "a provider WRITE reaches the transport without passing "
            "`providerwrites.perform`, so `require_resonate_os_campaign` "
            "cannot run and the destination's ownership is never asked: "
            + "; ".join("%s::%s -> %s" % s for s in sorted(new)))
        self.assertEqual(
            gone, set(),
            "a site on DIRECT_SITES_ACCEPTED no longer bypasses `perform` - "
            "good news, and the list has to lose it or it outlives the code: "
            + "; ".join("%s::%s -> %s" % s for s in sorted(gone)))

    def test_the_three_linkedin_push_sites_are_the_canary_channel_ones(self):
        """0238's count of three, re-derived rather than quoted."""
        found = direct_sites(self.sources, self.capable, self.sinks)
        push = {s for s in found
                if s[0] == "scripts/batch_linkedin_push.py"}
        self.assertEqual(
            {s[2] for s in push},
            {"heyreach.create_list", "heyreach.create_campaign",
             "heyreach.set_sequence"})

    def test_the_laundered_site_in_the_same_file_is_not_flagged(self):
        """C1. `stage_rows_to_list` hands its adapter call to
        `liststaging.stage_lead`, which performs it. A reader that flagged
        everything would score perfectly on the three above."""
        found = direct_sites(self.sources, self.capable, self.sinks)
        self.assertNotIn(
            ("scripts/batch_linkedin_push.py", "stage_rows_to_list",
             "heyreach.add_leads_to_list"), found)

    def test_a_post_that_reads_is_not_called_a_write(self):
        """`li_accounts` and `lists` are POSTs on HeyReach's read routes."""
        for read_verb in ("li_accounts", "lists", "campaigns",
                          "campaign_read"):
            self.assertNotIn(read_verb, self.capable["heyreach"], read_verb)
        for write_verb in ("create_campaign", "set_sequence", "create_list",
                           "pause_campaign", "add_leads_to_list"):
            self.assertIn(write_verb, self.capable["heyreach"], write_verb)


class TheReaderHasTeeth(unittest.TestCase):
    """Planted trees, so every leg above can be forced red on demand."""

    def test_a_planted_bypass_is_found_and_named(self):
        tree = _fake_tree(
            "from src.providers import heyreach\n"
            "def go():\n"
            "    heyreach.set_sequence(565765, {})\n")
        capable, sinks = _adapters(tree), perform_sinks(tree)
        self.assertIn(("scripts/caller.py", "go", "heyreach.set_sequence"),
                      direct_sites(tree, capable, sinks))

    def test_a_planted_laundered_call_is_not_found(self):
        tree = _fake_tree(
            "from src import liststaging\n"
            "from src.providers import heyreach\n"
            "def go():\n"
            "    liststaging.stage(7, lambda p: "
            "heyreach.set_sequence(p['id'], {}))\n")
        capable, sinks = _adapters(tree), perform_sinks(tree)
        self.assertEqual(direct_sites(tree, capable, sinks), set())

    def test_keying_on_the_adapter_name_reports_zero_with_a_bypass_present(self):
        """0238's placement point, REPRODUCED. The adapters mention the door
        zero times each, so a reader that asks the adapter's own file whether
        the door is there answers yes for every call and finds nothing."""
        tree = _fake_tree(
            "from src.providers import heyreach\n"
            "def go():\n"
            "    heyreach.set_sequence(565765, {})\n")
        capable, sinks = _adapters(tree), perform_sinks(tree)
        self.assertEqual(
            direct_sites(tree, capable, sinks, key_on_adapter_name=True),
            set())
        self.assertNotEqual(direct_sites(tree, capable, sinks), set())


class TheHandoffNothingRefuses(unittest.TestCase):
    """PART B. `SEND_LEAD_TO_BISON` is in `PAYLOAD_REQUIRED`, so the
    validator requires it to be WELL-FORMED, never ABSENT - and it never
    looks at the EmailBison campaign the payload names.

    The stored standard sequence is campaign 565765's graph read verbatim and
    its three hand-offs are pinned to the client's EmailBison 417 and 418.
    `scripts/batch_linkedin_push.drop_bison_handoff` strips them, and nothing
    else does: the protection is in ONE caller, not in the adapter.

    These bytes are never written. The config is read and deep-copied; the
    plant below carries an INVENTED nine-digit id that names no campaign
    anywhere, and `validate_sequence_for_write` is a pure function that
    opens no socket.
    """

    STANDARD = os.path.join(ROOT, "config", "linkedin",
                            "productive-standard.json")
    #: Invented. Nine digits, matches nothing, and deliberately not 417/418.
    PLANTED = 419357281

    @staticmethod
    def _handoffs(node, where="root", out=None):
        out = [] if out is None else out
        if isinstance(node, dict):
            if str(node.get("nodeType") or "") == "SEND_LEAD_TO_BISON":
                out.append((where, node))
            for key in ("conditionalNode", "unconditionalNode"):
                if node.get(key) is not None:
                    self_ = TheHandoffNothingRefuses
                    self_._handoffs(node[key], where + "." + key, out)
        return out

    @staticmethod
    def ownership_violations(graph, allowed_ids=()):
        """THE PROPOSED ASSERTION, as an assertion.

        Every `SEND_LEAD_TO_BISON` in a graph about to be written must name
        an EmailBison campaign positively recorded as a Resonate OS
        campaign. An unrecognised id is a violation; an UNRESOLVABLE one is
        a violation too, because unknown never becomes safe.

        It refuses nothing and no writer calls it. The gate version is a
        proposal in `LANE-pilotcaps.md`.
        """
        allowed = {str(a).strip() for a in allowed_ids if str(a or "").strip()}
        out = []
        for where, node in TheHandoffNothingRefuses._handoffs(graph):
            payload = node.get("payload")
            if not isinstance(payload, dict):
                out.append((where, None, "no payload, so no destination"))
                continue
            raw = payload.get("bisonCampaignId", payload.get("campaignId"))
            key = str(raw).strip() if raw is not None else ""
            if not key:
                out.append((where, None, "names no EmailBison campaign id"))
            elif key not in allowed:
                out.append((where, key,
                            "EmailBison campaign %s is not positively "
                            "recorded as a Resonate OS campaign" % key))
        return out

    def _graph(self):
        import copy
        import json

        with open(self.STANDARD, "rb") as fh:
            raw = fh.read()
        return copy.deepcopy(json.loads(raw.decode("utf-8"))["graph"])

    def test_the_stored_standard_carries_the_clients_own_campaign_ids(self):
        ids = sorted({str((n.get("payload") or {}).get("bisonCampaignId"))
                      for _w, n in self._handoffs(self._graph())})
        self.assertEqual(ids, ["417", "418"])

    def test_the_adapter_only_detects_the_handoff_and_does_not_refuse_it(self):
        from src.providers import heyreach

        hazards = dict(heyreach.sequence_hazards(self._graph()))
        self.assertIn(heyreach.BISON_HANDOFF, hazards)
        self.assertEqual(sorted(hazards[heyreach.BISON_HANDOFF]),
                         ["417", "418"])

    def test_the_handoff_is_payload_required_and_not_words_required(self):
        """The exact reason the validator cannot see this: membership of
        `PAYLOAD_REQUIRED` means MUST BE WELL-FORMED, not MUST BE ABSENT."""
        from src.providers import heyreach

        self.assertIn("SEND_LEAD_TO_BISON", heyreach.PAYLOAD_REQUIRED)
        self.assertNotIn("SEND_LEAD_TO_BISON", heyreach.WORDS_REQUIRED)

    def test_the_validator_passes_an_invented_provider_id(self):
        """C6. THE DEFECT, on the real shape. If this ever goes red the
        validator has learned to ask, and that is the fix landing."""
        from src.providers import heyreach

        graph = heyreach.sequence_for_write(self._graph())
        self.assertTrue(self._handoffs(graph),
                        "sequence_for_write dropped the handoff; the premise "
                        "of this test no longer holds")
        hits = self._handoffs(graph)
        hits[0][1]["payload"] = dict(hits[0][1]["payload"] or {},
                                     bisonCampaignId=self.PLANTED)
        self.assertEqual(heyreach.validate_sequence_for_write(graph), (17, 6))

    def test_the_proposed_assertion_fails_on_the_same_input(self):
        """C6 leg 2. A proposal that cannot be shown failing is not priced."""
        from src.providers import heyreach

        graph = heyreach.sequence_for_write(self._graph())
        hits = self._handoffs(graph)
        hits[0][1]["payload"] = dict(hits[0][1]["payload"] or {},
                                     bisonCampaignId=self.PLANTED)
        bad = self.ownership_violations(graph)
        self.assertEqual(len(bad), 3)
        self.assertIn(str(self.PLANTED), [b[1] for b in bad])

    def test_the_proposed_assertion_can_also_pass(self):
        """An assertion that can only fail measures nothing."""
        import importlib.util
        import sys

        from src.providers import heyreach

        path = os.path.join(ROOT, "scripts", "batch_linkedin_push.py")
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        spec = importlib.util.spec_from_file_location("_t0241_push", path)
        push = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(push)

        stripped = heyreach.sequence_for_write(
            push.drop_bison_handoff(self._graph()))
        self.assertEqual(self._handoffs(stripped), [])
        self.assertEqual(self.ownership_violations(stripped), [])
        self.assertEqual(
            self.ownership_violations(self._graph(),
                                      allowed_ids=("417", "418")), [])

    def test_only_the_two_posting_readers_strip_the_handoff(self):
        """B6. Keyed on reaching the stripper, and the SECOND posting path is
        an INDIRECT reader a basename grep cannot see:
        `batch_linkedin_reconcile` does `import batch_linkedin_push as build`
        and calls `build.standard_graph()`."""
        stripper, wrapper = "drop_bison_handoff", "standard_graph"
        readers = {}
        for sub in ("src", "scripts", "tests"):
            for dirpath, dirnames, filenames in os.walk(
                    os.path.join(ROOT, sub)):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for name in sorted(filenames):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, "rb") as fh:
                        blob = fh.read()
                    rel = os.path.relpath(path, ROOT).replace("\\", "/")
                    if (b"productive-standard.json" in blob
                            or wrapper.encode() in blob):
                        readers[rel] = blob

        posting, stripped_names, bare = set(), set(), set()
        for rel, blob in readers.items():
            tree = ast.parse(blob, filename=rel)
            names = set()
            for node in ast.walk(tree):
                f = getattr(node, "func", None)
                if isinstance(f, ast.Attribute):
                    names.add(f.attr)
                elif isinstance(f, ast.Name):
                    names.add(f.id)
            if names & {"set_sequence", "create_campaign"}:
                posting.add(rel)
            (stripped_names if names & {stripper, wrapper}
             else bare).add(rel)

        self.assertEqual(posting, {"scripts/batch_linkedin_push.py",
                                   "scripts/batch_linkedin_reconcile.py"})
        self.assertEqual(posting - stripped_names, set())
        self.assertIn("scripts/obs2_nine.py", bare)


if __name__ == "__main__":
    unittest.main()
