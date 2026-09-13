#!/usr/bin/env python3
"""Install checksum-locked archives; the receipt is inventory, not tree authority.

Run only in an isolated image build with exclusively controlled destinations.
No private keys, workload resolution, or installed-tree attestation belong here.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: object) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= 4096
            and all(32 <= ord(char) < 127 for char in value))


def _absolute_path(value: object) -> Path:
    if not _text(value) or "\\" in value:
        raise RuntimeError("invalid absolute installation path")
    path = Path(value)
    if (not path.is_absolute() or value.startswith("//") or path == Path("/") or ".." in path.parts
            or path.as_posix() != value):
        raise RuntimeError("noncanonical absolute installation path")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
            raise RuntimeError("unsafe installation path ancestor")
    return path


def _validate_entry(entry: object) -> dict[str, object]:
    required = {"name", "version", "url", "format", "destination", "strip_components"}
    if not isinstance(entry, dict):
        raise RuntimeError("archive entry must be an object")
    algorithms = set(entry) & {"sha256", "sha512"}
    if len(algorithms) != 1 or set(entry) != required | algorithms:
        raise RuntimeError("archive requires exactly one SHA-256 or SHA-512 checksum")
    algorithm = next(iter(algorithms))
    checksum = entry[algorithm]
    if (not isinstance(checksum, str)
            or re.fullmatch(r"[0-9a-f]{%d}" % (64 if algorithm == "sha256" else 128), checksum) is None):
        raise RuntimeError("invalid archive checksum")
    name = entry["name"]
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name) is None:
        raise RuntimeError("archive name must be a safe basename")
    if not _text(entry["version"]) or entry["version"].strip() != entry["version"]:
        raise RuntimeError("invalid archive version")
    if not _text(entry["url"]) or any(char.isspace() for char in entry["url"]):
        raise RuntimeError("invalid archive URL")
    try:
        url = urllib.parse.urlsplit(entry["url"])
        valid_url = (url.scheme == "https" and url.hostname and url.path.startswith("/")
                     and not url.username and not url.password and not url.query and not url.fragment
                     and url.port in (None, 443) and "\\" not in entry["url"])
    except ValueError:
        valid_url = False
    if not valid_url:
        raise RuntimeError("archive URL must be credential-free HTTPS")
    if entry["format"] not in ("file", "zip", "tar.gz"):
        raise RuntimeError("unsupported archive format")
    strip = entry["strip_components"]
    if type(strip) is not int or not 0 <= strip <= 32 or (entry["format"] == "file" and strip != 0):
        raise RuntimeError("invalid archive strip_components")
    destination = _absolute_path(entry["destination"])
    if destination.exists():
        raise RuntimeError("archive destination already exists")
    if name == "android-build-tools":
        if (re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", entry["version"]) is None
                or entry["format"] != "zip" or destination.name != entry["version"]
                or destination.parent.name != "build-tools"):
            raise RuntimeError("build-tools destination must match its exact version")
    return dict(entry)


def _validate_manifest(lock: object, output: Path) -> list[dict[str, object]]:
    if (not isinstance(lock, dict)
            or set(lock) != {"contract_name", "contract_version", "platform", "base_images", "archives"}
            or lock["contract_name"] != "fleet.android_preview12_toolchain.v1"
            or type(lock["contract_version"]) is not int or lock["contract_version"] != 1
            or lock["platform"] != "linux/amd64"):
        raise RuntimeError("unexpected toolchain lock contract")
    images = lock["base_images"]
    if not isinstance(images, list) or not images or len(images) > 32:
        raise RuntimeError("invalid base image inventory")
    image_names = set()
    for image in images:
        if (not isinstance(image, dict) or set(image) != {"name", "version", "reference", "digest"}
                or not all(_text(value) for value in image.values())
                or re.fullmatch(r"sha256:[0-9a-f]{64}", image["digest"]) is None
                or image["name"] in image_names):
            raise RuntimeError("invalid or duplicate base image inventory")
        image_names.add(image["name"])
    if not isinstance(lock["archives"], list) or not 1 <= len(lock["archives"]) <= 128:
        raise RuntimeError("invalid archive inventory")
    entries = [_validate_entry(entry) for entry in lock["archives"]]
    output = _absolute_path(os.fspath(output))
    if output.exists():
        raise RuntimeError("receipt destination already exists")
    names, urls, destinations = set(), set(), [output]
    for entry in entries:
        destination = Path(entry["destination"])
        if entry["name"] in names or entry["url"] in urls:
            raise RuntimeError("duplicate archive")
        if any(destination.is_relative_to(prior) or prior.is_relative_to(destination) for prior in destinations):
            raise RuntimeError("overlapping archive or receipt destinations")
        names.add(entry["name"])
        urls.add(entry["url"])
        destinations.append(destination)
    return entries


def _contained(path: Path, destination: Path) -> None:
    try:
        if not path.resolve().is_relative_to(destination):
            raise RuntimeError("archive path escapes destination")
    except (OSError, ValueError, RuntimeError):
        raise RuntimeError("unsafe resolved archive path") from None


def _target(destination: Path, relative: Path) -> Path:
    target = destination / relative
    _contained(target.parent, destination)
    if target.is_symlink():
        raise RuntimeError("archive member replaces a symlink")
    _contained(target, destination)
    return target


def _relative(name: str, strip: int) -> Path | None:
    pure = PurePosixPath(name)
    if not name or "\0" in name or "\\" in name or pure.is_absolute() or ".." in pure.parts:
        raise RuntimeError(f"unsafe archive member: {name}")
    parts = tuple(part for part in pure.parts if part not in ("", "."))
    return None if len(parts) <= strip else Path(*parts[strip:])
def _extract_zip(archive: Path, destination: Path, strip: int) -> None:
    seen = set()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            mode, relative = member.external_attr >> 16, _relative(member.filename, strip)
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"symlink forbidden in {member.filename}")
            if relative is None:
                continue
            if relative in seen:
                raise RuntimeError("duplicate archive member")
            seen.add(relative)
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise RuntimeError("non-regular zip member")
            target = _target(destination, relative)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            if mode & 0o111:
                target.chmod(0o755)
def _extract_tar(archive: Path, destination: Path, strip: int) -> None:
    seen = set()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            relative = _relative(member.name, strip)
            if relative is None:
                continue
            if relative in seen:
                raise RuntimeError("duplicate archive member")
            seen.add(relative)
            target = _target(destination, relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise RuntimeError(f"cannot read {member.name}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                if not member.linkname or "\0" in member.linkname or "\\" in member.linkname or link.is_absolute():
                    raise RuntimeError(f"unsafe archive symlink: {member.name}")
                # Resolve against the REAL parent: an earlier dir -> . link can
                # make a lexically-contained ../ target escape the destination.
                _contained(target.parent / member.linkname, destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)
                _contained(target, destination)
            elif member.islnk():
                linked = _relative(member.linkname, strip)
                source = _target(destination, linked) if linked is not None else None
                if source is None or not source.is_file():
                    raise RuntimeError(f"unsafe archive hardlink: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, target)
            else:
                raise RuntimeError(f"non-regular archive member forbidden: {member.name}")
def _install(entry: dict[str, object], scratch: Path) -> None:
    entry = _validate_entry(entry)
    name = entry["name"]
    algorithm = "sha256" if "sha256" in entry else "sha512"
    archive = scratch / name
    request = urllib.request.Request(str(entry["url"]), headers={"User-Agent": "fleet-signer-image/1"})
    with urllib.request.urlopen(request, timeout=120) as source, archive.open("xb") as output:
        shutil.copyfileobj(source, output)
    if _digest(archive, algorithm) != entry[algorithm]:
        raise RuntimeError(f"{name} {algorithm} mismatch")
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
    with lock_path.open("rb") as stream:
        lock_bytes = stream.read(1024 * 1024 + 1)
    if len(lock_bytes) > 1024 * 1024:
        raise RuntimeError("toolchain lock exceeds size bound")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError("duplicate JSON field")
            result[key] = value
        return result
    lock = json.loads(lock_bytes, object_pairs_hook=unique_object)
    output = Path(sys.argv[2])
    entries = _validate_manifest(lock, output)
    with tempfile.TemporaryDirectory(prefix="fleet-toolchain-") as temporary:
        for entry in entries:
            _install(entry, Path(temporary))
    for entry in entries:
        if entry["name"] == "android-build-tools":
            for executable in ("aapt2", "apksigner", "zipalign"):
                target = _target(Path(entry["destination"]), Path(executable))
                if not target.is_file():
                    raise RuntimeError("build-tools executable missing")
                target.chmod(0o755)
    receipt = {"contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(), "base_images": lock["base_images"],
        "archives": [{key: entry[key] for key in ("name", "version", "url", "sha256", "sha512") if key in entry}
                     for entry in entries]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
