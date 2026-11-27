"""Pure canonical check -> Issue/Project plan.

Bootstrap and hierarchy: Profession. Stable identity and incremental preflight:
Fable Five. No network, tokens or filesystem writes in this module.
"""
import re

from blueprint_parent_status import derive_parent_status, project_status_label
from canonical_config import ID


def marker_of(issue, config):
    body = issue.get("body") or ""
    label = re.escape(config["marker"])
    raw = re.findall(r"<!--\s*" + label + r":\s*(.*?)\s*-->", body, flags=re.S)
    markers = re.findall(r"<!--\s*" + label + r"\b", body)
    if len(markers) != len(raw):
        raise ValueError("malformed canonical marker")
    if not raw:
        return None
    if len(raw) != 1:
        raise ValueError("ambiguous canonical marker")
    identity = raw[0]
    if config.get("ignore_legacy_m") and re.fullmatch(r"M[0-9]+(?:\.[0-9]+)?", identity):
        return None
    if not re.fullmatch(ID, identity):
        raise ValueError("invalid canonical marker")
    return identity


def desired_nodes(parents):
    nodes = {}

    def add(item, parent, children, card):
        identity = item["id"]
        if identity in nodes:
            raise ValueError("duplicate canonical identity " + identity)
        if children:
            derived = derive_parent_status(c["status"] for c in children)
            allowed = {"Done": {"✅"}, "In Progress": {"⏳"}, "Todo": {"☐", "⏸️"}}
            if item["status"] not in allowed[derived]:
                raise ValueError("inconsistent derived status: " + identity)
        nodes[identity] = {
            "parent": parent, "title": identity + " — " + item["title"],
            "state": "closed" if item["status"] == "✅" else "open",
            "card": project_status_label(derive_parent_status(c["status"] for c in children)) if card else None,
        }

    for phase in parents:
        groups = phase["groups"]
        add(phase, None, phase["children"], not groups)
        if groups:
            for group in groups:
                add(group, phase["id"], group["children"], True)
                for task in group["children"]:
                    add(task, group["id"], [], False)
        else:
            for task in phase["children"]:
                add(task, phase["id"], [], False)
    return nodes


def index_issues(issues, config):
    by_id, by_number = {}, {}
    for issue in issues:
        number = issue.get("number")
        if not isinstance(number, int) or number <= 0 or number in by_number:
            raise ValueError("missing or duplicate Issue number")
        by_number[number] = issue
        identity = marker_of(issue, config)
        if identity is not None:
            if identity in by_id:
                raise ValueError("duplicate canonical marker: " + identity)
            if not isinstance(issue.get("id"), int) or not issue.get("node_id"):
                raise ValueError("canonical Issue missing database/node identity")
            if issue.get("state") not in {"open", "closed"}:
                raise ValueError("invalid canonical Issue state")
            by_id[identity] = issue
    return by_id, by_number


def build_plan(nodes, snapshot, config):
    """Plan all writes before any mutation. Reject ambiguity and unrelated links."""
    issues = snapshot["issues"]
    indexed, numbers = index_issues(issues, config)
    retired = set(config.get("retired_ids", []))
    if retired & nodes.keys():
        raise ValueError("retired identity still present in active check")
    unknown = indexed.keys() - nodes.keys() - retired
    if unknown:
        raise ValueError("unapproved retired identities: " + ", ".join(sorted(unknown)))
    managed = {i["number"]: key for key, i in indexed.items()}
    parents, children = snapshot["parents"], snapshot["children"]
    for number in managed:
        if number not in parents or number not in children:
            raise ValueError("incomplete native hierarchy")
        parent = parents[number]
        if parent is not None and parent not in managed:
            raise ValueError("canonical Issue has unrelated parent")
        if parent is not None and number not in children.get(parent, []):
            raise ValueError("inconsistent native parent")
        direct = children[number]
        if len(set(direct)) != len(direct):
            raise ValueError("duplicate native child")
        for child in direct:
            if child not in managed or parents.get(child) != number:
                raise ValueError("unrelated or inconsistent native child")
    for key in nodes.keys() - indexed.keys():
        prefix = re.compile(r"^" + re.escape(key) + r"(?:\s|$)")
        if any(prefix.match(i.get("title") or "") for i in issues if i["number"] not in managed):
            raise ValueError("unmarked candidate: " + key)

    cards = {}
    all_card_ids = set()
    for card in snapshot["board"]["cards"]:
        if not card.get("id") or card["id"] in all_card_ids or type(card.get("archived")) is not bool:
            raise ValueError("invalid/duplicate Project card identity")
        all_card_ids.add(card["id"])
        if (card.get("repository") or "").casefold() == config["repository"].casefold():
            if card.get("number") in managed:
                cards.setdefault(managed[card["number"]], []).append(card)
    for key, memberships in cards.items():
        if sum(not c["archived"] for c in memberships) > 1:
            raise ValueError("duplicate active Project cards: " + key)
    options = snapshot["board"]["options"]
    for label in ("Backlog", "In progress", "Done"):
        if label.casefold() not in options:
            raise ValueError("Project Status option missing: " + label)

    actions = []
    def action(kind, key, **values):
        actions.append({"kind": kind, "id": key, **values})

    for key, node in nodes.items():
        if key not in indexed:
            action("create", key, title=node["title"])
        elif indexed[key]["title"] != node["title"]:
            action("title", key, value=node["title"])

    # Create all identities first, then detach obsolete managed edges before adding new ones.
    targets = {key: n["parent"] for key, n in nodes.items()}
    targets.update({key: None for key in sorted(retired) if key in indexed})
    for key, target in targets.items():
        old = managed.get(parents.get(indexed[key]["number"])) if key in indexed else None
        if old != target and old is not None:
            action("detach", key, parent=old)
    for key, target in targets.items():
        old = managed.get(parents.get(indexed[key]["number"])) if key in indexed else None
        if old != target and target is not None:
            action("attach", key, parent=target)

    for key, node in nodes.items():
        if node["state"] == "open" and key in indexed and indexed[key]["state"] != "open":
            action("state", key, value="open")
    for key in reversed(list(nodes)):
        if nodes[key]["state"] == "closed" and (key not in indexed or indexed[key]["state"] != "closed"):
            action("state", key, value="closed", reason="completed")
    for key in sorted(retired & indexed.keys()):
        if indexed[key]["state"] != "closed":
            action("state", key, value="closed", reason="not_planned")

    # A grouped phase has cards for its groups, a direct phase has one parent card.
    # Archive rather than delete stale memberships: history and custom values survive.
    for key, target in targets.items():
        wanted = nodes.get(key, {}).get("card")
        memberships = cards.get(key, [])
        active = next((c for c in memberships if not c["archived"]), None)
        if wanted is None:
            if active:
                action("archive", key, card=active["id"])
            continue
        if active is None:
            archived = [c for c in memberships if c["archived"]]
            if len(archived) > 1:
                raise ValueError("ambiguous archived memberships: " + key)
            if archived:
                action("unarchive", key, card=archived[0]["id"])
            else:
                action("add_card", key)
            action("card_status", key, value=wanted)
        elif (active.get("status") or "").casefold() != wanted.casefold():
            action("card_status", key, value=wanted)
    return actions, indexed
