# OMuse as a single container (Docker Desktop / any Docker host), instead of the Olares chart.
#   docker build -t omuse .
#   docker run -d --name omuse --restart unless-stopped -p 8080:8080 -v omuse-data:/omuse \
#     -e OMUSE_PASSWORD=... -e OMUSE_MODEL_URL=https://api.openai.com/v1 -e OMUSE_MODEL=gpt-4.1 \
#     -e OMUSE_MODEL_API_KEY=sk-... omuse
# Same base as the chart's browser container: Chromium + Xvfb + Python 3.12, for amd64 and arm64.
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends tini tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/omuse
COPY requirements.txt requirements-browser.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt -r requirements-browser.txt playwright==1.56.0

COPY app ./app
COPY deploy/docker ./deploy/docker

# Release builds pass the git tag (e.g. locius-v0.3.1); the app shows it as v0.3.1. Empty = version from the source.
ARG OMUSE_VERSION=
ENV OMUSE_VERSION=$OMUSE_VERSION

# all state (vault, audit log, memory, workspace files, browser profile) lives in one volume
RUN mkdir -p /omuse && chown pwuser:pwuser /omuse
VOLUME /omuse
USER pwuser

ENV HOME=/home/pwuser \
    TZ=UTC \
    OMUSE_DATA=/omuse \
    OMUSE_MODEL_URL=https://api.openai.com/v1 \
    OMUSE_MODEL=gpt-4.1 \
    VOICE_PORT=8083

# 8080: web UI (password protected). 8083: phone-call media/webhooks, only needed for the Telnyx phone line.
EXPOSE 8080 8083
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/sentinel/api/health || exit 1
ENTRYPOINT ["tini", "--", "/opt/omuse/deploy/docker/entrypoint.sh"]
