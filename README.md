# Strategic Signal Scanner

Dockyard Lab public version.

A modular Google Cloud Run Job pipeline for capturing, scoring, archiving, and emailing high-signal information.

## Start here

- [Quickstart](quickstart.md)
- [Cloud Run guide](cloudrun/README.md)

## What this repo contains

- Python pipeline code for capture, scoring, reporting, and archive generation
- Google Cloud Run Job entrypoint
- Source group definitions
- A small set of sample inputs
- Minimal docs for local use and Google Cloud deployment

## Default behavior

The public default entrypoint is `cloudrun`, which maps to the balanced source group.

If you want a richer reading list, switch to `balanced_plus`.
If you want the Anthropic / Claude / Lenny-focused version, switch to `ai_native_product`.

## Google Cloud stack

This project is built around the Google Cloud stack:

- **Google Cloud Run Job** for scheduled batch execution
- **Vertex AI** for Gemini-based relevance scoring
- **Cloud Storage** for report and archive persistence
- **Cloud Scheduler** for timed execution

## Repository layout

- `capture_and_score.py`: one-command capture + scoring pipeline
- `rss_capture.py`: capture-only pipeline
- `score_raw_rss.py`: score an existing raw file
- `build_report.py`: render HTML report
- `build_archive.py`: render browsable archive
- `cloudrun_job.py`: Google Cloud Run Job entrypoint
- `cloudrun/`: Cloud Run-specific docs
- `smoke-tests/`: smoke test and development flow notes
- `samples/`: minimal sample inputs

## Safety notes

Do not commit:

- API keys
- App Passwords
- Secret values
- personal emails
- real project IDs
- real bucket names

## License

This repo uses `LICENSE` at the root.

## How to use it

For local usage and Cloud Run deployment details, start with:

- [quickstart.md](quickstart.md)
- [cloudrun/README.md](cloudrun/README.md)
- [smoke-tests/README.md](smoke-tests/README.md)
