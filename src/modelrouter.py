#!/usr/bin/env python3
"""Central model router.  TASK-360.

The ONLY place model slugs are resolved.  Provider adapters read their
allowlists and defaults from `config/model_policy.yaml` through this
module.  No other module in `src/` carries a model slug as a string
literal - a test enforces that.

Two outcomes from `resolve(task_type)`:

1. A `RoutingDecision` with provider, model, reasoning, max_tokens,
   fallback and policy_version.  Data, not a string.
2. A `NotAModelDecision` exception, when the task_type is a
   deterministic-safety gate.  The router REFUSES to pick a model for
   something code must decide.  Section 2: LLMs reason.  Code governs.

The router does not make live model calls.  It returns data that a
caller uses to construct the right adapter.

## Provider availability

`mark_unavailable(provider)` and `mark_available(provider)` let a
caller tell the router that a provider is down.  When the primary
provider for a task is unavailable, `resolve` returns the declared
fallback.  A task with no fallback raises `NoFallbackAvailable`.

## The policy is versioned

Every `RoutingDecision` carries `policy_version`.  Observability
records it so a cost audit can trace which policy a call was made
under.  Changing the best model for a task bumps the version.
"""
import os
from collections import namedtuple

from . import clients

_POLICY = None
_POLICY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "model_policy.yaml")

RoutingDecision = namedtuple("RoutingDecision", [
    "task_type", "provider", "model", "reasoning", "max_tokens",
    "fallback", "policy_version",
])


class NotAModelDecision(Exception):
    """The router was asked to route a deterministic-safety task.

    Suppression, sending eligibility, activation, budgets, ceilings,
    schemas, identity, provenance, provider state, cadence, approval
    and production writes are decided in Python, not by a model.
    """


class UnknownTaskType(KeyError):
    """The task_type is not in the policy."""


class NoFallbackAvailable(Exception):
    """The primary provider is unavailable and no fallback is declared."""


# --------------------------------------------------------------- loading

def _load():
    """Parse config/model-policy.yaml.  Cached after first call."""
    global _POLICY
    if _POLICY is not None:
        return _POLICY
    try:
        with open(_POLICY_PATH, encoding="utf-8") as fh:
            _POLICY = clients.parse(fh.read())
    except FileNotFoundError:
        _POLICY = {}
    return _POLICY


def reload():
    """Force a re-read.  Tests call this after swapping the config."""
    global _POLICY
    _POLICY = None
    return _load()


def _policy():
    return _load()


# --------------------------------------------------------- provider state

_UNAVAILABLE = set()


def mark_unavailable(provider):
    """Tell the router a provider is down.  Fallbacks will be used."""
    _UNAVAILABLE.add(provider)


def mark_available(provider):
    """Clear a previous mark_unavailable."""
    _UNAVAILABLE.discard(provider)


def is_available(provider):
    return provider not in _UNAVAILABLE


def reset_availability():
    """Clear all availability marks.  Tests call this."""
    _UNAVAILABLE.clear()


# --------------------------------------------------------- policy access

def version():
    """The policy version.  Every RoutingDecision carries this."""
    return _policy().get("version", 0)


def task_types():
    """The known task_types as a dict."""
    return dict((_policy().get("task_types") or {}))


def deterministic_safety_tasks():
    """The task_types the router REFUSES."""
    return list(_policy().get("deterministic_safety") or [])


def providers():
    """The provider catalog."""
    return dict(_policy().get("providers") or {})


def provider_config(provider):
    """One provider's config, or None."""
    return (_policy().get("providers") or {}).get(provider)


def default_model(provider):
    """The default model for a provider."""
    cfg = provider_config(provider)
    if not cfg:
        return None
    return cfg.get("default")


def provider_models(provider):
    """The model catalog for a provider, as a tuple of model ids."""
    cfg = provider_config(provider)
    if not cfg:
        return ()
    models = cfg.get("models")
    if not isinstance(models, dict):
        return ()
    return tuple(models.keys())


def provider_serves(provider):
    """The serves remap for a provider, or None if not declared."""
    cfg = provider_config(provider)
    if not cfg:
        return None
    serves = cfg.get("serves")
    if not isinstance(serves, dict):
        return None
    return dict(serves)


def all_slugs():
    """Every model slug in the policy, as a set.

    The slug test reads this to know what to look for in `src/`.
    """
    slugs = set()
    for prov_cfg in (_policy().get("providers") or {}).values():
        if not isinstance(prov_cfg, dict):
            continue
        for model_id in (prov_cfg.get("models") or {}):
            slugs.add(model_id)
        for served in (prov_cfg.get("serves") or {}).values():
            slugs.add(served)
    for task_cfg in (_policy().get("task_types") or {}).values():
        if not isinstance(task_cfg, dict):
            continue
        m = task_cfg.get("model")
        if m:
            slugs.add(m)
        fb_model = task_cfg.get("fallback_model")
        if fb_model:
            slugs.add(fb_model)
    return slugs


# ------------------------------------------------------------- resolving

def resolve(task_type):
    """Resolve a task_type to a RoutingDecision.

    Raises
    ------
    NotAModelDecision
        The task_type is a deterministic-safety gate.  Code decides,
        not a model.
    UnknownTaskType
        The task_type is not in the policy.
    NoFallbackAvailable
        The primary provider is unavailable and no fallback exists.
    """
    if task_type in deterministic_safety_tasks():
        raise NotAModelDecision(
            f"{task_type!r} is a deterministic-safety decision.  "
            f"Code governs, not a model.  The router refuses to pick one.")

    tasks = task_types()
    if task_type not in tasks:
        raise UnknownTaskType(
            f"{task_type!r} is not in the model policy.  "
            f"Known: {', '.join(sorted(tasks))}")

    entry = tasks[task_type]
    if not isinstance(entry, dict):
        raise UnknownTaskType(
            f"policy entry for {task_type!r} is not a mapping")

    primary_provider = entry.get("provider", "")
    primary_model = entry.get("model", "")
    fb_provider = entry.get("fallback_provider")
    fb_model = entry.get("fallback_model")

    if _UNAVAILABLE and primary_provider in _UNAVAILABLE:
        if not fb_provider or not fb_model:
            raise NoFallbackAvailable(
                f"provider {primary_provider!r} is unavailable and "
                f"{task_type!r} declares no fallback")
        return RoutingDecision(
            task_type=task_type,
            provider=fb_provider,
            model=fb_model,
            reasoning=entry.get("reasoning", ""),
            max_tokens=int(entry.get("max_tokens") or 0),
            fallback=None,
            policy_version=version(),
        )

    fallback_decision = None
    if fb_provider and fb_model:
        fallback_decision = RoutingDecision(
            task_type=task_type,
            provider=fb_provider,
            model=fb_model,
            reasoning=entry.get("reasoning", ""),
            max_tokens=int(entry.get("max_tokens") or 0),
            fallback=None,
            policy_version=version(),
        )

    return RoutingDecision(
        task_type=task_type,
        provider=primary_provider,
        model=primary_model,
        reasoning=entry.get("reasoning", ""),
        max_tokens=int(entry.get("max_tokens") or 0),
        fallback=fallback_decision,
        policy_version=version(),
    )
