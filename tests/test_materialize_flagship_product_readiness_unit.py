from __future__ import annotations

import importlib.util
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit

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
        "external_proof_paths.py",
        "refresh_flagship_readiness_proof.sh",
    ):
        (scripts_dir / relative_path).write_text(f"# {relative_path}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source_repo)], check=True)
    subprocess.run(["git", "-C", str(source_repo), "config", "user.name", "Fleet test"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "config", "user.email", "fleet-test@example.invalid"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source_repo),
            "remote",
            "add",
            "origin",
            "https://github.com/ArchonMegalon/fleet.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(source_repo), "add", "scripts"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "commit", "-qm", "seed producer"], check=True)
    head = subprocess.check_output(
        ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    return source_repo, head


def _git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _create_allowed_repo(
    tmp_path: Path,
    *,
    directory_name: str,
    repository: str,
    tracked_files: dict[str, str] | None = None,
) -> tuple[Path, str]:
    repo = tmp_path / directory_name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Evidence test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "evidence-test@example.invalid"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            f"https://github.com/{repository}.git",
        ],
        check=True,
    )
    for relative_path, content in (tracked_files or {"README.md": "evidence\n"}).items():
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed evidence"], check=True)
    return repo, _git_head(repo)


def _resolver(
    module,
    *,
    repositories: tuple[Path, ...] = (),
    runtime_roots: tuple[Path, ...] = (),
    runtime_commit: str = "a" * 40,
):
    return module.EvidenceAuthorityResolver(
        checkouts=module._repository_checkouts(repositories),
        runtime_roots=runtime_roots,
        runtime_repository="ArchonMegalon/fleet",
        runtime_commit=runtime_commit,
    )


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


def test_reviewed_source_commit_rejects_any_dirty_source_file(tmp_path: Path) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)
    imported_helper = source_repo / "scripts" / "external_proof_paths.py"
    imported_helper.write_text("# unreviewed imported helper change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source tree differs"):
        module._reviewed_source_commit(head, repo_root=source_repo)


def test_reviewed_source_commit_rejects_untracked_source_file(tmp_path: Path) -> None:
    module = _load_module()
    source_repo, head = _create_source_repo(tmp_path)
    (source_repo / "scripts" / "shadow_helper.py").write_text(
        "raise RuntimeError('unreviewed')\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source tree differs"):
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
    source_repo, _head = _create_source_repo(tmp_path)
    fleet_proof = source_repo / ".codex-studio" / "published" / "proof.json"
    fleet_proof.parent.mkdir(parents=True)
    fleet_proof.write_text('{"status":"fail"}\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(source_repo), "add", ".codex-studio"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "commit", "-qm", "add proof"], check=True)
    head = _git_head(source_repo)
    ui_repo, ui_head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    ui_proof = ui_repo / ".codex-studio" / "published" / "proof.json"
    ui_proof.parent.mkdir(parents=True)
    ui_proof.write_text('{"status":"fail"}\n', encoding="utf-8")
    trusted_roots = ["/tmp/chummer-presentation-main-push"]
    ui_gate = ui_repo / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_gate.write_text(
        json.dumps({"evidence": {"trusted_local_roots": trusted_roots}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "build_flagship_product_readiness_payload",
        lambda **_kwargs: {
            "generated_at": "2026-07-20T00:00:00Z",
            "status": "fail",
            "evidence_sources": {
                "fleet": str(fleet_proof),
                "ui": str(ui_proof),
            },
            "coverage_details": {
                "desktop_client": {
                    "evidence": {
                        "ui_executable_gate_trusted_local_roots": [
                            *trusted_roots,
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
        ui_executable_exit_gate_path=ui_gate,
    )

    payload = module.materialize_flagship_product_readiness(**kwargs)

    assert payload["evidence_sources"] == {
        "fleet": (
            f"repo://ArchonMegalon/fleet@{head}/.codex-studio/published/proof.json"
        ),
        "ui": (
            f"artifact://ArchonMegalon/chummer6-ui@{ui_head}/sha256/"
            f"{hashlib.sha256(ui_proof.read_bytes()).hexdigest()}"
        ),
    }
    trusted_reference = payload["coverage_details"]["desktop_client"]["evidence"][
        "ui_executable_gate_trusted_local_roots"
    ][0]
    assert trusted_reference == (
        f"artifact://ArchonMegalon/chummer6-ui@{ui_head}/sha256/"
        f"{hashlib.sha256(ui_gate.read_bytes()).hexdigest()}"
        "#%2Fevidence%2Ftrusted_local_roots%2F0"
    )


@pytest.mark.parametrize(
    "value",
    (
        "copied from `/tmp/private/proof.json`",
        "sources=[/tmp/private/proof.json]",
        "sources,/tmp/private/proof.json",
        "file:///tmp/private/proof.json",
        "/var/lib/codex-fleet/private.json",
        "/opt/build/private.json",
        "/mnt/work/private.json",
        "/Volumes/work/private.json",
        r"\\server\share\private.json",
        r"C:\Users\operator\private.json",
        "[proof](/tmp/private/proof.json)",
    ),
)
def test_portable_receipt_detects_all_adversarial_machine_local_paths(value: str) -> None:
    module = _load_module()
    resolver = _resolver(module)

    with pytest.raises(ValueError, match="invalid machine-local evidence at evidence.message"):
        module._portable_public_receipt_value(
            {"evidence": {"message": value}},
            resolver=resolver,
        )


@pytest.mark.parametrize(
    "value",
    (
        "/docker/fleet/../../etc/passwd",
        "/docker/chummercomplete/chummer6-ui/../../secret.txt",
        "file:///docker/fleet/%2e%2e/%2e%2e/etc/passwd",
    ),
)
def test_portable_receipt_rejects_dot_and_traversal(value: str) -> None:
    module = _load_module()
    resolver = _resolver(module)

    with pytest.raises(ValueError, match="invalid machine-local evidence at evidence.path"):
        module._portable_public_receipt_value(
            {"evidence": {"path": value}},
            resolver=resolver,
        )


def test_fleet_repo_root_is_derived_only_from_fleet_mirror_acceptance_path(tmp_path: Path) -> None:
    module = _load_module()

    assert module._fleet_repo_root_from_acceptance_path(
        tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    ) == tmp_path
    assert module._fleet_repo_root_from_acceptance_path(
        tmp_path / "products" / "chummer" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    ) is None


def test_portable_receipt_uses_verified_repo_commit_or_artifact_digest(tmp_path: Path) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
        tracked_files={"proofs/tracked.json": "tracked\n"},
    )
    untracked = repo / "proofs" / "runtime.json"
    untracked.write_text("runtime\n", encoding="utf-8")
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    assert module._portable_public_receipt_value(
        {
            "tracked": str(repo / "proofs" / "tracked.json"),
            "runtime": str(untracked),
        },
        resolver=resolver,
    ) == {
        "tracked": f"repo://ArchonMegalon/chummer6-ui@{head}/proofs/tracked.json",
        "runtime": (
            f"artifact://ArchonMegalon/chummer6-ui@{head}/sha256/"
            f"{hashlib.sha256(untracked.read_bytes()).hexdigest()}"
        ),
    }


def test_portable_receipt_digest_binds_directory_with_untracked_bytes(tmp_path: Path) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="fleet",
        repository="ArchonMegalon/fleet",
        tracked_files={"proofs/commands/run.sh": "#!/bin/sh\nexit 0\n"},
    )
    commands = repo / "proofs" / "commands"
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    assert module._portable_public_receipt_value(
        {"commands": str(commands)},
        resolver=resolver,
    ) == {
        "commands": f"repo://ArchonMegalon/fleet@{head}/proofs/commands"
    }

    (commands / "runtime-proof.tgz").write_bytes(b"runtime archive\n")
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)
    digest = module.EvidenceAuthorityResolver._artifact_sha256(commands)

    assert module._portable_public_receipt_value(
        {"commands": str(commands)},
        resolver=resolver,
    ) == {
        "commands": (
            f"artifact://ArchonMegalon/fleet@{head}/sha256/{digest}"
        )
    }


def test_portable_receipt_does_not_claim_missing_committed_path(tmp_path: Path) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="fleet",
        repository="ArchonMegalon/fleet",
        tracked_files={"proofs/tracked.json": "tracked\n"},
    )
    tracked = repo / "proofs" / "tracked.json"
    tracked.unlink()
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    assert module._portable_public_receipt_value(
        {"tracked": str(tracked)},
        resolver=resolver,
    ) == {"tracked": None}


def test_portable_receipt_does_not_fabricate_authority_from_field_or_basename(tmp_path: Path) -> None:
    module = _load_module()
    resolver = _resolver(module)

    with pytest.raises(ValueError, match="invalid machine-local evidence at ui_release_channel"):
        module._portable_public_receipt_value(
            {"ui_release_channel": str(tmp_path / "RELEASE_CHANNEL.generated.json")},
            resolver=resolver,
        )


def test_portability_post_scan_rejects_local_paths_and_unverified_authorities() -> None:
    module = _load_module()
    resolver = _resolver(module)

    with pytest.raises(ValueError, match="post-scan found machine-local evidence"):
        module._validate_portable_public_receipt(
            {"message": "sources=[/opt/private.json]"},
            resolver=resolver,
        )
    with pytest.raises(ValueError, match="unverified portable authority"):
        module._validate_portable_public_receipt(
            {"path": "repo://ArchonMegalon/fleet@" + "a" * 40 + "/secret.txt"},
            resolver=resolver,
        )


def test_trusted_local_roots_keep_one_to_one_source_artifact_pointers(tmp_path: Path) -> None:
    module = _load_module()
    ui_repo, ui_head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    roots = [f"/tmp/historical-ui-checkout-{index}" for index in range(26)]
    gate_path = ui_repo / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    gate_payload = {"evidence": {"trusted_local_roots": roots}}
    gate_path.write_text(json.dumps(gate_payload, sort_keys=True) + "\n", encoding="utf-8")
    resolver = _resolver(module, repositories=(ui_repo,), runtime_commit=ui_head)
    payload = {
        "coverage_details": {
            "desktop_client": {
                "evidence": {"ui_executable_gate_trusted_local_roots": roots}
            }
        }
    }
    bindings = module._trusted_local_root_occurrence_bindings(
        payload,
        source_artifact_path=gate_path,
        resolver=resolver,
    )

    portable = module._portable_public_receipt_value(
        payload,
        resolver=resolver,
        occurrence_bindings=bindings,
    )
    references = portable["coverage_details"]["desktop_client"]["evidence"][
        "ui_executable_gate_trusted_local_roots"
    ]
    digest = hashlib.sha256(gate_path.read_bytes()).hexdigest()
    prefix = f"artifact://ArchonMegalon/chummer6-ui@{ui_head}/sha256/{digest}#"
    assert len(references) == len(roots) == 26
    assert len(set(references)) == 26
    assert all(reference.startswith(prefix) for reference in references)
    for index, reference in enumerate(references):
        pointer = unquote(urlsplit(reference).fragment)
        assert pointer == f"/evidence/trusted_local_roots/{index}"
        assert gate_payload["evidence"]["trusted_local_roots"][index] == roots[index]
    rendered = json.dumps(portable)
    assert not any(root in rendered for root in roots)


def test_trusted_local_root_without_source_binding_is_rejected() -> None:
    module = _load_module()
    resolver = _resolver(module)

    with pytest.raises(ValueError, match="invalid machine-local evidence"):
        module._portable_public_receipt_value(
            {
                "coverage_details": {
                    "desktop_client": {
                        "evidence": {
                            "ui_executable_gate_trusted_local_roots": [
                                "/tmp/unknown-ui-checkout"
                            ]
                        }
                    }
                }
            },
            resolver=resolver,
        )


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
