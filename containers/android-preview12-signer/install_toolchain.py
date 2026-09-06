#!/usr/bin/env python3
"""Install only SHA-256-locked toolchain archives into the signer image."""
from __future__ import annotations
import hashlib
import json
import os
import posixpath
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
def _relative(name: str, strip: int) -> Path | None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts:
        raise RuntimeError(f"unsafe archive member: {name}")
    parts = tuple(part for part in pure.parts if part not in ("", "."))
    return None if len(parts) <= strip else Path(*parts[strip:])
def _extract_zip(archive: Path, destination: Path, strip: int) -> None:
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            mode, relative = member.external_attr >> 16, _relative(member.filename, strip)
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"symlink forbidden in {member.filename}")
            if relative is None:
                continue
            target = destination / relative
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            if mode & 0o111:
                target.chmod(0o755)
def _extract_tar(archive: Path, destination: Path, strip: int) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            relative = _relative(member.name, strip)
            if relative is None:
                continue
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise RuntimeError(f"cannot read {member.name}")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                resolved = PurePosixPath(posixpath.normpath(str(PurePosixPath(relative.as_posix()).parent / link)))
                if link.is_absolute() or resolved.is_absolute() or ".." in resolved.parts:
                    raise RuntimeError(f"unsafe archive symlink: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)
            elif member.islnk():
                linked = _relative(member.linkname, strip)
                if linked is None or not (destination / linked).is_file():
                    raise RuntimeError(f"unsafe archive hardlink: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(destination / linked, target)
            else:
                raise RuntimeError(f"non-regular archive member forbidden: {member.name}")
def _install(entry: dict[str, object], scratch: Path) -> None:
    name, expected = str(entry["name"]), str(entry["sha256"])
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise RuntimeError(f"{name} has no SHA-256 lock")
    archive = scratch / name
    request = urllib.request.Request(str(entry["url"]), headers={"User-Agent": "fleet-signer-image/1"})
    with urllib.request.urlopen(request, timeout=120) as source, archive.open("wb") as output:
        shutil.copyfileobj(source, output)
    actual = _sha256(archive)
    if actual != expected:
        raise RuntimeError(f"{name} SHA-256 mismatch: {actual}")
    destination, archive_format, strip = Path(str(entry["destination"])), str(entry["format"]), int(entry["strip_components"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if archive_format == "file":
        if destination.exists():
            raise RuntimeError(f"destination already exists: {destination}")
        shutil.copyfile(archive, destination)
        return
    destination.mkdir(parents=True, exist_ok=False)
    if archive_format == "zip":
        _extract_zip(archive, destination, strip)
    elif archive_format == "tar.gz":
        _extract_tar(archive, destination, strip)
    else:
        raise RuntimeError(f"unsupported archive format: {archive_format}")
def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: install_toolchain.py LOCK OUTPUT_RECEIPT")
    lock_path = Path(sys.argv[1])
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    if lock.get("contract_name") != "fleet.android_preview12_toolchain.v1":
        raise RuntimeError("unexpected toolchain lock contract")
    with tempfile.TemporaryDirectory(prefix="fleet-toolchain-") as temporary:
        for entry in lock["archives"]:
            _install(entry, Path(temporary))
    for executable in ("aapt2", "apksigner", "zipalign"):
        (Path("/opt/android-sdk/build-tools/35.0.0") / executable).chmod(0o755)
    receipt = {"contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(), "base_images": lock["base_images"],
        "archives": [{key: entry[key] for key in ("name", "version", "url", "sha256")} for entry in lock["archives"]]}
    output = Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
