#!/usr/bin/env bash
# One-time Hetzner (Ubuntu 24.04) bootstrap. Run as root on a fresh VPS:
#   curl -fsSL https://raw.githubusercontent.com/YOUR_USER/spider-python/master/deploy/bootstrap.sh | bash
# Or copy this repo and: sudo bash deploy/bootstrap.sh
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/spider}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if ! id "${DEPLOY_USER}" &>/dev/null; then
  useradd -m -s /bin/bash "${DEPLOY_USER}"
fi
usermod -aG docker "${DEPLOY_USER}"

mkdir -p "${APP_DIR}/deploy"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  if [[ -f "${APP_DIR}/deploy/env.example" ]]; then
    cp "${APP_DIR}/deploy/env.example" "${APP_DIR}/.env"
  else
  cat >"${APP_DIR}/.env" <<'EOF'
SPIDER_IMAGE=ghcr.io/YOUR_GITHUB_USER/spider-python
IMAGE_TAG=latest
POSTGRES_PASSWORD=change-me-long-random
DOMAIN=spider.example.com
ACME_EMAIL=you@example.com
SESSION_COOKIE_SECURE=true
CORS_ORIGINS=https://spider.example.com
EOF
  fi
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env — edit before first deploy."
fi

echo ""
echo "Bootstrap done."
echo "  1. Add SSH public key for ${DEPLOY_USER} (~${DEPLOY_USER}/.ssh/authorized_keys)"
echo "  2. Edit ${APP_DIR}/.env (SPIDER_IMAGE, POSTGRES_PASSWORD, DOMAIN, …)"
echo "  3. Point DNS for DOMAIN to this server"
echo "  4. Configure GitHub Actions secrets (see deploy/README.md)"
echo "  5. Push to main/master to deploy"
