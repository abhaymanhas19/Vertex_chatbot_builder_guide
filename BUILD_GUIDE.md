# Build a Private-Document Search Chatbot with Google Cloud Agent Search

This guide takes you from an empty Google Cloud project to a working chatbot that answers questions from a private document collection, cites sources, and declines to invent answers when the documents do not contain enough evidence.

The repository includes a **synthetic private knowledge base** for a fictional company named AcmeDesk. It is safe for learning and can later be replaced by your own PDFs, TXT files, exported forum threads, or Google Takeout `.mbox` data.

> Product naming note: Google currently documents this capability under **Agent Search / AI Applications**. Older tutorials and job posts may call it **Vertex AI Search**, **Generative AI App Builder**, or **Agent Builder**. The underlying search service/API is Discovery Engine.

---

## 1. What you are building

Architecture:

```text
Private documents / forum export
          |
          v
     Cloud Storage
          |
          v
  Agent Search data store
  - parses documents
  - chunks content
  - indexes text
  - stores metadata
          |
          v
     Search application
          |
          +----> Retrieval results
          |
          +----> Grounded generated answer
                 + citations
                 + low-evidence fallback
          |
          v
   Search widget / your own UI
```

The key idea is Retrieval-Augmented Generation (RAG): the model does not need to memorize your private content. Search first retrieves relevant passages, and the answer model generates a response from those passages.

---

## 2. What is inside this starter ZIP

```text
vertex_search_chatbot_starter/
  BUILD_GUIDE.md
  README.md
  .env.example
  requirements.txt

  docs/private_kb/
    01_product_overview.txt
    ...
    12_known_limitations.txt

  evaluation/questions.csv

  scripts/
    build_metadata.py
    upload_to_gcs.sh
    import_documents.py
    answer_query.sh
    search_cli.py
    mbox_to_threads.py

  web/
    widget-template.html

  cloudrun/
    Dockerfile
    Dockerfile.takeout
    process_takeout_job.py
```

The private documents are fictional. They deliberately contain facts such as password reset policy, SSO troubleshooting, API limits, retention, incident information, and webhook behavior. The evaluation set includes questions that should be answered and questions that should be refused.

---

## 3. Prerequisites

You need:

1. A Google account with access to Google Cloud.
2. A Google Cloud project with billing enabled.
3. Permission to create Cloud Storage buckets and Agent Search resources.

You **do not need to install software on your work computer** if you use **Google Cloud Shell**. Cloud Shell already includes `gcloud`, a terminal, Python, and an editor.

For the first build, use Cloud Shell. Once the system works, move repeated ingestion into a Cloud Run Job.

---

## 4. Create or select a Google Cloud project

Open Google Cloud Console and create a project, for example:

```text
acme-private-search-lab
```

Open Cloud Shell and set the project:

```bash
gcloud config set project YOUR_PROJECT_ID
```

Confirm:

```bash
gcloud config get-value project
```

Set useful shell variables:

```bash
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="global"
```

Agent Search is commonly created in the `global` location. Keep the location consistent between the data store, app, and API calls.

---

## 5. Enable required APIs

From Cloud Shell:

```bash
gcloud services enable \
  discoveryengine.googleapis.com \
  storage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

The most important API is:

```text
discoveryengine.googleapis.com
```

That is the service behind Agent Search / Vertex AI Search.

---

## 6. Upload this starter project to Cloud Shell

Download the ZIP from ChatGPT, then in Cloud Shell use **Upload file** and upload the ZIP.

Extract it:

```bash
unzip vertex_search_chatbot_starter.zip
cd vertex_search_chatbot_starter
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Application Default Credentials are normally available in Cloud Shell. If you run locally instead, you may need:

```bash
gcloud auth application-default login
```

---

## 7. Inspect the sample private documents

Run:

```bash
ls docs/private_kb
```

Read one:

```bash
cat docs/private_kb/03_sso_troubleshooting.txt
```

The goal is to create a chatbot that can answer questions such as:

```text
What usually causes an invalid audience SSO error?
```

and cite the SSO document.

It should also handle:

```text
What is the CEO's home address?
```

by stating that the knowledge base does not provide enough information.

That second behavior is just as important as the first.

---

## 8. Create a private Cloud Storage bucket

Choose a globally unique bucket name:

```bash
export BUCKET_NAME="YOUR_PROJECT_ID-private-search"
```

Create it, choosing an appropriate region for your real deployment. For a lab you can choose a nearby region, for example:

```bash
gcloud storage buckets create "gs://$BUCKET_NAME" \
  --location=us-central1 \
  --uniform-bucket-level-access
```

Do **not** make this bucket public.

Verify:

```bash
gcloud storage buckets describe "gs://$BUCKET_NAME"
```

---

## 9. Build metadata with stable document IDs

Run:

```bash
python scripts/build_metadata.py --bucket "$BUCKET_NAME"
```

This creates:

```text
generated/metadata.jsonl
```

Inspect the first line:

```bash
head -1 generated/metadata.jsonl
```

A record looks conceptually like:

```json
{
  "id": "03-sso-troubleshooting-...",
  "structData": {
    "title": "Sso Troubleshooting",
    "source_type": "internal_training_doc",
    "classification": "internal",
    "filename": "03_sso_troubleshooting.txt"
  },
  "content": {
    "mimeType": "text/plain",
    "uri": "gs://YOUR_BUCKET/documents/03_sso_troubleshooting.txt"
  }
}
```

### Why stable IDs matter

Incremental imports are upserts. If an incoming document uses the same document ID, the existing document can be replaced rather than duplicated.

For a production forum archive, derive the ID from a stable thread identifier if one exists. Avoid using random UUIDs every time you export the same archive.

---

## 10. Upload documents and metadata

Set the variable and run:

```bash
export BUCKET_NAME="YOUR_BUCKET_NAME"
./scripts/upload_to_gcs.sh
```

Verify:

```bash
gcloud storage ls "gs://$BUCKET_NAME/documents/"
gcloud storage ls "gs://$BUCKET_NAME/metadata/"
```

At this point the documents are in private Cloud Storage, but they are not searchable yet.

---

## 11. Create the Agent Search data store

Use the Google Cloud Console for the first build because it makes the configuration visible.

Go to:

```text
Google Cloud Console
→ AI Applications
→ Data Stores
→ Create data store
```

Choose a Cloud Storage / unstructured-document source.

Important choices:

- Data type: **Unstructured documents**
- Search use case: **Custom/general search**
- Location: use the location you chose for Agent Search, commonly `global`
- Source: your Cloud Storage metadata JSONL
- Enable **document chunking** during creation

### Critical chunking warning

Google currently documents that document chunking **cannot be turned on or off after the data store is created**. If you want RAG-style chunk retrieval, enable chunking now.

For a learning project, start with the default chunk size. Google currently documents a default of 500 tokens and a supported layout-aware range of 100–500 tokens.

For TXT forum threads, start simple. You can later test whether preprocessing one message per block or producing your own thread/message boundaries improves retrieval.

Give the data store an ID such as:

```text
acme-private-kb
```

Save that ID:

```bash
export DATA_STORE_ID="acme-private-kb"
```

### If console import asks for your metadata file

Use:

```text
gs://YOUR_BUCKET/metadata/metadata.jsonl
```

The JSONL maps each document to its TXT object and supplies metadata.

---

## 12. Wait for indexing and inspect documents

The console should show import/indexing status.

Open your data store and verify that documents are present.

Check several records and confirm that fields such as these appear:

```text
title
source_type
classification
filename
```

Do not tune anything yet. First establish a working baseline.

---

## 13. Create the search application

In **AI Applications**:

```text
Apps
→ Create app
→ Search / Custom Search
```

Attach the data store you created.

Use an app ID such as:

```text
acme-private-search
```

Save it:

```bash
export ENGINE_ID="acme-private-search"
```

Google APIs often refer to the search app internally as an **engine**, which is why the scripts use `ENGINE_ID`.

---

## 14. Turn on generative responses

Open your app:

```text
AI Applications
→ Apps
→ acme-private-search
→ Configurations
→ Response Settings
```

Turn on the available **Generative Responses** / answer features required for generated answers.

Google notes that generative features can add cost, so review current pricing before using production traffic.

You want the app to perform two different tasks:

1. Retrieve relevant private documents/chunks.
2. Generate an answer grounded in those results.

---

## 15. Configure “do not guess” behavior

For API-based answer generation, use the following concepts:

```text
includeCitations = true
ignoreLowRelevantContent = true
custom prompt preamble
```

This starter includes:

```bash
./scripts/answer_query.sh "How long does a password reset link last?"
```

Before running it:

```bash
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="global"
export ENGINE_ID="acme-private-search"
```

The script sends a prompt preamble equivalent to:

```text
Answer only from the retrieved private knowledge base.
If the retrieved sources do not contain enough information,
state that the knowledge base does not provide enough information.
Do not guess or invent company policy.
```

It also asks Agent Search to include citations and to ignore low-relevance content.

Test an answerable query:

```bash
./scripts/answer_query.sh "What is the Standard API request limit?"
```

Expected fact:

```text
300 requests per minute
```

Then test an unsupported query:

```bash
./scripts/answer_query.sh "What is the CEO's home address?"
```

Desired behavior:

```text
The private knowledge base does not provide enough information.
```

The exact wording may differ, but it should not invent an address.

---

## 16. Evaluate retrieval before blaming the LLM

Open:

```text
evaluation/questions.csv
```

It contains 15 questions.

For each query record:

```text
1. Was the expected document retrieved?
2. Was it in the top 3?
3. Was the answer factually correct?
4. Was the citation correct?
5. Did unsupported questions get a fallback instead of a guess?
```

A simple scorecard:

```text
Top-3 retrieval hit rate = correct source in top 3 / answerable questions
Answer accuracy = correct answers / answerable questions
Refusal accuracy = proper refusals / unanswerable questions
Citation accuracy = correct citations / answered questions
```

Do not change five settings at once. Change one thing, re-run the same evaluation set, and compare.

---

## 17. Tune chunking

Chunking determines how much text is retrieved as one unit.

Too small:

```text
Relevant sentence is retrieved but important context is missing.
```

Too large:

```text
Relevant paragraph is buried in lots of unrelated text.
```

For the sample TXT files, defaults should be enough to learn the workflow.

For a real forum archive, test these alternatives:

### A. One file per entire thread

Good when threads are short and focused.

### B. One file per thread, Agent Search chunking enabled

Often a practical starting point.

### C. Pre-split by message or logical section

Useful when threads are extremely long or change topic.

Use the evaluation questions to determine which strategy actually improves retrieval.

---

## 18. Tune with metadata

This starter stores metadata such as:

```text
classification
source_type
filename
title
```

A real forum system should consider:

```text
thread_id
subject
participants
message_count
start_date
last_date
forum_name
category
source_url
```

Metadata is useful for:

- filtering
- user-facing labels
- citations
- ranking/boosting
- access-control logic

Example concepts:

```text
Only search the "engineering" forum
Only search documents after 2024
Prefer resolved incident threads
Boost official administrator posts
```

Do not boost a field only because it exists. Every boost should correspond to a hypothesis you can measure.

---

## 19. Ranking and serving controls

Agent Search supports serving controls such as boosting, burying, filtering, and synonyms.

Example hypotheses:

```text
Hypothesis A: newer troubleshooting threads should rank higher.
Hypothesis B: long active threads contain more useful solutions.
Hypothesis C: official staff posts should rank above casual discussion.
```

For each hypothesis:

```text
baseline → apply one control → run same evaluation set → compare
```

Keep the control only if it improves the metric that matters.

Do not let “newer” automatically mean “more correct.” Some historical archives contain definitive older answers.

---

## 20. Add the web widget

Open:

```text
AI Applications
→ your app
→ Integration
→ Widget
```

Google currently supports different authorization patterns, including public access and token-based access.

### For a public knowledge base

You can choose public widget access and restrict the widget to your web domain.

### For private/company-only documents

Do **not** expose the app publicly merely for convenience.

Use the token/OAuth/JWT option appropriate to your architecture and organization. Your backend or identity system should issue/obtain the authorization token expected by the widget.

Google's widget configuration UI provides the current HTML/JavaScript snippet. Copy that exact snippet rather than relying on an old tutorial, because widget attributes can change.

A placeholder page is included at:

```text
web/widget-template.html
```

Paste the generated snippet into that page.

For localhost testing, configure the allowed domain according to the widget UI/documentation.

---

## 21. Incremental refresh without duplicates

This is a core requirement for the original job description.

The target workflow is:

```text
new Takeout export
     |
     v
convert/update thread files
     |
     v
upload changed documents
     |
     v
rebuild metadata using SAME stable IDs
     |
     v
INCREMENTAL import
```

The starter includes:

```text
scripts/import_documents.py
```

Create a `.env` file from the sample:

```bash
cp .env.example .env
```

Edit:

```text
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
DATA_STORE_ID=acme-private-kb
ENGINE_ID=acme-private-search
BUCKET_NAME=your-bucket
METADATA_GCS_URI=gs://your-bucket/metadata/metadata.jsonl
```

Then run:

```bash
python scripts/import_documents.py
```

It requests `INCREMENTAL` reconciliation.

With stable IDs:

```text
same ID + changed content = update/replace
new ID = new document
```

That is what prevents repeated exports from creating a second copy of the same logical thread.

### When FULL reconciliation is useful

A full reconciliation is useful when you intentionally want the data store to mirror the source and remove records that disappeared from the source. Do not use it casually until you understand its deletion behavior.

---

## 22. Simulate an update

Edit one sample document:

```bash
nano docs/private_kb/04_api_rate_limits.txt
```

For example, add a clearly marked test line.

Re-run:

```bash
./scripts/upload_to_gcs.sh
python scripts/import_documents.py
```

Then query the updated information.

Inspect the document count before and after. It should not create a duplicate for a document with the same stable ID.

This is the test you should perform before claiming that incremental updates are solved.

---

## 23. Convert a Google Takeout `.mbox`

A local learning converter is included:

```bash
python scripts/mbox_to_threads.py /path/to/forum.mbox --out converted_threads
```

It demonstrates:

- reading Python `mailbox.mbox`
- approximate thread grouping
- extracting plain-text email bodies
- removing `>` quoted lines
- creating one TXT file per thread

### Important production warning

The sample converter groups primarily by normalized subject. That is acceptable for learning but not necessarily robust enough for a real mailing-list archive.

A production converter should inspect the headers available in the actual export, such as:

```text
Message-ID
In-Reply-To
References
provider-specific thread/list identifiers
```

Build thread identity from the most stable provider/list identifiers available. Validate the converter against known threads before processing all 1.6 GB.

---

## 24. Cloud-side processing when software cannot be installed locally

There are two useful stages.

### Stage 1: use Cloud Shell

This already satisfies many “no local install” situations.

Upload the `.mbox` to Cloud Storage and run your parser from Cloud Shell.

### Stage 2: use a Cloud Run Job

For a repeatable production workflow:

```text
Browser upload to gs://bucket/raw/
        |
        v
Cloud Run Job
        |
        +-- downloads mbox
        +-- converts threads
        +-- uploads processed TXT files
        |
        v
metadata build + incremental import
```

A learning Cloud Run Job implementation is included:

```text
cloudrun/process_takeout_job.py
cloudrun/Dockerfile.takeout
```

Build it with Cloud Build:

```bash
gcloud builds submit \
  --tag "gcr.io/$GOOGLE_CLOUD_PROJECT/acme-takeout-processor" \
  -f cloudrun/Dockerfile.takeout .
```

If your Cloud Build command/environment requires Artifact Registry instead of Container Registry, create an Artifact Registry repository and use its image URL. Google Cloud's preferred image registry workflows evolve, so follow the current Cloud Run console prompt if it differs.

Create the job conceptually with:

```bash
gcloud run jobs create acme-takeout-processor \
  --image "YOUR_IMAGE_URL" \
  --region us-central1 \
  --set-env-vars "RAW_MBOX_GCS=gs://YOUR_BUCKET/raw/forum.mbox,OUTPUT_BUCKET=YOUR_BUCKET,OUTPUT_PREFIX=forum-threads"
```

Execute:

```bash
gcloud run jobs execute acme-takeout-processor --region us-central1
```

Then inspect:

```bash
gcloud storage ls "gs://YOUR_BUCKET/forum-threads/"
```

For production, extend the job to generate metadata and call the incremental import after successful conversion.

---

## 25. IAM and service accounts

Do not run a production ingestion pipeline with broad owner credentials.

Use a dedicated service account such as:

```text
forum-ingestion@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Grant only the permissions it needs, for example:

```text
read raw input objects
write processed objects
invoke the necessary Discovery Engine import operations
write logs
```

This is the principle of least privilege.

For private search users, separately design who is allowed to query the indexed content. Search authorization and ingestion authorization are different concerns.

---

## 26. Recommended production folder structure

For a real forum archive:

```text
gs://YOUR_BUCKET/
  raw/
    takeout-2026-10-01.mbox
    takeout-2026-11-01.mbox

  processed/
    threads/
      thread-a81c....txt
      thread-f72d....txt

  metadata/
    metadata.jsonl

  manifests/
    2026-10-01.json
    2026-11-01.json
```

A manifest can record:

```text
source export hash
processing time
script version
number of threads
number changed
number inserted
number failed
import operation ID
```

That makes the system auditable and easier to debug.

---

## 27. Duplicate prevention strategy

Use multiple protections:

### Stable logical ID

Example:

```text
thread ID from provider
```

or a deterministic hash derived from stable thread metadata.

### Content hash

Store a SHA-256 content hash in your manifest.

```text
same thread ID + same hash → skip upload/import
same thread ID + new hash  → update
new thread ID              → insert
```

### Never use the export date as the primary thread ID

Bad:

```text
2026-10-01-thread-123
2026-11-01-thread-123
```

Those become duplicates even though they represent the same thread.

Better:

```text
thread-123
```

with an updated document payload.

---

## 28. Citation quality

A technically generated citation is not enough if the source label is meaningless.

Good metadata:

```text
title: Authentication failure after v4 upgrade
thread_id: abc123
last_date: 2026-08-18
source_url: internal archive URL
```

A user should be able to understand where the answer came from and, when authorized, open the original source.

Test citations using the evaluation set.

---

## 29. “I don't know” testing

Create unsupported questions intentionally:

```text
What is the CEO's home address?
What will pricing be in 2030?
Which acquisition will the company announce next year?
```

The bot should not infer an answer from unrelated passages.

When it fails this test, investigate in this order:

```text
1. Did retrieval return irrelevant content?
2. Is low-relevance filtering enabled/configured appropriately?
3. Is the answer prompt telling it to avoid unsupported policy/facts?
4. Are broad documents creating misleading chunks?
5. Is your evaluation query ambiguous?
```

Do not attempt to solve every hallucination only by making the system prompt longer.

---

## 30. Security checklist before using real private content

Before indexing real company/forum data, confirm:

- The Cloud Storage bucket is not public.
- The source archive is permitted to be copied into Google Cloud.
- Your Google Cloud project is approved for this content.
- IAM follows least privilege.
- Logs do not accidentally record sensitive document content unnecessarily.
- The widget is not configured for public access when the content is private.
- Authorized users are clearly defined.
- Retention/deletion requirements are documented.
- You understand the implications of generated answers exposing indexed content to authorized users.

For regulated or highly sensitive data, involve the relevant security/legal/compliance owners instead of treating the demo architecture as a complete compliance design.

---

## 31. Practical tuning sequence

Use this order:

```text
1. Verify ingestion completeness.
2. Verify correct source documents are retrievable.
3. Enable/use chunking appropriately.
4. Improve metadata.
5. Build evaluation questions.
6. Fix retrieval failures.
7. Add filters/boosts only where measured.
8. Configure grounded answers + citations.
9. Test unsupported questions.
10. Test incremental updates.
11. Add authentication/sharing.
12. Automate ingestion.
```

This order prevents you from tuning generation on top of bad retrieval.

---

## 32. Minimum definition of “working”

Do not call the project finished until all of these are true:

### Data

- Documents exist in Cloud Storage.
- Metadata uses deterministic IDs.
- Data store reports successful ingestion.

### Retrieval

- At least the expected source appears in the top results for most evaluation questions.

### Generation

- Answerable questions are answered from the corpus.
- Citations point to correct sources.
- Unsupported questions produce a fallback instead of invented facts.

### Refresh

- Re-importing unchanged documents does not double the corpus.
- Updating one source updates the indexed content.
- New source documents can be added incrementally.

### Sharing

- Widget or application UI works.
- Authorization matches the sensitivity of the indexed content.

### Operations

- Logs show failed jobs/imports.
- Service account permissions are limited.
- Another person can follow the runbook without the original developer.

---

## 33. Suggested portfolio demo

Record a short demonstration showing:

1. The private documents in Cloud Storage.
2. The Agent Search data store.
3. A correct SSO question with citation.
4. A correct API rate-limit question with citation.
5. An unsupported question where the bot refuses to guess.
6. Edit one private document.
7. Run incremental import.
8. Ask again and show the updated answer.
9. Show the embedded/authenticated widget.

That demo directly maps to the skills in the job description.

---

## 34. Common mistakes

### Mistake: random IDs on every import

Result: duplicate logical documents.

Fix: deterministic/stable document IDs.

### Mistake: enabling chunking too late

Google currently documents that chunking cannot be toggled after data-store creation.

Fix: decide on chunking during data-store creation.

### Mistake: evaluating only happy-path questions

Result: chatbot appears impressive but hallucinates unsupported answers.

Fix: include explicit “no answer in corpus” questions.

### Mistake: making private search public

Result: data exposure risk.

Fix: token-based/OAuth/JWT access and proper identity controls where required.

### Mistake: changing ranking settings without measurement

Result: no idea whether quality improved.

Fix: fixed evaluation set and before/after scores.

### Mistake: treating a subject line as a perfect thread ID

Result: unrelated threads can merge; renamed subjects can split.

Fix: use real thread/reply identifiers when available in the source archive.

---

## 35. Current Google documentation used for this guide

These are useful references to check when the console/UI changes:

- Prepare data for ingesting:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/prepare-data

- Create a search data store:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/create-data-store-es

- Parse and chunk documents:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/parse-chunk-documents

- Custom search overview:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/about-generic-search

- Get answers and follow-ups:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/answer

- Metadata filtering:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata

- Serving controls / boosts:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/configure-serving-controls

- Add the search widget:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/add-widget

- Incremental Cloud Storage import example:
  https://docs.cloud.google.com/generative-ai-app-builder/docs/samples/genappbuilder-import-documents-gcs

Google Cloud product names, console labels, quotas, model versions, and pricing can change. Prefer the current documentation and the code snippet generated by your own Cloud Console when it conflicts with an older tutorial.

---

## 36. Next upgrade after you finish this lab

Replace the 12 fictional documents with 50–100 realistic forum threads and add metadata:

```text
thread_id
subject
participants
message_count
start_date
last_date
```

Then expand `evaluation/questions.csv` to at least 30–50 questions collected from real user needs.

That moves you from a demo to the same class of engineering problem described in the job posting.
