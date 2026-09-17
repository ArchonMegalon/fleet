#!/bin/sh
# Never run on the host. Only an independently approved, network-disabled image
# build may pass this explicit execution argument. No Python is needed here.
set -eu
test "$#" -eq 1 && test "$1" = --execute-offline-install || exit 64
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
DEBIAN_FRONTEND=noninteractive
DEBCONF_NONINTERACTIVE_SEEN=true
export PATH LC_ALL DEBIAN_FRONTEND DEBCONF_NONINTERACTIVE_SEEN
test "$(id -u)" -eq 0
test "$(dpkg-query -W -f='${Version}' apt)" = 2.8.3
test -x /usr/sbin/policy-rc.d
printf '%s  %s\n' \
    ffe8b0570226814bea62229669fcfaaab1b08a6c6d53bb74aedd706f0c230adc /packages/package-files.tsv \
    2e7f3a8f400a08ee22cfe48a85c94071aeb899b07343e3962b29cad03321feef /packages/install-order.tsv \
    4b0d6972477a55bb64330f66e336903c39f5c93b0186a3553736ef6b9567f4aa /usr/sbin/policy-rc.d \
    | sha256sum --strict --check

work=$(mktemp -d /tmp/offline-apt.XXXXXXXX)
chmod 0755 "$work"  # Public-only APT inputs; allow the normal _apt sandbox.
mkdir "$work/lists" "$work/archives" "$work/archives/partial"

# The initial APT_CONFIG is read before normal apt.conf snippets. Disable those
# snippets as well as every repository source/list; only explicit local .debs
# are available. Keep the real image dpkg status, never the planning surrogate.
printf '%s\n' \
    'Dir::Etc::main "/dev/null";' \
    'Dir::Etc::parts "-";' \
    'Dir::Etc::sourcelist "/dev/null";' \
    'Dir::Etc::sourceparts "-";' \
    "Dir::State::lists \"$work/lists\";" \
    "Dir::Cache::archives \"$work/archives\";" \
    'Dir::Cache::pkgcache "";' \
    'Dir::Cache::srcpkgcache "";' \
    'Acquire::Retries "0";' \
    'DPkg::Lock::Timeout "0";' \
    'Dpkg::Use-Pty "0";' \
    > "$work/apt.conf"

awk '
# BEGIN_MANIFEST_PARSER
BEGIN { FS = "\t" }
NR == 1 { if ($0 != "filename\tbytes\tsha256") bad = 1; next }
{
    if (NF != 3 || $1 !~ /^[a-z0-9][a-z0-9+._~-]*[.]deb$/ || seen[$1]++ ||
        $2 !~ /^[1-9][0-9]*$/ || length($3) != 64 || $3 ~ /[^0-9a-f]/) bad = 1
    count++; bytes += $2
}
END { if (bad || count != 52 || bytes != 13482674) exit 1 }
# END_MANIFEST_PARSER
' /packages/package-files.tsv
awk 'NR > 1' /packages/package-files.tsv > "$work/archive-rows"
awk -F '\t' 'NR > 1 { print $1 }' /packages/package-files.tsv | sort > "$work/expected-files"
find /packages/debs -mindepth 1 -maxdepth 1 -printf '%f\n' | sort > "$work/actual-files"
cmp "$work/expected-files" "$work/actual-files"

check_archives() {
    while IFS="$(printf '\t')" read -r filename bytes digest; do
        archive=/packages/debs/$filename
        test -f "$archive" && test ! -L "$archive" || exit 65
        test "$(stat -c %s "$archive")" = "$bytes"
        printf '%s  %s\n' "$digest" "$archive" | sha256sum --strict --check --status
    done < "$work/archive-rows"
}
check_archives
set --
while IFS="$(printf '\t')" read -r filename bytes digest; do
    set -- "$@" "/packages/debs/$filename"
done < "$work/archive-rows"
test "$#" -eq 52

offline_apt() {
    env -i PATH="$PATH" LC_ALL=C DEBIAN_FRONTEND=noninteractive \
        DEBCONF_NONINTERACTIVE_SEEN=true APT_CONFIG="$work/apt.conf" \
        /usr/bin/apt-get --yes --no-download --no-remove \
        --no-install-recommends --no-install-suggests "$@" < /dev/null
}
simulation_status=0
offline_apt --simulate install "$@" > "$work/simulation.txt" || simulation_status=$?
# Public diagnostics also reach build stdout before a failure discards the layer.
tee /offline-apt-simulation.txt < "$work/simulation.txt"
test "$simulation_status" -eq 0
action_status=0
awk '
# BEGIN_ACTION_PARSER
$1 == "Remv" || $1 == "Purg" { bad = 1 }
$1 == "Inst" || $1 == "Conf" {
    action = $1; package = $2; rest = $0
    if (package !~ /^[a-z0-9][a-z0-9+.-]*$/) bad = 1
    sub(/^[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]+/, "", rest)
    if (action == "Inst") sub(/^\[[^][]+\][[:space:]]+/, "", rest)
    if (rest !~ /^\([^()[:space:]]+[[:space:])]/ || index(rest, ")") == 0) bad = 1
    sub(/^\(/, "", rest)
    split(rest, fields, /[[:space:])]/)
    version = fields[1]
    if (version !~ /^[0-9][A-Za-z0-9.+:~-]*$/ || seen[action, package]++) bad = 1
    if (action == "Inst") { installed[package] = version; installs++ }
    else { if (!(package in installed) || installed[package] != version) bad = 1; configs++ }
    print action "\t" package "\t" version
}
END { if (bad || installs != 52 || configs != 52) exit 1 }
# END_ACTION_PARSER
' "$work/simulation.txt" > "$work/actual-actions.tsv" || action_status=$?
tee /offline-apt-actions.tsv < "$work/actual-actions.tsv"
test "$action_status" -eq 0
awk -F '\t' 'NR > 1 { print $1 "\t" $2 "\t" $3 }' \
    /packages/install-order.tsv > "$work/expected-actions.tsv"
cmp "$work/expected-actions.tsv" "$work/actual-actions.tsv"

# Recheck bytes after simulation. Same local requests/options, no retries,
# downloads, removals, recommends or repository fallback on the install path.
check_archives
# APT 2.8.3 --no-download shuts down acquisition even for local .deb inputs.
# Its cache-hit branch needs the canonical FULL-version basename, including
# a lowercase %3a epoch escape, and trusts SIZE ONLY. Stage verified copies;
# never remove --no-download or let APT obtain bytes from any other source.
# BEGIN_CACHE_FUNCTIONS
cache_basename() {
    package=$(dpkg-deb -f "$1" Package)
    version=$(dpkg-deb -f "$1" Version)
    architecture=$(dpkg-deb -f "$1" Architecture)
    case "$package" in ''|*[!a-z0-9+.-]*) exit 65;; esac
    case "$version" in ''|*[!0-9A-Za-z.+:~-]*) exit 65;; esac
    case "$architecture" in amd64|all) ;; *) exit 65;; esac
    expected=$(awk -F '\t' -v file="${1##*/}" '$1 == "Inst" && $4 == file { print $2 "\t" $3 }' /packages/install-order.tsv)
    test "$expected" = "$(printf '%s\t%s' "$package" "$version")"
    # Other APT QuoteString special characters (_, %, control/non-ASCII)
    # are excluded above; + . ~ and - intentionally remain literal.
    printf '%s_%s_%s.deb\n' "$package" "$(printf '%s' "$version" | sed 's/:/%3a/g')" "$architecture"
}
stage_cached_archives() {
    : > "$work/cached-rows"
    while IFS="$(printf '\t')" read -r filename bytes digest; do
        source=/packages/debs/$filename
        cache_name=$(cache_basename "$source")
        cached=$work/archives/$cache_name
        test ! -e "$cached" && test ! -L "$cached"
        (set -C; cat "$source" > "$cached")
        chmod 0444 "$cached"
        printf '%s\t%s\t%s\n' "$cache_name" "$bytes" "$digest" >> "$work/cached-rows"
    done < "$work/archive-rows"
}
check_cached_archives() {
    while IFS="$(printf '\t')" read -r cache_name bytes digest; do
        cached=$work/archives/$cache_name
        test -f "$cached" && test ! -L "$cached"
        test "$(stat -c %h "$cached")" -eq 1
        test "$(stat -c %s "$cached")" = "$bytes"
        printf '%s  %s\n' "$digest" "$cached" | sha256sum --strict --check --status
    done < "$work/cached-rows"
}
# END_CACHE_FUNCTIONS
stage_cached_archives
check_cached_archives
tee /offline-apt-cache.tsv < "$work/cached-rows"
check_cached_archives
offline_apt install "$@"
dpkg --audit > /package-audit.txt
test ! -s /package-audit.txt
dpkg-query -W > /package-inventory.txt
mkdir -p /mnt/recovery-store /export /var/lib/nfs/ganesha /run/rpcbind
