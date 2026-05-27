# Strategic Signal Scanner · Local Replay

This is the smallest low-cost test loop for the signal scanner.

## What it does

- Reads sample JSON files from `samples/`
- Runs a local mock judgment by default
- Compares `expected` vs `actual`
- Prints a short report
- Costs zero API tokens in mock mode

## Run it

```bash
cd "/Users/rosy/Documents/New project"
python3 signal_replay.py --samples samples
```

## Useful options

Run a single sample:

```bash
python3 signal_replay.py --samples samples/001_mckinsey_superagency.json
```

Limit how many samples to replay:

```bash
python3 signal_replay.py --samples samples --limit 2
```

Print JSON instead of text:

```bash
python3 signal_replay.py --samples samples --json
```

Retryable errors and raw response debug:

```bash
python3 signal_replay.py --samples samples --mode gemini --model gemini-3.1-flash-lite-preview --retry-attempts 5 --debug-response
```

## Optional Gemini mode

When you want to spend a small amount of credit later:

```bash
export GEMINI_API_KEY="your_key"
python3 signal_replay.py --samples samples --mode gemini --model gemini-3.1-flash-lite-preview
```

If `google-genai` is not installed, stay in `mock` mode first.

## What to look at

- `relevance_score`
- `signal_type`
- `tier`
- `reason`
- `key_signal`

If mock mode is already close to your expected labels, the prompt and sample set are in good shape.
