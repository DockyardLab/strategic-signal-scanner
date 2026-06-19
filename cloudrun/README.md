# Cloud Run Guide

This folder contains the deployment notes for the Cloud Run Job version of Strategic Signal Scanner.

## What Cloud Run does

Cloud Run runs the batch workflow on a schedule:

1. capture sources
2. score the items with Gemini
3. render a daily HTML report
4. rebuild the archive index
5. upload artifacts to Cloud Storage
6. optionally send an email summary
7. record reader feedback when `FEEDBACK_BASE_URL` is configured

## Default Cloud Run group

The public deployment uses:

```bash
RUN_GROUP=cloudrun
```

Inside the code, `cloudrun` maps to the balanced source group.

## Common environment variables

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
FEEDBACK_BASE_URL=https://your-feedback-service-url
FEEDBACK_TOKEN=optional-shared-secret
```

## Feedback service

If you want the report buttons to record `like` / `dislike` clicks, deploy the companion feedback service from `tools/feedback_service.py`.

The service stores article-level decisions in `artifacts/rss/feedback.json` and, when `ARCHIVE_BUCKET` is set, mirrors that file into Cloud Storage. The next Cloud Run Job downloads the same file before scoring, so feedback becomes part of the next report cycle.

Recommended setup:

1. Deploy the scanner as a Cloud Run Job.
2. Deploy `tools/feedback_service.py` as a separate Cloud Run Service.
3. Set the feedback service env vars: `ARCHIVE_BUCKET`, `ARCHIVE_PREFIX`, and optionally `FEEDBACK_TOKEN`.
4. Set the scanner job env vars: `FEEDBACK_BASE_URL` and the same `FEEDBACK_TOKEN`.

`FEEDBACK_TOKEN` is optional, but recommended for public email links. It is not user authentication; it is a lightweight guard so random public requests cannot write preference data.

## Deploy feedback loop

After the scanner job image has been updated, deploy the feedback endpoint as a Cloud Run Service.

```bash
FEEDBACK_TOKEN="$(openssl rand -hex 16)"

gcloud run deploy strategic-signal-feedback \
  --source . \
  --region asia-east1 \
  --service-account signal-archive-job@strategic-signal-scanner.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --command python \
  --args tools/feedback_service.py \
  --set-env-vars ARCHIVE_BUCKET=strategic-signal-scanner-archive,ARCHIVE_PREFIX=signal-archive,FEEDBACK_TOKEN="$FEEDBACK_TOKEN"
```

Copy the service URL from the deploy output, then connect it back to the scheduled scanner job:

```bash
gcloud run jobs update strategic-signal-scanner \
  --region asia-east1 \
  --update-env-vars FEEDBACK_BASE_URL=https://your-feedback-service-url,FEEDBACK_TOKEN="$FEEDBACK_TOKEN"
```

Run one manual job execution after updating the env vars. The new report should show `喜欢这篇` and `不相关` on each item.

## Switch groups

To change the run group on Cloud Run:

```bash
gcloud run jobs update strategic-signal-scanner \
  --region asia-east1 \
  --set-env-vars RUN_GROUP=balanced_plus
```

Other useful values:

- `balanced`
- `balanced_plus`
- `ai_native_product`
- `fast`
- `upstream`

## Local smoke test

Run this from the repository root.

```bash
SCORE_MODE=mock RUN_GROUP=cloudrun ITEMS_PER_FEED=1 MAX_ARTICLES=5 OUTPUT_DIR=/tmp/strategy-agent-cloudrun python3 tools/cloudrun_job.py
```

## Related docs

- [groups.md](groups.md)
- [quickstart.md](../docs/quickstart.md)
