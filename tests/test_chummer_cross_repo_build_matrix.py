from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_chummer_cross_repo_build_matrix import (
    CHECKOUT_ACTION,
    ContractError,
    canonical_matrix_digest,
    load_json,
    validate_matrix,
    validate_schema_definition,
    validate_workflow_definition,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests/fixtures/chummer_cross_repo_build_matrix.synthetic.json"
SCHEMA_PATH = REPO_ROOT / "config/chummer_cross_repo_build_matrix.schema.json"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/chummer-cross-repo-build-matrix.yml"


def fixture() -> dict:
    return load_json(FIXTURE_PATH, label="test fixture")


def resign(payload: dict) -> dict:
    payload["matrixDigest"] = canonical_matrix_digest(payload)
    return payload


def invalid(payload: dict, match: str) -> None:
    with pytest.raises(ContractError, match=match):
        validate_matrix(payload)


def test_checked_in_schema_workflow_and_synthetic_fixture_are_closed_world_valid() -> None:
    schema = load_json(SCHEMA_PATH, label="schema")
    workflow = load_json(WORKFLOW_PATH, label="workflow")
    payload = fixture()

    validate_schema_definition(schema)
    validate_workflow_definition(workflow)
    validate_matrix(payload)

    assert payload["mode"] == "synthetic-fixture"
    assert payload["matrixDigest"] == canonical_matrix_digest(payload)
    assert [row["repositoryId"] for row in payload["rows"]] == [
        "chummer-android",
        "chummer6-ui",
        "chummer6-core",
        "chummer6-hub",
        "chummer6-hub-registry",
        "chummer6-ui-kit",
        "chummer6-media-factory",
        "chummer6-design",
        "chummer5a",
    ]


@pytest.mark.parametrize("field", ["contractName", "mode", "rows", "workflowPosture", "matrixDigest"])
def test_missing_root_field_fails_closed(field: str) -> None:
    payload = fixture()
    payload.pop(field)
    invalid(payload, "matrix fields differ")


def test_extra_root_field_fails_even_when_attacker_resigns_payload() -> None:
    payload = fixture()
    payload["releaseStatus"] = "passed"
    resign(payload)
    invalid(payload, "extra=\\['releaseStatus'\\]")


def test_missing_extra_reordered_and_wrong_repository_rows_fail_closed() -> None:
    missing = fixture()
    missing["rows"].pop()
    resign(missing)
    invalid(missing, "exactly 9")

    extra = fixture()
    extra["rows"].append(copy.deepcopy(extra["rows"][-1]))
    extra["rows"][-1]["repositoryId"] = "unowned-repo"
    extra["rows"][-1]["repository"] = "ArchonMegalon/unowned-repo"
    extra["rows"][-1]["artifactName"] = "synthetic-unowned-repo-build-proof"
    resign(extra)
    invalid(extra, "exactly 9")

    reordered = fixture()
    reordered["rows"][0], reordered["rows"][1] = reordered["rows"][1], reordered["rows"][0]
    resign(reordered)
    invalid(reordered, "exact ordered closed-world")

    wrong = fixture()
    wrong["rows"][0]["repository"] = "ArchonMegalon/chummer-android-fork"
    resign(wrong)
    invalid(wrong, "exact ordered closed-world")


@pytest.mark.parametrize("field", ["repositoryId", "repository", "artifactName"])
def test_duplicate_and_case_colliding_row_identities_fail_closed(field: str) -> None:
    duplicate = fixture()
    duplicate["rows"][1][field] = duplicate["rows"][0][field]
    resign(duplicate)
    invalid(duplicate, "duplicate")

    collision = fixture()
    collision["rows"][1][field] = duplicate["rows"][0][field].upper()
    resign(collision)
    if field in {"repositoryId", "artifactName"}:
        invalid(collision, "not canonical")
    else:
        invalid(collision, "case-collision")


@pytest.mark.parametrize("value", ["latest", "main", "a" * 39, "A" * 40, "a" * 41])
def test_refs_require_exact_lowercase_sha40(value: str) -> None:
    payload = fixture()
    payload["rows"][0]["ref"] = value
    resign(payload)
    invalid(payload, "ref must be a lowercase hexadecimal digest")


@pytest.mark.parametrize("value", ["0" * 40, "a" * 40, "01" * 20])
def test_refs_reject_low_entropy_placeholder_digests(value: str) -> None:
    payload = fixture()
    payload["rows"][0]["ref"] = value
    resign(payload)
    invalid(payload, "low-entropy placeholder digest")


@pytest.mark.parametrize("field", ["assetsSha256", "membersSha256", "artifactSha256"])
@pytest.mark.parametrize("value", ["latest", "b" * 63, "B" * 64, "b" * 65])
def test_asset_member_and_artifact_bindings_require_sha256(field: str, value: str) -> None:
    payload = fixture()
    payload["rows"][0][field] = value
    resign(payload)
    invalid(payload, f"{field} must be a lowercase hexadecimal digest")


@pytest.mark.parametrize("field", ["assetsSha256", "membersSha256", "artifactSha256"])
@pytest.mark.parametrize("value", ["0" * 64, "b" * 64, "01" * 32])
def test_asset_member_and_artifact_bindings_reject_placeholder_sha256(
    field: str, value: str
) -> None:
    payload = fixture()
    payload["rows"][0][field] = value
    resign(payload)
    invalid(payload, "low-entropy placeholder digest")


@pytest.mark.parametrize("field", ["runId", "runAttempt", "artifactId"])
@pytest.mark.parametrize("value", [False, 0, -1, "1", 1.5])
def test_run_attempt_and_artifact_ids_are_exact_positive_integers(field: str, value: object) -> None:
    payload = fixture()
    payload["rows"][0][field] = value
    resign(payload)
    invalid(payload, f"{field} must be an integer")


def test_run_attempt_has_a_bounded_upper_limit() -> None:
    payload = fixture()
    payload["rows"][0]["runAttempt"] = 1001
    resign(payload)
    invalid(payload, "runAttempt must be an integer in \\[1, 1000\\]")


def test_duplicate_artifact_id_fails_closed_even_when_resigned() -> None:
    payload = fixture()
    payload["rows"][1]["artifactId"] = payload["rows"][0]["artifactId"]
    resign(payload)
    invalid(payload, "duplicate artifactId")


@pytest.mark.parametrize(
    "field",
    [
        "repositoryId",
        "repository",
        "ref",
        "assetsSha256",
        "membersSha256",
        "runId",
        "runAttempt",
        "artifactId",
        "artifactName",
        "artifactSha256",
    ],
)
def test_missing_exact_row_field_fails_even_when_resigned(field: str) -> None:
    payload = fixture()
    payload["rows"][0].pop(field)
    resign(payload)
    invalid(payload, "rows\\[0\\] fields differ")


def test_extra_exact_row_field_fails_even_when_resigned() -> None:
    payload = fixture()
    payload["rows"][0]["artifactUrl"] = "https://invalid.test/artifact"
    resign(payload)
    invalid(payload, "extra=\\['artifactUrl'\\]")


@pytest.mark.parametrize(
    "repository",
    [
        "ArchonMegalon/latest",
        "ArchonMegalon/sibling",
        "ArchonMegalon/siblings",
        "ArchonMegalon/placeholder",
    ],
)
def test_stale_or_sibling_repository_bindings_fail_closed(repository: str) -> None:
    payload = fixture()
    payload["rows"][0]["repository"] = repository
    resign(payload)
    invalid(payload, "stale/mutable binding")


@pytest.mark.parametrize(
    "artifact_name",
    [
        "synthetic-latest-build-proof",
        "synthetic-main-build-proof",
        "synthetic-siblings-build-proof",
        "synthetic-placeholder-build-proof",
        "synthetic-todo-build-proof",
    ],
)
def test_stale_or_sibling_artifact_placeholders_fail_closed(artifact_name: str) -> None:
    payload = fixture()
    payload["rows"][0]["artifactName"] = artifact_name
    resign(payload)
    invalid(payload, "stale/mutable binding")


def test_synthetic_and_candidate_artifact_names_cannot_be_confused() -> None:
    synthetic = fixture()
    synthetic["rows"][0]["artifactName"] = "candidate-chummer-android-build-proof"
    resign(synthetic)
    invalid(synthetic, "synthetic-fixture artifact names")

    candidate_shaped = fixture()
    candidate_shaped["mode"] = "candidate-bound"
    for row in candidate_shaped["rows"]:
        row["artifactName"] = row["artifactName"].removeprefix("synthetic-")
    resign(candidate_shaped)
    validate_matrix(candidate_shaped)

    candidate_shaped["rows"][0]["artifactName"] = "synthetic-chummer-android-build-proof"
    resign(candidate_shaped)
    invalid(candidate_shaped, "candidate-bound artifact names")


def test_canonical_digest_covers_every_nested_binding() -> None:
    payload = fixture()
    original = payload["matrixDigest"]
    payload["rows"][4]["membersSha256"] = payload["rows"][5]["membersSha256"]
    assert canonical_matrix_digest(payload) != original
    invalid(payload, "matrixDigest does not match")


def test_resigning_cannot_hide_a_forbidden_posture_or_extra_field() -> None:
    payload = fixture()
    payload["workflowPosture"]["runner"] = "ubuntu-latest"
    resign(payload)
    invalid(payload, "runner must be ubuntu-24.04")

    payload = fixture()
    payload["workflowPosture"]["android"]["channel"] = "latest"
    resign(payload)
    invalid(payload, "android fields differ")


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("dotnetSdk",), "10.0.x", "dotnetSdk must be 10.0.110"),
        (("android", "apiLevel"), 35, "API 36"),
        (("android", "systemImage"), "default", "API 36"),
        (("android", "architecture"), "arm64-v8a", "API 36"),
        (("android", "deviceProfile"), "pixel", "API 36"),
    ],
)
def test_exact_toolchain_posture_is_required(path: tuple[str, ...], value: object, match: str) -> None:
    payload = fixture()
    target = payload["workflowPosture"]
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = value
    resign(payload)
    invalid(payload, match)


def test_journeys_reject_missing_extra_reordered_duplicate_and_case_collision() -> None:
    mutations = [
        lambda values: values.pop(),
        lambda values: values.append("invented-journey"),
        lambda values: values.reverse(),
        lambda values: values.__setitem__(1, values[0]),
        lambda values: values.__setitem__(1, values[0].upper()),
    ]
    for mutate in mutations:
        payload = fixture()
        mutate(payload["workflowPosture"]["journeys"])
        resign(payload)
        invalid(payload, "journeys")


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ('{"contractName":"a","contractName":"b"}', "duplicate JSON key"),
        ('{"ref":"a","Ref":"b"}', "case-colliding JSON keys"),
        ('{"value":NaN}', "non-finite JSON number"),
    ],
)
def test_strict_json_loader_rejects_duplicate_case_collision_and_nonfinite(
    tmp_path: Path, raw: str, match: str
) -> None:
    path = tmp_path / "hostile.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ContractError, match=match):
        load_json(path, label="hostile")


def test_schema_validator_rejects_open_or_cardinality_drift() -> None:
    schema = load_json(SCHEMA_PATH, label="schema")
    validate_schema_definition(schema)

    opened = copy.deepcopy(schema)
    opened["$defs"]["repositoryRow"]["additionalProperties"] = True
    with pytest.raises(ContractError, match="repositoryRow must be closed"):
        validate_schema_definition(opened)

    cardinality = copy.deepcopy(schema)
    cardinality["properties"]["rows"]["maxItems"] = 10
    with pytest.raises(ContractError, match="cardinality drifted"):
        validate_schema_definition(cardinality)

    digest_pattern = copy.deepcopy(schema)
    digest_pattern["$defs"]["sha40"]["pattern"] = ".*"
    with pytest.raises(ContractError, match="SHA-40 definition drifted"):
        validate_schema_definition(digest_pattern)


def test_workflow_is_inactive_read_only_and_sha_pinned() -> None:
    workflow = load_json(WORKFLOW_PATH, label="workflow")
    validate_workflow_definition(workflow)

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["inactive-build-matrix-skeleton"]["if"] == "${{ false }}"
    assert workflow["jobs"]["contract-tests"]["steps"][0]["uses"] == CHECKOUT_ACTION


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda workflow: workflow["jobs"]["contract-tests"]["steps"][0].__setitem__(
                "uses", "actions/checkout@v4"
            ),
            "contract-tests steps drifted",
        ),
        (
            lambda workflow: workflow["jobs"]["inactive-build-matrix-skeleton"].__setitem__(
                "if", "${{ true }}"
            ),
            "statically inactive",
        ),
        (
            lambda workflow: workflow["jobs"]["inactive-build-matrix-skeleton"].__setitem__(
                "runs-on", "ubuntu-latest"
            ),
            "runner/timeout posture drifted",
        ),
        (
            lambda workflow: workflow["jobs"]["inactive-build-matrix-skeleton"]["strategy"][
                "matrix"
            ]["journey"].append("invented"),
            "journeys drifted",
        ),
        (
            lambda workflow: workflow["jobs"].__setitem__("publish", {"runs-on": "ubuntu-24.04"}),
            "workflow.jobs fields differ",
        ),
        (
            lambda workflow: workflow["on"].__setitem__("push", {"branches": ["main"]}),
            "workflow.on fields differ",
        ),
    ],
)
def test_workflow_drift_fails_closed(mutator, match: str) -> None:
    workflow = load_json(WORKFLOW_PATH, label="workflow")
    mutator(workflow)
    with pytest.raises(ContractError, match=match):
        validate_workflow_definition(workflow)


def test_workflow_rejects_any_additional_unpinned_action() -> None:
    workflow = load_json(WORKFLOW_PATH, label="workflow")
    workflow["jobs"]["contract-tests"]["steps"].append(
        {"name": "Mutable action", "uses": "actions/setup-dotnet@v5"}
    )
    with pytest.raises(ContractError, match="contract-tests steps drifted"):
        validate_workflow_definition(workflow)
