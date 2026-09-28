"""Training-pair capture from approved review files.

OPERATOR DECISION, 2026-09-25: every APPROVED review file feeds
``work/training/``; at 5,000 pairs, fine-tune Qwen 32B and rerun the blind
A/B; Sonnet then only for low confidence and the exec persona.

The fine-tune is far off. The capture is urgent: a pair not written when the
file is approved is gone for good. Approval is the only moment the ground
truth exists, because approval is what makes the copy correct rather than
merely generated.

This module captures. It does not fine-tune, route, or A/B. Those are the
operator's decisions and are not licensed here.

WHAT A PAIR IS

    input   what the writer saw: the facts, the angle, the persona, the
            company hook, the lead's role - the ``lead_user`` turn
    output  what the operator APPROVED: subject, first line, bridges,
            LinkedIn messages

A pair whose file was never approved is not training data. It is a draft,
and training on drafts teaches the model to produce drafts.

WHERE IT HOOKS

``reviewapproval.record()`` calls ``capture()`` after writing the approval
row. The pipeline does not call this module; the pipeline runs whether or
not the operator ever approves, and that is exactly the distinction that
matters.

HELD LEADS

Held leads are captured separately as negative examples: the facts that did
NOT support a first line are as instructive as the ones that did.

RULES

- ``work/`` is gitignored and this is real prospect copy. It stays local.
- One JSONL row per pair, append-only, never rewritten.
"""
import json
import os

from . import store

#: Environment override so tests redirect away from the real ``work/``.
#: Listed in ``store.STATE_OVERRIDES`` so ``use_directory`` moves it.
ENV = "TRAINING"

#: File names inside the training directory.
PAIRS_FILE = "pairs.jsonl"
HELD_FILE = "held.jsonl"

#: The operator's target. A counter the operator can watch.
TARGET = 5_000


def _dir():
    """Where training files live. Resolved per call, not at import."""
    override = os.environ.get(ENV)
    if override:
        return os.path.abspath(override)
    return os.path.join(os.path.dirname(store.queue_path()), "training")


def pairs_path():
    return os.path.join(_dir(), PAIRS_FILE)


def held_path():
    return os.path.join(_dir(), HELD_FILE)


def _append(path, row):
    """Append one JSONL row under the store's lock.

    Uses the same lock discipline as ``reviewapproval.record``: the lock
    sits on the file being written, held only for the append.
    """
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with store.lock(for_path=path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_pair(pair):
    """Append one approved training pair. Returns nothing.

    A pair is a dict with at least ``input`` and ``output`` keys. The
    caller is responsible for assembling the right shape; this function
    validates that the minimum is present and appends.
    """
    if not isinstance(pair, dict):
        raise TypeError("a training pair must be a dict, got %s"
                        % type(pair).__name__)
    if "input" not in pair:
        raise ValueError("a training pair must have an 'input' key")
    if "output" not in pair:
        raise ValueError("a training pair must have an 'output' key")
    _append(pairs_path(), pair)


def write_held(pair):
    """Append one held lead as a negative example."""
    if not isinstance(pair, dict):
        raise TypeError("a held pair must be a dict, got %s"
                        % type(pair).__name__)
    _append(held_path(), pair)


def capture(pairs=None, held=None):
    """Write training data from an approval. Called by ``reviewapproval.record``.

    ``pairs`` is a list of training-pair dicts. Each must have ``input``
    and ``output`` keys. ``held`` is a list of held-lead dicts for
    negative examples.

    Either may be empty or None; nothing is written for a missing list.
    Returns the count of pairs and held rows written.
    """
    n_pairs = 0
    n_held = 0
    for pair in (pairs or []):
        write_pair(pair)
        n_pairs += 1
    for row in (held or []):
        write_held(row)
        n_held += 1
    return {"pairs": n_pairs, "held": n_held}


def _count_file(path):
    """Count non-empty lines in a JSONL file. A missing file is zero."""
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def count():
    """How many pairs and held rows exist. The acceptance command.

    Returns a dict with ``pairs``, ``held``, ``total`` and ``target``.
    """
    p = _count_file(pairs_path())
    h = _count_file(held_path())
    return {"pairs": p, "held": h, "total": p + h, "target": TARGET}


def progress():
    """Human-readable progress toward the target."""
    c = count()
    pct = (c["pairs"] / c["target"] * 100) if c["target"] else 0
    return (f"{c['pairs']}/{c['target']} pairs ({pct:.1f}%), "
            f"{c['held']} held negative examples")
