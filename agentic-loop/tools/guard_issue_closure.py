"""Canonical closure policy. No GitHub I/O here: deterministic and testable."""
from blueprint_parent_status import derive_parent_status, project_status_label

from canonical_plan import marker_of as _marker_of


def marker_of(issue, config=None):
    return _marker_of(issue, config or {"marker": "CHECK-ID"})


def canonical_node(parents, identifier):
    """Return (node, immediate children); no hidden fallback to title similarity."""
    for parent in parents:
        if identifier == parent["id"]:
            immediate = parent["groups"] if parent["groups"] else parent["children"]
            return parent, immediate
        for group in parent["groups"]:
            if identifier == group["id"]:
                return group, group["children"]
        for task in parent["children"]:
            if identifier == task["id"]:
                return task, []
    return None, None


def closure_verdict(parents, identifier, native_children, config=None):
    """(allowed, message, project_status or None). Fail closed on missing evidence.

    A completed canonical task may close. Groups and parents may close only if
    the canonical immediate children are all complete AND native child Issues are
    exactly that expected set and are all closed. The check remains authoritative.
    """
    node, expected = canonical_node(parents, identifier)
    if node is None:
        return True, "not an active canonical check item", None
    if not expected:
        if node["status"] == "✅":
            return True, "task marked complete in canonical check", None
        return False, f"{identifier} is {node['status']} in CONTEXTO.md; check must be approved and updated before closing", None

    # The complete descendant tree matters. A box marked ✅ with a pending
    # grandchild must NOT permit the outer P0 sprint to close.
    def canonically_complete(item):
        return item["status"] == "✅" and all(
            canonically_complete(sub) for sub in item.get("children", []))

    statuses = [child["status"] for child in expected]
    project_status = project_status_label(derive_parent_status(statuses)) if not node.get("groups") else None

    if native_children is None:
        return False, "native sub-issues could not be independently read", project_status

    actual = {}
    for child in native_children:
        try:
            child_id = marker_of(child, config)
        except ValueError:
            return False, "native sub-issues contain an invalid or ambiguous marker", project_status
        if child_id is None or child_id in actual:
            return False, "native sub-issues contain an unidentified or duplicate canonical child", project_status
        actual[child_id] = child
    expected_ids = {child["id"] for child in expected}
    if set(actual) != expected_ids:
        return False, f"native hierarchy differs from check (expected {sorted(expected_ids)}; found {sorted(actual)})", project_status
    open_issues = [f"{cid} #{actual[cid].get('number')}" for cid in sorted(actual)
                   if actual[cid].get("state") != "closed"]
    if open_issues:
        return False, "open direct sub-issues: " + ", ".join(open_issues), project_status
    # A manual GitHub close cannot silently change canonical status.
    incomplete = [child["id"] for child in expected if not canonically_complete(child)]
    if incomplete:
        return False, "not completed in canonical check: " + ", ".join(incomplete), project_status
    return True, f"{identifier} has all canonical and native direct children completed", project_status
