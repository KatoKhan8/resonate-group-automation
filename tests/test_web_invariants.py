"""Structural rules for the web layer, checked against the source itself.

The web application is allowed to render, route and refuse. It is not allowed
to *decide*. Every verdict on every screen must come from the same function the
CLI calls, because a UI that re-derives "is this sendable" has invented a second
answer to a question with one right answer - and the second one is the one
nobody tests.

These tests read the source rather than the behaviour, which is the only way to
state a rule that must hold for code nobody has written yet.
"""
import ast
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "src", "web")

# The functions that decide something. A page that calls one of these has
# started making its own rulings.
DECISION_CALLS = {
    "score", "classify", "decide", "resolve", "evaluate", "apply_to_record",
    "check_step", "report", "payloads", "build", "run", "for_domain",
    "qualify_scale", "approve_record", "simulate",
}

# Modules a page may not import at all. Rendering does not need the engine.
FORBIDDEN_IN_PAGES = {
    "icp", "segments", "channels", "verification", "mx", "lint", "qa", "push",
    "cadence", "qualify", "approve", "orchestrator", "store", "campaigns",
    "repo", "jobs", "explorer", "dmplan", "report", "scalesim",
    # `hygiene` decides what a lead's history means. The template renders
    # the labels it is handed and does not look any of them up.
    "hygiene", "accountpolicy", "agencydnc", "priority", "signals",
    # The pack is assembled in `api` and rendered here. A template that
    # could build one could also decide what it says.
    "contextpack", "playbooks",
}


def source(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def tree(name):
    return ast.parse(source(name))


def imported_modules(node):
    found = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Import):
            found.update(a.name.split(".")[0] for a in item.names)
        elif isinstance(item, ast.ImportFrom):
            found.update(a.name.split(".")[0] for a in item.names)
            if item.module:
                found.add(item.module.split(".")[-1])
    return found


def called_names(node):
    names = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        if isinstance(func, ast.Attribute):
            names.append(func.attr)
        elif isinstance(func, ast.Name):
            names.append(func.id)
    return names


class NoBusinessLogicInTheFrontend(unittest.TestCase):

    def test_pages_import_no_engine_module(self):
        """`pages.py` renders. It does not know what a channel verdict is."""
        found = imported_modules(tree("pages.py")) & FORBIDDEN_IN_PAGES
        self.assertEqual(sorted(found), [],
                         f"pages.py imports engine modules: {sorted(found)}")

    def test_pages_call_no_decision_function(self):
        called = set(called_names(tree("pages.py")))
        # `build`, `report` and `run` are common English words; only flag them
        # when they arrive as an attribute on an engine module, which the
        # import check above already forbids. What is left to check is that no
        # decision name is called bare.
        overlap = called & {"score", "evaluate", "check_step", "payloads",
                            "classify", "resolve"}
        self.assertEqual(sorted(overlap), [])

    def test_the_service_layer_is_where_the_engine_is_called(self):
        """And it calls the real thing, not a copy of it.

        The list is the point: if somebody removes `verification.resolve` from
        `api.py` and computes a confirmation count in a template instead, this
        fails.
        """
        text = source("api.py")
        for call in ("icp.score", "segments.classify", "channels.evaluate",
                     "verification.resolve", "verification.decide",
                     "lint.check_step", "qa.report", "push.payloads",
                     "cadence.build", "mx.stored_decision", "qualify.dossier",
                     "report.funnel_for", "scalesim.qualify_scale"):
            self.assertIn(call, text, f"api.py no longer calls {call}")

    def test_no_page_writes_to_the_store(self):
        for name in ("pages.py", "assets.py"):
            text = source(name)
            for forbidden in ("store.save", "store.load", "open(",
                              "campaign_store"):
                self.assertNotIn(forbidden, text, f"{name} touches state")


class TheHandlerCannotForget(unittest.TestCase):

    def test_every_read_route_has_a_permission(self):
        """A route that answers 200 with no entry in the table is a hole.

        The table is checked before the handler runs, so the way to add an
        unprotected surface is to add a route and forget the table. This test
        is what makes that a build failure rather than a discovery.
        """
        from src.web import app

        text = source("app.py")
        routes = set()
        for match in __import__("re").finditer(
                r'path == "(/[a-z0-9/._-]*)"', text):
            routes.add(match.group(1))
        # Surfaces that legitimately need only a session, plus the ones that
        # need none at all. `/admin` and everything under it is the third
        # kind: guarded by `_require_super_admin` rather than by a workspace
        # permission, because no workspace permission can express "may read
        # every workspace at once". `test_every_admin_route_is_super_admin`
        # below is what keeps that exemption honest.
        exempt = {"/login", "/logout", "/healthz", "/assets/app.css",
                  "/assets/app.js", "/workspaces", "/admin", "/admin/slack",
                  "/admin/health",
                  # The sign-in flow itself, and a fourth kind of exemption:
                  # these run *before* anybody is anybody, so there is no
                  # membership to check a permission against. What keeps
                  # this one honest is `tests/test_production_auth.py`,
                  # which proves both routes 404 when no provider is
                  # configured, refuse a callback whose state this process
                  # did not mint, and issue no session for an address the
                  # roster does not carry however perfectly it was proved.
                  "/auth/start", "/auth/callback",
                  "/select-workspace", "/upload/commit", "/approvals/campaign",
                  "/users/add", "/users/role",
                  # Adding a workspace is the same third kind as `/admin`:
                  # it is not an action inside a workspace, so no workspace
                  # permission can express it. Guarded by
                  # `_require_super_admin`, and
                  # `test_creating_a_workspace_is_super_admin_only` below is
                  # what keeps this one honest.
                  "/workspaces/create"}
        missing = sorted(r for r in routes
                         if r not in exempt and app.permission_for(r) is None)
        self.assertEqual(missing, [],
                         f"routes with no permission: {missing}")

    def test_no_request_path_reaches_an_unscoped_repo(self):
        """`repo.py` says this test exists. Until now it did not.

        `admin_repo()` returns a `Repo` with no client and no workspace -
        every record, every campaign, every tenant. It is deliberate and
        it is for the CLI and for cross-client reporting. One call from a
        request handler would be a tenancy boundary undone by an import,
        and the docstring promising this check was the only thing standing
        between that and nobody noticing.

        Asserted on the import graph and the call graph rather than by
        searching for a word: a comment mentioning `admin_repo` should not
        fail a build, and a call spelled `repo_module.admin_repo()` should.
        """
        called = []
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".py"):
                continue
            for node in ast.walk(tree(name)):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute) and                         func.attr == "admin_repo":
                    called.append(f"{name}:{node.lineno}")
                elif isinstance(func, ast.Name) and func.id == "admin_repo":
                    called.append(f"{name}:{node.lineno}")
        self.assertEqual(called, [],
                         f"the web layer called admin_repo at: {called}")

    def test_every_prefix_route_has_a_permission_too(self):
        """The class of route most likely to carry an id from a URL.

        The test above regexes `path == "literal"` and so never saw a
        `path.startswith(...)` branch - which is exactly where a record id,
        a campaign id or a contact key arrives from the address bar. All of
        them resolve today; nothing was making that a build failure.
        """
        from src.web import app

        prefixes = sorted({m.group(1) for m in __import__("re").finditer(
            r'path\.startswith\("(/[a-z0-9/._-]*)"\)', source("app.py"))})
        self.assertTrue(prefixes, "no prefix routes found - has the "
                                  "dispatcher changed shape?")
        missing = [p for p in prefixes
                   if app.permission_for(p + "x") is None]
        self.assertEqual(missing, [],
                         f"prefix routes with no permission: {missing}")

    def test_the_routes_dispatched_from_a_constant_are_accounted_for(self):
        """A path that never appears as a literal is invisible to both
        tests above and to their list of deliberate exceptions.

        `/slack/interactions` is the one, and it is not session-guarded at
        all: it is authenticated by Slack's own HMAC, above the session
        gate. That is a real answer and it should be written down here
        rather than discovered by somebody grepping for the path.
        """
        from src.providers import slack
        from src.web import app

        self.assertEqual(app.SLACK_INTERACTIONS_PATH, "/slack/interactions")
        self.assertIsNone(app.permission_for(app.SLACK_INTERACTIONS_PATH),
                          "if this grew a permission, this test is the "
                          "wrong place to say so")
        self.assertIn("slack.verify(", source("../interactions.py"),
                      "the signature check is what stands in for a session "
                      "on this route")
        self.assertTrue(hasattr(slack, "verify"))

    def test_no_markup_is_passed_where_a_label_is_expected(self):
        """`row()` escapes its label. Markup there prints as source.

        Found on the account screen, which showed
        `<span class="chan email"></span>email` to an operator. The label
        half of a key/value row is text by design - `raw=True` governs the
        value - so a helper that returns markup belongs on the right.
        """
        parsed = ast.parse(source("pages.py"))
        markup = {"tag", "link", "external", "unavailable", "progress",
                  "_channel", "_state", "_severity_tag", "_destination_tag"}
        offenders = []
        for node in ast.walk(parsed):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "row"
                    and node.args):
                continue
            first = node.args[0]
            if (isinstance(first, ast.Call)
                    and isinstance(first.func, ast.Name)
                    and first.func.id in markup):
                offenders.append(
                    f"line {node.lineno}: row() label is {first.func.id}(), "
                    f"which returns markup")
        self.assertEqual(sorted(set(offenders)), [],
                         chr(10).join(sorted(set(offenders))))

    def test_no_code_chip_is_rendered_from_a_value_that_may_be_empty(self):
        """`<code>{x or ""}</code>` draws a small grey box for nothing.

        On the approvals and plan-review screens that box sat where a
        fingerprint or a step key belonged, and it reads as a rendering
        fault rather than as an absence. The idiom is to render the chip
        only when there is something to put in it - or `unavailable()`,
        which says what is missing.
        """
        text = source("pages.py")
        offenders = [line.strip() for line in text.splitlines()
                     if "<code>" in line and ' or ""' in line]
        self.assertEqual(offenders, [], chr(10).join(offenders))

    def test_no_page_shadows_a_helper_it_then_calls(self):
        """A loop variable named `row` breaks the next `row()` call.

        This has now happened twice in `pages.py`, both times as a 500 on a
        screen nobody had a test for, and both times the traceback said
        "'dict' object is not callable" with no hint of which name.

        The check is deliberately narrow: shadowing a helper is only a bug if
        the helper is *called afterwards in the same function*. A loop over
        `for section in ...` that never calls `section()` again is harmless,
        and failing on it would force cosmetic renames that teach nobody
        anything.
        """
        parsed = ast.parse(source("pages.py"))
        helpers = {n.name for n in parsed.body
                   if isinstance(n, ast.FunctionDef)}

        def bound(node):
            found = []
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assign):
                    found += [(t.id, t.lineno) for t in inner.targets
                              if isinstance(t, ast.Name)]
                elif isinstance(inner, (ast.For, ast.comprehension)):
                    target = inner.target
                    if isinstance(target, ast.Name):
                        found.append((target.id,
                                      getattr(inner, "lineno",
                                              target.lineno)))
            return found

        offenders = []
        for node in parsed.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            shadows = {name: line for name, line in bound(node)
                       if name in helpers}
            if not shadows:
                continue
            for call in ast.walk(node):
                if not (isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name)):
                    continue
                name = call.func.id
                if name in shadows and call.lineno > shadows[name]:
                    offenders.append(
                        f"{node.name}: {name}() at line {call.lineno} is "
                        f"shadowed by a local bound at line {shadows[name]}")
        self.assertEqual(sorted(set(offenders)), [],
                         chr(10).join(sorted(set(offenders))))

    def test_no_module_defines_the_same_name_twice(self):
        """A shadowed helper is silent until the first caller crashes.

        `pages.py` is four thousand lines. A second `_health_tag` defined
        near the bottom replaced the one near the top, and every screen using
        the original broke - with a TypeError about dict keys, five hundred
        lines from either definition. Python will not warn about this, so
        this does.
        """
        import glob

        offenders = []
        for path in sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.py"),
                                     recursive=True)):
            with open(path, encoding="utf-8") as f:
                parsed = ast.parse(f.read())
            seen = {}
            for node in parsed.body:
                if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    continue
                if node.name in seen:
                    offenders.append(
                        f"{os.path.relpath(path, ROOT)}: {node.name} "
                        f"redefined at line {node.lineno} "
                        f"(first at {seen[node.name]})")
                seen[node.name] = node.lineno
        self.assertEqual(offenders, [], chr(10).join(offenders))

    def test_every_admin_route_is_super_admin(self):
        """An `/admin` route exempt from the table must earn the exemption.

        The exemption above is granted by path prefix. Without this, adding
        `/admin/anything` would silently opt a new unscoped surface out of the
        permission table - which is exactly the hole the table exists to
        close.
        """
        import re as _re

        text = source("app.py")
        for match in _re.finditer(r'if path == "(/admin[a-z0-9/._-]*)":',
                                  text):
            after = text[match.end():match.end() + 400]
            self.assertIn("_require_super_admin(session)", after,
                          f"{match.group(1)} is not super-admin guarded")

    def test_creating_a_workspace_is_super_admin_only(self):
        """The exemption above, earned in the source rather than assumed.

        A workspace permission cannot express "may add a workspace" - a
        workspace admin runs their own client and must not be able to add
        somebody else's - so this route is guarded the way `/admin` is, and
        this is what stops that guard being quietly dropped.
        """
        import re as _re

        text = source("app.py")
        match = _re.search(r'if path == "/workspaces/create":', text)
        self.assertIsNotNone(match, "the route moved or was renamed")
        after = text[match.end():match.end() + 400]
        self.assertIn("_require_super_admin(session)", after)

    def test_every_post_route_reaches_a_permission_check(self):
        """A write endpoint that forgets to ask is a hole the menu hides.

        `permission_for` runs on the read side only, so a POST route is
        guarded by whatever it does itself. `/upload` did not, and the
        result was an oracle: a viewer could post a CSV of domains and
        read back how many were suppressed or already known - workspace
        history, for the one role that may not see contacts.

        Two ways to satisfy this, and both are real guards rather than
        spellings of one:

          `security.require(...)` in the handler, or
          an `api.*` call whose own body asks `repo.require(...)`

        `/select-workspace` is the single exemption, and it is not an
        unguarded route: it is guarded by membership rather than by
        permission, because choosing a workspace is what a member does
        before any permission in that workspace means anything.
        """
        import re as _re

        text = source("app.py")
        start = text.index(
            "    def _post(self, path, fields, files, token, session):")
        rest = text[start + 10:]
        after = _re.search(r"\n    def \w+\(", rest)
        body = text[start:start + 10 + (after.start() if after
                                        else len(rest))]

        api_text = source("api.py")
        asks = set()
        for match in _re.finditer(r"\ndef (\w+)\(", api_text):
            nxt = _re.search(r"\ndef \w+\(", api_text[match.end():])
            fn = api_text[match.end():match.end()
                          + (nxt.start() if nxt else len(api_text))]
            if _re.search(r"\.require\(", fn):
                asks.add(match.group(1))

        marks = [(m.start(), m.group(1)) for m in _re.finditer(
            r'if path (?:==|\.startswith\()\s*"([^"]+)"', body)]
        self.assertGreater(len(marks), 15, "the POST block was not found")

        for i, (at, path) in enumerate(marks):
            if path == "/select-workspace":
                continue
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(body)
            block = body[at:stop]
            called = set(_re.findall(r"api\.(\w+)\(", block))
            guarded = ("security.require(" in block
                       or "_require_super_admin(" in block
                       or bool(called & asks))
            self.assertTrue(
                guarded,
                f"POST {path} reaches no permission check: add "
                f"security.require(...) to the handler, or call an api "
                f"function that asks repo.require(...)")

    def test_the_upload_preview_is_not_a_way_round_the_upload_permission(self):
        """The specific hole above, named so it cannot come back quietly.

        Parsing a CSV reads this workspace's records to answer "have we
        seen these before". That is the read the permission exists to
        gate, and it happens on the POST whether or not anything is
        committed afterwards.
        """
        text = source("app.py")
        # Anchored on the two route lines rather than on anything written
        # between them. The guard is the claim; a reworded comment should
        # be able neither to fail this nor to satisfy it.
        start = text.index('        if path == "/upload":\n')
        stop = text.index('        if path == "/upload/commit":')
        self.assertLess(start, stop)
        self.assertIn("security.require(session, workspaces.BATCH_CREATE)",
                      text[start:stop])

    def test_every_permission_named_in_the_table_exists(self):
        from src import workspaces
        from src.web import app
        for _, permission in app.READ_PERMISSIONS:
            self.assertIn(permission, workspaces.PERMISSIONS)

    def test_every_nav_permission_exists(self):
        from src import workspaces
        from src.web import pages
        for href, label, permission in pages.NAV:
            if permission in (None, "__super_admin__"):
                continue
            self.assertIn(permission, workspaces.PERMISSIONS,
                          f"{href} names an unknown permission")

    def test_the_nav_and_the_table_agree(self):
        """A link a role can see must lead somewhere that role may go.

        Not the other way round - a route may be stricter than its link is
        absent - but a *visible* link that returns 403 is a bug the nav check
        is supposed to prevent.
        """
        from src.web import app, pages
        for href, label, permission in pages.NAV:
            if not href or permission in (None, "__super_admin__"):
                continue
            needed = app.permission_for(href)
            if needed is None:
                continue
            self.assertEqual(
                permission, needed,
                f"{href}: nav shows it to {permission}, handler wants {needed}")


    def test_exactly_one_nav_item_is_current_and_it_is_the_specific_one(self):
        """Two lit items tell a reader they are in two places at once.

        Any-prefix-wins lit "Replies" and "Reply policy" together, and
        "Outreach preview" alongside "Accounts". A sub-page with no entry of
        its own still lights its section; a section whose child has its own
        entry does not steal it.
        """
        from src.web import pages
        hrefs = [h for h, _, _ in pages.NAV if h]
        for path, expected in (("/replies/policy", "/replies/policy"),
                               ("/replies", "/replies"),
                               ("/outreach/accounts", "/outreach/accounts"),
                               ("/outreach/contact/a/b", "/outreach"),
                               ("/campaigns/new", "/campaigns/new"),
                               ("/campaigns/c1", "/campaigns"),
                               ("/reporting/senders", "/reporting/senders"),
                               ("/", "/"),
                               ("/nowhere", None)):
            self.assertEqual(pages._current_nav(path, hrefs), expected, path)

    def test_no_nav_href_is_a_non_boundary_prefix_of_another(self):
        """`/rep` matching `/reporting` would light the wrong section."""
        hrefs = [h for h, _, _ in __import__(
            "src.web.pages", fromlist=["pages"]).NAV if h and h != "/"]
        for a in hrefs:
            for b in hrefs:
                if a != b and b.startswith(a) and not b.startswith(
                        a.rstrip("/") + "/"):
                    self.fail(f"{a} is a mid-segment prefix of {b}")



class TheNavigationIsSectioned(unittest.TestCase):
    """Forty flat links was an index, not a menu. An index is what you
    reach for when you already know the name of the thing you want."""

    def sections(self):
        from src.web import pages
        return pages.SECTIONS

    def test_the_flat_view_is_derived_from_the_sections(self):
        """`NAV` is what every other invariant walks. Maintaining it beside
        `SECTIONS` would let the two disagree, and the disagreement would
        be invisible."""
        from src.web import pages
        rebuilt = tuple(
            item
            for _, label, _, children in pages.SECTIONS
            for item in (("", label, None),) + tuple(children))
        self.assertEqual(pages.NAV, rebuilt)

    def test_every_section_has_a_key_a_label_and_children(self):
        for key, label, own, children in self.sections():
            self.assertTrue(key, label)
            self.assertTrue(label)
            self.assertTrue(children, f"{key} has no children")

    def test_no_section_is_larger_than_a_person_can_scan(self):
        """The point of the exercise. A section with eighteen children is
        the old problem wearing a disclosure triangle."""
        for key, _, _, children in self.sections():
            self.assertLessEqual(len(children), 9, key)

    def test_every_href_appears_in_exactly_one_section(self):
        seen = {}
        for key, _, _, children in self.sections():
            for href, _, _ in children:
                self.assertNotIn(href, seen,
                                 f"{href} is in {seen.get(href)} and {key}")
                seen[href] = key

    def test_the_import_screen_is_reachable_from_the_navigation(self):
        """It was not. `/upload` had no entry and nothing linked to it, so
        the only way in was to know the URL - which makes the core workflow
        of the product undiscoverable."""
        from src.web import pages
        self.assertIn("/upload", [h for h, _, _ in pages.NAV])

    def test_the_import_entry_is_named_for_what_a_gtm_operator_calls_it(self):
        from src.web import pages
        label = [l for h, l, _ in pages.NAV if h == "/upload"][0]
        self.assertIn("import", label.lower())

    def test_global_is_kept_apart_from_the_workspace_sections(self):
        """Everything under Global aggregates across workspaces and
        everything else is scoped to one. A reader should not have to
        guess which they are looking at."""
        keys = [key for key, _, _, _ in self.sections()]
        self.assertEqual(keys[0], "global")


class TheSidebarShowsOneSectionAtATime(unittest.TestCase):

    def shell_for(self, path, permissions, super_admin=False):
        from src.web import pages
        ctx = {"permissions": list(permissions), "super_admin": super_admin,
               "workspace": "productive", "workspaces": [],
               "csrf": "t", "demo": True, "live_sending": False}
        session = {"email": "op@x.test", "csrf": "t"}
        return pages.shell("<p>body</p>", session, ctx, path=path)

    def sections_in(self, html):
        import re as _re
        return _re.findall(
            r'<details class="navsec"( open)?><summary>([^<]+)</summary>',
            html)

    ALL = ("workspace.view", "operations.view", "contacts.view",
           "campaign.create", "batch.create", "approvals.review",
           "replies.view", "reporting.view", "users.manage")

    def test_only_the_section_you_are_in_is_open(self):
        found = self.sections_in(self.shell_for("/campaigns", self.ALL))
        opened = [label for is_open, label in found if is_open]
        self.assertEqual(opened, ["Outreach"])

    def test_a_nested_url_expands_its_section(self):
        """/outreach/account/acme is Outreach, without anybody storing
        that it should be."""
        found = self.sections_in(
            self.shell_for("/outreach/account/acme", self.ALL))
        self.assertEqual([l for o, l in found if o], ["Outreach"])

    def test_the_import_screen_expands_audience(self):
        found = self.sections_in(self.shell_for("/upload", self.ALL))
        self.assertEqual([l for o, l in found if o], ["Audience"])

    def test_a_section_with_nothing_permitted_is_absent_not_empty(self):
        """An empty disclosure is a promise of nothing."""
        found = self.sections_in(
            self.shell_for("/", ("workspace.view", "reporting.view")))
        labels = [label for _, label in found]
        self.assertNotIn("Outreach", labels)
        self.assertNotIn("Settings", labels)
        self.assertIn("Reporting", labels)

    def test_a_client_facing_role_sees_a_short_sidebar(self):
        found = self.sections_in(
            self.shell_for("/", ("workspace.view", "reporting.view")))
        self.assertLessEqual(len(found), 3)

    def test_exactly_one_link_is_current(self):
        import re as _re
        html = self.shell_for("/replies/policy", self.ALL)
        current = _re.findall(r'<a class="on" href="([^"]+)"', html)
        self.assertEqual(current, ["/replies/policy"])

    def test_the_disclosure_needs_no_script(self):
        """Server-rendered `<details>`: it survives a refresh, a pasted
        deep link and a browser with script disabled."""
        html = self.shell_for("/campaigns", self.ALL)
        self.assertIn("<details class=\"navsec\"", html)
        self.assertNotIn("<script", html.split("<nav")[-1].split("</nav>")[0]
                         if "<nav" in html else "")


class TheDashboardOffersTheActionsARoleCanTake(unittest.TestCase):

    def test_an_operator_is_offered_the_import(self):
        from src.web import pages
        html = pages.quick_actions({"batch.create", "campaign.create"})
        self.assertIn("Import leads", html)
        self.assertIn("/upload", html)

    def test_the_import_is_the_primary_action(self):
        """It is what a new workspace needs and what was hardest to find."""
        from src.web import pages
        html = pages.quick_actions({"batch.create"})
        self.assertIn('class="quick primary"', html)

    def test_an_action_a_role_cannot_take_is_not_offered(self):
        """A button that refuses is worse than no button."""
        from src.web import pages
        html = pages.quick_actions({"reporting.view"})
        self.assertNotIn("/upload", html)
        self.assertNotIn("/campaigns/new", html)

    def test_a_role_with_nothing_to_do_gets_no_empty_row(self):
        from src.web import pages
        self.assertEqual(pages.quick_actions(set()), "")


class NothingSends(unittest.TestCase):

    def test_no_web_module_calls_a_provider_transport(self):
        """Read as code, not as text.

        `pages.py` explains in prose that `push.run(live=True)` raises, which
        is exactly the kind of sentence a module that must not send should
        contain. A text match would forbid the explanation along with the act,
        so this walks the tree and looks at calls.
        """
        forbidden = {("push", "run"), ("transport", "request"),
                     ("urllib", "urlopen"), ("requests", "get"),
                     ("requests", "post")}
        offenders = []
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".py"):
                continue
            for node in ast.walk(tree(name)):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and (func.value.id, func.attr) in forbidden):
                    offenders.append(f"{name}: {func.value.id}.{func.attr}")
                if isinstance(func, ast.Name) and func.id == "urlopen":
                    offenders.append(f"{name}: urlopen")
        self.assertEqual(offenders, [])

    def test_the_health_endpoint_states_sending_is_off(self):
        self.assertIn('"live_sending": False', source("app.py"))
