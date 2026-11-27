"""Small invariant tests: number and order of parents, boxes and tasks may change."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agentic-loop" / "tools"))
from blueprint_check_parser import parse_canonical
from blueprint_parent_status import derive_parent_status, project_status_label


class TestCanonicalHierarchy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "CONTEXTO.md").read_text(encoding="utf-8")
        config_path = ROOT / ".github/canonical-check.json"
        section = json.loads(config_path.read_text(encoding="utf-8"))["section"]
        cls.parents = parse_canonical(cls.source, section=section)

    def test_every_task_reachable_once(self):
        ids = [p["id"] for p in self.parents]
        for p in self.parents:
            ids.extend(g["id"] for g in p["groups"])
            ids.extend(t["id"] for t in p["children"])
            self.assertEqual(sum(len(g["children"]) for g in p["groups"]),
                             sum(t["group"] is not None for t in p["children"]))
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_group_can_derive_status(self):
        for p in self.parents:
            children = p["groups"] if p["groups"] else p["children"]
            self.assertIn(project_status_label(derive_parent_status(
                [c["status"] for c in children])), ("Backlog", "In progress", "Done"))
            for g in p["groups"]:
                derive_parent_status([t["status"] for t in g["children"]])

    def test_extra_box_and_task_are_accepted(self):
        source = """## Check canónico
* ⏳ P9. Ejemplo
  A. ⏳ P9.A Primera caja
    1. ⏳ P9.1 Uno
  B. ☐ P9.B Segunda caja
    1. ☐ P9.2 Dos
  C. ☐ P9.C Tercera caja
    1. ☐ P9.3 Tres
  D. ☐ P9.D Cuarta caja
    1. ☐ P9.4 Cuatro
  E. ☐ P9.E Quinta caja
    1. ☐ P9.5 Cinco
* ☐ P10. Sin cajas
  1. ☐ P10.1 Directa
"""
        parsed = parse_canonical(source)
        self.assertEqual(len(parsed[0]["groups"]), 5)
        self.assertEqual(len(parsed[1]["groups"]), 0)
        self.assertEqual(len(parsed[1]["children"]), 1)

    def test_duplicate_identity_rejected(self):
        source = """## Check canónico
* ☐ P2. Padre
  1. ☐ P2.1 Uno
  2. ☐ P2.1 Duplicado
"""
        with self.assertRaisesRegex(ValueError, "duplicate identity"):
            parse_canonical(source)

    def test_orphan_and_nonsequential_ordinal_rejected(self):
        for source in (
            "## Check canónico\n    1. ☐ P2.1 Huérfana\n",
            "## Check canónico\n* ☐ P2. Padre\n  2. ☐ P2.1 Mal orden\n",
        ):
            with self.assertRaises(ValueError):
                parse_canonical(source)

    def test_wrong_group_indent_rejected(self):
        source = """## Check canónico
* ☐ P0. Padre
  A. ☐ P0.A Caja
  1. ☐ P0.1 Indentación errónea
"""
        with self.assertRaises(ValueError):
            parse_canonical(source)


class TestWorkflowSafety(unittest.TestCase):
    def test_all_writers_share_lock_and_require_main(self):
        for name in ("sync-blueprint-all.yml", "sync-blueprint-parent-project.yml", "guard-canonical-closures.yml"):
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("group: canonical-kanban", source)
            self.assertIn("refs/heads/main", source)
            self.assertIn("vars.CANONICAL_SYNC_ENABLED", source)
            self.assertNotIn("pull_request:", source)
            self.assertNotIn("jaterub/", source)
        test = (ROOT / ".github/workflows/check-hierarchy-tests.yml").read_text(encoding="utf-8")
        self.assertNotIn("issues: write", test)
        self.assertIn("test_canonical_sync.py", test)


if __name__ == "__main__":
    unittest.main()
