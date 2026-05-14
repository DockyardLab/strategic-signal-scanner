# Cloud Run Deployment Guide

This repository is ready to run as a **Cloud Run Job**.
That is the right fit for the scanner because the workflow is batch-based:

1. capture sources
2. score them with Gemini
3. render a report
4. rebuild the archive
5. optionally upload the artifacts to Cloud Storage

## Files added for Cloud Run

- `cloudrun_job.py` - batch entrypoint
- `Dockerfile` - container image definition
- `requirements.txt` - runtime dependencies
- `build_archive.py` - now accepts `--artifact-dir`

## Recommended Cloud Run shape

- **Service type**: Cloud Run Job
- **Schedule**: later, via Cloud Scheduler on Tuesday + Friday
- **Output store**: Google Cloud Storage bucket
- **Model scoring**: Gemini API key stored as a Secret

## Suggested environment variables

Set these on the Cloud Run Job:

```bash
RUN_GROUP=cloudrun
SCORE_MODE=gemini
GEMINI_MODEL=gemini-3.1-flash-lite-preview
ITEMS_PER_FEED=1
MAX_ARTICLES=30
MAX_AGE_DAYS=180
REPORT_MAX_AGE_DAYS=180
OUTPUT_DIR=/tmp/artifacts/rss
ARCHIVE_BUCKET=your-bucket-name
ARCHIVE_PREFIX=signal-archive
```

If you want a dry local test, switch the score mode to `mock`.

## Secrets

The scoring step uses a Gemini API key.
On Cloud Run, store it in Secret Manager and mount it as:

```bash
GEMINI_API_KEY
```

The code expects the environment variable name above.

## Storage

If `ARCHIVE_BUCKET` is set, the job uploads the generated artifacts to:

```text
gs://$ARCHIVE_BUCKET/$ARCHIVE_PREFIX/
```

The uploaded files keep the same relative layout, so:

- `archive_index.html`
- `report_YYYY-MM-DD.html`
- `scored_YYYY-MM-DD.json`
- `raw_YYYY-MM-DD.json`

all stay linkable to each other.

## Deploy from source

From the repository root:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com secretmanager.googleapis.com

gcloud run jobs deploy strategic-signal-scanner \
  --source . \
  --region asia-east1 \
  --task-timeout 3600 \
  --max-retries 1 \
  --set-env-vars RUN_GROUP=cloudrun,SCORE_MODE=gemini,GEMINI_MODEL=gemini-3.1-flash-lite-preview,ITEMS_PER_FEED=1,MAX_ARTICLES=30,MAX_AGE_DAYS=180,REPORT_MAX_AGE_DAYS=180,OUTPUT_DIR=/tmp/artifacts/rss,ARCHIVE_BUCKET=YOUR_BUCKET,ARCHIVE_PREFIX=signal-archive \
  --set-secrets GEMINI_API_KEY=YOUR_GEMINI_SECRET:latest
```

## Run it manually

```bash
gcloud run jobs execute strategic-signal-scanner --region asia-east1
```

## Schedule it for Tuesday / Friday

Cloud Scheduler can trigger the job twice a week once the Job exists.
The recommended cadence is:

- Tuesday
- Friday

Use the Scheduler to call the Cloud Run Jobs `:run` endpoint with the
job's service account and OIDC auth.
This can be added after the first manual job run is verified.

## Local smoke test

Before deploying, you can test the batch locally:

```bash
SCORE_MODE=mock RUN_GROUP=cloudrun ITEMS_PER_FEED=1 MAX_ARTICLES=5 OUTPUT_DIR=/tmp/strategy-agent-cloudrun python3 cloudrun_job.py
```

This will generate:

- `raw_YYYY-MM-DD.json`
- `scored_YYYY-MM-DD.json`
- `report_YYYY-MM-DD.html`
- `archive_index.html`

in the output directory.
