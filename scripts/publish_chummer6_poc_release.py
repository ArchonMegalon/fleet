#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path


OWNER = "ArchonMegalon"
REPO = "Chummer6"
TAG = "poc-0.1-test-dummy-drop"
TITLE = "Chummer6 POC 0.1 - Test Dummy Drop"
RELEASE_CONTROL_SCRIPT = Path("/docker/fleet/scripts/materialize_chummer_release_registry_projection.py")
DOWNLOADS_MANIFEST = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json")
COMPAT_DOWNLOADS_MANIFEST = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/releases.json")
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


def release_body(policy: dict[str, object]) -> str:
    data = load_release_payload()
    artifacts = data.get("artifacts")
    downloads = data.get("downloads", [])
    version = data.get("version", "unknown")
    channel = data.get("channelId", data.get("channel", "unknown"))
    published_at = data.get("publishedAt", "unknown")
    source_label = str(policy.get("release_source_label", "active Chummer6 code repos")).strip()
    assert_clean(source_label, policy, label="release source label")
    lines = [
        "## Chummer6 POC 0.1 - Test Dummy Drop",
        "",
        "This is a **proof-of-concept build shelf**.",
        "",
        "It is unfinished, unpolished, and not pretending otherwise.",
        "",
        "These binaries come from the active Chummer app build pipeline, **not** from the `Chummer6` guide repo itself.",
        "",
        f"- build source: `{source_label}`",
        f"- build manifest version: `{version}`",
        f"- build channel: `{channel}`",
        f"- build date: `{published_at}`",
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


def main() -> int:
    policy = load_policy()
    body = release_body(policy)
    existing = run("gh", "api", f"repos/{OWNER}/{REPO}/releases/tags/{TAG}", check=False)
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        release_id = str(release["id"])
        payload = json.dumps(
            {
                "tag_name": TAG,
                "target_commitish": "main",
                "name": TITLE,
                "body": body,
                "draft": False,
                "prerelease": True,
            }
        )
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
    else:
        payload = json.dumps(
            {
                "tag_name": TAG,
                "target_commitish": "main",
                "name": TITLE,
                "body": body,
                "draft": False,
                "prerelease": True,
            }
        )
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
    print(json.dumps({"repo": f"{OWNER}/{REPO}", "tag": TAG, "status": "published"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
