"""Source list for Strategic Signal Scanner."""

from __future__ import annotations

# Nine groups:
# - FRONT: the people / official blogs the user wants to see first
# - YOUTUBE_FRONT: the YouTube channels the user explicitly asked to subscribe to
# - UPSTREAM_BUILDERS: curated follow-builders feeds we subscribe to as an upstream detector
# - CLOUDRUN: the default bundled production scan set for Cloud Run Jobs
# - FAST_HIGH_SIGNAL: should usually run next
# - PODCASTS_RSS: podcast sources with real RSS feeds
# - PODCASTS_WEB: podcast or interview sources that are better scraped from web pages
# - SLOW_RESEARCH: useful but more likely to time out or be noisier
# - LATE_THOUGHT_LEADERS: valuable sources, but placed after the main list

FRONT: list[dict[str, object]] = [
    {"name": "Paul Graham", "url": "https://x.com/paulg", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Google Labs", "url": "https://labs.google/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Claude", "url": "https://x.com/claudeai", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Peter Yang", "url": "https://creatoreconomy.so/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Amanda Askell", "url": "https://x.com/AmandaAskell", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news", "type": "web", "tier": 1, "refresh_hours": 336},
    {"name": "Anthropic Research", "url": "https://www.anthropic.com/research", "type": "web", "tier": 1, "refresh_hours": 336},
    {"name": "Anthropic Engineering", "url": "https://www.anthropic.com/engineering", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Claude Blog", "url": "https://claude.com/blog", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Andrej Karpathy", "url": "https://karpathy.ai/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "AI Builders", "url": "https://followaibuilders.com/", "type": "web", "tier": 1, "refresh_hours": 24},
]

YOUTUBE_FRONT: list[dict[str, object]] = [
    {"name": "Sequoia Capital", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCWrF0oN6unbXrWsTN7RctTw", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Google DeepMind", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCP7jMXSY2xbc3KCAE0MHQ-A", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Andrej Karpathy", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Y Combinator", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCxIJaCMEptJjxmmQgGFsnCg", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Claude", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCV03SRZXJEz-hchIAogeJOg", "type": "rss", "tier": 1, "refresh_hours": 24},
]

# Backward-compatible alias for older commands / docs.
YOUTUBE_CHANNELS = YOUTUBE_FRONT

UPSTREAM_BUILDERS: list[dict[str, object]] = [
    {
        "name": "Follow Builders X Feed",
        "url": "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json",
        "type": "follow_builders_x",
        "tier": 1,
        "refresh_hours": 12,
    },
    {
        "name": "Follow Builders Blogs Feed",
        "url": "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json",
        "type": "follow_builders_blogs",
        "tier": 1,
        "refresh_hours": 24,
    },
    {
        "name": "Follow Builders Podcasts Feed",
        "url": "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json",
        "type": "follow_builders_podcasts",
        "tier": 1,
        "refresh_hours": 84,
    },
]

FAST_HIGH_SIGNAL: list[dict[str, object]] = [
    {"name": "Google DeepMind Blog", "url": "https://deepmind.google/discover/blog/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com/", "type": "web", "tier": 1, "refresh_hours": 24},
    {"name": "YC Blog", "url": "https://www.ycombinator.com/blog", "type": "web", "tier": 2, "refresh_hours": 12},
    {"name": "a16z Enterprise x AI", "url": "https://a16z.com/category/enterprise/enterprise-x-ai/", "type": "web", "tier": 2, "refresh_hours": 24},
    {"name": "a16z Applications", "url": "https://a16z.com/category/enterprise/applications/", "type": "web", "tier": 2, "refresh_hours": 24},
    {"name": "a16z Company Building", "url": "https://a16z.com/category/company-building/", "type": "web", "tier": 2, "refresh_hours": 24},
    {"name": "Sequoia Perspectives", "url": "https://www.sequoiacap.com/perspectives/", "type": "web", "tier": 2, "refresh_hours": 24},
    {"name": "Stratechery", "url": "https://stratechery.com/feed/", "type": "rss", "tier": 2, "refresh_hours": 24},
    {"name": "Sequoia Capital", "url": "https://www.sequoiacap.com/feed/", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "type": "rss", "tier": 3, "refresh_hours": 1},
]

PODCASTS_RSS: list[dict[str, object]] = [
    {"name": "Latent Space", "url": "https://api.substack.com/feed/podcast/1084089.rss", "type": "rss", "tier": 1, "refresh_hours": 84},
    {"name": "No Priors", "url": "https://rss.art19.com/no-priors-ai", "type": "rss", "tier": 1, "refresh_hours": 84},
    {"name": "Unsupervised Learning with Jacob Effron", "url": "https://feeds.simplecast.com/dOSE_bdP", "type": "rss", "tier": 1, "refresh_hours": 84},
    {"name": "The MAD Podcast with Matt Turck", "url": "https://anchor.fm/s/f2ee4948/podcast/rss", "type": "rss", "tier": 1, "refresh_hours": 84},
    {"name": "AI & I", "url": "https://anchor.fm/s/ed1f5584/podcast/rss", "type": "rss", "tier": 1, "refresh_hours": 84},
]

PODCASTS_WEB: list[dict[str, object]] = [
    {"name": "Training Data", "url": "https://rss.com/podcasts/trainingdata/", "type": "web", "tier": 1, "refresh_hours": 84},
]

SLOW_RESEARCH: list[dict[str, object]] = [
    {"name": "McKinsey Insights", "url": "https://www.mckinsey.com/our-insights", "type": "web", "tier": 1, "timeout_seconds": 30, "refresh_hours": 336},
    {"name": "McKinsey Tech & AI", "url": "https://www.mckinsey.com/business-functions/mckinsey-digital/our-insights", "type": "web", "tier": 1, "timeout_seconds": 30, "refresh_hours": 336},
    {"name": "AWS Machine Learning Blog", "url": "https://aws.amazon.com/blogs/ai/feed/", "type": "rss", "tier": 2, "refresh_hours": 24},
    {"name": "Allen Institute for Artificial Intelligence (AI2) - YouTube", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCEqgmyWChwvt6MFGGlmUQCQ", "type": "rss", "tier": 2, "refresh_hours": 24},
    {"name": "MIRI Blog", "url": "https://intelligence.org/blog/feed/", "type": "rss", "tier": 2, "refresh_hours": 72},
    {"name": "fast.ai", "url": "http://www.fast.ai/atom.xml?format=xml", "type": "rss", "tier": 2, "refresh_hours": 24},
    {"name": "Berkeley AI Research Blog", "url": "http://bair.berkeley.edu/blog/feed.xml", "type": "rss", "tier": 2, "refresh_hours": 72},
    {"name": "MIT CSAIL - YouTube", "url": "https://www.youtube.com/feeds/videos.xml?user=MITCSAIL", "type": "rss", "tier": 2, "refresh_hours": 24},
    {"name": "Distill", "url": "https://distill.pub/rss.xml", "type": "rss", "tier": 2, "refresh_hours": 72},
    {"name": "Every", "url": "https://every.to/", "type": "web", "tier": 3, "refresh_hours": 24},
    {"name": "Lenny's Newsletter", "url": "https://www.lennysnewsletter.com/", "type": "web", "tier": 3, "refresh_hours": 24},
    {"name": "The Atlantic Tech", "url": "https://www.theatlantic.com/technology/", "type": "web", "tier": 3, "refresh_hours": 24},
    {"name": "Lightspeed Perspectives", "url": "https://lsvp.com/perspectives/", "type": "web", "tier": 2, "refresh_hours": 24},
]

LATE_THOUGHT_LEADERS: list[dict[str, object]] = [
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Dwarkesh Patel", "url": "https://www.dwarkeshpatel.com/feed", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Geoffrey Litt", "url": "https://www.geoffreylitt.com/feed.xml", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Mitchell Hashimoto", "url": "https://mitchellh.com/feed.xml", "type": "rss", "tier": 1, "refresh_hours": 24},
    {"name": "Sean Goedecke", "url": "https://www.seangoedecke.com/rss.xml", "type": "rss", "tier": 1, "refresh_hours": 24},
]

RSS_FEEDS: list[dict[str, object]] = FRONT + YOUTUBE_FRONT + UPSTREAM_BUILDERS + FAST_HIGH_SIGNAL + PODCASTS_RSS + PODCASTS_WEB + SLOW_RESEARCH + LATE_THOUGHT_LEADERS

# Cloud Run default: a compact but high-signal batch that is practical for scheduled jobs.
CLOUDRUN: list[dict[str, object]] = FRONT + YOUTUBE_FRONT + UPSTREAM_BUILDERS + FAST_HIGH_SIGNAL

DEFAULT_ITEMS_PER_FEED = 5

SOURCE_GROUPS: dict[str, list[dict[str, object]]] = {
    "front": FRONT,
    "youtube_front": YOUTUBE_FRONT,
    "youtube": YOUTUBE_FRONT,
    "upstream": UPSTREAM_BUILDERS,
    "fast": FAST_HIGH_SIGNAL,
    "podcasts": PODCASTS_RSS + PODCASTS_WEB,
    "podcasts_rss": PODCASTS_RSS,
    "podcasts_web": PODCASTS_WEB,
    "slow": SLOW_RESEARCH,
    "late": LATE_THOUGHT_LEADERS,
    "cloudrun": CLOUDRUN,
    "all": RSS_FEEDS,
}


def get_feeds(group: str = "all") -> list[dict[str, object]]:
    normalized = (group or "all").strip().lower()
    if normalized not in SOURCE_GROUPS:
        raise ValueError(f"Unknown source group: {group}")
    return list(SOURCE_GROUPS[normalized])
