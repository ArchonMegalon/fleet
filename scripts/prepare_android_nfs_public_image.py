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
MAX_FILE = 3_000_000
MAX_OUTPUT = 1 << 20
ACQUISITION_SECONDS = 120
RECIPE = Path(__file__).resolve().parents[1] / 'tests/fixtures/android_nfs_recovery/public-image'
RECIPE_HASHES = {
    'Dockerfile': '620a73ecdb7e9b6c4757e9f6d1fcc03792f911ab18974d1e3e674240f0e9af79',
    'install-offline.sh': '3343cdb95a1fe7dc58583ebbd17e7932b7f92b3c2dfac915327fee77d40c95ac',
    'package-files.tsv': 'ffe8b0570226814bea62229669fcfaaab1b08a6c6d53bb74aedd706f0c230adc',
    'install-order.tsv': '2e7f3a8f400a08ee22cfe48a85c94071aeb899b07343e3962b29cad03321feef',
    'policy-rc.d': '4b0d6972477a55bb64330f66e336903c39f5c93b0186a3553736ef6b9567f4aa',
    'public-packages.tsv': '16dfc268213abfde56500e53b5b1772ad3bb85dcab73d38b33ba0d5c0ccb0a48',
}


def fail(message):
    raise ValueError(message)


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
    context.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in RECIPE_HASHES:
        shutil.copyfile(RECIPE / name, context / name)
    verify_recipe(context)
    debs = context / 'debs'; debs.mkdir(mode=0o700)
    for name, _size, _sha, _url in rows:
        shutil.copyfile(acquired / name, debs / name)


def inspect_image(config, image):
    raw = bounded_command(['/usr/bin/docker', '--config', str(config), 'image', 'inspect',
                           '--format', '{{json .Id}} {{json .RootFS.Layers}} {{json .Architecture}} {{json .Os}}', image], 30)
    # Docker's format emits adjacent JSON values, not an array.
    decoder = json.JSONDecoder(); values = []
    text = raw.strip()
    while text:
        value, end = decoder.raw_decode(text.lstrip()); values.append(value); text = text.lstrip()[end:]
    if len(values) != 4 or not isinstance(values[0], str) or not isinstance(values[1], list):
        fail('image inspection shape')
    if values[2] != 'amd64' or values[3] != 'linux' or not values[0].startswith('sha256:'):
        fail('image platform')
    return values[0], values[1]


def main(argv=None):
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
    base = bounded_command(['/usr/bin/docker', '--config', str(docker_config), 'image', 'inspect',
                            '--format', '{{json .Id}}', BASE], 30).strip()
    if json.loads(base) != BASE_ID: fail('pulled public base identity differs')
    iid = args.work_root / 'image.iid'
    bounded_command(['/usr/bin/docker', '--config', str(docker_config), 'buildx', 'build',
                     '--builder', 'default', '--platform', 'linux/amd64', '--pull=false',
                     '--network=none', '--no-cache', '--resource', 'memory=1g',
                     '--resource', 'memory-swap=1g', '--resource', 'cpu-period=100000',
                     '--resource', 'cpu-quota=50000', '--progress=plain', '--provenance=false',
                     '--load',
                     '--sbom=false', '--iidfile', str(iid), '--tag', TAG,
                     str(context)], 280, cwd=str(args.work_root))
    image_id, layers = inspect_image(docker_config, iid.read_text().strip())
    verify_recipe(RECIPE)
    verify_recipe(context)
    recipe_files = {name: hashlib.sha256((RECIPE / name).read_bytes()).hexdigest()
                    for name in ('Dockerfile', 'install-offline.sh', 'policy-rc.d',
                                 'package-files.tsv', 'install-order.tsv', 'public-packages.tsv')}
    fixture = RECIPE.parent
    source_files = {name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
                    for name in ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')}
    receipt = {'kind': 'android-nfs-disposable-public-image-observation', 'version': 1,
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


if __name__ == '__main__':
    main()
