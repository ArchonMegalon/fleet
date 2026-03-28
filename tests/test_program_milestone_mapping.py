from __future__ import annotations

import unittest
from pathlib import Path

import yaml


MILESTONES_PATH = Path("/docker/fleet/config/program_milestones.yaml")


class ProgramMilestoneMappingTests(unittest.TestCase):
    def test_fleet_phase_i_scope_is_milestone_mapped(self) -> None:
        payload = yaml.safe_load(MILESTONES_PATH.read_text(encoding="utf-8")) or {}
        projects = dict(payload.get("projects") or {})
        fleet = dict(projects.get("fleet") or {})

        uncovered = [str(item).strip() for item in (fleet.get("uncovered_scope") or []) if str(item).strip()]
        self.assertEqual(
            uncovered,
            [],
            "fleet should express remaining phase-I work through explicit milestones instead of uncovered scope",
        )

        milestones = [dict(item) for item in (fleet.get("remaining_milestones") or []) if isinstance(item, dict)]
        i1 = next((row for row in milestones if str(row.get("id") or "").strip() == "I1"), None)
        self.assertIsNotNone(i1, "fleet should keep explicit I1 participation convergence mapping")
        self.assertEqual(str((i1 or {}).get("design_area") or ""), "participation_convergence")
        i2 = next((row for row in milestones if str(row.get("id") or "").strip() == "I2"), None)
        self.assertIsNone(i2, "fleet should retire I2 once the package/bootstrap lane is closed in canon")
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNotNone(i3, "fleet should keep explicit I3 status-plane milestone mapping")
        self.assertEqual(str((i3 or {}).get("design_area") or ""), "truth_convergence")

    def test_control_plane_group_tracks_phase_i_milestones_without_uncovered_scope(self) -> None:
        payload = yaml.safe_load(MILESTONES_PATH.read_text(encoding="utf-8")) or {}
        groups = dict(payload.get("groups") or {})
        control_plane = dict(groups.get("control-plane") or {})

        uncovered = [str(item).strip() for item in (control_plane.get("uncovered_scope") or []) if str(item).strip()]
        self.assertEqual(
            uncovered,
            [],
            "control-plane should represent its remaining phase-I work through explicit milestones instead of uncovered scope",
        )

        milestones = [dict(item) for item in (control_plane.get("remaining_milestones") or []) if isinstance(item, dict)]
        i1 = next((row for row in milestones if str(row.get("id") or "").strip() == "I1"), None)
        self.assertIsNotNone(i1, "control-plane should include I1 participation convergence mapping")
        self.assertEqual(str((i1 or {}).get("owner_project") or ""), "fleet")
        i2 = next((row for row in milestones if str(row.get("id") or "").strip() == "I2"), None)
        self.assertIsNone(i2, "control-plane should retire I2 once bootstrap convergence is closed")
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNotNone(i3, "control-plane should include I3 mapping for status-plane convergence")
        self.assertEqual(str((i3 or {}).get("owner_project") or ""), "fleet")


if __name__ == "__main__":
    unittest.main()
