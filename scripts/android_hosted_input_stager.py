"""Deliver a pinned role bearer or stage two hosted OIDC request files.

This module/interpreter/import closure must be admitted BEFORE import. Profile,
context and deployment hashes are independent inputs, never self-admission.
Only explicitly injected values are copied to admitted fresh private paths.
No credential generation/fetch, signing-key provisioning, token request,
client, owner or deployment is performed. Delivery is not authentication.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import sys

from scripts import android_deployment_materializer as materializer
from scripts import android_hosted_controller_roles as hosted

ERROR = "hosted input staging stopped; preserve partial files and reconcile"
COMPLETE = "hosted request inputs staged; not authentication or deployment authority"
BEARER_COMPLETE = "hosted role bearer delivered; not authentication or deployment authority"
PROTECTED_COMPLETE = "protected request inputs staged; not authentication or deployment authority"
ENVIRONMENT = (("oidc_request_url", "ACTIONS_ID_TOKEN_REQUEST_URL"),
               ("oidc_request_credential", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"))
ROLES = ("capture", "emission")


class StagingError(RuntimeError):
    """Constant message only; no input paths, credential bytes or digests."""


def _require(value):
    if not value:
        raise StagingError(ERROR)


def _directory_stamp(info):
    # Child creation intentionally changes size/nlink/timestamps, not binding.
    return tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid"))


def _text(value, limit):
    _require(type(value) is str and 0 < len(value) <= limit)
    raw = value.encode("ascii")
    _require(all(0x21 <= char <= 0x7e for char in raw))
    return raw


def deliver_role_bearer(*, role, profile, profile_sha256, context, context_sha256,
                        deployment, deployment_sha256, environment=None):
    """Copy one explicitly injected, owner-hash-bound bearer; no remote transfer."""
    try:
        _require(role in ROLES and os.getuid() == os.geteuid() and os.getgid() == os.getegid())
        specs = ((profile, profile_sha256, materializer.MAX_PROFILE, True),
                 (context, context_sha256, materializer.MAX_CONTEXT, True),
                 (deployment, deployment_sha256, hosted.MAX_CONFIG, False))
        for path, digest, _limit, _public in specs:
            _require(isinstance(path, Path) and hosted._path(str(path)) == path
                     and hosted.identity._hex(digest, 64))
        with ExitStack() as cleanup:
            held = []
            def hold(path, limit, *, expected, public=False):
                item = hosted._Input(path, limit, expected=expected, public=public)
                cleanup.callback(item.close)
                held.append(item)
                return item
            documents = [hold(path, limit, expected=digest, public=public)
                         for path, digest, limit, public in specs]
            _require(len({item.stamp[:2] for item in documents}) == len(documents))
            profile_value = materializer._json(documents[0].raw)
            expected = materializer.render(profile_value, materializer._json(documents[1].raw), role)
            _require(documents[2].raw == expected)
            phase = "capture" if role == "capture" else "emission-prepare"
            value, _job, _artifact, pins, inputs, attempt = hosted._document(expected, phase)
            bearer_path = inputs["role_bearer"]
            expected_bearer = profile_value["owner"]["bearer_sha256"][role]
            _require(hosted.identity._hex(expected_bearer, 64))
            fresh = [bearer_path, *(inputs[name] for name, _ in ENVIRONMENT), attempt]
            paths = [item.path for item in documents] + [pin.path for pin in pins.values()] + fresh
            root_path = value["attestation_output_root"]
            if root_path is not None:
                paths.append(hosted._path(root_path))
            # Reject equal/ancestor/descendant aliases before any secret read.
            _require(all(not left.is_relative_to(right) and not right.is_relative_to(left)
                         for index, left in enumerate(paths) for right in paths[index + 1:]))
            parents = {}
            for path in fresh:
                _require(not os.path.lexists(path))
                chain = hosted.journal._parent(path)
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                cleanup.callback(os.close, fd)
                _require(_directory_stamp(os.fstat(fd)) == chain[-1])
                parents[path] = (chain, fd)
            slots = [(parents[path][0][-1][:2], path.name) for path in fresh]
            _require(len(set(slots)) == len(slots))
            root_binding = None
            if root_path is not None:
                root = hosted._path(root_path)
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                cleanup.callback(os.close, fd)
                root_binding = (root, fd, _directory_stamp(os.fstat(fd)))
            created = False
            def check():
                for item in held:
                    item.recheck()
                for path, (chain, fd) in parents.items():
                    _require(hosted.journal._parent(path) == chain
                             and _directory_stamp(os.fstat(fd)) == chain[-1])
                    if not (created and path == bearer_path):
                        _require(not os.path.lexists(path))
                if root_binding is not None:
                    root, fd, stamp = root_binding
                    _require(root.resolve(strict=True) == root
                             and _directory_stamp(root.lstat()) == stamp
                             and _directory_stamp(os.fstat(fd)) == stamp)
                    # A differently named bind of the action root must not
                    # conceal that an input/output parent is physically inside it.
                    chains = [item.parents for item in held] + [chain for chain, _ in parents.values()]
                    _require(all(stamp[:2] != ancestor[:2] for chain in chains for ancestor in chain))
            check()
            for pin in pins.values():
                hold(pin.path, 1024**2, expected=pin.sha256)
                _require(len({item.stamp[:2] for item in held}) == len(held))
                check()
            # Authenticate all public bytes/custody before the sole environment
            # lookup. The owner digest binds bytes exactly: never strip or mint.
            for item in held:
                _require(item.read() == item.raw)
                check()
            selected_environment = os.environ if environment is None else environment
            raw = _text(selected_environment.get("ANDROID_PREVIEW12_ROLE_BEARER"),
                        hosted.INPUT_LIMITS["role_bearer"])
            _require(hashlib.sha256(raw).hexdigest() == expected_bearer)
            check()
            materializer._write_exclusive(bearer_path, raw)
            bearer = hold(bearer_path, hosted.INPUT_LIMITS["role_bearer"], expected=expected_bearer)
            created = True
            _require(bearer.raw == raw and len({item.stamp[:2] for item in held}) == len(held))
            check()
            for item in held:
                _require(item.read() == item.raw)
                check()
            return BEARER_COMPLETE
    except BaseException:
        raise StagingError(ERROR) from None


def stage(*, role, profile, profile_sha256, context, context_sha256,
          deployment, deployment_sha256, environment=None):
    """Use existing custody/renderer contracts; return a constant diagnostic."""
    try:
        _require(role in ROLES and os.getuid() == os.geteuid() and os.getgid() == os.getegid())
        specs = ((profile, profile_sha256, materializer.MAX_PROFILE, True),
                 (context, context_sha256, materializer.MAX_CONTEXT, True),
                 (deployment, deployment_sha256, hosted.MAX_CONFIG, False))
        for path, digest, _limit, _public in specs:
            _require(isinstance(path, Path) and hosted._path(str(path)) == path
                     and hosted.identity._hex(digest, 64))
        with ExitStack() as cleanup:
            held = []
            def hold(path, limit, *, expected, public=False):
                item = hosted._Input(path, limit, expected=expected, public=public)
                cleanup.callback(item.close)
                held.append(item)
                return item
            documents = [hold(path, limit, expected=digest, public=public)
                         for path, digest, limit, public in specs]
            _require(len({item.stamp[:2] for item in documents}) == 3)
            profile_value = materializer._json(documents[0].raw)
            context_value = materializer._json(documents[1].raw)
            expected = materializer.render(profile_value, context_value, role)
            _require(documents[2].raw == expected)
            phase = "capture" if role == "capture" else "emission-prepare"
            value, _job, _artifact, pins, inputs, attempt = hosted._document(expected, phase)
            destinations = [inputs[name] for name, _ in ENVIRONMENT]
            bearer_path = inputs["role_bearer"]
            bearer_meta = hosted._metadata(bearer_path, hosted.INPUT_LIMITS["role_bearer"])
            ca_meta = {name: hosted._metadata(pin.path, 1024**2) for name, pin in pins.items()}
            public_ids = {item.stamp[:2] for item in documents} | {meta[0][:2] for meta in ca_meta.values()}
            _require(bearer_meta[0][:2] not in public_ids)
            all_paths = [item.path for item in documents] + [pin.path for pin in pins.values()] + [bearer_path]
            _require(len(set(destinations)) == 2 and not set(destinations) & set(all_paths))
            _require(not os.path.lexists(attempt))
            # All output parents are already private and independently supplied;
            # this helper creates no directories and never chmods existing ones.
            parents = {}
            for path in [*destinations, attempt]:
                _require(not os.path.lexists(path))
                chain = hosted.journal._parent(path)
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                cleanup.callback(os.close, fd)
                _require(_directory_stamp(os.fstat(fd)) == chain[-1])
                parents[path] = (chain, fd)
            slots = [(parents[path][0][-1][:2], path.name) for path in destinations]
            _require(len(set(slots)) == 2)
            output_root = value["attestation_output_root"]
            root_binding = None
            if output_root is not None:
                root = hosted._path(output_root)
                _require(all(not path.is_relative_to(root) for path in [*all_paths, *destinations]))
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                cleanup.callback(os.close, fd)
                root_binding = (root, fd, _directory_stamp(os.fstat(fd)))
            created = set()
            def check():
                for item in held:
                    item.recheck()
                for path, (chain, fd) in parents.items():
                    _require(hosted.journal._parent(path) == chain
                             and _directory_stamp(os.fstat(fd)) == chain[-1])
                    if path not in created:
                        _require(not os.path.lexists(path))
                if root_binding is not None:
                    root, fd, stamp = root_binding
                    _require(root.resolve(strict=True) == root
                             and _directory_stamp(root.lstat()) == stamp
                             and _directory_stamp(os.fstat(fd)) == stamp)
            check()
            # Alias rejection above precedes opening/reading credential bytes.
            for name, pin in pins.items():
                ca = hold(pin.path, 1024**2, expected=pin.sha256)
                _require((ca.stamp, ca.parents) == ca_meta[name])
                check()
            bearer = hold(bearer_path, hosted.INPUT_LIMITS["role_bearer"],
                          expected=profile_value["owner"]["bearer_sha256"][role])
            _require((bearer.stamp, bearer.parents) == bearer_meta)
            _text(bearer.raw.decode("ascii"), hosted.INPUT_LIMITS["role_bearer"])
            check()
            selected_environment = os.environ if environment is None else environment
            raw_inputs = {name: _text(selected_environment.get(variable), hosted.INPUT_LIMITS[name])
                          for name, variable in ENVIRONMENT}
            hosted.oidc._endpoint(raw_inputs["oidc_request_url"].decode("ascii"))
            _require(raw_inputs["oidc_request_credential"] != bearer.raw)
            check()
            for name, _ in ENVIRONMENT:
                path, raw = inputs[name], raw_inputs[name]
                check()
                materializer._write_exclusive(path, raw)
                item = hold(path, hosted.INPUT_LIMITS[name], expected=hashlib.sha256(raw).hexdigest())
                created.add(path)
                _require(item.raw == raw and item.stamp[:2] not in {other.stamp[:2] for other in held[:-1]})
                check()
            for item in held:
                _require(item.read() == item.raw)
                check()
            return COMPLETE
    except BaseException:
        raise StagingError(ERROR) from None


def stage_protected_request_inputs(*, profile, profile_sha256, context, context_sha256,
                                   deployment, deployment_sha256, environment=None):
    """Stage only the root protected consumer's two request files; never read keys."""
    try:
        protected = materializer.protected
        _require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0)
        specs = ((profile, profile_sha256, materializer.MAX_PROFILE, False),
                 (context, context_sha256, materializer.MAX_CONTEXT, False),
                 (deployment, deployment_sha256, protected.MAX_DEPLOYMENT, True))
        for path, digest, _limit, _private in specs:
            _require(isinstance(path, Path) and protected._path(str(path)) == path
                     and hosted.identity._hex(digest, 64))
        with ExitStack() as cleanup:
            held, metadata, parents = [], {}, {}
            def parent(path, private):
                protected.fleet._trusted_root(path.parent, "owner input")
                if private:
                    hosted.journal._parent(path)  # Existing private-parent contract.
                if path.parent not in parents:
                    chain = tuple((part, _directory_stamp(part.lstat()))
                                  for part in (*reversed(path.parent.parents), path.parent))
                    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                    cleanup.callback(os.close, fd)
                    _require(_directory_stamp(os.fstat(fd)) == chain[-1][1])
                    parents[path.parent] = (chain, fd)
            def observe(path, limit, private=True):
                stamp = protected._metadata(path, limit, private=private)
                parent(path, private)
                metadata[path] = (limit, private, stamp)
                return stamp
            def hold(path, limit, *, expected, private=True):
                item = protected._OwnedFile(path, limit, expected=expected, private=private)
                cleanup.callback(item.close)
                _require(item.stamp == metadata[path][2])
                held.append(item)
                return item
            for path, _digest, limit, private in specs:
                observe(path, limit, private)
            documents = [hold(path, limit, expected=digest, private=private)
                         for path, digest, limit, private in specs]
            profile_value = materializer._json(documents[0].raw)
            expected = materializer.render(profile_value, materializer._json(documents[1].raw), "protected")
            _require(documents[2].raw == expected)
            value, config, pins, secrets, transport, _job, _artifact, policy = protected._document(expected)
            destinations = [transport[name] for name, _ in ENVIRONMENT]
            bearers = {name: transport[name + "_bearer"] for name in ("intake", "binary")}
            validation = {name: Path(config["validation"][name]) for name in protected.VALIDATION_FILE_LIMITS}
            unused = [Path(value["operation_directory"]), Path(config["output"]),
                      Path(config["recovery"]) / config["attempt"], Path(config["socket"])]
            paths = [item.path for item in documents] + [pin.path for pin in pins.values()]
            paths += [*validation.values(), *secrets.values(), *transport.values(), *unused]
            _require(all(not left.is_relative_to(right) and not right.is_relative_to(left)
                         for index, left in enumerate(paths) for right in paths[index + 1:]))
            mounted = [Path(config[name]) for name in ("fleet_root", "handoff", "requests", "responses")]
            mounted += [Path(config["socket"]).parent, Path(value["persistent"]["parent"])]
            mounted += [Path(config["validation"][name]) for name in
                        ("workspace_root", "authority_root", "dotnet_root", "java_root", "android_sdk_root")]
            mounted += [Path(row.source) for row in policy.binds]
            private_paths = [*secrets.values(), *transport.values()]
            _require(all(not path.is_relative_to(root) and not root.is_relative_to(path)
                         for path in private_paths for root in mounted))
            # Metadata only for signing inputs. All aliases precede any transport read.
            for path in secrets.values():
                observe(path, 1400000)
            for name, path in bearers.items():
                observe(path, protected.TRANSPORT_LIMITS[name + "_bearer"])
            for name, pin in pins.items():
                observe(pin.path, protected.PIN_LIMITS[name], False)
            for name, path in validation.items():
                observe(path, protected.VALIDATION_FILE_LIMITS[name])
            _require(len({row[2][:2] for row in metadata.values()}) == len(metadata))
            for path in destinations:
                _require(not os.path.lexists(path))
                parent(path, True)
            slots = [(parents[path.parent][0][-1][1][:2], path.name) for path in destinations]
            _require(len(set(slots)) == 2)
            boundaries = {}
            for root in set(mounted):
                if not os.path.lexists(root):
                    boundaries[root] = None
                    continue
                _require(root.resolve(strict=True) == root)
                fd = os.open(root, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
                cleanup.callback(os.close, fd)
                boundaries[root] = (fd, _directory_stamp(os.fstat(fd)))
            created = set()
            def check():
                for path, (limit, private, stamp) in metadata.items():
                    _require(protected._metadata(path, limit, private=private) == stamp)
                for chain, fd in parents.values():
                    _require(all(_directory_stamp(part.lstat()) == stamp for part, stamp in chain)
                             and _directory_stamp(os.fstat(fd)) == chain[-1][1])
                for item in held:
                    item.recheck()
                _require(all(not os.path.lexists(path) for path in [*destinations, *unused] if path not in created))
                private_chains = [parents[path.parent][0] for path in private_paths]
                private_ids = {metadata[path][2][:2] for path in (*secrets.values(), *bearers.values())}
                for root, binding in boundaries.items():
                    if binding is None:
                        _require(not os.path.lexists(root))
                    else:
                        fd, stamp = binding
                        _require(root.resolve(strict=True) == root and _directory_stamp(root.lstat()) == stamp
                                 and _directory_stamp(os.fstat(fd)) == stamp and stamp[:2] not in private_ids)
                        _require(all(stamp[:2] != ancestor[:2] for chain in private_chains for _, ancestor in chain))
            check()
            for name, pin in pins.items():
                hold(pin.path, protected.PIN_LIMITS[name], expected=pin.sha256, private=False)
                check()
            # The admitted pin binds CA bytes; no TLS/client, token request, mount,
            # lock execution, validation runner or signing-key reader is constructed.
            for item in held:
                _require(item.read() == item.raw)
                check()
            texts = []
            for name, path in bearers.items():
                item = hold(path, protected.TRANSPORT_LIMITS[name + "_bearer"],
                            expected=profile_value["owner"]["bearer_sha256"][name])
                texts.append(_text(item.raw.decode("ascii"), protected.TRANSPORT_LIMITS[name + "_bearer"]))
                check()
            _require(len(set(texts)) == 2)
            selected_environment = os.environ if environment is None else environment
            raw_inputs = {}
            for name, variable in ENVIRONMENT:
                check()
                raw_inputs[name] = _text(selected_environment.get(variable), protected.TRANSPORT_LIMITS[name])
                check()
            protected.entrypoint._endpoint(raw_inputs["oidc_request_url"].decode("ascii"))
            _require(raw_inputs["oidc_request_credential"] not in texts)
            check()
            for name, _variable in ENVIRONMENT:
                path, raw = transport[name], raw_inputs[name]
                check()
                materializer._write_exclusive(path, raw)
                observe(path, protected.TRANSPORT_LIMITS[name])
                item = hold(path, protected.TRANSPORT_LIMITS[name], expected=hashlib.sha256(raw).hexdigest())
                created.add(path)
                _require(item.raw == raw and len({row[2][:2] for row in metadata.values()}) == len(metadata))
                check()
            for item in held:
                _require(item.read() == item.raw)
                check()
            return PROTECTED_COMPLETE
    except BaseException:
        raise StagingError(ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise StagingError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument("--deliver-role-bearer", action="store_true")
        modes.add_argument("--stage-protected-request-inputs", action="store_true")
        parser.add_argument("--role", choices=ROLES)
        for name in ("profile", "context", "deployment"):
            parser.add_argument("--" + name, required=True)
            parser.add_argument("--" + name + "-sha256", required=True)
        args = parser.parse_args(argv)
        _require((args.role is None) if args.stage_protected_request_inputs else (args.role in ROLES))
        operation = (stage_protected_request_inputs if args.stage_protected_request_inputs else
                     deliver_role_bearer if args.deliver_role_bearer else stage)
        role = {} if args.stage_protected_request_inputs else {"role": args.role}
        print(operation(**role, profile=hosted._path(args.profile), profile_sha256=args.profile_sha256,
                    context=hosted._path(args.context), context_sha256=args.context_sha256,
                    deployment=hosted._path(args.deployment), deployment_sha256=args.deployment_sha256), flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
