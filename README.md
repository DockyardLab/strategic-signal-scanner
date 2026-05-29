# Strategic Signal Scanner

Dockyard Lab public version.

A modular Google Cloud Run Job pipeline for capturing, scoring, archiving, and emailing high-signal information.

## Start here

- [Quickstart](docs/quickstart.md)
- [Cloud Run guide](cloudrun/README.md)
- [Tools guide](tools/README.md)

## What this repo contains

- `tools/`: the runnable implementation scripts for capture, scoring, reporting, archive generation, replay, and the Cloud Run Job entrypoint
- `fetcher.py`, `mailer.py`, `sources.py`, and `state.py`: shared pipeline modules
- `cloudrun/`: Google Cloud Run deployment notes
- `smoke-tests/`: development and replay notes
- `samples/`: a small set of sample inputs

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

## Feedback loop

The HTML report includes feedback links for each item when `FEEDBACK_BASE_URL` is set.

- `like` increases the chance that similar items stay visible
- `dislike` hides the item from future reports and downranks similar content

The feedback service writes to `artifacts/rss/feedback.json` and can sync that state to Cloud Storage alongside the reports.

Typical setup:

```bash
FEEDBACK_BASE_URL=https://your-feedback-service-url
```

## Repository layout

- `tools/capture_and_score.py`: one-command capture + scoring pipeline
- `tools/rss_capture.py`: capture-only pipeline
- `tools/score_raw_rss.py`: score an existing raw file
- `tools/build_report.py`: render HTML report
- `tools/build_archive.py`: render browsable archive
- `tools/cloudrun_job.py`: Google Cloud Run Job entrypoint
- `tools/feedback_service.py`: lightweight feedback collector for report clicks
- `tools/signal_replay.py`: local replay and evaluation helper
- `tools/youtube_to_raw.py`: convert a YouTube transcript into a raw scanner item
- `cloudrun/`: Google Cloud Run-specific docs
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

For local usage and Google Cloud deployment details, start with:

- [quickstart.md](docs/quickstart.md)
- [cloudrun/README.md](cloudrun/README.md)
- [smoke-tests/README.md](smoke-tests/README.md)
