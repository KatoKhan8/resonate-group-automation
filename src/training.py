"""Training pair capture from approved review files.

OPERATOR DECISION, 2026-09-25: every APPROVED review file feeds
``work/training/``; at 5,000 pairs, fine-tune Qwen 32B and rerun the blind
A/B; Sonnet then only for low confidence and the exec persona.

THIS MODULE CAPTURES. It does not fine-tune, route, or A/B. Those are later
tasks. The capture is urgent because a pair not written when the file is
approved is gone for good. Approval is the only moment the ground truth
exists, because approval is what makes the copy correct rather than merely
generated.

A pair whose file was never approved is not training data. It is a draft,
and training on drafts teaches the model to produce drafts.

WHY IT HOOKS reviewapproval.record AND NOT THE PIPELINE.

The pipeline runs whether or not the operator ever approves. The approval
is the event that makes the copy ground truth. Capturing in the pipeline
would capture drafts; capturing in ``record`` captures only what a human
read and said yes to.

HELD LEADS AS NEGATIVE EXAMPLES.

A held lead is one the facts did not support. The facts that did NOT
support a first line are as instructive as the ones that did, and they are
the cheapest thing to get wrong later. Captured separately.

DATA DISCIPLINE.

``work/`` is gitignored and this is real prospect copy. It stays local,
is not committed, and is not published. Same standing as ``queue.jsonl``.
One JSONL row per pair, append-only, never rewritten.
"""
import json
import os

from . import store

#: Target for the fine-tune. The operator watches this.
FINE_TUNE_TARGET = 5_000


def training_dir():
    """Where training data lives. Beside the queue, not in git."""
    return os.path.abspath(os.path.join(os.path.dirname(store.queue_path()),
                                        "training"))


def pair_path():
    """Approved pairs. Append-only JSONL."""
    return os.path.join(training_dir(), "pairs.jsonl")


def held_path():
    """Held leads as negative examples. Append-only JSONL."""
    return os.path.join(training_dir(), "held.jsonl")


def _ensure_dir():
    store.refuse_production_write(training_dir())
    os.makedirs(training_dir(), exist_ok=True)


def _append(path, row):
    """One row, appended atomically under the store lock.

    The lock is the same one ``reviewapproval.record`` and ``store`` use,
    so a capture cannot interleave with a queue write or an approval write.
    """
    store.refuse_production_write(path)
    _ensure_dir()
    with store.lock(for_path=path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_all(path):
    """Every row in the file. Empty list if the file does not exist."""
    try:
        return store.read_jsonl(path)
    except FileNotFoundError:
        return []


def write_pair(pair):
    """Append one approved training pair.

    A pair is a dict with at least:
      - ``review_hash``   the hash the operator approved against
      - ``campaign``      the provider campaign id
      - ``approval``      the full approval row
      - ``input``         what the writer saw (facts, angle, persona, ...)
      - ``output``        what the operator approved (subject, body, ...)

    Optional fields: ``model``, ``confidence``.
    """
    if not isinstance(pair, dict):
        raise TypeError(f"pair must be a dict, not {type(pair).__name__}")
    for required in ("review_hash", "campaign", "approval", "input", "output"):
        if required not in pair:
            raise ValueError(f"pair missing required field: {required}")
    _append(pair_path(), pair)


def write_held(pair):
    """Append one held lead as a negative example.

    Same shape as an approved pair, but the output is what was NOT approved
    and the pair carries a ``held_reason`` field.
    """
    if not isinstance(pair, dict):
        raise TypeError(f"held pair must be a dict, not {type(pair).__name__}")
    _append(held_path(), pair)


def count():
    """How many approved pairs exist. The number the operator watches."""
    return len(_read_all(pair_path()))


def held_count():
    """How many held (negative) examples exist."""
    return len(_read_all(held_path()))


def progress():
    """A summary the operator can read at a glance."""
    p = count()
    h = held_count()
    return {
        "pairs": p,
        "held": h,
        "target": FINE_TUNE_TARGET,
        "remaining": max(0, FINE_TUNE_TARGET - p),
        "pct": round(100.0 * p / FINE_TUNE_TARGET, 1) if FINE_TUNE_TARGET else 0,
    }


def capture(approval_row, pairs=None, held=None):
    """Write training data for one approval event.

    Called by ``reviewapproval.record`` after the approval is written.
    ``pairs`` is a list of approved pair dicts; ``held`` is a list of held
    example dicts. Either or both may be None or empty.

    A pair not written when the file is approved is gone for good, so this
    function refuses silently rather than raising: an approval must never
    fail because its training capture had a bad row. The row is validated
    and bad rows are skipped, but the approval itself always succeeds.
    """
    if pairs:
        for pair in pairs:
            try:
                write_pair(pair)
            except (TypeError, ValueError):
                continue
    if held:
        for pair in held:
            try:
                write_held(pair)
            except TypeError:
                continue
