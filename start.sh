#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'Docker is not installed. Install and start Docker Desktop:' 'https://docs.docker.com/get-docker/' 'You do not need Node.js, npm, Python, or PostgreSQL on your computer.'
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' 'Docker Compose v2 is required: https://docs.docker.com/compose/install/'
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' 'Docker is installed but not running. Start Docker Desktop, then run this script again.'
  exit 1
fi
printf '%s\n' 'Building the application and starting PostgreSQL. The first run downloads dependencies.'
docker compose up --build -d --wait
printf '%s\n' 'Ready: http://localhost:8000' 'Stop with: docker compose down'
