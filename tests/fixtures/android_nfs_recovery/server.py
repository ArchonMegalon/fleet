"""Test-only Ganesha entrypoint; no mounts, images, credentials or host services."""
import os
from pathlib import Path
import subprocess

if __name__ == '__main__':
    os.umask(0o077)
    # Runtime mounts hide image-layer directories; preserve Ganesha recovery
    # state across this container's controlled stop/start.
    for directory in ('/run/rpcbind', '/var/lib/nfs/ganesha'):
        Path(directory).mkdir(mode=0o700, exist_ok=True)
    # rpcbind is container-private. NFS clients are pinned directly to TCP2049.
    subprocess.run(['/usr/sbin/rpcbind', '-w'], check=True, timeout=10)
    os.execv('/usr/bin/ganesha.nfsd', ['/usr/bin/ganesha.nfsd', '-F', '-L', 'STDOUT',
                                     '-f', '/packet/ganesha.conf', '-p', '/run/ganesha.pid'])
