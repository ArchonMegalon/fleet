# Dormant, credential-free image recipe. No image build or tree authority is implied.
FROM mcr.microsoft.com/dotnet/runtime-deps:10.0.10-noble-amd64@sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e

COPY containers/android-preview12-rebuilder/ubuntu.sources /opt/fleet-rebuilder/ubuntu.sources
COPY containers/android-preview12-rebuilder/ubuntu-InRelease.SHA256SUMS /opt/fleet-rebuilder/ubuntu-InRelease.SHA256SUMS
# BEGIN SNAPSHOT BOOTSTRAP
RUN set -eu; \
    apt_lists="$(mktemp -d /tmp/fleet-rebuilder-apt.XXXXXXXX)"; \
    apt-get -o Dir::Etc::sourcelist=/opt/fleet-rebuilder/ubuntu.sources \
        -o Dir::Etc::sourceparts=- -o Dir::State::lists="$apt_lists" \
        -o Acquire::AllowInsecureRepositories=false -o APT::Get::AllowUnauthenticated=false \
        -o Acquire::Check-Valid-Until=true update; \
    (cd "$apt_lists" && sha256sum --strict --check /opt/fleet-rebuilder/ubuntu-InRelease.SHA256SUMS); \
    test "$(find "$apt_lists" -maxdepth 1 -type f -name '*InRelease' | wc -l)" -eq 3; \
    apt-get -o Dir::Etc::sourcelist=/opt/fleet-rebuilder/ubuntu.sources \
        -o Dir::Etc::sourceparts=- -o Dir::State::lists="$apt_lists" \
        -o Acquire::AllowInsecureRepositories=false -o APT::Get::AllowUnauthenticated=false \
        -o Acquire::Check-Valid-Until=true install -y --no-install-recommends \
        git jq python3 bash openssl zip unzip coreutils findutils libatomic1 ca-certificates; \
    dpkg-query -W > /opt/fleet-rebuilder/os-package-inventory.txt; \
    case "$apt_lists" in /tmp/fleet-rebuilder-apt.????????) rm -rf -- "$apt_lists" ;; *) exit 1 ;; esac
# END SNAPSHOT BOOTSTRAP

COPY containers/android-preview12-signer/install_toolchain.py /opt/fleet-rebuilder/install_toolchain.py
COPY containers/android-preview12-rebuilder/toolchain.lock.json /opt/fleet-rebuilder/toolchain.lock.json
COPY containers/android-preview12-rebuilder/bootstrap.py /opt/fleet-rebuilder/bootstrap.py
COPY scripts/android_preview12_external_rebuilder.py /opt/fleet-rebuilder/android_preview12_external_rebuilder.py
RUN /usr/bin/python3 -I -E -S /opt/fleet-rebuilder/bootstrap.py \
    && /usr/bin/python3 -I -E -S /opt/fleet-rebuilder/android_preview12_external_rebuilder.py --help

ENV PATH=/usr/bin:/bin \
    DOTNET_ROOT=/opt/dotnet \
    JAVA_HOME=/opt/jdk \
    ANDROID_HOME=/opt/android-sdk \
    DOTNET_CLI_TELEMETRY_OPTOUT=1
WORKDIR /transaction
# No key inputs, signing server, or activated workflow. Default entry only shows help.
ENTRYPOINT ["/usr/bin/python3", "-I", "-E", "-S", "/opt/fleet-rebuilder/android_preview12_external_rebuilder.py"]
CMD ["--help"]
