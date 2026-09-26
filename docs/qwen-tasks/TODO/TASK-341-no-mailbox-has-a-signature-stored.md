PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-341 - no mailbox has a signature stored

Found while verifying the fifty against the ten on 2026-09-26.

Every one of the 31 written leads renders, on all five email steps:

    mailbox signature
    none stored on this mailbox

That is **155 email steps with no signature**, and the ten behaves identically -
so this is not a regression in the fifty, it is an estate-wide data gap that has
been invisible because the review page renders the empty state politely.

`docs/OPERATOR-DIRECTIVES-2026-09-25.md` section 10 requires the copy engine to
test **"correct signature rendering"**. A test asserting the block renders would
pass today on an empty signature, which is the guard-that-cannot-fail shape.

## What to do

**This is an investigation and a test, not a content-authoring task. Do not write
a signature.** What a sender's signature says is the operator's and the client's
decision, and inventing one would put words nobody approved at the bottom of
every email.

1. Determine where a mailbox signature is meant to come from: the provider
   (EmailBison sender settings), a config file, or the client YAML. Name the
   canonical source, by file and field.
2. Determine whether it is **absent at the source** or **present at the source
   and lost in the pipeline.** Those are completely different defects and the
   distinction is the main deliverable. A provider read is permitted if it is a
   READ - prove from the code that it is, or report it as needing authorisation.
3. Report how many of the 154 attested mailboxes have a signature at the
   canonical source. A count, not an impression.
4. Add a test that **fails when a step renders an empty signature**, so a silent
   empty signature cannot ship again. Mark it skipped-with-reason if the operator
   has not yet decided signatures are required - but write it.

## Acceptance

1. The canonical source named, with file and field.
2. The count of mailboxes with and without a signature at that source.
3. A verdict, stated plainly: ABSENT AT SOURCE or LOST IN PIPELINE, with the
   evidence.
4. `py -3 -m unittest tests.test_a_step_never_renders_an_empty_signature -v`
5. Section 11 report with the REMOTE SHA verified.

## What this task may NOT do

- **Do not author, invent or template a signature.** Operator and client decision.
- Do not modify an active campaign or any sender configuration at the provider.
  Read only, and only if provably a read.
- Do not modify the fifty's posted files.
- Nothing sent, nothing activated.
