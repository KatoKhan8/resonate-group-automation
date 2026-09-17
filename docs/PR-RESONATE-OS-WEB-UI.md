# Resonate OS: repository-backed web control center

The existing application exposes the operating workflows, but its shared
presentation did not provide the responsive, branded control center specified
in Figma. This change builds on those server-rendered routes and their existing
authorization and business services.

## Changes

- Introduce a dark design system, local Resonate logo, responsive navigation,
  accessible tables, status treatments, pending states and error screens.
- Connect the operator dashboard to actual qualification, job, workspace audit
  and optional reply-poller state. Keep actionable attention ahead of counts.
- Add scoped company/contact search before pagination and real batch job
  progress; retain upload preview followed by explicit commit.
- Apply the shell and shared components to the repository-backed decision,
  campaign, approval, reporting and control-plane screens. The screen/route
  mapping is in `docs/RESONATE-WEB-UI.md`.
- Keep eligibility, suppression, approval fingerprints, reply pauses and
  report redaction on the existing server. Refuse foreign/missing batch IDs
  uniformly; prevent dynamic response caching.
- Add a deterministic static-asset build and development-only browser checks.
  The application still runs on the existing Python stack.

## Validation

See `docs/RESONATE-WEB-UI-VALIDATION.md` for the exact baseline comparison,
commands, results and release limitations. New HTTP/UI integration tests cover
tenant isolation, CSRF, roles, search, escaping, assets, runtime redaction and
error states. A real-browser check covers 24 screens, detail navigation,
mobile layout, upload commit, pending states and no-JavaScript navigation.

Existing tests are retained. Three HTML-selection helpers follow the new
semantic/labelled elements. The hostile-search test parses HTML to distinguish
an inert preserved query from an actual event-handler attribute, and verifies
that the query round-trips. The static public-route contract includes only the
additional exact logo path.
The foreign-batch acceptance test now expects the hardened 404 contract for
both absent and foreign batches, retaining every record-disclosure assertion.

## Safety and release status

No Send/Launch action or production provider write is added. The existing
`push.run(live=True)` refusal remains intact. Upstream's separately guarded
provider activation and watcher paths are preserved; the console's disabled
sending indicator does not assert that external provider campaigns are idle.

This is a reviewable feature branch, not a production-readiness certification.
The upstream offline suite has existing failures; production Python 3.14 and
real deployment/auth configuration still require release verification.

Prepared against `master` at `702a04e12d1b2b2a171881806de84840853e6bfd`.
Target branch: `feat/resonate-os-web-ui`. GitHub publication is blocked by
`403 Resource not accessible by integration`; no pull request has been opened.
