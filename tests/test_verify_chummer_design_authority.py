from pathlib import Path

from scripts import verify_chummer_design_authority as mod


def test_git_branch_sync_parses_left_right_counts_as_ahead_then_behind(monkeypatch):
    def fake_git_stdout(_repo: Path, *args: str) -> str:
        if args[:2] == ("branch", "--show-current"):
            return "main"
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return "origin/main"
        if args[:2] == ("rev-list", "--left-right"):
            return "1 0"
        raise AssertionError(args)

    monkeypatch.setattr(mod, "git_stdout", fake_git_stdout)

    sync = mod.git_branch_sync(Path("/tmp/repo"))

    assert sync["branch"] == "main"
    assert sync["upstream"] == "origin/main"
    assert sync["ahead"] == 1
    assert sync["behind"] == 0
