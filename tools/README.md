# Tools

This folder contains the runnable implementation scripts for Strategic Signal Scanner.

## What lives here

- `capture_and_score.py`: one-command capture + scoring pipeline
- `rss_capture.py`: capture-only pipeline
- `score_raw_rss.py`: score an existing raw file
- `build_report.py`: render the daily HTML report
- `build_archive.py`: render the browsable archive index
- `cloudrun_job.py`: Google Cloud Run Job entrypoint
- `signal_replay.py`: local replay and evaluation helper
- `youtube_to_raw.py`: convert a YouTube transcript into a raw scanner item

## How to run

Run these scripts from the repository root so the relative paths in the docs stay simple.

Examples:

```bash
python3 tools/capture_and_score.py --group balanced --items-per-feed 1 --max-articles 10 --score-mode mock
python3 tools/build_report.py --scored-file artifacts/rss/scored_YYYY-MM-DD.json
python3 tools/cloudrun_job.py
```

## Notes

- Shared modules still live at the repository root: `fetcher.py`, `mailer.py`, `sources.py`, and `state.py`.
- The Cloud Run / archive / smoke-test docs are in `cloudrun/` and `smoke-tests/`.
