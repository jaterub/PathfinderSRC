"""Project-specific configuration for the shared canonical Kanban engine."""
import json
import os
import re
from pathlib import Path

ID = r"P[0-9]+(?:\.[A-Z]|\.[0-9]+)?"
CONFIG = ".github/canonical-check.json"


def load_config(root, repository):
    path = Path(root) / CONFIG
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"repository", "project_id", "project_title", "section", "marker"}
    optional = {"retired_ids", "ignore_legacy_m"}
    if not isinstance(data, dict) or not required <= data.keys() or data.keys() - required - optional:
        raise ValueError("invalid canonical-check configuration keys")
    if not all(isinstance(data[k], str) and data[k].strip() for k in required):
        raise ValueError("canonical-check configuration contains empty/non-string fields")
    if not repository or data["repository"].casefold() != repository.casefold():
        raise ValueError("configured repository does not match current repository")
    if not re.fullmatch(r"PVT_[A-Za-z0-9_-]+", data["project_id"]):
        raise ValueError("invalid Project V2 identity")
    if not re.fullmatch(r"(?:[A-Z][A-Z0-9-]*-)?CHECK-ID", data["marker"]):
        raise ValueError("invalid canonical marker")
    retired = data.get("retired_ids", [])
    if (not isinstance(retired, list) or any(not isinstance(x, str) or not re.fullmatch(ID, x)
            for x in retired) or len(set(retired)) != len(retired)):
        raise ValueError("invalid or duplicate retired canonical identities")
    if type(data.get("ignore_legacy_m", False)) is not bool:
        raise ValueError("ignore_legacy_m must be boolean")
    return {**data, "retired_ids": retired, "ignore_legacy_m": data.get("ignore_legacy_m", False)}


def authorize_apply(config, env=None):
    """Only the configured main branch and explicitly enabled workflows can write."""
    env = os.environ if env is None else env
    if (env.get("GITHUB_REPOSITORY", "").casefold() != config["repository"].casefold()
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("CANONICAL_SYNC_ENABLED") != "true"
            or env.get("GITHUB_EVENT_NAME") not in {"push", "issues", "workflow_dispatch"}):
        raise ValueError("STOP: repository, branch, event or explicit sync enablement invalid")
