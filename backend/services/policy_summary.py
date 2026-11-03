"""Policy summarisation for notifications and rationales.

Parses the STORED IAM policy dict into short human-readable summaries.
Notification services stay dumb: callers (main.py) build the summary
string here and pass it in, so no Block Kit / HTML code ever parses
policies.
"""

from __future__ import annotations

from typing import Any

MAX_ACTIONS_SHOWN = 6
MAX_RESOURCES_SHOWN = 4


def policy_actions(policy: Any) -> list[str]:
    """Distinct Allow-action names in first-seen order."""
    actions: list[str] = []
    if not isinstance(policy, dict):
        return actions
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return actions
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        raw = stmt.get("Action", [])
        items = [raw] if isinstance(raw, str) else raw
        for action in items:
            if isinstance(action, str) and action and action not in actions:
                actions.append(action)
    return actions


def policy_resources(policy: Any) -> list[str]:
    """Distinct Resource ARNs in first-seen order."""
    resources: list[str] = []
    if not isinstance(policy, dict):
        return resources
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return resources
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        raw = stmt.get("Resource", [])
        items = [raw] if isinstance(raw, str) else raw
        for resource in items:
            if isinstance(resource, str) and resource and resource not in resources:
                resources.append(resource)
    return resources


def short_resource(resource: str) -> str:
    """Shorten an ARN to ``service:name``; non-ARNs pass through trimmed."""
    resource = (resource or "").strip()
    if not resource.startswith("arn:"):
        return resource[:80] if len(resource) > 80 else resource
    parts = resource.split(":", 5)
    service = parts[2] if len(parts) > 2 else ""
    remainder = parts[5] if len(parts) > 5 else ""
    name = remainder.split("/")[0].split(":")[0] or remainder
    label = f"{service}:{name}" if service else name
    if resource.endswith("/*") and not label.endswith("/*"):
        label += "/*"
    return label


def privilege_level(actions: list[str]) -> str:
    """Privilege word for a set of action names.

    admin-level when any iam: action, any wildcard, or
    Delete/Put/Attach/Create verbs dominate; write-level for
    Put/Update/Create non-iam verbs; read-only for Get/List/Describe
    only; mixed otherwise.
    """
    if not actions:
        return "mixed"
    lowered = [a.lower() for a in actions]
    if any(a == "*" or a.endswith(":*") or "*" in a for a in lowered):
        return "admin-level"
    if any(a.startswith("iam:") for a in lowered):
        return "admin-level"
    verbs = [a.split(":")[-1] for a in lowered]
    destructive = sum(
        1
        for v in verbs
        if v.startswith(("delete", "put", "attach", "create", "detach", "remove", "terminate", "purge"))
    )
    if destructive and destructive * 2 >= len(verbs):
        return "admin-level"
    writey = sum(
        1
        for v in verbs
        if v.startswith(("put", "update", "create", "write", "publish", "send", "post", "set"))
    )
    if writey:
        return "write-level"
    if all(v.startswith(("get", "list", "describe", "head", "read", "lookup", "check")) for v in verbs):
        return "read-only"
    return "mixed"


def summarize_policy(policy: Any) -> str:
    """One short string describing the stored policy's grants.

    Example: ``"3 actions (s3:GetObject, s3:ListBucket, …) on 2
    resources (s3:team-bucket, s3:logs-bucket)"``. Callers pass this
    prebuilt string into the notification services.
    """
    actions = policy_actions(policy)
    resources = policy_resources(policy)
    if not actions and not resources:
        return "No granted actions recorded."
    shown_actions = actions[:MAX_ACTIONS_SHOWN]
    extra_actions = len(actions) - len(shown_actions)
    action_part = f"{len(actions)} action{'s' if len(actions) != 1 else ''}"
    if shown_actions:
        action_part += f" ({', '.join(shown_actions)}"
        if extra_actions:
            action_part += f", +{extra_actions} more"
        action_part += ")"
    if not resources:
        return action_part + " on unspecified resources."
    shown = [short_resource(r) for r in resources[:MAX_RESOURCES_SHOWN]]
    extra = len(resources) - len(shown)
    resource_part = f"{len(resources)} resource{'s' if len(resources) != 1 else ''}"
    resource_part += f" ({', '.join(shown)}"
    if extra:
        resource_part += f", +{extra} more"
    resource_part += ")"
    return f"{action_part} on {resource_part}."
