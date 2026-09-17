# Resonate OS web UI validation

Validated on 2026-09-17 against upstream
`702a04e12d1b2b2a171881806de84840853e6bfd` on branch
`feat/resonate-os-web-ui`. See `RESONATE-WEB-UI.md` for the Figma/route map
and architecture; `PR-RESONATE-OS-WEB-UI.md` is the prepared PR body.

## Environment and method

This environment provides Python 3.12.14, Node 24.19 and Playwright 1.62.1.
The repository targets Python 3.14; that interpreter was unavailable here.
Browser verification used Chromium 153 supplied outside the checkout because
the normal browser download was unavailable. No browser runtime or provider
credentials were added to the repository.

The original pre-change baseline was checked at `14354e3`. After rebasing onto
the newer upstream above, both baseline and feature suites were run again.
The final comparison uses only the newer pinned upstream, in separate
worktrees. Tests run sequentially with `tests.offline.block()` active and
loopback proxy environment variables removed. All discovered tests are split
into bounded groups at whole-module boundaries, without skipping assertions
or changing test outcomes. The delivery includes the group runner and a JSON
result summary for reproduction. This grouped execution does not prove that
a single-process run has no cross-module state interactions.

## Results

| Check | Result |
| --- | --- |
| Pinned upstream offline suite | 9,835 tests: 9,625 passed, 80 failures, 109 errors, 14 expected failures, 7 skipped |
| Feature offline suite | 9,854 tests: 9,645 passed, 79 failures, 109 errors, 14 expected failures, 7 skipped |
| Feature-only failing/error test IDs | **0** after corrections |
| New HTTP/UI integration tests | **19/19 passed** in a separate final run |
| Browser verification | **Passed**: 24 screens plus detail, mobile, upload, roles and no-JavaScript flows |
| Python compilation | **Passed**: `python -m compileall -q src tests` |
| JavaScript syntax | **Passed**: `npm run lint:web` |
| Production assets | **Passed**: three local assets and SHA-256 manifest |
| Diff whitespace | **Passed**: `git diff --check` |

No unexpected successes occurred. The initial feature pass exposed eight
additional failing/error cases. The attention-order regression was fixed and
markup/404/search test contracts were updated as described below. Groups 2,
3, 10 and 12 were then rerun; the table uses their latest results. All other
groups retain their completed full-discovery results. New tests and the real
browser flow were rerun after the final page edits.

The sole baseline-only failure is the timing-sensitive
`test_scalesim.TestLinearity.test_no_phase_grows_faster_than_the_batch`.
Its absence on the feature run is **not** attributed to this UI change.
The feature still has 188 existing failing/error cases; the full suite is
**not green**. The delivery's `validation-summary.json` lists their exact IDs.
Many concern existing provider/cadence configuration and fixture contracts;
none were bypassed to approve this change.

## Coverage and review

The 19 new tests in `tests/test_resonate_web_ui.py` cover real HTTP/session
flows, scoped search before pagination, foreign-workspace exclusions, batch
membership, CSRF refusal, client/operator separation, XSS escaping, static
allowlisting, no-store/CSP headers, safe errors, audit/poller redaction, empty
filters and reproducible build output.

The browser runner visits 24 real screens and follows existing detail links.
It checks desktop/mobile overflow, keyboard navigation, pending state, empty
search, upload preview and commit, viewer restrictions and no-JavaScript
navigation. Data comes from the existing disposable demo server. The pending
state assertion briefly prevents navigation at the form boundary; subsequent
navigation and mutations use the real server.

Three pre-existing test helpers required HTML selector updates for semantic
`main` and labelled `nav` elements; their business assertions are preserved.
An attention-order regression was corrected in the page itself. The existing
public-static-route invariant adds only the exact PNG path and retains auth
checks on other routes.
The foreign-batch acceptance test follows the new uniform 404 response and
still checks that no foreign record ID or company appears in the response.

The hostile-search test previously rejected any literal `onerror=alert(1)`
substring, including inert text inside an escaped input value. Because search
now preserves the query, the test parses HTML and asserts that no actual event
handler attributes exist and the decoded input value equals the payload. The
script-injection assertion remains. No encoding workaround was introduced to
hide a substring from a test.

The complete offline discovery includes existing held-contact, reply-pause,
campaign-fingerprint, RBAC, tenant and reporting tests. Where existing backend
tests fail, the baseline comparison documents the limitation rather than
weakening a guard to make the suite green.

The final diff keeps `src/push.py`, `src/repo.py`, `src/store.py`, workspace
authorization and web session/security modules unchanged. Added presentation
adapters read scoped records and allowlisted audit/runtime fields. Dynamic
responses are not cached. No Send/Launch control, provider write, paid call or
deployment was performed. Client reports retain their separate server
redaction boundary.

A credential-pattern scan of changed text files found no private keys,
GitHub tokens, AWS access keys or common model-provider key patterns. This is
a bounded diff review, not a comprehensive audit of repository history.

## Release limitations

- GitHub writes returned `403 Resource not accessible by integration`.
  Native push also lacked credentials. The branch and commits exist locally;
  no remote branch or PR was successfully created. A bundle and patch preserve
  the concrete changes for an authenticated checkout.
- Existing upstream test failures remain release gates. This UI change is not
  a safe basis for claiming the entire backend is production-ready.
- Python 3.14, production OIDC/proxy/session configuration, durable storage,
  backup/restore and deployment-specific operation were not validated here.
- Live provider delivery was not exercised. `push.run(live=True)` remains
  refused; upstream's separate guarded provider activation/watchers remain
  unchanged. The web console does not enable them or assert they are idle.

## Commands

```sh
python -m tests.offline
python -m compileall -q src tests
npm ci
npx playwright install chromium
npm run lint:web
npm run test:web
python -m src.web.build
git diff --check
```

For the bounded offline run, run the included `check_suite.py list` from the
checkout, then each numbered group sequentially with an output JSON path.
Remove loopback proxy variables only for that test process. The browser test
accepts `BROWSER_EXECUTABLE_PATH` and `PLAYWRIGHT_MODULE_PATH` when development
tools are already installed outside the checkout.

No TypeScript project or configured static Python type checker exists for
these changes. Python compilation and JavaScript syntax checks were run;
they are not represented as a type-check result.

## Changed files

- `DESIGN-SYSTEM.md`
- `WEB-APP.md`
- `docs/PR-RESONATE-OS-WEB-UI.md`
- `docs/RESONATE-WEB-UI-VALIDATION.md`
- `docs/RESONATE-WEB-UI.md`
- `package-lock.json`
- `package.json`
- `src/web/api.py`
- `src/web/app.py`
- `src/web/assets.py`
- `src/web/build.py`
- `src/web/pages.py`
- `src/web/static/app.css`
- `src/web/static/app.js`
- `src/web/static/resonate-logo.png`
- `tests/browser/control-center.cjs`
- `tests/test_client_dashboard.py`
- `tests/test_demo_smoke.py`
- `tests/test_tenancy_penetration.py`
- `tests/test_resonate_web_ui.py`
- `tests/test_web_invariants.py`
- `tests/test_web_acceptance.py`
- `tests/test_web_app.py`
