"""Actual filesystem exercises, only inside the reviewed disposable NFS client."""
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path('/mnt/recovery-store')
UNSIGNED = b'not-an-AAB: unsigned synthetic placeholder\n'
SIGNED = b'not-an-AAB: final signed-placeholder bytes; no cryptography\n'
AMBIGUOUS = b'post-fsync response deliberately not acknowledged; do not retry\n'


def require(ok, label):
    if not ok:
        raise RuntimeError(label)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            require(count > 0, 'short-write')
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_dir(path.parent)


def exact(path, raw):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'private-file')
    require(path.read_bytes() == raw, 'exact-readback')


def private_directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
            and stat.S_IMODE(info.st_mode) == 0o700, 'private-directory')


def collision(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        return
    os.close(fd)
    raise RuntimeError('exclusive-create-did-not-reject-existing')


def mount():
    require(os.getuid() == 0 and ROOT.is_dir(), 'client-identity')
    subprocess.run(['/usr/bin/mount', '-t', 'nfs4', '-o',
        'vers=4.1,proto=tcp,port=2049,sec=sys,hard,timeo=50,retrans=2,nosharecache,noresvport',
        '172.30.249.2:/qualify', str(ROOT)], check=True)
    rows = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()
            if line.split()[4] == str(ROOT)]
    require(len(rows) == 1, 'one-exact-mount')
    row = rows[0]
    separator = row.index('-')
    options = set(row[separator + 3].split(','))
    require(row[separator + 1] == 'nfs4' and row[separator + 2] == '172.30.249.2:/qualify'
            and {'rw', 'vers=4.1', 'proto=tcp', 'sec=sys', 'hard'} <= options
            and 'soft' not in options, 'actual-hard-nfsv41')
    private_directory(ROOT)
    print(json.dumps({'observation': 'mounted', 'filesystem': 'nfs4',
                      'version': '4.1', 'security': 'AUTH_SYS', 'hard': True}), flush=True)


def write_phase():
    recovery, outputs = ROOT / 'recovery', ROOT / 'outputs'
    recovery.mkdir(mode=0o700)
    outputs.mkdir(mode=0o700)
    sync_dir(ROOT)
    attempt = recovery / 'synthetic-attempt'
    attempt.mkdir(mode=0o700)
    sync_dir(recovery)
    final = attempt / 'signed-placeholder.bin'
    exclusive(final, UNSIGNED)
    collision(final)
    # Simulate a tool replacing the file, then fsync the actual final inode.
    replacement = attempt / 'replacement.tmp'
    exclusive(replacement, SIGNED)
    os.replace(replacement, final)
    fd = os.open(final, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(os.read(fd, 4096) == SIGNED, 'final-file-bytes')
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_dir(attempt)
    exact(final, SIGNED)
    lock = os.open(attempt / 'operation.lock', os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child = subprocess.run([sys.executable, '-I', '-B', __file__, 'lock-child',
                                str(attempt / 'operation.lock')], check=False)
        require(child.returncode == 23, 'second-process-lock-excluded')
        os.fsync(lock)
    finally:
        os.close(lock)
    sync_dir(attempt)
    destination = outputs / attempt.name
    require(not destination.exists(), 'no-replace-existing-output')
    before = final.stat().st_ino
    os.rename(attempt, destination)
    sync_dir(recovery)
    sync_dir(outputs)
    require(not attempt.exists() and (destination / final.name).stat().st_ino == before,
            'same-filesystem-rename')
    exact(destination / final.name, SIGNED)
    print(json.dumps({'observation': 'final-placeholder-fsync-and-rename-completed'}), flush=True)
    # No completion acknowledgement is emitted after these durable writes.
    # This is an injected client-response loss, not a network-partition claim.
    exclusive(recovery / 'unacknowledged-operation.bin', AMBIGUOUS)
    os._exit(47)


def read_phase():
    require({p.name for p in ROOT.iterdir()} == {'recovery', 'outputs'}, 'root-inventory')
    recovery, outputs = ROOT / 'recovery', ROOT / 'outputs'
    require({p.name for p in recovery.iterdir()} == {'unacknowledged-operation.bin'}, 'retained-inventory')
    require({p.name for p in outputs.iterdir()} == {'synthetic-attempt'}, 'output-inventory')
    attempt = outputs / 'synthetic-attempt'
    for path in (ROOT, recovery, outputs, attempt):
        private_directory(path)
    require({p.name for p in attempt.iterdir()} == {'signed-placeholder.bin', 'operation.lock'},
            'attempt-inventory')
    exact(outputs / 'synthetic-attempt/signed-placeholder.bin', SIGNED)
    exact(outputs / 'synthetic-attempt/operation.lock', b'')
    exact(recovery / 'unacknowledged-operation.bin', AMBIGUOUS)
    collision(recovery / 'unacknowledged-operation.bin')
    sync_dir(recovery)
    sync_dir(outputs)
    print(json.dumps({'observation': 'replacement-client-readback-completed',
                      'ambiguousRecord': 'retained-without-retry'}), flush=True)


def main():
    os.umask(0o077)
    if sys.argv[1:] and sys.argv[1] == 'lock-child':
        fd = os.open(sys.argv[2], os.O_RDWR | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(23)
        finally:
            os.close(fd)
        raise SystemExit(24)
    require(sys.argv[1:] in (['write'], ['read']), 'exact-client-phase')
    require(Path('/proc/self/attr/current').read_text().strip() ==
            'nfs-qualification-client-bkpapg6l (enforce)', 'exact-client-mount-profile')
    mount()
    if sys.argv[1] == 'write':
        write_phase()
    else:
        read_phase()
        subprocess.run(['/usr/bin/umount', str(ROOT)], check=True)


if __name__ == '__main__':
    main()
