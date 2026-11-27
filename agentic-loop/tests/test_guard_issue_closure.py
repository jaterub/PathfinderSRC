"""Regression tests for canonical Issue closure using a self-contained example check."""
import copy
import json
import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agentic-loop" / "tools"))
from blueprint_check_parser import parse_canonical
from guard_issue_closure import canonical_node, closure_verdict, marker_of
from enforce_issue_closure import correct_closure

# This fixture is intentionally independent of the current CONTEXTO.md hierarchy.
# It covers grouped and direct children, completed/pending/paused states and P0.
EXAMPLE_CHECK = """## Check canónico
* ⏳ P0. Grouped test parent
  A. ⏳ P0.A Mixed-status group
    1. ✅ P0.1 Completed task
    2. ☐ P0.2 Pending task
  B. ☐ P0.B Pending group
    1. ☐ P0.3 Pending task
    2. ⏸️ P0.4 Paused task
* ⏳ P2. Direct mixed-status parent
  1. ✅ P2.1 Completed task
  2. ⏳ P2.2 Active task
* ☐ P3. Direct pending parent
  1. ☐ P3.1 Pending task
  2. ⏸️ P3.2 Paused task
"""
PARENTS = parse_canonical(EXAMPLE_CHECK)


def native(items, closed=True):
    return [{"number": i + 200, "body": f"<!-- CHECK-ID: {x['id']} -->",
             "state": "closed" if closed else "open"} for i, x in enumerate(items)]


def complete_parents():
    parents = copy.deepcopy(PARENTS)
    for p in parents:
        p["status"] = "✅"
        for t in p["children"]:
            t["status"] = "✅"
        for g in p["groups"]:
            g["status"] = "✅"
    return parents


class TestClosurePolicy(unittest.TestCase):
    def test_actual_case_group_p0_a_with_two_open_children(self):
        _, children = canonical_node(PARENTS, "P0.A")
        allowed, reason, status = closure_verdict(PARENTS, "P0.A", native(children, closed=False))
        self.assertFalse(allowed)
        self.assertIn("open direct sub-issues", reason)
        self.assertEqual(status, "In progress")

    def test_group_p0_a_two_closed_but_check_pending_still_rejected(self):
        _, children = canonical_node(PARENTS, "P0.A")
        allowed, reason, status = closure_verdict(PARENTS, "P0.A", native(children))
        self.assertFalse(allowed)
        self.assertIn("not completed in canonical check", reason)
        self.assertEqual(status, "In progress")

    def test_group_p0_a_two_closed_and_both_checked_passes(self):
        parents = complete_parents()
        _, children = canonical_node(parents, "P0.A")
        self.assertTrue(closure_verdict(parents, "P0.A", native(children))[0])

    def test_p0_parent_rejects_completed_group_with_pending_grandchild(self):
        parents = complete_parents()
        parents[0]["groups"][0]["children"][0]["status"] = "⏳"
        _, boxes = canonical_node(parents, "P0")
        allowed, reason, _ = closure_verdict(parents, "P0", native(boxes))
        self.assertFalse(allowed)
        self.assertIn("P0.A", reason)

    def test_invalid_native_child_marker_fails_closed(self):
        _, children = canonical_node(PARENTS, "P0.A")
        items = native(children)
        items[0]["body"] = "<!-- CHECK-ID: P0.2 --> <!-- CHECK-ID: P0.2 -->"
        allowed, reason, _ = closure_verdict(PARENTS, "P0.A", items)
        self.assertFalse(allowed)
        self.assertIn("ambiguous marker", reason)

    def test_parent_p0_open_boxes_rejected(self):
        _, children = canonical_node(PARENTS, "P0")
        ok, reason, status = closure_verdict(PARENTS, "P0", native(children, closed=False))
        self.assertFalse(ok)
        self.assertIn("open direct sub-issues", reason)
        self.assertIsNone(status)

    def test_parent_p0_all_boxes_closed_without_check_rejected(self):
        _, children = canonical_node(PARENTS, "P0")
        ok, reason, _ = closure_verdict(PARENTS, "P0", native(children))
        self.assertFalse(ok)
        self.assertIn("not completed in canonical check", reason)

    def test_parent_p0_all_boxes_and_tasks_complete(self):
        parents = complete_parents()
        _, children = canonical_node(parents, "P0")
        self.assertTrue(closure_verdict(parents, "P0", native(children))[0])

    def test_p2_parent_with_open_subissues_rejected(self):
        _, children = canonical_node(PARENTS, "P2")
        ok, why, state = closure_verdict(PARENTS, "P2", native(children, closed=False))
        self.assertFalse(ok)
        self.assertIn("open direct sub-issues", why)
        self.assertEqual(state, "In progress")

    def test_p3_parent_paused_and_pending_is_backlog(self):
        _, children = canonical_node(PARENTS, "P3")
        ok, _, state = closure_verdict(PARENTS, "P3", native(children, closed=False))
        self.assertFalse(ok)
        self.assertEqual(state, "Backlog")

    def test_p0_b_pending_box_should_return_backlog(self):
        _, children = canonical_node(PARENTS, "P0.B")
        ok, _, state = closure_verdict(PARENTS, "P0.B", native(children, closed=False))
        self.assertFalse(ok)
        self.assertEqual(state, "Backlog")

    def test_task_cannot_close_if_not_checked_in_canonical(self):
        ok, reason, status = closure_verdict(PARENTS, "P0.2", [])
        self.assertFalse(ok)
        self.assertIn("CONTEXTO.md", reason)
        self.assertIsNone(status)

    def test_task_may_close_if_checked(self):
        ok, _, status = closure_verdict(PARENTS, "P2.1", [])
        self.assertTrue(ok)
        self.assertIsNone(status)

    def test_native_hierarchy_missing_rejected(self):
        ok, reason, _ = closure_verdict(PARENTS, "P0.A", None)
        self.assertFalse(ok)
        self.assertIn("could not be", reason)

    def test_native_hierarchy_wrong_child_rejected(self):
        _, children = canonical_node(PARENTS, "P0.A")
        items = native(children)
        items[0]["body"] = "<!-- CHECK-ID: P0.3 -->"
        ok, why, _ = closure_verdict(PARENTS, "P0.A", items)
        self.assertFalse(ok)
        self.assertIn("hierarchy differs", why)

    def test_native_hierarchy_duplicate_rejected(self):
        _, children = canonical_node(PARENTS, "P0.A")
        items = native(children)
        items[1]["body"] = items[0]["body"]
        ok, why, _ = closure_verdict(PARENTS, "P0.A", items)
        self.assertFalse(ok)
        self.assertIn("duplicate", why)

    def test_native_hierarchy_unmarked_rejected(self):
        ok, why, _ = closure_verdict(PARENTS, "P0.A", [{"number": 22, "body": "", "state": "open"}])
        self.assertFalse(ok)
        self.assertIn("unidentified", why)

    def test_missing_children_rejected(self):
        ok, why, _ = closure_verdict(PARENTS, "P0.A", [])
        self.assertFalse(ok)
        self.assertIn("hierarchy differs", why)

    def test_noncanonical_issue_ignored(self):
        self.assertIsNone(marker_of({"body": "Normal issue"}))
        self.assertTrue(closure_verdict(PARENTS, "P10.77", [])[0])

    def test_ambiguous_marker_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            marker_of({"body": "<!-- CHECK-ID: P0.A --> <!-- CHECK-ID: P0.B -->"})

    def test_invalid_marker_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            marker_of({"body": "<!-- CHECK-ID: TERRIBLE -->"})


class TestImmediateClosureCorrection(unittest.TestCase):
    def test_invalid_closure_reopens_without_project_credentials(self):
        config = {"marker": "CHECK-ID", "repository": "demo/client"}
        state = {"number": 100, "state": "closed", "body": "<!-- CHECK-ID: P0.A -->"}
        requests = []
        def rest(method, path, payload=None):
            requests.append((method, path))
            if method == "GET" and path == "issues/100":
                return state.copy()
            if method == "GET" and "sub_issues" in path:
                raise RuntimeError("simulated unavailable native hierarchy")
            if method == "GET" and path.startswith("issues?"):
                return [state.copy()]
            if method == "PATCH":
                state.update(payload)
                return state.copy()
            if method == "POST" and path.endswith("comments"):
                return {}
            self.fail("unexpected request " + path)

        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(correct_closure(rest, PARENTS, config, 100, tmp))
            evidence = json.loads((Path(tmp) / "closure-guard.json").read_text())
            self.assertEqual(evidence["state"], "verified_open")
        self.assertEqual(state["state"], "open")
        self.assertIn(("POST", "issues/100/comments"), requests)

    def test_duplicate_closure_identity_never_writes(self):
        config = {"marker": "CHECK-ID", "repository": "demo/client"}
        current = {"number": 100, "state": "closed", "body": "<!-- CHECK-ID: P0.2 -->"}
        def rest(method, path, payload=None):
            self.assertEqual(method, "GET")
            if path == "issues/100":
                return current
            if path.startswith("issues?"):
                return [current, {**current, "number": 101}]
            self.fail("unexpected request")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "ambiguous closure identity"):
                correct_closure(rest, PARENTS, config, 100, tmp)

    def test_valid_leaf_closure_is_read_only(self):
        config = {"marker": "CHECK-ID", "repository": "demo/client"}
        def rest(method, path, payload=None):
            self.assertEqual(method, "GET")
            return {"number": 12, "state": "closed", "body": "<!-- CHECK-ID: P2.1 -->"}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(correct_closure(rest, PARENTS, config, 12, tmp))
            self.assertFalse((Path(tmp) / "closure-guard.json").exists())

    def test_unrelated_issue_ignored(self):
        def rest(method, path, payload=None):
            self.assertEqual(method, "GET")
            return {"number": 12, "state": "closed", "body": "ordinary issue"}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(correct_closure(rest, PARENTS, {"marker": "CHECK-ID"}, 12, tmp))


if __name__ == "__main__":
    unittest.main()
