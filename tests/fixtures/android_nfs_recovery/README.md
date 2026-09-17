# Disposable NFS fixture: public-input alternative

Source preparation only. The private GHCR recovery fixture has no Fleet Actions
access; do not add a package grant, token, image export or private-image fallback.
The manual workflow builds a **different local image** from public inputs instead:

1. Exact Microsoft MCR base manifest and config ID.
2. 52 fixed Ubuntu HTTPS archives, 13,482,674 bytes total, with exact SHA-256 values.
3. The unchanged reviewed offline installer, install order and package inventory.

Acquisition rejects redirects and proxies and has a 120-second process alarm.
The anonymous MCR pull uses an empty Docker configuration. Installation runs in
an ordinary named, non-privileged container with network disabled, 1 GiB RAM,
no swap and half a CPU; `public-image/install-bounded.sh` checks the actual
cgroup limits before invoking the unchanged offline installer. The container
must exit successfully without OOM before the host daemon commits a local
image. Source hashes are checked before acquisition and context creation and
again before the observation is written. The fixture runs by the resulting
immutable config ID, never by a mutable tag or the former private image ID.
The adjacent `public-image/Dockerfile` is historical evidence only: it is not
copied, executed, or represented in the active recipe receipt.
The read-only `/packages` mount is not copied into the committed image layer.

The receipt is a same-job local observation, **not signed release authority**.
It binds package/recipe/fixture hashes, base identity and observed rootfs layers.
Only an explicitly admitted disposable GitHub-hosted VM may run preparation or
the fixture; local shared-host execution is refused. These are accident guards,
not cryptographic proof that a machine is disposable.

Preparation has a 10-minute step limit (acquisition 120s, pull 60s, each inspection
30s, installer 280s, local commit 60s). These resource limits bound the installer,
not the Docker daemon's commit/compression work. The overall job limit is 15
minutes. The existing fixture body
210s / cleanup 30s budgets, non-replay behavior and isolation remain unchanged.
Failed preparation commands retain at most 1 MiB of public output as escaped JSON
in the job log. Uploads remain the four explicitly allowlisted fixture records;
no package archive, image archive, Docker configuration or work directory is
published. Job cancellation does not prove successful VM destruction or cleanup
of stuck hard-NFS I/O.

Local verification (synthetic/source only; no Docker, network, SDK or mounts):

```sh
python3 -I -B -m unittest discover -s tests -p test_android_nfs_disposable.py -v
```

Preparing or testing these sources does not build an image, qualify a durable
signer backend, sign Android, upload to Play, or authorize publication. A future
manual disposable-VM run must use the reviewed protected-main execution SHA.
