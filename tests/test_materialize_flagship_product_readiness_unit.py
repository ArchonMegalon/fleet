from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "materialize_flagship_product_readiness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("materialize_flagship_product_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_source_repo(tmp_path: Path) -> tuple[Path, str]:
    source_repo = tmp_path / "fleet"
    scripts_dir = source_repo / "scripts"
    scripts_dir.mkdir(parents=True)
    for relative_path in (
        "materialize_flagship_product_readiness.py",
        "chummer_design_supervisor.py",
        "refresh_flagship_readiness_proof.sh",
    ):
        (scripts_dir / relative_path).write_text(f"# {relative_path}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source_repo)], check=True)
    subprocess.run(["git", "-C", str(source_repo), "config", "user.name", "Fleet test"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "config", "user.email", "fleet-test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "add", "scripts"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "commit", "-qm", "seed producer"], check=True)
    head = subprocess.check_output(
        ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    return source_repo, head


def test_reviewed_source_commit_requires_exact_checked_out_full_sha(tmp_path: Path) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)

    assert module._reviewed_source_commit(head.upper(), repo_root=source_repo) == head
    with pytest.raises(ValueError, match="reviewed full 40-character commit SHA"):
        module._reviewed_source_commit("", repo_root=source_repo)
    with pytest.raises(ValueError, match="does not match the reviewed checkout"):
        module._reviewed_source_commit(
            "f" * 40 if head != "f" * 40 else "e" * 40,
            repo_root=source_repo,
        )


def test_reviewed_source_commit_rejects_dirty_producer_code(tmp_path: Path) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)
    producer = source_repo / "scripts" / "materialize_flagship_product_readiness.py"
    producer.write_text("# unreviewed producer change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="producer code differs"):
        module._reviewed_source_commit(head, repo_root=source_repo)


def test_materializer_emits_agreeing_reviewed_source_commit_aliases(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)
    monkeypatch.setattr(
        module,
        "build_flagship_product_readiness_payload",
        lambda **_kwargs: {"generated_at": "2026-07-20T00:00:00Z", "status": "fail"},
    )
    out_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    kwargs = {
        name: tmp_path / name
        for name, parameter in inspect.signature(module.materialize_flagship_product_readiness).parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    kwargs.update(
        source_commit=head,
        source_repo_root=source_repo,
        out_path=out_path,
        mirror_path=None,
        external_proof_runbook_path=None,
    )

    payload = module.materialize_flagship_product_readiness(**kwargs)

    assert payload["sourceCommit"] == head
    assert payload["source_commit"] == head
    assert out_path.read_text(encoding="utf-8").count(head) == 2


def test_executable_gate_freshness_issues_allows_stale_flagged_subproofs() -> None:
    module = _load_module()

    parsed_ages, issues = module.executable_gate_freshness_issues(
        {
            "evidence": {
                "flagship UI release gate proof_age_seconds": 100034,
                "flagship UI release gate proof_stale_pass_receipt_allowed": True,
                "desktop workflow execution gate proof_age_seconds": 6,
                "desktop visual familiarity gate proof_age_seconds": 6,
            }
        }
    )

    assert parsed_ages["flagship UI release gate proof_age_seconds"] == 100034
    assert issues == []


def test_live_fleet_horizon_mirror_matches_canonical_doc_set() -> None:
    module = _load_module()

    canonical_names = {path.name for path in module.CANONICAL_HORIZONS_DIR.glob("*.md")}
    mirror_names = {path.name for path in module.DEFAULT_HORIZONS_DIR.glob("*.md")}

    assert canonical_names
    assert mirror_names == canonical_names


def test_supervisor_state_root_alias_to_chummer_design_supervisor() -> None:
    module = _load_module()

    assert module._supervisor_state_root(Path("/docker/fleet/state/design-supervisor/state.json")) == Path(
        "/docker/fleet/state/chummer_design_supervisor"
    )
    assert module._supervisor_state_root(Path("/docker/fleet/state/design-supervisor/shard-7")) == Path(
        "/docker/fleet/state/chummer_design_supervisor/shard-7"
    )
    assert module._supervisor_state_root(Path("/docker/fleet/state/design-supervisor/orphaned-shard-7")) == Path(
        "/docker/fleet/state/chummer_design_supervisor/orphaned-shard-7"
    )
