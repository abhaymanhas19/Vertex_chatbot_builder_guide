#!/usr/bin/env python3
"""Build Agent Search JSONL metadata for the synthetic private knowledge base.

Usage:
  python scripts/build_metadata.py --bucket YOUR_BUCKET
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs" / "private_kb"
OUT_DIR = ROOT / "generated"
OUT_FILE = OUT_DIR / "metadata.jsonl"


def stable_id(filename: str) -> str:
    stem = Path(filename).stem.lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", stem).strip("-")
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
    # RFC-1034-friendly ID, stable across imports as long as filename remains stable.
    return f"{slug}-{digest}"[:63].strip("-")


def title_from_text(path: Path) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    return first.replace("ACME PRIVATE KNOWLEDGE BASE — ", "").title()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="GCS bucket name, without gs://")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    records = []
    for path in sorted(DOCS_DIR.glob("*.txt")):
        doc_id = stable_id(path.name)
        record = {
            "id": doc_id,
            "structData": {
                "title": title_from_text(path),
                "source_type": "internal_training_doc",
                "classification": "internal",
                "filename": path.name,
            },
            "content": {
                "mimeType": "text/plain",
                "uri": f"gs://{args.bucket}/documents/{path.name}",
            },
        }
        records.append(record)

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {OUT_FILE}")


if __name__ == "__main__":
    main()
