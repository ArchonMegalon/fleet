#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import PurePosixPath
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts.external_proof_paths import resolve_release_channel_path
except ModuleNotFoundError:
    from external_proof_paths import resolve_release_channel_path


DEFAULT_REPO = "ArchonMegalon/Chummer6"
DEFAULT_REPO_SPEC = str(os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO).strip() or DEFAULT_REPO
REPO_SPEC = str(os.environ.get("CHUMMER_GITHUB_RELEASE_REPO") or DEFAULT_REPO_SPEC).strip() or DEFAULT_REPO_SPEC
OWNER, REPO = REPO_SPEC.split("/", 1)
TAG = str(os.environ.get("CHUMMER_GITHUB_RELEASE_TAG") or "desktop-latest").strip() or "desktop-latest"
TITLE = str(os.environ.get("CHUMMER_GITHUB_RELEASE_TITLE") or "Chummer6 Desktop Latest").strip() or "Chummer6 Desktop Latest"
TARGET_COMMITISH = (
    str(os.environ.get("CHUMMER_GITHUB_RELEASE_TARGET_COMMITISH") or os.environ.get("GITHUB_SHA") or "main").strip()
    or "main"
)
RELEASE_CONTROL_SCRIPT = Path("/docker/fleet/scripts/materialize_chummer_release_registry_projection.py")
DEFAULT_RELEASE_CHANNEL_PATH = resolve_release_channel_path()
DOWNLOADS_MANIFEST = Path(
    os.environ.get("CHUMMER6_RELEASE_CHANNEL_PATH")
    or str(DEFAULT_RELEASE_CHANNEL_PATH)
)
COMPAT_DOWNLOADS_MANIFEST = Path(
    os.environ.get("CHUMMER6_RELEASE_COMPAT_PATH")
    or str(DEFAULT_RELEASE_CHANNEL_PATH.with_name("releases.json"))
)
DOWNLOADS_FILES_DIR = Path(
    os.environ.get("CHUMMER6_RELEASE_FILES_DIR")
    or "/docker/chummercomplete/chummer6-ui/Docker/Downloads/files"
)
DOWNLOADS_BASE = "https://chummer.run"
POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")
DEFAULT_POLICY = {
    "forbidden_origin_mentions": [],
    "release_source_label": "active Chummer6 code repos",
}


def run(*args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def load_policy() -> dict[str, object]:
    policy = dict(DEFAULT_POLICY)
    if POLICY_PATH.exists():
        loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            policy.update(loaded)
    return policy


def assert_clean(text: str, policy: dict[str, object], *, label: str) -> None:
    forbidden = [
        str(item).strip()
        for item in policy.get("forbidden_origin_mentions", [])
        if str(item).strip()
    ]
    lowered = text.lower()
    for item in forbidden:
        if item.lower() in lowered:
            raise ValueError(f"{label} contains forbidden Chummer6 provenance text: {item}")


def refresh_release_projection() -> None:
    if RELEASE_CONTROL_SCRIPT.exists():
        run("python3", str(RELEASE_CONTROL_SCRIPT), check=False)


def _load_release_payload_path(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"release payload must be a JSON object: {path}")
    return loaded


def _payload_has_release_rows(payload: dict[str, object]) -> bool:
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        return True
    downloads = payload.get("downloads")
    return isinstance(downloads, list) and bool(downloads)


def load_release_payload() -> dict[str, object]:
    for path in (DOWNLOADS_MANIFEST, COMPAT_DOWNLOADS_MANIFEST):
        loaded = _load_release_payload_path(path)
        if loaded is not None and _payload_has_release_rows(loaded):
            return loaded
    refresh_release_projection()
    for path in (DOWNLOADS_MANIFEST, COMPAT_DOWNLOADS_MANIFEST):
        loaded = _load_release_payload_path(path)
        if loaded is not None:
            return loaded
    raise FileNotFoundError(f"release manifest not found: {DOWNLOADS_MANIFEST}")


def release_asset_file_names(data: dict[str, object]) -> list[str]:
    names: list[str] = []
    artifacts = data.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            file_name = str(item.get("fileName") or "").strip()
            if file_name:
                names.append(file_name)
    downloads = data.get("downloads")
    if isinstance(downloads, list):
        for item in downloads:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            name = PurePosixPath(url).name.strip()
            if name:
                names.append(name)
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name not in seen:
            deduped.append(name)
            seen.add(name)
    return deduped


def release_asset_paths(data: dict[str, object]) -> list[Path]:
    paths: list[Path] = []
    for manifest_path in (DOWNLOADS_MANIFEST, COMPAT_DOWNLOADS_MANIFEST):
        if manifest_path.exists():
            paths.append(manifest_path)
    for name in release_asset_file_names(data):
        candidate = DOWNLOADS_FILES_DIR / name
        if not candidate.exists():
            raise FileNotFoundError(f"release asset not found: {candidate}")
        paths.append(candidate)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = path.name
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def release_body(policy: dict[str, object]) -> str:
    data = load_release_payload()
    artifacts = data.get("artifacts")
    downloads = data.get("downloads", [])
    version = data.get("version", "unknown")
    channel = data.get("channelId", data.get("channel", "unknown"))
    published_at = data.get("publishedAt", "unknown")
    rollout_reason = str(data.get("rolloutReason") or "").strip()
    supportability_summary = str(data.get("supportabilitySummary") or "").strip()
    fix_availability_summary = str(data.get("fixAvailabilitySummary") or "").strip()
    known_issue_summary = str(data.get("knownIssueSummary") or "").strip()
    proof = data.get("releaseProof") if isinstance(data.get("releaseProof"), dict) else {}
    proof_status = str((proof or {}).get("status") or "").strip()
    proof_generated_at = str((proof or {}).get("generatedAt") or "").strip()
    source_label = str(policy.get("release_source_label", "active Chummer6 code repos")).strip()
    assert_clean(source_label, policy, label="release source label")
    lines = [
        f"## {TITLE}",
        "",
        "This is the rolling **latest desktop bundle shelf**.",
        "",
        "It is regenerated from the current desktop build pipeline and replaced in place.",
        "",
        "These binaries come from the active Chummer app build pipeline, not from hand-uploaded release leftovers.",
        "The attached GitHub release assets are kept in rolling sync with the latest published desktop bundle.",
        "",
        f"- build source: `{source_label}`",
        f"- build manifest version: `{version}`",
        f"- build channel: `{channel}`",
        f"- build date: `{published_at}`",
        *([f"- rollout posture: `{rollout_reason}`"] if rollout_reason else []),
        *([f"- supportability: `{supportability_summary}`"] if supportability_summary else []),
        *([f"- local release proof: `{proof_status}` @ `{proof_generated_at}`"] if proof_status else []),
        "",
        "### Street warning",
        "Never trust software.",
        "Never trust a dev.",
        "Assume this thing might already be **marked, hacked, or one bad click away from bricking your evening**.",
        "",
        "### Use this if",
        "- you want to poke the future",
        "- you are willing to find bugs",
        "- you can tolerate rough edges",
        "",
        "### Do not use this if",
        "- you want stable software",
        "- you want polished UX",
        "- you want guarantees",
        "- you are attached to your dignity",
        "",
        "### Downloads",
    ]
    if known_issue_summary or fix_availability_summary:
        lines.extend(
            [
                "",
                "### Current trust lane",
                f"- known issues: {known_issue_summary or 'Check the install and trust lane before you commit a fresh device to this preview.'}",
                f"- fix availability: {fix_availability_summary or 'Verify the affected install can receive the current channel artifact before closing the loop.'}",
            ]
        )
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            url = f"{DOWNLOADS_BASE}{item.get('downloadUrl') or ''}"
            label = str(item.get("platformLabel") or item.get("platform") or item.get("artifactId") or "Artifact").strip()
            lines.extend(
                [
                    f"- [{label}]({url})",
                    f"  - sha256: `{item.get('sha256') or 'unknown'}`",
                    f"  - size: `{item.get('sizeBytes') or 0}` bytes",
                ]
            )
    else:
        for item in downloads:
            if not isinstance(item, dict):
                continue
            url = f"{DOWNLOADS_BASE}{item['url']}"
            lines.extend(
                [
                    f"- [{item['platform']}]({url})",
                    f"  - sha256: `{item['sha256']}`",
                    f"  - size: `{item['sizeBytes']}` bytes",
                ]
            )
    lines.extend(
        [
            "",
            "### If it explodes",
            "Please tell me:",
            "- what you installed",
            "- what you clicked",
            "- what you expected",
            "- what actually happened",
        ]
    )
    body = "\n".join(lines)
    assert_clean(body, policy, label="release body")
    return body


def upsert_release(body: str) -> dict[str, object]:
    existing = run("gh", "api", f"repos/{OWNER}/{REPO}/releases/tags/{TAG}", check=False)
    payload = json.dumps(
        {
            "tag_name": TAG,
            "target_commitish": TARGET_COMMITISH,
            "name": TITLE,
            "body": body,
            "draft": False,
            "prerelease": True,
        }
    )
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        release_id = str(release["id"])
        run(
            "gh",
            "api",
            "--method",
            "PATCH",
            f"repos/{OWNER}/{REPO}/releases/{release_id}",
            "--input",
            "-",
            input_text=payload,
        )
        refreshed = run("gh", "api", f"repos/{OWNER}/{REPO}/releases/tags/{TAG}")
        return json.loads(refreshed.stdout)

    created = run(
        "gh",
        "api",
        "--method",
        "POST",
        f"repos/{OWNER}/{REPO}/releases",
        "--input",
        "-",
        input_text=payload,
        check=False,
    )
    if created.returncode != 0:
        retry = run("gh", "api", f"repos/{OWNER}/{REPO}/releases/tags/{TAG}", check=False)
        if retry.returncode != 0:
            raise subprocess.CalledProcessError(created.returncode, created.args, created.stdout, created.stderr)
        release = json.loads(retry.stdout)
        release_id = str(release["id"])
        run(
            "gh",
            "api",
            "--method",
            "PATCH",
            f"repos/{OWNER}/{REPO}/releases/{release_id}",
            "--input",
            "-",
            input_text=payload,
        )
        refreshed = run("gh", "api", f"repos/{OWNER}/{REPO}/releases/tags/{TAG}")
        return json.loads(refreshed.stdout)
    return json.loads(created.stdout)


def sync_release_assets(release: dict[str, object], asset_paths: list[Path]) -> None:
    expected_names = {path.name for path in asset_paths}
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        if not name or name in expected_names:
            continue
        run("gh", "release", "delete-asset", TAG, name, "-R", f"{OWNER}/{REPO}", "--yes")
    upload_cmd = ["gh", "release", "upload", TAG, "-R", f"{OWNER}/{REPO}", "--clobber"]
    upload_cmd.extend(str(path) for path in asset_paths)
    run(*upload_cmd)


def main() -> int:
    policy = load_policy()
    payload = load_release_payload()
    body = release_body(policy)
    release = upsert_release(body)
    asset_paths = release_asset_paths(payload)
    sync_release_assets(release, asset_paths)
    print(
        json.dumps(
            {
                "repo": f"{OWNER}/{REPO}",
                "tag": TAG,
                "status": "published",
                "asset_count": len(asset_paths),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
