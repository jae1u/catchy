FROM ubuntu:26.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN npm i -g @openai/codex
ENV CODEX_HOME=/workspace/.codex
COPY config.toml /workspace/.codex/config.toml
WORKDIR /workspace