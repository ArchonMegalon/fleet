"""One disposable-VM NFS exercise using an explicitly prepared local image."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

PACKET = Path(__file__).resolve().parent
PREFIX = 'nfs-qualification-bkpapg6l'
LABEL = {'chummer.nfs-qualification': 'BKpapg6L'}
PROFILE = 'nfs-qualification-client-bkpapg6l'
SUBNET = '172.30.249.0/29'
MAX_OUTPUT = 128 * 1024
COMMAND_DEADLINE = None
IMAGE_REF = 'chummer-android-recovery-fixture-public:recipe-v1'
BASE_IMAGE_REF = ('mcr.microsoft.com/dotnet/runtime-deps:10.0.10-noble-amd64@'
                  'sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e')
BASE_IMAGE_ID = 'sha256:9993b46fc643b59f3c9ea5859acfc1b8b6c3859cfe7b5586cfc24455a0ab6dd7'
HOST_TOOLS = ('/usr/bin/docker', '/usr/bin/findmnt', '/usr/sbin/modprobe',
              '/usr/sbin/apparmor_parser', '/usr/bin/ip', '/usr/bin/python3')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def command(args, timeout=15, allowed=(0,), include_stderr=False):
    """Bound local command pipes/deadline; not a hard-NFS kernel kill promise."""
    deadline = time.monotonic() + timeout
    if COMMAND_DEADLINE is not None:
        deadline = min(deadline, COMMAND_DEADLINE)
    require(time.monotonic() < deadline, 'phase deadline; no further command started')
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'})
    streams = {process.stdout: bytearray(), process.stderr: bytearray()}
    try:
        with selectors.DefaultSelector() as select:
            for stream in streams:
                os.set_blocking(stream.fileno(), False)
                select.register(stream, selectors.EVENT_READ)
            while select.get_map():
                require(time.monotonic() < deadline, 'command deadline')
                for key, _events in select.select(0.1):
                    raw = os.read(key.fd, 8192)
                    if not raw:
                        select.unregister(key.fileobj)
                    else:
                        streams[key.fileobj].extend(raw)
                        require(sum(map(len, streams.values())) <= MAX_OUTPUT, 'command output bound')
        code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        require(code in allowed, 'command failed: ' + str(code))
        raw = bytes(streams[process.stdout])
        if include_stderr:
            raw += bytes(streams[process.stderr])
        return code, raw.decode('utf-8', errors='strict')
    finally:
        if process.poll() is None:
            process.kill()
        # A failure to reap is not converted into a successful cleanup claim.
        process.wait(timeout=2)
        for stream in streams:
            stream.close()


def json_values(raw):
    decoder, rows = json.JSONDecoder(), []
    while raw.strip():
        raw = raw.lstrip()
        value, offset = decoder.raw_decode(raw)
        rows.append(value)
        raw = raw[offset:]
    return rows


def validate_events(role, exit_code, events):
    require(type(exit_code) is int and type(events) is list, 'phase result types')
    mounted = {'observation': 'mounted', 'filesystem': 'nfs4',
               'version': '4.1', 'security': 'AUTH_SYS', 'hard': True}
    if role == 'client-a':
        expected = [mounted, {'observation': 'final-placeholder-fsync-and-rename-completed'}]
        require(exit_code == 47 and json.dumps(events, sort_keys=True) == json.dumps(expected, sort_keys=True),
                'write observations')
    else:
        expected = [mounted, {'observation': 'replacement-client-readback-completed',
                              'ambiguousRecord': 'retained-without-retry'}]
        require(role == 'client-b' and exit_code == 0
                and json.dumps(events, sort_keys=True) == json.dumps(expected, sort_keys=True), 'read observations')


def read_receipt(path):
    require(path.is_absolute() and path.resolve() == path and path.parent.resolve() == path.parent
            and path.is_file(), 'image observation path')
    parent = path.parent.stat()
    require(parent.st_uid == os.getuid() and not parent.st_mode & 0o077,
            'image observation parent custody')
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    # Descriptor checks, not a path-only preflight, bind the bytes actually read.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == os.getuid() and not before.st_mode & 0o077
                and before.st_size <= 16 * 1024, 'image observation custody')
        raw = stream.read(16 * 1024 + 1)
        after = os.fstat(stream.fileno())
        require(identity(before) == identity(after) == identity(path.lstat())
                and identity(parent) == identity(path.parent.stat()) and len(raw) <= 16 * 1024,
                'image observation changed during read')
    def no_duplicate(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate image observation key')
            value[key] = item
        return value
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicate)
    required = {'kind', 'version', 'imageRef', 'imageId', 'rootfsDiffIds', 'baseImageRef',
                'baseImageId', 'packageManifestSha256', 'packageCount', 'packageBytes',
                'recipeFiles', 'fixtureSourceHashes', 'publicOnly', 'releaseAuthority'}
    require(type(value) is dict and set(value) == required
            and value.get('kind') == 'android-nfs-disposable-public-image-observation'
            and type(value.get('version')) is int and value.get('version') == 1
            and value.get('imageRef') == IMAGE_REF
            and value.get('baseImageRef') == BASE_IMAGE_REF and value.get('baseImageId') == BASE_IMAGE_ID
            and value.get('publicOnly') is True and value.get('releaseAuthority') is False
            and type(value.get('packageCount')) is int and value.get('packageCount') == 52
            and type(value.get('packageBytes')) is int and value.get('packageBytes') == 13482674,
            'unapproved image observation')
    require(type(value.get('imageId')) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', value['imageId'])
            and type(value.get('rootfsDiffIds')) is list
            and 0 < len(value['rootfsDiffIds']) <= 128
            and all(type(row) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', row)
                                                for row in value['rootfsDiffIds']),
            'image observation identity')
    manifest = PACKET / 'public-image' / 'public-packages.tsv'
    require(manifest.is_file() and value.get('packageManifestSha256') ==
            hashlib.sha256(manifest.read_bytes()).hexdigest(), 'public manifest drift')
    recipe_names = ('Dockerfile', 'install-offline.sh', 'policy-rc.d', 'package-files.tsv',
                    'install-order.tsv', 'public-packages.tsv')
    require(type(value['recipeFiles']) is dict and set(value['recipeFiles']) == set(recipe_names)
            and all(type(value['recipeFiles'][name]) is str
                    and re.fullmatch(r'[0-9a-f]{64}', value['recipeFiles'][name])
                    and hashlib.sha256((PACKET / 'public-image' / name).read_bytes()).hexdigest()
                    == value['recipeFiles'][name] for name in recipe_names), 'recipe drift')
    source_names = ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')
    require(type(value['fixtureSourceHashes']) is dict
            and set(value['fixtureSourceHashes']) == set(source_names)
            and all(value['fixtureSourceHashes'][name] == hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
                    for name in source_names), 'fixture source drift')
    return value


def admit_vm(args, environment):
    require(args.execute and args.disposable_vm, 'explicit disposable VM admission required')
    # Negative accident guards, NOT cryptographic proof of hosted/disposable identity.
    require(environment.get('GITHUB_ACTIONS') == 'true'
            and environment.get('RUNNER_ENVIRONMENT') == 'github-hosted'
            and os.getuid() == 0 and not Path('/docker/chummercomplete').exists(),
            'refuse shared/local host')
    args.image_observation = read_receipt(args.image_receipt)
    require(args.output.is_absolute() and args.output.parent.resolve(strict=True) == args.output.parent
            and args.output.name.startswith('nfs-qualification-'), 'fresh canonical output path')


def host_inventory(docker, output, environment, image_ref):
    """Bounded public observations, NOT approval of the runner/tool closure."""
    result = {'scope': 'observed disposable-host profile; not approved environment or durability',
        'kernel': list(os.uname()), 'python': list(sys.version_info[:3]), 'tools': {}, 'errors': [],
        'runner': {name: environment.get(name, '') for name in
                   ('RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_ENVIRONMENT', 'ImageOS', 'ImageVersion')}}
    def observe(name, call):
        try:
            result[name] = call()
        except Exception as error:
            result['errors'].append(failure(name, error))
    def public_file(path, limit=16384):
        with Path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'inventory file bound')
        return raw.decode('utf-8')
    observe('osRelease', lambda: public_file('/etc/os-release'))
    observe('apparmorEnabled', lambda: public_file('/sys/module/apparmor/parameters/enabled').strip())
    for path in HOST_TOOLS:
        def tool(path=path):
            target = Path(path).resolve(strict=True)
            info = target.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
                    and not info.st_mode & 0o022 and info.st_size <= 128 * 1024**2, 'host tool custody')
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            flag = '-Version' if path == '/usr/bin/ip' else '--version'
            version = command([path, flag], timeout=5, include_stderr=True)[1]
            require(len(version) <= 4096, 'tool version bound')
            result['tools'][path] = {'resolved': str(target), 'sha256': digest, 'version': version}
        observe('tool:' + path, tool)
    observe('docker', lambda: json_values(docker('info', '--format',
        '{{json .SecurityOptions}} {{json .OSType}} {{json .Architecture}} {{json .CgroupVersion}}')))
    observe('image', lambda: json_values(docker('image', 'inspect', '--format',
        '{{json .Id}} {{json .RepoTags}} {{json .RepoDigests}} {{json .Architecture}} {{json .Os}} {{json .Config.Labels}} {{json .RootFS.Layers}}', image_ref)))
    observe('backing', lambda: command(['/usr/bin/findmnt', '-n', '-o', 'FSTYPE', '-T', str(output)])[1].strip())
    observe('stopTimeoutSupported', lambda: '--timeout' in docker('stop', '--help'))
    observe('nfsModuleDryRun', lambda: command(['/usr/sbin/modprobe', '--dry-run', 'nfsv4'])[0] == 0)
    observe('routes', lambda: json.loads(command(['/usr/bin/ip', '-j', '-4', 'route', 'show', 'table', 'all'])[1]))
    def networks():
        ids = docker('network', 'ls', '--format', '{{.ID}}').splitlines()
        require(0 < len(ids) <= 64 and all(re.fullmatch('[0-9a-f]{12,64}', item) for item in ids), 'network inventory')
        return json_values(docker('network', 'inspect', '--format', '{{json .IPAM.Config}}', *ids))
    observe('networkIpam', networks)
    return result


def validate_host(value, observation=None):
    """Necessary supported-profile checks, not an image/kernel approval receipt."""
    require(not value['errors'], 'host inventory incomplete; no fallback')
    require(set(value['tools']) == set(HOST_TOOLS)
            and all(re.fullmatch('[0-9a-f]{64}', row['sha256']) and 0 < len(row['version']) <= 4096
                    for row in value['tools'].values()), 'host tool inventory incomplete')
    os_release = dict(line.split('=', 1) for line in value['osRelease'].splitlines() if '=' in line)
    require(os_release.get('ID') == 'ubuntu' and os_release.get('VERSION_ID') == '"24.04"'
            and value['kernel'][0] == 'Linux' and value['kernel'][4] == 'x86_64'
            and value['python'][:2] == [3, 12], 'unsupported host OS/architecture/Python')
    require(value['runner']['RUNNER_OS'] == 'Linux' and value['runner']['RUNNER_ARCH'] == 'X64'
            and value['runner']['RUNNER_ENVIRONMENT'] == 'github-hosted'
            and value['runner']['ImageOS'] == 'ubuntu24'
            and re.fullmatch(r'[0-9]{8}\.[0-9]+\.[0-9]+', value['runner']['ImageVersion']), 'unsupported runner profile')
    require(value['apparmorEnabled'] == 'Y' and value['backing'] == 'ext4'
            and value['stopTimeoutSupported'] is True and value['nfsModuleDryRun'] is True,
            'required kernel/filesystem/tool feature unavailable')
    security, operating_system, architecture, cgroup = value['docker']
    require(type(security) is list and 'name=apparmor' in security
            and 'name=seccomp,profile=builtin' in security and 'name=rootless' not in security
            and operating_system == 'linux' and architecture in ('x86_64', 'amd64') and cgroup == '2',
            'unsupported Docker isolation profile')
    image_id, tags, digests, architecture, operating_system, labels, layers = value['image']
    require(type(observation) is dict, 'image observation required')
    require(observation is not None and image_id == observation['imageId']
            and tags == [IMAGE_REF] and digests == [] and layers == observation['rootfsDiffIds']
            and architecture == 'amd64' and operating_system == 'linux'
            and (labels is None or type(labels) is dict), 'prepared local image mismatch')
    target = ipaddress.ip_network(SUBNET)
    require(type(value['routes']) is list and type(value['networkIpam']) is list, 'network inventory shape')
    routes = [row['dst'] for row in value['routes'] if row.get('dst', 'default') != 'default']
    for rows in value['networkIpam']:
        require(rows is None or type(rows) is list, 'network IPAM shape')
        routes += [row['Subnet'] for row in (rows or []) if 'Subnet' in row]
    require(all(not target.overlaps(ipaddress.ip_network(route, strict=False))
                for route in routes if ':' not in route), 'fixture subnet collision')
    return labels


def create_args(image, network, role, stage, output):
    require(role in ('server', 'client-a', 'client-b'), 'exact role')
    name = PREFIX + '-' + role
    args = ['create', '--pull', 'never', '--name', name,
        '--label', 'chummer.nfs-qualification=BKpapg6L', '--network', network,
        '--ip', '172.30.249.2' if role == 'server' else '172.30.249.3',
        '--read-only', '--user', '0:0', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--pids-limit', '256' if role == 'server' else '64',
        '--cpus', '0.25' if role == 'server' else '0.5',
        '--memory', '384m' if role == 'server' else '256m',
        '--memory-swap', '384m' if role == 'server' else '256m',
        '--tmpfs', '/run:rw,nosuid,nodev,noexec,size=16777216,mode=0755',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16777216,mode=1777',
        '--volume', str(stage) + ':/packet:ro,rprivate',
        '--entrypoint', '/usr/bin/python3', '--workdir', '/']
    if role == 'server':
        args.extend(('--log-driver', 'local', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1'))
        for cap in ('DAC_READ_SEARCH', 'SETUID', 'SETGID', 'NET_BIND_SERVICE'):
            args.extend(('--cap-add', cap))
        args.extend(('--volume', str(output / 'export') + ':/export:rw,rprivate',
                     '--volume', str(output / 'state') + ':/var/lib/nfs:rw,rprivate'))
        script = ['/packet/server.py']
    else:
        args.extend(('--log-driver', 'none', '--cap-add', 'SYS_ADMIN', '--security-opt', 'apparmor=' + PROFILE,
                     '--attach', 'stdout', '--attach', 'stderr'))
        script = ['/packet/client.py', 'write' if role == 'client-a' else 'read']
    return [*args, image, '-I', '-B', *script]


def failure(stage, error):
    # Only caller-fixed stages and a fixed vocabulary: never exception text/argv.
    kind = 'deadline' if isinstance(error, TimeoutError) else (
        'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'rejected-or-command-failed')
    return {'stage': stage, 'kind': kind}


def record(output, name, value):
    with (output / name).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def exercise(args):
    admit_vm(args, os.environ)  # Refusal must not create evidence on a shared host.
    os.umask(0o077)
    args.output.mkdir(mode=0o700)  # Exclusive; never adopt an old packet or data.
    progress = {'stage': 'source-staging', 'hostChangesAttempted': False}
    try:
        run_fixture(args, progress)
    except BaseException as error:
        try:
            record(args.output, 'OBSERVATIONS.json', {'exerciseCompleted': False,
                'failure': failure(progress['stage'], error), 'observations': [],
                'unresolvedCleanup': ['host-state-unknown'] if progress['hostChangesAttempted'] else [],
                'scope': 'failed synthetic exercise; no deployment or cleanup authority'})
        except FileExistsError:
            pass  # Preserve the more complete inner cleanup record; never replace it.
        raise


def run_fixture(args, progress):
    global COMMAND_DEADLINE
    COMMAND_DEADLINE = time.monotonic() + 210  # Inventory consumes the original body budget too.
    for name in ('export', 'state', 'program', 'docker-client-empty'):
        (args.output / name).mkdir(mode=0o700)
    stage = args.output / 'program'
    for name in ('client.py', 'server.py', 'ganesha.conf'):
        raw = (PACKET / name).read_bytes()
        with (stage / name).open('xb') as stream:
            stream.write(raw)
        (stage / name).chmod(0o444)
    stage.chmod(0o555)
    docker_prefix = ['/usr/bin/docker', '--config', str(args.output / 'docker-client-empty'),
                     '--host', 'unix:///run/docker.sock']
    def docker(*tail, **kw):
        return command([*docker_prefix, *tail], **kw)[1]
    progress['stage'] = 'host-inventory'
    observation = args.image_observation
    inventory = host_inventory(docker, args.output, os.environ, observation['imageId'])
    record(args.output, 'HOST_INVENTORY.json', inventory)  # Retain unsupported profiles before rejection.
    progress['stage'] = 'host-profile-admission'
    image_id, image_labels = observation['imageId'], validate_host(inventory, observation)
    labels = (image_labels or {}) | LABEL
    progress['stage'] = 'existing-resource-admission'
    require(not docker('ps', '-aq', '--filter', 'name=^/' + PREFIX).strip(), 'existing container name')
    require(not docker('network', 'ls', '-q', '--filter', 'name=^' + PREFIX + '$').strip(), 'existing network name')
    profiles = Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines()
    require(not any(row.startswith(PROFILE + ' ') for row in profiles), 'existing AppArmor profile')
    record(args.output, 'INTENT.json', {'imageId': image_id, 'imageRef': observation['imageRef'],
        'sourceHashes': {name: hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
                         for name in ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')},
        'scope': 'synthetic controlled restart and same-VM replacement client; no authority'})
    containers, network, profile_loaded, observations, cleanup_errors = {}, None, False, [], []
    def identity(cid, role):
        rows = json_values(docker('inspect', '--format',
            '{{json .Id}} {{json .Image}} {{json .Name}} {{json .Config.Labels}} {{json .State.Status}}', cid))
        require(rows[:4] == [cid, image_id, '/' + PREFIX + '-' + role, labels]
                and len(rows) == 5 and rows[4] in ('created', 'running', 'exited'), 'foreign container')
        return rows[4]
    def remove(cid, role):
        if identity(cid, role) == 'running':
            docker('stop', '--timeout', '5', cid, timeout=8)
        require(identity(cid, role) in ('created', 'exited'), 'container still running')
        docker('rm', cid, timeout=5)
        require(not docker('ps', '-aq', '--filter', 'name=^/' + PREFIX + '-' + role + '$').strip(),
                'container name still occupied; do not remove replacement')
        del containers[cid]
    def create(role):
        cid = docker(*create_args(observation['imageId'], network, role, stage, args.output)).strip()
        require(re.fullmatch(r'[0-9a-f]{64}', cid), 'ambiguous create; VM disposal required')
        containers[cid] = role
        identity(cid, role)
        return cid
    def phase(role, exit_code):
        progress['stage'] = role + '-create'
        cid = create(role)
        # Docker start/attach CLI exit does not substitute for container State.ExitCode.
        progress['stage'] = role + '-start-attach'
        raw = docker('start', '--attach', cid, timeout=65, allowed=(0, 47))
        progress['stage'] = role + '-exit-and-events'
        require(identity(cid, role) == 'exited', 'client did not exit')
        actual = json.loads(docker('inspect', '--format', '{{json .State.ExitCode}}', cid))
        require(actual == exit_code, 'unexpected client exit')
        events = [json.loads(row) for row in raw.splitlines() if row.strip()]
        validate_events(role, actual, events)
        observations.append({'client': role, 'exitCode': actual, 'events': events})
        progress['stage'] = role + '-remove'
        remove(cid, role)
    def alarm(_sig, _frame):
        raise TimeoutError('cooperative driver deadline; VM disposal may remain necessary')
    for sig in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, alarm)
    require(time.monotonic() < COMMAND_DEADLINE, 'body deadline')
    signal.setitimer(signal.ITIMER_REAL, COMMAND_DEADLINE - time.monotonic())
    completed, failed = False, None
    try:
        # These host changes are authorized ONLY on the externally admitted disposable VM.
        progress.update(stage='nfs-module-load', hostChangesAttempted=True)
        command(['/usr/sbin/modprobe', 'nfsv4'])
        progress['stage'] = 'apparmor-profile-load'
        command(['/usr/sbin/apparmor_parser', '-a', str(PACKET / 'client.apparmor')])
        profile_loaded = True
        progress['stage'] = 'private-network-create'
        created_network = docker('network', 'create', '--internal', '--driver', 'bridge', '--subnet', SUBNET,
                                 '--label', 'chummer.nfs-qualification=BKpapg6L', PREFIX).strip()
        require(re.fullmatch(r'[0-9a-f]{64}', created_network), 'ambiguous network create; VM disposal required')
        network = created_network
        progress['stage'] = 'server-create'
        server = create('server')
        progress['stage'] = 'server-start'
        docker('start', server)
        # Readiness is exact TCP2049 in the admitted server; no host/public listener.
        progress['stage'] = 'server-readiness'
        ready = 'import socket; s=socket.create_connection(("127.0.0.1",2049),1); s.close()'
        for _ in range(15):
            try:
                docker('exec', server, '/usr/bin/python3', '-I', '-B', '-c', ready, timeout=2)
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError('server not ready')
        time.sleep(11)  # Configured ten-second initial grace, not an I/O deadline.
        phase('client-a', 47)
        progress['stage'] = 'server-controlled-restart'
        require(identity(server, 'server') == 'running', 'server drift')
        docker('stop', '--timeout', '5', server, timeout=8)
        require(identity(server, 'server') == 'exited', 'server stop incomplete')
        docker('start', server)
        time.sleep(11)
        phase('client-b', 0)
        completed = True
    except BaseException as error:
        failed = failure(progress['stage'], error)
        raise
    finally:
        progress['stage'] = 'cleanup'
        COMMAND_DEADLINE = time.monotonic() + 30
        signal.setitimer(signal.ITIMER_REAL, 30)
        try:
            for cid, role in list(containers.items()):
                if role == 'server':
                    try:
                        state = identity(cid, role)
                        exit_code = json.loads(docker('inspect', '--format', '{{json .State.ExitCode}}', cid))
                        log = docker('logs', '--timestamps', '--tail', '1000', cid,
                                     timeout=5, include_stderr=True)
                        record(args.output, 'SERVER_LOG.json', {'containerId': cid, 'state': state,
                               'exitCode': exit_code, 'log': log})
                    except BaseException:
                        cleanup_errors.append('server-diagnostic-unavailable:' + cid)
            for cid, role in list(containers.items()):
                try:
                    remove(cid, role)
                except BaseException:
                    cleanup_errors.append('container:' + cid)
            if network:
                try:
                    values = json_values(docker('network', 'inspect', '--format',
                        '{{json .Id}} {{json .Name}} {{json .Labels}} {{json .Internal}} {{json .Containers}}', network))
                    require(values == [network, PREFIX, LABEL, True, {}], 'foreign/occupied network')
                    docker('network', 'rm', network, timeout=5)
                    require(not docker('network', 'ls', '-q', '--filter', 'name=^' + PREFIX + '$').strip(),
                            'network name still occupied; do not remove replacement')
                except BaseException:
                    cleanup_errors.append('network:' + network)
            if profile_loaded and not containers:
                try:
                    command(['/usr/sbin/apparmor_parser', '-R', str(PACKET / 'client.apparmor')], timeout=5)
                except BaseException:
                    cleanup_errors.append('AppArmor-profile')
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            record(args.output, 'OBSERVATIONS.json', {'exerciseCompleted': completed,
                'failure': failed or ({'stage': 'cleanup', 'kind': 'unresolved'} if cleanup_errors else None),
                'observations': observations, 'unresolvedCleanup': cleanup_errors,
                'scope': 'same-VM controlled restart/remount only; no power-loss or deployment proof'})
    require(completed and not cleanup_errors, 'unfinished; retain records and dispose whole VM')
    print('Controlled NFS exercise complete; dispose VM after retaining public observations')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--disposable-vm', action='store_true')
    parser.add_argument('--image-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    exercise(parser.parse_args())


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        print('NFS exercise incomplete; whole disposable VM disposal may be required', file=sys.stderr)
        raise SystemExit(1) from None
