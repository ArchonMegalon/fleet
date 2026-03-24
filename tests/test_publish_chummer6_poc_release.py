from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import pytest


MODULE_PATH = Path("/docker/fleet/scripts/publish_chummer6_poc_release.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("publish_chummer6_poc_release", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_release_payload_prefers_existing_nonempty_registry_projection(monkeypatch, tmp_path: Path) -> None:
    publisher = _load_module()
    canonical = tmp_path / "RELEASE_CHANNEL.generated.json"
    compat = tmp_path / "releases.json"
    canonical.write_text(
        json.dumps(
            {
                "version": "smoke-2026-03-24",
                "channelId": "preview",
                "publishedAt": "2026-03-24T11:33:23Z",
                "artifacts": [{"artifactId": "avalonia-linux-x64-archive"}],
            }
        ),
        encoding="utf-8",
    )
    compat.write_text(
        json.dumps(
            {
                "version": "compat-only",
                "channel": "preview",
                "publishedAt": "2026-03-24T11:33:23Z",
                "downloads": [],
            }
        ),
        encoding="utf-8",
    )
    refreshed: list[bool] = []
    monkeypatch.setattr(publisher, "DOWNLOADS_MANIFEST", canonical)
    monkeypatch.setattr(publisher, "COMPAT_DOWNLOADS_MANIFEST", compat)
    monkeypatch.setattr(publisher, "refresh_release_projection", lambda: refreshed.append(True))

    payload = publisher.load_release_payload()

    assert payload["version"] == "smoke-2026-03-24"
    assert refreshed == []


def test_release_asset_paths_include_manifests_and_built_files(monkeypatch, tmp_path: Path) -> None:
    publisher = _load_module()
    canonical = tmp_path / "RELEASE_CHANNEL.generated.json"
    compat = tmp_path / "releases.json"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    installer = files_dir / "chummer-avalonia-win-x64-installer.exe"
    archive = files_dir / "chummer-avalonia-win-x64.zip"
    installer.write_text("installer", encoding="utf-8")
    archive.write_text("archive", encoding="utf-8")
    canonical.write_text(
        json.dumps(
            {
                "version": "smoke-2026-03-24",
                "channelId": "preview",
                "publishedAt": "2026-03-24T11:33:23Z",
                "artifacts": [
                    {"fileName": installer.name},
                    {"fileName": archive.name},
                ],
            }
        ),
        encoding="utf-8",
    )
    compat.write_text(json.dumps({"downloads": []}), encoding="utf-8")
    monkeypatch.setattr(publisher, "DOWNLOADS_MANIFEST", canonical)
    monkeypatch.setattr(publisher, "COMPAT_DOWNLOADS_MANIFEST", compat)
    monkeypatch.setattr(publisher, "DOWNLOADS_FILES_DIR", files_dir)

    paths = publisher.release_asset_paths(json.loads(canonical.read_text(encoding="utf-8")))

    assert [path.name for path in paths] == [
        "RELEASE_CHANNEL.generated.json",
        "releases.json",
        "chummer-avalonia-win-x64-installer.exe",
        "chummer-avalonia-win-x64.zip",
    ]


def test_release_asset_paths_fail_when_built_file_missing(monkeypatch, tmp_path: Path) -> None:
    publisher = _load_module()
    canonical = tmp_path / "RELEASE_CHANNEL.generated.json"
    compat = tmp_path / "releases.json"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    canonical.write_text(
        json.dumps({"artifacts": [{"fileName": "missing.exe"}]}),
        encoding="utf-8",
    )
    compat.write_text(json.dumps({"downloads": []}), encoding="utf-8")
    monkeypatch.setattr(publisher, "DOWNLOADS_MANIFEST", canonical)
    monkeypatch.setattr(publisher, "COMPAT_DOWNLOADS_MANIFEST", compat)
    monkeypatch.setattr(publisher, "DOWNLOADS_FILES_DIR", files_dir)

    with pytest.raises(FileNotFoundError, match="missing.exe"):
        publisher.release_asset_paths(json.loads(canonical.read_text(encoding="utf-8")))


def test_sync_release_assets_prunes_stale_and_uploads_current(monkeypatch, tmp_path: Path) -> None:
    publisher = _load_module()
    monkeypatch.setattr(publisher, "OWNER", "ArchonMegalon")
    monkeypatch.setattr(publisher, "REPO", "Chummer6")
    monkeypatch.setattr(publisher, "TAG", "desktop-latest")
    manifest = tmp_path / "RELEASE_CHANNEL.generated.json"
    compat = tmp_path / "releases.json"
    installer = tmp_path / "chummer-avalonia-win-x64-installer.exe"
    manifest.write_text("{}", encoding="utf-8")
    compat.write_text("{}", encoding="utf-8")
    installer.write_text("binary", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str, input_text: str | None = None, check: bool = True):
        calls.append(tuple(args))
        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return _Result()

    monkeypatch.setattr(publisher, "run", fake_run)

    publisher.sync_release_assets(
        {
            "assets": [
                {"name": "old-build.zip"},
                {"name": "RELEASE_CHANNEL.generated.json"},
                {"name": "releases.json"},
            ]
        },
        [manifest, compat, installer],
    )

    assert ("gh", "release", "delete-asset", "desktop-latest", "old-build.zip", "-R", "ArchonMegalon/Chummer6", "--yes") in calls
    upload_calls = [call for call in calls if call[:4] == ("gh", "release", "upload", "desktop-latest")]
    assert len(upload_calls) == 1
    assert upload_calls[0][-3:] == (str(manifest), str(compat), str(installer))
