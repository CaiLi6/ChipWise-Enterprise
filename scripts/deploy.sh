#!/usr/bin/env bash
# ChipWise Enterprise — local CD helper.
#
# Pulls the published GHCR image at TAG (default "latest") and rolls
# the FastAPI gateway + Celery workers + web frontend forward, then
# smoke-tests /readiness.
#
# Usage:
#   scripts/deploy.sh                # pull :latest and restart
#   scripts/deploy.sh 6f83590        # pin to a git short SHA
#   DRY_RUN=1 scripts/deploy.sh      # print actions without running
#
# Environment overrides:
#   IMAGE_REPO       ghcr.io/<owner>/<repo>  (auto-detected from `git remote`)
#   COMPOSE_FILE     docker-compose.prod.yml
#   READINESS_URL    http://localhost:8080/readiness
#   HEALTH_TIMEOUT   60      seconds to wait for /readiness=200

set -euo pipefail

TAG="${1:-latest}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
READINESS_URL="${READINESS_URL:-http://localhost:8080/readiness}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"

if [[ -z "${IMAGE_REPO:-}" ]]; then
  remote_url=$(git config --get remote.origin.url || true)
  owner_repo=$(echo "$remote_url" \
    | sed -E 's#(git@|https://)github.com[:/](.+)\.git#\2#' \
    | tr '[:upper:]' '[:lower:]')
  if [[ -z "$owner_repo" ]]; then
    echo "❌ cannot derive IMAGE_REPO from git remote; export IMAGE_REPO manually" >&2
    exit 1
  fi
  IMAGE_REPO="ghcr.io/${owner_repo}"
fi

API_IMAGE="${IMAGE_REPO}/api:${TAG}"
CELERY_IMAGE="${IMAGE_REPO}/celery:${TAG}"
WEB_IMAGE="${IMAGE_REPO}/web:${TAG}"

run() {
  echo "▸ $*"
  if [[ "${DRY_RUN:-0}" != "1" ]]; then
    eval "$@"
  fi
}

echo "🚀 ChipWise CD — tag=${TAG}"
echo "   API:    ${API_IMAGE}"
echo "   Celery: ${CELERY_IMAGE}"
echo "   Web:    ${WEB_IMAGE}"
echo

echo "── 1/4 git pull (config & migrations may have changed)"
run "git pull --ff-only"

echo "── 2/4 docker pull"
run "docker pull '${API_IMAGE}'"
run "docker pull '${CELERY_IMAGE}'"
run "docker pull '${WEB_IMAGE}'"

echo "── 3/4 docker compose up -d (only app services, leave PG/Milvus/Redis intact)"
export API_IMAGE CELERY_IMAGE WEB_IMAGE
APP_SERVICES="api celery-default celery-heavy celery-crawler celery-beat frontend-web"
# Filter to services that actually exist in this compose file (use raw grep
# so we don't need PG/Milvus to be defined in this file for `config` to work).
EXISTING=""
for svc in $APP_SERVICES; do
  if grep -qE "^  ${svc}:" "$COMPOSE_FILE"; then
    EXISTING="$EXISTING $svc"
  fi
done
if [[ -z "$EXISTING" ]]; then
  echo "❌ none of the app services found in $COMPOSE_FILE" >&2
  exit 1
fi
run "docker compose -f '$COMPOSE_FILE' up -d --no-deps --remove-orphans $EXISTING"

echo "── 4/4 smoke test /readiness (timeout=${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
ok=0
while [[ $(date +%s) -lt $deadline ]]; do
  if curl -sf -o /dev/null "$READINESS_URL"; then
    ok=1
    break
  fi
  sleep 2
done

if [[ $ok -eq 1 ]]; then
  echo "✅ /readiness responded OK — deploy complete"
  echo
  curl -s "$READINESS_URL" | head -c 800; echo
else
  echo "❌ /readiness did not return 2xx within ${HEALTH_TIMEOUT}s" >&2
  echo "   inspect: docker compose -f '$COMPOSE_FILE' logs --tail 80 api" >&2
  exit 1
fi
