#!/usr/bin/env bash
# Build the backend Docker image and push it to Alibaba Container Registry (ACR).
#
# Required environment variables:
#   ACR_REGISTRY   Alibaba Cloud registry host
#                  e.g. registry.cn-hangzhou.aliyuncs.com
#   ACR_NAMESPACE  Your registry namespace (created in the ACR console)
#                  e.g. my-company
#
# Optional:
#   IMAGE_TAG      Tag to apply (default: latest)
#                  Use a git SHA for reproducible deployments:
#                  IMAGE_TAG=$(git rev-parse --short HEAD)
#
# Usage:
#   ACR_REGISTRY=registry.cn-hangzhou.aliyuncs.com \
#   ACR_NAMESPACE=my-company \
#   IMAGE_TAG=1.0.0 \
#   ./scripts/push-to-acr.sh

set -euo pipefail

# ── Validate inputs ──────────────────────────────────────────────────────────
: "${ACR_REGISTRY:?Set ACR_REGISTRY to your ACR host, e.g. registry.cn-hangzhou.aliyuncs.com}"
: "${ACR_NAMESPACE:?Set ACR_NAMESPACE to your ACR namespace}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

REPO="${ACR_REGISTRY}/${ACR_NAMESPACE}/businesspilot-api"
FULL_IMAGE="${REPO}:${IMAGE_TAG}"

# ── Locate repository root ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"

echo "==> Build context : ${BACKEND_DIR}"
echo "==> Image         : ${FULL_IMAGE}"
echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
# The build context is ONLY ./backend — the frontend directory is never included.
docker build \
  --platform linux/amd64 \
  --tag "${FULL_IMAGE}" \
  --tag "${REPO}:latest" \
  "${BACKEND_DIR}"

echo ""
echo "==> Build complete. Pushing to ACR..."

# ── Push ──────────────────────────────────────────────────────────────────────
# Log in first if not already authenticated:
#   docker login "${ACR_REGISTRY}" -u <your-RAM-user> -p <your-password>
docker push "${FULL_IMAGE}"
docker push "${REPO}:latest"

echo ""
echo "==> Done."
echo "    Tagged : ${FULL_IMAGE}"
echo "    Latest : ${REPO}:latest"
echo ""
echo "Deploy with:"
echo "  ACR_IMAGE=${FULL_IMAGE} \\"
echo "    docker compose -f docker-compose.prod.yml up -d"
