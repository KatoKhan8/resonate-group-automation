# The master gate refuses — control measured 2026-10-15

TASK 0010. The question was never "does a ruleset exist" but "does the server
refuse a real push". Both are now answered, and they are different
measurements.

## 1. The ruleset exists

`gh api repos/KatoKhan8/resonate-group-automation/rulesets` ->
one entry, `id 25125359`, `name master-protected`, `enforcement: active`,
created `2026-10-15T01:38:29+02:00`.

    conditions.ref_name.include  = ["~DEFAULT_BRANCH"]
    rules                        = deletion, non_fast_forward, pull_request
    bypass_actors                = []            <- EMPTY, as specified
    current_user_can_bypass      = "never"

**`~DEFAULT_BRANCH` IS NOT THE STRING `master`, AND THAT HAD TO BE CHECKED.**
The condition is a macro. `repos/.../  default_branch` is `master`, so it
resolves — but the authority for "what rules apply to this ref" is
`repos/.../rules/branches/master`, which returns the `pull_request` rule with
`ruleset_id 25125359`. That endpoint, not the ruleset body, is what was read.
Had the default branch been `main` the ruleset would have existed, read as
correct, and protected nothing.

## 2. `branches/master/protection` STILL RETURNS 404 AND THAT IS NOT A GAP

    gh api repos/.../branches/master/protection
      -> {"message":"Branch not protected","status":"404"}   exit 1

Rulesets and legacy branch protection are two systems with two endpoints.
A 404 from the legacy one is now **uninformative**, not negative. The earlier
reading of that same 404 as "nothing protects master" was correct only because
`rulesets` was `[]` at the same time. `branches/master` now reports
`"protected": true`.

## 3. The control: a real push, refused

A tree-identical empty commit built with `commit-tree` (so local `master` never
moved), parent = the remote tip, pushed over an explicit `https://` URL from
the remote-less clone. Local and remote master were both
`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` beforehand, so the push was a
fast-forward and **only protection could decline it** — a non-fast-forward
rejection would have been a confounded control.

    control commit  a273f234ce896827e87b6ac6a19aca28d5a44c99
    tree            d85cd444371b4261d64f0c00199954031341dddb  (= master's tree)
    git diff master a273f234  -> empty

Server output, verbatim:

    remote: error: GH013: Repository rule violations found for refs/heads/master.
    remote: Review all repository rules at https://github.com/KatoKhan8/resonate-group-automation/rules?ref=refs%2Fheads%2Fmaster
    remote:
    remote: - Changes must be made through a pull request.
    remote:
    To https://github.com/KatoKhan8/resonate-group-automation.git
     ! [remote rejected]     a273f234ce896827e87b6ac6a19aca28d5a44c99 -> master (push declined due to repository rule violations)
    error: failed to push some refs to 'https://github.com/KatoKhan8/resonate-group-automation.git'

    EXIT CODE 1

**The code is GH013, not GH006.** GH006 is the legacy branch-protection
refusal; GH013 is the repository-rules refusal. Same class, same effect, and a
check that greps for the literal string `GH006` will record this refusal as a
pass. Match on the exit code and on `remote rejected`, not on the code number.

**WHO REFUSED IT:** every line carries the `remote:` prefix and names the
repository's own rules page. This is the server, not git locally and not the
Claude Code permission classifier. The token used was the owner's own
(`KatoKhan8`, scopes `gist, read:org, repo, workflow`) — i.e. a push that was
fully **authorised** and still declined, which is the only version of this
control that proves anything. An auth failure would also have been non-zero.

## 4. THE OBJECT REACHED THE REMOTE. THE REF DID NOT MOVE.

    gh api repos/.../commits/a273f234...   -> 200, sha returned
    gh api repos/.../git/ref/heads/master  -> b1f290c84  (UNCHANGED)
    a273f234 is the tip of NONE of the 100 branches
    compare master...a273f234 -> ahead=1, files_changed=0

This is ordinary git: the pack is transferred and the objects written, *then*
the ref update is evaluated and declined. **A 200 from the commits endpoint is
therefore not evidence that a push landed** — it is a dangling object awaiting
GC. The authority for "did it land" is the ref, and the ref says no.

## 5. What this does and does not close

Closed: a direct push to `master` from this machine is refused by the server.
`b1f290c84` — the earlier PROBE commit that got in because `rulesets` was `[]`
— could not be created today.

Not closed, and not tested here: `deletion` and `non_fast_forward` are in the
ruleset but only `pull_request` was exercised. `required_approving_review_count`
is **0**, so a PR from the owner can be opened and merged by the owner with no
second reader. The gate enforces *route*, not review.

## 6. Two environment faults found on the way

- **`GIT_CONFIG_KEY_0=credential.helper` is set with no `GIT_CONFIG_VALUE_0`.**
  Every `git` invocation in this session died with
  `error: missing config value GIT_CONFIG_VALUE_0` / `fatal: unable to parse
  command-line config`, **exit 128, before git did anything**. Read as a repo
  fault this looks catastrophic; it is a malformed environment. Worked around
  per-command with `GIT_CONFIG_VALUE_0=''` (empty = clear the helper, which is
  the evident intent). Credentials for the push were supplied explicitly with
  `-c credential.helper='!gh auth git-credential'`, so no token appears in any
  command line, file or log.
- **`queue/_STANDING-RULES.md`, which this task opens by naming, does not
  exist.** Not in the working tree, not in `git log --all` for any
  `*STANDING-RULES*` path, and no file in the repository mentions the string.
  There is no `queue/` directory at all; the task queue is
  `docs/qwen-tasks/{TODO,RUNNING,DONE,...}`. Read instead:
  `docs/qwen-tasks/README.md`, `docs/qwen-tasks/DEFAULT-CHECKS.md`, `CLAUDE.md`.
  A dispatched worker told to read it first will either stop or invent it.

## 7. Dispatch

The condition on TASK 0010 was **"dispatch stays held until this task returns a
rejection."** It returned one: exit 1, GH013, ref unmoved. The gate condition is
met. Releasing dispatch is the operator's action, not this task's.
