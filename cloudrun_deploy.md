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
- **Schedule**: Cloud Scheduler on Tuesday + Friday
- **Output store**: Google Cloud Storage bucket
- **Model scoring**: Vertex AI on Cloud Run

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
ARCHIVE_BUCKET=YOUR_BUCKET_NAME
ARCHIVE_PREFIX=signal-archive
```

If you want a dry local test, switch the score mode to `mock`.

## Secrets

The Cloud Run job currently supports two backends:

- `vertex` for Cloud Run
- `api_key` for local / Cloud Shell smoke tests

For the Cloud Run deployment we use Vertex AI, so the job needs:

- `GEMINI_BACKEND=vertex`
- `GEMINI_PROJECT=YOUR_PROJECT_ID`
- `GEMINI_LOCATION=global`
- `GEMINI_MODEL=gemini-2.5-flash-lite`

The `GEMINI_API_KEY` secret can stay mounted for local compatibility, but the Cloud Run job does not rely on it in Vertex mode.

## Email notification

Cloud Run can send a summary email after each successful run by using SMTP.

Recommended environment variables:

```bash
MAIL_BACKEND=smtp
MAIL_TO=YOUR_RECIPIENT_EMAIL
MAIL_FROM='Strategic Signal Scanner <your-gmail-address@example.com>'
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-gmail-address@example.com
SMTP_PASSWORD=your-gmail-app-password
```

Notes:

- For Gmail, the simplest path is an **App Password**.
- Keep `SMTP_PASSWORD` in Secret Manager instead of plain text.
- The Job will skip email safely if `MAIL_TO` is not set.
- The message body uses a neutral project signature.

Recommended secret setup:

```bash
gcloud secrets create SMTP_PASSWORD --replication-policy=automatic
read -s -p "Paste Gmail app password: " SMTP_PASSWORD_VALUE; echo
printf '%s' "$SMTP_PASSWORD_VALUE" | gcloud secrets versions add SMTP_PASSWORD --data-file=-
unset SMTP_PASSWORD_VALUE
```

Then mount it on the Cloud Run Job:

```bash
--set-secrets SMTP_PASSWORD=SMTP_PASSWORD:latest
```

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

If the bucket is made public, the archive can be accessed directly with:

```text
https://storage.googleapis.com/YOUR_BUCKET_NAME/signal-archive/archive_index.html
```

and each daily report:

```text
https://storage.googleapis.com/YOUR_BUCKET_NAME/signal-archive/report_YYYY-MM-DD.html
```

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
  --set-env-vars RUN_GROUP=cloudrun,SCORE_MODE=gemini,GEMINI_MODEL=gemini-3.1-flash-lite-preview,ITEMS_PER_FEED=1,MAX_ARTICLES=30,MAX_AGE_DAYS=180,REPORT_MAX_AGE_DAYS=180,OUTPUT_DIR=/tmp/artifacts/rss,ARCHIVE_BUCKET=YOUR_BUCKET_NAME,ARCHIVE_PREFIX=signal-archive \
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

The Cloud Scheduler job should call the Cloud Run Jobs `:run` endpoint:

```text
https://run.googleapis.com/v2/projects/YOUR_PROJECT_ID/locations/asia-east1/jobs/strategic-signal-scanner:run
```

Use a dedicated scheduler service account with `roles/run.invoker` on the job.

Example setup:

```bash
gcloud services enable cloudscheduler.googleapis.com

gcloud iam service-accounts create signal-archive-scheduler \
  --display-name="Signal Archive Scheduler"

gcloud run jobs add-iam-policy-binding strategic-signal-scanner \
  --region asia-east1 \
  --member="serviceAccount:signal-archive-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud scheduler jobs create http strategic-signal-scanner-schedule \
  --location asia-east1 \
  --schedule="0 9 * * 2,5" \
  --time-zone="Asia/Shanghai" \
  --uri="https://run.googleapis.com/v2/projects/YOUR_PROJECT_ID/locations/asia-east1/jobs/strategic-signal-scanner:run" \
  --http-method POST \
  --oauth-service-account-email="signal-archive-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
```

If you want to force a one-off run from Scheduler later, use:

```bash
gcloud scheduler jobs run strategic-signal-scanner-schedule --location asia-east1
```

To verify whether the Scheduler job exists:

```bash
gcloud scheduler jobs list --location asia-east1
gcloud scheduler jobs describe strategic-signal-scanner-schedule --location asia-east1
```

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
