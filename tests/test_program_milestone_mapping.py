from __future__ import annotations

import unittest
from pathlib import Path

import yaml


MILESTONES_PATH = Path("/docker/fleet/config/program_milestones.yaml")


class ProgramMilestoneMappingTests(unittest.TestCase):
    def test_fleet_status_plane_scope_is_milestone_mapped(self) -> None:
        payload = yaml.safe_load(MILESTONES_PATH.read_text(encoding="utf-8")) or {}
        projects = dict(payload.get("projects") or {})
        fleet = dict(projects.get("fleet") or {})

        uncovered = [str(item).strip() for item in (fleet.get("uncovered_scope") or []) if str(item).strip()]
        self.assertFalse(
            any("canonical downstream status plane" in row.lower() for row in uncovered),
            "status-plane work should be milestone-mapped instead of left in uncovered scope",
        )

        milestones = [dict(item) for item in (fleet.get("remaining_milestones") or []) if isinstance(item, dict)]
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNotNone(i3, "fleet should keep explicit I3 status-plane milestone mapping")
        self.assertEqual(str((i3 or {}).get("design_area") or ""), "truth_convergence")

    def test_solo_fleet_group_tracks_i3_status_plane_milestone(self) -> None:
        payload = yaml.safe_load(MILESTONES_PATH.read_text(encoding="utf-8")) or {}
        groups = dict(payload.get("groups") or {})
        solo_fleet = dict(groups.get("solo-fleet") or {})

        milestones = [dict(item) for item in (solo_fleet.get("remaining_milestones") or []) if isinstance(item, dict)]
        i3 = next((row for row in milestones if str(row.get("id") or "").strip() == "I3"), None)
        self.assertIsNotNone(i3, "solo-fleet should include I3 mapping for status-plane convergence")
        self.assertEqual(str((i3 or {}).get("owner_project") or ""), "fleet")


if __name__ == "__main__":
    unittest.main()
