"""One reconciler for canonical pushes, manual plans and Issue closure events."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from blueprint_check_parser import parse_canonical
from canonical_config import authorize_apply, load_config
from canonical_plan import build_plan, desired_nodes, index_issues
from guard_issue_closure import closure_verdict

AUTO_ADD_BLOCKER = ("Project workflow 'Auto-add sub-issues to project' is enabled. "
                    "Turn it off in Project Workflows and generate a fresh plan before apply.")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def save(path, value):
    """Atomic journal writes, outside the repository."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".kanban-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def public_snapshot(snapshot, config):
    """Backup mutable canonical state. Redact bodies/other-repo content from artifacts."""
    indexed, _ = index_issues(snapshot["issues"], config)
    numbers = {i["number"] for i in indexed.values()}
    issues = {key: {k: i.get(k) for k in ("number", "title", "state", "state_reason", "id", "node_id")}
              for key, i in indexed.items()}
    canonical = [c for c in snapshot["board"]["cards"]
                 if (c.get("repository") or "").casefold() == config["repository"].casefold()
                 and c["number"] in numbers]
    other = [c for c in snapshot["board"]["cards"] if c not in canonical]
    return {"sha256": digest(snapshot), "issues": issues, "parents": snapshot["parents"],
            "children": snapshot["children"], "cards": canonical,
            "field": snapshot["board"]["field"], "options": snapshot["board"]["options"],
            "auto_add_sub_issues": snapshot["board"]["auto_add_sub_issues"],
            "unrelated_cards": len(other), "unrelated_sha256": digest(other)}


def synchronize(api, parents, config, out, *, apply=False, sleep=time.sleep):
    nodes = desired_nodes(parents)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    before = api.snapshot()
    actions, indexed = build_plan(nodes, before, config)
    backup = public_snapshot(before, config)
    save(out / "snapshot.json", backup)
    blockers = [AUTO_ADD_BLOCKER] if backup["auto_add_sub_issues"] else []
    save(out / "plan.json", {"apply": apply, "snapshot_sha256": backup["sha256"],
                             "actions": actions, "blockers": blockers})
    print(f"PLAN: {len(actions)} changes; {'apply' if apply else 'read-only'}", flush=True)
    journal = []
    save(out / "journal.json", journal)
    for blocker in blockers:
        print(f"BLOCKED APPLY: {blocker}", flush=True)
    if not apply:
        return actions
    if blockers:
        raise RuntimeError(AUTO_ADD_BLOCKER)
    # Fail closed if someone changed an Issue or card since preflight.
    fresh = api.snapshot()
    if digest(fresh) != digest(before):
        raise RuntimeError("state changed since preflight; rerun")
    _, indexed = build_plan(nodes, fresh, config)
    for action in actions:
        entry = {"action": action, "state": "started"}
        journal.append(entry)
        save(out / "journal.json", journal)
        api.execute(action, indexed)
        entry["state"] = "completed"
        save(out / "journal.json", journal)
    # Re-read independent API state; never report success from a mutation alone.
    for attempt in range(3):
        after = api.snapshot()
        remaining, _ = build_plan(nodes, after, config)
        if after["board"]["auto_add_sub_issues"]:
            save(out / "remaining.json", remaining)
            raise RuntimeError(AUTO_ADD_BLOCKER)
        if not remaining:
            verified = public_snapshot(after, config)
            indexed, numbers = index_issues(after["issues"], config)
            for key, issue in indexed.items():
                if key in nodes and issue["state"] == "closed":
                    native = [numbers[n] for n in after["children"][issue["number"]]]
                    if not closure_verdict(parents, key, native, config)[0]:
                        raise RuntimeError("closure verification failed: " + key)
            if verified["unrelated_sha256"] != backup["unrelated_sha256"]:
                raise RuntimeError("unrelated board membership/status changed during sync")
            save(out / "verified.json", verified)
            print(f"PASS: {len(actions)} changes; independent plan is empty", flush=True)
            return actions
        if attempt < 2:
            sleep(2)
    save(out / "remaining.json", remaining)
    if all(a["kind"] == "archive" and a["id"] in nodes and nodes[a["id"]]["parent"] is not None
           for a in remaining):
        raise RuntimeError("post-write drift: unexpected active sub-issue cards; inspect remaining.json, "
                           "check Project auto-add workflows, and generate a fresh plan before apply")
    raise RuntimeError("post-write verification detected drift; inspect journal and rerun")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    config = load_config(root, os.environ.get("GITHUB_REPOSITORY", ""))
    apply = args.mode == "apply"
    if apply:
        authorize_apply(config)
    source = (root / "CONTEXTO.md").read_text(encoding="utf-8")
    parents = parse_canonical(source, section=config["section"])
    from canonical_github import GitHub
    api = GitHub(config, os.environ.get("GH_TOKEN"), os.environ.get("PROJECTS_TOKEN"), writable=apply)
    out = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "canonical-kanban"
    synchronize(api, parents, config, out, apply=apply)


if __name__ == "__main__":
    main()
