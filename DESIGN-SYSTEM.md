# Design System

The visual language of Resonate Outbound OS. One place the brand is written
down, so a new screen inherits it rather than inventing a variant.

Read this before adding a component to `src/web/assets.py` or a colour to
`src/clientreport.py`.

---

## 0. Where the brand came from, and what was not available

The intended reference is the public site at **https://www.resonategroup.co/**.

**This build has no network access**, and the site was not reachable from it.
Nothing below was derived from the site's pixels. It is derived from the
brief's own description of the language to aim for - premium, editorial,
clean, confident, minimal, agency-quality - and from what an outbound
operations product needs.

When somebody can open the site alongside the app, these are the things to
check and correct here rather than on individual screens:

- the exact brand blue, and whether it is used as sparingly here as there
- the display typeface and whether the type scale below matches its rhythm
- how much white space the site gives a heading, and whether §3 is close
- whether the site's near-black is warm or cool; this product uses warm

Until then, treating any hex value below as "the Resonate blue" would be a
claim nobody has checked.

---

## 1. What this product should feel like

Resonate Group evolved into an outbound operations platform. Not a generic
admin theme, not an AI-SaaS template, not a developer console with a
stylesheet over it.

Three commitments, in order:

**Density with air.** Operators read tables of hundreds of contacts. The type
is small and the leading is generous; the page does not waste vertical space on
decoration, and it does not crush rows together to fit more of them.

**Colour means something.** Every hue in this system is semantic. Green is a
verified fact, amber is a hold, red is a block, violet is a pause, blue is
Resonate. Nothing is coloured because a card looked plain.

**An absence is stated.** The most characteristic component in this product is
`.absent` - italic, muted, and always carrying a reason. A blank cell reads as
a broken page, and "we did not look" and "we looked and found nothing" are
different facts.

---

## 2. Tokens

Defined once on `:root` in `src/web/assets.py`. A screen that needs a colour
uses a token; a screen that needs a *new* colour adds a token here first.

### Brand and surface

The ground is warm off-white, not blue-grey. The page should read as paper
with panels sitting on it, not as a dashboard floating over a gradient.

| Token | Value | Used for |
| --- | --- | --- |
| `--bg` | `#f7f7f5` | Page ground |
| `--panel` | `#fff` | Cards, tables, panels |
| `--panel-2` | `#fbfbfa` | Table headers, inset blocks |
| `--head` | `#14161a` | Sidebar, code blocks |
| `--accent` | `#1a4d8f` | Links, primary actions, the one accent |
| `--accent-deep` | `#12355f` | Pressed state |
| `--accent-soft` | `#eef3fa` | Selected rows, hover fills |
| `--line` | `#e3e3df` | Every border |

**One accent, used sparingly.** Colour is semantic in this product. A screen
that accents everything has told the reader nothing.

### Text

| Token | Value | Used for |
| --- | --- | --- |
| `--ink` | `#14161a` | Body. Warm near-black, not navy |
| `--muted` | `#6b7280` | Labels, secondary text, table headers |
| `--faint` | `#9aa1ab` | Footers, timestamps, absent values |

`.absent` (`#93a1b0`, italic) is not a token but a component - see §5.

### Status

Four states, each with a foreground and a background. They are the same four
words everywhere in the product, and `pages.KIND` maps every status string in
the system onto one of them so a status renders the same colour on every screen
it appears on.

| State | Foreground | Background | Means |
| --- | --- | --- | --- |
| pass | `--pass` `#1b6640` | `--pass-bg` `#dff2e7` | Verified, approved, confirmed |
| warn | `--warn` `#7a5300` | `--warn-bg` `#fdecc8` | Held, waiting, unknown |
| block | `--block` `#8d2020` | `--block-bg` `#fadcdc` | Blocked, invalid, failed |
| pause | `--pause` `#4b2d85` | `--pause-bg` `#e9e0fa` | Paused, cancelled |

"Unknown" is amber, not grey and not green. A missing timezone, an unknown
sending limit and an unverified address are all things somebody has to decide
about, and colouring them as neutral is how they stop being decided about.

### Channel

| Token | Value | Channel |
| --- | --- | --- |
| `--email` | `#25457e` | Email |
| `--linkedin` | `#0a66c2` | LinkedIn |
| `--both` | `#4b2d85` | Multichannel |

Semantic, not decorative: the same hue means the same channel on the cadence
view, the sender screens and the reply centre.

### Shape

| Token | Value |
| --- | --- |
| `--radius` | `6px` (controls, inputs, cards) |
| `--radius-lg` | `9px` (panels) |
| `--radius-pill` | `11px` (tags) |
| `--shadow` | `0 1px 2px rgba(16,32,53,.06)` |
| `--shadow-lift` | `0 4px 14px rgba(16,32,53,.10)` |
| `--focus` | `#4d8fe0` |

### Type

System stack - `-apple-system, "Segoe UI", Roboto, Helvetica, Arial`. No web
font: the repository takes no third-party dependencies, and a CDN font is a
third-party dependency that also fails offline.

Eight steps, as tokens, so a new screen inherits the hierarchy rather than
inventing one. The jumps are large enough to read as hierarchy rather than as
inconsistency - the previous scale had four sizes within three pixels of each
other, which is why every screen looked flat.

| Token | Size | Used for |
| --- | --- | --- |
| `--t-display` | 30px | Account name, report title |
| `--t-title` | 21px | `h1`, page title |
| `--t-section` | 16px | `h2` |
| `--t-card` | 14px | `h3`, panel headings |
| `--t-body` | 13.5px | Body |
| `--t-small` | 12px | Tables, secondary |
| `--t-caption` | 11px | `h4`, tags, labels, uppercase |
| `--t-metric` | 26px | The number on a metric card |

Weight does as much work as size: 640-660 on headings and metrics, 400 on
body. Line height is 1.2 on headings and 1.55 on body.

Numbers use `font-variant-numeric: tabular-nums` in tables and metric cards,
so columns of figures line up.

Spacing is a 4px scale: 2, 4, 6, 8, 10, 14, 18, 22, 26.

---

## 3. Layout

`.shell` is a two-column grid: a 216px sidebar and the content. The sidebar is
sticky and scrolls independently. Content lives in `.wrap`, capped at 1500px,
because a table stretched across an ultrawide monitor is unreadable.

Below 1000px the sidebar becomes a horizontal wrapped nav, `.grid2`/`.grid3`
collapse to one column, and `table.kv` becomes stacked blocks. Priority is
large desktop, then laptop, then tablet. Dense operational workflows simplify
on a phone rather than being made to fit.

---

## 4. Navigation

Seven sections, one open at a time.

**GLOBAL** aggregates across every workspace the person may enter.
**OVERVIEW, AUDIENCE, OUTREACH, INBOX, REPORTING, SETTINGS** are scoped to
the workspace they are inside. A reader should never have to guess which
they are looking at, which is why Global stays first and apart.

### Why it is sectioned

It used to be forty links under five headings, rendered at once. That is
not a menu, it is an index - and an index only helps somebody who already
knows the name of the thing they want. A person opening this product for
the first time was reading a directory.

At rest an operator now sees **nine things**: seven section labels and the
two children of the one they are in. A client-facing viewer sees five, and
the sections they cannot enter are *absent* rather than closed, because an
empty disclosure is a promise of nothing.

### How it opens

Server-rendered `<details>`, open when the current path is inside the
section. No script. That means it survives a refresh and a pasted deep
link, `/outreach/account/acme` expands Outreach without anything being
remembered, and it is keyboard-usable for free.

### `SECTIONS` is the definition; `NAV` is derived

`SECTIONS` in `src/web/pages.py` carries the hierarchy. The flat `NAV`
every invariant walks is *computed* from it, so the two cannot drift - a
test rebuilds one from the other and compares.

Each entry carries the permission the *handler* enforces; hiding a link is
a courtesy, not the control. A menu full of refusals is a bad tool, and a
menu that is the only check is a vulnerability.

### Quick actions

The dashboard leads with the handful of things somebody opens this product
to do, filtered to what the role can actually perform - a button that
refuses is worse than no button. **Import leads** is first and primary,
because it is what a new workspace needs and because it was, until this
change, the hardest screen in the product to find: it had no navigation
entry and nothing linked to it, so the only way in was to already know the
URL.

---

## 5. Components

Every one of these lives in `src/web/assets.py` and has a helper in
`src/web/pages.py`. Use the helper; do not hand-roll the markup.

| Component | Class | Helper | Notes |
| --- | --- | --- | --- |
| Metric card | `.stat` in `.stats` | `stat()`, `stats()` | Number then label. Optional state colour. |
| Panel | `.panel` | `panel()` | The default container. |
| Card grid | `.wsgrid` / `.wscard` | — | Workspace directory. |
| Table | `table`, `.scroll` | `table()` | Always inside `.scroll`; the page body never scrolls sideways. |
| Key/value | `table.kv` | `kv()`, `row()` | Stacks on narrow screens. |
| Tag | `.tag` + state | `tag()` | State comes from `KIND`, never chosen per call. |
| Disclosure | `details` / `.secbody` | `section()` | Progressive disclosure for dense dossiers. |
| Empty state | `.empty` | `empty()` | Title, one line of explanation, and the next safe action. |
| Absence | `.absent` | `unavailable()` | Always carries a reason. |
| Note | `.note`, `.note.ok`, `.note.stop` | — | Inline explanation. |
| Banner | `.banner`, `.banner.stop` | — | Page-level safety state. |
| Cadence step | `.step` + state | — | Left border carries the state colour. |
| Timeline | `.timeline` | — | `.confirmed` / `.refused` borders. |
| Cross-channel | `.xchan.ok` / `.xchan.no` | — | Whether a handoff phrase is allowed. |
| Bar | `.bar` / `.bar i` | `progress()` | Fraction only; never a fabricated percentage. |
| Buttons | `button`, `.ghost`, `.danger` | — | Primary is filled, ghost is bordered, danger is red. |
| Checkbox group | `.checks` / `.check` | — | Report sections. |
| Filters | `.filters` | — | Search and select row above a table. |
| Skeleton | `.skel` | — | Loading placeholder; respects `prefers-reduced-motion`. |

### Rules

- **Never `outline: none`.** `:focus-visible` draws a 2px `--focus` ring on
  every control. A keyboard user with no visible focus is lost, and no visual
  gain is worth that.
- **A destructive control must not look like a safe neighbour.** Delete,
  reject, suppress and reassign use `button.danger`.
- **Every empty state names the next safe action.** "No campaigns yet" is
  half a component; "No campaigns yet - create one from a segment" is the
  whole one.
- **No page-specific styling.** If a screen needs a shape that is not here,
  add it here first, with a sentence about what it means.

---

## 6. The PDF

`src/clientreport.py` carries its own palette, in PDF colour fractions, kept in
step with the tokens above by this document. It cannot import the CSS - one is
a stylesheet string and the other is `0.09 0.32 0.78 rg` - so the discipline is
that a brand change is made in both places, and this table is what says so.

| PDF constant | CSS token | Value |
| --- | --- | --- |
| `BRAND` | `--accent` (deepened for print) | `0.09, 0.32, 0.78` |
| `BRAND_DEEP` | `--head` | `0.05, 0.15, 0.40` |
| `INK` | `--ink` | `0.09, 0.11, 0.16` |
| `MUTED` | `--muted` | `0.42, 0.46, 0.55` |
| `RULE` | `--line` | `0.87, 0.89, 0.92` |
| `GOOD` / `WARN` / `BAD` | pass / warn / block | see module |

Type is Helvetica, Helvetica-Bold and Helvetica-Oblique - three of the
fourteen standard PDF fonts, so nothing is embedded and a report stays tens of
kilobytes. Three weights rather than seven is what makes it look designed.

---

## 7. Accessibility

- Contrast: body text and every status foreground on its own background clear
  WCAG AA at their rendered size. The muted grey is used for secondary text
  only, never for a value somebody has to read to make a decision.
- Focus: see §5. Every interactive control is reachable and visibly focused.
- Semantics: real `<table>`, `<th>`, `<label>`, `<button>`, `<details>`. No
  div-with-a-click-handler standing in for a control.
- Motion: the only animation is the loading skeleton, and it stops under
  `prefers-reduced-motion`.
- Tables: headers are sticky, every column has a `<th>`, and a table that
  breaks across pages in the PDF repeats its header.

Not yet done, and worth being honest about: no automated contrast audit runs
in CI, and no screen-reader pass has been performed. Both are listed in
`PRODUCTION-READINESS.md`.
