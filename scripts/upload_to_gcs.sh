#!/usr/bin/env bash
set -euo pipefail

: "${BUCKET_NAME:?Set BUCKET_NAME first}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python "$ROOT/scripts/build_metadata.py" --bucket "$BUCKET_NAME"

gcloud storage cp "$ROOT/docs/private_kb/"*.txt "gs://$BUCKET_NAME/documents/"
gcloud storage cp "$ROOT/generated/metadata.jsonl" "gs://$BUCKET_NAME/metadata/metadata.jsonl"

echo "Uploaded documents and metadata to gs://$BUCKET_NAME"
