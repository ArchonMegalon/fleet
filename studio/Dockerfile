FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      git \
      gnupg \
      jq \
      nodejs \
      npm \
      ripgrep \
      unzip \
      xz-utils \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb \
 && dpkg -i /tmp/packages-microsoft-prod.deb \
 && rm /tmp/packages-microsoft-prod.deb \
 && apt-get update \
 && apt-get install -y --no-install-recommends dotnet-sdk-8.0 dotnet-sdk-10.0 \
 && rm -rf /var/lib/apt/lists/*

ARG CODEX_NPM_REFRESH_TOKEN=static
ARG OPENAI_CODEX_VERSION=0.118.0
RUN echo "$CODEX_NPM_REFRESH_TOKEN" >/tmp/.codex-refresh-token \
 && npm install -g "@openai/codex@${OPENAI_CODEX_VERSION}"

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app.py /app/app.py

EXPOSE 8091
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091"]
