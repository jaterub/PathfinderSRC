"""Canonical check parser: variable parents, optional grouping boxes, stable identities."""
import re

STATUS = r"(✅|☐|⏸️|⏳)"
PARENT_RE = re.compile(r"^\* " + STATUS + r" (P[0-9]+)\. (.+)$")
GROUP_RE = re.compile(r"^  ([A-Z])\. " + STATUS + r" (P[0-9]+\.[A-Z]) (.+)$")
TASK_RE = re.compile(r"^(  |    )([1-9][0-9]*)\. " + STATUS + r" (P[0-9]+\.[0-9]+) (.+)$")


def parse_canonical(blueprint, section="Check canónico"):
    """Parse two-level check; reject orphans, duplicate IDs and invalid ordinals."""
    parents, parent, group = [], None, None
    inside, found, seen = False, False, set()
    group_ordinal = direct_ordinal = 0
    for line in blueprint.splitlines():
        if line.startswith("## "):
            if inside:
                break
            if line[3:].strip() == section:
                if found:
                    raise ValueError("duplicate canonical section")
                inside = found = True
            continue
        if not inside or not line.strip() or line.startswith(">"):
            continue
        match = PARENT_RE.fullmatch(line)
        if match:
            status, identifier, title = match.groups()
            if identifier in seen:
                raise ValueError(f"duplicate identity {identifier}")
            seen.add(identifier)
            parent = {"id": identifier, "status": status, "title": title, "groups": [], "children": []}
            parents.append(parent)
            group = None
            direct_ordinal = 0
            continue
        match = GROUP_RE.fullmatch(line)
        if match:
            letter, status, identifier, title = match.groups()
            if parent is None or identifier != f"{parent['id']}.{letter}":
                raise ValueError(f"group outside parent: {line}")
            if identifier in seen:
                raise ValueError(f"duplicate identity {identifier}")
            seen.add(identifier)
            group = {"id": identifier, "status": status, "title": title, "children": []}
            parent["groups"].append(group)
            group_ordinal = 0
            continue
        match = TASK_RE.fullmatch(line)
        if match:
            indent, ordinal, status, identifier, title = match.groups()
            if parent is None or not identifier.startswith(parent["id"] + "."):
                raise ValueError(f"task outside correct parent: {line}")
            if indent == "    ":
                if group is None:
                    raise ValueError(f"grouped task without box: {line}")
                group_ordinal += 1
                if int(ordinal) != group_ordinal:
                    raise ValueError(f"nonsequential box ordinal: {line}")
            else:
                if group is not None:
                    raise ValueError(f"direct task after box: {line}")
                direct_ordinal += 1
                if int(ordinal) != direct_ordinal:
                    raise ValueError(f"nonsequential direct ordinal: {line}")
            if identifier in seen:
                raise ValueError(f"duplicate identity {identifier}")
            seen.add(identifier)
            task = {"id": identifier, "status": status, "title": title,
                    "group": group["id"] if indent == "    " else None}
            parent["children"].append(task)
            if indent == "    ":
                group["children"].append(task)
            continue
        raise ValueError(f"unrecognized canonical line: {line}")
    if not found or not parents:
        raise ValueError("canonical section or parents missing")
    for parent in parents:
        if not parent["children"]:
            raise ValueError(f"parent {parent['id']} has no tasks")
        if parent["groups"] and any(t["group"] is None for t in parent["children"]):
            raise ValueError(f"mixed direct and grouped tasks under {parent['id']}")
        if any(not g["children"] for g in parent["groups"]):
            raise ValueError(f"empty box under {parent['id']}")
    return parents
