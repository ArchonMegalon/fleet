from __future__ import annotations

import importlib.util
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import tempfile
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
    checkouts = []
    for repository_root in repositories:
        remote = subprocess.check_output(
            ["git", "-C", str(repository_root), "config", "--get", "remote.origin.url"],
            text=True,
        ).strip()
        checkouts.append(
            module.RepositoryCheckout(
                root=repository_root.resolve(),
                repository=module._canonical_repository_from_remote(remote),
                commit=_git_head(repository_root),
            )
        )
    return module.EvidenceAuthorityResolver(
        checkouts=tuple(checkouts),
        runtime_roots=runtime_roots,
        runtime_repository="ArchonMegalon/fleet",
        runtime_commit=runtime_commit,
        artifact_store_root=Path(tempfile.mkdtemp(prefix="fleet-readiness-cas-test-")),
    )


def _write_release_authority(
    path: Path,
    repositories: tuple[tuple[str, str], ...],
) -> tuple[Path, str]:
    content = (
        json.dumps(
            {
                "contract": "chummer.release-repository-authority/v1",
                "repositories": [
                    {"repository": repository, "commit": commit}
                    for repository, commit in repositories
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


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
    monkeypatch.setattr(module, "_remote_commit_reachable", lambda _repository, _commit: True)
    source_repo, head = _create_source_repo(tmp_path)
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (("ArchonMegalon/fleet", head),),
    )
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
        release_repository_authority_path=authority_path,
        release_repository_authority_sha256=authority_sha256,
        out_path=out_path,
        mirror_path=None,
        external_proof_runbook_path=None,
    )

    payload = module.materialize_flagship_product_readiness(**kwargs)

    assert payload["sourceCommit"] == head
    assert payload["source_commit"] == head
    assert payload["portableEvidenceAuthority"]["repositoryAuthority"]["repositories"] == [
        {"repository": "ArchonMegalon/fleet", "commit": head}
    ]


def test_explicit_release_proofs_are_repository_authority_mapped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_remote_commit_reachable", lambda _repository, _commit: True)
    source_repo, _head = _create_source_repo(tmp_path)
    final_gold_janitor = (
        source_repo
        / "_completion"
        / "full_product_reaudit_v20"
        / "FINAL_GOLD_JANITOR.generated.json"
    )
    live_backed_truth = (
        source_repo
        / "_completion"
        / "full_product_reaudit_v20"
        / "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json"
    )
    final_gold_janitor.parent.mkdir(parents=True)
    final_gold_janitor.write_text(
        '{"contract_name":"chummer.final_gold_janitor","status":"failed"}\n',
        encoding="utf-8",
    )
    live_backed_truth.write_text(
        '{"contract_name":"chummer.live_backed_release_truth","status":"failed"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(source_repo), "add", "_completion"], check=True)
    subprocess.run(["git", "-C", str(source_repo), "commit", "-qm", "add aggregate proofs"], check=True)
    head = _git_head(source_repo)
    core_repo, core_head = _create_allowed_repo(
        tmp_path,
        directory_name="core",
        repository="ArchonMegalon/chummer6-core",
        tracked_files={
            ".codex-studio/published/ENGINE_PROOF_PACK.generated.json": (
                '{"contract_name":"chummer6-core.engine_proof_pack","status":"passed"}\n'
            )
        },
    )
    media_repo, media_head = _create_allowed_repo(
        tmp_path,
        directory_name="media",
        repository="ArchonMegalon/chummer6-media-factory",
        tracked_files={
            ".codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json": (
                '{"contract_name":"chummer6-media-factory.local_release_proof","status":"passed"}\n'
            )
        },
    )
    rules_proof = core_repo / ".codex-studio" / "published" / "ENGINE_PROOF_PACK.generated.json"
    media_proof = media_repo / ".codex-studio" / "published" / "MEDIA_LOCAL_RELEASE_PROOF.generated.json"
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (
            ("ArchonMegalon/fleet", head),
            ("ArchonMegalon/chummer6-core", core_head),
            ("ArchonMegalon/chummer6-media-factory", media_head),
        ),
    )
    captured: dict[str, object] = {}

    def build_payload(**kwargs):
        captured.update(kwargs)
        return {
            "generated_at": "2026-07-20T00:00:00Z",
            "status": "fail",
            "evidence": {
                "rules_certification_path": str(kwargs["rules_certification_path"]),
                "media_proof_path": str(kwargs["media_proof_path"]),
                "final_gold_janitor_path": str(kwargs["final_gold_janitor_path"]),
                "live_backed_truth_path": str(kwargs["live_backed_truth_path"]),
            },
        }

    monkeypatch.setattr(module, "build_flagship_product_readiness_payload", build_payload)
    runtime_root = tmp_path / "runtime"
    out_path = runtime_root / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    kwargs = {
        name: runtime_root / name
        for name, parameter in inspect.signature(module.materialize_flagship_product_readiness).parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    kwargs.update(
        source_commit=head,
        source_repo_root=source_repo,
        release_repository_authority_path=authority_path,
        release_repository_authority_sha256=authority_sha256,
        out_path=out_path,
        mirror_path=None,
        external_proof_runbook_path=None,
        rules_certification_path=rules_proof,
        media_proof_path=media_proof,
        final_gold_janitor_path=final_gold_janitor,
        live_backed_truth_path=live_backed_truth,
    )

    payload = module.materialize_flagship_product_readiness(**kwargs)

    assert captured["rules_certification_path"] == rules_proof
    assert captured["media_proof_path"] == media_proof
    assert captured["final_gold_janitor_path"] == final_gold_janitor
    assert captured["live_backed_truth_path"] == live_backed_truth
    assert payload["evidence"] == {
        "rules_certification_path": (
            f"repo://ArchonMegalon/chummer6-core@{core_head}/"
            ".codex-studio/published/ENGINE_PROOF_PACK.generated.json"
        ),
        "media_proof_path": (
            f"repo://ArchonMegalon/chummer6-media-factory@{media_head}/"
            ".codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"
        ),
        "final_gold_janitor_path": (
            f"repo://ArchonMegalon/fleet@{head}/"
            "_completion/full_product_reaudit_v20/FINAL_GOLD_JANITOR.generated.json"
        ),
        "live_backed_truth_path": (
            f"repo://ArchonMegalon/fleet@{head}/"
            "_completion/full_product_reaudit_v20/LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json"
        ),
    }


@pytest.mark.parametrize(
    ("override_name", "repository", "relative_path"),
    (
        (
            "rules_certification_path",
            "ArchonMegalon/chummer6-core",
            ".codex-studio/published/ENGINE_PROOF_PACK.generated.json",
        ),
        (
            "media_proof_path",
            "ArchonMegalon/chummer6-media-factory",
            ".codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json",
        ),
        (
            "final_gold_janitor_path",
            "ArchonMegalon/fleet",
            "_completion/full_product_reaudit_v20/FINAL_GOLD_JANITOR.generated.json",
        ),
        (
            "live_backed_truth_path",
            "ArchonMegalon/fleet",
            "_completion/full_product_reaudit_v20/LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json",
        ),
    ),
)
def test_explicit_proof_outside_repository_authority_fails_closed(
    tmp_path: Path,
    monkeypatch,
    override_name: str,
    repository: str,
    relative_path: str,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_remote_commit_reachable", lambda _repository, _commit: True)
    source_repo, head = _create_source_repo(tmp_path)
    unmapped_repo, _unmapped_head = _create_allowed_repo(
        tmp_path,
        directory_name=f"unmapped-{override_name}",
        repository=repository,
        tracked_files={
            relative_path: '{"contract_name":"test.proof","status":"passed"}\n'
        },
    )
    proof_path = unmapped_repo / relative_path
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (("ArchonMegalon/fleet", head),),
    )
    monkeypatch.setattr(
        module,
        "build_flagship_product_readiness_payload",
        lambda **kwargs: {
            "generated_at": "2026-07-20T00:00:00Z",
            "status": "fail",
            override_name: str(kwargs[override_name]),
        },
    )
    runtime_root = tmp_path / "runtime"
    kwargs = {
        name: runtime_root / name
        for name, parameter in inspect.signature(module.materialize_flagship_product_readiness).parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    kwargs.update(
        source_commit=head,
        source_repo_root=source_repo,
        release_repository_authority_path=authority_path,
        release_repository_authority_sha256=authority_sha256,
        out_path=runtime_root / "FLAGSHIP_PRODUCT_READINESS.generated.json",
        mirror_path=None,
        external_proof_runbook_path=None,
    )
    kwargs[override_name] = proof_path

    with pytest.raises(
        ValueError,
        match=rf"invalid machine-local evidence at {override_name}",
    ):
        module.materialize_flagship_product_readiness(**kwargs)


def test_explicit_proof_loader_rejects_final_symlink(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "proof.json"
    target.write_text('{"status":"passed"}\n', encoding="utf-8")
    linked = tmp_path / "linked-proof.json"
    linked.symlink_to(target)

    with pytest.raises(ValueError, match="requires a regular file"):
        module._selected_proof_payload(
            explicit_path=linked,
            candidates=(),
            label="media proof",
        )


def test_explicit_proof_loader_rejects_hard_link(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "proof.json"
    target.write_text('{"status":"passed"}\n', encoding="utf-8")
    linked = tmp_path / "hard-linked-proof.json"
    os.link(target, linked)

    with pytest.raises(ValueError, match="single-link regular file"):
        module._selected_proof_payload(
            explicit_path=linked,
            candidates=(),
            label="final-gold janitor proof",
        )


def test_explicit_proof_loader_overrides_legacy_candidates(tmp_path: Path) -> None:
    module = _load_module()
    legacy = tmp_path / "legacy.json"
    explicit = tmp_path / "explicit.json"
    legacy.write_text('{"status":"failed"}\n', encoding="utf-8")
    explicit.write_text('{"status":"passed"}\n', encoding="utf-8")

    selected_path, payload = module._selected_proof_payload(
        explicit_path=explicit,
        candidates=(legacy,),
        label="rules certification",
    )

    assert selected_path == explicit
    assert payload == {"status": "passed"}


def test_absent_current_live_backed_truth_selects_no_path(tmp_path: Path) -> None:
    module = _load_module()

    selected_path, payload = module._selected_proof_payload(
        explicit_path=None,
        candidates=(tmp_path / "missing-v20-live-backed-truth.json",),
        label="live-backed release truth",
    )

    assert selected_path is None
    assert payload == {}
    assert (str(selected_path) if selected_path else "") == ""


def test_proof_cli_and_environment_overrides_are_explicit(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    env_rules = tmp_path / "env-rules.json"
    env_media = tmp_path / "env-media.json"
    env_janitor = tmp_path / "env-janitor.json"
    env_live = tmp_path / "env-live.json"
    cli_media = tmp_path / "cli-media.json"
    cli_live = tmp_path / "cli-live.json"
    monkeypatch.setenv(module.RULES_CERTIFICATION_ENV, str(env_rules))
    monkeypatch.setenv(module.MEDIA_PROOF_ENV, str(env_media))
    monkeypatch.setenv(module.FINAL_GOLD_JANITOR_ENV, str(env_janitor))
    monkeypatch.setenv(module.LIVE_BACKED_TRUTH_ENV, str(env_live))

    args = module.parse_args(
        [
            "--media-proof",
            str(cli_media),
            "--live-backed-truth",
            str(cli_live),
        ]
    )

    assert args.rules_certification == str(env_rules)
    assert args.media_proof == str(cli_media)
    assert args.final_gold_janitor == str(env_janitor)
    assert args.live_backed_truth == str(cli_live)


def test_materializer_emits_portable_evidence_references(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_remote_commit_reachable", lambda _repository, _commit: True)
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
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (
            ("ArchonMegalon/fleet", head),
            ("ArchonMegalon/chummer6-ui", ui_head),
        ),
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
        release_repository_authority_path=authority_path,
        release_repository_authority_sha256=authority_sha256,
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


def test_repo_reference_rejects_worktree_executable_mode_drift(tmp_path: Path) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
        tracked_files={"proofs/tracked.json": "tracked\n"},
    )
    tracked = repo / "proofs" / "tracked.json"
    tracked.chmod(tracked.stat().st_mode | 0o111)
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    portable = module._portable_public_receipt_value(
        {"tracked": str(tracked)},
        resolver=resolver,
    )

    assert portable["tracked"].startswith(
        f"artifact://ArchonMegalon/chummer6-ui@{head}/sha256/"
    )
    assert portable["tracked"] != (
        f"repo://ArchonMegalon/chummer6-ui@{head}/proofs/tracked.json"
    )


def test_repo_reference_preserves_final_symlink_identity_and_bytes(tmp_path: Path) -> None:
    module = _load_module()
    repo, _head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
        tracked_files={"proofs/target-a.json": "target a\n", "proofs/target-b.json": "target b\n"},
    )
    link = repo / "proofs" / "current.json"
    link.symlink_to("target-a.json")
    subprocess.run(["git", "-C", str(repo), "add", "proofs/current.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add evidence link"], check=True)
    head = _git_head(repo)
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    # Target drift must not change the authority of the committed link itself.
    (repo / "proofs" / "target-a.json").write_text("unreviewed target bytes\n", encoding="utf-8")
    assert module._portable_public_receipt_value(
        {"link": str(link)},
        resolver=resolver,
    ) == {
        "link": f"repo://ArchonMegalon/chummer6-ui@{head}/proofs/current.json"
    }

    link.unlink()
    link.symlink_to("target-b.json")
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)
    assert module._portable_public_receipt_value(
        {"link": str(link)},
        resolver=resolver,
    ) == {"link": None}


def test_repository_checkout_rejects_authority_for_fabricated_local_commit(tmp_path: Path) -> None:
    module = _load_module()
    repo, remotely_reachable_head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    (repo / "local-only.txt").write_text("fabricated local commit\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "local-only.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "local only"], check=True)
    fabricated_head = _git_head(repo)
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (("ArchonMegalon/chummer6-ui", fabricated_head),),
    )
    authority = module._load_release_repository_authority(
        authority_path,
        authority_sha256,
    )

    with pytest.raises(ValueError, match="not remotely reachable"):
        module._repository_checkouts(
            (repo,),
            authority=authority,
            remote_probe=lambda _repository, commit: commit == remotely_reachable_head,
            required_paths=(repo,),
        )


def test_remote_commit_reachable_rejects_ambient_url_rewrite_for_unpublished_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_module()
    repo, _head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    (repo / "local-only.txt").write_text(
        "ambient rewrite must not become GitHub authority\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "local-only.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "local only"], check=True)
    unpublished_commit = _git_head(repo)
    canonical_remote = "https://github.com/ArchonMegalon/chummer6-ui.git"

    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.file://{repo}/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", canonical_remote)
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "always")

    redirected_probe = tmp_path / "ambient-redirect-probe.git"
    subprocess.run(["git", "init", "--bare", "-q", str(redirected_probe)], check=True)
    ambient_fetch = subprocess.run(
        [
            "git",
            "-C",
            str(redirected_probe),
            "fetch",
            "--quiet",
            "--no-tags",
            "--depth=1",
            canonical_remote,
            unpublished_commit,
        ],
        check=False,
        capture_output=True,
        env=os.environ,
    )
    assert ambient_fetch.returncode == 0

    assert not module._remote_commit_reachable(
        "ArchonMegalon/chummer6-ui",
        unpublished_commit,
    )


def test_remote_commit_reachable_uses_filtered_bounded_transport_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_module()
    commit = "a" * 40
    calls: list[tuple[list[str], dict[str, object]]] = []
    fetch_attempts = 0

    def fake_run(args, **kwargs):
        nonlocal fetch_attempts
        command = [str(item) for item in args]
        calls.append((command, dict(kwargs)))
        if "init" in command:
            return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
        if "fetch" in command:
            fetch_attempts += 1
            return subprocess.CompletedProcess(
                command,
                1 if fetch_attempts == 1 else 0,
                stdout=b"",
                stderr=b"",
            )
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout=f"{commit}\n", stderr="")
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._remote_commit_reachable(
        "ArchonMegalon/chummer6-ui",
        commit,
    )
    fetch_calls = [(command, kwargs) for command, kwargs in calls if "fetch" in command]
    assert len(fetch_calls) == 2
    for command, kwargs in fetch_calls:
        assert "--filter=blob:none" in command
        assert "--depth=1" in command
        assert command[-2:] == [
            "https://github.com/ArchonMegalon/chummer6-ui.git",
            commit,
        ]
        assert kwargs["timeout"] == 30
        authority_env = kwargs["env"]
        assert isinstance(authority_env, dict)
        assert authority_env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert authority_env["GIT_CONFIG_GLOBAL"] == os.devnull
        assert authority_env["GIT_TERMINAL_PROMPT"] == "0"


def test_repository_checkout_uses_pinned_authority_not_mutable_origin_config(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "set-url",
            "origin",
            "https://github.com/ArchonMegalon/fleet.git",
        ],
        check=True,
    )
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (("ArchonMegalon/chummer6-ui", head),),
    )
    authority = module._load_release_repository_authority(
        authority_path,
        authority_sha256,
    )

    assert module._repository_checkouts(
        (repo,),
        authority=authority,
        remote_probe=lambda repository, commit: (
            repository == "ArchonMegalon/chummer6-ui" and commit == head
        ),
        required_paths=(repo,),
    ) == (
        module.RepositoryCheckout(
            root=repo.resolve(),
            repository="ArchonMegalon/chummer6-ui",
            commit=head,
        ),
    )


def test_release_repository_authority_digest_pins_exact_input_bytes(tmp_path: Path) -> None:
    module = _load_module()
    authority_path, authority_sha256 = _write_release_authority(
        tmp_path / "repository-authority.json",
        (("ArchonMegalon/fleet", "a" * 40),),
    )
    authority_path.write_bytes(authority_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="digest does not match reviewed bytes"):
        module._load_release_repository_authority(
            authority_path,
            authority_sha256,
        )


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


def test_artifact_json_pointer_remains_valid_after_source_mutation_and_deletion(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo, head = _create_allowed_repo(
        tmp_path,
        directory_name="ui",
        repository="ArchonMegalon/chummer6-ui",
    )
    source = repo / "runtime-proof.json"
    original = b'{"evidence":{"routes":["/status","/downloads"]}}\n'
    source.write_bytes(original)
    resolver = _resolver(module, repositories=(repo,), runtime_commit=head)

    base, staged_payload = resolver.stage_json_artifact(source)
    assert staged_payload["evidence"]["routes"][0] == "/status"
    pointer = resolver.register_reference(
        base + "#%2Fevidence%2Froutes%2F0"
    )
    source.write_text('{"evidence":{"routes":["/wrong"]}}\n', encoding="utf-8")
    source.unlink()

    module._validate_portable_public_receipt(
        {"routeAuthority": pointer},
        resolver=resolver,
    )
    inventory = resolver.artifact_locator_inventory()
    assert inventory["artifacts"] == [
        {
            "authority": base,
            "sha256": hashlib.sha256(original).hexdigest(),
            "kind": "file",
            "size": len(original),
            "locator": (
                "artifact-cas/sha256/"
                + hashlib.sha256(original).hexdigest()[:2]
                + "/"
                + hashlib.sha256(original).hexdigest()
                + ".blob"
            ),
        }
    ]


def test_public_routes_are_not_misclassified_as_machine_local_paths() -> None:
    module = _load_module()
    resolver = _resolver(module)
    routes = ["/status", "/downloads", "/api/releases/current", "/healthz"]

    assert module._portable_public_receipt_value(
        {"routes": routes},
        resolver=resolver,
    ) == {"routes": routes}


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
