"""Render one admitted Android role profile for one exact invocation.

This is a source-only, private-profile renderer.  The profile contains the
existing owner, hosted-capture, hosted-emission and protected-bootstrap JSON
documents; this module never invents a deployment, reads credential bytes,
contacts GitHub, or treats a caller-supplied digest as authority.  Protected
provisioning must independently admit the profile/context bytes and this
module's interpreter/import closure before using the output.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from scripts import android_artifact_origin as origin
from scripts import android_hosted_controller_roles as hosted
from scripts import android_local_capture_owner as owner
from scripts import android_protected_job_bootstrap as protected
from scripts import android_workflow_identity as identity

ERROR = "deployment materialization stopped; preserve inputs and do not retry"
MAX_PROFILE = 2 * 1024 * 1024
MAX_CONTEXT = 16 * 1024
ROLES = ("owner", "capture", "emission", "protected")
PROFILE_FIELDS = frozenset(ROLES)
CONTEXT_FIELDS = frozenset(("fleet_sha", "workflow_sha", "ref", "run_id", "run_attempt", "transaction_id"))
MUTABLE_JOB_FIELDS = ("sha", "workflow_sha", "ref", "run_id", "run_attempt", "transaction_id")
MUTABLE_ARTIFACT_FIELDS = ("source_commit", "source_ref", "run_id", "run_attempt")


class MaterializerError(RuntimeError):
    """Constant failure only; never expose profile paths or private inputs."""


def _require(value):
    if not value:
        raise MaterializerError(ERROR)


def _hex(value, length=64):
    return type(value) is str and len(value) == length and all(char in "0123456789abcdef" for char in value)


def _path(value):
    _require(type(value) is str and value.startswith("/") and "\x00" not in value and "\\" not in value)
    path = Path(value)
    _require(str(path) == value and value != "/" and not any(part in {"", ".", ".."} for part in value.split("/")[1:]))
    return path


def _read_admitted(path: Path, expected: str, limit: int) -> bytes:
    _require(isinstance(path, Path) and path.is_absolute() and _hex(expected))
    try:
        info = path.lstat()
        _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                 and not info.st_mode & 0o022 and 0 < info.st_size <= limit
                 and path.resolve(strict=True) == path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                     (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns))
            raw = os.pread(fd, limit + 1, 0)
            after = os.fstat(fd)
            _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                     (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                     and len(raw) == before.st_size and 0 < len(raw) <= limit
                     and hashlib.sha256(raw).hexdigest() == expected)
            return raw
        finally:
            os.close(fd)
    except (OSError, ValueError):
        raise MaterializerError(ERROR) from None


def _json(raw: bytes):
    try:
        return identity._json(raw)
    except Exception:
        raise MaterializerError(ERROR) from None


def _validate_context(value):
    _require(type(value) is dict and set(value) == CONTEXT_FIELDS)
    _require(_hex(value["fleet_sha"], 40) and _hex(value["workflow_sha"], 40)
             and value["fleet_sha"] == value["workflow_sha"])
    _require(identity._ref(value["ref"]) and identity._number(value["run_id"])
             and identity._number(value["run_attempt"]) and _hex(value["transaction_id"]))
    return dict(value)


def _parse_documents(value, selected_role):
    _require(type(value) is dict and set(value) == PROFILE_FIELDS)
    encoded = lambda document: json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    # These are the real consumers' parsers.  They only validate shape/policy;
    # this renderer never invokes constructors, networking, mounts or secrets.
    owner._document(encoded(value["owner"]))
    if selected_role == "capture":
        hosted._document(encoded(value["capture"]), "capture")
    else:
        hosted._document_shape(encoded(value["capture"]), "capture")
    if selected_role == "emission":
        hosted._document(encoded(value["emission"]), "emission-prepare")
    else:
        hosted._document_shape(encoded(value["emission"]), "emission-prepare")
    protected._document(encoded(value["protected"]))


def _self_referential_workflow(raw):
    job_ref, job_sha = raw.get("job_workflow_ref"), raw.get("job_workflow_sha")
    _require((job_ref is None) == (job_sha is None))
    if job_ref is None:
        return False
    ref_matches = job_ref == raw.get("workflow_ref")
    sha_matches = job_sha == raw.get("workflow_sha")
    # A different workflow file can legitimately be pinned to the same commit.
    # Only this workflow's own reference requires its exact admitted source SHA.
    _require(not ref_matches or sha_matches)
    return ref_matches


def _job_context(raw, context):
    _require(type(raw) is dict)
    self_reference = _self_referential_workflow(raw)
    for name in MUTABLE_JOB_FIELDS:
        raw[name] = context["fleet_sha"] if name in {"sha", "workflow_sha"} else context[name]
    _require(raw["workflow_ref"].endswith("@" + context["ref"]))
    if raw.get("job_workflow_ref") is not None:
        _require(raw["job_workflow_sha"] is not None)
        if self_reference:
            raw["job_workflow_sha"] = context["workflow_sha"]
    return self_reference


def _artifact_context(raw, context, *, direct_signer, self_reference):
    _require(type(raw) is dict)
    for name in MUTABLE_ARTIFACT_FIELDS:
        source_name = {"source_commit": "fleet_sha", "source_ref": "ref",
                       "run_id": "run_id", "run_attempt": "run_attempt"}[name]
        raw[name] = context[source_name]
    _require(raw["build_config_identity"].endswith("@" + context["ref"]))
    if direct_signer or self_reference:
        raw["signer_commit"] = context["workflow_sha"]


def _binding(value, context):
    if "role_binding" not in value:
        return
    binding = value["role_binding"]
    _require(type(binding) is dict and set(binding) == {"job_names", "templates"})
    _require(type(binding["templates"]) is dict and set(binding["templates"]) == {"capture", "emission", "protected"})
    for template in binding["templates"].values():
        _job_context(template, context)


def _mutate(value, context):
    for document in value.values():
        _binding(document, context)

    owner_doc = value["owner"]
    self_references = {}
    for name in ("capture_policy", "emission_policy", "protected_job_policy"):
        self_references[name] = _job_context(owner_doc[name], context)
    direct_signer = owner_doc["emission_policy"].get("job_workflow_ref") is None
    shared_signer_update = direct_signer or self_references["emission_policy"] or self_references["protected_job_policy"]
    _artifact_context(owner_doc["artifact_policy"], context, direct_signer=direct_signer,
                      self_reference=shared_signer_update)

    for role in ("capture", "emission"):
        document = value[role]
        _job_context(document["job_policy"], context)
        _artifact_context(document["artifact_policy"], context, direct_signer=direct_signer,
                          self_reference=shared_signer_update)

    document = value["protected"]
    _job_context(document["job_policy"], context)
    _artifact_context(document["artifact_policy"], context, direct_signer=direct_signer,
                      self_reference=shared_signer_update)
    launcher = document["launcher"]
    persistent = document["persistent"]
    _require(launcher["output"] == str(Path(persistent["parent"]) / "outputs" / launcher["attempt"]))
    launcher["attempt"] = context["transaction_id"]
    launcher["output"] = str(Path(persistent["parent"]) / "outputs" / context["transaction_id"])


def _check_alignment(value, selected_role):
    encoded = lambda document: json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    parsed = {
        "owner": owner._document(encoded(value["owner"])),
        "capture": (hosted._document(encoded(value["capture"]), "capture")
                    if selected_role == "capture" else hosted._document_shape(encoded(value["capture"]), "capture")),
        "emission": (hosted._document(encoded(value["emission"]), "emission-prepare")
                     if selected_role == "emission" else hosted._document_shape(encoded(value["emission"]), "emission-prepare")),
        "protected": protected._document(encoded(value["protected"])),
    }
    owner_jobs = parsed["owner"][2]
    jobs = {"capture": parsed["capture"][1], "emission": parsed["emission"][1],
            "protected": parsed["protected"][5]}
    for index, role in enumerate(("capture", "emission", "protected")):
        job = jobs[role]
        owner_job = owner_jobs[index]
        _require(job == owner_job)
    owner_artifact = parsed["owner"][3]
    artifacts = {"capture": parsed["capture"][2], "emission": parsed["emission"][2],
                 "protected": parsed["protected"][6]}
    for role in ("capture", "emission", "protected"):
        _require(artifacts[role] == owner_artifact)
    for document, role, job in ((value["owner"], "capture", owner_jobs[0]),
                                (value["owner"], "emission", owner_jobs[1]),
                                (value["owner"], "protected", owner_jobs[2]),
                                (value["capture"], "capture", jobs["capture"]),
                                (value["emission"], "emission", jobs["emission"]),
                                (value["protected"], "protected", jobs["protected"])):
        if "role_binding" in document:
            binding = document["role_binding"]
            _require(binding["templates"][role] == {field.name: getattr(job, field.name)
                                                     for field in fields(identity.WorkflowJobPolicy)})

    bindings = [value[role].get("role_binding") for role in ROLES if "role_binding" in value[role]]
    _require(not bindings or len(bindings) == len(ROLES))
    if bindings:
        _require(all(binding == bindings[0] for binding in bindings[1:]))
    bases = [value[role]["base_url"] for role in ROLES]
    _require(len(set(bases)) == 1)
    barriers = [value[role].get("startup_barrier") for role in ROLES]
    _require(all((barrier is None) == (barriers[0] is None) for barrier in barriers))
    if barriers[0] is not None:
        _require(all(barrier == barriers[0] for barrier in barriers[1:]))
    _require(type(value["protected"].get("preparation_wait_seconds")) is int
             and 1 <= value["protected"]["preparation_wait_seconds"] <= 1800)
    _require(value["owner"]["pins"]["lock"]["sha256"] == value["protected"]["pins"]["lock"]["sha256"])
    return parsed


def render(profile, context, role):
    """Return one existing role document after validating all consumers."""
    try:
        context = _validate_context(context)
        _require(role in ROLES)
        profile = deepcopy(profile)
        _parse_documents(profile, role)
        _check_alignment(profile, role)
        _mutate(profile, context)
        _check_alignment(profile, role)
        raw = json.dumps(profile[role], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        _require(len(raw) <= (hosted.MAX_CONFIG if role in {"capture", "emission"} else protected.MAX_DEPLOYMENT))
        return raw
    except MaterializerError:
        raise
    except Exception:
        raise MaterializerError(ERROR) from None


def _write_exclusive(path: Path, raw: bytes):
    _require(isinstance(path, Path) and path.is_absolute() and path != Path("/")
             and path.resolve(strict=False) == path)
    parent_fd = fd = None
    try:
        parent = path.parent
        info = parent.lstat()
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                 and stat.S_IMODE(info.st_mode) == 0o700 and not path.exists())
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        parent_stamp = os.fstat(parent_fd)
        _require((parent_stamp.st_dev, parent_stamp.st_ino, parent_stamp.st_mode, parent_stamp.st_uid) ==
                 (info.st_dev, info.st_ino, info.st_mode, info.st_uid))
        fd = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=parent_fd)
        try:
            written = 0
            while written < len(raw):
                count = os.write(fd, raw[written:])
                _require(count > 0)
                written += count
            os.fsync(fd)
            stat_before = os.fstat(fd)
            stat_after = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            def stamp(info):
                return tuple(getattr(info, name) for name in (
                    "st_dev", "st_ino", "st_size", "st_mode", "st_uid", "st_gid",
                    "st_nlink", "st_mtime_ns", "st_ctime_ns"))
            _require(stat_before.st_dev == stat_after.st_dev and stat_before.st_ino == stat_after.st_ino
                     and stat_before.st_size == len(raw) and stat.S_ISREG(stat_after.st_mode)
                     and stat_after.st_uid == os.getuid() and stat_after.st_nlink == 1
                     and stat.S_IMODE(stat_after.st_mode) == 0o600
                     and hashlib.sha256(os.pread(fd, len(raw), 0)).hexdigest() == hashlib.sha256(raw).hexdigest())
            os.fsync(parent_fd)
            # Readback and directory fsync are observable IO boundaries.  The
            # returned digest must still name this exact stable output, not an
            # old held inode whose pathname was replaced during either call.
            _require(stamp(os.fstat(fd)) == stamp(stat_before)
                     and stamp(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False))
                     == stamp(stat_before))
            after_parent = os.fstat(parent_fd)
            _require((after_parent.st_dev, after_parent.st_ino, after_parent.st_mode, after_parent.st_uid) ==
                     (parent_stamp.st_dev, parent_stamp.st_ino, parent_stamp.st_mode, parent_stamp.st_uid)
                     and parent.resolve(strict=True) == parent)
            named_parent = parent.lstat()
            _require((named_parent.st_dev, named_parent.st_ino, named_parent.st_mode,
                      named_parent.st_uid, named_parent.st_nlink) ==
                     (parent_stamp.st_dev, parent_stamp.st_ino, parent_stamp.st_mode,
                      parent_stamp.st_uid, parent_stamp.st_nlink))
        finally:
            os.close(fd)
            fd = None
        os.close(parent_fd)
        parent_fd = None
    except (OSError, ValueError):
        raise MaterializerError(ERROR) from None
    finally:
        for descriptor in (fd, parent_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def materialize(profile_path: Path, profile_sha256: str, context_path: Path,
                context_sha256: str, output_path: Path, role: str) -> str:
    """Materialize admitted public bytes; return the output digest."""
    profile = _json(_read_admitted(profile_path, profile_sha256, MAX_PROFILE))
    context = _json(_read_admitted(context_path, context_sha256, MAX_CONTEXT))
    raw = render(profile, context, role)
    _write_exclusive(output_path, raw)
    return hashlib.sha256(raw).hexdigest()


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise MaterializerError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--profile-sha256", required=True)
        parser.add_argument("--context", required=True)
        parser.add_argument("--context-sha256", required=True)
        parser.add_argument("--role", choices=ROLES, required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args(argv)
        digest = materialize(_path(args.profile), args.profile_sha256, _path(args.context),
                             args.context_sha256, _path(args.output), args.role)
        print(digest, flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
