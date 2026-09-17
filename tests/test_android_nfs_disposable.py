"""Local synthetic/source checks only; never starts Docker or mounts NFS."""
import importlib.util
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PACKET = Path(__file__).resolve().parent / 'fixtures' / 'android_nfs_recovery'


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_' + name, PACKET / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver, client = load('run'), load('client')
SYNTHETIC_IMAGE_ID = 'sha256:' + '0' * 64
prep_spec = importlib.util.spec_from_file_location('public_prep', PACKET.parents[2] / 'scripts/prepare_android_nfs_public_image.py')
prep = importlib.util.module_from_spec(prep_spec); prep_spec.loader.exec_module(prep)


class LostAcknowledgement(BaseException):
    pass


class PacketTests(unittest.TestCase):
    def receipt_model(self):
        return {'kind': 'android-nfs-disposable-public-image-observation', 'version': 1,
            'preparationMode': 'bounded_container_install_then_local_commit',
            'imageRef': driver.IMAGE_REF, 'imageId': 'sha256:' + 'a' * 64,
            'rootfsDiffIds': ['sha256:' + 'b' * 64], 'baseImageRef': driver.BASE_IMAGE_REF,
            'baseImageId': driver.BASE_IMAGE_ID, 'packageManifestSha256':
                hashlib.sha256((PACKET / 'public-image/public-packages.tsv').read_bytes()).hexdigest(),
            'packageCount': 52, 'packageBytes': 13482674,
            'recipeFiles': {name: hashlib.sha256((PACKET / 'public-image' / name).read_bytes()).hexdigest()
                           for name in prep.RECIPE_HASHES},
            'fixtureSourceHashes': {name: hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
                                   for name in ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')},
            'publicOnly': True, 'releaseAuthority': False}

    def test_observation_requires_exact_types_and_source_identity(self):
        with tempfile.TemporaryDirectory(prefix='public-receipt-unit-') as folder:
            receipt = Path(folder) / 'image.json'
            value = self.receipt_model()
            receipt.write_text(json.dumps(value)); receipt.chmod(0o600)
            self.assertEqual(driver.read_receipt(receipt), value)
            mutations = [('version', True), ('packageCount', 52.0), ('packageBytes', 13482674.0),
                         ('imageId', 'mutable:tag'), ('rootfsDiffIds', [False]),
                         ('rootfsDiffIds', []), ('recipeFiles', []), ('fixtureSourceHashes', {}),
                         ('packageManifestSha256', '0' * 64), ('publicOnly', False),
                         ('releaseAuthority', True)]
            for key, replacement in mutations:
                with self.subTest(key=key, replacement=replacement):
                    mutated = value | {key: replacement}
                    receipt.write_text(json.dumps(mutated))
                    with self.assertRaises(RuntimeError): driver.read_receipt(receipt)
            receipt.write_text(json.dumps(value)[:-1] + ',"version":1}')
            with self.assertRaisesRegex(RuntimeError, 'duplicate'): driver.read_receipt(receipt)
            receipt.write_text(' ' * (16 * 1024 + 1))
            with self.assertRaisesRegex(RuntimeError, 'custody'): driver.read_receipt(receipt)

    def test_observation_rejects_shared_readable_linked_or_replaced_files(self):
        with tempfile.TemporaryDirectory(prefix='public-receipt-unit-') as folder:
            root = Path(folder); receipt = root / 'image.json'
            receipt.write_text(json.dumps(self.receipt_model())); receipt.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'custody'): driver.read_receipt(receipt)
            receipt.chmod(0o600)
            link = root / 'symlink.json'; link.symlink_to(receipt)
            with self.assertRaisesRegex(RuntimeError, 'path'): driver.read_receipt(link)
            linked = root / 'hardlink.json'; os.link(receipt, linked)
            with self.assertRaisesRegex(RuntimeError, 'custody'): driver.read_receipt(receipt)
            linked.unlink()
            root.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, 'parent custody'): driver.read_receipt(receipt)
            root.chmod(0o700)
            actual = os.fstat
            calls = 0
            def changed(fd):
                nonlocal calls
                calls += 1
                result = actual(fd)
                if calls == 1: return result
                return SimpleNamespace(**{name: getattr(result, name) for name in
                    ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size', 'st_mtime_ns')},
                    st_ctime_ns=result.st_ctime_ns + 1)
            with patch.object(driver.os, 'fstat', side_effect=changed):
                with self.assertRaisesRegex(RuntimeError, 'changed during read'): driver.read_receipt(receipt)

    def test_reviewed_recipe_is_checked_before_context_and_acquisition(self):
        prep.verify_recipe(prep.RECIPE)
        with tempfile.TemporaryDirectory(prefix='public-recipe-unit-') as folder:
            with self.assertRaisesRegex(ValueError, 'recipe drift'): prep.verify_recipe(Path(folder))
        # Model each refusal explicitly: tests also run on an admitted hosted VM.
        cases = [('false', 'github-hosted', False),
                 ('true', 'self-hosted', False), ('true', 'github-hosted', True)]
        for actions, runner, shared in cases:
            with self.subTest(actions=actions, runner=runner, shared=shared), \
                    patch.dict(os.environ, {'GITHUB_ACTIONS': actions, 'RUNNER_ENVIRONMENT': runner}), \
                    patch.object(Path, 'exists', return_value=shared), \
                    patch.object(Path, 'mkdir', side_effect=AssertionError('no directory creation')) as mkdir, \
                    patch.object(prep, 'acquire', side_effect=AssertionError('no network')) as acquire:
                with self.assertRaisesRegex(ValueError, 'refuse shared/local host'):
                    prep.main(['--execute', '--disposable-vm', '--output-receipt', '/never/image.json',
                               '--work-root', '/never/work'])
                acquire.assert_not_called()
                mkdir.assert_not_called()

    def test_hosted_recipe_drift_rejects_before_directory_or_acquisition(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted'}), \
                patch.object(Path, 'exists', return_value=False), \
                patch.object(prep, 'verify_recipe', side_effect=ValueError('reviewed public recipe drift')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('no directory creation')) as mkdir, \
                patch.object(prep, 'acquire', side_effect=AssertionError('no network')) as acquire:
            with self.assertRaisesRegex(ValueError, 'recipe drift'):
                prep.main(['--execute', '--disposable-vm', '--output-receipt', '/never/image.json',
                           '--work-root', '/never/work'])
            mkdir.assert_not_called()
            acquire.assert_not_called()

    def test_archive_size_hash_redirect_and_proxy_controls(self):
        data = b'deb!'
        good = ('model.deb', len(data), hashlib.sha256(data).hexdigest(),
                'https://archive.ubuntu.com/ubuntu/pool/model.deb')
        for content, expected_hash in ((data, good[2]), (data + b'x', good[2]), (data, '0' * 64)):
            def opener_factory(proxy, redirect):
                self.assertEqual(proxy.proxies, {})
                with self.assertRaisesRegex(ValueError, 'redirect'):
                    redirect().redirect_request(None)
                return SimpleNamespace(open=lambda *a, **k: io.BytesIO(content))
            with self.subTest(content=content, expected_hash=expected_hash), \
                    tempfile.TemporaryDirectory(prefix='public-fetch-model-') as folder, \
                    patch.object(prep, 'build_opener', side_effect=opener_factory), \
                    patch.object(prep, 'TOTAL', len(data)):
                row = (good[0], good[1], expected_hash, good[3])
                if content == data and expected_hash == good[2]:
                    prep.acquire([row], Path(folder) / 'debs')
                    self.assertEqual((Path(folder) / 'debs/model.deb').read_bytes(), data)
                else:
                    with self.assertRaises(ValueError): prep.acquire([row], Path(folder) / 'debs')

    def test_acquisition_alarm_interrupts_blocked_read_and_is_restored(self):
        class SlowResponse(io.BytesIO):
            def read(self, *args):
                time.sleep(1)
                return b''
        previous = prep.signal.getsignal(prep.signal.SIGALRM)
        with tempfile.TemporaryDirectory(prefix='public-fetch-model-') as folder, \
                patch.object(prep, 'ACQUISITION_SECONDS', .02), \
                patch.object(prep, 'build_opener', return_value=SimpleNamespace(open=lambda *a, **k: SlowResponse())):
            with self.assertRaisesRegex(ValueError, 'acquisition deadline'):
                prep.acquire([('model.deb', 1, '0' * 64, 'https://archive.ubuntu.com/ubuntu/pool/model.deb')],
                             Path(folder) / 'debs')
        self.assertEqual(prep.signal.getitimer(prep.signal.ITIMER_REAL), (0.0, 0.0))
        self.assertEqual(prep.signal.getsignal(prep.signal.SIGALRM), previous)

    def test_failed_public_command_keeps_bounded_json_diagnostic(self):
        # A tiny local Python child only: no Docker, network, SDK or mounts.
        output = io.StringIO()
        with patch.object(prep, 'MAX_OUTPUT', 32), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, 'output bound'):
                prep.bounded_command(['/usr/bin/python3', '-I', '-B', '-c', 'print("x" * 256)'], 2)
        record = json.loads(output.getvalue())
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(len(record['output']), 32)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                prep.bounded_command(['/usr/bin/python3', '-I', '-B', '-c', 'import time; time.sleep(2)'], .02)

    def test_public_manifest_is_exact_pinned_https_set_and_prep_has_no_registry_path(self):
        rows, digest = prep.read_manifest(PACKET / 'public-image/public-packages.tsv')
        self.assertEqual((len(rows), sum(row[1] for row in rows)), (52, 13482674))
        self.assertTrue(all(row[3].startswith('https://archive.ubuntu.com/ubuntu/pool/') for row in rows))
        source = (PACKET.parents[2] / 'scripts/prepare_android_nfs_public_image.py').read_text()
        self.assertNotIn('login ghcr.io', source)
        self.assertNotIn("login ghcr", source)
        self.assertIn("'container', 'create'", source)
        self.assertIn("'--memory', CONTAINER_MEMORY", source)
        self.assertNotIn("'buildx', 'build'", source)
        self.assertNotIn("'--resource'", source)

    def test_public_manifest_drift_and_receipt_extra_keys_reject(self):
        with tempfile.TemporaryDirectory(prefix='public-recipe-unit-') as folder:
            bad = Path(folder) / 'manifest.tsv'
            bad.write_text((PACKET / 'public-image/public-packages.tsv').read_text().replace('https://', 'http://', 1))
            with self.assertRaises(ValueError): prep.read_manifest(bad)
            receipt = Path(folder) / 'receipt.json'
            value = {'kind': 'android-nfs-disposable-public-image-observation', 'version': 1,
                'preparationMode': 'bounded_container_install_then_local_commit',
                'imageRef': driver.IMAGE_REF, 'imageId': 'sha256:' + 'a' * 64,
                'rootfsDiffIds': ['sha256:' + 'b' * 64], 'baseImageRef': driver.BASE_IMAGE_REF,
                'baseImageId': driver.BASE_IMAGE_ID, 'packageManifestSha256':
                    __import__('hashlib').sha256((PACKET / 'public-image/public-packages.tsv').read_bytes()).hexdigest(),
                'packageCount': 52, 'packageBytes': 13482674,
                'recipeFiles': {n: __import__('hashlib').sha256((PACKET / 'public-image' / n).read_bytes()).hexdigest()
                               for n in ('install-bounded.sh', 'install-offline.sh', 'policy-rc.d', 'package-files.tsv', 'install-order.tsv', 'public-packages.tsv')},
                'fixtureSourceHashes': {n: __import__('hashlib').sha256((PACKET / n).read_bytes()).hexdigest()
                                        for n in ('run.py', 'client.py', 'server.py', 'ganesha.conf', 'client.apparmor')},
                'publicOnly': True, 'releaseAuthority': False, 'extra': 'reject'}
            receipt.write_text(json.dumps(value)); receipt.chmod(0o600)
            with self.assertRaises(RuntimeError): driver.read_receipt(receipt)

    def _base_image(self):
        return {'Id': prep.BASE_ID, 'Architecture': 'amd64', 'Os': 'linux',
                'Config': {'Env': ['BASE=public'], 'WorkingDir': '/work', 'Volumes': None},
                'RootFS': {'Layers': ['sha256:' + '1' * 64]}}

    def _install_container(self, context, *, running=True):
        base = self._base_image()
        name = 'nfs-public-install-1-2'; cid = 'a' * 64
        return base, name, cid, {
            'Id': cid, 'Name': '/' + name, 'Image': prep.BASE_ID,
            'Config': {'Image': prep.BASE_ID, 'Labels': {prep.CONTAINER_LABEL: prep.CONTAINER_LABEL_VALUE},
                       'Entrypoint': ['/bin/sh'],
                       'Cmd': ['-c', 'exec /bin/sh /packages/install-bounded.sh --execute-bounded-install'],
                       'User': '0:0', 'Env': ['BASE=public'], 'WorkingDir': '/work', 'Volumes': None},
            'HostConfig': {'NetworkMode': 'none', 'Memory': 1073741824, 'MemorySwap': 1073741824,
                           'NanoCpus': 500000000, 'Privileged': False, 'CapAdd': None, 'Devices': None},
            'Mounts': [{'Type': 'bind', 'Source': str(context.resolve()), 'Destination': '/packages', 'RW': False}],
            'State': {'Running': running, 'Status': 'running' if running else 'exited',
                      'ExitCode': 0, 'OOMKilled': False}}

    def test_bounded_install_script_requires_zero_swap_and_pinned_policy(self):
        source = (PACKET / 'public-image/install-bounded.sh').read_text()
        self.assertIn('test "$memory_swap_max" = 0', source)
        self.assertIn('4b0d6972477a55bb64330f66e336903c39f5c93b0186a3553736ef6b9567f4aa', source)
        with self.assertRaisesRegex(ValueError, 'effective install cgroup'):
            prep._check_install_output('BOUNDED_INSTALL_CGROUP memory.max=1073741824 memory.swap.max=1073741824 cpu.max=50000 100000\n')

    def test_bounded_container_command_order_and_exact_limits_are_mocked_only(self):
        with tempfile.TemporaryDirectory(prefix='bounded-container-unit-') as folder:
            context = Path(folder) / 'context'; context.mkdir()
            base, name, cid, initial = self._install_container(context)
            final = dict(initial); final['State'] = {'Running': False, 'Status': 'exited',
                                                     'ExitCode': 0, 'OOMKilled': False}
            commands = []
            marker = 'BOUNDED_INSTALL_CGROUP memory.max=1073741824 memory.swap.max=0 cpu.max=50000 100000\n'
            def docker(_config, *args, **_kwargs):
                commands.append(args)
                if args[:2] == ('container', 'create'):
                    return cid + '\n'
                if args[:2] == ('start', '--attach'):
                    return marker
                return ''
            with patch.object(prep, '_container_name', return_value=name), \
                    patch.object(prep, '_docker', side_effect=docker), \
                    patch.object(prep, '_inspect_container', side_effect=[initial, final]):
                self.assertEqual(prep._prepare_container(Path(folder) / 'docker-config', context, base), (name, cid))
            self.assertEqual(commands[1][:2], ('start', '--attach'))
            create = commands[0]
            self.assertIn('--network', create); self.assertEqual(create[create.index('--network') + 1], 'none')
            self.assertEqual(create[create.index('--memory') + 1], '1073741824')
            self.assertEqual(create[create.index('--memory-swap') + 1], '1073741824')
            self.assertEqual(create[create.index('--cpus') + 1], '0.5')
            self.assertEqual(create[create.index('--entrypoint') + 2], prep.BASE_ID)
            self.assertNotIn(prep.BASE, create)
            self.assertNotIn('--privileged', create); self.assertNotIn('--cap-add', create)
            self.assertNotIn('exec', create[create.index('--entrypoint'):])

    def test_public_context_traverses_under_private_workflow_umask(self):
        with tempfile.TemporaryDirectory(prefix='bounded-context-unit-') as folder:
            root = Path(folder); root.chmod(0o700)
            acquired = root / 'archives'; acquired.mkdir()
            archive = acquired / 'synthetic.deb'; archive.write_bytes(b'public test bytes')
            context = root / 'context'
            previous = os.umask(0o077)
            try:
                prep.make_context(context, [('synthetic.deb', 17, '', '')], acquired)
            finally:
                os.umask(previous)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            for directory in (context, context / 'debs'):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((context / 'debs/synthetic.deb').stat().st_mode), 0o444)

    def test_container_actual_image_mismatch_rejects(self):
        context = Path('/tmp/public-context')
        base, name, cid, value = self._install_container(context)
        value['Image'] = 'sha256:' + 'f' * 64
        with self.assertRaisesRegex(ValueError, 'container ownership'):
            prep._assert_container_config(value, name, context, cid, base)

    def test_cleanup_rechecks_owned_full_id_and_never_removes_by_name(self):
        with tempfile.TemporaryDirectory(prefix='bounded-cleanup-unit-') as folder:
            context = Path(folder) / 'context'; context.mkdir()
            base, name, cid, value = self._install_container(context)
            calls = []
            with patch.object(prep, '_inspect_container', return_value=value), \
                    patch.object(prep, '_docker', side_effect=lambda _c, *args, **kw: calls.append(args) or ''):
                prep._stop_remove_owned(Path(folder) / 'docker-config', name, cid)
            self.assertEqual(calls, [('stop', '--timeout', '5', cid), ('rm', '--force', cid)])

    def test_installer_timeout_stops_and_removes_exact_container(self):
        context = Path('/tmp/public-context')
        base, name, cid, value = self._install_container(context)
        calls = []
        def docker(_config, *args, **_kwargs):
            calls.append(args)
            if args[:2] == ('container', 'create'):
                return cid + '\n'
            if args[:2] == ('start', '--attach'):
                raise TimeoutError('modeled installer deadline')
            return ''
        with patch.object(prep, '_container_name', return_value=name), \
                patch.object(prep, '_inspect_container', return_value=value), \
                patch.object(prep, '_docker', side_effect=docker):
            with self.assertRaisesRegex(TimeoutError, 'modeled installer deadline'):
                prep._prepare_container(Path('/tmp/docker-config'), context, base)
        self.assertEqual(calls[-2:], [('stop', '--timeout', '5', cid), ('rm', '--force', cid)])

    def test_stop_error_still_force_removes_and_preserves_failure(self):
        context = Path('/tmp/public-context')
        base, name, cid, value = self._install_container(context)
        calls = []
        def docker(_config, *args, **_kwargs):
            calls.append(args)
            if args[0] == 'stop':
                raise TimeoutError('modeled stop deadline')
            return ''
        with patch.object(prep, '_inspect_container', return_value=value), \
                patch.object(prep, '_docker', side_effect=docker):
            with self.assertRaisesRegex(TimeoutError, 'modeled stop deadline'):
                prep._stop_remove_owned(Path('/tmp/docker-config'), name, cid)
        self.assertEqual(calls, [('stop', '--timeout', '5', cid), ('rm', '--force', cid)])

    def test_cleanup_rejects_rebound_identity_before_removal(self):
        context = Path('/tmp/public-context')
        base, name, cid, value = self._install_container(context)
        value['Id'] = 'b' * 64
        with patch.object(prep, '_inspect_container', return_value=value), \
                patch.object(prep, '_docker') as docker:
            with self.assertRaisesRegex(ValueError, 'container ownership'):
                prep._stop_remove_owned(Path('/tmp/docker-config'), name, cid)
            docker.assert_not_called()

    def test_observation_is_written_only_after_cleanup_success(self):
        # Entire daemon/acquisition boundary is modeled; no Docker/network runs.
        original_exists = Path.exists
        def modeled_exists(path):
            return False if str(path) == '/docker/chummercomplete' else original_exists(path)
        for cleanup_fails in (False, True):
            with self.subTest(cleanup_fails=cleanup_fails), \
                    tempfile.TemporaryDirectory(prefix='bounded-main-unit-') as folder, \
                    contextlib.ExitStack() as stack:
                receipt = Path(folder) / 'receipt.json'
                base = self._base_image()
                result = {'Id': 'sha256:' + 'c' * 64, 'RootFS': {'Layers': ['sha256:' + 'd' * 64]}}
                stack.enter_context(patch.object(Path, 'exists', modeled_exists))
                stack.enter_context(patch.dict(os.environ, {'GITHUB_ACTIONS': 'true',
                    'RUNNER_ENVIRONMENT': 'github-hosted'}))
                for name in ('acquire', 'make_context', 'bounded_command', 'verify_recipe'):
                    stack.enter_context(patch.object(prep, name))
                stack.enter_context(patch.object(prep, '_inspect_image_json', return_value=base))
                stack.enter_context(patch.object(prep, '_prepare_container', return_value=('owned', 'a' * 64)))
                stack.enter_context(patch.object(prep, '_commit_image', return_value=result))
                def cleanup(*args):
                    self.assertFalse(original_exists(receipt))
                    if cleanup_fails:
                        raise RuntimeError('modeled cleanup failure')
                remover = stack.enter_context(patch.object(prep, '_stop_remove_owned', side_effect=cleanup))
                args = ['--execute', '--disposable-vm', '--work-root', str(Path(folder) / 'work'),
                        '--output-receipt', str(receipt)]
                if cleanup_fails:
                    with self.assertRaisesRegex(RuntimeError, 'modeled cleanup failure'):
                        prep.main(args)
                    self.assertFalse(original_exists(receipt))
                else:
                    prep.main(args)
                    self.assertEqual(json.loads(receipt.read_text())['preparationMode'],
                                     'bounded_container_install_then_local_commit')
                remover.assert_called_once()

    def test_sigterm_unwinds_preparation_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        with patch.object(prep, '_main', side_effect=lambda _: signal.raise_signal(signal.SIGTERM)):
            with self.assertRaisesRegex(InterruptedError, 'preparation terminated'):
                prep.main([])
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_commit_checks_base_config_and_clears_runtime_command(self):
        base = self._base_image()
        final = {'Id': 'sha256:' + '2' * 64, 'Architecture': 'amd64', 'Os': 'linux',
                 'Config': {'Entrypoint': ['/usr/bin/python3', '-I', '-B'], 'Cmd': [], 'User': '0',
                            'Env': ['BASE=public'], 'WorkingDir': '/work', 'Volumes': None},
                 'RootFS': {'Layers': base['RootFS']['Layers'] + ['sha256:' + '3' * 64]}}
        calls = []
        committed = 'sha256:' + '2' * 64
        final['Id'] = committed
        def docker(_config, *args, **_kwargs):
            calls.append(args)
            return committed if args[0] == 'commit' else json.dumps(final)
        with patch.object(prep, '_docker', side_effect=docker):
            self.assertEqual(prep._commit_image(Path('/tmp/docker-config'), 'a' * 64, base), final)
        self.assertEqual(calls[0][0], 'commit')
        self.assertIn('ENTRYPOINT ["/usr/bin/python3","-I","-B"]', calls[0])
        self.assertIn('CMD []', calls[0]); self.assertIn('USER 0', calls[0])
        self.assertEqual(calls[0][-2:], ('a' * 64, prep.TAG))

    def profile(self):
        return {'errors': [], 'osRelease': 'ID=ubuntu\nVERSION_ID="24.04"\n',
            'kernel': ['Linux', 'synthetic-host', '6.8.0-test', 'test', 'x86_64'], 'python': [3, 12, 3],
            'runner': {'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64', 'RUNNER_ENVIRONMENT': 'github-hosted',
                       'ImageOS': 'ubuntu24', 'ImageVersion': '20260901.1.0'},
            'tools': {path: {'resolved': path, 'sha256': 'a' * 64, 'version': 'synthetic version'}
                      for path in driver.HOST_TOOLS},
            'apparmorEnabled': 'Y', 'backing': 'ext4', 'stopTimeoutSupported': True, 'nfsModuleDryRun': True,
            'docker': [['name=apparmor', 'name=seccomp,profile=builtin'], 'linux', 'x86_64', '2'],
            'image': [SYNTHETIC_IMAGE_ID, [driver.IMAGE_REF], [], 'amd64', 'linux', None, ['sha256:' + 'b' * 64]],
            'routes': [{'dst': 'default'}, {'dst': '10.0.0.0/24'}], 'networkIpam': [None, [], [{'Subnet': '172.17.0.0/16'}]]}

    def test_required_host_profile_and_exact_preloaded_image(self):
        self.assertIsNone(driver.validate_host(self.profile(), {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]}))
        changes = [('osRelease', 'ID=debian\nVERSION_ID="24.04"'), ('python', [3, 11, 1]),
            ('kernel', ['Linux', 'model', '6.8', 'test', 'aarch64']), ('apparmorEnabled', 'N'),
            ('backing', 'overlay'), ('stopTimeoutSupported', False), ('nfsModuleDryRun', False),
            ('errors', [{'observation': 'tool', 'errorType': 'FileNotFoundError'}]), ('tools', {})]
        for key, value in changes:
            with self.subTest(key=key):
                model = self.profile(); model[key] = value
                with self.assertRaises(RuntimeError): driver.validate_host(model, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})
        for key, value in [('RUNNER_ENVIRONMENT', 'self-hosted'), ('RUNNER_OS', 'Windows'),
                           ('RUNNER_ARCH', 'ARM64'), ('ImageOS', 'ubuntu22'), ('ImageVersion', '')]:
            model = self.profile(); model['runner'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): driver.validate_host(model, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})

    def test_unsupported_docker_security_or_image_never_falls_back(self):
        for section, index, value in [('docker', 0, ['name=apparmor']), ('docker', 0, ['name=seccomp,profile=builtin']),
                ('docker', 0, ['name=apparmor', 'name=seccomp,profile=builtin', 'name=rootless']),
                ('docker', 1, 'windows'), ('docker', 2, 'aarch64'), ('docker', 3, '1'),
                ('image', 0, 'sha256:' + 'f' * 64), ('image', 1, ['other@sha256:' + 'a' * 64]),
                ('image', 2, ['unexpected-digest']), ('image', 3, 'arm64'), ('image', 4, 'windows'),
                ('image', 5, []), ('image', 6, ['sha256:' + 'f' * 64])]:
            model = self.profile(); model[section][index] = value
            with self.subTest(section=section, index=index, value=value), self.assertRaises(RuntimeError):
                driver.validate_host(model, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})

    def test_subnet_overlap_in_routes_or_existing_network_rejects(self):
        for overlap in ('172.30.249.0/29', '172.30.0.0/16', '172.30.249.2/32'):
            for field in ('routes', 'networkIpam'):
                model = self.profile()
                model[field] = [{'dst': overlap}] if field == 'routes' else [[{'Subnet': overlap}]]
                with self.subTest(field=field, overlap=overlap), self.assertRaisesRegex(RuntimeError, 'subnet collision'):
                    driver.validate_host(model, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})
        model = self.profile(); model['networkIpam'].append([{'Subnet': 'fd00::/64'}])
        driver.validate_host(model, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})

    def test_unknown_observation_is_retained_as_constant_failure_type(self):
        with patch.object(driver, 'command', side_effect=RuntimeError('DO_NOT_RETAIN_RAW_EXCEPTION')):
            observed = driver.host_inventory(lambda *a: (_ for _ in ()).throw(RuntimeError('PRIVATE')),
                Path('/nonexistent-model-output'), {'REGISTRY_TOKEN': 'PRIVATE', 'ImageVersion': 'public-model'}, SYNTHETIC_IMAGE_ID)
        # Tool-file metadata/public version reads only; all commands are blocked above.
        self.assertTrue(observed['errors'])
        self.assertNotIn('REGISTRY_TOKEN', observed['runner'])
        self.assertNotIn('PRIVATE', json.dumps(observed))
        self.assertNotIn('DO_NOT_RETAIN_RAW_EXCEPTION', json.dumps(observed))
        with self.assertRaises(RuntimeError): driver.validate_host(observed, {'imageId': SYNTHETIC_IMAGE_ID, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})

    def test_both_controlled_stop_paths_preserve_five_second_grace(self):
        source = (PACKET / 'run.py').read_text()
        calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'docker'
                 and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'stop']
        stops = [node for node in calls if len(node.args) > 2]
        self.assertEqual(len(stops), 2)
        for node in stops:
            self.assertEqual([arg.value for arg in node.args[:3]], ['stop', '--timeout', '5'])
            self.assertEqual({kw.arg: kw.value.value for kw in node.keywords}, {'timeout': 8})
        self.assertNotIn("'--time'", source)

    def test_inventory_precedes_host_mutation_and_shared_host_refusal_precedes_inventory(self):
        tree = ast.parse((PACKET / 'run.py').read_bytes())
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for function, first, second in [('exercise', 'admit_vm', 'run_fixture'),
                                         ('run_fixture', 'host_inventory', 'validate_host')]:
            calls = [node for node in ast.walk(functions[function]) if isinstance(node, ast.Call)]
            positions = {name: min(node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == name)
                         for name in (first, second)}
            self.assertLess(positions[first], positions[second])
        source = (PACKET / 'run.py').read_text()
        self.assertLess(source.index("record(args.output, 'HOST_INVENTORY.json', inventory)"), source.index('validate_host(inventory,'))
        self.assertLess(source.index('validate_host(inventory,'), source.index("command(['/usr/sbin/modprobe', 'nfsv4'])"))
        self.assertNotIn('apt-get', source)
        self.assertNotIn('unconfined', source)

    def test_failed_host_profile_has_evidence_before_any_command(self):
        with tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
            args = SimpleNamespace(output=Path(folder) / 'fresh', image_observation={'imageId': SYNTHETIC_IMAGE_ID,
                'imageRef': driver.IMAGE_REF, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})
            model = self.profile(); model['backing'] = 'overlay'
            with patch.object(driver, 'admit_vm'), patch.object(driver.os, 'umask'), \
                    patch.object(driver, 'host_inventory', return_value=model), \
                    patch.object(driver, 'command', side_effect=AssertionError('must not execute')):
                with self.assertRaises(RuntimeError): driver.exercise(args)
            value = json.loads((args.output / 'OBSERVATIONS.json').read_text())
            self.assertEqual(value['failure']['stage'], 'host-profile-admission')
            self.assertFalse(value['exerciseCompleted'])
            self.assertEqual(value['unresolvedCleanup'], [])
            self.assertEqual(json.loads((args.output / 'HOST_INVENTORY.json').read_text()), model)

    def test_refusal_and_existing_output_never_write_or_replace_evidence(self):
        with tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
            args = SimpleNamespace(output=Path(folder) / 'fresh')
            with patch.object(driver, 'admit_vm', side_effect=RuntimeError('refused')):
                with self.assertRaises(RuntimeError): driver.exercise(args)
            self.assertFalse(args.output.exists())
            args.output.mkdir(); receipt = args.output / 'OBSERVATIONS.json'; receipt.write_text('preserved')
            with patch.object(driver, 'admit_vm'), patch.object(driver.os, 'umask'), \
                    patch.object(driver, 'run_fixture', side_effect=AssertionError('no reuse')):
                with self.assertRaises(FileExistsError): driver.exercise(args)
            self.assertEqual(receipt.read_text(), 'preserved')

    def test_modeled_command_server_and_client_failures_retain_stage_without_error_text(self):
        # Driver control flow is real; every host command, signal and host admission is modeled.
        for target in ('nfs-module-load', 'server-start', 'client-a-start-attach', 'client-b-start-attach'):
            states, roles = {}, {}
            def modeled_command(args, **kwargs):
                if args[0] != '/usr/bin/docker':
                    if target == 'nfs-module-load': raise RuntimeError('PRIVATE_EXCEPTION_BYTES')
                    return 0, ''
                tail = args[5:]
                if tail[0] in ('ps', 'logs', 'exec'): return 0, ''
                if tail[:2] == ['network', 'ls']: return 0, ''
                if tail[:2] == ['network', 'create']: return 0, 'f' * 64
                if tail[:2] == ['network', 'inspect']:
                    return 0, ' '.join(map(json.dumps, ['f' * 64, driver.PREFIX, driver.LABEL, True, {}]))
                if tail[:2] == ['network', 'rm']: return 0, ''
                if tail[0] == 'create':
                    role = tail[tail.index('--name') + 1].removeprefix(driver.PREFIX + '-')
                    cid = {'server': 'a', 'client-a': 'b', 'client-b': 'c'}[role] * 64
                    roles[cid], states[cid] = role, 'created'
                    return 0, cid
                cid, role = tail[-1], roles[tail[-1]]
                if tail[0] == 'inspect':
                    if '.State.ExitCode' in tail[2]: return 0, '47' if role == 'client-a' else '0'
                    return 0, ' '.join(map(json.dumps, [cid, SYNTHETIC_IMAGE_ID,
                        '/' + driver.PREFIX + '-' + role, driver.LABEL, states[cid]]))
                if tail[0] == 'start':
                    stage = 'server-start' if role == 'server' else role + '-start-attach'
                    if target == stage: raise RuntimeError('PRIVATE_EXCEPTION_BYTES')
                    states[cid] = 'running' if role == 'server' else 'exited'
                    events = [{'observation': 'mounted', 'filesystem': 'nfs4', 'version': '4.1',
                               'security': 'AUTH_SYS', 'hard': True},
                              {'observation': 'final-placeholder-fsync-and-rename-completed'}]
                    return 0, '\n'.join(map(json.dumps, events)) if role == 'client-a' else ''
                if tail[0] == 'stop': states[cid] = 'exited'; return 0, ''
                if tail[0] == 'rm': del states[cid]; return 0, ''
                raise AssertionError('unmodeled command')
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
                args = SimpleNamespace(output=Path(folder) / 'fresh', image_observation={'imageId': SYNTHETIC_IMAGE_ID,
                    'imageRef': driver.IMAGE_REF, 'rootfsDiffIds': ['sha256:' + 'b' * 64]})
                with patch.object(driver, 'admit_vm'), patch.object(driver.os, 'umask'), \
                        patch.object(driver, 'host_inventory', return_value=self.profile()), \
                        patch.object(driver, 'command', side_effect=modeled_command), \
                        patch.object(driver.Path, 'read_text', return_value=''), \
                        patch.object(driver.signal, 'signal'), patch.object(driver.signal, 'setitimer'), \
                        patch.object(driver.time, 'sleep'):
                    with self.assertRaises(RuntimeError): driver.exercise(args)
                raw = (args.output / 'OBSERVATIONS.json').read_text(); value = json.loads(raw)
                self.assertEqual(value['failure'], {'stage': target, 'kind': 'rejected-or-command-failed'})
                self.assertFalse(value['exerciseCompleted'])
                self.assertEqual(value['unresolvedCleanup'], [])
                self.assertNotIn('PRIVATE_EXCEPTION_BYTES', raw)
                self.assertEqual(states, {})

    def test_workflow_is_manual_pinned_credential_bounded_and_public_evidence_only(self):
        path = PACKET.parents[2] / '.github/workflows/android-nfs-disposable-fixture.yml'
        source = path.read_text()
        self.assertIn('workflow_dispatch:', source)
        self.assertNotIn('pull_request:', source)
        self.assertNotIn('push:', source)
        self.assertIn('timeout-minutes: 15', source)
        self.assertIn('timeout-minutes: 10', source)
        self.assertIn('runs-on: ubuntu-24.04', source)
        self.assertIn('permissions: {}', source)
        self.assertIn('      contents: read', source)
        self.assertNotIn('packages: read', source)
        self.assertNotIn('id-token:', source)
        self.assertNotIn('secrets.', source)
        self.assertEqual(source.count('${{ github.token }}'), 0)
        self.assertIn('persist-credentials: false', source)
        self.assertLess(source.index('test_android_nfs_disposable.py -v'),
                        source.index('Acquire fixed public archives'))
        self.assertIn('scripts/prepare_android_nfs_public_image.py', source)
        self.assertIn('archive.ubuntu.com', (PACKET / 'public-image/public-packages.tsv').read_text())
        self.assertNotIn('ghcr.io', source)
        self.assertIn('sudo /usr/bin/env -i', source)
        self.assertNotIn('docker save', source)
        self.assertNotIn('apt-get', source)
        self.assertNotIn('unconfined', source)
        for line in source.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'uses: actions/[a-z-]+@[0-9a-f]{40}$')
        paths = source.split('          path: |\n', 1)[1].split('          if-no-files-found:', 1)[0]
        self.assertEqual(len(paths.splitlines()), 4)
        self.assertNotIn('*', paths)

    def test_imports_have_no_execution(self):
        with patch('subprocess.Popen', side_effect=AssertionError('runtime forbidden')):
            load('run')
            load('client')
            load('server')

    def test_expired_cleanup_deadline_never_launches_later_commands(self):
        with patch.object(driver, 'COMMAND_DEADLINE', 1.0), \
                patch.object(driver.time, 'monotonic', return_value=2.0), \
                patch.object(driver.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            for _ in range(3):
                with self.assertRaisesRegex(RuntimeError, 'phase deadline'):
                    driver.command(['/usr/bin/docker', 'anything'])

    def test_shared_host_is_never_admitted(self):
        args = SimpleNamespace(execute=True, disposable_vm=True,
            image_id='sha256:' + 'a' * 64, image_ref='example.invalid/nfs@sha256:' + 'b' * 64,
            output=Path('/tmp/nfs-qualification-never-created'))
        with patch.object(driver.os, 'getuid', return_value=0), \
                patch.object(driver.Path, 'exists', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'refuse shared/local host'):
                driver.admit_vm(args, {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted'})

    def test_explicit_execution_and_disposable_admission_required(self):
        for execute, disposable in ((False, False), (False, True), (True, False)):
            with self.subTest(execute=execute, disposable=disposable):
                with self.assertRaisesRegex(RuntimeError, 'explicit disposable VM'):
                    driver.admit_vm(SimpleNamespace(execute=execute, disposable_vm=disposable), {})

    def test_fixed_container_resource_and_isolation_arguments(self):
        for role in ('server', 'client-a', 'client-b'):
            args = driver.create_args('image@sha256:' + 'a' * 64, 'b' * 64, role,
                                      Path('/out/program'), Path('/out'))
            with self.subTest(role=role):
                self.assertEqual(args[args.index('--pull') + 1], 'never')
                self.assertEqual(args[args.index('--network') + 1], 'b' * 64)
                self.assertIn('--read-only', args)
                self.assertEqual(args[args.index('--user') + 1], '0:0')
                self.assertEqual(args[args.index('--cap-drop') + 1], 'ALL')
                self.assertEqual(args[args.index('--memory') + 1], '384m' if role == 'server' else '256m')
                self.assertEqual(args[args.index('--cpus') + 1], '0.25' if role == 'server' else '0.5')
                self.assertEqual(args[args.index('--memory-swap') + 1], args[args.index('--memory') + 1])
                self.assertFalse(set(args) & {'--privileged', '--publish', '-p', '--device', '--pid', '--ipc'})
                self.assertFalse(any('/run/docker.sock' in item or 'unconfined' in item for item in args))
                self.assertEqual(sum(item == '--tmpfs' for item in args), 2)
                self.assertIn('no-new-privileges', args)
                self.assertIn('/out/program:/packet:ro,rprivate', args)
        server = driver.create_args('image', 'network', 'server', Path('/out/program'), Path('/out'))
        self.assertNotIn('SYS_ADMIN', server)
        self.assertIn('max-size=64k', server)
        self.assertIn('max-file=1', server)
        self.assertIn('/out/export:/export:rw,rprivate', server)
        self.assertIn('/out/state:/var/lib/nfs:rw,rprivate', server)
        native = driver.create_args('image', 'network', 'client-a', Path('/out/program'), Path('/out'))
        self.assertIn('SYS_ADMIN', native)
        self.assertIn('apparmor=' + driver.PROFILE, native)
        with self.assertRaises(RuntimeError):
            driver.create_args('image', 'network', 'unrecognized', Path('/out/program'), Path('/out'))

    def test_mount_and_server_configuration_are_narrow(self):
        source = (PACKET / 'client.py').read_text()
        self.assertIn("['/usr/bin/mount', '-t', 'nfs4', '-o'", source)
        self.assertIn('vers=4.1,proto=tcp,port=2049,sec=sys,hard', source)
        self.assertIn('nosharecache', source)
        config = (PACKET / 'ganesha.conf').read_text()
        self.assertIn('Access_Type = None;', config)
        self.assertEqual(config.count('Squash = No_Root_Squash;'), 1)
        self.assertIn('Clients = 172.30.249.3;', config)
        self.assertIn('RecoveryBackend = fs_ng;', config)
        profile = (PACKET / 'client.apparmor').read_text()
        self.assertIn('mount fstype=nfs4 -> /mnt/recovery-store/,', profile)
        self.assertNotIn('mount,', profile)

    def test_events_require_both_real_phase_observations(self):
        mounted = {'observation': 'mounted', 'filesystem': 'nfs4', 'version': '4.1',
                   'security': 'AUTH_SYS', 'hard': True}
        write = [mounted, {'observation': 'final-placeholder-fsync-and-rename-completed'}]
        read = [mounted, {'observation': 'replacement-client-readback-completed',
                          'ambiguousRecord': 'retained-without-retry'}]
        driver.validate_events('client-a', 47, write)
        driver.validate_events('client-b', 0, read)
        for role, code, rows in (('client-a', 0, write), ('client-b', 47, read),
                                 ('client-a', 47, []), ('client-b', 0, [mounted]),
                                 ('other', 0, read), ('client-a', 47, write + [mounted]),
                                 ('client-b', False, read),
                                 ('client-a', 47, [mounted | {'hard': 1}, write[1]])):
            with self.subTest(role=role, code=code, rows=rows), self.assertRaises(RuntimeError):
                driver.validate_events(role, code, rows)

    def test_local_exclusive_create_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
            path = Path(folder) / 'file'
            client.exclusive(path, b'first')
            client.collision(path)
            with self.assertRaises(FileExistsError):
                client.exclusive(path, b'replacement')
            self.assertEqual(path.read_bytes(), b'first')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_local_fsync_order_rename_and_injected_loss_preserve_bytes(self):
        # This exercises the real local syscalls, NOT NFS, root UID mapping or
        # independent-client exclusion. Synthetic ownership and flock only.
        with tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
            root = Path(folder)
            events = []
            real_fsync, real_rename = os.fsync, os.rename
            def fsync(fd):
                info = os.fstat(fd)
                raw = None
                if stat.S_ISREG(info.st_mode):
                    raw = Path('/proc/self/fd/' + str(fd)).read_bytes()
                events.append(('fsync', info.st_ino, raw))
                return real_fsync(fd)
            def rename(source, target):
                inode = (source / 'signed-placeholder.bin').stat().st_ino
                self.assertIn(('fsync', inode, client.SIGNED), events)
                events.append(('rename', inode, None))
                return real_rename(source, target)
            def exact_fixture(path, raw):
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(path.stat().st_nlink, 1)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with patch.object(client, 'ROOT', root), patch.object(client, 'exact', exact_fixture), \
                    patch.object(client, 'private_directory'), patch.object(client.os, 'fsync', fsync), \
                    patch.object(client.os, 'rename', rename), \
                    patch.object(client.subprocess, 'run', return_value=SimpleNamespace(returncode=23)), \
                    patch.object(client.os, '_exit', side_effect=LostAcknowledgement):
                with self.assertRaises(LostAcknowledgement):
                    client.write_phase()
                lost = root / 'recovery/unacknowledged-operation.bin'
                self.assertEqual(lost.read_bytes(), client.AMBIGUOUS)
                self.assertIn(('fsync', lost.stat().st_ino, client.AMBIGUOUS), events)
                client.read_phase()
                self.assertEqual(lost.read_bytes(), client.AMBIGUOUS)

    def test_bad_root_directory_modes_and_symlink_fail(self):
        with tempfile.TemporaryDirectory(prefix='nfs-packet-unit-') as folder:
            path = Path(folder)
            fake = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)
            with patch.object(client.Path, 'lstat', return_value=fake), self.assertRaises(RuntimeError):
                client.private_directory(path)
            fake.st_mode = stat.S_IFLNK | 0o700
            with patch.object(client.Path, 'lstat', return_value=fake), self.assertRaises(RuntimeError):
                client.private_directory(path)



if __name__ == '__main__':
    unittest.main()
