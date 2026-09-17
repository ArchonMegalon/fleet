"""Acquire the pinned public archives and build the local NFS fixture image.

This is preparation for the synthetic fixture only. It has no registry login,
credential input, package permission, image export, or release authority.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import selectors
import signal
import stat
import subprocess
import time
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

COUNT = 52
TOTAL = 13_482_674
BASE = ('mcr.microsoft.com/dotnet/runtime-deps:10.0.10-noble-amd64@'
        'sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e')
BASE_ID = 'sha256:9993b46fc643b59f3c9ea5859acfc1b8b6c3859cfe7b5586cfc24455a0ab6dd7'
TAG = 'chummer-android-recovery-fixture-public:recipe-v1'
CONTAINER_LABEL = 'chummer.nfs.public-preparation'
CONTAINER_LABEL_VALUE = 'bounded-install-v1'
CONTAINER_MEMORY = '1073741824'
CONTAINER_CPU = '0.5'
MAX_FILE = 3_000_000
MAX_OUTPUT = 1 << 20
ACQUISITION_SECONDS = 120
RECIPE = Path(__file__).resolve().parents[1] / 'tests/fixtures/android_nfs_recovery/public-image'
RECIPE_HASHES = {
    'install-bounded.sh': 'e4263e47b4e7a6f8b1654347a3bbfbdbb5471254d425d46c762531e3b6b2a3cb',
    'install-offline.sh': '3343cdb95a1fe7dc58583ebbd17e7932b7f92b3c2dfac915327fee77d40c95ac',
    'package-files.tsv': 'ffe8b0570226814bea62229669fcfaaab1b08a6c6d53bb74aedd706f0c230adc',
    'install-order.tsv': '2e7f3a8f400a08ee22cfe48a85c94071aeb899b07343e3962b29cad03321feef',
    'policy-rc.d': '4b0d6972477a55bb64330f66e336903c39f5c93b0186a3553736ef6b9567f4aa',
    'public-packages.tsv': '16dfc268213abfde56500e53b5b1772ad3bb85dcab73d38b33ba0d5c0ccb0a48',
}


def fail(message):
    raise ValueError(message)


def require(ok, message):
    if not ok:
        fail(message)


def verify_recipe(root):
    for name, digest in RECIPE_HASHES.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            fail('reviewed public recipe drift')


def read_manifest(path):
    rows = []
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    for number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
        if number == 1:
            if line != 'filename\tbytes\tsha256\turl': fail('manifest header')
            continue
        fields = line.split('\t')
        if len(fields) != 4: fail('manifest columns')
        name, size, sha, url = fields
        if (not name.endswith('.deb') or Path(name).name != name or '/' in name or '\\' in name
                or not size.isdigit() or not 0 < int(size) <= MAX_FILE
                or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha)):
            fail('manifest archive row')
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.netloc != 'archive.ubuntu.com'
                or parts.query or parts.fragment or not parts.path.startswith('/ubuntu/pool/')
                or unquote(parts.path.rsplit('/', 1)[-1]) != name):
            fail('manifest URL is not fixed public HTTPS archive')
        rows.append((name, int(size), sha, url))
    if len(rows) != COUNT or len({r[0] for r in rows}) != COUNT or sum(r[1] for r in rows) != TOTAL:
        fail('manifest count/bytes')
    pinned = []
    for number, line in enumerate((RECIPE / 'package-files.tsv').read_text().splitlines(), 1):
        if number == 1:
            if line != 'filename\tbytes\tsha256': fail('pinned package header')
            continue
        fields = line.split('\t')
        if len(fields) != 3: fail('pinned package columns')
        pinned.append((fields[0], int(fields[1]), fields[2]))
    if {(n, s, h) for n, s, h, _ in rows} != set(pinned): fail('manifest differs from pinned package set')
    return rows, digest


def bounded_command(args, timeout, cwd=None):
    if any(x in ('ghcr.io', 'login', 'push', 'save') for x in args):
        fail('private registry/export command rejected')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'DOCKER_CONFIG': str(Path(cwd or '.'))}
    process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chunks = bytearray(); deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() >= deadline: fail('preparation command deadline')
                for key, _ in selector.select(max(0, min(.1, deadline - time.monotonic()))):
                    block = os.read(key.fd, 65536)
                    if not block: selector.unregister(key.fileobj)
                    else:
                        room = MAX_OUTPUT - len(chunks)
                        chunks.extend(block[:room])
                        if len(block) > room: fail('preparation output bound')
        remaining = max(.01, deadline - time.monotonic())
        if process.wait(timeout=remaining) != 0: fail('preparation command failed')
    except Exception as error:
        # Only fixed public commands run here, with an empty credential environment.
        # JSON escaping prevents captured newlines becoming Actions commands.
        print(json.dumps({'stage': 'public-image-command', 'status': 'failed',
                          'errorType': type(error).__name__,
                          'output': bytes(chunks).decode('utf-8', errors='replace')}), flush=True)
        raise
    finally:
        if process.poll() is None: process.kill()
        process.wait(timeout=2)
        process.stdout.close()
    return bytes(chunks).decode('utf-8', errors='strict')


def acquire(rows, destination):
    # Socket timeouts alone do not bound a slow-trickle response read.
    def expired(_number, _frame):
        fail('archive acquisition deadline')
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        fail('existing acquisition alarm')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, ACQUISITION_SECONDS)
    try:
        _acquire(rows, destination)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _acquire(rows, destination):
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    class RejectRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, *unused):
            fail('archive redirect rejected')
    opener = build_opener(ProxyHandler({}), RejectRedirect)
    deadline = time.monotonic() + ACQUISITION_SECONDS
    received = 0
    for name, expected_size, expected_sha, url in rows:
        target = destination / name
        request = Request(url, headers={'Accept': 'application/vnd.debian.binary-package'})
        hasher = hashlib.sha256(); count = 0
        if time.monotonic() >= deadline: fail('archive acquisition deadline')
        with opener.open(request, timeout=20) as source, target.open('xb') as sink:
            while True:
                if time.monotonic() >= deadline: fail('archive acquisition deadline')
                block = source.read(64 * 1024)
                if not block: break
                count += len(block); received += len(block)
                if count > expected_size or received > TOTAL: fail('archive size bound')
                hasher.update(block); sink.write(block)
        if count != expected_size or hasher.hexdigest() != expected_sha:
            fail('archive size/hash mismatch')
        target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    if received != TOTAL: fail('archive total')


def make_context(context, rows, acquired):
    verify_recipe(RECIPE)
    context.mkdir(mode=0o755, parents=True, exist_ok=False)
    context.chmod(0o755)  # These public inputs must traverse under workflow umask 077.
    for name in RECIPE_HASHES:
        shutil.copyfile(RECIPE / name, context / name)
        (context / name).chmod(0o555 if name.endswith('.sh') else 0o444)
    verify_recipe(context)
    debs = context / 'debs'; debs.mkdir(mode=0o755)
    debs.chmod(0o755)
    for name, _size, _sha, _url in rows:
        shutil.copyfile(acquired / name, debs / name)
        (debs / name).chmod(0o444)


def _docker(config, *args, timeout=30):
    return bounded_command(['/usr/bin/docker', '--config', str(config), *args], timeout)


def _inspect_container(config, name):
    raw = _docker(config, 'container', 'inspect', '--format', '{{json .}}', name)
    values = json.loads(raw.strip())
    if not isinstance(values, dict):
        fail('container inspection shape')
    return values


def _inspect_image_json(config, image):
    raw = _docker(config, 'image', 'inspect', '--format', '{{json .}}', image)
    value = json.loads(raw.strip())
    if not isinstance(value, dict):
        fail('image inspection shape')
    return value


def _container_name():
    return 'nfs-public-install-%d-%d' % (os.getpid(), time.monotonic_ns())


def _container_id(value):
    value = value.strip()
    require(len(value) == 64 and all(c in '0123456789abcdef' for c in value),
            'container identity')
    return value


def _assert_container_config(value, name, context, container_id, base):
    config = value.get('Config') or {}
    host = value.get('HostConfig') or {}
    labels = config.get('Labels') or {}
    base_config = base.get('Config') or {}
    require(value.get('Id') == container_id and value.get('Name') == '/' + name
            and value.get('Image') == BASE_ID and config.get('Image') == BASE_ID
            and labels.get(CONTAINER_LABEL) == CONTAINER_LABEL_VALUE,
            'container ownership')
    require(host.get('NetworkMode') == 'none' and host.get('Memory') == int(CONTAINER_MEMORY)
            and host.get('MemorySwap') == int(CONTAINER_MEMORY)
            and host.get('NanoCpus') == 500000000 and host.get('Privileged') is False
            and not host.get('CapAdd') and not host.get('Devices'), 'container resource policy')
    mounts = value.get('Mounts') or []
    package_mounts = [mount for mount in mounts if mount.get('Destination') == '/packages']
    require(len(mounts) == 1 and len(package_mounts) == 1
            and package_mounts[0].get('Type') == 'bind'
            and package_mounts[0].get('Source') == str(context.resolve())
            and package_mounts[0].get('RW') is False, 'package mount policy')
    require(config.get('Entrypoint') == ['/bin/sh']
            and config.get('Cmd') == ['-c', 'exec /bin/sh /packages/install-bounded.sh --execute-bounded-install']
            and config.get('User') == '0:0' and config.get('Env') == base_config.get('Env')
            and config.get('WorkingDir') == base_config.get('WorkingDir')
            and config.get('Volumes') == base_config.get('Volumes'), 'container config policy')


def _check_install_output(raw):
    lines = raw.splitlines()
    expected = ('BOUNDED_INSTALL_CGROUP memory.max=1073741824 '
                'memory.swap.max=0 cpu.max=50000 100000')
    require(lines and lines[0] == expected, 'effective install cgroup')


def _stop_remove_owned(config, name, container_id):
    value = _inspect_container(config, container_id)
    labels = (value.get('Config') or {}).get('Labels') or {}
    require(value.get('Id') == container_id and value.get('Name') == '/' + name
            and labels.get(CONTAINER_LABEL) == CONTAINER_LABEL_VALUE, 'container ownership')
    if (value.get('State') or {}).get('Running'):
        try:
            _docker(config, 'stop', '--timeout', '5', container_id, timeout=15)
        finally:
            # A failed stop CLI must not leave the daemon-owned workload running.
            # Preserve stop failure even when force removal succeeds.
            _docker(config, 'rm', '--force', container_id, timeout=15)
        return
    # The immutable ID, name, and ownership label are rechecked above; never
    # remove by a prefix, label selector, or broad prune operation.
    _docker(config, 'rm', '--force', container_id, timeout=15)


def _prepare_container(config, context, base):
    name = _container_name()
    create = ['container', 'create', '--name', name, '--label',
              '%s=%s' % (CONTAINER_LABEL, CONTAINER_LABEL_VALUE), '--network', 'none',
              '--memory', CONTAINER_MEMORY, '--memory-swap', CONTAINER_MEMORY,
              '--cpus', CONTAINER_CPU, '--user', '0:0',
              '--mount', 'type=bind,src=%s,dst=/packages,readonly' % context.resolve(),
              '--entrypoint', '/bin/sh', BASE_ID, '-c',
              'exec /bin/sh /packages/install-bounded.sh --execute-bounded-install']
    container_id = None
    try:
        container_id = _container_id(_docker(config, *create, timeout=30))
        _assert_container_config(_inspect_container(config, container_id), name, context, container_id, base)
        output = _docker(config, 'start', '--attach', container_id, timeout=280)
        _check_install_output(output)
        value = _inspect_container(config, container_id)
        _assert_container_config(value, name, context, container_id, base)
        state = value.get('State') or {}
        require(state.get('Status') == 'exited' and state.get('ExitCode') == 0
                and state.get('OOMKilled') is False, 'bounded install result')
        return name, container_id
    except BaseException:
        if container_id is not None:
            _stop_remove_owned(config, name, container_id)
        raise


def _commit_image(config, name, base):
    committed = _docker(config, 'commit', '--change', 'ENTRYPOINT ["/usr/bin/python3","-I","-B"]',
            '--change', 'CMD []', '--change', 'USER 0', '--change', 'LABEL %s=%s' %
            (CONTAINER_LABEL, CONTAINER_LABEL_VALUE), name, TAG, timeout=60).strip()
    require(committed.startswith('sha256:') and len(committed) == 71
            and all(c in '0123456789abcdef' for c in committed[7:]), 'commit identity')
    value = _inspect_image_json(config, committed)
    image_config = value.get('Config') or {}
    base_config = base.get('Config') or {}
    base_layers = (base.get('RootFS') or {}).get('Layers') or []
    layers = (value.get('RootFS') or {}).get('Layers') or []
    require(image_config.get('Entrypoint') == ['/usr/bin/python3', '-I', '-B']
            and image_config.get('Cmd') in (None, []) and image_config.get('User') == '0'
            and image_config.get('Env') == base_config.get('Env')
            and image_config.get('WorkingDir') == base_config.get('WorkingDir')
            and image_config.get('Volumes') == base_config.get('Volumes')
            and (value.get('Architecture'), value.get('Os')) == ('amd64', 'linux')
            and layers[:len(base_layers)] == base_layers and len(layers) == len(base_layers) + 1
            and value.get('Id') == committed,
            'committed image configuration')
    return value


def _main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-receipt', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--disposable-vm', action='store_true')
    args = parser.parse_args(argv)
    if not (args.execute and args.disposable_vm): fail('explicit preparation admission required')
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted' or
            Path('/docker/chummercomplete').exists()):
        fail('refuse shared/local host')
    verify_recipe(RECIPE)
    rows, manifest_sha = read_manifest(RECIPE / 'public-packages.tsv')
    args.work_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    acquired = args.work_root / 'debs'
    acquire(rows, acquired)
    context = args.work_root / 'context'; make_context(context, rows, acquired)
    docker_config = args.work_root / 'docker-config'; docker_config.mkdir(mode=0o700)
    bounded_command(['/usr/bin/docker', '--config', str(docker_config), 'pull', BASE], 60)
    base = _inspect_image_json(docker_config, BASE)
    require(base.get('Id') == BASE_ID and (base.get('Architecture'), base.get('Os')) == ('amd64', 'linux'),
            'pulled public base identity differs')
    container_name, container_id = _prepare_container(docker_config, context, base)
    try:
        image = _commit_image(docker_config, container_id, base)
        image_id = image.get('Id')
        layers = (image.get('RootFS') or {}).get('Layers')
        require(isinstance(image_id, str) and image_id.startswith('sha256:')
                and isinstance(layers, list) and layers, 'committed image identity')
    finally:
        _stop_remove_owned(docker_config, container_name, container_id)
    verify_recipe(RECIPE)
    verify_recipe(context)
    recipe_files = {name: hashlib.sha256((RECIPE / name).read_bytes()).hexdigest()
                    for name in RECIPE_HASHES}
    fixture = RECIPE.parent
    source_files = {name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
                    for name in ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')}
    receipt = {'kind': 'android-nfs-disposable-public-image-observation', 'version': 1,
               'preparationMode': 'bounded_container_install_then_local_commit',
               'imageRef': TAG, 'imageId': image_id, 'rootfsDiffIds': layers,
               'baseImageRef': BASE, 'baseImageId': BASE_ID,
               'packageManifestSha256': manifest_sha, 'packageCount': COUNT,
               'packageBytes': TOTAL, 'recipeFiles': recipe_files,
               'fixtureSourceHashes': source_files, 'publicOnly': True,
               'releaseAuthority': False}
    args.output_receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with args.output_receipt.open('x') as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(',', ':')); stream.write('\n')
    args.output_receipt.chmod(0o600)


def main(argv=None):
    def terminated(_number, _frame):
        raise InterruptedError('preparation terminated')
    previous = signal.signal(signal.SIGTERM, terminated)
    try:
        return _main(argv)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    main()
