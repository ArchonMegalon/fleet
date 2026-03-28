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
        self.assertIsNone(i1, "fleet should retire I1 once participation convergence is closed in canon")
        i2 = next((row for row in milestones if str(row.get("id") or "").strip() == "I2"), None)
        self.assertIsNone(i2, "fleet should retire I2 once the package/bootstrap lane is closed in canon")
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNone(i3, "fleet should retire I3 once status-plane truth is compiled and consumed end to end")
        self.assertEqual(milestones, [], "fleet should have no remaining phase-I control-plane milestones once I1-I3 are closed")

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
        self.assertIsNone(i1, "control-plane should retire I1 once participation convergence is closed")
        i2 = next((row for row in milestones if str(row.get("id") or "").strip() == "I2"), None)
        self.assertIsNone(i2, "control-plane should retire I2 once bootstrap convergence is closed")
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNone(i3, "control-plane should retire I3 once status-plane convergence is closed")
        self.assertEqual(milestones, [], "control-plane should have no remaining phase-I milestones once the status plane closure lands")


if __name__ == "__main__":
    unittest.main()
