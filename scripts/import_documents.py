#!/usr/bin/env python3
"""Run an INCREMENTAL Agent Search import from JSONL metadata in GCS."""
from __future__ import annotations

import os
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as discoveryengine

load_dotenv()

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
DATA_STORE_ID = os.environ["DATA_STORE_ID"]
METADATA_GCS_URI = os.environ["METADATA_GCS_URI"]


def main() -> None:
    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=PROJECT_ID,
        location=LOCATION,
        data_store=DATA_STORE_ID,
        branch="default_branch",
    )

    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=discoveryengine.GcsSource(
            input_uris=[METADATA_GCS_URI],
            data_schema="custom",
        ),
        reconciliation_mode=(
            discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL
        ),
    )

    operation = client.import_documents(request=request)
    print(f"Import operation: {operation.operation.name}")
    response = operation.result()
    print("Import completed")
    print(response)


if __name__ == "__main__":
    main()
