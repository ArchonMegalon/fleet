"""Private, key-free GitHub artifact-origin verification; no signing authority.

The caller must independently admit this module, its imported Fleet helper,
policy, verifier, trust root and stable input custody. Nothing here selects a
workflow, installs tools, authenticates a protected runtime, or constructs
AuthenticatedRebuildHandoff. The handoff composition uses only the existing
preserved root-manifest closure, never an inferred transport archive. gh
implements Sigstore; this module checks its verified output, not an unverified
bundle's asserted claims.
POSIX process groups bound ordinary child execution, not hostile-code escape.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
import hashlib
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from scripts import android_preview12_external_rebuilder as _fleet


class OriginError(RuntimeError):
    """Sanitized, fail-closed origin failure; never includes subprocess output."""


def _text(value: object, limit: int = 2048) -> bool:
    return type(value) is str and 0 < len(value) <= limit and not any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char in "*?[]\\"
        for char in value
    )


def _hex(value: object, length: int) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


@dataclass(frozen=True, slots=True)
class OriginPolicy:
    repository: str
    repository_id: str
    repository_uri: str
    owner_id: str
    owner_uri: str
    source_commit: str
    signer_commit: str
    source_ref: str
    workflow_identity: str
    build_config_identity: str
    issuer: str
    predicate_type: str
    trigger: str
    run_id: str
    run_attempt: str
    subject_name: str
    subject_sha256: str
    visibility: str
    runner_environment: str
    timestamp_types: tuple[str, ...]
    maximum_age_seconds: int
    future_skew_seconds: int

    def __post_init__(self) -> None:
        strings = [field.name for field in fields(self) if field.name not in
                   {"timestamp_types", "maximum_age_seconds", "future_skew_seconds"}]
        if any(not _text(getattr(self, name)) for name in strings):
            raise OriginError("origin policy is not exact")
        if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", self.repository):
            raise OriginError("repository policy is invalid")
        owner, repo = self.repository.split("/")
        if repo in {".", ".."} or self.repository_uri != "https://github.com/" + self.repository \
                or self.owner_uri != "https://github.com/" + owner:
            raise OriginError("repository URI policy is inconsistent")
        if any(not re.fullmatch(r"[1-9][0-9]{0,19}", value) for value in
               (self.repository_id, self.owner_id, self.run_id, self.run_attempt)):
            raise OriginError("numeric identity policy is invalid")
        if not _hex(self.source_commit, 40) or not _hex(self.signer_commit, 40) \
                or not _hex(self.subject_sha256, 64):
            raise OriginError("digest policy is invalid")
        if not re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9._/-]+", self.source_ref) \
                or any(part in {"", ".", ".."} for part in self.source_ref.split("/")) \
                or ".." in self.source_ref or self.source_ref.endswith(".lock"):
            raise OriginError("source ref policy is invalid")
        # Signer workflow may be an independently admitted reusable workflow.
        # Never derive its authority from the source repository/workflow.
        if not re.fullmatch(r"https://github.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/\.github/workflows/"
                            r"[A-Za-z0-9_.-]+\.ya?ml@(refs/(heads|tags)/[A-Za-z0-9._/-]+|[0-9a-f]{40})",
                            self.workflow_identity) \
                or any(part in {".", ".."} for part in self.workflow_identity.split("/")):
            raise OriginError("signer workflow identity policy is invalid")
        prefix = self.repository_uri + "/.github/workflows/"
        suffix = "@" + self.source_ref
        if not self.build_config_identity.startswith(prefix) or not self.build_config_identity.endswith(suffix) \
                or not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", self.build_config_identity[len(prefix):-len(suffix)]):
            raise OriginError("source workflow identity policy is invalid")
        if self.issuer != "https://token.actions.githubusercontent.com" \
                or not self.predicate_type.startswith("https://") \
                or self.visibility not in {"public", "private", "internal"} \
                or self.runner_environment != "github-hosted":
            raise OriginError("unsupported origin policy")
        if type(self.timestamp_types) is not tuple or not 1 <= len(self.timestamp_types) <= 8 \
                or any(not _text(value, 128) for value in self.timestamp_types) \
                or len(set(self.timestamp_types)) != len(self.timestamp_types):
            raise OriginError("timestamp policy is invalid")
        if type(self.maximum_age_seconds) is not int or not 1 <= self.maximum_age_seconds <= 31536000 \
                or type(self.future_skew_seconds) is not int or not 0 <= self.future_skew_seconds <= 3600:
            raise OriginError("freshness policy is invalid")


@dataclass(frozen=True, slots=True)
class PinnedFile:
    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute() or not _hex(self.sha256, 64):
            raise OriginError("pinned file admission is invalid")


@dataclass(frozen=True, slots=True)
class OriginFacts:
    policy: OriginPolicy
    bundle_sha256: str
    verifier_sha256: str
    trusted_root_sha256: str
    verified_timestamps: tuple[tuple[str, str], ...]
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class _CapturedFile:
    pin: PinnedFile
    identity: tuple[int, ...]
    raw: bytes
    limit: int
    executable: bool

    def recheck(self) -> None:
        if _capture(self.pin, self.limit, self.executable) != self:
            raise OriginError("origin input changed")


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return tuple(getattr(value, name) for name in (
        "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
        "st_size", "st_mtime_ns", "st_ctime_ns"))


def _capture(pin: PinnedFile, limit: int, executable: bool = False) -> _CapturedFile:
    if type(pin) is not PinnedFile:
        raise OriginError("pinned file admission is invalid")
    try:
        before = pin.path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit \
                or (executable and not before.st_mode & 0o111):
            raise OriginError("origin input is not a regular admitted file")
        raw = _fleet._stable_bytes(pin.path, "origin input", limit)
        if _identity(before) != _identity(pin.path.lstat()) or hashlib.sha256(raw).hexdigest() != pin.sha256:
            raise OriginError("origin input identity or digest differs")
        return _CapturedFile(pin, _identity(before), raw, limit, executable)
    except (OSError, ValueError, _fleet.RebuilderError):
        raise OriginError("origin input is unavailable or changed") from None


def _json(raw: bytes, *, array: bool = False) -> object:
    # Reuse Fleet's single duplicate-key/UTF-8/non-finite parser, including for
    # gh's top-level array. The wrapper is internal, never a wire protocol.
    try:
        value = _fleet._strict_json(b'{"result":' + raw + b'}' if array else raw, "origin JSON")
        if array:
            if set(value) != {"result"} or type(value["result"]) is not list:
                raise OriginError("origin JSON shape is invalid")
            value = value["result"]
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 64 or count > 20000 or (type(item) is float and not math.isfinite(item)):
                raise OriginError("origin JSON exceeds structural bounds")
            if isinstance(item, (list, dict)):
                if count + len(pending) + len(item) > 20000:
                    raise OriginError("origin JSON exceeds structural bounds")
                pending.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
        return value
    except (ValueError, UnicodeError, RecursionError, _fleet.RebuilderError):
        raise OriginError("origin JSON is invalid") from None


def _run(command: list[str], directory: Path, timeout: float, out_limit: int, err_limit: int) -> bytes:
    if os.name != "posix":
        raise OriginError("origin verifier process isolation is unsupported")
    process = None
    deadline = time.monotonic() + timeout
    output, error_size = bytearray(), 0
    try:
        process = subprocess.Popen(
            command, cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "GH_HOST": "github.com",
                 "GH_CONFIG_DIR": str(directory / "gh-config"),
                 "XDG_CONFIG_HOME": str(directory / "config"), "TMPDIR": str(directory)},
        )
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map() or process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OriginError("origin verifier timed out")
                for key, _ in selector.select(min(remaining, 0.05)):
                    is_output = key.fileobj is process.stdout
                    available = out_limit - len(output) if is_output else err_limit - error_size
                    chunk = os.read(key.fd, min(65536, available + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if len(chunk) > available:
                        raise OriginError("origin verifier output exceeds bounds")
                    if is_output:
                        output.extend(chunk)
                    else:
                        error_size += len(chunk)
            if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
                raise OriginError("origin cryptographic verification failed")
        return bytes(output)
    except (OSError, subprocess.SubprocessError):
        raise OriginError("origin verifier execution failed") from None
    finally:
        if process is not None:
            # Kill the dedicated process group even if the direct child exited:
            # descendants may still hold the pipes. Reap our child in all paths.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    raise OriginError("origin verifier cleanup did not complete") from None
                finally:
                    for stream in (process.stdout, process.stderr):
                        if stream is not None:
                            stream.close()


def _claims(output: bytes, policy: OriginPolicy, now: datetime) -> tuple[tuple[str, str], ...]:
    value = _json(output, array=True)
    if len(value) != 1 or type(value[0]) is not dict:
        raise OriginError("origin must contain exactly one verified statement")
    result = value[0].get("verificationResult")
    if type(result) is not dict or type(result.get("statement")) is not dict:
        raise OriginError("verified origin statement is missing")
    statement = result["statement"]
    if statement.get("_type") != "https://in-toto.io/Statement/v1" \
            or statement.get("predicateType") != policy.predicate_type \
            or type(statement.get("predicate")) is not dict \
            or statement.get("subject") != [{"name": policy.subject_name, "digest": {"sha256": policy.subject_sha256}}]:
        raise OriginError("verified origin subject or predicate differs")
    signature = result.get("signature")
    certificate = signature.get("certificate") if type(signature) is dict else None
    if type(certificate) is not dict:
        raise OriginError("verified origin certificate is missing")
    expected = {
        "issuer": policy.issuer, "subjectAlternativeName": policy.workflow_identity,
        "buildSignerURI": policy.workflow_identity, "buildSignerDigest": policy.signer_commit,
        "runnerEnvironment": policy.runner_environment, "sourceRepositoryURI": policy.repository_uri,
        "sourceRepositoryIdentifier": policy.repository_id, "sourceRepositoryOwnerIdentifier": policy.owner_id,
        "sourceRepositoryDigest": policy.source_commit, "sourceRepositoryRef": policy.source_ref,
        "sourceRepositoryOwnerURI": policy.owner_uri, "sourceRepositoryVisibilityAtSigning": policy.visibility,
        "buildConfigURI": policy.build_config_identity, "buildConfigDigest": policy.source_commit,
        "buildTrigger": policy.trigger,
        "runInvocationURI": f"{policy.repository_uri}/actions/runs/{policy.run_id}/attempts/{policy.run_attempt}",
    }
    if any(type(certificate.get(key)) is not str or certificate[key] != item for key, item in expected.items()):
        raise OriginError("verified origin certificate identity differs")
    timestamps = result.get("verifiedTimestamps")
    if type(timestamps) is not list or not 1 <= len(timestamps) <= 64:
        raise OriginError("verified origin timestamps are missing")
    captured = []
    for row in timestamps:
        if type(row) is not dict or row.get("type") not in policy.timestamp_types \
                or type(row.get("timestamp")) is not str \
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(Z|[+-]\d{2}:\d{2})", row["timestamp"]) \
                or row["timestamp"].endswith("-00:00"):
            raise OriginError("verified origin timestamp is invalid")
        try:
            parsed = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).astimezone(UTC)
            if parsed < now - timedelta(seconds=policy.maximum_age_seconds) \
                    or parsed > now + timedelta(seconds=policy.future_skew_seconds):
                raise OriginError("verified origin timestamp is not fresh")
        except (ValueError, OverflowError):
            raise OriginError("verified origin timestamp is invalid") from None
        captured.append((row["type"], parsed.isoformat().replace("+00:00", "Z")))
    return tuple(captured)


def verify_origin(
    policy: OriginPolicy, subject: PinnedFile, bundle: PinnedFile,
    verifier: PinnedFile, trusted_root: PinnedFile, *, now: datetime,
    timeout_seconds: float = 30, stdout_limit: int = 1024 * 1024, stderr_limit: int = 65536,
) -> OriginFacts:
    """Measure and verify exact inputs. Success is origin-only, not release admission.

    Same-user mutable ancestors/host custody are not authenticated by these
    rechecks. The caller must keep admitted roots quiescent/immutable throughout.
    Actual pinned-gh/root/bundle qualification is separate from stand-in tests.
    """
    if type(policy) is not OriginPolicy or type(now) is not datetime or now.tzinfo is None \
            or now.utcoffset() != timedelta(0):
        raise OriginError("origin policy or clock admission is invalid")
    policy.__post_init__()
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30 \
            or not math.isfinite(timeout_seconds) or type(stdout_limit) is not int \
            or not 1 <= stdout_limit <= 1024 * 1024 or type(stderr_limit) is not int \
            or not 1 <= stderr_limit <= 65536:
        raise OriginError("origin execution bounds are invalid")
    snapshots = (_capture(subject, 64 * 1024 * 1024), _capture(bundle, 8 * 1024 * 1024),
                 _capture(verifier, 256 * 1024 * 1024, True), _capture(trusted_root, 16 * 1024 * 1024))
    if subject.sha256 != policy.subject_sha256:
        raise OriginError("subject bytes differ from origin policy")
    _json(snapshots[1].raw)
    try:
        with tempfile.TemporaryDirectory(prefix="fleet-artifact-origin-") as temporary:
            directory = Path(temporary)
            copies = tuple(directory / name for name in ("subject", "bundle.json", "gh", "trusted-root.json"))
            for snapshot, path in zip(snapshots, copies):
                path.write_bytes(snapshot.raw)
                path.chmod(0o700 if snapshot.executable else 0o600)
            private = tuple(_capture(PinnedFile(path, snapshot.pin.sha256), snapshot.limit, snapshot.executable)
                            for snapshot, path in zip(snapshots, copies))
            command = [str(copies[2]), "attestation", "verify", str(copies[0]),
                       "--bundle", str(copies[1]), "--custom-trusted-root", str(copies[3]),
                       "--repo", policy.repository, "--cert-identity", policy.workflow_identity,
                       "--cert-oidc-issuer", policy.issuer, "--signer-digest", policy.signer_commit,
                       "--source-digest", policy.source_commit, "--source-ref", policy.source_ref,
                       "--predicate-type", policy.predicate_type, "--deny-self-hosted-runners", "--format=json"]
            try:
                for snapshot in snapshots + private:
                    snapshot.recheck()
                output = _run(command, directory, timeout_seconds, stdout_limit, stderr_limit)
                timestamps = _claims(output, policy, now)
            finally:
                for snapshot in snapshots + private:
                    snapshot.recheck()
        return OriginFacts(policy, bundle.sha256, verifier.sha256, trusted_root.sha256, timestamps, now)
    except OSError:
        raise OriginError("origin verification files are unavailable") from None


def verify_rebuild_handoff_origin(
    retained: _fleet.PreservedRebuildHandoff, policy: OriginPolicy,
    bundle: PinnedFile, verifier: PinnedFile, trusted_root: PinnedFile, *, now: datetime,
    timeout_seconds: float = 30, stdout_limit: int = 1024 * 1024, stderr_limit: int = 65536,
) -> OriginFacts:
    """Verify origin of the exact retained manifest and its existing byte closure.

    Policy (including expected subject SHA) is independently admitted, never
    derived from the candidate. Full handoff checks bracket the real verifier,
    including its failure path. The execution timeout bounds the verifier, not
    these byte-bounded filesystem checks. Custody must remain independently
    admitted and quiescent; the returned facts are not producer-job attribution,
    runtime authentication, credential isolation or signing permission.
    """
    if type(retained) is not _fleet.PreservedRebuildHandoff or type(policy) is not OriginPolicy:
        raise OriginError("preserved handoff and origin policy admission are required")
    policy.__post_init__()
    try:
        retained.assert_exact()
        if policy.subject_name != "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json" \
                or policy.subject_sha256 != retained.artifact_closure_sha256:
            raise OriginError("origin policy differs from the retained handoff subject")
        subject = PinnedFile(retained.artifact_subject_path, retained.artifact_closure_sha256)
        try:
            return verify_origin(
                policy, subject, bundle, verifier, trusted_root, now=now,
                timeout_seconds=timeout_seconds, stdout_limit=stdout_limit, stderr_limit=stderr_limit,
            )
        finally:
            retained.assert_exact()
    except _fleet.RebuilderError:
        raise OriginError("preserved rebuild handoff no longer matches its admission") from None
