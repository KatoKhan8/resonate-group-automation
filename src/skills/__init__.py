"""Skill loader and registry.

A skill is an executable SOP: it wraps an existing stage prompt, declares
which pipeline stage consumes it, and carries the validation, examples and
output schema that make the stage testable.

The audit found modules nobody reads. A skill with no consumer is the same
disease. This registry refuses it: ``registry()`` raises if any registered
skill has an empty consumer, and the test asserts it on every run.
"""
import dataclasses
import importlib
from typing import Any, Dict, List, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class Skill:
    name: str
    purpose: str
    inputs: Tuple[str, ...]
    secondbrain_sections: Tuple[str, ...]
    approved_tools: Tuple[str, ...]
    procedure: str
    examples_good: Tuple[Dict[str, Any], ...]
    examples_bad: Tuple[Dict[str, Any], ...]
    validation: Tuple[str, ...]
    output_schema: Dict[str, Any]
    failure_handling: str
    escalation: str
    consumer: str


_REGISTRY: Dict[str, Skill] = {}

_SKILL_MODULES = (
    "signal_verification",
    "account_research",
    "campaign_strategy",
    "cold_email_writing",
    "linkedin_writing",
)


def _register(skill: Skill) -> None:
    if not skill.consumer:
        raise ValueError(
            "skill %r has no consumer — a skill with no consumer is "
            "documentation, not a stage" % skill.name
        )
    _REGISTRY[skill.name] = skill


def _load_all() -> None:
    if _REGISTRY:
        return
    for mod_name in _SKILL_MODULES:
        mod = importlib.import_module(
            ".%s" % mod_name, package=__name__
        )
        skill = getattr(mod, "SKILL", None)
        if skill is None:
            raise ImportError(
                "skill module %r defines no SKILL" % mod_name
            )
        _register(skill)


def load(name: str) -> Skill:
    _load_all()
    if name not in _REGISTRY:
        raise KeyError("unknown skill %r; known: %s"
                       % (name, sorted(_REGISTRY)))
    return _REGISTRY[name]


def registry() -> Dict[str, Skill]:
    _load_all()
    without_consumer = [n for n, s in _REGISTRY.items() if not s.consumer]
    if without_consumer:
        raise RuntimeError(
            "skills with no consumer: %s — the audit found modules nobody "
            "reads; a skill with no consumer is the next one"
            % ", ".join(sorted(without_consumer))
        )
    return dict(_REGISTRY)
