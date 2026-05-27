# Quickstart

This is the fastest way to try Strategic Signal Scanner locally.

Run these commands from the repository root.

## 1. Run the balanced public default

```bash
python3 tools/capture_and_score.py --group balanced --items-per-feed 1 --max-articles 10 --score-mode mock
```

## 2. Try the richer public variant

```bash
python3 tools/capture_and_score.py --group balanced_plus --items-per-feed 1 --max-articles 10 --score-mode mock
```

## 3. Try the AI Native Product focus

```bash
python3 tools/capture_and_score.py --group ai_native_product --items-per-feed 1 --max-articles 12 --score-mode mock
```

## 4. Build a report from a scored file

```bash
python3 tools/build_report.py --scored-file artifacts/rss/scored_YYYY-MM-DD.json
```

## 5. Build the archive

```bash
python3 tools/build_archive.py --artifact-dir artifacts/rss --output artifacts/rss/archive_index.html
```

## 6. Cloud Run smoke test

```bash
SCORE_MODE=mock RUN_GROUP=cloudrun ITEMS_PER_FEED=1 MAX_ARTICLES=5 OUTPUT_DIR=/tmp/strategy-agent-cloudrun python3 tools/cloudrun_job.py
```

## Where to read next

- [cloudrun/README.md](../cloudrun/README.md)
- [cloudrun/groups.md](../cloudrun/groups.md)
