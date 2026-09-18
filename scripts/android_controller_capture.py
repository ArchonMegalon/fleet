"""One-shot controller orchestration of authenticated request, capture and emission.

The owner admits this controller/import closure, existing challenge store, exact
job policies, Docker inputs, preserved namespace, and emitter independently.
The emitter is an explicit trusted integration, not implemented by this module.
It receives public preserved bytes and the authenticated intended emission job;
its result is accepted only after the existing cryptographic origin verifier.

GitHub authenticates the REQUESTING jobs, not the location of the controller's
Docker execution. No local build is relabelled hosted, no signing/runtime
capability is produced, and the existing seven-file handoff stays unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import threading
import time
from typing import Callable

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_container_runtime as runtime
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_workflow_challenge_store as challenges
from scripts import android_workflow_identity as identity


class ControllerCaptureError(RuntimeError):
    """Constant errors only; raw workload tokens must never be logged."""


@dataclass(frozen=True, slots=True)
class ControllerEmission:
    capture_job: identity.WorkflowJobIdentity
    emission_job: identity.WorkflowJobIdentity
    capture: capture.BuilderHandoffCapture
    artifact_origin: origin.OriginFacts
    capture_order: str = "authenticated-job-before-build"
    # Ordinary local composition facts, never an authenticated signing lease.


def _require(value, code):
    if not value:
        raise ControllerCaptureError(code)


def _role(policy):
    return tuple((item.name, getattr(policy, item.name)) for item in fields(policy)
                 if item.name not in {"challenge_nonce", "challenge_issued_at", "challenge_expires_at"})


def _challenge(policy):
    return hashlib.sha256(policy.audience.encode("ascii")).hexdigest()


class OwnedSingleBuild:
    """One real owner-invoked build kept live until authenticated transfer.

    This is not deserializable build evidence or a signing capability. The
    admitted owner invokes the fixed builder itself, without a supplied AAB,
    then admits the measured manifest digest into the existing exact policies.
    GitHub subsequently authorizes transfer/emission, not this earlier build.
    A lost owner process cannot reconstruct this object from retained files.
    """

    def __init__(self, *, policy: runtime.RuntimePolicy, docker: origin.PinnedFile,
                 lock: origin.PinnedFile, operation_directory: Path,
                 output_bind_target: str, handoff_child_name: str):
        self._mutex = threading.RLock()
        self._claimed = self._failed = False
        self._arguments = (policy, docker, lock, operation_directory,
                           output_bind_target, handoff_child_name)
        try:
            _require(type(policy) is runtime.RuntimePolicy and policy.process_role == "builder"
                     and type(docker) is origin.PinnedFile and type(lock) is origin.PinnedFile,
                     "single-build-admission")
            policy.__post_init__()
            self._lock = origin._capture(lock, 1024 * 1024)
            value = fleet._strict_json(self._lock.raw, "single-build owner lock")
            _require(fleet.build_verification_mode(value) == "internal-single-build"
                     and not fleet.validate_unsigned_rebuild_lock(value, self._lock.raw,
                                                                  policy.requested_image),
                     "single-build-owner-policy")
            self._limits = capture._limits(value)
            self._result = capture.run_builder_capture_handoff(
                policy, docker, operation_directory, lock, output_bind_target, handoff_child_name)
            self._lock.recheck()
            _require(type(self._result) is capture.BuilderHandoffCapture
                     and self._result.directory == operation_directory / capture.COPY_DIRECTORY
                     and self._result.lock_sha256 == lock.sha256, "single-build-capture")
            self._digests = dict(self._result.file_sha256)
            _require(len(self._digests) == len(self._result.file_sha256)
                     and set(self._digests) == set(self._limits)
                     and self._digests[capture.MANIFEST] == self._result.artifact_closure_sha256,
                     "single-build-inventory")
            self._owner = os.getuid(), os.getgid()
            fd = capture._directory(self._result.directory, self._owner)
            try:
                self._root = capture._identity(os.fstat(fd))
                self._metadata = capture._metadata(fd, self._limits, self._owner)
            finally:
                os.close(fd)
            self.assert_exact()
        except BaseException:
            self._failed = True
            raise ControllerCaptureError("owned-single-build-failed-no-retry") from None

    def assert_exact(self):
        with self._mutex:
            try:
                _require(not self._failed, "single-build-stopped")
                self._lock.recheck()
                capture._terminal(self._result.execution, self._arguments[0])
                fd = capture._directory(self._result.directory, self._owner)
                try:
                    capture._recheck(fd, self._result.directory, self._root, self._metadata,
                                     self._limits, self._owner, self._digests)
                finally:
                    os.close(fd)
                self._lock.recheck()
            except BaseException:
                self._failed = True
                raise ControllerCaptureError("owned-single-build-drift") from None

    @property
    def manifest_sha256(self):
        self.assert_exact()
        return self._result.artifact_closure_sha256

    def check_binding(self, policy, docker, lock, operation_directory,
                      output_bind_target, handoff_child_name, artifact_policy):
        with self._mutex:
            try:
                self.assert_exact()
                _require(not self._claimed and self._arguments ==
                         (policy, docker, lock, operation_directory, output_bind_target, handoff_child_name)
                         and type(artifact_policy) is origin.OriginPolicy
                         and artifact_policy.subject_name == capture.MANIFEST
                         and artifact_policy.subject_sha256 == self._result.artifact_closure_sha256,
                         "single-build-binding")
            except BaseException:
                self._failed = True
                raise ControllerCaptureError("owned-single-build-binding") from None

    def _claim(self, *arguments):
        with self._mutex:
            self.check_binding(*arguments)
            self._claimed = True  # A later authentication/copy failure cannot reuse this build.
            return self._result


class ControllerCaptureSession:
    """Single in-memory attempt; lost/failed actions never replay from receipts.

    ``capture_job`` is the freshly issued existing policy. ``emission_job`` is
    the independently admitted second-job template; its challenge is issued by
    the owner only after the long build, without renewing the capture job slot.
    Policies must select distinct exact check runs in the same transaction and
    workflow invocation. The store remains the only challenge/crypto authority.
    An explicit live ``owned_single_build`` instead authorizes transfer of the
    owner's earlier build; it never makes that build GitHub-requested or hosted.
    """

    def __init__(self, store: challenges.SQLiteWorkflowChallengeStore,
                 capture_job: identity.WorkflowJobPolicy, emission_job: identity.WorkflowJobPolicy,
                 artifact_policy: origin.OriginPolicy, preserved_directory: Path, *,
                 owned_single_build: OwnedSingleBuild | None = None):
        try:
            _require(type(store) is challenges.SQLiteWorkflowChallengeStore
                     and type(capture_job) is identity.WorkflowJobPolicy
                     and type(emission_job) is identity.WorkflowJobPolicy
                     and type(artifact_policy) is origin.OriginPolicy, "controller-admission")
            capture_job.__post_init__()
            emission_job.__post_init__()
            artifact_policy.__post_init__()
            same = ("repository", "repository_id", "repository_owner", "repository_owner_id",
                    "sha", "ref", "workflow_ref", "workflow_sha", "run_id", "run_attempt", "transaction_id")
            _require(all(getattr(capture_job, name) == getattr(emission_job, name) for name in same)
                     and capture_job.check_run_id != emission_job.check_run_id
                     and capture_job.runner_environment == emission_job.runner_environment == "github-hosted"
                     and capture_job.job_status == emission_job.job_status == "in_progress"
                     and capture_job.run_status == emission_job.run_status == "in_progress", "controller-job-relation")
            identity._same_context(emission_job, artifact_policy)
            _require(artifact_policy.subject_name == capture.MANIFEST
                     and isinstance(preserved_directory, Path)
                     and runtime._path(str(preserved_directory)), "controller-subject-admission")
            self._store, self._capture_job, self._emission_job = store, capture_job, emission_job
            self._artifact_policy, self._preserved_directory = artifact_policy, preserved_directory
            _require(owned_single_build is None or type(owned_single_build) is OwnedSingleBuild,
                     "controller-owned-build-type")
            if owned_single_build is not None:
                _require(owned_single_build.manifest_sha256 == artifact_policy.subject_sha256,
                         "controller-owned-build-subject")
            self._owned_single_build = owned_single_build
            self._capture_started = self._emission_started = False
            self._captured = self._requester = self._lock_pin = self._lock_snapshot = None
            self._mutex = threading.RLock()
        except BaseException:
            raise ControllerCaptureError("controller-admission-failed") from None

    def _consume(self, issued, token):
        # Compare the actual stored policy, not a caller-supplied identity or
        # only the returned facts (which omit some original policy fields).
        _row, stored = self._store._read(_challenge(issued))
        _require(stored == issued, "controller-challenge-policy")
        facts = self._store.authenticate_and_consume(_challenge(issued), token)
        self._store._match(facts, issued, int(time.time()))
        return facts

    def capture(self, token: str, *, policy: runtime.RuntimePolicy, docker: origin.PinnedFile,
                lock: origin.PinnedFile, operation_directory: Path, output_bind_target: str,
                handoff_child_name: str) -> capture.BuilderHandoffCapture:
        """Authenticate capture or one-time transfer of the live owner build."""
        with self._mutex:
            _require(not self._capture_started and not self._emission_started, "controller-capture-already-started")
            self._capture_started = True
            try:
                _require(type(policy) is runtime.RuntimePolicy and policy.process_role == "builder"
                         and type(docker) is origin.PinnedFile and type(lock) is origin.PinnedFile,
                         "controller-builder-admission")
                policy.__post_init__()
                self._lock_snapshot = origin._capture(lock, 1024 * 1024)
                self._lock_pin = lock
                value = None
                if self._owned_single_build is not None:
                    # Claim once before authentication. Invalid or lost transfer
                    # authorization never licenses reassignment to another job.
                    value = self._owned_single_build._claim(
                        policy, docker, lock, operation_directory, output_bind_target,
                        handoff_child_name, self._artifact_policy)
                self._requester = self._consume(self._capture_job, token)
                self._lock_snapshot.recheck()
                self._store._match(self._requester, self._capture_job, int(time.time()))
                if value is None:
                    value = capture.run_builder_capture_handoff(
                        policy, docker, operation_directory, lock, output_bind_target, handoff_child_name)
                else:
                    self._owned_single_build.assert_exact()
                self._lock_snapshot.recheck()
                _require(type(value) is capture.BuilderHandoffCapture
                         and value.directory == operation_directory / capture.COPY_DIRECTORY
                         and value.lock_sha256 == lock.sha256
                         and value.artifact_closure_sha256 == self._artifact_policy.subject_sha256,
                         "controller-capture-binding")
                capture._terminal(value.execution, policy)
                lock_value = fleet._strict_json(self._lock_snapshot.raw, "controller lock")
                expected = capture._limits(lock_value)
                members = dict(value.file_sha256)
                _require(len(members) == len(value.file_sha256) and set(members) == set(expected)
                         and members[capture.MANIFEST] == value.artifact_closure_sha256,
                         "controller-capture-inventory")
                self._captured = value
                return value
            except BaseException:
                # The original operation evidence and consumed challenge stay.
                # No reset, recreation, automatic retry, or secret-bearing error.
                raise ControllerCaptureError("controller-capture-failed-no-retry") from None

    def _retained(self, retained):
        if self._owned_single_build is not None:
            self._owned_single_build.assert_exact()
        _require(type(retained) is fleet.PreservedRebuildHandoff
                 and retained.artifact_subject_path == self._preserved_directory / capture.MANIFEST,
                 "controller-preserved-path")
        retained.assert_exact()
        self._lock_snapshot.recheck()
        expected = dict(self._captured.file_sha256)
        _require(retained.artifact_closure_sha256 == self._captured.artifact_closure_sha256
                 and retained.handoff["bindings"]["lockSha256"] == self._lock_pin.sha256
                 and retained._snapshot["lock"][1] == self._lock_pin.sha256
                 and set(retained._snapshot) == set(expected) | {"directory", "lock"}
                 and all(retained._snapshot[name][1] == digest for name, digest in expected.items()),
                 "controller-preserved-capture-differs")

    def emit(self, issued_job: identity.WorkflowJobPolicy, token: str,
             retained: fleet.PreservedRebuildHandoff, *,
             emitter: Callable[[fleet.PreservedRebuildHandoff, identity.WorkflowJobIdentity], origin.PinnedFile],
             verifier: origin.PinnedFile, trusted_root: origin.PinnedFile) -> ControllerEmission:
        """Invoke one admitted emitter, then verify its actual exact-byte origin.

        No emitter/provider is discovered or installed. A callback success is
        not evidence: the returned bundle must pass the existing real verifier.
        Exceptions, drift, expiry, or lost responses poison this attempt; the
        already consumed challenge/emitted data must be reconciled externally.
        """
        with self._mutex:
            _require(self._captured is not None and not self._emission_started, "controller-emission-state")
            self._emission_started = True
            try:
                _require(type(issued_job) is identity.WorkflowJobPolicy and callable(emitter)
                         and _role(issued_job) == _role(self._emission_job), "controller-emission-job")
                issued_job.__post_init__()
                self._retained(retained)
                # Pin verifier/trust bytes before any emitter action. They are
                # never chosen from the callback's output or candidate files.
                tool = origin._capture(verifier, 256 * 1024 * 1024, executable=True)
                root = origin._capture(trusted_root, 16 * 1024 * 1024)
                facts = self._consume(issued_job, token)
                _require(facts.job_id != self._requester.job_id, "controller-distinct-emission-job")
                self._retained(retained)
                self._store._match(facts, issued_job, int(time.time()))
                try:
                    bundle = emitter(retained, facts)
                finally:
                    self._retained(retained)
                    tool.recheck()
                    root.recheck()
                _require(type(bundle) is origin.PinnedFile, "controller-emission-bundle")
                self._store._match(facts, issued_job, int(time.time()))
                try:
                    verified = origin.verify_rebuild_handoff_origin(
                        retained, self._artifact_policy, bundle, verifier, trusted_root, now=datetime.now(UTC))
                    _require(type(verified) is origin.OriginFacts and verified.policy == self._artifact_policy,
                             "controller-emission-origin")
                    identity._same_context(issued_job, verified.policy)
                    self._store._match(facts, issued_job, int(time.time()))
                finally:
                    self._retained(retained)
                    tool.recheck()
                    root.recheck()
                order = ("owner-build-before-authenticated-transfer" if self._owned_single_build is not None
                         else "authenticated-job-before-build")
                return ControllerEmission(self._requester, facts, self._captured, verified, order)
            except BaseException:
                raise ControllerCaptureError("controller-emission-failed-no-retry") from None
