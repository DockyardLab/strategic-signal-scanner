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
```

## Feedback service

If you want the report buttons to record `like` / `dislike` clicks, deploy the companion feedback service from `tools/feedback_service.py`.

The service stores its state in `artifacts/rss/feedback.json` and, when `ARCHIVE_BUCKET` is set, mirrors that file into Cloud Storage.

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
