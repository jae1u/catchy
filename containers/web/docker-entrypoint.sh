#!/usr/bin/env bash
set -euo pipefail

if [[ "${CATCHY_DIND:-1}" == "1" ]]; then
    mkdir -p /var/lib/docker /var/run

    if ! docker info >/dev/null 2>&1; then
        dockerd ${DOCKERD_ARGS:-} >/tmp/dockerd.log 2>&1 &

        for _ in $(seq 1 60); do
            if docker info >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        if ! docker info >/dev/null 2>&1; then
            cat /tmp/dockerd.log >&2
            exit 1
        fi
    fi
fi

mkdir -p "${CATCHY_DATA_DIR:-/data}"
mkdir -p \
    "$(dirname "${CATCHY_SQLITE_PATH:-${CATCHY_DATA_DIR:-/data}/db.sqlite3}")" \
    "${DJANGO_STATIC_ROOT:-${CATCHY_DATA_DIR:-/data}/staticfiles}" \
    "${DJANGO_MEDIA_ROOT:-${CATCHY_DATA_DIR:-/data}/media}"

if [[ "${CATCHY_COLLECTSTATIC:-1}" == "1" ]]; then
    python -m catchy.web.manage collectstatic --noinput
fi

if [[ "${CATCHY_MIGRATE:-1}" == "1" ]]; then
    python -m catchy.web.manage migrate --noinput
fi

exec "$@"
