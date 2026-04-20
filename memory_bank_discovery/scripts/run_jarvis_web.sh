#!/usr/bin/env bash
# Starts `adk web` with Vertex AI Memory Bank wired in for the Jarvis agent.
#
# Sources AGENT_ENGINE_ID from memory_bank_discovery/.env and passes it to
# adk via --memory_service_uri=agentengine://<engine_id>. The agentengine://
# URI scheme accepts either the short engine ID or the full resource name.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MEM_ENV="$REPO_ROOT/memory_bank_discovery/.env"

if [[ ! -f "$MEM_ENV" ]]; then
  echo "ERROR: $MEM_ENV not found." >&2
  exit 1
fi

# Load AGENT_ENGINE_ID (and any other memory-discovery env vars).
set -a
# shellcheck disable=SC1090
source "$MEM_ENV"
set +a

if [[ -z "${AGENT_ENGINE_ID:-}" ]]; then
  echo "ERROR: AGENT_ENGINE_ID not set after sourcing $MEM_ENV" >&2
  exit 1
fi

cd "$REPO_ROOT"

echo "Starting adk web with Memory Bank wired in."
echo "  Engine: $AGENT_ENGINE_ID"
echo "  Agents dir: $REPO_ROOT"

exec adk web --memory_service_uri="agentengine://$AGENT_ENGINE_ID" .
