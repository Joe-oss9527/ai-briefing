
import time
import datetime as dt
import requests
from typing import List, Dict, Any
from briefing.utils import clean_text, get_logger, normalize_http_url

logger = get_logger(__name__)

BASE = "https://hacker-news.firebaseio.com/v0"

def _story_ids(story_type: str) -> List[int]:
    if story_type == "new":
        path = "newstories"
    elif story_type == "best":
        path = "beststories"
    else:
        path = "topstories"
    url = f"{BASE}/{path}.json"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json() or []

def _get_item(item_id: int) -> dict:
    url = f"{BASE}/item/{item_id}.json"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json() or {}

def fetch(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    story_type = source_config.get("hn_story_type", "top")
    limit = int(source_config.get("hn_limit", 50))
    ids = _story_ids(story_type)[:limit]

    items: List[Dict[str, Any]] = []
    for sid in ids:
        js = _get_item(sid)
        if not js or js.get("type") != "story":
            continue
        title = js.get("title") or ""
        text = js.get("text") or ""
        # URL processing with validation
        raw_url = js.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        url = normalize_http_url(raw_url)
        if not url:
            logger.warning("hackernews_adapter: drop item %s due to invalid url", sid)
            continue

        author = js.get("by") or "Unknown"
        created = js.get("time", int(time.time()))
        ts = dt.datetime.utcfromtimestamp(created).replace(tzinfo=dt.timezone.utc)

        content = clean_text(f"{title}\n\n{text}")
        if not content:
            logger.warning("hackernews_adapter: drop item %s due to empty content after cleaning", sid)
            continue

        items.append({
            "id": str(sid),
            "text": content,
            "url": url,
            "author": author,
            "timestamp": ts.isoformat(),
            "metadata": {"source": "hackernews", "score": js.get("score")}
        })

    logger.info("hackernews_adapter fetched_items=%d type=%s", len(items), story_type)
    return items

