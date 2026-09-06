FROM docker.io/library/python:3.12.11-slim-bookworm@sha256:c00fc7b44d844b6da22861ec24af43968a5200eac4ec607b4725d585165d6b49 AS python
FROM mcr.microsoft.com/dotnet/sdk:8.0.424-bookworm-slim-amd64@sha256:237133a0ea20cffcfaa92588e1c8a56d58fe99f44da72dcff35aeb017119abcf

COPY --from=python /usr/local /usr/local
COPY config/release/android-preview12-signer-toolchain.lock.json /opt/fleet-signer/toolchain.lock.json
COPY containers/android-preview12-signer/install_toolchain.py /opt/fleet-signer/install_toolchain.py
RUN python3 /opt/fleet-signer/install_toolchain.py \
      /opt/fleet-signer/toolchain.lock.json \
      /opt/fleet-signer/toolchain-installed.json \
    && /opt/jdk/bin/java -version \
    && dotnet --version \
    && /opt/android-sdk/build-tools/35.0.0/aapt2 version \
    && /opt/jdk/bin/java -jar /opt/android-sdk/tools/bundletool.jar version

COPY scripts/android_preview12_signer.py /opt/fleet-signer/android_preview12_signer.py

ENV ANDROID_HOME=/opt/android-sdk \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    JAVA_HOME=/opt/jdk \
    PATH=/opt/jdk/bin:/opt/dotnet:/opt/android-sdk/build-tools/35.0.0:/usr/local/bin:/usr/bin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /transaction
CMD ["python3", "/opt/fleet-signer/android_preview12_signer.py", "--help"]
