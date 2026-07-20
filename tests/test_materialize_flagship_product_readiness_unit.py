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


def test_materializer_emits_portable_evidence_references(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)
    monkeypatch.setattr(
        module,
        "build_flagship_product_readiness_payload",
        lambda **_kwargs: {
            "generated_at": "2026-07-20T00:00:00Z",
            "status": "fail",
            "evidence_sources": {
                "fleet": str(source_repo / ".codex-studio" / "published" / "proof.json"),
                "ui": "/docker/chummercomplete/chummer6-ui/.codex-studio/published/proof.json",
                "route": "/status",
            },
            "coverage_details": {
                "desktop_client": {
                    "evidence": {
                        "ui_executable_gate_trusted_local_roots": [
                            "/tmp/chummer-presentation-main-push",
                        ]
                    }
                }
            },
        },
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

    assert payload["evidence_sources"] == {
        "fleet": "repo://ArchonMegalon/fleet/.codex-studio/published/proof.json",
        "ui": "repo://ArchonMegalon/chummer6-ui/.codex-studio/published/proof.json",
        "route": "/status",
    }
    assert payload["coverage_details"]["desktop_client"]["evidence"][
        "ui_executable_gate_trusted_local_roots"
    ] == ["repo://ArchonMegalon/chummer6-ui"]


def test_portable_receipt_rejects_unmapped_machine_local_path() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="unmapped machine-local path at evidence.unknown"):
        module._portable_public_receipt_value(
            {"evidence": {"unknown": "/Users/operator/private/proof.json"}},
            fleet_repo_roots=(),
        )
    with pytest.raises(ValueError, match="unmapped machine-local path at evidence.message"):
        module._portable_public_receipt_value(
            {"evidence": {"message": "receipt copied from /private/tmp/proof.json"}},
            fleet_repo_roots=(),
        )


def test_portable_receipt_rewrites_embedded_known_path_without_changing_message() -> None:
    module = _load_module()

    assert module._portable_public_receipt_value(
        {"reason": "receipt copied from /docker/fleet/.codex-studio/published/proof.json."},
        fleet_repo_roots=(),
    ) == {
        "reason": (
            "receipt copied from "
            "repo://ArchonMegalon/fleet/.codex-studio/published/proof.json."
        )
    }


def test_fleet_repo_root_is_derived_only_from_fleet_mirror_acceptance_path(tmp_path: Path) -> None:
    module = _load_module()

    assert module._fleet_repo_root_from_acceptance_path(
        tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    ) == tmp_path
    assert module._fleet_repo_root_from_acceptance_path(
        tmp_path / "products" / "chummer" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    ) is None


def test_portable_receipt_binds_ltd_registry_to_fleet_authority() -> None:
    module = _load_module()

    assert module._portable_public_receipt_value(
        {
            "readiness_planes": {
                "feedback_loop_ready": {
                    "evidence": {
                        "feedback_discovery_ltd_registry_path": (
                            "/tmp/LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml"
                        )
                    }
                }
            }
        },
        fleet_repo_roots=(),
    )["readiness_planes"]["feedback_loop_ready"]["evidence"][
        "feedback_discovery_ltd_registry_path"
    ] == (
        "repo://ArchonMegalon/fleet/.codex-design/product/"
        "LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml"
    )


def test_portable_receipt_resolves_fixture_owner_from_list_field_and_path(tmp_path: Path) -> None:
    module = _load_module()

    assert module._portable_public_receipt_value(
        {
            "platform_tuple_receipts": [
                str(tmp_path / "ui-b" / ".codex-studio" / "published" / "proof.json")
            ],
            "reason": (
                "selected "
                + str(tmp_path / "ui-b" / ".codex-studio" / "published" / "proof.json")
            ),
        },
        fleet_repo_roots=(tmp_path,),
    ) == {
        "platform_tuple_receipts": [
            "repo://ArchonMegalon/chummer6-ui/.codex-studio/published/proof.json"
        ],
        "reason": (
            "selected "
            "repo://ArchonMegalon/chummer6-ui/.codex-studio/published/proof.json"
        ),
    }


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
