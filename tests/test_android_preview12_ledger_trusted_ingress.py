"""Opt-in transport-peer admission. Public fixtures only; no tunnel activation."""
import asyncio
from dataclasses import replace
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
from urllib.parse import urlsplit

import pytest

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_server as launcher
from scripts import android_preview12_approval_ledger_service as service


_spec = importlib.util.spec_from_file_location(
    "trusted_ingress_launcher_fixture",
    Path(__file__).with_name("test_android_preview12_approval_ledger_server.py"),
)
server_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server_fixture)
sf = server_fixture.service_fixture
bound = sf.bound
certificates = server_fixture.certificates
launch = server_fixture.launch


def proxy_headers(**changes):
    values = {"x-forwarded-for": "203.0.113.7, 198.51.100.8", "x-forwarded-proto": "https"}
    values.update(changes)
    return sf.headers(sf.raw_request(), **values)


INVALID_CONFIGS = [
    None, [], ["127.0.0.1"], "127.0.0.1", (None,), (True,), (123,), ([],),
    ("127.0.0.1",) * 2, ("10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"),
    ("*",), ("",), ("10.0.0.0/8",), ("127.000.0.1",), (" 127.0.0.1",),
    ("127.0.0.1\n",), ("localhost",), ("0.0.0.0",), ("::",), ("224.0.0.1",),
    ("255.255.255.255",), ("8.8.8.8",), ("169.254.1.1",), ("100.64.0.1",),
    ("192.0.2.1",), ("[::1]",), ("0:0:0:0:0:0:0:1",), ("fc00::1%eth0",),
    ("FC00::1",), ("::ffff:127.0.0.1",), ("ff02::1",), ("fe80::1",), ("2001:db8::1",),
]


@pytest.mark.parametrize("addresses", INVALID_CONFIGS)
def test_invalid_factory_peers_do_not_access_store(bound, addresses):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()
    with pytest.raises(service.ServiceConfigurationError) as error:
        service.create_app(**arguments, trusted_proxy_addresses=addresses)
    assert str(error.value) == "explicit ledger service configuration is invalid"
    assert error.value.__cause__ is None and error.value.__context__ is None
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("addresses", INVALID_CONFIGS)
def test_invalid_launcher_peers_reject_before_opening_any_input(launch, monkeypatch, addresses):
    opened = []
    original = launcher._HeldFile

    def tracked(*args, **kwargs):
        opened.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(launcher, "_HeldFile", tracked)
    before = Path(launch[2].database).read_bytes()
    server_fixture.reject(replace(launch[2], trusted_proxy_addresses=addresses))
    assert opened == []
    assert Path(launch[2].database).read_bytes() == before


@pytest.mark.parametrize("peer", ["127.0.0.1", "10.0.0.2", "172.19.0.2", "192.168.1.2", "::1", "fd00::2"])
def test_explicit_peer_can_authenticate_without_forwarded_identity(bound, peer):
    _, store, policy, signatures, arguments = bound
    app = service.create_app(**arguments, trusted_proxy_addresses=(peer,))
    # XFF is intentionally not an identity parser or an authorization claim.
    status, raw, _ = sf.invoke(app, raw_headers=proxy_headers(**{"x-forwarded-for": "untrusted-client-metadata"}),
                              changes={"client": (peer, 40000)})
    assert status == 200 and store.calls == 1 and len(signatures) == 1
    checked = protocol.validate_response(json.loads(raw), request=json.loads(sf.raw_request()), policy=policy)
    assert checked["receipt"]["state"] == "reserved"
    assert b"untrusted-client-metadata" not in raw and b"untrusted-client-metadata" not in signatures[0]


@pytest.mark.parametrize("client", [
    None, (), ("127.0.0.1",), ("127.0.0.1", 123, "extra"), "127.0.0.1",
    ("10.0.0.9", 123), ("203.0.113.7", 123), ("::ffff:127.0.0.1", 123),
    (b"127.0.0.1", 123), (["127.0.0.1"], 123), ("127.0.0.1", True),
    ("127.0.0.1", "443"), ("127.0.0.1", 0), ("127.0.0.1", 65536), ("127.0.0.1", -1),
])
def test_forwarded_headers_cannot_authenticate_a_wrong_transport_peer(bound, client):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()

    async def forbidden_receive():
        pytest.fail("untrusted peer consumed body")

    result = sf.invoke(service.create_app(**arguments, trusted_proxy_addresses=("127.0.0.1",)),
        changes={"client": client}, raw_headers=proxy_headers(**{
            "x-forwarded-for": "127.0.0.1", "cf-connecting-ip": "127.0.0.1",
        }), receive_override=forbidden_receive)
    assert result[0] == 400 and result[1] == b'{"error":"invalid_request"}'
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("changes,status", [
    ({"x-forwarded-for": None}, 400), ({"x-forwarded-for": ""}, 400),
    ({"x-forwarded-for": "   "}, 400), ({"x-forwarded-for": "x" * 1025}, 400),
    ({"x-forwarded-for": "bad\r\nheader"}, 400), ({"x-forwarded-proto": None}, 400),
    ({"x-forwarded-proto": "http"}, 400), ({"x-forwarded-proto": "HTTPS"}, 400),
    ({"x-forwarded-proto": "https,http"}, 400), ({"forwarded": "proto=https"}, 400),
    ({"x-forwarded-host": "ledger.example.test"}, 400), ({"x-forwarded-port": "443"}, 400),
    ({"host": "other.example.test"}, 400), ({"origin": "https://ledger.example.test"}, 403),
    ({"authorization": None}, 401), ({"authorization": "Bearer wrong"}, 401),
    ({"content-type": "text/plain"}, 415), ({"transfer-encoding": "chunked"}, 400),
])
def test_trusted_proxy_cannot_bypass_existing_headers_auth_or_framing(bound, changes, status):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()

    async def forbidden_receive():
        pytest.fail("rejected headers consumed body")

    result = sf.invoke(service.create_app(**arguments, trusted_proxy_addresses=("127.0.0.1",)),
                       raw_headers=proxy_headers(**changes), receive_override=forbidden_receive)
    assert result[0] == status and sf.TOKEN not in result[1]
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("mode", ["direct", "http", "duplicate", "missing-forwarding", "missing-client"])
def test_opt_in_never_weakens_actual_tls_or_default_header_rejection(bound, mode):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()
    peers = () if mode == "direct" else ("127.0.0.1",)
    headers = proxy_headers()
    changes = {}
    if mode == "http":
        changes["scheme"] = "http"
    elif mode == "duplicate":
        headers.append((b"X-Forwarded-Proto", b"https"))
    elif mode == "missing-forwarding":
        headers = sf.headers(sf.raw_request())
    elif mode == "missing-client":
        changes["client"] = None

    async def forbidden_receive():
        pytest.fail("failed admission consumed body")

    assert sf.invoke(service.create_app(**arguments, trusted_proxy_addresses=peers),
        raw_headers=headers, changes=changes, receive_override=forbidden_receive)[0] == 400
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


def test_cli_converts_repeatable_peers_to_immutable_tuple(launch, monkeypatch, capsys):
    config = launch[2]
    names = ("policy", "database", "database_id", *server_fixture.CREDENTIALS, "bind_address")
    args = [item for field in names for item in ("--" + field.replace("_", "-"), getattr(config, field))]
    captured = []

    def capture(options):
        captured.append(options)
        raise launcher.LaunchError("test-only-no-bind")

    monkeypatch.setattr(launcher, "prepare", capture)
    assert launcher.main([*args, "--trusted-proxy-address", "127.0.0.1", "--trusted-proxy-address", "::1"]) == 1
    assert len(captured) == 1 and captured[0].trusted_proxy_addresses == ("127.0.0.1", "::1")
    assert type(captured[0].trusted_proxy_addresses) is tuple
    output = capsys.readouterr()
    assert output.out == "" and output.err == "ledger_server=unavailable\n"


def test_real_tls_proxy_hop_retains_client_receipt_and_peer_checks(launch):
    config = replace(launch[2], trusted_proxy_addresses=("127.0.0.1",))
    trust = ssl.create_default_context(cafile=config.tls_cert_file)
    assert trust.verify_mode == ssl.CERT_REQUIRED and trust.check_hostname

    async def exercise(prepared):
        assert prepared.config.proxy_headers is False and prepared.config.forwarded_allow_ips == ""
        assert prepared.config.port == 443 and prepared.config.workers == 1
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
                    pytest.fail("test TLS server exited before readiness")
                await asyncio.sleep(0.01)

        def transport(url, body, headers, timeout, *, forwarded=True):
            connection = http.client.HTTPSConnection(server_fixture.HOST, context=trust, timeout=min(timeout, 3))
            try:
                raw = socket.create_connection(("127.0.0.1", port), timeout=3)
                connection.sock = trust.wrap_socket(raw, server_hostname=server_fixture.HOST)
                outgoing = dict(headers, Host=server_fixture.HOST)
                if forwarded:
                    outgoing.update({"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"})
                connection.request("POST", urlsplit(url).path, body, outgoing)
                response = connection.getresponse()
                payload = response.read(65537)
                assert len(payload) <= 65536
                return protocol.HttpResponse(response.status, dict(response.getheaders()), payload)
            finally:
                connection.close()

        def round_trip():
            before = Path(config.database).read_bytes()
            rejected = transport("https://" + server_fixture.HOST + sf.PREFIX + "reserve",
                sf.raw_request(), {key.decode(): value.decode() for key, value in sf.headers(sf.raw_request()) if key != b"host"},
                3, forwarded=False)
            assert rejected.status == 400 and Path(config.database).read_bytes() == before
            client = protocol.DurableApprovalLedgerClient(sf.fixture.active_ledger_policy(),
                {protocol.CREDENTIAL_ENV_NAME: sf.TOKEN.decode()}, transport=transport, sleeper=lambda _: None)
            subject = sf.fixture.subject()
            reserved = client.reserve(subject)
            committed = client.commit(subject, sf.APPROVAL, reserved)
            recovered = client.status(subject, reserved)
            assert reserved["receipt"]["revision"] == 1
            assert committed["receipt"]["revision"] == recovered["receipt"]["revision"] == 2
            assert recovered["receipt"]["state"] == "committed"

        try:
            await asyncio.wait_for(started(), 5)
            with pytest.raises(ssl.SSLCertVerificationError):
                await asyncio.wait_for(asyncio.open_connection(
                    "127.0.0.1", port, ssl=trust, server_hostname="wrong.example.test"), 3)
            await asyncio.wait_for(asyncio.to_thread(round_trip), 15)
        finally:
            prepared.server.should_exit = True
            try:
                await asyncio.wait_for(task, 5)
            finally:
                listener.close()

    with launcher.prepare(config) as prepared:
        asyncio.run(exercise(prepared))
