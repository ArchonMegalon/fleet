#!/usr/bin/env python3
"""Fail-closed validation for Fleet's Chummer cross-repository matrix contract.

This validator deliberately performs no network access, repository checkout,
artifact download, publication, or release-state mutation.  It validates only
the supplied bytes and the static, inactive workflow skeleton.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


CONTRACT_NAME = "chummer.cross-repo-build-matrix/v1"
EXPECTED_REPOSITORIES: tuple[tuple[str, str], ...] = (
    ("chummer-android", "ArchonMegalon/chummer-android"),
    ("chummer6-ui", "ArchonMegalon/chummer6-ui"),
    ("chummer6-core", "ArchonMegalon/chummer6-core"),
    ("chummer6-hub", "ArchonMegalon/chummer6-hub"),
    ("chummer6-hub-registry", "ArchonMegalon/chummer6-hub-registry"),
    ("chummer6-ui-kit", "ArchonMegalon/chummer6-ui-kit"),
    ("chummer6-media-factory", "ArchonMegalon/chummer6-media-factory"),
    ("chummer6-design", "ArchonMegalon/chummer6-design"),
    ("chummer5a", "ArchonMegalon/chummer5a"),
)
EXPECTED_JOURNEYS: tuple[str, ...] = (
    "full-editing",
    "creation-prerequisite",
    "career-active-skill-advance",
    "career-weapon-fire",
)
EXPECTED_WORKFLOW_POSTURE: dict[str, Any] = {
    "runner": "ubuntu-24.04",
    "dotnetSdk": "10.0.110",
    "android": {
        "apiLevel": 36,
        "systemImage": "google_apis",
        "architecture": "x86_64",
        "deviceProfile": "pixel_6",
    },
    "journeys": list(EXPECTED_JOURNEYS),
}
ROOT_KEYS = {"contractName", "mode", "rows", "workflowPosture", "matrixDigest"}
ROW_KEYS = {
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
}
POSTURE_KEYS = {"runner", "dotnetSdk", "android", "journeys"}
ANDROID_KEYS = {"apiLevel", "systemImage", "architecture", "deviceProfile"}
SHA40_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
ACTION_PIN_RE = re.compile(r"[^/@\s]+/[^@\s]+@[0-9a-f]{40}\Z")
STALE_BINDING_TOKENS = {
    "head",
    "latest",
    "local",
    "main",
    "master",
    "pending",
    "placeholder",
    "replace",
    "sibling",
    "siblings",
    "tbd",
    "todo",
    "unknown",
}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_RUN_ID = 9223372036854775807
CHECKOUT_ACTION = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"


class ContractError(ValueError):
    """Raised when contract bytes are not closed-world valid."""


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folded: dict[str, str] = {}
    for key, value in pairs:
        if not isinstance(key, str):
            raise ContractError("JSON object keys must be strings")
        normalized = key.casefold()
        previous = folded.get(normalized)
        if previous is not None:
            if previous == key:
                raise ContractError(f"duplicate JSON key: {key}")
            raise ContractError(f"case-colliding JSON keys: {previous} / {key}")
        folded[normalized] = key
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ContractError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"{label} cannot be read: {path}: {exc}") from exc
    if not raw or len(raw) > MAX_JSON_BYTES:
        raise ContractError(f"{label} size is outside the accepted range")
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ContractError) as exc:
        raise ContractError(f"{label} is not strict JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{label} root must be an object")
    return payload


def _require_exact_keys(value: Any, expected: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractError(f"{label} fields differ; missing={missing}; extra={extra}")
    return value


def _require_exact_list(value: Any, expected: Iterable[str], *, label: str) -> list[str]:
    expected_list = list(expected)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractError(f"{label} must be a string array")
    folded = [item.casefold() for item in value]
    if len(folded) != len(set(folded)):
        raise ContractError(f"{label} contains duplicate or case-colliding values")
    if value != expected_list:
        raise ContractError(f"{label} must equal {expected_list}")
    return value


def _require_sha(value: Any, pattern: re.Pattern[str], *, label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ContractError(f"{label} must be a lowercase hexadecimal digest")
    if len(set(value)) < 4:
        raise ContractError(f"{label} is a low-entropy placeholder digest")
    return value


def _require_positive_int(value: Any, *, label: str, maximum: int = MAX_RUN_ID) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ContractError(f"{label} must be an integer in [1, {maximum}]")
    return value


def _binding_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.casefold()) if token}


def _reject_stale_binding(value: str, *, label: str) -> None:
    stale = sorted(_binding_tokens(value) & STALE_BINDING_TOKENS)
    if stale:
        raise ContractError(f"{label} contains stale/mutable binding token(s): {stale}")


def canonical_matrix_digest(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "matrixDigest"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_workflow_posture(value: Any) -> None:
    posture = _require_exact_keys(value, POSTURE_KEYS, label="workflowPosture")
    android = _require_exact_keys(posture["android"], ANDROID_KEYS, label="workflowPosture.android")
    expected_android = EXPECTED_WORKFLOW_POSTURE["android"]
    if posture["runner"] != EXPECTED_WORKFLOW_POSTURE["runner"]:
        raise ContractError("workflowPosture.runner must be ubuntu-24.04")
    if posture["dotnetSdk"] != EXPECTED_WORKFLOW_POSTURE["dotnetSdk"]:
        raise ContractError("workflowPosture.dotnetSdk must be 10.0.110")
    if android != expected_android:
        raise ContractError("workflowPosture.android must be API 36 google_apis/x86_64/pixel_6")
    _require_exact_list(posture["journeys"], EXPECTED_JOURNEYS, label="workflowPosture.journeys")


def validate_matrix(payload: dict[str, Any]) -> None:
    root = _require_exact_keys(payload, ROOT_KEYS, label="matrix")
    if root["contractName"] != CONTRACT_NAME:
        raise ContractError(f"contractName must be {CONTRACT_NAME}")
    mode = root["mode"]
    if mode not in {"synthetic-fixture", "candidate-bound"}:
        raise ContractError("mode must be synthetic-fixture or candidate-bound")
    validate_workflow_posture(root["workflowPosture"])

    rows = root["rows"]
    if not isinstance(rows, list):
        raise ContractError("rows must be an array")
    if len(rows) != len(EXPECTED_REPOSITORIES):
        raise ContractError(f"rows must contain exactly {len(EXPECTED_REPOSITORIES)} repositories")

    seen_ids: dict[str, str] = {}
    seen_repositories: dict[str, str] = {}
    seen_artifact_names: dict[str, str] = {}
    seen_artifact_ids: set[int] = set()
    actual_repositories: list[tuple[str, str]] = []
    for index, raw_row in enumerate(rows):
        row = _require_exact_keys(raw_row, ROW_KEYS, label=f"rows[{index}]")
        repository_id = row["repositoryId"]
        repository = row["repository"]
        artifact_name = row["artifactName"]
        if not isinstance(repository_id, str) or ARTIFACT_NAME_RE.fullmatch(repository_id) is None:
            raise ContractError(f"rows[{index}].repositoryId is not canonical")
        if not isinstance(repository, str):
            raise ContractError(f"rows[{index}].repository must be a string")
        if not isinstance(artifact_name, str) or ARTIFACT_NAME_RE.fullmatch(artifact_name) is None:
            raise ContractError(f"rows[{index}].artifactName is not canonical")
        if not 3 <= len(artifact_name) <= 160:
            raise ContractError(f"rows[{index}].artifactName length is outside [3, 160]")
        _reject_stale_binding(repository, label=f"rows[{index}].repository")
        _reject_stale_binding(artifact_name, label=f"rows[{index}].artifactName")

        for value, seen, label in (
            (repository_id, seen_ids, "repositoryId"),
            (repository, seen_repositories, "repository"),
            (artifact_name, seen_artifact_names, "artifactName"),
        ):
            folded = value.casefold()
            previous = seen.get(folded)
            if previous is not None:
                collision = "duplicate" if previous == value else "case-collision"
                raise ContractError(f"rows contain {collision} {label}: {previous} / {value}")
            seen[folded] = value

        _require_sha(row["ref"], SHA40_RE, label=f"rows[{index}].ref")
        _require_sha(row["assetsSha256"], SHA256_RE, label=f"rows[{index}].assetsSha256")
        _require_sha(row["membersSha256"], SHA256_RE, label=f"rows[{index}].membersSha256")
        _require_positive_int(row["runId"], label=f"rows[{index}].runId")
        _require_positive_int(row["runAttempt"], label=f"rows[{index}].runAttempt", maximum=1000)
        artifact_id = _require_positive_int(row["artifactId"], label=f"rows[{index}].artifactId")
        if artifact_id in seen_artifact_ids:
            raise ContractError(f"rows contain duplicate artifactId: {artifact_id}")
        seen_artifact_ids.add(artifact_id)
        _require_sha(row["artifactSha256"], SHA256_RE, label=f"rows[{index}].artifactSha256")

        if mode == "synthetic-fixture" and not artifact_name.startswith("synthetic-"):
            raise ContractError("synthetic-fixture artifact names must start with synthetic-")
        if mode == "candidate-bound" and artifact_name.startswith("synthetic-"):
            raise ContractError("candidate-bound artifact names must not start with synthetic-")
        actual_repositories.append((repository_id, repository))

    if tuple(actual_repositories) != EXPECTED_REPOSITORIES:
        raise ContractError(
            "rows must match the exact ordered closed-world repository set: "
            + ", ".join(item[0] for item in EXPECTED_REPOSITORIES)
        )

    supplied_digest = _require_sha(root["matrixDigest"], SHA256_RE, label="matrixDigest")
    expected_digest = canonical_matrix_digest(root)
    if not hmac.compare_digest(supplied_digest, expected_digest):
        raise ContractError("matrixDigest does not match canonical matrix bytes")


def validate_schema_definition(schema: dict[str, Any]) -> None:
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ContractError("schema must use JSON Schema draft 2020-12")
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise ContractError("schema root must be a closed object")
    if set(schema.get("required") or []) != ROOT_KEYS:
        raise ContractError("schema root required fields drifted")
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        raise ContractError("schema $defs are missing")
    if set(definitions) != {"sha40", "sha256", "repositoryRow", "workflowPosture"}:
        raise ContractError("schema $defs differ from the closed contract")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or set(properties) != ROOT_KEYS:
        raise ContractError("schema root properties drifted")
    if properties.get("contractName") != {"const": CONTRACT_NAME}:
        raise ContractError("schema contractName const drifted")
    if properties.get("mode") != {"enum": ["synthetic-fixture", "candidate-bound"]}:
        raise ContractError("schema mode enum drifted")
    if properties.get("matrixDigest") != {"$ref": "#/$defs/sha256"}:
        raise ContractError("schema matrixDigest binding drifted")
    if definitions.get("sha40") != {"type": "string", "pattern": "^[0-9a-f]{40}$"}:
        raise ContractError("schema SHA-40 definition drifted")
    if definitions.get("sha256") != {"type": "string", "pattern": "^[0-9a-f]{64}$"}:
        raise ContractError("schema SHA-256 definition drifted")
    row = definitions.get("repositoryRow")
    posture = definitions.get("workflowPosture")
    android = ((posture or {}).get("properties") or {}).get("android")
    if not isinstance(row, dict) or row.get("additionalProperties") is not False:
        raise ContractError("schema repositoryRow must be closed")
    if set(row.get("required") or []) != ROW_KEYS:
        raise ContractError("schema repositoryRow required fields drifted")
    row_properties = row.get("properties")
    if not isinstance(row_properties, dict) or set(row_properties) != ROW_KEYS:
        raise ContractError("schema repositoryRow properties drifted")
    if row_properties.get("repositoryId") != {
        "type": "string",
        "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
    }:
        raise ContractError("schema repositoryId binding drifted")
    if row_properties.get("repository") != {
        "type": "string",
        "pattern": "^ArchonMegalon/[A-Za-z0-9][A-Za-z0-9._-]*$",
    }:
        raise ContractError("schema repository binding drifted")
    if row_properties.get("artifactName") != {
        "type": "string",
        "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
        "minLength": 3,
        "maxLength": 160,
    }:
        raise ContractError("schema artifactName binding drifted")
    for digest_field, reference in (
        ("ref", "#/$defs/sha40"),
        ("assetsSha256", "#/$defs/sha256"),
        ("membersSha256", "#/$defs/sha256"),
        ("artifactSha256", "#/$defs/sha256"),
    ):
        if row_properties.get(digest_field) != {"$ref": reference}:
            raise ContractError(f"schema {digest_field} digest binding drifted")
    for integer_field, maximum in (
        ("runId", MAX_RUN_ID),
        ("runAttempt", 1000),
        ("artifactId", MAX_RUN_ID),
    ):
        if row_properties.get(integer_field) != {
            "type": "integer",
            "minimum": 1,
            "maximum": maximum,
        }:
            raise ContractError(f"schema {integer_field} integer binding drifted")
    if not isinstance(posture, dict) or posture.get("additionalProperties") is not False:
        raise ContractError("schema workflowPosture must be closed")
    if set(posture.get("required") or []) != POSTURE_KEYS:
        raise ContractError("schema workflowPosture required fields drifted")
    posture_properties = posture.get("properties")
    if not isinstance(posture_properties, dict) or set(posture_properties) != POSTURE_KEYS:
        raise ContractError("schema workflowPosture properties drifted")
    if posture_properties.get("runner") != {"const": "ubuntu-24.04"}:
        raise ContractError("schema runner const drifted")
    if posture_properties.get("dotnetSdk") != {"const": "10.0.110"}:
        raise ContractError("schema .NET SDK const drifted")
    if not isinstance(android, dict) or android.get("additionalProperties") is not False:
        raise ContractError("schema workflowPosture.android must be closed")
    if set(android.get("required") or []) != ANDROID_KEYS:
        raise ContractError("schema workflowPosture.android required fields drifted")
    if android.get("properties") != {
        "apiLevel": {"const": 36},
        "systemImage": {"const": "google_apis"},
        "architecture": {"const": "x86_64"},
        "deviceProfile": {"const": "pixel_6"},
    }:
        raise ContractError("schema Android posture drifted")
    journeys = posture_properties.get("journeys")
    if journeys != {
        "type": "array",
        "minItems": len(EXPECTED_JOURNEYS),
        "maxItems": len(EXPECTED_JOURNEYS),
        "uniqueItems": True,
        "items": {"enum": list(EXPECTED_JOURNEYS)},
    }:
        raise ContractError("schema journey posture drifted")
    rows = properties.get("rows") or {}
    if rows.get("minItems") != len(EXPECTED_REPOSITORIES) or rows.get("maxItems") != len(EXPECTED_REPOSITORIES):
        raise ContractError("schema rows cardinality drifted")
    if rows.get("items") != {"$ref": "#/$defs/repositoryRow"}:
        raise ContractError("schema rows item binding drifted")


def _collect_action_uses(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "uses":
                if not isinstance(child, str):
                    raise ContractError("workflow uses values must be strings")
                result.append(child)
            result.extend(_collect_action_uses(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_collect_action_uses(child))
    return result


def validate_workflow_definition(workflow: dict[str, Any]) -> None:
    _require_exact_keys(workflow, {"name", "on", "permissions", "jobs"}, label="workflow")
    if workflow["name"] != "Chummer cross-repository build matrix contract":
        raise ContractError("workflow name drifted")
    triggers = _require_exact_keys(workflow["on"], {"pull_request", "workflow_dispatch"}, label="workflow.on")
    _require_exact_keys(triggers["workflow_dispatch"], set(), label="workflow.on.workflow_dispatch")
    pull_request = _require_exact_keys(triggers["pull_request"], {"paths"}, label="workflow.on.pull_request")
    expected_paths = [
        ".github/workflows/chummer-cross-repo-build-matrix.yml",
        ".github/requirements-cross-repo-matrix.txt",
        "config/chummer_cross_repo_build_matrix.schema.json",
        "scripts/verify_chummer_cross_repo_build_matrix.py",
        "tests/fixtures/chummer_cross_repo_build_matrix.synthetic.json",
        "tests/test_chummer_cross_repo_build_matrix.py",
    ]
    _require_exact_list(pull_request["paths"], expected_paths, label="workflow.on.pull_request.paths")
    if workflow["permissions"] != {"contents": "read"}:
        raise ContractError("workflow permissions must be contents: read only")

    jobs = _require_exact_keys(
        workflow["jobs"],
        {"contract-tests", "inactive-build-matrix-skeleton"},
        label="workflow.jobs",
    )
    tests_job = _require_exact_keys(
        jobs["contract-tests"],
        {"name", "runs-on", "timeout-minutes", "steps"},
        label="workflow.jobs.contract-tests",
    )
    if tests_job["runs-on"] != "ubuntu-24.04" or tests_job["timeout-minutes"] != 10:
        raise ContractError("contract-tests runner/timeout posture drifted")
    if tests_job["name"] != "Synthetic contract and fail-closed tests":
        raise ContractError("contract-tests name drifted")
    expected_test_steps = [
        {
            "name": "Check out exact Fleet revision",
            "uses": CHECKOUT_ACTION,
            "with": {"fetch-depth": 1, "persist-credentials": False},
        },
        {
            "name": "Create hash-locked Python environment",
            "run": "\n".join(
                [
                    "set -euo pipefail",
                    'python3 -m venv "$RUNNER_TEMP/chummer-matrix-python"',
                    '"$RUNNER_TEMP/chummer-matrix-python/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes --requirement .github/requirements-cross-repo-matrix.txt',
                ]
            ),
        },
        {
            "name": "Compile validator",
            "run": '"$RUNNER_TEMP/chummer-matrix-python/bin/python" -m py_compile scripts/verify_chummer_cross_repo_build_matrix.py',
        },
        {
            "name": "Run synthetic contract tests",
            "run": '"$RUNNER_TEMP/chummer-matrix-python/bin/python" -m pytest -q tests/test_chummer_cross_repo_build_matrix.py',
        },
        {
            "name": "Validate synthetic matrix and inactive workflow",
            "run": '"$RUNNER_TEMP/chummer-matrix-python/bin/python" scripts/verify_chummer_cross_repo_build_matrix.py --matrix tests/fixtures/chummer_cross_repo_build_matrix.synthetic.json',
        },
    ]
    if tests_job["steps"] != expected_test_steps:
        raise ContractError("contract-tests steps drifted")

    skeleton = _require_exact_keys(
        jobs["inactive-build-matrix-skeleton"],
        {"name", "if", "runs-on", "timeout-minutes", "strategy", "env", "steps"},
        label="workflow.jobs.inactive-build-matrix-skeleton",
    )
    if skeleton["if"] != "${{ false }}":
        raise ContractError("build-matrix skeleton must remain statically inactive")
    if skeleton["name"] != "Inactive API36 journey skeleton (${{ matrix.journey }})":
        raise ContractError("build-matrix skeleton name drifted")
    if skeleton["runs-on"] != "ubuntu-24.04" or skeleton["timeout-minutes"] != 1:
        raise ContractError("build-matrix skeleton runner/timeout posture drifted")
    if skeleton["strategy"] != {"fail-fast": False, "matrix": {"journey": list(EXPECTED_JOURNEYS)}}:
        raise ContractError("build-matrix skeleton journeys drifted")
    if skeleton["env"] != {
        "DOTNET_SDK_VERSION": "10.0.110",
        "ANDROID_API_LEVEL": "36",
        "ANDROID_SYSTEM_IMAGE": "google_apis",
        "ANDROID_ARCHITECTURE": "x86_64",
        "ANDROID_DEVICE_PROFILE": "pixel_6",
    }:
        raise ContractError("build-matrix skeleton toolchain posture drifted")
    if skeleton["steps"] != [
        {
            "name": "Inactive by design",
            "run": "echo 'Synthetic contract skeleton only; no repository or artifact is consumed.'",
        }
    ]:
        raise ContractError("build-matrix skeleton steps drifted")

    action_uses = _collect_action_uses(workflow)
    if action_uses != [CHECKOUT_ACTION]:
        raise ContractError("workflow must use only the exact pinned checkout action")
    for action in action_uses:
        if ACTION_PIN_RE.fullmatch(action) is None:
            raise ContractError(f"workflow action is not SHA-40 pinned: {action}")

    serialized = json.dumps(workflow, sort_keys=True).casefold()
    for token in ("ubuntu-latest", "@main", "@master", "siblings", "../"):
        if token in serialized:
            raise ContractError(f"workflow contains forbidden mutable/sibling token: {token}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("config/chummer_cross_repo_build_matrix.schema.json"),
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=Path(".github/workflows/chummer-cross-repo-build-matrix.yml"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        schema = load_json(args.schema, label="schema")
        workflow = load_json(args.workflow, label="workflow")
        matrix = load_json(args.matrix, label="matrix")
        validate_schema_definition(schema)
        validate_workflow_definition(workflow)
        validate_matrix(matrix)
    except ContractError as exc:
        print(f"cross-repo-build-matrix invalid: {exc}", file=sys.stderr)
        return 1
    print("cross-repo-build-matrix contract valid (no live authority asserted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
