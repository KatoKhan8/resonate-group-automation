"""The Resonate Outbound Control Center: the engine, through a browser.

Four modules, and the split between them is the architectural invariant:

    app.py      HTTP. Routing, sessions, CSRF, status codes. No decisions.
    api.py      The service layer. Arguments in, plain data out.
    pages.py    HTML. Rendering only; it is handed data and escapes it.
    assets.py   CSS and a little JavaScript, as strings.

**No business rule lives here.** Every verdict on every screen came out of the
same function the CLI and the tests call: `icp.score`, `verification.decide`,
`mx.allows_email`, `channels.evaluate`, `eligibility.decide`, `lint.check_step`,
`qa.report`, `push.payloads`. The browser displays decisions and is never
authoritative for one - `tests/test_web_invariants.py` asserts that by walking
this package's own source.

Stdlib only, like the rest of the repository. `http.server` and hand-written
HTML rather than a framework and a build step, because a zero-dependency tree
is a property this codebase already has and is worth more than a router.
"""
