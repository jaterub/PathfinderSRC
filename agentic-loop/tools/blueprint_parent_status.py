"""Canonical mapping from Blueprint child checks to parent Kanban status."""

VALID_CHILD_STATUSES = {"☐", "⏳", "⏸️", "✅"}


def derive_parent_status(child_statuses):
    """Return Todo, In Progress, or Done for a non-empty child status collection.

    Done: every child is complete.
    In Progress: at least one child is complete or actively in progress.
    Todo: no child is complete or active (pending/paused only).
    """
    statuses = list(child_statuses)
    if not statuses:
        raise ValueError("a parent must have at least one canonical child")

    unknown = sorted(set(statuses) - VALID_CHILD_STATUSES)
    if unknown:
        raise ValueError(f"unsupported child status(es): {', '.join(unknown)}")

    if all(status == "✅" for status in statuses):
        return "Done"
    if any(status in {"✅", "⏳"} for status in statuses):
        return "In Progress"
    return "Todo"


PROJECT_STATUS_LABELS = {
    "Todo": "Backlog",
    "In Progress": "In progress",
    "Done": "Done",
}


def project_status_label(parent_status):
    """Map canonical lifecycle status to the configured GitHub Project column."""
    try:
        return PROJECT_STATUS_LABELS[parent_status]
    except KeyError as exc:
        raise ValueError(f"unsupported parent status: {parent_status}") from exc
