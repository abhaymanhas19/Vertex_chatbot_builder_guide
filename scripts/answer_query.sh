#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${ENGINE_ID:?Set ENGINE_ID}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
QUERY="${1:-How long does a password reset link last?}"

python - "$QUERY" <<'PY' > /tmp/agent-search-answer.json
import json, sys
query = sys.argv[1]
payload = {
    "query": {"text": query},
    "answerGenerationSpec": {
        "includeCitations": True,
        "ignoreLowRelevantContent": True,
        "promptSpec": {
            "preamble": (
                "Answer only from the retrieved private knowledge base. "
                "If the retrieved sources do not contain enough information, "
                "state that the knowledge base does not provide enough information. "
                "Do not guess or invent company policy."
            )
        }
    }
}
print(json.dumps(payload))
PY

curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://discoveryengine.googleapis.com/v1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/collections/default_collection/engines/${ENGINE_ID}/servingConfigs/default_search:answer" \
  -d @/tmp/agent-search-answer.json

echo
