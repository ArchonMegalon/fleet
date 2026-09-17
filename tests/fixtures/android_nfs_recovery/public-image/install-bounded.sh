#!/bin/sh
# Public-input preparation only.  Run inside the exact bounded container.
# The offline installer is the reviewed existing script; this wrapper only
# checks the effective cgroup and installs the pinned service-start policy.
set -eu
test "$#" -eq 1 && test "$1" = --execute-bounded-install || exit 64
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL

memory_max=$(cat /sys/fs/cgroup/memory.max)
memory_swap_max=$(cat /sys/fs/cgroup/memory.swap.max)
cpu_max=$(cat /sys/fs/cgroup/cpu.max)
printf 'BOUNDED_INSTALL_CGROUP memory.max=%s memory.swap.max=%s cpu.max=%s\n' \
    "$memory_max" "$memory_swap_max" "$cpu_max"
test "$memory_max" = 1073741824
test "$memory_swap_max" = 0
test "$cpu_max" = '50000 100000'

test -f /packages/policy-rc.d && test ! -L /packages/policy-rc.d
printf '%s  %s\n' \
    4b0d6972477a55bb64330f66e336903c39f5c93b0186a3553736ef6b9567f4aa \
    /packages/policy-rc.d | sha256sum --strict --check --status
test ! -e /usr/sbin/policy-rc.d && test ! -L /usr/sbin/policy-rc.d
install -o 0 -g 0 -m 0555 /packages/policy-rc.d /usr/sbin/policy-rc.d
test -f /usr/sbin/policy-rc.d && test ! -L /usr/sbin/policy-rc.d
test "$(stat -c '%u:%g:%a:%h' /usr/sbin/policy-rc.d)" = '0:0:555:1'

exec /bin/sh /packages/install-offline.sh --execute-offline-install
