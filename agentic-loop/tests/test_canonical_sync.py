"""Offline integration: same planner, synchronizer and transport as production."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agentic-loop/tools"))
from blueprint_check_parser import parse_canonical
from canonical_config import load_config, authorize_apply
from canonical_plan import build_plan, desired_nodes, index_issues
from canonical_sync import synchronize
from canonical_github import GitHub
from canonical_backup import (capture, PROJECT_QUERY, ITEMS_QUERY, VALUES_QUERY,
                              stable_hash, compare_semantic, write_backup, read_backup, SnapshotStop)

CONFIG = {"repository": "demo/client", "project_id": "PVT_test", "project_title": "Test",
          "section": "Check canónico", "marker": "CHECK-ID", "retired_ids": [], "ignore_legacy_m": False}
CHECK = """## Check canónico
* ✅ P1. Finished
  1. ✅ P1.1 Complete
* ⏳ P2. Backend
  1. ✅ P2.1 Persistence
  2. ☐ P2.2 Login
* ⏳ P9. Grouped
  A. ⏳ P9.A Building
    1. ⏳ P9.1 Work
  B. ☐ P9.B Later
    1. ☐ P9.2 Wait
"""
PILOT_SHAPE = """## Check canónico
* ✅ P1. First phase
  1. ✅ P1.1 First task
* ⏳ P2. Second phase
  1. ✅ P2.1 Work 1
  2. ✅ P2.2 Work 2
  3. ✅ P2.3 Work 3
  4. ☐ P2.4 Work 4
  5. ☐ P2.5 Work 5
"""


class FakeGitHub:
    """Deterministic in-memory API; preserves unrelated and archived cards."""
    def __init__(self, config=CONFIG):
        self.config = config
        self.issues = []
        self.parents = {}
        self.children = {}
        self.board = {"field": "field", "options": {"backlog": "b", "in progress": "i", "done": "d"},
                      "auto_add_sub_issues": False,
                      "cards": [{"id": "unrelated", "repository": "other/client", "number": 6,
                                 "archived": False, "status": "Done", "content_id": "other"}]}
        self.writes = []
        self.fail_on = None

    def snapshot(self):
        return copy.deepcopy({"issues": self.issues, "parents": self.parents,
                              "children": self.children, "board": self.board})

    def execute(self, a, indexed):
        self.writes.append(a.copy())
        if self.fail_on == len(self.writes):
            raise RuntimeError("simulated API failure")
        key, kind = a["id"], a["kind"]
        if kind == "create":
            n = len(self.issues) + 1
            i = {"number": n, "id": 1000+n, "node_id": f"I{n}", "title": a["title"],
                 "body": f"<!-- {self.config['marker']}: {key} -->", "state": "open", "state_reason": None}
            self.issues.append(i)
            self.parents[n] = None
            self.children[n] = []
            indexed[key] = i
            return
        n = indexed[key]["number"]
        i = next(x for x in self.issues if x["number"] == n)
        if kind in ("title", "state"):
            i[kind] = a["value"]
            if kind == "state":
                i["state_reason"] = a.get("reason")
        elif kind in ("attach", "detach"):
            parent = indexed[a["parent"]]["number"]
            if kind == "attach":
                if self.parents[n] is not None:
                    raise ValueError("already attached")
                self.parents[n] = parent
                self.children[parent].append(n)
                self.children[parent].sort()
            else:
                self.parents[n] = None
                self.children[parent].remove(n)
        elif kind == "add_card":
            self.board["cards"].append({"id": f"C{n}", "repository": self.config["repository"],
                "number": n, "archived": False, "status": None, "content_id": i["node_id"]})
        elif kind in ("archive", "unarchive"):
            next(c for c in self.board["cards"] if c["id"] == a["card"])["archived"] = kind == "archive"
        elif kind == "card_status":
            next(c for c in self.board["cards"] if c["number"] == n and
                 c["repository"] == self.config["repository"] and not c["archived"])["status"] = a["value"]
        else:
            raise AssertionError(kind)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.parents = parse_canonical(CHECK, section=CONFIG["section"])
        self.api = FakeGitHub()

    def run_sync(self, apply=False, config=CONFIG, parents=None):
        return synchronize(self.api, parents or self.parents, config, self.out,
                           apply=apply, sleep=lambda _: None)

    def test_01_empty_bootstrap_then_idempotence(self):
        self.assertTrue(self.run_sync(True))
        nodes = desired_nodes(self.parents)
        self.assertEqual(len(self.api.issues), len(nodes))
        cards = [c for c in self.api.board["cards"] if c["repository"] == CONFIG["repository"] and not c["archived"]]
        self.assertEqual(len(cards), sum(n["card"] is not None for n in nodes.values()))
        self.assertEqual(self.run_sync(True), [])
        self.assertTrue((self.out / "verified.json").exists())

    def test_02_plan_is_read_only_and_redacted(self):
        before = self.api.snapshot()
        plan = self.run_sync()
        self.assertTrue(plan)
        self.assertEqual(self.api.snapshot(), before)
        self.assertEqual(self.api.writes, [])
        backup = (self.out / "snapshot.json").read_text()
        self.assertNotIn("other/client", backup)
        self.assertIn("unrelated_sha256", backup)

    def test_pilot_shape_enabled_auto_add_blocks_all_writes(self):
        parents = parse_canonical(PILOT_SHAPE, section=CONFIG["section"])
        self.api.board["auto_add_sub_issues"] = True
        plan = self.run_sync(parents=parents)
        self.assertEqual(len(plan), 23)
        self.assertEqual([a["id"] for a in plan if a["kind"] == "add_card"], ["P1", "P2"])
        self.assertIn("Auto-add sub-issues to project",
                      json.loads((self.out / "plan.json").read_text(encoding="utf-8"))["blockers"][0])
        with self.assertRaisesRegex(RuntimeError, "Turn it off"):
            self.run_sync(True, parents=parents)
        self.assertEqual(self.api.writes, [])
        self.assertEqual(json.loads((self.out / "journal.json").read_text(encoding="utf-8")), [])
        self.api.board["auto_add_sub_issues"] = False
        self.assertEqual(len(self.run_sync(True, parents=parents)), 23)
        self.assertEqual(self.run_sync(parents=parents), [])

    def test_pilot_shape_unreported_auto_add_drift_and_archive_only_recovery(self):
        parents = parse_canonical(PILOT_SHAPE, section=CONFIG["section"])
        execute = self.api.execute

        def execute_with_native_auto_add(action, indexed):
            execute(action, indexed)
            if action["kind"] == "add_card":
                for number in self.api.children[indexed[action["id"]]["number"]]:
                    self.api.board["cards"].append({"id": f"C{number}", "repository": CONFIG["repository"],
                        "number": number, "archived": False, "status": "Backlog", "content_id": f"I{number}"})

        self.api.execute = execute_with_native_auto_add
        with self.assertRaisesRegex(RuntimeError, "unexpected active sub-issue cards"):
            self.run_sync(True, parents=parents)
        journal = json.loads((self.out / "journal.json").read_text(encoding="utf-8"))
        remaining = json.loads((self.out / "remaining.json").read_text(encoding="utf-8"))
        self.assertEqual([e["state"] for e in journal], ["completed"] * 23)
        self.assertEqual(len(self.api.issues), 8)
        self.assertEqual(sum(c["repository"] == CONFIG["repository"] for c in self.api.board["cards"]), 8)
        self.assertEqual({(a["kind"], a["id"]) for a in remaining},
                         {("archive", key) for key in ("P1.1", "P2.1", "P2.2", "P2.3", "P2.4", "P2.5")})
        self.api.execute = execute
        before = self.api.snapshot()
        self.assertEqual(self.run_sync(parents=parents), remaining)
        self.assertEqual(self.run_sync(True, parents=parents), remaining)
        self.assertEqual(self.run_sync(parents=parents), [])
        after = self.api.snapshot()
        for key in ("issues", "parents", "children"):
            self.assertEqual(after[key], before[key])
        self.assertEqual([c for c in after["board"]["cards"] if c["id"] == "unrelated"],
                         [c for c in before["board"]["cards"] if c["id"] == "unrelated"])
        self.assertEqual(sum(c["repository"] == CONFIG["repository"] and not c["archived"]
                             for c in after["board"]["cards"]), 2)

    def test_03_incremental_rename_and_no_overwrite_of_body(self):
        self.run_sync(True)
        old, _ = index_issues(self.api.issues, CONFIG)
        old["P2.1"]["body"] += "\nHuman note"
        changed = copy.deepcopy(self.parents)
        changed[1]["children"][0]["title"] = "New title"
        self.assertEqual([a["kind"] for a in self.run_sync(True, parents=changed)], ["title"])
        self.assertIn("Human note", old["P2.1"]["body"])

    def test_04_invalid_closure_reopens_and_repairs_board(self):
        self.run_sync(True)
        indexed, _ = index_issues(self.api.issues, CONFIG)
        indexed["P2"]["state"] = "closed"
        next(c for c in self.api.board["cards"] if c["number"] == indexed["P2"]["number"])["status"] = "Done"
        actions = self.run_sync(True)
        self.assertEqual({a["kind"] for a in actions}, {"state", "card_status"})
        self.assertEqual(indexed["P2"]["state"], "open")
        self.assertEqual(self.run_sync(True), [])

    def test_05_duplicate_marker_stops_before_writes(self):
        self.run_sync(True)
        self.api.issues[1]["body"] = self.api.issues[0]["body"]
        n = len(self.api.writes)
        with self.assertRaisesRegex(ValueError, "duplicate canonical marker"):
            self.run_sync(True)
        self.assertEqual(len(self.api.writes), n)

    def test_06_unmarked_candidate_stops(self):
        self.api.issues.append({"number": 1, "title": "P1 — similar", "body": "", "state": "open"})
        with self.assertRaisesRegex(ValueError, "unmarked candidate"):
            self.run_sync(True)
        self.assertEqual(self.api.writes, [])

    def test_07_wrong_native_parent_stops(self):
        self.run_sync(True)
        self.api.children[1].remove(2)
        self.api.parents[2] = 99
        n = len(self.api.writes)
        with self.assertRaisesRegex(ValueError, "unrelated parent"):
            self.run_sync(True)
        self.assertEqual(len(self.api.writes), n)

    def test_inconsistent_native_edge_stops_before_writes(self):
        self.run_sync(True)
        self.api.parents[2] = None
        n = len(self.api.writes)
        with self.assertRaisesRegex(ValueError, "inconsistent native child"):
            self.run_sync(True)
        self.assertEqual(len(self.api.writes), n)

    def test_08_partial_failure_journal_and_safe_retry(self):
        self.api.fail_on = 4
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.run_sync(True)
        journal = json.loads((self.out / "journal.json").read_text())
        self.assertEqual([e["state"] for e in journal], ["completed"] * 3 + ["started"])
        self.api.fail_on = None
        self.run_sync(True)
        self.assertEqual(self.run_sync(True), [])
        self.assertEqual(len(self.api.issues), len(desired_nodes(self.parents)))

    def test_09_retirement_preserves_issue_and_archives_card(self):
        self.run_sync(True)
        reduced = copy.deepcopy(self.parents[1:])
        with self.assertRaisesRegex(ValueError, "unapproved retired"):
            self.run_sync(True, parents=reduced)
        config = {**CONFIG, "retired_ids": ["P1", "P1.1"]}
        self.run_sync(True, config, reduced)
        indexed, _ = index_issues(self.api.issues, CONFIG)
        self.assertIn("P1", indexed)
        card = next(c for c in self.api.board["cards"] if c["number"] == indexed["P1"]["number"])
        self.assertTrue(card["archived"])
        self.assertEqual(self.run_sync(True, config, reduced), [])
        self.run_sync(True)
        self.assertFalse(card["archived"])

    def test_10_wrong_project_options_fail_before_write(self):
        del self.api.board["options"]["backlog"]
        with self.assertRaisesRegex(ValueError, "Status option missing"):
            self.run_sync(True)
        self.assertEqual(self.api.writes, [])

    def test_11_actual_installed_check_bootstraps_and_repeats(self):
        config = json.loads((ROOT / ".github/canonical-check.json").read_text(encoding="utf-8"))
        parents = parse_canonical((ROOT / "CONTEXTO.md").read_text(encoding="utf-8"),
                                  section=config["section"])
        api = FakeGitHub(config)
        synchronize(api, parents, config, self.out, apply=True, sleep=lambda _: None)
        self.assertEqual(synchronize(api, parents, config, self.out, apply=True, sleep=lambda _: None), [])

    def test_12_inconsistent_parent_status_rejected(self):
        wrong = copy.deepcopy(self.parents)
        wrong[1]["status"] = "✅"
        with self.assertRaisesRegex(ValueError, "inconsistent derived"):
            self.run_sync(True, parents=wrong)

    def test_13_configured_legacy_m_is_preserved(self):
        config = {**CONFIG, "ignore_legacy_m": True}
        self.api.issues.append({"number": 1, "title": "Historical milestone", "body": "<!-- CHECK-ID: M1 -->",
                                "state": "closed"})
        self.run_sync(True, config)
        self.assertEqual(self.api.issues[0]["body"], "<!-- CHECK-ID: M1 -->")

    def test_14_drift_before_apply_is_rejected(self):
        original = self.api.snapshot
        calls = 0
        def snapshot():
            nonlocal calls
            calls += 1
            result = original()
            if calls == 2:
                result["board"]["cards"][0]["status"] = "Backlog"
            return result
        self.api.snapshot = snapshot
        with self.assertRaisesRegex(RuntimeError, "state changed"):
            self.run_sync(True)
        self.assertEqual(self.api.writes, [])

    def test_15_duplicate_cards_rejected(self):
        self.run_sync(True)
        self.api.board["cards"].append({**self.api.board["cards"][1], "id": "duplicate"})
        with self.assertRaisesRegex(ValueError, "duplicate active"):
            self.run_sync(True)


class TransportTests(unittest.TestCase):
    def test_read_only_gate_blocks_mutations(self):
        def forbidden(*args):
            self.fail("network must not be called")
        api = GitHub(CONFIG, "issue", "project", transport=forbidden)
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            api.rest("POST", "issues", {})
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            api.gql("mutation { x }", {})

    def test_scope_and_trigger_gate(self):
        valid = {"GITHUB_REPOSITORY": CONFIG["repository"], "GITHUB_REF": "refs/heads/main",
                 "GITHUB_EVENT_NAME": "push", "CANONICAL_SYNC_ENABLED": "true"}
        authorize_apply(CONFIG, valid)
        for key, bad in (("GITHUB_REPOSITORY", "other/repo"), ("GITHUB_REF", "refs/heads/feature"),
                         ("GITHUB_EVENT_NAME", "pull_request"), ("CANONICAL_SYNC_ENABLED", "")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                authorize_apply(CONFIG, {**valid, key: bad})

    def test_config_rejects_wrong_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".github/canonical-check.json"
            p.parent.mkdir()
            p.write_text(json.dumps(CONFIG))
            self.assertEqual(load_config(tmp, CONFIG["repository"]), CONFIG)
            with self.assertRaisesRegex(ValueError, "repository"):
                load_config(tmp, "other/repo")

    def test_graphql_and_rest_write_contracts(self):
        calls = []
        def transport(method, url, token, payload, allow_404):
            calls.append((method, url, payload))
            if url.endswith("/issues") and method == "POST":
                return {"number": 7, "id": 17, "node_id": "I7"}
            if url.endswith("/issues/7") and method == "PATCH":
                return {"number": 7}
            if url.endswith("/graphql"):
                query = payload["query"]
                if "addProjectV2ItemById" in query:
                    return {"data": {"addProjectV2ItemById": {"item": {"id": "C7"}}}}
                if "updateProjectV2ItemFieldValue" in query:
                    return {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "C7"}}}}
                if "archiveProjectV2Item" in query:
                    return {"data": {"archiveProjectV2Item": {"item": {"id": "C7"}}}}
            self.fail("unexpected transport call " + url)
        api = GitHub(CONFIG, "issue", "project", writable=True, transport=transport)
        api.field_id = "field"
        api.options = {"done": "done-option"}
        indexed = {}
        for action in ({"kind": "create", "id": "P1", "title": "P1 — Test"},
                       {"kind": "state", "id": "P1", "value": "closed", "reason": "completed"},
                       {"kind": "add_card", "id": "P1"},
                       {"kind": "card_status", "id": "P1", "value": "Done"},
                       {"kind": "archive", "id": "P1", "card": "C7"}):
            api.execute(action, indexed)
        self.assertEqual(len(calls), 5)
        self.assertIn("<!-- CHECK-ID: P1 -->", calls[0][2]["body"])
        self.assertEqual(calls[3][2]["variables"]["o"], "done-option")

    def test_project_scope_link_and_permissions(self):
        def transport(method, url, token, payload, allow_404):
            return {"data": {"node": {"id": CONFIG["project_id"], "title": CONFIG["project_title"],
                "closed": False, "template": False, "viewerCanUpdate": False,
                "repositories": {"nodes": [{"nameWithOwner": "other/client"}],
                                 "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}
        read = GitHub(CONFIG, "issue", "project", transport=transport)
        with self.assertRaisesRegex(ValueError, "not linked"):
            read.verify_scope()
        write = GitHub(CONFIG, "issue", "project", writable=True, transport=transport)
        with self.assertRaisesRegex(ValueError, "cannot update"):
            write.verify_scope()

        def linked(method, url, token, payload, allow_404):
            result = transport(method, url, token, payload, allow_404)
            result["data"]["node"]["viewerCanUpdate"] = True
            result["data"]["node"]["repositories"]["nodes"] = [{"nameWithOwner": CONFIG["repository"]}]
            return result
        write.transport = linked
        write.verify_scope()

    def test_paginated_project_query_and_identity_checks(self):
        def transport(method, url, token, payload, allow_404):
            cursor = payload["variables"]["cursor"]
            rows = [{"id": "a"}] if cursor is None else [{"id": "b"}]
            return {"data": {"node": {"id": CONFIG["project_id"], "title": CONFIG["project_title"],
                "items": {"nodes": rows, "pageInfo": {"hasNextPage": cursor is None,
                                                   "endCursor": "next" if cursor is None else None}}}}}
        api = GitHub(CONFIG, "issue", "project", transport=transport)
        self.assertEqual(api.project_pages("query { node }", "items"), [{"id": "a"}, {"id": "b"}])
        api.config = {**CONFIG, "project_title": "Wrong"}
        with self.assertRaisesRegex(ValueError, "identity/title"):
            api.project_pages("query { node }", "items")

    def test_native_auto_add_uses_read_only_paginated_workflow_state(self):
        seen = []
        active = True

        def transport(method, url, token, payload, allow_404):
            self.assertTrue(payload["query"].lstrip().startswith("query"))
            self.assertEqual(token, "project")
            cursor = payload["variables"]["cursor"]
            seen.append(cursor)
            workflow = {"name": "Item closed", "enabled": True} if cursor is None else {
                "name": "Auto-add sub-issues to project", "enabled": active}
            return {"data": {"node": {"id": CONFIG["project_id"], "title": CONFIG["project_title"],
                "workflows": {"nodes": [workflow], "pageInfo": {"hasNextPage": cursor is None,
                                                               "endCursor": "next"}}}}}
        api = GitHub(CONFIG, "issue", "project", transport=transport)
        self.assertTrue(api.sub_issue_auto_add_enabled())
        active = False
        self.assertFalse(api.sub_issue_auto_add_enabled())
        self.assertEqual(seen, [None, "next", None, "next"])

class BackupTests(unittest.TestCase):
    def capture(self, *, unknown=False, wrong_title=False, repeated_cursor=False):
        def fetch(query, variables):
            cursor = variables["cursor"]
            node = {"id": variables["id"], "title": "Wrong" if wrong_title else "Test"}
            if query == PROJECT_QUERY:
                name, rows = "fields", [{"id": "field", "name": "Status", "__typename": "ProjectV2SingleSelectField"}]
                more = False
            elif query == ITEMS_QUERY:
                name = "items"
                rows = [{"id": "active" if cursor is None else "archived",
                         "type": "ISSUE", "isArchived": cursor is not None,
                         "content": {"__typename": "Issue", "number": 3 if cursor is None else 4,
                                     "repository": {"nameWithOwner": "demo/client" if cursor is None else "other/repo"}}}]
                more = cursor is None or repeated_cursor
            elif query == VALUES_QUERY:
                name = "fieldValues"
                rows = [{"__typename": "UnsupportedField" if unknown else "ProjectV2ItemFieldSingleSelectValue",
                         "field": {"id": "field", "name": "Status"}, "name": "Done"}]
                more = False
            else:
                self.fail("unexpected query")
            node[name] = {"nodes": rows, "pageInfo": {"hasNextPage": more,
                                                     "endCursor": "next" if more else None}}
            return {"data": {"node": node}}
        return capture(fetch, project_id="PVT_test", project_title="Test", repository="demo/client")

    def test_full_paged_backup_preserves_archived_and_unrelated(self):
        backup = self.capture()
        self.assertEqual([c["id"] for c in backup["cards"]], ["active", "archived"])
        self.assertTrue(backup["write_eligible"])
        self.assertTrue(compare_semantic(backup, self.capture()))
        self.assertEqual(stable_hash(backup), stable_hash(self.capture()))

    def test_backup_rejects_wrong_project_and_repeated_cursor(self):
        with self.assertRaisesRegex(SnapshotStop, "title mismatch"):
            self.capture(wrong_title=True)
        with self.assertRaisesRegex(SnapshotStop, "repeated cursor"):
            self.capture(repeated_cursor=True)

    def test_unsupported_fields_do_not_authorize_migration(self):
        backup = self.capture(unknown=True)
        self.assertFalse(backup["write_eligible"])
        with self.assertRaisesRegex(SnapshotStop, "unsupported"):
            compare_semantic(backup, copy.deepcopy(backup))

    def test_backup_file_checksum_and_no_overwrite(self):
        backup = self.capture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.json"
            self.assertEqual(write_backup(path, backup), stable_hash(backup))
            self.assertEqual(read_backup(path), backup)
            with self.assertRaises(FileExistsError):
                write_backup(path, backup)
            corrupt = json.loads(path.read_text(encoding="utf-8"))
            corrupt["snapshot"]["cards"][0]["is_archived"] = True
            path.write_text(json.dumps(corrupt), encoding="utf-8")
            with self.assertRaisesRegex(SnapshotStop, "checksum"):
                read_backup(path)


if __name__ == "__main__":
    unittest.main()
