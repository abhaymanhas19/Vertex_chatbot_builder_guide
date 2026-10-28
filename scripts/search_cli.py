#!/usr/bin/env python3
"""Minimal command-line search smoke test for Agent Search."""
from __future__ import annotations

import argparse
import os
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as discoveryengine

load_dotenv()

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
ENGINE_ID = os.environ["ENGINE_ID"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Search query")
    args = parser.parse_args()

    client = discoveryengine.SearchServiceClient()
    serving_config = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/"
        f"engines/{ENGINE_ID}/servingConfigs/default_config"
    )

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=args.query,
        page_size=5,
    )

    response = client.search(request=request)
    for i, result in enumerate(response.results, start=1):
        doc = result.document
        print(f"\n[{i}] id={doc.id}")
        if doc.struct_data:
            print(dict(doc.struct_data))


if __name__ == "__main__":
    main()
