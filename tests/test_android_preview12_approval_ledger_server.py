"""Local launcher qualification using PUBLIC RFC keys and private temp fixtures.

One real TLS listener binds only 127.0.0.1 on a test-owned ephemeral socket.
Its client verifies the fixture CA and hostname; no remote DNS, service, real
credential, approval-signing authority, deployment or publication is exercised.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import FrozenInstanceError, replace
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import textwrap
import time
from urllib.parse import urlsplit

import pytest

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_server as launcher
from scripts import android_preview12_approval_ledger_store as persistence


_spec = importlib.util.spec_from_file_location(
    "launcher_existing_service_fixture",
    Path(__file__).with_name("test_android_preview12_approval_ledger_service.py"),
)
service_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service_fixture)
fixture = service_fixture.fixture
ROOT = Path(__file__).resolve().parents[1]
HOST = "ledger.example.test"
DATABASE_ID = "c" * 64
# RFC 8032 section 7.1 test vector 2, distinct from the receipt fixture key.
OTHER_PRIVATE_DER = bytes.fromhex(
    "302e020100300506032b657004220420"
    "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
)
OTHER_PUBLIC_DER = bytes.fromhex(
    "302a300506032b6570032100"
    "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
)
CREDENTIALS = ("bearer_sha256_file", "receipt_key_file", "tls_cert_file", "tls_key_file")


def private_write(path, raw):
    path.write_bytes(raw)
    path.chmod(0o600)
    return str(path)


@pytest.fixture(scope="module")
def certificates():
    # Direct /tmp child is intentional: launcher ancestry validation does not
    # grant pytest's ambient TMPDIR or another sticky directory an exception.
    with tempfile.TemporaryDirectory(prefix="ledger-tls-public-test-", dir="/tmp") as name:
        root = Path(name)
        pairs = []
        for index, host in enumerate((HOST, "other.example.test")):
            key, cert = root / f"key-{index}.pem", root / f"cert-{index}.pem"
            result = subprocess.run(
                ["/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-sha256", "-days", "2", "-config", "/dev/null", "-subj", f"/CN={host}",
                 "-addext", f"subjectAltName=DNS:{host}", "-keyout", str(key), "-out", str(cert)],
                capture_output=True, timeout=15, check=False,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            )
            assert result.returncode == 0, "public TLS fixture generation failed"
            pairs.append((cert.read_bytes(), key.read_bytes()))
        # Additional certificates deliberately reuse PUBLIC RFC role keys.
        # Their private DER fixtures are not deployed TLS or approval keys.
        for index, private_der in enumerate((fixture.TEST_PRIVATE_DER, OTHER_PRIVATE_DER), 2):
            key = root / f"rfc-key-{index}.der"
            private_write(key, private_der)
            certificate = fixture.openssl([
                "req", "-x509", "-key", str(key), "-keyform", "DER", "-days", "2",
                "-config", "/dev/null", "-subj", f"/CN={HOST}",
                "-addext", f"subjectAltName=DNS:{HOST}",
            ])
            pairs.append((certificate, private_der))
        yield pairs


@pytest.fixture
def launch(certificates):
    with tempfile.TemporaryDirectory(prefix="ledger-launcher-test-", dir="/tmp") as name:
        root = Path(name)
        policy = json.loads((ROOT / "config/release/android-preview12-two-green-release-approval.json").read_bytes())
        policy["replay_protection"]["external_ledger"] = fixture.active_ledger_policy()
        # Keep the approval issuer's real PUBLIC source pin unchanged. Only the
        # separate ledger receipt role is bound to a public RFC test key.
        database = root / "ledger.sqlite3"
        persistence.SQLiteApprovalLedgerStore.create(
            database, service_identity="chummer.preview12.approval-ledger", database_id=DATABASE_ID,
        )
        config = launcher.LaunchConfig(
            policy=private_write(root / "policy.json", protocol.pretty_bytes(policy)),
            database=str(database), database_id=DATABASE_ID,
            bearer_sha256_file=private_write(root / "bearer.sha256", service_fixture.TOKEN_DIGEST.encode() + b"\n"),
            receipt_key_file=private_write(root / "receipt.der", fixture.TEST_PRIVATE_DER),
            tls_cert_file=private_write(root / "cert.pem", certificates[0][0]),
            tls_key_file=private_write(root / "tls-key.pem", certificates[0][1]),
            bind_address="127.0.0.1",
        )
        yield root, policy, config


def reject(config):
    with pytest.raises(launcher.LaunchError) as error:
        launcher.prepare(config)
    text = str(error.value)
    assert "ledger-launcher-test-" not in text
    assert service_fixture.TOKEN.decode() not in text
    assert "PRIVATE KEY" not in text
    return text


def reject_before_credentials(config, monkeypatch):
    forbidden = {getattr(config, field) for field in CREDENTIALS}
    attempted = []
    original = launcher._HeldFile

    def tracked_hold(value, limit):
        if value in forbidden:
            attempted.append(value)
        return original(value, limit)

    with monkeypatch.context() as patch:
        patch.setattr(launcher, "_HeldFile", tracked_hold)
        reject(config)
    # An inline assertion alone could be normalized into LaunchError.
    assert attempted == []


def test_prepared_configuration_is_frozen_tls_only_and_bounded(launch):
    _, _, config = launch
    with pytest.raises(FrozenInstanceError):
        config.bind_address = "0.0.0.0"
    with launcher.prepare(config) as prepared:
        server = prepared.config
        assert server.loaded and server.is_ssl and isinstance(server.ssl, ssl.SSLContext)
        assert server.host == "127.0.0.1" and server.port == 443
        assert server.workers == 1 and not server.reload
        assert server.proxy_headers is False and server.access_log is False
        assert server.limit_concurrency == config.maximum_connections
        assert server.timeout_graceful_shutdown == config.shutdown_timeout
        assert server.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2
        assert prepared.server.config is server


def test_dormant_policy_is_rejected_before_any_credential_open(launch, monkeypatch):
    root, policy, config = launch
    policy["replay_protection"]["external_ledger"] = protocol.dormant_ledger_policy()
    private_write(Path(config.policy), protocol.pretty_bytes(policy))
    for field in CREDENTIALS:
        path = Path(getattr(config, field))
        path.unlink()
        os.mkfifo(path, 0o600)
    before = (root / "ledger.sqlite3").read_bytes()
    reject_before_credentials(config, monkeypatch)
    assert (root / "ledger.sqlite3").read_bytes() == before


@pytest.mark.parametrize("field", ("policy", "database", *CREDENTIALS))
@pytest.mark.parametrize("defect", ("missing", "symlink", "hardlink", "nonprivate"))
def test_input_custody_rejects_unsafe_files_without_creating_database(launch, field, defect):
    root, _, config = launch
    path = Path(getattr(config, field))
    if defect == "missing":
        path.unlink()
    elif defect == "symlink":
        target = root / "saved-input"
        path.rename(target)
        path.symlink_to(target)
    elif defect == "hardlink":
        os.link(path, root / "extra-link")
    else:
        path.chmod(0o640)
    reject(config)
    if defect == "missing":
        assert not path.exists()


@pytest.mark.parametrize("defect", ("relative", "dotdot", "fifo", "directory", "oversized", "empty"))
def test_receipt_key_rejects_noncanonical_or_unbounded_inputs(launch, defect):
    root, _, config = launch
    path = Path(config.receipt_key_file)
    if defect == "relative":
        config = replace(config, receipt_key_file="receipt.der")
    elif defect == "dotdot":
        config = replace(config, receipt_key_file=str(root) + "/../" + root.name + "/receipt.der")
    elif defect == "oversized":
        path.write_bytes(b"x" * 65537)
    elif defect == "empty":
        path.write_bytes(b"")
    else:
        path.unlink()
        os.mkfifo(path, 0o600) if defect == "fifo" else path.mkdir(mode=0o700)
    reject(config)


@pytest.mark.parametrize("mode", (0o777, 0o770, 0o1777))
def test_private_ancestor_cannot_inherit_tmp_sticky_exception(launch, mode):
    root, _, config = launch
    root.chmod(mode)
    try:
        reject(config)
    finally:
        root.chmod(0o700)


def test_modeled_wrong_owner_is_rejected_even_with_private_mode(launch, monkeypatch):
    config = launch[2]
    target = Path(config.receipt_key_file)
    original = Path.lstat

    def modeled_lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            fields = list(info)
            fields[4] = os.getuid() + 1
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(Path, "lstat", modeled_lstat)
    reject(config)


@pytest.mark.parametrize("field,value", [
    ("maximum_in_flight", True), ("maximum_in_flight", 0), ("maximum_in_flight", 9),
    ("maximum_connections", True), ("maximum_connections", 0), ("maximum_connections", 257),
    ("body_timeout", True), ("body_timeout", 0), ("body_timeout", 11), ("body_timeout", float("nan")),
    ("shutdown_timeout", 0), ("shutdown_timeout", float("inf")),
    ("bind_address", "ledger.example.test"), ("bind_address", "127.0.0.1:443"),
    ("database_id", "D" * 64), ("database_id", "d" * 64),
])
def test_limits_bind_address_and_database_identity_fail_closed(launch, field, value):
    reject(replace(launch[2], **{field: value}))


@pytest.mark.parametrize("raw", (b"not-a-digest\n", b"A" * 64, b"1" * 64 + b"\n\n", b"1" * 65537))
def test_bearer_digest_requires_exact_bounded_lowercase_hex(launch, raw):
    config = launch[2]
    Path(config.bearer_sha256_file).write_bytes(raw)
    reject(config)


@pytest.mark.parametrize("raw", (OTHER_PRIVATE_DER, fixture.TEST_PRIVATE_DER + b"\x00", b"not a private key"))
def test_receipt_key_must_be_canonical_and_match_pinned_public_key(launch, raw):
    config = launch[2]
    Path(config.receipt_key_file).write_bytes(raw)
    reject(config)


@pytest.mark.parametrize("defect", ("reuse", "invalid_spki", "alternate_spki", "wrong_digest"))
def test_approval_public_key_is_valid_distinct_and_digest_bound(launch, defect):
    _, policy, config = launch
    key = policy["external_ed25519_key"]
    raw = {"reuse": fixture.PUBLIC_DER, "alternate_spki": OTHER_PUBLIC_DER}.get(defect, b"not SPKI")
    if defect != "wrong_digest":
        key["public_key_spki_der_base64"] = base64.b64encode(raw).decode()
        key["expected_public_key_spki_sha256"] = hashlib.sha256(raw).hexdigest()
    else:
        key["expected_public_key_spki_sha256"] = "0" * 64
    private_write(Path(config.policy), protocol.pretty_bytes(policy))
    reject(config)


def test_source_approval_key_cannot_be_relabelled_as_receipt_key(launch, monkeypatch):
    _, policy, config = launch
    approval = policy["external_ed25519_key"]
    ledger = policy["replay_protection"]["external_ledger"]
    ledger["receipt_public_key_spki_der_base64"] = approval["public_key_spki_der_base64"]
    ledger["receipt_public_key_spki_sha256"] = approval["expected_public_key_spki_sha256"]
    approval["public_key_spki_der_base64"] = base64.b64encode(OTHER_PUBLIC_DER).decode()
    approval["expected_public_key_spki_sha256"] = hashlib.sha256(OTHER_PUBLIC_DER).hexdigest()
    private_write(Path(config.policy), protocol.pretty_bytes(policy))
    Path(config.receipt_key_file).unlink()
    reject_before_credentials(config, monkeypatch)


@pytest.mark.parametrize("defect", ("mismatched_key", "wrong_hostname", "invalid_cert", "invalid_key"))
def test_tls_pair_and_policy_hostname_are_checked_before_startup(launch, certificates, defect):
    config = launch[2]
    if defect == "mismatched_key":
        Path(config.tls_key_file).write_bytes(certificates[1][1])
    elif defect == "wrong_hostname":
        Path(config.tls_cert_file).write_bytes(certificates[1][0])
        Path(config.tls_key_file).write_bytes(certificates[1][1])
    else:
        field = "tls_cert_file" if defect == "invalid_cert" else "tls_key_file"
        Path(getattr(config, field)).write_bytes(b"PRIVATE-TEST-SENTINEL")
    reject(config)


@pytest.mark.parametrize("role,index", (("receipt", 2), ("test_only_approval", 3)))
def test_tls_public_role_reuse_is_rejected_before_private_key_access(launch, certificates, monkeypatch, role, index):
    _, policy, config = launch
    if role == "test_only_approval":
        # Model the issuer source pin with RFC vector 2 ONLY within this test.
        # This never claims knowledge of the production approval private key.
        public = base64.b64encode(OTHER_PUBLIC_DER).decode()
        digest = hashlib.sha256(OTHER_PUBLIC_DER).hexdigest()
        monkeypatch.setattr(launcher.issuer, "RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64", public)
        monkeypatch.setattr(launcher.issuer, "RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256", digest)
        policy["external_ed25519_key"].update(
            public_key_spki_der_base64=public, expected_public_key_spki_sha256=digest,
        )
        private_write(Path(config.policy), protocol.pretty_bytes(policy))
    private_write(Path(config.tls_cert_file), certificates[index][0])
    Path(config.tls_key_file).unlink()
    os.mkfifo(config.tls_key_file, 0o600)
    attempted = []
    original = launcher._HeldFile

    def tracked_hold(value, limit):
        attempted.append(value)
        return original(value, limit)

    monkeypatch.setattr(launcher, "_HeldFile", tracked_hold)
    before = Path(config.database).read_bytes()
    reject(config)
    assert config.tls_cert_file in attempted  # Policy and receipt admission passed.
    assert config.tls_key_file not in attempted
    assert Path(config.database).read_bytes() == before


def test_real_certificate_verifier_rejects_expiry_at_advanced_test_clock(launch, monkeypatch):
    original = launcher._openssl
    checked = []

    def advanced_clock(arguments, descriptors):
        if arguments[0] == "verify":
            checked.append(True)
            arguments = ["verify", "-attime", str(int(time.time()) + 7 * 86400), *arguments[1:]]
        return original(arguments, descriptors)

    monkeypatch.setattr(launcher, "_openssl", advanced_clock)
    reject(launch[2])
    assert checked == [True]


def test_receipt_signing_is_input_bound_and_close_revokes_capability(launch):
    config = launch[2]
    prepared = launcher.prepare(config)
    statement = {"testOnly": True, "publicationAuthorized": False}
    raw = protocol.canonical_bytes(statement)
    expected = base64.b64decode(fixture.sign(statement)["signature"]["signatureBase64"])
    tls_descriptors = [int(path.rsplit("/", 1)[1]) for path in (
        prepared.config.ssl_certfile, prepared.config.ssl_keyfile,
    )]
    try:
        assert prepared.sign_receipt(raw) == expected
        Path(config.receipt_key_file).unlink()
        with pytest.raises(launcher.LaunchError):
            prepared.sign_receipt(raw)
    finally:
        prepared.close()
    prepared.close()
    for descriptor in tls_descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    with pytest.raises(launcher.LaunchError):
        prepared.sign_receipt(raw)


def test_failed_tls_startup_closes_all_sealed_input_descriptors(launch, certificates, monkeypatch):
    config = launch[2]
    Path(config.tls_key_file).write_bytes(certificates[1][1])
    descriptors = []
    original = launcher._sealed

    def tracked_seal(data, stack):
        descriptor = original(data, stack)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(launcher, "_sealed", tracked_seal)
    reject(config)
    assert len(descriptors) == 4
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_actual_composition_signs_protocol_receipt_and_rejects_forwarding(launch):
    with launcher.prepare(launch[2]) as prepared:
        status, raw, _ = service_fixture.invoke(prepared.app)
        assert status == 200
        request = json.loads(service_fixture.raw_request())
        checked = protocol.validate_response(json.loads(raw), request=request, policy=fixture.active_ledger_policy())
        assert checked["receipt"]["state"] == "reserved"
        headers = service_fixture.headers(service_fixture.raw_request(), **{"x-forwarded-proto": "https"})
        assert service_fixture.invoke(prepared.app, raw_headers=headers)[0] == 400


def test_changed_bearer_file_rejects_before_database_mutation(launch):
    config = launch[2]
    with launcher.prepare(config) as prepared:
        before = Path(config.database).read_bytes()
        Path(config.bearer_sha256_file).write_bytes(b"0" * 64 + b"\n")
        status, raw, _ = service_fixture.invoke(prepared.app)
        assert (status, raw) == (503, b'{"error":"service_unavailable"}')
        assert Path(config.database).read_bytes() == before


def test_cli_has_no_plaintext_or_port_override(launch, monkeypatch, capsys):
    config = launch[2]
    required = ("policy", "database", "database_id", *CREDENTIALS, "bind_address")
    arguments = [item for field in required for item in ("--" + field.replace("_", "-"), getattr(config, field))]
    monkeypatch.setattr(launcher, "prepare", lambda _: pytest.fail("CLI override reached preparation"))
    assert launcher.main([*arguments, "--port", "8443"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "ledger_server=unavailable\n"


@pytest.mark.parametrize("stop_signal", (signal.SIGTERM, signal.SIGINT))
def test_actual_cli_signal_closes_descriptors_before_terminal_status(launch, stop_signal):
    config = launch[2]
    required = ("policy", "database", "database_id", *CREDENTIALS, "bind_address")
    arguments = [item for field in required for item in ("--" + field.replace("_", "-"), getattr(config, field))]
    # Actual main/prepare/TLS/server signal handling; only socket binding and a
    # post-close observation hook are test substitutions. No production port.
    driver = textwrap.dedent("""
        import errno, os, socket, sys
        from scripts import android_preview12_approval_ledger_server as launcher
        original_prepare = launcher.prepare
        def prepare(config):
            prepared = original_prepare(config)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(('127.0.0.1', 0))
            listener.listen(16)
            listener.setblocking(False)
            original_run, original_close = prepared.server.run, prepared.close
            descriptors = {held.fd for held in prepared._files}
            descriptors.update((listener.fileno(), prepared._receipt_fd))
            descriptors.update(int(path.rsplit('/', 1)[1]) for path in (
                prepared.config.ssl_certfile, prepared.config.ssl_keyfile))
            def close():
                original_close()
                listener.close()
                for descriptor in descriptors:
                    try:
                        os.fstat(descriptor)
                    except OSError as error:
                        assert error.errno == errno.EBADF
                    else:
                        raise AssertionError('launcher descriptor still open')
                print('test_cleanup=closed', flush=True)
            prepared.server.run = lambda: original_run(sockets=[listener])
            prepared.close = close
            return prepared
        launcher.prepare = prepare
        raise SystemExit(launcher.main(sys.argv[1:]))
    """)
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", driver, *arguments], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    observed = bytearray()
    try:
        deadline = time.monotonic() + 10
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            while b"ledger_server=ready\n" not in observed:
                remaining = deadline - time.monotonic()
                assert remaining > 0, "test TLS child did not become ready"
                assert ready.select(remaining), "test TLS child readiness timed out"
                chunk = os.read(process.stdout.fileno(), 4096)
                assert chunk, "test TLS child exited before readiness"
                observed.extend(chunk)
                assert len(observed) <= 4096
        process.send_signal(stop_signal)
        tail, errors = process.communicate(timeout=10)
        observed.extend(tail)
        assert process.returncode == 128 + int(stop_signal)
        assert observed.splitlines() == [
            b"ledger_server=ready", b"test_cleanup=closed",
            ("ledger_server=stopped signal=" + stop_signal.name).encode(),
        ]
        assert errors == b"" and b"Traceback" not in observed
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        process.stdout.close()
        process.stderr.close()


def test_actual_tls_loopback_uses_verified_host_and_unchanged_client_then_shuts_down(launch):
    config = launch[2]
    trust = ssl.create_default_context(cafile=config.tls_cert_file)
    assert trust.verify_mode == ssl.CERT_REQUIRED and trust.check_hostname

    async def exercise(prepared):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        listener.setblocking(False)
        port = listener.getsockname()[1]
        task = asyncio.create_task(prepared.server.serve(sockets=[listener]))

        async def started():
            while not prepared.server.started:
                if task.done():
                    await task
                    pytest.fail("TLS server exited before startup")
                await asyncio.sleep(0.01)

        def transport(url, body, headers, timeout):
            parsed = urlsplit(url)
            assert parsed.hostname == HOST and parsed.scheme == "https" and parsed.port is None
            connection = http.client.HTTPSConnection(HOST, context=trust, timeout=min(timeout, 3))
            try:
                raw = socket.create_connection(("127.0.0.1", port), timeout=3)
                connection.sock = trust.wrap_socket(raw, server_hostname=HOST)
                assert connection.sock.getpeercert()["subjectAltName"] == (("DNS", HOST),)
                connection.request("POST", parsed.path, body, dict(headers, Host=HOST))
                response = connection.getresponse()
                payload = response.read(65537)
                assert len(payload) <= 65536
                return protocol.HttpResponse(response.status, dict(response.getheaders()), payload)
            finally:
                connection.close()

        def round_trip():
            client = protocol.DurableApprovalLedgerClient(
                fixture.active_ledger_policy(), {protocol.CREDENTIAL_ENV_NAME: service_fixture.TOKEN.decode()},
                transport=transport, sleeper=lambda _: None,
            )
            subject = fixture.subject()
            reserved = client.reserve(subject)
            committed = client.commit(subject, service_fixture.APPROVAL, reserved)
            recovered = client.status(subject, reserved)
            assert reserved["receipt"]["revision"] == 1
            assert committed["receipt"]["revision"] == recovered["receipt"]["revision"] == 2
            assert recovered["receipt"]["state"] == "committed"
            assert base64.b64decode(recovered["receipt"]["approval"]["publicJsonBase64"]) == service_fixture.APPROVAL

        try:
            await asyncio.wait_for(started(), 5)
            with pytest.raises(ssl.SSLCertVerificationError):
                await asyncio.wait_for(asyncio.open_connection(
                    "127.0.0.1", port, ssl=trust, server_hostname="wrong.example.test",
                ), 3)
            await asyncio.wait_for(asyncio.to_thread(round_trip), 15)
        finally:
            prepared.server.should_exit = True
            try:
                await asyncio.wait_for(task, 5)
            finally:
                listener.close()
        assert task.done() and not task.cancelled()

    with launcher.prepare(config) as prepared:
        asyncio.run(exercise(prepared))
    with pytest.raises(launcher.LaunchError):
        prepared.sign_receipt(b"closed")
