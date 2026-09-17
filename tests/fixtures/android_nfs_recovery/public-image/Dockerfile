# PREPARATION ONLY: same pinned public inputs as eDzvCuFu. No remote frontend.
FROM mcr.microsoft.com/dotnet/runtime-deps:10.0.10-noble-amd64@sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e
USER 0
COPY --chmod=0555 policy-rc.d /usr/sbin/policy-rc.d
COPY --chmod=0555 install-offline.sh /usr/local/libexec/install-offline.sh
COPY --chmod=0444 package-files.tsv install-order.tsv /packages/
COPY --chmod=0444 debs/*.deb /packages/debs/
RUN --network=none set -eu; \
    memory_max="$(cat /sys/fs/cgroup/memory.max)"; \
    memory_swap_max="$(cat /sys/fs/cgroup/memory.swap.max)"; \
    cpu_max="$(cat /sys/fs/cgroup/cpu.max)"; \
    printf 'BUILD_CGROUP_V2 memory.max=%s memory.swap.max=%s cpu.max=%s\n' "$memory_max" "$memory_swap_max" "$cpu_max"; \
    test "$memory_max" = 1073741824; \
    test "$memory_swap_max" = 0; \
    test "$cpu_max" = '50000 100000'; \
    exec /bin/sh /usr/local/libexec/install-offline.sh --execute-offline-install
ENTRYPOINT ["/usr/bin/python3", "-I", "-B"]
