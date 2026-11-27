import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from blueprint_parent_status import derive_parent_status, project_status_label


class TestDeriveParentStatus(unittest.TestCase):
    def test_all_pending_is_todo(self):
        self.assertEqual(derive_parent_status(["☐", "☐", "☐", "☐"]), "Todo")

    def test_one_completed_and_remaining_pending_is_in_progress(self):
        self.assertEqual(derive_parent_status(["✅", "☐", "☐", "☐"]), "In Progress")

    def test_two_completed_and_two_pending_is_in_progress(self):
        self.assertEqual(derive_parent_status(["✅", "✅", "☐", "☐"]), "In Progress")

    def test_one_active_child_is_in_progress(self):
        self.assertEqual(derive_parent_status(["⏳", "☐", "☐", "☐"]), "In Progress")

    def test_completed_and_active_is_in_progress(self):
        self.assertEqual(derive_parent_status(["✅", "⏳", "☐", "☐"]), "In Progress")

    def test_all_completed_is_done(self):
        self.assertEqual(derive_parent_status(["✅", "✅", "✅", "✅"]), "Done")

    def test_pending_and_paused_without_progress_is_todo(self):
        self.assertEqual(derive_parent_status(["⏸️", "☐", "⏸️", "☐"]), "Todo")

    def test_all_paused_is_todo(self):
        self.assertEqual(derive_parent_status(["⏸️", "⏸️"]), "Todo")

    def test_empty_children_are_rejected(self):
        with self.assertRaises(ValueError):
            derive_parent_status([])

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            derive_parent_status(["🟡"])


    def test_todo_maps_to_actual_project_backlog_column(self):
        self.assertEqual(project_status_label("Todo"), "Backlog")

    def test_in_progress_maps_to_actual_project_column(self):
        self.assertEqual(project_status_label("In Progress"), "In progress")

    def test_done_maps_to_actual_project_column(self):
        self.assertEqual(project_status_label("Done"), "Done")

    def test_unknown_parent_status_mapping_is_rejected(self):
        with self.assertRaises(ValueError):
            project_status_label("Blocked")


if __name__ == "__main__":
    unittest.main()
