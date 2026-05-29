#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ARCHIVE_PATH="${1:-$SCRIPT_DIR/macos-proof-command-pack.tgz}"
SHA_PATH="${2:-$SCRIPT_DIR/macos-proof-command-pack.tgz.sha256}"
OUTPUT_DIR="${3:-$SCRIPT_DIR}"
export ARCHIVE_PATH
export SHA_PATH
export OUTPUT_DIR
test -s "$ARCHIVE_PATH"
test -s "$SHA_PATH"
if command -v shasum >/dev/null 2>&1; then
  ARCHIVE_DIR="$(dirname -- "$ARCHIVE_PATH")"
  ARCHIVE_NAME="$(basename -- "$ARCHIVE_PATH")"
  SHA_NAME="$(basename -- "$SHA_PATH")"
  (cd "$ARCHIVE_DIR" && shasum -a 256 -c "$SHA_NAME")
elif command -v sha256sum >/dev/null 2>&1; then
  ARCHIVE_DIR="$(dirname -- "$ARCHIVE_PATH")"
  ARCHIVE_NAME="$(basename -- "$ARCHIVE_PATH")"
  SHA_NAME="$(basename -- "$SHA_PATH")"
  (cd "$ARCHIVE_DIR" && sha256sum -c "$SHA_NAME")
elif command -v python3 >/dev/null 2>&1; then
  python3 -c 'import hashlib, os, pathlib, sys; archive=pathlib.Path(os.environ["ARCHIVE_PATH"]); sha_path=pathlib.Path(os.environ["SHA_PATH"]); raw=sha_path.read_text(encoding="utf-8").strip(); parts=raw.split(); sys.exit(f"external-proof-command-pack-sha256-sidecar-invalid:{sha_path}") if len(parts) < 2 else None; expected=parts[0].strip().lower(); digest=hashlib.sha256(archive.read_bytes()).hexdigest().lower(); sys.exit(0) if digest == expected else sys.exit(f"external-proof-command-pack-sha256-mismatch:{archive}:digest={digest}:expected={expected}")'
else
  echo 'external-proof-command-pack-sha256-tool-missing: need shasum, sha256sum, or python3 to verify the command pack' >&2
  exit 1
fi
mkdir -p "$OUTPUT_DIR"
python3 -c 'import os, pathlib, shutil, tarfile
archive=pathlib.Path(os.environ["ARCHIVE_PATH"])
output_dir=pathlib.Path(os.environ["OUTPUT_DIR"])
output_dir.mkdir(parents=True, exist_ok=True)
output_dir_resolved=output_dir.resolve()
bad=[]
copied=[]
with tarfile.open(archive, "r:gz") as payload:
    for member in payload.getmembers():
        pure=pathlib.PurePosixPath(member.name)
        parts=tuple(part for part in pure.parts if part not in ("", "."))
        if member.isdir():
            continue
        if member.name.startswith("/") or ".." in parts or not member.isfile():
            bad.append(member.name)
            continue
        destination=output_dir.joinpath(*parts)
        destination_parent=destination.parent.resolve()
        if output_dir_resolved != destination_parent and output_dir_resolved not in destination_parent.parents:
            bad.append(member.name)
            continue
        source=payload.extractfile(member)
        if source is None:
            bad.append(member.name)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source, destination.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        copied.append("/".join(parts))
assert not bad, "external-proof-command-pack-member-unsafe:" + ",".join(sorted(set(bad)))
assert copied, "external-proof-command-pack-empty:" + str(archive)'
echo "Prepared $ARCHIVE_PATH into $OUTPUT_DIR"
