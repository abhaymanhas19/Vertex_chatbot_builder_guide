#!/usr/bin/env python3
"""Convert a Takeout-style .mbox into one TXT file per approximate email thread.

This is intentionally simple and auditable for learning. For production archives,
validate thread reconstruction against the source archive because mailing-list
headers differ between providers.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import mailbox
import re
from collections import defaultdict
from email.header import decode_header, make_header
from pathlib import Path


def decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def normalize_subject(subject: str) -> str:
    s = decode(subject).strip()
    while re.match(r"^(re|fw|fwd)\s*:\s*", s, flags=re.I):
        s = re.sub(r"^(re|fw|fwd)\s*:\s*", "", s, count=1, flags=re.I).strip()
    return re.sub(r"\s+", " ", s).lower()


def get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        candidates = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp.lower():
                try:
                    candidates.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace"))
                except Exception:
                    pass
        body = "\n".join(candidates)
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            body = str(msg.get_payload())
        else:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return strip_quoted_reply(body)


def strip_quoted_reply(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        if re.match(r"^On .+ wrote:$", line.strip(), flags=re.I):
            break
        if line.strip() in {"-----Original Message-----", "________________________________"}:
            break
        kept.append(line)
    return "\n".join(kept).strip()


def thread_key(msg: email.message.Message) -> str:
    # Subject is used as a fallback learning implementation. Production systems
    # should prefer reliable provider/list thread identifiers where available.
    subject = normalize_subject(msg.get("Subject", "")) or "no-subject"
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:20]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mbox")
    ap.add_argument("--out", default="converted_threads")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)

    box = mailbox.mbox(args.mbox)
    for msg in box:
        groups[thread_key(msg)].append(msg)

    for key, msgs in groups.items():
        msgs.sort(key=lambda m: m.get("Date", ""))
        subject = decode(msgs[0].get("Subject")) or "(no subject)"
        path = out / f"thread-{key}.txt"
        with path.open("w", encoding="utf-8") as f:
            f.write(f"Subject: {subject}\n")
            f.write(f"Message count: {len(msgs)}\n\n")
            for i, msg in enumerate(msgs, 1):
                f.write(f"--- Message {i} ---\n")
                f.write(f"From: {decode(msg.get('From'))}\n")
                f.write(f"Date: {decode(msg.get('Date'))}\n")
                f.write(get_body(msg))
                f.write("\n\n")
        print(path)

    print(f"Created {len(groups)} thread files in {out}")


if __name__ == "__main__":
    main()
