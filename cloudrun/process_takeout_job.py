#!/usr/bin/env python3
"""Cloud Run Job pattern for processing a raw .mbox from GCS.

Required env vars:
  RAW_MBOX_GCS=gs://bucket/raw/forum.mbox
  OUTPUT_BUCKET=bucket-name
  OUTPUT_PREFIX=forum-threads

This learning implementation groups by normalized subject. Adapt thread identity to
provider-specific headers before using it on a production archive.
"""
from __future__ import annotations

import hashlib
import mailbox
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from google.cloud import storage


def parse_gs(uri: str):
    u = urlparse(uri)
    if u.scheme != "gs":
        raise ValueError("Expected gs:// URI")
    return u.netloc, u.path.lstrip("/")


def normalize_subject(value: str) -> str:
    s = value or "(no subject)"
    while re.match(r"^(re|fw|fwd)\s*:\s*", s, flags=re.I):
        s = re.sub(r"^(re|fw|fwd)\s*:\s*", "", s, count=1, flags=re.I).strip()
    return re.sub(r"\s+", " ", s).lower()


def body(msg) -> str:
    parts = []
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition", "")).lower():
                data = p.get_payload(decode=True)
                if data:
                    parts.append(data.decode(p.get_content_charset() or "utf-8", errors="replace"))
    else:
        data = msg.get_payload(decode=True)
        if data:
            parts.append(data.decode(msg.get_content_charset() or "utf-8", errors="replace"))
    text = "\n".join(parts)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))


def main():
    raw_uri = os.environ["RAW_MBOX_GCS"]
    output_bucket = os.environ["OUTPUT_BUCKET"]
    prefix = os.getenv("OUTPUT_PREFIX", "forum-threads").strip("/")

    client = storage.Client()
    src_bucket, src_blob = parse_gs(raw_uri)

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "source.mbox"
        client.bucket(src_bucket).blob(src_blob).download_to_filename(local)

        groups = {}
        for msg in mailbox.mbox(local):
            normalized = normalize_subject(msg.get("Subject", ""))
            thread_id = hashlib.sha256(normalized.encode()).hexdigest()[:24]
            groups.setdefault(thread_id, []).append(msg)

        bucket = client.bucket(output_bucket)
        for thread_id, messages in groups.items():
            chunks = [f"Subject: {messages[0].get('Subject', '(no subject)')}\n"]
            for i, msg in enumerate(messages, 1):
                chunks.append(f"\n--- Message {i} ---\nFrom: {msg.get('From','')}\nDate: {msg.get('Date','')}\n{body(msg)}\n")
            bucket.blob(f"{prefix}/thread-{thread_id}.txt").upload_from_string("".join(chunks), content_type="text/plain")

        print(f"Uploaded {len(groups)} thread files to gs://{output_bucket}/{prefix}/")


if __name__ == "__main__":
    main()
