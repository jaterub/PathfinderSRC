"""Reopen an invalid canonical closure before attempting board reconciliation.

A failed Projects token must not prevent the Issue safety correction. The
shared reconciler subsequently restores the board and verifies all state.
"""
import json
import os
from pathlib import Path

from blueprint_check_parser import parse_canonical
from canonical_config import authorize_apply, load_config
from canonical_github import API, request
from canonical_plan import marker_of
from canonical_sync import main as reconcile, save
from guard_issue_closure import canonical_node, closure_verdict


def correct_closure(rest, parents, config, issue_number, out):
    current = rest("GET", f"issues/{issue_number}")
    if current.get("number") != issue_number:
        raise RuntimeError("Issue identity mismatch")
    identifier = marker_of(current, config)
    if identifier is None or current.get("state") != "closed":
        return False
    node, expected = canonical_node(parents, identifier)
    if node is None:
        return False
    children = []
    if expected:
        try:
            for page in range(1, 31):
                batch = rest("GET", f"issues/{issue_number}/sub_issues?per_page=100&page={page}")
                if not isinstance(batch, list):
                    raise ValueError("invalid native sub-issues response")
                # Native sub-issues can belong to other repositories. Never
                # treat a same-number/marker child in another repo as ours.
                if any((c.get("repository_url") or "").casefold() !=
                       f"{API}/repos/{config['repository']}".casefold() for c in batch):
                    raise ValueError("native child belongs to another repository")
                children.extend(batch)
                if len(batch) < 100:
                    break
            else:
                raise ValueError("native sub-issue pagination limit")
        except (ValueError, RuntimeError):
            children = None
    allowed, reason, _ = closure_verdict(parents, identifier, children, config)
    if allowed:
        return True
    matches = []
    for page in range(1, 31):
        batch = rest("GET", f"issues?state=all&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("cannot verify closure identity")
        matches.extend(i["number"] for i in batch if "pull_request" not in i
                       and marker_of(i, config) == identifier)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("closure identity pagination exceeded")
    if matches != [issue_number]:
        raise RuntimeError("ambiguous closure identity; no writes")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = {"id": identifier, "number": issue_number, "before": "closed",
                "reason": reason, "state": "started"}
    save(out / "closure-guard.json", evidence)
    result = rest("PATCH", f"issues/{issue_number}", {"state": "open"})
    if result.get("number") != issue_number:
        raise RuntimeError("Issue reopen response mismatch")
    if rest("GET", f"issues/{issue_number}").get("state") != "open":
        raise RuntimeError("Issue reopening not independently verified")
    evidence["state"] = "verified_open"
    save(out / "closure-guard.json", evidence)
    try:
        rest("POST", f"issues/{issue_number}/comments",
             {"body": "Canonical check guard: invalid closure reopened. " + reason})
        evidence["comment"] = "posted"
    except RuntimeError:
        evidence["comment"] = "failed"
        print("WARNING: reopen verified, but audit comment failed", flush=True)
    save(out / "closure-guard.json", evidence)
    print(f"REOPENED: {identifier} #{issue_number}; verified independently", flush=True)
    return True


def main():
    root = Path(__file__).resolve().parents[2]
    config = load_config(root, os.environ.get("GITHUB_REPOSITORY", ""))
    authorize_apply(config)
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as stream:
        event = json.load(stream)
    if event.get("action") != "closed":
        raise ValueError("guard only accepts a closed Issue event")
    number = (event.get("issue") or {}).get("number")
    if not isinstance(number, int) or number < 1:
        raise ValueError("invalid Issue number")
    token = os.environ["GH_TOKEN"]
    if not token:
        raise ValueError("missing Issues token")
    def rest(method, path, payload=None):
        return request(method, f"{API}/repos/{config['repository']}/{path}", token, payload)
    parents = parse_canonical((root / "CONTEXTO.md").read_text(encoding="utf-8"), section=config["section"])
    out = Path(os.environ["RUNNER_TEMP"]) / "canonical-kanban"
    if correct_closure(rest, parents, config, number, out):
        reconcile(["--mode", "apply"])


if __name__ == "__main__":
    main()
