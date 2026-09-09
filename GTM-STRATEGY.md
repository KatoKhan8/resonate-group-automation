# GTM decision memory

## The question

Six months after somebody set the minimum company size to 50, the setting
is still there and the reason is not. The audit log says who changed it and
when, which is the wrong half — nobody disputes that it was changed. They
want to know whether the reason still holds.

---

## 1. It decides nothing

The most important property, and the one every test in `tests/test_gtm.py`
is built around.

Recording *"we are moving up-market to 100+ employees"* changes no
threshold, excludes no company and blocks no send. `workspaces.set_policy`
remains the only thing that changes what the machine does.

A decision store that also enforced would be a second configuration system,
quietly disagreeing with the first, and the one nobody thinks to check when
a campaign behaves oddly. So:

- `gtm.current()` says what was **decided**
- `workspaces.POLICY_KEYS` says what is **in force**
- the settings screen shows them side by side

There is a test asserting that recording a decision about
`sending.daily_email_volume` leaves the volume alone. It is the one
somebody will expect to work, and it deliberately does not.

## 2. Evidence, or an honest admission that there is none

Every decision carries a **basis**:

| | |
| --- | --- |
| `measured` | numbers from this workspace's own results |
| `research` | desk research, a source that can be pointed at |
| `client` | the client asked for it |
| `judgement` | somebody's read of it, nothing measured |

`measured` and `research` **must** say what the evidence was. Otherwise
"measured" is a word somebody picked from a dropdown.

`judgement` exists because it is frequently the true answer. A required
field with no honest option is a field that gets filled with
plausible-sounding fiction, and a decision that *looks* evidenced is worse
than one admitting it was a hunch.

The distinction a reader needs is not good decision versus bad decision. It
is **this rested on 40 replies** versus **this was somebody's instinct in
March** — because only the first can be re-examined by looking at data, and
only the second has to be argued again from scratch. The summary reports
`checkable` against `judgement` for exactly that reason.

## 3. Superseded, never edited

A decision that turned out wrong is not deleted or corrected in place. It
is superseded, and both rows stay.

"We believed X, then we learned Y" is the entire value of a decision log. A
log showing only the current belief is a configuration file with worse
ergonomics.

`supersede()` makes the only non-append write in the module, and it writes
a *link* — `superseded_by` on the old row — never a change to its text. A
decision already superseded cannot be superseded again, or the chain forks
and "what do we believe now" has two answers.

This is the retraction path `signals` does not have. See
`PRODUCT-GAPS.md` — the shape is the same, and it is built in here from the
start because append-only storage makes withdrawal a row rather than a
delete.

## 4. Settings changed with no reason recorded

The one thing here that reads the configuration at all. `unexplained()`
lists policy keys this workspace has overridden with no decision attached.

Not a fault. Most settings are left alone and most changes are obvious at
the time. They stop being obvious about six months later, which is when
somebody asks whether the reason still holds.

The demo deliberately leaves one setting unexplained. A demo where
everything is explained would teach that the list is decorative.

## 5. Who may

| | |
| --- | --- |
| Read | `operations.view` |
| Record | `workspace.manage` |

Reading is gated above the client-facing line because this is agency
reasoning *about* a client, not a summary *for* one. A viewer sees
outcomes; the argument behind the targeting is not one of them.

Recording is workspace-admin because an operator runs the machine and this
is a statement about which direction it is pointed.

## 6. Areas

Named for the question they settle rather than for the screen they appear
on, so a decision keeps its meaning when the interface changes:
targeting, channel, messaging, cadence, spend, qualification, operations.

## 7. What is not here

- **No enforcement**, by design — §1.
- **No review cadence.** Nothing asks whether a two-year-old judgement call
  is still believed. The `at` date is shown and that is all.
- **No link to outcomes.** A decision cannot yet be scored against what
  happened after it. That would need the reporting layer to slice by a
  date range a decision defines, and it does not.
