# Vertex AI / Agent Search Private Chatbot Starter

A hands-on learning project for building a Google Cloud private-document search chatbot with retrieval, grounded generated answers, citations, incremental imports, an embeddable widget, and optional `.mbox` processing.

Start here: **BUILD_GUIDE.md**

## Included sample corpus

`docs/private_kb/` contains 12 synthetic internal documents for fictional company **AcmeDesk**. They are not real private or proprietary data.

## Fast path

```bash
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="global"
export BUCKET_NAME="YOUR_BUCKET"

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/build_metadata.py --bucket "$BUCKET_NAME"
./scripts/upload_to_gcs.sh
```

Then create the Agent Search data store and app using the detailed guide.

## Important

Google Cloud console labels and feature names change over time. The guide was prepared against current Google Cloud documentation in October 2026 and links to the relevant official pages.
