FROM ubuntu:26.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN npm i -g @openai/codex
ENV CODEX_HOME=/.codex
COPY config.toml /.codex/config.toml
WORKDIR /challenge