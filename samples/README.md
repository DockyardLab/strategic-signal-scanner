# Sample format

Each sample is a single JSON file with this shape:

```json
{
  "id": "unique_id",
  "input": {
    "title": "original title",
    "source": "source name",
    "date": "YYYY-MM-DD",
    "url": "original url",
    "content": "short article excerpt or notes"
  },
  "expected": {
    "tier": 1,
    "signal_type": "AI趋势",
    "relevance_score": 4
  },
  "note": "why this sample matters"
}
```

Keep `input.content` short and focused. The goal is to test relevance judgment, not to simulate full articles.
